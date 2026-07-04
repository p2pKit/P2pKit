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
import dev.p2pkit.core.testfixtures.SnapshotList
import dev.p2pkit.core.testfixtures.createTestKit
import dev.p2pkit.core.transfer.FileTransferConfig
import dev.p2pkit.core.transfer.FileTransferState
import dev.p2pkit.core.transfer.isTerminal
import dev.p2pkit.core.transport.RawConnection
import dev.p2pkit.core.transport.TransportContext
import dev.p2pkit.core.transport.TransportFactory
import dev.p2pkit.core.transport.TransportPair
import kotlin.concurrent.atomics.AtomicInt
import kotlin.concurrent.atomics.ExperimentalAtomicApi
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Job
import kotlinx.coroutines.async
import kotlinx.coroutines.cancel
import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.delay
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
import kotlinx.io.IOException
import kotlinx.io.RawSource
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
        createTestKit {
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
        createTestKit {
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

            // AUDIT-2026-07 (FIL-11 / P1-23): a REAL subscriber, attached
            // before any offer is sent — the headline invariant is that the
            // oversize offer never surfaces on incomingFiles (the previous
            // assertSubscriberSeesNoOffer helper asserted nothing).
            val surfacedOffers = SnapshotList<String>()
            val subscribed = CompletableDeferred<Unit>()
            val collectJob = launch {
                incomingSession.incomingFiles
                    .onSubscription { subscribed.complete(Unit) }
                    .collect { surfacedOffers.add(it.name) }
            }
            subscribed.await()

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

            // Sentinel: a conforming offer sent AFTER the oversize one must be
            // the only offer the subscriber ever sees. Its arrival bounds the
            // wait — a wrongly-emitted "huge.bin" would land before/alongside it.
            outgoing.sendFile(
                name = "small.bin",
                sizeBytes = 16L,
                mimeType = null,
                source = Buffer().apply { write(ByteArray(16)) }
            )
            withTimeout(5_000) { while (surfacedOffers.snapshot().isEmpty()) delay(10) }
            delay(50)  // grace so a late oversize emission would surface
            assertEquals(
                listOf("small.bin"),
                surfacedOffers.snapshot(),
                "oversize offer must never surface on incomingFiles"
            )
            collectJob.cancel()
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

    // ---- Group H (AUDIT-2026-07): file-transfer terminal-path robustness, E2E ----

    @Test
    fun senderSourceExhaustionNotifiesReceiverAndKeepsSessionConnected() = runBlocking {
        // AUDIT-2026-07 (FIL-2 / P1-21): a sender whose source runs out mid-
        // stream (declared 1024 bytes, holds 512) must fail ONLY that
        // transfer, notify the peer via FILE_CANCEL so the accepted receiver
        // does not wait indefinitely, and leave the session Connected.
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

            val source = CloseTrackingSource(Buffer().apply { write(ByteArray(512) { 9 }) })
            val transfer = outgoing.sendFile(
                name = "short.bin",
                sizeBytes = 1024L,
                mimeType = null,
                source = source
            )
            val offer = withTimeout(5_000) { offerDeferred.await() }
            val incomingTransfer = offer.accept(Buffer())

            val senderTerminal = withTimeout(5_000) { transfer.state.first { it.isTerminal() } }
            assertIs<FileTransferState.Failed>(senderTerminal)
            // Receiver must reach a terminal state within a bound — the
            // sender-side FILE_CANCEL crossed the wire.
            val receiverTerminal = withTimeout(5_000) { incomingTransfer.state.first { it.isTerminal() } }
            val cancelled = assertIs<FileTransferState.Cancelled>(receiverTerminal)
            assertTrue(
                cancelled.reason?.contains("sender source failure") == true,
                "receiver should carry the sender-side failure reason, got ${cancelled.reason}"
            )

            // Transfer-failure isolation: sessions stay Connected and still move messages.
            assertEquals(dev.p2pkit.core.ConnectionState.Connected, outgoing.state.value)
            assertEquals(dev.p2pkit.core.ConnectionState.Connected, incomingSession.state.value)
            outgoing.send(dev.p2pkit.core.P2pMessage.Text("still alive"))
            val msg = withTimeout(5_000) { msgDeferred.await() }
            assertEquals("still alive", assertIs<dev.p2pkit.core.P2pMessage.Text>(msg).value)

            // Source released exactly once (P1-20 tie-in).
            withTimeout(5_000) { while (source.closeCount < 1) delay(10) }
            delay(50)
            assertEquals(1, source.closeCount)
        } finally {
            alice.stop()
            bob.stop()
        }
    }

    @Test
    fun sessionCloseMidTransferTerminalizesBothSidesAndClosesSource() = runBlocking {
        // AUDIT-2026-07 (FIL-1 / P1-24 / P1-20 close-mid-stream): user
        // close() while a transfer is pinned mid-stream must terminalize both
        // sides' handles (no awaiter hangs) and release the sender's source
        // exactly once.
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

            val source = CloseTrackingSource(Buffer().apply { write(ByteArray(1024) { 4 }) })
            val transfer = outgoing.sendFile(
                name = "midstream.bin",
                sizeBytes = 1024L,
                mimeType = null,
                source = source
            )
            val offer = withTimeout(5_000) { offerDeferred.await() }
            // Park alice's writes AFTER the offer is out: the streamer's next
            // chunk write suspends like a stalled socket write, pinning the
            // transfer deterministically mid-stream (it can never complete).
            pair.a.suspendWrites()
            val incomingTransfer = offer.accept(Buffer())
            withTimeout(5_000) { transfer.state.first { it is FileTransferState.Sending } }

            withTimeout(10_000) { outgoing.close() }

            val senderTerminal = withTimeout(5_000) { transfer.state.first { it.isTerminal() } }
            assertIs<FileTransferState.Failed>(senderTerminal)
            val receiverTerminal = withTimeout(5_000) { incomingTransfer.state.first { it.isTerminal() } }
            assertTrue(
                receiverTerminal is FileTransferState.Failed || receiverTerminal is FileTransferState.Cancelled,
                "receiver handle must terminalize, got $receiverTerminal"
            )
            assertEquals(dev.p2pkit.core.ConnectionState.Closed, outgoing.state.value)
            withTimeout(5_000) {
                incomingSession.state.first {
                    it == dev.p2pkit.core.ConnectionState.Closed || it == dev.p2pkit.core.ConnectionState.Failed
                }
            }

            withTimeout(5_000) { while (source.closeCount < 1) delay(10) }
            delay(50)  // grace so a (wrong) second close would surface
            assertEquals(1, source.closeCount, "close() mid-stream must release the source exactly once")
        } finally {
            alice.stop()
            bob.stop()
        }
    }

    @Test
    fun kitStopMidTransferTerminalizesBothSidesAndClosesSource() = runBlocking {
        // AUDIT-2026-07 (FIL-1 / P1-24 / P1-20 stop-mid-stream): kit.stop()
        // variant of the mid-stream teardown — same invariants as close().
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

            val source = CloseTrackingSource(Buffer().apply { write(ByteArray(1024) { 6 }) })
            val transfer = outgoing.sendFile(
                name = "midstream-stop.bin",
                sizeBytes = 1024L,
                mimeType = null,
                source = source
            )
            val offer = withTimeout(5_000) { offerDeferred.await() }
            pair.a.suspendWrites()
            val incomingTransfer = offer.accept(Buffer())
            withTimeout(5_000) { transfer.state.first { it is FileTransferState.Sending } }

            withTimeout(10_000) { alice.stop() }

            val senderTerminal = withTimeout(5_000) { transfer.state.first { it.isTerminal() } }
            assertIs<FileTransferState.Failed>(senderTerminal)
            val receiverTerminal = withTimeout(5_000) { incomingTransfer.state.first { it.isTerminal() } }
            assertTrue(
                receiverTerminal is FileTransferState.Failed || receiverTerminal is FileTransferState.Cancelled,
                "receiver handle must terminalize, got $receiverTerminal"
            )
            withTimeout(5_000) {
                outgoing.state.first {
                    it == dev.p2pkit.core.ConnectionState.Closed || it == dev.p2pkit.core.ConnectionState.Failed
                }
            }

            withTimeout(5_000) { while (source.closeCount < 1) delay(10) }
            delay(50)
            assertEquals(1, source.closeCount, "kit.stop() mid-stream must release the source exactly once")
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
                protocol.fileData.none { it.first == transferId },
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

    // ---- Group H (AUDIT-2026-07): outgoing-source terminal-path matrix (P1-20…P1-22) ----

    @Test
    fun sourceClosedExactlyOnceOnCompletedTransfer() = runBlocking {
        val scope = CoroutineScope(coroutineContext + Job())
        val protocol = RecordingFileProtocol()
        val dispatcher = directDispatcher(scope, protocol)
        try {
            val source = CloseTrackingSource(Buffer().apply { write(ByteArray(64) { 1 }) })
            val transfer = dispatcher.sendFile("done.bin", 64L, null, source)
            dispatcher.onFileAccept(protocol.fileOffers.single())
            val terminal = withTimeout(5_000) { transfer.state.first { it.isTerminal() } }
            assertIs<FileTransferState.Completed>(terminal)
            assertEquals(64L, transfer.bytesTransferred.value)
            repeat(10) { yield() }  // let the backstop watcher run too
            assertEquals(1, source.closeCount, "source must close exactly once on Completed")
        } finally {
            scope.cancel()
        }
    }

    @Test
    fun sourceClosedExactlyOnceOnRejectedOffer() = runBlocking {
        val scope = CoroutineScope(coroutineContext + Job())
        val protocol = RecordingFileProtocol()
        val dispatcher = directDispatcher(scope, protocol)
        try {
            val source = CloseTrackingSource(Buffer().apply { write(ByteArray(8) { 2 }) })
            val transfer = dispatcher.sendFile("rejected.bin", 8L, null, source)
            dispatcher.onFileReject(protocol.fileOffers.single(), "no thanks")
            assertIs<FileTransferState.Rejected>(transfer.state.value)
            // The close is synchronous with the terminal transition (FIL-1) …
            assertEquals(1, source.closeCount, "source must close at the Rejected transition")
            repeat(10) { yield() }
            // … and idempotent across the backstop watcher.
            assertEquals(1, source.closeCount, "close-once guard must hold after the watcher runs")
        } finally {
            scope.cancel()
        }
    }

    @Test
    fun sourceClosedExactlyOnceOnCancelBeforeAccept() = runBlocking {
        val scope = CoroutineScope(coroutineContext + Job())
        val protocol = RecordingFileProtocol()
        val dispatcher = directDispatcher(scope, protocol)
        try {
            val source = CloseTrackingSource(Buffer().apply { write(ByteArray(8) { 3 }) })
            val transfer = dispatcher.sendFile("cancelled-early.bin", 8L, null, source)
            val transferId = protocol.fileOffers.single()
            transfer.cancel("changed my mind")
            val cancelled = assertIs<FileTransferState.Cancelled>(transfer.state.value)
            assertEquals("changed my mind", cancelled.reason)
            assertEquals(listOf<Pair<MessageId, String?>>(transferId to "changed my mind"), protocol.fileCancels)
            repeat(10) { yield() }
            assertEquals(1, source.closeCount, "source must close exactly once on local cancel before accept")
        } finally {
            scope.cancel()
        }
    }

    @Test
    fun sourceClosedExactlyOnceOnCancelAfterAccept() = runBlocking {
        val scope = CoroutineScope(coroutineContext + Job())
        val protocol = RecordingFileProtocol()
        val dispatcher = directDispatcher(scope, protocol)
        try {
            val source = CloseTrackingSource(Buffer().apply { write(ByteArray(8) { 4 }) })
            val transfer = dispatcher.sendFile("cancelled-late.bin", 8L, null, source)
            val transferId = protocol.fileOffers.single()
            dispatcher.onFileAccept(transferId)
            dispatcher.onFileCancel(transferId, "remote cancelled")
            repeat(10) { yield() }  // drain the (bailing) streamer + the watcher
            assertIs<FileTransferState.Cancelled>(transfer.state.value)
            assertEquals(1, source.closeCount, "source must close exactly once on remote cancel after accept")
        } finally {
            scope.cancel()
        }
    }

    @Test
    fun sourceClosedExactlyOnceOnOfferWriteFailure() = runBlocking {
        val scope = CoroutineScope(coroutineContext + Job())
        val protocol = RecordingFileProtocol()
        val dispatcher = directDispatcher(scope, protocol)
        try {
            protocol.offerFailure = IOException("wire failed before FILE_OFFER")
            val source = CloseTrackingSource(Buffer().apply { write(ByteArray(8) { 5 }) })
            assertFailsWith<P2pError.ConnectionFailed> {
                dispatcher.sendFile("never-offered.bin", 8L, null, source)
            }
            repeat(10) { yield() }
            assertEquals(1, source.closeCount, "offer-write failure must release the source exactly once")
        } finally {
            scope.cancel()
        }
    }

    @Test
    fun sourceClosedExactlyOnceOnRearmCloseAll() = runBlocking {
        val scope = CoroutineScope(coroutineContext + Job())
        val protocol = RecordingFileProtocol()
        val dispatcher = directDispatcher(scope, protocol)
        try {
            val source = CloseTrackingSource(Buffer().apply { write(ByteArray(8) { 6 }) })
            val transfer = dispatcher.sendFile("inflight.bin", 8L, null, source)
            // The reconnect-rearm path: closeAll fails in-flight transfers.
            dispatcher.closeAll("reconnect: connection replaced")
            val failed = assertIs<FileTransferState.Failed>(transfer.state.value)
            assertIs<P2pError.ConnectionFailed>(failed.error)
            assertEquals(1, source.closeCount, "rearm closeAll must release the source")
            // reopen() must leave the dispatcher usable and the first source's
            // close-once latch untouched.
            dispatcher.reopen()
            val source2 = CloseTrackingSource(Buffer().apply { write(ByteArray(8) { 7 }) })
            val transfer2 = dispatcher.sendFile("after-rearm.bin", 8L, null, source2)
            assertEquals(2, protocol.fileOffers.size)
            transfer2.cancel("cleanup")
            assertIs<FileTransferState.Cancelled>(transfer2.state.value)
            repeat(10) { yield() }
            assertEquals(1, source.closeCount, "rearm closeAll must not double-close the first source")
            assertEquals(1, source2.closeCount)
        } finally {
            scope.cancel()
        }
    }

    @Test
    fun sendFileOnClosedDispatcherThrowsWithoutLeakingEntry() = runBlocking {
        // AUDIT-2026-07 (FIL-6): a sendFile refused because the dispatcher is
        // closed must not leave a half-registered entry behind — after
        // reopen() (the reconnect rearm) a fresh transfer must work.
        val scope = CoroutineScope(coroutineContext + Job())
        val protocol = RecordingFileProtocol()
        val dispatcher = directDispatcher(scope, protocol)
        try {
            dispatcher.closeAll("session closing")
            assertFailsWith<P2pError.ConnectionFailed> {
                dispatcher.sendFile(
                    "late.bin", 8L, null,
                    CloseTrackingSource(Buffer().apply { write(ByteArray(8)) })
                )
            }
            assertTrue(protocol.fileOffers.isEmpty(), "no FILE_OFFER may leave a closed dispatcher")

            dispatcher.reopen()
            val source = CloseTrackingSource(Buffer().apply { write(ByteArray(8) { 8 }) })
            val transfer = dispatcher.sendFile("ok.bin", 8L, null, source)
            assertEquals(1, protocol.fileOffers.size)
            transfer.cancel("cleanup")
            repeat(10) { yield() }
            assertEquals(1, source.closeCount)
        } finally {
            scope.cancel()
        }
    }

    @Test
    fun senderSourceReadFailureSendsFileCancelAndFailsOnlyThatTransfer() = runBlocking {
        // AUDIT-2026-07 (FIL-2 / P1-21): the source throws mid-stream on a
        // healthy wire → sender Failed, FILE_CANCEL recorded on the wire with
        // the sender-source-failure reason, no FILE_DONE, source closed once.
        val scope = CoroutineScope(coroutineContext + Job())
        val protocol = RecordingFileProtocol()
        val dispatcher = directDispatcher(
            scope, protocol,
            FileTransferConfig(offerTimeoutMillis = 60_000, chunkSizeBytes = 16)
        )
        try {
            // Declares 64 bytes; the source throws after serving 32.
            val source = CloseTrackingSource(
                Buffer().apply { write(ByteArray(64) { 7 }) },
                failAfterBytes = 32
            )
            val transfer = dispatcher.sendFile("truncated.bin", 64L, null, source)
            val transferId = protocol.fileOffers.single()
            dispatcher.onFileAccept(transferId)

            val terminal = withTimeout(5_000) { transfer.state.first { it.isTerminal() } }
            val failed = assertIs<FileTransferState.Failed>(terminal)
            assertIs<P2pError.ConnectionFailed>(failed.error)
            assertTrue(
                failed.error.message?.contains("source read failed") == true,
                "sender failure should be classified as a source read failure, got ${failed.error}"
            )
            val cancel = protocol.fileCancels.single()
            assertEquals(transferId, cancel.first)
            assertTrue(
                cancel.second?.contains("sender source failure") == true,
                "FILE_CANCEL should carry the sender-source-failure reason, got ${cancel.second}"
            )
            assertTrue(protocol.fileDones.isEmpty(), "a failed stream must not send FILE_DONE")
            assertEquals(32L, transfer.bytesTransferred.value)
            repeat(10) { yield() }
            assertEquals(1, source.closeCount)
        } finally {
            scope.cancel()
        }
    }

    @Test
    fun duplicateFileAcceptDoesNotLaunchSecondStreamer() = runBlocking {
        // AUDIT-2026-07 (FIL-4 / P1-22): duplicate FILE_ACCEPT frames — while
        // Accepted, while Sending (mid-stream), and after completion — must
        // not launch a second streamer or regress state: chunks 0..n-1 once,
        // one FILE_DONE, bytesTransferred == sizeBytes exactly.
        val scope = CoroutineScope(coroutineContext + Job())
        val protocol = RecordingFileProtocol().apply { gateDataFrames = true }
        val dispatcher = directDispatcher(
            scope, protocol,
            FileTransferConfig(offerTimeoutMillis = 60_000, chunkSizeBytes = 16)
        )
        try {
            val source = CloseTrackingSource(Buffer().apply { write(ByteArray(64) { 5 }) })
            val transfer = dispatcher.sendFile("dup.bin", 64L, null, source)
            val transferId = protocol.fileOffers.single()

            dispatcher.onFileAccept(transferId)
            assertEquals(FileTransferState.Accepted, transfer.state.value)
            // Duplicate while Accepted (streamer not yet running) — ignored.
            dispatcher.onFileAccept(transferId)
            assertEquals(FileTransferState.Accepted, transfer.state.value)

            // Let the (single) streamer reach the gate: chunk 0 recorded, then parked.
            withTimeout(5_000) { while (protocol.fileData.size < 1) yield() }
            assertIs<FileTransferState.Sending>(transfer.state.value)
            // Duplicate while Sending — no state regression, no second streamer.
            dispatcher.onFileAccept(transferId)
            assertIs<FileTransferState.Sending>(transfer.state.value)

            repeat(4) { protocol.dataFrameReleases.send(Unit) }
            val terminal = withTimeout(5_000) { transfer.state.first { it.isTerminal() } }
            assertIs<FileTransferState.Completed>(terminal)
            // Duplicate after completion (entry removed) — unknown-transfer branch.
            dispatcher.onFileAccept(transferId)

            assertEquals(
                listOf(0, 1, 2, 3),
                protocol.fileData.filter { it.first == transferId }.map { it.second },
                "chunks 0..3 must be sent exactly once, in order"
            )
            assertEquals(1, protocol.fileDones.count { it == transferId }, "exactly one FILE_DONE")
            assertEquals(64L, transfer.bytesTransferred.value, "bytesTransferred must equal sizeBytes exactly")
            repeat(10) { yield() }
            assertEquals(1, source.closeCount)
        } finally {
            scope.cancel()
        }
    }

    private fun directDispatcher(
        scope: CoroutineScope,
        protocol: P2pProtocol,
        config: FileTransferConfig = FileTransferConfig(offerTimeoutMillis = 60_000)
    ): FileTransferDispatcher {
        val pair = FakeConnectionPair()
        return FileTransferDispatcher(
            sessionId = "direct-test",
            remotePeer = syntheticPeer("peer-id", "Peer"),
            protocol = protocol,
            getConnection = { pair.a },
            sendMutex = Mutex(),
            config = config,
            scope = scope,
            random = Random(42),
            logger = P2pLogger.NoOp
        )
    }
}

