package dev.p2pkit.transport.lan

import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.TimeoutCancellationException
import kotlinx.coroutines.awaitCancellation
import kotlinx.coroutines.flow.flow
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withTimeout
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertSame
import kotlin.test.assertTrue

class AppleLanDiscoveryFailureTest {
    @Test
    fun successfulActionIsNotReplacedOrRepeated() = runBlocking {
        var calls = 0
        val actual = traceAppleLanDiscovery(AppleLanDiscoveryStage.INITIAL_PEER) {
            calls++
            7
        }
        assertEquals(7, actual)
        assertEquals(1, calls)
    }

    @Test
    fun timeoutKeepsOriginalInstanceAndOnlyAddsClosedStageContext() = runBlocking {
        val original = assertFailsWith<TimeoutCancellationException> {
            withTimeout(1) { awaitCancellation() }
        }
        val message = original.message
        val observed = assertFailsWith<TimeoutCancellationException> {
            traceAppleLanDiscovery(AppleLanDiscoveryStage.INITIAL_PEER) { throw original }
        }
        assertSame(original, observed)
        assertEquals(message, observed.message)
        assertEquals(
            "APPLE_LAN_DISCOVERY_WAIT_TIMEOUT stage=INITIAL_PEER",
            observed.suppressedExceptions.single().message
        )
    }

    @Test
    fun callerCancellationIsNeitherWrappedNorRelabeled() = runBlocking {
        val original = CancellationException("synthetic caller cancellation")
        val observed = assertFailsWith<CancellationException> {
            traceAppleLanDiscovery(AppleLanDiscoveryStage.REDISCOVERY) { throw original }
        }
        assertSame(original, observed)
        assertTrue(observed.suppressedExceptions.isEmpty())
    }

    @Test
    fun onlyClosedBrowserListenerAndPackagingMarkersAreRetained() {
        assertEquals(
            setOf(
                AppleLanDiscoveryMarker.BROWSER_WAITING,
                AppleLanDiscoveryMarker.BROWSER_ERROR_PRESENT,
                AppleLanDiscoveryMarker.BROWSER_CODE_MINUS_65570
            ),
            appleLanDiscoveryMarkers("[42][browse] state -> waiting errCode=-65570")
        )
        assertEquals(
            setOf(AppleLanDiscoveryMarker.LISTENER_READY),
            appleLanDiscoveryMarkers("[42][data] listener state -> ready")
        )
        assertEquals(
            setOf(AppleLanDiscoveryMarker.MISSING_BONJOUR_SERVICE),
            appleLanDiscoveryMarkers(
                "[42][packaging] startAdvertising: Host Info.plist NSBonjourServices is missing 'private-service'; " +
                    "add the exact service type used by this P2pKit security profile"
            )
        )
        for (line in listOf(
            "[42][peer] private-peer", "[42][browse] state -> waiting errCode=private-secret",
            "[42][browse] state -> ready private-payload", "[42][browse] state -> unknown",
            "x".repeat(4097)
        )) {
            assertTrue(appleLanDiscoveryMarkers(line).isEmpty())
        }
    }

    @Test
    fun observerSubscribesBeforeEventsAndOwnsOnlyItsBoundedCollector() = runBlocking {
        val originalHistory = IosLanDebug.retainHistory
        val originalConsole = IosLanDebug.mirrorToConsole
        val observed = CompletableDeferred<Unit>()
        val retired = CompletableDeferred<Unit>()
        val events = flow {
            try {
                emit("[42][browse] state -> ready")
                emit("[42][peer] private-identity private-payload")
                emit("[42][browse] state -> ready")
                observed.complete(Unit)
                awaitCancellation()
            } finally {
                retired.complete(Unit)
            }
        }
        val trace = AppleLanDiscoveryTrace(events)
        try {
            withTimeout(1_000) { observed.await() }
            assertEquals(setOf(AppleLanDiscoveryMarker.BROWSER_READY), trace.snapshot())
            assertEquals(originalHistory, IosLanDebug.retainHistory)
            assertEquals(originalConsole, IosLanDebug.mirrorToConsole)
        } finally {
            withTimeout(1_000) { trace.close() }
        }
        assertTrue(retired.isCompleted)
        withTimeout(1_000) { trace.close() }
    }

    @Test
    fun timeoutContextContainsOnlyChosenEnumsAndPreservesTheOriginalFailure() = runBlocking {
        val original = assertFailsWith<TimeoutCancellationException> {
            withTimeout(1) { awaitCancellation() }
        }
        val observed = assertFailsWith<TimeoutCancellationException> {
            traceAppleLanDiscovery(
                AppleLanDiscoveryStage.INITIAL_PEER_SET,
                { setOf(AppleLanDiscoveryMarker.BROWSER_WAITING, AppleLanDiscoveryMarker.BROWSER_ERROR_PRESENT) }
            ) { throw original }
        }
        assertSame(original, observed)
        assertEquals(
            listOf(
                "APPLE_LAN_DISCOVERY_WAIT_TIMEOUT stage=INITIAL_PEER_SET",
                "APPLE_LAN_DISCOVERY_OBSERVED marker=BROWSER_ERROR_PRESENT",
                "APPLE_LAN_DISCOVERY_OBSERVED marker=BROWSER_WAITING"
            ),
            observed.suppressedExceptions.map { it.message }
        )
    }
}
