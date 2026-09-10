package dev.p2pkit.core.internal.security.noise

import dev.p2pkit.core.ConnectionState
import dev.p2pkit.core.P2pError
import dev.p2pkit.core.internal.security.ReconnectTransportRetirement
import dev.p2pkit.core.internal.security.SecureTerminalFailureSource
import dev.p2pkit.core.security.PlatformSecurityCryptography
import dev.p2pkit.core.security.platformSecurityCryptography
import dev.p2pkit.core.testfixtures.FakeConnectionPair
import dev.p2pkit.core.testfixtures.FakeRawConnection
import dev.p2pkit.core.testfixtures.runWireTest
import dev.p2pkit.core.transport.RawConnection
import kotlinx.coroutines.CoroutineStart
import kotlinx.coroutines.async
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.take
import kotlinx.coroutines.flow.toList
import kotlinx.coroutines.launch
import kotlinx.coroutines.supervisorScope
import kotlinx.coroutines.test.runTest
import kotlin.test.Test
import kotlin.test.assertContentEquals
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertIs
import kotlin.test.assertNotNull

class SecureV2TransportTest {
    private val cryptography: PlatformSecurityCryptography = platformSecurityCryptography()
    private val driver = SecureV2HandshakeDriver(cryptography)

    @Test
    fun oneRawCollectorCarriesPrefaceHandshakeAndBoundedEncryptedRecords() = runWireTest { delivery ->
        val pair = FakeConnectionPair(delivery)
        val initiatorRaw = CopyingRawConnection(pair.a)
        val responderRaw = CopyingRawConnection(pair.b)
        val initiatorPump = SingleCollectorRawPump(initiatorRaw, this)
        val responderPump = SingleCollectorRawPump(responderRaw, this)
        val initiatorStatic = generatedKeyPair()
        val responderStatic = generatedKeyPair()

        val initiatorDeferred = async {
            driver.establish(initiatorPump, NoiseRole.Initiator, "secure.test", initiatorStatic) { true }
        }
        val responderDeferred = async {
            driver.establish(responderPump, NoiseRole.Responder, "secure.test", responderStatic) { true }
        }
        val initiator = initiatorDeferred.await()
        val responder = responderDeferred.await()
        try {
            assertEquals(1, initiatorRaw.readCalls)
            assertEquals(1, responderRaw.readCalls)
            assertContentEquals(
                responderStatic.copyPublicKey(),
                initiator.copyRemoteStaticPublicKey(),
            )
            assertContentEquals(
                initiatorStatic.copyPublicKey(),
                responder.copyRemoteStaticPublicKey(),
            )
            assertContentEquals(initiator.copyHandshakeHash(), responder.copyHandshakeHash())

            val plaintext = ByteArray(SECURE_RECORD_MAX_PLAINTEXT_BYTES * 2 + 37) { index ->
                (index * 31).toByte()
            }
            val received = async { responder.connection.read().take(3).toList() }
            initiator.connection.write(plaintext)
            val records = received.await()
            assertEquals(listOf(16_384, 16_384, 37), records.map(ByteArray::size))
            assertContentEquals(plaintext.copyOfRange(0, 16_384), records[0])
            assertContentEquals(plaintext.copyOfRange(16_384, 32_768), records[1])
            assertContentEquals(plaintext.copyOfRange(32_768, plaintext.size), records[2])

            // Three handshake writes plus three records; transport records are
            // length-prefixed ciphertext and never equal their plaintext.
            assertEquals(6, pair.a.writtenChunks.size)
            assertEquals(false, pair.a.writtenChunks.takeLast(3).any { it.contentEquals(plaintext) })
        } finally {
            initiator.clearMetadata()
            responder.clearMetadata()
            initiator.connection.close()
            responder.connection.close()
            initiatorStatic.destroy()
            responderStatic.destroy()
        }
    }

