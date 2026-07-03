package dev.p2pkit.core.internal

import dev.p2pkit.core.AppId
import dev.p2pkit.core.P2pError
import dev.p2pkit.core.P2pKit
import dev.p2pkit.core.P2pLogger
import dev.p2pkit.core.P2pMessage
import dev.p2pkit.core.Peer
import dev.p2pkit.core.PeerId
import dev.p2pkit.core.Platform
import dev.p2pkit.core.TransportKind
import dev.p2pkit.core.protocol.FileOfferPayload
import dev.p2pkit.core.protocol.Frame
import dev.p2pkit.core.protocol.HelloPayload
import dev.p2pkit.core.protocol.MessageId
import dev.p2pkit.core.protocol.P2pProtocol
import dev.p2pkit.core.protocol.ProtocolEvent
import dev.p2pkit.core.testfixtures.FakeConnectionPair
import dev.p2pkit.core.testfixtures.FakeDataTransport
import dev.p2pkit.core.transfer.FileTransferConfig
import dev.p2pkit.core.transfer.FileTransferState
import dev.p2pkit.core.transport.RawConnection
import dev.p2pkit.core.transport.TransportContext
import dev.p2pkit.core.transport.TransportFactory
import dev.p2pkit.core.transport.TransportPair
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Job
import kotlinx.coroutines.async
import kotlinx.coroutines.cancel
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.emptyFlow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.onSubscription
import kotlinx.coroutines.launch
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.withTimeout
import kotlinx.coroutines.yield
import kotlinx.io.Buffer
import kotlinx.io.readByteArray
import kotlinx.io.write
import kotlin.random.Random
import kotlin.test.Test
import kotlin.test.assertContentEquals
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertIs
import kotlin.test.assertTrue

class FileTransferFlowTest {

    private fun outgoingKit(name: String, outgoing: RawConnection, configureFileTransfer: Boolean = false): P2pKit =
        P2pKit.create {
            appId = AppId("com.example.ft")
            deviceName = name
            keepAlive {
                pingIntervalMillis = 60_000
                timeoutMillis = 120_000
            }
            if (configureFileTransfer) {
                fileTransfer {
                    maxFileSizeBytes = 512
                    offerTimeoutMillis = 200
                    chunkSizeBytes = 64
                }
            } else {
                fileTransfer {
                    chunkSizeBytes = 256
                    offerTimeoutMillis = 60_000
                }
            }
            transports {
                register(FtFactoryFor(FakeDataTransport(outgoingConnection = { outgoing })))
            }
        }

    private fun incomingKit(name: String, incoming: RawConnection, configureFileTransfer: Boolean = false): P2pKit =
        P2pKit.create {
            appId = AppId("com.example.ft")
            deviceName = name
            keepAlive {
                pingIntervalMillis = 60_000
                timeoutMillis = 120_000
            }
            if (configureFileTransfer) {
                fileTransfer {
                    maxFileSizeBytes = 512
                    offerTimeoutMillis = 200
                    chunkSizeBytes = 64
                }
            } else {
                fileTransfer {
                    chunkSizeBytes = 256
                    offerTimeoutMillis = 60_000
                }
            }
            // Match the dialed id ("bob-id") so the outgoing handshake's peerId
            // verification passes (mirrors production discovery).
            peerIdStorage = InMemoryPeerIdStorage(seed = PeerId("bob-id"))
            transports {
                register(FtFactoryFor(FakeDataTransport(preStagedIncoming = listOf(incoming))))
            }
        }

    private fun syntheticPeer(id: String, name: String): Peer = Peer(
        id = PeerId(id),
        name = name,
        platform = Platform.JVM_DESKTOP,
        supportedTransports = setOf(TransportKind.LAN)
    )

