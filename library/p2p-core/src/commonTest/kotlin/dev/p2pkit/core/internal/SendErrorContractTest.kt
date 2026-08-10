package dev.p2pkit.core.internal

import dev.p2pkit.core.ConnectionState
import dev.p2pkit.core.FileTransferFailureKind
import dev.p2pkit.core.FileTransferPhase
import dev.p2pkit.core.KeepAliveConfig
import dev.p2pkit.core.P2pError
import dev.p2pkit.core.P2pLogger
import dev.p2pkit.core.P2pMessage
import dev.p2pkit.core.Peer
import dev.p2pkit.core.PeerId
import dev.p2pkit.core.Platform
import dev.p2pkit.core.Retryability
import dev.p2pkit.core.TransportKind
import dev.p2pkit.core.protocol.DefaultP2pProtocol
import dev.p2pkit.core.protocol.ProtocolEvent
import dev.p2pkit.core.testfixtures.FakeConnectionPair
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.launch
import kotlinx.coroutines.test.StandardTestDispatcher
import kotlinx.coroutines.test.TestScope
import kotlinx.coroutines.test.advanceTimeBy
import kotlinx.coroutines.test.runCurrent
import kotlinx.coroutines.test.runTest
import kotlinx.io.Buffer
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertIs
import kotlin.test.assertNull
import kotlin.test.assertSame
import kotlin.test.assertTrue

/**
 * AUDIT-2026-07 (API-2, decision #12a) — coverage plan row P1-05.
 *
 * Pins the typed-error contract at the public [P2pSessionImpl.send] /
 * [P2pSessionImpl.sendFile] boundary:
 *
 *  - an unexpected transport-level write failure surfaces as
 *    [P2pError.ConnectionFailed] with the original exception preserved as the
 *    error's `cause` (identity-asserted), for single-chunk and multi-chunk
 *    sends, and for the variant where [P2pSessionImpl.rearmWith] swaps the
 *    connection between the state pre-check and the write;
 *  - raw `IllegalStateException`-shaped failures never escape the boundary;
 *  - [CancellationException] passes through unwrapped;
 *  - already-typed [P2pError]s ([P2pError.PayloadTooLarge], the
 *    not-Connected pre-check refusal) pass through unchanged (no
 *    double-wrap, `cause` stays null where it was null);
     *  - file-transfer failures use [P2pError.FileTransferFailed] with stable
     *    kind, phase, retryability, transfer-id, and cause fields.
 *
 * Uses fixture F2 (write-fault injection in
 * [dev.p2pkit.core.testfixtures.FakeRawConnection]: `writeFailure`,
 * `failNextWrite`, `suspendWrites`, `writeLatencyMillis`) under `runTest`
 * virtual time, mirroring the KeepAliveTest construction idiom.
 */
@OptIn(ExperimentalCoroutinesApi::class)
@Suppress("DEPRECATION")
class SendErrorContractTest {

    /** Stands in for a raw platform transport exception (e.g. an IOException shape). */
    private class FakeTransportWriteException(message: String) : Exception(message)

    private class Harness(
        val pair: FakeConnectionPair,
        val session: P2pSessionImpl,
        val events: Channel<ProtocolEvent>,
        val scope: CoroutineScope
    )

    private fun TestScope.harness(): Harness {
        val pair = FakeConnectionPair()
        val protocol = DefaultP2pProtocol(clock = { testScheduler.currentTime })
        val supervisor = SupervisorJob()
        val scope = CoroutineScope(StandardTestDispatcher(testScheduler) + supervisor)
        val events = Channel<ProtocolEvent>(Channel.UNLIMITED)
        val peer = Peer(
            id = PeerId("send-error-contract"),
            name = "Test",
            platform = Platform.JVM_DESKTOP,
            supportedTransports = setOf(TransportKind.LAN)
        )
        val session = P2pSessionImpl(
            id = "send-error-contract-session",
            peer = peer,
            initialConnection = pair.a,
            initialEvents = events,
            protocol = protocol,
            parentScope = scope,
            // Long intervals so keep-alive never interferes with the
            // virtual-time choreography of these tests.
            keepAlive = KeepAliveConfig(pingIntervalMillis = 600_000, timeoutMillis = 1_200_000),
            clock = { testScheduler.currentTime },
            logger = P2pLogger.NoOp
        )
        session.start()
        return Harness(pair, session, events, scope)
    }

