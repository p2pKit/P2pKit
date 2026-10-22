package dev.p2pkit.sample.android.runtime

/** Failure diagnostics only: this never admits a task card or changes an acceptance outcome. */
internal fun needsLegacyFailureScene(
    api: Int, stage: String, error: Throwable, completed: List<String>, recentsScreenshotRequested: Boolean,
): Boolean = api == 32 && stage == "actual-recents-original" &&
    (error as? LegacyCaptureFailure)?.code == LegacyCaptureFailureCode.RECENTS_ADMISSION_TIMEOUT &&
    completed == listOf("initial-secure-foreground") && !recentsScreenshotRequested

/** One additional diagnostic image, not an acceptance retry. All bitmap ownership stays in this call. */
internal fun <S : Any, B : Any> captureLegacyFailureScene(
    until: Long,
    now: () -> Long,
    state: () -> S,
    screenshot: () -> B?,
    retain: (B) -> Unit,
    recycle: (B) -> Unit,
) {
    fun bounded() = checkLegacyCapture(now() < until, LegacyCaptureFailureCode.BODY_DEADLINE_EXCEEDED)
    bounded()
    val before = state()
    bounded()
    val bitmap = screenshot()
    try {
        bounded()
        val after = state()
        bounded()
        checkLegacyCapture(before == after, LegacyCaptureFailureCode.CAPTURE_STATE_INVALID)
        retain(requireLegacyCaptureValue(bitmap, LegacyCaptureFailureCode.SCREENSHOT_UNAVAILABLE))
        bounded()
    } finally { bitmap?.let(recycle) }
}
