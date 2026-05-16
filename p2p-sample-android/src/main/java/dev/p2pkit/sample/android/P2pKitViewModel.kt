package dev.p2pkit.sample.android

import android.app.Application
import android.util.Log
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.compose.runtime.snapshots.SnapshotStateList
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import dev.p2pkit.core.AppId
import dev.p2pkit.core.P2pKit
import dev.p2pkit.core.P2pLogger
import dev.p2pkit.core.P2pMessage
import dev.p2pkit.core.P2pSession
import dev.p2pkit.core.Peer
import dev.p2pkit.transport.lan.lan
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

/**
 * Owns the [P2pKit] instance and the **room** state of the sample.
 *
 * Architecture rule: the SDK exposes one [P2pSession] per peer. There is no
 * "room" type in :p2p-core. This ViewModel implements the room/broadcast UX
 * purely on the sample side by iterating [P2pKit.sessions] and fanning out
 * sends. Incoming messages from every active session are merged into a
 * single [roomMessages] timeline so messages from non-targeted peers are
 * never dropped.
 *
 * No fixed cap on connected peers: broadcast sends to every entry in the
 * live [connectedSessions] snapshot, and targeted sends use any subset of
 * peer ids stored in [targetedPeerIds]. Practical limits are
 * network-dependent (router multicast, mDNS cache pressure).
 *
 * Lifecycle survives Activity recreation (rotation, dark-mode, locale, …).
 * Process death is out of scope (would require `SavedStateHandle`).
 */
class P2pKitViewModel(application: Application) : AndroidViewModel(application) {

    // --- public state for the UI -------------------------------------------

    private val _isRunning = MutableStateFlow(false)
    val isRunning: StateFlow<Boolean> = _isRunning.asStateFlow()

    var deviceName: String by mutableStateOf("Android-${(0..9999).random()}")
        private set

    private val _peers = MutableStateFlow<List<Peer>>(emptyList())
    val peers: StateFlow<List<Peer>> = _peers.asStateFlow()

    /**
     * Every currently-connected peer's session, observed from
     * [P2pKit.sessions]. Used by the UI to render the connected-peers row.
     */
    val connectedSessions: SnapshotStateList<P2pSession> = mutableStateListOf()

    /**
     * One merged room timeline. Includes incoming messages from every active
     * session, outgoing messages the local user sent, and system events
     * (peer connected / disconnected).
     */
    val roomMessages: SnapshotStateList<RoomMessage> = mutableStateListOf()

    /**
     * Peer ids the user has explicitly targeted. Empty = broadcast to every
     * connected peer.
     */
    val targetedPeerIds: SnapshotStateList<String> = mutableStateListOf()

    // --- internals ---------------------------------------------------------

    private var kit: P2pKit? = null
    private var runScope: CoroutineScope? = null
    private val cleanupScope = CoroutineScope(Dispatchers.Default + SupervisorJob())

    /** One incoming-collector job per session id, so we can cancel on session removal. */
    private val sessionJobs: MutableMap<String, Job> = mutableMapOf()
    private var nextMessageId: Long = 1L

    // --- intents from the UI -----------------------------------------------

    fun updateDeviceName(name: String) {
        deviceName = name
    }

    fun togglePeerTarget(peerId: String) {
        if (targetedPeerIds.contains(peerId)) targetedPeerIds.remove(peerId)
        else targetedPeerIds.add(peerId)
    }

    fun clearPeerTargets() {
        targetedPeerIds.clear()
    }

    fun start() {
        if (_isRunning.value) return  // idempotent
        val newKit = P2pKit.create {
            appId = AppId(APP_ID)
            this.deviceName = this@P2pKitViewModel.deviceName
            transports { lan(getApplication<Application>().applicationContext) }
            logger = LogcatLogger
        }
        kit = newKit
        Log.i(LOG_TAG, "kit started: deviceName=$deviceName appId=$APP_ID")

        val supervisor = SupervisorJob(viewModelScope.coroutineContext[Job])
        val scope = CoroutineScope(viewModelScope.coroutineContext + supervisor)
        runScope = scope

        scope.launch {
            newKit.peers.collect { _peers.value = it }
        }

        // Single source of truth for "which peers do we have a session with":
        // P2pKit.sessions. This handles incoming AND outgoing uniformly and
        // also fires when a session terminates so we can clean up.
        scope.launch {
            newKit.sessions.collect { current ->
                reconcileSessions(current, scope)
            }
        }

        scope.launch {
            runCatching { newKit.startAdvertising() }
            runCatching { newKit.startDiscovery() }
        }

        _isRunning.value = true
    }

    fun connect(peer: Peer) {
        val currentKit = kit ?: return
        val scope = runScope ?: return
        scope.launch {
            // The session itself is registered into newKit.sessions inside
            // SessionManager — the reconcile collector above will pick it up
            // and wire incoming. We only handle the connect-attempt failure.
            runCatching { currentKit.connect(peer) }.onFailure {
                Log.w(LOG_TAG, "connect to ${peer.name} failed", it)
                appendSystemMessage("failed to connect to ${peer.name}: ${it.message ?: it::class.simpleName}")
            }
        }
    }

