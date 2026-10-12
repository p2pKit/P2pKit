package dev.p2pkit.sample.desktop.ui

/** UI-thread admission reservation; stale ordinary Start actions cannot run behind the RPC section. */
internal class DesktopSampleRunAdmission {
    private var rpcOwner: Any? = null
    private var terminal = false
    val ordinaryAllowed: Boolean get() = !terminal && rpcOwner == null

    fun reserveRpc(ordinaryIdle: Boolean): Any? {
        if (terminal || !ordinaryIdle || rpcOwner != null) return null
        return Any().also { rpcOwner = it }
    }

    fun sealForTerminalExit() { terminal = true }

    /** Only a successful close of the exact entry may release its reservation. */
    fun releaseRpc(owner: Any): Boolean {
        if (rpcOwner !== owner) return false
        rpcOwner = null
        return true
    }
}
