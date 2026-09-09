package dev.p2pkit.sample.android

import androidx.lifecycle.viewModelScope
import dev.p2pkit.core.P2pState
import dev.p2pkit.core.Peer
import dev.p2pkit.core.PeerId
import dev.p2pkit.core.Platform
import dev.p2pkit.core.TransportKind
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.Job
import kotlinx.coroutines.test.runCurrent
import kotlinx.coroutines.test.runTest
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

/** #377: retire every sibling collector of the failed run, not its surviving ViewModel parent. */
@OptIn(ExperimentalCoroutinesApi::class)
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [35], manifest = Config.NONE)
class SampleStartupScopeTest {
    @Test
    fun startupFailureCancelsCapturedRunAfterCleanupAndPreventsOldStateUpdates() = runTest {
        withSampleViewModel {
            val startup = barrier().also { room.beforeAdvertising = { it.await() } }
            room.advertisingFailure = IllegalStateException("synthetic startup failure after collectors subscribe")
            vm.start()
            runCurrent()
            assertTrue(room.peers.subscriptionCount.value > 0)
            assertTrue(room.state.subscriptionCount.value > 0)
            assertTrue(room.networkPathStatus.subscriptionCount.value > 0)
            assertTrue(room.sessions.subscriptionCount.value > 0)

            startup.complete(Unit)
            runCurrent()
            assertEquals(1, room.stopCalls)
            assertEquals(0, room.peers.subscriptionCount.value)
            assertEquals(0, room.state.subscriptionCount.value)
            assertEquals(0, room.networkPathStatus.subscriptionCount.value)
            assertEquals(0, room.sessions.subscriptionCount.value)
            assertTrue(requireNotNull(vm.viewModelScope.coroutineContext[Job]).isActive)
            assertEquals(P2pState.Stopped, vm.kitState.value)

            room.state.value = P2pState.Running
            room.peers.value = listOf(
                Peer(PeerId("synthetic-stale-peer"), "Stale peer", Platform.ANDROID, setOf(TransportKind.LAN))
            )
            runCurrent()
            assertEquals(P2pState.Stopped, vm.kitState.value)
            assertTrue(vm.peers.value.isEmpty())
        }
    }
}
