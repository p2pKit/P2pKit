package dev.p2pkit.core.transfer

import dev.p2pkit.core.ConnectionState
import dev.p2pkit.core.FileTransferFailureKind
import dev.p2pkit.core.FileTransferPhase
import dev.p2pkit.core.KeepAliveConfig
import dev.p2pkit.core.P2pError
import dev.p2pkit.core.P2pLogger
import dev.p2pkit.core.Peer
import dev.p2pkit.core.PeerId
import dev.p2pkit.core.Platform
import dev.p2pkit.core.Retryability
import dev.p2pkit.core.TransportKind
import dev.p2pkit.core.internal.P2pSessionImpl
import dev.p2pkit.core.protocol.DefaultP2pProtocol
import dev.p2pkit.core.protocol.Frame
import dev.p2pkit.core.protocol.FrameCodec
import dev.p2pkit.core.protocol.PacketType
import dev.p2pkit.core.protocol.ProtocolConstants
import dev.p2pkit.core.protocol.ProtocolEvent
import dev.p2pkit.core.protocol.ProtocolFeatures
import dev.p2pkit.core.protocol.ProtocolSessionState
import dev.p2pkit.core.testfixtures.FakeConnectionPair
import dev.p2pkit.core.transport.RawConnection
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.CoroutineStart
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.NonCancellable
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancelAndJoin
import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.launch
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withContext
import kotlinx.coroutines.withTimeout
import java.io.File
import java.io.FileInputStream
import java.nio.file.Files
import java.nio.file.StandardCopyOption
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicInteger
import kotlin.test.Test
import kotlin.test.assertContentEquals
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertIs
import kotlin.test.assertTrue

/**
 * Actual JVM sendFile(File), v2 framing, session and durable-destination integration.
 * Sessions begin after authenticated HELLO: these tests do not exercise Noise or LAN discovery.
 */
class VerifiedJvmFileTransferTest {
    @Test
    fun sameSizePathReplacementSendsNoSubstitutedData() = runBlocking {
        withFileSessions {
            assertRejectedBeforeData { file ->
                val substitute = File(directory, "replacement.bin").also { it.writeBytes(changedPayload) }
                Files.move(substitute.toPath(), file.toPath(), StandardCopyOption.REPLACE_EXISTING)
            }
        }
    }

    @Test
    fun sameSizeInPlaceEditSendsNoSubstitutedData() = runBlocking {
        withFileSessions { assertRejectedBeforeData { it.writeBytes(changedPayload) } }
    }

    @Test
    fun appendedAndTruncatedSourcesFailBeforeData() = runBlocking {
        withFileSessions {
            assertRejectedBeforeData { it.appendBytes(byteArrayOf(99)) }
            assertRejectedBeforeData { it.writeBytes(originalPayload.copyOf(originalPayload.size - 1)) }
        }
    }

    @Test
    fun symlinkSubstitutionSendsNoTargetData() = runBlocking {
        withFileSessions {
            assertRejectedBeforeData { file ->
                val substitute = File(directory, "symlink-target.bin").also { it.writeBytes(changedPayload) }
                Files.delete(file.toPath())
                // A real symlink, not a path-stat mock. Creating it is required, never silently skipped.
                try {
                    Files.createSymbolicLink(file.toPath(), substitute.toPath())
                } catch (cause: Exception) {
                    throw AssertionError(
                        "This regression requires a real symbolic link in java.io.tmpdir. " +
                            "Use a symlink-capable filesystem (e.g. NTFS on Windows). Windows/JDK 17 " +
                            "also requires a test-process token with SeCreateSymbolicLinkPrivilege; " +
                            "Developer Mode alone is insufficient. See docs/testing/local.md.",
                        cause
                    )
                }
            }
        }
    }

    @Test
    fun unchangedAndEmptyFilesStillFinishAndDurablyCommit() = runBlocking {
        withFileSessions {
            for (payload in listOf(originalPayload, byteArrayOf())) {
                val file = File(directory, "source.bin").also { it.writeBytes(payload) }
                val outgoing = sender.sendFile(file)
                val offer = awaitOffer(outgoing)
                val target = File(directory, "received-${outgoing.id}.bin")
                val destination = ObservedDestination(durableFileDestination(target))
                val incoming = offer.accept(destination)

                assertIs<FileTransferState.Completed>(awaitTerminal(outgoing))
                assertIs<FileTransferState.Completed>(awaitTerminal(incoming))
                assertContentEquals(payload, target.readBytes())
                assertEquals(payload.size.toLong(), outgoing.bytesTransferred.value)
                assertEquals(1, destination.commits.get())
                assertEquals(payload.size.toLong(), dataBytes(outgoing))
                assertEquals(1, senderFrames(outgoing).count { it.type == PacketType.FILE_FINISH })
                assertEquals(1, receiverFrames(incoming).count { it.type == PacketType.FILE_COMMIT })
                assertFalse(directory.listFiles().orEmpty().any { it.extension == "part" })
            }
        }
    }

