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
        val packaging: Packaging = Packaging(false, false, false)
    )

    private val observation = MutableStateFlow(Observation())
    private val reported = MutableStateFlow(false)

    /** One runBlocking, with the original body and its async children owned by that same scope. */
    fun <T> run(block: suspend CoroutineScope.() -> T): T {
        val flags = try {
            packaging()
        } catch (_: Throwable) {
            Packaging(false, false, false)
        }
        observation.value = Observation(packaging = flags)
        reported.value = false
        try {
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
            observation.value = Observation()
            reported.value = false
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

    /** Only this closed native browse grammar is admitted; the original string is never retained. */
    fun record(line: String) {
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

    private fun report(phase: Phase, failure: TimeoutCancellationException) {
        if (!reported.compareAndSet(expect = false, update = true)) return
        val marker = try {
            snapshot(phase).takeIf { it.length <= MAX_MARKER_BYTES && it.all { char -> char.code in 32..126 } }
        } catch (_: Throwable) {
            null
        } ?: return
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

    private companion object {
        const val MAX_INPUT_CHARS = 96
        const val MAX_MARKER_BYTES = 512
        const val MAX_RAW_STATE = 4_294_967_295L
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
