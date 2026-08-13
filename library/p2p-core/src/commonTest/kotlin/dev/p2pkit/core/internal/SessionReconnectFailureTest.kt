package dev.p2pkit.core.internal

import dev.p2pkit.core.ConnectionState
import dev.p2pkit.core.KeepAliveConfig
import dev.p2pkit.core.P2pError
import dev.p2pkit.core.P2pLogger
import dev.p2pkit.core.Peer
import dev.p2pkit.core.PeerId
import dev.p2pkit.core.Platform
import dev.p2pkit.core.TransportKind
import dev.p2pkit.core.internal.security.SecureTerminalFailureSource
import dev.p2pkit.core.protocol.DefaultP2pProtocol
import dev.p2pkit.core.protocol.Frame
import dev.p2pkit.core.protocol.FrameCodec
import dev.p2pkit.core.protocol.FrameFlags
import dev.p2pkit.core.protocol.MessageId
import dev.p2pkit.core.protocol.PacketType
import dev.p2pkit.core.protocol.ProtocolConstants
import dev.p2pkit.core.protocol.ProtocolEvent
import dev.p2pkit.core.protocol.ProtocolFeatures
import dev.p2pkit.core.protocol.ProtocolSessionState
import dev.p2pkit.core.testfixtures.FakeConnectionPair
import dev.p2pkit.core.transfer.FileTransferState
import dev.p2pkit.core.transfer.PreparedFileSource
import dev.p2pkit.core.transfer.Sha256Digest
import dev.p2pkit.core.transport.RawConnection
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.awaitCancellation
import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.launch
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.test.StandardTestDispatcher
import kotlinx.coroutines.test.runTest
import kotlinx.coroutines.withTimeout
import kotlinx.io.Buffer
import kotlin.random.Random
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertIs

@OptIn(ExperimentalCoroutinesApi::class)
class SessionReconnectFailureTest {

    @Test
    fun unexpectedReconnectHandlerFailureTransitionsSessionToFailed() = runTest {
        val fixture = reconnectingSession()
        fixture.session.reconnectHandler = object : ReconnectHandler {
            override suspend fun onConnectionLost(session: P2pSessionImpl) {
                throw IllegalStateException("reconnect driver defect")
            }
        }
        fixture.session.start()

        fixture.events.close()
        testScheduler.runCurrent()

        assertEquals(ConnectionState.Failed, fixture.session.state.value)
        fixture.supervisor.cancel()
    }

    @Test
    fun peerErrorIsReconnectEligibleRatherThanUnconditionallyTerminal() = runTest {
        val fixture = reconnectingSession()
        val handlerEntered = CompletableDeferred<Unit>()
        fixture.session.reconnectHandler = object : ReconnectHandler {
            override suspend fun onConnectionLost(session: P2pSessionImpl) {
                handlerEntered.complete(Unit)
                awaitCancellation()
            }
        }
        fixture.session.start()

        fixture.events.send(ProtocolEvent.PeerError("remote retryable error"))
        handlerEntered.await()

        assertEquals(ConnectionState.Reconnecting, fixture.session.state.value)
        fixture.supervisor.cancel()
    }

    @Test
    fun authenticatedProtocolViolationIsTerminalAndNeverReconnects() = runTest {
        val fixture = reconnectingSession()
        val reconnectCalled = CompletableDeferred<Unit>()
        fixture.session.reconnectHandler = object : ReconnectHandler {
            override suspend fun onConnectionLost(session: P2pSessionImpl) {
                reconnectCalled.complete(Unit)
                awaitCancellation()
            }
        }
        fixture.session.start()

        fixture.events.close(P2pError.ProtocolError("malformed authenticated envelope"))
        testScheduler.runCurrent()

        assertEquals(ConnectionState.Failed, fixture.session.state.value)
        assertEquals(false, reconnectCalled.isCompleted)
        fixture.supervisor.cancel()
    }

    @Test
    fun postHandshakeAuthenticationFailureWinsRawCloseAndNeverReconnects() = runTest {
        val raw = AuthFailingRawConnection()
        val fixture = reconnectingSession(raw)
        val reconnectCalled = CompletableDeferred<Unit>()
        fixture.session.reconnectHandler = object : ReconnectHandler {
            override suspend fun onConnectionLost(session: P2pSessionImpl) {
                reconnectCalled.complete(Unit)
                awaitCancellation()
            }
        }
        fixture.session.start()

        raw.failAuthentication()
        testScheduler.runCurrent()

        assertEquals(ConnectionState.Failed, fixture.session.state.value)
        assertEquals(false, reconnectCalled.isCompleted)
        fixture.supervisor.cancel()
    }

