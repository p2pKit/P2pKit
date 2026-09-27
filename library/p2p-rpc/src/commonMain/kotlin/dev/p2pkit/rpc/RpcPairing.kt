package dev.p2pkit.rpc

import dev.p2pkit.core.PeerIdentity
import dev.p2pkit.core.PeerPairingQr
import dev.p2pkit.rpc.internal.EnrollmentGate
import dev.p2pkit.rpc.internal.RpcClock
import dev.p2pkit.rpc.internal.RpcLink
import dev.p2pkit.rpc.internal.WireKind
import dev.p2pkit.rpc.internal.WireMessage
import dev.p2pkit.rpc.internal.constantTimeSame
import dev.p2pkit.rpc.internal.newWireId
import dev.p2pkit.rpc.internal.parseHex
import dev.p2pkit.rpc.internal.secureRpcBytes
import dev.p2pkit.rpc.internal.toHex
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.NonCancellable
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext
import kotlinx.coroutines.withTimeoutOrNull
import kotlin.time.Duration
import kotlin.time.Duration.Companion.minutes

/** Invitation secret is deliberately excluded from toString/diagnostics. Display qr only in a trusted local UI. */
public class RpcInvitation internal constructor(
    internal val hostQr: String,
    internal val id: String,
    private val secret: ByteArray,
    public val endpoint: RpcEndpoint,
) {
    public val qr: String get() = "rpc1|$hostQr|$id|${secret.toHex()}|${endpoint.address}|${endpoint.port}"
    internal fun proof(): ByteArray = parseHex(id, 16) + secret
    override fun toString(): String = "RpcInvitation(redacted)"

    /** Best-effort zeroing of this object's secret when the local invitation UI is dismissed. */
    public fun clear() { secret.fill(0) }

    public companion object {
        /** Syntax only; pair() verifies AppId binding, numeric LAN policy, host pin and remote invitation validity. */
        public fun parse(qr: String): RpcInvitation {
            require(qr.length <= 512) { "Invalid RPC invitation" }
            val fields = qr.split('|')
            require(fields.size == 6 && fields[0] == "rpc1") { "Invalid RPC invitation" }
            require(PeerPairingQr.parseOrNull(fields[1]) != null) { "Invalid RPC host identity" }
            parseHex(fields[2], 16)
            val secret = parseHex(fields[3], 32)
            val port = fields[5].toIntOrNull() ?: throw IllegalArgumentException("Invalid RPC port")
            require(port.toString() == fields[5])
            return RpcInvitation(fields[1], fields[2], secret, RpcEndpoint(fields[4], port))
        }
    }
}

public class RpcPairingRequest internal constructor(
    public val id: String,
    public val peer: PeerIdentity,
    public val remainingMillis: Long,
) {
    override fun toString(): String = "RpcPairingRequest(redacted)"
}

