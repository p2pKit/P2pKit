package dev.p2pkit.transport.lan

import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.CoroutineStart
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.TimeoutCancellationException
import kotlinx.coroutines.cancelAndJoin
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.collect
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

/** Closed failure context only; never changes an existing wait, exception or cleanup obligation. */
internal enum class AppleLanDiscoveryStage {
    INITIAL_PEER,
    INITIAL_PEER_SET,
    REDISCOVERY
}

/** Observations only: these do not admit a peer or prove delivery of every debug event. */
internal enum class AppleLanDiscoveryMarker {
    BROWSER_READY,
    BROWSER_WAITING,
    BROWSER_FAILED,
    BROWSER_ERROR_PRESENT,
    BROWSER_CODE_MINUS_65570,
    BROWSER_CODE_MINUS_65563,
    LISTENER_READY,
    LISTENER_FAILED,
    MISSING_LOCAL_NETWORK_USAGE,
    MISSING_BONJOUR_SERVICE
}

private val browserState = Regex(
    """\[[0-9]{1,6}\]\[browse\] state -> (ready|waiting|failed|cancelled)(?: errCode=(-?[0-9]{1,10}))?"""
)
private val listenerState = Regex(
    """\[[0-9]{1,6}\]\[data\] listener state -> (ready|failed|cancelled)(?: errCode=(-?[0-9]{1,10}))?"""
)
private val packagingPrefix = Regex("""\[[0-9]{1,6}\]\[packaging\] .*""")

internal fun appleLanDiscoveryMarkers(line: String): Set<AppleLanDiscoveryMarker> = buildSet {
    if (line.length > 4096) return@buildSet
    browserState.matchEntire(line)?.let { match ->
        when (match.groupValues[1]) {
            "ready" -> add(AppleLanDiscoveryMarker.BROWSER_READY)
            "waiting" -> add(AppleLanDiscoveryMarker.BROWSER_WAITING)
            "failed" -> add(AppleLanDiscoveryMarker.BROWSER_FAILED)
        }
        val code = match.groupValues[2].toIntOrNull()
        if (code != null && code != 0) add(AppleLanDiscoveryMarker.BROWSER_ERROR_PRESENT)
        when (code) {
            -65570 -> add(AppleLanDiscoveryMarker.BROWSER_CODE_MINUS_65570)
            -65563 -> add(AppleLanDiscoveryMarker.BROWSER_CODE_MINUS_65563)
        }
    }
    listenerState.matchEntire(line)?.let { match ->
        when (match.groupValues[1]) {
            "ready" -> add(AppleLanDiscoveryMarker.LISTENER_READY)
            "failed" -> add(AppleLanDiscoveryMarker.LISTENER_FAILED)
        }
    }
    if (packagingPrefix.matches(line)) {
        if ("Host Info.plist is missing a nonblank NSLocalNetworkUsageDescription;" in line) {
            add(AppleLanDiscoveryMarker.MISSING_LOCAL_NETWORK_USAGE)
        }
        if ("Host Info.plist NSBonjourServices is missing '" in line) {
            add(AppleLanDiscoveryMarker.MISSING_BONJOUR_SERVICE)
        }
    }
}

/** Per-fixture bounded enum set; subscribe BEFORE kits start, without changing global logging or transport. */
internal class AppleLanDiscoveryTrace(events: Flow<String> = IosLanDebug.events) {
    private val owner = SupervisorJob()
    private val markers = MutableStateFlow(emptySet<AppleLanDiscoveryMarker>())

    init {
        CoroutineScope(owner + Dispatchers.Default).launch(start = CoroutineStart.UNDISPATCHED) {
            events.collect { line ->
                val observed = appleLanDiscoveryMarkers(line)
                if (observed.isNotEmpty()) markers.update { it + observed }
            }
        }
    }

    fun snapshot(): Set<AppleLanDiscoveryMarker> = markers.value

    suspend fun close() {
        owner.cancelAndJoin()
    }
}

internal suspend fun <T> traceAppleLanDiscovery(
    stage: AppleLanDiscoveryStage,
    observations: () -> Set<AppleLanDiscoveryMarker> = { emptySet() },
    action: suspend () -> T
): T = try {
    action()
} catch (failure: TimeoutCancellationException) {
    // Native stack traces do not always retain source lines. Preserve the exact
    // cancellation instance and original timeout; attach no identity or payload.
    failure.addSuppressed(AssertionError("APPLE_LAN_DISCOVERY_WAIT_TIMEOUT stage=${stage.name}"))
    observations().sortedBy { it.name }.forEach { marker ->
        failure.addSuppressed(AssertionError("APPLE_LAN_DISCOVERY_OBSERVED marker=${marker.name}"))
    }
    throw failure
}
