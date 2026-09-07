package dev.p2pkit.core.internal

import dev.p2pkit.core.AppId
import dev.p2pkit.core.ConnectionState
import dev.p2pkit.core.ExplicitSecurityRisk
import dev.p2pkit.core.P2pError
import dev.p2pkit.core.P2pKit
import dev.p2pkit.core.P2pLogger
import dev.p2pkit.core.P2pMessage
import dev.p2pkit.core.P2pSession
import dev.p2pkit.core.PeerAuthorizationPolicy
import dev.p2pkit.core.PeerId
import dev.p2pkit.core.ReconnectPolicy
import dev.p2pkit.core.internal.security.noise.NoiseProtocolException
import dev.p2pkit.core.protocol.FrameCodec
import dev.p2pkit.core.protocol.HelloPayload
import dev.p2pkit.core.protocol.PacketType
import dev.p2pkit.core.testfixtures.CopyingRawConnection
import dev.p2pkit.core.testfixtures.FakeConnectionPair
import dev.p2pkit.core.testfixtures.FakeDataTransport
import dev.p2pkit.core.testfixtures.FakeNetworkPathObserver
import dev.p2pkit.core.testfixtures.MemorySecureIdentityStorage
import dev.p2pkit.core.testfixtures.RecordingLogger
import dev.p2pkit.core.testfixtures.SnapshotList
import dev.p2pkit.core.testfixtures.WireDelivery
import dev.p2pkit.core.testfixtures.WireGoldenBytes
import dev.p2pkit.core.testfixtures.createSecureTestKit
import dev.p2pkit.core.testfixtures.createTestKit
import dev.p2pkit.core.testfixtures.peerForSecureKit
import dev.p2pkit.core.testfixtures.runWireBlocking
import dev.p2pkit.core.transport.DataTransport
import dev.p2pkit.core.transport.RawConnection
import dev.p2pkit.core.transport.TransportContext
import dev.p2pkit.core.transport.TransportDescriptor
import dev.p2pkit.core.transport.TransportFactory
import dev.p2pkit.core.transport.TransportPair
import dev.p2pkit.core.transport.TransportSecurityProfile
import kotlin.concurrent.atomics.AtomicInt
import kotlin.concurrent.atomics.ExperimentalAtomicApi
import kotlin.test.Test
import kotlin.test.assertContentEquals
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertIs
import kotlin.test.assertTrue
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.CoroutineStart
import kotlinx.coroutines.Job
import kotlinx.coroutines.NonCancellable
import kotlinx.coroutines.cancelAndJoin
import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.channels.ClosedReceiveChannelException
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.onStart
import kotlinx.coroutines.flow.onSubscription
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import kotlinx.coroutines.withTimeout

/** Real builders/managers over a synthetic stream, not two platform processes or physical transports. */
@OptIn(ExplicitSecurityRisk::class, ExperimentalAtomicApi::class)
class MixedSecurityProfileIntegrationTest {
    @Test
    fun secureOutgoingToLegacyIncomingFailsClosedOnRepeatedAttempts() = runWireBlocking { delivery ->
        assertMismatch(secureOutgoing = true, delivery)
    }

    @Test
    fun legacyOutgoingToSecureIncomingFailsClosedOnRepeatedAttempts() = runWireBlocking { delivery ->
        assertMismatch(secureOutgoing = false, delivery)
    }

