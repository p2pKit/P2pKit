package dev.p2pkit.transport.lan

import android.system.ErrnoException
import android.system.Os
import android.system.OsConstants
import android.system.StructPollfd
import java.io.FileDescriptor
import java.net.InetSocketAddress
import java.net.SocketException

/** Public Android APIs only: no reflection, hidden APIs, process binding, root, or interface-name exceptions. */
internal object AndroidOsSocketOps : AndroidSocketOps {
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

    override fun open(ipv6: Boolean): FileDescriptor = checked {
        Os.socket(if (ipv6) OsConstants.AF_INET6 else OsConstants.AF_INET,
            OsConstants.SOCK_STREAM or OsConstants.SOCK_NONBLOCK or OsConstants.SOCK_CLOEXEC, OsConstants.IPPROTO_TCP)
    }

    override fun configureAccepted(fd: FileDescriptor) = checked {
        Os.fcntlInt(fd, OsConstants.F_SETFL, Os.fcntlInt(fd, OsConstants.F_GETFL, 0) or OsConstants.O_NONBLOCK)
        Os.fcntlInt(fd, OsConstants.F_SETFD, Os.fcntlInt(fd, OsConstants.F_GETFD, 0) or OsConstants.FD_CLOEXEC)
        Unit
    }

    override fun bind(fd: FileDescriptor, address: InetSocketAddress) = checked {
        Os.bind(fd, address.address, address.port)
    }
    override fun listen(fd: FileDescriptor, backlog: Int) = checked { Os.listen(fd, backlog) }
    override fun accept(fd: FileDescriptor): FileDescriptor? = ready { Os.accept(fd, InetSocketAddress(0)) }
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
    override fun close(fd: FileDescriptor) = checked { Os.close(fd) }
}
