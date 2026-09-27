package dev.p2pkit.rpc.internal

import dev.p2pkit.core.ConnectionState
import dev.p2pkit.core.P2pMessage
import dev.p2pkit.core.P2pSession
import dev.p2pkit.core.PayloadBudget
import dev.p2pkit.core.PayloadLease
import dev.p2pkit.core.PeerAdmission
import dev.p2pkit.core.PeerIdentity
import dev.p2pkit.core.SessionConnectionInfo
import dev.p2pkit.rpc.RpcFailure
import dev.p2pkit.rpc.RpcFailureKind
import dev.p2pkit.rpc.RpcFailurePhase
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.CoroutineStart
import kotlinx.coroutines.Job
import kotlinx.coroutines.NonCancellable
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.collect
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.Semaphore
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext

/** Internal seam for deterministic tests, never an injectable public transport/security bypass. */
internal interface RpcLink {
    val identity: PeerIdentity
    val admission: PeerAdmission
    val transportState: StateFlow<ConnectionState>
    val generation: StateFlow<SessionConnectionInfo>
    val failure: StateFlow<RpcFailureKind?>
    suspend fun offer(
        message: WireMessage,
        expiresAt: Long,
        notification: Boolean = false,
        onStart: () -> Unit = {},
    ): SendTicket?
    suspend fun close()
}

/** A cancelled QUEUED ticket can never be sent later. Once started, outcome is conservatively ambiguous. */
internal class SendTicket(
    val message: WireMessage,
    val expiresAt: Long,
    val generation: Long,
    val notification: Boolean,
    private val allowance: PayloadLease? = null,
    private val onStart: () -> Unit = {},
    private val onRelease: () -> Unit = {},
) {
    private val state = MutableStateFlow(0)
    val completion = CompletableDeferred<Boolean>()
    val started: Boolean get() = state.value in 1..2
    val bytes: Long = (message.body?.size ?: 0).toLong() + message.name.length + RpcWire.HEADER_BYTES

    fun begin(): Boolean {
        if (!state.compareAndSet(0, 1)) return false
        onStart()
        return true
    }

    fun cancelQueued(): Boolean {
        if (!state.compareAndSet(0, 3)) return false
        completion.complete(false)
        release()
        return true
    }

    fun finish(success: Boolean) {
        if (state.compareAndSet(1, 2)) {
            completion.complete(success)
            release()
        } else cancelQueued()
    }

    private fun release() {
        message.release()
        allowance?.release()
        onRelease()
    }
}

