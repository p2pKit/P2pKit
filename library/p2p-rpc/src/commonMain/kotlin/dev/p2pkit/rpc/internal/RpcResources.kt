package dev.p2pkit.rpc.internal

import dev.p2pkit.core.PayloadBudget
import dev.p2pkit.core.PayloadLease
import dev.p2pkit.rpc.RpcFailure
import dev.p2pkit.rpc.RpcFailureKind
import dev.p2pkit.rpc.RpcFailurePhase
import kotlinx.coroutines.flow.MutableStateFlow
import kotlin.time.TimeSource

internal fun interface RpcClock { fun now(): Long }

internal class MonotonicRpcClock : RpcClock {
    private val origin = TimeSource.Monotonic.markNow()
    override fun now(): Long = origin.elapsedNow().inWholeMilliseconds
}

/** One handle per owner. A final release drops the byte-array reference as well as its allowance. */
internal class OwnedBytes private constructor(private val storage: Storage) {
    private class Storage(bytes: ByteArray, val lease: PayloadLease) {
        val references = MutableStateFlow(1)
        val data = MutableStateFlow<ByteArray?>(bytes)
    }

    private val released = MutableStateFlow(false)
    val bytes: ByteArray get() {
        check(!released.value) { "Released payload handle" }
        return checkNotNull(storage.data.value)
    }
    val size: Int get() = bytes.size

    fun retain(): OwnedBytes {
        check(!released.value)
        while (true) {
            val current = storage.references.value
            check(current > 0)
            if (storage.references.compareAndSet(current, current + 1)) return OwnedBytes(storage)
        }
    }

    fun release() {
        if (!released.compareAndSet(false, true)) return
        while (true) {
            val current = storage.references.value
            check(current > 0)
            if (storage.references.compareAndSet(current, current - 1)) {
                if (current == 1) {
                    storage.data.value = null
                    storage.lease.release()
                }
                return
            }
        }
    }

    companion object {
        fun take(bytes: ByteArray, lease: PayloadLease): OwnedBytes = OwnedBytes(Storage(bytes, lease))
        fun copy(bytes: ByteArray, budget: PayloadBudget): OwnedBytes {
            val lease = budget.reserve(bytes.size.toLong() + 256)
            return try { take(bytes.copyOf(), lease) } catch (failure: Throwable) {
                lease.release()
                throw failure
            }
        }
    }
}

internal fun PayloadBudget.reserve(bytes: Long): PayloadLease = tryReserve(bytes)
    ?: throw RpcFailure(RpcFailureKind.Overloaded, RpcFailurePhase.Admission)

internal expect fun secureRpcBytes(size: Int): ByteArray

internal fun newWireId(): String = secureRpcBytes(16).toHex()
internal const val ZERO_ID: String = "00000000000000000000000000000000"

internal fun ByteArray.toHex(): String = buildString(size * 2) {
    for (byte in this@toHex) {
        val value = byte.toInt() and 255
        append("0123456789abcdef"[value ushr 4])
        append("0123456789abcdef"[value and 15])
    }
}

internal fun parseHex(text: String, size: Int): ByteArray {
    require(text.length == size * 2 && text.all { it in '0'..'9' || it in 'a'..'f' })
    return ByteArray(size) { index -> text.substring(index * 2, index * 2 + 2).toInt(16).toByte() }
}

internal fun constantTimeSame(left: ByteArray, right: ByteArray): Boolean {
    var difference = left.size xor right.size
    for (index in 0 until minOf(left.size, right.size)) {
        difference = difference or (left[index].toInt() xor right[index].toInt())
    }
    return difference == 0
}
