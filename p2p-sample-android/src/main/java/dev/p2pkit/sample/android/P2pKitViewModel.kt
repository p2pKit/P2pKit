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
import dev.p2pkit.core.P2pState
import dev.p2pkit.core.Peer
import dev.p2pkit.core.ReconnectPolicy
import dev.p2pkit.transport.lan.lan
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.launch

/**
 * Owns the [P2pKit] instance and the **room** state of the sample, which
 * doubles as P2pKit's primary visual test harness on Android.
 *
 * Exposed surface (consumed by [MainActivity]):
 *  - identity / config: [appId], [localDeviceName], [localPeerId]
 *  - lifecycle: [isRunning], [kitState], [advertising], [discovering]
 *  - configuration: [reconnectChoice]
 *  - discovery: [peers]
 *  - sessions / messaging: [connectedSessions], [roomMessages], [targetedPeerIds]
 *  - diagnostics: [logTail]
 *
 * No fixed cap on connected peers: broadcast sends to every entry in the
 * live [connectedSessions] snapshot; targeted sends use any subset of
 * peer ids in [targetedPeerIds]. Practical limits are network-dependent.
 *
 * Lifecycle survives Activity recreation (rotation, dark-mode, locale, …).
 * Process death is out of scope.
 */
class P2pKitViewModel(application: Application) : AndroidViewModel(application) {

    // --- identity ----------------------------------------------------------

    val appId: String = APP_ID
    var deviceName: String by mutableStateOf("Android-${(0..9999).random()}")
        private set

    private val _localPeerId = MutableStateFlow<String?>(null)
    val localPeerId: StateFlow<String?> = _localPeerId.asStateFlow()

    // --- lifecycle ---------------------------------------------------------

    private val _isRunning = MutableStateFlow(false)
    val isRunning: StateFlow<Boolean> = _isRunning.asStateFlow()

    private val _kitState = MutableStateFlow<P2pState>(P2pState.Idle)
    val kitState: StateFlow<P2pState> = _kitState.asStateFlow()

    private val _advertising = MutableStateFlow(false)
    val advertising: StateFlow<Boolean> = _advertising.asStateFlow()

    private val _discovering = MutableStateFlow(false)
    val discovering: StateFlow<Boolean> = _discovering.asStateFlow()

    /**
     * Auto-mesh: when ON, the sample auto-connects to every newly discovered
     * peer in the room. To avoid both sides racing each other into duplicate
     * sessions (the current SDK doesn't arbitrate simultaneous-open), the
     * caller only initiates when their own `localPeerId` is lexicographically
     * less than the discovered peer's id. Exactly one side per pair initiates;
     * the other accepts the incoming session.
     *
     * Default ON — this is the behavior that makes a 3-device room work
     * out-of-the-box. Toggle OFF to test selective connect.
     */
    private val _autoMesh = MutableStateFlow(true)
    val autoMesh: StateFlow<Boolean> = _autoMesh.asStateFlow()

    // --- configuration ----------------------------------------------------

    var reconnectChoice: ReconnectChoice by mutableStateOf(ReconnectChoice.Disabled)
        private set

    // --- discovery + sessions ---------------------------------------------

    private val _peers = MutableStateFlow<List<Peer>>(emptyList())
    val peers: StateFlow<List<Peer>> = _peers.asStateFlow()

    val connectedSessions: SnapshotStateList<P2pSession> = mutableStateListOf()
    val roomMessages: SnapshotStateList<RoomMessage> = mutableStateListOf()
    val targetedPeerIds: SnapshotStateList<String> = mutableStateListOf()

    // --- diagnostics ------------------------------------------------------

    /** Last N lines from the logger; surfaced under the room timeline. */
    val logTail: SnapshotStateList<String> = mutableStateListOf()

    // --- internals --------------------------------------------------------

    private var kit: P2pKit? = null
    private var runScope: CoroutineScope? = null
    private val cleanupScope = CoroutineScope(Dispatchers.Default + SupervisorJob())
    private val sessionJobs: MutableMap<String, Job> = mutableMapOf()
    private var nextMessageId: Long = 1L

