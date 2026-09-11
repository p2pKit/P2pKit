package dev.p2pkit.transport.lan

import kotlinx.coroutines.CoroutineDispatcher
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.CoroutineStart
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.async
import kotlinx.coroutines.cancel
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.FlowCollector

/**
 * Creates the actual collection coroutine, initially lazy, for an owned Swift subscription.
 *
 * Register ownership and a [Job.invokeOnCompletion] handler before calling [Job.start].
 * Cancelling this job cancels its cooperative collection, not the source or another subscriber.
 * Cancellation before start never subscribes. Collection runs on [Dispatchers.Main]; its private
 * parent is closed on completion. Source/collector failures remain the terminal completion cause;
 * [Job.join] waits for completion but does not rethrow that cause (and starts an unstarted job).
 *
 * This is not automatic propagation from `Swift.Task.cancel()`. Swift must cancel the returned job
 * and separately drain callbacks it has accepted. In particular, a Swift collector must acknowledge
 * each suspended `emit` even when its UI callback is deliberately skipped during teardown.
 */
public fun createIosOwnedFlowCollection(flow: Flow<Any?>, collector: FlowCollector<Any?>): Job =
    createIosOwnedFlowCollection(flow, collector, Dispatchers.Main)

internal fun createIosOwnedFlowCollection(
    flow: Flow<Any?>,
    collector: FlowCollector<Any?>,
    dispatcher: CoroutineDispatcher
): Job {
    val scope = CoroutineScope(dispatcher)
    // Deferred retains failure for the completion observer rather than reporting an unhandled
    // root launch exception. Return this coroutine itself, never an unrelated cancellation token.
    val collection = scope.async(start = CoroutineStart.LAZY) { flow.collect(collector) }
    collection.invokeOnCompletion { scope.cancel() }
    return collection
}
