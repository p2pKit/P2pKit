package dev.p2pkit.sample.desktop.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.MoreVert
import androidx.compose.material3.AssistChip
import androidx.compose.material3.AssistChipDefaults
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilterChip
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.RadioButton
import androidx.compose.material3.Surface
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.runtime.snapshots.SnapshotStateList
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.window.Window
import androidx.compose.ui.window.application
import androidx.compose.ui.window.rememberWindowState
import dev.p2pkit.core.AppId
import dev.p2pkit.core.ConnectionState
import dev.p2pkit.core.ExperimentalP2pApi
import dev.p2pkit.core.P2pKit
import dev.p2pkit.core.P2pLogger
import dev.p2pkit.core.P2pMessage
import dev.p2pkit.core.P2pSession
import dev.p2pkit.core.P2pState
import dev.p2pkit.core.Peer
import dev.p2pkit.core.ReconnectPolicy
import dev.p2pkit.core.provisioning.ManualConnectionInfo
import dev.p2pkit.core.transfer.FileTransferState
import dev.p2pkit.core.transfer.P2pFileTransfer
import dev.p2pkit.core.transfer.sendFile
import dev.p2pkit.provisioning.desktop.jvm
import dev.p2pkit.transport.lan.lan
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.launch
import kotlinx.io.asSink
import java.awt.FileDialog
import java.awt.Frame
import java.io.File

// =====================================================================
// Entry point
// =====================================================================

fun main() = application {
    Window(
        onCloseRequest = ::exitApplication,
        state = rememberWindowState(width = 980.dp, height = 760.dp),
        title = "P2pKit Test Harness (Desktop)"
    ) {
        MaterialTheme {
            Surface(modifier = Modifier.fillMaxSize()) {
                P2pKitSampleApp()
            }
        }
    }
}

@Composable
private fun P2pKitSampleApp() {
    // Parent-scoped coroutine scope. Survives the screen leaving composition,
    // which is critical for `kit.stop()` cleanup to complete on Stop without
    // being cancelled mid-flight.
    val appScope = rememberCoroutineScope()
    val holder = remember { DesktopP2pState(appScope) }

    // Final clean-up when the whole app composable leaves.
    DisposableEffect(holder) {
        onDispose { holder.shutdownIfRunning() }
    }

    if (!holder.isRunning) {
        SetupScreen(holder)
    } else {
        RoomScreen(holder)
    }
}

// =====================================================================
// State holder — desktop equivalent of P2pKitViewModel
// =====================================================================

/**
 * Owns the [P2pKit] instance and all room state for the desktop sample.
 *
 * Mirrors `P2pKitViewModel` in the Android sample but as a plain class
 * since desktop has no ViewModelStore. Lifetime is tied to the parent
 * Composable scope ([appScope]).
 *
 * No fixed cap on connected peers: broadcast sends to every entry in the
 * live [connectedSessions] snapshot; targeted sends use any subset of
 * peer ids in [targetedPeerIds].
 */
private class DesktopP2pState(private val appScope: CoroutineScope) {

    // --- identity / config -------------------------------------------------

    var deviceName: String by mutableStateOf("Desktop-${(1000..9999).random()}")
    var appIdInput: String by mutableStateOf(DEFAULT_APP_ID)
    var reconnectChoice: ReconnectChoice by mutableStateOf(ReconnectChoice.Disabled)

    private val _localPeerId = MutableStateFlow<String?>(null)
    val localPeerId: StateFlow<String?> = _localPeerId.asStateFlow()

    // --- lifecycle flags ---------------------------------------------------

    var isRunning: Boolean by mutableStateOf(false)
        private set

    private val _kitState = MutableStateFlow<P2pState>(P2pState.Idle)
    val kitState: StateFlow<P2pState> = _kitState.asStateFlow()

    private val _advertising = MutableStateFlow(false)
    val advertising: StateFlow<Boolean> = _advertising.asStateFlow()

    private val _discovering = MutableStateFlow(false)
    val discovering: StateFlow<Boolean> = _discovering.asStateFlow()

    /**
     * Auto-mesh: when ON, auto-connects to every discovered peer using
     * a lexicographic tie-break (only initiate if our [localPeerId] is
     * less than the peer's) so both sides never race into duplicate
     * sessions. Default ON — makes the three-device room work without
     * any manual Connect taps.
     */
    private val _autoMesh = MutableStateFlow(true)
    val autoMesh: StateFlow<Boolean> = _autoMesh.asStateFlow()

    private val _manualConnectionInfo = MutableStateFlow<ManualConnectionInfo?>(null)
    val manualConnectionInfo: StateFlow<ManualConnectionInfo?> = _manualConnectionInfo.asStateFlow()

    /** True for the brief duration of [start] (setting up flow collectors). */
    private val _isStarting = MutableStateFlow(false)
    val isStarting: StateFlow<Boolean> = _isStarting.asStateFlow()

    /** True from [stop] until the in-flight kit.stop() coroutine returns. */
    private val _isStopping = MutableStateFlow(false)
    val isStopping: StateFlow<Boolean> = _isStopping.asStateFlow()

    /** True while a [connectManual] call is in-flight. */
    private val _isManualDialing = MutableStateFlow(false)
    val isManualDialing: StateFlow<Boolean> = _isManualDialing.asStateFlow()

    /**
     * Peers whose [connect] coroutine is in-flight. Used to disable their
     * Connect button and show "Connecting…" while waiting on the SDK.
     */
    val pendingConnectPeerIds: SnapshotStateList<String> = mutableStateListOf()

    // --- room state --------------------------------------------------------

    private val _peers = MutableStateFlow<List<Peer>>(emptyList())
    val peers: StateFlow<List<Peer>> = _peers.asStateFlow()

    val connectedSessions: SnapshotStateList<P2pSession> = mutableStateListOf()
    val roomMessages: SnapshotStateList<RoomMessage> = mutableStateListOf()
    val targetedPeerIds: SnapshotStateList<String> = mutableStateListOf()
    val logTail: SnapshotStateList<String> = mutableStateListOf()
    val fileTransfers: SnapshotStateList<FileTransferRow> = mutableStateListOf()

