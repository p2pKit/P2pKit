package dev.p2pkit.core

import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow

/** Authenticated admission, never a substitute for proof of possession of the transport key. */
public enum class PeerAdmission {
    Trusted,
    EnrollmentOnly,
    Rejected,
}

/**
 * A live, non-blocking decision over an already authenticated identity. Implementations must use an
 * atomic snapshot: no storage, UI, network I/O or suspension in this callback. Exceptions fail closed.
 * EnrollmentOnly permits only the restricted binary channel, not general P2P/file-transfer use.
 * The application protocol must further restrict enrollment messages. Upgrades require a new session;
 * an enrolled session remains quarantined even after approval so it can deliver the approval notice.
 */
public fun interface PeerAdmissionController {
    public fun admission(identity: PeerIdentity): PeerAdmission
}

/**
 * Opt-in binary-only, authenticated session profile for bounded application protocols.
 * A null profile preserves ordinary P2P defaults, including inbound-only admission accounting.
 * This profile enforces both directions, strips file-transfer capabilities and shares [payloadBudget]
 * with its owning application protocol. It does not certify a device's connection capacity.
 */
public class P2pSessionProfile(
    public val admission: PeerAdmissionController,
    public val payloadBudget: PayloadBudget,
    public val maxTrustedSessions: Int,
    public val maxEnrollmentSessions: Int = 4,
    public val maxInboundHandshakes: Int = 16,
    public val maxApplicationBytes: Int = 1_048_576 + 4_096,
    public val maxQueuedMessagesPerSession: Int = 16,
    public val maxQueuedBytesPerSession: Long = 4L * 1_048_576,
    public val reconnect: BoundedReconnect = BoundedReconnect(),
) {
    init {
        require(maxTrustedSessions in 1..128)
        require(maxEnrollmentSessions in 0..4)
        require(maxInboundHandshakes in 1..16)
        require(maxApplicationBytes in 1..(1_048_576 + 4_096))
        require(maxQueuedMessagesPerSession in 1..64)
        require(maxQueuedBytesPerSession in 1..(8L * 1_048_576))
    }

    internal fun decide(identity: PeerIdentity): PeerAdmission = try {
        if (identity.fingerprint == null) PeerAdmission.Rejected else admission.admission(identity)
    } catch (_: Exception) {
        PeerAdmission.Rejected
    }
}

/** Additional bounds for the existing reconnect owner, not another reconnect loop. */
public class BoundedReconnect(
    public val windowMillis: Long = 30_000,
    public val initialDelayMillis: Long = 100,
    public val maximumDelayMillis: Long = 2_000,
) {
    init {
        require(windowMillis in 1..30_000)
        require(initialDelayMillis in 1..maximumDelayMillis)
        require(maximumDelayMillis <= 2_000)
    }
}

/**
 * Shared retained-payload accounting. Reserve BEFORE allocating/retaining a buffer and release its
 * lease only when the final owner is finished. CAS accounting is safe across Native/JVM callbacks.
 * This is a policy allowance, not a process RSS bound (OS buffers, thread stacks and application
 * object graphs are not measured). Failed reservations allocate no payload and never wait.
 */
public class PayloadBudget(public val capacityBytes: Long) {
    init {
        require(capacityBytes > 0)
    }

    private val retained = MutableStateFlow(0L)
    public val retainedBytes: StateFlow<Long> = retained.asStateFlow()

    public fun tryReserve(bytes: Long): PayloadLease? {
        require(bytes >= 0)
        while (true) {
            val current = retained.value
            if (bytes > capacityBytes - current) return null
            if (retained.compareAndSet(current, current + bytes)) return PayloadLease(bytes, this)
        }
    }

    internal fun release(bytes: Long) {
        while (true) {
            val current = retained.value
            check(current >= bytes) { "Payload accounting underflow" }
            if (retained.compareAndSet(current, current - bytes)) return
        }
    }
}

/** Idempotent release and downward-only ownership resizing; never holds the actual payload. */
public class PayloadLease internal constructor(
    bytes: Long,
    private val budget: PayloadBudget,
) {
    private val retained = MutableStateFlow(bytes)
    public val bytes: Long get() = retained.value.coerceAtLeast(0)

    /** Release unused encoding/scratch allowance after it becomes an actual retained payload. */
    public fun shrinkTo(bytes: Long): Boolean {
        require(bytes >= 0)
        while (true) {
            val current = retained.value
            if (current < 0) return false
            require(bytes <= current) { "A payload lease cannot grow" }
            if (retained.compareAndSet(current, bytes)) {
                budget.release(current - bytes)
                return true
            }
        }
    }

    public fun release() {
        while (true) {
            val current = retained.value
            if (current < 0) return
            if (retained.compareAndSet(current, -1)) {
                budget.release(current)
                return
            }
        }
    }
}

internal fun PayloadBudget.reserveOrThrow(bytes: Long): PayloadLease = tryReserve(bytes)
    ?: throw P2pError.ProtocolError("Shared retained-payload capacity exceeded")