    // --- intents from the UI ----------------------------------------------

    fun updateDeviceName(name: String) {
        deviceName = name
    }

    fun updateReconnectChoice(choice: ReconnectChoice) {
        if (_isRunning.value) return  // locked at kit construction
        reconnectChoice = choice
    }

    fun togglePeerTarget(peerId: String) {
        if (targetedPeerIds.contains(peerId)) targetedPeerIds.remove(peerId)
        else targetedPeerIds.add(peerId)
    }

    fun clearPeerTargets() {
        targetedPeerIds.clear()
    }

    fun toggleAutoMesh() {
        _autoMesh.value = !_autoMesh.value
        Log.i(LOG_TAG, "auto-mesh = ${_autoMesh.value}")
    }

    fun start() {
        if (_isRunning.value) return  // idempotent
        val choice = reconnectChoice
        val newKit = P2pKit.create {
            appId = AppId(APP_ID)
            this.deviceName = this@P2pKitViewModel.deviceName
            transports { lan(getApplication<Application>().applicationContext) }
            lifecycle {
                reconnectPolicy = when (choice) {
                    ReconnectChoice.Disabled -> ReconnectPolicy.Disabled
                    is ReconnectChoice.Enabled -> ReconnectPolicy.Enabled(
                        maxAttempts = choice.maxAttempts,
                        retryDelayMillis = choice.retryDelayMillis
                    )
                }
            }
            logger = TailLogger(this@P2pKitViewModel)
        }
        kit = newKit
        _localPeerId.value = newKit.localPeerId.value
        Log.i(
            LOG_TAG,
            "kit started: deviceName=${newKit.localDeviceName} appId=${newKit.appId.value} " +
                "peerId=${newKit.localPeerId.value} reconnect=$choice"
        )

        val supervisor = SupervisorJob(viewModelScope.coroutineContext[Job])
        val scope = CoroutineScope(viewModelScope.coroutineContext + supervisor)
        runScope = scope

        scope.launch {
            newKit.state.collect { _kitState.value = it }
        }
        scope.launch {
            newKit.peers.collect { _peers.value = it }
        }
        // Single source of truth for "which peers do we have a session with".
        scope.launch {
            newKit.sessions.collect { current ->
                reconcileSessions(current, scope)
            }
        }
        scope.launch {
            runCatching { newKit.startAdvertising() }
                .onSuccess { _advertising.value = true }
                .onFailure { Log.w(LOG_TAG, "startAdvertising failed", it) }
            runCatching { newKit.startDiscovery() }
                .onSuccess { _discovering.value = true }
                .onFailure { Log.w(LOG_TAG, "startDiscovery failed", it) }
        }

        // Auto-mesh: react to peer changes and connect to anyone we should
        // initiate (lexicographic tie-break by peer id). Combining with
        // [autoMesh] means toggling the flag back ON re-evaluates immediately.
        scope.launch {
            combine(_autoMesh, newKit.peers) { enabled, peers -> enabled to peers }
                .collect { (enabled, peers) ->
                    if (!enabled) return@collect
                    val myId = newKit.localPeerId.value
                    val connectedIds = connectedSessions.map { it.peer.id.value }.toSet()
                    for (peer in peers) {
                        if (peer.id.value in connectedIds) continue
                        if (myId < peer.id.value) {
                            Log.i(LOG_TAG, "auto-mesh: initiating connect to ${peer.name}")
                            runCatching { newKit.connect(peer) }.onFailure {
                                Log.w(LOG_TAG, "auto-mesh connect to ${peer.name} failed", it)
                            }
                        }
                    }
                }
        }

        _isRunning.value = true
    }

    fun connect(peer: Peer) {
        val currentKit = kit ?: return
        val scope = runScope ?: return
        scope.launch {
            runCatching { currentKit.connect(peer) }.onFailure {
                Log.w(LOG_TAG, "connect to ${peer.name} failed", it)
                appendSystemMessage("failed to connect to ${peer.name}: ${it.message ?: it::class.simpleName}")
            }
        }
    }

