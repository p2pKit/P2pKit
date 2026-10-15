package dev.p2pkit.sample.android

import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow

/** Process admission, not an SDK singleton: exactly one ordinary owner or RPC section may acquire a run. */
internal class SampleProcessOwner {
    enum class Lane { Ordinary, RpcSection }
    class Token internal constructor(val lane: Lane)

    private val held = MutableStateFlow<Token?>(null)
    val state: StateFlow<Token?> = held.asStateFlow()

    @Synchronized
    fun acquire(lane: Lane, rpcRuntimeOccupied: () -> Boolean = { false }): Token? {
        if (held.value != null || (lane == Lane.Ordinary && rpcRuntimeOccupied())) return null
        return Token(lane).also { held.value = it }
    }

    @Synchronized
    fun release(token: Token): Boolean = held.compareAndSet(token, null)

    fun isCurrent(token: Token): Boolean = held.value === token

    /** Atomically bridge the UI reservation to the existing process-retained RPC creator. Never suspend here. */
    @Synchronized
    fun <T> withCurrent(token: Token, action: () -> T): T {
        check(held.value === token) { "The sample entry no longer owns process admission" }
        return action()
    }
}

internal typealias SampleRpcSectionToken = SampleProcessOwner.Token

internal object SampleProcessOwnership {
    val owner = SampleProcessOwner()
}
