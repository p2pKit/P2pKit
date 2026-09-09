package dev.p2pkit.sample.desktop

import java.io.BufferedReader
import java.util.concurrent.CountDownLatch
import java.util.concurrent.Executors
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicBoolean
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Job
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.suspendCancellableCoroutine

/** The hook requests cancellation; only the application owner executes teardown. */
internal fun runCliWithShutdownHook(block: suspend () -> Unit) {
    val owner = Job()
    val finished = CountDownLatch(1)
    val shutdownRequested = AtomicBoolean(false)
    val runtime = Runtime.getRuntime()
    val hook = Thread({
        shutdownRequested.set(true)
        owner.cancel(CancellationException("JVM shutdown requested"))
        // A broken cleanup must not hold process termination forever. A timeout
        // is explicitly incomplete cleanup, never a successful shutdown result.
        if (!finished.await(30, TimeUnit.SECONDS)) {
            System.err.println("[p2pkit ERROR] CLI shutdown exceeded 30s; cleanup is incomplete")
        }
    }, "p2pkit-cli-shutdown")
    runtime.addShutdownHook(hook)
    try {
        runBlocking(owner) { block() }
    } catch (cancelled: CancellationException) {
        if (!shutdownRequested.get()) throw cancelled
        // The JVM retains its native signal/exit status. Do not call System.exit
        // from either owner: it would wait recursively for this same hook.
    } finally {
        owner.cancel()
        finished.countDown()
        try {
            runtime.removeShutdownHook(hook)
        } catch (_: IllegalStateException) {
            // JVM shutdown already started; its hook observes finished above.
        }
    }
}

/** One on-demand read, with no prefetch or application work on the reader thread. */
internal class CliConsoleInput(private val reader: BufferedReader) : AutoCloseable {
    private val executor = Executors.newSingleThreadExecutor { task ->
        Thread(task, "p2pkit-cli-stdin").apply { isDaemon = true }
    }

    suspend fun readLine(): String? = suspendCancellableCoroutine { continuation ->
        val read = executor.submit {
            continuation.resumeWith(runCatching { reader.readLine() })
        }
        continuation.invokeOnCancellation { read.cancel(true) }
    }

    override fun close() {
        executor.shutdownNow()
        // OS stdin need not respond to interruption. Closing a BufferedReader
        // can itself wait for its read lock. Never close caller-owned stdin or
        // join this daemon: cancellation already prevents re-entry into the REPL,
        // and a blocked read cannot keep the terminating JVM alive.
    }
}
