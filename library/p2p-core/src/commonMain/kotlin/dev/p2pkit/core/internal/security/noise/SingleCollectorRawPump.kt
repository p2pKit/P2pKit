package dev.p2pkit.core.internal.security.noise

import dev.p2pkit.core.ConnectionState
import dev.p2pkit.core.transport.RawConnection
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Deferred
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.NonCancellable
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.async
import kotlinx.coroutines.cancel
import kotlinx.coroutines.cancelAndJoin
import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.collect
import kotlinx.coroutines.launch
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.TimeoutCancellationException
import kotlinx.coroutines.withContext
import kotlinx.coroutines.withTimeout

private const val RAW_PUMP_CHANNEL_CAPACITY: Int = 4
private const val RAW_PUMP_SEGMENT_BYTES: Int = 16_384

/**
 * Sole collector of a [RawConnection]'s single-use read flow. Handshake and
 * transport code consume the same bounded byte pump, so no reader can start on
 * the unprotected connection and later bypass the secure stream.
 */
internal class SingleCollectorRawPump(
    private val rawConnection: RawConnection,
    parentScope: CoroutineScope,
) {
    val state: StateFlow<ConnectionState> get() = rawConnection.state

    private val ownerJob = SupervisorJob(parentScope.coroutineContext[Job])
    private val ownerScope = CoroutineScope(parentScope.coroutineContext + ownerJob)
    private val chunks = Channel<ByteArray>(
        capacity = RAW_PUMP_CHANNEL_CAPACITY,
        onUndeliveredElement = { bytes -> bytes.wipe() },
    )
    private val readMutex = Mutex()
    private val rawCloseMutex = Mutex()
    private val rawCloseScope = CoroutineScope(SupervisorJob() + Dispatchers.Default)
    private var currentChunk: ByteArray? = null
    private var currentOffset: Int = 0
    private var rawCloseAttempted: Boolean = false
    private var rawCloseTask: Deferred<Throwable?>? = null

    private val collectorJob = ownerScope.launch {
        var primaryFailure: Throwable? = null
        try {
            rawConnection.read().collect { bytes ->
                var offset = 0
                while (offset < bytes.size) {
                    val end = minOf(offset + RAW_PUMP_SEGMENT_BYTES, bytes.size)
                    val segment = bytes.copyOfRange(offset, end)
                    try {
                        chunks.send(segment)
                    } catch (cause: Throwable) {
                        segment.wipe()
                        throw cause
                    }
                    offset = end
                }
            }
        } catch (cause: Throwable) {
            primaryFailure = cause
        } finally {
            val closeFailure = withContext(NonCancellable) { closeRawWithinDeadline() }
            if (primaryFailure != null && closeFailure != null) {
                primaryFailure.addSuppressed(closeFailure)
            } else if (primaryFailure == null) {
                primaryFailure = closeFailure
            }
            chunks.close(primaryFailure)
        }
    }

    suspend fun write(bytes: ByteArray) {
        rawConnection.write(bytes)
    }

    suspend fun readExactly(byteCount: Int): ByteArray =
        readExactlyOrNull(byteCount)
            ?: throw NoiseTransportEofException("Raw connection ended before $byteCount bytes were available")

    suspend fun readExactlyOrNull(byteCount: Int): ByteArray? {
        require(byteCount >= 0) { "byteCount must not be negative" }
        if (byteCount == 0) return ByteArray(0)
        return readMutex.withLock {
            val result = ByteArray(byteCount)
            var resultOffset = 0
            try {
                while (resultOffset < byteCount) {
                    var chunk = currentChunk
                    if (chunk == null) {
                        val received = chunks.receiveCatching()
                        chunk = received.getOrNull()
                        if (chunk == null) {
                            val failure = received.exceptionOrNull()
                            if (failure != null) throw failure
                            if (resultOffset == 0) {
                                result.wipe()
                                return@withLock null
                            }
                            throw NoiseTransportEofException(
                                "Raw connection ended after $resultOffset of $byteCount required bytes",
                            )
                        }
                        currentChunk = chunk
                        currentOffset = 0
                    }

                    val copyCount = minOf(byteCount - resultOffset, chunk.size - currentOffset)
                    chunk.copyInto(
                        destination = result,
                        destinationOffset = resultOffset,
                        startIndex = currentOffset,
                        endIndex = currentOffset + copyCount,
                    )
                    resultOffset += copyCount
                    currentOffset += copyCount
                    if (currentOffset == chunk.size) {
                        chunk.wipe()
                        currentChunk = null
                        currentOffset = 0
                    }
                }
                result
            } catch (cause: Throwable) {
                result.wipe()
                throw cause
            }
        }
    }

    suspend fun close() {
        val closeFailure = withContext(NonCancellable) {
            var failure = closeRawWithinDeadline()
            ownerJob.cancel(CancellationException("Secure raw pump closed"))
            try {
                withTimeout(SECURE_V2_CLEANUP_TIMEOUT_MILLIS) {
                    collectorJob.cancelAndJoin()
                }
            } catch (_: TimeoutCancellationException) {
                failure = failure.combineCleanupFailure(
                    NoiseProtocolException("Timed out stopping the secure raw collector"),
                )
            }
            currentChunk?.wipe()
            currentChunk = null
            currentOffset = 0
            chunks.cancel()
            failure
        }
        closeFailure?.let { throw it }
    }

    private suspend fun closeRawWithinDeadline(): Throwable? {
        val task = rawCloseMutex.withLock {
            if (rawCloseAttempted) {
                checkNotNull(rawCloseTask) { "Raw close ownership was latched without a task" }
            } else {
                // Latch before scheduling untrusted transport cleanup. The
                // detached task lets the caller honor its deadline even if a
                // transport close ignores coroutine cancellation or blocks.
                rawCloseAttempted = true
                rawCloseScope.async {
                    try {
                        rawConnection.close()
                        null
                    } catch (cause: Throwable) {
                        cause
                    }
                }.also { rawCloseTask = it }
            }
        }
        // The detached close runs on Default, so its deadline must use that
        // same real dispatcher. Otherwise a virtual-time test dispatcher can
        // advance the timeout before the close task receives one CPU turn.
        return withContext(Dispatchers.Default) {
            try {
                val result = withTimeout(SECURE_V2_CLEANUP_TIMEOUT_MILLIS) {
                    task.await()
                }
                rawCloseScope.cancel()
                result
            } catch (_: TimeoutCancellationException) {
                // Do not join here: a broken close implementation may be
                // non-cancellable. Cancellation stops cooperative implementations.
                rawCloseScope.cancel(CancellationException("Raw secure transport close timed out"))
                NoiseProtocolException("Timed out closing the raw secure transport")
            } catch (_: CancellationException) {
                NoiseProtocolException("Raw secure transport close did not complete")
            }
        }
    }
}

private fun Throwable?.combineCleanupFailure(additional: Throwable): Throwable =
    this?.also { it.addSuppressed(additional) } ?: additional