    // ---- send(): wrap semantics ----

    @Test
    fun singleChunkWriteFailureSurfacesAsConnectionFailedWithCausePreserved() = runTest {
        val h = harness()
        try {
            val raw = FakeTransportWriteException("simulated raw transport write failure")
            h.pair.a.writeFailure = raw

            val err = assertFailsWith<P2pError.ConnectionFailed> {
                h.session.send(P2pMessage.Text("hello"))
            }
            assertSame(raw, err.cause, "original exception must be preserved as cause")
            assertTrue(err.reason.contains("send failed"), "reason should identify the operation: ${err.reason}")
        } finally {
            h.scope.cancel()
        }
    }

    @Test
    fun rawIllegalStateExceptionNeverEscapesSend() = runTest {
        val h = harness()
        try {
            val raw = IllegalStateException("raw internal failure shape")
            h.pair.a.failNextWrite(raw)

            val err = assertFailsWith<P2pError.ConnectionFailed> {
                h.session.send(P2pMessage.Text("hello"))
            }
            assertIs<IllegalStateException>(err.cause)
            assertSame(raw, err.cause)
        } finally {
            h.scope.cancel()
        }
    }

    @Test
    fun multiChunkMidStreamWriteFailureSurfacesAsConnectionFailedWithCause() = runTest {
        val h = harness()
        try {
            // 130 KiB → 3 DATA chunks at the 64 KiB default. 10 ms virtual
            // latency per write lets the test inject the failure between
            // chunk 1 (succeeds) and chunk 2 (fails).
            h.pair.a.writeLatencyMillis = 10
            val payload = ByteArray(130 * 1024) { it.toByte() }

            var thrown: Throwable? = null
            val sendJob = h.scope.launch {
                try {
                    h.session.send(P2pMessage.Binary(payload))
                } catch (e: Throwable) {
                    thrown = e
                }
            }
            runCurrent()
            advanceTimeBy(11) // chunk 1 written; chunk 2 parked in its latency delay
            assertEquals(1, h.pair.a.writtenChunks.size, "first chunk should be on the wire")

            val raw = FakeTransportWriteException("mid-stream write failure")
            h.pair.a.writeFailure = raw
            advanceTimeBy(11) // chunk 2's write now fails
            sendJob.join()

            val err = assertIs<P2pError.ConnectionFailed>(thrown, "expected typed error, got $thrown")
            assertSame(raw, err.cause)
            assertEquals(1, h.pair.a.writtenChunks.size, "no further chunk after the failure")
        } finally {
            h.scope.cancel()
        }
    }

    @Test
    fun rearmSwapBetweenStateCheckAndWriteSurfacesTypedErrorAndKeepsRearmedSessionHealthy() = runTest {
        val h = harness()
        try {
            // Park the in-flight write on the old connection, then rearm. The
            // rearm closes the old connection, which releases the parked
            // writer with a raw IllegalStateException — the boundary must
            // surface it typed while the rearmed session stays Connected.
            h.pair.a.suspendWrites()

            var thrown: Throwable? = null
            val sendJob = h.scope.launch {
                try {
                    h.session.send(P2pMessage.Text("racing a rearm"))
                } catch (e: Throwable) {
                    thrown = e
                }
            }
            runCurrent()
            assertEquals(1, h.pair.a.writeAttempts, "send should be parked inside write()")

            val replacement = FakeConnectionPair()
            val newEvents = Channel<ProtocolEvent>(Channel.UNLIMITED)
            h.session.rearmWith(replacement.a, newEvents)
            // runCurrent, not advanceUntilIdle: the parked-writer release is
            // an un-delayed task, and advancing until idle would fast-forward
            // through the rearmed epoch's keep-alive schedule until it times
            // the session out.
            runCurrent()
            sendJob.join()

            val err = assertIs<P2pError.ConnectionFailed>(thrown, "expected typed error, got $thrown")
            assertIs<IllegalStateException>(err.cause, "the raw release exception must be the cause")
            assertEquals(
                ConnectionState.Connected,
                h.session.state.value,
                "the rearmed session must stay Connected; the failed send was on the old epoch"
            )
        } finally {
            h.scope.cancel()
        }
    }

