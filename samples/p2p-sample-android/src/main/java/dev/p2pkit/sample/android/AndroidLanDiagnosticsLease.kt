package dev.p2pkit.sample.android

import dev.p2pkit.transport.lan.AndroidLanDiag

/**
 * Temporarily enables the process-wide LAN diagnostics used by this sample.
 *
 * The first owner captures the host's settings. Overlapping owners keep the
 * diagnostics active until the last lease is released, at which point the
 * captured settings are restored. Each lease is safe to release repeatedly.
 */
internal class AndroidLanDiagnosticsLease private constructor(
    private val token: Any
) {
    private var released: Boolean = false

    @Synchronized
    fun release() {
        if (released) return
        released = true
        AndroidLanDiagnosticsOwnership.release(token)
    }

    companion object {
        fun acquire(): AndroidLanDiagnosticsLease =
            AndroidLanDiagnosticsLease(AndroidLanDiagnosticsOwnership.acquire())
    }
}

private object AndroidLanDiagnosticsOwnership {
    private data class PreviousState(
        val enabled: Boolean,
        val retainHistory: Boolean
    )

    private val activeTokens: MutableSet<Any> = mutableSetOf()
    private var previousState: PreviousState? = null

    @Synchronized
    fun acquire(): Any {
        if (activeTokens.isEmpty()) {
            previousState = PreviousState(
                enabled = AndroidLanDiag.enabled,
                retainHistory = AndroidLanDiag.retainHistory
            )
        }
        val token = Any()
        check(activeTokens.add(token))
        // Enable replay before logging so the first diagnostic cannot be lost.
        AndroidLanDiag.retainHistory = true
        AndroidLanDiag.enabled = true
        return token
    }

    @Synchronized
    fun release(token: Any) {
        if (!activeTokens.remove(token) || activeTokens.isNotEmpty()) return
        val previous = checkNotNull(previousState)
        previousState = null
        // Stop new sample diagnostics before dropping their replay. If the
        // host had diagnostics enabled, its original setting remains active.
        AndroidLanDiag.enabled = previous.enabled
        AndroidLanDiag.retainHistory = previous.retainHistory
    }
}