    fun closeSession(peerId: String) {
        val scope = runScope ?: return
        val target = connectedSessions.firstOrNull { it.peer.id.value == peerId } ?: return
        scope.launch {
            runCatching { target.close() }.onFailure {
                Log.w(LOG_TAG, "close session to ${target.peer.name} failed", it)
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

    fun toggleAdvertising() {
        val currentKit = kit ?: return
        val scope = runScope ?: return
        scope.launch {
            if (_advertising.value) {
                runCatching { currentKit.stopAdvertising() }
                    .onSuccess { _advertising.value = false }
                    .onFailure { Log.w(LOG_TAG, "stopAdvertising failed", it) }
            } else {
                runCatching { currentKit.startAdvertising() }
                    .onSuccess { _advertising.value = true }
                    .onFailure { Log.w(LOG_TAG, "startAdvertising failed", it) }
            }
        }
    }

    fun toggleDiscovery() {
        val currentKit = kit ?: return
        val scope = runScope ?: return
        scope.launch {
            if (_discovering.value) {
                runCatching { currentKit.stopDiscovery() }
                    .onSuccess { _discovering.value = false }
                    .onFailure { Log.w(LOG_TAG, "stopDiscovery failed", it) }
            } else {
                runCatching { currentKit.startDiscovery() }
                    .onSuccess { _discovering.value = true }
                    .onFailure { Log.w(LOG_TAG, "startDiscovery failed", it) }
            }
        }
    }

    fun stop() {
        val toStop = kit ?: return
        kit = null
        _isRunning.value = false
        _advertising.value = false
        _discovering.value = false
        _kitState.value = P2pState.Stopped
        runScope?.cancel()
        runScope = null
        sessionJobs.clear()
        _peers.value = emptyList()
        connectedSessions.clear()
        targetedPeerIds.clear()
        roomMessages.clear()
        _localPeerId.value = null
        viewModelScope.launch { runCatching { toStop.stop() } }
    }

    override fun onCleared() {
        super.onCleared()
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

    // --- helpers ----------------------------------------------------------

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
            // Log session state transitions (Connected / Reconnecting / Failed / Closed).
            scope.launch {
                session.state.collect { st ->
                    Log.i(LOG_TAG, "session ${session.peer.name} → $st")
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

    internal fun recordLog(level: String, message: String) {
        // Trim to keep the strip bounded.
        if (logTail.size >= LOG_TAIL_CAPACITY) {
            logTail.removeAt(0)
        }
        logTail.add("$level  $message")
    }

    private companion object {
        const val APP_ID = "p2pkit-desktop-sample"
        const val LOG_TAG = "p2pkit"
        const val LOG_TAIL_CAPACITY = 30
    }
}

/** Sample-level message envelope rendered in the room timeline. */
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

/** User-facing reconnect policy choice on the Setup screen. */
sealed class ReconnectChoice {
    data object Disabled : ReconnectChoice()
    data class Enabled(val maxAttempts: Int, val retryDelayMillis: Long) : ReconnectChoice()
}

/**
 * Logger that mirrors output to logcat AND to the ViewModel's [P2pKitViewModel.logTail]
 * for in-app diagnostics.
 */
private class TailLogger(private val vm: P2pKitViewModel) : P2pLogger {
    private val tag = "p2pkit"
    override fun debug(message: String) {
        Log.d(tag, message)
        vm.recordLog("D", message)
    }
    override fun info(message: String) {
        Log.i(tag, message)
        vm.recordLog("I", message)
    }
    override fun warn(message: String, throwable: Throwable?) {
        if (throwable != null) Log.w(tag, message, throwable) else Log.w(tag, message)
        vm.recordLog("W", if (throwable != null) "$message — ${throwable.message ?: throwable::class.simpleName}" else message)
    }
    override fun error(message: String, throwable: Throwable?) {
        if (throwable != null) Log.e(tag, message, throwable) else Log.e(tag, message)
        vm.recordLog("E", if (throwable != null) "$message — ${throwable.message ?: throwable::class.simpleName}" else message)
    }
}
