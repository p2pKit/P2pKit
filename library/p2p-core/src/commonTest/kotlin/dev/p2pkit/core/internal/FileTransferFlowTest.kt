package dev.p2pkit.core.internal

import dev.p2pkit.core.AppId
import dev.p2pkit.core.FileTransferFailureKind
import dev.p2pkit.core.FileTransferPhase
import dev.p2pkit.core.P2pError
import dev.p2pkit.core.P2pKit
import dev.p2pkit.core.P2pLogger
import dev.p2pkit.core.P2pMessage
import dev.p2pkit.core.Peer
import dev.p2pkit.core.PeerId
import dev.p2pkit.core.Platform
import dev.p2pkit.core.Retryability
import dev.p2pkit.core.TransportKind
import dev.p2pkit.core.protocol.FileOfferPayload
import dev.p2pkit.core.protocol.Frame
import dev.p2pkit.core.protocol.HelloPayload
import dev.p2pkit.core.protocol.MessageId
import dev.p2pkit.core.protocol.P2pProtocol
import dev.p2pkit.core.protocol.ProtocolEvent
import dev.p2pkit.core.protocol.ProtocolSessionState
import dev.p2pkit.core.protocol.ProtocolFeatures
import dev.p2pkit.core.protocol.SecureFileCommit
import dev.p2pkit.core.protocol.SecureFileFinish
import dev.p2pkit.core.protocol.SecureFileOffer
import dev.p2pkit.core.protocol.SecureFileResult
import dev.p2pkit.core.protocol.FileResultCode
import dev.p2pkit.core.internal.security.sha256
import dev.p2pkit.core.testfixtures.FakeConnectionPair
import dev.p2pkit.core.testfixtures.FakeDataTransport
import dev.p2pkit.core.testfixtures.createTestKit
import dev.p2pkit.core.transfer.FileTransferConfig
import dev.p2pkit.core.transfer.FileTransferDestination
import dev.p2pkit.core.transfer.FileTransferState
import dev.p2pkit.core.transfer.PreparedFileSource
import dev.p2pkit.core.transfer.Sha256Digest
import dev.p2pkit.core.transfer.outgoingOfferWatchdogMillis
import dev.p2pkit.core.transfer.isTerminal
import dev.p2pkit.core.transport.RawConnection
import dev.p2pkit.core.transport.TransportContext
import dev.p2pkit.core.transport.TransportFactory
import dev.p2pkit.core.transport.TransportPair
import kotlin.concurrent.atomics.AtomicInt
import kotlin.concurrent.atomics.ExperimentalAtomicApi
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.CoroutineStart
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.Job
import kotlinx.coroutines.NonCancellable
import kotlinx.coroutines.async
import kotlinx.coroutines.cancel
import kotlinx.coroutines.cancelAndJoin
import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.collect
import kotlinx.coroutines.flow.emptyFlow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.onSubscription
import kotlinx.coroutines.launch
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.test.advanceTimeBy
import kotlinx.coroutines.test.runCurrent
import kotlinx.coroutines.test.runTest
import kotlinx.coroutines.withContext
import kotlinx.coroutines.withTimeout
import kotlinx.coroutines.yield
import kotlinx.io.Buffer
import kotlinx.io.IOException
import kotlinx.io.RawSource
import kotlinx.io.RawSink
import kotlinx.io.readByteArray
import kotlinx.io.write
import kotlin.random.Random
import kotlin.test.Test
import kotlin.test.assertContentEquals
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertFailsWith
import kotlin.test.assertIs
import kotlin.test.assertTrue

@OptIn(ExperimentalCoroutinesApi::class)
@Suppress("DEPRECATION")
class FileTransferFlowTest {