    // --- internals ---------------------------------------------------------

    private var kit: P2pKit? = null
    private var runScope: CoroutineScope? = null
    private val sessionJobs: MutableMap<String, Job> = mutableMapOf()
    private var nextMessageId: Long = 1L

    // --- intents -----------------------------------------------------------

    fun togglePeerTarget(peerId: String) {
        if (targetedPeerIds.contains(peerId)) targetedPeerIds.remove(peerId)
        else targetedPeerIds.add(peerId)
    }

    fun clearPeerTargets() {
        targetedPeerIds.clear()
    }

    fun toggleAutoMesh() {
        _autoMesh.value = !_autoMesh.value
        System.err.println("[p2pkit] auto-mesh = ${_autoMesh.value}")
    }

    fun start() {
        if (isRunning || _isStarting.value) return  // idempotent + re-entry safe
        val trimmedName = deviceName.trim()
        if (trimmedName.isEmpty()) {
            System.err.println("[p2pkit WARN] start aborted: deviceName is blank")
            return
        }
        deviceName = trimmedName
        _isStarting.value = true
        val choice = reconnectChoice
        val effectiveAppId = appIdInput.trim().ifEmpty { DEFAULT_APP_ID }
        appIdInput = effectiveAppId
        val newKit = P2pKit.create {
            appId = AppId(effectiveAppId)
            this.deviceName = this@DesktopP2pState.deviceName
            transports { lan() }
            networkProvisioning { jvm() }
            lifecycle {
                reconnectPolicy = when (choice) {
                    ReconnectChoice.Disabled -> ReconnectPolicy.Disabled
                    is ReconnectChoice.Enabled -> ReconnectPolicy.Enabled(
                        maxAttempts = choice.maxAttempts,
                        retryDelayMillis = choice.retryDelayMillis
                    )
                }
            }
            logger = TailLogger(this@DesktopP2pState)
        }
        kit = newKit
        _localPeerId.value = newKit.localPeerId.value
        System.err.println(
            "[p2pkit] kit started: deviceName=${newKit.localDeviceName} " +
                "appId=${newKit.appId.value} peerId=${newKit.localPeerId.value} " +
                "reconnect=${choice.describe()}"
        )

        val supervisor = SupervisorJob(appScope.coroutineContext[Job])
        val scope = CoroutineScope(appScope.coroutineContext + supervisor)
        runScope = scope

        scope.launch { newKit.state.collect { _kitState.value = it } }
        scope.launch { newKit.peers.collect { _peers.value = it } }
        scope.launch { newKit.sessions.collect { reconcileSessions(it, scope) } }
        scope.launch {
            // Refresh manual connection info on a slow cadence so the UI shows
            // the latest local host(s) without spamming the provisioning impl.
            while (true) {
                _manualConnectionInfo.value = runCatching {
                    newKit.networkProvisioning.getManualConnectionInfo()
                }.getOrNull()
                kotlinx.coroutines.delay(5_000)
            }
        }
        scope.launch {
            runCatching { newKit.startAdvertising() }
                .onSuccess { _advertising.value = true }
                .onFailure {
                    System.err.println("[p2pkit WARN] startAdvertising failed: ${it.message}")
                    appendSystemMessage("advertise failed: ${it.message ?: it::class.simpleName}")
                }
            runCatching { newKit.startDiscovery() }
                .onSuccess { _discovering.value = true }
                .onFailure {
                    System.err.println("[p2pkit WARN] startDiscovery failed: ${it.message}")
                    appendSystemMessage("discovery failed: ${it.message ?: it::class.simpleName}")
                }
        }

        // Auto-mesh: route through [connect] (which holds the pendingConnect
        // guard) instead of calling `kit.connect` directly, so a manual
        // Connect tap during the in-flight window doesn't race onto a
        // second `kit.connect` invocation. See the Android sample's
        // equivalent block for the full rationale.
        scope.launch {
            combine(_autoMesh, newKit.peers) { enabled, peers -> enabled to peers }
                .collect { (enabled, peers) ->
                    if (!enabled) return@collect
                    val myId = newKit.localPeerId.value
                    val connectedIds = connectedSessions.map { it.peer.id.value }.toSet()
                    for (peer in peers) {
                        if (peer.id.value in connectedIds) continue
                        if (pendingConnectPeerIds.contains(peer.id.value)) continue
                        if (myId < peer.id.value) {
                            System.err.println("[p2pkit] auto-mesh: initiating connect to ${peer.name}")
                            connect(peer)
                        }
                    }
                }
        }

        isRunning = true
        _isStarting.value = false
    }

    fun connect(peer: Peer) {
        val currentKit = kit ?: return
        val scope = runScope ?: return
        val peerId = peer.id.value
        if (pendingConnectPeerIds.contains(peerId)) {
            appendSystemMessage("already connecting to ${peer.name}")
            return
        }
        val existing = connectedSessions.firstOrNull { it.peer.id.value == peerId }
        if (existing != null && existing.state.value == ConnectionState.Connected) {
            appendSystemMessage("already connected to ${peer.name}")
            return
        }
        pendingConnectPeerIds.add(peerId)
        scope.launch {
            try {
                runCatching { currentKit.connect(peer) }.onFailure {
                    System.err.println("[p2pkit WARN] connect to ${peer.name} failed: ${it.message}")
                    appendSystemMessage("failed to connect to ${peer.name}: ${it.message ?: it::class.simpleName}")
                }
            } finally {
                pendingConnectPeerIds.remove(peerId)
            }
        }
    }

