package dev.p2pkit.transport.lan

import java.io.Closeable
import java.io.IOException
import java.nio.ByteBuffer

/** Loaded only by the source/hash/architecture-pinned Mac LAN loader. No class initializer loads code. */
internal object MacBonjourNative : MacBonjourCalls {
    external fun abi(): Int
    override external fun open(
        index: Int, operation: Int, profile: Int, name: ByteArray, port: Int, txt: ByteArray, output: LongArray,
    ): Int
    override external fun poll(handle: Long, timeout: Int, output: ByteArray): Int
    override external fun close(handle: Long): Int
}

internal interface MacBonjourCalls {
    fun open(
        index: Int, operation: Int, profile: Int, name: ByteArray, port: Int, txt: ByteArray, output: LongArray,
    ): Int
    fun poll(handle: Long, timeout: Int, output: ByteArray): Int
    fun close(handle: Long): Int
}

internal data class MacBonjourEvent(
    val kind: Int, val index: Int, val name: String, val port: Int, val txt: ByteArray,
)

/** Strict ABI parsing, separate from untrusted DNS TXT/protocol admission. No native pointers cross JNI. */
internal fun decodeMacBonjourEvent(bytes: ByteArray, expectedIndex: Int): MacBonjourEvent {
    require(bytes.size == 2048 && expectedIndex > 0)
    val input = ByteBuffer.wrap(bytes)
    val kind = input.int
    val error = input.int
    val index = input.int
    val port = input.int
    val nameLength = input.int
    val txtLength = input.int
    check(kind in 1..5 && index == expectedIndex && port in 0..65535)
    check(nameLength in 0..63 && txtLength in 0..1300)
    check(bytes.asSequence().drop(24 + nameLength + txtLength).all { it == 0.toByte() })
    if (kind == 5) {
        check(error != 0 && port == 0 && nameLength == 0 && txtLength == 0)
        throw IOException("Scoped Bonjour system error $error")
    }
    check(error == 0 && nameLength > 0)
    check(if (kind == 3) port > 0 else port == 0 && txtLength == 0)
    val name = bytes.decodeToString(24, 24 + nameLength, throwOnInvalidSequence = true)
    check(validDiscoveryPeerIdOrNull(name) != null)
    return MacBonjourEvent(kind, index, name, port, bytes.copyOfRange(24 + nameLength, 24 + nameLength + txtLength))
}

/** An inert owner exists BEFORE allocation. Serial access and native leases also guard close/poll races. */
internal class MacBonjourRef(private val api: MacBonjourCalls, private val index: Int) : Closeable {
    private var handle = 0L
    private var closed = false
    private var closeFailure: Throwable? = null
    private val output = ByteArray(2048)

    @Synchronized fun open(
        operation: Int, profile: Int, name: String = "", port: Int = 0, txt: ByteArray = byteArrayOf(),
    ) {
        check(!closed && handle == 0L)
        val encoded = name.encodeToByteArray(throwOnInvalidSequence = true)
        require(index > 0 && encoded.size <= 63 && txt.size <= 1300)
        val owned = LongArray(1)
        val result = try { api.open(index, operation, profile, encoded, port, txt, owned) }
        finally { handle = owned[0] }
        if (result != 0 || handle == 0L) throw IOException("Scoped Bonjour open failed ($result)")
    }

    @Synchronized fun poll(timeout: Int = 0): MacBonjourEvent? {
        check(!closed && handle != 0L)
        return when (val result = api.poll(handle, timeout, output)) {
            0 -> null
            1 -> decodeMacBonjourEvent(output, index)
            else -> throw IOException("Scoped Bonjour poll failed ($result)")
        }
    }

    @Synchronized override fun close() {
        closeFailure?.let { throw IOException("Scoped Bonjour ownership quarantined", it) }
        if (closed) return
        closed = true
        if (handle == 0L) return
        val result = try { api.close(handle) } catch (failure: Throwable) {
            closeFailure = failure
            throw failure
        }
        if (result != 0) {
            val failure = IOException("Scoped Bonjour close failed ($result)")
            closeFailure = failure
            throw failure
        }
        handle = 0L
    }
}
