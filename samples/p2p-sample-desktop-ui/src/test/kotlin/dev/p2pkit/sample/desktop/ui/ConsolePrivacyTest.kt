package dev.p2pkit.sample.desktop.ui

import dev.p2pkit.core.ConnectionState
import dev.p2pkit.core.P2pMessage
import dev.p2pkit.core.P2pSession
import dev.p2pkit.core.Peer
import dev.p2pkit.core.PeerId
import dev.p2pkit.core.Platform
import dev.p2pkit.core.transfer.P2pFileOffer
import dev.p2pkit.core.transfer.P2pFileTransfer
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
import kotlin.test.assertTrue

class ConsolePrivacyTest {
    @Test
    fun actualSessionCollectorsKeepTheBodyInChatButNotInConsole() = runBlocking {
        val home = Files.createTempDirectory("p2pkit-desktop-console-test").toFile()
        val owner = SupervisorJob()
        val scope = CoroutineScope(Dispatchers.Unconfined + owner)
        val state = DesktopP2pState(scope, home)
        val original = System.err
        val output = ByteArrayOutputStream()
        val stream = PrintStream(output, true, "UTF-8")
        try {
            System.setErr(stream)
            val session = SyntheticSession()
            state.reconcileSessions(listOf(session), scope)
            assertEquals(1, session.incoming.subscriptionCount.value)
            val body = "synthetic private text 👋"
            session.incoming.emit(P2pMessage.Text(body))
            session.incoming.emit(P2pMessage.Binary(body.toByteArray()))
            val log = output.toString("UTF-8")
            assertFalse(log.contains(body))
            assertFalse(log.contains(session.peer.name))
            assertFalse(log.contains(session.peer.id.value))
            val size = body.toByteArray().size
            assertTrue(log.contains("<text ${size}B>"))
            assertTrue(log.contains("<binary ${size}B>"))
            assertTrue(state.roomMessages.any { it.body == body && it.senderName == session.peer.name })
        } finally {
            owner.cancelAndJoin()
            state.shutdownIfRunning()
            System.setErr(original)
            stream.close()
            home.deleteRecursively()
        }
    }

    @Test
    fun actualSdkDelegateKeepsBothConsoleAndLogTailFreeOfArbitraryDetails() = runBlocking {
        val home = Files.createTempDirectory("p2pkit-desktop-console-test").toFile()
        val owner = SupervisorJob()
        val state = DesktopP2pState(CoroutineScope(Dispatchers.Unconfined + owner), home)
        val original = System.err
        val output = ByteArrayOutputStream()
        val stream = PrintStream(output, true, "UTF-8")
        try {
            System.setErr(stream)
            val logger = TailLogger(state)
            val canary = "Synthetic Private Name /private/example.txt 192.0.2.9"
            logger.debug(canary)
            logger.info(canary)
            logger.warn(canary, IllegalArgumentException(canary))
            logger.error(canary, IllegalStateException(canary, Exception(canary)))
            assertFalse(output.toString("UTF-8").contains(canary))
            assertFalse(state.logTail.any { it.contains(canary) })
            assertTrue(output.toString("UTF-8").contains("IllegalStateException"))
            assertEquals(4, state.logTail.size)
        } finally {
            owner.cancelAndJoin()
            state.shutdownIfRunning()
            System.setErr(original)
            stream.close()
            home.deleteRecursively()
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
