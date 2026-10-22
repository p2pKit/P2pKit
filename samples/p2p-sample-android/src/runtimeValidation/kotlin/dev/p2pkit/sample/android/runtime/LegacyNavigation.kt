package dev.p2pkit.sample.android.runtime

import android.accessibilityservice.AccessibilityService

/** Closed, public system actions; a true request result never proves navigation completed. */
internal enum class LegacyNavigationAction(val platformAction: Int) {
    HOME(AccessibilityService.GLOBAL_ACTION_HOME),
    RECENTS(AccessibilityService.GLOBAL_ACTION_RECENTS),
}

/** Exactly one request, no fallback. Retain an actual false result before failing its caller. */
internal fun requestLegacyNavigation(
    action: LegacyNavigationAction,
    perform: (Int) -> Boolean,
    returned: (Boolean) -> Unit,
) {
    val accepted = perform(action.platformAction)
    returned(accepted)
    checkLegacyCapture(accepted, LegacyCaptureFailureCode.NAVIGATION_ACTION_REJECTED)
}
