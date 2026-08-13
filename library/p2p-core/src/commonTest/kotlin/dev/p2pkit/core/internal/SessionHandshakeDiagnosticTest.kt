package dev.p2pkit.core.internal

import dev.p2pkit.core.AppId
import dev.p2pkit.core.ExplicitSecurityRisk
import dev.p2pkit.core.KeepAliveConfig
import dev.p2pkit.core.P2pError
import dev.p2pkit.core.P2pLogger
import dev.p2pkit.core.Peer
import dev.p2pkit.core.PeerAuthorizationPolicy
import dev.p2pkit.core.PeerFingerprint
import dev.p2pkit.core.PeerId
import dev.p2pkit.core.Platform
import dev.p2pkit.core.ReconnectPolicy
import dev.p2pkit.core.SecurityMode
import dev.p2pkit.core.TransportKind
import dev.p2pkit.core.internal.security.AuthenticatedV2SecurityEngine
import dev.p2pkit.core.internal.security.noise.wipe
import dev.p2pkit.core.protocol.DefaultP2pProtocol
import dev.p2pkit.core.protocol.HelloPayload
import dev.p2pkit.core.protocol.P2pProtocol
import dev.p2pkit.core.security.IdentityDerivation
import dev.p2pkit.core.security.LocalSecureIdentity
import dev.p2pkit.core.security.PlatformSecurityCryptography
import dev.p2pkit.core.security.platformSecurityCryptography
import dev.p2pkit.core.testfixtures.FakeConnectionPair
import dev.p2pkit.core.testfixtures.FakeDataTransport
import dev.p2pkit.core.transport.InternalPeer
import dev.p2pkit.core.transport.RawConnection
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.async
import kotlinx.coroutines.cancelAndJoin
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withTimeout
import kotlin.test.Test
import kotlin.test.assertIs
import kotlin.test.assertTrue

@OptIn(ExplicitSecurityRisk::class)
class SessionHandshakeDiagnosticTest {
    @Test
    fun callbackCancellationCannotMaskAuthenticatedHelloIdentityMismatch() = runBlocking {
        val appId = AppId("secure.session.diagnostic-cancellation")
        val cryptography = platformSecurityCryptography()
        val aliceIdentity = generateIdentity(appId, cryptography)
        val bobIdentity = generateIdentity(appId, cryptography)
        val pair = FakeConnectionPair()
        val aliceTransport = FakeDataTransport(
            outgoingConnection = { CopyingHandshakeRawConnection(pair.a) }
        )
        val bobTransport = FakeDataTransport(
            preStagedIncoming = listOf(CopyingHandshakeRawConnection(pair.b))
        )
        val aliceJob = SupervisorJob()
        val bobJob = SupervisorJob()
        val aliceScope = CoroutineScope(Dispatchers.Default + aliceJob)
        val bobScope = CoroutineScope(Dispatchers.Default + bobJob)
        val bobLogger = HandshakeFailureLogger()
        val aliceManager = sessionManager(
            scope = aliceScope,
            transport = aliceTransport,
            protocol = ForgedHelloProtocol(
                DefaultP2pProtocol(clock = { 0L }),
                forgedPeerId = "forged-peer-id"
            ),
            appId = appId,
            identity = aliceIdentity,
            cryptography = cryptography,
            logger = P2pLogger.NoOp
        )
        val bobManager = sessionManager(
            scope = bobScope,
            transport = bobTransport,
            protocol = CancellationThrowingErrorProtocol(DefaultP2pProtocol(clock = { 0L })),
            appId = appId,
            identity = bobIdentity,
            cryptography = cryptography,
            logger = bobLogger
        )
        var outgoingAttempt: kotlinx.coroutines.Deferred<Result<dev.p2pkit.core.P2pSession>>? = null
        try {
            bobManager.startAcceptingIncoming(listOf(bobTransport))
            val peer = Peer(
                id = bobIdentity.peerId,
                name = "Bob",
                platform = Platform.JVM_DESKTOP,
                supportedTransports = setOf(TransportKind.LAN)
            )
            outgoingAttempt = async {
                runCatching {
                    aliceManager.connect(
                        peer = peer,
                        internalPeer = InternalPeer(peer, transportHints = emptyList()),
                        lifecycleGeneration = 1L
                    )
                }
            }

            val failure = withTimeout(5_000) { bobLogger.incomingFailure.await() }
            val mismatch = assertIs<P2pError.AuthenticatedIdentityMismatch>(failure)
            assertTrue(mismatch.reason.contains("Encrypted HELLO"))
            withTimeout(5_000) { bobLogger.callbackCancellationDiagnostic.await() }
            assertTrue(bobManager.sessions.value.isEmpty())
        } finally {
            outgoingAttempt?.cancelAndJoin()
            runCatching { aliceManager.shutdownAllSessions() }
            runCatching { bobManager.shutdownAllSessions() }
            aliceJob.cancelAndJoin()
            bobJob.cancelAndJoin()
            runCatching { pair.a.close() }
            runCatching { pair.b.close() }
            aliceIdentity.clearPrivate()
            bobIdentity.clearPrivate()
        }
    }

