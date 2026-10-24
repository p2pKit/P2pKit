package dev.p2pkit.transport.lan

import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.cancel
import kotlinx.coroutines.currentCoroutineContext
import kotlinx.coroutines.launch
import kotlinx.coroutines.test.runTest
import kotlin.test.Test
import kotlin.test.assertContentEquals
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertIs
import kotlin.test.assertNotEquals
import kotlin.test.assertNotNull
import kotlin.test.assertNull
import kotlin.test.assertSame

class LanOutboundRouteValueTest {
    @Test
    fun cancellationDuringCleanupCannotBeConvertedIntoFallbackPermission() = runTest {
        val original = LanRouteRejected("TCP failed")
        val cleanup = IllegalStateException("retirement uncertain")
        val observed = CompletableDeferred<Throwable>()
        val job = launch {
            currentCoroutineContext().cancel(CancellationException("cancel during retirement"))
            try {
                rethrowRouteCancellation(original, cleanup)
                error("cancelled route must not reach fallback classification")
            } catch (failure: Throwable) {
                observed.complete(failure)
            }
        }
        job.join()
        val failure = assertIs<CancellationException>(observed.await())
        assertSame(original, failure.suppressedExceptions[0])
        assertSame(cleanup, failure.suppressedExceptions[1])
    }

    @Test
    fun numericValueDefensivelyCopiesInputAndOutput() {
        val bytes = byteArrayOf(10, 2, 3, 4)
        val address = assertNotNull(LanNumericAddress.copyOf(bytes))
        bytes[0] = 99
        address.copyBytes()[1] = 99
        assertContentEquals(byteArrayOf(10, 2, 3, 4), address.copyBytes())
        assertEquals(LanNumericAddress.copyOf(byteArrayOf(10, 2, 3, 4)), address)
    }

    @Test
    fun ipv6ScopeIsPartOfTheExactNumericIdentity() {
        val bytes = ByteArray(16).also { it[0] = 0xfe.toByte(); it[1] = 0x80.toByte(); it[15] = 1 }
        assertNull(LanNumericAddress.copyOf(bytes))
        val scoped = assertNotNull(LanNumericAddress.copyOf(bytes, 7))
        assertEquals(scoped, LanNumericAddress.copyOf(bytes, 7))
        assertNotEquals(scoped, LanNumericAddress.copyOf(bytes, 8))
        assertNull(LanNumericAddress.copyOf(bytes, -1))
    }

    @Test
    fun unsupportedAddressesAndPortsCannotBecomeRoutes() {
        assertNull(LanNumericAddress.copyOf(ByteArray(4)))
        assertNull(LanNumericAddress.copyOf(ByteArray(16)))
        assertNull(LanNumericAddress.copyOf(ByteArray(5)))
        assertNull(LanNumericAddress.copyOf(byteArrayOf(224.toByte(), 0, 0, 1)))
        assertNull(LanNumericAddress.copyOf(byteArrayOf(127, 0, 0, 1), 1))
        val loopback = assertNotNull(LanNumericAddress.copyOf(byteArrayOf(127, 0, 0, 1)))
        assertFailsWith<IllegalArgumentException> { LanTcpEndpoint(loopback, 0) }
        assertFailsWith<IllegalArgumentException> { LanTcpEndpoint(loopback, 65_536) }
        assertEquals(65_535, LanTcpEndpoint(loopback, 65_535).port)
    }
}
