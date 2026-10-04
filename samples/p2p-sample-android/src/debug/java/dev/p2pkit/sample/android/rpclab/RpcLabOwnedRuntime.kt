package dev.p2pkit.sample.android.rpclab

import dev.p2pkit.sample.rpc.RpcPhoneLab
import kotlinx.coroutines.Job
import kotlinx.coroutines.cancelAndJoin

/** Bound cleanup data, not an Activity-bound close callback. The active monitor is drained before retirement. */
internal class RpcLabOwnedRuntime(val lab: RpcPhoneLab, val mobileFiles: AndroidRpcCapacityFiles?) {
    @Volatile private var monitor: Job? = null
    @Volatile var mobileFailed: Boolean = false
        private set
    @Volatile private var mobileStopRequested = false

    fun bindMonitor(job: Job) {
        check(mobileFiles != null && monitor == null)
        monitor = job
    }

    fun failMobile() { if (mobileFiles != null) mobileFailed = true }
    fun approveMobileStop() { check(mobileFiles != null); mobileStopRequested = true }

    suspend fun close() {
        try {
            monitor?.cancelAndJoin()
            monitor = null
            lab.close()
            val files = mobileFiles ?: return
            val receipt = lab.mobileClosedRecord(!mobileFailed && mobileStopRequested)
            // A retry verifies the same receipt, never replaces an earlier result.
            val existing = files.read("closed.txt", optional = true)
            if (existing == null) files.publish("closed.txt", receipt) else check(existing == receipt)
        } catch (failure: Throwable) {
            failMobile()
            throw failure
        }
    }
}

/** Debug-lab-only process gate, including Activity destruction/recreation; never a global SDK scope. */
internal object RpcLabProcessRuntime {
    val owner = RpcLabRuntimeOwner<RpcLabOwnedRuntime>()
}
