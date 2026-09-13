package dev.p2pkit.sample.android

import dev.p2pkit.core.ConnectionState
import dev.p2pkit.core.P2pMessage
import dev.p2pkit.core.P2pSession
import dev.p2pkit.core.Peer
import dev.p2pkit.core.PeerId
import dev.p2pkit.core.Platform
import dev.p2pkit.core.TransportKind
import dev.p2pkit.core.transfer.P2pFileOffer
import dev.p2pkit.core.transfer.P2pFileTransfer
import dev.p2pkit.sample.diagnostics.DiagnosticEventNames
import java.util.zip.ZipFile
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertNotNull
import kotlin.test.assertTrue
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.test.runCurrent
import kotlinx.coroutines.test.runTest
import kotlinx.io.RawSource
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

/** Real ViewModel collector/export with inert session state; not a handshake or device test. */
@OptIn(ExperimentalCoroutinesApi::class)
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [35], manifest = Config.NONE)
class SecureConnectionDiagnosticTest {
    @Test
    fun connectedReconnectAndDiagnosticSnapshotCannotInventOrCarryOptionalFeatures() = runTest {
        withSampleViewModel {
            vm.start()
            runCurrent()
            val session = DiagnosticSession()
            room.sessions.value = listOf(session)
            runCurrent()
            fun assertProfiles(expected: Int) {
                val events = vm.diagnosticEvents()
                val profiles = events.filter { it.eventName == DiagnosticEventNames.PROTOCOL_NEGOTIATED }
                assertEquals(expected, profiles.size)
                assertEquals(expected, events.count { it.eventName == DiagnosticEventNames.CONNECTION_AUTHENTICATED })
                profiles.forEach {
                    assertEquals("secure-v2", it.currentState)
                    assertNotNull(it.connectionId)
                    assertTrue(it.details.isEmpty())
                }
            }
            assertProfiles(1)
            session.state.value = ConnectionState.Reconnecting
            runCurrent()
            assertProfiles(1)
            session.state.value = ConnectionState.Connected
            runCurrent()
            assertProfiles(2)

            vm.beginDiagnosticSession("profile-snapshot")
            runCurrent()
            assertProfiles(2) // A diagnostic snapshot is not another handshake.
            assertTrue(vm.diagnosticEvents().any { it.details["sessionSnapshot"] == "true" })
            session.state.value = ConnectionState.Reconnecting
            runCurrent()
            session.state.value = ConnectionState.Connected
            runCurrent()
            assertProfiles(3)
            val archive = assertNotNull(vm.exportDiagnosticEvidence())
            ZipFile(archive).use { zip ->
                val jsonl = zip.getInputStream(zip.getEntry("events.jsonl")).bufferedReader().use { it.readText() }
                assertTrue(jsonl.contains(DiagnosticEventNames.PROTOCOL_NEGOTIATED))
                assertFalse(jsonl.contains("file-commit-sha256-v1"))
            }
            room.sessions.value = emptyList()
            runCurrent()
            assertEquals(0, session.state.subscriptionCount.value)
            assertEquals(0, session.incoming.subscriptionCount.value)
        }
    }

    @Suppress("OVERRIDE_DEPRECATION")
    private class DiagnosticSession : P2pSession {
        override val id = "synthetic-session"
        override val peer = Peer(PeerId("synthetic-peer"), "test", Platform.UNKNOWN, setOf(TransportKind.LAN))
        override val state = MutableStateFlow<ConnectionState>(ConnectionState.Connected)
        override val incoming = MutableSharedFlow<P2pMessage>()
        override val incomingFiles = MutableSharedFlow<P2pFileOffer>()
        override suspend fun send(message: P2pMessage): Unit = error("No protocol operation in this fixture")
        override suspend fun sendFile(
            name: String,
            sizeBytes: Long,
            mimeType: String?,
            source: RawSource
        ): P2pFileTransfer = error("No file operation in this fixture")
        override suspend fun close() { state.value = ConnectionState.Closed }
    }
}
