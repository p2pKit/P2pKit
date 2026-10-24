package dev.p2pkit.transport.lan

import android.system.ErrnoException
import android.system.Os
import android.system.OsConstants
import android.system.StructPollfd
import java.io.FileDescriptor
import java.net.SocketException

/** Public API21+ socketpair/poll; no reflective FileDescriptor access, hidden API or per-socket thread. */
internal class AndroidSocketPoller private constructor() : SocketPoller<AndroidSocketHandle> {
    private val wakeRead = FileDescriptor()
    private val wakeWrite = FileDescriptor()
    private val wakeByte = byteArrayOf(1)
    private val drain = ByteArray(128)

    init {
        Os.socketpair(OsConstants.AF_UNIX,
            OsConstants.SOCK_DGRAM or ANDROID_SOCK_NONBLOCK or ANDROID_SOCK_CLOEXEC,
            0, wakeRead, wakeWrite)
    }

    override fun wakeup() {
        while (true) {
            try {
                // Linux MSG_NOSIGNAL, deliberately per send, never a process-wide signal change.
                Os.sendto(wakeWrite, wakeByte, 0, 1, 0x4000, null, 0)
                return
            } catch (failure: ErrnoException) {
                if (failure.errno == OsConstants.EAGAIN) return // A queued wake is already sticky.
                if (failure.errno != OsConstants.EINTR) throw failure
            }
        }
    }

    override fun select(interests: List<SocketInterest<AndroidSocketHandle>>): IntArray {
        val leases = mutableListOf<AndroidSocketHandle.PollLease?>()
        try {
            val result = IntArray(interests.size)
            var invalid = false
            val rows = arrayOfNulls<StructPollfd>(interests.size + 1)
            rows[0] = StructPollfd().apply { fd = wakeRead; events = OsConstants.POLLIN.toShort() }
            interests.forEachIndexed { index, interest ->
                val lease = interest.key.leaseForPoll()
                leases += lease
                rows[index + 1] = StructPollfd().apply {
                    fd = lease?.descriptor ?: FileDescriptor() // poll ignores fd=-1 for a closing owner.
                    events = ((if (interest.operations and READABLE != 0) OsConstants.POLLIN else 0) or
                        (if (interest.operations and WRITABLE != 0) OsConstants.POLLOUT else 0)).toShort()
                }
                if (lease == null) { invalid = true; result[index] = interest.operations }
            }
            try {
                // Normally wake-driven. A one-second safety ceiling also bounds a damaged wake channel.
                Os.poll(rows.requireNoNulls(), if (invalid) 0 else 1_000)
            } catch (failure: ErrnoException) {
                if (failure.errno != OsConstants.EINTR) throw failure
            }
            val wakeEvents = checkNotNull(rows[0]).revents.toInt()
            if (wakeEvents and (OsConstants.POLLERR or OsConstants.POLLHUP or OsConstants.POLLNVAL) != 0) {
                throw SocketException("Socket readiness wake channel failed")
            }
            if (wakeEvents and OsConstants.POLLIN != 0) drainWake()
            interests.forEachIndexed { index, interest ->
                val events = checkNotNull(rows[index + 1]).revents.toInt()
                if (events and OsConstants.POLLIN != 0) result[index] = result[index] or READABLE
                if (events and OsConstants.POLLOUT != 0) result[index] = result[index] or WRITABLE
                if (events and (OsConstants.POLLERR or OsConstants.POLLHUP or OsConstants.POLLNVAL) != 0) {
                    result[index] = interest.operations // Original leased read/write reports the socket error.
                }
            }
            return result
        } finally { leases.asReversed().forEach { it?.close() } }
    }

    private fun drainWake() {
        repeat(256) {
            try { Os.read(wakeRead, drain, 0, drain.size) } catch (failure: ErrnoException) {
                if (failure.errno == OsConstants.EAGAIN) return
                if (failure.errno != OsConstants.EINTR) throw failure
            }
        }
    }

    override fun close() {
        var failure: Throwable? = null
        for (fd in listOf(wakeWrite, wakeRead)) {
            try { Os.close(fd); check(!fd.valid()) } catch (error: Throwable) {
                if (failure == null) failure = error else failure.addSuppressed(error)
            }
        }
        failure?.let { throw it } // The shared owner retains failed retirement and refuses replacement.
    }

    companion object {
        val readiness = SocketReadiness("p2pkit-android-readiness", create = ::AndroidSocketPoller)
    }
}

// Linux socket UAPI values: the public OsConstants fields were added only in API29.
// Pass flags atomically to socketpair on API24-28 too; never set CLOEXEC after publication.
private const val ANDROID_SOCK_NONBLOCK = 0x800
private const val ANDROID_SOCK_CLOEXEC = 0x80000
