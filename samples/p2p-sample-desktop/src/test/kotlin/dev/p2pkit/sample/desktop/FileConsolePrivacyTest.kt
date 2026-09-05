package dev.p2pkit.sample.desktop

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
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancelAndJoin
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.runBlocking
import kotlinx.io.RawSource
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertFalse
import kotlin.test.assertIs
import kotlin.test.assertTrue

class FileConsolePrivacyTest {
    @Test
    fun healthySourceStillReachesSessionSend() = runBlocking {
        withFileConsole { home, scope, _ ->
            val selected = File(home, PRIVATE_FILE).apply { writeText("published fixture") }
            val session = FileTestSession()
            sendSelectedFile(session, selected, scope)
            assertEquals(1, session.sendCalls)
            assertTrue(CliDiagnostics.recorder.snapshot().any {
                it.eventName == DiagnosticEventNames.FILE_SENDER_HASH
            })
        }
    }

    @Test
    fun healthyReceiverRereadStillRecordsTheDigest() = runBlocking {
        withFileConsole { home, _, output ->
            val selected = File(home, PRIVATE_FILE).apply { writeText("published fixture") }
            reportCommittedFile(FileTestTransfer(), "synthetic-session", selected)
            assertTrue(CliDiagnostics.recorder.snapshot().any {
                it.eventName == DiagnosticEventNames.FILE_RECEIVER_HASH
            })
            assertTrue(output.toString("UTF-8").contains("durable sha256=${testFileSha256(selected)}"))
            assertFalse(output.toString("UTF-8").contains(PRIVATE_FILE))
        }
    }

    @Test
    fun sourceRemovedAfterSelectionDoesNotSendOrExposeItsPath() = runBlocking {
        withFileConsole { home, scope, output ->
            val selected = File(home, PRIVATE_FILE).apply { writeText("fixture") }
            assertTrue(selected.isFile && selected.canRead())
            assertTrue(selected.delete()) // deterministic post-precheck race
            val session = FileTestSession()
            sendSelectedFile(session, selected, scope)
            assertEquals(0, session.sendCalls)
            val log = output.toString("UTF-8")
            assertTrue(log.contains("preparation failed: FileNotFoundException"))
            assertFalse(log.contains(PRIVATE_FILE))
            assertFalse(log.contains(home.path))
        }
    }

    @Test
    fun optionalReceiverRereadFailureKeepsCommittedOutcomeAndPublishedBytes() = runBlocking {
        withFileConsole { home, _, output ->
            val selected = File(home, PRIVATE_FILE).apply { writeText("published fixture") }
            val moved = File(home, "moved-by-operator.txt")
            assertTrue(selected.renameTo(moved))
            val transfer = FileTestTransfer()
            reportCommittedFile(transfer, "synthetic-session", selected)
            assertEquals(FileTransferState.Completed, transfer.state.value)
            assertEquals(0, transfer.cancelCalls)
            assertEquals("published fixture", moved.readText())
            assertFalse(selected.exists())
            val log = output.toString("UTF-8")
            assertTrue(log.contains("committed; diagnostic hash unavailable: FileNotFoundException"))
            assertFalse(log.contains(PRIVATE_FILE))
            assertFalse(log.contains(home.path))
            val events = CliDiagnostics.recorder.snapshot()
            val committed = events.single { it.eventName == DiagnosticEventNames.TRANSFER_DURABLE_COMMITTED }
            assertEquals("Completed", committed.currentState)
            assertEquals(DiagnosticOutcome.SUCCESS, committed.outcome)
            assertFalse(events.any { it.eventName == DiagnosticEventNames.FILE_RECEIVER_HASH })
        }
    }

    @Test
    fun sourceCancellationPropagatesWithoutSendingOrLoggingFailure() = runBlocking {
        withFileConsole { home, scope, output ->
            val selected = object : File(home, PRIVATE_FILE) {
                override fun getPath(): String = throw CancellationException("synthetic cancelled read")
            }
            val session = FileTestSession()
            assertFailsWith<CancellationException> { sendSelectedFile(session, selected, scope) }
            assertEquals(0, session.sendCalls)
            assertEquals("", output.toString("UTF-8"))
        }
    }
}

private const val PRIVATE_FILE = "synthetic-private-document.txt"

private suspend fun withFileConsole(block: suspend (File, CoroutineScope, ByteArrayOutputStream) -> Unit) {
    val home = Files.createTempDirectory("p2pkit-cli-file-console").toFile()
    val owner = SupervisorJob()
    val scope = CoroutineScope(Dispatchers.Unconfined + owner)
    val previousOut = System.out
    val previousErr = System.err
    val output = ByteArrayOutputStream()
    val stream = PrintStream(output, true, "UTF-8")
    try {
        val options = assertIs<CliParseResult.Success>(parseCliOptions(emptyArray())).options
        CliDiagnostics.configure(options, home)
        System.setOut(stream)
        System.setErr(stream)
        block(home, scope, output)
    } finally {
        owner.cancelAndJoin()
        System.setOut(previousOut)
        System.setErr(previousErr)
        stream.close()
        CliDiagnostics.close()
        check(home.deleteRecursively())
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
