package dev.p2pkit.sample.android.rpclab

import java.io.File
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertFalse
import kotlin.test.assertNull
import kotlin.test.assertSame
import kotlin.test.assertTrue
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.CoroutineStart
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.Job
import kotlinx.coroutines.NonCancellable
import kotlinx.coroutines.async
import kotlinx.coroutines.cancelAndJoin
import kotlinx.coroutines.currentCoroutineContext
import kotlinx.coroutines.flow.collect
import kotlinx.coroutines.job
import kotlinx.coroutines.launch
import kotlinx.coroutines.test.StandardTestDispatcher
import kotlinx.coroutines.test.runCurrent
import kotlinx.coroutines.test.runTest
import kotlinx.coroutines.withContext

/** Host JVM controls with inert resources, not Android radio/Activity execution or successful SDK retry evidence. */
@OptIn(ExperimentalCoroutinesApi::class)
class RpcLabRuntimeOwnerTest {
    private class Runtime(var failure: Exception? = null) {
        var closes = 0
        suspend fun close() { closes++; failure?.let { throw it } }
    }

    private fun <T : Any> hold(owner: RpcLabRuntimeOwner<T>, value: T): RpcLabRuntimeOwner.Token {
        val creator = Job()
        val token = owner.beginCreation(creator)
        owner.retain(token, value)
        owner.finishCreation(token)
        creator.complete()
        return token
    }

    @Test
    fun cancelledDispatcherReturnRetainsFailedUnpublishedOwnerAndCannotBeHiddenByJoin() = runTest {
        val owner = RpcLabRuntimeOwner<Runtime>()
        val failure = IllegalStateException("synthetic late close failure")
        val runtime = Runtime(failure)
        val reported = mutableListOf<Exception>()
        var published: Runtime? = null
        var beforeCancellation: RpcLabRuntimeOwner.Snapshot<Runtime>? = null
        lateinit var action: Job
        action = backgroundScope.launch(start = CoroutineStart.LAZY) {
            val token = owner.beginCreation(currentCoroutineContext().job)
            var created: Runtime? = null
            try {
                try {
                    withContext(StandardTestDispatcher(testScheduler)) {
                        created = runtime
                        owner.retain(token, runtime)
                        beforeCancellation = owner.snapshot()
                        action.cancel()
                    }
                    published = created
                } finally {
                    if (created != null && published !== created) withContext(NonCancellable) {
                        owner.retire(token) { it.close() }
                    }
                }
            } catch (error: Exception) { reported += error }
            finally { owner.finishCreation(token) }
        }
        action.start()
        runCurrent()
        action.join()
        val stopped = checkNotNull(beforeCancellation)
        assertNull(published)
        assertEquals<List<Exception>>(listOf(failure), reported)
        assertSame(runtime, owner.current(stopped.token))
        assertSame(failure, checkNotNull(owner.failure).cause)
        assertSame(failure, assertFailsWith<IllegalStateException> { owner.awaitCreation(stopped) })
        assertFailsWith<IllegalStateException> { owner.beginCreation(Job()) }
        assertEquals(1, runtime.closes, "Stop must report the newly failed cleanup, not silently retry it")

        val retry = checkNotNull(owner.snapshot()) // A new controller/Activity must use this same retained token.
        owner.awaitCreation(retry)
        runtime.failure = null
        owner.retire(retry.token) { it.close() }
        assertEquals(2, runtime.closes)
        assertFalse(owner.occupied)
        assertNull(owner.failure)
        assertEquals<List<Exception>>(listOf(failure), reported, "Later cleanup does not erase the earlier failure")
        val replacement = Runtime()
        val next = hold(owner, replacement)
        assertSame(replacement, owner.current(next))
        owner.retire(next) { it.close() }
    }

