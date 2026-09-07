package dev.p2pkit.core.internal

import dev.p2pkit.core.AppId
import dev.p2pkit.core.KeepAliveConfig
import dev.p2pkit.core.PeerId
import dev.p2pkit.core.Platform
import dev.p2pkit.core.ReconnectPolicy
import dev.p2pkit.core.SecurityMode
import dev.p2pkit.core.TransportKind
import dev.p2pkit.core.protocol.DefaultP2pProtocol
import dev.p2pkit.core.testfixtures.RecordingLogger
import dev.p2pkit.core.transport.DataTransport
import dev.p2pkit.core.transport.InternalPeer
import dev.p2pkit.core.transport.RawConnection
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancelAndJoin
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.flow
import kotlinx.coroutines.test.TestScope
import kotlinx.coroutines.test.runTest

/** Pins acceptance shutdown while the parent is still active, as during kit transport/observer cleanup. */
@OptIn(ExperimentalCoroutinesApi::class)
class InboundAcceptanceShutdownTest {
    @Test
    fun terminalNormalCompletionDoesNotWarnOrRecollect() = assertTerminal(Ending.NORMAL)

    @Test
    fun terminalExceptionalCompletionDoesNotWarnOrRecollect() = assertTerminal(Ending.FAILURE)

    @Test
    fun terminalTransportCancellationDoesNotWarnOrRecollect() = assertTerminal(Ending.CANCELLATION)

    @Test
    fun activeNormalCompletionStillWarnsAndRecoversAfterBackoff() = assertRecovery(Ending.NORMAL)

    @Test
    fun activeFailureStillWarnsAndRecoversAfterBackoff() = assertRecovery(Ending.FAILURE)

    @Test
    fun activeTransportCancellationStillWarnsAndRecoversAfterBackoff() = assertRecovery(Ending.CANCELLATION)

    @Test
    fun shutdownDuringRecoveryBackoffPreventsAnotherCollection() = runTest {
        withManager(Ending.NORMAL) { manager, transport, logger, _ ->
            manager.startAcceptingIncoming(listOf(transport))
            testScheduler.runCurrent()
            transport.close()
            testScheduler.runCurrent()
            assertEquals(1, logger.warnings.size)
            assertTrue(manager.shutdownAllSessions().isEmpty())
            testScheduler.advanceTimeBy(30_000)
            testScheduler.runCurrent()
            assertEquals(1, transport.collections)
            assertEquals(1, logger.warnings.size, "No new failure after terminal shutdown")
            assertTrue(logger.errors.isEmpty())
        }
    }

    @Test
    fun acceptingAfterTerminalShutdownNeverCallsTransport() = runTest {
        withManager(Ending.NORMAL) { manager, transport, logger, _ ->
            assertTrue(manager.shutdownAllSessions().isEmpty())
            manager.startAcceptingIncoming(listOf(transport))
            testScheduler.runCurrent()
            assertEquals(0, transport.collections)
            logger.assertNoUnexpectedWarnOrError()
        }
    }

    @Test
    fun genuineParentCancellationStillTerminatesWithoutDiagnostics() = runTest {
        withManager(Ending.NORMAL) { manager, transport, logger, owner ->
            manager.startAcceptingIncoming(listOf(transport))
            testScheduler.runCurrent()
            assertEquals(1, transport.activeCollectors)
            owner.cancelAndJoin()
            assertEquals(0, transport.activeCollectors)
            assertEquals(1, transport.collections)
            logger.assertNoUnexpectedWarnOrError()
        }
    }

    private fun assertTerminal(ending: Ending) = runTest {
        withManager(ending) { manager, transport, logger, owner ->
            manager.startAcceptingIncoming(listOf(transport))
            testScheduler.runCurrent()
            assertEquals(1, transport.collections)
            assertTrue(manager.shutdownAllSessions().isEmpty())
            transport.close()
            testScheduler.runCurrent()
            testScheduler.advanceTimeBy(30_000)
            testScheduler.runCurrent()
            assertTrue(owner.isActive, "The test must not hide shutdown behind parent cancellation")
            assertEquals(emptyList<String>() to 1, logger.warnings to transport.collections)
            assertEquals(0, transport.activeCollectors)
            assertTrue(manager.sessions.value.isEmpty())
            logger.assertNoUnexpectedWarnOrError()
        }
    }

