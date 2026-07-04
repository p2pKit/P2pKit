package dev.p2pkit.transport.lan

import dev.p2pkit.core.AppId
import dev.p2pkit.core.P2pKit
import dev.p2pkit.core.PeerId
import dev.p2pkit.core.Platform
import dev.p2pkit.core.transport.PeerEvent
import java.io.File
import java.net.Inet4Address
import java.net.InetAddress
import java.net.NetworkInterface
import java.nio.file.Files
import javax.jmdns.JmDNS
import javax.jmdns.ServiceInfo
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.onStart
import kotlinx.coroutines.launch
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withContext
import kotlinx.coroutines.withTimeout
import kotlin.test.AfterTest
import kotlin.test.BeforeTest
import kotlin.test.Test
import kotlin.test.assertTrue
import kotlin.test.fail
import org.junit.Assume

/**
 * AUDIT-2026-07 (DSC-1) / P1-13: JVM discovery heartbeat — while discovery is
 * active the transport re-emits [PeerEvent.Updated] every
 * [LanConstants.PEER_REANNOUNCE_INTERVAL_MS] for every appId-matching service
 * already resolved in the local JmDNS cache, so `PeerRegistry.lastSeen` keeps
 * refreshing and a healthy idle peer survives the registry's 15 s staleness
 * eviction. Pre-fix, `serviceResolved` fired effectively once per service
 * appearance and `kit.peers` silently emptied ~15 s after resolution in
 * steady state (only iOS had a re-announce loop).
 *
 * Two legs, per the coverage row:
 *
 *  - **Transport-level re-emit contract**: periodic `Updated` for a
 *    conforming cached record; the RBS-1 pid validation and the appId gate
 *    apply to re-emits exactly as to `serviceResolved`; the loop halts on
 *    `stopDiscovery`.
 *  - **Kit-level loopback (the P1-13 integration leg)**: a discovered peer
 *    remains in `kit.peers` at t = 20 s and t = 35 s of connect-free idle,
 *    and a departed advertiser (clean stop → mDNS goodbye → cache entry
 *    pruned → no re-emit) still ages out via registry eviction — the JmDNS
 *    goodbye observation (removals carry no TXT, so the Lost path never
 *    fires) makes eviction the only disappearance path on JVM/Android.
 *
 * Like [JvmLanLoopbackTest], this depends on multicast working on the test
 * machine and skips (Assume) when no routable IPv4 interface is available.
 */
class JvmLanDiscoveryHeartbeatTest {

    private val unique = "p2pkit-dsc1-${System.currentTimeMillis()}"
    private var bindAddress: String? = null

    @BeforeTest
    fun setup() {
        val routable = findRoutableIpv4()
        Assume.assumeTrue(
            "No routable IPv4 interface available for JmDNS loopback test",
            routable != null
        )
        bindAddress = routable
        System.setProperty(JMDNS_BIND_PROPERTY, routable!!)
    }

    private val toStop = mutableListOf<P2pKit>()
    private val tempHomes = mutableListOf<File>()

    @AfterTest
    fun teardown() {
        runBlocking {
            toStop.forEach { runCatching { it.stop() } }
            toStop.clear()
            tempHomes.forEach { runCatching { it.deleteRecursively() } }
            tempHomes.clear()
        }
        System.clearProperty(JMDNS_BIND_PROPERTY)
    }

    // ── Transport-level re-emit contract ────────────────────────────────

    private class TimedEvent(val event: PeerEvent, val atMillis: Long)

