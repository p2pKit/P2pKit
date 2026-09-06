package dev.p2pkit.sample.diagnostics

import java.io.InterruptedIOException
import java.nio.channels.ClosedByInterruptException
import java.util.concurrent.CancellationException

/** Shared presentation boundary for the sample clear buttons and CLI command. */
public object DiagnosticClearAction {
    public const val FAILURE_MESSAGE: String =
        "Could not clear diagnostic history. Memory was retained; some log files may already be cleared. " +
            "Stop active logging, check storage, and retry."

    /** Only storage failures are presented here; cancellation and callback failures propagate. */
    public fun confirm(clear: () -> Int, onCleared: (Int) -> Unit, onFailure: (String) -> Unit) {
        if (Thread.currentThread().isInterrupted) throw InterruptedException("Diagnostic clear was interrupted")
        val removed = try {
            clear()
        } catch (failure: Exception) {
            if (failure is CancellationException) throw failure
            if (failure is InterruptedException || failure is InterruptedIOException ||
                failure is ClosedByInterruptException
            ) {
                Thread.currentThread().interrupt()
                throw failure
            }
            if (Thread.currentThread().isInterrupted) throw failure
            // Do not expose filenames, operating-system error details or log contents.
            onFailure(FAILURE_MESSAGE)
            return
        }
        onCleared(removed)
    }
}
