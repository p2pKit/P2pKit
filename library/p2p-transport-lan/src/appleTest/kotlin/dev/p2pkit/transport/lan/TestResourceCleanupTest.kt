package dev.p2pkit.transport.lan

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertSame
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.awaitCancellation
import kotlinx.coroutines.cancelAndJoin
import kotlinx.coroutines.currentCoroutineContext
import kotlinx.coroutines.ensureActive
import kotlinx.coroutines.launch
import kotlinx.coroutines.runBlocking

class TestResourceCleanupTest {
    @Test
    fun failureBetweenAcquisitionsRetiresExactlyTheAcquiredResources() = runBlocking {
        for (acquired in 1..3) {
            val retired = mutableListOf<Int>()
            val primary = IllegalStateException("synthetic setup failure")
            val result = runCatching {
                withTestResourceCleanup { cleanup ->
                    repeat(acquired) { resource -> cleanup.own { retired += resource } }
                    throw primary
                }
            }
            assertSame(primary, result.exceptionOrNull())
            assertEquals((0 until acquired).reversed().toList(), retired)
        }
    }

    @Test
    fun cleanupFailuresDoNotSkipIndependentResourcesOrReplacePrimaryFailure() = runBlocking {
        val primary = CancellationException("synthetic cancelled setup")
        val first = IllegalStateException("first cleanup failure")
        val second = IllegalStateException("second cleanup failure")
        val retired = mutableListOf<Int>()
        val result = runCatching {
            withTestResourceCleanup { cleanup ->
                cleanup.own { retired += 0; throw second }
                cleanup.own { currentCoroutineContext().ensureActive(); retired += 1; throw first }
                throw primary
            }
        }
        assertSame(primary, result.exceptionOrNull())
        assertEquals(listOf(first, second), primary.suppressedExceptions)
        assertEquals(listOf(1, 0), retired)
    }

    @Test
    fun otherwiseSuccessfulTestFailsOnCleanupAndStillRetiresEveryResource() = runBlocking {
        val failure = IllegalStateException("cleanup failure")
        val retired = mutableListOf<Int>()
        val result = runCatching {
            withTestResourceCleanup { cleanup ->
                cleanup.own { retired += 0 }
                cleanup.own { retired += 1; throw failure }
            }
        }
        assertSame(failure, result.exceptionOrNull())
        assertEquals(listOf(1, 0), retired)
    }

    @Test
    fun cancelledOwnerStillExecutesSuspendingCleanupInAnActiveContext() = runBlocking {
        val entered = CompletableDeferred<Unit>()
        var cleaned = false
        val child = launch {
            withTestResourceCleanup { cleanup ->
                cleanup.own {
                    currentCoroutineContext().ensureActive()
                    cleaned = true
                }
                entered.complete(Unit)
                awaitCancellation()
            }
        }
        entered.await()
        child.cancelAndJoin()
        assertEquals(true, cleaned)
    }

    @Test
    fun acquisitionEnrolledDuringRetirementIsAlsoDrained() = runBlocking {
        val retired = mutableListOf<Int>()
        withTestResourceCleanup { cleanup ->
            cleanup.own { retired += 0 }
            cleanup.own {
                retired += 1
                cleanup.own { retired += 2 }
            }
        }
        assertEquals(listOf(1, 2, 0), retired)
    }
}
