package dev.p2pkit.transport.lan

import dev.p2pkit.transport.lan.IosLanNativeCallbackDiagnostics.Availability
import dev.p2pkit.transport.lan.IosLanTimeoutDiagnostics.CaseId
import dev.p2pkit.transport.lan.IosLanTimeoutDiagnostics.Packaging
import dev.p2pkit.transport.lan.IosLanTimeoutDiagnostics.Phase
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.NonCancellable
import kotlinx.coroutines.TimeoutCancellationException
import kotlinx.coroutines.async
import kotlinx.coroutines.awaitCancellation
import kotlinx.coroutines.cancel
import kotlinx.coroutines.cancelAndJoin
import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.currentCoroutineContext
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.launch
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withContext
import kotlinx.coroutines.withTimeout
import kotlinx.coroutines.yield
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertFalse
import kotlin.test.assertNotNull
import kotlin.test.assertNull
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
        assertEquals(4, notes.size)
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
        assertEquals(8, notes.size)
        val outsidePrimary = notes.takeLast(4).single { it.startsWith("P2PKIT_IOS_LAN_TIMEOUT_V1 ") }
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
        assertEquals(4, notes.size)
        assertEquals(notes.first(), caught.suppressedExceptions.single().message)
        assertTrue(" advStarted=1 " in notes.last())
        assertTrue(notes.last().length <= 300 && notes.last().all { it.code in 32..126 })
        assertFailsWith<TimeoutCancellationException> {
            diagnostics.run<Unit> { diagnostics.withTimeout<Unit>(Phase.REDISCOVERY, 1) { awaitCancellation() } }
        }
        assertEquals(0, events.subscriptionCount.value)
        assertEquals(8, notes.size)
        assertTrue(notes.last().startsWith("P2PKIT_IOS_LAN_STAGE_V1 phase=REDISCOVERY "))
        assertTrue(" advStarted=0 " in notes.last())
        val cancellation = CancellationException("synthetic stage cancellation")
        assertSame(cancellation, assertFailsWith<CancellationException> {
            diagnostics.run<Unit> { throw cancellation }
        })
        val failure = ControlFailure(Any())
        assertSame(failure, assertFailsWith<ControlFailure> { diagnostics.run<Unit> { throw failure } })
        assertEquals(0, events.subscriptionCount.value)
        assertEquals(8, notes.size)
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
        assertEquals(4, notes.size)
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
        assertEquals(8, notes.size)
        val reset = notes.takeLast(4).single { it.startsWith("P2PKIT_IOS_LAN_NATIVE_V1 ") }
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
        assertEquals(8, notes.size)
    }

    @Test
    fun nativeCallbackEpochsKeepClosedHandlesInertAndNewEpochsIsolated() {
        assertNull(IosLanNativeCallbackDiagnostics.captureLease())
        val first = IosLanNativeCallbackDiagnostics.install()
        val oldLease = try {
            assertEquals(Availability.AVAILABLE, first.snapshot().availability)
            assertFalse(first.snapshot().witnessesComplete)
            val lease = assertNotNull(IosLanNativeCallbackDiagnostics.captureLease())
            repeat(2) {
                lease.started()
                lease.ready(currentAtEntry = false)
                lease.ready(currentAtEntry = true)
            }
            assertEquals(1, first.snapshot().created)
            assertEquals(1, first.snapshot().started)
            assertEquals(1, first.snapshot().ready)
            assertTrue(first.snapshot().witnessesComplete)
            repeat(2) { lease.terminal() }
            assertEquals(1, first.snapshot().terminal)
            assertFalse(first.snapshot().witnessesComplete)
            lease
        } finally {
            first.close()
        }
        val closed = first.snapshot()
        assertEquals(Availability.CLOSED, closed.availability)
        assertNull(IosLanNativeCallbackDiagnostics.captureLease())
        val second = IosLanNativeCallbackDiagnostics.install()
        try {
            val untouched = second.snapshot()
            oldLease.started()
            oldLease.ready(currentAtEntry = true)
            oldLease.terminal()
            oldLease.unavailable()
            oldLease.result(currentAtEntry = true, oldNonNull = true, newNonNull = true, batchComplete = true)
            first.close()
            assertEquals(closed, first.snapshot())
            assertEquals(untouched, second.snapshot())
            assertEquals(Availability.AVAILABLE, untouched.availability)
            assertEquals(0, untouched.created)
            assertEquals(0, untouched.raw)
            val current = assertNotNull(IosLanNativeCallbackDiagnostics.captureLease())
            current.started()
            current.ready(currentAtEntry = true)
            assertTrue(second.snapshot().witnessesComplete)
            assertEquals(1, second.snapshot().created)
        } finally {
            second.close()
        }
        assertNull(IosLanNativeCallbackDiagnostics.captureLease())
    }

    @Test
    fun nativeCallbackConcurrentInstallationsFailClosedWithoutStealingTheOwner() {
        runBlocking {
            withTimeout(5_000) {
                val start = CompletableDeferred<Unit>()
                val release = CompletableDeferred<Unit>()
                val installed = Channel<IosLanNativeCallbackDiagnostics.Epoch>(capacity = 2)
                val workers = List(2) {
                    launch(Dispatchers.Default) {
                        start.await()
                        val epoch = IosLanNativeCallbackDiagnostics.install()
                        try {
                            installed.send(epoch)
                            release.await()
                        } finally {
                            epoch.close()
                        }
                    }
                }
                try {
                    start.complete(Unit)
                    val epochs = listOf(installed.receive(), installed.receive())
                    epochs.forEach {
                        assertEquals(Availability.INSTALL_CONFLICT, it.snapshot().availability)
                        assertFalse(it.snapshot().witnessesComplete)
                    }
                    val lease = assertNotNull(IosLanNativeCallbackDiagnostics.captureLease())
                    lease.started()
                    lease.ready(currentAtEntry = true)
                    val owner = epochs.single { it.snapshot().created == 1 }
                    val rejected = epochs.single { it !== owner }
                    rejected.close()
                    assertNotNull(IosLanNativeCallbackDiagnostics.captureLease())
                    assertEquals(2, owner.snapshot().created)
                    assertEquals(Availability.INSTALL_CONFLICT, owner.snapshot().availability)
                    assertFalse(owner.snapshot().witnessesComplete)
                    owner.close()
                    assertNull(IosLanNativeCallbackDiagnostics.captureLease())
                } finally {
                    release.complete(Unit)
                    withContext(NonCancellable) { workers.forEach { it.cancelAndJoin() } }
                    installed.close()
                }
            }
        }
        val next = IosLanNativeCallbackDiagnostics.install()
        try {
            assertEquals(Availability.AVAILABLE, next.snapshot().availability)
            assertEquals(0, next.snapshot().created)
        } finally {
            next.close()
        }
    }

    @Test
    fun nativeCallbackResultsCountCurrentStaleNullAndBatchFlagsIndependently() {
        val epoch = IosLanNativeCallbackDiagnostics.install()
        try {
            val lease = assertNotNull(IosLanNativeCallbackDiagnostics.captureLease())
            lease.started()
            lease.ready(currentAtEntry = false)
            assertEquals(0, epoch.snapshot().ready)
            assertFalse(epoch.snapshot().witnessesComplete)
            lease.ready(currentAtEntry = true)
            for (current in listOf(false, true)) {
                for (old in listOf(false, true)) {
                    for (new in listOf(false, true)) {
                        for (complete in listOf(false, true)) {
                            lease.result(current, old, new, complete)
                        }
                    }
                }
            }
            val seen = epoch.snapshot()
            assertEquals(16, seen.raw)
            assertEquals(8, seen.current)
            assertEquals(8, seen.stale)
            assertEquals(8, seen.oldNonNull)
            assertEquals(8, seen.newNonNull)
            assertEquals(8, seen.batchComplete)
            assertEquals(8, seen.batchIncomplete)
            assertFalse(seen.overflow)
            assertTrue(seen.witnessesComplete)
            lease.terminal()
            lease.result(currentAtEntry = false, oldNonNull = false, newNonNull = false, batchComplete = false)
            assertEquals(17, epoch.snapshot().raw)
            assertEquals(9, epoch.snapshot().stale)
            assertEquals(1, epoch.snapshot().terminal)
            assertFalse(epoch.snapshot().witnessesComplete)
            lease.unavailable()
            assertEquals(Availability.OBSERVER_FAILURE, epoch.snapshot().availability)
            assertFalse(epoch.snapshot().witnessesComplete)
        } finally {
            epoch.close()
        }
    }

    @Test
    fun nativeCallbackCountersSaturateAndOverflowInvalidatesZeroEvidence() {
        assertEquals(255, IosLanNativeCallbackDiagnostics.MAX_COUNTER)
        val events = IosLanNativeCallbackDiagnostics.install()
        try {
            val lease = assertNotNull(IosLanNativeCallbackDiagnostics.captureLease())
            lease.started()
            lease.ready(currentAtEntry = true)
            repeat(255) { lease.result(true, true, true, true) }
            val edge = events.snapshot()
            assertEquals(255, edge.raw)
            assertEquals(255, edge.current)
            assertEquals(255, edge.oldNonNull)
            assertEquals(255, edge.newNonNull)
            assertEquals(255, edge.batchComplete)
            assertEquals(0, edge.stale)
            assertEquals(0, edge.batchIncomplete)
            assertFalse(edge.overflow)
            assertTrue(edge.witnessesComplete)
            lease.result(false, false, false, false)
            val over = events.snapshot()
            assertEquals(255, over.raw)
            assertEquals(1, over.stale)
            assertEquals(1, over.batchIncomplete)
            assertTrue(over.overflow)
            assertFalse(over.witnessesComplete)
            repeat(300) { lease.result(false, false, false, false) }
            assertEquals(255, events.snapshot().stale)
            assertEquals(255, events.snapshot().batchIncomplete)
            assertTrue(events.snapshot().overflow)
        } finally {
            events.close()
        }
        val witnesses = IosLanNativeCallbackDiagnostics.install()
        try {
            repeat(255) {
                val lease = assertNotNull(IosLanNativeCallbackDiagnostics.captureLease())
                repeat(2) {
                    lease.started()
                    lease.ready(currentAtEntry = true)
                    lease.terminal()
                }
            }
            val edge = witnesses.snapshot()
            assertEquals(255, edge.created)
            assertEquals(255, edge.started)
            assertEquals(255, edge.ready)
            assertEquals(255, edge.terminal)
            assertFalse(edge.overflow)
            val extra = assertNotNull(IosLanNativeCallbackDiagnostics.captureLease())
            extra.started()
            extra.ready(currentAtEntry = true)
            extra.terminal()
            val over = witnesses.snapshot()
            assertEquals(255, over.created)
            assertEquals(255, over.started)
            assertEquals(255, over.ready)
            assertEquals(255, over.terminal)
            assertTrue(over.overflow)
            assertFalse(over.witnessesComplete)
        } finally {
            witnesses.close()
        }
    }

    @Test
    fun nativeCallbackTimeoutSnapshotPreservesFailureAndClosesTheCapturedEpoch() {
        val events = MutableSharedFlow<String>()
        val notes = mutableListOf<String>()
        val diagnostics = IosLanTimeoutDiagnostics(events, { PRESENT_PACKAGING }) {
            notes += it
            throw ControlFailure(Any())
        }
        var lease: IosLanNativeCallbackDiagnostics.Lease? = null
        var original: TimeoutCancellationException? = null
        val caught = assertFailsWith<TimeoutCancellationException> {
            diagnostics.run<Unit> {
                lease = assertNotNull(IosLanNativeCallbackDiagnostics.captureLease()).also {
                    it.started()
                    it.ready(currentAtEntry = true)
                    it.result(currentAtEntry = true, oldNonNull = false, newNonNull = true, batchComplete = false)
                }
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
        assertNull(IosLanNativeCallbackDiagnostics.captureLease())
        assertEquals(4, notes.size)
        assertEquals(notes.first(), caught.suppressedExceptions.single().message)
        val direct = notes.single { it.startsWith("P2PKIT_IOS_LAN_CALLBACK_V1 ") }
        assertTrue(" scope=TEST_EPOCH_BROWSER_LEASES " in direct)
        assertTrue(" availability=AVAILABLE " in direct)
        assertTrue(" overflow=false " in direct && " witnessesComplete=true " in direct)
        assertTrue(" raw=1 current=1 stale=0 " in direct)
        assertTrue(" oldNonNull=0 newNonNull=1 batchComplete=0 batchIncomplete=1" in direct)
        assertTrue(direct.length <= 512 && direct.all { it.code in 32..126 })
        val legacy = notes.single { it.startsWith("P2PKIT_IOS_LAN_NATIVE_V1 ") }
        assertTrue(" rawResults=0 rawCurrent=0 rawStale=0 " in legacy)
        val inactive = diagnostics.callbackSnapshot(Phase.DISCOVERY)
        assertNotNull(lease).result(true, true, true, true)
        assertEquals(inactive, diagnostics.callbackSnapshot(Phase.DISCOVERY))
        assertFailsWith<TimeoutCancellationException> {
            diagnostics.run<Unit> { diagnostics.withTimeout<Unit>(Phase.REDISCOVERY, 1) { awaitCancellation() } }
        }
        val next = notes.takeLast(4).single { it.startsWith("P2PKIT_IOS_LAN_CALLBACK_V1 ") }
        assertTrue(" witnessesComplete=false " in next)
        assertTrue(" created=0 started=0 ready=0 terminal=0 raw=0 " in next)
        assertEquals(8, notes.size)
        assertEquals(0, events.subscriptionCount.value)
        assertNull(IosLanNativeCallbackDiagnostics.captureLease())
    }

    @Test
    fun nativeCallbackObserverFactoryFailureCannotReplaceBodyFailureOrCancellation() {
        val events = MutableSharedFlow<String>()
        val notes = mutableListOf<String>()
        val diagnostics = IosLanTimeoutDiagnostics(events, { PRESENT_PACKAGING }) { notes += it }
        val observerFailure = ControlFailure(Any())
        val install: () -> IosLanNativeCallbackDiagnostics.Epoch = { throw observerFailure }
        assertEquals(7, diagnostics.runWithNativeObserver(install) {
            assertEquals(1, events.subscriptionCount.value)
            assertTrue(" availability=OBSERVER_FAILURE " in diagnostics.callbackSnapshot(Phase.DISCOVERY))
            assertTrue(" witnessesComplete=false " in diagnostics.callbackSnapshot(Phase.DISCOVERY))
            7
        })
        val failure = ControlFailure(Any())
        assertSame(failure, assertFailsWith<ControlFailure> {
            diagnostics.runWithNativeObserver<Unit>(install) { throw failure }
        })
        val cancellation = CancellationException("synthetic direct observer cancellation")
        assertSame(cancellation, assertFailsWith<CancellationException> {
            diagnostics.runWithNativeObserver<Unit>(install) {
                currentCoroutineContext().cancel(cancellation)
                awaitCancellation()
            }
        })
        assertEquals(0, events.subscriptionCount.value)
        assertTrue(notes.isEmpty())
        var original: TimeoutCancellationException? = null
        val timeout = assertFailsWith<TimeoutCancellationException> {
            diagnostics.runWithNativeObserver<Unit>(install) {
                diagnostics.withTimeout<Unit>(Phase.DISCOVERY, 1) {
                    try {
                        awaitCancellation()
                    } catch (caught: TimeoutCancellationException) {
                        original = caught
                        throw caught
                    }
                }
            }
        }
        assertSame(assertNotNull(original), timeout)
        assertEquals(notes.first(), timeout.suppressedExceptions.single().message)
        assertEquals(4, notes.size)
        val direct = notes.single { it.startsWith("P2PKIT_IOS_LAN_CALLBACK_V1 ") }
        assertTrue(" availability=OBSERVER_FAILURE " in direct)
        assertTrue(" witnessesComplete=false " in direct)
        assertTrue(" created=0 started=0 ready=0 terminal=0 raw=0 " in direct)
        assertEquals(0, events.subscriptionCount.value)
        assertNull(IosLanNativeCallbackDiagnostics.captureLease())
        val next = IosLanNativeCallbackDiagnostics.install()
        try {
            assertEquals(Availability.AVAILABLE, next.snapshot().availability)
        } finally {
            next.close()
        }
    }

    @Test
    fun nativeCallbackCaseIdentityIsClosedScopedAndResetAcrossEveryExit() {
        assertEquals(
            listOf(
                "CONTROL", "UNSPECIFIED", "LOOPBACK_TEXT", "LOOPBACK_BINARY", "LOOPBACK_FILE",
                "LIFECYCLE_PEER_LOSS", "LIFECYCLE_DISCOVERY_RESTART", "LIFECYCLE_REPEATED_KIT",
                "LIFECYCLE_THREE_PEERS", "LIFECYCLE_CLEAN_REMOTE_STOP", "LIFECYCLE_TRANSFER_CANCEL",
                "LIFECYCLE_ADVERTISE_CHURN", "LIFECYCLE_CONNECT_CLOSE"
            ),
            CaseId.entries.map { it.name }
        )
        val events = MutableSharedFlow<String>()
        val notes = mutableListOf<String>()
        // Even real enum literals here are synthetic CONTROL-suite data, never real-case evidence.
        val diagnostics = IosLanTimeoutDiagnostics(events, { PRESENT_PACKAGING }) {
            notes += it
            throw ControlFailure(Any())
        }
        fun marker(caseId: CaseId): String = diagnostics.callbackSnapshot(Phase.DISCOVERY).also {
            assertTrue(it.startsWith(
                "P2PKIT_IOS_LAN_CALLBACK_V1 phase=DISCOVERY caseId=${caseId.name} scope=TEST_EPOCH_BROWSER_LEASES "
            ))
            assertTrue(it.length <= 512 && it.all { char -> char.code in 32..126 })
        }
        fun reset() {
            assertTrue(" availability=NOT_INSTALLED " in marker(CaseId.UNSPECIFIED))
            assertEquals(0, events.subscriptionCount.value)
            assertNull(IosLanNativeCallbackDiagnostics.captureLease())
        }
        reset()
        assertEquals(7, diagnostics.run {
            marker(CaseId.CONTROL)
            7
        })
        reset()
        var oldLease: IosLanNativeCallbackDiagnostics.Lease? = null
        diagnostics.run(CaseId.LOOPBACK_TEXT) {
            marker(CaseId.LOOPBACK_TEXT)
            oldLease = assertNotNull(IosLanNativeCallbackDiagnostics.captureLease()).also {
                it.started()
                it.ready(currentAtEntry = true)
                it.result(true, false, true, true)
            }
            assertTrue(" raw=1 current=1 stale=0 " in marker(CaseId.LOOPBACK_TEXT))
        }
        reset()
        diagnostics.run(CaseId.LIFECYCLE_DISCOVERY_RESTART) {
            val before = marker(CaseId.LIFECYCLE_DISCOVERY_RESTART)
            assertTrue(" created=0 started=0 ready=0 terminal=0 raw=0 " in before)
            assertNotNull(oldLease).result(true, true, true, true)
            assertNotNull(oldLease).unavailable()
            assertEquals(before, marker(CaseId.LIFECYCLE_DISCOVERY_RESTART))
        }
        reset()
        val failure = ControlFailure(Any())
        assertSame(failure, assertFailsWith<ControlFailure> {
            diagnostics.run<Unit>(CaseId.LOOPBACK_BINARY) {
                marker(CaseId.LOOPBACK_BINARY)
                throw failure
            }
        })
        reset()
        val cancellation = CancellationException("synthetic case-identity cancellation")
        assertSame(cancellation, assertFailsWith<CancellationException> {
            diagnostics.run<Unit>(CaseId.LIFECYCLE_PEER_LOSS) {
                marker(CaseId.LIFECYCLE_PEER_LOSS)
                currentCoroutineContext().cancel(cancellation)
                awaitCancellation()
            }
        })
        reset()
        assertTrue(notes.isEmpty())
        val longestCase = CaseId.LIFECYCLE_DISCOVERY_RESTART
        val longestPhase = Phase.TRANSFER_RECEIVER_TERMINAL
        assertEquals(CaseId.entries.maxOf { it.name.length }, longestCase.name.length)
        assertEquals(Phase.entries.maxOf { it.name.length }, longestPhase.name.length)
        var original: TimeoutCancellationException? = null
        val timeout = assertFailsWith<TimeoutCancellationException> {
            diagnostics.run<Unit>(longestCase) {
                repeat(255) {
                    assertNotNull(IosLanNativeCallbackDiagnostics.captureLease()).also {
                        it.started()
                        it.ready(currentAtEntry = true)
                        it.terminal()
                        it.result(true, true, true, true)
                        it.result(false, false, false, false)
                        it.unavailable()
                    }
                }
                diagnostics.withTimeout<Unit>(longestPhase, 1) {
                    try {
                        awaitCancellation()
                    } catch (caught: TimeoutCancellationException) {
                        original = caught
                        throw caught
                    }
                }
            }
        }
        assertSame(assertNotNull(original), timeout)
        reset()
        assertEquals(4, notes.size)
        assertEquals(notes.first(), timeout.suppressedExceptions.single().message)
        assertTrue(notes.last().startsWith("P2PKIT_IOS_LAN_STAGE_V1 "))
        val direct = notes.single { it.startsWith("P2PKIT_IOS_LAN_CALLBACK_V1 ") }
        assertTrue(direct.startsWith(
            "P2PKIT_IOS_LAN_CALLBACK_V1 phase=${longestPhase.name} caseId=${longestCase.name} " +
                "scope=TEST_EPOCH_BROWSER_LEASES "
        ))
        assertTrue(" availability=OBSERVER_FAILURE overflow=true witnessesComplete=false " in direct)
        for (counter in listOf(
            "created", "started", "ready", "terminal", "raw", "current", "stale",
            "oldNonNull", "newNonNull", "batchComplete", "batchIncomplete"
        )) {
            assertTrue(Regex(" $counter=255(?: |$)").containsMatchIn(direct))
        }
        assertTrue(direct.length <= 512 && direct.all { it.code in 32..126 })
        for (legacy in notes.filterNot { it.startsWith("P2PKIT_IOS_LAN_CALLBACK_V1 ") }) {
            assertFalse("caseId=" in legacy)
        }
        original = null
        val unavailable = assertFailsWith<TimeoutCancellationException> {
            diagnostics.runWithNativeObserver<Unit>({ throw failure }, CaseId.LOOPBACK_FILE) {
                assertTrue(" availability=OBSERVER_FAILURE " in marker(CaseId.LOOPBACK_FILE))
                diagnostics.withTimeout<Unit>(Phase.DISCOVERY, 1) {
                    try {
                        awaitCancellation()
                    } catch (caught: TimeoutCancellationException) {
                        original = caught
                        throw caught
                    }
                }
            }
        }
        assertSame(assertNotNull(original), unavailable)
        reset()
        assertEquals(8, notes.size)
        assertEquals(notes[4], unavailable.suppressedExceptions.single().message)
        val last = notes.takeLast(4).single { it.startsWith("P2PKIT_IOS_LAN_CALLBACK_V1 ") }
        assertTrue(" phase=DISCOVERY caseId=LOOPBACK_FILE scope=TEST_EPOCH_BROWSER_LEASES " in last)
        assertTrue(" availability=OBSERVER_FAILURE " in last && " witnessesComplete=false " in last)
        assertTrue(" created=0 started=0 ready=0 terminal=0 raw=0 " in last)
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
