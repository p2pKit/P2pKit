package dev.p2pkit.transport.lan

import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.CoroutineStart
import kotlinx.coroutines.NonCancellable
import kotlinx.coroutines.TimeoutCancellationException
import kotlinx.coroutines.cancelAndJoin
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withContext
import platform.Foundation.NSBundle

/** Test-only, process-wide best-effort observations; never a per-peer diagnosis or a raw event history. */
internal class IosLanTimeoutDiagnostics(
    private val events: SharedFlow<String> = IosLanDebug.events,
    private val packaging: () -> Packaging = { currentPackaging() },
    private val output: (String) -> Unit = { println(it) }
) {
    enum class Phase {
        DISCOVERY, REDISCOVERY, DISCOVERY_1, DISCOVERY_2, DISCOVERY_3,
        PEER_LOSS, LOCAL_WITHDRAWAL,
        HANDSHAKE_INCOMING, HANDSHAKE_OUTGOING, HANDSHAKE_CONNECTED,
        HANDSHAKE_1, HANDSHAKE_2, HANDSHAKE_3, CLEAN_CLOSE,
        MESSAGE_RECEIVE, FILE_OFFER, TRANSFER_PROGRESS,
        TRANSFER_SENDER_TERMINAL, TRANSFER_RECEIVER_TERMINAL, OUTSIDE_ANNOTATED_WAIT
    }

    enum class CaseId {
        CONTROL, UNSPECIFIED,
        LOOPBACK_TEXT, LOOPBACK_BINARY, LOOPBACK_FILE,
        LIFECYCLE_PEER_LOSS, LIFECYCLE_DISCOVERY_RESTART, LIFECYCLE_REPEATED_KIT,
        LIFECYCLE_THREE_PEERS, LIFECYCLE_CLEAN_REMOTE_STOP, LIFECYCLE_TRANSFER_CANCEL,
        LIFECYCLE_ADVERTISE_CHURN, LIFECYCLE_CONNECT_CLOSE
    }

    data class Packaging(
        val readOk: Boolean,
        val usageDescriptionPresent: Boolean,
        val requiredBonjourPresent: Boolean
    ) {
        companion object {
            fun from(usage: Any?, services: Any?): Packaging = Packaging(
                readOk = true,
                usageDescriptionPresent = !(usage as? String).isNullOrBlank(),
                requiredBonjourPresent = (services as? List<*>)
                    ?.any { it == LanConstants.LEGACY_SERVICE_TYPE_BONJOUR } == true
            )
        }
    }

    private enum class State { UNOBSERVED, READY, WAITING, FAILED, CANCELLED, OTHER }
    private enum class Flag { UNOBSERVED, TRUE, FALSE }

    private data class NativeFrontier(
        val regAdded: Int = 0,
        val regRemoved: Int = 0,
        val regOwn: Int = 0,
        val regOther: Int = 0,
        val regStale: Int = 0,
        val rawResults: Int = 0,
        val rawCurrent: Int = 0,
        val rawStale: Int = 0,
        val listenerState: State = State.UNOBSERVED,
        val listenerRawState: Long? = null,
        val listenerLastError: Int? = null,
        val listenerP2P: Flag = Flag.UNOBSERVED,
        val listenerCellBan: Flag = Flag.UNOBSERVED,
        val browserP2P: Flag = Flag.UNOBSERVED,
        val browserCellBan: Flag = Flag.UNOBSERVED
    )

    private enum class StageEvent {
        ADVERTISE_STARTED, ADVERTISE_DEFERRED, ENDPOINT_NULL, MALFORMED_TXT, RECORD_REJECTED, IDENTITY_MISMATCH
    }

    private data class Stages(
        val advStarted: Int = 0,
        val advDeferred: Int = 0,
        val listenerReady: Int = 0,
        val listenerFailed: Int = 0,
        val results: Int = 0,
        val added: Int = 0,
        val removed: Int = 0,
        val txtChanged: Int = 0,
        val endpointNull: Int = 0,
        val malformedTxt: Int = 0,
        val recordRejected: Int = 0,
        val identityMismatch: Int = 0
    )

    private data class Observation(
        val starts: Int = 0,
        val ready: Int = 0,
        val waiting: Int = 0,
        val failed: Int = 0,
        val cancelled: Int = 0,
        val other: Int = 0,
        val lastState: State = State.UNOBSERVED,
        val lastRawState: Long? = null,
        val lastError: Int? = null,
        val observationsAvailable: Boolean = true,
        val packaging: Packaging = Packaging(false, false, false),
        val stages: Stages = Stages(),
        val native: NativeFrontier = NativeFrontier()
    )

    private val observation = MutableStateFlow(Observation())
    private val reported = MutableStateFlow(false)
    private val nativeEpoch = MutableStateFlow<IosLanNativeCallbackDiagnostics.Epoch?>(null)
    private val nativeObserverFailed = MutableStateFlow(false)
    private val currentCaseId = MutableStateFlow(CaseId.UNSPECIFIED)

    /** One runBlocking, with the original body and its async children owned by that same scope. */
    fun <T> run(caseId: CaseId = CaseId.CONTROL, block: suspend CoroutineScope.() -> T): T =
        runWithNativeObserver({ IosLanNativeCallbackDiagnostics.install() }, caseId, block)

    /** Acquisition fault seam for controls; no replacement test scope or callback injector. */
    fun <T> runWithNativeObserver(
        install: () -> IosLanNativeCallbackDiagnostics.Epoch,
        caseId: CaseId = CaseId.CONTROL,
        block: suspend CoroutineScope.() -> T
    ): T {
        val flags = try {
            packaging()
        } catch (_: Throwable) {
            Packaging(false, false, false)
        }
        observation.value = Observation(packaging = flags)
        reported.value = false
        nativeObserverFailed.value = false
        var epoch: IosLanNativeCallbackDiagnostics.Epoch? = null
        try {
            currentCaseId.value = caseId
            epoch = try {
                install()
            } catch (_: Throwable) {
                nativeObserverFailed.value = true
                null
            }
            nativeEpoch.value = epoch
            return runBlocking {
                val collector = launch(start = CoroutineStart.UNDISPATCHED) {
                    try {
                        events.collect { record(it) }
                    } catch (cancellation: CancellationException) {
                        throw cancellation
                    } catch (_: Throwable) {
                        // A diagnostic observer must not cancel the test's scope.
                        observation.update { it.copy(observationsAvailable = false) }
                    }
                }
                try {
                    block(this)
                } finally {
                    withContext(NonCancellable) { collector.cancelAndJoin() }
                }
            }
        } catch (failure: TimeoutCancellationException) {
            report(Phase.OUTSIDE_ANNOTATED_WAIT, failure)
            throw failure
        } finally {
            try {
                epoch?.close()
            } catch (_: Throwable) {
                // Observer cleanup can never replace success, cancellation or the real failure.
            }
            nativeEpoch.value = null
            nativeObserverFailed.value = false
            observation.value = Observation()
            reported.value = false
            currentCaseId.value = CaseId.UNSPECIFIED
        }
    }

    suspend fun <T> withTimeout(phase: Phase, timeMillis: Long, block: suspend CoroutineScope.() -> T): T {
        try {
            return kotlinx.coroutines.withTimeout(timeMillis, block)
        } catch (failure: TimeoutCancellationException) {
            report(phase, failure)
            throw failure
        }
    }

    /** Only closed native grammars are admitted; the original string is never retained. */
    fun record(line: String) {
        if (line.length <= MAX_STAGE_INPUT_CHARS) {
            recordNative(line)
            recordStage(line)
        }
        if (line.length > MAX_INPUT_CHARS) return
        val match = BROWSE_LINE.matchEntire(line) ?: return
        val label = match.groupValues[1]
        if (label.isEmpty()) {
            observation.update { it.copy(starts = increment(it.starts)) }
            return
        }
        val rawText = match.groupValues[2]
        val raw = if (rawText.isEmpty()) null else (rawText.toLongOrNull() ?: return)
        if (raw != null && raw > MAX_RAW_STATE) return
        val errorText = match.groupValues[3]
        val error = if (errorText.isEmpty()) null else (errorText.toIntOrNull() ?: return)
        if (error != null && error.toString() != errorText) return
        val nextState = when (label) {
            "ready" -> State.READY
            "waiting" -> State.WAITING
            "failed" -> State.FAILED
            "cancelled" -> State.CANCELLED
            else -> State.OTHER
        }
        observation.update {
            it.copy(
                ready = if (nextState == State.READY) increment(it.ready) else it.ready,
                waiting = if (nextState == State.WAITING) increment(it.waiting) else it.waiting,
                failed = if (nextState == State.FAILED) increment(it.failed) else it.failed,
                cancelled = if (nextState == State.CANCELLED) increment(it.cancelled) else it.cancelled,
                other = if (nextState == State.OTHER) increment(it.other) else it.other,
                lastState = nextState,
                lastRawState = raw,
                lastError = error ?: it.lastError
            )
        }
    }

    /** Callback-entry/registration observations are not distinct peers or proof of later admission. */
    private fun recordNative(line: String) {
        val registration = NATIVE_REGISTRATION_LINE.matchEntire(line)
        if (registration != null) {
            val added = registration.groupValues[1] == "true"
            val localMatch = registration.groupValues[2] == "true"
            val current = registration.groupValues[3] == "true"
            observation.update {
                val seen = it.native
                it.copy(native = seen.copy(
                    regAdded = if (current && added) increment(seen.regAdded) else seen.regAdded,
                    regRemoved = if (current && !added) increment(seen.regRemoved) else seen.regRemoved,
                    regOwn = if (current && added && localMatch) increment(seen.regOwn) else seen.regOwn,
                    regOther = if (current && added && !localMatch) increment(seen.regOther) else seen.regOther,
                    regStale = if (!current) increment(seen.regStale) else seen.regStale
                ))
            }
            return
        }
        val result = NATIVE_RESULT_LINE.matchEntire(line)
        if (result != null) {
            val current = result.groupValues[1] == "true"
            observation.update {
                val seen = it.native
                it.copy(native = seen.copy(
                    rawResults = increment(seen.rawResults),
                    rawCurrent = if (current) increment(seen.rawCurrent) else seen.rawCurrent,
                    rawStale = if (!current) increment(seen.rawStale) else seen.rawStale
                ))
            }
            return
        }
        val parameters = NATIVE_PARAMETERS_LINE.matchEntire(line)
        if (parameters != null) {
            val listener = parameters.groupValues[1] == "data"
            if (parameters.groupValues[2] != if (listener) "TCP" else "BARE") return
            val peerToPeer = if (parameters.groupValues[3] == "true") Flag.TRUE else Flag.FALSE
            val cellularProhibited = if (parameters.groupValues[4] == "true") Flag.TRUE else Flag.FALSE
            observation.update {
                val seen = it.native
                it.copy(native = if (listener) {
                    seen.copy(listenerP2P = peerToPeer, listenerCellBan = cellularProhibited)
                } else {
                    seen.copy(browserP2P = peerToPeer, browserCellBan = cellularProhibited)
                })
            }
            return
        }
        val listener = NATIVE_LISTENER_LINE.matchEntire(line) ?: return
        val rawText = listener.groupValues[2]
        val raw = if (rawText.isEmpty()) null else (rawText.toLongOrNull() ?: return)
        if (raw != null && raw > MAX_RAW_STATE) return
        val errorText = listener.groupValues[3]
        val error = if (errorText.isEmpty()) null else (errorText.toIntOrNull() ?: return)
        if (error != null && error.toString() != errorText) return
        val state = when (listener.groupValues[1]) {
            "ready" -> State.READY
            "failed" -> State.FAILED
            "cancelled" -> State.CANCELLED
            else -> State.OTHER
        }
        observation.update {
            it.copy(native = it.native.copy(
                listenerState = state,
                listenerRawState = raw,
                listenerLastError = error ?: it.native.listenerLastError
            ))
        }
    }

    /** Existing fixed messages only: no ACCEPTED line, TXT map, peer name, address or arbitrary suffix. */
    private fun recordStage(line: String) {
        val fixed = FIXED_STAGE_LINE.matchEntire(line)
        if (fixed != null) {
            val event = FIXED_STAGE_EVENTS[fixed.groupValues[1]] ?: return
            observation.update {
                val stages = it.stages
                it.copy(stages = when (event) {
                    StageEvent.ADVERTISE_STARTED -> stages.copy(advStarted = increment(stages.advStarted))
                    StageEvent.ADVERTISE_DEFERRED -> stages.copy(advDeferred = increment(stages.advDeferred))
                    StageEvent.ENDPOINT_NULL -> stages.copy(endpointNull = increment(stages.endpointNull))
                    StageEvent.MALFORMED_TXT -> stages.copy(malformedTxt = increment(stages.malformedTxt))
                    StageEvent.RECORD_REJECTED -> stages.copy(recordRejected = increment(stages.recordRejected))
                    StageEvent.IDENTITY_MISMATCH -> stages.copy(identityMismatch = increment(stages.identityMismatch))
                })
            }
            return
        }
        val listener = LISTENER_STAGE_LINE.matchEntire(line)
        if (listener != null) {
            val errorText = listener.groupValues[2]
            if (errorText.isNotEmpty()) {
                val error = errorText.toIntOrNull() ?: return
                if (error.toString() != errorText) return
            }
            observation.update {
                val stages = it.stages
                it.copy(stages = if (listener.groupValues[1] == "ready") {
                    stages.copy(listenerReady = increment(stages.listenerReady))
                } else {
                    stages.copy(listenerFailed = increment(stages.listenerFailed))
                })
            }
            return
        }
        val result = RESULT_STAGE_LINE.matchEntire(line) ?: return
        observation.update {
            val stages = it.stages
            it.copy(stages = stages.copy(
                results = increment(stages.results),
                added = if (result.groupValues[1] == "true") increment(stages.added) else stages.added,
                removed = if (result.groupValues[2] == "true") increment(stages.removed) else stages.removed,
                txtChanged = if (result.groupValues[3] == "true") increment(stages.txtChanged) else stages.txtChanged
            ))
        }
    }

    fun snapshot(phase: Phase): String {
        val seen = observation.value
        return "P2PKIT_IOS_LAN_TIMEOUT_V1 phase=${phase.name} scope=PROCESS_WIDE_BEST_EFFORT" +
            " starts=${seen.starts} ready=${seen.ready} waiting=${seen.waiting}" +
            " failed=${seen.failed} cancelled=${seen.cancelled} other=${seen.other}" +
            " lastState=${seen.lastState.name} lastRawState=${seen.lastRawState ?: "NONE"}" +
            " lastError=${seen.lastError ?: "NONE"} observationsAvailable=${seen.observationsAvailable}" +
            " packagingReadOk=${seen.packaging.readOk}" +
            " usageDescriptionPresent=${seen.packaging.usageDescriptionPresent}" +
            " requiredBonjourPresent=${seen.packaging.requiredBonjourPresent}"
    }

    fun stageSnapshot(phase: Phase): String {
        val seen = observation.value.stages
        return "P2PKIT_IOS_LAN_STAGE_V1 phase=${phase.name} scope=PROCESS_WIDE_BEST_EFFORT" +
            " advStarted=${seen.advStarted} advDeferred=${seen.advDeferred}" +
            " listenerReady=${seen.listenerReady} listenerFailed=${seen.listenerFailed}" +
            " results=${seen.results} added=${seen.added} removed=${seen.removed} txtChanged=${seen.txtChanged}" +
            " endpointNull=${seen.endpointNull} malformedTxt=${seen.malformedTxt}" +
            " recordRejected=${seen.recordRejected} identityMismatch=${seen.identityMismatch}"
    }

    fun nativeSnapshot(phase: Phase): String {
        val seen = observation.value.native
        return "P2PKIT_IOS_LAN_NATIVE_V1 phase=${phase.name} scope=PROCESS_WIDE_BEST_EFFORT" +
            " regAdded=${seen.regAdded} regRemoved=${seen.regRemoved}" +
            " regOwn=${seen.regOwn} regOther=${seen.regOther} regStale=${seen.regStale}" +
            " rawResults=${seen.rawResults} rawCurrent=${seen.rawCurrent} rawStale=${seen.rawStale}" +
            " listenerState=${seen.listenerState.name} listenerRawState=${seen.listenerRawState ?: "NONE"}" +
            " listenerLastError=${seen.listenerLastError ?: "NONE"}" +
            " listenerP2P=${seen.listenerP2P.name} listenerCellBan=${seen.listenerCellBan.name}" +
            " browserP2P=${seen.browserP2P.name} browserCellBan=${seen.browserCellBan.name}"
    }

    /** Direct snapshot, not parsed logs. Availability/witnesses do not qualify the native test. */
    fun callbackSnapshot(phase: Phase): String {
        val seen = nativeEpoch.value?.snapshot() ?: IosLanNativeCallbackDiagnostics.Snapshot(
            availability = if (nativeObserverFailed.value) {
                IosLanNativeCallbackDiagnostics.Availability.OBSERVER_FAILURE
            } else {
                IosLanNativeCallbackDiagnostics.Availability.NOT_INSTALLED
            }
        )
        return "P2PKIT_IOS_LAN_CALLBACK_V1 phase=${phase.name}" +
            " caseId=${currentCaseId.value.name} scope=TEST_EPOCH_BROWSER_LEASES" +
            " availability=${seen.availability.name} overflow=${seen.overflow}" +
            " witnessesComplete=${seen.witnessesComplete}" +
            " created=${seen.created} started=${seen.started} ready=${seen.ready} terminal=${seen.terminal}" +
            " raw=${seen.raw} current=${seen.current} stale=${seen.stale}" +
            " oldNonNull=${seen.oldNonNull} newNonNull=${seen.newNonNull}" +
            " batchComplete=${seen.batchComplete} batchIncomplete=${seen.batchIncomplete}"
    }

    private fun report(phase: Phase, failure: TimeoutCancellationException) {
        if (!reported.compareAndSet(expect = false, update = true)) return
        val marker = try {
            snapshot(phase).takeIf { it.length <= MAX_MARKER_BYTES && it.all { char -> char.code in 32..126 } }
        } catch (_: Throwable) {
            null
        }
        val stageMarker = try {
            stageSnapshot(phase).takeIf {
                it.length <= MAX_STAGE_MARKER_BYTES && it.all { char -> char.code in 32..126 }
            }
        } catch (_: Throwable) {
            null
        }
        val nativeMarker = try {
            nativeSnapshot(phase).takeIf {
                it.length <= MAX_NATIVE_MARKER_BYTES && it.all { char -> char.code in 32..126 }
            }
        } catch (_: Throwable) {
            null
        }
        val callbackMarker = try {
            callbackSnapshot(phase).takeIf {
                it.length <= MAX_CALLBACK_MARKER_BYTES && it.all { char -> char.code in 32..126 }
            }
        } catch (_: Throwable) {
            null
        }
        if (marker != null) {
            try {
                failure.addSuppressed(IllegalStateException(marker))
            } catch (_: Throwable) {
                // Reporting is best-effort and must never replace the original timeout.
            }
            try {
                output(marker)
            } catch (_: Throwable) {
                // This is one safe test marker, not the global debug-console mirror.
            }
        }
        if (nativeMarker != null) {
            try {
                output(nativeMarker)
            } catch (_: Throwable) {
                // Preserve independent primary/stage output and the one original suppressed note.
            }
        }
        if (callbackMarker != null) {
            try {
                output(callbackMarker)
            } catch (_: Throwable) {
                // A direct observer has independent output and never adds a suppressed note.
            }
        }
        if (stageMarker != null) {
            try {
                output(stageMarker)
            } catch (_: Throwable) {
                // The companion never adds another suppressed exception or replaces the primary marker.
            }
        }
    }

    private companion object {
        const val MAX_INPUT_CHARS = 96
        const val MAX_STAGE_INPUT_CHARS = 128
        const val MAX_MARKER_BYTES = 512
        const val MAX_STAGE_MARKER_BYTES = 300
        const val MAX_NATIVE_MARKER_BYTES = 512
        const val MAX_CALLBACK_MARKER_BYTES = 512
        const val MAX_RAW_STATE = 4_294_967_295L
        const val TIMESTAMP = "\\[(?:0|[1-9][0-9]{0,5})]"
        val FIXED_STAGE_EVENTS = mapOf(
            "[advertise] started" to StageEvent.ADVERTISE_STARTED,
            "[advertise] listener null (rebind window?) — descriptor deferred to rebind hook" to
                StageEvent.ADVERTISE_DEFERRED,
            "[browse] emitPeer: copy_endpoint returned null — skip" to StageEvent.ENDPOINT_NULL,
            "[browse] emitPeer: malformed TXT record — reject" to StageEvent.MALFORMED_TXT,
            "[browse] emitPeer: filter — invalid/bounded TXT schema" to StageEvent.RECORD_REJECTED,
            "[browse] emitPeer: filter — Bonjour service identity does not match TXT peer id" to
                StageEvent.IDENTITY_MISMATCH
        )
        val FIXED_STAGE_LINE = Regex(
            TIMESTAMP + "(" + FIXED_STAGE_EVENTS.keys.joinToString("|") { Regex.escape(it) } + ")"
        )
        val LISTENER_STAGE_LINE = Regex(
            TIMESTAMP + "\\[data] listener state -> (ready|failed)(?: errCode=(-?(?:0|[1-9][0-9]{0,9})))?"
        )
        val RESULT_STAGE_LINE = Regex(
            TIMESTAMP + "\\[browse] result change: added=(true|false) removed=(true|false)" +
                " txtChanged=(true|false) batchComplete=(true|false) oldNull=(true|false) newNull=(true|false)"
        )
        val NATIVE_REGISTRATION_LINE = Regex(
            TIMESTAMP + "\\[advertise] native registration: added=(true|false)" +
                " localMatch=(true|false) current=(true|false)"
        )
        val NATIVE_RESULT_LINE = Regex(
            TIMESTAMP + "\\[browse] native result: currentAtEntry=(true|false)"
        )
        val NATIVE_PARAMETERS_LINE = Regex(
            TIMESTAMP + "\\[(data|browse)] native params: kind=(TCP|BARE)" +
                " peerToPeer=(true|false) cellularProhibited=(true|false)"
        )
        val NATIVE_LISTENER_LINE = Regex(
            TIMESTAMP + "\\[data] listener state -> (ready|failed|cancelled|raw=(0|[1-9][0-9]{0,9}))" +
                "(?: errCode=(-?(?:0|[1-9][0-9]{0,9})))?"
        )
        val BROWSE_LINE = Regex(
            "\\[(?:0|[1-9][0-9]{0,5})]\\[browse] " +
                "(?:nw_browser_start invoked|state -> (ready|waiting|failed|cancelled|raw=(0|[1-9][0-9]{0,9}))" +
                "(?: errCode=(-?(?:0|[1-9][0-9]{0,9})))?)"
        )

        fun increment(value: Int): Int = (value + 1).coerceAtMost(255)

        fun currentPackaging(): Packaging {
            val bundle = NSBundle.mainBundle
            return Packaging.from(
                bundle.objectForInfoDictionaryKey("NSLocalNetworkUsageDescription"),
                bundle.objectForInfoDictionaryKey("NSBonjourServices")
            )
        }
    }
}
