package dev.p2pkit.transport.lan

import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.Job
import kotlinx.coroutines.cancelAndJoin
import kotlinx.coroutines.currentCoroutineContext
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.FlowCollector
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.collect
import kotlinx.coroutines.flow.flow
import kotlinx.coroutines.flow.onCompletion
import kotlinx.coroutines.flow.onSubscription
import kotlinx.coroutines.launch
import kotlinx.coroutines.test.StandardTestDispatcher
import kotlinx.coroutines.test.UnconfinedTestDispatcher
import kotlinx.coroutines.test.runCurrent
import kotlinx.coroutines.test.runTest
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertIs
import kotlin.test.assertNotNull
import kotlin.test.assertSame
import kotlin.test.assertTrue

@OptIn(ExperimentalCoroutinesApi::class)
class IosOwnedFlowCollectionTest {
    @Test
    fun cancellationBeforeStartNeverAdmitsSourceOrCallback() = runTest {
        val source = MutableSharedFlow<Any?>()
        var subscriptions = 0
        var callbacks = 0
        val job = createIosOwnedFlowCollection(
            source.onSubscription { subscriptions++ },
            FlowCollector { callbacks++ },
            StandardTestDispatcher(testScheduler)
        )
        val parent = assertNotNull(job.parent)
        try {
            runCurrent()
            assertFalse(job.isActive)
            assertFalse(job.isCompleted)
            assertEquals(0, source.subscriptionCount.value)
            job.cancel()
            job.cancel()
            assertFalse(job.start())
            runCurrent()
            assertTrue(job.isCompleted)
            assertTrue(parent.isCompleted)
            assertEquals(0, source.subscriptionCount.value)
            assertEquals(0, subscriptions)
            assertEquals(0, callbacks)
        } finally {
            job.cancelAndJoin()
            parent.join()
        }
    }

    @Test
    fun idleSharedFlowCancellationClosesSubscriptionAndPrivateParent() = runTest {
        val source = MutableSharedFlow<Any?>()
        var collectingJob: Job? = null
        var completed = 0
        var terminalCause: Throwable? = null
        var slotsAtCompletion = -1
        val job = createIosOwnedFlowCollection(
            source.onSubscription { collectingJob = currentCoroutineContext()[Job] },
            FlowCollector { error("An idle source must not need a rescue emission") },
            StandardTestDispatcher(testScheduler)
        )
        val parent = assertNotNull(job.parent)
        job.invokeOnCompletion {
            terminalCause = it
            slotsAtCompletion = source.subscriptionCount.value
            completed++
        }
        try {
            assertTrue(job.start())
            runCurrent()
            assertSame(job, collectingJob)
            assertEquals(1, source.subscriptionCount.value)
            assertFalse(job.isCompleted)
            job.cancel()
            runCurrent()
            assertTrue(job.isCompleted)
            assertTrue(parent.isCompleted)
            assertEquals(0, source.subscriptionCount.value)
            assertEquals(0, slotsAtCompletion)
            assertIs<CancellationException>(terminalCause)
            job.cancel()
            assertEquals(1, completed)
        } finally {
            job.cancelAndJoin()
            parent.join()
        }
    }

    @Test
    fun stateFlowReplayAndCancellationPreserveTheOtherSubscriber() = runTest {
        val source = MutableStateFlow<Any?>("initial")
        val ownedValues = mutableListOf<Any?>()
        val otherValues = mutableListOf<Any?>()
        val other = backgroundScope.launch(UnconfinedTestDispatcher(testScheduler)) {
            source.collect { otherValues += it }
        }
        var finallyRan = false
        val job = createIosOwnedFlowCollection(
            source.onCompletion { finallyRan = true },
            FlowCollector { ownedValues += it },
            StandardTestDispatcher(testScheduler)
        )
        val parent = assertNotNull(job.parent)
        try {
            assertEquals(1, source.subscriptionCount.value)
            assertTrue(job.start())
            runCurrent()
            assertEquals(listOf("initial"), ownedValues)
            assertEquals(2, source.subscriptionCount.value)
            job.cancel()
            runCurrent()
            assertTrue(job.isCompleted)
            assertTrue(parent.isCompleted)
            assertTrue(finallyRan)
            assertEquals(1, source.subscriptionCount.value)
            assertTrue(other.isActive)
            // Only after actual idle retirement: this emission is not the cancellation mechanism.
            source.value = "after-retirement"
            runCurrent()
            assertEquals(listOf("initial"), ownedValues)
            assertEquals(listOf("initial", "after-retirement"), otherValues)
        } finally {
            job.cancelAndJoin()
            parent.join()
            other.cancelAndJoin()
        }
        assertEquals(0, source.subscriptionCount.value)
    }

    @Test
    fun normalCompletionAndFailuresRetainTheirOriginalTerminalCause() = runTest {
        val sourceFailure = IllegalStateException("source failed")
        val collectorFailure = IllegalArgumentException("collector failed")
        val sources: List<Pair<Flow<Any?>, Throwable?>> = listOf(
            flow<Any?> { emit("complete") } to null,
            flow<Any?> { throw sourceFailure } to sourceFailure,
            flow<Any?> { emit("collector-failure") } to collectorFailure
        )
        for ((source, expectedCause) in sources) {
            var completions = 0
            var observedCause: Throwable? = null
            val job = createIosOwnedFlowCollection(
                source,
                FlowCollector { if (it == "collector-failure") throw collectorFailure },
                StandardTestDispatcher(testScheduler)
            )
            val parent = assertNotNull(job.parent)
            job.invokeOnCompletion {
                observedCause = it
                completions++
            }
            try {
                job.start()
                runCurrent()
                assertTrue(job.isCompleted)
                assertTrue(parent.isCompleted)
                assertEquals(expectedCause != null, job.isCancelled)
                assertSame(expectedCause, observedCause)
                job.cancel()
                assertSame(expectedCause, observedCause)
                assertEquals(1, completions)
            } finally {
                job.cancelAndJoin()
                parent.join()
            }
        }
    }
}
