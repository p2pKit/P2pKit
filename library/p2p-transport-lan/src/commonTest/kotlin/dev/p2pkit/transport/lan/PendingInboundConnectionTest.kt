package dev.p2pkit.transport.lan

import dev.p2pkit.core.ConnectionState
import dev.p2pkit.core.transport.RawConnection
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.emptyFlow
import kotlinx.coroutines.launch
import kotlinx.coroutines.test.runCurrent
import kotlinx.coroutines.test.runTest
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertNotNull
import kotlin.test.assertNull
import kotlin.test.assertTrue

@OptIn(ExperimentalCoroutinesApi::class)
class PendingInboundConnectionTest {
    @Test
    fun promptReceiveCancellationDisposesTheResumedButUndeliveredSocket() = runTest {
        val fixture = Fixture()
        val channel = Channel<PendingInboundConnection>(1, onUndeliveredElement = PendingInboundConnection::discard)
        val receiver = launch { channel.receive().claim(); error("cancelled receive must not return") }
        runCurrent()
        assertTrue(channel.trySend(fixture.pending).isSuccess)
        receiver.cancel()
        receiver.join()
        channel.cancel()
        fixture.pending.discard()
        assertEquals(1, fixture.closes)
        assertEquals(0, fixture.created)
        assertEquals(0, fixture.limiter.heldForTest("source"))
    }

    @Test
    fun successfulClaimTransfersLeaseAndNativeOwnershipOnlyOnce() = runTest {
        val fixture = Fixture()
        val raw = assertNotNull(fixture.pending.claim())
        fixture.pending.discard()
        assertNull(fixture.pending.claim())
        assertEquals(0, fixture.closes)
        assertEquals(1, fixture.limiter.heldForTest("source"))
        raw.close()
        assertEquals(1, fixture.closes)
        assertEquals(0, fixture.limiter.heldForTest("source"))
    }

    @Test
    fun failedRawConstructionDisposesSocketAndLease() {
        val limiter = PerSourceAdmissionLimiter()
        var closes = 0
        val pending = PendingInboundConnection(
            assertNotNull(limiter.tryAcquire("source")),
            create = { error("injected construction failure") },
            closeSocket = { closes++ }
        )
        assertFailsWith<IllegalStateException> { pending.claim() }
        pending.discard()
        assertEquals(1, closes)
        assertEquals(0, limiter.heldForTest("source"))
    }

    private class Fixture {
        val limiter = PerSourceAdmissionLimiter()
        var closes = 0
        var created = 0
        val pending = PendingInboundConnection(
            assertNotNull(limiter.tryAcquire("source")),
            create = {
                created++
                object : RawConnection {
                    override val state = MutableStateFlow(ConnectionState.Connected)
                    override suspend fun write(bytes: ByteArray) = Unit
                    override fun read() = emptyFlow<ByteArray>()
                    override suspend fun close() { closes++ }
                }
            },
            closeSocket = { closes++ }
        )
    }
}