    private suspend fun CoroutineScope.assertMismatch(secureOutgoing: Boolean, delivery: WireDelivery) {
        val pairs = List(2) { FakeConnectionPair(delivery) }
        val dialIndex = AtomicInt(0)
        val outgoingData = FakeDataTransport(outgoingConnection = {
            CopyingRawConnection(pairs[dialIndex.fetchAndAdd(1)].a)
        })
        val incomingData = FakeDataTransport()
        val outgoingTransport = SubscribedDataTransport(outgoingData)
        val incomingTransport = SubscribedDataTransport(incomingData)
        val outgoingLogger = SetupFailureLogger()
        val incomingLogger = SetupFailureLogger()
        val store = MemorySecureIdentityStorage()
        val kits = mutableListOf<P2pKit>()
        val collectors = mutableListOf<Job>()
        val published = SnapshotList<P2pSession>()
        val delivered = SnapshotList<P2pMessage>()
        val nonemptyStores = SnapshotList<List<P2pSession>>()
        try {
            val outgoing = kit(secureOutgoing, outgoingTransport, outgoingLogger, store).also(kits::add)
            val incoming = kit(!secureOutgoing, incomingTransport, incomingLogger, store).also(kits::add)
            for (kit in kits) {
                val subscribed = CompletableDeferred<Unit>()
                collectors += launch(start = CoroutineStart.UNDISPATCHED) {
                    kit.incomingSessions.onSubscription { subscribed.complete(Unit) }.collect { session ->
                        published.add(session)
                        launch(start = CoroutineStart.UNDISPATCHED) {
                            session.incoming.collect { delivered.add(it) }
                        }
                    }
                }
                withTimeout(5_000) { subscribed.await() }
                collectors += launch(start = CoroutineStart.UNDISPATCHED) {
                    kit.sessions.collect { if (it.isNotEmpty()) nonemptyStores.add(it) }
                }
                kit.start()
            }
            withTimeout(5_000) {
                outgoingTransport.subscribed.await()
                incomingTransport.subscribed.await()
            }
            for ((attempt, pair) in pairs.withIndex()) {
                incomingData.emitIncoming(CopyingRawConnection(pair.b))
                val outgoingFailure = withTimeout(5_000) {
                    assertFailsWith<P2pError> { outgoing.connect(peerForSecureKit(incoming)) }
                }
                val incomingFailure = withTimeout(5_000) { incomingLogger.failures.receive() }
                val secureFailure = if (secureOutgoing) outgoingFailure else incomingFailure
                val legacyFailure = if (secureOutgoing) incomingFailure else outgoingFailure
                // The secure endpoint rejects legacy magic before Noise or plaintext HELLO processing.
                assertIs<NoiseProtocolException>(assertIs<P2pError.AuthenticationFailed>(secureFailure).cause)
                // No version reply is sent. EOF is a typed connection failure, not a setup deadline.
                assertIs<ClosedReceiveChannelException>(assertIs<P2pError.ConnectionFailed>(legacyFailure).cause)
                assertEquals(ConnectionState.Closed, pair.a.state.value)
                assertEquals(ConnectionState.Closed, pair.b.state.value)
                assertTrue(outgoing.sessions.value.isEmpty())
                assertTrue(incoming.sessions.value.isEmpty())
                assertEquals(attempt + 1, outgoingData.connectCalls.size)
                assertTrue(incomingData.connectCalls.isEmpty())

                val secureRaw = if (secureOutgoing) pair.a else pair.b
                val legacyRaw = if (secureOutgoing) pair.b else pair.a
                assertContentEquals(
                    if (secureOutgoing) WireGoldenBytes.read("preface-initiator") else ByteArray(0),
                    secureRaw.writtenChunks.fold(ByteArray(0)) { all, bytes -> all + bytes },
                )
                // Exactly one legacy HELLO, no DATA/FILE_DATA/CLOSE/fallback stream on either endpoint.
                val legacyFrame = FrameCodec.decode(legacyRaw.writtenChunks.single(), expectedVersion = 1)
                assertEquals(PacketType.HELLO, legacyFrame.type)
                assertEquals(1, HelloPayload.decode(legacyFrame.payload).protocolVersion)
            }
        } finally {
            withContext(NonCancellable) {
                var cleanupFailure: Throwable? = null
                suspend fun clean(block: suspend () -> Unit) {
                    try {
                        block()
                    } catch (failure: Throwable) {
                        cleanupFailure?.addSuppressed(failure) ?: run { cleanupFailure = failure }
                    }
                }
                kits.forEach { clean { it.stop() } }
                collectors.forEach { clean { it.cancelAndJoin() } }
                pairs.forEach { pair ->
                    clean { pair.a.close() }
                    clean { pair.b.close() }
                }
                clean { store.clear() }
                outgoingLogger.failures.close()
                incomingLogger.failures.close()
                cleanupFailure?.let { throw it }
            }
        }
        // Terminal shutdown joins kit-owned work: a delayed retry cannot escape this final count.
        assertEquals(2, outgoingData.connectCalls.size)
        assertTrue(incomingData.connectCalls.isEmpty())
        assertTrue(outgoingData.isClosed)
        assertTrue(incomingData.isClosed)
        assertTrue(published.snapshot().isEmpty())
        assertTrue(nonemptyStores.snapshot().isEmpty())
        assertTrue(delivered.snapshot().isEmpty())
        outgoingLogger.recorded.assertNoUnexpectedWarnOrError()
        incomingLogger.recorded.assertNoUnexpectedWarnOrError { it.message == INCOMING_FAILURE && it.throwable != null }
        assertEquals(2, incomingLogger.recorded.entries.count { it.message == INCOMING_FAILURE })
    }

    private fun kit(
        secure: Boolean,
        transport: DataTransport,
        logger: P2pLogger,
        store: MemorySecureIdentityStorage,
    ): P2pKit = if (secure) {
        createSecureTestKit(
            appId = AppId("wire.profile.boundary"),
            name = "Secure peer",
            store = store,
            transport = transport,
            authorization = PeerAuthorizationPolicy.AcceptAnyAuthenticatedSameApp,
        ) {
            this.logger = logger
            lifecycle { networkPathObserver = FakeNetworkPathObserver() }
        }
    } else {
        createTestKit {
            appId = AppId("wire.profile.boundary")
            deviceName = "Explicit legacy peer"
            peerIdStorage = InMemoryPeerIdStorage(PeerId("wire-profile-legacy"))
            this.logger = logger
            assertEquals(ReconnectPolicy.Disabled, reconnectPolicy)
            lifecycle { networkPathObserver = FakeNetworkPathObserver() }
            transports {
                register(object : TransportFactory {
                    override val descriptor = TransportDescriptor.dataOnly(transport.type)
                    override fun build(context: TransportContext): TransportPair {
                        assertEquals(TransportSecurityProfile.LegacyPlaintextV1, context.securityProfile)
                        return TransportPair(transport)
                    }
                })
            }
        }
    }
}

private const val INCOMING_FAILURE: String = "Incoming session setup failed"

private class SetupFailureLogger(val recorded: RecordingLogger = RecordingLogger()) : P2pLogger by recorded {
    val failures = Channel<Throwable>(capacity = 2)

    override fun warn(message: String, throwable: Throwable?) {
        recorded.warn(message, throwable)
        if (message == INCOMING_FAILURE && throwable != null) {
            check(failures.trySend(throwable).isSuccess)
        }
    }
}

private class SubscribedDataTransport(private val delegate: DataTransport) : DataTransport by delegate {
    val subscribed = CompletableDeferred<Unit>()

    override fun incomingConnections(): Flow<RawConnection> =
        delegate.incomingConnections().onStart { subscribed.complete(Unit) }
}
