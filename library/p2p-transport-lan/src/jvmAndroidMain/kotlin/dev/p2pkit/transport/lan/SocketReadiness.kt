package dev.p2pkit.transport.lan

import kotlinx.coroutines.CancellableContinuation
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.suspendCancellableCoroutine
import kotlinx.coroutines.yield
import java.io.IOException
import kotlin.coroutines.EmptyCoroutineContext
import kotlin.coroutines.resume
import kotlin.coroutines.resumeWithException

/** Internal byte-stream adapter. Null from a syscall means would-block; -1 from read means EOF. */
internal interface SuspendingSocketIo {
    suspend fun read(bytes: ByteArray): Int
    suspend fun write(bytes: ByteArray)
    fun close()
}

/** Native sockets keep their original owner; this interface does not expose or transfer descriptors. */
internal interface ReadinessSocket {
    fun asynchronousIo(): SuspendingSocketIo?
}

/** Nonblocking syscalls must not tell the scheduler that a worker is parked in blocking IO. */
internal object SocketIoWorkers {
    // Shared CPU workers, capped even on many-core desktops. Waiting releases the lane. Listener,
    // connect/setup and the legacy blocking test seam keep their separate IO dispatchers.
    val read = Dispatchers.Default.limitedParallelism(16)
    val write = Dispatchers.Default.limitedParallelism(16)
}

internal class ReadySocketIo<K : Any>(
    private val registration: SocketReadiness<K>.Registration,
    private val readNow: (ByteArray) -> Int?,
    private val writeNow: (ByteArray, Int, Int) -> Int?,
) : SuspendingSocketIo {
    override suspend fun read(bytes: ByteArray): Int {
        while (true) {
            registration.checkOpen()
            readNow(bytes)?.let { return it }
            registration.await(READABLE)
        }
    }

    override suspend fun write(bytes: ByteArray) {
        var offset = 0
        while (offset < bytes.size) {
            registration.checkOpen()
            // Bound each syscall and yield between chunks: one large writer cannot monopolize a worker.
            val length = minOf(bytes.size - offset, 65_536)
            val count = writeNow(bytes, offset, length)
            if (count == null) registration.await(WRITABLE)
            else {
                if (count !in 1..length) throw IOException("Invalid nonblocking socket write count")
                offset += count
                if (offset < bytes.size) yield()
            }
        }
    }

    override fun close() = registration.close()
}

internal const val READABLE = 1
internal const val WRITABLE = 2

internal data class SocketInterest<K : Any>(val key: K, val operations: Int)

/** Wake must be sticky through the next select and safe concurrently with select. No payload work here. */
internal interface SocketPoller<K : Any> {
    fun select(interests: List<SocketInterest<K>>): IntArray
    fun wakeup()
    fun close()
}

/**
 * One lazy, shared readiness thread per backend, NOT per transport, session or RPC client. There is
 * at most one read and one write waiter per owned socket, no payload queue or per-connection polling timer.
 * The last owner wakes, joins and closes the backend before release returns. Failed retirement is
 * retained, not silently replaced by another reactor. Socket ownership itself stays with the caller.
 */
