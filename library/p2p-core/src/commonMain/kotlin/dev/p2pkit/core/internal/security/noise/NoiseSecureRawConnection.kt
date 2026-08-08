package dev.p2pkit.core.internal.security.noise

import dev.p2pkit.core.ConnectionState
import dev.p2pkit.core.transport.RawConnection
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.NonCancellable
import kotlinx.coroutines.TimeoutCancellationException
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.flow
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext
import kotlinx.coroutines.withTimeout

/** Authenticated record stream produced only after a successful v2 handshake. */
internal class NoiseSecureRawConnection(
    private val pump: SingleCollectorRawPump,
    private val sendCipher: NoiseCipherState,
    private val receiveCipher: NoiseCipherState,
) : RawConnection {
    override val state: StateFlow<ConnectionState> get() = pump.state

    private val lifecycleMutex = Mutex()
    private val writeMutex = Mutex()
    private val receiveMutex = Mutex()
    private val readClaimMutex = Mutex()
    private var closed: Boolean = false
    private var readClaimed: Boolean = false

    override suspend fun write(bytes: ByteArray) {
        try {
            writeMutex.withLock {
                ensureOpen()
                if (bytes.isEmpty()) {
                    writeRecord(ByteArray(0))
                } else {
                    var offset = 0
                    while (offset < bytes.size) {
                        val end = minOf(offset + SECURE_RECORD_MAX_PLAINTEXT_BYTES, bytes.size)
                        val plaintext = bytes.copyOfRange(offset, end)
                        try {
                            writeRecord(plaintext)
                        } finally {
                            plaintext.wipe()
                        }
                        offset = end
                    }
                }
            }
        } catch (cause: Throwable) {
            closeAfterFailure(cause)
        }
    }

    override fun read(): Flow<ByteArray> = flow {
        readClaimMutex.withLock {
            check(!readClaimed) { "Secure connection read flow is single-collector" }
            readClaimed = true
        }
        try {
            while (true) {
                val header = pump.readExactlyOrNull(SECURE_RECORD_HEADER_SIZE_BYTES) ?: break
                val ciphertextLength = try {
                    readU16BigEndian(header[0], header[1]).also(SecureRecordFrame::validateCiphertextLength)
                } finally {
                    header.wipe()
                }
                val ciphertext = pump.readExactly(ciphertextLength)
                var plaintext: ByteArray? = null
                var delivered = false
                try {
                    plaintext = receiveMutex.withLock {
                        ensureOpen()
                        receiveCipher.decryptWithAd(ByteArray(0), ciphertext)
                    }
                    if (plaintext.size > SECURE_RECORD_MAX_PLAINTEXT_BYTES) {
                        throw NoiseAuthenticationException("Secure record plaintext exceeds its maximum")
                    }
                    // Flow collectors observe the same ByteArray during emit;
                    // ownership has transferred even when a downstream
                    // short-circuit (for example take()) aborts emit itself.
                    delivered = true
                    emit(plaintext)
                } finally {
                    ciphertext.wipe()
                    if (!delivered) plaintext?.wipe()
                }
            }
            close()
        } catch (cause: Throwable) {
            closeAfterFailure(cause)
        }
    }

    override suspend fun close() {
        closeInternal(primaryFailure = null)
    }

    private suspend fun writeRecord(plaintext: ByteArray) {
        var ciphertext: ByteArray? = null
        var frame: ByteArray? = null
        try {
            ciphertext = sendCipher.encryptWithAd(ByteArray(0), plaintext)
            frame = SecureRecordFrame.encode(ciphertext)
            pump.write(frame)
        } finally {
            ciphertext?.wipe()
            frame?.wipe()
        }
    }

    private suspend fun ensureOpen() {
        lifecycleMutex.withLock {
            check(!closed) { "Secure connection is closed" }
        }
    }

    private suspend fun closeAfterFailure(primaryFailure: Throwable): Nothing {
        closeInternal(primaryFailure)
        throw primaryFailure
    }

    private suspend fun closeInternal(primaryFailure: Throwable?) {
        var cleanupFailure: Throwable? = null
        withContext(NonCancellable) {
            val ownsClose = lifecycleMutex.withLock {
                if (closed) false else {
                    closed = true
                    true
                }
            }
            if (ownsClose) {
                // Close the underlying stream first so a blocked raw read or
                // write can release its directional mutex. Both the pump and
                // the subsequent cipher cleanup are independently bounded.
                try {
                    withContext(Dispatchers.Default) {
                        withTimeout(SECURE_V2_CLEANUP_TIMEOUT_MILLIS) {
                            pump.close()
                        }
                    }
                } catch (cause: Throwable) {
                    cleanupFailure = normalizeCleanupFailure(
                        cause,
                        "Timed out closing the secure raw pump",
                    )
                }
                try {
                    withContext(Dispatchers.Default) {
                        withTimeout(SECURE_V2_CLEANUP_TIMEOUT_MILLIS) {
                            writeMutex.withLock { sendCipher.destroy() }
                            receiveMutex.withLock { receiveCipher.destroy() }
                        }
                    }
                } catch (cause: Throwable) {
                    val normalized = normalizeCleanupFailure(
                        cause,
                        "Timed out clearing secure cipher state",
                    )
                    cleanupFailure = cleanupFailure?.also {
                        it.addSuppressed(normalized)
                    } ?: normalized
                }
            }
        }

        if (primaryFailure != null) {
            cleanupFailure?.let(primaryFailure::addSuppressed)
            return
        }
        cleanupFailure?.let { throw it }
    }

    private fun normalizeCleanupFailure(cause: Throwable, timeoutMessage: String): Throwable =
        if (cause is TimeoutCancellationException) NoiseProtocolException(timeoutMessage) else cause
}