    @Test
    fun heartbeatReemitsCachedConformingPeersAndHaltsOnStopDiscovery() {
        runBlocking {
            val conformingPid = "conforming-$unique"
            val otherAppPid = "other-app-$unique"

            val registration = LanServiceRegistration(
                appId = AppId(unique),
                localPeerId = PeerId("observer-$unique"),
                deviceName = "Observer",
                platform = Platform.JVM_DESKTOP,
                tcpPort = 46000
            )
            val transport = JvmLanDiscoveryTransport(registration)
            val seen = mutableListOf<TimedEvent>()
            val subscribed = CompletableDeferred<Unit>()
            val collector = launch {
                transport.events
                    .onStart { subscribed.complete(Unit) }
                    .collect { event ->
                        synchronized(seen) { seen.add(TimedEvent(event, System.currentTimeMillis())) }
                    }
            }
            subscribed.await()
            transport.startDiscovery()

            val crafter = withContext(Dispatchers.IO) {
                JmDNS.create(InetAddress.getByName(bindAddress))
            }
            try {
                withContext(Dispatchers.IO) {
                    // Non-conforming records advertised alongside the
                    // conforming one: the heartbeat must never re-emit them
                    // (same RBS-1 pid validation + appId gate as
                    // serviceResolved).
                    crafter.registerService(
                        craftedService("blank-pid-$unique", 46001, pid = " ", app = unique)
                    )
                    crafter.registerService(
                        craftedService("other-app-$unique", 46002, pid = otherAppPid, app = "$unique-other")
                    )
                    crafter.registerService(
                        craftedService("conforming-$unique", 46003, pid = conformingPid, app = unique)
                    )
                }

                // Heartbeat contract: at least two Updated re-emits for the
                // conforming cached record (one per ~5 s tick) after the
                // initial Found.
                awaitCondition("initial Found for the conforming record") {
                    synchronized(seen) {
                        seen.any { it.event is PeerEvent.Found && pidOf(it.event) == conformingPid }
                    }
                }
                awaitCondition("two heartbeat Updated re-emits for the conforming record") {
                    updatedCount(seen, conformingPid) >= 2
                }

                // Gates on the re-emit path: nothing blank, nothing from
                // another appId — on ANY event type.
                val snapshot = synchronized(seen) { seen.map { it.event } }
                assertTrue(
                    snapshot.none { pidOf(it).isBlank() },
                    "no event may carry a blank peer id: $snapshot"
                )
                assertTrue(
                    snapshot.none { pidOf(it) == otherAppPid },
                    "a record advertising another appId must never be re-emitted: $snapshot"
                )

                // Loop lifecycle: stopDiscovery cancels the heartbeat under
                // the transport lock, so no re-emit may arrive after it
                // returns (1 s slack for events buffered before the stop).
                transport.stopDiscovery()
                val quietFrom = System.currentTimeMillis() + 1_000
                delay(2 * LanConstants.PEER_REANNOUNCE_INTERVAL_MS + 2_000)
                val late = synchronized(seen) {
                    seen.filter {
                        it.event is PeerEvent.Updated &&
                            pidOf(it.event) == conformingPid &&
                            it.atMillis > quietFrom
                    }
                }
                assertTrue(
                    late.isEmpty(),
                    "heartbeat must halt on stopDiscovery; saw ${late.size} late re-emit(s)"
                )
            } finally {
                withContext(Dispatchers.IO) { runCatching { crafter.close() } }
                runCatching { transport.stopDiscovery() }
                collector.cancel()
            }
        }
    }

    // ── Kit-level loopback: the P1-13 integration leg ───────────────────

    /**
     * Two full kits over real mDNS + loopback-adjacent multicast, no connect
     * activity at all:
     *
     *  1. Bob stays in Alice's `kit.peers` at t = 20 s and t = 35 s idle —
     *     pre-fix he vanished at ~15 s and never returned.
     *  2. After Bob stops (clean goodbye), Alice's registry still ages him
     *     out — the heartbeat re-emits only cache-present peers, so eviction
     *     keeps working for genuinely departed ones.
     *
     * Self-gate rider: Alice advertises too, so her own service sits in her
     * JmDNS cache; the self-skip on the re-emit path keeps her out of her own
     * `kit.peers`.
     */
    @Test
    fun idlePeerSurvivesEvictionHorizonAndDepartedPeerStillAgesOut() {
        runBlocking {
            val alice = startAndAdvertise("Alice")
            val bob = startAndAdvertise("Bob")

            withTimeout(DISCOVERY_TIMEOUT_MS) {
                alice.peers.first { peers -> peers.any { it.name == "Bob" } }
            }
            val foundAt = System.currentTimeMillis()

            // Idle survival marks (t = 20 s, t = 35 s past first sighting).
            delayUntil(foundAt + 20_000)
            assertTrue(
                alice.peers.value.any { it.name == "Bob" },
                "healthy idle peer must still be visible at t=20 s (past the 15 s eviction horizon)"
            )
            assertTrue(
                alice.peers.value.none { it.name == "Alice" },
                "the re-emit path must keep skipping the local peer (self gate)"
            )
            delayUntil(foundAt + 35_000)
            assertTrue(
                alice.peers.value.any { it.name == "Bob" },
                "healthy idle peer must still be visible at t=35 s"
            )

            // Departure: clean stop → goodbye → cache entry pruned → the
            // heartbeat stops re-emitting Bob → staleness eviction removes
            // him (bounded by 15 s staleness + poll + goodbye slack).
            bob.stop()
            withTimeout(DEPARTURE_TIMEOUT_MS) {
                alice.peers.first { peers -> peers.none { it.name == "Bob" } }
            }
        }
    }

