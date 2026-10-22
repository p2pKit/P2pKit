package dev.p2pkit.sample.android.runtime

import android.accessibilityservice.AccessibilityServiceInfo
import android.annotation.SuppressLint
import android.app.Activity
import android.app.ActivityManager
import android.app.Application
import android.app.Instrumentation
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
import android.os.Process
import android.os.SystemClock
import android.view.View
import android.view.WindowManager
import android.view.accessibility.AccessibilityNodeInfo
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
            .put("syntheticOnly", true).put("captureObservationSchema", 2).put("bodyObservationBudgetMillis", 90_000)
            .put("perMainCallAndAwaitMillis", 5_000)
        deadline = SystemClock.elapsedRealtime() + 90_000
        stage = "real-activity-launch"
        main {
            application.registerActivityLifecycleCallbacks(lifecycle)
            application.startActivity(
                Intent(application, MainActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            )
        }
        await { main { created.size == 1 && created.single().hasWindowFocus() } }
        val first = created.single()
        check(main { secure(first) })
        model = main { ViewModelProvider(first)[P2pKitViewModel::class.java].also {
            check(it.currentRunAdmission().canRunKmpSmoke)
        } }
        val firstTask = main { first.taskId }
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
            recentsCloseAction = application.packageManager.getResourcesForApplication(recentsProvider)
                .getIdentifier("accessibility_close", "string", recentsProvider)
            check(recentsCloseAction != 0)
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
        redraw(pattern)
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
        redraw(replacementPattern)
        capture(stage, replacement, replacementPattern, true)
        stage = "reapplied-production-secure-policy"
        main { secureLegacyTaskWindow(replacement.window) }
        redraw(replacementPattern)
        capture(stage, replacement, replacementPattern, false)
        stage = "synthetic-unprotected-closing-control"
        try {
            main { replacement.window.clearFlags(WindowManager.LayoutParams.FLAG_SECURE) }
            redraw(replacementPattern)
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

    private fun redraw(view: PatternView) {
        val before = main { view.draws.also { view.invalidate() } }
        await { main { view.draws > before } }
    }

    private fun capture(name: String, activity: MainActivity?, view: PatternView?, visible: Boolean?) {
        // UNAVAILABLE is a provisional protected observation, never a unique denial or standalone PASS.
        // Actual Recents and both late positives still require original global pixels and independent review.
        val attempt = JSONObject().put("name", name).put("elapsedMillis", SystemClock.elapsedRealtime())
            .put("bodyRemainingMillis", deadline - SystemClock.elapsedRealtime()).put("operation", "BODY_DEADLINE")
        captureAttempts.put(attempt)
        checkLegacyCapture(SystemClock.elapsedRealtime() <= deadline, LegacyCaptureFailureCode.BODY_DEADLINE_EXCEEDED)
        attempt.put("operation", "SAMPLE_GEOMETRY")
        val before = view?.let { captureState(checkNotNull(activity), it) }
        before?.let {
            attempt.put("stateBefore", stateJson(it))
            checkLegacyCaptureState(it, secure = !checkNotNull(visible))
        }
        val systemBefore = if (view == null) admittedRecentsState(attempt) else null
        systemBefore?.let { attempt.put("systemWindowBefore", it) }
        attempt.put("operation", "GLOBAL_SCREENSHOT_REQUEST")
        val bitmap = uiAutomation.takeScreenshot()
        try {
            attempt.put("screenshotReturned", true).put("screenshotAvailable", bitmap != null)
            val after = view?.let { captureState(checkNotNull(activity), it) }
            after?.let { attempt.put("stateAfter", stateJson(it)) }
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
                    checkLegacyCaptureObservation(observation, visible = checkNotNull(visible))
                    record.put("sampleMatches", JSONArray(matches))
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

    private fun recentsState(until: Long, guard: (LegacyRecentsGuard) -> Unit): JSONObject? {
        fun pending(value: LegacyRecentsGuard): JSONObject? { guard(value); return null }
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
        val root = uiAutomation.rootInActiveWindow ?: return pending(LegacyRecentsGuard.ROOT_MISSING)
        try {
            if (!root.refresh()) return pending(LegacyRecentsGuard.ROOT_REFRESH_FAILED)
            if (!root.isVisibleToUser) return pending(LegacyRecentsGuard.ROOT_NOT_VISIBLE)
            if (root.packageName?.toString() != recentsProvider) return pending(LegacyRecentsGuard.ROOT_PACKAGE_INVALID)
            val bounds = Rect().also(root::getBoundsInScreen)
            if (bounds.width() <= 0 || bounds.height() <= 0 || root.windowId < 0) {
                return pending(LegacyRecentsGuard.ROOT_GEOMETRY_INVALID)
            }
            val nodes = mutableListOf<LegacyRecentsNode>()
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
            if (!complete) return pending(LegacyRecentsGuard.TREE_INCOMPLETE)
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
        } finally { @Suppress("DEPRECATION") root.recycle() }
    }

    private fun admittedRecentsState(attempt: JSONObject): JSONObject {
        val started = SystemClock.elapsedRealtime()
        val until = minOf(deadline, started + 5_000)
        val admission = JSONObject().put("startedElapsedMillis", started).put("deadlineElapsedMillis", until)
            .put("budgetMillis", 5_000).put("attempts", 0).put("operation", "PENDING")
        report.put("recentsAdmission", admission)
        attempt.put("operation", "RECENTS_ROOT_ADMISSION")
        var count = 0
        val state = awaitLegacyRecentsState(until, SystemClock::elapsedRealtime, { Thread.sleep(20) }) {
            admission.put("attempts", ++count).put("operation", "OBSERVING").remove("lastRootGuard")
            recentsState(until) { admission.put("lastRootGuard", it.name) }
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
