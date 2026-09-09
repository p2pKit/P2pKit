package dev.p2pkit.core.internal

import java.util.concurrent.TimeUnit

internal actual fun pausePeerPublication() {
    var interrupted = false
    var remaining = PEER_PUBLICATION_PAUSE_NANOS
    val deadline = System.nanoTime() + remaining
    try {
        // Clear only this thread's pre-existing flag to permit a real pause;
        // restore it in finally rather than allocating an exception each time.
        interrupted = Thread.interrupted()
        while (remaining > 0L) {
            try {
                TimeUnit.NANOSECONDS.sleep(remaining)
                return
            } catch (_: InterruptedException) {
                // Sleep clears the flag. Retain it while finishing this short
                // monotonic pause so an interrupted waiter cannot hot-spin.
                interrupted = true
                remaining = deadline - System.nanoTime()
            }
        }
    } finally {
        if (interrupted) Thread.currentThread().interrupt()
    }
}
