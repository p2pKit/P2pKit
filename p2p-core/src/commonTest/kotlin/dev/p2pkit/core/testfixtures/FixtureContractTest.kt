package dev.p2pkit.core.testfixtures

import dev.p2pkit.core.ConnectionState
import dev.p2pkit.core.PeerId
import dev.p2pkit.core.transport.PeerEvent
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.async
import kotlinx.coroutines.channels.ClosedSendChannelException
import kotlinx.coroutines.flow.launchIn
import kotlinx.coroutines.flow.onEach
import kotlinx.coroutines.flow.toList
import kotlinx.coroutines.launch
import kotlinx.coroutines.test.runCurrent
import kotlinx.coroutines.test.runTest
import kotlin.test.Test
import kotlin.test.assertContentEquals
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertFalse
import kotlin.test.assertTrue

/**
 * Fixture-fidelity self-tests (2026-07 fixture upgrade, TST-1 / P1-00).
 *
 * These pin the contract of the shared fakes so session/protocol suites can
 * rely on it: remote termination is modeled exactly like the shipped
 * transports (read completes normally and state flips to Closed — F1),
 * write faults are injectable (F2), the incoming-connections flow can end
 * with an error like the real accept loop (F3), and start()/close() follow
 * the shipped transport contract (F5).
 */
@OptIn(ExperimentalCoroutinesApi::class)
class FixtureContractTest {

    // ---- F1: remote-termination fidelity -------------------------------

    @Test
    fun breakWithCompletesReadNormallyAndFlipsState() = runTest {
        val pair = FakeConnectionPair()
        pair.b.write(byteArrayOf(1, 2, 3))
        pair.a.breakWith()

        // Like the shipped transports: buffered bytes drain, then the read
        // flow completes normally — it must NOT throw.
        val received = pair.a.read().toList()

        assertEquals(1, received.size)
        assertContentEquals(byteArrayOf(1, 2, 3), received[0])
        assertEquals(ConnectionState.Closed, pair.a.state.value)
    }

    @Test
    fun hangUpPropagatesRemoteTerminationToPartner() = runTest {
        val pair = FakeConnectionPair()
        pair.a.write(byteArrayOf(7))
        pair.hangUp(pair.a)

        // Partner drains buffered data, then its read completes normally...
        val seen = pair.b.read().toList()
        assertEquals(1, seen.size)
        assertContentEquals(byteArrayOf(7), seen[0])
        // ...the completed read flips the partner's state, like the shipped
        // transports' read loop does on EOF/read error...
        assertEquals(ConnectionState.Closed, pair.b.state.value)
        // ...and partner writes then fail.
        assertFailsWith<ClosedSendChannelException> { pair.b.write(byteArrayOf(9)) }
    }

    @Test
    fun peerSideClosePropagatesToPartner() = runTest {
        val pair = FakeConnectionPair()
        pair.a.close()

        val seen = pair.b.read().toList()
        assertTrue(seen.isEmpty())
        assertEquals(ConnectionState.Closed, pair.b.state.value)
        assertFailsWith<ClosedSendChannelException> { pair.b.write(byteArrayOf(1)) }
    }

    @Test
    fun breakWithExceptionThrowsFromReadForDefensivePathTests() = runTest {
        val pair = FakeConnectionPair()
        val cause = RuntimeException("simulated defensive-path failure")
        pair.a.breakWithException(cause)

        // Opt-in only: a throwing read is a signature no shipped transport
        // produces; it exists for tests of the defensive failure branch.
        val thrown = assertFailsWith<RuntimeException> { pair.a.read().collect { } }
        assertEquals("simulated defensive-path failure", thrown.message)
        assertEquals(ConnectionState.Closed, pair.a.state.value)
    }

    // ---- F2: write-fault injection --------------------------------------

    @Test
    fun failNextWriteFailsOnceAndConnectionStaysOpen() = runTest {
        val pair = FakeConnectionPair()
        pair.a.failNextWrite(IllegalStateException("transient write fault"))

        assertFailsWith<IllegalStateException> { pair.a.write(byteArrayOf(1)) }
        assertEquals(ConnectionState.Connected, pair.a.state.value)

        pair.a.write(byteArrayOf(2))
        assertEquals(1, pair.a.writtenChunks.size)
        assertEquals(2, pair.a.writeAttempts)
    }

    @Test
    fun writeFailureFailsEveryWriteWhileSet() = runTest {
        val pair = FakeConnectionPair()
        pair.a.writeFailure = IllegalStateException("persistent write fault")

        assertFailsWith<IllegalStateException> { pair.a.write(byteArrayOf(1)) }
        assertFailsWith<IllegalStateException> { pair.a.write(byteArrayOf(2)) }

        pair.a.writeFailure = null
        pair.a.write(byteArrayOf(3))
        assertEquals(1, pair.a.writtenChunks.size)
        assertEquals(3, pair.a.writeAttempts)
    }