/**
 * [RawSource] wrapper that counts [close] calls (terminal-path exactly-once
 * assertions) and can optionally throw after serving [failAfterBytes] bytes
 * (sender-side mid-stream read-failure injection). Reads are capped so the
 * failure point is deterministic regardless of upstream buffering.
 */
@OptIn(ExperimentalAtomicApi::class)
private class CloseTrackingSource(
    private val delegate: RawSource,
    private val failAfterBytes: Long = Long.MAX_VALUE
) : RawSource {
    private val closes = AtomicInt(0)
    private var bytesServed = 0L

    val closeCount: Int get() = closes.load()

    override fun readAtMostTo(sink: Buffer, byteCount: Long): Long {
        if (bytesServed >= failAfterBytes) {
            throw IOException("injected source read failure after $bytesServed bytes")
        }
        val n = delegate.readAtMostTo(sink, minOf(byteCount, failAfterBytes - bytesServed))
        if (n > 0) bytesServed += n
        return n
    }

    override fun close() {
        closes.addAndFetch(1)
        delegate.close()
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

    /** (transferId, chunkIndex) per FILE_DATA frame, in send order. */
    val fileData = mutableListOf<Pair<MessageId, Int>>()
    val fileDones = mutableListOf<MessageId>()

    /** (transferId, reason) per FILE_CANCEL, in send order. */
    val fileCancels = mutableListOf<Pair<MessageId, String?>>()
    val fileRejects = mutableListOf<MessageId>()

    /** When non-null, [sendFileOffer] throws it instead of recording (offer-write-failure injection). */
    var offerFailure: Throwable? = null

    /**
     * When true, each [sendFileDataFrame] records its frame and then parks
     * until [dataFrameReleases] provides one permit — a deterministic
     * mid-stream hold for the outgoing streamer.
     */
    var gateDataFrames = false
    val dataFrameReleases = Channel<Unit>(Channel.UNLIMITED)

    override suspend fun sendMessage(connection: RawConnection, message: P2pMessage) {}
    override suspend fun sendHello(connection: RawConnection, hello: HelloPayload) {}
    override suspend fun sendPing(connection: RawConnection) {}
    override suspend fun sendPong(connection: RawConnection) {}
    override suspend fun sendClose(connection: RawConnection) {}
    override suspend fun sendError(connection: RawConnection, reason: String) {}

    override suspend fun sendFileOffer(connection: RawConnection, transferId: MessageId, offer: FileOfferPayload) {
        offerFailure?.let { throw it }
        fileOffers.add(transferId)
    }

    override suspend fun sendFileAccept(connection: RawConnection, transferId: MessageId) {}

    override suspend fun sendFileReject(connection: RawConnection, transferId: MessageId, reason: String?) {
        fileRejects.add(transferId)
    }

    override suspend fun sendFileDataFrame(connection: RawConnection, frame: Frame) {
        fileData.add(frame.messageId to frame.chunkIndex)
        if (gateDataFrames) dataFrameReleases.receive()
    }

    override suspend fun sendFileDone(connection: RawConnection, transferId: MessageId) {
        fileDones.add(transferId)
    }

    override suspend fun sendFileCancel(connection: RawConnection, transferId: MessageId, reason: String?) {
        fileCancels.add(transferId to reason)
    }

    override fun events(connection: RawConnection): Flow<ProtocolEvent> = emptyFlow()
}
