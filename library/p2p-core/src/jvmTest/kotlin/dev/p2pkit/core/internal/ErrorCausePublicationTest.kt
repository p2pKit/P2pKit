package dev.p2pkit.core.internal

import dev.p2pkit.core.AppId
import dev.p2pkit.core.FeatureState
import dev.p2pkit.core.P2pError
import dev.p2pkit.core.P2pKit
import dev.p2pkit.core.PeerAuthorizationPolicy
import dev.p2pkit.core.SecurityMode
import dev.p2pkit.core.TransportKind
import dev.p2pkit.core.testfixtures.FakeDiscoveryTransport
import dev.p2pkit.core.testfixtures.FakeNetworkPathObserver
import dev.p2pkit.core.testfixtures.MemorySecureIdentityStorage
import dev.p2pkit.core.transport.DiscoveryTransport
import dev.p2pkit.core.transport.LocalPeerInfo
import dev.p2pkit.core.transport.TransportContext
import dev.p2pkit.core.transport.TransportDescriptor
import dev.p2pkit.core.transport.TransportFactory
import dev.p2pkit.core.transport.TransportPair
import java.util.concurrent.Executors
import java.util.concurrent.TimeUnit
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.NonCancellable
import kotlinx.coroutines.asCoroutineDispatcher
import kotlinx.coroutines.async
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.onSubscription
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withContext
import kotlinx.coroutines.withTimeout
import kotlin.test.Test
import kotlin.test.assertFailsWith
import kotlin.test.assertIs
import kotlin.test.assertNotSame
import kotlin.test.assertSame
import kotlin.test.assertTrue

/** Real kit publication contract, not a reproduction/proof of an unsynchronized visibility race. */
class ErrorCausePublicationTest {
    @Test
    fun advertisingFailurePreservesCauseOnAnotherDispatcher() = verifyFeatureCausePublication(advertising = true)

    @Test
    fun discoveryFailurePreservesCauseOnAnotherDispatcher() = verifyFeatureCausePublication(advertising = false)

    private fun verifyFeatureCausePublication(advertising: Boolean) = runBlocking {
        val callerThread = Thread.currentThread()
        val executor = Executors.newSingleThreadExecutor()
        try {
            executor.asCoroutineDispatcher().use { dispatcher ->
                val store = MemorySecureIdentityStorage()
                var kit: P2pKit? = null
                try {
                    val cause = IllegalStateException("synthetic feature start failure")
                    val activeKit = P2pKit.create {
                        appId = AppId("error-cause-publication")
                        deviceName = "Cause publication test"
                        secureIdentityStorage = store
                        strictSessionInvariants = true
                        security { mode = SecurityMode.AuthenticatedV2(PeerAuthorizationPolicy.RejectUnknown) }
                        networkPathObserver = FakeNetworkPathObserver()
                        transports { register(FailingFeatureFactory(cause)) }
                    }
                    kit = activeKit
                    coroutineScope {
                        val states = if (advertising) activeKit.advertisingState else activeKit.discoveryState
                        val subscribed = CompletableDeferred<Unit>()
                        val observer = async(dispatcher) {
                            val state = states.onSubscription { subscribed.complete(Unit) }
                                .first { it is FeatureState.Failed }
                            val error = assertIs<P2pError.ConnectionFailed>(assertIs<FeatureState.Failed>(state).error)
                            assertNotSame(callerThread, Thread.currentThread(), "collector must use another thread")
                            assertSame(cause, error.cause, "the collector must see the original diagnostic cause")
                            error
                        }
                        // Use the real clock: the owned executor does not run on a virtual test scheduler.
                        withTimeout(5_000) { subscribed.await() }
                        val thrown = assertFailsWith<P2pError.ConnectionFailed> {
                            if (advertising) activeKit.startAdvertising() else activeKit.startDiscovery()
                        }
                        assertSame(cause, thrown.cause)
                        val retained = withTimeout(5_000) { observer.await() }
                        assertSame(thrown, retained, "the published state must retain the thrown error instance")
                        activeKit.stop()
                        assertSame(cause, retained.cause, "shutdown must not clear a retained diagnostic cause")
                    }
                } finally {
                    withContext(NonCancellable) {
                        try {
                            kit?.stop()
                        } finally {
                            store.clear()
                        }
                    }
                }
            }
        } finally {
            executor.shutdownNow()
            assertTrue(executor.awaitTermination(5, TimeUnit.SECONDS), "owned observer executor must terminate")
        }
    }

    private class FailingFeatureFactory(private val failure: Throwable) : TransportFactory {
        override val descriptor: TransportDescriptor = TransportDescriptor.discoveryOnly(TransportKind.LAN)

        override fun build(context: TransportContext): TransportPair = TransportPair(
            discovery = object : DiscoveryTransport by FakeDiscoveryTransport() {
                override suspend fun startAdvertising(localPeer: LocalPeerInfo): Unit = throw failure

                override suspend fun startDiscovery(): Unit = throw failure
            }
        )
    }
}
