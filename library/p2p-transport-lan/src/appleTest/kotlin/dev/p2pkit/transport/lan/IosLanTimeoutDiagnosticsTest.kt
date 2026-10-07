package dev.p2pkit.transport.lan

import dev.p2pkit.transport.lan.IosLanTimeoutDiagnostics.Packaging
import dev.p2pkit.transport.lan.IosLanTimeoutDiagnostics.Phase
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.TimeoutCancellationException
import kotlinx.coroutines.async
import kotlinx.coroutines.awaitCancellation
import kotlinx.coroutines.cancel
import kotlinx.coroutines.currentCoroutineContext
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.withTimeout
import kotlinx.coroutines.yield
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertFalse
import kotlin.test.assertNotNull
import kotlin.test.assertSame
import kotlin.test.assertTrue

/** All events and packaging values below are synthetic control data, not native observations. */
class IosLanTimeoutDiagnosticsTest {
    @Test
    fun closedGrammarKeepsOnlyBoundedStateCountersAndIntegers() {
        val diagnostics = IosLanTimeoutDiagnostics(MutableSharedFlow(), { PRESENT_PACKAGING }, {})
        assertTrue(" lastState=UNOBSERVED " in diagnostics.snapshot(Phase.DISCOVERY))
        val events = listOf(
            "[0][browse] nw_browser_start invoked",
            "[1][browse] state -> ready errCode=-2147483648",
            "[2][browse] state -> waiting",
            "[3][browse] state -> failed",
            "[4][browse] state -> cancelled",
            "[999999][browse] state -> raw=0"
        )
        repeat(300) { events.forEach(diagnostics::record) }
        val saturated = diagnostics.snapshot(Phase.DISCOVERY)
        for (counter in listOf("starts", "ready", "waiting", "failed", "cancelled", "other")) {
            assertTrue(" $counter=255 " in saturated)
        }
        assertTrue(" lastRawState=0 " in saturated)
        assertTrue(" lastError=-2147483648 " in saturated)
        diagnostics.record("[9][browse] state -> raw=4294967295 errCode=2147483647")
        assertTrue(" lastRawState=4294967295 " in diagnostics.snapshot(Phase.DISCOVERY))
        diagnostics.record("[10][browse] state -> ready")
        for (phase in Phase.entries) {
            val marker = diagnostics.snapshot(phase)
            assertTrue(" lastState=READY lastRawState=NONE lastError=2147483647 " in marker)
            assertTrue(marker.length <= 512 && marker.all { it.code in 32..126 })
        }
    }

    @Test
    fun rejectsUnrelatedPrivateMalformedAndOversizedTextWithoutChangingState() {
        val diagnostics = IosLanTimeoutDiagnostics(MutableSharedFlow(), { PRESENT_PACKAGING }, {})
        diagnostics.record("[0][browse] state -> waiting errCode=0")
        val before = diagnostics.snapshot(Phase.DISCOVERY)
        val rejected = listOf(
            "[0][peer] state -> ready",
            "[0][browse] peer=SYNTHETIC_PRIVATE_SENTINEL",
            "[0][browse] address=192.0.2.1 TXT=synthetic payload=synthetic",
            "[0][browse] state -> ready peer=SYNTHETIC_PRIVATE_SENTINEL",
            "[0][browse] state -> ready\n",
            "[0][browse] state -> ready\r",
            "[0][browse] state -> ready\u0000",
            "[0][browse] state -> raw=4294967296",
            "[0][browse] state -> raw=-1",
            "[0][browse] state -> raw=00",
            "[0][browse] state -> ready errCode=2147483648",
            "[0][browse] state -> ready errCode=-2147483649",
            "[0][browse] state -> ready errCode=-0",
            "[0][browse] state -> ready errCode=01",
            "[0][browse] state -> ready errCode=+1",
            "[0][browse] nw_browser_start invoked errCode=1",
            "[1000000][browse] state -> ready",
            "[-1][browse] state -> ready",
            "[00][browse] state -> ready",
            "[0][browse] state -> ready" + "x".repeat(100)
        )
        rejected.forEach(diagnostics::record)
        assertEquals(before, diagnostics.snapshot(Phase.DISCOVERY))
    }

