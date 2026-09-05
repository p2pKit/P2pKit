package dev.p2pkit.sample.desktop

import dev.p2pkit.core.ConnectionState
import dev.p2pkit.core.P2pMessage
import dev.p2pkit.core.P2pSession
import dev.p2pkit.core.Peer
import dev.p2pkit.core.PeerId
import dev.p2pkit.core.Platform
import dev.p2pkit.core.transfer.P2pFileOffer
import dev.p2pkit.core.transfer.P2pFileTransfer
import dev.p2pkit.sample.diagnostics.SampleConsole
import java.io.ByteArrayOutputStream
import java.io.PrintStream
import java.nio.file.Files
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
import kotlin.test.assertFalse
import kotlin.test.assertIs
import kotlin.test.assertTrue

class ConsolePrivacyTest {
    @Test
    fun realIncomingCollectorPrintsSizeButNotBodyNameOrRawId() = runBlocking {
        val home = Files.createTempDirectory("p2pkit-cli-console-test").toFile()
        val owner = SupervisorJob()
        val scope = CoroutineScope(Dispatchers.Unconfined + owner)
        val previous = System.out
        val output = ByteArrayOutputStream()
        val stream = PrintStream(output, true, "UTF-8")
        try {
            val options = assertIs<CliParseResult.Success>(parseCliOptions(arrayOf("session=synthetic-test"))).options
            CliDiagnostics.configure(options, home)
            System.setOut(stream)
            val session = SyntheticSession()
            wireIncoming(session, scope, java.util.concurrent.ConcurrentHashMap())
            assertEquals(1, session.incoming.subscriptionCount.value)
            val body = "synthetic private text 👋\u001b[31m"
            session.incoming.emit(P2pMessage.Text(body))
            session.incoming.emit(P2pMessage.Binary(body.toByteArray()))
            val log = output.toString("UTF-8")
            assertFalse(log.contains(body))
            assertFalse(log.contains(session.peer.name))
            assertFalse(log.contains(session.peer.id.value))
            val size = body.toByteArray().size
            assertTrue(log.contains("<text ${size}B>"))
            assertTrue(log.contains("<binary ${size}B>"))
            assertTrue(log.contains(SampleConsole.identifier(session.peer.id.value)))
            assertFalse(log.contains('\u001b'))
        } finally {
            owner.cancelAndJoin()
            System.setOut(previous)
            stream.close()
            CliDiagnostics.close()
            home.deleteRecursively()
        }
    }

    @Test
    fun actualSdkDelegateDropsArbitraryUnlabelledTextAndExceptionDetails() {
        val original = System.err
        val output = ByteArrayOutputStream()
        val stream = PrintStream(output, true, "UTF-8")
        try {
            System.setErr(stream)
            val canary = "Synthetic Private Name /private/example.txt 192.0.2.9"
            StdErrLogger.info(canary)
            StdErrLogger.warn(canary, IllegalArgumentException(canary))
            StdErrLogger.error(canary, IllegalStateException(canary, Exception(canary)))
            val log = output.toString("UTF-8")
            assertFalse(log.contains(canary))
            assertTrue(log.contains("IllegalArgumentException"))
            assertTrue(log.contains("IllegalStateException"))
        } finally {
            System.setErr(original)
            stream.close()
        }
    }

    @Test
    fun displayedAliasesRemainUsableAlongsideLegacySelectors() {
        val peer = SyntheticSession().peer
        assertTrue(matches(peer, SampleConsole.identifier(peer.id.value)))
        assertTrue(matches(peer, peer.id.value.take(10)))
        assertTrue(matches(peer, peer.name.lowercase()))
        assertFalse(matches(peer, "not-a-peer"))
    }

    @Test
    fun invalidOptionsDoNotEchoArbitraryArguments() {
        for (args in listOf(arrayOf("unknown=private-value"), arrayOf("a", "b", "private-value"))) {
            assertFalse(assertIs<CliParseResult.Error>(parseCliOptions(args)).message.contains("private-value"))
        }
    }
}

private class SyntheticSession : P2pSession {
    override val id = "synthetic-session"
    override val peer = Peer(PeerId("synthetic-stable-peer-id"), "Synthetic Private Name", Platform.UNKNOWN, emptySet())
    override val state = MutableStateFlow(ConnectionState.Connected)
    override val incoming = MutableSharedFlow<P2pMessage>()
    @Deprecated("Observe pendingFileOffers")
    override val incomingFiles = MutableSharedFlow<P2pFileOffer>()
    override suspend fun send(message: P2pMessage) = Unit
    override suspend fun close() = Unit
    @Deprecated("Legacy only")
    override suspend fun sendFile(
        name: String, sizeBytes: Long, mimeType: String?, source: RawSource
    ): P2pFileTransfer =
        error("not used in logging test")
}