    /**
     * Manual-IP fallback: parses "host:port" and dials it via the
     * provisioning module's [createManualPeer]. Used when mDNS is blocked.
     */
    @OptIn(ExperimentalP2pApi::class)
    fun connectManual(input: String) {
        val currentKit = kit ?: run {
            appendSystemMessage("manual: kit not started")
            return
        }
        val scope = runScope ?: return
        if (_isManualDialing.value) {
            appendSystemMessage("manual: dial already in progress")
            return
        }
        val parts = input.trim().split(':', limit = 2)
        val host = parts.getOrNull(0)?.trim().orEmpty()
        val portStr = parts.getOrNull(1)?.trim().orEmpty()
        if (host.isEmpty()) {
            appendSystemMessage("manual: host cannot be empty (expected host:port)")
            return
        }
        val port = portStr.toIntOrNull()
        if (port == null || port !in 1..65_535) {
            appendSystemMessage("manual: port must be 1..65535 (got '$portStr')")
            return
        }
        // Reject obvious garbage in host so the user sees a useful message
        // instead of waiting for the OS connect to fail.
        if (!host.all { it.isLetterOrDigit() || it in ".:_-" }) {
            appendSystemMessage("manual: host contains invalid characters: '$host'")
            return
        }
        _isManualDialing.value = true
        scope.launch {
            try {
                val synthetic = runCatching {
                    currentKit.networkProvisioning.createManualPeer(host, port)
                }.getOrElse {
                    System.err.println("[p2pkit WARN] manual createManualPeer failed: ${it.message}")
                    appendSystemMessage("manual: createManualPeer failed: ${it.message ?: it::class.simpleName}")
                    return@launch
                }
                runCatching { currentKit.connect(synthetic) }.onFailure {
                    System.err.println("[p2pkit WARN] manual connect failed: ${it.message}")
                    appendSystemMessage("manual: connect to $host:$port failed: ${it.message ?: it::class.simpleName}")
                }
            } finally {
                _isManualDialing.value = false
            }
        }
    }

    fun closeSession(peerId: String) {
        val scope = runScope ?: return
        val target = connectedSessions.firstOrNull { it.peer.id.value == peerId }
        if (target == null) {
            appendSystemMessage("close failed: peer not in session list")
            return
        }
        scope.launch {
            runCatching { target.close() }.onFailure {
                System.err.println("[p2pkit WARN] close session to ${target.peer.name} failed: ${it.message}")
                appendSystemMessage("close ${target.peer.name} failed: ${it.message ?: it::class.simpleName}")
            }
        }
    }