    @Test
    fun packagingIsBooleanOnlyNonblankAndSpecificToTheLegacyTestProfile() {
        assertEquals(Packaging(true, false, false), Packaging.from(null, null))
        assertEquals(
            Packaging(true, false, false),
            Packaging.from(" \t\n", listOf(LanConstants.SECURE_SERVICE_TYPE_BONJOUR))
        )
        assertEquals(Packaging(true, false, false), Packaging.from(7, LanConstants.LEGACY_SERVICE_TYPE_BONJOUR))
        val sentinel = "SYNTHETIC_PRIVATE_SENTINEL"
        assertEquals(
            Packaging(true, true, false),
            Packaging.from(sentinel, listOf(LanConstants.SECURE_SERVICE_TYPE_BONJOUR))
        )
        val flags = Packaging.from(sentinel, listOf(7, LanConstants.LEGACY_SERVICE_TYPE_BONJOUR))
        assertEquals(PRESENT_PACKAGING, flags)
        val diagnostics = IosLanTimeoutDiagnostics(MutableSharedFlow(), { flags }, {})
        diagnostics.run {
            val marker = diagnostics.snapshot(Phase.DISCOVERY)
            assertTrue(" packagingReadOk=true usageDescriptionPresent=true requiredBonjourPresent=true" in marker)
            assertFalse(sentinel in marker)
            assertFalse(LanConstants.LEGACY_SERVICE_TYPE_BONJOUR in marker)
        }
        val unavailable = IosLanTimeoutDiagnostics(MutableSharedFlow(), { throw ControlFailure(Any()) }, {})
        unavailable.run {
            val marker = unavailable.snapshot(Phase.DISCOVERY)
            assertTrue(" packagingReadOk=false usageDescriptionPresent=false requiredBonjourPresent=false" in marker)
        }
    }

    @Test
    fun subscribesBeforeTheBodyAndUnsubscribesOnSuccessOrFailure() {
        val events = MutableSharedFlow<String>()
        val notes = mutableListOf<String>()
        val diagnostics = IosLanTimeoutDiagnostics(events, { PRESENT_PACKAGING }, { notes += it })
        assertEquals(7, diagnostics.run {
            assertEquals(1, events.subscriptionCount.value)
            events.emit("[0][browse] state -> ready")
            yield()
            assertTrue(" ready=1 " in diagnostics.snapshot(Phase.DISCOVERY))
            async { 7 }.await()
        })
        assertEquals(0, events.subscriptionCount.value)
        assertTrue(" lastState=UNOBSERVED " in diagnostics.snapshot(Phase.DISCOVERY))
        val failure = ControlFailure(Any())
        assertSame(failure, assertFailsWith<ControlFailure> {
            diagnostics.run<Unit> {
                assertEquals(1, events.subscriptionCount.value)
                throw failure
            }
        })
        assertEquals(0, events.subscriptionCount.value)
        assertTrue(notes.isEmpty())
    }

    @Test
    fun preservesTheRealTimeoutAndOneBoundedNoteEvenWhenTheOutputSinkThrows() {
        val events = MutableSharedFlow<String>()
        val notes = mutableListOf<String>()
        val diagnostics = IosLanTimeoutDiagnostics(events, { PRESENT_PACKAGING }) {
            notes += it
            throw ControlFailure(Any())
        }
        var original: TimeoutCancellationException? = null
        val caught = assertFailsWith<TimeoutCancellationException> {
            diagnostics.run<Unit> {
                diagnostics.withTimeout<Unit>(Phase.DISCOVERY, 1) {
                    try {
                        awaitCancellation()
                    } catch (failure: TimeoutCancellationException) {
                        original = failure
                        throw failure
                    }
                }
            }
        }
        assertSame(assertNotNull(original), caught)
        assertEquals(0, events.subscriptionCount.value)
        assertEquals(3, notes.size)
        val primary = notes.single { it.startsWith("P2PKIT_IOS_LAN_TIMEOUT_V1 ") }
        assertTrue(primary.startsWith("P2PKIT_IOS_LAN_TIMEOUT_V1 phase=DISCOVERY "))
        assertTrue(primary.length <= 512 && primary.all { it.code in 32..126 })
        assertEquals(primary, caught.suppressedExceptions.single().message)
        assertTrue(notes.single { it.startsWith("P2PKIT_IOS_LAN_STAGE_V1 ") }
            .startsWith("P2PKIT_IOS_LAN_STAGE_V1 phase=DISCOVERY "))

        val outside = assertFailsWith<TimeoutCancellationException> {
            diagnostics.run<Unit> { withTimeout<Unit>(1) { awaitCancellation() } }
        }
        assertEquals(0, events.subscriptionCount.value)
        assertEquals(6, notes.size)
        val outsidePrimary = notes.takeLast(3).single { it.startsWith("P2PKIT_IOS_LAN_TIMEOUT_V1 ") }
        assertTrue(outsidePrimary.startsWith("P2PKIT_IOS_LAN_TIMEOUT_V1 phase=OUTSIDE_ANNOTATED_WAIT "))
        assertEquals(outsidePrimary, outside.suppressedExceptions.single().message)
        assertTrue(notes.last().startsWith("P2PKIT_IOS_LAN_STAGE_V1 phase=OUTSIDE_ANNOTATED_WAIT "))
    }

