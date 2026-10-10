package dev.p2pkit.transport.lan

import java.io.ByteArrayOutputStream
import java.util.concurrent.TimeUnit

/** Fixed-tool exit/output checks and owned-stream retirement, not descendant or pipe-EOF qualification. */
internal object MacLanVerificationCommand {
    fun collect(process: Process): String {
        val output = ByteArrayOutputStream()
        var failure: Throwable? = null
        var result: String? = null
        var interrupted = false
        try {
            process.outputStream.close()
            val stream = process.inputStream
            fun readAvailable() {
                // This is the sole reader of the actual JDK process pipe. Never wait for inherited writers/EOF.
                while (true) {
                    val available = stream.available()
                    if (available == 0) return
                    val count = minOf(available, 65_537 - output.size())
                    val bytes = stream.readNBytes(count)
                    check(bytes.size == count) { "Installed verifier output changed during bounded read" }
                    output.write(bytes)
                    check(output.size() <= 65_536) { "Installed native verifier output exceeds limit" }
                }
            }
            val deadline = System.nanoTime() + TimeUnit.SECONDS.toNanos(15)
            while (true) {
                readAvailable()
                val left = deadline - System.nanoTime()
                check(left > 0) { "Installed native verification timed out" }
                if (process.waitFor(minOf(left, TimeUnit.MILLISECONDS.toNanos(10)), TimeUnit.NANOSECONDS)) {
                    readAvailable()
                    break
                }
            }
            check(process.exitValue() == 0) { "Installed native verification failed" }
            result = output.toString(Charsets.UTF_8)
        } catch (problem: Throwable) {
            failure = problem
            if (problem is InterruptedException) interrupted = true
        } finally {
            // Preserve the original rejection and attempt all cleanup. No competing reader can hold close's lock.
            fun cleanup(action: () -> Unit) {
                try {
                    action()
                } catch (problem: Throwable) {
                    if (problem is InterruptedException) interrupted = true
                    if (failure == null) failure = problem else if (failure !== problem) failure.addSuppressed(problem)
                }
            }
            fun awaitExit(deadline: Long): Boolean {
                while (true) {
                    val left = deadline - System.nanoTime()
                    if (left <= 0) return false
                    try {
                        return process.waitFor(left, TimeUnit.NANOSECONDS)
                    } catch (_: InterruptedException) {
                        interrupted = true
                    }
                }
            }
            cleanup { if (process.isAlive) process.destroyForcibly() }
            cleanup {
                check(awaitExit(System.nanoTime() + TimeUnit.SECONDS.toNanos(5))) {
                    "Installed verifier process did not retire"
                }
            }
            cleanup { process.outputStream.close() }
            cleanup { process.inputStream.close() }
            cleanup { process.errorStream.close() }
            if (interrupted) Thread.currentThread().interrupt()
        }
        failure?.let { throw it }
        return checkNotNull(result)
    }
}