    @Test
    fun queuedTamperedRecordIsClassifiedBeforeSecureStateBecomesTerminal() = runWireTest { delivery ->
        val pair = FakeConnectionPair(delivery)
        val initiatorPump = SingleCollectorRawPump(CopyingRawConnection(pair.a), this)
        val responderPump = SingleCollectorRawPump(CopyingRawConnection(pair.b), this)
        val initiatorStatic = generatedKeyPair()
        val responderStatic = generatedKeyPair()
        val initiatorDeferred = async {
            driver.establish(initiatorPump, NoiseRole.Initiator, "secure.test", initiatorStatic) { true }
        }
        val responderDeferred = async {
            driver.establish(responderPump, NoiseRole.Responder, "secure.test", responderStatic) { true }
        }
        val initiator = initiatorDeferred.await()
        val responder = responderDeferred.await()
        try {
            initiator.connection.write("tamper-me".encodeToByteArray())
            val encryptedRecord = pair.a.writtenChunks.last()
            encryptedRecord[encryptedRecord.lastIndex] =
                (encryptedRecord.last().toInt() xor 0x01).toByte()

            // Raw EOF is now queued behind the complete encrypted record.
            // The authenticated connection must not publish raw Closed before
            // its sole reader has verified that queued record.
            pair.a.close()
            testScheduler.runCurrent()
            assertEquals(ConnectionState.Connected, responder.connection.state.value)
            val failureSource = assertIs<SecureTerminalFailureSource>(responder.connection)
            assertEquals(null, failureSource.terminalFailure.value)

            assertFailsWith<NoiseAuthenticationException> {
                responder.connection.read().first()
            }
            assertEquals(ConnectionState.Failed, responder.connection.state.value)
            assertIs<P2pError.AuthenticationFailed>(failureSource.terminalFailure.value)
        } finally {
            initiator.clearMetadata()
            responder.clearMetadata()
            initiator.connection.close()
            responder.connection.close()
            initiatorStatic.destroy()
            responderStatic.destroy()
        }
    }

    @Test
    fun localReconnectRetirementDrainsValidRecordBeforeClassifyingQueuedTamper() = runWireTest { delivery ->
        val pair = FakeConnectionPair(delivery)
        val initiatorPump = SingleCollectorRawPump(CopyingRawConnection(pair.a), this)
        val responderPump = SingleCollectorRawPump(CopyingRawConnection(pair.b), this)
        val initiatorStatic = generatedKeyPair()
        val responderStatic = generatedKeyPair()
        val initiatorDeferred = async {
            driver.establish(initiatorPump, NoiseRole.Initiator, "secure.test", initiatorStatic) { true }
        }
        val responderDeferred = async {
            driver.establish(responderPump, NoiseRole.Responder, "secure.test", responderStatic) { true }
        }
        val initiator = initiatorDeferred.await()
        val responder = responderDeferred.await()
        try {
            // One valid prefix is a positive control: retirement must preserve
            // usable cipher state, not simply classify every remaining read as tampered.
            val validPrefix = "valid-before-retirement".encodeToByteArray()
            initiator.connection.write(validPrefix)
            initiator.connection.write("tamper-me".encodeToByteArray())
            val encryptedRecord = pair.a.writtenChunks.last()
            encryptedRecord[encryptedRecord.lastIndex] =
                (encryptedRecord.last().toInt() xor 0x01).toByte()
            testScheduler.runCurrent()
            assertEquals(ConnectionState.Connected, pair.b.state.value)

            // Enter a real secure write before retirement, held inside the raw
            // transport. Capture its result so the expected failure cannot cancel this test.
            pair.b.suspendWrites()
            val attemptsBeforeBlockedWrite = pair.b.writeAttempts
            val blockedWrite = async(start = CoroutineStart.UNDISPATCHED) {
                runCatching { responder.connection.write("blocked-old-write".encodeToByteArray()) }
            }
            assertEquals(attemptsBeforeBlockedWrite + 1, pair.b.writeAttempts)
            assertEquals(false, blockedWrite.isCompleted)

            // Unlike the existing remote-EOF control, the receiver itself
            // retires its raw transport while its secure reader has not started.
            assertIs<ReconnectTransportRetirement>(responder.connection).retireTransportForReconnect()
            assertEquals(ConnectionState.Closed, pair.b.state.value)
            testScheduler.runCurrent()
            val blockedFailure = assertIs<IllegalStateException>(blockedWrite.await().exceptionOrNull())
            assertEquals("connection closed while write was suspended", blockedFailure.message)
            assertEquals(ConnectionState.Connected, responder.connection.state.value)
            val failureSource = assertIs<SecureTerminalFailureSource>(responder.connection)
            assertEquals(null, failureSource.terminalFailure.value)

            // A newly submitted write must be rejected before another raw write,
            // without turning write refusal into destructive receive-side cleanup.
            val attemptsAfterRetirement = pair.b.writeAttempts
            assertFailsWith<IllegalStateException> {
                responder.connection.write("rejected-new-write".encodeToByteArray())
            }
            assertEquals(attemptsAfterRetirement, pair.b.writeAttempts)
            assertEquals(ConnectionState.Connected, responder.connection.state.value)
            assertEquals(null, failureSource.terminalFailure.value)

            val delivered = mutableListOf<ByteArray>()
            assertFailsWith<NoiseAuthenticationException> {
                responder.connection.read().collect { delivered += it }
            }
            assertEquals(1, delivered.size, "only the valid queued record may publish plaintext")
            assertContentEquals(validPrefix, delivered.single())
            assertEquals(ConnectionState.Failed, responder.connection.state.value)
            assertIs<P2pError.AuthenticationFailed>(failureSource.terminalFailure.value)
        } finally {
            // An earlier assertion must not leave the fixture's non-cancellable writer parked.
            pair.b.resumeWrites()
            initiator.clearMetadata()
            responder.clearMetadata()
            initiator.connection.close()
            responder.connection.close()
            initiatorStatic.destroy()
            responderStatic.destroy()
        }
    }