/** One reader and writer per existing P2P session; no alternate socket or reconnect implementation. */
internal class SessionRpcLink(
    private val session: P2pSession,
    parent: CoroutineScope,
    private val budget: PayloadBudget,
    private val notificationBudget: PayloadBudget,
    private val clock: RpcClock,
) : RpcLink {
    private val owner = SupervisorJob(parent.coroutineContext[Job])
    private val scope = CoroutineScope(parent.coroutineContext + owner)
    private val closed = MutableStateFlow(false)
    private val started = MutableStateFlow(false)
    private val lock = Mutex()
    private val closeLock = Mutex()
    private val priority = ArrayDeque<SendTicket>()
    private val notifications = ArrayDeque<SendTicket>()
    private var priorityBytes = 0L
    private var notificationBytes = 0L
    private val notificationEntries = Semaphore(16)
    private val peerNotificationBudget = PayloadBudget(128L * 1024)
    private val wake = Channel<Unit>(Channel.CONFLATED)
    private val failureState = MutableStateFlow<RpcFailureKind?>(null)
    override val failure: StateFlow<RpcFailureKind?> get() = failureState
    override val identity: PeerIdentity get() = session.peerIdentity
    override val admission: PeerAdmission get() = session.admission
    override val transportState: StateFlow<ConnectionState> get() = session.state
    override val generation: StateFlow<SessionConnectionInfo> get() = session.connectionInfo

    fun start(onMessage: suspend (WireMessage) -> Unit, onClosed: suspend () -> Unit) {
        check(started.compareAndSet(false, true))
        // UNDISPATCHED makes subscription part of construction, before HELLO/readiness/publication.
        scope.launch(start = CoroutineStart.UNDISPATCHED) {
            try {
                session.incoming.collect { raw ->
                    if (raw !is P2pMessage.Binary || raw.metadata.isNotEmpty() ||
                        raw.sizeBytes > RpcWire.MAX_PACKET_BYTES
                    ) throw RpcFailure(RpcFailureKind.Protocol, RpcFailurePhase.Decoding)
                    val lease = budget.reserve(raw.sizeBytes.toLong() + 512)
                    try {
                        val message = RpcWire.decode(raw.bytes, budget)
                        try { onMessage(message) } finally { message.release() }
                    } finally { lease.release() }
                }
            } catch (cancelled: CancellationException) {
                throw cancelled
            } catch (failure: Exception) {
                failureState.value = (failure as? RpcFailure)?.kind ?: RpcFailureKind.Protocol
            } finally {
                // A callback may throw CancellationException without cancelling this supervisor.
                // Never leave a connected but readerless link (or its queued payloads) behind.
                withContext(NonCancellable) { closeFromWorker() }
            }
        }
        scope.launch {
            try {
                for (ignored in wake) {
                    while (true) {
                        val item = lock.withLock {
                            when {
                                priority.isNotEmpty() -> priority.removeFirst().also { priorityBytes -= it.bytes }
                                notifications.isNotEmpty() -> notifications.removeFirst().also {
                                    notificationBytes -= it.bytes
                                }
                                else -> null
                            }
                        } ?: break
                        if (clock.now() >= item.expiresAt || session.state.value != ConnectionState.Connected ||
                            session.connectionInfo.value.generation != item.generation || !isActive
                        ) {
                            item.cancelQueued()
                            continue
                        }
                        if (!item.begin()) continue
                        var success = false
                        try {
                            val message = if (item.message.kind == WireKind.Invoke) item.message.copy(
                                budgetMillis = minOf(item.message.budgetMillis.toLong(), item.expiresAt - clock.now())
                                    .coerceAtLeast(1).toInt()
                            ) else item.message
                            val scratch = budget.reserve(2L * item.bytes + 1_024)
                            try {
                                session.sendAtGeneration(P2pMessage.Binary(RpcWire.encode(message)), item.generation)
                                success = true
                            } finally { scratch.release() }
                        } catch (cancelled: CancellationException) {
                            throw cancelled
                        } catch (_: Exception) {
                            // The existing session owns reconnection. RPC never launches another loop.
                        } finally { item.finish(success) }
                    }
                }
            } finally {
                withContext(NonCancellable) { closeFromWorker() }
            }
        }
        scope.launch(start = CoroutineStart.UNDISPATCHED) {
            try {
                session.state.collect { state ->
                    if (state == ConnectionState.Closed || state == ConnectionState.Failed) closeFromWorker()
                }
            } finally {
                withContext(NonCancellable) {
                    closeFromWorker()
                    try { onClosed() } catch (_: Exception) {
                        failureState.compareAndSet(null, RpcFailureKind.NotConnected)
                    }
                }
            }
        }
        owner.invokeOnCompletion { wake.cancel() }
    }

    private suspend fun closeFromWorker() {
        try { close() } catch (_: Exception) {
            // Explicit close/kit.stop retains the cleanup result. No platform text escapes an owned worker.
            failureState.compareAndSet(null, RpcFailureKind.NotConnected)
        }
    }

    override suspend fun offer(
        message: WireMessage,
        expiresAt: Long,
        notification: Boolean,
        onStart: () -> Unit,
    ): SendTicket? = lock.withLock {
        if (closed.value || session.state.value != ConnectionState.Connected || expiresAt <= clock.now()) {
            return@withLock null
        }
        val bytes = (message.body?.size ?: 0).toLong() + message.name.length + RpcWire.HEADER_BYTES
        val queue = if (notification) notifications else priority
        val used = if (notification) notificationBytes else priorityBytes
        val maximum = if (notification) 128L * 1024 else 4L * 1_048_576
        if (queue.size >= (if (notification) 16 else 32) || bytes > maximum - used) return@withLock null
        var allowance: PayloadLease? = null
        var peerAllowance: PayloadLease? = null
        if (notification) {
            if (!notificationEntries.tryAcquire()) return@withLock null
            peerAllowance = peerNotificationBudget.tryReserve(bytes)
            allowance = notificationBudget.tryReserve(bytes)
            if (peerAllowance == null || allowance == null) {
                peerAllowance?.release()
                allowance?.release()
                notificationEntries.release()
                return@withLock null
            }
        }
        val ticket = SendTicket(
            message.retained(), expiresAt, session.connectionInfo.value.generation, notification, allowance, onStart,
            onRelease = {
                peerAllowance?.release()
                if (notification) notificationEntries.release()
            },
        )
        queue.addLast(ticket)
        if (notification) notificationBytes += bytes else priorityBytes += bytes
        wake.trySend(Unit)
        ticket
    }

    override suspend fun close() {
        closed.value = true
        withContext(NonCancellable) {
            closeLock.withLock {
                lock.withLock {
                    priority.forEach { it.cancelQueued() }
                    notifications.forEach { it.cancelQueued() }
                    priority.clear()
                    notifications.clear()
                    priorityBytes = 0
                    notificationBytes = 0
                }
                // Repeated closes reobserve core's retained native cleanup instead of claiming
                // success solely because this facade was sealed by an earlier failed close.
                try { session.close() } finally { scope.cancel() }
            }
        }
    }
}
