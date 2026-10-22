package dev.p2pkit.transport.lan

import dev.p2pkit.core.transport.RawConnection
import kotlinx.coroutines.flow.MutableStateFlow

/** Native socket/lease ownership before a raw connection is handed to the collector. */
internal class PendingInboundConnection(
    private val lease: SourceAdmissionLease,
    private val create: () -> RawConnection,
    private val closeSocket: () -> Unit
) {
    private val pending = MutableStateFlow(true)

    /** Non-suspending channel disposal. The platform callback retains uncertain native cleanup. */
    fun discard() {
        if (pending.compareAndSet(expect = true, update = false)) release()
    }

    fun claim(): RawConnection? {
        if (!pending.compareAndSet(expect = true, update = false)) return null
        return try {
            AdmissionControlledRawConnection(create(), lease)
        } catch (failure: Throwable) {
            try {
                release()
            } catch (cleanup: Throwable) {
                failure.addSuppressed(cleanup)
            }
            throw failure
        }
    }

    private fun release() {
        try {
            closeSocket()
        } finally {
            lease.release()
        }
    }
}
