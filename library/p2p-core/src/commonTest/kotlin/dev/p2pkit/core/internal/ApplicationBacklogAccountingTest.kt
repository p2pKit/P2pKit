package dev.p2pkit.core.internal

import dev.p2pkit.core.ConnectionState
import dev.p2pkit.core.KeepAliveConfig
import dev.p2pkit.core.P2pMessage
import dev.p2pkit.core.Peer
import dev.p2pkit.core.PeerId
import dev.p2pkit.core.Platform
import dev.p2pkit.core.TransportKind
import dev.p2pkit.core.protocol.DefaultP2pProtocol
import dev.p2pkit.core.protocol.ProtocolEvent
import dev.p2pkit.core.testfixtures.FakeConnectionPair
import dev.p2pkit.core.testfixtures.RecordingLogger
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertIs
import kotlin.test.assertSame
import kotlin.test.assertTrue
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.CoroutineStart
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.Job
import kotlinx.coroutines.NonCancellable
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.async
import kotlinx.coroutines.cancelAndJoin
import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.launch
import kotlinx.coroutines.test.StandardTestDispatcher
import kotlinx.coroutines.test.TestScope
import kotlinx.coroutines.test.runTest
import kotlinx.coroutines.withContext
import kotlinx.coroutines.withTimeout

/** Exact policy charges and ownership, not measurements of a platform's heap layout. */
@OptIn(ExperimentalCoroutinesApi::class)
class ApplicationBacklogAccountingTest {
    @Test
    fun textUsesUtf16CodeUnitsAndFixedAllowanceRatherThanUtf8Encoding() = runTest {
        val cases = listOf(
            "" to 512L,
            "AAAA" to 520L,
            "éééé" to 520L,
            "中中中中" to 520L,
            "\uD83D\uDE00\uD83D\uDE00" to 520L,
            // Constructors permit these strings, but the real wire decoder rejects invalid Unicode.
            "\uD800" to 514L,
            "\uDC00" to 514L
        )
        withFixture {
            for ((value, charge) in cases) {
                val message = P2pMessage.Text(value)
                enqueue(message)
                assertClaimed(message)
                assertBacklog(1, charge)
                releaseOne()
                assertDelivered(message)
                assertBacklog(0, 0L)
            }
            logger.assertNoUnexpectedWarnOrError()
        }
    }

    @Test
    fun textAndBinaryIncludeMetadataCodeUnitsAndEachEntryAllowance() = runTest {
        val cases = listOf(
            mapOf("ab" to "cd") to 264L,
            mapOf("a" to "b", "c" to "d") to 520L,
            mapOf("é中\uD83D\uDE00" to "vλz") to 270L,
            mapOf("key" to "") to 262L,
            // Ten two-unit keys and 54 three-unit keys: 64 * 256 + 182 * 2.
            (0 until 64).associate { "k$it" to "" } to 16_748L
        )
        withFixture {
            for ((metadata, metadataCharge) in cases) {
                val messages = listOf(
                    P2pMessage.Text("x", metadata) to 514L,
                    P2pMessage.Binary(byteArrayOf(), metadata) to 512L,
                    P2pMessage.Binary(byteArrayOf(1, 2, 3), metadata) to 515L
                )
                for ((message, payloadAndFixedCharge) in messages) {
                    enqueue(message)
                    assertClaimed(message)
                    assertBacklog(1, payloadAndFixedCharge + metadataCharge)
                    releaseOne()
                    assertDelivered(message)
                    assertBacklog(0, 0L)
                }
            }
            logger.assertNoUnexpectedWarnOrError()
        }
    }

