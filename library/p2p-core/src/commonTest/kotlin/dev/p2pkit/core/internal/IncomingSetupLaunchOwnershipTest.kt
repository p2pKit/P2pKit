package dev.p2pkit.core.internal

import dev.p2pkit.core.AppId
import dev.p2pkit.core.ConnectionState
import dev.p2pkit.core.KeepAliveConfig
import dev.p2pkit.core.P2pLogger
import dev.p2pkit.core.PeerId
import dev.p2pkit.core.Platform
import dev.p2pkit.core.ReconnectPolicy
import dev.p2pkit.core.SecurityMode
import dev.p2pkit.core.TransportKind
import dev.p2pkit.core.protocol.DefaultP2pProtocol
import dev.p2pkit.core.testfixtures.FakeConnectionPair
import dev.p2pkit.core.testfixtures.FakeDataTransport
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.test.StandardTestDispatcher
import kotlinx.coroutines.test.runTest
import kotlinx.coroutines.withContext
import kotlinx.coroutines.withTimeout
import kotlin.test.Test
import kotlin.test.assertTrue

@OptIn(ExperimentalCoroutinesApi::class)
class IncomingSetupLaunchOwnershipTest {

    @Suppress("DEPRECATION")
    @Test
    fun parentCancellationAtIncomingLaunchBoundaryStillClosesAcceptedRaw() = runTest {
        val pair = FakeConnectionPair()
        val transport = FakeDataTransport(preStagedIncoming = listOf(pair.a))
        val supervisor = SupervisorJob()
        val managerScope = CoroutineScope(StandardTestDispatcher(testScheduler) + supervisor)
        val manager = SessionManager(
            scope = managerScope,
            transportManager = TransportManager(listOf(transport)),
            protocol = DefaultP2pProtocol(clock = { testScheduler.currentTime }),
            securityMode = SecurityMode.NoneForMvp,
            localSecureIdentity = null,
            authenticatedSecurity = null,
            keepAlive = KeepAliveConfig(60_000, 120_000),
            reconnectPolicy = ReconnectPolicy.Disabled,
            localAppId = AppId("incoming-launch-ownership"),
            localPeerId = PeerId("local-peer"),
            localDeviceName = "Local",
            localPlatform = Platform.JVM_DESKTOP,
            localTransports = setOf(TransportKind.LAN),
            clock = { testScheduler.currentTime },
            logger = P2pLogger.NoOp,
            lifecycleGate = AlwaysActiveSessionLifecycleGate,
            beforeIncomingSetupLaunchForTest = { supervisor.cancel() }
        )

        manager.startAcceptingIncoming(listOf(transport))
        testScheduler.runCurrent()

        // The fallback close is intentionally owned by a real detached
        // cleanup worker. Observe it under a real deadline rather than racing
        // runTest's virtual clock (which can jump five seconds before that
        // worker receives a CPU slice on Native).
        withContext(Dispatchers.Default) {
            withTimeout(5_000) {
                pair.a.state.first { it == ConnectionState.Closed }
            }
        }
        assertTrue(manager.sessions.value.isEmpty())
    }
}

private object AlwaysActiveSessionLifecycleGate : SessionLifecycleGate {
    override suspend fun isActive(expectedGeneration: Long?): Boolean = true

    override suspend fun <T : Any> commit(
        expectedGeneration: Long?,
        block: suspend () -> T
    ): T = block()
}
