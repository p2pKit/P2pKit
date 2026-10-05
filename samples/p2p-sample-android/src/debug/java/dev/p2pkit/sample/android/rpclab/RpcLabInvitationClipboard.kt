package dev.p2pkit.sample.android.rpclab

import android.content.ClipData
import android.content.ClipboardManager
import android.os.Handler
import android.os.Looper
import android.os.PersistableBundle
import android.os.SystemClock
import java.util.UUID

/** Foreground-only, explicit secret copy. Android cannot guarantee clipboard expiry after process death. */
internal class RpcLabInvitationClipboard(
    private val clipboard: ClipboardManager,
    private val clock: () -> Long = SystemClock::elapsedRealtime,
    private val schedule: (Long, () -> Unit) -> (() -> Unit) = { delay, action ->
        val handler = Handler(Looper.getMainLooper())
        val task = Runnable(action)
        handler.postDelayed(task, delay)
        val cancel: () -> Unit = { handler.removeCallbacks(task) }
        cancel
    },
    private val expired: () -> Unit = {},
) {
    private var invitation = ""
    private var deadline = 0L
    private var generation: UUID? = null
    private var copied: String? = null
    private var cancelExpiry: (() -> Unit)? = null

    /** Capture before minting, not when copying: copying must never extend the invitation's lifetime. */
    fun beginMinting(): Long { retire(); return clock() }

    fun minted(value: String, started: Long) {
        retire()
        require(value.isNotEmpty() && value.length <= 512 && started >= 0 && started <= clock())
        val remaining = LIFETIME_MILLIS - (clock() - started)
        if (remaining <= 0) { expired(); return }
        invitation = value
        deadline = started + LIFETIME_MILLIS
        val token = UUID.randomUUID()
        generation = token
        cancelExpiry = schedule(remaining) {
            if (generation == token) { retire(); expired() }
        }
    }

    fun copy(): Boolean {
        if (invitation.isEmpty() || clock() >= deadline) { retire(); return false }
        val token = UUID.randomUUID().toString()
        val clip = ClipData.newPlainText("One-use RPC invitation", invitation)
        clip.description.extras = PersistableBundle().apply {
            putBoolean("android.content.extra.IS_SENSITIVE", true)
            putString(OWNER_KEY, token)
        }
        return runCatching {
            clipboard.setPrimaryClip(clip)
            copied = token
            true
        }.getOrDefault(false)
    }

    /** Inspect only ownership metadata, never read or erase somebody else's clipboard text. */
    fun retire() {
        generation = null
        cancelExpiry?.invoke()
        cancelExpiry = null
        invitation = ""
        deadline = 0
        val token = copied
        copied = null
        if (token != null) runCatching {
            if (clipboard.primaryClipDescription?.extras?.getString(OWNER_KEY) == token) {
                if (android.os.Build.VERSION.SDK_INT >= 28) clipboard.clearPrimaryClip()
                else clipboard.setPrimaryClip(ClipData.newPlainText("", ""))
            }
        }
    }

    private companion object {
        const val OWNER_KEY = "dev.p2pkit.rpc.invitation-copy-owner"
        const val LIFETIME_MILLIS = 120_000L
    }
}
