package dev.p2pkit.sample.android.rpclab

import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock

/** A process-visible, token-bound creation and retirement gate. Failed cleanup never releases its exact owner. */
internal class RpcLabRuntimeOwner<T : Any> {
    internal class Token internal constructor()
    internal class Failure(val cause: Throwable)
    internal class Snapshot<T : Any> internal constructor(
        val token: Token,
        val creator: Job?,
        val current: T?,
        val failure: Failure? = null,
    )

    private val held = MutableStateFlow<Snapshot<T>?>(null)
    private val retirement = Mutex()
    val state: StateFlow<Snapshot<T>?> = held.asStateFlow()
    val occupied: Boolean get() = held.value != null
    val failure: Failure? get() = held.value?.failure

    fun snapshot(): Snapshot<T>? = held.value
    fun snapshotFor(token: Token?): Snapshot<T>? = held.value?.takeIf { it.token === token }
    fun current(token: Token): T? = held.value?.takeIf { it.token === token }?.current

    /** Called inside the creator, before its first factory/dispatcher boundary, with its actual coroutine Job. */
    fun beginCreation(action: Job): Token {
        val token = Token()
        check(held.compareAndSet(null, Snapshot(token, action, null))) { "A previous run still owns cleanup" }
        return token
    }

    fun retain(token: Token, value: T) {
        change(token) {
            check(it.creator != null && it.current == null && it.failure == null)
            Snapshot(token, it.creator, value)
        }
    }

    /** A successfully closed late result still reserves creation until this finally boundary completes. */
    fun finishCreation(token: Token) {
        change(token) {
            check(it.creator != null)
            if (it.current == null) {
                check(it.failure == null)
                null
            } else Snapshot(token, null, it.current, it.failure)
        }
    }

    /** Capture ONE snapshot BEFORE cancellation. A stale Stop has no authority over a replacement token. */
    suspend fun awaitCreation(observed: Snapshot<T>) {
        observed.creator?.join()
        held.value?.takeIf { it.token === observed.token }?.failure?.let {
            if (it !== observed.failure) throw it.cause
        }
    }

    /** The caller owns its existing NonCancellable barrier; no close deadline or native retry is changed. */
    suspend fun retire(token: Token, close: suspend (T) -> Unit): T? = retirement.withLock {
        val owned = current(token) ?: return@withLock null
        try {
            close(owned)
        } catch (failure: Throwable) {
            change(token) {
                check(it.current === owned)
                Snapshot(token, it.creator, owned, Failure(failure))
            }
            throw failure
        }
        change(token) {
            check(it.current === owned)
            if (it.creator == null) null else Snapshot(token, it.creator, null)
        }
        owned
    }

    private fun change(token: Token, transform: (Snapshot<T>) -> Snapshot<T>?) {
        while (true) {
            val before = checkNotNull(held.value) { "Creation token is no longer owned" }
            check(before.token === token) { "A stale callback cannot alter another run" }
            if (held.compareAndSet(before, transform(before))) return
        }
    }
}