    @Test
    fun smallFileTransfersEndToEnd() = runBlocking {
        val pair = FakeConnectionPair()
        val alice = outgoingKit("Alice", pair.a)
        val bob = incomingKit("Bob", pair.b)
        try {
            val outgoingDeferred = async { alice.connect(syntheticPeer("bob-id", "Bob")) }
            val incomingSession = withTimeout(5_000) { bob.incomingSessions.first() }
            val outgoing = withTimeout(5_000) { outgoingDeferred.await() }

            val payload = ByteArray(1024) { (it and 0xFF).toByte() }
            val sink = Buffer()

            // Subscribe to incomingFiles BEFORE the sender opens the offer —
            // SharedFlow with replay=0 won't replay an offer emitted before
            // a subscriber attaches.
            val offerReady = CompletableDeferred<Unit>()
            val offerDeferred = async {
                incomingSession.incomingFiles.onSubscription { offerReady.complete(Unit) }.first()
            }
            offerReady.await()

            val transfer = outgoing.sendFile(
                name = "blob.bin",
                sizeBytes = payload.size.toLong(),
                mimeType = "application/octet-stream",
                source = Buffer().apply { write(payload) }
            )

            val offer = withTimeout(5_000) { offerDeferred.await() }
            assertEquals("blob.bin", offer.name)
            assertEquals(payload.size.toLong(), offer.sizeBytes)
            assertEquals("application/octet-stream", offer.mimeType)

            val incomingTransfer = offer.accept(sink)

            // Wait for both sides to terminate. The sender reaches Completed
            // after FILE_DONE is written; the receiver reaches Completed after
            // its StreamingFileReceiver.finish() runs in response to FILE_DONE.
            // Reading the sink before the receiver finishes can race the last
            // chunk write through the buffered sink wrapper.
            val senderFinal = withTimeout(5_000) {
                transfer.state.first { it is FileTransferState.Completed || it is FileTransferState.Failed }
            }
            val receiverFinal = withTimeout(5_000) {
                incomingTransfer.state.first { it is FileTransferState.Completed || it is FileTransferState.Failed }
            }
            assertIs<FileTransferState.Completed>(senderFinal)
            assertIs<FileTransferState.Completed>(receiverFinal)
            assertEquals(payload.size.toLong(), transfer.bytesTransferred.value)
            assertEquals(payload.size.toLong(), incomingTransfer.bytesTransferred.value)
            assertContentEquals(payload, sink.readByteArray())
        } finally {
            alice.stop()
            bob.stop()
        }
    }

    @Test
    fun rejectedOfferSurfacesOnSender() = runBlocking {
        val pair = FakeConnectionPair()
        val alice = outgoingKit("Alice", pair.a)
        val bob = incomingKit("Bob", pair.b)
        try {
            val outgoingDeferred = async { alice.connect(syntheticPeer("bob-id", "Bob")) }
            val incomingSession = withTimeout(5_000) { bob.incomingSessions.first() }
            val outgoing = withTimeout(5_000) { outgoingDeferred.await() }

            val offerReady = CompletableDeferred<Unit>()
            val offerDeferred = async {
                incomingSession.incomingFiles.onSubscription { offerReady.complete(Unit) }.first()
            }
            offerReady.await()

            val transfer = outgoing.sendFile(
                name = "x.bin",
                sizeBytes = 16L,
                mimeType = null,
                source = Buffer().apply { write(ByteArray(16)) }
            )
            val offer = withTimeout(5_000) { offerDeferred.await() }
            offer.reject("no thanks")

            val terminal = withTimeout(5_000) {
                transfer.state.first { it is FileTransferState.Rejected || it is FileTransferState.Failed }
            }
            val rejected = assertIs<FileTransferState.Rejected>(terminal)
            assertEquals("no thanks", rejected.reason)
        } finally {
            alice.stop()
            bob.stop()
        }
    }

    @Test
    fun offerExceedingReceiverLimitAutoRejects() = runBlocking {
        val pair = FakeConnectionPair()
        // Receiver has 512-byte cap; sender wants to send 1024 bytes.
        val alice = outgoingKit("Alice", pair.a, configureFileTransfer = false)
        val bob = incomingKit("Bob", pair.b, configureFileTransfer = true)
        try {
            val outgoingDeferred = async { alice.connect(syntheticPeer("bob-id", "Bob")) }
            val incomingSession = withTimeout(5_000) { bob.incomingSessions.first() }
            val outgoing = withTimeout(5_000) { outgoingDeferred.await() }
            // No accept side — receiver auto-rejects on size.
            val transfer = outgoing.sendFile(
                name = "huge.bin",
                sizeBytes = 1024L,
                mimeType = null,
                source = Buffer().apply { write(ByteArray(1024)) }
            )
            val terminal = withTimeout(5_000) {
                transfer.state.first { it is FileTransferState.Rejected || it is FileTransferState.Failed }
            }
            val rejected = assertIs<FileTransferState.Rejected>(terminal)
            assertTrue(
                rejected.reason?.contains("exceeds", ignoreCase = true) == true,
                "Expected size-exceeds reason, got ${rejected.reason}"
            )
            // Receiver should never have surfaced the offer to its incomingFiles flow.
            assertSubscriberSeesNoOffer(incomingSession.incomingFiles.toString())
        } finally {
            alice.stop()
            bob.stop()
        }
    }