    fun sendRoomMessage(text: String) {
        val trimmed = text.trim()
        if (trimmed.isEmpty()) return
        val scope = runScope ?: return

        val sessionsSnapshot = connectedSessions.toList()
        val targetedSet = targetedPeerIds.toSet()
        val target: SendTarget = if (targetedSet.isEmpty()) SendTarget.All
        else SendTarget.Specific(targetedSet)

        val recipients = when (target) {
            SendTarget.All -> sessionsSnapshot
            is SendTarget.Specific -> sessionsSnapshot.filter { it.peer.id.value in target.peerIds }
        }
        if (recipients.isEmpty()) {
            Log.i(LOG_TAG, "room: send skipped (no recipients)")
            appendSystemMessage("nothing sent — no targeted peers are connected")
            return
        }

        val body = P2pMessage.Text(trimmed)
        val message = RoomMessage(
            id = nextMessageId++,
            senderPeerId = null,
            senderName = "(me)",
            body = body,
            timestamp = System.currentTimeMillis(),
            direction = RoomMessage.Direction.Outgoing,
            target = target
        )
        roomMessages.add(message)
        Log.i(
            LOG_TAG,
            "room: ${if (target is SendTarget.All) "broadcast" else "targeted"} " +
                "→ ${recipients.size} peer(s): ${trimmed.take(60)}"
        )

        for (session in recipients) {
            scope.launch {
                runCatching { session.send(body) }.onFailure {
                    Log.w(LOG_TAG, "room: send to ${session.peer.name} failed", it)
                    appendSystemMessage("send to ${session.peer.name} failed: ${it.message ?: it::class.simpleName}")
                }
            }
        }
    }

    fun stop() {
        val toStop = kit ?: return
        kit = null
        _isRunning.value = false
        runScope?.cancel()
        runScope = null
        sessionJobs.clear()  // jobs are cancelled by runScope.cancel()
        _peers.value = emptyList()
        connectedSessions.clear()
        targetedPeerIds.clear()
        roomMessages.clear()
        // viewModelScope still alive here — let kit.stop() complete cleanly.
        viewModelScope.launch { runCatching { toStop.stop() } }
    }

    override fun onCleared() {
        super.onCleared()
        // viewModelScope is already cancelled at this point. Finish kit
        // cleanup on a scope that survives the ViewModel.
        val toStop = kit
        kit = null
        if (toStop != null) {
            cleanupScope.launch {
                runCatching { toStop.stop() }
                cleanupScope.cancel()
            }
        } else {
            cleanupScope.cancel()
        }
    }

    // --- helpers -----------------------------------------------------------

    private fun reconcileSessions(current: List<P2pSession>, scope: CoroutineScope) {
        val currentIds = current.map { it.id }.toSet()

        // Drop sessions that left the kit.
        val droppedIds = sessionJobs.keys.toList().filter { it !in currentIds }
        for (id in droppedIds) {
            sessionJobs.remove(id)?.cancel()
            val removed = connectedSessions.firstOrNull { it.id == id }
            if (removed != null) {
                connectedSessions.remove(removed)
                targetedPeerIds.remove(removed.peer.id.value)
                appendSystemMessage("disconnected from ${removed.peer.name}")
                Log.i(LOG_TAG, "room: session removed ${removed.peer.name}")
            }
        }

        // Add sessions that are new in the kit.
        for (session in current) {
            if (sessionJobs.containsKey(session.id)) continue
            connectedSessions.add(session)
            appendSystemMessage("connected to ${session.peer.name}")
            Log.i(LOG_TAG, "room: session added ${session.peer.name}")
            sessionJobs[session.id] = scope.launch {
                session.incoming.collect { msg ->
                    Log.i(LOG_TAG, "room: incoming from ${session.peer.name}")
                    roomMessages.add(
                        RoomMessage(
                            id = nextMessageId++,
                            senderPeerId = session.peer.id.value,
                            senderName = session.peer.name,
                            body = msg,
                            timestamp = System.currentTimeMillis(),
                            direction = RoomMessage.Direction.Incoming
                        )
                    )
                }
            }
        }
    }

    private fun appendSystemMessage(text: String) {
        roomMessages.add(
            RoomMessage(
                id = nextMessageId++,
                senderPeerId = null,
                senderName = "(system)",
                body = P2pMessage.Text(text),
                timestamp = System.currentTimeMillis(),
                direction = RoomMessage.Direction.System
            )
        )
    }

    private companion object {
        const val APP_ID = "p2pkit-desktop-sample"
        const val LOG_TAG = "p2pkit"
    }
}

/**
 * Sample-level message envelope rendered in the room timeline. Carries
 * direction (incoming/outgoing/system), sender info, and the targeting
 * choice the user made for outgoing sends.
 */
data class RoomMessage(
    val id: Long,
    val senderPeerId: String?,
    val senderName: String,
    val body: P2pMessage,
    val timestamp: Long,
    val direction: Direction,
    val target: SendTarget = SendTarget.All
) {
    enum class Direction { Incoming, Outgoing, System }

    val displayBody: String
        get() = when (body) {
            is P2pMessage.Text -> body.value
            is P2pMessage.Binary -> "<binary ${body.bytes.size}B>"
        }
}

/** Targeting choice for an outgoing room send. */
sealed class SendTarget {
    data object All : SendTarget()
    data class Specific(val peerIds: Set<String>) : SendTarget()
}

private object LogcatLogger : P2pLogger {
    private const val TAG = "p2pkit"
    override fun debug(message: String) {
        Log.d(TAG, message)
    }
    override fun info(message: String) {
        Log.i(TAG, message)
    }
    override fun warn(message: String, throwable: Throwable?) {
        if (throwable != null) Log.w(TAG, message, throwable) else Log.w(TAG, message)
    }
    override fun error(message: String, throwable: Throwable?) {
        if (throwable != null) Log.e(TAG, message, throwable) else Log.e(TAG, message)
    }
}