    @Test
    fun sendQueuedOnOldEpochCannotRedirectOntoReplacementConnection() = runTest {
        val h = harness()
        try {
            h.pair.a.suspendWrites()
            var firstFailure: Throwable? = null
            var queuedFailure: Throwable? = null
            val first = h.scope.launch {
                try {
                    h.session.send(P2pMessage.Text("owns old writer"))
                } catch (failure: Throwable) {
                    firstFailure = failure
                }
            }
            runCurrent()
            assertEquals(1, h.pair.a.writeAttempts)

            val queued = h.scope.launch {
                try {
                    h.session.send(P2pMessage.Text("must not cross epoch"))
                } catch (failure: Throwable) {
                    queuedFailure = failure
                }
            }
            runCurrent()

            val replacement = FakeConnectionPair()
            assertTrue(
                h.session.rearmWith(
                    replacement.a,
                    Channel(Channel.UNLIMITED)
                )
            )
            runCurrent()
            first.join()
            queued.join()

            assertIs<P2pError.ConnectionFailed>(firstFailure)
            assertIs<P2pError.ConnectionFailed>(queuedFailure)
            assertTrue(
                replacement.a.writtenChunks.isEmpty(),
                "a send admitted against the old epoch must never write on the replacement"
            )
            assertEquals(ConnectionState.Connected, h.session.state.value)
        } finally {
            h.scope.cancel()
        }
    }

    // ---- send(): pass-through semantics ----

    @Test
    fun cancellationDuringSendPassesThroughUnwrapped() = runTest {
        val h = harness()
        try {
            h.pair.a.writeLatencyMillis = 1_000

            var thrown: Throwable? = null
            val sendJob = h.scope.launch {
                try {
                    h.session.send(P2pMessage.Text("to be cancelled"))
                } catch (e: Throwable) {
                    thrown = e
                }
            }
            runCurrent() // write parked in its latency delay
            sendJob.cancel()
            sendJob.join()

            assertIs<CancellationException>(thrown, "cancellation must not be wrapped")
            assertTrue(thrown !is P2pError, "cancellation must never surface as P2pError")
        } finally {
            h.scope.cancel()
        }
    }

    @Test
    fun notConnectedPreCheckRefusalPassesThroughUnchanged() = runTest {
        val h = harness()
        try {
            h.session.close()

            val err = assertFailsWith<P2pError.ConnectionFailed> {
                h.session.send(P2pMessage.Text("after close"))
            }
            assertTrue(err.reason.contains("cannot send"), "pre-check refusal shape unchanged: ${err.reason}")
            assertNull(err.cause, "the pre-check refusal carries no cause")
        } finally {
            h.scope.cancel()
        }
    }

    @Test
    fun payloadTooLargePassesThroughUnwrapped() = runTest {
        val h = harness()
        try {
            // One byte over the 4 MiB send() limit — thrown by the chunker
            // inside the wrapped block, must pass through as-is.
            val oversized = ByteArray(4 * 1024 * 1024 + 1)
            assertFailsWith<P2pError.PayloadTooLarge> {
                h.session.send(P2pMessage.Binary(oversized))
            }
            assertEquals(0, h.pair.a.writtenChunks.size, "nothing reaches the wire")
        } finally {
            h.scope.cancel()
        }
    }

    // ---- sendFile(): same boundary contract ----

    @Test
    fun sendFileOfferWriteFailureSurfacesAsTypedTransportFailureWithCausePreserved() = runTest {
        val h = harness()
        try {
            val raw = FakeTransportWriteException("simulated raw transport write failure")
            h.pair.a.writeFailure = raw

            val err = assertFailsWith<P2pError.FileTransferFailed> {
                h.session.sendFile(
                    name = "f.bin",
                    sizeBytes = 16,
                    mimeType = null,
                    source = Buffer().apply { write(ByteArray(16)) }
                )
            }
            assertEquals(FileTransferFailureKind.TRANSPORT, err.kind)
            assertEquals(FileTransferPhase.OFFER, err.phase)
            assertEquals(Retryability.RETRY_NEW_SESSION, err.retryability)
            assertTrue(err.transferId != null)
            assertSame(raw, err.cause, "original exception must be preserved as cause")
            assertTrue(err.reason.contains("FILE_OFFER write failed"), "reason: ${err.reason}")
        } finally {
            h.scope.cancel()
        }
    }

