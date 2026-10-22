package dev.p2pkit.sample.android.runtime

/** Test-only observations, not a claim that an unavailable capture has a unique security cause. */
internal data class LegacyCaptureState(
    val activity: Int,
    val window: Int,
    val view: Int,
    val taskId: Int,
    val width: Int,
    val height: Int,
    val points: List<Pair<Int, Int>>,
    val owned: Boolean,
    val attached: Boolean,
    val focused: Boolean,
    val secure: Boolean,
    val draws: Int,
)

internal data class LegacyCaptureObservation(
    val before: LegacyCaptureState,
    val after: LegacyCaptureState,
    val bitmapSize: Pair<Int, Int>?,
    val matches: List<Boolean>?,
)

internal fun checkLegacyCaptureState(state: LegacyCaptureState, secure: Boolean) {
    checkLegacyCapture(state.owned && state.attached && state.focused && state.secure == secure &&
        state.taskId >= 0 && state.width > 0 && state.height > 0 && state.draws > 0 &&
        state.points.size == 4 && state.points.distinct().size == 4,
        LegacyCaptureFailureCode.CAPTURE_STATE_INVALID)
}

private fun sameLegacyCaptureGeometry(first: LegacyCaptureState, second: LegacyCaptureState): Boolean =
    first.activity == second.activity && first.window == second.window && first.view == second.view &&
        first.taskId == second.taskId && first.width == second.width && first.height == second.height &&
        first.points == second.points

/** Allows only a provisional protected UNAVAILABLE observation; positives always need actual pixels. */
internal fun checkLegacyCaptureObservation(value: LegacyCaptureObservation, visible: Boolean) {
    checkLegacyCaptureState(value.before, secure = !visible)
    checkLegacyCaptureState(value.after, secure = !visible)
    checkLegacyCapture(sameLegacyCaptureGeometry(value.before, value.after),
        LegacyCaptureFailureCode.CAPTURE_STATE_INVALID)
    if (value.bitmapSize == null) {
        checkLegacyCapture(!visible, LegacyCaptureFailureCode.SCREENSHOT_UNAVAILABLE)
        checkLegacyCapture(value.matches == null, LegacyCaptureFailureCode.CAPTURE_STATE_INVALID)
    } else {
        val (width, height) = value.bitmapSize
        checkLegacyCapture(width > 0 && height > 0 &&
            value.before.points.all { (x, y) -> x in 0 until width && y in 0 until height },
            LegacyCaptureFailureCode.SAMPLE_OUTSIDE_SCREENSHOT)
        checkLegacyCapture(value.matches?.size == 4 && value.matches.all { it == visible },
            if (visible) LegacyCaptureFailureCode.POSITIVE_CONTROL_NOT_CAPTURED
            else LegacyCaptureFailureCode.SECURE_PATTERN_CAPTURED)
    }
}

/** Same-window positive -> protected -> positive. This never diagnoses a unique null-return cause. */
internal fun checkLegacyCaptureBracket(
    first: LegacyCaptureObservation,
    protected: LegacyCaptureObservation,
    closing: LegacyCaptureObservation,
) {
    checkLegacyCaptureObservation(first, visible = true)
    checkLegacyCaptureObservation(protected, visible = false)
    checkLegacyCaptureObservation(closing, visible = true)
    checkLegacyCapture(sameLegacyCaptureGeometry(first.before, protected.before) &&
        sameLegacyCaptureGeometry(first.before, closing.before) && first.bitmapSize == closing.bitmapSize &&
        (protected.bitmapSize == null || first.bitmapSize == protected.bitmapSize),
        LegacyCaptureFailureCode.CAPTURE_BRACKET_MISMATCH)
}