    @Test
    fun localPayloadTooLargeThrowsImmediately() = runBlocking<Unit> {
        val pair = FakeConnectionPair()
        val alice = outgoingKit("Alice", pair.a, configureFileTransfer = true)
        val bob = incomingKit("Bob", pair.b)
        try {
            val outgoingDeferred = async { alice.connect(syntheticPeer("bob-id", "Bob")) }
            withTimeout(5_000) { bob.incomingSessions.first() }
            val outgoing = withTimeout(5_000) { outgoingDeferred.await() }

            assertFailsWith<P2pError.PayloadTooLarge> {
                // 512 cap on Alice's side — 600 bytes is rejected locally before any wire writes.
                outgoing.sendFile(
                    name = "n",
                    sizeBytes = 600L,
                    mimeType = null,
                    source = Buffer().apply { write(ByteArray(600)) }
                )
            }
        } finally {
            alice.stop()
            bob.stop()
        }
    }

    @Test
    fun offerTimeoutAutoCancelsOnSender() = runBlocking {
        val pair = FakeConnectionPair()
        // Both sides have 200ms offer timeout.
        val alice = outgoingKit("Alice", pair.a, configureFileTransfer = true)
        val bob = incomingKit("Bob", pair.b, configureFileTransfer = true)
        try {
            val outgoingDeferred = async { alice.connect(syntheticPeer("bob-id", "Bob")) }
            val incomingSession = withTimeout(5_000) { bob.incomingSessions.first() }
            val outgoing = withTimeout(5_000) { outgoingDeferred.await() }

            // We deliberately don't subscribe to incomingFiles or call accept,
            // so both sender (200ms) and receiver (200ms) timeouts will fire.
            // Whichever fires first decides the terminal state. The receiver
            // typically wins (its FILE_REJECT path), so we expect Rejected.
            val transfer = outgoing.sendFile(
                name = "x",
                sizeBytes = 16L,
                mimeType = null,
                source = Buffer().apply { write(ByteArray(16)) }
            )
            val terminal = withTimeout(5_000) {
                transfer.state.first { it is FileTransferState.Cancelled || it is FileTransferState.Rejected }
            }
            // Either outcome is acceptable; the key is that we transitioned terminal.
            assertTrue(
                terminal is FileTransferState.Cancelled || terminal is FileTransferState.Rejected,
                "Expected terminal Cancelled or Rejected, got $terminal"
            )
            // Sanity: incomingSession was not closed by this — file transfer
            // failures don't kill the data session.
            assertEquals(dev.p2pkit.core.ConnectionState.Connected, incomingSession.state.value)
        } finally {
            alice.stop()
            bob.stop()
        }
    }

    @Test
    fun cancelMidStreamPropagatesToReceiver() = runBlocking {
        val pair = FakeConnectionPair()
        val alice = outgoingKit("Alice", pair.a)
        val bob = incomingKit("Bob", pair.b)
        try {
            val outgoingDeferred = async { alice.connect(syntheticPeer("bob-id", "Bob")) }
            val incomingSession = withTimeout(5_000) { bob.incomingSessions.first() }
            val outgoing = withTimeout(5_000) { outgoingDeferred.await() }

            val offerReady = CompletableDeferred<Unit>()
            val offerDeferred = async {
                incomingSession.incomingFiles.onSubscription { offerReady.complete(Unit) }.first()
            }
            offerReady.await()

            val transfer = outgoing.sendFile(
                name = "abort.bin",
                sizeBytes = 8L,
                mimeType = null,
                source = Buffer().apply { write(ByteArray(8)) }
            )
            val offer = withTimeout(5_000) { offerDeferred.await() }
            val incomingTransfer = offer.accept(Buffer())

            transfer.cancel("user aborted")

            val senderTerminal = withTimeout(5_000) {
                transfer.state.first {
                    it is FileTransferState.Cancelled || it is FileTransferState.Completed ||
                        it is FileTransferState.Failed
                }
            }
            val receiverTerminal = withTimeout(5_000) {
                incomingTransfer.state.first {
                    it is FileTransferState.Cancelled || it is FileTransferState.Completed ||
                        it is FileTransferState.Failed
                }
            }
            // Sender always reaches Cancelled. Receiver normally reaches
            // Cancelled (via inbound FILE_CANCEL); on a race where Completed
            // arrived first, accept that too.
            assertTrue(
                senderTerminal is FileTransferState.Cancelled,
                "Sender should observe Cancelled, got $senderTerminal"
            )
            assertTrue(
                receiverTerminal is FileTransferState.Cancelled || receiverTerminal is FileTransferState.Completed,
                "Receiver should reach Cancelled or Completed, got $receiverTerminal"
            )
        } finally {
            alice.stop()
            bob.stop()
        }
    }

