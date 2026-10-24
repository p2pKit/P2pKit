package dev.p2pkit.transport.lan

import dev.p2pkit.core.transport.OutboundRoute
import dev.p2pkit.core.transport.OutboundRouteConnection
import dev.p2pkit.core.transport.RawConnection
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.currentCoroutineContext
import kotlinx.coroutines.ensureActive

/** Copied numeric address, never a hostname or a native endpoint lease. Scope participates in identity. */
internal class LanNumericAddress private constructor(
    private val octets: ByteArray,
    val scopeId: Int
) {
    fun copyBytes(): ByteArray = octets.copyOf()

    override fun equals(other: Any?): Boolean = other is LanNumericAddress &&
        scopeId == other.scopeId && octets.contentEquals(other.octets)

    override fun hashCode(): Int = 31 * octets.contentHashCode() + scopeId

    companion object {
        fun copyOf(bytes: ByteArray, scopeId: Int = 0): LanNumericAddress? {
            val copied = bytes.copyOf()
            if (copied.size != 4 && copied.size != 16 || scopeId < 0) return null
            if (copied.size == 4 && scopeId != 0 || copied.all { it == 0.toByte() }) return null
            val first = copied[0].toInt() and 0xff
            if (copied.size == 4 && first >= 224 || copied.size == 16 && first == 255) return null
            // A link-local destination without its interface cannot be replayed safely.
            if (copied.size == 16 && first == 254 && (copied[1].toInt() and 0xc0) == 0x80 && scopeId == 0) {
                return null
            }
            return LanNumericAddress(copied, scopeId)
        }
    }
}

internal data class LanTcpEndpoint(val address: LanNumericAddress, val port: Int) {
    init {
        require(port in 1..65_535)
    }
}

/** Only Apple needs late binding: its raw wrapper starts before the effective endpoint is observable. */
internal class LanOutboundRouteConnection(
    private val delegate: RawConnection,
    override val outboundRoute: OutboundRoute
) : RawConnection by delegate, OutboundRouteConnection

/** An exact route failed a local admission/readback check; safe fallback still requires observed cleanup. */
internal class LanRouteRejected(message: String) : Exception(message)

/** Cancellation that wins during blocking I/O or noncancellable cleanup must never become fallback permission. */
internal suspend fun rethrowRouteCancellation(failure: Throwable, cleanupFailure: Throwable?) {
    if (failure is CancellationException) return // Preserve the original cancellation in the caller's catch.
    try {
        currentCoroutineContext().ensureActive()
    } catch (cancelled: CancellationException) {
        cancelled.addSuppressed(failure)
        cleanupFailure?.let(cancelled::addSuppressed)
        throw cancelled
    }
}

/** Missing optional evidence is unsupported; explicit cancellation and fatal errors are not evidence failures. */
internal inline fun <T> observeOptionalLanRoute(read: () -> T): T? = try {
    read()
} catch (cancelled: CancellationException) {
    throw cancelled
} catch (_: Exception) {
    null
}
