package dev.p2pkit.transport.lan

import java.io.IOException
import java.io.InputStream
import java.io.OutputStream
import java.net.InetAddress
import java.net.InetSocketAddress
import java.net.ServerSocket
import java.net.Socket
import java.net.SocketAddress
import java.net.SocketException
import java.net.SocketTimeoutException
import java.util.concurrent.CountDownLatch

internal class MacLanErrnos(values: IntArray) {
    init { require(values.size == 8 && values.all { it > 0 }) }
    private val values = values.copyOf()
    fun retry(error: Int): Boolean = error == values[0] || error == values[1] || error == values[2]
    fun connecting(error: Int): Boolean = error == values[3] || error == values[4] || error == values[2]
    fun interrupted(error: Int): Boolean = error == values[2]
}

internal fun macSocketError(operation: String, error: Int): IOException =
    SocketException("Scoped TCP $operation failed (errno=$error)")

/** A native close failure is terminal/quarantined, not a safe invitation to retry the descriptor number. */
internal interface JvmSocketCleanupEvidence { fun requireReleased() }

/** Allocations happen under the setup gate; no gate is held during a poll/read/write or close drain. */
internal class MacLanHandle(
    private val api: MacLanCalls,
    initial: Long = 0,
    private val retainFailure: (Throwable) -> Unit = {},
    private val released: () -> Unit = {},
) : JvmSocketCleanupEvidence {
    private val gate = Any()
    private val finished = CountDownLatch(1)
    @Volatile private var handle = initial
    @Volatile private var closing = false
    @Volatile private var cleanupFailure: Throwable? = null
    val isClosed: Boolean get() = closing

    fun setup(block: () -> Unit) = synchronized(gate) {
        checkOpen()
        block()
    }

    fun open(index: Int) = setup {
        check(handle == 0L)
        val output = LongArray(1)
        val error = api.open(index, output)
        handle = output[0] // Retain even an unsuccessful native open before throwing.
        if (error != 0) throw macSocketError("open", error)
        if (handle == 0L) throw IOException("Scoped TCP open returned no owned handle")
    }

    fun adopt(value: Long) = setup {
        check(handle == 0L)
        handle = value
    }

    fun value(): Long {
        checkOpen()
        return handle.takeIf { it != 0L } ?: throw SocketException("Scoped TCP socket is not open")
    }

    private fun checkOpen() { if (closing) throw SocketException("Scoped TCP socket is closed") }

    fun close() {
        val release = synchronized(gate) {
            if (closing) null else { closing = true; handle.also { handle = 0 } }
        }
        if (release != null) {
            try {
                if (release != 0L) {
                    val result = api.close(release)
                    if (result != 0) throw macSocketError("close; ownership quarantined", result)
                }
                released()
            } catch (failure: Throwable) { cleanupFailure = failure; retainFailure(failure) }
            finally { finished.countDown() }
        }
        requireReleased()
    }

    override fun requireReleased() {
        if (!closing) throw IOException("Scoped TCP cleanup was not requested")
        var interrupted = false
        while (true) {
            try { finished.await(); break } catch (_: InterruptedException) { interrupted = true }
        }
        if (interrupted) Thread.currentThread().interrupt()
        cleanupFailure?.let { throw it }
    }
}

