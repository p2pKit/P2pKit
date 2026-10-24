package dev.p2pkit.transport.lan

import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.CoroutineStart
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import java.io.IOException

internal fun interface SocketPathWatch {
    fun close()
}

/**
 * One idle-path timer per transport, not per connection. Each cohort gets a NEW OS snapshot after
 * the cohort is selected, used only for this watchdog pass and never for admission or I/O. Those
 * checks continue to read the OS independently. Every original socket still has its own predicate.
 *
 * Removal fences callbacks under [gate]; a closed registration cannot affect a replacement socket.
 * The last removal cancels the job. A new epoch cannot start until the old snapshot worker exits,
 * including rapid close/reopen churn. There are no descriptors, threads or payload queues here.
 */
internal class SocketPathWatchdog<S>(
    private val scope: CoroutineScope,
    private val readSnapshot: () -> S,
) {
    private val gate = Any()
    private val members = linkedSetOf<Member>()
    private var job: Job? = null
    private var failure: Throwable? = null

    fun register(allowed: (S) -> Boolean, rejected: () -> Unit): SocketPathWatch = synchronized(gate) {
        failure?.let { throw IOException("Socket path watchdog failed", it) }
        check(scope.isActive) { "Socket path watchdog scope is retired" }
        Member(allowed, rejected).also { members += it; startIfNeeded() }
    }

    private inner class Member(val allowed: (S) -> Boolean, val rejected: () -> Unit) : SocketPathWatch {
        override fun close() {
            synchronized(gate) {
                members -= this
                if (members.isEmpty()) job?.cancel()
            }
        }
    }

    /** Called under gate. Publish ownership before even an Unconfined/test scope can execute. */
    private fun startIfNeeded() {
        if (job != null || members.isEmpty() || failure != null) return
        val worker = scope.launch(start = CoroutineStart.LAZY) {
            try {
                while (isActive) {
                    delay(250)
                    val batch = synchronized(gate) { members.toList() }
                    if (batch.isEmpty()) break
                    val snapshot = readSnapshot()
                    batch.forEach { member ->
                        synchronized(gate) {
                            if (member in members) {
                                val allowed = try { member.allowed(snapshot) } catch (_: Exception) { false }
                                if (!allowed) {
                                    members -= member
                                    member.rejected()
                                }
                            }
                        }
                    }
                    if (synchronized(gate) { members.isEmpty() }) break
                }
            } catch (cancelled: CancellationException) {
                if (isActive) synchronized(gate) { fail(cancelled) } else throw cancelled
            } catch (error: Throwable) {
                synchronized(gate) { fail(error) }
                if (error !is Exception) throw error
            }
        }
        job = worker
        worker.invokeOnCompletion {
            synchronized(gate) {
                if (job === worker) {
                    job = null
                    if (!scope.isActive && members.isNotEmpty()) fail(IOException("Socket path watchdog retired"))
                    else startIfNeeded()
                }
            }
        }
        worker.start()
    }

    private fun fail(error: Throwable) {
        failure = error
        val remaining = members.toList()
        members.clear()
        remaining.forEach { member ->
            try { member.rejected() } catch (cleanup: Throwable) { if (cleanup !== error) error.addSuppressed(cleanup) }
        }
    }
}
