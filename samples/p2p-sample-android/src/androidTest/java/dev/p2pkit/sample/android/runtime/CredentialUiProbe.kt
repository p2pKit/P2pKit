package dev.p2pkit.sample.android.runtime

import android.annotation.TargetApi
import android.app.Instrumentation
import android.graphics.Bitmap
import android.graphics.Rect
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.os.Parcel
import android.os.SystemClock
import android.view.KeyEvent
import android.view.MotionEvent
import android.view.View
import android.view.ViewGroup
import android.view.ViewTreeObserver
import android.view.Window
import android.view.WindowInsets
import android.view.accessibility.AccessibilityNodeInfo
import android.view.accessibility.AccessibilityWindowInfo
import androidx.compose.runtime.State
import androidx.compose.runtime.saveable.SaveableStateRegistry
import androidx.compose.ui.platform.ViewRootForTest
import androidx.compose.ui.semantics.SemanticsActions
import androidx.compose.ui.semantics.SemanticsNode
import androidx.compose.ui.semantics.SemanticsProperties
import androidx.compose.ui.semantics.getOrNull
import androidx.compose.ui.text.TextLayoutResult
import androidx.lifecycle.Lifecycle
import dev.p2pkit.sample.android.MainActivity
import java.io.File
import java.security.MessageDigest
import java.util.concurrent.FutureTask
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicLong
import kotlin.math.ceil
import kotlin.math.floor
import kotlinx.coroutines.delay
import kotlinx.coroutines.withTimeout
import org.json.JSONArray
import org.json.JSONObject

internal fun <T> credentialMain(block: () -> T): T {
    check(Looper.myLooper() != Looper.getMainLooper())
    val task = FutureTask<T> { block() }
    check(Handler(Looper.getMainLooper()).post(task))
    return try { task.get(5, TimeUnit.SECONDS) } finally { task.cancel(false) }
}

internal suspend fun credentialAwait(condition: () -> Boolean) {
    val deadline = SystemClock.elapsedRealtimeNanos() + 5_000_000_000L
    withTimeout(5_000) {
        while (true) {
            val accepted = condition()
            check(SystemClock.elapsedRealtimeNanos() <= deadline) { "Five-second observation deadline exceeded" }
            if (accepted) break
            delay(50)
        }
    }
}

internal fun credentialDigest(bytes: ByteArray): String = MessageDigest.getInstance("SHA-256").digest(bytes)
    .joinToString("") { "%02x".format(it) }

/** The provider map is live/shallow. Encode AND decode all entries now, while the original secret still exists. */
internal fun credentialParcel(
    registry: SaveableStateRegistry,
    classLoader: ClassLoader,
    ssid: String,
    secret: String,
    output: File
): Map<String, List<Any?>> {
    check(Looper.myLooper() == Looper.getMainLooper())
    val writer = Parcel.obtain()
    val reader = Parcel.obtain()
    try {
        val before = SystemClock.elapsedRealtimeNanos()
        val live = registry.performSave()
        check(live.isNotEmpty()) { "No actual save providers registered" }
        writer.writeValue(live)
        val bytes = writer.marshall()
        check(bytes.size in 1..1_048_576)
        check(File(output, "saved-state.parcel").createNewFile())
        File(output, "saved-state.parcel").writeBytes(bytes)
        reader.unmarshall(bytes, 0, bytes.size)
        reader.setDataPosition(0)
        val decoded = checkNotNull(reader.readValue(classLoader) as? Map<*, *>)
        check(reader.dataAvail() == 0 && decoded.size == live.size)
        // Type-check every entry without filtering payloads or importing Android's private Parcelable State class.
        val restored = linkedMapOf<String, List<Any?>>()
        decoded.forEach { (key, value) ->
            check(key is String && value is List<*>)
            restored[key] = value.toList()
        }
        check(restored.keys == live.keys)
        val strings = mutableListOf<String>()
        val types = JSONArray()
        fun inspect(value: Any?, depth: Int = 0) {
            check(depth < 20 && types.length() < 1_024)
            types.put(value?.javaClass?.name ?: "null")
            when (value) {
                null, is Boolean, is Number, is Char -> Unit
                is String -> strings += value
                is State<*> -> inspect(value.value, depth + 1)
                is List<*> -> value.forEach { inspect(it, depth + 1) }
                is Map<*, *> -> value.forEach { (key, item) -> inspect(key, depth + 1); inspect(item, depth + 1) }
                else -> error("Uninspected saved-state payload type: ${value.javaClass.name}")
            }
        }
        var fullyInspected = false
        try {
            inspect(restored)
            fullyInspected = true
        } finally {
            val snapshot = JSONObject().put("beginElapsedNanos", before)
                .put("decodedElapsedNanos", SystemClock.elapsedRealtimeNanos())
                .put("bytes", bytes.size).put("sha256", credentialDigest(bytes)).put("entryCount", restored.size)
                .put("keys", JSONArray(restored.keys.toList())).put("payloadTypes", types)
                .put("fullyInspected", fullyInspected)
                .put("ssidPresent", ssid in strings).put("secretPresent", strings.any { secret in it })
            check(File(output, "saved-state.json").createNewFile())
            File(output, "saved-state.json").writeText(snapshot.toString(2) + "\n")
        }
        check(ssid in strings) { "SSID positive control is missing from the real saved payload" }
        check(strings.none { secret in it }) { "The pre-clear saved payload contains the synthetic credential" }
        return restored
    } finally {
        reader.recycle()
        writer.recycle()
    }
}