internal class SocketReadiness<K : Any>(
    private val name: String,
    private val startThread: (Thread) -> Unit = { it.start() },
    private val create: () -> SocketPoller<K>,
) {
    private val lifecycle = Any()
    private var engine: Engine? = null
    private var startupFailure: Throwable? = null
    private var startupPoller: SocketPoller<K>? = null

    fun register(key: K): Registration = synchronized(lifecycle) {
        startupFailure?.let { throw IOException("Socket readiness startup failed", it) }
        val active = engine ?: startEngine()
        synchronized(active.lock) {
            active.failure?.let { throw IOException("Socket readiness backend failed", it) }
            check(!active.stopping)
            check(active.members.none { it.key == key }) { "Socket already has a readiness owner" }
            Registration(active, key).also { active.members.add(it) }
        }
    }

    /** No registration has escaped yet. Retain failed startup/cleanup, including Thread.start failure. */
    private fun startEngine(): Engine {
        try {
            val poller = create().also { startupPoller = it }
            val active = Engine(poller).also { engine = it }
            startThread(active.thread)
            startupPoller = null // Ownership moved to the engine, never dropped.
            return active
        } catch (error: Throwable) {
            startupFailure = error
            val active = engine
            if (active != null) {
                synchronized(active.lock) { active.failure = error; active.stopping = true; active.wakeup() }
                if (active.thread.state == Thread.State.NEW) active.retire() else join(active.thread)
                active.retirementFailure?.let { if (it !== error) error.addSuppressed(it) }
            } else {
                try { startupPoller?.close() } catch (cleanup: Throwable) { error.addSuppressed(cleanup) }
            }
            // A failed start is not silently replaced. The original object/failure stays owned here.
            throw IOException("Socket readiness startup failed", error)
        }
    }

    private fun join(thread: Thread) {
        var interrupted = false
        while (true) {
            try { thread.join(); break } catch (_: InterruptedException) { interrupted = true }
        }
        if (interrupted) Thread.currentThread().interrupt()
    }

    internal inner class Registration internal constructor(private val owner: Engine, internal val key: K) {
        internal var closed = false
        internal var reader: CancellableContinuation<Unit>? = null
        internal var writer: CancellableContinuation<Unit>? = null

        fun checkOpen() = synchronized(owner.lock) {
            if (closed) throw IOException("Socket readiness owner is closed")
            owner.failure?.let { throw IOException("Socket readiness backend failed", it) }
        }

        suspend fun await(operation: Int): Unit = suspendCancellableCoroutine { continuation ->
            try {
                synchronized(owner.lock) {
                    checkOpen()
                    if (operation == READABLE) {
                        check(reader == null) { "Concurrent socket readers are not supported" }
                        reader = continuation
                    } else {
                        check(operation == WRITABLE && writer == null) { "Concurrent socket writers" }
                        writer = continuation
                    }
                    // Register under the same lock as shutdown so a wake cannot target a retired backend.
                    owner.wakeup()
                }
                continuation.invokeOnCancellation {
                    synchronized(owner.lock) {
                        if (reader === continuation) { reader = null; owner.wakeup() }
                        if (writer === continuation) { writer = null; owner.wakeup() }
                    }
                }
            } catch (failure: Throwable) {
                synchronized(owner.lock) {
                    if (reader === continuation) reader = null
                    if (writer === continuation) writer = null
                }
                continuation.resumeWithException(failure)
            }
        }

        fun close() = synchronized(lifecycle) {
            val pending = synchronized(owner.lock) drain@ {
                if (closed) return@drain emptyList<CancellableContinuation<Unit>>()
                closed = true
                check(owner.members.remove(this))
                val waiters = listOfNotNull(reader, writer)
                reader = null
                writer = null
                if (owner.members.isEmpty()) owner.stopping = true
                owner.wakeup()
                waiters
            }
            pending.forEach { deliver(it, IOException("Socket closed during readiness wait")) }
            if (owner.stopping) {
                // No application continuation ever runs on this thread, including Unconfined collectors.
                join(owner.thread)
                owner.retirementFailure?.let { throw IOException("Socket readiness retirement failed", it) }
                if (engine === owner) engine = null
            }
        }
    }

    internal inner class Engine(val poller: SocketPoller<K>) {
        val lock = Any()
        val members = linkedSetOf<Registration>()
        var stopping = false
        var failure: Throwable? = null
        private var retired = false
        private var wakePending = false
        fun wakeup() {
            // Mutations are serialized by lock. One sticky signal is sufficient until select
            // returns and the next snapshot can include ALL of them. Sending one datagram per
            // waiter exhausts Darwin's wake queue (ENOBUFS) during a 256-connection burst.
            // Do not reinterpret that error as success: avoid redundant sends instead.
            if (!retired && !wakePending) try {
                poller.wakeup()
                wakePending = true
            } catch (error: Throwable) {
                // Native select has a finite failure ceiling. Never lose a registered continuation if
                // wakeup fails, and never report a healthy backend after that failure.
                failure = error
            }
        }
        @Volatile var retirementFailure: Throwable? = null
        val thread = Thread(::run, name).apply { isDaemon = true }

        private fun run() {
            try {
                while (true) {
                    val snapshot = synchronized(lock) {
                        if (stopping) null else {
                            failure?.let { throw it }
                            members.mapNotNull { member ->
                                val ops = (if (member.reader != null) READABLE else 0) or
                                    (if (member.writer != null) WRITABLE else 0)
                                if (ops == 0) null else Pending(member, member.reader, member.writer, ops)
                            }
                        }
                    } ?: break
                    val events = poller.select(snapshot.map { SocketInterest(it.member.key, it.operations) })
                    check(events.size == snapshot.size) { "Invalid readiness batch" }
                    val ready = synchronized(lock) {
                        // Even a mutation after the backend drained its wake is in the NEXT
                        // snapshot. Reset under the mutation lock only after select returned;
                        // a later mutation can then send another sticky signal without a lost wake.
                        wakePending = false
                        buildList {
                            snapshot.forEachIndexed { index, pending ->
                                val member = pending.member
                                if (events[index] and READABLE != 0 && pending.reader != null &&
                                    member.reader === pending.reader
                                ) { member.reader = null; add(pending.reader) }
                                if (events[index] and WRITABLE != 0 && pending.writer != null &&
                                    member.writer === pending.writer
                                ) { member.writer = null; add(pending.writer) }
                            }
                        }
                    }
                    ready.forEach { deliver(it, null) }
                }
            } catch (error: Throwable) {
                val pending = synchronized(lock) {
                    failure = error
                    members.flatMap { member ->
                        listOfNotNull(member.reader, member.writer).also { member.reader = null; member.writer = null }
                    }
                }
                pending.forEach { deliver(it, IOException("Socket readiness backend failed", error)) }
            } finally { retire() }
        }

        // Keep retirement out of inline nonlocal-return/finally paths. It must catch a backend close
        // failure on normal stop just as on select failure, without an uncaught worker exception.
        fun retire() = synchronized(lock) {
            retired = true
            try { poller.close() } catch (error: Throwable) { retirementFailure = error; failure = error }
        }
    }

    private inner class Pending(
        val member: Registration,
        val reader: CancellableContinuation<Unit>?,
        val writer: CancellableContinuation<Unit>?,
        val operations: Int,
    )

    private fun deliver(continuation: CancellableContinuation<Unit>, failure: Throwable?) {
        Dispatchers.Default.dispatch(EmptyCoroutineContext) {
            if (failure == null) continuation.resume(Unit) else continuation.resumeWithException(failure)
        }
    }
}