    fun sendRoomMessage(text: String) {
        val trimmed = text.trim()
        if (trimmed.isEmpty()) {
            appendSystemMessage("nothing sent — message was empty")
            return
        }
        val scope = runScope ?: return

        val sessionsSnapshot = connectedSessions.toList()
        val targetedSet = targetedPeerIds.toSet()
        val target: SendTarget = if (targetedSet.isEmpty()) SendTarget.All
        else SendTarget.Specific(targetedSet)

        // Only Connected sessions can actually receive — Connecting /
        // Reconnecting / Closing / Closed all silently drop at the SDK
        // level. Filter here so the UI accurately reports who got the send.
        val recipients = when (target) {
            SendTarget.All -> sessionsSnapshot.filter { it.state.value == ConnectionState.Connected }
            is SendTarget.Specific -> sessionsSnapshot.filter {
                it.peer.id.value in target.peerIds && it.state.value == ConnectionState.Connected
            }
        }
        if (recipients.isEmpty()) {
            val why = if (sessionsSnapshot.isEmpty()) "no sessions"
            else "no peers are Connected (have ${sessionsSnapshot.size} session(s) in non-Connected states)"
            appendSystemMessage("nothing sent — $why")
            return
        }
        val skipped = sessionsSnapshot - recipients.toSet()
        for (s in skipped) {
            val inTarget = target is SendTarget.Specific && s.peer.id.value in target.peerIds
            val isTargeted = target is SendTarget.All || inTarget
            if (isTargeted) {
                appendSystemMessage("skipped ${s.peer.name} (state=${s.state.value})")
            }
        }

        val body = P2pMessage.Text(trimmed)
        roomMessages.add(
            RoomMessage(
                id = nextMessageId++,
                senderPeerId = null,
                senderName = "(me)",
                body = body,
                timestamp = System.currentTimeMillis(),
                direction = RoomMessage.Direction.Outgoing,
                target = target
            )
        )
        System.err.println(
            "[p2pkit] room: ${if (target is SendTarget.All) "broadcast" else "targeted"} " +
                "→ ${recipients.size} peer(s): ${trimmed.take(60)}"
        )

        for (session in recipients) {
            scope.launch {
                runCatching { session.send(body) }.onFailure {
                    System.err.println("[p2pkit WARN] send to ${session.peer.name} failed: ${it.message}")
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
                    .onFailure { System.err.println("[p2pkit WARN] stopAdvertising failed: ${it.message}") }
            } else {
                runCatching { currentKit.startAdvertising() }
                    .onSuccess { _advertising.value = true }
                    .onFailure { System.err.println("[p2pkit WARN] startAdvertising failed: ${it.message}") }
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
                    .onFailure { System.err.println("[p2pkit WARN] stopDiscovery failed: ${it.message}") }
            } else {
                runCatching { currentKit.startDiscovery() }
                    .onSuccess { _discovering.value = true }
                    .onFailure { System.err.println("[p2pkit WARN] startDiscovery failed: ${it.message}") }
            }
        }
    }

    fun stop() {
        val toStop = kit ?: return
        if (_isStopping.value) return
        _isStopping.value = true
        kit = null
        isRunning = false
        _advertising.value = false
        _discovering.value = false
        _kitState.value = P2pState.Stopped
        runScope?.cancel()
        runScope = null
        sessionJobs.clear()
        _peers.value = emptyList()
        connectedSessions.clear()
        pendingConnectPeerIds.clear()
        targetedPeerIds.clear()
        roomMessages.clear()
        fileTransfers.clear()
        _localPeerId.value = null
        _manualConnectionInfo.value = null
        _isManualDialing.value = false
        // appScope (not runScope) so the stop coroutine survives our
        // runScope.cancel() above.
        appScope.launch {
            runCatching { toStop.stop() }
            _isStopping.value = false
        }
    }

    // --- file transfer (v0.2.2) -------------------------------------------

    fun sendFile(peerId: String, file: File) {
        val scope = runScope ?: return
        val session = connectedSessions.firstOrNull { it.peer.id.value == peerId }
        if (session == null) {
            appendSystemMessage("send file '${file.name}' failed: peer not in session list")
            return
        }
        if (session.state.value != ConnectionState.Connected) {
            appendSystemMessage(
                "send file to ${session.peer.name} failed: session not Connected (state=${session.state.value})"
            )
            return
        }
        if (!file.exists() || !file.isFile) {
            appendSystemMessage("send file failed: '${file.absolutePath}' is missing or not a regular file")
            return
        }
        if (!file.canRead()) {
            appendSystemMessage("send file failed: '${file.absolutePath}' is not readable (check permissions)")
            return
        }
        if (file.length() == 0L) {
            appendSystemMessage("send file failed: '${file.name}' is empty (0 bytes)")
            return
        }
        scope.launch {
            val transfer = runCatching { session.sendFile(file) }
                .getOrElse {
                    System.err.println("[p2pkit WARN] sendFile failed: ${it.message}")
                    appendSystemMessage("send file '${file.name}' failed: ${it.message ?: it::class.simpleName}")
                    return@launch
                }
            registerOutgoingTransfer(transfer, session.peer.name, scope)
        }
    }

    /**
     * Called by the UI when the native file picker is dismissed without a
     * selection. Surfaces a system-message line so the user knows the
     * "Send file…" path silently terminated.
     */
    fun notifyFilePickerCancelled(peerId: String) {
        val peerName = connectedSessions.firstOrNull { it.peer.id.value == peerId }?.peer?.name
            ?: peerId.take(8)
        appendSystemMessage("file send to $peerName cancelled (no file chosen)")
    }

    fun cancelFileTransfer(id: String) {
        val row = fileTransfers.firstOrNull { it.id == id } ?: return
        val scope = runScope ?: return
        scope.launch { runCatching { row.transfer.cancel("user cancelled") } }
    }

    private fun wireIncomingFiles(session: P2pSession, scope: CoroutineScope) {
        scope.launch {
            session.incomingFiles.collect { offer ->
                val baseDir = File(System.getProperty("user.home") ?: ".", ".p2pkit/incoming")
                val saveDir = File(baseDir, sanitize(session.peer.name)).also { it.mkdirs() }
                val saveFile = File(saveDir, sanitize(offer.name))
                System.err.println(
                    "[p2pkit] incoming file ${offer.name} (${offer.sizeBytes}B) → ${saveFile.absolutePath}"
                )
                val out = runCatching { saveFile.outputStream() }
                    .getOrElse { e ->
                        System.err.println("[p2pkit WARN] cannot open $saveFile: ${e.message}")
                        runCatching { offer.reject("cannot open destination") }
                        return@collect
                    }
                val incoming = runCatching { offer.accept(out.asSink()) }
                    .getOrElse { e ->
                        runCatching { out.close() }
                        System.err.println("[p2pkit WARN] accept ${offer.name} failed: ${e.message}")
                        return@collect
                    }
                registerIncomingTransfer(incoming, session.peer.name, saveFile.absolutePath, scope, out)
            }
        }
    }

    private fun registerOutgoingTransfer(
        transfer: P2pFileTransfer,
        peerName: String,
        scope: CoroutineScope
    ) {
        addRow(
            FileTransferRow(
                id = transfer.id,
                direction = FileTransferDirection.Outgoing,
                name = transfer.name,
                sizeBytes = transfer.sizeBytes,
                peerName = peerName,
                state = transfer.state.value,
                bytesTransferred = 0L,
                destinationPath = null,
                transfer = transfer
            )
        )
        appendSystemMessage("sending file '${transfer.name}' (${transfer.sizeBytes}B) to $peerName")
        scope.launch { transfer.state.collect { st -> updateRowState(transfer.id, st) } }
        scope.launch { transfer.bytesTransferred.collect { b -> updateRowBytes(transfer.id, b) } }
    }

    private fun registerIncomingTransfer(
        transfer: P2pFileTransfer,
        peerName: String,
        destinationPath: String,
        scope: CoroutineScope,
        out: java.io.OutputStream
    ) {
        addRow(
            FileTransferRow(
                id = transfer.id,
                direction = FileTransferDirection.Incoming,
                name = transfer.name,
                sizeBytes = transfer.sizeBytes,
                peerName = peerName,
                state = transfer.state.value,
                bytesTransferred = 0L,
                destinationPath = destinationPath,
                transfer = transfer
            )
        )
        appendSystemMessage("receiving file '${transfer.name}' from $peerName → $destinationPath")
        scope.launch {
            transfer.state.collect { st ->
                updateRowState(transfer.id, st)
                if (st is FileTransferState.Completed ||
                    st is FileTransferState.Failed ||
                    st is FileTransferState.Cancelled
                ) {
                    runCatching { out.close() }
                }
            }
        }
        scope.launch { transfer.bytesTransferred.collect { b -> updateRowBytes(transfer.id, b) } }
    }

    private fun addRow(row: FileTransferRow) {
        fileTransfers.add(0, row)
        while (fileTransfers.size > FILE_TRANSFER_HISTORY_CAPACITY) {
            fileTransfers.removeAt(fileTransfers.size - 1)
        }
    }

    private fun updateRowState(id: String, state: FileTransferState) {
        val idx = fileTransfers.indexOfFirst { it.id == id }
        if (idx < 0) return
        fileTransfers[idx] = fileTransfers[idx].copy(state = state)
    }

    private fun updateRowBytes(id: String, bytes: Long) {
        val idx = fileTransfers.indexOfFirst { it.id == id }
        if (idx < 0) return
        fileTransfers[idx] = fileTransfers[idx].copy(bytesTransferred = bytes)
    }

    private fun sanitize(raw: String): String {
        val cleaned = raw.replace(Regex("""[\\/:*?"<>|]"""), "_").trim()
        return cleaned.ifEmpty { "untitled" }
    }

    /** Called when the whole UI composable disposes. */
    fun shutdownIfRunning() {
        if (isRunning) stop()
    }

    // --- helpers -----------------------------------------------------------

    private fun reconcileSessions(current: List<P2pSession>, scope: CoroutineScope) {
        val currentIds = current.map { it.id }.toSet()

        val droppedIds = sessionJobs.keys.toList().filter { it !in currentIds }
        for (id in droppedIds) {
            sessionJobs.remove(id)?.cancel()
            val removed = connectedSessions.firstOrNull { it.id == id }
            if (removed != null) {
                connectedSessions.remove(removed)
                targetedPeerIds.remove(removed.peer.id.value)
                appendSystemMessage("disconnected from ${removed.peer.name}")
                System.err.println("[p2pkit] room: session removed ${removed.peer.name}")
            }
        }

        for (session in current) {
            if (sessionJobs.containsKey(session.id)) continue
            connectedSessions.add(session)
            appendSystemMessage("connected to ${session.peer.name}")
            System.err.println("[p2pkit] room: session added ${session.peer.name}")
            sessionJobs[session.id] = scope.launch {
                session.incoming.collect { msg ->
                    System.err.println("[p2pkit] room: incoming from ${session.peer.name}")
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
            scope.launch {
                session.state.collect { st ->
                    System.err.println("[p2pkit] session ${session.peer.name} → $st")
                }
            }
            wireIncomingFiles(session, scope)
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
        if (logTail.size >= LOG_TAIL_CAPACITY) logTail.removeAt(0)
        logTail.add("$level  $message")
    }

    companion object {
        const val DEFAULT_APP_ID = "p2pkit-desktop-sample"
        const val LOG_TAIL_CAPACITY = 30
        const val FILE_TRANSFER_HISTORY_CAPACITY = 24
    }
}

enum class FileTransferDirection { Outgoing, Incoming }

data class FileTransferRow(
    val id: String,
    val direction: FileTransferDirection,
    val name: String,
    val sizeBytes: Long,
    val peerName: String,
    val state: FileTransferState,
    val bytesTransferred: Long,
    val destinationPath: String?,
    val transfer: P2pFileTransfer
)

private fun pickFile(): File? {
    val dialog = FileDialog(null as Frame?, "Select file to send", FileDialog.LOAD)
    dialog.isVisible = true
    val name = dialog.file ?: return null
    val dir = dialog.directory ?: return null
    return File(dir, name)
}

// =====================================================================
// Sample-level types — identical shape to the Android sample
// =====================================================================

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

sealed class SendTarget {
    data object All : SendTarget()
    data class Specific(val peerIds: Set<String>) : SendTarget()
}

sealed class ReconnectChoice {
    data object Disabled : ReconnectChoice()
    data class Enabled(val maxAttempts: Int, val retryDelayMillis: Long) : ReconnectChoice()
}

private fun ReconnectChoice.describe(): String = when (this) {
    is ReconnectChoice.Disabled -> "Disabled"
    is ReconnectChoice.Enabled -> "Enabled(maxAttempts=$maxAttempts, retryDelayMillis=$retryDelayMillis)"
}

/**
 * Logger that mirrors output to stderr AND to the sample's in-app log strip
 * for visual diagnostics.
 */
private class TailLogger(private val state: DesktopP2pState) : P2pLogger {
    override fun debug(message: String) {
        // Debug is too chatty for stderr; only echo to the in-app strip.
        state.recordLog("D", message)
    }
    override fun info(message: String) {
        System.err.println("[p2pkit] $message")
        state.recordLog("I", message)
    }
    override fun warn(message: String, throwable: Throwable?) {
        val rendered = if (throwable != null) "$message (${throwable.message})" else message
        System.err.println("[p2pkit WARN] $rendered")
        state.recordLog("W", rendered)
    }
    override fun error(message: String, throwable: Throwable?) {
        val rendered = if (throwable != null) "$message (${throwable.message})" else message
        System.err.println("[p2pkit ERROR] $rendered")
        state.recordLog("E", rendered)
    }
}

// =====================================================================
// Setup screen
// =====================================================================

@Composable
private fun SetupScreen(state: DesktopP2pState) {
    val isStarting by state.isStarting.collectAsState()
    Column(
        modifier = Modifier.fillMaxSize().padding(24.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp)
    ) {
        Text(
            text = "P2pKit Test Harness",
            style = MaterialTheme.typography.headlineSmall
        )
        Text(
            text = "Discover devices on your Wi-Fi and chat with all of them in a room. " +
                "Configure reconnect policy and identity before tapping Start.",
            style = MaterialTheme.typography.bodyMedium
        )
        OutlinedTextField(
            value = state.deviceName,
            onValueChange = { state.deviceName = it },
            label = { Text("Device name") },
            singleLine = true,
            enabled = !isStarting,
            modifier = Modifier.fillMaxWidth()
        )
        OutlinedTextField(
            value = state.appIdInput,
            onValueChange = { state.appIdInput = it },
            label = { Text("App ID (must match on every device)") },
            singleLine = true,
            enabled = !isStarting,
            modifier = Modifier.fillMaxWidth()
        )
        Text(text = "Reconnect policy", style = MaterialTheme.typography.titleSmall)
        ReconnectChoicePicker(state)
        Button(
            onClick = state::start,
            enabled = state.deviceName.trim().isNotEmpty() &&
                state.appIdInput.trim().isNotEmpty() &&
                !isStarting,
            modifier = Modifier.fillMaxWidth()
        ) {
            Text(if (isStarting) "Starting…" else "Start")
        }
    }
}

@Composable
private fun ReconnectChoicePicker(state: DesktopP2pState) {
    var maxAttemptsText by remember {
        mutableStateOf(
            (state.reconnectChoice as? ReconnectChoice.Enabled)?.maxAttempts?.toString() ?: "5"
        )
    }
    var retryDelayText by remember {
        mutableStateOf(
            (state.reconnectChoice as? ReconnectChoice.Enabled)?.retryDelayMillis?.toString() ?: "1000"
        )
    }
    val choice = state.reconnectChoice
    Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            RadioButton(
                selected = choice is ReconnectChoice.Disabled,
                onClick = { state.reconnectChoice = ReconnectChoice.Disabled }
            )
            Text("Disabled")
        }
        Row(verticalAlignment = Alignment.CenterVertically) {
            RadioButton(
                selected = choice is ReconnectChoice.Enabled,
                onClick = {
                    val attempts = maxAttemptsText.toIntOrNull()?.coerceAtLeast(1) ?: 5
                    val delay = retryDelayText.toLongOrNull()?.coerceAtLeast(0L) ?: 1_000L
                    state.reconnectChoice = ReconnectChoice.Enabled(attempts, delay)
                }
            )
            Text("Enabled")
        }
        if (choice is ReconnectChoice.Enabled) {
            Row(
                horizontalArrangement = Arrangement.spacedBy(8.dp),
                verticalAlignment = Alignment.CenterVertically
            ) {
                OutlinedTextField(
                    value = maxAttemptsText,
                    onValueChange = { txt ->
                        maxAttemptsText = txt.filter { it.isDigit() }.take(4)
                        val attempts = maxAttemptsText.toIntOrNull()?.coerceAtLeast(1) ?: 1
                        val delay = retryDelayText.toLongOrNull()?.coerceAtLeast(0L) ?: 0L
                        state.reconnectChoice = ReconnectChoice.Enabled(attempts, delay)
                    },
                    label = { Text("maxAttempts") },
                    singleLine = true,
                    modifier = Modifier.weight(1f)
                )
                OutlinedTextField(
                    value = retryDelayText,
                    onValueChange = { txt ->
                        retryDelayText = txt.filter { it.isDigit() }.take(6)
                        val attempts = maxAttemptsText.toIntOrNull()?.coerceAtLeast(1) ?: 1
                        val delay = retryDelayText.toLongOrNull()?.coerceAtLeast(0L) ?: 0L
                        state.reconnectChoice = ReconnectChoice.Enabled(attempts, delay)
                    },
                    label = { Text("retryDelayMillis") },
                    singleLine = true,
                    modifier = Modifier.weight(1f)
                )
            }
        }
    }
}

// =====================================================================
// Room screen
// =====================================================================

@Composable
private fun RoomScreen(state: DesktopP2pState) {
    val peers by state.peers.collectAsState()
    val kitState by state.kitState.collectAsState()
    val advertising by state.advertising.collectAsState()
    val discovering by state.discovering.collectAsState()
    val autoMesh by state.autoMesh.collectAsState()
    val localPeerId by state.localPeerId.collectAsState()
    val manualInfo by state.manualConnectionInfo.collectAsState()
    val isStopping by state.isStopping.collectAsState()
    val isManualDialing by state.isManualDialing.collectAsState()
    var draft by remember { mutableStateOf("") }

    Row(modifier = Modifier.fillMaxSize().padding(16.dp)) {
        // ---- Left column: header + peers + connected chips + logs ----
        Column(modifier = Modifier.width(360.dp).fillMaxHeight()) {
            StatusHeader(
                appId = state.appIdInput.ifBlank { DesktopP2pState.DEFAULT_APP_ID },
                deviceName = state.deviceName,
                peerId = localPeerId,
                kitState = kitState,
                advertising = advertising,
                discovering = discovering,
                autoMesh = autoMesh,
                isStopping = isStopping,
                onToggleAdvertising = state::toggleAdvertising,
                onToggleDiscovery = state::toggleDiscovery,
                onToggleAutoMesh = state::toggleAutoMesh,
                onStop = state::stop
            )
            HorizontalDivider(modifier = Modifier.padding(vertical = 8.dp))

            Text(
                text = "Discovered peers (${peers.size})",
                style = MaterialTheme.typography.titleSmall
            )
            Spacer(Modifier.height(4.dp))
            if (peers.isEmpty()) {
                Text(
                    text = "Searching… open another sample on the same Wi-Fi.",
                    style = MaterialTheme.typography.bodySmall
                )
            } else {
                LazyColumn(
                    modifier = Modifier.fillMaxWidth().height(220.dp),
                    verticalArrangement = Arrangement.spacedBy(6.dp)
                ) {
                    items(peers, key = { it.id.value }) { peer ->
                        PeerCard(
                            peer = peer,
                            isConnected = state.connectedSessions.any { it.peer.id.value == peer.id.value },
                            isConnecting = state.pendingConnectPeerIds.contains(peer.id.value),
                            onConnect = { state.connect(peer) }
                        )
                    }
                }
            }

            Spacer(Modifier.height(12.dp))
            ManualPeerSection(
                manualInfo = manualInfo,
                isManualDialing = isManualDialing,
                onConnectManual = state::connectManual
            )

            Spacer(Modifier.height(12.dp))
            Text(
                text = "Logs (last ${state.logTail.size})",
                style = MaterialTheme.typography.labelMedium
            )
            Spacer(Modifier.height(4.dp))
            Box(
                modifier = Modifier
                    .fillMaxWidth()
                    .height(200.dp)
                    .clip(RoundedCornerShape(6.dp))
                    .background(MaterialTheme.colorScheme.surfaceVariant)
                    .padding(6.dp)
            ) {
                LazyColumn {
                    items(state.logTail.toList()) { line ->
                        Text(
                            text = line,
                            style = MaterialTheme.typography.labelSmall,
                            maxLines = 2,
                            overflow = TextOverflow.Ellipsis
                        )
                    }
                }
            }
        }

        Spacer(Modifier.width(16.dp))

        // ---- Right column: room chips + timeline + input ----
        Column(modifier = Modifier.fillMaxSize()) {
            val connected = state.connectedSessions.toList()
            if (connected.isNotEmpty()) {
                Text(
                    text = "Room (${connected.size} connected)",
                    style = MaterialTheme.typography.titleMedium
                )
                Spacer(Modifier.height(4.dp))
                LazyRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    items(connected, key = { it.id }) { session ->
                        ConnectedPeerChip(
                            session = session,
                            isTargeted = state.targetedPeerIds.contains(session.peer.id.value),
                            onToggleTarget = { state.togglePeerTarget(session.peer.id.value) },
                            onCloseSession = { state.closeSession(session.peer.id.value) },
                            onSendFile = {
                                val file = pickFile()
                                if (file != null) state.sendFile(session.peer.id.value, file)
                                else state.notifyFilePickerCancelled(session.peer.id.value)
                            }
                        )
                    }
                    item {
                        if (state.targetedPeerIds.isNotEmpty()) {
                            AssistChip(
                                onClick = state::clearPeerTargets,
                                label = { Text("Clear targets") },
                                colors = AssistChipDefaults.assistChipColors()
                            )
                        }
                    }
                }
            } else {
                Text(
                    text = "Tap Connect on a peer to start a room.",
                    style = MaterialTheme.typography.bodyMedium
                )
            }

            if (state.fileTransfers.isNotEmpty()) {
                Spacer(Modifier.height(12.dp))
                Text(
                    text = "File transfers (${state.fileTransfers.size})",
                    style = MaterialTheme.typography.titleSmall
                )
                Spacer(Modifier.height(4.dp))
                LazyColumn(
                    modifier = Modifier.fillMaxWidth().height(140.dp),
                    verticalArrangement = Arrangement.spacedBy(4.dp)
                ) {
                    items(state.fileTransfers.toList(), key = { it.id }) { row ->
                        FileTransferRowView(row = row, onCancel = { state.cancelFileTransfer(row.id) })
                    }
                }
            }

            Spacer(Modifier.height(12.dp))

            Text(text = "Timeline", style = MaterialTheme.typography.titleSmall)
            Spacer(Modifier.height(4.dp))
            LazyColumn(
                modifier = Modifier
                    .fillMaxWidth()
                    .height(380.dp)
                    .clip(RoundedCornerShape(6.dp))
                    .background(MaterialTheme.colorScheme.surface)
                    .padding(8.dp),
                verticalArrangement = Arrangement.spacedBy(2.dp)
            ) {
                items(state.roomMessages.toList(), key = { it.id }) { line ->
                    RoomLine(line)
                }
            }

            Spacer(Modifier.height(8.dp))

            OutlinedTextField(
                value = draft,
                onValueChange = { draft = it },
                label = { Text("Message") },
                singleLine = true,
                modifier = Modifier.fillMaxWidth()
            )
            Spacer(Modifier.height(8.dp))
            val targetCount = state.targetedPeerIds.size
            val sendLabel = when {
                connected.isEmpty() -> "No peers connected"
                targetCount == 0 -> "Broadcast (${connected.size})"
                else -> "Send to $targetCount"
            }
            // Only enable Send when at least one session is actually in
            // ConnectionState.Connected — Connecting/Reconnecting peers
            // would silently drop the send at the SDK level.
            val hasConnectedSession = connected.any { it.state.collectAsState().value == ConnectionState.Connected }
            Button(
                onClick = {
                    val text = draft.trim()
                    if (text.isEmpty()) return@Button
                    draft = ""
                    state.sendRoomMessage(text)
                },
                modifier = Modifier.fillMaxWidth(),
                enabled = hasConnectedSession && draft.trim().isNotEmpty() && !isStopping
            ) {
                Text(sendLabel)
            }
        }
    }
}

// =====================================================================
// Pieces
// =====================================================================

@Composable
private fun StatusHeader(
    appId: String,
    deviceName: String,
    peerId: String?,
    kitState: P2pState,
    advertising: Boolean,
    discovering: Boolean,
    autoMesh: Boolean,
    isStopping: Boolean,
    onToggleAdvertising: () -> Unit,
    onToggleDiscovery: () -> Unit,
    onToggleAutoMesh: () -> Unit,
    onStop: () -> Unit
) {
    Column(verticalArrangement = Arrangement.spacedBy(2.dp)) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.SpaceBetween
        ) {
            Text(text = deviceName, fontWeight = FontWeight.SemiBold)
            OverflowMenu(onStop = onStop, isStopping = isStopping)
        }
        Text(text = "appId: $appId", style = MaterialTheme.typography.bodySmall)
        Text(
            text = "peerId: ${peerId?.take(8) ?: "—"}…",
            style = MaterialTheme.typography.bodySmall
        )
        Text(
            text = "state: ${kitState::class.simpleName}",
            style = MaterialTheme.typography.bodySmall
        )
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(12.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text("Advertise", style = MaterialTheme.typography.bodySmall)
                Switch(checked = advertising, onCheckedChange = { onToggleAdvertising() })
            }
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text("Discover", style = MaterialTheme.typography.bodySmall)
                Switch(checked = discovering, onCheckedChange = { onToggleDiscovery() })
            }
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text("Auto-mesh", style = MaterialTheme.typography.bodySmall)
                Switch(checked = autoMesh, onCheckedChange = { onToggleAutoMesh() })
            }
        }
    }
}

