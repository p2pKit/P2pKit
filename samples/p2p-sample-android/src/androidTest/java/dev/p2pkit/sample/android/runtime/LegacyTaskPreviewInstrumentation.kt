package dev.p2pkit.sample.android.runtime

import android.app.Activity
import android.app.ActivityManager
import android.app.Application
import android.app.Instrumentation
import android.content.Context
import android.content.Intent
import android.graphics.Bitmap
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Paint
import android.os.Build
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.os.Process
import android.os.SystemClock
import android.view.KeyEvent
import android.view.View
import android.view.WindowManager
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
    private val events = CopyOnWriteArrayList<JSONObject>()
    private val created = CopyOnWriteArrayList<MainActivity>()
    private val stopped = CopyOnWriteArrayList<MainActivity>()
    private var app: Application? = null
    private var model: P2pKitViewModel? = null
    private var output: File? = null
    private var stage = "admission"
    private var deadline = 0L
    private var token = ""

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
            report.put("failure", JSONObject().put("stage", stage).put("type", error.javaClass.name))
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
            report.put("outcome", outcome).put("captures", captures).put("lifecycle", JSONArray(events))
                .put("recentsReviewRequired", true)
                .put("scope", "API24/32 synthetic content in real MainActivity; not natural credential/RPC flow")
            try {
                output?.resolve("result.json")?.writeText(report.toString(2) + "\n")
            } catch (error: Throwable) {
                if (failure == null) failure = error
                result.putString("p2pkitRetention", "FAIL")
            }
            result.putString("p2pkitToken", token)
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
            .put("syntheticOnly", true).put("bodyObservationBudgetMillis", 90_000)
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

        stage = "home-stopped"
        key(KeyEvent.KEYCODE_HOME)
        await { main { first in stopped && !first.hasWindowFocus() } }
        check(main { secure(first) })
        stage = "actual-recents-original"
        key(KeyEvent.KEYCODE_APP_SWITCH)
        // Capture the actual system window, not a fabricated task bitmap. Its task-card identity and
        // absence of the synthetic phrase/pattern must also be independently reviewed in the original PNG.
        await { uiAutomation.rootInActiveWindow?.let { root ->
            try { root.packageName?.toString() != application.packageName && root.isVisibleToUser }
            finally { @Suppress("DEPRECATION") root.recycle() }
        } == true }
        capture(stage, null, null, null)
        report.put("taskId", firstTask)

        stage = "same-task-reentry"
        main {
            val manager = application.getSystemService(Context.ACTIVITY_SERVICE) as ActivityManager
            @Suppress("DEPRECATION") // RecentTaskInfo.id is the public API24-compatible field.
            val task = manager.appTasks.single { it.taskInfo.id == firstTask }
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
        check(SystemClock.elapsedRealtime() <= deadline)
        val samples = view?.let { main { it.samplesOnScreen() } }
        val bitmap = checkNotNull(uiAutomation.takeScreenshot()) { "Global screenshot unavailable" }
        try {
            val file = File(checkNotNull(output), "$name.png")
            file.outputStream().use { check(bitmap.compress(Bitmap.CompressFormat.PNG, 100, it)) }
            val record = JSONObject().put("name", name).put("file", file.name)
                .put("elapsedMillis", SystemClock.elapsedRealtime()).put("width", bitmap.width)
                .put("height", bitmap.height).put("activity", activity?.let { System.identityHashCode(it) })
            captures.put(record)
            if (samples != null) {
                val matches = samples.map { (x, y, color) ->
                    check(x in 0 until bitmap.width && y in 0 until bitmap.height)
                    bitmap.getPixel(x, y) == color
                }
                record.put("sampleMatches", JSONArray(matches))
                    .put("secureFlag", main { secure(checkNotNull(activity)) })
                if (visible == true) check(matches.all { it }) { "Unprotected positive control not captured" }
                if (visible == false) check(matches.none { it }) { "Secure window pattern captured" }
            }
        } finally { bitmap.recycle() }
    }

    private fun secure(activity: Activity): Boolean =
        activity.window.attributes.flags and WindowManager.LayoutParams.FLAG_SECURE != 0

    private fun key(code: Int) {
        check(uiAutomation.injectInputEvent(KeyEvent(KeyEvent.ACTION_DOWN, code), true))
        check(uiAutomation.injectInputEvent(KeyEvent(KeyEvent.ACTION_UP, code), true))
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

    private class PatternView(context: Context, private val label: String) : View(context) {
        private val paint = Paint()
        private val colors = listOf(Color.MAGENTA, Color.CYAN, Color.GREEN, Color.YELLOW)
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
