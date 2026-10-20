package dev.p2pkit.sample.android.runtime

import android.accessibilityservice.AccessibilityServiceInfo
import android.annotation.TargetApi
import android.app.Activity
import android.app.Application
import android.app.Instrumentation
import android.app.KeyguardManager
import android.content.Context
import android.content.Intent
import android.content.pm.ApplicationInfo
import android.content.res.Configuration
import android.graphics.Bitmap
import android.graphics.Rect
import android.os.Build
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.os.PowerManager
import android.os.Process
import android.os.SystemClock
import android.view.KeyEvent
import android.view.MotionEvent
import android.view.View
import android.view.ViewGroup
import android.view.ViewTreeObserver
import android.view.Window
import android.view.WindowInsets
import android.view.WindowManager
import android.view.accessibility.AccessibilityEvent
import android.view.accessibility.AccessibilityNodeInfo
import android.view.accessibility.AccessibilityWindowInfo
import androidx.compose.ui.platform.ComposeView
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import dev.p2pkit.core.BuildInfo
import dev.p2pkit.sample.android.MainActivity
import dev.p2pkit.sample.android.P2pKitSampleApplication
import dev.p2pkit.sample.android.P2pKitViewModel
import dev.p2pkit.sample.diagnostics.DiagnosticEvent
import dev.p2pkit.sample.diagnostics.DiagnosticFilter
import dev.p2pkit.sample.diagnostics.DiagnosticRecord
import dev.p2pkit.sample.diagnostics.diagnosticJson
import java.io.File
import java.security.MessageDigest
import java.util.concurrent.CopyOnWriteArrayList
import java.util.concurrent.FutureTask
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicBoolean
import java.util.concurrent.atomic.AtomicLong
import kotlinx.coroutines.Job
import kotlinx.coroutines.NonCancellable
import kotlinx.coroutines.delay
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withContext
import kotlinx.coroutines.withTimeout
import org.json.JSONArray
import org.json.JSONObject

/**
 * Explicit #317 rendered invalidation case, on an independently admitted, invocation-owned emulator.
 * No kit, replacement composition, Compose test internals, permission grant, or test clock is used.
 * A harness pass still requires retained-image/mutation review; it is not a physical campaign pass.
 */
@TargetApi(35)
class UiAcceptanceInstrumentation : Instrumentation() {
    private lateinit var arguments: Bundle
    private val result = Bundle()
    private val report = JSONObject()
    private val lifecycleEvents = CopyOnWriteArrayList<JSONObject>()
    private val inputEvents = CopyOnWriteArrayList<JSONObject>()
    private val windowEvents = CopyOnWriteArrayList<JSONObject>()
    private val actions = CopyOnWriteArrayList<JSONObject>()
    private val created = CopyOnWriteArrayList<MainActivity>()
    private val destroyed = CopyOnWriteArrayList<MainActivity>()
    private val overflow = AtomicBoolean()
    private val unexpectedActivity = AtomicBoolean()
    private val frames = mutableListOf<Frame>()
    private var stage = "admission"
    private var handsOff = false
    private var application: Application? = null
    private var activity: MainActivity? = null
    private var vm: P2pKitViewModel? = null
    private var output: File? = null
    private var callback: Window.Callback? = null
    private var priorCallback: Window.Callback? = null
    private var accessibilityAttached = false
    private var lifecycleAttached = false

    override fun onCreate(arguments: Bundle?) {
        super.onCreate(arguments)
        this.arguments = Bundle(arguments ?: Bundle())
        start()
    }