@Composable
private fun OverflowMenu(onStop: () -> Unit, isStopping: Boolean) {
    var expanded by remember { mutableStateOf(false) }
    Box {
        IconButton(onClick = { expanded = true }) {
            Icon(Icons.Default.MoreVert, contentDescription = "More")
        }
        DropdownMenu(expanded = expanded, onDismissRequest = { expanded = false }) {
            DropdownMenuItem(
                text = { Text(if (isStopping) "Stopping…" else "Stop kit") },
                enabled = !isStopping,
                onClick = {
                    expanded = false
                    onStop()
                }
            )
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun ConnectedPeerChip(
    session: P2pSession,
    isTargeted: Boolean,
    onToggleTarget: () -> Unit,
    onCloseSession: () -> Unit,
    onSendFile: () -> Unit
) {
    val state by session.state.collectAsState()
    var menuExpanded by remember { mutableStateOf(false) }
    Box {
        FilterChip(
            selected = isTargeted,
            onClick = onToggleTarget,
            label = {
                Text("${session.peer.name} · ${state.name.lowercase()}")
            },
            trailingIcon = {
                IconButton(onClick = { menuExpanded = true }) {
                    Icon(Icons.Default.MoreVert, contentDescription = "Session actions")
                }
            }
        )
        DropdownMenu(expanded = menuExpanded, onDismissRequest = { menuExpanded = false }) {
            DropdownMenuItem(
                text = { Text("Send file…") },
                enabled = state == ConnectionState.Connected,
                onClick = {
                    menuExpanded = false
                    onSendFile()
                }
            )
            DropdownMenuItem(
                text = { Text("Close session") },
                enabled = state == ConnectionState.Connected || state == ConnectionState.Reconnecting,
                onClick = {
                    menuExpanded = false
                    onCloseSession()
                }
            )
        }
    }
}

@Composable
private fun FileTransferRowView(row: FileTransferRow, onCancel: () -> Unit) {
    val state = row.state
    val isActive = state is FileTransferState.Offered ||
        state is FileTransferState.Accepted ||
        state is FileTransferState.Sending
    val arrow = if (row.direction == FileTransferDirection.Outgoing) "↑" else "↓"
    val sizeKb = row.sizeBytes / 1024
    val sentKb = row.bytesTransferred / 1024
    val pct = if (row.sizeBytes > 0) ((row.bytesTransferred * 100) / row.sizeBytes).toInt() else 0
    Card(modifier = Modifier.fillMaxWidth()) {
        Column(modifier = Modifier.padding(8.dp)) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.SpaceBetween
            ) {
                Text(
                    text = "$arrow ${row.name}",
                    style = MaterialTheme.typography.bodyMedium,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis
                )
                Text(
                    text = "${row.peerName} · ${state.label()}",
                    style = MaterialTheme.typography.labelSmall
                )
            }
            Text(
                text = "$sentKb / $sizeKb KiB ($pct%)",
                style = MaterialTheme.typography.labelSmall
            )
            if (row.destinationPath != null) {
                Text(
                    text = "saved to ${row.destinationPath}",
                    style = MaterialTheme.typography.labelSmall,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis
                )
            }
            if (isActive) {
                Spacer(Modifier.height(4.dp))
                TextButton(onClick = onCancel) { Text("Cancel") }
            }
        }
    }
}

private fun FileTransferState.label(): String = when (this) {
    is FileTransferState.Offered -> "offered"
    is FileTransferState.Accepted -> "accepted"
    is FileTransferState.Sending -> "sending ${"%.0f".format(progress * 100)}%"
    is FileTransferState.Completed -> "completed"
    is FileTransferState.Rejected -> "rejected" + (reason?.let { " — $it" } ?: "")
    is FileTransferState.Cancelled -> "cancelled" + (reason?.let { " — $it" } ?: "")
    is FileTransferState.Failed -> "failed — ${error.message ?: error::class.simpleName}"
}

@Composable
private fun RoomLine(message: RoomMessage) {
    val style = MaterialTheme.typography.bodyMedium
    val prefix = when (message.direction) {
        RoomMessage.Direction.Incoming -> "${message.senderName} → "
        RoomMessage.Direction.Outgoing -> {
            val tgt = message.target
            val tag = when (tgt) {
                SendTarget.All -> "broadcast"
                is SendTarget.Specific -> "→ ${tgt.peerIds.size} peer(s)"
            }
            "me [$tag]: "
        }
        RoomMessage.Direction.System -> "[system] "
    }
    Text(
        text = "$prefix${message.displayBody}",
        style = style,
        maxLines = 3,
        overflow = TextOverflow.Ellipsis
    )
}

@Composable
private fun ManualPeerSection(
    manualInfo: ManualConnectionInfo?,
    isManualDialing: Boolean,
    onConnectManual: (String) -> Unit
) {
    Text(text = "Manual peer (mDNS fallback)", style = MaterialTheme.typography.titleSmall)
    Spacer(Modifier.height(4.dp))
    if (manualInfo != null) {
        val hosts = manualInfo.hostAddresses.joinToString(", ")
        Text(
            text = "Local: $hosts : ${manualInfo.port}",
            style = MaterialTheme.typography.bodySmall,
            maxLines = 2,
            overflow = TextOverflow.Ellipsis
        )
    } else {
        Text(
            text = "Local: (no LAN port bound yet)",
            style = MaterialTheme.typography.bodySmall
        )
    }
    Spacer(Modifier.height(4.dp))
    var input by remember { mutableStateOf("") }
    Row(verticalAlignment = Alignment.CenterVertically) {
        OutlinedTextField(
            value = input,
            onValueChange = { input = it },
            label = { Text("Connect host:port") },
            singleLine = true,
            enabled = !isManualDialing,
            modifier = Modifier.weight(1f).padding(end = 8.dp)
        )
        Button(
            onClick = {
                val typed = input.trim()
                if (typed.isEmpty()) return@Button
                input = ""
                onConnectManual(typed)
            },
            enabled = input.trim().isNotEmpty() && !isManualDialing
        ) {
            Text(if (isManualDialing) "Dialing…" else "Connect by IP")
        }
    }
}

@Composable
private fun PeerCard(
    peer: Peer,
    isConnected: Boolean,
    isConnecting: Boolean,
    onConnect: () -> Unit
) {
    Card(modifier = Modifier.fillMaxWidth()) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(10.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.SpaceBetween
        ) {
            Column {
                Text(text = peer.name, style = MaterialTheme.typography.titleSmall)
                Text(
                    text = "${peer.platform} · ${peer.id.value.take(8)}…",
                    style = MaterialTheme.typography.bodySmall
                )
            }
            when {
                isConnected -> Text(text = "Connected", style = MaterialTheme.typography.labelSmall)
                isConnecting -> Text(text = "Connecting…", style = MaterialTheme.typography.labelSmall)
                else -> TextButton(onClick = onConnect) { Text("Connect") }
            }
        }
    }
}