/** Single-use, short-lived enrollment with explicit administrator approval and fresh subsequent authentication. */
public class RpcPairing internal constructor(
    private val scope: CoroutineScope,
    private val trust: RpcTrust,
    private val clock: RpcClock,
    private val gate: EnrollmentGate,
    private val incarnation: String,
    private val hostQr: String,
    private val endpoint: suspend () -> RpcEndpoint,
) {
    private class Entry(val id: String, val secret: ByteArray, val expiresAt: Long) {
        var link: RpcLink? = null
        var requestId: String? = null
        var approving = false
    }
    private val lock = Mutex()
    private var closed = false
    private val entries = mutableMapOf<String, Entry>()
    private val requests = MutableStateFlow<List<RpcPairingRequest>>(emptyList())
    public val pending: StateFlow<List<RpcPairingRequest>> = requests.asStateFlow()

    init {
        scope.launch {
            while (isActive) {
                delay(250)
                val expired = lock.withLock {
                    entries.values.filter { !it.approving && clock.now() >= it.expiresAt }.also { expired ->
                        expired.forEach { entries.remove(it.id); it.secret.fill(0) }
                        publish()
                    }
                }
                expired.forEach { entry ->
                    try { entry.link?.close() } catch (_: Exception) {
                        // Core retains incomplete cleanup; expiry still destroys admission material.
                    }
                }
            }
        }
    }

    @Throws(Exception::class)
    public suspend fun createInvitation(expiresIn: Duration = 2.minutes): RpcInvitation {
        require(expiresIn.inWholeMilliseconds in 1..120_000)
        val target = endpoint()
        return lock.withLock {
            if (closed) throw RpcFailure(RpcFailureKind.Closed, RpcFailurePhase.Trust)
            if (!trust.healthy || entries.size >= 4) throw RpcFailure(RpcFailureKind.Overloaded, RpcFailurePhase.Trust)
            val entry = Entry(newWireId(), secureRpcBytes(32), clock.now() + expiresIn.inWholeMilliseconds)
            entries[entry.id] = entry
            publish()
            RpcInvitation(hostQr, entry.id, entry.secret.copyOf(), target)
        }
    }

    internal suspend fun onRequest(link: RpcLink, message: WireMessage) {
        var accepted = false
        lock.withLock {
            val proof = checkNotNull(message.body).bytes
            val id = proof.copyOfRange(0, 16).toHex()
            val supplied = proof.copyOfRange(16, 48)
            try {
                val entry = entries[id]
                if (!closed && entry != null && clock.now() < entry.expiresAt &&
                    constantTimeSame(supplied, entry.secret) && trust.healthy &&
                    (entry.link == null || entry.link?.identity?.fingerprint == link.identity.fingerprint) &&
                    (!entry.approving || (entry.link === link && entry.requestId == message.id))
                ) {
                    entry.link = link // First valid proof binds the invitation to THIS authenticated identity.
                    entry.requestId = message.id
                    accepted = true
                    publish()
                }
            } finally { supplied.fill(0); proof.fill(0) }
        }
        val reply = WireMessage(if (accepted) WireKind.PairPending else WireKind.PairDenied, message.id, incarnation)
        val ticket = link.offer(reply, clock.now() + 1_000)
        if (!accepted) {
            withTimeoutOrNull(1_000) { ticket?.completion?.await() }
            link.close()
        }
    }

    /** Only the application administrator calls this after checking pending.peer in a trusted local UI. */
    @Throws(Exception::class)
    public suspend fun approve(id: String) {
        val entry = lock.withLock {
            val entry = entries[id]?.takeIf { !it.approving && it.link != null && clock.now() < it.expiresAt }
                ?: throw RpcFailure(RpcFailureKind.Unauthorized, RpcFailurePhase.Trust)
            entry.approving = true
            entry
        }
        withContext(NonCancellable) {
            val link = checkNotNull(entry.link)
            var completed = false
            try {
                pairingBoundary {
                    trust.approve(checkNotNull(link.identity.fingerprint))
                    // Old EnrollmentOnly admission cannot authorize in-place RPC.
                    val reply = WireMessage(WireKind.PairApproved, checkNotNull(entry.requestId), incarnation)
                    val ticket = link.offer(reply, clock.now() + 2_000)
                    withTimeoutOrNull(2_000) { ticket?.completion?.await() }
                }
                completed = true
            } finally {
                lock.withLock { entries.remove(id); entry.secret.fill(0); publish() }
                // Fresh full authentication is mandatory even if the approval notice was lost.
                closePreservingFailure(link, completed)
            }
        }
    }

    @Throws(Exception::class)
    public suspend fun reject(id: String) {
        val entry = lock.withLock {
            val entry = entries[id]?.takeIf { !it.approving } ?: return
            entries.remove(id)
            entry.secret.fill(0)
            publish()
            entry
        }
        withContext(NonCancellable) {
            entry.link?.let { link ->
                var completed = false
                try {
                    pairingBoundary {
                        val reply = WireMessage(WireKind.PairDenied, checkNotNull(entry.requestId), incarnation)
                        val ticket = link.offer(reply, clock.now() + 1_000)
                        withTimeoutOrNull(1_000) { ticket?.completion?.await() }
                    }
                    completed = true
                } finally { closePreservingFailure(link, completed) }
            }
        }
    }

    private suspend inline fun pairingBoundary(action: () -> Unit) {
        try { action() } catch (cancelled: CancellationException) {
            throw cancelled
        } catch (failure: RpcFailure) {
            throw failure
        } catch (_: Exception) {
            throw RpcFailure(RpcFailureKind.NotConnected, RpcFailurePhase.Trust)
        }
    }

    private suspend fun closePreservingFailure(link: RpcLink, actionCompleted: Boolean) {
        try { link.close() } catch (_: Exception) {
            if (actionCompleted) throw RpcFailure(RpcFailureKind.Closed, RpcFailurePhase.Trust)
            // Keep the original typed storage/transport failure or cancellation, not raw cleanup text.
        }
    }

    private fun publish() {
        gate.until.value = entries.values.maxOfOrNull { it.expiresAt } ?: 0
        requests.value = entries.values.mapNotNull { entry -> entry.link?.let {
            RpcPairingRequest(entry.id, it.identity, (entry.expiresAt - clock.now()).coerceAtLeast(0))
        } }
    }

    internal suspend fun close() = lock.withLock {
        closed = true
        entries.values.forEach { it.secret.fill(0) }
        entries.clear()
        publish()
    }
}