    // ── helpers ──────────────────────────────────────────────────────────

    private fun newKit(name: String): P2pKit = P2pKit.create {
        appId = AppId(unique)
        deviceName = name
        transports {
            lan()
        }
    }

    /** Mirrors [JvmLanLoopbackTest.startAndAdvertise] (per-kit temp `user.home` for distinct PeerIds). */
    private suspend fun startAndAdvertise(name: String): P2pKit {
        val savedHome = System.getProperty("user.home")
        val tempHome = Files.createTempDirectory("p2pkit-dsc1-${name}-").toFile()
        tempHomes.add(tempHome)
        System.setProperty("user.home", tempHome.absolutePath)
        val kit = try {
            newKit(name)
        } finally {
            System.setProperty("user.home", savedHome ?: "")
        }
        toStop.add(kit)
        kit.startAdvertising()
        kit.startDiscovery()
        return kit
    }

    private fun craftedService(
        instanceName: String,
        port: Int,
        pid: String,
        app: String
    ): ServiceInfo = ServiceInfo.create(
        LanConstants.SERVICE_TYPE_JMDNS,
        instanceName,
        port,
        /* weight = */ 0,
        /* priority = */ 0,
        mapOf(
            LanConstants.TXT_PEER_ID to pid,
            LanConstants.TXT_APP_ID to app,
            LanConstants.TXT_DEVICE_NAME to instanceName,
            LanConstants.TXT_PLATFORM to Platform.JVM_DESKTOP.name,
            LanConstants.TXT_CAPABILITIES to "LAN",
            LanConstants.TXT_PROTOCOL_VERSION to LanConstants.PROTOCOL_VERSION.toString()
        )
    )

    private fun updatedCount(seen: List<TimedEvent>, pid: String): Int =
        synchronized(seen) {
            seen.count { it.event is PeerEvent.Updated && pidOf(it.event) == pid }
        }

    private fun pidOf(event: PeerEvent): String = when (event) {
        is PeerEvent.Found -> event.peer.publicPeer.id.value
        is PeerEvent.Updated -> event.peer.publicPeer.id.value
        is PeerEvent.Lost -> event.peerId.value
    }

    private suspend fun awaitCondition(what: String, condition: () -> Boolean) {
        val deadline = System.currentTimeMillis() + DISCOVERY_TIMEOUT_MS
        while (!condition()) {
            if (System.currentTimeMillis() > deadline) fail("timed out waiting for: $what")
            delay(100)
        }
    }

    private suspend fun delayUntil(epochMillis: Long) {
        val remaining = epochMillis - System.currentTimeMillis()
        if (remaining > 0) delay(remaining)
    }

    private companion object {
        const val DISCOVERY_TIMEOUT_MS: Long = 30_000

        /**
         * Departure bound: worst case is a heartbeat tick right before the
         * goodbye (lastSeen refreshed at T) → eviction at T + 15 s staleness
         * + 1 s poll, plus goodbye processing slack. 30 s is comfortable
         * without masking a broken eviction path.
         */
        const val DEPARTURE_TIMEOUT_MS: Long = 30_000
        const val JMDNS_BIND_PROPERTY: String = "dev.p2pkit.test.jmdnsBindAddress"

        /** Mirrors [JvmLanLoopbackTest]'s interface selection. */
        fun findRoutableIpv4(): String? {
            val interfaces = NetworkInterface.getNetworkInterfaces() ?: return null
            for (iface in interfaces) {
                if (!iface.isUp || iface.isLoopback) continue
                for (addr in iface.inetAddresses) {
                    if (addr !is Inet4Address) continue
                    if (addr.isLoopbackAddress || addr.isLinkLocalAddress) continue
                    return addr.hostAddress
                }
            }
            return null
        }
    }
}
