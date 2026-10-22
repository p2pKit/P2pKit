package dev.p2pkit.sample.android.runtime

/** Fixed diagnostics only: no outcome relaxation or Android capture-policy inference. */
internal enum class LegacyCaptureFailureCode {
    OBSERVER_FLAGS_INVALID,
    INTERACTIVE_WINDOW_LIMIT_EXCEEDED,
    PRESENTATION_ADMISSION_TIMEOUT,
    PRESENTATION_STATS_UNAVAILABLE,
    PRESENTATION_FRAME_LIMIT_EXCEEDED,
    RECENTS_ADMISSION_TIMEOUT,
    RECENTS_TREE_LIMIT_EXCEEDED,
    NAVIGATION_ACTION_REJECTED,
    CAPTURE_STATE_INVALID,
    CAPTURE_BRACKET_MISMATCH,
    BITMAP_COPY_UNAVAILABLE,
    RECENTS_IMAGE_UNIFORM,
    BODY_DEADLINE_EXCEEDED,
    SCREENSHOT_UNAVAILABLE,
    OUTPUT_DIRECTORY_UNAVAILABLE,
    PNG_ENCODING_FAILED,
    SAMPLE_OUTSIDE_SCREENSHOT,
    POSITIVE_CONTROL_NOT_CAPTURED,
    SECURE_PATTERN_CAPTURED,
}

internal class LegacyCaptureFailure(val code: LegacyCaptureFailureCode) : IllegalStateException(code.name)

internal fun checkLegacyCapture(condition: Boolean, code: LegacyCaptureFailureCode) {
    if (!condition) throw LegacyCaptureFailure(code)
}

internal fun <T : Any> requireLegacyCaptureValue(value: T?, code: LegacyCaptureFailureCode): T =
    value ?: throw LegacyCaptureFailure(code)