    @Test
    fun truncatedRecordHeaderOrCiphertextFailsWithoutDeliveringPlaintext() =
        runWireTest { delivery ->
            for (truncated in listOf(byteArrayOf(0), byteArrayOf(0, 32, 1, 2, 3))) {
                val pair = FakeConnectionPair(delivery)
                val initiatorPump = SingleCollectorRawPump(CopyingRawConnection(pair.a), this)
                val responderPump = SingleCollectorRawPump(CopyingRawConnection(pair.b), this)
                val initiatorStatic = generatedKeyPair()
                val responderStatic = generatedKeyPair()
                var initiator: SecureV2HandshakeOutcome? = null
                var responder: SecureV2HandshakeOutcome? = null
                try {
                    val first = async {
                        driver.establish(initiatorPump, NoiseRole.Initiator, "secure.test", initiatorStatic) { true }
                    }
                    val second = async {
                        driver.establish(responderPump, NoiseRole.Responder, "secure.test", responderStatic) { true }
                    }
                    initiator = first.await()
                    val secureResponder = second.await().also { responder = it }
                    pair.a.write(truncated)
                    pair.a.close()
                    val delivered = mutableListOf<ByteArray>()
                    assertFailsWith<NoiseTransportEofException> {
                        secureResponder.connection.read().collect { delivered += it }
                    }
                    assertEquals(0, delivered.size, "an incomplete authenticated record must never publish plaintext")
                    assertEquals(ConnectionState.Failed, secureResponder.connection.state.value)
                    assertEquals(ConnectionState.Closed, pair.a.state.value)
                    assertEquals(ConnectionState.Closed, pair.b.state.value)
                } finally {
                    initiator?.clearMetadata()
                    responder?.clearMetadata()
                    initiator?.connection?.close()
                    responder?.connection?.close()
                    initiatorPump.close()
                    responderPump.close()
                    initiatorStatic.destroy()
                    responderStatic.destroy()
                }
            }
        }

    @Test
    fun malformedRecordHeaderPublishesTerminalProtocolFailure() = runTest {
        val pair = FakeConnectionPair()
        val initiatorPump = SingleCollectorRawPump(CopyingRawConnection(pair.a), this)
        val responderPump = SingleCollectorRawPump(CopyingRawConnection(pair.b), this)
        val initiatorStatic = generatedKeyPair()
        val responderStatic = generatedKeyPair()
        val initiatorDeferred = async {
            driver.establish(initiatorPump, NoiseRole.Initiator, "secure.test", initiatorStatic) { true }
        }
        val responderDeferred = async {
            driver.establish(responderPump, NoiseRole.Responder, "secure.test", responderStatic) { true }
        }
        val initiator = initiatorDeferred.await()
        val responder = responderDeferred.await()
        try {
            // Ciphertext length zero is structurally invalid even before
            // authentication; inject it below the encrypted writer.
            pair.a.write(byteArrayOf(0, 0))
            val failureSource = assertIs<SecureTerminalFailureSource>(responder.connection)

            assertFailsWith<NoiseProtocolException> {
                responder.connection.read().first()
            }

            assertEquals(ConnectionState.Failed, responder.connection.state.value)
            assertIs<P2pError.ProtocolError>(failureSource.terminalFailure.value)
        } finally {
            initiator.clearMetadata()
            responder.clearMetadata()
            initiator.connection.close()
            responder.connection.close()
            initiatorStatic.destroy()
            responderStatic.destroy()
        }
    }

