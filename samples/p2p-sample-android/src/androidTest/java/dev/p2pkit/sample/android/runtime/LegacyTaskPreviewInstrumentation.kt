package dev.p2pkit.sample.android.runtime

import android.accessibilityservice.AccessibilityService
import android.accessibilityservice.AccessibilityServiceInfo
import android.annotation.SuppressLint
import android.app.Activity
import android.app.ActivityManager
import android.app.Application
import android.app.Instrumentation
import android.app.KeyguardManager
import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.graphics.Bitmap
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Paint
import android.graphics.Rect
import android.os.Build
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.os.PowerManager
import android.os.Process
import android.os.SystemClock
import android.view.View
import android.view.WindowManager
import android.view.accessibility.AccessibilityNodeInfo
import android.view.accessibility.AccessibilityWindowInfo
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import dev.p2pkit.core.BuildInfo
import dev.p2pkit.sample.android.MainActivity
import dev.p2pkit.sample.android.P2pKitViewModel
import dev.p2pkit.sample.android.secureLegacyTaskWindow
import java.io.File
import java.util.concurrent.CopyOnWriteArrayList
import java.util.concurrent.FutureTask
import java.util.concurrent.TimeUnit
import kotlinx.coroutines.Job
import org.json.JSONArray
import org.json.JSONObject

/** Synthetic window-policy witness only; never enters provisioning, RPC or an actual credential. */
class LegacyTaskPreviewInstrumentation : Instrumentation() {
    private lateinit var args: Bundle
    private val report = JSONObject()
    private val captures = JSONArray()
    private val captureAttempts = JSONArray()
    private val navigationRequests = JSONArray()
    private val appObservations = mutableMapOf<String, LegacyCaptureObservation>()
    private val events = CopyOnWriteArrayList<JSONObject>()
    private val created = CopyOnWriteArrayList<MainActivity>()
    private val stopped = CopyOnWriteArrayList<MainActivity>()
    private var app: Application? = null
    private var model: P2pKitViewModel? = null
    private var output: File? = null
    private var stage = "admission"
    private var deadline = 0L
    private var token = ""
    private var recentsProvider = ""
    private var recentsCloseAction = 0
    private var publicAppLabel = ""
    private var observerFlags: LegacyInteractiveWindowFlags? = null
    private val observerReceipt = JSONObject()

    override fun onCreate(arguments: Bundle?) {
        super.onCreate(arguments)
        args = Bundle(arguments ?: Bundle())
        start()
    }

    override fun onStart() {
        super.onStart()
        val result = Bundle()
        var failure: Throwable? = null
        try {
            exercise()
        } catch (error: Throwable) {
            failure = error
            val diagnostic = JSONObject().put("stage", stage).put("type", error.javaClass.name)
            (error as? LegacyCaptureFailure)?.let { diagnostic.put("code", it.code.name) }
            if (deadline > 0) diagnostic.put("bodyRemainingMillis", deadline - SystemClock.elapsedRealtime())
            report.put("failure", diagnostic)
            try { retainFailureScene(error) }
            catch (secondary: Throwable) {
                // Even a diagnostic bookkeeping error must not escape or replace the original failure.
                try { report.put("failureSceneErrorType", secondary.javaClass.name) } catch (_: Throwable) { }
            }
        } finally {
            try {
                main {
                    created.filterNot { it.isDestroyed }.forEach {
                        // Restore protection even if the deliberately unprotected control failed.
                        secureLegacyTaskWindow(it.window)
                        it.finish()
                    }
                }
                await { main { created.all { it.isDestroyed } } }
                await { main { model?.viewModelScope?.coroutineContext?.get(Job)?.isCompleted != false } }
                app?.let { application -> main { application.unregisterActivityLifecycleCallbacks(lifecycle) } }
                report.put("cleanup", "OWNED_ACTIVITIES_DESTROYED")
            } catch (error: Throwable) {
                report.put("cleanupFailureType", error.javaClass.name)
                if (failure == null) failure = error
            }
            try {
                observerFlags?.let {
                    observerReceipt.put("operation", "RESTORE_FLAGS")
                    observerReceipt.put("restored", it.restore()).put("operation", "RESTORED")
                }
            } catch (error: Throwable) {
                report.put("observerCleanupFailureType", error.javaClass.name)
                if (failure == null) failure = error
            }
            val outcome = if (failure == null) "HARNESS_PASS_PENDING_REVIEW" else "FAIL"
            report.put("outcome", outcome).put("captures", captures).put("captureAttempts", captureAttempts)
                .put("lifecycle", JSONArray(events)).put("navigationRequests", navigationRequests)
                .put("recentsReviewRequired", true)
                .put("scope", "API24/32 synthetic content in real MainActivity; not natural credential/RPC flow")
            try {
                output?.resolve("result.json")?.writeText(report.toString(2) + "\n")
            } catch (error: Throwable) {
                if (failure == null) failure = error
                result.putString("p2pkitRetention", "FAIL")
            }
            result.putString("p2pkitToken", token)
            result.putString("p2pkitEvidence", "no_backup/ui-479-$token")
            result.putString("p2pkitOutcome", if (failure == null) outcome else "FAIL")
            result.putString("p2pkitCompleted", "1")
            result.putString("class", javaClass.name)
            result.putString("test", "legacyTaskPreviewPolicy")
            result.putInt("numtests", 1)
            result.putInt("current", 1)
            sendStatus(if (failure == null) 0 else -2, Bundle(result))
            finish(if (failure == null) Activity.RESULT_OK else Activity.RESULT_CANCELED, result)
        }
    }

