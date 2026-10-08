@file:OptIn(ExperimentalForeignApi::class)

package dev.p2pkit.transport.lan

import kotlin.time.TimeSource
import kotlinx.cinterop.ExperimentalForeignApi
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.NonCancellable
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.withContext
import kotlinx.coroutines.withTimeoutOrNull
import platform.Foundation.NSLock
import platform.darwin.dispatch_async
import platform.darwin.dispatch_queue_create
import platform.darwin.dispatch_queue_t

/** A failure-only observation. It cannot publish a peer or replace the original subscription. */
internal object IosLanLiveTxtFailureProbe {
    enum class Query { NOT_STARTED, STARTED, START_ERROR, SCHEDULE_ERROR, CALLBACK_ERROR, OVERFLOW, THREW }
    enum class Answer { EXPECTED, PREVIOUS, OTHER, MIXED, MALFORMED, EMPTY, INCOMPLETE, UNKNOWN }
    enum class Cleanup { COMPLETE, INCOMPLETE, NOT_STARTED }

    data class Result(
        val publisherQueue: Boolean = false,
        val receiverQueue: Boolean = false,
        val query: Query = Query.NOT_STARTED,
        val startError: Int? = null,
        val scheduleError: Int? = null,
        val callbackError: Int? = null,
        val callbacks: Int = 0,
        val pending: Boolean = false,
        val records: Int = 0,
        val answer: Answer = Answer.UNKNOWN,
        val queries: Int = 0,
        val reserved: Int = 0,
        val retained: Int = 0,
        val cleanup: Cleanup = Cleanup.INCOMPLETE,
        val capped: Boolean = false
    ) {
        fun renderFields(localCapped: Boolean = false): String =
            "publisherQueue=$publisherQueue receiverQueue=$receiverQueue query=$query " +
                "startError=${startError ?: "NONE"} scheduleError=${scheduleError ?: "NONE"} " +
                "callbackError=${callbackError ?: "NONE"} callbacks=$callbacks pending=$pending " +
                "records=$records answer=$answer queries=$queries reserved=$reserved retained=$retained " +
                "cleanup=$cleanup capped=${capped || localCapped}"
    }

    suspend fun inspect(
        service: IosLanTxtService,
        fullName: String,
        expected: Map<String, String>,
        previous: Map<String, String>,
        publisherQueue: dispatch_queue_t,
        receiverQueue: dispatch_queue_t
    ): Result = withContext(NonCancellable) {
        val session = Session(service, fullName, expected.toMap(), previous.toMap())
        try {
            session.begin(publisherQueue, receiverQueue)
            withTimeoutOrNull(session.remainingMillis(4000)) { session.readDone.await() }
        } finally {
            // Never await the production monitor's unbounded drain, or touch its lock from this caller.
            session.requestRetirement()
            withTimeoutOrNull(session.remainingMillis(5000)) { session.cleaned.await() }
        }
        session.result()
    }

