package dev.p2pkit.rpc

import dev.p2pkit.core.ConnectionState
import dev.p2pkit.core.PeerIdentity
import kotlinx.coroutines.NonCancellable
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext

/** Closed confirms completed physical teardown; a transport's Closed state alone does not. */
public enum class RpcPhysicalSessionClosure { Open, Closing, Closed, Incomplete }

/**
 * SDK-owned capability for one authenticated incoming Host session lifetime. Compare instances by
 * identity. A reconnect creates a different capability, even with the same peer and generation 1.
 * Neither request identifiers nor discovery/monitoring metadata can construct this capability.
 *
 * Retaining it never follows a newer connection. No extra connection, worker or timer is allocated.
 * Physical closure does not revoke an application login, cancel host-owned business work, undo its
 * effects, or prove that committed output was not delivered. Revoke the application session as well.
 */
public class RpcPhysicalSession internal constructor(
    public val peer: PeerIdentity,
    public val generation: Long,
    private val transportState: StateFlow<ConnectionState>,
    close: suspend () -> Unit,
) {
    private val gate = Mutex()
    private val closureState = MutableStateFlow(RpcPhysicalSessionClosure.Open)
    private var closeAction: (suspend () -> Unit)? = close

    public val closure: StateFlow<RpcPhysicalSessionClosure> = closureState.asStateFlow()

    /** Observation only, not an atomic authorization/check-and-act or application-login fence. */
    public val isConnected: Boolean
        get() = closureState.value == RpcPhysicalSessionClosure.Open &&
            transportState.value == ConnectionState.Connected

    /**
     * Seal and await teardown of this exact physical session, never a fingerprint lookup. Successful
     * return confirms physical cleanup; failure sets Incomplete and propagates the original cause.
     * Repeated/concurrent calls observe the same underlying session's retained cleanup transaction;
     * they do not reset its deadline. A completed close is idempotent and releases its transport owner.
     * Safe inside authentication/authorization/handler callbacks: does not join the calling RPC worker.
     * Does not await host-owned handlers. Caller cancellation cannot interrupt owned physical cleanup;
     * if cancellation is reported on return, inspect closure to distinguish completed cleanup.
     */
    @Throws(Exception::class)
    public suspend fun close(): Unit = withContext(NonCancellable) {
        gate.withLock {
            val action = closeAction ?: return@withLock
            closureState.value = RpcPhysicalSessionClosure.Closing
            try {
                action()
                closeAction = null
                closureState.value = RpcPhysicalSessionClosure.Closed
            } catch (failure: Throwable) {
                closureState.value = RpcPhysicalSessionClosure.Incomplete
                throw failure
            }
        }
    }

    override fun toString(): String = "RpcPhysicalSession(identity omitted)"
}

/** Transport-authenticated facts captured before typed application authentication can suspend. */
public class RpcAuthenticationContext internal constructor(
    public val peer: PeerIdentity,
    public val physicalSession: RpcPhysicalSession,
) {
    override fun toString(): String = "RpcAuthenticationContext(identity omitted)"
}
