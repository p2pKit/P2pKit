package dev.p2pkit.sample.desktop.ui

import dev.p2pkit.core.ConnectionState
import dev.p2pkit.core.P2pMessage
import dev.p2pkit.core.P2pSession
import dev.p2pkit.core.Peer
import dev.p2pkit.core.PeerId
import dev.p2pkit.core.Platform
import dev.p2pkit.core.transfer.FileTransferState
import dev.p2pkit.core.transfer.P2pFileOffer
import dev.p2pkit.core.transfer.P2pFileTransfer
import dev.p2pkit.core.transfer.PreparedFileSource
import dev.p2pkit.sample.diagnostics.DiagnosticEventNames
import dev.p2pkit.sample.diagnostics.DiagnosticOutcome
import java.io.ByteArrayOutputStream
import java.io.File
import java.io.PrintStream
import java.nio.file.Files
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CoroutineExceptionHandler
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancelAndJoin
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withTimeout
import kotlinx.io.RawSource
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertFalse
import kotlin.test.assertNull
import kotlin.test.assertTrue

class FileConsolePrivacyTest {
    @Test
    fun healthySourceStillReachesSessionSendAndCreatesItsUiRow() = runBlocking {
        withFileConsole { fixture ->
            val selected = File(fixture.home, PRIVATE_FILE).apply { writeText("published fixture") }
            val session = FileTestSession()
            fixture.state.sendSelectedFile(session, selected, fixture.scope)
            assertEquals(1, session.sendCalls)
            assertEquals(PRIVATE_FILE, fixture.state.fileTransfers.single().name)
            assertTrue(fixture.state.diagnostics.recorder.snapshot().any {
                it.eventName == DiagnosticEventNames.FILE_SENDER_HASH
            })
        }
    }

    @Test
    fun healthyReceiverRereadStillPopulatesTheUiDigest() = runBlocking {
        withFileConsole { fixture ->
            val selected = File(fixture.home, PRIVATE_FILE).apply { writeText("published fixture") }
            val transfer = FileTestTransfer()
            val watcher = fixture.state.registerIncomingTransfer(
                transfer, "synthetic-session", transfer.peer.name, selected.path, fixture.scope
            )
            withTimeout(5_000) { watcher.join() }
            assertTrue(fixture.unhandled.isEmpty())
            assertEquals(testFileSha256(selected), fixture.state.fileTransfers.single().sha256)
            assertTrue(fixture.state.diagnostics.recorder.snapshot().any {
                it.eventName == DiagnosticEventNames.FILE_RECEIVER_HASH
            })
        }
    }

    @Test
    fun removedSourceKeepsDetailsInUiButDoesNotSendOrLogThem() = runBlocking {
        withFileConsole { fixture ->
            val selected = File(fixture.home, PRIVATE_FILE).apply { writeText("fixture") }
            assertTrue(selected.isFile && selected.canRead())
            assertTrue(selected.delete()) // deterministic file-picker/preparation race
            val session = FileTestSession()
            fixture.state.sendSelectedFile(session, selected, fixture.scope)
            assertEquals(0, session.sendCalls)
            val log = fixture.output.toString("UTF-8")
            assertTrue(log.contains("preparation failed: FileNotFoundException"))
            assertFalse(log.contains(PRIVATE_FILE))
            assertFalse(log.contains(fixture.home.path))
            assertTrue(fixture.state.roomMessages.any { PRIVATE_FILE in it.body && "failed" in it.body })
        }
    }

