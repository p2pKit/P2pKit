package dev.p2pkit.transport.lan

import java.io.FileDescriptor
import java.net.InetSocketAddress
import java.net.SocketException
import java.util.concurrent.locks.ReentrantReadWriteLock
import kotlin.concurrent.read
import kotlin.concurrent.write

/** The operations are nonblocking. Null means retry after readiness, not EOF or successful completion. */
internal interface AndroidSocketOps {
    fun open(ipv6: Boolean): FileDescriptor
    fun configureAccepted(fd: FileDescriptor)
    fun bind(fd: FileDescriptor, address: InetSocketAddress)
    fun listen(fd: FileDescriptor, backlog: Int)
    fun accept(fd: FileDescriptor): FileDescriptor?
    fun local(fd: FileDescriptor): InetSocketAddress
    fun remote(fd: FileDescriptor): InetSocketAddress
    fun reuse(fd: FileDescriptor, enabled: Boolean)
    fun noDelay(fd: FileDescriptor, enabled: Boolean)
    fun read(fd: FileDescriptor, bytes: ByteArray, offset: Int, length: Int): Int?
    fun write(fd: FileDescriptor, bytes: ByteArray, offset: Int, length: Int): Int?
    fun poll(fd: FileDescriptor, writable: Boolean, timeoutMillis: Int)
    fun close(fd: FileDescriptor)
}

/**
 * Keep the descriptor alive across every syscall, including readiness waits. Closing gates new operations,
 * drains bounded polls, then closes once: no thread can accidentally use a recycled descriptor number.
 * This interval is a cancellation wake-up bound, not an extension of an RPC or transport deadline.
 */
internal class AndroidSocketHandle(private val fd: FileDescriptor, private val ops: AndroidSocketOps) {
    private val gate = ReentrantReadWriteLock(true)
    @Volatile private var closing = false
    @Volatile var closed = false
        private set

    fun <T> use(action: (FileDescriptor) -> T): T = gate.read {
        if (closing) throw SocketException("Socket closed")
        action(fd)
    }

    fun <T : Any> await(writable: Boolean = false, action: (FileDescriptor) -> T?): T {
        while (true) {
            use(action)?.let { return it }
            use { ops.poll(it, writable, 100) }
        }
    }

    fun close() {
        closing = true
        gate.write {
            if (!closed) {
                ops.close(fd)
                closed = true // A failed release stays owned and can be retried.
            }
        }
    }
}