    override fun onStart() {
        super.onStart()
        var failure: Throwable? = null
        runBlocking {
            try {
                withTimeout(60_000) { exercise() }
            } catch (error: Throwable) {
                failure = error
                report.put("failure", failureRecord(error, stage))
                result.putString("p2pkitFailureStage", stage)
                result.putString("p2pkitFailureType", error.javaClass.simpleName)
            } finally {
                handsOff = false
                // Attempt every observer/Activity retirement even after an earlier cleanup failure.
                val cleanupFailures = mutableListOf<JSONObject>()
                suspend fun retire(name: String, block: suspend () -> Unit) {
                    try {
                        withContext(NonCancellable) { withTimeout(10_000) { block() } }
                    } catch (error: Throwable) {
                        cleanupFailures += failureRecord(error, name)
                        if (failure == null) failure = error
                    }
                }
                retire("frame-callbacks") { main { frames.forEach { it.retire() } } }
                retire("window-callback") {
                    main {
                        val owned = callback
                        if (owned != null) {
                            val window = checkNotNull(activity).window
                            check(window.callback === owned) { "Window callback ownership changed" }
                            window.callback = checkNotNull(priorCallback)
                            callback = null
                        }
                    }
                }
                retire("owned-activities") {
                    main { created.filterNot { it.isDestroyed }.forEach { it.finish() } }
                    await(5_000) { main { created.all { it.isDestroyed } } }
                    main {
                        check(destroyed.size == created.size)
                        vm?.let { current ->
                            check(current.currentRunAdmission().canRunKmpSmoke)
                            check(current.viewModelScope.coroutineContext[Job]?.isCancelled == true)
                            check(current.diagnosticEvents().count {
                                it.eventName == "application.shutdown" && it.currentState == "view-model-cleared"
                            } == 1)
                        }
                    }
                }
                retire("lifecycle-callback") {
                    main {
                        if (lifecycleAttached) {
                            checkNotNull(application).unregisterActivityLifecycleCallbacks(lifecycle)
                            lifecycleAttached = false
                        }
                    }
                }
                retire("accessibility-listener") {
                    if (accessibilityAttached) {
                        uiAutomation.setOnAccessibilityEventListener(null)
                        accessibilityAttached = false
                    }
                }
                retire("retain-diagnostics") {
                    vm?.let { current -> write("events.jsonl", main { current.diagnosticRecorder.jsonLines() }) }
                }
                report.put("cleanupFailures", JSONArray(cleanupFailures))
                report.put("cleanupScope", "owned Activities and observers; host must retire the owned test process")
                report.put("lifecycle", JSONArray(lifecycleEvents))
                report.put("inputs", JSONArray(inputEvents))
                report.put("windowEvents", JSONArray(windowEvents))
                report.put("actions", JSONArray(actions))
                report.put("frames", JSONArray(frames.map { it.json() }))
                report.put("overflow", overflow.get())
                report.put("unexpectedActivity", unexpectedActivity.get())
                if (overflow.get() && failure == null) failure = IllegalStateException("Observer capacity exceeded")
                if (unexpectedActivity.get() && failure == null) {
                    failure = IllegalStateException("An unexpected Activity appeared in the owned application")
                }
                report.put("outcome", if (failure == null) "HARNESS_PASS_PENDING_REVIEW" else "FAIL")
                report.put("independentVisualAndMutationReview", "REQUIRED_NOT_PERFORMED_BY_RUNNER")
                result.putString("p2pkitCleanup", if (cleanupFailures.isEmpty()) "RETIRED_OWNED_OBSERVERS" else "FAIL")
                try {
                    if (output != null) write("result.json", report.toString(2) + "\n")
                } catch (error: Throwable) {
                    if (failure == null) failure = error
                    result.putString("p2pkitRetention", "FAIL")
                }
            }
        }
        result.putString("p2pkitOutcome", if (failure == null) "HARNESS_PASS_PENDING_REVIEW" else "FAIL")
        result.putString("p2pkitCompleted", "1")
        result.putString("class", javaClass.name)
        result.putString("test", "diagnosticEventAppearsWithoutInput")
        result.putInt("numtests", 1)
        result.putInt("current", 1)
        sendStatus(if (failure == null) 0 else -2, Bundle(result))
        finish(if (failure == null) Activity.RESULT_OK else Activity.RESULT_CANCELED, result)
    }

