package dev.p2pkit.sample.android

internal const val SAMPLE_OPEN_RPC_ACTION = "dev.p2pkit.sample.android.OPEN_RPC"

/** One fixed, non-secret navigation action; no payload, role selection, trust approval, or queued retries. */
internal class SampleRpcOpenRequest {
    private var pending = false

    fun offer(action: String?) {
        if (action == SAMPLE_OPEN_RPC_ACTION) pending = true
    }

    fun consume(resumed: Boolean, open: () -> Unit): Boolean {
        if (!resumed || !pending) return false
        pending = false // Consume before invoking; rejected admission never becomes a background retry.
        open()
        return true
    }
}