    @Test
    fun stopWaitsForCreationBeforeReadingItsRetainedOwner() = runTest {
        val owner = RpcLabRuntimeOwner<Runtime>()
        val runtime = Runtime()
        val release = CompletableDeferred<Unit>()
        val action = backgroundScope.launch {
            val token = owner.beginCreation(currentCoroutineContext().job)
            try { release.await(); owner.retain(token, runtime) }
            finally { owner.finishCreation(token) }
        }
        runCurrent()
        val stopped = checkNotNull(owner.snapshot())
        assertSame(action, stopped.creator)
        assertNull(stopped.current)
        assertTrue(owner.occupied, "A recreated Activity must see the pendingOwner factory reservation")
        assertFailsWith<IllegalStateException> { owner.beginCreation(Job()) }
        val stop = async {
            owner.awaitCreation(stopped)
            owner.retire(stopped.token) { it.close() }
        }
        runCurrent()
        assertFalse(stop.isCompleted)
        assertEquals(0, runtime.closes)
        release.complete(Unit)
        assertSame(runtime, stop.await())
        assertEquals(1, runtime.closes)
        assertFalse(owner.occupied)
    }

    @Test
    fun recreatedControllerCancelsAndJoinsOriginalCreationBeforeReportingItsLateCloseFailure() = runTest {
        val owner = RpcLabRuntimeOwner<Runtime>()
        val failure = IllegalStateException("synthetic old Activity late cleanup failure")
        val runtime = Runtime(failure)
        val releaseFactory = CompletableDeferred<Unit>()
        val reported = mutableListOf<Exception>()
        val action = backgroundScope.launch {
            val token = owner.beginCreation(currentCoroutineContext().job)
            try {
                try {
                    withContext(NonCancellable) {
                        releaseFactory.await()
                        owner.retain(token, runtime)
                    }
                } finally {
                    withContext(NonCancellable) { owner.retire(token) { it.close() } }
                }
            } catch (error: Exception) { reported += error }
            finally { owner.finishCreation(token) }
        }
        runCurrent()
        val newController = checkNotNull(owner.snapshot())
        assertSame(action, newController.creator)
        val stop = async {
            newController.creator?.cancel()
            try { owner.awaitCreation(newController); null } catch (error: Exception) { error }
        }
        runCurrent()
        assertFalse(stop.isCompleted)
        assertTrue(action.isCancelled)
        assertTrue(owner.occupied)
        assertFailsWith<IllegalStateException> { owner.beginCreation(Job()) }
        releaseFactory.complete(Unit)
        assertSame(failure, stop.await())
        assertEquals<List<Exception>>(listOf(failure), reported)
        assertSame(runtime, owner.current(newController.token))
        assertEquals(1, runtime.closes)
        val retry = checkNotNull(owner.snapshot())
        owner.awaitCreation(retry)
        runtime.failure = null
        owner.retire(retry.token) { it.close() }
        assertFalse(owner.occupied)
        assertEquals(2, runtime.closes)
    }

    @Test
    fun ordinaryCloseFailureKeepsTheExactOwnerAndEveryFailedAttemptDistinct() = runTest {
        val owner = RpcLabRuntimeOwner<Runtime>()
        val failure = IllegalStateException("synthetic latched failure")
        val runtime = Runtime(failure)
        val token = hold(owner, runtime)
        assertSame(failure, assertFailsWith<IllegalStateException> { owner.retire(token) { it.close() } })
        val first = checkNotNull(owner.snapshot())
        assertSame(failure, assertFailsWith<IllegalStateException> { owner.retire(token) { it.close() } })
        assertTrue(first.failure !== owner.failure)
        assertSame(failure, assertFailsWith<IllegalStateException> { owner.awaitCreation(first) })
        assertSame(runtime, owner.current(token))
        assertFailsWith<IllegalStateException> { owner.beginCreation(Job()) }
        runtime.failure = null
        owner.retire(token) { it.close() }
        assertFalse(owner.occupied)
    }

    @Test
    fun requiredClosedReceiptFailureCannotReleaseOwnershipEvenAfterRuntimeCloseReturns() = runTest {
        val owner = RpcLabRuntimeOwner<Runtime>()
        val runtime = Runtime()
        val publication = IllegalStateException("synthetic evidence publication failure")
        val token = hold(owner, runtime)
        assertSame(publication, assertFailsWith<IllegalStateException> {
            owner.retire(token) { it.close(); throw publication }
        })
        assertSame(runtime, owner.current(token))
        assertSame(publication, checkNotNull(owner.failure).cause)
        assertFailsWith<IllegalStateException> { owner.beginCreation(Job()) }
        owner.retire(token) { it.close() }
        assertFalse(owner.occupied)
        assertEquals(2, runtime.closes)
    }