    private suspend fun exercise() {
        check(arguments.keySet() == setOf("case", "token", "sourceCommit", "sourceTree"))
        check(arguments.getString("case") == "317") { "Only explicit case=317 is implemented" }
        val token = checkNotNull(arguments.getString("token")).also {
            check(it.matches(Regex("[0-9a-f]{32}")))
        }
        val source = checkNotNull(arguments.getString("sourceCommit")).also {
            check(it.matches(Regex("[0-9a-f]{40}")))
        }
        val sourceTree = checkNotNull(arguments.getString("sourceTree")).also {
            check(it.matches(Regex("[0-9a-f]{40}")))
        }
        check(Build.VERSION.SDK_INT >= 35) { "Frame/window admission requires an API35+ runtime" }
        check(BuildInfo.COMMIT == source && !BuildInfo.DIRTY) { "Wrong or dirty source-built library" }
        val app = main { targetContext.applicationContext as P2pKitSampleApplication }
        application = app
        check(app.packageName == PACKAGE && Process.myUid() == app.applicationInfo.uid)
        check(app.applicationInfo.targetSdkVersion == 37)
        check(app.applicationInfo.flags and ApplicationInfo.FLAG_DEBUGGABLE != 0)
        check(!(app.getSystemService(Context.KEYGUARD_SERVICE) as KeyguardManager).isKeyguardLocked)
        check((app.getSystemService(Context.POWER_SERVICE) as PowerManager).isInteractive)
        check(!File(app.noBackupFilesDir, "test-diagnostics").exists()) { "Fresh owned install is required" }
        check(app.getSharedPreferences("p2pkit-test-diagnostics", Context.MODE_PRIVATE).all.isEmpty())
        val directory = File(app.noBackupFilesDir.canonicalFile, "ui-317-$token")
        check(!directory.exists() && directory.mkdir() && directory.canonicalFile == directory)
        output = directory
        result.putString("p2pkitEvidence", "no_backup/${directory.name}")
        result.putString("p2pkitToken", token)
        report.put("schemaVersion", 1).put("case", "317").put("token", token)
        report.put("sourceCommit", source).put("declaredSourceTree", sourceTree)
        report.put("treeBinding", "host must verify source tree and both APK hashes; not independently readable in ART")
        report.put("api", Build.VERSION.SDK_INT).put("targetSdk", app.applicationInfo.targetSdkVersion)
        report.put("abis", JSONArray(Build.SUPPORTED_ABIS.toList()))
        report.put("pid", Process.myPid()).put("uid", Process.myUid())
        report.put("processStartElapsedMillis", Process.getStartElapsedRealtime())
        report.put("boundsMillis", JSONObject().put("body", 60_000).put("setup", 25_000)
            .put("handsOffRefresh", 5_000).put("mainCall", 5_000).put("cleanupAction", 10_000))

        stage = "setup"
        val prepared = withTimeout(25_000) {
            val info = uiAutomation.serviceInfo
            info.flags = info.flags or AccessibilityServiceInfo.FLAG_REPORT_VIEW_IDS or
                AccessibilityServiceInfo.FLAG_RETRIEVE_INTERACTIVE_WINDOWS
            uiAutomation.serviceInfo = info
            uiAutomation.setOnAccessibilityEventListener { event ->
                if (event.eventType in INPUT_ACCESSIBILITY_EVENTS) {
                    note(inputEvents, "accessibility-${event.eventType}")
                        ?.put("eventUptimeMillis", event.eventTime)
                        ?.put("targetPackage", event.packageName?.toString() == PACKAGE)
                }
            }
            accessibilityAttached = true
            main {
                app.registerActivityLifecycleCallbacks(lifecycle)
                lifecycleAttached = true
                app.startActivity(Intent(app, MainActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
            }
            await(10_000) {
                main { created.size == 1 && created.single().lifecycle.currentState == Lifecycle.State.RESUMED }
            }
            val current = main { created.single() }
            activity = current
            val model = main { ViewModelProvider(current)[P2pKitViewModel::class.java] }
            vm = model
            main { installWindowObserver(current) }
            val session = "ui317-$token"
            main {
                check(model.currentRunAdmission().canRunKmpSmoke) { "A kit or operation is already owned" }
                model.updateDiagnosticTestId("UI317")
                model.updateDiagnosticRole("observer")
                model.beginDiagnosticSession(session)
                model.recordDiagnostic(DiagnosticRecord(category = "ui", eventName = BASELINE))
                check(model.diagnosticRecorder.activeSessionId == session)
            }
            await(5_000) { currentAppTree()?.text("Diagnostics") != null }
            action(findText("Diagnostics"), AccessibilityNodeInfo.ACTION_CLICK, "open-diagnostics")
            await(5_000) { currentAppTree()?.text("Test diagnostics") != null }
            val search = editable("Search event, error, peer, packet")
            setText(search, SEARCH, "search-filter")
            val sessionField = editable("Session filter")
            val beforeFrame = main { armFrame("setup-render") }
            setText(sessionField, session, "session-filter")
            listOf(search, sessionField).forEach { original ->
                check(original.refresh())
                if (original.isFocused) action(original, AccessibilityNodeInfo.ACTION_CLEAR_FOCUS, "clear-input-focus")
                if (original.isAccessibilityFocused) {
                    action(original, AccessibilityNodeInfo.ACTION_CLEAR_ACCESSIBILITY_FOCUS, "clear-a11y-focus")
                }
            }
            val baseline = main { selected(model, session).single() }
            check(baseline.eventName == BASELINE)
            await(5_000) { beforeFrame.committed.get() != 0L && currentAppTree()?.ready(listOf(baseline)) == true }
            // Fixed settling allowance, not a retry that extends deadlines or requests another frame.
            delay(1_000)
            val before = tree()
            check(before.ready(listOf(baseline)))
            check(before.nodes.count { it.isEditable && it.text?.toString() == SEARCH } == 1)
            check(before.nodes.count { it.isEditable && it.text?.toString() == session } == 1)
            check(before.text("test=UI317  session=$session  role=observer") != null)
            check(before.nodes.none { it.isEditable && (it.isFocused || it.isAccessibilityFocused) })
            write("before-tree.json", before.json().toString(2) + "\n")
            val baselineImage = screenshot("before.png", before.targets(listOf(baseline)))
            report.put("beforeScreenshot", baselineImage).put("baselineRecord", JSONObject(diagnosticJson(baseline)))
            val lease = main { identity(current, model) }
            val fixedUi = before.fixedUi()
            val rootIdentity = before.root
            val revision = main { model.diagnosticRevision.value }
            val baselineEvents = main { model.diagnosticEvents() }
            val dropped = main { model.diagnosticRecorder.droppedEventCount() }
            check(dropped == 0L)
            report.put("identity", lease.json())
            report.put("recorderBefore", JSONArray(baselineEvents.map { JSONObject(diagnosticJson(it)) }))
            report.put("droppedBefore", dropped)
            Prepared(baseline, session, lease, fixedUi, rootIdentity, revision, baselineEvents, dropped)
        }
        exerciseHandsOff(checkNotNull(vm), prepared)
    }

    private suspend fun exerciseHandsOff(model: P2pKitViewModel, prepared: Prepared) {
        val (baseline, session, lease, fixedUi, rootIdentity, revision, baselineEvents, dropped) = prepared
        report.put("handsOffStart", moment())
        handsOff = true
        // A quiet witness before injection catches unsettled setup input/lifecycle callbacks.
        repeat(5) {
            delay(100)
            unchanged(lease, fixedUi, rootIdentity)
            check(main { model.diagnosticRevision.value == revision && model.diagnosticEvents() == baselineEvents })
        }
        stage = "hands-off-refresh"
        val injection = main {
            val begin = SystemClock.elapsedRealtimeNanos()
            model.recordDiagnostic(DiagnosticRecord(category = "ui", eventName = NEW_EVENT))
            val end = SystemClock.elapsedRealtimeNanos()
            // Observe the next natural commit; never invalidate/request layout or update Compose test state.
            val frame = armFrame("event-only")
            check(model.diagnosticRevision.value == revision + 1)
            Injection(begin, end, frame, model.diagnosticEvents())
        }
        val afterEvents = injection.events
        check(afterEvents.dropLast(1) == baselineEvents && afterEvents.last().eventName == NEW_EVENT)
        val added = afterEvents.last()
        check(added.testSessionId == session && added.gitCommitSha == BuildInfo.COMMIT)
        report.put("recorderAfter", JSONArray(afterEvents.map { JSONObject(diagnosticJson(it)) }))
        report.put("injection", JSONObject().put("beginElapsedNanos", injection.begin)
            .put("endElapsedNanos", injection.end).put("revisionBefore", revision).put("revisionAfter", revision + 1)
            .put("record", JSONObject(diagnosticJson(added))))
        val deadline = injection.end + 5_000_000_000L
        var after: Tree? = null
        do {
            val snapshot = unchanged(lease, fixedUi, rootIdentity)
            check(main { model.diagnosticEvents() == afterEvents && model.diagnosticRevision.value == revision + 1 })
            check(main { model.diagnosticRecorder.droppedEventCount() == dropped })
            val observed = SystemClock.elapsedRealtimeNanos()
            if (observed <= deadline && injection.frame.committed.get() >= injection.end &&
                snapshot.ready(listOf(baseline, added))) {
                after = snapshot
                report.put("renderedWitnessObservedElapsedNanos", observed)
                break
            }
            delay(100)
        } while (SystemClock.elapsedRealtimeNanos() < deadline)
        if (after == null) {
            val failed = tree()
            write("failed-tree.json", failed.json().toString(2) + "\n")
            report.put("failedScreenshot", screenshot("failed.png", emptyList()))
            error("Event was recorded, but no untouched two-row/count/frame witness arrived within five seconds")
        }
        val accepted = checkNotNull(after)
        write("after-tree.json", accepted.json().toString(2) + "\n")
        val afterImage = screenshot("after.png", accepted.targets(listOf(baseline, added)))
        report.put("afterScreenshot", afterImage)
        check(afterImage.getString("sha256") != report.getJSONObject("beforeScreenshot").getString("sha256"))
        repeat(3) { delay(100); check(unchanged(lease, fixedUi, rootIdentity).ready(listOf(baseline, added))) }
        check(main { model.diagnosticEvents() == afterEvents && model.diagnosticRevision.value == revision + 1 })
        check(main { model.diagnosticRecorder.droppedEventCount() == dropped })
        report.put("handsOffEnd", moment())
        report.put("observedCounts", JSONArray(listOf(1, 2)))
        report.put("droppedAfter", dropped)
        handsOff = false
        stage = "completed-rendered-witness"
    }

    private fun selected(model: P2pKitViewModel, session: String): List<DiagnosticEvent> =
        model.diagnosticEvents(DiagnosticFilter(testId = "UI317", sessionId = session, search = SEARCH))

    private fun installWindowObserver(current: MainActivity) {
        val prior = checkNotNull(current.window.callback)
        priorCallback = prior
        val observer = object : Window.Callback by prior {
            override fun dispatchKeyEvent(event: KeyEvent): Boolean {
                note(inputEvents, "key")
                return prior.dispatchKeyEvent(event)
            }
            override fun dispatchKeyShortcutEvent(event: KeyEvent): Boolean {
                note(inputEvents, "key-shortcut")
                return prior.dispatchKeyShortcutEvent(event)
            }
            override fun dispatchTouchEvent(event: MotionEvent): Boolean {
                note(inputEvents, "touch")
                return prior.dispatchTouchEvent(event)
            }
            override fun dispatchTrackballEvent(event: MotionEvent): Boolean {
                note(inputEvents, "trackball")
                return prior.dispatchTrackballEvent(event)
            }
            override fun dispatchGenericMotionEvent(event: MotionEvent): Boolean {
                note(inputEvents, "generic-motion")
                return prior.dispatchGenericMotionEvent(event)
            }
            override fun onWindowFocusChanged(hasFocus: Boolean) {
                note(windowEvents, "focus-$hasFocus")
                prior.onWindowFocusChanged(hasFocus)
            }
            override fun onContentChanged() {
                note(windowEvents, "content-replaced")
                prior.onContentChanged()
            }
            override fun onWindowAttributesChanged(attributes: WindowManager.LayoutParams) {
                note(windowEvents, "attributes-changed")
                prior.onWindowAttributesChanged(attributes)
            }
        }
        current.window.callback = observer
        callback = observer
    }

    private fun identity(current: MainActivity, model: P2pKitViewModel): Identity {
        check(created.size == 1 && destroyed.isEmpty() && created.single() === current)
        check(current.lifecycle.currentState == Lifecycle.State.RESUMED && current.hasWindowFocus())
        check(ViewModelProvider(current)[P2pKitViewModel::class.java] === model)
        check(model.currentRunAdmission().canRunKmpSmoke) { "Unexpected kit acquisition" }
        check(current.window.callback === callback)
        val decor = current.window.decorView
        check(decor.isShown && decor.isAttachedToWindow && decor.isHardwareAccelerated)
        check(!checkNotNull(decor.rootWindowInsets).isVisible(WindowInsets.Type.ime())) { "IME obscures the witness" }
        val views = mutableListOf<View>()
        fun visit(view: View) {
            check(views.size < 200)
            views += view
            if (view is ViewGroup) repeat(view.childCount) { visit(view.getChildAt(it)) }
        }
        visit(decor)
        val compose = views.filterIsInstance<ComposeView>().single()
        val config = Configuration(current.resources.configuration)
        check(config.screenWidthDp >= 900 && config.screenHeightDp >= 1_500) {
            "Pre-admit a sufficiently large display; do not change layout during this case"
        }
        val viewport = Rect().also { decor.getWindowVisibleDisplayFrame(it) }
        check(!viewport.isEmpty && compose.rootView === decor)
        check(!overflow.get() && !unexpectedActivity.get())
        return Identity(System.identityHashCode(current), System.identityHashCode(model),
            views, config, viewport, checkNotNull(decor.windowToken), lifecycleEvents.size,
            inputEvents.size, windowEvents.size, actions.size, model.diagnosticTestId, model.diagnosticRole,
            model.diagnosticRecorder.activeSessionId, model.lanPermissionState.value.toString())
    }

    private fun unchanged(lease: Identity, fixedUi: List<String>, root: AccessibilityNodeInfo): Tree {
        check(handsOff)
        check(main { identity(checkNotNull(activity), checkNotNull(vm)) } == lease) {
            "Activity/root/configuration/input/lifecycle/session/permission identity changed during hands-off interval"
        }
        val current = tree()
        check(current.root == root && current.fixedUi() == fixedUi) { "UI filters or root changed" }
        return current
    }

    private fun findText(value: String): AccessibilityNodeInfo = checkNotNull(tree().text(value)) {
        "Missing exact visible target: $value"
    }

    private fun editable(label: String): AccessibilityNodeInfo = tree().nodes.filter {
        it.isEditable && it.isVisibleToUser && (it.hintText?.toString() == label || it.text?.toString() == label ||
            (0 until it.childCount).any { index -> it.getChild(index)?.text?.toString() == label })
    }.single()

    private fun setText(node: AccessibilityNodeInfo, value: String, label: String) {
        val args = Bundle().apply {
            putCharSequence(AccessibilityNodeInfo.ACTION_ARGUMENT_SET_TEXT_CHARSEQUENCE, value)
        }
        action(node, AccessibilityNodeInfo.ACTION_SET_TEXT, label, args)
    }

    private fun action(node: AccessibilityNodeInfo, action: Int, label: String, args: Bundle? = null) {
        check(!handsOff) { "Input is forbidden after the baseline" }
        val target = if (action == AccessibilityNodeInfo.ACTION_CLICK) {
            generateSequence(node) { it.parent }.take(6).firstOrNull {
                it.packageName?.toString() == PACKAGE && it.isVisibleToUser && it.isEnabled && it.isClickable
            }
        } else node
        val entry = moment().put("action", action).put("label", label)
        actions += entry
        val success = checkNotNull(target).performAction(action, args)
        entry.put("success", success)
        check(success) { "Real UI action failed: $label" }
    }

    private fun tree(): Tree = checkNotNull(currentAppTree()) { "No active visible Android application window" }

    private fun currentAppTree(): Tree? {
        val root = uiAutomation.rootInActiveWindow ?: return null
        if (root.packageName?.toString() != PACKAGE || !root.isVisibleToUser) return null
        val nodes = mutableListOf<AccessibilityNodeInfo>()
        val pending = ArrayDeque<AccessibilityNodeInfo>()
        pending.add(root)
        while (pending.isNotEmpty()) {
            val node = pending.removeFirst()
            check(nodes.size < 1_500)
            check(node.packageName?.toString() == PACKAGE)
            nodes += node
            repeat(node.childCount) { node.getChild(it)?.let(pending::add) }
        }
        return Tree(root, nodes)
    }

    private fun screenshot(name: String, targets: List<Rect>): JSONObject {
        val before = SystemClock.elapsedRealtimeNanos()
        val viewport = main { Rect().also { checkNotNull(activity).window.decorView.getWindowVisibleDisplayFrame(it) } }
        val windows = uiAutomation.windows
        check(windows.size in 1..32)
        val appWindow = windows.single {
            it.type == AccessibilityWindowInfo.TYPE_APPLICATION && it.isActive && it.isFocused &&
                it.root?.packageName?.toString() == PACKAGE
        }
        targets.forEach { target ->
            check(viewport.contains(target)) { "Target lies outside the visible application viewport" }
            windows.filter { it.layer > appWindow.layer }.forEach { other ->
                val bounds = Rect().also { other.getBoundsInScreen(it) }
                check(!Rect.intersects(bounds, target)) { "A higher Android window obscures the target" }
            }
        }
        val bitmap = checkNotNull(uiAutomation.takeScreenshot()) { "Android display capture failed" }
        try {
            check(bitmap.width.toLong() * bitmap.height <= 16_777_216 && bitmap.config != Bitmap.Config.HARDWARE)
            val display = Rect(0, 0, bitmap.width, bitmap.height)
            targets.forEach { bounds ->
                check(!bounds.isEmpty && display.contains(bounds)) { "Target is clipped/off-screen" }
                val count = bounds.width().toLong() * bounds.height()
                check(count in 2L..1_048_576L)
                val pixels = IntArray(count.toInt())
                bitmap.getPixels(pixels, 0, bounds.width(), bounds.left, bounds.top, bounds.width(), bounds.height())
                check(pixels.any { it != pixels.first() }) { "Target display crop is blank" }
            }
            val file = newFile(name)
            file.outputStream().use { check(bitmap.compress(Bitmap.CompressFormat.PNG, 100, it)) }
            check(file.length() in 1L..16_777_216L)
            return JSONObject().put("file", name).put("sha256", digest(file.readBytes()))
                .put("beginElapsedNanos", before).put("endElapsedNanos", SystemClock.elapsedRealtimeNanos())
                .put("width", bitmap.width).put("height", bitmap.height)
                .put("windows", JSONArray(windows.map { window ->
                    JSONObject().put("id", window.id).put("type", window.type).put("layer", window.layer)
                        .put("bounds", rect(Rect().also { window.getBoundsInScreen(it) }))
                }))
                .put("targets", JSONArray(targets.map { rect(it) }))
                .put("pixelOracle", "nonblank in-bounds display crops; exact visible text requires independent review")
        } finally {
            bitmap.recycle()
        }
    }

    private fun armFrame(label: String): Frame {
        val observer = checkNotNull(activity).window.decorView.viewTreeObserver
        check(observer.isAlive)
        val frame = Frame(label, observer)
        frames += frame
        observer.registerFrameCommitCallback(frame.callback)
        return frame
    }

    private fun note(destination: CopyOnWriteArrayList<JSONObject>, kind: String): JSONObject? {
        if (destination.size >= 1_024) {
            overflow.set(true)
            return null
        }
        return moment().put("kind", kind).also { destination += it }
    }

    private val lifecycle = object : Application.ActivityLifecycleCallbacks {
        private fun event(activity: Activity, name: String) {
            note(lifecycleEvents, name)?.put("activityIdentity", System.identityHashCode(activity))
            if (activity !is MainActivity) unexpectedActivity.set(true)
        }
        override fun onActivityCreated(activity: Activity, state: Bundle?) {
            event(activity, "created")
            if (activity is MainActivity) created += activity
        }
        override fun onActivityStarted(activity: Activity) = event(activity, "started")
        override fun onActivityResumed(activity: Activity) = event(activity, "resumed")
        override fun onActivityPaused(activity: Activity) = event(activity, "paused")
        override fun onActivityStopped(activity: Activity) = event(activity, "stopped")
        override fun onActivitySaveInstanceState(activity: Activity, state: Bundle) = event(activity, "saved")
        override fun onActivityDestroyed(activity: Activity) {
            event(activity, "destroyed")
            if (activity is MainActivity) destroyed += activity
        }
    }

    private suspend fun await(millis: Long, condition: () -> Boolean) {
        withTimeout(millis) { while (!condition()) delay(100) }
    }

    private fun <T> main(block: () -> T): T {
        check(Looper.myLooper() != Looper.getMainLooper())
        val task = FutureTask<T> { block() }
        check(Handler(Looper.getMainLooper()).post(task))
        return try { task.get(5, TimeUnit.SECONDS) } finally { task.cancel(false) }
    }

    private fun newFile(name: String): File = File(checkNotNull(output), name).also {
        check(name.matches(Regex("[a-z-]+\\.(json|jsonl|png)")) && it.createNewFile()) { "Evidence already exists" }
    }

    private fun write(name: String, text: String) {
        val bytes = text.toByteArray(Charsets.UTF_8)
        check(bytes.size <= 2 * 1024 * 1024)
        newFile(name).writeBytes(bytes)
    }

    private data class Prepared(
        val baseline: DiagnosticEvent,
        val session: String,
        val lease: Identity,
        val fixedUi: List<String>,
        val root: AccessibilityNodeInfo,
        val revision: Long,
        val events: List<DiagnosticEvent>,
        val dropped: Long
    )

    private data class Injection(val begin: Long, val end: Long, val frame: Frame, val events: List<DiagnosticEvent>)

    private data class Identity(
        val activityIdentity: Int,
        val viewModelIdentity: Int,
        val views: List<View>,
        val configuration: Configuration,
        val viewport: Rect,
        val windowToken: Any,
        val lifecycleCount: Int,
        val inputCount: Int,
        val windowCount: Int,
        val actionCount: Int,
        val testId: String,
        val role: String,
        val session: String,
        val lanPermission: String
    ) {
        fun json(): JSONObject = JSONObject().put("activityIdentity", activityIdentity)
            .put("viewModelIdentity", viewModelIdentity)
            .put("windowTokenIdentity", System.identityHashCode(windowToken))
            .put("viewIdentities", JSONArray(views.map { System.identityHashCode(it) }))
            .put("viewClasses", JSONArray(views.map { it.javaClass.name })).put("viewport", rect(viewport))
            .put("screenWidthDp", configuration.screenWidthDp).put("screenHeightDp", configuration.screenHeightDp)
            .put("densityDpi", configuration.densityDpi).put("fontScale", configuration.fontScale)
            .put("lifecycleCount", lifecycleCount).put("inputCount", inputCount)
            .put("windowCount", windowCount).put("actionCount", actionCount)
            .put("testId", testId).put("role", role).put("session", session).put("lanPermission", lanPermission)
    }

    private class Tree(val root: AccessibilityNodeInfo, val nodes: List<AccessibilityNodeInfo>) {
        fun text(value: String): AccessibilityNodeInfo? = nodes.filter {
            it.isVisibleToUser && it.text?.toString() == value
        }.also { check(it.size <= 1) { "Ambiguous visible text" } }.singleOrNull()

        private fun row(event: DiagnosticEvent): AccessibilityNodeInfo? = nodes.filter {
            // A clickable Card may merge its two Text children into one accessibility node.
            it.isVisibleToUser && it.text?.toString() in setOf(title(event), "${title(event)}\nLOCAL")
        }.also { check(it.size <= 1) { "Ambiguous rendered diagnostic row" } }.singleOrNull()

        fun ready(events: List<DiagnosticEvent>): Boolean = text(count(events.size)) != null &&
            events.all { row(it) != null } && text("Pause live logs") != null

        fun targets(events: List<DiagnosticEvent>): List<Rect> =
            (listOf(checkNotNull(text(count(events.size)))) + events.map { checkNotNull(row(it)) })
                .map { node -> Rect().also { node.getBoundsInScreen(it) } }

        // All editable values, level selection and static summary are read-only interval guards.
        fun fixedUi(): List<String> = nodes.filter {
            it.isEditable || it.text?.toString() in setOf("All levels", "WARNING", "ERROR", "Pause live logs") ||
                it.text?.toString()?.startsWith("test=") == true
        }.map { node ->
            listOf(node.text, node.hintText, node.isSelected, node.isChecked, node.isFocused,
                node.isAccessibilityFocused).joinToString("|")
        }

        fun json(): JSONObject = JSONObject().put("captured", moment()).put("windowId", root.windowId)
            .put("nodes", JSONArray(nodes.map { node ->
                JSONObject().put("text", node.text?.toString()).put("hint", node.hintText?.toString())
                    .put("class", node.className?.toString()).put("visible", node.isVisibleToUser)
                    .put("editable", node.isEditable).put("selected", node.isSelected).put("checked", node.isChecked)
                    .put("focused", node.isFocused).put("accessibilityFocused", node.isAccessibilityFocused)
                    .put("bounds", rect(Rect().also { node.getBoundsInScreen(it) }))
            }))
    }

    private class Frame(val label: String, private val observer: ViewTreeObserver) {
        val committed = AtomicLong()
        val armed = SystemClock.elapsedRealtimeNanos()
        val callback = Runnable { committed.compareAndSet(0, SystemClock.elapsedRealtimeNanos()) }
        var removed = false
        fun retire() {
            if (committed.get() == 0L) {
                check(observer.isAlive)
                removed = observer.unregisterFrameCommitCallback(callback)
                check(removed || committed.get() != 0L) { "Frame callback retirement is unknown" }
            }
        }
        fun json(): JSONObject = JSONObject().put("label", label).put("armedElapsedNanos", armed)
            .put("committedElapsedNanos", committed.get()).put("removedBeforeCommit", removed)
    }

    private companion object {
        const val PACKAGE = "dev.p2pkit.sample.android"
        const val SEARCH = "probe317"
        const val BASELINE = "probe317_a"
        const val NEW_EVENT = "probe317_b"
        val INPUT_ACCESSIBILITY_EVENTS = setOf(
            AccessibilityEvent.TYPE_VIEW_CLICKED,
            AccessibilityEvent.TYPE_VIEW_LONG_CLICKED,
            AccessibilityEvent.TYPE_VIEW_SELECTED,
            AccessibilityEvent.TYPE_VIEW_FOCUSED,
            AccessibilityEvent.TYPE_VIEW_TEXT_CHANGED,
            AccessibilityEvent.TYPE_VIEW_TEXT_SELECTION_CHANGED,
            AccessibilityEvent.TYPE_VIEW_SCROLLED,
            AccessibilityEvent.TYPE_VIEW_ACCESSIBILITY_FOCUSED,
            AccessibilityEvent.TYPE_VIEW_ACCESSIBILITY_FOCUS_CLEARED,
            AccessibilityEvent.TYPE_TOUCH_INTERACTION_START,
            AccessibilityEvent.TYPE_TOUCH_INTERACTION_END
        )
        fun count(size: Int): String = "$size event(s); tap rows to select"
        fun title(event: DiagnosticEvent): String = "${event.timestamp} ${event.severity} ${event.eventName}"
        fun moment(): JSONObject = JSONObject().put("elapsedNanos", SystemClock.elapsedRealtimeNanos())
            .put("uptimeMillis", SystemClock.uptimeMillis())
        fun rect(value: Rect): JSONArray = JSONArray(listOf(value.left, value.top, value.right, value.bottom))
        fun digest(bytes: ByteArray): String = MessageDigest.getInstance("SHA-256").digest(bytes)
            .joinToString("") { "%02x".format(it) }
        fun failureRecord(error: Throwable, at: String): JSONObject = JSONObject().put("stage", at)
            .put("type", error.javaClass.name).put("message", error.message?.take(512))
    }
}