    @Test
    fun receiverRereadFailureKeepsCompletedRowAndPublishedBytesWithoutUncaughtReporting() = runBlocking {
        withFileConsole { fixture ->
            val selected = File(fixture.home, PRIVATE_FILE).apply { writeText("published fixture") }
            val moved = File(fixture.home, "moved-by-operator.txt")
            assertTrue(selected.renameTo(moved))
            val transfer = FileTestTransfer()
            val backgroundCollectors = fixture.owner.children.toSet()
            val watcher = fixture.state.registerIncomingTransfer(
                transfer, "synthetic-session", transfer.peer.name, selected.path, fixture.scope
            )
            withTimeout(5_000) { watcher.join() }
            assertTrue(fixture.unhandled.isEmpty(), "ordinary file failure escaped its sample handler")
            assertEquals(FileTransferState.Completed, transfer.state.value)
            assertEquals(0, transfer.cancelCalls)
            assertEquals("published fixture", moved.readText())
            assertFalse(selected.exists())
            val row = fixture.state.fileTransfers.single()
            assertEquals(FileTransferState.Completed, row.state)
            assertNull(row.sha256)
            assertEquals(transfer.sizeBytes, row.bytesTransferred)
            val log = fixture.output.toString("UTF-8")
            assertTrue(log.contains("committed file hash unavailable: FileNotFoundException"))
            assertFalse(log.contains(PRIVATE_FILE))
            assertFalse(log.contains(fixture.home.path))
            assertTrue(fixture.state.roomMessages.any { "diagnostic hash unavailable" in it.body })
            val events = fixture.state.diagnostics.recorder.snapshot()
            val committed = events.single { it.eventName == DiagnosticEventNames.TRANSFER_DURABLE_COMMITTED }
            assertEquals("Completed", committed.currentState)
            assertEquals(DiagnosticOutcome.SUCCESS, committed.outcome)
            assertFalse(events.any { it.eventName == DiagnosticEventNames.FILE_RECEIVER_HASH })
            assertTrue(events.any {
                it.eventName == DiagnosticEventNames.TEMP_FILE_CLEANED && it.currentState == "promoted"
            })
            assertEquals(backgroundCollectors, fixture.owner.children.toSet(), "transfer collectors must be released")
        }
    }

    @Test
    fun sourceCancellationIsNotReportedAsAnOrdinaryFileFailure() = runBlocking {
        withFileConsole { fixture ->
            val selected = object : File(fixture.home, PRIVATE_FILE) {
                override fun getPath(): String = throw CancellationException("synthetic cancelled read")
            }
            val session = FileTestSession()
            assertFailsWith<CancellationException> {
                fixture.state.sendSelectedFile(session, selected, fixture.scope)
            }
            assertEquals(0, session.sendCalls)
            assertEquals("", fixture.output.toString("UTF-8"))
            assertTrue(fixture.state.roomMessages.isEmpty())
        }
    }
}

private const val PRIVATE_FILE = "synthetic-private-document.txt"

private class FileConsoleFixture {
    val home = Files.createTempDirectory("p2pkit-desktop-file-console").toFile()
    val owner = SupervisorJob()
    val unhandled = mutableListOf<Throwable>()
    val scope = CoroutineScope(
        Dispatchers.Unconfined + owner + CoroutineExceptionHandler { _, failure -> unhandled += failure }
    )
    val state = DesktopP2pState(scope, home)
    val output = ByteArrayOutputStream()
}

private suspend fun withFileConsole(block: suspend (FileConsoleFixture) -> Unit) {
    val fixture = FileConsoleFixture()
    val previous = System.err
    val stream = PrintStream(fixture.output, true, "UTF-8")
    try {
        System.setErr(stream)
        block(fixture)
    } finally {
        fixture.owner.cancelAndJoin()
        fixture.state.shutdownIfRunning()
        System.setErr(previous)
        stream.close()
        check(fixture.home.deleteRecursively())
    }
}

private val fileTestPeer = Peer(PeerId("synthetic-file-peer"), "Synthetic Private Peer", Platform.UNKNOWN, emptySet())

private class FileTestTransfer : P2pFileTransfer {
    override val id = "synthetic-transfer"
    override val peer = fileTestPeer
    override val name = PRIVATE_FILE
    override val sizeBytes = 17L
    override val mimeType: String? = null
    override val state = MutableStateFlow<FileTransferState>(FileTransferState.Completed)
    override val bytesTransferred = MutableStateFlow(sizeBytes)
    var cancelCalls = 0
    override suspend fun cancel(reason: String?) { cancelCalls++ }
}

private class FileTestSession : P2pSession {
    override val id = "synthetic-session"
    override val peer = fileTestPeer
    override val state = MutableStateFlow(ConnectionState.Connected)
    override val incoming = MutableSharedFlow<P2pMessage>()
    @Deprecated("Observe pendingFileOffers")
    override val incomingFiles = MutableSharedFlow<P2pFileOffer>()
    var sendCalls = 0
    override suspend fun send(message: P2pMessage) = Unit
    override suspend fun close() = Unit
    override suspend fun sendFile(name: String, mimeType: String?, source: PreparedFileSource): P2pFileTransfer {
        sendCalls++
        return FileTestTransfer()
    }
    @Deprecated("Legacy only")
    override suspend fun sendFile(
        name: String, sizeBytes: Long, mimeType: String?, source: RawSource
    ): P2pFileTransfer {
        // File extensions deliberately use this overload for third-party session doubles.
        sendCalls++
        source.close()
        return FileTestTransfer()
    }
}