    private class Session(
        private val service: IosLanTxtService,
        private val fullName: String,
        private val expected: Map<String, String>,
        private val previous: Map<String, String>
    ) {
        private val started = TimeSource.Monotonic.markNow()
        private val queue = dispatch_queue_create("dev.p2pkit.test.live-txt.failure", null)
        private val native = PlatformIosLanTxtDns(queue)
        private val stateLock = NSLock()
        private val closed = MutableStateFlow(false)
        private val retirementRequested = MutableStateFlow(false)
        private val publisherSeen = MutableStateFlow(false)
        private val receiverSeen = MutableStateFlow(false)
        private val progress = MutableStateFlow(Result())
        val readDone = CompletableDeferred<Unit>()
        val cleaned = CompletableDeferred<Unit>()

        // These two variables and every monitor operation are confined to the fresh serial queue.
        private var settled = false
        private var answerFrozen = false

        private val dns = object : IosLanTxtDns {
            override fun constructFullName(name: String, type: String, domain: String): String = fullName

            override fun enqueue(block: () -> Unit) = onQueue(block)

            override fun start(
                fullName: String,
                callback: (Int, () -> IosLanTxtAnswer) -> Unit
            ): IosLanTxtDns.Start {
                // A queued start which loses the deadline must not create a native reference.
                check(open())
                return try {
                    val start = native.start(fullName) { error, fields ->
                        receive(error, fields, callback)
                    }
                    try {
                        progress.value = progress.value.copy(startError = start.error)
                        if (start.error != 0 || start.reference == null) {
                            progress.value = progress.value.copy(query = Query.START_ERROR)
                            requestRetirement()
                            start
                        } else {
                            progress.value = progress.value.copy(query = Query.STARTED)
                            IosLanTxtDns.Start(start.error, reference(start.reference))
                        }
                    } catch (failure: Throwable) {
                        if (start.error != 0 || start.reference == null) throw failure
                        // Wrapping/report allocation cannot strand an already-created native ref.
                        // Hand the original back: the closed monitor attaches it and retires it.
                        closed.value = true
                        try { thrown() } catch (_: Throwable) { }
                        start
                    }
                } catch (failure: Throwable) {
                    thrown()
                    throw failure
                }
            }
        }

        private val monitor = IosLanTxtMonitor(
            stateLock, dns,
            isCurrentGenerationLocked = { it == service.generation && open() },
            onSnapshot = {
                settled = true
                requestRetirement()
            },
            // No peer relay, admission, or getter/reentrant lock acquisition in this callback.
            onWithdrawLocked = { }
        )

        fun remainingMillis(limit: Long): Long = (limit - started.elapsedNow().inWholeMilliseconds).coerceAtLeast(0)

        private fun open(): Boolean = !closed.value && remainingMillis(4000) > 0

        fun begin(publisherQueue: dispatch_queue_t, receiverQueue: dispatch_queue_t) {
            dispatch_async(publisherQueue) { if (remainingMillis(5000) > 0) publisherSeen.value = true }
            dispatch_async(receiverQueue) { if (remainingMillis(5000) > 0) receiverSeen.value = true }
            onQueue {
                if (open()) {
                    monitor.add(service)
                    resources()
                } else {
                    requestRetirement()
                }
            }
        }

        private fun onQueue(block: () -> Unit) {
            dispatch_async(queue) {
                try { block() } catch (_: Throwable) { thrown() }
            }
        }

        private fun thrown() {
            progress.value = progress.value.copy(query = Query.THREW, answer = Answer.UNKNOWN)
            requestRetirement()
        }

        private fun reference(reference: IosLanTxtDns.Reference): IosLanTxtDns.Reference =
            object : IosLanTxtDns.Reference {
                override fun schedule(): Int = try {
                    reference.schedule().also { error ->
                        progress.value = progress.value.copy(scheduleError = error)
                        resources()
                        if (error != 0) {
                            progress.value = progress.value.copy(query = Query.SCHEDULE_ERROR)
                            requestRetirement()
                        }
                    }
                } catch (failure: Throwable) {
                    thrown()
                    throw failure
                }

                override fun deallocate() {
                    try { reference.deallocate() } catch (failure: Throwable) {
                        thrown()
                        throw failure
                    }
                }

                override fun disposeContext() {
                    try { reference.disposeContext() } catch (failure: Throwable) {
                        thrown()
                        throw failure
                    }
                }
            }

        private fun receive(
            error: Int,
            fields: () -> IosLanTxtAnswer,
            callback: (Int, () -> IosLanTxtAnswer) -> Unit
        ) {
            if (!open()) {
                requestRetirement()
                return
            }
            if (progress.value.callbacks == 64) {
                progress.value = progress.value.copy(query = Query.OVERFLOW, capped = true)
                requestRetirement()
                return
            }
            progress.value = progress.value.copy(callbacks = progress.value.callbacks + 1, callbackError = error)
            // Forward the original lazy supplier exactly once. A native error never reads its fields.
            if (error != 0) progress.value = progress.value.copy(query = Query.CALLBACK_ERROR, callbackError = error)
            try {
                callback(error, fields)
                resources()
                if (error != 0) requestRetirement()
            } catch (_: Throwable) {
                thrown()
            }
        }

        fun requestRetirement() {
            closed.value = true
            if (retirementRequested.compareAndSet(expect = false, update = true)) onQueue(::finishOnQueue)
        }

        private fun resources() {
            val queries = monitor.queryCountForTest
            val reserved = monitor.reservedQueryCountForTest
            val retained = monitor.retainedBytesForTest
            progress.value = progress.value.copy(
                queries = queries.coerceIn(0, 1), reserved = reserved.coerceIn(0, 1),
                retained = retained.coerceIn(0, 524280),
                capped = progress.value.capped || queries !in 0..1 || reserved !in 0..1 || retained !in 0..524280
            )
        }

        private fun finishOnQueue() {
            if (answerFrozen) return
            answerFrozen = true
            val snapshot = monitor.snapshotForTest(service.name)
            val records = snapshot?.records.orEmpty()
            progress.value = progress.value.copy(
                pending = snapshot?.pending == true,
                records = records.size.coerceIn(0, 8),
                answer = when {
                    progress.value.query != Query.STARTED || snapshot == null || !snapshot.owner.active ->
                        Answer.UNKNOWN
                    snapshot.pending -> Answer.INCOMPLETE
                    !settled -> Answer.UNKNOWN
                    else -> classify(records)
                },
                capped = progress.value.capped || records.size > 8
            )
            resources()
            readDone.complete(Unit)
            // The snapshot above is pre-retirement. Closing/deallocation/context disposal remain
            // the maintained monitor's operations on its scheduled queue, never a caller-side free.
            stateLock.lock()
            val retiring = try { monitor.invalidateAllLocked() } finally { stateLock.unlock() }
            monitor.retire(retiring)
            onQueue {
                onQueue {
                    resources()
                    val empty = monitor.queryCountForTest == 0 && monitor.reservedQueryCountForTest == 0 &&
                        monitor.retainedBytesForTest == 0
                    val complete = empty && remainingMillis(5000) > 0
                    progress.value = progress.value.copy(
                        cleanup = if (complete) Cleanup.COMPLETE else Cleanup.INCOMPLETE
                    )
                    cleaned.complete(Unit)
                }
            }
        }

        private fun classify(records: List<IosBonjour.DecodedRecord>): Answer = when {
            records.isEmpty() -> Answer.EMPTY
            records.any { it.malformed } -> Answer.MALFORMED
            records.map { it.properties }.distinct().size != 1 -> Answer.MIXED
            records.all { it.properties == expected } -> Answer.EXPECTED
            records.all { it.properties == previous } -> Answer.PREVIOUS
            else -> Answer.OTHER
        }

        fun result(): Result {
            // Reading immutable values cannot block on a stuck native queue/monitor lock. If the
            // barrier was late, closures/context retain safe ownership and finish later, not here.
            val value = progress.value
            return value.copy(
                publisherQueue = publisherSeen.value,
                receiverQueue = receiverSeen.value,
                answer = if (value.cleanup == Cleanup.COMPLETE) value.answer else Answer.UNKNOWN
            )
        }
    }
}
