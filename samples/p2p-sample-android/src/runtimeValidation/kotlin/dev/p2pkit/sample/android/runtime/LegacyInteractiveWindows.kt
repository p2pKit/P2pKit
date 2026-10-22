package dev.p2pkit.sample.android.runtime

/** Own only this instrumentation connection's flags; save before any possibly partial mutation. */
internal class LegacyInteractiveWindowFlags(
    private val read: () -> Int,
    private val write: (Int) -> Unit,
    requiredFlag: Int,
) {
    val original = read()
    val requested = original or requiredFlag

    fun enable(): Int {
        write(requested)
        return read().also { checkLegacyCapture(it == requested, LegacyCaptureFailureCode.OBSERVER_FLAGS_INVALID) }
    }

    fun restore(): Int {
        write(original)
        return read().also { checkLegacyCapture(it == original, LegacyCaptureFailureCode.OBSERVER_FLAGS_INVALID) }
    }
}

internal data class LegacyInteractiveWindow(
    val id: Int, val type: Int, val active: Boolean, val focused: Boolean, val bounds: List<Int>,
)

/** Match the actual View's ID, never the first window/title. Insets need not equal accessibility-root bounds. */
internal fun findLegacyInteractiveWindow(
    windows: List<LegacyInteractiveWindow>,
    id: Int,
    applicationType: Int,
    view: List<Int>,
    points: List<Pair<Int, Int>>,
): LegacyInteractiveWindow? {
    checkLegacyCapture(windows.size <= 256, LegacyCaptureFailureCode.INTERACTIVE_WINDOW_LIMIT_EXCEEDED)
    checkLegacyCapture(id >= 0 && view.size == 4 && view[0] < view[2] && view[1] < view[3],
        LegacyCaptureFailureCode.CAPTURE_STATE_INVALID)
    val matches = windows.filter { it.id == id }
    checkLegacyCapture(matches.size <= 1, LegacyCaptureFailureCode.CAPTURE_STATE_INVALID)
    val window = matches.singleOrNull() ?: return null
    if (window.type != applicationType || !window.active || !window.focused) return null
    val bounds = window.bounds
    if (bounds.size != 4 || bounds[0] > view[0] || bounds[1] > view[1] ||
        bounds[2] < view[2] || bounds[3] < view[3] ||
        points.any { (x, y) -> x !in bounds[0] until bounds[2] || y !in bounds[1] until bounds[3] }) return null
    return window
}
