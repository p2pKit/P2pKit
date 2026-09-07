package dev.p2pkit.core.internal.security.noise

import dev.p2pkit.core.AppId
import dev.p2pkit.core.ConnectionState
import dev.p2pkit.core.protocol.DefaultP2pProtocol
import dev.p2pkit.core.protocol.ProtocolConstants
import dev.p2pkit.core.protocol.ProtocolEvent
import dev.p2pkit.core.protocol.ProtocolSessionState
import dev.p2pkit.core.security.EncodedIdentityKeyPair
import dev.p2pkit.core.security.IdentityDerivation
import dev.p2pkit.core.security.PlatformSecurityCryptography
import dev.p2pkit.core.security.platformSecurityCryptography
import dev.p2pkit.core.testfixtures.RecordingLogger
import dev.p2pkit.core.testfixtures.SnapshotList
import dev.p2pkit.core.testfixtures.WireGoldenBytes
import dev.p2pkit.core.testfixtures.WireGoldenInputs
import dev.p2pkit.core.transport.RawConnection
import kotlin.concurrent.atomics.AtomicInt
import kotlin.concurrent.atomics.ExperimentalAtomicApi
import kotlin.test.Test
import kotlin.test.assertContentEquals
import kotlin.test.assertEquals
import kotlin.test.assertIs
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.async
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.flow
import kotlinx.coroutines.flow.onEach
import kotlinx.coroutines.flow.take
import kotlinx.coroutines.flow.toList
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withTimeout

/** Replays an immutable opposite endpoint, never another live encoder from this build. */
class SecureSessionWireGoldenTest {
    @Test
    fun initiatorDecodesFrozenResponderAndProducesFrozenInitiatorBytes() = runBlocking {
        for (readSize in listOf(1, 19, 2_048)) {
            withTimeout(5_000) { replay(NoiseRole.Initiator, readSize) }
        }
    }

    @Test
    fun responderDecodesFrozenInitiatorAndProducesFrozenResponderBytes() = runBlocking {
        for (readSize in listOf(1, 19, 2_048)) {
            withTimeout(5_000) { replay(NoiseRole.Responder, readSize) }
        }
    }

    @Test
    fun prologueAndPrefacesMatchFrozenBytes() {
        val initiator = WireGoldenBytes.read("preface-initiator")
        val responder = WireGoldenBytes.read("preface-responder")
        assertEquals(SecureV2Preface(NoiseRole.Initiator), SecureV2Preface.decode(initiator))
        assertEquals(SecureV2Preface(NoiseRole.Responder), SecureV2Preface.decode(responder))
        assertContentEquals(initiator, SecureV2Preface(NoiseRole.Initiator).encode())
        assertContentEquals(responder, SecureV2Preface(NoiseRole.Responder).encode())
        assertContentEquals(
            WireGoldenBytes.read("prologue"),
            SecureV2Prologue.encode(WireGoldenInputs.APP_ID, initiator, responder),
        )
    }

    private suspend fun CoroutineScope.replay(role: NoiseRole, readSize: Int) {
        println("Frozen secure channel: $role, max raw read $readSize bytes")
        val local = if (role == NoiseRole.Initiator) 0 else 1
        val remote = 1 - local
        val crypto = platformSecurityCryptography()
        val fixedCrypto = FixedEphemeralCryptography(crypto, firstPrivateByte = 64 + local * 32)
        val privateKey = ByteArray(32) { (local * 32 + it).toByte() }
        val localStatic = try {
            NoiseKeyPair(privateKey, crypto.deriveX25519PublicKey(privateKey))
        } finally {
            privateKey.fill(0)
        }
        val raw = GoldenTranscriptConnection(
            WireGoldenBytes.read("session-${if (remote == 0) "initiator" else "responder"}"),
            readSize,
        )
        val pump = SingleCollectorRawPump(raw, this)
        var outcome: SecureV2HandshakeOutcome? = null
        try {
            assertContentEquals(WireGoldenBytes.read("static-public-$local"), localStatic.copyPublicKey())
            var authorizations = 0
            outcome = SecureV2HandshakeDriver(fixedCrypto).establish(
                pump, role, WireGoldenInputs.APP_ID, localStatic,
            ) { remoteStatic ->
                authorizations++
                assertContentEquals(WireGoldenBytes.read("static-public-$remote"), remoteStatic)
                true
            }
            assertEquals(1, authorizations)
            assertEquals(1, fixedCrypto.generatedKeys)
            assertContentEquals(WireGoldenBytes.read("handshake-hash"), outcome.copyHandshakeHash())
            val remotePublic = outcome.copyRemoteStaticPublicKey()
            assertContentEquals(WireGoldenBytes.read("static-public-$remote"), remotePublic)
            val fingerprint = IdentityDerivation.fingerprint(remotePublic, crypto)
            assertEquals(WireGoldenInputs.fingerprints[remote], fingerprint.value)
            val namespace = IdentityDerivation.namespace(AppId(WireGoldenInputs.APP_ID), crypto)
            assertEquals(
                WireGoldenInputs.peerIds[remote],
                IdentityDerivation.peerId(namespace, fingerprint.digestBytes(), crypto).value,
            )

            exchangeApplicationPrefix(outcome.connection, local)
            assertContentEquals(
                WireGoldenBytes.read("session-${if (local == 0) "initiator" else "responder"}"),
                raw.writtenBytes(),
            )
            assertEquals(raw.inputSize, raw.emittedBytes)
        } finally {
            try {
                outcome?.clearMetadata()
                outcome?.connection?.close()
            } finally {
                try {
                    pump.close()
                } finally {
                    localStatic.destroy()
                }
            }
        }
        assertEquals(ConnectionState.Closed, raw.state.value)
        assertEquals(1, raw.readCalls)
        assertEquals(1, raw.closeCalls)
    }

