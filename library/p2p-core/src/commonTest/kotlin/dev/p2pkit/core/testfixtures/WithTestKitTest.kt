package dev.p2pkit.core.testfixtures

import dev.p2pkit.core.AppId
import dev.p2pkit.core.P2pError
import dev.p2pkit.core.P2pKit
import dev.p2pkit.core.P2pState
import dev.p2pkit.core.PeerId
import dev.p2pkit.core.internal.CleanupAggregateException
import dev.p2pkit.core.internal.InMemoryPeerIdStorage
import dev.p2pkit.core.transport.DataTransport
import dev.p2pkit.core.transport.TransportContext
import dev.p2pkit.core.transport.TransportDescriptor
import dev.p2pkit.core.transport.TransportFactory
import dev.p2pkit.core.transport.TransportPair
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.cancel
import kotlinx.coroutines.currentCoroutineContext
import kotlinx.coroutines.ensureActive
import kotlinx.coroutines.launch
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withTimeout
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertIs
import kotlin.test.assertSame
import kotlin.test.assertTrue

class WithTestKitTest {
    @Test
    fun quietScopeStopsBeforeCheckingAndRejectsLateShutdownWarnings() = runBlocking {
        val quiet = FakeDataTransport()
        withTestKit(
            create = { recording ->
                recording.debug("debug is not a failure")
                recording.info("info is not a failure")
                kit(recording, quiet)
            },
            verifyDiagnostics = { recording ->
                assertTrue(quiet.isClosed, "diagnostics must be checked after stop")
                recording.assertNoUnexpectedWarnOrError()
            }
        ) { it.start() }

        val late = FakeDataTransport()
        val lateCause = StatefulTestFailure("late shutdown cause sentinel")
        val failure = assertFailsWith<AssertionError> {
            withTestKit(create = { recording ->
                kit(recording, closing(late) { recording.warn("late shutdown warning", lateCause) })
            }) { it.start() }
        }
        assertTrue(late.isClosed)
        assertTrue(failure.message.orEmpty().contains("late shutdown warning"))
        assertTrue(failure.message.orEmpty().contains("late shutdown cause sentinel"))
    }

    @Test
    fun constructionFailureKeepsItsIdentityAndStillChecksDiagnostics() = runBlocking {
        val constructionFailure = IllegalStateException("constructor sentinel")
        val actual = assertFailsWith<IllegalStateException> {
            withTestKit(create = { recording ->
                recording.warn("construction warning")
                throw constructionFailure
            }) { error("failed construction must not run the body") }
        }
        assertSame(constructionFailure, actual)
        val diagnosticFailure = assertIs<AssertionError>(actual.suppressedExceptions.single())
        assertTrue(diagnosticFailure.message.orEmpty().contains("construction warning"))
    }

    @Test
    fun nestedScopesStopEveryKitAndRetainBodyStopAndDiagnosticFailures() = runBlocking {
        val first = FakeDataTransport()
        val second = FakeDataTransport()
        val bodyFailure = AssertionError("body sentinel")
        val stopFailure = IllegalStateException("stop sentinel")
        val actual = assertFailsWith<AssertionError> {
            withTestKit(create = { recording ->
                kit(recording, closing(first) {
                    recording.warn("first late warning")
                })
            }) { firstKit ->
                withTestKit(create = { recording ->
                    kit(recording, closing(second) {
                        recording.error("second late error")
                        throw stopFailure
                    })
                }) { secondKit ->
                    firstKit.start()
                    secondKit.start()
                    throw bodyFailure
                }
            }
        }
        assertSame(bodyFailure, actual)
        assertTrue(second.isClosed)
        assertTrue(first.isClosed, "one failed stop must not skip another kit's cleanup")
        assertEquals(3, actual.suppressedExceptions.size)
        val cleanup = actual.suppressedExceptions.filterIsInstance<P2pError.ConnectionFailed>().single()
        assertSame(stopFailure, assertIs<CleanupAggregateException>(cleanup.cause).issues.single().cause)
        val diagnosticFailures = actual.suppressedExceptions.filterIsInstance<AssertionError>()
        assertEquals(2, diagnosticFailures.size)
        assertTrue(diagnosticFailures.any { it.message.orEmpty().contains("first late warning") })
        assertTrue(diagnosticFailures.any { it.message.orEmpty().contains("second late error") })
    }

    @Test
    fun cancelledCallerStillStopsAndRetainsTheLateDiagnosticFailure() = runBlocking {
        val transport = FakeDataTransport()
        val cancellation = CancellationException("caller cancelled")
        val observed = CompletableDeferred<CancellationException>()
        var created: P2pKit? = null
        val caller = launch {
            try {
                withTestKit(create = { recording ->
                    kit(recording, closing(transport) { recording.error("cancelled shutdown error") })
                }) { kit ->
                    created = kit
                    kit.start()
                    currentCoroutineContext().cancel(cancellation)
                    currentCoroutineContext().ensureActive()
                }
            } catch (failure: CancellationException) {
                observed.complete(failure)
                throw failure
            }
        }
        val actual = withTimeout(5_000) {
            caller.join()
            observed.await()
        }
        assertSame(cancellation, actual)
        assertTrue(transport.isClosed)
        assertEquals(P2pState.Stopped, created?.state?.value)
        val diagnosticFailure = assertIs<AssertionError>(actual.suppressedExceptions.single())
        assertTrue(diagnosticFailure.message.orEmpty().contains("cancelled shutdown error"))
    }

    private fun kit(recording: RecordingLogger, transport: DataTransport): P2pKit = createTestKit {
        appId = AppId("test.kit.diagnostics")
        deviceName = "Diagnostic fixture"
        peerIdStorage = InMemoryPeerIdStorage(PeerId("diagnostic-fixture"))
        logger = recording
        lifecycle { networkPathObserver = FakeNetworkPathObserver() }
        transports {
            register(object : TransportFactory {
                override val descriptor = TransportDescriptor.dataOnly(transport.type)
                override fun build(context: TransportContext): TransportPair = TransportPair(transport)
            })
        }
    }

    private fun closing(transport: FakeDataTransport, afterClose: () -> Unit): DataTransport =
        object : DataTransport by transport {
            override suspend fun close() {
                transport.close()
                afterClose()
            }
        }
}
