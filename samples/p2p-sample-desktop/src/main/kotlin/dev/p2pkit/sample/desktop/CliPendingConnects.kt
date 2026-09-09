package dev.p2pkit.sample.desktop

import dev.p2pkit.core.P2pSession
import java.util.concurrent.ConcurrentHashMap
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.update

/** Shared command/mesh ownership plus a coalesced, once-consumed record of real SDK admissions. */
internal class CliPendingConnects private constructor(
    private val entries: MutableSet<String>
) : Set<String> by entries {
    constructor() : this(ConcurrentHashMap.newKeySet())

    private val admissionLock = Any()
    private val completedAdmissions = mutableSetOf<String>()
    private val mutableCompletions = MutableStateFlow(0L)
    val completions: StateFlow<Long> = mutableCompletions

    fun add(peerId: String): Boolean = entries.add(peerId)

    fun remove(peerId: String): Boolean = entries.remove(peerId).also { removed ->
        if (removed) mutableCompletions.update { it + 1L }
    }

    fun complete(peerId: String, ownsMarker: Boolean, admittedSession: P2pSession?) {
        // Record before releasing/waking: even an admission/removal conflated by
        // StateFlow is a real lost session, not permission to retry a bare failure.
        if (admittedSession != null) synchronized(admissionLock) {
            completedAdmissions += admittedSession.peer.id.value
        }
        val removed = ownsMarker && entries.remove(peerId)
        if (removed || admittedSession != null) mutableCompletions.update { it + 1L }
    }

    fun takeCompletedAdmissions(): Set<String> = synchronized(admissionLock) {
        completedAdmissions.toSet().also { completedAdmissions.clear() }
    }
}