    @Test
    fun ordinaryCancellationAndErrorsPropagateUnchangedAndAlwaysRemoveTheCollector() {
        val events = MutableSharedFlow<String>()
        val notes = mutableListOf<String>()
        val diagnostics = IosLanTimeoutDiagnostics(events, { PRESENT_PACKAGING }, { notes += it })
        val cancellation = CancellationException("synthetic owner cancellation")
        assertSame(cancellation, assertFailsWith<CancellationException> {
            diagnostics.run<Unit> {
                currentCoroutineContext().cancel(cancellation)
                awaitCancellation()
            }
        })
        assertEquals(0, events.subscriptionCount.value)
        val failure = ControlFailure(Any())
        assertSame(failure, assertFailsWith<ControlFailure> { diagnostics.run<Unit> { throw failure } })
        assertEquals(0, events.subscriptionCount.value)
        assertTrue(notes.isEmpty())
    }

    @Test
    fun stageGrammarCountsIndependentFlagsAndSaturatesWithinEveryPhaseBound() {
        val diagnostics = IosLanTimeoutDiagnostics(MutableSharedFlow(), { PRESENT_PACKAGING }, {})
        val primary = diagnostics.snapshot(Phase.DISCOVERY)
        val first = "[0][browse] result change: added=true removed=false txtChanged=false " +
            "batchComplete=true oldNull=true newNull=false"
        diagnostics.record(first)
        assertTrue(" results=1 added=1 removed=0 txtChanged=0 " in diagnostics.stageSnapshot(Phase.DISCOVERY))
        val events = listOf(
            "[0][advertise] started",
            "[1][advertise] listener null (rebind window?) — descriptor deferred to rebind hook",
            "[2][data] listener state -> ready errCode=-2147483648",
            "[3][data] listener state -> failed errCode=2147483647",
            "[4][browse] result change: added=true removed=true txtChanged=true " +
                "batchComplete=false oldNull=false newNull=false",
            "[5][browse] emitPeer: copy_endpoint returned null — skip",
            "[6][browse] emitPeer: malformed TXT record — reject",
            "[7][browse] emitPeer: filter — invalid/bounded TXT schema",
            "[999999][browse] emitPeer: filter — Bonjour service identity does not match TXT peer id"
        )
        repeat(300) { events.forEach(diagnostics::record) }
        for (phase in Phase.entries) {
            val marker = diagnostics.stageSnapshot(phase)
            for (counter in STAGE_COUNTERS) {
                assertTrue(Regex(" $counter=255(?: |$)").containsMatchIn(marker))
            }
            assertTrue(marker.length <= 300 && marker.all { it.code in 32..126 })
        }
        assertEquals(primary, diagnostics.snapshot(Phase.DISCOVERY))
    }

    @Test
    fun stageGrammarRejectsPrivateMalformedAndOversizedLinesWithoutChangingEitherSnapshot() {
        val diagnostics = IosLanTimeoutDiagnostics(MutableSharedFlow(), { PRESENT_PACKAGING }, {})
        val primary = diagnostics.snapshot(Phase.DISCOVERY)
        val stage = diagnostics.stageSnapshot(Phase.DISCOVERY)
        val rejected = listOf(
            "[0][advertise] started peer=SYNTHETIC_PRIVATE_SENTINEL",
            "[0][advertise] starting: peerId=SYNTHETIC_PRIVATE_SENTINEL app=synthetic name=synthetic",
            "[0][browse] emitPeer: txt={synthetic=private} (isUpdate=false)",
            "[0][browse] emitPeer: ACCEPTED Found SYNTHETIC_PRIVATE_SENTINEL pid=synthetic",
            "[0][browse] address=192.0.2.1 TXT=synthetic payload=synthetic",
            "[0][browse] emitPeer: malformed TXT record — reject extra",
            "[0][data] listener state -> ready errCode=-0",
            "[0][data] listener state -> ready errCode=01",
            "[0][data] listener state -> ready errCode=+1",
            "[0][data] listener state -> failed errCode=2147483648",
            "[0][data] listener state -> failed errCode=-2147483649",
            "[0][advertise] started\n",
            "[0][advertise] started\r",
            "[0][advertise] started\u0000",
            "[00][advertise] started",
            "[-1][advertise] started",
            "[1000000][advertise] started",
            "[0][browse] started",
            "[0][browse] result change: added=true removed=false txtChanged=false " +
                "batchComplete=false oldNull=false newNull=1",
            "[0][browse] result change: added=true removed=false txtChanged=false " +
                "batchComplete=false oldNull=false newNull=false extra",
            "[0][advertise] started" + "x".repeat(129)
        )
        rejected.forEach(diagnostics::record)
        assertEquals(primary, diagnostics.snapshot(Phase.DISCOVERY))
        assertEquals(stage, diagnostics.stageSnapshot(Phase.DISCOVERY))
    }

