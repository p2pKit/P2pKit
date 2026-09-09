package dev.p2pkit.core.internal

import dev.p2pkit.core.AppId
import dev.p2pkit.core.ExperimentalP2pApi
import dev.p2pkit.core.P2pLogger
import dev.p2pkit.core.PeerId
import dev.p2pkit.core.provisioning.NetworkProvisioningFactory
import dev.p2pkit.core.provisioning.NetworkProvisioningManager
import dev.p2pkit.core.provisioning.ProvisioningContext
import dev.p2pkit.core.provisioning.UnsupportedNetworkProvisioningManager
import dev.p2pkit.core.testfixtures.FakeDataTransport
import dev.p2pkit.core.testfixtures.createTestKit
import dev.p2pkit.core.transport.PeerEvent
import dev.p2pkit.core.transport.TransportContext
import dev.p2pkit.core.transport.TransportFactory
import dev.p2pkit.core.transport.TransportPair
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.runBlocking
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertIs
import kotlin.test.assertNotNull
import kotlin.test.assertSame
import kotlin.test.assertTrue

class LoggerIsolationTest {

    @Test
    fun isolatedLoggerSwallowsEveryDelegateThrowableIncludingCancellation() {
        val delegate = ThrowingLogger()
        val logger = delegate.failureIsolated()

        logger.debug("debug")
        logger.info("info")
        logger.warn("warn", IllegalStateException("context"))
        logger.error("error", AssertionError("context"))

        assertEquals(4, delegate.calls)
    }

    @OptIn(ExperimentalP2pApi::class)
    @Test
    fun defaultKitKeepsTheNoOpLoggerThroughItsRegistryWiring() = runBlocking {
        var provisioningContext: ProvisioningContext? = null
        val provisioning = object : NetworkProvisioningFactory {
            override fun build(context: ProvisioningContext): NetworkProvisioningManager {
                provisioningContext = context
                return UnsupportedNetworkProvisioningManager()
            }
        }
        // The legacy fixture uses the real shared logger boundary. This is
        // logger-wiring evidence, not an authenticated-defaults claim.
        val kit = createTestKit {
            appId = AppId("noop-logger-test")
            deviceName = "NoOp logger"
            peerIdStorage = InMemoryPeerIdStorage(PeerId("noop-logger-peer"))
            transports { register(LoggerIsolationFactory(FakeDataTransport())) }
            networkProvisioning { register(provisioning) }
        }
        try {
            val context = assertNotNull(provisioningContext)
            assertSame(P2pLogger.NoOp, context.logger)
            val registry = assertIs<PeerRegistry>(context.manualPeerRegistrar)
            registry.processEvent(PeerEvent.Lost(PeerId("invalid\u0000")))
            assertTrue(kit.peers.value.isEmpty())
        } finally {
            kit.stop()
        }
    }

    @Test
    fun kitLifecycleDoesNotDependOnApplicationLoggerCorrectness() = runBlocking {
        val transport = FakeDataTransport()
        val kit = createTestKit {
            appId = AppId("throwing-logger-test")
            deviceName = "Logger isolation"
            peerIdStorage = InMemoryPeerIdStorage(PeerId("logger-peer"))
            logger = ThrowingLogger()
            transports { register(LoggerIsolationFactory(transport)) }
        }

        kit.start()
        kit.stop()
    }
}

private class ThrowingLogger : P2pLogger {
    var calls: Int = 0
        private set

    override fun debug(message: String) = fail()
    override fun info(message: String) = fail()
    override fun warn(message: String, throwable: Throwable?) = fail()
    override fun error(message: String, throwable: Throwable?) = fail()

    private fun fail(): Nothing {
        calls += 1
        if (calls % 2 == 0) throw AssertionError("logger failure")
        throw CancellationException("logger cancellation is not SDK cancellation")
    }
}

private class LoggerIsolationFactory(
    private val transport: FakeDataTransport
) : TransportFactory {
    override val descriptor =
        dev.p2pkit.core.transport.TransportDescriptor.dataOnly(transport.type)

    override fun build(context: TransportContext): TransportPair =
        TransportPair(data = transport)
}
