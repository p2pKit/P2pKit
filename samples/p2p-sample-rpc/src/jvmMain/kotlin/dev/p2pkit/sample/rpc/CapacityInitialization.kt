package dev.p2pkit.sample.rpc

import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.coroutines.withTimeout

internal const val INITIALIZATION_CALLS_PER_CLIENT = 600
internal const val INITIALIZATION_PERIOD_NANOS = 100_000_000L
internal const val INITIALIZATION_TIMEOUT_MILLIS = 120_000L

/**
 * A fixed, separately accounted initialization, never a capacity measurement.
 * Exercise the actual RPC/codec/crypto paths, not just connection setup. Each
 * client awaits its reply before starting its next call; there are no discarded
 * slots, retries, adaptive repetitions or catch-up bursts. Any call failure
 * cancels this phase and prevents the unchanged full steady-state experiment.
 */
internal suspend fun initializeCapacityPaths(
    call: suspend (Int) -> Unit,
    nowNanos: () -> Long = System::nanoTime,
) = withTimeout(INITIALIZATION_TIMEOUT_MILLIS) {
    coroutineScope {
        repeat(RpcCapacityContract.CLIENTS) { index ->
            launch {
                repeat(INITIALIZATION_CALLS_PER_CLIENT) {
                    val started = nowNanos()
                    call(index)
                    val remaining = INITIALIZATION_PERIOD_NANOS - (nowNanos() - started)
                    if (remaining > 0) delay((remaining + 999_999) / 1_000_000)
                }
            }
        }
    }
}
