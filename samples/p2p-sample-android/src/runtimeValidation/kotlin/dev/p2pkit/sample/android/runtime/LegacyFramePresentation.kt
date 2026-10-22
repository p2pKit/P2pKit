package dev.p2pkit.sample.android.runtime

/** Timing observations only: they do not identify buffer contents or prove screenshot privacy. */
internal data class LegacyPresentedFrame(val index: Int, val posted: Long, val ready: Long, val presented: Long)

internal fun findLegacyPresentedFrame(
    frames: List<LegacyPresentedFrame>,
    invalidatedNano: Long,
    observedNano: Long,
): LegacyPresentedFrame? {
    checkLegacyCapture(frames.size <= 1024, LegacyCaptureFailureCode.PRESENTATION_FRAME_LIMIT_EXCEEDED)
    checkLegacyCapture(invalidatedNano > 0 && observedNano >= invalidatedNano,
        LegacyCaptureFailureCode.CAPTURE_STATE_INVALID)
    // Posted is producer-set (possibly desired vsync); ready is NOT proof of presentation.
    // -1/zero/future/unsignaled timestamps cannot pass. The actual pixel oracle remains mandatory.
    return frames.firstOrNull { it.presented in invalidatedNano..observedNano }
}

/** Clear and redraw exactly once; only observation is polled, within the caller's original deadline. */
internal fun <T : Any> awaitLegacyPresentation(
    until: Long,
    now: () -> Long,
    clear: () -> Boolean,
    redraw: () -> Unit,
    observe: () -> T?,
    pause: () -> Unit,
): T {
    fun bounded() = checkLegacyCapture(now() <= until, LegacyCaptureFailureCode.PRESENTATION_ADMISSION_TIMEOUT)
    bounded()
    checkLegacyCapture(clear(), LegacyCaptureFailureCode.PRESENTATION_STATS_UNAVAILABLE)
    bounded()
    redraw()
    bounded()
    while (true) {
        bounded()
        val observed = observe()
        bounded()
        if (observed != null) return observed
        pause()
    }
}

/** Accessibility-event quietness only, not compositor/animation completion or pixel identity. */
internal fun awaitLegacyAccessibilityIdle(
    until: Long,
    now: () -> Long,
    wait: (started: Long, maximumWait: Long) -> Unit,
): Long {
    val started = now()
    val remaining = until - started
    checkLegacyCapture(remaining > 0, LegacyCaptureFailureCode.PRESENTATION_ADMISSION_TIMEOUT)
    wait(started, remaining)
    // API24 may finish an idle-interval wait before rechecking its global timeout. Never accept a late return.
    return now().also { checkLegacyCapture(it <= until, LegacyCaptureFailureCode.PRESENTATION_ADMISSION_TIMEOUT) }
}
