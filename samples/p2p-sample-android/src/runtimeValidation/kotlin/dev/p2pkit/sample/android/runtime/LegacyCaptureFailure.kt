package dev.p2pkit.sample.android.runtime

/** Fixed diagnostics only: no outcome relaxation or Android capture-policy inference. */
internal enum class LegacyCaptureFailureCode {
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
