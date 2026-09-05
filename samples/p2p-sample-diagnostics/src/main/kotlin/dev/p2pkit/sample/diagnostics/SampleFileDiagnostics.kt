package dev.p2pkit.sample.diagnostics

import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

/**
 * Keep ordinary sample-owned diagnostic reads out of uncaught-exception loggers.
 * Callers render failures as types on the console and may retain details in UI.
 * A failed optional reread after commit must not change the transfer's outcome.
 * Cancellation and fatal errors are deliberately not converted into results.
 */
public suspend fun <T> readSampleFileDiagnostic(read: () -> T): Result<T> = withContext(Dispatchers.IO) {
    try {
        Result.success(read())
    } catch (cancelled: CancellationException) {
        throw cancelled
    } catch (failure: Exception) {
        Result.failure(failure)
    }
}