/** Public semantics read-side plus actual display/frame evidence; never forces measurement or recomposition. */
@TargetApi(35)
internal class CredentialUiProbe(
    private val instrumentation: Instrumentation,
    private val activity: MainActivity,
    private val output: File
) {
    val captures = JSONArray()
    val actions = JSONArray()
    val frames = mutableListOf<Frame>()
    val inputCount = AtomicLong()
    private val originalCallback = credentialMain { checkNotNull(activity.window.callback) }
    private val callback = object : Window.Callback by originalCallback {
        override fun dispatchKeyEvent(event: KeyEvent): Boolean {
            inputCount.incrementAndGet()
            return originalCallback.dispatchKeyEvent(event)
        }
        override fun dispatchKeyShortcutEvent(event: KeyEvent): Boolean {
            inputCount.incrementAndGet()
            return originalCallback.dispatchKeyShortcutEvent(event)
        }
        override fun dispatchTrackballEvent(event: MotionEvent): Boolean {
            inputCount.incrementAndGet()
            return originalCallback.dispatchTrackballEvent(event)
        }
        override fun dispatchTouchEvent(event: MotionEvent): Boolean {
            inputCount.incrementAndGet()
            return originalCallback.dispatchTouchEvent(event)
        }
        override fun dispatchGenericMotionEvent(event: MotionEvent): Boolean {
            inputCount.incrementAndGet()
            return originalCallback.dispatchGenericMotionEvent(event)
        }
    }

    init { credentialMain { activity.window.callback = callback } }

    fun frame(label: String): Frame = credentialMain {
        Frame(label, activity.window.decorView.viewTreeObserver).also {
            check(frames.size < 200)
            frames += it
            it.arm()
        }
    }

    fun click(vararg labels: String): Long {
        val nodes = nodes()
        val target = nodes.filter { it.isVisibleToUser && it.text?.toString() in labels }.single()
        return action(target, AccessibilityNodeInfo.ACTION_CLICK, labels.joinToString("/"))
    }

    fun enter(label: String, value: String) {
        val field = nodes().filter { node ->
            node.isEditable && node.isVisibleToUser && (node.hintText?.toString() == label ||
                node.text?.toString() == label || (0 until node.childCount).any {
                    node.getChild(it)?.text?.toString() == label
                })
        }.single()
        action(field, AccessibilityNodeInfo.ACTION_SET_TEXT, label, Bundle().apply {
            putCharSequence(AccessibilityNodeInfo.ACTION_ARGUMENT_SET_TEXT_CHARSEQUENCE, value)
        })
        check(field.refresh())
        if (field.isFocused) action(field, AccessibilityNodeInfo.ACTION_CLEAR_FOCUS, "clear-field-focus")
        if (field.isAccessibilityFocused) {
            action(field, AccessibilityNodeInfo.ACTION_CLEAR_ACCESSIBILITY_FOCUS, "clear-field-a11y-focus")
        }
    }

    private fun action(node: AccessibilityNodeInfo, action: Int, label: String, args: Bundle? = null): Long {
        val target = if (action == AccessibilityNodeInfo.ACTION_CLICK) {
            generateSequence(node) { it.parent }.take(6).firstOrNull {
                it.isClickable && it.isEnabled && it.isVisibleToUser && it.packageName?.toString() == PACKAGE
            }
        } else node
        check(actions.length() < 100)
        val begin = SystemClock.elapsedRealtimeNanos()
        val row = JSONObject().put("label", label).put("action", action).put("beginElapsedNanos", begin)
        actions.put(row)
        val ok = checkNotNull(target).performAction(action, args)
        row.put("success", ok).put("endElapsedNanos", SystemClock.elapsedRealtimeNanos())
        check(ok) { "Real credential UI action failed: $label" }
        return begin
    }

    fun textPresent(value: String): Boolean = nodes().any { it.isVisibleToUser && it.text?.toString() == value }

    fun identity(): List<Any> = credentialMain {
        check(activity.lifecycle.currentState == Lifecycle.State.RESUMED && activity.hasWindowFocus())
        val decor = activity.window.decorView
        check(decor.isHardwareAccelerated && decor.isShown && decor.isAttachedToWindow)
        check(activity.window.callback === callback)
        check(!checkNotNull(decor.rootWindowInsets).isVisible(WindowInsets.Type.ime()))
        val config = activity.resources.configuration
        check(config.screenWidthDp >= 600 && config.screenHeightDp >= 900)
        listOf(activity, decor, checkNotNull(decor.windowToken), root().first, config.toString())
    }

    suspend fun field(
        label: String,
        input: String,
        visibleText: String,
        password: Boolean,
        frame: Frame,
        minimumFrameNanos: Long = frame.armed
    ) {
        var observation: Drawn? = null
        credentialAwait {
            observation = credentialMain { drawnField(input) }
            val committed = frame.committed.get()
            if (committed > 0 && committed < minimumFrameNanos) credentialMain { frame.arm() }
            observation?.let { it.text == visibleText && it.password == password } == true &&
                frame.committed.get() >= minimumFrameNanos
        }
        identity()
        val witness = checkNotNull(observation)
        capture(label, listOf(witness.bounds), frame).put("drawnLength", witness.text.length)
            .put("password", password).put("inputLength", input.length)
            .put("layoutText", witness.text).put("layoutSha256", credentialDigest(witness.text.toByteArray()))
            .put("oracle", "actual GetTextLayoutResult; raw InputText is not a pixel-exposure assertion")
    }

    suspend fun status(label: String, visibleText: String, frame: Frame) {
        credentialAwait { frame.committed.get() != 0L && textPresent(visibleText) }
        identity()
        val target = nodes().filter { it.isVisibleToUser && it.text?.toString() == visibleText }.single()
        capture(label, listOf(Rect().also { target.getBoundsInScreen(it) }), frame)
    }

    suspend fun removed(label: String, frame: Frame) {
        credentialAwait { frame.committed.get() != 0L && !textPresent(CARD_TITLE) }
        check(nodes().none { it.isEditable })
        identity()
        capture(label, emptyList(), frame)
    }

    private fun drawnField(input: String): Drawn? {
        val (view, root) = root()
        val pending = ArrayDeque<SemanticsNode>()
        pending.add(root.semanticsOwner.unmergedRootSemanticsNode)
        val candidates = mutableListOf<SemanticsNode>()
        var count = 0
        while (pending.isNotEmpty()) {
            check(++count <= 1_500)
            val node = pending.removeFirst()
            if (node.config.getOrNull(SemanticsProperties.InputText)?.text == input &&
                node.config.getOrNull(SemanticsActions.GetTextLayoutResult)?.action != null) candidates += node
            pending.addAll(node.children)
        }
        check(candidates.size <= 1) { "Ambiguous actual credential text-layout owner" }
        val node = candidates.singleOrNull() ?: return null
        if (!node.layoutInfo.isAttached || !node.layoutInfo.isPlaced || node.layoutInfo.isDeactivated) return null
        val layouts = mutableListOf<TextLayoutResult>()
        if (!checkNotNull(node.config.getOrNull(SemanticsActions.GetTextLayoutResult)?.action)(layouts)) return null
        val layout = layouts.single()
        if (layout.hasVisualOverflow) return null
        if (node.config.getOrNull(SemanticsProperties.EditableText)?.text != layout.layoutInput.text.text) return null
        val screen = IntArray(2).also(view::getLocationOnScreen)
        val window = IntArray(2).also(view::getLocationInWindow)
        val bounds = node.boundsInWindow
        val rect = Rect(floor(bounds.left).toInt(), floor(bounds.top).toInt(),
            ceil(bounds.right).toInt(), ceil(bounds.bottom).toInt())
        rect.offset(screen[0] - window[0], screen[1] - window[1])
        return Drawn(layout.layoutInput.text.text, node.config.getOrNull(SemanticsProperties.Password) != null, rect)
    }

    private fun root(): Pair<View, ViewRootForTest> {
        val found = mutableListOf<Pair<View, ViewRootForTest>>()
        var count = 0
        fun visit(view: View) {
            check(++count < 200)
            if (view is ViewRootForTest) found += view to view
            if (view is ViewGroup) repeat(view.childCount) { visit(view.getChildAt(it)) }
        }
        visit(activity.window.decorView)
        return found.single()
    }

    private fun nodes(): List<AccessibilityNodeInfo> {
        val root = checkNotNull(instrumentation.uiAutomation.rootInActiveWindow)
        check(root.packageName?.toString() == PACKAGE && root.isVisibleToUser)
        val all = mutableListOf<AccessibilityNodeInfo>()
        val pending = ArrayDeque<AccessibilityNodeInfo>()
        pending.add(root)
        while (pending.isNotEmpty()) {
            check(all.size < 1_500)
            val node = pending.removeFirst()
            all += node
            repeat(node.childCount) { node.getChild(it)?.let(pending::add) }
        }
        return all
    }

    fun retainFailure(stage: String) {
        capture("failure", emptyList(), frames.lastOrNull()).put("failureStage", stage)
    }

    private fun capture(label: String, targets: List<Rect>, frame: Frame?): JSONObject {
        check(label.matches(Regex("[a-z0-9-]+")))
        val windows = instrumentation.uiAutomation.windows
        val appWindow = windows.single { it.isActive && it.isFocused &&
            it.type == AccessibilityWindowInfo.TYPE_APPLICATION && it.root?.packageName?.toString() == PACKAGE }
        val viewport = credentialMain { Rect().also { activity.window.decorView.getWindowVisibleDisplayFrame(it) } }
        targets.forEach { target ->
            check(!target.isEmpty && viewport.contains(target))
            windows.filter { it.layer > appWindow.layer }.forEach { other ->
                check(!Rect.intersects(target, Rect().also { other.getBoundsInScreen(it) }))
            }
        }
        val bitmap = checkNotNull(instrumentation.uiAutomation.takeScreenshot())
        val width = bitmap.width
        val height = bitmap.height
        val file = File(output, "$label.png")
        try {
            check(bitmap.width.toLong() * bitmap.height <= 16_777_216 && bitmap.config != Bitmap.Config.HARDWARE)
            val display = Rect(0, 0, bitmap.width, bitmap.height)
            targets.forEach { bounds ->
                check(display.contains(bounds))
                val size = bounds.width().toLong() * bounds.height()
                check(size in 2L..1_048_576L)
                val pixels = IntArray(size.toInt())
                bitmap.getPixels(pixels, 0, bounds.width(), bounds.left, bounds.top, bounds.width(), bounds.height())
                check(pixels.any { it != pixels.first() }) { "Blank display target" }
            }
            check(file.createNewFile())
            file.outputStream().use { check(bitmap.compress(Bitmap.CompressFormat.PNG, 100, it)) }
        } finally { bitmap.recycle() }
        check(file.length() in 1L..16_777_216L)
        val tree = JSONArray(nodes().map { node ->
            JSONObject().put("text", node.text?.toString()).put("hint", node.hintText?.toString())
                .put("editable", node.isEditable).put("password", node.isPassword).put("visible", node.isVisibleToUser)
                .put("bounds", Rect().also { node.getBoundsInScreen(it) }.toShortString())
        })
        val treeFile = File(output, "$label-tree.json")
        check(treeFile.createNewFile())
        treeFile.writeText(tree.toString(2) + "\n")
        return JSONObject().put("label", label).put("elapsedNanos", SystemClock.elapsedRealtimeNanos())
            .put("frame", frame?.json()).put("pngSha256", credentialDigest(file.readBytes()))
            .put("width", width).put("height", height)
            .put("targets", JSONArray(targets.map { it.toShortString() })).also { captures.put(it) }
    }

    fun retire() {
        credentialMain {
            var failure: Throwable? = null
            frames.forEach { frame ->
                try { frame.retire() } catch (error: Throwable) { if (failure == null) failure = error }
            }
            try {
                check(activity.window.callback === callback)
                activity.window.callback = originalCallback
            } catch (error: Throwable) { if (failure == null) failure = error }
            failure?.let { throw it }
        }
    }

    class Frame(val label: String, private val observer: ViewTreeObserver) {
        val committed = AtomicLong()
        var armed = 0L
            private set
        private var registered = false
        private var armCount = 0
        private val callback = Runnable { committed.set(SystemClock.elapsedRealtimeNanos()) }
        fun arm() {
            check(observer.isAlive && (!registered || committed.get() != 0L))
            check(++armCount <= 1_000)
            committed.set(0)
            armed = SystemClock.elapsedRealtimeNanos()
            registered = true
            observer.registerFrameCommitCallback(callback)
        }
        fun retire() {
            if (registered && committed.get() == 0L) {
                check(observer.unregisterFrameCommitCallback(callback) || committed.get() != 0L)
            }
            registered = false
        }
        fun json(): JSONObject = JSONObject().put("label", label).put("armedElapsedNanos", armed)
            .put("committedElapsedNanos", committed.get()).put("armCount", armCount)
    }

    private data class Drawn(val text: String, val password: Boolean, val bounds: Rect)

    companion object {
        const val PACKAGE = "dev.p2pkit.sample.android"
        const val CARD_TITLE = "Join hotspot (WifiNetworkSpecifier)"
        const val PASSPHRASE_LABEL = "Passphrase (blank = open network)"
    }
}