    @Test
    fun callerMutationAndBinaryCopiesCannotChangeRecordedOwnershipOrDelivery() = runTest {
        val bytes = byteArrayOf(1, 2, 3, 4)
        val metadata = mutableMapOf("k" to "é\uD83D\uDE00")
        val message = P2pMessage.Binary(bytes, metadata)
        val expected = P2pMessage.Binary(byteArrayOf(1, 2, 3, 4), mapOf("k" to "é\uD83D\uDE00"))
        val text = P2pMessage.Text("stable", metadata)
        val expectedText = P2pMessage.Text("stable", mapOf("k" to "é\uD83D\uDE00"))
        withFixture {
            enqueue(message)
            assertClaimed(message)
            assertBacklog(1, 780L) // 512 + 4 + 256 + 2 * (1 + 3).

            bytes.fill(0)
            metadata.clear()
            metadata["different"] = "changed".repeat(1_024)
            message.bytes.fill(0)

            assertBacklog(1, 780L)
            releaseOne()
            assertDelivered(expected)
            assertBacklog(0, 0L)

            enqueue(text)
            assertClaimed(text)
            assertBacklog(1, 788L)
            releaseOne()
            assertDelivered(expectedText)
            assertBacklog(0, 0L)
            logger.assertNoUnexpectedWarnOrError()
        }
    }

    @Test
    fun exactly64MessagesIncludingInFlightAreAdmittedAnd65thFails() = runTest {
        withFixture(nonCooperativeDelivery = true, pauseTerminal = true) {
            val first = P2pMessage.Text("")
            enqueue(first)
            assertClaimed(first)
            repeat(63) { enqueue(P2pMessage.Text("")) }
            assertEquals(ConnectionState.Connected, session.state.value)
            assertBacklog(64, 32_768L)

            enqueue(P2pMessage.Text(""))
            assertEquals(ConnectionState.Failed, session.state.value)
            assertBacklog(64, 32_768L)
            assertOverflowLogged()
            assertNoDeliveredMessage()
        }
    }

    @Test
    fun exactly8MiBIsAdmittedAndAnotherMessageFails() = runTest {
        assertByteBoundary(emptyMap(), metadataCharge = 0, excess = 0)
    }

    @Test
    fun oneByteBeyond8MiBIsRejectedWithoutChargingTheRejectedMessage() = runTest {
        assertByteBoundary(emptyMap(), metadataCharge = 0, excess = 1)
    }

    @Test
    fun exactly8MiBIncludingMetadataIsAdmitted() = runTest {
        assertByteBoundary(mapOf("meta" to "value"), metadataCharge = 274, excess = 0)
    }

    @Test
    fun metadataChargeParticipatesInTheOneByteOverflowBoundary() = runTest {
        assertByteBoundary(mapOf("meta" to "value"), metadataCharge = 274, excess = 1)
    }

    @Test
    fun successfulEmissionReleasesOnlyItsChargeAndPermitsReadmission() = runTest {
        withFixture {
            val first = P2pMessage.Text("first", mapOf("k" to "v"))
            val second = P2pMessage.Binary(byteArrayOf(1, 2, 3))
            enqueue(first)
            assertClaimed(first)
            enqueue(second)
            assertBacklog(2, 1_297L) // First 782, second 515.

            releaseOne()
            assertDelivered(first)
            assertClaimed(second)
            assertBacklog(1, 515L)
            releaseOne()
            assertDelivered(second)
            assertBacklog(0, 0L)

            val next = P2pMessage.Text("next")
            enqueue(next)
            assertClaimed(next)
            assertBacklog(1, 520L)
            releaseOne()
            assertDelivered(next)
            assertBacklog(0, 0L)
            assertEquals(ConnectionState.Connected, session.state.value)
            logger.assertNoUnexpectedWarnOrError()
        }
    }