    @Test
    fun cancelledUnpublishedMobileRetainsReceiptFailureUntilAnExplicitStopVerifiesTheSameRecord() = runTest {
        val owner = RpcLabRuntimeOwner<Runtime>()
        val runtime = Runtime()
        val failure = IllegalStateException("synthetic immutable receipt durability failure")
        val expected = "runtimeClosed=true\nclientPinsRemoved=true\ncontrolHealthy=false\n"
        var record: String? = null
        var publications = 0
        var published: Runtime? = null
        val reported = mutableListOf<Exception>()
        suspend fun close(retained: Runtime) {
            retained.close()
            val existing = record
            if (existing == null) {
                record = expected
                publications++
                throw failure // Immutable data can be visible before its final fsync fails.
            } else check(existing == expected)
        }
        var beforeCancellation: RpcLabRuntimeOwner.Snapshot<Runtime>? = null
        lateinit var action: Job
        action = backgroundScope.launch(start = CoroutineStart.LAZY) {
            val token = owner.beginCreation(currentCoroutineContext().job)
            var created: Runtime? = null
            try {
                try {
                    withContext(StandardTestDispatcher(testScheduler)) {
                        created = runtime
                        owner.retain(token, runtime)
                        beforeCancellation = owner.snapshot()
                        action.cancel()
                    }
                    published = created
                } finally {
                    if (created != null && published !== created) withContext(NonCancellable) {
                        owner.retire(token, ::close)
                    }
                }
            } catch (error: Exception) { reported += error }
            finally { owner.finishCreation(token) }
        }
        action.start()
        runCurrent()
        action.join()
        val stopped = checkNotNull(beforeCancellation)
        assertNull(published)
        assertEquals<List<Exception>>(listOf(failure), reported)
        assertSame(runtime, owner.current(stopped.token))
        assertSame(failure, checkNotNull(owner.failure).cause)
        assertSame(failure, assertFailsWith<IllegalStateException> { owner.awaitCreation(stopped) })
        assertFailsWith<IllegalStateException> { owner.beginCreation(Job()) }
        assertEquals(1, runtime.closes)
        assertEquals(1, publications)

        val retry = checkNotNull(owner.snapshot())
        owner.awaitCreation(retry)
        assertSame(runtime, owner.retire(retry.token, ::close))
        assertFalse(owner.occupied)
        assertNull(owner.failure)
        assertEquals(2, runtime.closes)
        assertEquals(1, publications, "A new controller must verify, not replace, the original immutable receipt")
        assertEquals(expected, record)
        assertEquals<List<Exception>>(
            listOf(failure),
            reported,
            "Cleanup never turns the earlier mobile campaign into a pass",
        )
    }

    @Test
    fun serializedSuccessfulRetirementClosesOneOwnerOnlyOnce() = runTest {
        val owner = RpcLabRuntimeOwner<Runtime>()
        val runtime = Runtime()
        val release = CompletableDeferred<Unit>()
        val token = hold(owner, runtime)
        val first = async { owner.retire(token) { release.await(); it.close() } }
        val second = async { owner.retire(token) { it.close() } }
        runCurrent()
        assertFalse(first.isCompleted)
        assertFalse(second.isCompleted)
        release.complete(Unit)
        assertSame(runtime, first.await())
        assertNull(second.await())
        assertEquals(1, runtime.closes)
        assertFalse(owner.occupied)
    }

    @Test
    fun successfulLateCloseStillReservesCreationUntilTheOriginalCreatorFinallyFinishes() = runTest {
        val owner = RpcLabRuntimeOwner<Runtime>()
        val creator = Job()
        val token = owner.beginCreation(creator)
        val runtime = Runtime()
        owner.retain(token, runtime)
        owner.retire(token) { it.close() }
        assertNull(owner.current(token))
        assertTrue(owner.occupied)
        assertSame(creator, checkNotNull(owner.snapshot()).creator)
        assertFailsWith<IllegalStateException> { owner.beginCreation(Job()) }
        owner.finishCreation(token)
        creator.complete()
        assertFalse(owner.occupied)
    }