    @Test
    fun rejectAndCancelDoNotReopenPendingFile() = runBlocking {
        withFileSessions {
            for (reject in listOf(true, false)) {
                val file = File(directory, "source.bin").also { it.writeBytes(originalPayload) }
                val outgoing = sender.sendFile(file)
                val offer = awaitOffer(outgoing)
                Files.delete(file.toPath())
                if (reject) {
                    offer.reject("declined")
                    assertIs<FileTransferState.Rejected>(awaitTerminal(outgoing))
                } else {
                    outgoing.cancel("cancelled before acceptance")
                    assertIs<FileTransferState.Cancelled>(awaitTerminal(outgoing))
                    withTimeout(5_000) { receiver.pendingFileOffers.first { it.none { it.id == offer.id } } }
                }
                assertEquals(0L, dataBytes(outgoing))
                assertFalse(senderFrames(outgoing).any { it.type == PacketType.FILE_FINISH })
                assertEquals(ConnectionState.Connected, sender.state.value)
            }
        }
    }

    @Test
    fun cancellationDuringPreflightClosesLateSourceWithoutSendingIt() = runBlocking {
        withFileSessions {
            val file = File(directory, "source.bin").also { it.writeBytes(originalPayload) }
            val entered = CompletableDeferred<Unit>()
            val closed = CompletableDeferred<Unit>()
            val release = CountDownLatch(1)
            val opens = AtomicInteger()
            val prepared = prepareJvmFileSource(file) {
                if (opens.incrementAndGet() == 1) file.inputStream()
                else object : FileInputStream(file) {
                    override fun read(bytes: ByteArray, offset: Int, length: Int): Int {
                        entered.complete(Unit)
                        check(release.await(5, TimeUnit.SECONDS)) { "test did not release the preflight read" }
                        return super.read(bytes, offset, length)
                    }

                    override fun close() {
                        super.close()
                        closed.complete(Unit)
                    }
                }
            }
            try {
                val outgoing = sender.sendFile(name = file.name, mimeType = null, source = prepared)
                val destination = ObservedDestination(durableFileDestination(File(directory, "received.bin")))
                val incoming = awaitOffer(outgoing).accept(destination)
                withTimeout(5_000) { entered.await() }

                outgoing.cancel("cancel preflight")
                assertIs<FileTransferState.Cancelled>(awaitTerminal(outgoing))
                assertIs<FileTransferState.Cancelled>(awaitTerminal(incoming))
                release.countDown()
                withTimeout(5_000) { closed.await(); destination.aborted.await() }

                assertEquals(2, opens.get())
                assertEquals(0L, dataBytes(outgoing))
                assertFalse(senderFrames(outgoing).any { it.type == PacketType.FILE_FINISH })
                assertEquals(0, destination.commits.get())
            } finally {
                release.countDown()
                if (entered.isCompleted) withTimeout(5_000) { closed.await() }
            }
        }
    }
}

private suspend fun withFileSessions(block: suspend FileSessions.() -> Unit) {
    val directory = Files.createTempDirectory("p2pkit-verified-transfer-").toFile()
    val parent = SupervisorJob()
    val scope = CoroutineScope(parent + Dispatchers.Default)
    val pair = FakeConnectionPair()
    val protocol = DefaultP2pProtocol(clock = System::currentTimeMillis, version = ProtocolConstants.SECURE_VERSION)

    fun session(local: String, remote: String, connection: RawConnection): P2pSessionImpl {
        val state = ProtocolSessionState(local, secure = true).also {
            it.completeHello(remote, ProtocolFeatures.SECURE_V2)
        }
        val events = Channel<ProtocolEvent>(16)
        val reader = scope.launch(start = CoroutineStart.UNDISPATCHED) {
            try {
                protocol.events(connection, state).collect { events.send(it) }
            } finally {
                events.close()
            }
        }
        return P2pSessionImpl(
            id = local,
            peer = Peer(PeerId(remote), remote, Platform.JVM_DESKTOP, setOf(TransportKind.LAN)),
            initialConnection = connection,
            initialEvents = events,
            initialReaderJob = reader,
            initialProtocolState = state,
            protocol = protocol,
            parentScope = scope,
            keepAlive = KeepAliveConfig(60_000, 120_000),
            clock = System::currentTimeMillis,
            logger = P2pLogger.NoOp
        ).also { it.start(); it.markRegistrationCommitted() }
    }

    val sender = session("sender", "receiver", pair.a)
    val receiver = session("receiver", "sender", pair.b)
    try {
        FileSessions(directory, sender, receiver, pair).block()
    } finally {
        withContext(NonCancellable) {
            try {
                withTimeout(5_000) { sender.close(); receiver.close() }
            } finally {
                withTimeout(5_000) { parent.cancelAndJoin() }
                assertTrue(directory.deleteRecursively(), "synthetic transfer directory must be removed")
            }
        }
    }
}

