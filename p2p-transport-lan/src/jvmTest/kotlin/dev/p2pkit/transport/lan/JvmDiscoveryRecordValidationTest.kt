package dev.p2pkit.transport.lan

import dev.p2pkit.core.AppId
import dev.p2pkit.core.PeerId
import dev.p2pkit.core.Platform
import dev.p2pkit.core.transport.PeerEvent
import java.net.Inet4Address
import java.net.InetAddress
import java.net.NetworkInterface
import javax.jmdns.JmDNS
import javax.jmdns.ServiceInfo
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.onStart
import kotlinx.coroutines.launch
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withContext
import kotlinx.coroutines.withTimeout
import kotlin.test.AfterTest
import kotlin.test.BeforeTest
import kotlin.test.Test
import kotlin.test.assertTrue
import org.junit.Assume

/**
 * AUDIT-2026-07 (RBS-1) / P1-25 integration leg: crafted-advertiser loopback
 * test for discovery-record input validation in [JvmLanDiscoveryTransport].
 *
 * A separate JmDNS instance (the "crafter") advertises real
 * `_p2pkit._tcp.local.` services with non-conforming TXT records — a
 * whitespace-only `pid` value and a record for a different appId — alongside
 * conforming ones. The transport under test must:
 *
 *  - never emit a `PeerEvent` for the malformed (blank-pid) record, on the
 *    found or the removed path;
 *  - never emit a `PeerEvent` for the other-app record on either path (the
 *    removed-path appId gate is new in RBS-1; the found path already had it);
 *  - keep delivering events for conforming records after processing the
 *    malformed input on both paths — i.e. no exception escapes the JmDNS
 *    callbacks and the listener worker stays alive. This settles the
 *    register's JVM/Android listener-thread-disposition residual.
 *
 * Removed-path observability note: with JmDNS 3.6.3, goodbye (TTL=0)
 * removals deliver `serviceRemoved` events whose `info` carries no TXT data
 * (the record set is already expired when the PTR removal is dispatched), so
 * the removed path skips every record at the pid validation and a
 * `PeerEvent.Lost` anchor is not observable over real goodbyes — peer
 * disappearance on JVM is covered by PeerRegistry staleness eviction. The
 * removed-path callbacks are therefore observed via [JvmLanDiag]'s replayed
 * trace (the transport's designed observation channel), and callback
 * survival is proven by a fresh conforming registration discovered *after*
 * the removals were processed.
 *
 * Like [JvmLanLoopbackTest], this depends on multicast working on the test
 * machine and skips (Assume) when no routable IPv4 interface is available.
 */
class JvmDiscoveryRecordValidationTest {

    private val unique = "p2pkit-rbs1-${System.currentTimeMillis()}"
    private var bindAddress: String? = null
    private var diagWasEnabled: Boolean = false

    @BeforeTest
    fun setup() {
        val routable = findRoutableIpv4()
        Assume.assumeTrue(
            "No routable IPv4 interface available for JmDNS loopback test",
            routable != null
        )
        bindAddress = routable
        System.setProperty(JMDNS_BIND_PROPERTY, routable!!)
        // The removed path emits no PeerEvent over real JmDNS goodbyes (see
        // class KDoc), so its callbacks are observed via the trace channel.
        diagWasEnabled = JvmLanDiag.enabled
        JvmLanDiag.enabled = true
    }

    @AfterTest
    fun teardown() {
        JvmLanDiag.enabled = diagWasEnabled
        System.clearProperty(JMDNS_BIND_PROPERTY)
    }