    @Test
    fun anotherControllerObservesReservationFailureAndFinalReleaseThroughReadonlyProcessState() = runTest {
        val owner = RpcLabRuntimeOwner<Runtime>()
        val observed = mutableListOf<Pair<Boolean, Throwable?>>()
        val listener = backgroundScope.launch {
            owner.state.collect { observed += (it != null) to it?.failure?.cause }
        }
        runCurrent()
        val creator = Job()
        val token = owner.beginCreation(creator)
        runCurrent()
        val failure = IllegalStateException("synthetic cross-controller failure")
        val runtime = Runtime(failure)
        owner.retain(token, runtime)
        owner.finishCreation(token)
        creator.complete()
        assertFailsWith<IllegalStateException> { owner.retire(token) { it.close() } }
        runCurrent()
        runtime.failure = null
        owner.retire(token) { it.close() }
        runCurrent()
        listener.cancelAndJoin()
        assertEquals<List<Pair<Boolean, Throwable?>>>(
            listOf(false to null, true to null, true to failure, false to null),
            observed,
        )
    }

    @Test
    fun staleStopAfterOriginalCreatorReleaseCannotRetireAReplacementRun() = runTest {
        val owner = RpcLabRuntimeOwner<Runtime>()
        val creator = Job()
        val oldToken = owner.beginCreation(creator)
        val old = Runtime()
        var oldActivityView: Runtime? = old
        owner.retain(oldToken, old)
        val stopped = checkNotNull(owner.snapshot())
        val joined = CompletableDeferred<Unit>()
        val resumeStop = CompletableDeferred<Unit>()
        val stop = async {
            owner.awaitCreation(stopped)
            joined.complete(Unit)
            resumeStop.await() // Deterministically expose the real join-to-retire scheduling boundary.
            val owned = owner.current(stopped.token) ?: stopped.current
            val retired = owner.retire(stopped.token) { it.close() }
            if (oldActivityView === owned) oldActivityView = null
            retired
        }
        runCurrent()
        assertFalse(stop.isCompleted)
        owner.retire(oldToken) { it.close() }
        owner.finishCreation(oldToken)
        creator.complete()
        joined.await()
        val replacement = Runtime()
        val newToken = hold(owner, replacement)
        resumeStop.complete(Unit)
        assertNull(stop.await())
        assertNull(oldActivityView, "Another controller's successful retirement must not leave a stale local lab")
        assertEquals(1, old.closes)
        assertEquals(0, replacement.closes)
        assertSame(replacement, owner.current(newToken))
        assertTrue(owner.occupied)
        owner.retire(newToken) { it.close() }
    }

    @Test
    fun staleCreationCallbacksCannotPublishOrReleaseAReplacementRun() = runTest {
        val owner = RpcLabRuntimeOwner<Runtime>()
        val creator = Job()
        val oldToken = owner.beginCreation(creator)
        owner.finishCreation(oldToken)
        creator.complete()
        val replacement = Runtime()
        val newToken = hold(owner, replacement)
        assertFailsWith<IllegalStateException> { owner.retain(oldToken, Runtime()) }
        assertFailsWith<IllegalStateException> { owner.finishCreation(oldToken) }
        assertNull(owner.retire(oldToken) { it.close() })
        assertSame(replacement, owner.current(newToken))
        assertEquals(0, replacement.closes)
        owner.retire(newToken) { it.close() }
    }

    @Test
    fun oldAutomaticLifecycleCallbackCannotCancelOrCloseAReplacementActivityRun() = runTest {
        val owner = RpcLabRuntimeOwner<Runtime>()
        val old = Runtime()
        val oldToken = hold(owner, old)
        owner.retire(oldToken) { it.close() }
        val newCreator = Job()
        val newToken = owner.beginCreation(newCreator)
        val replacement = Runtime()
        owner.retain(newToken, replacement)
        val automaticCallback = owner.snapshotFor(oldToken)
        assertNull(automaticCallback)
        automaticCallback?.creator?.cancel()
        if (automaticCallback != null) {
            owner.awaitCreation(automaticCallback)
            owner.retire(automaticCallback.token) { it.close() }
        }
        assertTrue(newCreator.isActive)
        assertEquals(0, replacement.closes)
        assertSame(replacement, owner.current(newToken))
        assertTrue(owner.occupied)
        owner.finishCreation(newToken)
        newCreator.complete()
        owner.retire(newToken) { it.close() }
    }

