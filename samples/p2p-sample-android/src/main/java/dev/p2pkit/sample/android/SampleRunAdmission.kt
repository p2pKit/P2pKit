package dev.p2pkit.sample.android

/** One sample LAN owner at a time, including a kit whose cleanup has not succeeded. */
internal data class SampleRunAdmission(
    val running: Boolean,
    val starting: Boolean,
    val stopping: Boolean,
    val cleanupPending: Boolean,
    val smokeBusy: Boolean,
    val roomOwnsKit: Boolean = false,
    val smokeOwnsKit: Boolean = false
) {
    // A retained room kit makes this action a cleanup retry, not a new acquisition.
    val canStartOrRetryCleanup: Boolean
        get() = !running && !starting && !stopping &&
            (roomOwnsKit || (!cleanupPending && !smokeBusy && !smokeOwnsKit))

    val canRunKmpSmoke: Boolean
        get() = !running && !starting && !stopping && !cleanupPending && !smokeBusy && !roomOwnsKit && !smokeOwnsKit

    val canRetryKmpCleanup: Boolean
        get() = smokeOwnsKit && !smokeBusy

    /** #376: a name configures a new room; it must never be required to retire an owned kit. */
    fun canUseStartAction(deviceName: String): Boolean =
        canStartOrRetryCleanup && (roomOwnsKit || deviceName.trim().isNotEmpty())
}
