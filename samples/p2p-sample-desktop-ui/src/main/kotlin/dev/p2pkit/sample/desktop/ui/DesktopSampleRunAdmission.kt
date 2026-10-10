package dev.p2pkit.sample.desktop.ui

/** UI-thread admission reservation; stale ordinary Start actions cannot run behind the RPC section. */
internal class DesktopSampleRunAdmission {
    private var rpcOwner: Any? = null
    val ordinaryAllowed: Boolean get() = rpcOwner == null

    fun reserveRpc(ordinaryIdle: Boolean): Any? {
        if (!ordinaryIdle || rpcOwner != null) return null
        return Any().also { rpcOwner = it }
    }

    /** Only a successful close of the exact entry may release its reservation. */
    fun releaseRpc(owner: Any): Boolean {
        if (rpcOwner !== owner) return false
        rpcOwner = null
        return true
    }
}
