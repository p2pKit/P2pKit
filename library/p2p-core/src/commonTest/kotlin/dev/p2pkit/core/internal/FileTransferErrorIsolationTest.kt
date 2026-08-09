package dev.p2pkit.core.internal

import dev.p2pkit.core.AppId
import dev.p2pkit.core.ConnectionState
import dev.p2pkit.core.FileTransferFailureKind
import dev.p2pkit.core.FileTransferPhase
import dev.p2pkit.core.P2pError
import dev.p2pkit.core.P2pKit
import dev.p2pkit.core.P2pMessage
import dev.p2pkit.core.Peer
import dev.p2pkit.core.PeerId
import dev.p2pkit.core.Platform
import dev.p2pkit.core.Retryability
import dev.p2pkit.core.TransportKind
import dev.p2pkit.core.testfixtures.FakeConnectionPair
import dev.p2pkit.core.testfixtures.FakeDataTransport
import dev.p2pkit.core.testfixtures.createTestKit
import dev.p2pkit.core.transfer.FileTransferState
import dev.p2pkit.core.transport.RawConnection
import dev.p2pkit.core.transport.TransportContext
import dev.p2pkit.core.transport.TransportFactory
import dev.p2pkit.core.transport.TransportPair
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.async
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.onSubscription
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withTimeout
import kotlinx.io.Buffer
import kotlinx.io.IOException
import kotlinx.io.RawSink
import kotlinx.io.readByteArray
import kotlinx.io.write
import kotlin.test.Test
import kotlin.test.assertContentEquals
import kotlin.test.assertEquals
import kotlin.test.assertIs
import kotlin.test.assertTrue

/**
 * Error-isolation guarantees for file transfers (AUDIT-2026-06 #3): a failure
 * confined to ONE transfer — here a receiver sink whose flush throws a raw
 * kotlinx-io [IOException] (disk full) while [FileTransferDispatcher.onFileDone]
 * finalizes the receive — must fail that transfer only. The owning session
 * stays Connected and unrelated traffic (a concurrent transfer, plain
 * messages) keeps flowing. Before the fix, the non-P2pError escaped into
 * P2pSessionImpl.routeEvents' catch(Throwable) and tore the whole session down.
 */
@Suppress("DEPRECATION")
class FileTransferErrorIsolationTest {

    private fun outgoingKit(name: String, outgoing: RawConnection): P2pKit =
        createTestKit {
            appId = AppId("com.example.ft")
            deviceName = name
            peerIdStorage = InMemoryPeerIdStorage(seed = PeerId("alice-id"))
            keepAlive {
                pingIntervalMillis = 60_000
                timeoutMillis = 120_000
            }
            fileTransfer {
                chunkSizeBytes = 256
                offerTimeoutMillis = 60_000
            }
            transports {
                register(ErrorIsolationFtFactory(FakeDataTransport(outgoingConnection = { outgoing })))
            }
        }

    private fun incomingKit(name: String, incoming: RawConnection): P2pKit =
        createTestKit {
            appId = AppId("com.example.ft")
            deviceName = name
            keepAlive {
                pingIntervalMillis = 60_000
                timeoutMillis = 120_000
            }
            fileTransfer {
                chunkSizeBytes = 256
                offerTimeoutMillis = 60_000
            }
            // Match the dialed id ("bob-id") so the outgoing handshake's peerId
            // verification passes (mirrors production discovery).
            peerIdStorage = InMemoryPeerIdStorage(seed = PeerId("bob-id"))
            transports {
                register(ErrorIsolationFtFactory(FakeDataTransport(preStagedIncoming = listOf(incoming))))
            }
        }

    private fun syntheticPeer(id: String, name: String): Peer = Peer(
        id = PeerId(id),
        name = name,
        platform = Platform.JVM_DESKTOP,
        supportedTransports = setOf(TransportKind.LAN)
    )

    /**
     * RawSink that accepts writes but throws a raw (non-P2pError) IOException
     * on flush — models a disk that filled up between the last write and the
     * FILE_DONE finalization in StreamingFileReceiver.finish().
     */
    private class DiskFullSink : RawSink {
        override fun write(source: Buffer, byteCount: Long) {
            source.skip(byteCount)
        }

        override fun flush() {
            throw IOException("disk full")
        }