    @Test
    fun failedChannelSendRollsBackItsChargeWithoutErasingExistingOwnership() = runTest {
        withFixture(nonCooperativeDelivery = true, pauseTerminal = true) {
            val first = P2pMessage.Text("a", mapOf("x" to "é"))
            val second = P2pMessage.Binary(byteArrayOf(1, 2, 3), mapOf("z" to "\uD83D\uDE00"))
            enqueue(first)
            assertClaimed(first)
            enqueue(second)
            assertBacklog(2, 1_551L) // First 774, second 777.

            // A different coroutine closes the application channel; the router stays live at the hook.
            val closeCall = async { runCatching { session.close() } }
            terminalPublished.await()
            assertEquals(ConnectionState.Closed, session.state.value)
            assertBacklog(2, 1_551L)

            enqueue(P2pMessage.Text("late", mapOf("late" to "metadata")))
            assertOverflowLogged() // Proves that the live router actually attempted the closed-channel send.
            assertBacklog(2, 1_551L)
            assertEquals(ConnectionState.Closed, session.state.value)

            releaseOne()
            assertBacklog(1, 777L)
            assertNoDeliveredMessage()
            releaseTerminal.complete(Unit)
            closeCall.await().getOrThrow()
            awaitTermination()
            assertBacklog(0, 0L)
        }
    }

    @Test
    fun terminalDrainLeavesNonCooperativeInFlightChargeUntilItsLateFinally() = runTest {
        withFixture(nonCooperativeDelivery = true, deliveryCloseTimeoutMillis = 50) {
            val first = P2pMessage.Text("retained", mapOf("x" to "\uD83D\uDE00"))
            val second = P2pMessage.Binary(byteArrayOf(1, 2, 3), mapOf("queued" to "value"))
            enqueue(first)
            assertClaimed(first)
            enqueue(second)
            assertBacklog(2, 1_583L) // First 790, second 793.
            events.send(ProtocolEvent.Close)

            // Production's cleanup deadline is real, not the virtual session scheduler's clock.
            withContext(Dispatchers.Default) {
                withTimeout(5_000) { deliveryDrained.await() }
            }
            assertEquals(ConnectionState.Closed, session.state.value)
            assertBacklog(1, 790L)
            assertNoDeliveredMessage()

            releaseOne()
            awaitTermination()
            assertBacklog(0, 0L)
            assertNoDeliveredMessage()
            val warning = logger.entries.single {
                it.level == RecordingLogger.Level.WARN &&
                    it.message == "session application-backlog-accounting terminal cleanup failed for " +
                        "session application-backlog-accounting application delivery"
            }
            val failure = assertIs<IllegalStateException>(warning.throwable)
            assertEquals("cleanup exceeded 50ms", failure.message)
            val deadline = assertIs<OwnedOperationTimeoutException>(failure.cause)
            assertEquals("Operation timed out after 50 ms", deadline.message)
            logger.assertNoUnexpectedWarnOrError { it === warning }
        }
    }

    @Test
    fun rearmPreservesChargesOwnedByTheSessionRatherThanTheOldEpoch() = runTest {
        withFixture {
            val first = P2pMessage.Text("old", mapOf("epoch" to "one"))
            val second = P2pMessage.Binary(byteArrayOf(1, 2, 3))
            enqueue(first)
            assertClaimed(first)
            enqueue(second)
            assertBacklog(2, 1_305L) // First 790, second 515.

            val replacementEvents = rearm()
            assertBacklog(2, 1_305L)
            val next = P2pMessage.Text("new")
            replacementEvents.send(ProtocolEvent.Message(next))
            tick()
            assertBacklog(3, 1_823L)

            releaseOne()
            assertDelivered(first)
            assertClaimed(second)
            assertBacklog(2, 1_033L)
            releaseOne()
            assertDelivered(second)
            assertClaimed(next)
            assertBacklog(1, 518L)
            releaseOne()
            assertDelivered(next)
            assertBacklog(0, 0L)
            assertEquals(ConnectionState.Connected, session.state.value)
            logger.assertNoUnexpectedWarnOrError()
        }
    }