    @Test
    fun postHandshakeStructuralFailureWinsRawCloseAndNeverReconnects() = runTest {
        val raw = AuthFailingRawConnection()
        val fixture = reconnectingSession(raw)
        val reconnectCalled = CompletableDeferred<Unit>()
        fixture.session.reconnectHandler = object : ReconnectHandler {
            override suspend fun onConnectionLost(session: P2pSessionImpl) {
                reconnectCalled.complete(Unit)
                awaitCancellation()
            }
        }
        fixture.session.start()

        raw.failProtocol()
        testScheduler.runCurrent()

        assertEquals(ConnectionState.Failed, fixture.session.state.value)
        assertEquals(false, reconnectCalled.isCompleted)
        fixture.supervisor.cancel()
    }

    @Test
    fun postHandshakeAuthenticationFailureTerminalizesActiveTransferCausally() = runBlocking {
        val raw = AuthFailingRawConnection()
        val protocolState = ProtocolSessionState("local", secure = true).also {
            it.completeHello("remote", ProtocolFeatures.SECURE_V2)
        }
        val fixture = realDispatcherSession(raw, protocolState)
        val reconnectCalled = CompletableDeferred<Unit>()
        fixture.session.reconnectHandler = object : ReconnectHandler {
            override suspend fun onConnectionLost(session: P2pSessionImpl) {
                reconnectCalled.complete(Unit)
                awaitCancellation()
            }
        }
        fixture.session.start()
        val transfer = fixture.session.sendFile(
            name = "authentication.bin",
            mimeType = "application/octet-stream",
            source = object : PreparedFileSource {
                override val sizeBytes: Long = 0
                override val sha256: Sha256Digest = Sha256Digest(ByteArray(32))
                override fun open(): Buffer = Buffer()
            }
        )
        assertEquals(false, reconnectCalled.isCompleted, "offer write must not trigger reconnect")

        raw.failAuthentication()

        withTimeout(5_000) {
            fixture.session.state.first { it == ConnectionState.Failed }
        }
        val transferFailure = withTimeout(5_000) {
            assertIs<FileTransferState.Failed>(
                transfer.state.first { it is FileTransferState.Failed }
            )
        }
        assertEquals(false, reconnectCalled.isCompleted)
        val error = assertIs<P2pError.FileTransferFailed>(transferFailure.error)
        assertEquals(dev.p2pkit.core.FileTransferFailureKind.AUTHENTICATION, error.kind)
        assertEquals(dev.p2pkit.core.Retryability.NOT_RETRYABLE, error.retryability)
        fixture.supervisor.cancel()
    }

    @Test
    fun establishedVersionMismatchIsTerminalAndNeverReconnects() = runTest {
        val pair = FakeConnectionPair()
        val supervisor = SupervisorJob()
        val scope = CoroutineScope(StandardTestDispatcher(testScheduler) + supervisor)
        val events = Channel<ProtocolEvent>(Channel.UNLIMITED)
        val protocol = DefaultP2pProtocol(
            clock = { testScheduler.currentTime },
            version = ProtocolConstants.SECURE_VERSION
        )
        val protocolState = ProtocolSessionState("local", secure = true).also {
            it.completeHello("remote", ProtocolFeatures.SECURE_V2)
        }
        val reader = scope.launch {
            try {
                protocol.events(pair.a, protocolState).collect(events::send)
                events.close()
            } catch (failure: Throwable) {
                events.close(failure)
            }
        }
        val session = P2pSessionImpl(
            id = "established-version-mismatch",
            peer = Peer(
                PeerId("reconnect-peer"),
                "Peer",
                Platform.JVM_DESKTOP,
                setOf(TransportKind.LAN)
            ),
            initialConnection = pair.a,
            initialEvents = events,
            initialReaderJob = reader,
            initialProtocolState = protocolState,
            protocol = protocol,
            parentScope = scope,
            keepAlive = KeepAliveConfig(60_000, 120_000),
            clock = { testScheduler.currentTime },
            logger = P2pLogger.NoOp
        )
        val reconnectCalled = CompletableDeferred<Unit>()
        session.reconnectHandler = object : ReconnectHandler {
            override suspend fun onConnectionLost(session: P2pSessionImpl) {
                reconnectCalled.complete(Unit)
                awaitCancellation()
            }
        }
        session.start()

        pair.b.write(
            FrameCodec.encode(
                Frame(
                    type = PacketType.PING,
                    flags = FrameFlags.LAST_CHUNK.toByte(),
                    messageId = MessageId.random(Random(81)),
                    chunkIndex = 0,
                    totalChunks = 1,
                    payload = ByteArray(0),
                    version = ProtocolConstants.LEGACY_VERSION
                )
            )
        )
        testScheduler.runCurrent()

        assertEquals(ConnectionState.Failed, session.state.value)
        assertEquals(false, reconnectCalled.isCompleted)
        supervisor.cancel()
    }