    private fun sessionManager(
        scope: CoroutineScope,
        transport: FakeDataTransport,
        protocol: P2pProtocol,
        appId: AppId,
        identity: LocalSecureIdentity,
        cryptography: PlatformSecurityCryptography,
        logger: P2pLogger
    ): SessionManager = SessionManager(
        scope = scope,
        transportManager = TransportManager(listOf(transport)),
        protocol = protocol,
        securityMode = SecurityMode.AuthenticatedV2(
            PeerAuthorizationPolicy.AcceptAnyAuthenticatedSameApp
        ),
        localSecureIdentity = identity,
        authenticatedSecurity = AuthenticatedV2SecurityEngine(cryptography),
        keepAlive = KeepAliveConfig(60_000L, 120_000L),
        reconnectPolicy = ReconnectPolicy.Disabled,
        localAppId = appId,
        localPeerId = identity.peerId,
        localDeviceName = "Test peer",
        localPlatform = Platform.JVM_DESKTOP,
        localTransports = setOf(TransportKind.LAN),
        clock = { 0L },
        logger = logger,
        lifecycleGate = DiagnosticAlwaysActiveLifecycleGate
    )

    private fun generateIdentity(
        appId: AppId,
        cryptography: PlatformSecurityCryptography
    ): LocalSecureIdentity {
        val keyPair = cryptography.generateX25519KeyPair()
        val publicKey = keyPair.publicKeyBytes()
        var fingerprintDigest: ByteArray? = null
        return try {
            fingerprintDigest = IdentityDerivation.fingerprintDigest(publicKey, cryptography)
            val fingerprint = PeerFingerprint.fromDigest(fingerprintDigest)
            val peerId = IdentityDerivation.peerId(
                IdentityDerivation.namespace(appId, cryptography),
                fingerprintDigest,
                cryptography
            )
            LocalSecureIdentity(peerId, fingerprint, keyPair)
        } catch (cause: Throwable) {
            keyPair.clearPrivate()
            throw cause
        } finally {
            publicKey.wipe()
            fingerprintDigest?.wipe()
        }
    }
}

private object DiagnosticAlwaysActiveLifecycleGate : SessionLifecycleGate {
    override suspend fun isActive(expectedGeneration: Long?): Boolean = true

    override suspend fun <T : Any> commit(
        expectedGeneration: Long?,
        block: suspend () -> T
    ): T = block()
}

private class ForgedHelloProtocol(
    private val delegate: P2pProtocol,
    private val forgedPeerId: String
) : P2pProtocol by delegate {
    override suspend fun sendHello(connection: RawConnection, hello: HelloPayload) {
        delegate.sendHello(connection, hello.copy(peerId = forgedPeerId))
    }
}

private class CancellationThrowingErrorProtocol(
    delegate: P2pProtocol
) : P2pProtocol by delegate {
    override suspend fun sendError(connection: RawConnection, reason: String) {
        throw CancellationException("protocol rejection callback cancelled itself")
    }
}

private class CopyingHandshakeRawConnection(
    private val delegate: RawConnection
) : RawConnection {
    override val state get() = delegate.state

    override suspend fun write(bytes: ByteArray) = delegate.write(bytes.copyOf())

    override fun read(): Flow<ByteArray> = delegate.read()

    override suspend fun close() = delegate.close()
}

private class HandshakeFailureLogger : P2pLogger {
    val incomingFailure = CompletableDeferred<Throwable>()
    val callbackCancellationDiagnostic = CompletableDeferred<Unit>()

    override fun debug(message: String) {
        if (message.contains("CancellationException from active protocol callback")) {
            callbackCancellationDiagnostic.complete(Unit)
        }
    }

    override fun info(message: String) = Unit

    override fun warn(message: String, throwable: Throwable?) {
        if (message == "Incoming session setup failed" && throwable != null) {
            incomingFailure.complete(throwable)
        }
    }

    override fun error(message: String, throwable: Throwable?) = Unit
}
