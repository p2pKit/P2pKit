package dev.p2pkit.sample.android

import dev.p2pkit.core.ExperimentalP2pApi
import dev.p2pkit.core.NetworkProvisioningError
import dev.p2pkit.core.Peer
import dev.p2pkit.core.PeerFingerprint
import dev.p2pkit.core.provisioning.JoinNetworkResult
import dev.p2pkit.core.provisioning.LocalNetworkConfig
import dev.p2pkit.core.provisioning.LocalNetworkResult
import dev.p2pkit.core.provisioning.ManualConnectionInfo
import dev.p2pkit.core.provisioning.NetworkProvisioningEvent
import dev.p2pkit.core.provisioning.NetworkProvisioningManager
import dev.p2pkit.core.provisioning.NetworkProvisioningState
import dev.p2pkit.core.provisioning.NetworkState
import dev.p2pkit.core.provisioning.WifiCredentials
import dev.p2pkit.core.provisioning.WifiPassword
import dev.p2pkit.core.provisioning.WifiSecurityType
import kotlin.coroutines.CoroutineContext
import kotlin.test.Test
import kotlin.test.assertFalse
import kotlin.test.assertIs
import kotlin.test.assertTrue
import kotlinx.coroutines.CoroutineDispatcher
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Job
import kotlinx.coroutines.channels.BufferOverflow
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.MutableStateFlow

/** Tests the production consumer with real flows and an explicitly drained main-thread scheduler. */
class ProvisioningUiStateTest {
    @Test
    fun systemHotspotStopReplacesSuccessWithItsTypedFailure() = withHarness { h ->
        assertTrue(h.ui.startHotspot())
        h.drain()
        assertIs<LocalNetworkResult.Started>(h.ui.hotspotResult.value)

        h.manager.stopFromSystem()
        h.drain()

        val failure = assertIs<LocalNetworkResult.Failed>(h.ui.hotspotResult.value)
        assertIs<NetworkProvisioningError.HotspotStopped>(failure.error)
        assertFalse(h.ui.busy.value)
    }

    @Test
    fun systemJoinReleaseReplacesSuccessWithItsTypedFailure() = withHarness { h ->
        assertTrue(h.ui.joinHotspot(credentials))
        h.drain()
        assertIs<JoinNetworkResult.Joined>(h.ui.joinResult.value)

        h.manager.releaseFromSystem()
        h.drain()

        val failure = assertIs<JoinNetworkResult.Failed>(h.ui.joinResult.value)
        assertIs<NetworkProvisioningError.JoinFailed>(failure.error)
        assertFalse(h.ui.busy.value)
    }

    private fun withHarness(block: (Harness) -> Unit) {
        val harness = Harness()
        try {
            block(harness)
        } finally {
            harness.ui.detach()
            harness.job.cancel()
            harness.drain()
            assertTrue(harness.job.isCompleted, "test must not retain presentation coroutines")
        }
    }

    private class Harness {
        val dispatcher = MainQueue()
        val job = Job()
        val scope = CoroutineScope(dispatcher + job)
        val manager = FakeManager()
        val ui = ProvisioningUiState().apply { attach(manager, scope) }
        fun drain() = dispatcher.drain()
    }

    private class MainQueue : CoroutineDispatcher() {
        private val queue = ArrayDeque<Runnable>()
        override fun dispatch(context: CoroutineContext, block: Runnable) {
            queue.addLast(block)
        }

        fun drain() {
            var steps = 0
            while (queue.isNotEmpty()) {
                check(++steps < 10_000) { "presentation scheduler did not become idle" }
                queue.removeFirst().run()
            }
        }
    }

    @OptIn(ExperimentalP2pApi::class)
    private class FakeManager : NetworkProvisioningManager {
        override val state = MutableStateFlow<NetworkProvisioningState>(NetworkProvisioningState.Idle)
        override val networkState = MutableStateFlow<NetworkState>(NetworkState.Unknown)
        override val events = MutableSharedFlow<NetworkProvisioningEvent>(
            replay = 0,
            extraBufferCapacity = 16,
            onBufferOverflow = BufferOverflow.DROP_OLDEST
        )

        override suspend fun startLocalNetwork(config: LocalNetworkConfig): LocalNetworkResult {
            networkState.value = NetworkState.LocalNetworkHosted(credentials, listOf("192.0.2.1"))
            state.value = NetworkProvisioningState.LocalNetworkRunning
            events.tryEmit(NetworkProvisioningEvent.LocalNetworkStarted(credentials))
            return LocalNetworkResult.Started(credentials, null)
        }

        override suspend fun joinLocalNetwork(credentials: WifiCredentials): JoinNetworkResult {
            val joined = NetworkState.ConnectedToWifi(credentials.ssid, listOf("192.0.2.2"))
            networkState.value = joined
            state.value = NetworkProvisioningState.JoinedNetwork
            events.tryEmit(NetworkProvisioningEvent.NetworkJoined(joined))
            return JoinNetworkResult.Joined(joined)
        }

        fun stopFromSystem() {
            val error = NetworkProvisioningError.HotspotStopped("synthetic OS stop")
            state.value = NetworkProvisioningState.Failed(error)
            networkState.value = NetworkState.Unknown
            events.tryEmit(NetworkProvisioningEvent.Failed(error))
        }

        fun releaseFromSystem() {
            val error = NetworkProvisioningError.JoinFailed("synthetic OS release")
            state.value = NetworkProvisioningState.Failed(error)
            networkState.value = NetworkState.Unknown
            events.tryEmit(NetworkProvisioningEvent.Failed(error))
        }

        override suspend fun stopLocalNetwork() = error("unused")
        override suspend fun getManualConnectionInfo(): ManualConnectionInfo? = error("unused")
        @Deprecated("Test stub for the deprecated API")
        override suspend fun createManualPeer(host: String, port: Int): Peer = error("unused")
        override suspend fun createManualPeer(host: String, port: Int, expectedFingerprint: PeerFingerprint): Peer =
            error("unused")
        override suspend fun close() = error("presentation must not own native cleanup")
    }

    private companion object {
        val credentials = WifiCredentials("synthetic-hotspot", WifiPassword("test-only-pass"), WifiSecurityType.WPA2)
    }
}