internal class MacLanSocket(
    private val api: MacLanCalls,
    private val errors: MacLanErrnos,
    private val prepare: (InetAddress) -> Int,
    initial: Long = 0,
    initialIndex: Int = 0,
    private val retainFailure: (Throwable) -> Unit = {},
    private val released: () -> Unit = {},
    private val beforeConnect: (MacLanSocket, InetAddress) -> Unit = { _, _ -> },
) : Socket(), JvmSocketCleanupEvidence {
    private val owned = MacLanHandle(api, initial, retainFailure, released)
    @Volatile internal var interfaceIndex = initialIndex
        private set
    @Volatile private var local: InetSocketAddress? = null
    @Volatile private var remote: InetSocketAddress? = null
    @Volatile private var connected = false
    private var noDelay = false
    private var reuse = false

    internal fun retainAccepted(handle: Long) = owned.adopt(handle)

    internal fun adoptAccepted() {
        verifyScope()
        local = endpoint(0)
        remote = endpoint(1)
        connected = true
    }

    override fun bind(bindpoint: SocketAddress?) = owned.setup {
        if (local != null) throw SocketException("Scoped TCP socket is already bound")
        val address = numericEndpoint(bindpoint, allowZeroPort = true)
        interfaceIndex = prepare(address.address)
        owned.open(interfaceIndex)
        checkResult("reuse-address", api.option(owned.value(), 1, if (reuse) 1 else 0))
        checkResult("bind", api.bind(owned.value(), address.address.address, address.port))
        verifyScope()
        local = endpoint(0)
        if (local?.address != address.address || local?.port == 0) throw SocketException("Scoped TCP bind mismatch")
    }

    override fun connect(endpoint: SocketAddress?, timeout: Int) {
        require(timeout > 0) { "Scoped TCP connect requires its existing finite deadline" }
        if (local == null || connected) throw SocketException("Scoped TCP connect requires an unconnected bound socket")
        val destination = numericEndpoint(endpoint, allowZeroPort = false)
        val deadline = System.nanoTime() + timeout.toLong() * 1_000_000
        verifyScope()
        beforeConnect(this, destination.address)
        if (System.nanoTime() >= deadline) throw SocketTimeoutException("Scoped TCP connect deadline expired")
        val result = api.connect(owned.value(), destination.address.address, destination.port)
        if (result != 0 && !errors.connecting(result)) throw macSocketError("connect", result)
        if (result != 0) {
            while (true) {
                val remaining = deadline - System.nanoTime()
                if (remaining <= 0) throw SocketTimeoutException("Scoped TCP connect deadline expired")
                val ready = poll(true, minOf(100, ((remaining + 999_999) / 1_000_000).toInt()))
                if (!ready) continue
                val outcome = api.connected(owned.value())
                if (outcome == 0) break
                if (!errors.connecting(outcome)) throw macSocketError("connect completion", outcome)
            }
        }
        if (System.nanoTime() >= deadline) throw SocketTimeoutException("Scoped TCP connect deadline expired")
        verifyScope()
        val actual = this.endpoint(1)
        if (actual != destination) throw SocketException("Scoped TCP remote endpoint mismatch")
        remote = actual
        connected = true
    }

    override fun connect(endpoint: SocketAddress?) {
        throw SocketException("Scoped TCP connect requires an explicit finite deadline")
    }

    internal fun verifyScope(): Boolean {
        val result = IntArray(1)
        checkResult("scope readback", api.boundInterface(owned.value(), result))
        if (interfaceIndex <= 0 || result[0] != interfaceIndex) throw SocketException("Scoped TCP interface mismatch")
        return true
    }

    private fun endpoint(remote: Int): InetSocketAddress {
        val address = ByteArray(4)
        val port = IntArray(1)
        checkResult("endpoint readback", api.endpoint(owned.value(), remote, address, port))
        if (port[0] !in 1..65535) throw SocketException("Scoped TCP endpoint has no port")
        return InetSocketAddress(InetAddress.getByAddress(address), port[0])
    }

    private fun poll(writable: Boolean, timeout: Int = 100): Boolean {
        val ready = api.poll(owned.value(), if (writable) 1 else 0, timeout)
        if (ready < 0) {
            if (errors.interrupted(-ready)) return false
            throw macSocketError("poll", -ready)
        }
        if (ready !in 0..1) throw SocketException("Scoped TCP invalid poll result")
        return ready == 1
    }

    private val input = object : InputStream() {
        override fun read(): Int {
            val one = ByteArray(1)
            return if (read(one, 0, 1) < 0) -1 else one[0].toInt() and 0xff
        }
        override fun read(bytes: ByteArray, offset: Int, length: Int): Int {
            checkBounds(bytes, offset, length)
            if (length == 0) return 0
            if (!connected) throw SocketException("Scoped TCP socket is not connected")
            while (true) {
                val count = api.read(owned.value(), bytes, offset, minOf(length, 65536))
                if (count == 0) return -1
                if (count > 0) {
                    if (count > minOf(length, 65536)) throw SocketException("Scoped TCP invalid read count")
                    return count
                }
                if (!errors.retry(-count)) throw macSocketError("read", -count)
                poll(false)
            }
        }
        override fun close() = this@MacLanSocket.close()
    }
    private val output = object : OutputStream() {
        override fun write(value: Int) = write(byteArrayOf(value.toByte()), 0, 1)
        override fun write(bytes: ByteArray, offset: Int, length: Int) {
            checkBounds(bytes, offset, length)
            if (!connected) throw SocketException("Scoped TCP socket is not connected")
            var sent = 0
            while (sent < length) {
                val requested = minOf(length - sent, 65536)
                val count = api.write(owned.value(), bytes, offset + sent, requested)
                if (count > 0) {
                    if (count > requested) throw SocketException("Scoped TCP invalid write count")
                    sent += count
                } else if (count == 0) {
                    throw SocketException("Scoped TCP write made no progress")
                } else {
                    if (!errors.retry(-count)) throw macSocketError("write", -count)
                    poll(true) // The unchanged JvmRawConnection write watchdog owns the overall deadline.
                }
            }
        }
        override fun close() = this@MacLanSocket.close()
    }

    override fun getInputStream(): InputStream = input
    override fun getOutputStream(): OutputStream = output
    override fun setTcpNoDelay(on: Boolean) {
        checkResult("no-delay", api.option(owned.value(), 2, if (on) 1 else 0)); noDelay = on
    }
    override fun getTcpNoDelay(): Boolean = noDelay
    override fun setReuseAddress(on: Boolean) {
        if (local != null) checkResult("reuse-address", api.option(owned.value(), 1, if (on) 1 else 0))
        reuse = on
    }
    override fun getReuseAddress(): Boolean = reuse
    override fun getLocalAddress(): InetAddress = local?.address ?: InetAddress.getByAddress(ByteArray(4))
    override fun getInetAddress(): InetAddress? = remote?.address
    override fun getLocalPort(): Int = local?.port ?: -1
    override fun getPort(): Int = remote?.port ?: 0
    override fun getLocalSocketAddress(): SocketAddress? = local
    override fun getRemoteSocketAddress(): SocketAddress? = remote
    override fun isConnected(): Boolean = connected
    override fun isBound(): Boolean = local != null
    override fun isClosed(): Boolean = owned.isClosed
    override fun close() = owned.close()
    override fun requireReleased() = owned.requireReleased()
}

