package dev.p2pkit.transport.lan

import kotlinx.coroutines.NonCancellable
import kotlinx.coroutines.withContext

/** Register immediately after acquisition, before any start/await/assertion. Test-only. */
internal class TestResourceCleanup {
    private val retirements = mutableListOf<suspend () -> Unit>()

    fun own(retire: suspend () -> Unit) {
        retirements += retire
    }

    suspend fun retire(primary: Throwable?) = withContext(NonCancellable) {
        var failure = primary
        while (retirements.isNotEmpty()) {
            // A suspended close can finish another owned acquisition. Drain that
            // newly enrolled resource too, without mutating a live iterator.
            val retirement = retirements.removeAt(retirements.lastIndex)
            try {
                retirement()
            } catch (error: Throwable) {
                if (failure == null) failure = error else if (failure !== error) failure.addSuppressed(error)
            }
        }
        retirements.clear()
        if (primary == null) failure?.let { throw it }
    }
}

internal suspend fun <T> withTestResourceCleanup(block: suspend (TestResourceCleanup) -> T): T {
    val cleanup = TestResourceCleanup()
    var primary: Throwable? = null
    try {
        return block(cleanup)
    } catch (error: Throwable) {
        primary = error
        throw error
    } finally {
        cleanup.retire(primary)
    }
}