    @Test
    fun anotherControllerRetiresOriginalBoundContextOnlyAfterItsOriginalMonitorDrains() = runTest {
        val originalRecords = mutableListOf<String>()
        val unrelatedRecords = mutableListOf<String>()
        val events = mutableListOf<String>()
        val monitorStarted = CompletableDeferred<Unit>()
        val monitor = backgroundScope.launch {
            try { monitorStarted.complete(Unit); CompletableDeferred<Unit>().await() }
            finally { events += "original monitor drained" }
        }
        monitorStarted.await()
        class BoundRuntime(val records: MutableList<String>, val monitor: Job) {
            suspend fun close() {
                monitor.cancelAndJoin()
                events += "original runtime closed"
                records += "original-run:controlHealthy=false"
            }
        }
        val owner = RpcLabRuntimeOwner<BoundRuntime>()
        val original = BoundRuntime(originalRecords, monitor)
        hold(owner, original)
        val newController = checkNotNull(owner.snapshot())
        owner.awaitCreation(newController)
        owner.retire(newController.token) { it.close() }
        assertEquals(listOf("original monitor drained", "original runtime closed"), events)
        assertEquals(listOf("original-run:controlHealthy=false"), originalRecords)
        assertEquals(emptyList(), unrelatedRecords, "A new Activity cannot substitute its own mobile files")
        assertFalse(owner.occupied)
    }

    private fun assertBefore(source: String, first: String, second: String) {
        val left = source.indexOf(first)
        val right = source.indexOf(second)
        assertTrue(left >= 0, "Missing required source marker: $first")
        assertTrue(right >= 0, "Missing required source marker: $second")
        assertTrue(left < right, "Expected $first before $second")
    }

    private fun debugSource(name: String): String {
        val relative = "src/debug/java/dev/p2pkit/sample/android/rpclab/$name.kt"
        return generateSequence(File(checkNotNull(System.getProperty("user.dir"))).absoluteFile) { it.parentFile }
            .flatMap { sequenceOf(File(it, relative), File(it, "samples/p2p-sample-android/$relative")) }
            .first(File::isFile).readText()
    }

    @Test
    fun sourceOrderControlRejectsMissingOrReversedMarkers() {
        assertFailsWith<AssertionError> { assertBefore("second", "first", "second") }
        assertFailsWith<AssertionError> { assertBefore("first", "first", "second") }
        assertFailsWith<AssertionError> { assertBefore("neither", "first", "second") }
        assertFailsWith<AssertionError> { assertBefore("second first", "first", "second") }
        assertBefore("first second", "first", "second")
    }