    private fun outgoingKit(name: String, outgoing: RawConnection, configureFileTransfer: Boolean = false): P2pKit =
        createTestKit {
            appId = AppId("com.example.ft")
            deviceName = name
            // The suite simulates two installations in one process. Explicit
            // storage prevents host-persistent defaults from leaking identity
            // across test runs and colliding with the seeded receiver.
            peerIdStorage = InMemoryPeerIdStorage(seed = PeerId("alice-id"))
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

            val transfer = outgoing.sendFile(
                name = "blob.bin",
                sizeBytes = payload.size.toLong(),
                mimeType = "application/octet-stream",
                source = Buffer().apply { write(payload) }
            )

            // Deliberately observe only after sendFile returns: retained state
            // must make the offer available to a late subscriber.
            val offer = withTimeout(5_000) {
                incomingSession.pendingFileOffers.first { it.isNotEmpty() }.first()
            }
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

            val offerDeferred = async {
                incomingSession.pendingFileOffers.first { it.isNotEmpty() }.first()
            }

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
            assertTrue(
                incomingSession.pendingFileOffers.value.isEmpty(),
                "oversize offer must never enter retained pending state"
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
            val retained = withTimeout(5_000) {
                incomingSession.pendingFileOffers.first { it.isNotEmpty() }
            }
            assertEquals(listOf("small.bin"), retained.map { it.name })
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

            // The receiver is the normal unanswered-offer timeout authority;
            // the sender watchdog has a response grace and cannot race it.
            val transfer = outgoing.sendFile(
                name = "x",
                sizeBytes = 16L,
                mimeType = null,
                source = Buffer().apply { write(ByteArray(16)) }
            )
            val terminal = withTimeout(5_000) {
                transfer.state.first { it.isTerminal() }
            }
            val rejected = assertIs<FileTransferState.Rejected>(terminal)
            assertEquals("timeout", rejected.reason)
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

            val offerDeferred = async {
                incomingSession.pendingFileOffers.first { it.isNotEmpty() }.first()
            }

            val transfer = outgoing.sendFile(
                name = "abort.bin",
                sizeBytes = 8L,
                mimeType = null,
                source = Buffer().apply { write(ByteArray(8)) }
            )
            val offer = withTimeout(5_000) { offerDeferred.await() }

            // Hold the sender's first FILE_DATA write so this is genuinely a
            // mid-stream cancellation test. With an eight-byte source and an
            // unconstrained in-memory wire, the transfer could complete
            // before cancel() was invoked, making the asserted lifecycle
            // outcome scheduler-dependent.
            pair.a.suspendWrites()
            val writesBeforeAccept = pair.a.writeAttempts
            val incomingTransfer = offer.accept(Buffer())

            withTimeout(5_000) {
                while (pair.a.writeAttempts == writesBeforeAccept) yield()
            }
            val cancellation = async { transfer.cancel("user aborted") }
            withTimeout(5_000) {
                transfer.state.first { it is FileTransferState.Cancelled }
            }
            pair.a.resumeWrites()
            withTimeout(5_000) { cancellation.await() }

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
            assertTrue(
                senderTerminal is FileTransferState.Cancelled,
                "Sender should observe Cancelled, got $senderTerminal"
            )
            assertTrue(
                receiverTerminal is FileTransferState.Cancelled,
                "Receiver should observe Cancelled, got $receiverTerminal"
            )
        } finally {
            pair.a.resumeWrites()
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

            val offerDeferred = async {
                incomingSession.pendingFileOffers.first { it.isNotEmpty() }.first()
            }

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

            val offerDeferred = async {
                incomingSession.pendingFileOffers.first { it.isNotEmpty() }.first()
            }

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

            val offerDeferred = async {
                incomingSession.pendingFileOffers.first { it.isNotEmpty() }.first()
            }

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

            val offerDeferred = async {
                incomingSession.pendingFileOffers.first { it.isNotEmpty() }.first()
            }

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
    fun pendingOfferIsRetainedBeforeObservationAndExpiresAtExactDeadline() = runTest {
        val protocol = RecordingFileProtocol()
        val config = FileTransferConfig(
            maxFileSizeBytes = 8L,
            chunkSizeBytes = 1,
            offerTimeoutMillis = 100L
        )
        val dispatcher = directDispatcher(backgroundScope, protocol, config)
        val id = MessageId.random(Random(5_001))

        dispatcher.onFileOffer(id, FileOfferPayload("retained.bin", 1L))

        val initial = dispatcher.pendingFileOffers.value
        assertEquals(listOf(id.toString()), initial.map { it.id })
        assertTrue(
            runCatching { (initial as MutableList).clear() }.isFailure,
            "retained offer snapshots must reject mutation"
        )

        runCurrent()
        advanceTimeBy(99L)
        runCurrent()
        assertEquals(listOf(id.toString()), dispatcher.pendingFileOffers.value.map { it.id })
        advanceTimeBy(1L)
        runCurrent()

        assertTrue(dispatcher.pendingFileOffers.value.isEmpty())
        val rejected = assertIs<FileTransferState.Rejected>(
            (initial.single() as IncomingFileSession).state.value
        )
        assertEquals("timeout", rejected.reason)
        withTimeout(5_000) { while (protocol.fileRejects.isEmpty()) yield() }
        assertEquals(id, protocol.fileRejects.single())
        assertFailsWith<IllegalStateException> { initial.single().accept(Buffer()) }
        assertFailsWith<IllegalStateException> { initial.single().reject("late") }
        assertTrue(dispatcher.pendingFileOffers.value.isEmpty(), "late response must not revive an expired offer")
    }

    @Test
    fun pendingOffersStayOrderedAndEveryTerminalOwnershipPathRemovesThem() = runBlocking<Unit> {
        val scope = CoroutineScope(coroutineContext + Job())
        val protocol = RecordingFileProtocol()
        val dispatcher = directDispatcher(scope, protocol)
        try {
            val firstId = MessageId.random(Random(5_010))
            val secondId = MessageId.random(Random(5_011))
            dispatcher.onFileOffer(firstId, FileOfferPayload("first.bin", 1L))
            dispatcher.onFileOffer(secondId, FileOfferPayload("second.bin", 1L))

            val initial = dispatcher.pendingFileOffers.value
            assertEquals(listOf("first.bin", "second.bin"), initial.map { it.name })
            initial.first().reject("declined")
            assertEquals(listOf("second.bin"), dispatcher.pendingFileOffers.value.map { it.name })

            dispatcher.onFileCancel(secondId, "remote cancelled")
            assertTrue(dispatcher.pendingFileOffers.value.isEmpty())
            assertIs<FileTransferState.Cancelled>((initial[1] as IncomingFileSession).state.value)

            val closingId = MessageId.random(Random(5_012))
            dispatcher.onFileOffer(closingId, FileOfferPayload("closing.bin", 1L))
            val closingOffer = dispatcher.pendingFileOffers.value.single() as IncomingFileSession
            dispatcher.closeAll("session closing")
            assertTrue(dispatcher.pendingFileOffers.value.isEmpty())
            assertIs<FileTransferState.Cancelled>(closingOffer.state.value)
        } finally {
            scope.cancel()
        }
    }

    @Test
    fun offerRemainsPendingUntilFileAcceptWriteCommits() = runBlocking {
        val scope = CoroutineScope(coroutineContext + Job())
        val protocol = RecordingFileProtocol().apply { gateAccept = true }
        val dispatcher = directDispatcher(scope, protocol)
        try {
            val id = MessageId.random(Random(5_020))
            dispatcher.onFileOffer(id, FileOfferPayload("commit.bin", 1L))
            val offer = dispatcher.pendingFileOffers.value.single()

            val accepting = async { offer.accept(Buffer()) }
            protocol.acceptStarted.await()
            assertTrue(
                dispatcher.pendingFileOffers.value.single() === offer,
                "an in-flight FILE_ACCEPT must not remove retained ownership"
            )

            protocol.acceptReleases.send(Unit)
            assertTrue(accepting.await() === offer)
            assertTrue(dispatcher.pendingFileOffers.value.isEmpty())
        } finally {
            scope.cancel()
        }
    }

    @Test
    fun exactDuplicateOfferIsIdempotentAndDoesNotResetDeadlineOrReemit() = runTest {
        val protocol = RecordingFileProtocol()
        val config = FileTransferConfig(
            maxFileSizeBytes = 8L,
            chunkSizeBytes = 1,
            offerTimeoutMillis = 100L
        )
        val dispatcher = directDispatcher(backgroundScope, protocol, config)
        val emitted = Channel<IncomingFileSession>(Channel.UNLIMITED)
        backgroundScope.launch(start = CoroutineStart.UNDISPATCHED) {
            dispatcher.incomingFiles.collect { emitted.send(it as IncomingFileSession) }
        }
        val id = MessageId.random(Random(5_030))
        val payload = FileOfferPayload("same.bin", 1L, "application/octet-stream")

        dispatcher.onFileOffer(id, payload)
        runCurrent()
        val admitted = emitted.receive()
        advanceTimeBy(60L)
        dispatcher.onFileOffer(id, payload.copy())
        runCurrent()

        assertTrue(dispatcher.pendingFileOffers.value.single() === admitted)
        assertTrue(emitted.tryReceive().isFailure, "an exact duplicate must not re-emit")
        advanceTimeBy(40L)
        runCurrent()
        assertTrue(dispatcher.pendingFileOffers.value.isEmpty(), "duplicate must not extend retention")
        assertIs<FileTransferState.Rejected>(admitted.state.value)
    }

    @Test
    fun conflictingDuplicateOfferIsTypedProtocolFailureAndCannotReplaceOwnership() = runTest {
        val dispatcher = directDispatcher(backgroundScope, RecordingFileProtocol())
        val id = MessageId.random(Random(5_040))
        dispatcher.onFileOffer(id, FileOfferPayload("original.bin", 1L))
        val original = dispatcher.pendingFileOffers.value.single()

        val failure = assertFailsWith<P2pError.FileTransferFailed> {
            dispatcher.onFileOffer(id, FileOfferPayload("conflict.bin", 1L))
        }
        assertEquals(FileTransferFailureKind.TRANSFER_PROTOCOL, failure.kind)
        assertEquals(FileTransferPhase.OFFER, failure.phase)
        assertEquals(Retryability.NOT_RETRYABLE, failure.retryability)
        assertEquals(id.toString(), failure.transferId)
        assertTrue(dispatcher.pendingFileOffers.value.single() === original)
    }

    @Test
    fun concurrentOfferResponsesHaveOneWinnerAndDoNotReviveTerminalOffer() = runBlocking<Unit> {
        val scope = CoroutineScope(coroutineContext + Job())
        val protocol = RecordingFileProtocol().apply { gateAccept = true }
        val dispatcher = directDispatcher(scope, protocol)
        try {
            val id = MessageId.random(Random(5_050))
            dispatcher.onFileOffer(id, FileOfferPayload("race.bin", 1L))
            val offer = dispatcher.pendingFileOffers.value.single()

            val accepting = async { offer.accept(Buffer()) }
            protocol.acceptStarted.await()
            assertFailsWith<IllegalStateException> { offer.accept(Buffer()) }
            assertFailsWith<IllegalStateException> { offer.reject("too late") }
            protocol.acceptReleases.send(Unit)
            accepting.await()

            assertTrue(dispatcher.pendingFileOffers.value.isEmpty())
            assertFailsWith<IllegalStateException> { offer.accept(Buffer()) }
            assertFailsWith<IllegalStateException> { offer.reject("already accepted") }
        } finally {
            scope.cancel()
        }
    }

    @Test
    fun pendingOfferCapacityIsBoundedAtSixtyFour() = runTest {
        val protocol = RecordingFileProtocol()
        val dispatcher = directDispatcher(
            backgroundScope,
            protocol,
            FileTransferConfig(maxFileSizeBytes = 1L, offerTimeoutMillis = 60_000L, chunkSizeBytes = 1)
        )
        repeat(64) { index ->
            dispatcher.onFileOffer(
                MessageId.random(Random(5_100 + index)),
                FileOfferPayload("pending-$index.bin", 1L)
            )
        }
        assertEquals(64, dispatcher.pendingFileOffers.value.size)

        val overflowId = MessageId.random(Random(5_200))
        dispatcher.onFileOffer(overflowId, FileOfferPayload("overflow.bin", 1L))
        assertEquals(64, dispatcher.pendingFileOffers.value.size)
        assertEquals(overflowId, protocol.fileRejects.single())
    }

    @Test
    fun deprecatedOfferStreamDropsBackpressuredEventInsteadOfDeferringItPastClose() = runTest {
        val protocol = RecordingFileProtocol()
        val dispatcher = directDispatcher(
            backgroundScope,
            protocol,
            FileTransferConfig(maxFileSizeBytes = 1L, offerTimeoutMillis = 60_000L, chunkSizeBytes = 1)
        )
        val delivered = mutableListOf<String>()
        val firstDelivered = CompletableDeferred<Unit>()
        val releaseCollector = CompletableDeferred<Unit>()
        backgroundScope.launch(start = CoroutineStart.UNDISPATCHED) {
            dispatcher.incomingFiles.collect { offer ->
                delivered += offer.name
                if (offer.name == "migration-0.bin") {
                    firstDelivered.complete(Unit)
                    releaseCollector.await()
                }
            }
        }

        suspend fun admitAndReject(index: Int) {
            dispatcher.onFileOffer(
                MessageId.random(Random(5_300 + index)),
                FileOfferPayload("migration-$index.bin", 1L)
            )
            if (index == 0) {
                runCurrent()
                firstDelivered.await()
            }
            dispatcher.pendingFileOffers.value.single().reject("test cleanup")
            runCurrent()
        }

        // One event is held by the collector and 64 fit in the bounded
        // migration buffer. The 66th event must be dropped synchronously;
        // it must not live in an unowned emit coroutine until after close.
        repeat(66) { index -> admitAndReject(index) }
        assertEquals(listOf("migration-0.bin"), delivered)

        dispatcher.closeAll("test close")
        releaseCollector.complete(Unit)
        runCurrent()

        assertEquals((0..64).map { "migration-$it.bin" }, delivered)
        assertFalse(delivered.contains("migration-65.bin"))
    }

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
    fun rejectReturnsAfterDeadlineWhenControlWriteIgnoresCancellation() = runBlocking {
        val scope = CoroutineScope(coroutineContext + Job())
        val protocol = RecordingFileProtocol().apply { gateReject = true }
        val dispatcher = directDispatcher(
            scope,
            protocol,
            FileTransferConfig(maxFileSizeBytes = 1L, offerTimeoutMillis = 50L, chunkSizeBytes = 1)
        )
        try {
            val id = MessageId.random(Random(8_010))
            dispatcher.onFileOffer(id, FileOfferPayload("wedged-reject.bin", 1L))
            val offer = assertIs<IncomingFileSession>(dispatcher.pendingFileOffers.value.single())
            val rejecting = async { offer.reject("not now") }

            protocol.rejectStarted.await()
            withTimeout(5_000) { rejecting.await() }

            assertIs<FileTransferState.Rejected>(offer.state.value)
            assertTrue(dispatcher.pendingFileOffers.value.isEmpty())
            assertEquals(listOf(id), protocol.fileRejects)

            // The independently owned best-effort task was cancelled at its
            // deadline. Release the deliberately non-cooperative fake and
            // prove it leaves no live test work behind.
            protocol.rejectRelease.complete(Unit)
            withTimeout(5_000) { protocol.rejectExited.await() }
        } finally {
            protocol.rejectRelease.complete(Unit)
            scope.cancel()
        }
    }

    @Test
    fun cancelledAcceptReturnsAfterDeadlineWhenCompensationIgnoresCancellation() = runBlocking {
        val scope = CoroutineScope(coroutineContext + Job())
        val protocol = RecordingFileProtocol().apply {
            gateAccept = true
            gateCancel = true
        }
        val dispatcher = directDispatcher(
            scope,
            protocol,
            FileTransferConfig(maxFileSizeBytes = 1L, offerTimeoutMillis = 50L, chunkSizeBytes = 1)
        )
        try {
            val id = MessageId.random(Random(8_011))
            dispatcher.onFileOffer(id, FileOfferPayload("wedged-accept.bin", 1L))
            val offer = assertIs<IncomingFileSession>(dispatcher.pendingFileOffers.value.single())
            val accepting = async { offer.accept(Buffer()) }

            protocol.acceptStarted.await()
            accepting.cancel(CancellationException("cancel wedged accept"))
            protocol.cancelStarted.await()
            withTimeout(5_000) { accepting.join() }

            assertIs<FileTransferState.Cancelled>(offer.state.value)
            assertFalse(offer.retainsReceiver())
            assertTrue(dispatcher.pendingFileOffers.value.isEmpty())
            assertEquals(
                listOf<Pair<MessageId, String?>>(id to "accept did not commit"),
                protocol.fileCancels
            )

            // Release the deliberately cancellation-ignoring fake only after
            // the caller has returned, then prove its independent task exits.
            protocol.cancelRelease.complete(Unit)
            withTimeout(5_000) { protocol.cancelExited.await() }
        } finally {
            protocol.cancelRelease.complete(Unit)
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
    fun preparedSourceReturningAfterTerminalReleaseIsClosedAndCannotBeRetained() = runTest {
        val dispatcher = directDispatcher(backgroundScope, RecordingFileProtocol())
        val opened = CloseTrackingSource(Buffer().apply { write(byteArrayOf(1, 2, 3)) })
        lateinit var handle: OutgoingFileTransferImpl
        val prepared = HookedPreparedSource(
            content = byteArrayOf(1, 2, 3),
            opened = opened,
            beforeOpenReturns = { handle.closeSourceOnce() }
        )
        handle = OutgoingFileTransferImpl(
            peer = syntheticPeer("peer-id", "Peer"),
            name = "late-open.bin",
            sizeBytes = prepared.sizeBytes,
            mimeType = null,
            transferId = MessageId.random(Random(8_000)),
            source = null,
            preparedSource = prepared,
            expectedDigest = prepared.sha256,
            offerHash = null,
            dispatcher = dispatcher
        )

        assertFailsWith<IllegalStateException> { handle.openPreparedSource() }

        assertEquals(1, prepared.openCount)
        assertEquals(1, opened.closeCount)
        assertFalse(handle.retainsSource())
        assertFailsWith<IllegalStateException> { handle.sourceOrThrow() }
    }

    @Test
    fun sourceClosedExactlyOnceOnOfferWriteFailure() = runBlocking {
        val scope = CoroutineScope(coroutineContext + Job())
        val protocol = RecordingFileProtocol()
        val dispatcher = directDispatcher(scope, protocol)
        try {
            val wireFailure = IOException("wire failed before FILE_OFFER")
            protocol.offerFailure = wireFailure
            val source = CloseTrackingSource(Buffer().apply { write(ByteArray(8) { 5 }) })
            val failure = assertFailsWith<P2pError.FileTransferFailed> {
                dispatcher.sendFile("never-offered.bin", 8L, null, source)
            }
            assertEquals(FileTransferFailureKind.TRANSPORT, failure.kind)
            assertEquals(FileTransferPhase.OFFER, failure.phase)
            assertEquals(Retryability.RETRY_NEW_SESSION, failure.retryability)
            assertTrue(failure.transferId != null)
            assertTrue(failure.cause === wireFailure)
            repeat(10) { yield() }
            assertEquals(1, source.closeCount, "offer-write failure must release the source exactly once")
        } finally {
            scope.cancel()
        }
    }

    @Test
    fun acceptWriteFailureIsTypedAndClearsPendingReceiverOwnership() = runBlocking {
        val scope = CoroutineScope(coroutineContext + Job())
        val raw = IOException("accept control write failed")
        val protocol = RecordingFileProtocol().apply { acceptFailure = raw }
        val dispatcher = directDispatcher(scope, protocol)
        try {
            val id = MessageId.random(Random(8_001))
            dispatcher.onFileOffer(id, FileOfferPayload("accept-failure.bin", 1L))
            val offer = dispatcher.pendingFileOffers.value.single() as IncomingFileSession

            val failure = assertFailsWith<P2pError.FileTransferFailed> {
                offer.accept(Buffer())
            }
            assertEquals(FileTransferFailureKind.TRANSPORT, failure.kind)
            assertEquals(FileTransferPhase.ACCEPT, failure.phase)
            assertEquals(Retryability.RETRY_NEW_SESSION, failure.retryability)
            assertEquals(offer.id, failure.transferId)
            val preserved = assertIs<IOException>(failure.cause)
            assertEquals(raw.message, preserved.message)
            assertTrue(dispatcher.pendingFileOffers.value.isEmpty())
            assertFalse(offer.retainsReceiver())
            assertEquals(id, protocol.fileCancels.single().first)
        } finally {
            scope.cancel()
        }
    }

    @Test
    fun dataWriteFailureIsTypedTransportSendFailureWithCause() = runBlocking {
        val scope = CoroutineScope(coroutineContext + Job())
        val raw = IOException("data write failed")
        val protocol = RecordingFileProtocol().apply { dataFailure = raw }
        val dispatcher = directDispatcher(scope, protocol)
        try {
            val transfer = dispatcher.sendFile(
                "data-failure.bin",
                1L,
                null,
                Buffer().apply { writeByte(1) }
            )
            dispatcher.onFileAccept(protocol.fileOffers.single())

            val failed = assertIs<FileTransferState.Failed>(
                withTimeout(5_000) { transfer.state.first { it.isTerminal() } }
            )
            val failure = assertIs<P2pError.FileTransferFailed>(failed.error)
            assertEquals(FileTransferFailureKind.TRANSPORT, failure.kind)
            assertEquals(FileTransferPhase.SEND, failure.phase)
            assertEquals(Retryability.RETRY_NEW_SESSION, failure.retryability)
            assertEquals(transfer.id, failure.transferId)
            assertTrue(failure.cause === raw)
        } finally {
            scope.cancel()
        }
    }

    @Test
    fun receiverSinkWriteFailureIsTypedStorageReceiveFailure() = runBlocking {
        val scope = CoroutineScope(coroutineContext + Job())
        val protocol = RecordingFileProtocol()
        val dispatcher = directDispatcher(
            scope,
            protocol,
            FileTransferConfig(maxFileSizeBytes = 16_384L, offerTimeoutMillis = 60_000L, chunkSizeBytes = 16_384)
        )
        val raw = IOException("receiver storage write failed")
        val sink = object : RawSink {
            override fun write(source: Buffer, byteCount: Long) {
                throw raw
            }

            override fun flush() = Unit
            override fun close() = Unit
        }
        try {
            val id = MessageId.random(Random(8_010))
            dispatcher.onFileOffer(id, FileOfferPayload("storage-failure.bin", 9_000L))
            val offer = dispatcher.pendingFileOffers.value.single() as IncomingFileSession
            offer.accept(sink)
            dispatcher.onFileData(
                Frame(
                    type = dev.p2pkit.core.protocol.PacketType.FILE_DATA,
                    flags = dev.p2pkit.core.protocol.FrameFlags.LAST_CHUNK.toByte(),
                    messageId = id,
                    chunkIndex = 0,
                    totalChunks = 1,
                    payload = ByteArray(9_000)
                )
            )

            val failed = assertIs<FileTransferState.Failed>(offer.state.value)
            val failure = assertIs<P2pError.FileTransferFailed>(failed.error)
            assertEquals(FileTransferFailureKind.STORAGE, failure.kind)
            assertEquals(FileTransferPhase.RECEIVE, failure.phase)
            assertEquals(Retryability.RETRY_AFTER_USER_ACTION, failure.retryability)
            assertEquals(offer.id, failure.transferId)
            assertTrue(failure.cause === raw)
            assertEquals(id, protocol.fileCancels.single().first)
            assertFalse(offer.retainsReceiver())
        } finally {
            scope.cancel()
        }
    }

    @Test
    fun invalidChunkOrderingIsTypedTransferProtocolFailure() = runBlocking {
        val scope = CoroutineScope(coroutineContext + Job())
        val protocol = RecordingFileProtocol()
        val dispatcher = directDispatcher(scope, protocol)
        try {
            val id = MessageId.random(Random(8_020))
            dispatcher.onFileOffer(id, FileOfferPayload("ordering.bin", 2L))
            val offer = dispatcher.pendingFileOffers.value.single() as IncomingFileSession
            offer.accept(Buffer())
            dispatcher.onFileData(
                Frame(
                    type = dev.p2pkit.core.protocol.PacketType.FILE_DATA,
                    flags = dev.p2pkit.core.protocol.FrameFlags.LAST_CHUNK.toByte(),
                    messageId = id,
                    chunkIndex = 1,
                    totalChunks = 2,
                    payload = byteArrayOf(1)
                )
            )

            val failed = assertIs<FileTransferState.Failed>(offer.state.value)
            val failure = assertIs<P2pError.FileTransferFailed>(failed.error)
            assertEquals(FileTransferFailureKind.TRANSFER_PROTOCOL, failure.kind)
            assertEquals(FileTransferPhase.RECEIVE, failure.phase)
            assertEquals(Retryability.NOT_RETRYABLE, failure.retryability)
            assertEquals(offer.id, failure.transferId)
            assertIs<P2pError.ProtocolError>(failure.cause)
            assertEquals(id, protocol.fileCancels.single().first)
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
            val error = assertIs<P2pError.FileTransferFailed>(failed.error)
            assertEquals(FileTransferFailureKind.REMOTE_DISCONNECTED, error.kind)
            assertEquals(FileTransferPhase.OFFER, error.phase)
            assertEquals(Retryability.RETRY_NEW_SESSION, error.retryability)
            assertEquals(transfer.id, error.transferId)
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
    fun closeAllJoinsCancelledSenderBeforeDispatcherCanReopen() = runBlocking {
        val scope = CoroutineScope(coroutineContext + Job())
        val protocol = RecordingFileProtocol().apply { gateDataFrames = true }
        val dispatcher = directDispatcher(
            scope,
            protocol,
            FileTransferConfig(offerTimeoutMillis = 60_000L, chunkSizeBytes = 16)
        )
        try {
            val transfer = dispatcher.sendFile(
                "settle-before-reopen.bin",
                16L,
                null,
                Buffer().apply { write(ByteArray(16) { 9 }) }
            )
            dispatcher.onFileAccept(protocol.fileOffers.single())
            withTimeout(5_000) { while (protocol.fileData.isEmpty()) yield() }

            dispatcher.closeAll("reconnect: connection replaced")

            assertTrue(
                protocol.dataFrameExited.isCompleted,
                "closeAll must join the cancelled sender, not merely request cancellation"
            )
            assertIs<FileTransferState.Failed>(transfer.state.value)
            dispatcher.reopen()
        } finally {
            scope.cancel()
        }
    }

    @Test
    fun acceptQueuedBeforeReopenCannotWriteOnReplacementEpoch() = runTest {
        val protocol = RecordingFileProtocol()
        val oldConnection = FakeConnectionPair().a
        val replacementConnection = FakeConnectionPair().a
        var currentConnection: RawConnection = oldConnection
        val writeGate = Mutex()
        writeGate.lock()
        var gateHeld = true
        val dispatcher = directDispatcher(
            backgroundScope,
            protocol,
            connectionProvider = { currentConnection },
            sendMutex = writeGate
        )
        try {
            val id = MessageId.random(Random(8_030))
            dispatcher.onFileOffer(id, FileOfferPayload("queued-accept.bin", 1L))
            val offer = dispatcher.pendingFileOffers.value.single()
            val accepting = async { runCatching { offer.accept(Buffer()) } }
            runCurrent()

            val jobs = dispatcher.beginCloseAll("reconnect: connection replaced")
            dispatcher.awaitCloseAll(jobs)
            currentConnection = replacementConnection
            dispatcher.reopen()
            writeGate.unlock()
            gateHeld = false
            runCurrent()

            assertIs<P2pError.FileTransferFailed>(accepting.await().exceptionOrNull())
            assertTrue(
                protocol.fileAcceptConnections.isEmpty(),
                "a pre-reconnect accept must fail before invoking the protocol on the replacement"
            )
            assertTrue(
                protocol.fileCancels.isEmpty(),
                "stale accept compensation must not emit FILE_CANCEL on the replacement"
            )
        } finally {
            if (gateHeld) writeGate.unlock()
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
            val failure = assertFailsWith<P2pError.FileTransferFailed> {
                dispatcher.sendFile(
                    "late.bin", 8L, null,
                    CloseTrackingSource(Buffer().apply { write(ByteArray(8)) })
                )
            }
            assertEquals(FileTransferFailureKind.REMOTE_DISCONNECTED, failure.kind)
            assertEquals(FileTransferPhase.OFFER, failure.phase)
            assertEquals(Retryability.RETRY_NEW_SESSION, failure.retryability)
            assertEquals(null, failure.transferId)
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
            val failure = assertIs<P2pError.FileTransferFailed>(failed.error)
            assertEquals(FileTransferFailureKind.SOURCE_IO, failure.kind)
            assertEquals(FileTransferPhase.SOURCE_READ, failure.phase)
            assertEquals(Retryability.RETRY_AFTER_USER_ACTION, failure.retryability)
            assertEquals(transfer.id, failure.transferId)
            assertIs<IOException>(failure.cause)
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

    @Test
    fun acceptCancellationRollsBackReceiverAndNotifiesPeer() = runBlocking {
        val scope = CoroutineScope(coroutineContext + Job())
        val protocol = RecordingFileProtocol().apply { gateAccept = true }
        val dispatcher = directDispatcher(scope, protocol)
        try {
            val subscribed = CompletableDeferred<Unit>()
            val offerDeferred = async(start = CoroutineStart.UNDISPATCHED) {
                dispatcher.incomingFiles
                    .onSubscription { subscribed.complete(Unit) }
                    .first()
            }
            subscribed.await()
            val id = MessageId.random(Random(91))
            dispatcher.onFileOffer(id, FileOfferPayload("cancel.bin", 8L))
            val offer = offerDeferred.await() as IncomingFileSession

            val accepting = async { offer.accept(Buffer()) }
            protocol.acceptStarted.await()
            accepting.cancelAndJoin()

            assertIs<FileTransferState.Cancelled>(offer.state.value)
            assertFalse(offer.retainsReceiver(), "cancelled accept must release its receiver reference")
            assertEquals(id, protocol.fileCancels.single().first)
        } finally {
            scope.cancel()
        }
    }

    @Test
    fun acceptedIdleDeadlineIsExactAndPositiveProgressRearmsIt() = runTest {
        val protocol = RecordingFileProtocol()
        val dispatcher = directDispatcher(
            backgroundScope,
            protocol,
            FileTransferConfig(maxFileSizeBytes = 2L, offerTimeoutMillis = 100L, chunkSizeBytes = 1)
        )
        val offerDeferred = async(start = CoroutineStart.UNDISPATCHED) {
            dispatcher.incomingFiles.first()
        }
        val id = MessageId.random(Random(92))
        dispatcher.onFileOffer(id, FileOfferPayload("idle.bin", 2L))
        runCurrent()
        val offer = offerDeferred.await() as IncomingFileSession
        offer.accept(Buffer())

        advanceTimeBy(60L)
        dispatcher.onFileData(
            Frame(
                type = dev.p2pkit.core.protocol.PacketType.FILE_DATA,
                flags = 0,
                messageId = id,
                chunkIndex = 0,
                totalChunks = 2,
                payload = byteArrayOf(1)
            )
        )
        advanceTimeBy(99L)
        runCurrent()
        assertFalse(offer.state.value.isTerminal())
        advanceTimeBy(1L)
        runCurrent()
        val failed = assertIs<FileTransferState.Failed>(offer.state.value)
        val failure = assertIs<P2pError.FileTransferFailed>(failed.error)
        assertEquals(FileTransferFailureKind.TIMEOUT, failure.kind)
        assertEquals(FileTransferPhase.RECEIVE, failure.phase)
        assertEquals(Retryability.RETRY_NEW_SESSION, failure.retryability)
        assertEquals(offer.id, failure.transferId)
        assertTrue(failure.reason.startsWith("idle transfer timeout"))
        assertEquals(id, protocol.fileCancels.single().first)
        assertFalse(offer.retainsReceiver())
    }

    @Test
    fun overallDeadlineWinsDespiteContinuousPositiveProgress() = runTest {
        val protocol = RecordingFileProtocol()
        val dispatcher = directDispatcher(
            backgroundScope,
            protocol,
            FileTransferConfig(maxFileSizeBytes = 100L, offerTimeoutMillis = 10L, chunkSizeBytes = 1)
        )
        val offerDeferred = async(start = CoroutineStart.UNDISPATCHED) {
            dispatcher.incomingFiles.first()
        }
        val id = MessageId.random(Random(93))
        dispatcher.onFileOffer(id, FileOfferPayload("overall.bin", 100L))
        runCurrent()
        val offer = offerDeferred.await() as IncomingFileSession
        offer.accept(Buffer())

        repeat(22) { index ->
            advanceTimeBy(9L)
            dispatcher.onFileData(
                Frame(
                    type = dev.p2pkit.core.protocol.PacketType.FILE_DATA,
                    flags = 0,
                    messageId = id,
                    chunkIndex = index,
                    totalChunks = 100,
                    payload = byteArrayOf(index.toByte())
                )
            )
        }
        assertFalse(offer.state.value.isTerminal())
        advanceTimeBy(2L)
        runCurrent()
        val failed = assertIs<FileTransferState.Failed>(offer.state.value)
        val failure = assertIs<P2pError.FileTransferFailed>(failed.error)
        assertEquals(FileTransferFailureKind.TIMEOUT, failure.kind)
        assertEquals(FileTransferPhase.RECEIVE, failure.phase)
        assertEquals(Retryability.RETRY_NEW_SESSION, failure.retryability)
        assertTrue(failure.reason.startsWith("overall transfer timeout"))
    }

    @Test
    fun duplicateTransferIdsCannotOverwriteExistingOwnership() = runBlocking {
        val scope = CoroutineScope(coroutineContext + Job())
        val protocol = RecordingFileProtocol()
        val constantRandom = object : Random() {
            override fun nextBits(bitCount: Int): Int = 0
        }
        val dispatcher = directDispatcher(scope, protocol, random = constantRandom)
        try {
            val firstSource = CloseTrackingSource(Buffer().apply { write(ByteArray(1)) })
            val secondSource = CloseTrackingSource(Buffer().apply { write(ByteArray(1)) })
            val first = dispatcher.sendFile("first.bin", 1L, null, firstSource)
            val failure = assertFailsWith<P2pError.FileTransferFailed> {
                dispatcher.sendFile("second.bin", 1L, null, secondSource)
            }
            assertEquals(FileTransferFailureKind.TRANSFER_PROTOCOL, failure.kind)
            assertEquals(FileTransferPhase.OFFER, failure.phase)
            assertEquals(Retryability.RETRY_NEW_SESSION, failure.retryability)
            assertEquals(null, failure.transferId)
            assertTrue(failure.reason.contains("unique transfer id"))
            assertEquals(1, protocol.fileOffers.size)
            assertEquals(1, secondSource.closeCount)
            first.cancel("cleanup")
            assertEquals(1, firstSource.closeCount)
        } finally {
            scope.cancel()
        }
    }

    @Test
    fun rejectAfterAcceptCannotRegressOrTerminateStreamingTransfer() = runBlocking {
        val scope = CoroutineScope(coroutineContext + Job())
        val protocol = RecordingFileProtocol().apply { gateDataFrames = true }
        val dispatcher = directDispatcher(
            scope,
            protocol,
            FileTransferConfig(offerTimeoutMillis = 60_000L, chunkSizeBytes = 16)
        )
        try {
            val transfer = dispatcher.sendFile(
                "transition.bin",
                16L,
                null,
                Buffer().apply { write(ByteArray(16)) }
            )
            val id = protocol.fileOffers.single()
            dispatcher.onFileAccept(id)
            withTimeout(5_000) { while (protocol.fileData.isEmpty()) yield() }
            dispatcher.onFileReject(id, "late reject")
            assertFalse(transfer.state.value is FileTransferState.Rejected)
            protocol.dataFrameReleases.send(Unit)
            assertIs<FileTransferState.Completed>(
                withTimeout(5_000) { transfer.state.first { it.isTerminal() } }
            )
        } finally {
            scope.cancel()
        }
        Unit
    }

    @Test
    fun terminalStateFreezesProgressAndReleasesSource() = runBlocking {
        val scope = CoroutineScope(coroutineContext + Job())
        val protocol = RecordingFileProtocol().apply { gateDataFrames = true }
        val dispatcher = directDispatcher(
            scope,
            protocol,
            FileTransferConfig(offerTimeoutMillis = 60_000L, chunkSizeBytes = 16)
        )
        try {
            val source = CloseTrackingSource(Buffer().apply { write(ByteArray(16)) })
            val transfer = dispatcher.sendFile("freeze.bin", 16L, null, source) as OutgoingFileTransferImpl
            dispatcher.onFileAccept(protocol.fileOffers.single())
            withTimeout(5_000) { while (protocol.fileData.isEmpty()) yield() }
            transfer.cancel("stop before write commit")
            assertIs<FileTransferState.Cancelled>(transfer.state.value)
            assertEquals(0L, transfer.bytesTransferred.value)
            assertFalse(transfer.retainsSource())
            assertEquals(1, source.closeCount)
        } finally {
            scope.cancel()
        }
    }

    @Test
    fun sinkWriteAndCancellationAreSerializedPerTransfer() = runBlocking {
        val scope = CoroutineScope(coroutineContext + Job())
        val protocol = RecordingFileProtocol()
        val dispatcher = directDispatcher(scope, protocol)
        try {
            val offerDeferred = async(start = CoroutineStart.UNDISPATCHED) {
                dispatcher.incomingFiles.first()
            }
            val id = MessageId.random(Random(94))
            val payload = ByteArray(64 * 1024) { 7 }
            dispatcher.onFileOffer(id, FileOfferPayload("serialized.bin", payload.size.toLong()))
            val offer = offerDeferred.await() as IncomingFileSession
            val sink = GatedSink()
            offer.accept(sink)

            val data = async(Dispatchers.Default) {
                dispatcher.onFileData(
                    Frame(
                        type = dev.p2pkit.core.protocol.PacketType.FILE_DATA,
                        flags = dev.p2pkit.core.protocol.FrameFlags.LAST_CHUNK.toByte(),
                        messageId = id,
                        chunkIndex = 0,
                        totalChunks = 1,
                        payload = payload
                    )
                )
            }
            sink.entered.await()
            val cancellation = async(start = CoroutineStart.UNDISPATCHED) {
                offer.cancel("concurrent cancel")
            }
            assertFalse(cancellation.isCompleted, "cancel must wait for the active sink operation")
            sink.release.complete(Unit)
            data.await()
            cancellation.await()

            assertIs<FileTransferState.Cancelled>(offer.state.value)
            assertFalse(offer.retainsReceiver())
            assertEquals(payload.size.toLong(), offer.bytesTransferred.value)
        } finally {
            scope.cancel()
        }
    }

    @Test
    fun stalledAcceptedCapacityIsReleasedByIdleDeadlines() = runTest {
        val protocol = RecordingFileProtocol()
        val config = FileTransferConfig(
            maxFileSizeBytes = 64L,
            chunkSizeBytes = 1,
            offerTimeoutMillis = 100L
        )
        val dispatcher = directDispatcher(backgroundScope, protocol, config)
        val delivered = Channel<IncomingFileSession>(Channel.UNLIMITED)
        backgroundScope.launch(start = CoroutineStart.UNDISPATCHED) {
            dispatcher.incomingFiles.collect { delivered.send(it as IncomingFileSession) }
        }
        val accepted = mutableListOf<IncomingFileSession>()
        repeat(64) { index ->
            val id = MessageId.random(Random(1_000 + index))
            dispatcher.onFileOffer(id, FileOfferPayload("stalled-$index.bin", 1L))
            runCurrent()
            delivered.receive().also {
                it.accept(Buffer())
                accepted += it
            }
        }
        val overflowId = MessageId.random(Random(2_000))
        dispatcher.onFileOffer(overflowId, FileOfferPayload("overflow.bin", 1L))
        runCurrent()
        assertEquals(overflowId, protocol.fileRejects.single())

        advanceTimeBy(100L)
        runCurrent()
        assertTrue(accepted.all { it.state.value is FileTransferState.Failed })
        accepted.forEach { offer ->
            val failed = assertIs<FileTransferState.Failed>(offer.state.value)
            val failure = assertIs<P2pError.FileTransferFailed>(failed.error)
            assertEquals(FileTransferFailureKind.TIMEOUT, failure.kind)
            assertEquals(FileTransferPhase.RECEIVE, failure.phase)
        }
        assertTrue(accepted.all { !it.retainsReceiver() })

        val replacementId = MessageId.random(Random(2_001))
        dispatcher.onFileOffer(replacementId, FileOfferPayload("replacement.bin", 1L))
        runCurrent()
        assertEquals(replacementId, delivered.receive().transferId)
    }

    @Test
    fun outgoingOfferWatchdogStartsOnlyAfterWireWriteCompletes() = runTest {
        val protocol = RecordingFileProtocol().apply { gateOffer = true }
        val config = FileTransferConfig(
            maxFileSizeBytes = 8L,
            chunkSizeBytes = 1,
            offerTimeoutMillis = 100L
        )
        val dispatcher = directDispatcher(backgroundScope, protocol, config)
        val sending = async {
            dispatcher.sendFile("gated-offer.bin", 1L, null, Buffer().apply { writeByte(1) })
        }
        protocol.offerStarted.await()
        advanceTimeBy(config.outgoingOfferWatchdogMillis * 2L)
        runCurrent()
        assertFalse(sending.isCompleted, "watchdog cannot run before FILE_OFFER write returns")

        protocol.offerRelease.complete(Unit)
        runCurrent()
        val transfer = sending.await()
        advanceTimeBy(config.outgoingOfferWatchdogMillis - 1L)
        runCurrent()
        assertFalse(transfer.state.value.isTerminal())
        advanceTimeBy(1L)
        runCurrent()
        val failed = assertIs<FileTransferState.Failed>(transfer.state.value)
        val failure = assertIs<P2pError.FileTransferFailed>(failed.error)
        assertEquals(FileTransferFailureKind.TIMEOUT, failure.kind)
        assertEquals(FileTransferPhase.OFFER, failure.phase)
        assertEquals(Retryability.RETRY_SAME_SESSION, failure.retryability)
        assertEquals(transfer.id, failure.transferId)
    }

    @Test
    fun preparedSenderCompletesOnlyAfterMatchingDurableCommit() = runTest {
        val protocol = RecordingFileProtocol()
        val dispatcher = directDispatcher(
            backgroundScope,
            protocol,
            FileTransferConfig(chunkSizeBytes = 2, offerTimeoutMillis = 1_000),
            protocolState = secureProtocolState()
        )
        val bytes = byteArrayOf(1, 2, 3, 4, 5)
        val source = ByteArrayPreparedSource(bytes)
        val transfer = dispatcher.sendPreparedFile(
            "secure.bin",
            "application/octet-stream",
            source
        )
        val offer = protocol.secureOffers.single()
        assertEquals(0, source.openCount, "prepared source must stay closed while only offered")
        dispatcher.onFileAccept(offer.transferId)
        runCurrent()

        assertEquals(1, source.openCount)
        val finish = protocol.fileFinishes.single()
        assertFalse(transfer.state.value.isTerminal(), "sender must wait for durable FILE_COMMIT")
        assertEquals(3, finish.chunkCount)
        dispatcher.onFileCommit(
            SecureFileCommit(
                offer.transferId,
                bytes.size.toLong(),
                finish.contentDigest,
                offer.offerHash
            )
        )
        assertIs<FileTransferState.Completed>(transfer.state.value)
    }

    @Test
    fun rejectedPreparedOfferNeverOpensSource() = runTest {
        val protocol = RecordingFileProtocol()
        val dispatcher = directDispatcher(
            backgroundScope,
            protocol,
            FileTransferConfig(chunkSizeBytes = 2, offerTimeoutMillis = 1_000),
            protocolState = secureProtocolState()
        )
        val source = ByteArrayPreparedSource(byteArrayOf(1, 2, 3))
        val transfer = dispatcher.sendPreparedFile("rejected.bin", null, source)
        dispatcher.onFileReject(protocol.secureOffers.single().transferId, "no storage")

        assertEquals(0, source.openCount)
        assertIs<FileTransferState.Rejected>(transfer.state.value)
    }

    @Test
    fun preparedTransferWithoutNegotiatedFeatureFailsBeforeOpeningOrOffering() = runTest {
        val protocol = RecordingFileProtocol()
        val state = ProtocolSessionState("local", secure = true).also {
            it.completeHello("remote", listOf(ProtocolFeatures.APP_MESSAGE_ENVELOPE_V1))
        }
        val dispatcher = directDispatcher(
            backgroundScope,
            protocol,
            FileTransferConfig(chunkSizeBytes = 2, offerTimeoutMillis = 1_000),
            protocolState = state
        )
        val source = ByteArrayPreparedSource(byteArrayOf(1, 2, 3))

        val error = assertFailsWith<P2pError.FileTransferFailed> {
            dispatcher.sendPreparedFile("unsupported.bin", null, source)
        }

        assertEquals(FileTransferFailureKind.UNSUPPORTED_FEATURE, error.kind)
        assertEquals(FileTransferPhase.OFFER, error.phase)
        assertEquals(0, source.openCount)
        assertTrue(protocol.secureOffers.isEmpty())
    }

    @Test
    fun preparedSnapshotGetterFailureIsTypedBeforeOfferRegistration() = runTest {
        val protocol = RecordingFileProtocol()
        val dispatcher = directDispatcher(
            backgroundScope,
            protocol,
            FileTransferConfig(chunkSizeBytes = 2, offerTimeoutMillis = 1_000),
            protocolState = secureProtocolState()
        )
        val source = object : PreparedFileSource {
            override val sizeBytes: Long = 1
            override val sha256: Sha256Digest get() = throw IOException("snapshot unavailable")
            override fun open(): RawSource = error("must not open")
        }

        val error = assertFailsWith<P2pError.FileTransferFailed> {
            dispatcher.sendPreparedFile("snapshot.bin", null, source)
        }
        assertEquals(FileTransferFailureKind.SOURCE_IO, error.kind)
        assertEquals(FileTransferPhase.SOURCE_READ, error.phase)
        assertTrue(protocol.secureOffers.isEmpty())
    }

    @Test
    fun preparedSourceMutationFailsWithoutFinishOrCommit() = runTest {
        val protocol = RecordingFileProtocol()
        val dispatcher = directDispatcher(
            backgroundScope,
            protocol,
            FileTransferConfig(chunkSizeBytes = 2, offerTimeoutMillis = 1_000),
            protocolState = secureProtocolState()
        )
        val expected = byteArrayOf(1, 2, 3)
        val mutated = byteArrayOf(1, 2, 4)
        val transfer = dispatcher.sendPreparedFile(
            "changed.bin",
            null,
            ByteArrayPreparedSource(mutated, sha256(expected))
        )
        dispatcher.onFileAccept(protocol.secureOffers.single().transferId)
        runCurrent()
        withTimeout(5_000) { while (protocol.fileResults.isEmpty()) yield() }

        val failed = assertIs<FileTransferState.Failed>(transfer.state.value)
        val error = assertIs<P2pError.FileTransferFailed>(failed.error)
        assertEquals(FileTransferFailureKind.SOURCE_CHANGED, error.kind)
        assertEquals(FileTransferPhase.SOURCE_READ, error.phase)
        assertTrue(protocol.fileFinishes.isEmpty())
        assertEquals(FileResultCode.SOURCE_CHANGED, protocol.fileResults.single().code)
    }

    @Test
    fun preparedSourceLengthChangesFailWithoutFinishOrCommit() = runTest {
        val cases = listOf(
            byteArrayOf(1, 2, 3) to byteArrayOf(1, 2, 3, 4),
            byteArrayOf(1, 2, 3) to byteArrayOf(1, 2),
            byteArrayOf() to byteArrayOf(1)
        )

        cases.forEachIndexed { index, (snapshot, openedBytes) ->
            val protocol = RecordingFileProtocol()
            val dispatcher = directDispatcher(
                backgroundScope,
                protocol,
                FileTransferConfig(chunkSizeBytes = 2, offerTimeoutMillis = 1_000),
                protocolState = secureProtocolState()
            )
            val transfer = dispatcher.sendPreparedFile(
                "length-changed-$index.bin",
                null,
                ByteArrayPreparedSource(
                    content = openedBytes,
                    sha256 = sha256(snapshot),
                    sizeBytes = snapshot.size.toLong()
                )
            )

            dispatcher.onFileAccept(protocol.secureOffers.single().transferId)
            runCurrent()
            withTimeout(5_000) { while (protocol.fileResults.isEmpty()) yield() }

            val failed = assertIs<FileTransferState.Failed>(transfer.state.value)
            val error = assertIs<P2pError.FileTransferFailed>(failed.error)
            assertEquals(FileTransferFailureKind.SOURCE_CHANGED, error.kind, "case $index")
            assertEquals(FileTransferPhase.SOURCE_READ, error.phase, "case $index")
            assertTrue(protocol.fileFinishes.isEmpty(), "case $index must not send FILE_FINISH")
            assertTrue(protocol.fileCommits.isEmpty(), "case $index must not send FILE_COMMIT")
            assertTrue(protocol.fileCancels.isEmpty(), "case $index must use authenticated FILE_RESULT")
            assertEquals(FileResultCode.SOURCE_CHANGED, protocol.fileResults.single().code, "case $index")
        }
    }

    @Test
    fun receiverCommitFailureAbortsAndReturnsTypedResultToSender() = runTest {
        val protocol = RecordingFileProtocol()
        val dispatcher = directDispatcher(
            backgroundScope,
            protocol,
            FileTransferConfig(chunkSizeBytes = 4, offerTimeoutMillis = 1_000),
            protocolState = secureProtocolState()
        )
        val bytes = byteArrayOf(9, 8, 7, 6)
        val id = MessageId.random(Random(91))
        val offer = SecureFileOffer.create(id, "durable.bin", bytes.size.toLong(), null, sha256(bytes))
        dispatcher.onFileOffer(id, FileOfferPayload("durable.bin", bytes.size.toLong()), offer)
        val pending = assertIs<IncomingFileSession>(dispatcher.pendingFileOffers.value.single())
        val destination = RecordingDestination(commitFailure = IOException("fsync failed"))
        pending.accept(destination)
        dispatcher.onFileData(fileFrame(id, bytes))
        dispatcher.onFileFinish(
            SecureFileFinish(id, bytes.size.toLong(), 1, sha256(bytes), offer.offerHash)
        )

        val failed = assertIs<FileTransferState.Failed>(pending.state.value)
        val error = assertIs<P2pError.FileTransferFailed>(failed.error)
        assertEquals(FileTransferFailureKind.STORAGE, error.kind)
        assertEquals(FileTransferPhase.DURABLE_COMMIT, error.phase)
        assertEquals(1, destination.flushCount)
        assertEquals(1, destination.abortCount)
        assertEquals(FileResultCode.STORAGE_FAILURE, protocol.fileResults.single().code)
        val senderError = protocol.fileResults.single().toPublicFailure()
        assertEquals(FileTransferFailureKind.STORAGE, senderError.kind)
        assertEquals(FileTransferPhase.DURABLE_COMMIT, senderError.phase)
    }

    @Test
    fun secureFinishWaitsForInFlightAcceptCommit() = runTest {
        val protocol = RecordingFileProtocol().apply { gateAccept = true }
        val dispatcher = directDispatcher(
            backgroundScope,
            protocol,
            FileTransferConfig(chunkSizeBytes = 4, offerTimeoutMillis = 1_000),
            protocolState = secureProtocolState()
        )
        val bytes = ByteArray(0)
        val id = MessageId.random(Random(97))
        val offer = SecureFileOffer.create(id, "empty.bin", 0L, null, sha256(bytes))
        dispatcher.onFileOffer(id, FileOfferPayload("empty.bin", 0L), offer)
        val pending = assertIs<IncomingFileSession>(dispatcher.pendingFileOffers.value.single())
        val destination = RecordingDestination()

        val accepting = async { pending.accept(destination) }
        protocol.acceptStarted.await()
        val finishing = async {
            dispatcher.onFileFinish(SecureFileFinish(id, 0L, 0, sha256(bytes), offer.offerHash))
        }
        runCurrent()
        assertFalse(finishing.isCompleted)
        assertEquals(0, destination.commitCount)

        protocol.acceptReleases.send(Unit)
        accepting.await()
        finishing.await()

        assertEquals(1, destination.commitCount)
        assertIs<FileTransferState.Completed>(pending.state.value)
        assertEquals(id, protocol.fileCommits.single().transferId)
    }

    @Test
    fun destinationOpenCancellationPropagatesAndCleansRetainedOffer() = runTest {
        val protocol = RecordingFileProtocol()
        val dispatcher = directDispatcher(
            backgroundScope,
            protocol,
            FileTransferConfig(chunkSizeBytes = 4, offerTimeoutMillis = 1_000),
            protocolState = secureProtocolState()
        )
        val bytes = byteArrayOf(1)
        val id = MessageId.random(Random(96))
        val secureOffer = SecureFileOffer.create(id, "cancel.bin", 1L, null, sha256(bytes))
        dispatcher.onFileOffer(id, FileOfferPayload("cancel.bin", 1L), secureOffer)
        val pending = assertIs<IncomingFileSession>(dispatcher.pendingFileOffers.value.single())
        val destination = RecordingDestination(openFailure = CancellationException("cancel open"))

        assertFailsWith<CancellationException> { pending.accept(destination) }
        assertEquals(1, destination.abortCount)
        assertTrue(dispatcher.pendingFileOffers.value.isEmpty())
        assertIs<FileTransferState.Cancelled>(pending.state.value)
    }

    @Test
    fun receiverDigestMismatchNeverCommitsAndReportsIntegrityFailure() = runTest {
        val protocol = RecordingFileProtocol()
        val dispatcher = directDispatcher(
            backgroundScope,
            protocol,
            FileTransferConfig(chunkSizeBytes = 3, offerTimeoutMillis = 1_000),
            protocolState = secureProtocolState()
        )
        val expected = byteArrayOf(1, 2, 3)
        val received = byteArrayOf(1, 2, 4)
        val id = MessageId.random(Random(92))
        val offer = SecureFileOffer.create(id, "digest.bin", 3L, null, sha256(expected))
        dispatcher.onFileOffer(id, FileOfferPayload("digest.bin", 3L), offer)
        val pending = assertIs<IncomingFileSession>(dispatcher.pendingFileOffers.value.single())
        val destination = RecordingDestination()
        pending.accept(destination)
        dispatcher.onFileData(fileFrame(id, received))
        dispatcher.onFileFinish(SecureFileFinish(id, 3L, 1, sha256(expected), offer.offerHash))

        val error = assertIs<P2pError.FileTransferFailed>(
            assertIs<FileTransferState.Failed>(pending.state.value).error
        )
        assertEquals(FileTransferFailureKind.INTEGRITY, error.kind)
        assertEquals(FileTransferPhase.VERIFY, error.phase)
        assertEquals(0, destination.flushCount, "digest mismatch must fail before destination flush")
        assertEquals(0, destination.commitCount)
        assertEquals(1, destination.abortCount)
        assertEquals(FileResultCode.DIGEST_MISMATCH, protocol.fileResults.single().code)
    }

    @Test
    fun senderCommitTimeoutIsTypedAndNeverCompletes() = runTest {
        val protocol = RecordingFileProtocol()
        val config = FileTransferConfig(chunkSizeBytes = 2, offerTimeoutMillis = 100)
        val dispatcher = directDispatcher(
            backgroundScope,
            protocol,
            config,
            protocolState = secureProtocolState()
        )
        val transfer = dispatcher.sendPreparedFile(
            "timeout.bin",
            null,
            ByteArrayPreparedSource(byteArrayOf(1, 2, 3))
        )
        dispatcher.onFileAccept(protocol.secureOffers.single().transferId)
        runCurrent()
        assertEquals(1, protocol.fileFinishes.size)
        advanceTimeBy(config.offerTimeoutMillis)
        runCurrent()

        val error = assertIs<P2pError.FileTransferFailed>(
            assertIs<FileTransferState.Failed>(transfer.state.value).error
        )
        assertEquals(FileTransferFailureKind.TIMEOUT, error.kind)
        assertEquals(FileTransferPhase.DURABLE_COMMIT, error.phase)
        assertEquals(Retryability.RETRY_NEW_SESSION, error.retryability)
    }

    @Test
    fun senderRejectsCommitThatDoesNotMatchAuthenticatedOffer() = runTest {
        val protocol = RecordingFileProtocol()
        val dispatcher = directDispatcher(
            backgroundScope,
            protocol,
            FileTransferConfig(chunkSizeBytes = 2, offerTimeoutMillis = 1_000),
            protocolState = secureProtocolState()
        )
        val transfer = dispatcher.sendPreparedFile(
            "mismatch.bin",
            null,
            ByteArrayPreparedSource(byteArrayOf(1, 2, 3))
        )
        val offer = protocol.secureOffers.single()
        dispatcher.onFileAccept(offer.transferId)
        runCurrent()

        dispatcher.onFileCommit(
            SecureFileCommit(
                offer.transferId,
                transfer.sizeBytes,
                sha256(byteArrayOf(9, 9, 9)),
                offer.offerHash
            )
        )

        val error = assertIs<P2pError.FileTransferFailed>(
            assertIs<FileTransferState.Failed>(transfer.state.value).error
        )
        assertEquals(FileTransferFailureKind.INTEGRITY, error.kind)
        assertEquals(FileTransferPhase.DURABLE_COMMIT, error.phase)
    }

    @Test
    fun senderRejectsCommitBeforeFinishAsTransferProtocolFailure() = runTest {
        val protocol = RecordingFileProtocol()
        val dispatcher = directDispatcher(
            backgroundScope,
            protocol,
            FileTransferConfig(chunkSizeBytes = 2, offerTimeoutMillis = 1_000),
            protocolState = secureProtocolState()
        )
        val transfer = dispatcher.sendPreparedFile(
            "early-commit.bin",
            null,
            ByteArrayPreparedSource(byteArrayOf(1, 2, 3))
        )
        val offer = protocol.secureOffers.single()

        dispatcher.onFileCommit(
            SecureFileCommit(
                offer.transferId,
                transfer.sizeBytes,
                offer.contentDigest,
                offer.offerHash
            )
        )

        val error = assertIs<P2pError.FileTransferFailed>(
            assertIs<FileTransferState.Failed>(transfer.state.value).error
        )
        assertEquals(FileTransferFailureKind.TRANSFER_PROTOCOL, error.kind)
        assertEquals(FileTransferPhase.DURABLE_COMMIT, error.phase)
        assertFalse((transfer as OutgoingFileTransferImpl).retainsSource())
    }

    @Test
    fun receiverFlushFailureReturnsExactSenderPhase() = runTest {
        val protocol = RecordingFileProtocol()
        val dispatcher = directDispatcher(
            backgroundScope,
            protocol,
            FileTransferConfig(chunkSizeBytes = 3, offerTimeoutMillis = 1_000),
            protocolState = secureProtocolState()
        )
        val bytes = byteArrayOf(1, 2, 3)
        val id = MessageId.random(Random(93))
        val offer = SecureFileOffer.create(id, "flush.bin", 3L, null, sha256(bytes))
        dispatcher.onFileOffer(id, FileOfferPayload("flush.bin", 3L), offer)
        val pending = assertIs<IncomingFileSession>(dispatcher.pendingFileOffers.value.single())
        val destination = RecordingDestination(flushFailure = IOException("flush failed"))
        pending.accept(destination)
        dispatcher.onFileData(fileFrame(id, bytes))
        dispatcher.onFileFinish(SecureFileFinish(id, 3L, 1, sha256(bytes), offer.offerHash))

        val receiverError = assertIs<P2pError.FileTransferFailed>(
            assertIs<FileTransferState.Failed>(pending.state.value).error
        )
        assertEquals(FileTransferFailureKind.STORAGE, receiverError.kind)
        assertEquals(FileTransferPhase.FLUSH, receiverError.phase)
        val result = protocol.fileResults.single()
        assertEquals(FileTransferPhase.FLUSH, result.phase)
        val senderError = result.toPublicFailure()
        assertEquals(FileTransferFailureKind.STORAGE, senderError.kind)
        assertEquals(FileTransferPhase.FLUSH, senderError.phase)
    }

    private fun directDispatcher(
        scope: CoroutineScope,
        protocol: P2pProtocol,
        config: FileTransferConfig = FileTransferConfig(offerTimeoutMillis = 60_000),
        random: Random = Random(42),
        protocolState: ProtocolSessionState = ProtocolSessionState.legacy(),
        connectionProvider: (() -> RawConnection)? = null,
        sendMutex: Mutex = Mutex()
    ): FileTransferDispatcher {
        val pair = FakeConnectionPair()
        return FileTransferDispatcher(
            sessionId = "direct-test",
            remotePeer = syntheticPeer("peer-id", "Peer"),
            protocol = protocol,
            getConnection = connectionProvider ?: { pair.a },
            getProtocolState = { protocolState },
            sendMutex = sendMutex,
            config = config,
            scope = scope,
            random = random,
            logger = P2pLogger.NoOp
        )
    }

    private fun secureProtocolState(): ProtocolSessionState =
        ProtocolSessionState("local", secure = true).also {
            it.completeHello("remote", ProtocolFeatures.SECURE_V2)
        }

    private fun fileFrame(id: MessageId, bytes: ByteArray): Frame = Frame(
        type = dev.p2pkit.core.protocol.PacketType.FILE_DATA,
        flags = dev.p2pkit.core.protocol.FrameFlags.LAST_CHUNK.toByte(),
        messageId = id,
        chunkIndex = 0,
        totalChunks = 1,
        payload = bytes
    )
}

private class GatedSink : RawSink {
    val entered = CompletableDeferred<Unit>()
    val release = CompletableDeferred<Unit>()

    override fun write(source: Buffer, byteCount: Long) {
        entered.complete(Unit)
        runBlocking { release.await() }
        source.skip(byteCount)
    }

    override fun flush() {}
    override fun close() {}
}

private class ByteArrayPreparedSource(
    private val content: ByteArray,
    override val sha256: Sha256Digest = sha256(content),
    override val sizeBytes: Long = content.size.toLong()
) : PreparedFileSource {
    var openCount: Int = 0
        private set

    override fun open(): RawSource {
        openCount++
        return Buffer().apply { write(content) }
    }
}

private class HookedPreparedSource(
    content: ByteArray,
    private val opened: RawSource,
    private val beforeOpenReturns: () -> Unit
) : PreparedFileSource {
    override val sizeBytes: Long = content.size.toLong()
    override val sha256: Sha256Digest = sha256(content)
    var openCount: Int = 0
        private set

    override fun open(): RawSource {
        openCount++
        beforeOpenReturns()
        return opened
    }
}

private class RecordingDestination(
    private val commitFailure: Throwable? = null,
    private val flushFailure: Throwable? = null,
    private val openFailure: Throwable? = null
) : FileTransferDestination {
    val buffer = Buffer()
    var commitCount = 0
    var abortCount = 0
    var flushCount = 0

    override fun openSink(): RawSink {
        openFailure?.let { throw it }
        return object : RawSink {
        override fun write(source: Buffer, byteCount: Long) {
            buffer.write(source, byteCount)
        }

        override fun flush() {
            flushCount++
            flushFailure?.let { throw it }
        }

        override fun close() {}
        }
    }

    override suspend fun commit() {
        commitCount++
        commitFailure?.let { throw it }
    }

    override suspend fun abort(cause: P2pError.FileTransferFailed?) {
        abortCount++
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
    override val descriptor =
        dev.p2pkit.core.transport.TransportDescriptor.dataOnly(transport.type)
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
    val secureOffers = mutableListOf<SecureFileOffer>()

    /** (transferId, chunkIndex) per FILE_DATA frame, in send order. */
    val fileData = mutableListOf<Pair<MessageId, Int>>()
    val fileDones = mutableListOf<MessageId>()
    val fileFinishes = mutableListOf<SecureFileFinish>()
    val fileCommits = mutableListOf<SecureFileCommit>()
    val fileResults = mutableListOf<SecureFileResult>()
    val fileAcceptConnections = mutableListOf<RawConnection>()

    /** (transferId, reason) per FILE_CANCEL, in send order. */
    val fileCancels = mutableListOf<Pair<MessageId, String?>>()
    val fileRejects = mutableListOf<MessageId>()

    /** When non-null, [sendFileOffer] throws it instead of recording (offer-write-failure injection). */
    var offerFailure: Throwable? = null
    var acceptFailure: Throwable? = null
    var dataFailure: Throwable? = null
    var gateOffer: Boolean = false
    val offerStarted = CompletableDeferred<Unit>()
    val offerRelease = CompletableDeferred<Unit>()
    var gateAccept: Boolean = false
    val acceptStarted = CompletableDeferred<Unit>()
    val acceptReleases = Channel<Unit>(Channel.UNLIMITED)
    var gateReject: Boolean = false
    val rejectStarted = CompletableDeferred<Unit>()
    val rejectRelease = CompletableDeferred<Unit>()
    val rejectExited = CompletableDeferred<Unit>()
    var gateCancel: Boolean = false
    val cancelStarted = CompletableDeferred<Unit>()
    val cancelRelease = CompletableDeferred<Unit>()
    val cancelExited = CompletableDeferred<Unit>()

    /**
     * When true, each [sendFileDataFrame] records its frame and then parks
     * until [dataFrameReleases] provides one permit — a deterministic
     * mid-stream hold for the outgoing streamer.
     */
    var gateDataFrames = false
    val dataFrameReleases = Channel<Unit>(Channel.UNLIMITED)
    val dataFrameExited = CompletableDeferred<Unit>()

    override suspend fun sendMessage(
        connection: RawConnection,
        message: P2pMessage,
        sessionState: ProtocolSessionState
    ) {}
    override suspend fun sendHello(connection: RawConnection, hello: HelloPayload) {}
    override suspend fun sendPing(connection: RawConnection) {}
    override suspend fun sendPong(connection: RawConnection) {}
    override suspend fun sendClose(connection: RawConnection) {}
    override suspend fun sendError(connection: RawConnection, reason: String) {}

    override suspend fun sendFileOffer(connection: RawConnection, transferId: MessageId, offer: FileOfferPayload) {
        offerFailure?.let { throw it }
        if (gateOffer) {
            offerStarted.complete(Unit)
            offerRelease.await()
        }
        fileOffers.add(transferId)
    }

    override suspend fun sendSecureFileOffer(connection: RawConnection, offer: SecureFileOffer) {
        offerFailure?.let { throw it }
        secureOffers += offer
    }

    override suspend fun sendFileAccept(connection: RawConnection, transferId: MessageId) {
        acceptFailure?.let { throw it }
        fileAcceptConnections += connection
        if (gateAccept) {
            acceptStarted.complete(Unit)
            acceptReleases.receive()
        }
    }

    override suspend fun sendSecureFileAccept(connection: RawConnection, transferId: MessageId) {
        sendFileAccept(connection, transferId)
    }

    override suspend fun sendFileReject(connection: RawConnection, transferId: MessageId, reason: String?) {
        fileRejects.add(transferId)
        if (gateReject) {
            rejectStarted.complete(Unit)
            try {
                withContext(NonCancellable) { rejectRelease.await() }
            } finally {
                rejectExited.complete(Unit)
            }
        }
    }

    override suspend fun sendFileDataFrame(connection: RawConnection, frame: Frame) {
        dataFailure?.let { throw it }
        fileData.add(frame.messageId to frame.chunkIndex)
        if (gateDataFrames) {
            try {
                dataFrameReleases.receive()
            } finally {
                dataFrameExited.complete(Unit)
            }
        }
    }

    override suspend fun sendFileDone(connection: RawConnection, transferId: MessageId) {
        fileDones.add(transferId)
    }

    override suspend fun sendFileFinish(connection: RawConnection, finish: SecureFileFinish) {
        fileFinishes += finish
    }

    override suspend fun sendFileCommit(connection: RawConnection, commit: SecureFileCommit) {
        fileCommits += commit
    }

    override suspend fun sendFileResult(connection: RawConnection, result: SecureFileResult) {
        fileResults += result
    }

    override suspend fun sendFileCancel(connection: RawConnection, transferId: MessageId, reason: String?) {
        fileCancels.add(transferId to reason)
        if (gateCancel) {
            cancelStarted.complete(Unit)
            try {
                withContext(NonCancellable) { cancelRelease.await() }
            } finally {
                cancelExited.complete(Unit)
            }
        }
    }

    override fun events(
        connection: RawConnection,
        sessionState: ProtocolSessionState
    ): Flow<ProtocolEvent> = emptyFlow()
}