    private suspend fun exchangeApplicationPrefix(connection: RawConnection, local: Int) = coroutineScope {
        val remote = 1 - local
        val logger = RecordingLogger()
        val protocol = DefaultP2pProtocol(
            clock = { 0L },
            random = WireGoldenInputs.messageIds(local),
            version = ProtocolConstants.SECURE_VERSION,
            logger = logger,
        )
        val state = ProtocolSessionState(WireGoldenInputs.peerIds[local], secure = true)
        val helloReceived = CompletableDeferred<ProtocolEvent.Hello>()
        val outgoingSent = CompletableDeferred<Unit>()
        val received = async {
            protocol.events(connection, state).onEach { event ->
                if (event is ProtocolEvent.Hello) {
                    helloReceived.complete(event)
                    // take(3) closes the secure flow; finish local sends before draining its last event.
                    outgoingSent.await()
                }
            }.take(3).toList()
        }
        assertEquals(WireGoldenInputs.hello(remote), helloReceived.await().payload)
        assertEquals(WireGoldenInputs.peerIds[remote], state.remotePeerId)
        assertEquals(setOf("app-message-envelope-v1", "file-commit-sha256-v1"), state.negotiatedFeatures)
        protocol.sendHello(connection, WireGoldenInputs.hello(local))
        protocol.sendMessage(connection, WireGoldenInputs.textMessage(withMetadata = local == 0), state)
        protocol.sendMessage(connection, WireGoldenInputs.binaryMessage(withMetadata = local == 1), state)
        outgoingSent.complete(Unit)
        val events = received.await()
        assertEquals(3, events.size)
        assertEquals(
            WireGoldenInputs.textMessage(withMetadata = remote == 0),
            assertIs<ProtocolEvent.Message>(events[1]).message,
        )
        assertEquals(
            WireGoldenInputs.binaryMessage(withMetadata = remote == 1),
            assertIs<ProtocolEvent.Message>(events[2]).message,
        )
        logger.assertNoUnexpectedWarnOrError()
    }
}

private class FixedEphemeralCryptography(
    private val delegate: PlatformSecurityCryptography,
    private val firstPrivateByte: Int,
) : PlatformSecurityCryptography by delegate {
    var generatedKeys: Int = 0
        private set

    override fun generateX25519KeyPair(): EncodedIdentityKeyPair {
        check(generatedKeys++ == 0) { "Golden handshake requested another ephemeral key" }
        val privateKey = ByteArray(32) { (firstPrivateByte + it).toByte() }
        return try {
            EncodedIdentityKeyPair(privateKey, delegate.deriveX25519PublicKey(privateKey))
        } finally {
            privateKey.fill(0)
        }
    }
}

/** Stays open after input, like an idle peer; EOF would close the pump before the local sends. */
@OptIn(ExperimentalAtomicApi::class)
private class GoldenTranscriptConnection(private val input: ByteArray, private val readSize: Int) : RawConnection {
    private val closed = CompletableDeferred<Unit>()
    private val mutableState = MutableStateFlow(ConnectionState.Connected)
    private val reads = AtomicInt(0)
    private val closes = AtomicInt(0)
    private val emitted = AtomicInt(0)
    private val writes = SnapshotList<ByteArray>()

    override val state: StateFlow<ConnectionState> get() = mutableState
    val readCalls: Int get() = reads.load()
    val closeCalls: Int get() = closes.load()
    val inputSize: Int get() = input.size
    val emittedBytes: Int get() = emitted.load()

    override fun read(): Flow<ByteArray> = flow {
        check(reads.addAndFetch(1) == 1)
        var offset = 0
        while (offset < input.size) {
            val end = minOf(offset + readSize, input.size)
            emitted.addAndFetch(end - offset)
            emit(input.copyOfRange(offset, end))
            offset = end
        }
        closed.await()
    }

    override suspend fun write(bytes: ByteArray) {
        check(!closed.isCompleted)
        writes.add(bytes.copyOf())
    }

    override suspend fun close() {
        closes.addAndFetch(1)
        mutableState.value = ConnectionState.Closed
        closed.complete(Unit)
    }

    fun writtenBytes(): ByteArray = writes.snapshot().fold(ByteArray(0)) { all, part -> all + part }
}