    @Test
    fun stageCompanionPreservesTimeoutIdentityResetsAndNeverAddsAnotherSuppressedNote() {
        val events = MutableSharedFlow<String>()
        val notes = mutableListOf<String>()
        val diagnostics = IosLanTimeoutDiagnostics(events, { PRESENT_PACKAGING }) {
            notes += it
            throw ControlFailure(Any())
        }
        var original: TimeoutCancellationException? = null
        val caught = assertFailsWith<TimeoutCancellationException> {
            diagnostics.run<Unit> {
                events.emit("[0][advertise] started")
                diagnostics.withTimeout<Unit>(Phase.DISCOVERY, 1) {
                    try {
                        awaitCancellation()
                    } catch (failure: TimeoutCancellationException) {
                        original = failure
                        throw failure
                    }
                }
            }
        }
        assertSame(assertNotNull(original), caught)
        assertEquals(0, events.subscriptionCount.value)
        assertEquals(3, notes.size)
        assertEquals(notes.first(), caught.suppressedExceptions.single().message)
        assertTrue(" advStarted=1 " in notes.last())
        assertTrue(notes.last().length <= 300 && notes.last().all { it.code in 32..126 })
        assertFailsWith<TimeoutCancellationException> {
            diagnostics.run<Unit> { diagnostics.withTimeout<Unit>(Phase.REDISCOVERY, 1) { awaitCancellation() } }
        }
        assertEquals(0, events.subscriptionCount.value)
        assertEquals(6, notes.size)
        assertTrue(notes.last().startsWith("P2PKIT_IOS_LAN_STAGE_V1 phase=REDISCOVERY "))
        assertTrue(" advStarted=0 " in notes.last())
        val cancellation = CancellationException("synthetic stage cancellation")
        assertSame(cancellation, assertFailsWith<CancellationException> {
            diagnostics.run<Unit> { throw cancellation }
        })
        val failure = ControlFailure(Any())
        assertSame(failure, assertFailsWith<ControlFailure> { diagnostics.run<Unit> { throw failure } })
        assertEquals(0, events.subscriptionCount.value)
        assertEquals(6, notes.size)
    }