    private fun assertRecovery(ending: Ending) = runTest {
        withManager(ending) { manager, transport, logger, _ ->
            manager.startAcceptingIncoming(listOf(transport))
            testScheduler.runCurrent()
            transport.close() // Unexpected completion while the manager still accepts peers.
            testScheduler.runCurrent()
            assertEquals(1, transport.collections)
            testScheduler.advanceTimeBy(99)
            testScheduler.runCurrent()
            assertEquals(1, transport.collections)
            testScheduler.advanceTimeBy(1)
            testScheduler.runCurrent()
            assertEquals(2, transport.collections)
            assertEquals(1, transport.maxActiveCollectors)
            assertEquals(2, logger.warnings.size)
            assertTrue(logger.errors.isEmpty())
            assertEquals(listOf(transport.failure, transport.failure), logger.entries.map { it.throwable })
        }
    }

    @Suppress("DEPRECATION")
    private suspend fun TestScope.withManager(
        ending: Ending,
        block: suspend (SessionManager, EndingTransport, RecordingLogger, Job) -> Unit,
    ) {
        val transport = EndingTransport(ending)
        val logger = RecordingLogger()
        val owner = SupervisorJob(coroutineContext[Job])
        val manager = SessionManager(
            scope = CoroutineScope(coroutineContext + owner),
            transportManager = TransportManager(listOf(transport)),
            protocol = DefaultP2pProtocol(clock = { testScheduler.currentTime }),
            securityMode = SecurityMode.NoneForMvp,
            localSecureIdentity = null,
            authenticatedSecurity = null,
            keepAlive = KeepAliveConfig(60_000, 120_000),
            reconnectPolicy = ReconnectPolicy.Disabled,
            localAppId = AppId("acceptance.shutdown"),
            localPeerId = PeerId("synthetic-local"),
            localDeviceName = "Local",
            localPlatform = Platform.UNKNOWN,
            localTransports = setOf(TransportKind.LAN),
            clock = { testScheduler.currentTime },
            logger = logger,
            lifecycleGate = object : SessionLifecycleGate {
                override suspend fun isActive(expectedGeneration: Long?): Boolean = true
                override suspend fun <T : Any> commit(expectedGeneration: Long?, block: suspend () -> T): T = block()
            },
            strictInvariants = true,
        )
        try {
            block(manager, transport, logger, owner)
        } finally {
            try {
                owner.cancelAndJoin()
            } finally {
                transport.close()
            }
        }
    }
}

private enum class Ending { NORMAL, FAILURE, CANCELLATION }

/** Single test dispatcher owns counters; terminating the source affects later collections too. */
private class EndingTransport(ending: Ending) : DataTransport {
    override val type: TransportKind = TransportKind.LAN
    override val priority: Int = 1
    val failure: Throwable? = when (ending) {
        Ending.NORMAL -> null
        Ending.FAILURE -> IllegalStateException("synthetic acceptance failure")
        Ending.CANCELLATION -> CancellationException("transport-owned cancellation")
    }
    private val ended = CompletableDeferred<Unit>()
    var collections: Int = 0
        private set
    var activeCollectors: Int = 0
        private set
    var maxActiveCollectors: Int = 0
        private set

    override fun incomingConnections(): Flow<RawConnection> = flow {
        collections++
        activeCollectors++
        maxActiveCollectors = maxOf(maxActiveCollectors, activeCollectors)
        try {
            ended.await()
            failure?.let { throw it }
        } finally {
            activeCollectors--
        }
    }

    override fun canConnect(peer: InternalPeer): Boolean = false
    override suspend fun connect(peer: InternalPeer): RawConnection = error("No outgoing connections")
    override suspend fun stop() = Unit
    override suspend fun close() { ended.complete(Unit) }
}
