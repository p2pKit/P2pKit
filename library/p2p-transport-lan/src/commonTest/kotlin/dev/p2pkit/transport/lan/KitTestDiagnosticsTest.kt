package dev.p2pkit.transport.lan

import dev.p2pkit.core.AppId
import dev.p2pkit.core.NetworkPathStatus
import dev.p2pkit.core.P2pKit
import dev.p2pkit.core.P2pLogger
import dev.p2pkit.core.P2pSession
import dev.p2pkit.core.P2pState
import dev.p2pkit.core.Peer
import dev.p2pkit.core.PeerFingerprint
import dev.p2pkit.core.PeerId
import dev.p2pkit.core.permission.P2pPermissionManager
import dev.p2pkit.core.provisioning.NetworkProvisioningManager
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.cancel
import kotlinx.coroutines.currentCoroutineContext
import kotlinx.coroutines.ensureActive
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.launch
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withTimeout
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertIs
import kotlin.test.assertSame
import kotlin.test.assertTrue

class KitTestDiagnosticsTest {
    @Test
    fun cancelledOwnerStillStopsAllKitsAndChecksFailedConstructionDiagnostics() = runBlocking {
        val cancellation = CancellationException("synthetic owner cancellation")
        val stopFailure = SyntheticStopFailure(Any())
        val constructionFailure = IllegalArgumentException("synthetic constructor failure")
        val events = mutableListOf<String>()
        val settled = CompletableDeferred<Unit>()
        val child = launch {
            val diagnostics = KitTestDiagnostics()
            diagnostics.create { recording ->
                StopOnlyKit {
                    currentCoroutineContext().ensureActive() // Must run under NonCancellable.
                    events += "first stop"
                    recording.warn("late first-kit warning")
                    throw stopFailure
                }
            }
            diagnostics.create { StopOnlyKit { events += "second stop" } }
            assertSame(constructionFailure, assertFailsWith<IllegalArgumentException> {
                diagnostics.create { recording ->
                    recording.error("failed construction error")
                    throw constructionFailure
                }
            })
            currentCoroutineContext().cancel(cancellation)
            diagnostics.finish(cancellation) { events += "restore owned settings" }
            settled.complete(Unit)
        }
        withTimeout(5_000) {
            child.join()
            settled.await()
        }
        assertEquals(listOf("first stop", "second stop", "restore owned settings"), events)
        val failures = cancellation.suppressedExceptions
        assertEquals(3, failures.size)
        assertSame(stopFailure, failures[0])
        assertTrue(assertIs<AssertionError>(failures[1]).message.orEmpty().contains("late first-kit warning"))
        assertTrue(assertIs<AssertionError>(failures[2]).message.orEmpty().contains("failed construction error"))
    }

    @Test
    fun quietBodyCannotPassLateWarningAndRecordingPrecedesACustomDelegate() = runBlocking {
        val diagnostics = KitTestDiagnostics()
        val callbackFailure = IllegalStateException("synthetic callback failure")
        val recording = KitTestDiagnostics.Recording(object : P2pLogger by P2pLogger.NoOp {
            override fun warn(message: String, throwable: Throwable?) { throw callbackFailure }
        })
        var stopped = false
        diagnostics.create(recording) {
            StopOnlyKit {
                stopped = true
                assertSame(callbackFailure, assertFailsWith<IllegalStateException> {
                    recording.warn("late warning retained before delegate")
                })
            }
        }
        val diagnostic = assertFailsWith<AssertionError> { diagnostics.finish() }
        assertTrue(stopped)
        assertTrue(diagnostic.message.orEmpty().contains("late warning retained before delegate"))
        assertEquals(KitTestDiagnostics.Recording.Level.WARN, recording.entries.single().level)
    }

    // Extra instance state prevents coroutine stack recovery from copying this identity-sensitive fixture.
    private class SyntheticStopFailure(val marker: Any) : IllegalStateException("synthetic first stop failure")

    /** Only stop is exercised here; real factory/runtime wiring stays in the migrated integration suites. */
    private class StopOnlyKit(private val onStop: suspend () -> Unit) : P2pKit {
        override val appId = AppId("synthetic.test.diagnostics")
        override val localDeviceName = "Synthetic diagnostic fixture"
        override val localPeerId = PeerId("synthetic-test-logger")
        override val localFingerprint: PeerFingerprint? = null
        override val localPairingQr: String? = null
        override val state = MutableStateFlow<P2pState>(P2pState.Idle)
        override val networkPathStatus = MutableStateFlow<NetworkPathStatus>(NetworkPathStatus.Unknown)
        override val peers = MutableStateFlow<List<Peer>>(emptyList())
        override val sessions = MutableStateFlow<List<P2pSession>>(emptyList())
        override val incomingSessions = MutableSharedFlow<P2pSession>()
        override val permissions: P2pPermissionManager get() = error("not used")
        override val networkProvisioning: NetworkProvisioningManager get() = error("not used")
        override fun parsePeerPairingQr(value: String): PeerFingerprint? = error("not used")
        override suspend fun start(): Unit = error("not used")
        override suspend fun startAdvertising(): Unit = error("not used")
        override suspend fun stopAdvertising(): Unit = error("not used")
        override suspend fun startDiscovery(): Unit = error("not used")
        override suspend fun stopDiscovery(): Unit = error("not used")
        override suspend fun connect(peer: Peer): P2pSession = error("not used")
        override suspend fun connect(peer: Peer, expectedFingerprint: PeerFingerprint): P2pSession = error("not used")
        override fun lastSeen(peerId: PeerId): Long? = error("not used")
        override fun notifyAppBackgrounded(): Unit = error("not used")
        override fun notifyAppForegrounded(): Unit = error("not used")
        override suspend fun stop() = onStop()
    }
}