internal class MacLanServerSocket(
    private val api: MacLanCalls,
    private val errors: MacLanErrnos,
    private val prepare: (InetAddress) -> Int,
    private val retainFailure: (Throwable) -> Unit = {},
    private val released: () -> Unit = {},
    private val childFactory: ((Int) -> MacLanSocket)? = null,
) : ServerSocket() {
    private val owned = MacLanHandle(api, retainFailure = retainFailure)
    private var index = 0
    private var local: InetSocketAddress? = null
    private var reuse = false
    private val retainedChildren = mutableListOf<MacLanSocket>()
    // wait/notify coordinate native accept drain without holding I/O locks.
    @Suppress("PLATFORM_CLASS_MAPPED_TO_KOTLIN")
    private val acceptGate = Object()
    private var accepting = 0
    private var retiring = false

    override fun bind(endpoint: SocketAddress?, backlog: Int) = owned.setup {
        if (local != null) throw SocketException("Scoped TCP listener is already bound")
        val address = numericEndpoint(endpoint, allowZeroPort = true)
        index = prepare(address.address)
        owned.open(index)
        checkResult("reuse-address", api.option(owned.value(), 1, if (reuse) 1 else 0))
        checkResult("listener bind", api.bind(owned.value(), address.address.address, address.port))
        val scope = IntArray(1)
        checkResult("listener scope", api.boundInterface(owned.value(), scope))
        if (scope[0] != index) throw SocketException("Scoped TCP listener interface mismatch")
        checkResult("listen", api.listen(owned.value(), if (backlog <= 0) 50 else backlog))
        val ip = ByteArray(4); val port = IntArray(1)
        checkResult("listener endpoint", api.endpoint(owned.value(), 0, ip, port))
        if (!ip.contentEquals(address.address.address) || port[0] !in 1..65535) {
            throw SocketException("Scoped TCP listener bind mismatch")
        }
        local = InetSocketAddress(InetAddress.getByAddress(ip), port[0])
    }
    override fun bind(endpoint: SocketAddress?) = bind(endpoint, 50)

    override fun accept(): Socket {
        synchronized(acceptGate) {
            if (retiring || local == null) throw SocketException("Scoped TCP listener is not active")
            accepting++
        }
        try {
            while (true) {
                // All JVM holders/ledger storage exist BEFORE native accept can create an owned descriptor.
                val output = LongArray(1)
                val child = childFactory?.invoke(index) ?:
                    MacLanSocket(api, errors, prepare, initialIndex = index, retainFailure = retainFailure)
                synchronized(retainedChildren) { retainedChildren += child }
                var thrown: Throwable? = null
                val result = try { api.accept(owned.value(), output) }
                    catch (failure: Throwable) { thrown = failure; Int.MIN_VALUE }
                child.retainAccepted(output[0])
                try {
                    thrown?.let { throw it }
                    if (output[0] != 0L) {
                        if (result != 0) throw macSocketError("accepted child setup", result)
                        child.adoptAccepted()
                        synchronized(acceptGate) {
                            if (retiring) throw SocketException("Scoped TCP listener retired during accept")
                            synchronized(retainedChildren) { retainedChildren.remove(child) }
                            return child
                        }
                    }
                    if (result == 0) throw SocketException("Scoped TCP accept returned no child")
                    if (!errors.retry(result)) throw macSocketError("accept", result)
                    child.close()
                    synchronized(retainedChildren) { retainedChildren.remove(child) }
                } catch (failure: Throwable) {
                    try {
                        child.close()
                        synchronized(retainedChildren) { retainedChildren.remove(child) }
                    } catch (cleanup: Throwable) { if (cleanup !== failure) failure.addSuppressed(cleanup) }
                    throw failure
                }
                val ready = api.poll(owned.value(), 0, 100)
                if (ready < 0 && !errors.interrupted(-ready)) throw macSocketError("accept poll", -ready)
            }
        } finally {
            synchronized(acceptGate) { accepting--; acceptGate.notifyAll() }
        }
    }

    override fun close() {
        synchronized(acceptGate) { retiring = true }
        var failure: Throwable? = null
        try { owned.close() } catch (error: Throwable) { failure = error }
        var interrupted = false
        synchronized(acceptGate) {
            while (accepting != 0) {
                try { acceptGate.wait() } catch (_: InterruptedException) { interrupted = true }
            }
        }
        if (interrupted) Thread.currentThread().interrupt()
        val children = synchronized(retainedChildren) { retainedChildren.toList() }
        for (child in children) {
            try { child.close(); synchronized(retainedChildren) { retainedChildren.remove(child) } }
            catch (error: Throwable) {
                if (failure == null) failure = error else if (failure !== error) failure.addSuppressed(error)
            }
        }
        failure?.let { throw it }
        released()
    }
    override fun setReuseAddress(on: Boolean) { reuse = on }
    override fun getReuseAddress(): Boolean = reuse
    override fun getInetAddress(): InetAddress? = local?.address
    override fun getLocalPort(): Int = local?.port ?: -1
    override fun getLocalSocketAddress(): SocketAddress? = local
    override fun isBound(): Boolean = local != null
    override fun isClosed(): Boolean = owned.isClosed
}

private fun checkResult(operation: String, error: Int) { if (error != 0) throw macSocketError(operation, error) }
private fun checkBounds(bytes: ByteArray, offset: Int, length: Int) {
    if (offset < 0 || length < 0 || offset > bytes.size - length) throw IndexOutOfBoundsException("TCP buffer bounds")
}
private fun numericEndpoint(endpoint: SocketAddress?, allowZeroPort: Boolean): InetSocketAddress {
    val value = endpoint as? InetSocketAddress ?: throw SocketException("Scoped TCP requires a numeric endpoint")
    if (value.isUnresolved || value.address.address.size != 4 || value.address.isAnyLocalAddress ||
        value.port !in (if (allowZeroPort) 0 else 1)..65535
    ) throw SocketException("Scoped TCP requires a bound numeric IPv4 endpoint")
    return value
}