    @SuppressLint("DiscouragedApi") // Read the actual system provider action resource; never guess its numeric ID.
    private fun exercise() {
        check(args.keySet() == setOf("case", "token", "sourceCommit", "sourceTree"))
        check(args.getString("case") == "479")
        token = checkNotNull(args.getString("token")).also { check(it.matches(Regex("[0-9a-f]{32}"))) }
        val source = checkNotNull(args.getString("sourceCommit"))
        val tree = checkNotNull(args.getString("sourceTree"))
        check(source.matches(Regex("[0-9a-f]{40}")) && tree.matches(Regex("[0-9a-f]{40}")))
        check(Build.VERSION.SDK_INT in setOf(24, 32))
        check(BuildInfo.COMMIT == source && !BuildInfo.DIRTY)
        val application = targetContext.applicationContext as Application
        check(application.packageName == "dev.p2pkit.sample.android")
        app = application
        val parent = application.noBackupFilesDir.canonicalFile
        output = File(parent, "ui-479-$token").also {
            check(!it.exists() && it.mkdir() && it.canonicalFile.parentFile == parent)
        }
        report.put("case", "479").put("token", token).put("sourceCommit", source).put("declaredSourceTree", tree)
            .put("sourceBinding", "host must bind clean checkout/tree, installed APK hashes and original run")
            .put("api", Build.VERSION.SDK_INT).put("fingerprint", Build.FINGERPRINT).put("pid", Process.myPid())
            .put("targetSdk", application.applicationInfo.targetSdkVersion)
            .put("syntheticOnly", true).put("captureObservationSchema", 5).put("bodyObservationBudgetMillis", 90_000)
            .put("perMainCallAndAwaitMillis", 5_000)
        deadline = SystemClock.elapsedRealtime() + 90_000
        stage = "observer-flags-admission"
        report.put("interactiveWindowObserver", observerReceipt)
        observerFlags = LegacyInteractiveWindowFlags(
            read = { uiAutomation.serviceInfo.flags },
            write = { flags -> uiAutomation.serviceInfo = uiAutomation.serviceInfo.also { it.flags = flags } },
            requiredFlag = AccessibilityServiceInfo.FLAG_RETRIEVE_INTERACTIVE_WINDOWS,
        )
        checkNotNull(observerFlags).let {
            observerReceipt.put("original", it.original).put("requested", it.requested).put("operation", "SET_FLAGS")
            observerReceipt.put("readback", it.enable()).put("operation", "ADMITTED")
        }
        stage = "real-activity-launch-request"
        main {
            application.registerActivityLifecycleCallbacks(lifecycle)
            application.startActivity(
                Intent(application, MainActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            )
        }
        stage = "real-activity-launch-focus"
        await { main {
            // Diagnostic-only: these booleans do not change the original short-circuit focus predicate.
            val snapshot = JSONObject().put("createdCount", created.size)
                .put("focusedCount", created.count { it.hasWindowFocus() })
                .put("destroyedCount", created.count { it.isDestroyed })
                .put("elapsedMillis", SystemClock.elapsedRealtime())
                .put("bodyRemainingMillis", deadline - SystemClock.elapsedRealtime())
                .put("isInteractive", (application.getSystemService(Context.POWER_SERVICE) as PowerManager)
                    .isInteractive)
                .put("keyguardLocked", (application.getSystemService(Context.KEYGUARD_SERVICE) as KeyguardManager)
                    .isKeyguardLocked)
            report.put("launchFocusObservation", snapshot)
            created.size == 1 && created.single().hasWindowFocus()
        } }
        val first = created.single()
        stage = "real-activity-launch-secure"
        check(main { secure(first) })
        stage = "real-activity-launch-admission"
        model = main { ViewModelProvider(first)[P2pKitViewModel::class.java].also {
            val admitted = it.currentRunAdmission().canRunKmpSmoke
            report.put("launchModelAdmitted", admitted)
            check(admitted)
        } }
        val firstTask = main { first.taskId }
        stage = "real-activity-launch-mount"
        val pattern = mount(first)
        stage = "initial-secure-foreground"
        capture(stage, first, pattern, false)

        stage = "home-request"
        navigate(LegacyNavigationAction.HOME)
        stage = "home-stopped"
        await { main { first in stopped && !first.hasWindowFocus() } }
        stage = "home-secure"
        check(main { secure(first) })
        stage = "recents-observer-admission"
        val requiredFlags = AccessibilityServiceInfo.FLAG_INCLUDE_NOT_IMPORTANT_VIEWS or
            AccessibilityServiceInfo.FLAG_REPORT_VIEW_IDS
        val serviceFlags = uiAutomation.serviceInfo.flags
        check(serviceFlags and requiredFlags == requiredFlags)
        publicAppLabel = application.applicationInfo.loadLabel(application.packageManager).toString()
        check(publicAppLabel == "P2pKit Sample")
        recentsProvider = if (Build.VERSION.SDK_INT == 24) "com.android.systemui"
            else "com.google.android.apps.nexuslauncher"
        if (Build.VERSION.SDK_INT == 32) {
            val lookup = JSONObject().put("operation", "PACKAGE_INFO")
            report.put("recentsProviderLookup", lookup)
            @Suppress("DEPRECATION") // API24-compatible overload; exact single debug visibility declaration.
            val providerInfo = application.packageManager.getApplicationInfo(recentsProvider, 0)
            check(providerInfo.packageName == recentsProvider && providerInfo.uid != Process.myUid())
            lookup.put("packageMatches", true).put("distinctUid", true).put("operation", "PACKAGE_RESOURCES")
            val resources = application.packageManager.getResourcesForApplication(providerInfo)
            lookup.put("operation", "ACTION_RESOURCE")
            recentsCloseAction = resources.getIdentifier("accessibility_close", "string", recentsProvider)
            check(recentsCloseAction != 0)
            lookup.put("operation", "COMPLETE")
        }
        report.put("recentsObserver", JSONObject().put("provider", recentsProvider)
            .put("publicAppLabel", publicAppLabel).put("requiredFlagsPresent", true).put("serviceFlags", serviceFlags)
            .put("closeActionId", recentsCloseAction).put("maxNodes", 256).put("maxDepth", 24))
        stage = "recents-request"
        navigate(LegacyNavigationAction.RECENTS)
        stage = "actual-recents-original"
        // Capture the actual system window, not a fabricated task bitmap. Its task-card identity and
        // absence of the synthetic phrase/pattern must also be independently reviewed in the original PNG.
        capture(stage, null, null, null)
        report.put("taskId", firstTask)

        stage = "same-task-reentry"
        main {
            val manager = application.getSystemService(Context.ACTIVITY_SERVICE) as ActivityManager
            @Suppress("DEPRECATION") // RecentTaskInfo.id is the public API24-compatible field.
            val task = manager.appTasks.single { it.taskInfo?.id == firstTask }
            task.moveToFront()
        }
        await { main { first.hasWindowFocus() && created.size == 1 } }
        check(main { secure(first) && first.taskId == firstTask })
        capture(stage, first, pattern, false)

        stage = "real-activity-recreation"
        main { first.recreate() }
        await { main { created.size == 2 && first.isDestroyed && created.last().hasWindowFocus() } }
        val replacement = created.last()
        check(main { secure(replacement) && replacement.taskId == firstTask })
        val replacementPattern = mount(replacement)
        capture(stage, replacement, replacementPattern, false)

        // Run this control LAST so the Recents/reentry originals above have never been exposed to
        // an unprotected window. Only this synthetic replacement-view content may be captured.
        stage = "synthetic-unprotected-positive-control"
        main { replacement.window.clearFlags(WindowManager.LayoutParams.FLAG_SECURE) }
        capture(stage, replacement, replacementPattern, true)
        stage = "reapplied-production-secure-policy"
        main { secureLegacyTaskWindow(replacement.window) }
        capture(stage, replacement, replacementPattern, false)
        stage = "synthetic-unprotected-closing-control"
        try {
            main { replacement.window.clearFlags(WindowManager.LayoutParams.FLAG_SECURE) }
            capture(stage, replacement, replacementPattern, true)
        } finally { main { secureLegacyTaskWindow(replacement.window) } }
        checkLegacyCaptureBracket(
            appObservations.getValue("synthetic-unprotected-positive-control"),
            appObservations.getValue("reapplied-production-secure-policy"),
            appObservations.getValue("synthetic-unprotected-closing-control"),
        )
        check(captures.length() == 7 && appObservations.size == 6)
        check(SystemClock.elapsedRealtime() <= deadline)
    }

    private fun mount(activity: MainActivity): PatternView {
        val view = main { PatternView(activity, "SYNTHETIC PREVIEW ${token.take(8)}").also(activity::setContentView) }
        await { main { view.isAttachedToWindow && view.hasWindowFocus() && view.draws > 0 } }
        return view
    }

    private data class AppCaptureSample(val state: LegacyCaptureState, val root: JSONObject)

    /** The ID comes from the actual owned View, not a guessed first window or a fabricated node. */
    private fun appCaptureSample(
        activity: MainActivity, view: PatternView, visible: Boolean, diagnostic: JSONObject? = null,
        guard: (String) -> Unit,
    ): AppCaptureSample? {
        fun pending(reason: String): AppCaptureSample? { guard(reason); return null }
        val state = captureState(activity, view)
        checkLegacyCaptureState(state, secure = !visible)
        val owned = main {
            val node = view.createAccessibilityNodeInfo()
            try {
                val bounds = Rect().also(node::getBoundsInScreen)
                Triple(node.windowId, bounds, node.packageName?.toString() == targetContext.packageName)
            } finally { @Suppress("DEPRECATION") node.recycle() }
        }
        checkLegacyCapture(owned.third, LegacyCaptureFailureCode.CAPTURE_STATE_INVALID)
        val root = uiAutomation.rootInActiveWindow
        diagnostic?.put("rootAvailable", root != null)
        if (root == null) return pending("ROOT_MISSING")
        try {
            val refreshed = root.refresh()
            diagnostic?.put("refreshed", refreshed)
            if (!refreshed) return pending("ROOT_REFRESH_FAILED")
            // Same refreshed root, no extra query or arbitrary system text; do not erase a failed after sample.
            diagnostic?.put("windowId", root.windowId)?.put("idMatchesActualView", root.windowId == owned.first)
                ?.put("packageMatchesTarget", root.packageName?.toString() == targetContext.packageName)
                ?.put("visible", root.isVisibleToUser)?.put("bounds", Rect().also(root::getBoundsInScreen).let {
                    JSONArray(listOf(it.left, it.top, it.right, it.bottom))
                })
            if (!root.isVisibleToUser) return pending("ROOT_NOT_VISIBLE")
            if (root.windowId < 0 || root.windowId != owned.first) return pending("ROOT_WINDOW_MISMATCH")
            if (root.packageName?.toString() != targetContext.packageName) return pending("ROOT_PACKAGE_MISMATCH")
            val bounds = Rect().also(root::getBoundsInScreen)
            val viewBounds = owned.second
            if (viewBounds.width() != state.width || viewBounds.height() != state.height ||
                !bounds.contains(viewBounds) || state.points.any { (x, y) -> !viewBounds.contains(x, y) }) {
                return pending("ROOT_GEOMETRY_MISMATCH")
            }
            val window = interactiveWindow(root.windowId, viewBounds, state.points)
                ?: return pending("INTERACTIVE_WINDOW_NOT_READY")
            diagnostic?.put("interactiveWindow", JSONObject().put("windowId", window.id).put("type", window.type)
                .put("active", window.active).put("focused", window.focused).put("bounds", JSONArray(window.bounds)))
            guard("READY")
            return AppCaptureSample(state, JSONObject().put("windowId", root.windowId)
                .put("package", targetContext.packageName)
                .put("bounds", JSONArray(listOf(bounds.left, bounds.top, bounds.right, bounds.bottom)))
                .put("viewBounds", JSONArray(listOf(viewBounds.left, viewBounds.top,
                    viewBounds.right, viewBounds.bottom)))
                .put("interactiveWindow", JSONObject().put("windowId", window.id).put("type", window.type)
                    .put("active", window.active).put("focused", window.focused).put("uniqueMatch", true)
                    .put("bounds", JSONArray(window.bounds))))
        } finally { @Suppress("DEPRECATION") root.recycle() }
    }

    private fun interactiveWindow(id: Int, view: Rect, points: List<Pair<Int, Int>>): LegacyInteractiveWindow? {
        val windows = uiAutomation.windows
        try {
            checkLegacyCapture(windows.size <= 256, LegacyCaptureFailureCode.INTERACTIVE_WINDOW_LIMIT_EXCEEDED)
            val observations = windows.map { window ->
                val bounds = Rect().also(window::getBoundsInScreen)
                LegacyInteractiveWindow(window.id, window.type, window.isActive, window.isFocused,
                    listOf(bounds.left, bounds.top, bounds.right, bounds.bottom))
            }
            return findLegacyInteractiveWindow(observations, id, AccessibilityWindowInfo.TYPE_APPLICATION,
                listOf(view.left, view.top, view.right, view.bottom), points)
        } finally {
            @Suppress("DEPRECATION") // API24-compatible owned AccessibilityWindowInfo instances.
            windows.forEach { it.recycle() }
        }
    }

    private fun sameAppCapture(first: AppCaptureSample, second: AppCaptureSample): Boolean =
        first.state.copy(draws = second.state.draws) == second.state && first.root.toString() == second.root.toString()

    private fun admittedAppCapture(
        activity: MainActivity, view: PatternView, visible: Boolean, attempt: JSONObject,
    ): AppCaptureSample {
        val start = SystemClock.elapsedRealtime()
        val until = minOf(deadline, start + 5_000)
        val receipt = JSONObject().put("startedElapsedMillis", start).put("deadlineElapsedMillis", until)
            .put("budgetMillis", 5_000).put("operation", "ACTIVE_OWNED_ROOT")
        attempt.put("presentation", receipt)
        fun bounded() = checkLegacyCapture(SystemClock.elapsedRealtime() <= until,
            LegacyCaptureFailureCode.PRESENTATION_ADMISSION_TIMEOUT)
        bounded()
        checkLegacyCaptureState(captureState(activity, view), secure = !visible)
        receipt.put("operation", "ACCESSIBILITY_EVENT_IDLE")
        val idle = JSONObject().put("quietMillis", 500)
        receipt.put("eventIdle", idle)
        val idleCompleted = awaitLegacyAccessibilityIdle(until, SystemClock::elapsedRealtime) { started, maximumWait ->
            idle.put("startedElapsedMillis", started).put("maximumWaitMillis", maximumWait)
            uiAutomation.waitForIdle(500, maximumWait)
            idle.put("returned", true)
        }
        idle.put("completedElapsedMillis", idleCompleted)
        receipt.put("operation", "ACTIVE_OWNED_ROOT")
        var baseline: AppCaptureSample
        while (true) {
            bounded()
            val sample = appCaptureSample(activity, view, visible) { receipt.put("lastRootGuard", it) }
            bounded()
            if (sample != null) { baseline = sample; break }
            Thread.sleep(20)
        }
        receipt.put("root", baseline.root).put("baselineDraws", baseline.state.draws)
        var invalidatedNano = 0L
        var polls = 0
        return awaitLegacyPresentation(until, SystemClock::elapsedRealtime,
            clear = {
                receipt.put("operation", "CLEAR_FRAME_STATS")
                uiAutomation.clearWindowContentFrameStats(baseline.root.getInt("windowId")).also {
                    receipt.put("clearReturned", it)
                }
            },
            redraw = {
                receipt.put("operation", "INVALIDATE_ONCE")
                main {
                    bounded()
                    checkLegacyCapture(!activity.isDestroyed && view.isAttachedToWindow &&
                        activity.hasWindowFocus() && view.hasWindowFocus() && secure(activity) == !visible,
                        LegacyCaptureFailureCode.CAPTURE_STATE_INVALID)
                    invalidatedNano = System.nanoTime()
                    view.invalidate()
                }
                receipt.put("invalidatedNano", invalidatedNano)
            },
            observe = {
                receipt.put("operation", "OBSERVE_PRESENTATION").put("polls", ++polls)
                val sample = requireLegacyCaptureValue(appCaptureSample(activity, view, visible) {
                    receipt.put("lastRootGuard", it)
                },
                    LegacyCaptureFailureCode.CAPTURE_STATE_INVALID)
                checkLegacyCapture(sameAppCapture(baseline, sample), LegacyCaptureFailureCode.CAPTURE_STATE_INVALID)
                val stats = requireLegacyCaptureValue(
                    uiAutomation.getWindowContentFrameStats(baseline.root.getInt("windowId")),
                    LegacyCaptureFailureCode.PRESENTATION_STATS_UNAVAILABLE)
                val queriedNano = System.nanoTime()
                checkLegacyCapture(stats.frameCount in 0..1024,
                    LegacyCaptureFailureCode.PRESENTATION_FRAME_LIMIT_EXCEEDED)
                val frames = (0 until stats.frameCount).map { index -> LegacyPresentedFrame(index,
                    stats.getFramePostedTimeNano(index), stats.getFrameReadyTimeNano(index),
                    stats.getFramePresentedTimeNano(index)) }
                val frame = findLegacyPresentedFrame(frames, invalidatedNano, queriedNano)
                receipt.put("frameCount", stats.frameCount).put("observedDraws", sample.state.draws)
                    .put("queriedNano", queriedNano)
                if (frame == null || sample.state.draws <= baseline.state.draws) null else {
                    bounded()
                    receipt.put("frameIndex", frame.index).put("postedNano", frame.posted)
                        .put("readyNano", frame.ready).put("presentedNano", frame.presented)
                        .put("operation", "READY").put("completedElapsedMillis", SystemClock.elapsedRealtime())
                    sample
                }
            }, pause = { Thread.sleep(20) })
    }

    private fun capture(name: String, activity: MainActivity?, view: PatternView?, visible: Boolean?) {
        // UNAVAILABLE is a provisional protected observation, never a unique denial or standalone PASS.
        // Actual Recents and both late positives still require original global pixels and independent review.
        val attempt = JSONObject().put("name", name).put("elapsedMillis", SystemClock.elapsedRealtime())
            .put("bodyRemainingMillis", deadline - SystemClock.elapsedRealtime()).put("operation", "BODY_DEADLINE")
        captureAttempts.put(attempt)
        checkLegacyCapture(SystemClock.elapsedRealtime() <= deadline, LegacyCaptureFailureCode.BODY_DEADLINE_EXCEEDED)
        attempt.put("operation", "SAMPLE_GEOMETRY")
        val appBefore = view?.let { admittedAppCapture(checkNotNull(activity), it, checkNotNull(visible), attempt) }
        val before = appBefore?.state
        before?.let {
            attempt.put("stateBefore", stateJson(it))
            checkLegacyCaptureState(it, secure = !checkNotNull(visible))
        }
        val systemBefore = if (view == null) admittedRecentsState(attempt) else null
        systemBefore?.let { attempt.put("systemWindowBefore", it) }
        checkLegacyCapture(SystemClock.elapsedRealtime() <= deadline, LegacyCaptureFailureCode.BODY_DEADLINE_EXCEEDED)
        attempt.put("operation", "GLOBAL_SCREENSHOT_REQUEST")
        val bitmap = uiAutomation.takeScreenshot()
        try {
            attempt.put("screenshotReturned", true).put("screenshotAvailable", bitmap != null)
            val afterRoot = JSONObject()
            if (view != null) attempt.put("afterRootObservation", afterRoot)
            val appAfter = view?.let { requireLegacyCaptureValue(
                appCaptureSample(checkNotNull(activity), it, checkNotNull(visible), afterRoot) { guard ->
                    attempt.put("activeRootAfterGuard", guard)
                },
                LegacyCaptureFailureCode.CAPTURE_STATE_INVALID) }
            if (appBefore != null) checkLegacyCapture(sameAppCapture(appBefore, checkNotNull(appAfter)),
                LegacyCaptureFailureCode.CAPTURE_STATE_INVALID)
            val after = appAfter?.state
            after?.let { attempt.put("stateAfter", stateJson(it)) }
            appAfter?.let { attempt.put("activeRootAfter", it.root) }
            val systemAfter = if (view == null) requireLegacyCaptureValue(
                recentsState(minOf(deadline, SystemClock.elapsedRealtime() + 5_000)) {
                    attempt.put("recentsAfterRootGuard", it.name)
                }, LegacyCaptureFailureCode.CAPTURE_STATE_INVALID,
            ) else null
            if (systemBefore != null) {
                attempt.put("systemWindowAfter", systemAfter)
                checkLegacyCapture(systemBefore.toString() == systemAfter?.toString(),
                    LegacyCaptureFailureCode.CAPTURE_STATE_INVALID)
            }
            val record = JSONObject().put("name", name).put("elapsedMillis", SystemClock.elapsedRealtime())
            if (before != null) record.put("stateBefore", stateJson(before))
                .put("stateAfter", stateJson(checkNotNull(after)))
                .put("presentation", attempt.getJSONObject("presentation"))
                .put("activeRootAfter", checkNotNull(appAfter).root)
            if (systemBefore != null) record.put("systemWindowBefore", systemBefore)
                .put("systemWindowAfter", systemAfter)
            if (bitmap == null) {
                // Null Recents or positive controls fail. No file, dimensions or invented false pixels.
                val observation = LegacyCaptureObservation(
                    requireLegacyCaptureValue(before, LegacyCaptureFailureCode.SCREENSHOT_UNAVAILABLE),
                    checkNotNull(after), null, null,
                )
                checkLegacyCaptureObservation(observation, visible = checkNotNull(visible))
                appObservations[name] = observation
                captures.put(record.put("observation", "UNAVAILABLE"))
                attempt.put("operation", "PROTECTED_UNAVAILABLE_OBSERVED")
                return
            }
            // Hardware-backed global screenshots need owned software readback for getPixel/PNG.
            // This copies actual captured pixels; it is not a View rendering or fabricated image.
            attempt.put("operation", "BITMAP_READBACK")
            val pixels = requireLegacyCaptureValue(bitmap.copy(Bitmap.Config.ARGB_8888, false),
                LegacyCaptureFailureCode.BITMAP_COPY_UNAVAILABLE)
            try {
                checkLegacyCapture(pixels.width == bitmap.width && pixels.height == bitmap.height,
                    LegacyCaptureFailureCode.BITMAP_COPY_UNAVAILABLE)
                record.put("sourceBitmapConfig", bitmap.config?.name ?: "UNKNOWN")
                    .put("sourceBitmapWidth", bitmap.width).put("sourceBitmapHeight", bitmap.height)
                    .put("pixelReadback", "ARGB_8888_COPY")
                attempt.put("bitmapWidth", pixels.width).put("bitmapHeight", pixels.height)
                    .put("operation", "PNG_OUTPUT_OPEN")
                val directory = requireLegacyCaptureValue(output, LegacyCaptureFailureCode.OUTPUT_DIRECTORY_UNAVAILABLE)
                val file = File(directory, "$name.png")
                file.outputStream().use {
                    attempt.put("operation", "PNG_ENCODING")
                    checkLegacyCapture(pixels.compress(Bitmap.CompressFormat.PNG, 100, it),
                        LegacyCaptureFailureCode.PNG_ENCODING_FAILED)
                }
                record.put("observation", "BITMAP").put("file", file.name)
                    .put("width", pixels.width).put("height", pixels.height)
                captures.put(record)
                attempt.put("operation", "PIXEL_ORACLE")
                if (before != null) {
                    val matches = before.points.mapIndexed { index, (x, y) ->
                        checkLegacyCapture(x in 0 until pixels.width && y in 0 until pixels.height,
                            LegacyCaptureFailureCode.SAMPLE_OUTSIDE_SCREENSHOT)
                        pixels.getPixel(x, y) == PATTERN_COLORS[index]
                    }
                    val observation = LegacyCaptureObservation(before, checkNotNull(after),
                        pixels.width to pixels.height, matches)
                    record.put("sampleMatches", JSONArray(matches))
                    checkLegacyCaptureObservation(observation, visible = checkNotNull(visible))
                    appObservations[name] = observation
                } else {
                    val firstPixel = pixels.getPixel(0, 0)
                    val varied = (0 until 8).any { y -> (0 until 8).any { x ->
                        pixels.getPixel(x * (pixels.width - 1) / 7, y * (pixels.height - 1) / 7) != firstPixel
                    } }
                    record.put("pixelVariation", varied)
                    checkLegacyCapture(varied, LegacyCaptureFailureCode.RECENTS_IMAGE_UNIFORM)
                }
                attempt.put("operation", "COMPLETE")
            } finally { if (pixels !== bitmap) pixels.recycle() }
        } finally { bitmap?.recycle() }
    }

    /** Private failure evidence only. Never adds an acceptance capture or replaces the first failure. */
    private fun retainFailureScene(primary: Throwable) {
        val completed = (0 until captures.length()).map { captures.getJSONObject(it).getString("name") }
        val requested = (0 until captureAttempts.length()).any { index ->
            val attempt = captureAttempts.getJSONObject(index)
            attempt.optString("name") == "actual-recents-original" &&
                (attempt.optString("operation") == "GLOBAL_SCREENSHOT_REQUEST" || attempt.has("screenshotReturned"))
        }
        if (!needsLegacyFailureScene(Build.VERSION.SDK_INT, stage, primary, completed, requested)) return
        val started = SystemClock.elapsedRealtime()
        val until = minOf(deadline, started + 5_000)
        val receipt = JSONObject().put("purpose", "NOT_ACCEPTANCE").put("api", 32)
            .put("triggerStage", stage).put("triggerCode", (primary as LegacyCaptureFailure).code.name)
            .put("primaryFailurePreserved", true).put("startedElapsedMillis", started)
            .put("deadlineElapsedMillis", until).put("budgetMillis", 5_000).put("operation", "OWNER_BEFORE")
            .put("lastCompletedAttempt", report.optJSONObject("recentsAdmission")?.optInt("lastCompletedAttempt"))
        report.put("failureScene", receipt)
        var pending: File? = null
        var published: File? = null
        var stateCount = 0
        fun bounded() = checkLegacyCapture(SystemClock.elapsedRealtime() < until,
            LegacyCaptureFailureCode.BODY_DEADLINE_EXCEEDED)
        try {
            captureLegacyFailureScene(until, SystemClock::elapsedRealtime, state = {
                receipt.put("operation", if (stateCount == 0) "OWNER_BEFORE" else "OWNER_AFTER")
                val observed = JSONObject()
                receipt.put(if (stateCount++ == 0) "stateBefore" else "stateAfter", observed)
                failureSceneState(until, observed).toString()
            }, screenshot = {
                receipt.put("operation", "DIAGNOSTIC_SCREENSHOT_REQUEST")
                    .put("requestedElapsedMillis", SystemClock.elapsedRealtime())
                val bitmap = uiAutomation.takeScreenshot()
                try {
                    receipt.put("screenshotReturned", true).put("screenshotAvailable", bitmap != null)
                        .put("returnedElapsedMillis", SystemClock.elapsedRealtime())
                    bitmap
                } catch (error: Throwable) { bitmap?.recycle(); throw error }
            }, retain = { bitmap ->
                receipt.put("operation", "BITMAP_COPY")
                val pixels = requireLegacyCaptureValue(bitmap.copy(Bitmap.Config.ARGB_8888, false),
                    LegacyCaptureFailureCode.BITMAP_COPY_UNAVAILABLE)
                try {
                    bounded()
                    checkLegacyCapture(pixels.width == bitmap.width && pixels.height == bitmap.height &&
                        pixels.width > 0 && pixels.height > 0, LegacyCaptureFailureCode.BITMAP_COPY_UNAVAILABLE)
                    receipt.put("sourceBitmapConfig", bitmap.config?.name ?: "UNKNOWN")
                        .put("width", pixels.width).put("height", pixels.height).put("pixelReadback", "ARGB_8888_COPY")
                    val directory = requireLegacyCaptureValue(output,
                        LegacyCaptureFailureCode.OUTPUT_DIRECTORY_UNAVAILABLE)
                    val file = File(directory, "failure-recents-scene.part")
                    bounded()
                    check(file.createNewFile())
                    pending = file // Only this newly created private file is ever removed on failure.
                    receipt.put("operation", "PNG_ENCODING")
                    file.outputStream().use {
                        bounded()
                        checkLegacyCapture(pixels.compress(Bitmap.CompressFormat.PNG, 100, it),
                            LegacyCaptureFailureCode.PNG_ENCODING_FAILED)
                    }
                    bounded()
                } finally { if (pixels !== bitmap) pixels.recycle() }
            }, recycle = Bitmap::recycle)
            bounded()
            val file = checkNotNull(pending)
            val destination = File(file.parentFile, "failure-recents-scene.png")
            check(!destination.exists() && file.renameTo(destination))
            published = destination
            bounded()
            receipt.put("file", destination.name).put("operation", "DIAGNOSTIC_RETAINED")
                .put("completedElapsedMillis", SystemClock.elapsedRealtime())
        } catch (secondary: Throwable) {
            receipt.remove("file")
            receipt.put("failedOperation", receipt.optString("operation")).put("operation", "NOT_CAPTURED")
                .put("failureType", secondary.javaClass.name)
                .put("failedElapsedMillis", SystemClock.elapsedRealtime())
            (secondary as? LegacyCaptureFailure)?.let { receipt.put("failureCode", it.code.name) }
            receipt.put("partialOutputRemoved", listOfNotNull(pending, published).all { !it.exists() || it.delete() })
        }
    }

    /** One fresh root and actual owned task per side; no task-card matching, polling or arbitrary text. */
    private fun failureSceneState(until: Long, observed: JSONObject): JSONObject {
        fun bounded() = checkLegacyCapture(SystemClock.elapsedRealtime() < until,
            LegacyCaptureFailureCode.BODY_DEADLINE_EXCEEDED)
        bounded()
        val expected = captures.getJSONObject(0).getJSONObject("stateBefore")
        val first = created.single()
        val task = FutureTask {
            check(first.taskId == expected.getInt("taskId") &&
                System.identityHashCode(first) == expected.getInt("activity") && !first.isDestroyed &&
                first in stopped && !first.hasWindowFocus() && secure(first))
            val manager = targetContext.getSystemService(Context.ACTIVITY_SERVICE) as ActivityManager
            val tasks = manager.appTasks
            val info = checkNotNull(tasks.single().taskInfo)
            val component = ComponentName(targetContext, MainActivity::class.java)
            @Suppress("DEPRECATION") // Same API24-compatible original app-task identity; diagnostic is API32 only.
            check(info.id == first.taskId && info.baseActivity == component && info.topActivity == component)
            JSONObject().put("activity", System.identityHashCode(first)).put("taskId", first.taskId)
                .put("secureFlag", true).put("stopped", true).put("windowFocused", false)
                .put("ownedTaskCount", tasks.size).put("baseActivityMatches", true).put("topActivityMatches", true)
        }
        val remaining = until - SystemClock.elapsedRealtime()
        checkLegacyCapture(remaining > 0, LegacyCaptureFailureCode.BODY_DEADLINE_EXCEEDED)
        check(Handler(Looper.getMainLooper()).post(task))
        val owner = try { task.get(remaining, TimeUnit.MILLISECONDS) } finally { task.cancel(false) }
        bounded()
        owner.keys().forEach { key -> observed.put(key, owner.get(key)) }
        val candidate = uiAutomation.rootInActiveWindow
        observed.put("rootAvailable", candidate != null)
        val root = requireLegacyCaptureValue(candidate, LegacyCaptureFailureCode.CAPTURE_STATE_INVALID)
        try {
            bounded()
            val refreshed = root.refresh()
            bounded()
            val rectangle = Rect().also(root::getBoundsInScreen)
            observed.put("refreshed", refreshed).put("windowId", root.windowId)
                .put("providerMatches", root.packageName?.toString() == "com.google.android.apps.nexuslauncher")
                .put("visible", root.isVisibleToUser)
                .put("bounds", JSONArray(listOf(rectangle.left, rectangle.top, rectangle.right, rectangle.bottom)))
            checkLegacyCapture(refreshed && observed.getBoolean("providerMatches") && root.isVisibleToUser &&
                root.windowId >= 0 && rectangle.width() > 0 && rectangle.height() > 0,
                LegacyCaptureFailureCode.CAPTURE_STATE_INVALID)
            bounded()
            return observed
        } finally { @Suppress("DEPRECATION") root.recycle() }
    }

    private data class EducationObservation(
        val owner: JSONObject, val popup: JSONObject?, val presence: LegacyEducationPresence, val absence: JSONObject,
    )

    private fun recentsState(
        until: Long, query: JSONObject? = null,
        educationObserver: ((EducationObservation) -> Unit)? = null,
        guard: (LegacyRecentsGuard) -> Unit,
    ): JSONObject? {
        fun pending(value: LegacyRecentsGuard): JSONObject? { guard(value); return null }
        query?.put("phase", "OWNED_TASK")
        val first = created.first()
        val owner = main {
            checkLegacyCapture(!first.isDestroyed && first in stopped && !first.hasWindowFocus() && secure(first),
                LegacyCaptureFailureCode.CAPTURE_STATE_INVALID)
            val manager = targetContext.getSystemService(Context.ACTIVITY_SERVICE) as ActivityManager
            val tasks = manager.appTasks
            val info = tasks.singleOrNull()?.taskInfo
            val component = ComponentName(targetContext, MainActivity::class.java)
            @Suppress("DEPRECATION") // Public API24 task identity, same contract as moveToFront.
            val exactTask = info != null && info.id == first.taskId &&
                info.baseActivity == component && info.topActivity == component
            checkLegacyCapture(exactTask, LegacyCaptureFailureCode.CAPTURE_STATE_INVALID)
            val label = info?.taskDescription?.label
            checkLegacyCapture(label.isNullOrEmpty() || label == publicAppLabel,
                LegacyCaptureFailureCode.CAPTURE_STATE_INVALID)
            JSONObject().put("activity", System.identityHashCode(first)).put("taskId", first.taskId)
                .put("secureFlag", true).put("stopped", true).put("windowFocused", false)
                .put("ownedTaskCount", tasks.size).put("baseActivityMatches", true).put("topActivityMatches", true)
        }
        query?.put("phase", "ACTIVE_ROOT")
        val root = uiAutomation.rootInActiveWindow ?: return pending(LegacyRecentsGuard.ROOT_MISSING)
        val nodes = mutableListOf<LegacyRecentsNode>()
        val educationNodes = mutableListOf<LegacyEducationNode>()
        var treeComplete = false
        var primaryFailure: Throwable? = null
        try {
            if (!root.refresh()) return pending(LegacyRecentsGuard.ROOT_REFRESH_FAILED)
            if (!root.isVisibleToUser) return pending(LegacyRecentsGuard.ROOT_NOT_VISIBLE)
            if (root.packageName?.toString() != recentsProvider) return pending(LegacyRecentsGuard.ROOT_PACKAGE_INVALID)
            val bounds = Rect().also(root::getBoundsInScreen)
            if (bounds.width() <= 0 || bounds.height() <= 0 || root.windowId < 0) {
                return pending(LegacyRecentsGuard.ROOT_GEOMETRY_INVALID)
            }
            query?.put("phase", "TREE_VISIT")?.put("visitedNodeCount", 0)
            var complete = true
            fun visit(node: AccessibilityNodeInfo, parent: Int?, depth: Int) {
                checkLegacyCapture(SystemClock.elapsedRealtime() <= until,
                    LegacyCaptureFailureCode.RECENTS_ADMISSION_TIMEOUT)
                checkLegacyCapture(nodes.size < 256 && depth <= 24,
                    LegacyCaptureFailureCode.RECENTS_TREE_LIMIT_EXCEEDED)
                if (parent != null && !node.refresh()) { complete = false; return }
                val rectangle = Rect().also(node::getBoundsInScreen)
                val index = nodes.size
                val kind = when (node.viewIdResourceName) {
                    "$recentsProvider:id/title" -> LegacyRecentsResource.TITLE
                    "$recentsProvider:id/task_view_bar" -> LegacyRecentsResource.HEADER
                    "$recentsProvider:id/task_view_thumbnail" -> LegacyRecentsResource.THUMBNAIL
                    "$recentsProvider:id/snapshot" -> LegacyRecentsResource.SNAPSHOT
                    else -> LegacyRecentsResource.OTHER
                }
                nodes += LegacyRecentsNode(parent, kind,
                    node.packageName?.toString() == recentsProvider && node.windowId == root.windowId,
                    node.isVisibleToUser, listOf(rectangle.left, rectangle.top, rectangle.right, rectangle.bottom),
                    node.text?.toString() == publicAppLabel, node.contentDescription?.toString() == publicAppLabel,
                    node.collectionItemInfo != null,
                    recentsCloseAction != 0 && node.actionList.any { it.id == recentsCloseAction })
                if (educationObserver != null) {
                    val resource = when (node.viewIdResourceName) {
                        "$recentsProvider:id/text" -> LegacyEducationResource.TEXT
                        "$recentsProvider:id/arrow" -> LegacyEducationResource.ARROW
                        "$recentsProvider:id/drag_layer" -> LegacyEducationResource.DRAG_LAYER
                        else -> LegacyEducationResource.OTHER
                    }
                    val kind = when (node.className?.toString()) {
                        "android.widget.TextView" -> LegacyEducationClass.TEXT_VIEW
                        "android.view.View" -> LegacyEducationClass.VIEW
                        "android.widget.LinearLayout" -> LegacyEducationClass.LINEAR_LAYOUT
                        else -> LegacyEducationClass.OTHER
                    }
                    educationNodes += LegacyEducationNode(nodes.last(), resource, kind,
                        node.text?.toString() == LEGACY_RECENTS_EDUCATION_TEXT)
                }
                query?.put("visitedNodeCount", nodes.size)
                checkLegacyCapture(node.childCount <= 256, LegacyCaptureFailureCode.RECENTS_TREE_LIMIT_EXCEEDED)
                for (childIndex in 0 until node.childCount) {
                    checkLegacyCapture(SystemClock.elapsedRealtime() <= until,
                        LegacyCaptureFailureCode.RECENTS_ADMISSION_TIMEOUT)
                    val child = node.getChild(childIndex)
                    if (child == null) { complete = false; return }
                    try { visit(child, index, depth + 1) }
                    finally { @Suppress("DEPRECATION") child.recycle() }
                    if (!complete) return
                }
            }
            visit(root, null, 0)
            checkLegacyCapture(SystemClock.elapsedRealtime() <= until,
                LegacyCaptureFailureCode.RECENTS_ADMISSION_TIMEOUT)
            treeComplete = complete
            query?.put("treeComplete", complete)?.put("phase", "CARD_SELECTION")
            if (!complete) return pending(LegacyRecentsGuard.TREE_INCOMPLETE)
            if (educationObserver != null) {
                val selection = selectLegacyRecentsEducation(educationNodes)
                val popup = selection.popup
                val absence = JSONObject().put("complete", true)
                    .put("textIds", educationNodes.count { it.resource == LegacyEducationResource.TEXT })
                    .put("arrowIds", educationNodes.count { it.resource == LegacyEducationResource.ARROW })
                    .put("exactTexts", educationNodes.count { it.exactText })
                val textMarker = educationNodes.singleOrNull { it.resource == LegacyEducationResource.TEXT }
                val arrowMarker = educationNodes.singleOrNull { it.resource == LegacyEducationResource.ARROW }
                val sameParent = textMarker?.observation?.parent != null &&
                    textMarker.observation.parent == arrowMarker?.observation?.parent
                val sharedParent = if (sameParent) educationNodes[checkNotNull(textMarker.observation.parent)]
                    else null
                val association = JSONObject().put("textMarkerUnique", textMarker != null)
                    .put("arrowMarkerUnique", arrowMarker != null).put("textExact", textMarker?.exactText == true)
                    .put("textClassMatches", textMarker?.kind == LegacyEducationClass.TEXT_VIEW)
                    .put("arrowClassMatches", arrowMarker?.kind == LegacyEducationClass.VIEW)
                    .put("sameParent", sameParent).put("sharedParentResource", sharedParent?.resource?.name ?: "NONE")
                    .put("sharedParentClass", sharedParent?.kind?.name ?: "NONE")
                query?.put("educationPredicates", JSONObject()
                    .put("complete", true).put("nodes", educationNodes.size)
                    .put("textIds", educationNodes.count { it.resource == LegacyEducationResource.TEXT })
                    .put("arrowIds", educationNodes.count { it.resource == LegacyEducationResource.ARROW })
                    .put("exactTexts", educationNodes.count { it.exactText })
                    .put("textClasses", educationNodes.count { it.kind == LegacyEducationClass.TEXT_VIEW })
                    .put("arrowClasses", educationNodes.count { it.kind == LegacyEducationClass.VIEW })
                    .put("parentClasses", educationNodes.count { it.kind == LegacyEducationClass.LINEAR_LAYOUT })
                    .put("owned", educationNodes.count { it.observation.owned })
                    .put("visible", educationNodes.count { it.observation.visible })
                    .put("rootContained", educationNodes.count {
                        val b = it.observation.bounds
                        b[0] < b[2] && b[1] < b[3] && bounds.contains(b[0], b[1], b[2], b[3])
                    }).put("knownPopup", popup != null).put("presence", selection.presence.name)
                    .put("markerAssociation", association))
                val popupJson = popup?.let {
                    JSONObject().put("parentBounds", JSONArray(nodes[it.parent].bounds))
                        .put("textBounds", JSONArray(nodes[it.text].bounds))
                        .put("arrowBounds", JSONArray(nodes[it.arrow].bounds))
                        .put("exactText", true).put("exactIds", true).put("expectedClasses", true)
                        .put("unique", true).put("rootContained", true).put("complete", true)
                        .put("parentProjection", it.projection.name)
                        .put("dragLayerResourceMatch", educationNodes[it.parent].resource ==
                            LegacyEducationResource.DRAG_LAYER)
                        .put("markerCounts", JSONObject().put("textIds", absence.getInt("textIds"))
                            .put("arrowIds", absence.getInt("arrowIds"))
                            .put("exactTexts", absence.getInt("exactTexts")))
                }
                val observedOwner = JSONObject(owner.toString()).put("package", recentsProvider)
                    .put("windowId", root.windowId)
                    .put("bounds", JSONArray(listOf(bounds.left, bounds.top, bounds.right, bounds.bottom)))
                educationObserver(EducationObservation(observedOwner, popupJson, selection.presence, absence))
                if (selection.presence != LegacyEducationPresence.ABSENT) {
                    return pending(LegacyRecentsGuard.CARD_NOT_IDENTIFIED)
                }
            }
            val card = findLegacyRecentsCard(Build.VERSION.SDK_INT, nodes)
                ?: return pending(LegacyRecentsGuard.CARD_NOT_IDENTIFIED)
            fun rectangle(index: Int) = JSONArray(nodes[index].bounds)
            val anchor = JSONObject().put("kind", if (Build.VERSION.SDK_INT == 24) "SYSTEM_UI_TASK_TITLE"
                else "QUICKSTEP_TASK_DESCRIPTION").put("exactPublicLabelMatch", true)
                .put("cardBounds", rectangle(card.card)).put("labelBounds", rectangle(card.label))
                .put("snapshotBounds", rectangle(card.snapshot)).put("uniqueStructuredCard", true)
            guard(LegacyRecentsGuard.READY)
            return owner.put("package", recentsProvider).put("windowId", root.windowId)
                .put("bounds", JSONArray(listOf(bounds.left, bounds.top, bounds.right, bounds.bottom)))
                .put("taskCard", anchor)
        } catch (error: Throwable) {
            primaryFailure = error
            throw error
        } finally {
            try {
                if (query != null) retainRecentsQuery(query, nodes, treeComplete)
            } catch (error: Throwable) {
                // Diagnostic failure cannot replace the original query/ownership/budget failure.
                if (primaryFailure == null) throw error
            } finally { @Suppress("DEPRECATION") root.recycle() }
        }
    }

    private fun retainRecentsQuery(query: JSONObject, nodes: List<LegacyRecentsNode>, complete: Boolean) {
        val summary = summarizeLegacyRecentsNodes(nodes)
        query.put("treeComplete", complete).put("predicateCounts", JSONObject(summary.counts))
            .put("candidateCount", summary.candidateCount).put("candidatesTruncated", summary.candidateCount > 16)
        query.put("candidates", JSONArray(summary.candidates.map { index ->
            val node = nodes[index]
            JSONObject().put("index", index).put("parent", node.parent ?: JSONObject.NULL)
                .put("resource", node.resource.name).put("visible", node.visible).put("owned", node.owned)
                .put("bounds", JSONArray(node.bounds)).put("labelMatches", node.labelMatches)
                .put("descriptionMatches", node.descriptionMatches).put("closeAction", node.closeAction)
                .put("taskCollectionItem", node.taskCollectionItem)
                .put("snapshotChildCount", nodes.count { it.parent == index &&
                    it.resource == LegacyRecentsResource.SNAPSHOT })
        }))
    }

    private fun admittedRecentsState(attempt: JSONObject): JSONObject {
        val started = SystemClock.elapsedRealtime()
        val until = minOf(deadline, started + 5_000)
        val admission = JSONObject().put("startedElapsedMillis", started).put("deadlineElapsedMillis", until)
            .put("budgetMillis", 5_000).put("attempts", 0).put("operation", "PENDING")
        report.put("recentsAdmission", admission)
        attempt.put("operation", "RECENTS_ROOT_ADMISSION")
        val progress = LegacyRecentsProgress()
        val dismissal = LegacyEducationDismissal()
        val education = if (Build.VERSION.SDK_INT == 32) JSONObject().put("schema", 1).put("api", 32)
            .put("operation", "OBSERVING").put("observations", 0).also { report.put("recentsEducation", it) }
            else null
        var educationObservations = 0
        val state = awaitLegacyRecentsState(until, SystemClock::elapsedRealtime, { Thread.sleep(20) }) {
            progress.begin()
            admission.put("attempts", progress.attempt).put("operation", "OBSERVING")
            val query = JSONObject().put("attempt", progress.attempt)
                .put("startedElapsedMillis", SystemClock.elapsedRealtime())
            report.put("recentsQueryCurrent", query)
            var returnedGuard: LegacyRecentsGuard? = null
            var educationObservation: EducationObservation? = null
            val educationObserver: ((EducationObservation) -> Unit)? = if (education != null) {
                { observation -> educationObservation = observation }
            } else null
            val value = recentsState(until, query, educationObserver) { returnedGuard = it }
            val guard = checkNotNull(returnedGuard)
            progress.completed(guard)
            query.put("phase", "RETURNED").put("guard", guard.name)
                .put("completedElapsedMillis", SystemClock.elapsedRealtime())
            admission.put("lastRootGuard", guard.name).put("lastCompletedGuard", guard.name)
                .put("lastCompletedAttempt", progress.lastCompletedAttempt)
                .put("guardCounts", JSONObject(progress.guardCounts.mapKeys { it.key.name }))
            report.put("recentsQueryLastCompleted", JSONObject(query.toString()))
            educationObservation?.let { observed ->
                val ledger = checkNotNull(education)
                ledger.put("observations", ++educationObservations)
                if (observed.popup != null && !dismissal.requested) {
                    ledger.put("before", JSONObject().put("attempt", progress.attempt)
                        .put("observedElapsedMillis", SystemClock.elapsedRealtime())
                        .put("owner", observed.owner).put("popup", observed.popup))
                    val request = JSONObject().put("action", "BACK").put("platformAction", 1)
                    ledger.put("request", request).put("operation", "REQUESTING")
                    dismissal.request(until, SystemClock::elapsedRealtime) {
                        request.put("requestedElapsedMillis", SystemClock.elapsedRealtime())
                        // Only this positively identified API32 education popup may request BACK once.
                        try {
                            val accepted = uiAutomation.performGlobalAction(AccessibilityService.GLOBAL_ACTION_BACK)
                            request.put("returned", true).put("accepted", accepted)
                                .put("returnedElapsedMillis", SystemClock.elapsedRealtime())
                            accepted
                        } catch (error: Throwable) {
                            request.put("failureType", error.javaClass.name)
                            throw error
                        }
                    }
                    ledger.put("operation", "AWAITING_REAL_CARD")
                }
                if (value != null) {
                    check(observed.presence == LegacyEducationPresence.ABSENT && observed.popup == null)
                    ledger.put("operation", if (dismissal.requested) "DISMISSED" else "NONE_REQUIRED")
                        .put("after", JSONObject().put("attempt", progress.attempt)
                            .put("observedElapsedMillis", SystemClock.elapsedRealtime())
                            .put("popupAbsent", true).put("absence", observed.absence).put("systemWindow", value))
                }
            }
            if (education != null && value != null) checkNotNull(educationObservation)
            value
        }
        admission.put("completedElapsedMillis", SystemClock.elapsedRealtime()).put("operation", "READY")
        return state // No second root acquisition before the one original screenshot.
    }

    private fun captureState(activity: MainActivity, view: PatternView): LegacyCaptureState = main {
        LegacyCaptureState(System.identityHashCode(activity), System.identityHashCode(activity.window),
            System.identityHashCode(view), activity.taskId, view.width, view.height,
            view.samplesOnScreen().map { (x, y, _) -> x to y },
            activity in created && !activity.isDestroyed && view.context === activity,
            view.isAttachedToWindow, activity.hasWindowFocus() && view.hasWindowFocus(), secure(activity), view.draws)
    }

    private fun stateJson(state: LegacyCaptureState): JSONObject = JSONObject()
        .put("activity", state.activity).put("window", state.window).put("view", state.view).put("taskId", state.taskId)
        .put("viewWidth", state.width).put("viewHeight", state.height).put("viewDraws", state.draws)
        .put("samplePoints", JSONArray(state.points.map { (x, y) -> JSONArray(listOf(x, y)) }))
        .put("owned", state.owned).put("viewAttached", state.attached)
        .put("windowFocused", state.focused).put("secureFlag", state.secure)

    private fun secure(activity: Activity): Boolean =
        activity.window.attributes.flags and WindowManager.LayoutParams.FLAG_SECURE != 0

    private fun navigate(action: LegacyNavigationAction) {
        val request = JSONObject().put("action", action.name).put("platformAction", action.platformAction)
            .put("requestedElapsedMillis", SystemClock.elapsedRealtime()).put("operation", "GLOBAL_ACTION_REQUEST")
        navigationRequests.put(request)
        try {
            requestLegacyNavigation(action, perform = { uiAutomation.performGlobalAction(it) }) { accepted ->
                request.put("returned", true).put("accepted", accepted)
                    .put("returnedElapsedMillis", SystemClock.elapsedRealtime())
                    .put("operation", "GLOBAL_ACTION_RETURNED")
            }
        } catch (error: Throwable) {
            // A thrown request is not an invented false return; preserve the original exception.
            if (!request.has("returned")) {
                request.put("operation", "GLOBAL_ACTION_THROWN").put("failureType", error.javaClass.name)
                    .put("failedElapsedMillis", SystemClock.elapsedRealtime())
            }
            throw error
        }
        // A true return acknowledges the request only. Actual lifecycle/window/image oracles follow.
    }

    private fun <T> main(block: () -> T): T {
        val task = FutureTask(block)
        check(Handler(Looper.getMainLooper()).post(task))
        return try { task.get(5, TimeUnit.SECONDS) } finally { task.cancel(false) }
    }

    private fun await(predicate: () -> Boolean) {
        val until = SystemClock.elapsedRealtime() + 5_000
        while (!predicate()) {
            check(SystemClock.elapsedRealtime() < until) { "Observation deadline at $stage" }
            Thread.sleep(20)
        }
    }

    private val lifecycle = object : Application.ActivityLifecycleCallbacks {
        private fun record(activity: Activity, event: String) {
            if (activity is MainActivity) events += JSONObject().put("event", event)
                .put("activity", System.identityHashCode(activity)).put("taskId", activity.taskId)
                .put("secureFlag", secure(activity)).put("elapsedMillis", SystemClock.elapsedRealtime())
        }
        override fun onActivityCreated(activity: Activity, state: Bundle?) {
            if (activity is MainActivity) created += activity
            record(activity, "created")
        }
        override fun onActivityStarted(activity: Activity) = record(activity, "started")
        override fun onActivityResumed(activity: Activity) = record(activity, "resumed")
        override fun onActivityPaused(activity: Activity) = record(activity, "paused")
        override fun onActivityStopped(activity: Activity) {
            if (activity is MainActivity) stopped += activity
            record(activity, "stopped")
        }
        override fun onActivitySaveInstanceState(activity: Activity, state: Bundle) = record(activity, "saved")
        override fun onActivityDestroyed(activity: Activity) = record(activity, "destroyed")
    }

    private companion object {
        val PATTERN_COLORS = listOf(Color.MAGENTA, Color.CYAN, Color.GREEN, Color.YELLOW)
    }

    private class PatternView(context: Context, private val label: String) : View(context) {
        private val paint = Paint()
        private val colors = PATTERN_COLORS
        var draws = 0
            private set
        override fun onDraw(canvas: Canvas) {
            super.onDraw(canvas)
            for (index in colors.indices) {
                paint.color = colors[index]
                canvas.drawRect(index * width / 4f, 0f, (index + 1) * width / 4f, height.toFloat(), paint)
            }
            paint.color = Color.BLACK
            paint.textSize = 28f
            canvas.drawText(label, 20f, height / 2f, paint)
            draws++
        }
        fun samplesOnScreen(): List<Triple<Int, Int, Int>> {
            val position = IntArray(2)
            getLocationOnScreen(position)
            check(width > 0 && height > 0)
            return colors.mapIndexed { index, color ->
                Triple(position[0] + (index * 2 + 1) * width / 8, position[1] + height / 4, color)
            }
        }
    }
}
