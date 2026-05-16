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
 * Owns the [P2pKit] instance and all session/peer/chat state for the sample
 * app, surviving configuration changes (rotation, dark mode, locale, etc.).
 *
 * Lifecycle:
 * - Created on first `viewModel()` call; reused across [MainActivity] recreations.
 * - `onCleared()` runs when the ViewModelStore is permanently destroyed —
 *   i.e., the user really leaves the app, not on a rotation. At that point
 *   `viewModelScope` has already been cancelled, so a dedicated cleanup scope
 *   is used to let `kit.stop()` complete asynchronously.
 * - **Process death is not handled**: if Android kills the app process while
 *   it's in the background, the kit and its in-memory state are lost.
 *   `SavedStateHandle`-based recovery is intentionally out of scope; the next
 *   launch starts at the setup screen with a fresh kit. The persistent
 *   `PeerId` from v0.2 Task 1 still carries over so other peers recognise
 *   the device.
 */
class P2pKitViewModel(application: Application) : AndroidViewModel(application) {

    // --- public state for the UI -------------------------------------------

    private val _isRunning = MutableStateFlow(false)
    val isRunning: StateFlow<Boolean> = _isRunning.asStateFlow()

    var deviceName: String by mutableStateOf("Android-${(0..9999).random()}")
        private set

    private val _peers = MutableStateFlow<List<Peer>>(emptyList())
    val peers: StateFlow<List<Peer>> = _peers.asStateFlow()

    val sessions: SnapshotStateList<P2pSession> = mutableStateListOf()
    val messages: SnapshotStateList<ChatLine> = mutableStateListOf()

    var selectedSession: P2pSession? by mutableStateOf(null)
        private set

    // --- internals ---------------------------------------------------------

    private var kit: P2pKit? = null

    /**
     * Scope for all in-flight collectors and ad-hoc launches while the kit
     * is running. Cancelled on [stop] so a subsequent [start] doesn't have
     * stale work from the previous run.
     */
    private var runScope: CoroutineScope? = null

    /**
     * Outlives [viewModelScope] so [kit].stop() can finish after [onCleared].
     */
    private val cleanupScope = CoroutineScope(Dispatchers.Default + SupervisorJob())

    // --- intents from the UI -----------------------------------------------

    fun updateDeviceName(name: String) {
        deviceName = name
    }

    fun selectSession(session: P2pSession?) {
        selectedSession = session
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
        scope.launch {
            newKit.incomingSessions.collect { session ->
                if (sessions.none { it.id == session.id }) sessions.add(session)
                if (selectedSession == null) selectedSession = session
                launch {
                    session.incoming.collect { msg ->
                        messages.add(ChatLine(session.peer.name, msg))
                    }
                }
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
            val session = runCatching { currentKit.connect(peer) }.getOrNull() ?: return@launch
            if (sessions.none { it.id == session.id }) sessions.add(session)
            selectedSession = session
            launch {
                session.incoming.collect { msg ->
                    messages.add(ChatLine(session.peer.name, msg))
                }
            }
        }
    }

    fun sendText(text: String) {
        val s = selectedSession ?: return
        val scope = runScope ?: return
        scope.launch {
            runCatching { s.send(P2pMessage.Text(text)) }
            messages.add(ChatLine("(me)", P2pMessage.Text(text)))
        }
    }

    fun stop() {
        val toStop = kit ?: return
        kit = null
        _isRunning.value = false
        runScope?.cancel()
        runScope = null
        _peers.value = emptyList()
        sessions.clear()
        messages.clear()
        selectedSession = null
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

    private companion object {
        const val APP_ID = "p2pkit-desktop-sample"
        const val LOG_TAG = "p2pkit"
    }
}

/** One line of chat displayed in the running screen. */
data class ChatLine(val from: String, val message: P2pMessage) {
    val formatted: String
        get() = when (message) {
            is P2pMessage.Text -> message.value
            is P2pMessage.Binary -> "<binary ${message.bytes.size}B>"
        }
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