    @Test
    fun asciiAtExactlyTheRetentionBudgetIsAdmitted() = runTest {
        withFixture {
            val message = P2pMessage.Text("a".repeat(4_194_048))
            enqueue(message)
            assertClaimed(message)
            assertEquals(ConnectionState.Connected, session.state.value)
            assertBacklog(1, 8_388_608L) // 512 + 2 * 4_194_048.
            releaseOne()
            assertDelivered(message)
            assertBacklog(0, 0L)
            logger.assertNoUnexpectedWarnOrError()
        }
    }

    @Test
    fun asciiOneCodeUnitAboveTheRetentionBudgetIsRejected() = runTest {
        assertSingleAsciiRejected(4_194_049)
    }

    @Test
    fun maximumWireSizedAsciiIsRejectedEvenWhenTheBacklogWasEmpty() = runTest {
        // The unchanged 4 MiB wire-content ceiling is not a guarantee of receive-backlog admission.
        assertSingleAsciiRejected(4 * 1_024 * 1_024)
    }

    private suspend fun TestScope.assertSingleAsciiRejected(length: Int) {
        withFixture(nonCooperativeDelivery = true, pauseTerminal = true) {
            enqueue(P2pMessage.Text("a".repeat(length)))
            assertEquals(ConnectionState.Failed, session.state.value)
            assertBacklog(0, 0L)
            assertTrue(claimed.tryReceive().isFailure, "a rejected message must not transfer delivery ownership")
            assertOverflowLogged()
            assertNoDeliveredMessage()
        }
    }

    private suspend fun TestScope.assertByteBoundary(
        metadata: Map<String, String>,
        metadataCharge: Int,
        excess: Int
    ) {
        withFixture(nonCooperativeDelivery = true, pauseTerminal = true) {
            val payloadSize = 4_194_304 - 512 - metadataCharge
            val first = P2pMessage.Binary(ByteArray(payloadSize), metadata)
            enqueue(first)
            assertClaimed(first)
            assertBacklog(1, 4_194_304L)

            enqueue(P2pMessage.Binary(ByteArray(payloadSize + excess), metadata))
            if (excess == 0) {
                assertEquals(ConnectionState.Connected, session.state.value)
                assertBacklog(2, 8_388_608L)
                enqueue(P2pMessage.Binary(byteArrayOf()))
                assertEquals(ConnectionState.Failed, session.state.value)
                assertBacklog(2, 8_388_608L)
            } else {
                assertEquals(ConnectionState.Failed, session.state.value)
                assertBacklog(1, 4_194_304L)
            }
            assertOverflowLogged()
            assertNoDeliveredMessage()
        }
    }

    private suspend fun TestScope.withFixture(
        nonCooperativeDelivery: Boolean = false,
        pauseTerminal: Boolean = false,
        deliveryCloseTimeoutMillis: Long = 2_000,
        block: suspend Fixture.() -> Unit
    ) {
        val fixture = Fixture(this, nonCooperativeDelivery, pauseTerminal, deliveryCloseTimeoutMillis)
        try {
            fixture.block()
        } finally {
            fixture.cleanup()
        }
    }

