package dev.p2pkit.sample.android

import android.view.Window
import android.view.WindowManager

/**
 * API24–32 have no public task-snapshot-only opt-out. Keep this flag for the window's entire lifetime,
 * including foreground reveal and stop/reentry: clearing it on stop can race OS snapshot capture.
 * The deliberate legacy tradeoff also blocks foreground screenshots, recordings and insecure displays.
 */
internal fun secureLegacyTaskWindow(window: Window) {
    window.addFlags(WindowManager.LayoutParams.FLAG_SECURE)
}