    @Test
    fun nativeFrontierGrammarCountsAndBoundsEveryClosedField() {
        val diagnostics = IosLanTimeoutDiagnostics(MutableSharedFlow(), { PRESENT_PACKAGING }, {})
        val primary = diagnostics.snapshot(Phase.DISCOVERY)
        val stage = diagnostics.stageSnapshot(Phase.DISCOVERY)
        assertTrue(" listenerP2P=UNOBSERVED " in diagnostics.nativeSnapshot(Phase.DISCOVERY))
        diagnostics.record("[0][advertise] native registration: added=true localMatch=true current=true")
        diagnostics.record("[1][advertise] native registration: added=false localMatch=true current=true")
        diagnostics.record("[2][advertise] native registration: added=true localMatch=false current=false")
        diagnostics.record("[3][browse] native result: currentAtEntry=true")
        diagnostics.record("[4][browse] native result: currentAtEntry=false")
        val first = diagnostics.nativeSnapshot(Phase.DISCOVERY)
        assertTrue(" regAdded=1 regRemoved=1 regOwn=1 regOther=0 regStale=1 " in first)
        assertTrue(" rawResults=2 rawCurrent=1 rawStale=1 " in first)
        val events = listOf(
            "[0][advertise] native registration: added=true localMatch=true current=true",
            "[1][advertise] native registration: added=true localMatch=false current=true",
            "[2][advertise] native registration: added=false localMatch=true current=true",
            "[3][advertise] native registration: added=false localMatch=false current=false",
            "[4][browse] native result: currentAtEntry=true",
            "[999999][browse] native result: currentAtEntry=false"
        )
        repeat(300) { events.forEach(diagnostics::record) }
        for (peerToPeer in listOf(false, true)) {
            for (cellularProhibited in listOf(false, true)) {
                for ((tag, kind) in listOf("data" to "TCP", "browse" to "BARE")) {
                    diagnostics.record(
                        "[5][$tag] native params: kind=$kind peerToPeer=$peerToPeer " +
                            "cellularProhibited=$cellularProhibited"
                    )
                }
                val marker = diagnostics.nativeSnapshot(Phase.DISCOVERY)
                val p2p = if (peerToPeer) "TRUE" else "FALSE"
                val cell = if (cellularProhibited) "TRUE" else "FALSE"
                assertTrue(" listenerP2P=$p2p listenerCellBan=$cell " in marker)
                assertTrue(marker.endsWith(" browserP2P=$p2p browserCellBan=$cell"))
            }
        }
        assertEquals(primary, diagnostics.snapshot(Phase.DISCOVERY))
        assertEquals(stage, diagnostics.stageSnapshot(Phase.DISCOVERY))
        for ((label, state) in listOf("ready" to "READY", "failed" to "FAILED", "cancelled" to "CANCELLED")) {
            diagnostics.record("[6][data] listener state -> $label")
            assertTrue(" listenerState=$state listenerRawState=NONE " in diagnostics.nativeSnapshot(Phase.DISCOVERY))
        }
        diagnostics.record("[7][data] listener state -> raw=0 errCode=2147483647")
        assertTrue(" listenerLastError=2147483647 " in diagnostics.nativeSnapshot(Phase.DISCOVERY))
        diagnostics.record("[8][data] listener state -> raw=4294967295 errCode=-2147483648")
        for (phase in Phase.entries) {
            val marker = diagnostics.nativeSnapshot(phase)
            for (counter in NATIVE_COUNTERS) {
                assertTrue(Regex(" $counter=255(?: |$)").containsMatchIn(marker))
            }
            assertTrue(" listenerState=OTHER listenerRawState=4294967295 listenerLastError=-2147483648 " in marker)
            assertTrue(marker.length <= 512 && marker.all { it.code in 32..126 })
        }
    }

    @Test
    fun nativeFrontierRejectsPrivateMalformedAndOversizedInput() {
        val diagnostics = IosLanTimeoutDiagnostics(MutableSharedFlow(), { PRESENT_PACKAGING }, {})
        val primary = diagnostics.snapshot(Phase.DISCOVERY)
        val stage = diagnostics.stageSnapshot(Phase.DISCOVERY)
        val native = diagnostics.nativeSnapshot(Phase.DISCOVERY)
        val rejected = listOf(
            "[0][advertise] native registration: added=true localMatch=true current=true peer=PRIVATE_SENTINEL",
            "[0][advertise] native registration: added=1 localMatch=true current=true",
            "[0][advertise] native registration: added=true localMatch=TRUE current=true",
            "[0][advertise] native registration: added=true localMatch=true current=0",
            "[0][browse] native result: currentAtEntry=true TXT=PRIVATE_SENTINEL",
            "[0][browse] native result: currentAtEntry=TRUE",
            "[0][browse] native result: currentAtEntry=true\n",
            "[0][browse] native result: currentAtEntry=true\r",
            "[0][browse] native result: currentAtEntry=true\u0000",
            "[0][data] native params: kind=BARE peerToPeer=true cellularProhibited=true",
            "[0][browse] native params: kind=TCP peerToPeer=true cellularProhibited=true",
            "[0][peer] native params: kind=BARE peerToPeer=true cellularProhibited=true",
            "[0][browse] native params: kind=BARE peerToPeer=1 cellularProhibited=true",
            "[0][data] native params: kind=TCP peerToPeer=true cellularProhibited=TRUE",
            "[0][data] listener state -> raw=4294967296",
            "[0][data] listener state -> raw=-1",
            "[0][data] listener state -> raw=00",
            "[0][data] listener state -> ready errCode=2147483648",
            "[0][data] listener state -> failed errCode=-2147483649",
            "[0][data] listener state -> cancelled errCode=-0",
            "[0][data] listener state -> raw=0 errCode=01",
            "[0][data] listener state -> raw=0 errCode=+1",
            "[00][browse] native result: currentAtEntry=true",
            "[-1][browse] native result: currentAtEntry=true",
            "[1000000][browse] native result: currentAtEntry=true",
            "[0][browse] native result: currentAtEntry=true" + "x".repeat(129)
        )
        rejected.forEach(diagnostics::record)
        assertEquals(primary, diagnostics.snapshot(Phase.DISCOVERY))
        assertEquals(stage, diagnostics.stageSnapshot(Phase.DISCOVERY))
        assertEquals(native, diagnostics.nativeSnapshot(Phase.DISCOVERY))
    }