    @Test
    fun suspendWritesParksWriterUntilResumed() = runTest {
        val pair = FakeConnectionPair()
        pair.a.suspendWrites()

        val writer = launch { pair.a.write(byteArrayOf(1)) }
        runCurrent()
        assertFalse(writer.isCompleted, "write must stay parked while writes are suspended")
        assertTrue(pair.a.writtenChunks.isEmpty())

        pair.a.resumeWrites()
        writer.join()
        assertEquals(1, pair.a.writtenChunks.size)
    }

    @Test
    fun closeReleasesAParkedWriteWithAFailure() = runTest {
        val pair = FakeConnectionPair()
        pair.a.suspendWrites()

        val outcome = async { runCatching { pair.a.write(byteArrayOf(1)) } }
        runCurrent()
        assertFalse(outcome.isCompleted, "write must stay parked until close releases it")

        pair.a.close()
        assertTrue(
            outcome.await().isFailure,
            "a write parked at close time must surface a failure, like a real socket close"
        )
        assertTrue(pair.a.writtenChunks.isEmpty())
    }

    // ---- F3 + F5: FakeDataTransport contract -----------------------------

    @Test
    fun failIncomingTerminatesIncomingFlowWithCause() = runTest {
        val transport = FakeDataTransport()
        val collected = async { runCatching { transport.incomingConnections().collect { } } }
        runCurrent()

        transport.failIncoming(IllegalStateException("accept loop ended"))

        val outcome = collected.await()
        assertTrue(outcome.isFailure, "incoming flow must terminate with the injected cause")
        assertEquals("accept loop ended", outcome.exceptionOrNull()?.message)
    }

    @Test
    fun startRecordsCallsAndSucceedsByDefault() = runTest {
        val transport = FakeDataTransport()
        assertTrue(transport.start().isSuccess)
        assertTrue(transport.start().isSuccess)
        assertEquals(2, transport.startCalls)
    }

    @Test
    fun startAfterCloseReportsFailurePerTheShippedContract() = runTest {
        val transport = FakeDataTransport()
        transport.close()
        assertTrue(transport.isClosed)
        assertTrue(transport.start().isFailure, "start() after close() must report failure")
    }

    @Test
    fun startFailureKnobMakesStartReportFailure() = runTest {
        val transport = FakeDataTransport()
        transport.startFailure = IllegalStateException("bind refused")
        assertEquals("bind refused", transport.start().exceptionOrNull()?.message)

        transport.startFailure = null
        assertTrue(transport.start().isSuccess)
    }

    @Test
    fun emitIncomingAfterCloseFailsLoudly() = runTest {
        val transport = FakeDataTransport()
        transport.close()
        assertFailsWith<IllegalStateException> {
            transport.emitIncoming(FakeConnectionPair().a)
        }
    }

    // ---- F4: discovery event delivery ------------------------------------

    @Test
    fun discoveryEventsDeliverToAnActiveCollectorInBothModes() = runTest {
        for (strict in listOf(false, true)) {
            val transport = FakeDiscoveryTransport(strictDelivery = strict)
            val events = mutableListOf<PeerEvent>()
            val job = transport.events.onEach { events.add(it) }.launchIn(this)
            runCurrent()

            transport.emit(PeerEvent.Lost(PeerId("peer-1")))
            runCurrent()

            assertEquals(1, events.size, "strictDelivery=$strict must deliver to an active collector")
            job.cancel()
        }
    }

    // ---- F7: RecordingLogger ---------------------------------------------

    @Test
    fun recordingLoggerCapturesEntriesAndTeardownConventionWorks() {
        val logger = RecordingLogger()
        logger.debug("d1")
        logger.info("i1")
        logger.warn("w1")
        logger.error("e1", RuntimeException("recorded cause"))

        assertEquals(4, logger.entries.size)
        assertEquals(listOf("w1"), logger.warnings)
        assertEquals(listOf("e1"), logger.errors)
        assertEquals("recorded cause", logger.entries.last().throwable?.message)

        assertFailsWith<AssertionError> { logger.assertNoUnexpectedWarnOrError() }
        // Expected diagnostics can be accounted for explicitly.
        logger.assertNoUnexpectedWarnOrError { it.message == "w1" || it.message == "e1" }

        val quiet = RecordingLogger()
        quiet.debug("only debug")
        quiet.assertNoUnexpectedWarnOrError()
    }
}
