package dev.p2pkit.rpc

import dev.p2pkit.core.PeerFingerprint
import dev.p2pkit.core.PeerIdentity
import dev.p2pkit.rpc.internal.RpcClock
import kotlinx.coroutines.NonCancellable
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext
import kotlin.time.Duration
import kotlin.time.Duration.Companion.milliseconds
import kotlin.time.TimeSource

/**
 * One application-verified login, bound to an authenticated device. RPC does not validate employee
 * credentials: the application must do so before returning a scope from registerScoped(). Reuse this
 * exact instance for that login; a later login needs a new instance, even with the same identifiers.
 * Identifiers are immutable metadata, not credentials, and must not contain bearer secrets.
 *
 * Revocation/expiry fence authorization admission, handler start and outbound commitment. They cannot
 * undo business effects or output already committed. No thread or transport is allocated per session.
 */
public class RpcApplicationSession private constructor(
    public val peer: PeerFingerprint,
    public val principal: String,
    public val sessionId: String,
    private val lifetime: Duration,
    private val age: () -> Duration,
) {
    public constructor(
        peer: PeerFingerprint,
        principal: String,
        sessionId: String,
        lifetime: Duration = Duration.INFINITE,
    ) : this(peer, principal, sessionId, lifetime, monotonicSessionAge())

    internal constructor(
        peer: PeerFingerprint, principal: String, sessionId: String, lifetime: Duration, clock: RpcClock,
    ) : this(peer, principal, sessionId, lifetime, clock.now().let { created ->
        { (clock.now() - created).milliseconds }
    })

    init {
        require(principal.isNotBlank() && validAuthorizationIdentifier(principal))
        require(sessionId.isNotBlank() && validAuthorizationIdentifier(sessionId))
        require(lifetime.isPositive()) { "Application-session lifetime must be positive" }
    }

    private val gate = Mutex()
    private val revoked = MutableStateFlow(false)

    /** Observation only; use revoke() and await it before an employee/policy transition. */
    public val isActive: Boolean get() = !revoked.value && age() < lifetime

    /**
     * Irreversible fence. If revocation wins before outbound commitment, that output cannot start.
     * Commitment is the owned writer's ticket-start transaction, not receipt or remote presentation.
     * Already committed output may finish after this returns; clear private presentation separately.
     * This method does not wait for network I/O or cancel an already-started business operation.
     * Use RpcHost.revokeApplicationSession() to also request cancellation of this host's owned work.
     */
    public suspend fun revoke(): Unit = withContext(NonCancellable) {
        gate.withLock { revoked.value = true }
    }

    // No application authorization callback or network I/O runs under this gate.
    internal suspend fun commit(action: () -> Boolean): Boolean = gate.withLock {
        if (isActive) action() else false
    }

    override fun toString(): String = "RpcApplicationSession(identifiers omitted)"
}

/**
 * Immutable authorization facts captured from a verified request. Resource is an application-defined,
 * bounded identifier, not the mutable current employee or a bearer credential. Retained outcomes,
 * control operations and queued output keep this exact original session/resource pair.
 */
public class RpcAuthorizationScope(
    public val session: RpcApplicationSession,
    public val resource: String = "",
) {
    init { require(validAuthorizationIdentifier(resource)) }
    override fun toString(): String = "RpcAuthorizationScope(authorization data omitted)"
}

/** Fresh policy checks distinguish execution/control from every kind of disclosure. */
public enum class RpcAuthorizationOperation {
    Invoke, Execute, Duplicate, Status, Cancel, Receipt,
    Success, ApplicationError, Failure, Running, Notification,
}

/**
 * Fresh authorization input. Peer comes from the authenticated transport; scope always comes from the
 * original application-authenticated request (or explicit notification), never a replacement login.
 * Applications must check current employee/session/resource permissions and credential expiry/disable.
 */
public class RpcAuthorizationContext internal constructor(
    public val peer: PeerIdentity,
    public val requestId: RpcRequestId,
    public val procedureName: String,
    public val procedureVersion: Int,
    public val hostIncarnation: String,
    public val scope: RpcAuthorizationScope,
    public val operation: RpcAuthorizationOperation,
) {
    override fun toString(): String = "RpcAuthorizationContext(authorization data omitted)"
}

private fun monotonicSessionAge(): () -> Duration {
    val created = TimeSource.Monotonic.markNow()
    return { created.elapsedNow() }
}

private fun validAuthorizationIdentifier(value: String): Boolean =
    value.length <= 256 && value.none { it < ' ' || it == '\u007f' }