    @Test
    fun unsupportedPrefaceClosesPumpWithoutNoiseOrPlaintextFallback() = runWireTest { delivery ->
        val pair = FakeConnectionPair(delivery)
        val initiatorRaw = CopyingRawConnection(pair.a)
        val peerRaw = CopyingRawConnection(pair.b)
        val pump = SingleCollectorRawPump(initiatorRaw, this)
        val localStatic = generatedKeyPair()
        val peer = launch {
            peerRaw.read().first()
            peerRaw.write(ByteArray(SECURE_V2_PREFACE_SIZE_BYTES))
        }
        try {
            assertFailsWith<NoiseProtocolException> {
                driver.establish(pump, NoiseRole.Initiator, "secure.test", localStatic) { true }
            }
            peer.join()
            assertEquals(ConnectionState.Closed, pair.a.state.value)
            assertEquals(1, pair.a.writeAttempts)
        } finally {
            localStatic.destroy()
            peerRaw.close()
        }
    }

    @Test
    fun rejectedResponderStaticNeverRevealsInitiatorStaticOrWritesThirdFlight() = runTest {
        val pair = FakeConnectionPair()
        val initiatorPump = SingleCollectorRawPump(CopyingRawConnection(pair.a), this)
        val responderPump = SingleCollectorRawPump(CopyingRawConnection(pair.b), this)
        val initiatorStatic = generatedKeyPair()
        val responderStatic = generatedKeyPair()
        var initiatorAuthorizationCalls = 0

        try {
            supervisorScope {
                val initiatorDeferred = async {
                    driver.establish(
                        initiatorPump,
                        NoiseRole.Initiator,
                        "secure.test",
                        initiatorStatic,
                    ) {
                        initiatorAuthorizationCalls += 1
                        false
                    }
                }
                val responderDeferred = async {
                    driver.establish(
                        responderPump,
                        NoiseRole.Responder,
                        "secure.test",
                        responderStatic,
                    ) { true }
                }
                assertFailsWith<NoiseAuthenticationException> { initiatorDeferred.await() }
                assertFailsWith<NoiseTransportEofException> { responderDeferred.await() }
            }
            assertEquals(1, initiatorAuthorizationCalls)
            // Initiator wrote only its preface and message 1. Message 3,
            // which contains its encrypted static key, was never emitted.
            assertEquals(2, pair.a.writeAttempts)
            assertEquals(2, pair.a.writtenChunks.size)
        } finally {
            initiatorStatic.destroy()
            responderStatic.destroy()
        }
    }

    @Test
    fun ambiguousRawWriteFailureClosesConnectionAndRejectsRetry() = runTest {
        val pair = FakeConnectionPair()
        val initiatorPump = SingleCollectorRawPump(CopyingRawConnection(pair.a), this)
        val responderPump = SingleCollectorRawPump(CopyingRawConnection(pair.b), this)
        val initiatorStatic = generatedKeyPair()
        val responderStatic = generatedKeyPair()
        val initiatorDeferred = async {
            driver.establish(initiatorPump, NoiseRole.Initiator, "secure.test", initiatorStatic) { true }
        }
        val responderDeferred = async {
            driver.establish(responderPump, NoiseRole.Responder, "secure.test", responderStatic) { true }
        }
        val initiator = initiatorDeferred.await()
        val responder = responderDeferred.await()
        try {
            pair.a.failNextWrite(IllegalStateException("ambiguous raw write"))
            val first = assertFailsWith<IllegalStateException> {
                initiator.connection.write("secret".encodeToByteArray())
            }
            assertEquals("ambiguous raw write", first.message)
            assertFailsWith<IllegalStateException> {
                initiator.connection.write("retry".encodeToByteArray())
            }
            assertEquals(ConnectionState.Closed, pair.a.state.value)
        } finally {
            initiator.clearMetadata()
            responder.clearMetadata()
            initiator.connection.close()
            responder.connection.close()
            initiatorStatic.destroy()
            responderStatic.destroy()
        }
    }

    private fun generatedKeyPair(): NoiseKeyPair {
        val encoded = cryptography.generateX25519KeyPair()
        val privateKey = encoded.privateKeyBytes()
        val publicKey = encoded.publicKeyBytes()
        return try {
            NoiseKeyPair(privateKey, publicKey)
        } finally {
            encoded.clearPrivate()
            privateKey.wipe()
            publicKey.wipe()
        }
    }
}

private class CopyingRawConnection(
    private val delegate: FakeRawConnection,
) : RawConnection {
    var readCalls: Int = 0
        private set

    override val state: StateFlow<ConnectionState> get() = delegate.state

    override suspend fun write(bytes: ByteArray) {
        delegate.write(bytes.copyOf())
    }

    override fun read(): Flow<ByteArray> {
        readCalls += 1
        return delegate.read()
    }

    override suspend fun close() {
        delegate.close()
    }
}