    @Test
    fun malformedAndOtherAppRecordsAreSkippedWhileConformingRecordsStillFlow() {
        runBlocking {
            val conformingPid = "conforming-$unique"
            val postRemovalPid = "post-removal-$unique"
            val otherAppPid = "other-app-$unique"

            val registration = LanServiceRegistration(
                appId = AppId(unique),
                localPeerId = PeerId("observer-$unique"),
                deviceName = "Observer",
                platform = Platform.JVM_DESKTOP,
                tcpPort = 45000
            )
            val transport = JvmLanDiscoveryTransport(registration)
            val seen = mutableListOf<PeerEvent>()
            val subscribed = CompletableDeferred<Unit>()
            val collector = launch {
                transport.events
                    // onStart (not onSubscription — `events` is typed Flow):
                    // on runBlocking's single-threaded event loop the
                    // collector registers its subscription before the awaiting
                    // parent resumes, so no event can be missed.
                    .onStart { subscribed.complete(Unit) }
                    .collect { event -> synchronized(seen) { seen.add(event) } }
            }
            subscribed.await()
            transport.startDiscovery()

            val crafter = withContext(Dispatchers.IO) {
                JmDNS.create(InetAddress.getByName(bindAddress))
            }
            try {
                val blankPidService = craftedService(
                    instanceName = "blank-pid-$unique",
                    port = 45001,
                    pid = " ", // whitespace-only: passes a null check, rejected by PeerId()
                    app = unique,
                    deviceName = "BlankPid"
                )
                val otherAppService = craftedService(
                    instanceName = "other-app-$unique",
                    port = 45002,
                    pid = otherAppPid,
                    app = "$unique-other",
                    deviceName = "OtherApp"
                )
                val conformingService = craftedService(
                    instanceName = "conforming-$unique",
                    port = 45003,
                    pid = conformingPid,
                    app = unique,
                    deviceName = "Conforming"
                )
                withContext(Dispatchers.IO) {
                    // Non-conforming records first, so the listener processes
                    // them before (or alongside) the conforming one — the
                    // conforming events arriving proves the callback survived
                    // the malformed input.
                    crafter.registerService(blankPidService)
                    crafter.registerService(otherAppService)
                    crafter.registerService(conformingService)
                }

                // Found path: the conforming record still resolves and emits
                // even though the blank-pid record went through the same
                // serviceResolved callback.
                awaitCondition {
                    synchronized(seen) {
                        seen.any { it is PeerEvent.Found && pidOf(it) == conformingPid }
                    }
                }

                // Removed path: goodbye all three. Each processed removal is
                // visible on the trace channel; none may emit a PeerEvent for
                // the non-conforming records, and none may throw.
                withContext(Dispatchers.IO) {
                    crafter.unregisterService(blankPidService)
                    crafter.unregisterService(otherAppService)
                    crafter.unregisterService(conformingService)
                }
                awaitCondition {
                    JvmLanDiag.events.replayCache.count { "serviceRemoved" in it } >= 2
                }

                // Listener survival after the removed-path callbacks: a fresh
                // conforming record must still be discovered.
                val postRemovalService = craftedService(
                    instanceName = "post-removal-$unique",
                    port = 45004,
                    pid = postRemovalPid,
                    app = unique,
                    deviceName = "PostRemoval"
                )
                withContext(Dispatchers.IO) { crafter.registerService(postRemovalService) }
                awaitCondition {
                    synchronized(seen) {
                        seen.any { it is PeerEvent.Found && pidOf(it) == postRemovalPid }
                    }
                }

                val snapshot = synchronized(seen) { seen.toList() }
                assertTrue(
                    snapshot.none { pidOf(it).isBlank() },
                    "no event may carry a blank peer id: $snapshot"
                )
                assertTrue(
                    snapshot.none { pidOf(it) == otherAppPid },
                    "a record advertising another appId must not emit Found or Lost: $snapshot"
                )
            } finally {
                withContext(Dispatchers.IO) { runCatching { crafter.close() } }
                runCatching { transport.stopDiscovery() }
                collector.cancel()
            }
        }
    }

    private fun craftedService(
        instanceName: String,
        port: Int,
        pid: String,
        app: String,
        deviceName: String
    ): ServiceInfo = ServiceInfo.create(
        LanConstants.SERVICE_TYPE_JMDNS,
        instanceName,
        port,
        /* weight = */ 0,
        /* priority = */ 0,
        mapOf(
            LanConstants.TXT_PEER_ID to pid,
            LanConstants.TXT_APP_ID to app,
            LanConstants.TXT_DEVICE_NAME to deviceName,
            LanConstants.TXT_PLATFORM to Platform.JVM_DESKTOP.name,
            LanConstants.TXT_CAPABILITIES to "LAN",
            LanConstants.TXT_PROTOCOL_VERSION to LanConstants.PROTOCOL_VERSION.toString()
        )
    )

    private suspend fun awaitCondition(condition: () -> Boolean) {
        withTimeout(DISCOVERY_TIMEOUT_MS) {
            while (!condition()) {
                delay(100)
            }
        }
    }

    private fun pidOf(event: PeerEvent): String = when (event) {
        is PeerEvent.Found -> event.peer.publicPeer.id.value
        is PeerEvent.Updated -> event.peer.publicPeer.id.value
        is PeerEvent.Lost -> event.peerId.value
    }

    private companion object {
        const val DISCOVERY_TIMEOUT_MS: Long = 30_000
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