    private class Fixture(
        private val testScope: TestScope,
        nonCooperativeDelivery: Boolean,
        pauseTerminal: Boolean,
        deliveryCloseTimeoutMillis: Long
    ) {
        private val supervisor = SupervisorJob(testScope.coroutineContext[Job])
        private val scope = CoroutineScope(StandardTestDispatcher(testScope.testScheduler) + supervisor)
        private val pair = FakeConnectionPair()
        private val ownedPairs = mutableListOf(pair)
        val events = Channel<ProtocolEvent>(Channel.UNLIMITED)
        private val ownedEvents = mutableListOf(events)
        val claimed = Channel<P2pMessage>(Channel.UNLIMITED)
        private val deliveryPermits = Channel<Unit>(Channel.UNLIMITED)
        private val delivered = Channel<P2pMessage>(Channel.UNLIMITED)
        val terminalPublished = CompletableDeferred<Unit>()
        val releaseTerminal = CompletableDeferred<Unit>()
        val deliveryDrained = CompletableDeferred<Unit>()
        val logger = RecordingLogger()
        val session = P2pSessionImpl(
            id = "application-backlog-accounting",
            peer = Peer(PeerId("backlog-peer"), "Peer", Platform.JVM_DESKTOP, setOf(TransportKind.LAN)),
            initialConnection = pair.a,
            initialEvents = events,
            protocol = DefaultP2pProtocol(clock = { testScope.testScheduler.currentTime }),
            parentScope = scope,
            keepAlive = KeepAliveConfig(60_000, 120_000),
            clock = { testScope.testScheduler.currentTime },
            logger = logger,
            beforeApplicationMessageEmitForTest = { message ->
                claimed.send(message)
                if (nonCooperativeDelivery) {
                    withContext(NonCancellable) { deliveryPermits.receive() }
                } else {
                    deliveryPermits.receive()
                }
            },
            afterTerminalStatePublishedForTest = {
                terminalPublished.complete(Unit)
                if (pauseTerminal) releaseTerminal.await()
            },
            applicationDeliveryCloseTimeoutMillis = deliveryCloseTimeoutMillis,
            afterApplicationDeliveryDrainForTest = { deliveryDrained.complete(Unit) }
        )

        init {
            scope.launch(start = CoroutineStart.UNDISPATCHED) { session.incoming.collect(delivered::send) }
            session.start()
        }

        suspend fun enqueue(message: P2pMessage) {
            events.send(ProtocolEvent.Message(message))
            tick()
        }

        fun tick() {
            testScope.testScheduler.runCurrent()
        }

        fun assertClaimed(expected: P2pMessage) {
            assertSame(expected, claimed.tryReceive().getOrThrow())
        }

        fun releaseOne() {
            deliveryPermits.trySend(Unit).getOrThrow()
            tick()
        }

        fun assertDelivered(expected: P2pMessage) {
            assertEquals(expected, delivered.tryReceive().getOrThrow())
        }

        fun assertNoDeliveredMessage() {
            assertTrue(delivered.tryReceive().isFailure, "terminal/rejected messages must not be emitted")
        }

        suspend fun assertBacklog(count: Int, bytes: Long) {
            assertEquals(count to bytes, session.applicationBacklogForTest())
        }

        fun assertOverflowLogged() {
            assertEquals(1, logger.warnings.count { "application receive backlog exceeded" in it })
        }

        suspend fun rearm(): Channel<ProtocolEvent> {
            val replacement = FakeConnectionPair()
            val replacementEvents = Channel<ProtocolEvent>(Channel.UNLIMITED)
            ownedPairs += replacement
            ownedEvents += replacementEvents
            assertTrue(session.rearmWith(replacement.a, replacementEvents))
            assertEquals(ConnectionState.Closed, pair.a.state.value)
            return replacementEvents
        }

        suspend fun awaitTermination() {
            withContext(Dispatchers.Default) {
                withTimeout(5_000) { session.awaitRuntimeTermination() }
            }
            assertFalse(session.runtimeJobIsActiveForTest)
        }

        suspend fun cleanup() = withContext(NonCancellable) {
            deliveryPermits.cancel()
            releaseTerminal.complete(Unit)
            try {
                session.close()
                awaitTermination()
                assertBacklog(0, 0L)
            } finally {
                try {
                    withContext(Dispatchers.Default) {
                        withTimeout(5_000) { supervisor.cancelAndJoin() }
                    }
                } finally {
                    ownedEvents.forEach { it.cancel() }
                    claimed.cancel()
                    delivered.cancel()
                    for (connectionPair in ownedPairs) {
                        try {
                            connectionPair.a.close()
                        } finally {
                            connectionPair.b.close()
                        }
                    }
                }
            }
        }
    }
}
