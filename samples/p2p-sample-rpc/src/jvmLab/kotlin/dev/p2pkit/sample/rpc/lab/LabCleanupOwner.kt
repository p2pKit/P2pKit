package dev.p2pkit.sample.rpc.lab

/** One terminal physical cleanup attempt; neither a failure nor an in-flight attempt is closed. */
internal class LabCleanupOwner<T>(
    private val resources: Collection<T>,
    private val retire: (T) -> Unit,
    private val publishClosed: () -> Unit,
) {
    private sealed interface Outcome {
        data object Pending : Outcome
        data object Closing : Outcome
        data object Closed : Outcome
        class Failed(val failure: Throwable) : Outcome
    }

    private var outcome: Outcome = Outcome.Pending

    @Synchronized
    fun close() {
        when (val observed = outcome) {
            Outcome.Closed -> return
            is Outcome.Failed -> throw observed.failure
            Outcome.Closing -> error("Synthetic cleanup must not reenter its physical attempt")
            Outcome.Pending -> Unit
        }
        outcome = Outcome.Closing
        try {
            var failure: Throwable? = null
            for (resource in resources) {
                try {
                    retire(resource)
                } catch (caught: Throwable) {
                    // Keep draining independent resources without replacing the first failure.
                    val first = failure
                    if (first == null) failure = caught else if (first !== caught) first.addSuppressed(caught)
                }
            }
            failure?.let { throw it }
            publishClosed()
            outcome = Outcome.Closed
        } catch (failure: Throwable) {
            // Retrying already-destroyed vaults is unsafe. Preserve the exact failure for every caller.
            outcome = Outcome.Failed(failure)
            throw failure
        }
    }
}
