package dev.p2pkit.sample.android.rpclab

import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue

/** One entry/session authority for toolbar, system and predictive Back. No timers or queued navigation. */
internal class RpcLabLeaveGate {
    enum class Phase { Active, Confirm, Cleaning, Failed, Left, Detached }
    class Token internal constructor()

    var phase by mutableStateOf(Phase.Active)
        private set
    private var pending: Token? = null

    /** Null consumes Back in place. Only an idle entry can skip confirmation, never its cleanup barrier. */
    fun request(foreground: Boolean, needsCleanup: Boolean): Token? {
        if (!foreground || phase != Phase.Active) return null
        if (needsCleanup) {
            phase = Phase.Confirm
            return null
        }
        return begin()
    }

    fun confirm(foreground: Boolean): Token? {
        if (!foreground || phase !in setOf(Phase.Confirm, Phase.Failed)) return null
        return begin()
    }

    fun stay() {
        if (phase == Phase.Confirm || phase == Phase.Failed) phase = Phase.Active
    }

    /** Cleanup completed in the background never queues an exit to replay on foreground. */
    fun complete(token: Token, succeeded: Boolean, foreground: Boolean): Boolean {
        if (pending !== token || phase != Phase.Cleaning) return false
        pending = null
        phase = when {
            !succeeded -> Phase.Failed
            foreground -> Phase.Left
            else -> Phase.Active
        }
        return phase == Phase.Left
    }

    fun detach() {
        pending = null
        phase = Phase.Detached
    }

    private fun begin(): Token {
        check(pending == null)
        phase = Phase.Cleaning
        return Token().also { pending = it }
    }
}