        override fun close() {}
    }

    @Test
    fun sinkFlushFailureOnFinishFailsOnlyThatTransfer() = runBlocking {
        val pair = FakeConnectionPair()
        val alice = outgoingKit("Alice", pair.a)
        val bob = incomingKit("Bob", pair.b)
        try {
            val outgoingDeferred = async { alice.connect(syntheticPeer("bob-id", "Bob")) }
            val incomingSession = withTimeout(5_000) { bob.incomingSessions.first() }
            val outgoing = withTimeout(5_000) { outgoingDeferred.await() }

            // Subscribe to messages and offers BEFORE anything is sent —
            // SharedFlows with replay=0 won't replay earlier emissions.
            val msgReady = CompletableDeferred<Unit>()
            val msgDeferred = async {
                incomingSession.incoming.onSubscription { msgReady.complete(Unit) }.first()
            }
            withTimeout(5_000) { msgReady.await() }

            val offersDeferred = async {
                incomingSession.pendingFileOffers.first { it.size == 2 }
            }

            // Two concurrent transfers: "bad.bin" lands in a sink whose flush
            // throws during finish(); "good.bin" must be unaffected.
            val badPayload = ByteArray(256) { 1 }
            val goodPayload = ByteArray(256) { 2 }
            outgoing.sendFile(
                name = "bad.bin",
                sizeBytes = badPayload.size.toLong(),
                mimeType = null,
                source = Buffer().apply { write(badPayload) }
            )
            val goodTransfer = outgoing.sendFile(
                name = "good.bin",
                sizeBytes = goodPayload.size.toLong(),
                mimeType = null,
                source = Buffer().apply { write(goodPayload) }
            )

            val offers = withTimeout(5_000) { offersDeferred.await() }
            val badOffer = offers.first { it.name == "bad.bin" }
            val goodOffer = offers.first { it.name == "good.bin" }

            val goodSink = Buffer()
            val badIncoming = badOffer.accept(DiskFullSink())
            val goodIncoming = goodOffer.accept(goodSink)

            // The failing receive must land in Failed (flush threw in finish())…
            val badTerminal = withTimeout(5_000) {
                badIncoming.state.first { it is FileTransferState.Failed || it is FileTransferState.Completed }
            }
            val failed = assertIs<FileTransferState.Failed>(badTerminal)
            val error = assertIs<P2pError.FileTransferFailed>(failed.error)
            assertEquals(FileTransferFailureKind.STORAGE, error.kind)
            assertEquals(FileTransferPhase.FLUSH, error.phase)
            assertEquals(Retryability.RETRY_AFTER_USER_ACTION, error.retryability)
            assertEquals(badIncoming.id, error.transferId)
            assertIs<IOException>(error.cause)
            assertTrue(
                failed.error.message?.contains("disk full") == true,
                "Failure should carry the sink's IOException, got ${failed.error}"
            )

            // …while the concurrent transfer completes on both sides…
            val goodReceiverFinal = withTimeout(5_000) {
                goodIncoming.state.first { it is FileTransferState.Completed || it is FileTransferState.Failed }
            }
            val goodSenderFinal = withTimeout(5_000) {
                goodTransfer.state.first { it is FileTransferState.Completed || it is FileTransferState.Failed }
            }
            assertIs<FileTransferState.Completed>(goodReceiverFinal)
            assertIs<FileTransferState.Completed>(goodSenderFinal)
            assertContentEquals(goodPayload, goodSink.readByteArray())

            // …and the SESSION survives: plain messages still flow end-to-end
            // and both sides report Connected.
            outgoing.send(P2pMessage.Text("still alive"))
            val msg = withTimeout(5_000) { msgDeferred.await() }
            assertEquals("still alive", assertIs<P2pMessage.Text>(msg).value)
            assertEquals(ConnectionState.Connected, incomingSession.state.value)
            assertEquals(ConnectionState.Connected, outgoing.state.value)
        } finally {
            alice.stop()
            bob.stop()
        }
    }
}

private class ErrorIsolationFtFactory(private val transport: FakeDataTransport) : TransportFactory {
    override val descriptor =
        dev.p2pkit.core.transport.TransportDescriptor.dataOnly(transport.type)
    override fun build(context: TransportContext): TransportPair =
        TransportPair(data = transport, discovery = null)
}