    @Test
    fun nativeFrontierCompanionPreservesTimeoutOwnershipAndResets() {
        val events = MutableSharedFlow<String>()
        val notes = mutableListOf<String>()
        val diagnostics = IosLanTimeoutDiagnostics(events, { PRESENT_PACKAGING }) {
            notes += it
            throw ControlFailure(Any())
        }
        var original: TimeoutCancellationException? = null
        val caught = assertFailsWith<TimeoutCancellationException> {
            diagnostics.run<Unit> {
                assertEquals(1, events.subscriptionCount.value)
                events.emit("[0][advertise] native registration: added=true localMatch=true current=true")
                events.emit("[1][browse] native result: currentAtEntry=true")
                events.emit("[2][data] native params: kind=TCP peerToPeer=true cellularProhibited=true")
                diagnostics.withTimeout<Unit>(Phase.DISCOVERY, 1) {
                    try {
                        awaitCancellation()
                    } catch (failure: TimeoutCancellationException) {
                        original = failure
                        throw failure
                    }
                }
            }
        }
        assertSame(assertNotNull(original), caught)
        assertEquals(0, events.subscriptionCount.value)
        assertEquals(3, notes.size)
        assertEquals(notes.first(), caught.suppressedExceptions.single().message)
        val native = notes.single { it.startsWith("P2PKIT_IOS_LAN_NATIVE_V1 ") }
        assertTrue(native.startsWith("P2PKIT_IOS_LAN_NATIVE_V1 phase=DISCOVERY "))
        assertTrue(" regOwn=1 " in native && " rawResults=1 rawCurrent=1 rawStale=0 " in native)
        assertTrue(" listenerP2P=TRUE listenerCellBan=TRUE " in native)
        assertTrue(native.length <= 512 && native.all { it.code in 32..126 })
        assertFailsWith<TimeoutCancellationException> {
            diagnostics.run<Unit> { diagnostics.withTimeout<Unit>(Phase.REDISCOVERY, 1) { awaitCancellation() } }
        }
        assertEquals(0, events.subscriptionCount.value)
        assertEquals(6, notes.size)
        val reset = notes.takeLast(3).single { it.startsWith("P2PKIT_IOS_LAN_NATIVE_V1 ") }
        assertTrue(reset.startsWith("P2PKIT_IOS_LAN_NATIVE_V1 phase=REDISCOVERY "))
        for (counter in NATIVE_COUNTERS) assertTrue(" $counter=0 " in reset)
        assertTrue(" listenerP2P=UNOBSERVED " in reset)
        val cancellation = CancellationException("synthetic native diagnostic cancellation")
        assertSame(cancellation, assertFailsWith<CancellationException> {
            diagnostics.run<Unit> { throw cancellation }
        })
        val failure = ControlFailure(Any())
        assertSame(failure, assertFailsWith<ControlFailure> { diagnostics.run<Unit> { throw failure } })
        assertEquals(0, events.subscriptionCount.value)
        assertEquals(6, notes.size)
    }

    // Extra instance state also prevents JVM coroutine stack recovery from copying this control exception.
    private class ControlFailure(val marker: Any) : IllegalStateException("synthetic diagnostic control")

    private companion object {
        val PRESENT_PACKAGING = Packaging(true, true, true)
        val NATIVE_COUNTERS = listOf(
            "regAdded", "regRemoved", "regOwn", "regOther", "regStale", "rawResults", "rawCurrent", "rawStale"
        )
        val STAGE_COUNTERS = listOf(
            "advStarted", "advDeferred", "listenerReady", "listenerFailed", "results", "added", "removed", "txtChanged",
            "endpointNull", "malformedTxt", "recordRejected", "identityMismatch"
        )
    }
}