    @Test
    fun sendFileNegativeSizeRefusalIsTypedWithArgumentCause() = runTest {
        val h = harness()
        try {
            val err = assertFailsWith<P2pError.FileTransferFailed> {
                h.session.sendFile(
                    name = "f.bin",
                    sizeBytes = -1,
                    mimeType = null,
                    source = Buffer()
                )
            }
            assertEquals(FileTransferFailureKind.INVALID_METADATA, err.kind)
            assertEquals(FileTransferPhase.OFFER, err.phase)
            assertEquals(Retryability.NOT_RETRYABLE, err.retryability)
            assertNull(err.transferId)
            assertIs<IllegalArgumentException>(err.cause)
        } finally {
            h.scope.cancel()
        }
    }

    @Test
    fun sendFileInvalidNameIsTypedBeforeAnyWireWrite() = runTest {
        val h = harness()
        try {
            val err = assertFailsWith<P2pError.FileTransferFailed> {
                h.session.sendFile(
                    name = "../secret.bin",
                    sizeBytes = 0,
                    mimeType = null,
                    source = Buffer()
                )
            }
            assertEquals(FileTransferFailureKind.INVALID_METADATA, err.kind)
            assertEquals(FileTransferPhase.OFFER, err.phase)
            assertEquals(Retryability.NOT_RETRYABLE, err.retryability)
            assertNull(err.transferId)
            assertIs<IllegalArgumentException>(err.cause)
            assertEquals(0, h.pair.a.writtenChunks.size)
        } finally {
            h.scope.cancel()
        }
    }

    @Test
    fun sendFileAfterSessionCloseIsTypedRemoteDisconnection() = runTest {
        val h = harness()
        try {
            h.session.close()
            val err = assertFailsWith<P2pError.FileTransferFailed> {
                h.session.sendFile("closed.bin", 0, null, Buffer())
            }
            assertEquals(FileTransferFailureKind.REMOTE_DISCONNECTED, err.kind)
            assertEquals(FileTransferPhase.OFFER, err.phase)
            assertEquals(Retryability.RETRY_NEW_SESSION, err.retryability)
            assertNull(err.transferId)
            assertNull(err.cause)
        } finally {
            h.scope.cancel()
        }
    }

    @Test
    fun transferFailureCauseIsDiagnosticAndExcludedFromStableValueShape() = runTest {
        val h = harness()
        try {
            val raw = FakeTransportWriteException("diagnostic")
            h.pair.a.writeFailure = raw
            val err = assertFailsWith<P2pError.FileTransferFailed> {
                h.session.sendFile("cause.bin", 0, null, Buffer())
            }
            val copy = err.copy()
            assertEquals(err, copy)
            assertSame(raw, err.cause)
            assertNull(copy.cause, "copy deliberately excludes the diagnostic platform cause")
        } finally {
            h.scope.cancel()
        }
    }

    @Test
    fun sendFilePayloadTooLargePassesThroughUnwrapped() = runTest {
        val h = harness()
        try {
            assertFailsWith<P2pError.PayloadTooLarge> {
                h.session.sendFile(
                    name = "huge.bin",
                    sizeBytes = 2L * 1024 * 1024 * 1024 + 1, // default maxFileSizeBytes + 1
                    mimeType = null,
                    source = Buffer()
                )
            }
            assertEquals(0, h.pair.a.writtenChunks.size, "nothing reaches the wire")
        } finally {
            h.scope.cancel()
        }
    }

    @Test
    fun cancellationDuringSendFilePassesThroughUnwrapped() = runTest {
        val h = harness()
        try {
            h.pair.a.writeLatencyMillis = 1_000

            var thrown: Throwable? = null
            val sendJob = h.scope.launch {
                try {
                    h.session.sendFile(
                        name = "f.bin",
                        sizeBytes = 16,
                        mimeType = null,
                        source = Buffer().apply { write(ByteArray(16)) }
                    )
                } catch (e: Throwable) {
                    thrown = e
                }
            }
            runCurrent() // FILE_OFFER write parked in its latency delay
            sendJob.cancel()
            sendJob.join()

            assertIs<CancellationException>(thrown, "cancellation must not be wrapped")
            assertTrue(thrown !is P2pError, "cancellation must never surface as P2pError")
        } finally {
            h.scope.cancel()
        }
    }
}