private class FileSessions(
    val directory: File,
    val sender: P2pSessionImpl,
    val receiver: P2pSessionImpl,
    private val pair: FakeConnectionPair
) {
    val originalPayload = ByteArray(1024 * 1024) { (it * 31).toByte() }
    val changedPayload = ByteArray(originalPayload.size) { (it * 31 + 1).toByte() }

    suspend fun awaitOffer(outgoing: P2pFileTransfer): P2pFileOffer = withTimeout(5_000) {
        receiver.pendingFileOffers.first { offers -> offers.any { it.id == outgoing.id } }
            .single { it.id == outgoing.id }
    }

    suspend fun awaitTerminal(transfer: P2pFileTransfer): FileTransferState = withTimeout(5_000) {
        transfer.state.first { it.isTerminal() }
    }

    fun senderFrames(transfer: P2pFileTransfer): List<Frame> = frames(pair.a.writtenChunks, transfer)

    fun receiverFrames(transfer: P2pFileTransfer): List<Frame> = frames(pair.b.writtenChunks, transfer)

    fun dataBytes(transfer: P2pFileTransfer): Long = senderFrames(transfer)
        .filter { it.type == PacketType.FILE_DATA }.sumOf { it.payload.size.toLong() }

    private fun frames(chunks: List<ByteArray>, transfer: P2pFileTransfer): List<Frame> = chunks.map {
        FrameCodec.decode(it, ProtocolConstants.SECURE_VERSION)
    }.filter { it.messageId.toString() == transfer.id }

    suspend fun assertRejectedBeforeData(substitute: (File) -> Unit) {
        val file = File(directory, "source.bin").also { it.writeBytes(originalPayload) }
        val outgoing = sender.sendFile(file)
        val offer = awaitOffer(outgoing)
        assertEquals(originalPayload.size.toLong(), offer.sizeBytes)
        substitute(file) // The prepared descriptor is closed; the peer has not accepted yet.
        val target = File(directory, "received-${outgoing.id}.bin")
        val destination = ObservedDestination(durableFileDestination(target))
        val incoming = offer.accept(destination)

        for (transfer in listOf(outgoing, incoming)) {
            val terminal = assertIs<FileTransferState.Failed>(awaitTerminal(transfer))
            val error = assertIs<P2pError.FileTransferFailed>(terminal.error)
            assertEquals(FileTransferFailureKind.SOURCE_CHANGED, error.kind)
            assertEquals(FileTransferPhase.SOURCE_READ, error.phase)
            // Only the sender can fix and reprepare its source; retain the existing
            // conservative remote FILE_RESULT classification at the receiver.
            assertEquals(
                if (transfer === outgoing) Retryability.RETRY_AFTER_USER_ACTION else Retryability.NOT_RETRYABLE,
                error.retryability
            )
            assertEquals(transfer.id, error.transferId)
        }
        withTimeout(5_000) { destination.aborted.await() }
        assertEquals(0L, dataBytes(outgoing), "no substituted FILE_DATA payload may reach the transport")
        assertEquals(0L, outgoing.bytesTransferred.value)
        assertEquals(0L, incoming.bytesTransferred.value)
        assertFalse(senderFrames(outgoing).any { it.type == PacketType.FILE_FINISH })
        assertFalse(receiverFrames(incoming).any { it.type == PacketType.FILE_COMMIT })
        assertEquals(0, destination.commits.get())
        assertFalse(target.exists())
        assertFalse(directory.listFiles().orEmpty().any { it.extension == "part" })
        assertEquals(ConnectionState.Connected, sender.state.value)
        assertEquals(ConnectionState.Connected, receiver.state.value)
    }
}

private class ObservedDestination(private val delegate: FileTransferDestination) : FileTransferDestination by delegate {
    val commits = AtomicInteger()
    val aborted = CompletableDeferred<Unit>()

    override suspend fun commit() {
        commits.incrementAndGet()
        delegate.commit()
    }

    override suspend fun abort(cause: P2pError.FileTransferFailed?) {
        delegate.abort(cause)
        aborted.complete(Unit)
    }
}
