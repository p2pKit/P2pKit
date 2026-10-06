package dev.p2pkit.sample.android.rpclab

import androidx.compose.runtime.AbstractApplier
import androidx.compose.runtime.BroadcastFrameClock
import androidx.compose.runtime.Composable
import androidx.compose.runtime.Composition
import androidx.compose.runtime.Recomposer
import androidx.compose.runtime.SideEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.snapshots.Snapshot
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.launch
import kotlinx.coroutines.test.advanceTimeBy
import kotlinx.coroutines.test.runCurrent
import kotlinx.coroutines.test.runTest
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [35], manifest = Config.NONE)
@OptIn(ExperimentalCoroutinesApi::class)
class RpcLabLiveCompositionTest {
    private class NoOpApplier : AbstractApplier<Unit>(Unit) {
        override fun insertBottomUp(index: Int, instance: Unit) = Unit
        override fun insertTopDown(index: Int, instance: Unit) = Unit
        override fun move(from: Int, to: Int, count: Int) = Unit
        override fun remove(index: Int, count: Int) = Unit
        override fun onClear() = Unit
    }

    @Composable
    private fun Root(observer: RpcLabLiveObserver, root: () -> Unit, leaf: (RpcLabLiveView) -> Unit) {
        SideEffect(root)
        Leaf(observer, leaf)
    }

    @Composable
    private fun Leaf(observer: RpcLabLiveObserver, composed: (RpcLabLiveView) -> Unit) {
        val view by observer.view.collectAsState()
        SideEffect { composed(view) }
    }

    @Test
    fun unchangedTwentyThousandTicksDoNotRecomposeAndOneChangedSampleOnlyInvalidatesTheLeaf() = runTest {
        var sample = RpcLabLiveSnapshot(true, "Running", 0, 0, 0, emptyList())
        val observer = RpcLabLiveObserver(this, {}, { error("Unexpected read failure") })
        val clock = BroadcastFrameClock()
        val recomposer = Recomposer(coroutineContext + clock)
        val runner = launch(clock) { recomposer.runRecomposeAndApplyChanges() }
        val composition = Composition(NoOpApplier(), recomposer)
        var roots = 0
        var leaves = 0
        var rendered: RpcLabLiveView? = null
        fun frame() {
            runCurrent()
            Snapshot.sendApplyNotifications()
            runCurrent()
            clock.sendFrame(testScheduler.currentTime * 1_000_000)
            runCurrent()
        }
        try {
            observer.start(Any()) { sample.copy(pending = emptyList()) }
            runCurrent()
            composition.setContent { Root(observer, { roots++ }, { rendered = it; leaves++ }) }
            frame()
            assertEquals(sample, rendered?.snapshot)
            val baselineRoots = roots
            val baselineLeaves = leaves
            assertTrue(baselineRoots > 0 && baselineLeaves > 0)
            repeat(20_000) { advanceTimeBy(500); frame() }
            assertEquals(baselineRoots, roots)
            assertEquals(baselineLeaves, leaves)
            sample = sample.copy(completed = 1)
            advanceTimeBy(500); frame()
            assertEquals(1L, rendered?.snapshot?.completed)
            assertEquals(baselineRoots, roots)
            assertEquals(baselineLeaves + 1, leaves)
        } finally {
            observer.stop()
            composition.dispose()
            recomposer.close()
            runCurrent()
            runner.cancel()
        }
    }
}
