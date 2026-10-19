package dev.p2pkit.transport.lan

import android.os.ParcelFileDescriptor
import android.system.ErrnoException
import android.system.Os
import android.system.OsConstants
import android.system.StructPollfd
import java.io.FileDescriptor
import java.net.InetSocketAddress
import java.net.SocketException
import java.util.IdentityHashMap

/** Public Android APIs only: no reflection, hidden APIs, process binding, root, or interface-name exceptions. */
internal object AndroidOsSocketOps : AndroidSocketOps {
    // Strong ownership keeps ParcelFileDescriptor's finalizer from closing a leased socket.
    // Keys are the exact descriptor objects returned to AndroidSocketHandle, never descriptor numbers.
    private val owners = IdentityHashMap<FileDescriptor, ParcelFileDescriptor>()
    // Stable Linux/Android socket UAPI value, absent from the public OsConstants facade.
    // Suppress SIGPIPE per send, without changing the application's process-wide signal disposition.
    private const val MSG_NOSIGNAL = 0x4000
    private fun <T> checked(action: () -> T): T = try { action() } catch (failure: ErrnoException) {
        throw SocketException("Android socket operation failed (errno ${failure.errno})").apply { initCause(failure) }
    }

    private fun <T> ready(action: () -> T): T? = try { action() } catch (failure: ErrnoException) {
        if (failure.errno == OsConstants.EAGAIN || failure.errno == OsConstants.EINTR) null
        else throw SocketException("Android socket operation failed (errno ${failure.errno})")
            .apply { initCause(failure) }
    }

    private fun own(number: Int): FileDescriptor {
        if (number < 0) throw nativeFailure(number)
        val owner = try { ParcelFileDescriptor.adoptFd(number) } catch (failure: Throwable) {
            val result = AndroidNativeSockets.closeUnowned(number)
            if (result < 0) failure.addSuppressed(nativeFailure(result))
            throw failure
        }
        try {
            val fd = owner.fileDescriptor
            synchronized(owners) { check(owners.put(fd, owner) == null) }
            return fd
        } catch (failure: Throwable) {
            try { owner.close() } catch (cleanup: Throwable) { failure.addSuppressed(cleanup) }
            throw failure
        }
    }

    private fun number(fd: FileDescriptor): Int = synchronized(owners) {
        (owners[fd] ?: throw SocketException("Socket descriptor is not owned")).fd
    }

    private fun nativeFailure(result: Int): SocketException =
        SocketException("Android native socket operation failed (errno ${-result})")

    override fun open(ipv6: Boolean): FileDescriptor = own(AndroidNativeSockets.open(ipv6))

    override fun configureAccepted(fd: FileDescriptor) {
        // accept4 established both flags before publication, including on API24-29. Os.fcntlInt
        // is public only since API30; ParcelFileDescriptor.dup does not set CLOEXEC on older Android.
        val result = AndroidNativeSockets.verifyFlags(number(fd))
        if (result < 0) throw nativeFailure(result)
    }

    override fun bind(fd: FileDescriptor, address: InetSocketAddress) = checked {
        Os.bind(fd, address.address, address.port)
    }
    override fun listen(fd: FileDescriptor, backlog: Int) = checked { Os.listen(fd, backlog) }
    override fun accept(fd: FileDescriptor): FileDescriptor? {
        val result = AndroidNativeSockets.accept(number(fd))
        return if (result == -OsConstants.EAGAIN || result == -OsConstants.EINTR) null else own(result)
    }
    override fun local(fd: FileDescriptor): InetSocketAddress = checked { Os.getsockname(fd) as InetSocketAddress }
    override fun remote(fd: FileDescriptor): InetSocketAddress = checked { Os.getpeername(fd) as InetSocketAddress }
    override fun reuse(fd: FileDescriptor, enabled: Boolean) = checked {
        Os.setsockoptInt(fd, OsConstants.SOL_SOCKET, OsConstants.SO_REUSEADDR, if (enabled) 1 else 0)
    }
    override fun noDelay(fd: FileDescriptor, enabled: Boolean) = checked {
        Os.setsockoptInt(fd, OsConstants.IPPROTO_TCP, OsConstants.TCP_NODELAY, if (enabled) 1 else 0)
    }
    override fun read(fd: FileDescriptor, bytes: ByteArray, offset: Int, length: Int): Int? =
        ready { Os.read(fd, bytes, offset, length) }
    override fun write(fd: FileDescriptor, bytes: ByteArray, offset: Int, length: Int): Int? =
        ready { Os.sendto(fd, bytes, offset, length, MSG_NOSIGNAL, null, 0) }
    override fun poll(fd: FileDescriptor, writable: Boolean, timeoutMillis: Int) {
        ready {
            val row = StructPollfd().apply {
                this.fd = fd
                events = (if (writable) OsConstants.POLLOUT else OsConstants.POLLIN).toShort()
            }
            Os.poll(arrayOf(row), timeoutMillis)
            if (row.revents.toInt() and OsConstants.POLLNVAL != 0) throw SocketException("Invalid socket descriptor")
        }
    }
    override fun close(fd: FileDescriptor) = synchronized(owners) {
        val owner = owners[fd] ?: throw SocketException("Socket descriptor is not owned")
        owner.close() // Release through its Android owner (including fdsan); do not close a borrowed integer.
        check(!fd.valid()) { "Socket descriptor remained valid after close" }
        check(owners.remove(fd) === owner)
    }
}
