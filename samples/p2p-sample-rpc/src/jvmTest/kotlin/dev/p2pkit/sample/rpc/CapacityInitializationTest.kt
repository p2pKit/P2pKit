package dev.p2pkit.sample.rpc

import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.TimeoutCancellationException
import kotlinx.coroutines.awaitCancellation
import kotlinx.coroutines.delay
import kotlinx.coroutines.test.runTest
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertTrue

@OptIn(ExperimentalCoroutinesApi::class)
class CapacityInitializationTest {
    @Test
    fun everyIndependentClientCompletesTheFixedInitializationBeforeReturning() = runTest {
        val calls = IntArray(128)
        initializeCapacityPaths(call = { calls[it]++ }, nowNanos = { testScheduler.currentTime * 1_000_000 })
        assertEquals(List(128) { 600 }, calls.toList())
        assertEquals(60_000L, testScheduler.currentTime)
        // Initialization cannot shrink the original capacity contract.
        assertEquals(1800, RpcCapacityContract.STEADY_SECONDS)
        assertEquals(10, RpcCapacityContract.CALLS_PER_SECOND_PER_CLIENT)
    }

    @Test
    fun slowInitializationCallsAreAwaitedWithoutDroppedSlotsOrOverlappingCallsPerClient() = runTest {
        val active = BooleanArray(128)
        val calls = IntArray(128)
        initializeCapacityPaths(call = { index ->
            assertTrue(!active[index])
            active[index] = true
            delay(150)
            calls[index]++
            active[index] = false
        }, nowNanos = { testScheduler.currentTime * 1_000_000 })
        assertEquals(List(128) { 600 }, calls.toList())
        assertEquals(90_000L, testScheduler.currentTime)
        assertTrue(active.none { it })
    }

    @Test
    fun aCallFailureIsNotRetriedOrTurnedIntoSuccessfulInitialization() = runTest {
        var failedClientCalls = 0
        var active = 0
        assertFailsWith<IllegalStateException> {
            initializeCapacityPaths(call = { index ->
                active++
                try {
                    if (index == 0) {
                        failedClientCalls++
                        error("Synthetic failure")
                    }
                    awaitCancellation()
                } finally { active-- }
            }, nowNanos = { testScheduler.currentTime * 1_000_000 })
        }
        assertEquals(1, failedClientCalls)
        assertEquals(0, active)
    }

    @Test
    fun initializationHasItsOwnFixedDeadlineAndRetiresAllCallChildren() = runTest {
        var active = 0
        assertFailsWith<TimeoutCancellationException> {
            initializeCapacityPaths(call = {
                active++
                try { awaitCancellation() } finally { active-- }
            }, nowNanos = { testScheduler.currentTime * 1_000_000 })
        }
        assertEquals(120_000L, testScheduler.currentTime)
        assertEquals(0, active)
    }
}