    private fun kotlinx.coroutines.test.TestScope.reconnectingSession(
        rawConnection: RawConnection? = null,
        protocolState: ProtocolSessionState = ProtocolSessionState.legacy(),
        logger: P2pLogger = P2pLogger.NoOp
    ): SessionFixture {
        val pair = FakeConnectionPair()
        val supervisor = SupervisorJob()
        val scope = CoroutineScope(StandardTestDispatcher(testScheduler) + supervisor)
        val events = Channel<ProtocolEvent>(Channel.UNLIMITED)
        val session = P2pSessionImpl(
            id = "reconnect-handler-failure",
            peer = Peer(
                PeerId("reconnect-peer"),
                "Peer",
                Platform.JVM_DESKTOP,
                setOf(TransportKind.LAN)
            ),
            initialConnection = rawConnection ?: pair.a,
            initialEvents = events,
            initialProtocolState = protocolState,
            protocol = DefaultP2pProtocol(clock = { testScheduler.currentTime }),
            parentScope = scope,
            keepAlive = KeepAliveConfig(60_000, 120_000),
            clock = { testScheduler.currentTime },
            logger = logger
        )
        return SessionFixture(session, events, supervisor)
    }

    private data class SessionFixture(
        val session: P2pSessionImpl,
        val events: Channel<ProtocolEvent>,
        val supervisor: Job
    )

    private fun realDispatcherSession(
        rawConnection: RawConnection,
        protocolState: ProtocolSessionState
    ): SessionFixture {
        val supervisor = SupervisorJob()
        val scope = CoroutineScope(Dispatchers.Default + supervisor)
        val events = Channel<ProtocolEvent>(Channel.UNLIMITED)
        val session = P2pSessionImpl(
            id = "authenticated-transfer-terminal",
            peer = Peer(
                PeerId("reconnect-peer"),
                "Peer",
                Platform.JVM_DESKTOP,
                setOf(TransportKind.LAN)
            ),
            initialConnection = rawConnection,
            initialEvents = events,
            initialProtocolState = protocolState,
            protocol = DefaultP2pProtocol(clock = { 0L }),
            parentScope = scope,
            keepAlive = KeepAliveConfig(60_000, 120_000),
            clock = { 0L },
            logger = P2pLogger.NoOp
        )
        return SessionFixture(session, events, supervisor)
    }
}

private class AuthFailingRawConnection : RawConnection, SecureTerminalFailureSource {
    private val mutableState = MutableStateFlow(ConnectionState.Connected)
    override val state: StateFlow<ConnectionState> = mutableState.asStateFlow()

    private val mutableTerminalFailure = MutableStateFlow<P2pError?>(null)
    override val terminalFailure: StateFlow<P2pError?> = mutableTerminalFailure.asStateFlow()

    override suspend fun write(bytes: ByteArray) = Unit

    override fun read() = kotlinx.coroutines.flow.emptyFlow<ByteArray>()

    override suspend fun close() {
        mutableState.value = ConnectionState.Closed
    }

    fun failAuthentication() {
        mutableTerminalFailure.value = P2pError.AuthenticationFailed(
            "Secure record authentication failed"
        )
        mutableState.value = ConnectionState.Failed
    }

    fun failProtocol() {
        mutableTerminalFailure.value = P2pError.ProtocolError(
            "Secure record ciphertext length is invalid"
        )
        mutableState.value = ConnectionState.Failed
    }
}
