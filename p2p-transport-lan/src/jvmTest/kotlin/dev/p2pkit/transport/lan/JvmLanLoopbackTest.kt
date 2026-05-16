package dev.p2pkit.transport.lan

import dev.p2pkit.core.AppId
import dev.p2pkit.core.P2pKit
import dev.p2pkit.core.P2pMessage
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.async
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.onSubscription
import kotlinx.coroutines.launch
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withTimeout
import java.io.File
import java.nio.file.Files
import kotlin.test.AfterTest
import kotlin.test.Test
import kotlin.test.assertContentEquals
import kotlin.test.assertEquals
import kotlin.test.assertIs

/**
 * Integration test: two [P2pKit] instances on `127.0.0.1`, both using the
 * `lan()` transport, discover each other via mDNS and exchange messages over
 * TCP.
 *
 * This test depends on multicast working on the test machine (UDP 5353 to
 * 224.0.0.251). Most desktops are fine; corporate or hardened networks may
 * block multicast even on loopback. Allow up to 30 s for discovery.
 */
class JvmLanLoopbackTest {

    private val unique = "p2pkit-itest-${System.currentTimeMillis()}"

    private fun newKit(name: String): P2pKit = P2pKit.create {
        appId = AppId(unique)
        deviceName = name
        keepAlive {
            pingIntervalMillis = 60_000
            timeoutMillis = 120_000
        }
        transports {
            lan()
        }
    }

    private val toStop = mutableListOf<P2pKit>()
    private val tempHomes = mutableListOf<File>()

    @AfterTest
    fun teardown() = runBlocking {
        toStop.forEach { runCatching { it.stop() } }
        toStop.clear()
        tempHomes.forEach { runCatching { it.deleteRecursively() } }
        tempHomes.clear()
    }

    /**
     * Construct a [P2pKit] under a per-call temporary `user.home`. This forces
     * the default JVM [dev.p2pkit.core.internal.PeerIdStorage] to write under a
     * fresh directory, so two kits in the same JVM (sharing an `appId`) end up
     * with **different** `PeerId`s — otherwise each would filter the other
     * out of mDNS results as "self". The `user.home` swap is restored
     * synchronously after [P2pKit.create] returns; the kit captures its
     * `PeerId` at construction so later `user.home` changes don't affect it.
     */
    private suspend fun startAndAdvertise(name: String): P2pKit {
        val savedHome = System.getProperty("user.home")
        val tempHome = Files.createTempDirectory("p2pkit-itest-${name}-").toFile()
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

    @Test
    fun twoKitsDiscoverEachOtherAndExchangeText() {
        runBlocking {
            val alice = startAndAdvertise("Alice")
            val bob = startAndAdvertise("Bob")

            val bobAsSeenByAlice = withTimeout(DISCOVERY_TIMEOUT_MS) {
                alice.peers.first { peers -> peers.any { it.name == "Bob" } }
                    .first { it.name == "Bob" }
            }

            val outgoingDeferred = async { alice.connect(bobAsSeenByAlice) }
            val incomingSession = withTimeout(HANDSHAKE_TIMEOUT_MS) { bob.incomingSessions.first() }
            val outgoing = withTimeout(HANDSHAKE_TIMEOUT_MS) { outgoingDeferred.await() }

            assertEquals("Alice", incomingSession.peer.name)
            assertEquals("Bob", outgoing.peer.name)

            // Alice → Bob text
            val ready = CompletableDeferred<Unit>()
            val received = async {
                incomingSession.incoming.onSubscription { ready.complete(Unit) }.first()
            }
            ready.await()
            outgoing.send(P2pMessage.Text("hi from Alice"))
            val msg = assertIs<P2pMessage.Text>(withTimeout(MESSAGE_TIMEOUT_MS) { received.await() })
            assertEquals("hi from Alice", msg.value)
        }
    }

    @Test
    fun largeBinaryPayloadRoundTripsOverTcp() {
        runBlocking {
            val alice = startAndAdvertise("Alice")
            val bob = startAndAdvertise("Bob")

            val bobAsSeenByAlice = withTimeout(DISCOVERY_TIMEOUT_MS) {
                alice.peers.first { peers -> peers.any { it.name == "Bob" } }
                    .first { it.name == "Bob" }
            }
            val outgoingDeferred = async { alice.connect(bobAsSeenByAlice) }
            val incomingSession = withTimeout(HANDSHAKE_TIMEOUT_MS) { bob.incomingSessions.first() }
            val outgoing = withTimeout(HANDSHAKE_TIMEOUT_MS) { outgoingDeferred.await() }

            // 200 KB — well over the default 64 KB chunk size, so this also
            // exercises chunking + reassembly over a real TCP socket.
            val payload = ByteArray(200 * 1024) { (it and 0xFF).toByte() }

            val ready = CompletableDeferred<Unit>()
            val received = async {
                outgoing.incoming.onSubscription { ready.complete(Unit) }.first()
            }
            ready.await()
            incomingSession.send(P2pMessage.Binary(payload))
            val bin = assertIs<P2pMessage.Binary>(withTimeout(MESSAGE_TIMEOUT_MS) { received.await() })
            assertContentEquals(payload, bin.bytes)
        }
    }

    private companion object {
        const val DISCOVERY_TIMEOUT_MS: Long = 30_000
        const val HANDSHAKE_TIMEOUT_MS: Long = 10_000
        const val MESSAGE_TIMEOUT_MS: Long = 10_000
    }
}