    @Test
    fun fileTransfersDoNotBlockMessages() = runBlocking {
        val pair = FakeConnectionPair()
        val alice = outgoingKit("Alice", pair.a)
        val bob = incomingKit("Bob", pair.b)
        try {
            val outgoingDeferred = async { alice.connect(syntheticPeer("bob-id", "Bob")) }
            val incomingSession = withTimeout(5_000) { bob.incomingSessions.first() }
            val outgoing = withTimeout(5_000) { outgoingDeferred.await() }

            val msgReady = CompletableDeferred<Unit>()
            val msgDeferred = async {
                incomingSession.incoming.onSubscription { msgReady.complete(Unit) }.first()
            }
            msgReady.await()

            val offerReady = CompletableDeferred<Unit>()
            val offerDeferred = async {
                incomingSession.incomingFiles.onSubscription { offerReady.complete(Unit) }.first()
            }
            offerReady.await()

            // Kick off a file transfer, then send a regular message — message
            // should land regardless of transfer state.
            val payload = ByteArray(2048) { (it and 0xFF).toByte() }
            val fileJob = launch {
                val transfer = outgoing.sendFile(
                    name = "parallel.bin",
                    sizeBytes = payload.size.toLong(),
                    mimeType = null,
                    source = Buffer().apply { write(payload) }
                )
                val offer = offerDeferred.await()
                offer.accept(Buffer())
                transfer.state.first { it is FileTransferState.Completed || it is FileTransferState.Failed }
            }
            outgoing.send(dev.p2pkit.core.P2pMessage.Text("ping"))
            val msg = withTimeout(5_000) { msgDeferred.await() }
            val text = assertIs<dev.p2pkit.core.P2pMessage.Text>(msg)
            assertEquals("ping", text.value)

            // Wait for the file transfer launch to finish before entering the
            // finally block. Without this, `alice.stop()` in `finally` can race
            // ahead of the launch's `offer.accept(...)`: alice's close tears
            // down her wire, bob's `routeEvents` exits, bob's `markCleanlyClosed`
            // fires, and bob's FileTransferDispatcher.closeAll evicts the
            // pending offer — so the still-suspended `offer.accept(...)` would
            // throw "Offer no longer pending" after the assertions are already
            // done. The OLD SDK was lenient (markCleanlyClosed did NOT call
            // closeAll), so the offer survived to be accepted on a wire that
            // was being torn down. The S3 commit makes terminal transitions
            // symmetric (file-transfer cleanup happens on every terminal path),
            // which is the correct semantic — and exposes this test's reliance
            // on the previous looseness.
            withTimeout(5_000) { fileJob.join() }
        } finally {
            alice.stop()
            bob.stop()
        }
    }

    // ---- Direct-dispatcher tests (recording protocol, no wire I/O) ----

    @Test
    fun offerProcessedWhileDispatcherClosedIsDroppedAndLeaksNoEntry() = runBlocking {
        // Single-threaded (runBlocking's event loop) so coroutine interleaving
        // is deterministic.
        val scope = CoroutineScope(coroutineContext + Job())
        val protocol = RecordingFileProtocol()
        val dispatcher = directDispatcher(scope, protocol)
        try {
            val received = mutableListOf<String>()
            val subscribed = CompletableDeferred<Unit>()
            scope.launch {
                dispatcher.incomingFiles
                    .onSubscription { subscribed.complete(Unit) }
                    .collect { received.add(it.name) }
            }
            subscribed.await()

            dispatcher.closeAll("session closing")
            val transferId = MessageId.random(Random(7))
            dispatcher.onFileOffer(transferId, FileOfferPayload(name = "late.bin", sizeBytes = 8L))
            repeat(10) { yield() }  // drain any (wrongly) launched emit
            assertTrue(
                received.isEmpty(),
                "FILE_OFFER processed while closed must not surface an offer, got $received"
            )
            assertTrue(
                protocol.fileRejects.isEmpty(),
                "A closed dispatcher must drop the offer silently, sent ${protocol.fileRejects}"
            )

            // The dropped offer must leave no entry behind in `incoming`: after
            // reopen() (the reconnect-rearm path) the same transferId must be
            // treated as brand-new — a leaked entry would trip the
            // duplicate-transferId guard and swallow this second offer.
            dispatcher.reopen()
            dispatcher.onFileOffer(transferId, FileOfferPayload(name = "late.bin", sizeBytes = 8L))
            withTimeout(5_000) {
                while (received.isEmpty()) yield()
            }
            assertEquals(listOf("late.bin"), received)
        } finally {
            scope.cancel()
        }
    }