    @Test
    fun actualActivityUsesRetainedOwnershipForCancellationStopAndNewRoleButtons() {
        val source = debugSource("RpcLabActivity")
        assertTrue(source.contains("private val runtimeOwner get() = RpcLabProcessRuntime.owner"))
        assertFalse(source.contains("RpcLabRuntimeOwner<"))
        val lifecycle = source.substringAfter("override fun onStop()").substringBefore("override fun onDestroy()")
        assertTrue(lifecycle.contains("stop(runtimeOwner.snapshotFor(ownedToken))"))
        val start = source.substringAfter("private fun start(").substringBefore("private fun loadMobile(")
        assertBefore(start, "runtimeOwner.beginCreation(currentCoroutineContext().job)", "ownedToken = creation")
        assertBefore(start, "ownedToken = creation", "withContext(Dispatchers.Default)")
        assertBefore(start, "val files = if (mobile != null) checkNotNull(mobileFiles) else null",
            "withContext(Dispatchers.Default)")
        assertBefore(start, "created = RpcLabOwnedRuntime(runtime, files)",
            "runtimeOwner.retain(creation, checkNotNull(created))")
        assertBefore(start, "runtimeOwner.retain(creation, checkNotNull(created))", "if (foreground)")
        val finalizer = start.substringAfter("} finally {")
        assertTrue(finalizer.contains("withContext(NonCancellable)"))
        assertBefore(finalizer, "runtimeOwner.retire(creation) { it.close() }",
            "runtimeOwner.finishCreation(creation)")
        val stop = source.substringAfter("private fun stop(").substringBefore("private fun call(")
        assertBefore(stop, "pendingOwner: RpcLabRuntimeOwner.Snapshot<RpcLabOwnedRuntime>? = runtimeOwner.snapshot()",
            "previousAction?.cancel()")
        assertTrue(stop.contains("pendingOwner?.creator?.takeIf { it !== previousAction }?.cancel()"))
        assertBefore(stop, "runtimeOwner.awaitCreation(pendingOwner)", "runtimeOwner.current(it.token)")
        assertBefore(stop, "runtimeOwner.awaitCreation(pendingOwner)", "runtimeOwner.retire(pendingOwner.token)")
        assertBefore(stop, "runtimeOwner.retire(pendingOwner.token)",
            "if (pendingOwner == null || lab === owned?.lab) lab = null")
        assertTrue(stop.contains("runtimeOwner.current(it.token) ?: it.current"))
        assertFalse(stop.contains("val owned = lab"))
        assertFalse(stop.contains("mobileFiles"))
        val buttons = source.substringAfter("private fun Controls()")
        assertTrue(buttons.contains("val ownership by runtimeOwner.state.collectAsState()"))
        assertTrue(buttons.contains("val hasOwner = ownership != null"))
        assertEquals(4, Regex("enabled = !busy && !hasOwner").findAll(buttons).count())
        assertTrue(buttons.contains("enabled = !closing && hasOwner"))
        val clear = buttons.substringBefore("Text(\"Clear loaded session; preserve its evidence files\")")
            .substringAfterLast("Button({")
        assertBefore(clear, "if (busy || runtimeOwner.occupied) return@Button", "mobileConfig = null")
        assertBefore(clear, "if (busy || runtimeOwner.occupied) return@Button", "mobileFiles = null")
    }

    @Test
    fun actualBoundRuntimeDrainsOriginalMonitorAndPublishesOriginalReceiptWithoutActivityCleanupData() {
        val source = debugSource("RpcLabOwnedRuntime")
        assertTrue(source.contains("internal object RpcLabProcessRuntime"))
        assertTrue(source.contains("val owner = RpcLabRuntimeOwner<RpcLabOwnedRuntime>()"))
        assertTrue(source.contains("val lab: RpcPhoneLab, val mobileFiles: AndroidRpcCapacityFiles?"))
        val close = source.substringAfter("suspend fun close()")
            .substringBefore("/** Debug-lab-only process gate")
        assertBefore(close, "monitor?.cancelAndJoin()", "lab.close()")
        assertBefore(close, "lab.close()", "val files = mobileFiles ?: return")
        assertBefore(close, "lab.close()", "lab.mobileClosedRecord(!mobileFailed && mobileStopRequested)")
        assertBefore(close, "lab.mobileClosedRecord(", "files.read(\"closed.txt\", optional = true)")
        assertTrue(close.contains("else check(existing == receipt)"))
        assertFalse(close.contains("Activity"))
        val monitor = debugSource("RpcLabActivity").substringAfter("private fun monitorMobile(")
            .substringBefore("private fun stop(")
        assertBefore(monitor, "ui.launch(start = CoroutineStart.LAZY)", "owned.bindMonitor(monitor)")
        assertBefore(monitor, "owned.bindMonitor(monitor)", "monitor.start()")
        assertTrue(monitor.contains("val files = checkNotNull(owned.mobileFiles)"))
        assertTrue(monitor.contains("owned.approveMobileStop()"))
        assertTrue(monitor.contains("owned.failMobile()"))
        assertEquals(2, Regex(Regex.escape("stop(runtimeOwner.snapshotFor(token))")).findAll(monitor).count())
    }
}
