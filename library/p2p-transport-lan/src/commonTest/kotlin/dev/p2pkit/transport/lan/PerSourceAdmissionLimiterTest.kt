package dev.p2pkit.transport.lan

import dev.p2pkit.core.ConnectionState
import dev.p2pkit.core.transport.RawConnection
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.emptyFlow
import kotlinx.coroutines.launch
import kotlinx.coroutines.runBlocking
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertNotNull
import kotlin.test.assertNull

class PerSourceAdmissionLimiterTest {
    @Test
    fun oneSourceCannotConsumeAnotherSourcesShare() {
        val limiter = PerSourceAdmissionLimiter(maxPerSource = 2, maxTrackedSources = 4)
        val first = assertNotNull(limiter.tryAcquire("source-a"))
        val second = assertNotNull(limiter.tryAcquire("source-a"))

        assertNull(limiter.tryAcquire("source-a"))
        val other = assertNotNull(limiter.tryAcquire("source-b"))
        assertEquals(2, limiter.heldForTest("source-a"))
        assertEquals(1, limiter.heldForTest("source-b"))

        first.release()
        first.release()
        second.release()
        other.release()
        assertEquals(0, limiter.trackedSourcesForTest())
    }

    @Test
    fun trackedSourceMapHasAnIndependentBoundAndRecovers() {
        val limiter = PerSourceAdmissionLimiter(maxPerSource = 2, maxTrackedSources = 2)
        val first = assertNotNull(limiter.tryAcquire("source-a"))
        val second = assertNotNull(limiter.tryAcquire("source-b"))

        assertNull(limiter.tryAcquire("source-c"))
        first.release()
        val third = assertNotNull(limiter.tryAcquire("source-c"))

        second.release()
        third.release()
        assertEquals(0, limiter.trackedSourcesForTest())
    }

    @Test
    fun connectionCloseAndHandshakeReleaseReturnOneLeaseExactlyOnce() = runBlocking<Unit> {
        val limiter = PerSourceAdmissionLimiter(maxPerSource = 1, maxTrackedSources = 1)
        val lease = assertNotNull(limiter.tryAcquire("source"))
        val delegate = StubRawConnection()
        val connection = AdmissionControlledRawConnection(delegate, lease)

        connection.releasePreHandshakeAdmission()
        connection.releasePreHandshakeAdmission()
        connection.close()

        assertEquals(1, delegate.closeCalls)
        assertEquals(0, limiter.heldForTest("source"))
        assertNotNull(limiter.tryAcquire("source")).release()
    }

    @Test
    fun concurrentReleaseRaceRemovesTheSourceExactlyOnce() = runBlocking {
        val limiter = PerSourceAdmissionLimiter(maxPerSource = 1, maxTrackedSources = 1)
        val lease = assertNotNull(limiter.tryAcquire("source"))

        coroutineScope {
            repeat(32) { launch(Dispatchers.Default) { lease.release() } }
        }

        assertEquals(0, limiter.heldForTest("source"))
        assertEquals(0, limiter.trackedSourcesForTest())
        assertNotNull(limiter.tryAcquire("replacement")).release()
    }
}

private class StubRawConnection : RawConnection {
    override val state: StateFlow<ConnectionState> =
        MutableStateFlow(ConnectionState.Connected)
    var closeCalls: Int = 0

    override suspend fun write(bytes: ByteArray) = Unit
    override fun read(): Flow<ByteArray> = emptyFlow()
    override suspend fun close() {
        closeCalls += 1
    }
}