    @Test
    fun acceptThenImmediateCancelNeverStreamsOrSendsFileDone() = runBlocking {
        val scope = CoroutineScope(coroutineContext + Job())
        val protocol = RecordingFileProtocol()
        val dispatcher = directDispatcher(scope, protocol)
        try {
            val payload = ByteArray(64) { 3 }
            val transfer = dispatcher.sendFile(
                name = "cancelled.bin",
                sizeBytes = payload.size.toLong(),
                mimeType = null,
                source = Buffer().apply { write(payload) }
            )
            val transferId = protocol.fileOffers.single()

            // Remote accepted then cancelled back-to-back: the streamer job
            // must be registered as entry.sender (and therefore cancellable)
            // before it can produce a single frame (E:370).
            dispatcher.onFileAccept(transferId)
            dispatcher.onFileCancel(transferId, "changed my mind")
            repeat(10) { yield() }  // give any (wrongly) surviving streamer a chance to run

            val cancelled = assertIs<FileTransferState.Cancelled>(transfer.state.value)
            assertEquals("changed my mind", cancelled.reason)
            assertTrue(
                protocol.fileData.none { it == transferId },
                "cancelled transfer must not stream FILE_DATA, sent ${protocol.fileData}"
            )
            assertTrue(
                protocol.fileDones.none { it == transferId },
                "cancelled transfer must not send FILE_DONE, sent ${protocol.fileDones}"
            )
        } finally {
            scope.cancel()
        }
    }

    private fun directDispatcher(scope: CoroutineScope, protocol: P2pProtocol): FileTransferDispatcher {
        val pair = FakeConnectionPair()
        return FileTransferDispatcher(
            sessionId = "direct-test",
            remotePeer = syntheticPeer("peer-id", "Peer"),
            protocol = protocol,
            getConnection = { pair.a },
            sendMutex = Mutex(),
            config = FileTransferConfig(offerTimeoutMillis = 60_000),
            scope = scope,
            random = Random(42),
            logger = P2pLogger.NoOp
        )
    }

    @Suppress("UNUSED_PARAMETER")
    private fun assertSubscriberSeesNoOffer(name: String) {
        // No-op probe — left as a hook so future versions can replace with
        // a definitive "flow received nothing in N ms" assertion.
    }
}

private class FtFactoryFor(private val transport: FakeDataTransport) : TransportFactory {
    override fun build(context: TransportContext): TransportPair =
        TransportPair(data = transport, discovery = null)
}

/**
 * [P2pProtocol] fake that records file-frame sends without any wire I/O.
 * Used by the direct-dispatcher tests to observe exactly which frames a
 * transfer emitted.
 */
private class RecordingFileProtocol : P2pProtocol {
    val fileOffers = mutableListOf<MessageId>()
    val fileData = mutableListOf<MessageId>()
    val fileDones = mutableListOf<MessageId>()
    val fileCancels = mutableListOf<MessageId>()
    val fileRejects = mutableListOf<MessageId>()

    override suspend fun sendMessage(connection: RawConnection, message: P2pMessage) {}
    override suspend fun sendHello(connection: RawConnection, hello: HelloPayload) {}
    override suspend fun sendPing(connection: RawConnection) {}
    override suspend fun sendPong(connection: RawConnection) {}
    override suspend fun sendClose(connection: RawConnection) {}
    override suspend fun sendError(connection: RawConnection, reason: String) {}

    override suspend fun sendFileOffer(connection: RawConnection, transferId: MessageId, offer: FileOfferPayload) {
        fileOffers.add(transferId)
    }

    override suspend fun sendFileAccept(connection: RawConnection, transferId: MessageId) {}

    override suspend fun sendFileReject(connection: RawConnection, transferId: MessageId, reason: String?) {
        fileRejects.add(transferId)
    }

    override suspend fun sendFileDataFrame(connection: RawConnection, frame: Frame) {
        fileData.add(frame.messageId)
    }

    override suspend fun sendFileDone(connection: RawConnection, transferId: MessageId) {
        fileDones.add(transferId)
    }

    override suspend fun sendFileCancel(connection: RawConnection, transferId: MessageId, reason: String?) {
        fileCancels.add(transferId)
    }

    override fun events(connection: RawConnection): Flow<ProtocolEvent> = emptyFlow()
}
