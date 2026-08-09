package dev.p2pkit.sample.android

import dev.p2pkit.core.FeatureState
import kotlinx.coroutines.CoroutineStart
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.launch
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.yield
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertTrue

/** Deterministic ordering tests for Android Activity foreground recovery. */
class ForegroundFeatureRestorerTest {
    @Test
    fun waitsForBackgroundPauseBeforeRestartingRequestedFeature() = runBlocking {
        val states = MutableStateFlow<FeatureState>(FeatureState.Active)
        var starts = 0
        var restored = false

        val job = launch(start = CoroutineStart.UNDISPATCHED) {
            restored = restoreRequestedFeatureAfterForeground(
                isStillRequested = { true },
                states = states,
                start = { starts += 1 }
            )
        }
        assertEquals(0, starts)
        states.value = FeatureState.Stopping
        yield()
        assertEquals(0, starts)

        states.value = FeatureState.Idle
        job.join()
        assertTrue(restored)
        assertEquals(1, starts)
    }

    @Test
    fun revokedIntentDoesNotRestartAfterPauseSettles() = runBlocking {
        val states = MutableStateFlow<FeatureState>(FeatureState.Active)
        var requested = true
        var starts = 0
        var restored = true

        val job = launch(start = CoroutineStart.UNDISPATCHED) {
            restored = restoreRequestedFeatureAfterForeground(
                isStillRequested = { requested },
                states = states,
                start = { starts += 1 }
            )
        }
        requested = false
        states.value = FeatureState.Idle
        job.join()

        assertFalse(restored)
        assertEquals(0, starts)
    }

    @Test
    fun alreadySettledRequestedFeatureRestartsImmediately() = runBlocking {
        val states = MutableStateFlow<FeatureState>(FeatureState.Idle)
        var starts = 0

        assertTrue(
            restoreRequestedFeatureAfterForeground(
                isStillRequested = { true },
                states = states,
                start = { starts += 1 }
            )
        )
        assertEquals(1, starts)
    }
}
