package dev.p2pkit.transport.lan

import dev.p2pkit.core.AppId
import dev.p2pkit.core.P2pKit
import dev.p2pkit.core.dsl.jvmSecureIdentityStore
import java.io.File
import java.net.Inet4Address
import java.net.NetworkInterface
import java.nio.file.Files
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withTimeout
import kotlin.test.AfterTest
import kotlin.test.BeforeTest
import kotlin.test.Test
import kotlin.test.assertTrue
import org.junit.Assume

/**
 * LAN discovery lifetime integration: DNS-SD owns TTL/removal and core does
 * not age a healthy native-browser contribution out after 15 seconds.
 *
 * Exact TXT-less removal ownership is covered without UDP timing in
 * [JvmServiceAdmissionsTest]. Real multicast delivery remains exercised by
 * discovery here, while clean/abrupt departure timing is hostile-network
 * evidence rather than a deterministic unit-test clock.
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

    /**
     * Two full kits over real mDNS + loopback-adjacent multicast, no connect
     * activity at all:
     *
     *  1. Bob stays in Alice's `kit.peers` at t = 20 s and t = 35 s idle —
     *     pre-fix he vanished at ~15 s and never returned.
     * Self-gate rider: Alice advertises too, so her own service sits in her
     * JmDNS cache; the self-skip on the native listener keeps her out of her
     * own `kit.peers`.
     */
    @Test
    fun idlePeerSurvivesEvictionHorizon() {
        runBlocking {
            val alice = startAndAdvertise("Alice")
            startAndAdvertise("Bob")

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
                "native discovery must keep skipping the local peer (self gate)"
            )
            delayUntil(foundAt + 35_000)
            assertTrue(
                alice.peers.value.any { it.name == "Bob" },
                "healthy idle peer must still be visible at t=35 s"
            )
        }
    }

    // ── helpers ──────────────────────────────────────────────────────────

    private fun newKit(name: String): P2pKit = P2pKit.create {
        appId = AppId(unique)
        deviceName = name
        jvmSecureIdentityStore(InMemoryTestJvmSecureIdentityStore())
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

    private suspend fun delayUntil(epochMillis: Long) {
        val remaining = epochMillis - System.currentTimeMillis()
        if (remaining > 0) delay(remaining)
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
