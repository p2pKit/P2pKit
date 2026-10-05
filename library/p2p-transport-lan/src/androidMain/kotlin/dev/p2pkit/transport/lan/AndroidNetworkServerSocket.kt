package dev.p2pkit.transport.lan

import android.net.Network
import java.io.FileDescriptor
import java.io.InputStream
import java.io.OutputStream
import java.net.Inet6Address
import java.net.InetAddress
import java.net.InetSocketAddress
import java.net.ServerSocket
import java.net.Socket
import java.net.SocketAddress
import java.net.SocketException

/**
 * The selected Network marks the unconnected descriptor BEFORE bind/listen. Linux TCP children inherit that
 * socket mark; they never use a process-default socket. Fresh Network/local/remote checks still gate each
 * accepted connection and all subsequent I/O. The ordinary (unrestricted) Java listener is unchanged.
 *
 * The primary constructor is an internal host-test seam. Production always supplies the non-null Network
 * through the secondary constructor; a null test binding can never satisfy organization-LAN admission.
 */
internal class AndroidNetworkServerSocket(
    val boundNetwork: Network?,
    private val ops: AndroidSocketOps,
    private val bindNetwork: (FileDescriptor) -> Unit,
) : ServerSocket() {
    constructor(network: Network) : this(network, AndroidOsSocketOps, network::bindSocket)

    private val resources = Any()
    private var handle: AndroidSocketHandle? = null
    private val pending = mutableSetOf<AndroidSocketHandle>()
    @Volatile private var closing = false
    @Volatile private var closed = false
    private var reuse = false
    private var endpoint: InetSocketAddress? = null

    override fun setReuseAddress(on: Boolean) = synchronized(resources) {
        checkOpen()
        handle?.use { ops.reuse(it, on) }
        reuse = on
    }
    override fun getReuseAddress(): Boolean = reuse
    override fun bind(endpoint: SocketAddress?) = bind(endpoint, 50)
    override fun bind(endpoint: SocketAddress?, backlog: Int) = synchronized(resources) {
        checkOpen()
        if (handle != null) throw SocketException("Listener already owns a descriptor")
        val address = endpoint as? InetSocketAddress ?: throw SocketException("Numeric listener address required")
        if (address.isUnresolved || address.address.isAnyLocalAddress) {
            throw SocketException("Explicit numeric listener address required")
        }
        val owned = AndroidSocketHandle(ops.open(address.address is Inet6Address), ops)
        handle = owned // Retain before any fallible Network/configuration/bind call.
        owned.use {
            bindNetwork(it)
            ops.reuse(it, reuse)
            ops.bind(it, address)
            ops.listen(it, if (backlog > 0) backlog else 50)
            this.endpoint = ops.local(it)
        }
    }

    override fun accept(): Socket {
        val listener = synchronized(resources) {
            checkOpen()
            if (endpoint == null) throw SocketException("Listener is not bound")
            checkNotNull(handle)
        }
        val accepted = listener.await { fd ->
            ops.accept(fd)?.let { child ->
                AndroidSocketHandle(child, ops).also { synchronized(resources) { pending += it } }
            }
        }
        try {
            val socket = accepted.use {
                ops.configureAccepted(it)
                AndroidNetworkSocket(accepted, ops, ops.local(it), ops.remote(it))
            }
            synchronized(resources) {
                checkOpen()
                check(pending.remove(accepted))
            }
            return socket
        } catch (failure: Throwable) {
            try { accepted.close(); synchronized(resources) { pending -= accepted } }
            catch (cleanup: Throwable) { failure.addSuppressed(cleanup) }
            throw failure
        }
    }

    override fun getLocalPort(): Int = endpoint?.port ?: -1
    override fun getInetAddress(): InetAddress? = endpoint?.address
    override fun getLocalSocketAddress(): SocketAddress? = endpoint
    override fun isBound(): Boolean = endpoint != null
    override fun isClosed(): Boolean = closed

    override fun close() {
        val listener = synchronized(resources) { closing = true; handle }
        val failures = mutableListOf<Throwable>()
        // No resources lock while draining accept's descriptor lease: it owns registration of any new child.
        try { listener?.close() } catch (failure: Throwable) { failures += failure }
        val children = synchronized(resources) { pending.toList() }
        children.forEach { child ->
            try { child.close(); synchronized(resources) { pending -= child } }
            catch (failure: Throwable) { failures += failure }
        }
        if (failures.isNotEmpty()) throw SocketException("Network listener cleanup failed").apply {
            initCause(failures.first())
            failures.drop(1).forEach(::addSuppressed)
        }
        super.close()
        closed = true
    }

    private fun checkOpen() { if (closing) throw SocketException("Listener closed") }
}

/** Minimal internal Socket surface consumed by AndroidRawConnection; owns one nonblocking descriptor. */
private class AndroidNetworkSocket(
    private val handle: AndroidSocketHandle,
    private val ops: AndroidSocketOps,
    private val local: InetSocketAddress,
    private val remote: InetSocketAddress,
) : Socket() {
    override fun getLocalAddress(): InetAddress = local.address
    override fun getInetAddress(): InetAddress = remote.address
    override fun getLocalPort(): Int = local.port
    override fun getPort(): Int = remote.port
    override fun getLocalSocketAddress(): SocketAddress = local
    override fun getRemoteSocketAddress(): SocketAddress = remote
    override fun isBound(): Boolean = true
    override fun isConnected(): Boolean = true
    override fun isClosed(): Boolean = handle.closed
    override fun setTcpNoDelay(on: Boolean) { handle.use { ops.noDelay(it, on) } }
    override fun close() { handle.close(); super.close() }

    override fun getInputStream(): InputStream = object : InputStream() {
        override fun read(): Int {
            val one = ByteArray(1)
            return if (read(one, 0, 1) < 0) -1 else one[0].toInt() and 0xff
        }
        override fun read(bytes: ByteArray, offset: Int, length: Int): Int {
            checkRange(bytes, offset, length)
            if (length == 0) return 0
            val count = handle.await { ops.read(it, bytes, offset, length) }
            return if (count == 0) -1 else count
        }
        override fun close() = this@AndroidNetworkSocket.close()
    }

    override fun getOutputStream(): OutputStream = object : OutputStream() {
        override fun write(value: Int) = write(byteArrayOf(value.toByte()), 0, 1)
        override fun write(bytes: ByteArray, offset: Int, length: Int) {
            checkRange(bytes, offset, length)
            var sent = 0
            while (sent < length) {
                val count = handle.await(writable = true) { ops.write(it, bytes, offset + sent, length - sent) }
                if (count <= 0) throw SocketException("Socket write made no progress")
                sent += count
            }
        }
        override fun close() = this@AndroidNetworkSocket.close()
    }

    private fun checkRange(bytes: ByteArray, offset: Int, length: Int) {
        if (offset < 0 || length < 0 || offset > bytes.size - length) throw IndexOutOfBoundsException()
    }
}
