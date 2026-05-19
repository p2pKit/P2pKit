package dev.p2pkit.transport.lan

import dev.p2pkit.core.AppId
import dev.p2pkit.core.P2pKit
import dev.p2pkit.core.P2pMessage
import dev.p2pkit.core.transfer.FileTransferState
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.async
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.onSubscription
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withTimeout
import kotlinx.io.Buffer
import kotlinx.io.readByteArray
import kotlinx.io.write
import kotlin.test.AfterTest
import kotlin.test.Test
import kotlin.test.assertContentEquals
import kotlin.test.assertEquals
import kotlin.test.assertIs
import platform.Foundation.NSDate
import platform.Foundation.NSUserDefaults
import platform.Foundation.timeIntervalSince1970

/**
 * Integration test: two [P2pKit] instances in one process, both using the
 * iOS `lan()` transport, discover each other via `NWBrowser` /
 * `nw_listener_set_advertise_descriptor` and exchange messages over
 * `NWConnection`.
 *
 * Runs on `iosSimulatorArm64Test`. Mirrors `JvmLanLoopbackTest` in shape —
 * text + 200 KB binary + 5 MiB file round-trip — so any regression on
 * iOS lights up the same matrix the JVM/Android pipeline catches.
 *
 * Two kits in one process would normally share an `NSUserDefaults`-backed
 * `PeerId` (same `appId` → same key). [removeStoredPeerId] clears that key
 * before each kit construction so each [NSUserDefaultsPeerIdStorage] mints a
 * fresh UUID. Once the kit captures its id during construction, later
 * defaults edits don't affect it.
 */
class IosLanLoopbackTest {

    private val unique: String =
        "p2pkit-ios-itest-${NSDate().timeIntervalSince1970.toLong()}"
    private val peerIdKey: String = "dev.p2pkit.peerId.$unique"

    private val toStop: MutableList<P2pKit> = mutableListOf()

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

    private fun removeStoredPeerId() {
        NSUserDefaults.standardUserDefaults.removeObjectForKey(peerIdKey)
    }

    private suspend fun startAndAdvertise(name: String): P2pKit {
        removeStoredPeerId()
        val kit = newKit(name)
        toStop.add(kit)
        kit.startAdvertising()
        kit.startDiscovery()
        return kit
    }

    @AfterTest
    fun teardown() = runBlocking {
        toStop.forEach { runCatching { it.stop() } }
        toStop.clear()
        removeStoredPeerId()
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

            // 200 KB — exercises chunking + reassembly over a real
            // NWConnection. Same payload pattern as the JVM loopback test.
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

    @Test
    fun fileTransferRoundTripsOverTcp() {
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

            // 5 MiB deterministic payload. Streamed in-memory via kotlinx-io
            // Buffer on both sides; the JVM loopback test uses temp files
            // because java.io is more familiar there, but the protocol layer
            // is identical and the LAN socket is the actual unit under test.
            val totalBytes = 5 * 1024 * 1024
            val payload = ByteArray(totalBytes) { ((it * 31) and 0xFF).toByte() }
            val srcBuffer = Buffer().apply { write(payload) }
            val dstBuffer = Buffer()

            val offerReady = CompletableDeferred<Unit>()
            val offerDeferred = async {
                incomingSession.incomingFiles.onSubscription { offerReady.complete(Unit) }.first()
            }
            offerReady.await()

            val transfer = outgoing.sendFile(
                name = "ios-itest.bin",
                sizeBytes = totalBytes.toLong(),
                mimeType = "application/octet-stream",
                source = srcBuffer
            )

            val offer = withTimeout(MESSAGE_TIMEOUT_MS) { offerDeferred.await() }
            val incomingTransfer = offer.accept(dstBuffer)

            val senderFinal = withTimeout(FILE_TRANSFER_TIMEOUT_MS) {
                transfer.state.first { s ->
                    s is FileTransferState.Completed || s is FileTransferState.Failed
                }
            }
            val receiverFinal = withTimeout(FILE_TRANSFER_TIMEOUT_MS) {
                incomingTransfer.state.first { s ->
                    s is FileTransferState.Completed || s is FileTransferState.Failed
                }
            }
            assertIs<FileTransferState.Completed>(senderFinal)
            assertIs<FileTransferState.Completed>(receiverFinal)
            assertEquals(totalBytes.toLong(), transfer.bytesTransferred.value)
            assertContentEquals(payload, dstBuffer.readByteArray())
        }
    }

    private companion object {
        const val DISCOVERY_TIMEOUT_MS: Long = 30_000
        const val HANDSHAKE_TIMEOUT_MS: Long = 15_000
        const val MESSAGE_TIMEOUT_MS: Long = 15_000
        const val FILE_TRANSFER_TIMEOUT_MS: Long = 120_000
    }
}
