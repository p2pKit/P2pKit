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
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.selection.selectable
import androidx.compose.foundation.selection.selectableGroup
import androidx.compose.foundation.selection.toggleable
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
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.key
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.runtime.snapshots.SnapshotStateList
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.window.Window
import androidx.compose.ui.window.application
import androidx.compose.ui.window.rememberWindowState
import dev.p2pkit.core.AppId
import dev.p2pkit.core.protocol.FrameTrace
import dev.p2pkit.transport.lan.JvmLanDiag
import dev.p2pkit.core.ConnectionState
import dev.p2pkit.core.ExperimentalP2pApi
import dev.p2pkit.core.ExplicitSecurityRisk
import dev.p2pkit.core.P2pKit
import dev.p2pkit.core.P2pLogger
import dev.p2pkit.core.P2pMessage
import dev.p2pkit.core.P2pSession
import dev.p2pkit.core.P2pState
import dev.p2pkit.core.Peer
import dev.p2pkit.core.PeerAuthorizationPolicy
import dev.p2pkit.core.PeerFingerprint
import dev.p2pkit.core.ReconnectPolicy
import dev.p2pkit.core.SecurityMode
import dev.p2pkit.core.dsl.jvmSecureIdentityStore
import dev.p2pkit.core.provisioning.ManualConnectionInfo
import dev.p2pkit.core.transfer.FileTransferState
import dev.p2pkit.core.transfer.P2pFileOffer
import dev.p2pkit.core.transfer.P2pFileTransfer
import dev.p2pkit.core.transfer.sendFile
import dev.p2pkit.sample.diagnostics.DiagnosticDirection
import dev.p2pkit.sample.diagnostics.DiagnosticEventNames
import dev.p2pkit.sample.diagnostics.DiagnosticOutcome
import dev.p2pkit.sample.diagnostics.DiagnosticRecord
import dev.p2pkit.sample.diagnostics.DiagnosticSeverity
import dev.p2pkit.sample.diagnostics.cleanupStaleTransferPartsOnce
import dev.p2pkit.sample.diagnostics.reservedFileDestination
import dev.p2pkit.provisioning.desktop.jvm
import dev.p2pkit.transport.lan.lan
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.NonCancellable
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancelAndJoin
import kotlinx.coroutines.cancel
import kotlinx.coroutines.channels.BufferOverflow
import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.launch
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext
import java.awt.FileDialog
import java.awt.Frame
import java.io.File

// =====================================================================
// Entry point
// =====================================================================

fun main() {
    // LAN forensic trace (Issue #2) + decoded frame-type trace: emit every
    // P2pKitLAN / P2pKitFRAME line to stdout of the terminal that launched the
    // UI. Harmless in a test harness; the library defaults stay off.
    JvmLanDiag.enabled = true
    application {
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
}

@Composable
private fun P2pKitSampleApp() {
    // Keep SDK ownership independent of Setup/Room composition lifetimes.
    // `rememberCoroutineScope()` is cancelled as soon as its composition is
    // disposed, which could cancel the in-flight kit.stop() operation launched
    // by the disposal hook itself.
    val compositionScope = rememberCoroutineScope()
    val appScope = remember {
        CoroutineScope(compositionScope.coroutineContext.minusKey(Job) + SupervisorJob())
    }
    val holder = remember { DesktopP2pState(appScope) }
    var showDiagnostics by remember { mutableStateOf(false) }
    DisposableEffect(holder) {
        val frameTraceLease = FrameTrace.installSink(enabled = true) {
            println("P2pKitFRAME $it")
            holder.diagnostics.frame(it)
        }
        onDispose {
            frameTraceLease.release()
            holder.shutdownIfRunning()
            // The stop coroutine above is owned by appScope; cancellation is
            // intentionally deferred to process/window teardown by the host.
        }
    }

    Box(modifier = Modifier.fillMaxSize()) {
        if (showDiagnostics) {
            DesktopDiagnosticsScreen(
                diagnostics = holder.diagnostics,
                activeConnections = holder.connectedSessions.map { session ->
                    DesktopDiagnosticConnectionSnapshot(
                        sessionId = session.id,
                        peerId = session.peer.id.value,
                        state = session.state.value.toString()
                    )
                },
                revision = holder.diagnosticRevision,
                onBack = { showDiagnostics = false }
            )
        } else if (!holder.isRunning) {
            SetupScreen(holder)
        } else {
            RoomScreen(holder)
        }
        if (!showDiagnostics) {
            Button(
                onClick = { showDiagnostics = true },
                modifier = Modifier.align(Alignment.TopEnd).padding(8.dp)
            ) {
                Text("Diagnostics")
            }
        }
    }
}

// =====================================================================
// State holder — desktop equivalent of P2pKitViewModel
// =====================================================================

/**
 * Owns the [P2pKit] instance and all room state for the desktop sample.
 *
 * Mirrors `P2pKitViewModel` in the Android sample but as a plain class
 * since desktop has no ViewModelStore. Teardown uses a dedicated [appScope]
 * that is not cancelled by a Setup/Room composition transition.
 *
 * No fixed cap on connected peers: broadcast sends to every entry in the
 * live [connectedSessions] snapshot; targeted sends use any subset of
 * peer ids in [targetedPeerIds].
 */
@OptIn(ExplicitSecurityRisk::class)
internal class DesktopP2pState(private val appScope: CoroutineScope) {

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

    /** A failed start/stop still owns a kit that must be stopped before restart. */
    private val _cleanupPending = MutableStateFlow(false)
    val cleanupPending: StateFlow<Boolean> = _cleanupPending.asStateFlow()

    /** User-visible lifecycle failure; never silently discard kit ownership. */
    private val _lifecycleError = MutableStateFlow<String?>(null)
    val lifecycleError: StateFlow<String?> = _lifecycleError.asStateFlow()

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
    /** Incoming offers stay pending until explicit user consent. */
    val pendingFileOffers: SnapshotStateList<IncomingFileOffer> = mutableStateListOf()
    var diagnosticRevision: Long by mutableStateOf(0L)
        private set
    val diagnostics = DesktopDiagnosticHarness { diagnosticRevision++ }

    // --- internals ---------------------------------------------------------

    private var kit: P2pKit? = null
    private var runScope: CoroutineScope? = null
    private val advertisingToggleMutex = Mutex()
    private val discoveryToggleMutex = Mutex()

    // AUDIT-2026-06 (A-G9-samples-desktop-ios-21): track ALL per-session collector
    // jobs (incoming messages, state, pendingFileOffers) so every one of them is
    // cancelled when the session leaves kit.sessions — previously only the
    // incoming-message job was tracked and the rest leaked until kit stop.
    private val sessionJobs: MutableMap<String, List<Job>> = mutableMapOf()

    private var nextMessageId: Long = 1L

    // AUDIT-2026-06 (A-G9-samples-desktop-ios-26): P2pLogger callbacks arrive on
    // arbitrary SDK threads (JmDNS listeners, socket coroutines). Funnel them
    // through a channel consumed on the UI scope so logTail is only ever mutated
    // — including the trim — on the UI dispatcher.
    private val logLines = Channel<String>(capacity = 256, onBufferOverflow = BufferOverflow.DROP_OLDEST)

    init {
        appScope.launch {
            for (line in logLines) {
                if (logTail.size >= LOG_TAIL_CAPACITY) logTail.removeAt(0)
                logTail.add(line)
            }
        }
        appScope.launch {
            JvmLanDiag.events.collect { diagnostics.transport(it) }
        }
    }

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
        if (isRunning || _isStarting.value || _isStopping.value) return  // idempotent + re-entry safe
        if (kit != null) {
            _lifecycleError.value = "cleanup is still pending; retrying kit stop before a new start"
            stop()
            return
        }
        val trimmedName = deviceName.trim()
        if (trimmedName.isEmpty()) {
            System.err.println("[p2pkit WARN] start aborted: deviceName is blank")
            return
        }
        deviceName = trimmedName
        _isStarting.value = true
        _lifecycleError.value = null
        val choice = reconnectChoice
        val effectiveAppId = appIdInput.trim().ifEmpty { DEFAULT_APP_ID }
        appIdInput = effectiveAppId
        val newKit = try {
            P2pKit.create {
                appId = AppId(effectiveAppId)
                this.deviceName = this@DesktopP2pState.deviceName
                jvmSecureIdentityStore(DevelopmentOnlyInMemorySecureIdentityStore())
                security {
                    mode = SecurityMode.AuthenticatedV2(
                        PeerAuthorizationPolicy.AcceptAnyAuthenticatedSameApp
                    )
                }
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
                logger = diagnostics.logger(TailLogger(this@DesktopP2pState))
            }
        } catch (t: Throwable) {
            _isStarting.value = false
            _lifecycleError.value = "start failed: ${t.message ?: t::class.simpleName}"
            System.err.println("[p2pkit ERROR] ${_lifecycleError.value}".sanitizedForTerminal())
            return
        }
        kit = newKit
        _cleanupPending.value = false
        _localPeerId.value = newKit.localPeerId.value
        diagnostics.localPeerId = newKit.localPeerId.value
        val startedLine =
            "[p2pkit] kit started: deviceName=${newKit.localDeviceName} " +
                "appId=${newKit.appId.value} peerId=${newKit.localPeerId.value} " +
                "reconnect=${choice.describe()}"
        System.err.println(startedLine.sanitizedForTerminal())

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
                _manualConnectionInfo.value = runCatchingCancellable {
                    newKit.networkProvisioning.getManualConnectionInfo()
                }.getOrNull()
                kotlinx.coroutines.delay(5_000)
            }
        }
        scope.launch {
            // Treat advertise/discover as one startup transaction. Cancellation
            // belongs to teardown and must not be reported as a start failure.
            try {
                newKit.startAdvertising()
                _advertising.value = true
                newKit.startDiscovery()
                _discovering.value = true
                isRunning = true
            } catch (cancelled: CancellationException) {
                throw cancelled
            } catch (t: Throwable) {
                _advertising.value = false
                _discovering.value = false
                _lifecycleError.value = "start failed: ${t.message ?: t::class.simpleName}"
                appendSystemMessage(_lifecycleError.value!!)
                runCatchingCancellable { newKit.stop() }
                    .onSuccess {
                        if (kit === newKit) kit = null
                        _cleanupPending.value = false
                        diagnostics.localPeerId = null
                    }
                    .onFailure { cleanupError ->
                        _cleanupPending.value = true
                        _lifecycleError.value =
                            "startup cleanup failed; retry cleanup: " +
                                (cleanupError.message ?: cleanupError::class.simpleName)
                        appendSystemMessage(_lifecycleError.value!!)
                    }
                isRunning = false
                runScope = null
                this@DesktopP2pState._kitState.value = P2pState.Stopped
                cancel()
            } finally {
                _isStarting.value = false
            }
        }

        // Auto-mesh: route through [connect] (which holds the pendingConnect
        // guard) instead of calling `kit.connect` directly, so a manual
        // Connect tap during the in-flight window doesn't race onto a
        // second `kit.connect` invocation. See the Android sample's
        // equivalent block for the full rationale.
        // AUDIT-2026-06 (A-G9-samples-desktop-ios-25): kit.sessions is part of the
        // combine trigger so the mesh pass re-fires when a session drops while the
        // peer list stays stable (heartbeats do not churn the peers StateFlow).
        // Without it, a lost session with reconnect Disabled never self-heals
        // until a peer Lost/Found cycle or a manual Connect tap.
        scope.launch {
            combine(_autoMesh, newKit.peers, newKit.sessions) { enabled, peers, sessions ->
                Triple(enabled, peers, sessions)
            }.collect { (enabled, peers, sessions) ->
                if (!enabled || !isRunning) return@collect
                val myId = newKit.localPeerId.value
                val sessionPeerIds = sessions.map { it.peer.id.value }.toSet()
                for (peer in peers) {
                    if (peer.id.value in sessionPeerIds) continue
                    if (pendingConnectPeerIds.contains(peer.id.value)) continue
                    if (myId < peer.id.value) {
                        System.err.println("[p2pkit] auto-mesh: initiating connect to ${peer.name.sanitizedForTerminal()}")
                        connect(peer)
                    }
                }
            }
        }

        // The startup coroutine owns the Running transition so a partial
        // advertise/discover startup never presents a usable room.
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
                // AUDIT-2026-06 (A-G9-samples-desktop-ios-29): rethrows cancellation.
                runCatchingCancellable { currentKit.connect(peer) }.onFailure {
                    System.err.println(
                        "[p2pkit WARN] connect to ${peer.name} failed: ${it.message}".sanitizedForTerminal()
                    )
                    appendSystemMessage("failed to connect to ${peer.name}: ${it.message ?: it::class.simpleName}")
                }
            } finally {
                pendingConnectPeerIds.remove(peerId)
            }
        }
    }

    /**
     * Manual-IP fallback: parses "host:port fingerprint" and dials it via the
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
        val manualParts = input.trim().split(Regex("\\s+"), limit = 2)
        val endpoint = manualParts.getOrNull(0).orEmpty()
        val fingerprint = manualParts.getOrNull(1)?.let(PeerFingerprint::parseOrNull)
        if (fingerprint == null) {
            appendSystemMessage("manual: expected host:port followed by a full p2f1 fingerprint")
            return
        }
        val parsed = parseManualEndpoint(endpoint)
        if (parsed is ManualEndpointResult.Invalid) {
            appendSystemMessage("manual: ${parsed.reason}")
            return
        }
        parsed as ManualEndpointResult.Valid
        val (host, port) = parsed.endpoint
        _isManualDialing.value = true
        scope.launch {
            try {
                val synthetic = runCatchingCancellable {
                    currentKit.networkProvisioning.createManualPeer(host, port, fingerprint)
                }.getOrElse {
                    System.err.println(
                        "[p2pkit WARN] manual createManualPeer failed: ${it.message}".sanitizedForTerminal()
                    )
                    appendSystemMessage("manual: createManualPeer failed: ${it.message ?: it::class.simpleName}")
                    return@launch
                }
                runCatchingCancellable { currentKit.connect(synthetic) }.onFailure {
                    System.err.println(
                        "[p2pkit WARN] manual connect failed: ${it.message}".sanitizedForTerminal()
                    )
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
            runCatchingCancellable { target.close() }.onFailure {
                System.err.println(
                    "[p2pkit WARN] close session to ${target.peer.name} failed: ${it.message}".sanitizedForTerminal()
                )
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
        appendRoomMessage(
            RoomMessage(
                id = nextMessageId++,
                senderPeerId = null,
                senderName = "(me)",
                body = trimmed,
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
            val connectionId = diagnostics.connectionIdFor(session.peer.id.value)
            val payloadSize = trimmed.toByteArray().size.toLong()
            diagnostics.recorder.record(
                DiagnosticRecord(
                    peerId = session.peer.id.value,
                    connectionId = connectionId,
                    category = "metadata",
                    eventName = DiagnosticEventNames.METADATA_CREATED,
                    payloadSizeBytes = payloadSize,
                    direction = DiagnosticDirection.SENT,
                    details = mapOf("messageType" to "text")
                )
            )
            scope.launch {
                runCatchingCancellable { session.send(body) }
                    .onSuccess {
                        diagnostics.recorder.record(
                            DiagnosticRecord(
                                peerId = session.peer.id.value,
                                connectionId = connectionId,
                                category = "metadata",
                                eventName = DiagnosticEventNames.METADATA_SENT,
                                payloadSizeBytes = payloadSize,
                                direction = DiagnosticDirection.SENT,
                                outcome = DiagnosticOutcome.SUCCESS
                            )
                        )
                    }
                    .onFailure {
                        diagnostics.recorder.record(
                            DiagnosticRecord(
                                peerId = session.peer.id.value,
                                connectionId = connectionId,
                                category = "metadata",
                                eventName = DiagnosticEventNames.METADATA_REJECTED,
                                severity = DiagnosticSeverity.ERROR,
                                payloadSizeBytes = payloadSize,
                                direction = DiagnosticDirection.SENT,
                                outcome = DiagnosticOutcome.FAILURE,
                                errorCode = it::class.simpleName,
                                errorDescription = it.message
                            )
                        )
                        System.err.println(
                            "[p2pkit WARN] send to ${session.peer.name} failed: ${it.message}".sanitizedForTerminal()
                        )
                        appendSystemMessage("send to ${session.peer.name} failed: ${it.message ?: it::class.simpleName}")
                    }
            }
        }
    }

    fun toggleAdvertising() {
        val currentKit = kit ?: return
        val scope = runScope ?: return
        scope.launch {
            advertisingToggleMutex.withLock {
                if (_advertising.value) {
                    runCatchingCancellable { currentKit.stopAdvertising() }
                        .onSuccess { _advertising.value = false }
                        .onFailure {
                            System.err.println(
                                "[p2pkit WARN] stopAdvertising failed: ${it.message}".sanitizedForTerminal()
                            )
                        }
                } else {
                    runCatchingCancellable { currentKit.startAdvertising() }
                        .onSuccess { _advertising.value = true }
                        .onFailure {
                            System.err.println(
                                "[p2pkit WARN] startAdvertising failed: ${it.message}".sanitizedForTerminal()
                            )
                        }
                }
            }
        }
    }

    fun toggleDiscovery() {
        val currentKit = kit ?: return
        val scope = runScope ?: return
        scope.launch {
            discoveryToggleMutex.withLock {
                if (_discovering.value) {
                    runCatchingCancellable { currentKit.stopDiscovery() }
                        .onSuccess { _discovering.value = false }
                        .onFailure {
                            System.err.println(
                                "[p2pkit WARN] stopDiscovery failed: ${it.message}".sanitizedForTerminal()
                            )
                        }
                } else {
                    runCatchingCancellable { currentKit.startDiscovery() }
                        .onSuccess { _discovering.value = true }
                        .onFailure {
                            System.err.println(
                                "[p2pkit WARN] startDiscovery failed: ${it.message}".sanitizedForTerminal()
                            )
                        }
                }
            }
        }
    }

    fun stop() {
        val toStop = kit ?: return
        if (_isStopping.value) return
        diagnostics.recorder.record(
            DiagnosticRecord(
                category = "application",
                eventName = DiagnosticEventNames.APPLICATION_SHUTDOWN,
                currentState = "stopping"
            )
        )
        _isStopping.value = true
        _cleanupPending.value = true
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
        val offersToReject = pendingFileOffers.toList()
        pendingFileOffers.clear()
        _localPeerId.value = null
        _manualConnectionInfo.value = null
        _isManualDialing.value = false
        // appScope (not runScope) so the stop coroutine survives our
        // runScope.cancel() above.
        appScope.launch {
            try {
                offersToReject.forEach { pending ->
                    runCatchingCancellable { pending.offer.reject("sample stopped before consent") }
                }
                val stopped = runCatchingCancellable { toStop.stop() }
                stopped.onFailure {
                    // Keep ownership so a failed stop can be retried; report it
                    // visibly without claiming Running after all collectors
                    // and feature state were already torn down.
                    _cleanupPending.value = true
                    _lifecycleError.value = "stop failed: ${it.message ?: it::class.simpleName}"
                    appendSystemMessage(_lifecycleError.value!!)
                    System.err.println("[p2pkit ERROR] ${_lifecycleError.value}".sanitizedForTerminal())
                }.onSuccess {
                    if (kit === toStop) kit = null
                    _cleanupPending.value = false
                    diagnostics.localPeerId = null
                    _lifecycleError.value = null
                }
            } finally {
                _isStopping.value = false
            }
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
            val sourceDigest = withContext(Dispatchers.IO) { testFileSha256(file) }
            diagnostics.recorder.record(
                DiagnosticRecord(
                    peerId = session.peer.id.value,
                    connectionId = diagnostics.connectionIdFor(session.peer.id.value),
                    category = "file",
                    eventName = DiagnosticEventNames.FILE_SELECTED,
                    payloadSizeBytes = file.length(),
                    details = mapOf("filename" to file.name, "mimeType" to "test-fixture")
                )
            )
            appendSystemMessage("prepared ${file.name} sha256=$sourceDigest")
            val transfer = runCatchingCancellable { session.sendFile(file) }
                .getOrElse {
                    System.err.println(
                        "[p2pkit WARN] sendFile failed: ${it.message}".sanitizedForTerminal()
                    )
                    appendSystemMessage("send file '${file.name}' failed: ${it.message ?: it::class.simpleName}")
                    return@launch
                }
            diagnostics.transfer(
                peerId = session.peer.id.value,
                transferId = transfer.id,
                eventName = DiagnosticEventNames.TRANSFER_PREPARED,
                state = transfer.state.value.toString(),
                size = transfer.sizeBytes,
                direction = DiagnosticDirection.SENT
            )
            diagnostics.hash(
                session.peer.id.value,
                transfer.id,
                file.length(),
                sourceDigest,
                receiver = false
            )
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
        diagnostics.transfer(
            peerId = row.transfer.peer.id.value,
            transferId = id,
            eventName = DiagnosticEventNames.TRANSFER_CANCELLED,
            state = "Cancelling",
            outcome = DiagnosticOutcome.CANCELLATION
        )
        scope.launch { runCatchingCancellable { row.transfer.cancel("user cancelled") } }
    }

    fun rejectFileOffer(id: String) {
        val pending = pendingFileOffers.firstOrNull { it.id == id } ?: return
        pendingFileOffers.remove(pending)
        diagnostics.transfer(
            peerId = pending.offer.peer.id.value,
            transferId = id,
            eventName = DiagnosticEventNames.TRANSFER_OFFER_REJECTED,
            state = "Rejected",
            size = pending.sizeBytes,
            direction = DiagnosticDirection.RECEIVED,
            outcome = DiagnosticOutcome.CANCELLATION,
            details = mapOf("reason" to "operator rejected")
        )
        appScope.launch { runCatchingCancellable { pending.offer.reject("rejected by user") } }
    }

    fun acceptFileOffer(id: String) {
        val scope = runScope ?: return
        val pending = pendingFileOffers.firstOrNull { it.id == id } ?: return
        pendingFileOffers.remove(pending)
        diagnostics.transfer(
            peerId = pending.offer.peer.id.value,
            transferId = id,
            eventName = DiagnosticEventNames.TRANSFER_OFFER_ACCEPTED,
            state = "Accepted",
            size = pending.sizeBytes,
            direction = DiagnosticDirection.RECEIVED
        )
        scope.launch { acceptIncomingFile(pending, scope) }
    }

    // AUDIT-2026-06 (A-G9-samples-desktop-ios-21): returns the collector Job so
    // reconcileSessions can track and cancel it with the session.
    private fun wireIncomingFiles(session: P2pSession, scope: CoroutineScope): Job =
        scope.launch {
            var previousIds: Set<String> = emptySet()
            try {
                session.pendingFileOffers.collect { offers ->
                    val currentIds = offers.mapTo(mutableSetOf()) { it.id }
                    pendingFileOffers.removeAll { it.id in previousIds && it.id !in currentIds }
                    for (offer in offers) {
                        if (pendingFileOffers.none { it.id == offer.id }) {
                            pendingFileOffers += IncomingFileOffer(
                                id = offer.id,
                                name = offer.name,
                                sizeBytes = offer.sizeBytes,
                                peerName = session.peer.name,
                                offer = offer
                            )
                            appendSystemMessage(
                                "incoming file '${offer.name}' from ${session.peer.name} — awaiting consent"
                            )
                            diagnostics.transfer(
                                peerId = session.peer.id.value,
                                transferId = offer.id,
                                eventName = DiagnosticEventNames.TRANSFER_OFFER_RECEIVED,
                                state = "Offered",
                                size = offer.sizeBytes,
                                direction = DiagnosticDirection.RECEIVED
                            )
                        }
                    }
                    previousIds = currentIds
                }
            } finally {
                pendingFileOffers.removeAll { it.id in previousIds }
            }
        }

    private suspend fun acceptIncomingFile(pending: IncomingFileOffer, scope: CoroutineScope) {
        val maxBytes = 50L * 1024 * 1024
        if (pending.sizeBytes !in 0..maxBytes) {
            runCatchingCancellable { pending.offer.reject("receiver quota exceeded") }
            appendSystemMessage("rejected '${pending.name}': exceeds 50 MiB sample quota")
            return
        }
        val baseDir = File(System.getProperty("user.home") ?: ".", ".p2pkit/incoming")
        val saveDir = File(baseDir, sanitize(pending.peerName)).also { it.mkdirs() }
        runCatching { cleanupStaleTransferPartsOnce(saveDir) }
            .getOrElse { error ->
                runCatchingCancellable { pending.offer.reject("cannot clean stale destination parts") }
                appendSystemMessage(
                    "rejected '${pending.name}': ${error.message ?: "stale-part cleanup failed"}"
                )
                return
            }
        if (saveDir.usableSpace < pending.sizeBytes + 1L * 1024 * 1024) {
            runCatchingCancellable { pending.offer.reject("receiver free space is insufficient") }
            appendSystemMessage("rejected '${pending.name}': insufficient free space")
            return
        }
        val saveFile = runCatching { uniqueSaveFile(saveDir, sanitize(pending.name)) }
            .getOrElse { error ->
                runCatchingCancellable { pending.offer.reject("cannot claim destination") }
                appendSystemMessage("rejected '${pending.name}': ${error.message ?: "cannot claim destination"}")
                return
            }
        val destination = runCatching { reservedFileDestination(saveFile) }
            .getOrElse { e ->
                runCatching { saveFile.delete() }
                runCatchingCancellable { pending.offer.reject("cannot open destination") }
                appendSystemMessage("rejected '${pending.name}': ${e.message ?: "cannot open destination"}")
                return
            }
        recordTemporaryFileEvent(
            peerId = pending.offer.peer.id.value,
            transferId = pending.id,
            eventName = DiagnosticEventNames.TEMP_FILE_CREATED,
            state = "prepared"
        )
        val incoming = try {
            pending.offer.accept(destination)
        } catch (cancelled: CancellationException) {
            val cleanup = withContext(NonCancellable) {
                // Cleanup is best effort and must not replace the caller's
                // original cancellation if a broken callback throws its own
                // CancellationException.
                runCatching { destination.abort(null) }
            }
            recordTemporaryFileEvent(
                peerId = pending.offer.peer.id.value,
                transferId = pending.id,
                eventName = DiagnosticEventNames.TEMP_FILE_CLEANED,
                state = if (cleanup.isSuccess) "aborted" else "cleanup-failed",
                outcome = if (cleanup.isSuccess) DiagnosticOutcome.SUCCESS else DiagnosticOutcome.FAILURE,
                error = cleanup.exceptionOrNull()
            )
            throw cancelled
        } catch (e: Throwable) {
            val cleanup = withContext(NonCancellable) {
                val result = runCatching { destination.abort(null) }
                runCatching { saveFile.delete() }
                runCatching { pending.offer.reject("accept failed on receiver") }
                result
            }
            recordTemporaryFileEvent(
                peerId = pending.offer.peer.id.value,
                transferId = pending.id,
                eventName = DiagnosticEventNames.TEMP_FILE_CLEANED,
                state = if (cleanup.isSuccess) "aborted" else "cleanup-failed",
                outcome = if (cleanup.isSuccess) DiagnosticOutcome.SUCCESS else DiagnosticOutcome.FAILURE,
                error = cleanup.exceptionOrNull()
            )
            appendSystemMessage("receive '${pending.name}' failed: ${e.message ?: e::class.simpleName}")
            return
        }
        registerIncomingTransfer(incoming, pending.peerName, saveFile.absolutePath, scope)
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
                sha256 = null,
                transfer = transfer
            )
        )
        diagnostics.transfer(
            peerId = transfer.peer.id.value,
            transferId = transfer.id,
            eventName = DiagnosticEventNames.TRANSFER_STARTED,
            state = transfer.state.value.toString(),
            size = transfer.sizeBytes,
            direction = DiagnosticDirection.SENT
        )
        appendSystemMessage("sending file '${transfer.name}' (${transfer.sizeBytes}B) to $peerName")
        watchTransfer(transfer, scope)
    }

    private fun registerIncomingTransfer(
        transfer: P2pFileTransfer,
        peerName: String,
        destinationPath: String,
        scope: CoroutineScope
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
                sha256 = null,
                transfer = transfer
            )
        )
        diagnostics.transfer(
            peerId = transfer.peer.id.value,
            transferId = transfer.id,
            eventName = DiagnosticEventNames.TRANSFER_STARTED,
            state = transfer.state.value.toString(),
            size = transfer.sizeBytes,
            direction = DiagnosticDirection.RECEIVED
        )
        appendSystemMessage("receiving file '${transfer.name}' from $peerName → $destinationPath")
        // The transactional destination is owned by the SDK and is committed
        // or aborted even if this UI collector is cancelled.
        watchTransfer(transfer, scope) { completed ->
            if (!completed) {
                val cleanup = runCatching {
                    val destination = File(destinationPath)
                    if (destination.exists() && !destination.delete()) {
                        error("destination reservation cleanup failed")
                    }
                }
                recordTemporaryFileEvent(
                    peerId = transfer.peer.id.value,
                    transferId = transfer.id,
                    eventName = DiagnosticEventNames.TEMP_FILE_CLEANED,
                    state = if (cleanup.isSuccess) "aborted" else "cleanup-failed",
                    outcome = if (cleanup.isSuccess) DiagnosticOutcome.SUCCESS else DiagnosticOutcome.FAILURE,
                    error = cleanup.exceptionOrNull()
                )
            } else {
                recordTemporaryFileEvent(
                    peerId = transfer.peer.id.value,
                    transferId = transfer.id,
                    eventName = DiagnosticEventNames.TEMP_FILE_CLEANED,
                    state = "promoted",
                    outcome = DiagnosticOutcome.SUCCESS
                )
                val digest = withContext(Dispatchers.IO) {
                    testFileSha256(File(destinationPath))
                }
                updateRowDigest(transfer.id, digest)
                diagnostics.hash(
                    transfer.peer.id.value,
                    transfer.id,
                    File(destinationPath).length(),
                    digest,
                    receiver = true
                )
                diagnostics.transfer(
                    peerId = transfer.peer.id.value,
                    transferId = transfer.id,
                    eventName = DiagnosticEventNames.TRANSFER_DURABLE_COMMITTED,
                    state = "Completed",
                    size = transfer.sizeBytes,
                    direction = DiagnosticDirection.RECEIVED,
                    outcome = DiagnosticOutcome.SUCCESS,
                    details = mapOf("durable" to "true")
                )
                appendSystemMessage("received ${transfer.name} sha256=$digest")
            }
        }
    }

    /**
     * Collects a transfer's state/bytes into its history row, stopping once the
     * transfer reaches a terminal state so per-transfer collectors don't pile up
     * over long runs. [onFinally] runs when collection ends for any reason
     * (terminal state or run-scope cancellation).
     */
    private fun watchTransfer(
        transfer: P2pFileTransfer,
        scope: CoroutineScope,
        onFinally: (suspend (completed: Boolean) -> Unit)? = null
    ) {
        scope.launch {
            var completed = false
            val bytesJob = launch {
                transfer.bytesTransferred.collect { b -> updateRowBytes(transfer.id, b) }
            }
            try {
                transfer.state.first { st ->
                    updateRowState(transfer.id, st)
                    diagnostics.transfer(
                        peerId = transfer.peer.id.value,
                        transferId = transfer.id,
                        eventName = when (st) {
                            is FileTransferState.Completed -> DiagnosticEventNames.TRANSFER_COMPLETED
                            is FileTransferState.Failed -> DiagnosticEventNames.TRANSFER_FAILED
                            is FileTransferState.Cancelled -> DiagnosticEventNames.TRANSFER_CANCELLED
                            is FileTransferState.Rejected -> DiagnosticEventNames.TRANSFER_OFFER_REJECTED
                            else -> DiagnosticEventNames.TRANSFER_PROGRESS
                        },
                        state = st.toString(),
                        size = transfer.bytesTransferred.value,
                        direction = if (fileTransfers.firstOrNull { it.id == transfer.id }?.direction ==
                            FileTransferDirection.Outgoing
                        ) {
                            DiagnosticDirection.SENT
                        } else {
                            DiagnosticDirection.RECEIVED
                        },
                        outcome = when (st) {
                            is FileTransferState.Completed -> DiagnosticOutcome.SUCCESS
                            is FileTransferState.Failed -> DiagnosticOutcome.FAILURE
                            is FileTransferState.Cancelled -> DiagnosticOutcome.CANCELLATION
                            is FileTransferState.Rejected -> DiagnosticOutcome.CANCELLATION
                            else -> null
                        },
                        error = (st as? FileTransferState.Failed)?.error
                    )
                    if (st.isTerminal()) {
                        completed = st is FileTransferState.Completed
                        true
                    } else {
                        false
                    }
                }
                // Snap the byte counter to its final value before the collector dies.
                updateRowBytes(transfer.id, transfer.bytesTransferred.value)
            } finally {
                withContext(NonCancellable) {
                    bytesJob.cancelAndJoin()
                    onFinally?.invoke(completed)
                }
            }
        }
    }

    private fun addRow(row: FileTransferRow) {
        fileTransfers.add(0, row)
        // AUDIT-2026-06 (A-G9-samples-desktop-ios-24): evict only TERMINAL rows
        // (oldest first). An active transfer keeps its progress row and Cancel
        // button even when the history is over capacity.
        var idx = fileTransfers.size - 1
        while (fileTransfers.size > FILE_TRANSFER_HISTORY_CAPACITY && idx > 0) {
            if (fileTransfers[idx].state.isTerminal()) fileTransfers.removeAt(idx)
            idx--
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

    private fun updateRowDigest(id: String, digest: String?) {
        val idx = fileTransfers.indexOfFirst { it.id == id }
        if (idx < 0) return
        fileTransfers[idx] = fileTransfers[idx].copy(sha256 = digest)
    }

    private fun recordTemporaryFileEvent(
        peerId: String,
        transferId: String,
        eventName: String,
        state: String,
        outcome: DiagnosticOutcome? = null,
        error: Throwable? = null
    ) {
        diagnostics.recorder.record(
            DiagnosticRecord(
                peerId = peerId,
                connectionId = diagnostics.connectionIdFor(peerId),
                transferId = transferId,
                category = "storage",
                eventName = eventName,
                severity = if (error == null) DiagnosticSeverity.INFO else DiagnosticSeverity.ERROR,
                currentState = state,
                direction = DiagnosticDirection.RECEIVED,
                outcome = outcome,
                errorCode = error?.let { it::class.simpleName },
                errorDescription = error?.message,
                details = mapOf("location" to "app-private", "contentsExported" to "false")
            )
        )
    }

    private fun sanitize(raw: String): String {
        val cleaned = raw.filterNot { it.isISOControl() }
            .replace(Regex("""[\\/:*?"<>|]"""), "_")
            .trim()
        return cleaned.takeUnless { it.isEmpty() || it == "." || it == ".." } ?: "untitled"
    }

    /** Called when the whole UI composable disposes, including during startup. */
    fun shutdownIfRunning() {
        diagnostics.shutdown()
        if (kit != null) stop()
    }

    // --- helpers -----------------------------------------------------------

    private fun reconcileSessions(current: List<P2pSession>, scope: CoroutineScope) {
        val currentIds = current.map { it.id }.toSet()

        val droppedIds = sessionJobs.keys.toList().filter { it !in currentIds }
        for (id in droppedIds) {
            // AUDIT-2026-06 (A-G9-samples-desktop-ios-21): cancel every collector
            // launched for this session, not just the incoming-message job.
            sessionJobs.remove(id)?.forEach { it.cancel() }
            val removed = connectedSessions.firstOrNull { it.id == id }
            if (removed != null) {
                diagnostics.connection(
                    removed.id,
                    removed.peer.id.value,
                    "Closed",
                    removed.state.value.toString()
                )
                connectedSessions.remove(removed)
                targetedPeerIds.remove(removed.peer.id.value)
                appendSystemMessage("disconnected from ${removed.peer.name}")
                System.err.println("[p2pkit] room: session removed ${removed.peer.name.sanitizedForTerminal()}")
            }
        }

        for (session in current) {
            if (sessionJobs.containsKey(session.id)) continue
            diagnostics.connection(
                session.id,
                session.peer.id.value,
                session.state.value.toString()
            )
            connectedSessions.add(session)
            appendSystemMessage("connected to ${session.peer.name}")
            System.err.println("[p2pkit] room: session added ${session.peer.name.sanitizedForTerminal()}")
            val jobs = mutableListOf<Job>()
            jobs += scope.launch {
                session.incoming.collect { msg ->
                    System.err.println("[p2pkit] room: incoming from ${session.peer.name.sanitizedForTerminal()}")
                    // AUDIT-2026-06 (B-G9-samples-desktop-ios-18): keep a size-only
                    // summary of Binary payloads instead of retaining the bytes in
                    // history.
                    val storedBody = when (msg) {
                        is P2pMessage.Text -> msg.value
                        is P2pMessage.Binary -> "<binary ${msg.bytes.size}B>"
                    }
                    val payloadSize = when (msg) {
                        is P2pMessage.Text -> msg.value.toByteArray().size.toLong()
                        is P2pMessage.Binary -> msg.bytes.size.toLong()
                    }
                    diagnostics.recorder.record(
                        DiagnosticRecord(
                            peerId = session.peer.id.value,
                            connectionId = diagnostics.connectionIdFor(session.peer.id.value),
                            category = "metadata",
                            eventName = DiagnosticEventNames.METADATA_RECEIVED,
                            payloadSizeBytes = payloadSize,
                            direction = DiagnosticDirection.RECEIVED
                        )
                    )
                    diagnostics.recorder.record(
                        DiagnosticRecord(
                            peerId = session.peer.id.value,
                            connectionId = diagnostics.connectionIdFor(session.peer.id.value),
                            category = "metadata",
                            eventName = DiagnosticEventNames.METADATA_VALIDATED,
                            payloadSizeBytes = payloadSize,
                            direction = DiagnosticDirection.RECEIVED,
                            outcome = DiagnosticOutcome.SUCCESS,
                            details = mapOf("authenticated" to "true")
                        )
                    )
                    appendRoomMessage(
                        RoomMessage(
                            id = nextMessageId++,
                            senderPeerId = session.peer.id.value,
                            senderName = session.peer.name,
                            body = storedBody,
                            timestamp = System.currentTimeMillis(),
                            direction = RoomMessage.Direction.Incoming
                        )
                    )
                }
            }
            jobs += scope.launch {
                var previous: String? = null
                session.state.collect { st ->
                    System.err.println("[p2pkit] session ${session.peer.name.sanitizedForTerminal()} → $st")
                    diagnostics.connection(
                        session.id,
                        session.peer.id.value,
                        st.toString(),
                        previous
                    )
                    previous = st.toString()
                }
            }
            jobs += wireIncomingFiles(session, scope)
            sessionJobs[session.id] = jobs
        }
    }

    // AUDIT-2026-06 (B-G9-samples-desktop-ios-18): bound the timeline like every
    // other history in this sample (logTail, fileTransfers) — trim oldest first.
    private fun appendRoomMessage(message: RoomMessage) {
        roomMessages.add(message)
        while (
            roomMessages.size > ROOM_MESSAGE_CAPACITY ||
            roomMessages.sumOf { it.body.toByteArray().size } > ROOM_MESSAGE_BYTE_CAPACITY
        ) {
            roomMessages.removeAt(0)
        }
    }

    private fun appendSystemMessage(text: String) {
        appendRoomMessage(
            RoomMessage(
                id = nextMessageId++,
                senderPeerId = null,
                senderName = "(system)",
                body = text,
                timestamp = System.currentTimeMillis(),
                direction = RoomMessage.Direction.System
            )
        )
    }

    internal fun recordLog(level: String, message: String) {
        // AUDIT-2026-06 (A-G9-samples-desktop-ios-26): thread-safe handoff — the
        // SnapshotStateList is only touched by the channel consumer on appScope.
        logLines.trySend("$level  ${message.sanitizedForTerminal()}")
    }

    companion object {
        const val DEFAULT_APP_ID = "p2pkit-desktop-sample"
        const val LOG_TAIL_CAPACITY = 30
        const val FILE_TRANSFER_HISTORY_CAPACITY = 24

        // AUDIT-2026-06 (B-G9-samples-desktop-ios-18): timeline history cap.
        const val ROOM_MESSAGE_CAPACITY = 500
        const val ROOM_MESSAGE_BYTE_CAPACITY = 256 * 1024
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
    val sha256: String?,
    val transfer: P2pFileTransfer
)

data class IncomingFileOffer(
    val id: String,
    val name: String,
    val sizeBytes: Long,
    val peerName: String,
    val offer: P2pFileOffer
)

private fun pickFile(): File? {
    val dialog = FileDialog(null as Frame?, "Select file to send", FileDialog.LOAD)
    dialog.isVisible = true
    val name = dialog.file ?: return null
    val dir = dialog.directory ?: return null
    return File(dir, name)
}

// AUDIT-2026-06 (A-G9-samples-desktop-ios-24): a transfer is terminal once it can
// no longer make progress. Only terminal rows may be evicted from history, and
// only non-terminal rows show a Cancel button.
private fun FileTransferState.isTerminal(): Boolean = when (this) {
    is FileTransferState.Completed,
    is FileTransferState.Rejected,
    is FileTransferState.Cancelled,
    is FileTransferState.Failed -> true
    is FileTransferState.Offered,
    is FileTransferState.Accepted,
    is FileTransferState.Sending -> false
}

/**
 * AUDIT-2026-06 (A-G9-samples-desktop-ios-29): [runCatching] variant that rethrows
 * [CancellationException], so a coroutine cancelled mid-suspend-call (Stop / window
 * close) propagates cancellation promptly instead of logging a spurious failure
 * and completing normally.
 */
private inline fun <T> runCatchingCancellable(block: () -> T): Result<T> = try {
    Result.success(block())
} catch (e: CancellationException) {
    throw e
} catch (t: Throwable) {
    Result.failure(t)
}

// =====================================================================
// Shared UI tokens
// =====================================================================

// AUDIT-2026-06 (C-G9-samples-desktop-ios-29): single source of truth for spacing
// and panel shape so screens and cards stay visually consistent instead of
// drifting per call site.
private object Dimens {
    val ScreenPadding = 16.dp
    val SectionGap = 12.dp
    val ItemGap = 8.dp
    val LabelGap = 4.dp
    val LineGap = 2.dp
    val CardPadding = 10.dp
    val PanelPadding = 8.dp
    val PanelShape = RoundedCornerShape(8.dp)
}

// AUDIT-2026-06 (C-G9-samples-desktop-ios-22): one shared default pair for the
// reconnect preset — used by the radio preset AND as the blank-field fallback.
private const val DEFAULT_RECONNECT_MAX_ATTEMPTS = 5
private const val DEFAULT_RECONNECT_RETRY_DELAY_MS = 1_000L

// =====================================================================
// Sample-level types — identical shape to the Android sample
// =====================================================================

data class RoomMessage(
    val id: Long,
    val senderPeerId: String?,
    val senderName: String,
    /** Timeline text only; binary payload bytes never enter Compose state. */
    val body: String,
    val timestamp: Long,
    val direction: Direction,
    val target: SendTarget = SendTarget.All
) {
    enum class Direction { Incoming, Outgoing, System }

    val displayBody: String get() = body
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
        val safe = message.sanitizedForTerminal()
        System.err.println("[p2pkit] $safe")
        state.recordLog("I", safe)
    }
    override fun warn(message: String, throwable: Throwable?) {
        val rendered = (if (throwable != null) "$message (${throwable.message})" else message)
            .sanitizedForTerminal()
        System.err.println("[p2pkit WARN] $rendered")
        state.recordLog("W", rendered)
    }
    override fun error(message: String, throwable: Throwable?) {
        val rendered = (if (throwable != null) "$message (${throwable.message})" else message)
            .sanitizedForTerminal()
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
    val isStopping by state.isStopping.collectAsState()
    val cleanupPending by state.cleanupPending.collectAsState()
    val lifecycleError by state.lifecycleError.collectAsState()
    Column(
        // AUDIT-2026-06 (C-G9-samples-desktop-ios-29): same screen padding as RoomScreen.
        modifier = Modifier.fillMaxSize().padding(Dimens.ScreenPadding),
        verticalArrangement = Arrangement.spacedBy(Dimens.SectionGap)
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
        if (lifecycleError != null) {
            Text(
                text = lifecycleError!!,
                color = MaterialTheme.colorScheme.error,
                style = MaterialTheme.typography.bodySmall
            )
        }
        OutlinedTextField(
            value = state.deviceName,
            onValueChange = { state.deviceName = it },
            label = { Text("Device name") },
            singleLine = true,
            enabled = !isStarting && !isStopping,
            modifier = Modifier.fillMaxWidth()
        )
        OutlinedTextField(
            value = state.appIdInput,
            onValueChange = { state.appIdInput = it },
            label = { Text("App ID (must match on every device)") },
            singleLine = true,
            enabled = !isStarting && !isStopping,
            modifier = Modifier.fillMaxWidth()
        )
        Text(text = "Reconnect policy", style = MaterialTheme.typography.titleSmall)
        ReconnectChoicePicker(state)
        Button(
            onClick = state::start,
            enabled = state.deviceName.trim().isNotEmpty() &&
                state.appIdInput.trim().isNotEmpty() &&
                !isStarting && !isStopping,
            modifier = Modifier.fillMaxWidth()
        ) {
            Text(
                when {
                    isStopping -> "Stopping…"
                    isStarting -> "Starting…"
                    cleanupPending -> "Retry cleanup"
                    else -> "Start"
                }
            )
        }
    }
}

@Composable
private fun ReconnectChoicePicker(state: DesktopP2pState) {
    var maxAttemptsText by remember {
        mutableStateOf(
            (state.reconnectChoice as? ReconnectChoice.Enabled)?.maxAttempts?.toString()
                ?: DEFAULT_RECONNECT_MAX_ATTEMPTS.toString()
        )
    }
    var retryDelayText by remember {
        mutableStateOf(
            (state.reconnectChoice as? ReconnectChoice.Enabled)?.retryDelayMillis?.toString()
                ?: DEFAULT_RECONNECT_RETRY_DELAY_MS.toString()
        )
    }
    val choice = state.reconnectChoice
    val attemptsValid = (maxAttemptsText.toIntOrNull() ?: 0) >= 1
    val delayValid = retryDelayText.toLongOrNull() != null

    // AUDIT-2026-06 (C-G9-samples-desktop-ios-22): never commit a policy from
    // blank/invalid fields — keep the last valid policy and flag the field with
    // isError instead of silently coercing to Enabled(1, 0).
    fun commitIfValid() {
        val attempts = maxAttemptsText.toIntOrNull()?.takeIf { it >= 1 } ?: return
        val delay = retryDelayText.toLongOrNull()?.takeIf { it >= 0L } ?: return
        state.reconnectChoice = ReconnectChoice.Enabled(attempts, delay)
    }

    // AUDIT-2026-06 (D-G9-samples-desktop-ios-18): selectable rows with
    // Role.RadioButton inside a selectableGroup, so labels are clickable and
    // screen readers announce one named radio per row.
    Column(
        verticalArrangement = Arrangement.spacedBy(Dimens.LabelGap),
        modifier = Modifier.selectableGroup()
    ) {
        Row(
            verticalAlignment = Alignment.CenterVertically,
            modifier = Modifier.selectable(
                selected = choice is ReconnectChoice.Disabled,
                role = Role.RadioButton,
                onClick = { state.reconnectChoice = ReconnectChoice.Disabled }
            )
        ) {
            RadioButton(selected = choice is ReconnectChoice.Disabled, onClick = null)
            Text("Disabled")
        }
        Row(
            verticalAlignment = Alignment.CenterVertically,
            modifier = Modifier.selectable(
                selected = choice is ReconnectChoice.Enabled,
                role = Role.RadioButton,
                onClick = {
                    val attempts = maxAttemptsText.toIntOrNull()?.coerceAtLeast(1)
                        ?: DEFAULT_RECONNECT_MAX_ATTEMPTS
                    val delay = retryDelayText.toLongOrNull()?.coerceAtLeast(0L)
                        ?: DEFAULT_RECONNECT_RETRY_DELAY_MS
                    // Keep the fields in sync with what is actually committed.
                    maxAttemptsText = attempts.toString()
                    retryDelayText = delay.toString()
                    state.reconnectChoice = ReconnectChoice.Enabled(attempts, delay)
                }
            )
        ) {
            RadioButton(selected = choice is ReconnectChoice.Enabled, onClick = null)
            Text("Enabled")
        }
        if (choice is ReconnectChoice.Enabled) {
            Row(
                horizontalArrangement = Arrangement.spacedBy(Dimens.ItemGap),
                verticalAlignment = Alignment.CenterVertically
            ) {
                OutlinedTextField(
                    value = maxAttemptsText,
                    onValueChange = { txt ->
                        maxAttemptsText = txt.filter { it.isDigit() }.take(4)
                        commitIfValid()
                    },
                    label = { Text("maxAttempts") },
                    isError = !attemptsValid,
                    supportingText = if (!attemptsValid) {
                        { Text("must be ≥ 1 — last valid value (${choice.maxAttempts}) still applies") }
                    } else null,
                    singleLine = true,
                    modifier = Modifier.weight(1f)
                )
                OutlinedTextField(
                    value = retryDelayText,
                    onValueChange = { txt ->
                        retryDelayText = txt.filter { it.isDigit() }.take(6)
                        commitIfValid()
                    },
                    label = { Text("retryDelayMillis") },
                    isError = !delayValid,
                    supportingText = if (!delayValid) {
                        { Text("must be ≥ 0 — last valid value (${choice.retryDelayMillis}) still applies") }
                    } else null,
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
    val lifecycleError by state.lifecycleError.collectAsState()
    var draft by remember { mutableStateOf("") }

    Row(modifier = Modifier.fillMaxSize().padding(Dimens.ScreenPadding)) {
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
            if (lifecycleError != null) {
                Text(
                    text = lifecycleError!!,
                    color = MaterialTheme.colorScheme.error,
                    style = MaterialTheme.typography.bodySmall
                )
            }
            HorizontalDivider(modifier = Modifier.padding(vertical = Dimens.ItemGap))

            Text(
                text = "Discovered peers (${peers.size})",
                style = MaterialTheme.typography.titleSmall
            )
            Spacer(Modifier.height(Dimens.LabelGap))
            if (peers.isEmpty()) {
                // AUDIT-2026-06 (D-G9-samples-desktop-ios-12): don't claim an
                // active search while discovery is toggled off.
                Text(
                    text = if (discovering) {
                        "Searching… open another sample on the same Wi-Fi."
                    } else {
                        "Discovery is off — toggle Discover to search for peers."
                    },
                    style = MaterialTheme.typography.bodySmall
                )
            } else {
                LazyColumn(
                    modifier = Modifier.fillMaxWidth().height(220.dp),
                    verticalArrangement = Arrangement.spacedBy(Dimens.ItemGap)
                ) {
                    items(peers, key = { it.id.value }) { peer ->
                        // AUDIT-2026-06 (D-G9-samples-desktop-ios-09): pass the live
                        // session state so the card distinguishes Connected from
                        // Connecting/Handshaking/Reconnecting.
                        val session = state.connectedSessions
                            .firstOrNull { it.peer.id.value == peer.id.value }
                        val sessionState = if (session != null) session.state.collectAsState().value else null
                        PeerCard(
                            peer = peer,
                            sessionState = sessionState,
                            isConnecting = state.pendingConnectPeerIds.contains(peer.id.value),
                            onConnect = { state.connect(peer) }
                        )
                    }
                }
            }

            Spacer(Modifier.height(Dimens.SectionGap))
            ManualPeerSection(
                manualInfo = manualInfo,
                isManualDialing = isManualDialing,
                onConnectManual = state::connectManual
            )

            Spacer(Modifier.height(Dimens.SectionGap))
            Text(
                text = "Logs (last ${state.logTail.size})",
                style = MaterialTheme.typography.labelMedium
            )
            Spacer(Modifier.height(Dimens.LabelGap))
            Box(
                modifier = Modifier
                    .fillMaxWidth()
                    .height(200.dp)
                    .clip(Dimens.PanelShape)
                    .background(MaterialTheme.colorScheme.surfaceVariant)
                    .padding(Dimens.PanelPadding)
            ) {
                // AUDIT-2026-06 (D-G9-samples-desktop-ios-10): pin the log strip
                // to the newest line on append.
                val logListState = rememberLazyListState()
                val logSnapshot = state.logTail.toList()
                LaunchedEffect(logSnapshot.size, logSnapshot.lastOrNull()) {
                    if (logSnapshot.isNotEmpty()) {
                        logListState.scrollToItem(logSnapshot.size - 1)
                    }
                }
                LazyColumn(state = logListState) {
                    items(logSnapshot) { line ->
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

        Spacer(Modifier.width(Dimens.ScreenPadding))

        // ---- Right column: room chips + timeline + input ----
        Column(modifier = Modifier.fillMaxSize()) {
            val connected = state.connectedSessions.toList()
            // AUDIT-2026-06 (A-G9-samples-desktop-ios-27): collect each session's
            // state exactly once, keyed by session id, instead of calling
            // collectAsState inside a short-circuiting any{} — subscription count
            // and positions stay stable across recompositions.
            val sessionStates = connected.map { session ->
                key(session.id) { session.state.collectAsState().value }
            }
            // AUDIT-2026-06 (D-G9-samples-desktop-ios-09): only sessions actually
            // in ConnectionState.Connected count as connected.
            val connectedCount = sessionStates.count { it == ConnectionState.Connected }
            if (connected.isNotEmpty()) {
                Text(
                    text = "Room ($connectedCount of ${connected.size} connected)",
                    style = MaterialTheme.typography.titleMedium
                )
                Spacer(Modifier.height(Dimens.LabelGap))
                LazyRow(horizontalArrangement = Arrangement.spacedBy(Dimens.ItemGap)) {
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

            if (state.pendingFileOffers.isNotEmpty()) {
                Spacer(Modifier.height(Dimens.SectionGap))
                Text(
                    text = "Incoming file offers (${state.pendingFileOffers.size})",
                    style = MaterialTheme.typography.titleSmall
                )
                Spacer(Modifier.height(Dimens.LabelGap))
                Column(verticalArrangement = Arrangement.spacedBy(Dimens.LabelGap)) {
                    state.pendingFileOffers.toList().forEach { offer ->
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Column(modifier = Modifier.weight(1f)) {
                                Text("${offer.name} from ${offer.peerName}", maxLines = 1, overflow = TextOverflow.Ellipsis)
                                Text("${offer.sizeBytes} bytes — consent required", style = MaterialTheme.typography.labelSmall)
                            }
                            TextButton(onClick = { state.acceptFileOffer(offer.id) }) { Text("Accept") }
                            TextButton(onClick = { state.rejectFileOffer(offer.id) }) { Text("Reject") }
                        }
                    }
                }
            }

            if (state.fileTransfers.isNotEmpty()) {
                Spacer(Modifier.height(Dimens.SectionGap))
                Text(
                    text = "File transfers (${state.fileTransfers.size})",
                    style = MaterialTheme.typography.titleSmall
                )
                Spacer(Modifier.height(Dimens.LabelGap))
                LazyColumn(
                    modifier = Modifier.fillMaxWidth().height(140.dp),
                    verticalArrangement = Arrangement.spacedBy(Dimens.LabelGap)
                ) {
                    items(state.fileTransfers.toList(), key = { it.id }) { row ->
                        FileTransferRowView(row = row, onCancel = { state.cancelFileTransfer(row.id) })
                    }
                }
            }

            Spacer(Modifier.height(Dimens.SectionGap))

            Text(text = "Timeline", style = MaterialTheme.typography.titleSmall)
            Spacer(Modifier.height(Dimens.LabelGap))
            // AUDIT-2026-06 (D-G9-samples-desktop-ios-10): auto-scroll to the
            // newest entry on every append (message ids are monotonic).
            val timelineListState = rememberLazyListState()
            LaunchedEffect(state.roomMessages.lastOrNull()?.id) {
                if (state.roomMessages.isNotEmpty()) {
                    timelineListState.animateScrollToItem(state.roomMessages.size - 1)
                }
            }
            LazyColumn(
                state = timelineListState,
                modifier = Modifier
                    .fillMaxWidth()
                    .height(380.dp)
                    .clip(Dimens.PanelShape)
                    // AUDIT-2026-06 (C-G9-samples-desktop-ios-29): same panel role
                    // as the log strip (surface blended into the window background).
                    .background(MaterialTheme.colorScheme.surfaceVariant)
                    .padding(Dimens.PanelPadding),
                verticalArrangement = Arrangement.spacedBy(Dimens.LineGap)
            ) {
                items(state.roomMessages.toList(), key = { it.id }) { line ->
                    RoomLine(line)
                }
            }

            Spacer(Modifier.height(Dimens.ItemGap))

            OutlinedTextField(
                value = draft,
                onValueChange = { draft = it },
                label = { Text("Message") },
                singleLine = true,
                modifier = Modifier.fillMaxWidth()
            )
            Spacer(Modifier.height(Dimens.ItemGap))
            val targetCount = state.targetedPeerIds.size
            val sendLabel = when {
                connectedCount == 0 -> "No peers connected"
                targetCount == 0 -> "Broadcast ($connectedCount)"
                else -> "Send to $targetCount"
            }
            // Only enable Send when at least one session is actually in
            // ConnectionState.Connected — Connecting/Reconnecting peers
            // would silently drop the send at the SDK level.
            // AUDIT-2026-06 (A-G9-samples-desktop-ios-27): derived from the stable
            // per-session snapshots collected above, not collectAsState-in-any{}.
            val hasConnectedSession = connectedCount > 0
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
    Column(verticalArrangement = Arrangement.spacedBy(Dimens.LineGap)) {
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
            horizontalArrangement = Arrangement.spacedBy(Dimens.SectionGap),
            verticalAlignment = Alignment.CenterVertically
        ) {
            LabelledSwitch(label = "Advertise", checked = advertising, onToggle = onToggleAdvertising)
            LabelledSwitch(label = "Discover", checked = discovering, onToggle = onToggleDiscovery)
            LabelledSwitch(label = "Auto-mesh", checked = autoMesh, onToggle = onToggleAutoMesh)
        }
    }
}

/**
 * AUDIT-2026-06 (D-G9-samples-desktop-ios-18): label + switch merged into one
 * toggleable row (Role.Switch), so the label is clickable and screen readers
 * announce a single named switch.
 */
@Composable
private fun LabelledSwitch(label: String, checked: Boolean, onToggle: () -> Unit) {
    Row(
        verticalAlignment = Alignment.CenterVertically,
        modifier = Modifier.toggleable(
            value = checked,
            role = Role.Switch,
            onValueChange = { onToggle() }
        )
    ) {
        Text(label, style = MaterialTheme.typography.bodySmall)
        Spacer(Modifier.width(Dimens.LabelGap))
        Switch(checked = checked, onCheckedChange = null)
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
    val isActive = !state.isTerminal()
    val arrow = if (row.direction == FileTransferDirection.Outgoing) "↑" else "↓"
    val sizeKb = row.sizeBytes / 1024
    val sentKb = row.bytesTransferred / 1024
    val pct = if (row.sizeBytes > 0) ((row.bytesTransferred * 100) / row.sizeBytes).toInt() else 0
    Card(modifier = Modifier.fillMaxWidth()) {
        // AUDIT-2026-06 (C-G9-samples-desktop-ios-29): same card padding as PeerCard.
        Column(modifier = Modifier.padding(Dimens.CardPadding)) {
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
            if (row.sha256 != null) {
                Text(
                    text = "sha256 ${row.sha256}",
                    style = MaterialTheme.typography.labelSmall,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis
                )
            }
            if (isActive) {
                Spacer(Modifier.height(Dimens.LabelGap))
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
    Spacer(Modifier.height(Dimens.LabelGap))
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
    Spacer(Modifier.height(Dimens.LabelGap))
    var input by remember { mutableStateOf("") }
    Row(verticalAlignment = Alignment.CenterVertically) {
        OutlinedTextField(
            value = input,
            onValueChange = { input = it },
            label = { Text("Connect host:port p2f1-fingerprint") },
            singleLine = true,
            enabled = !isManualDialing,
            modifier = Modifier.weight(1f).padding(end = Dimens.ItemGap)
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
    sessionState: ConnectionState?,
    isConnecting: Boolean,
    onConnect: () -> Unit
) {
    Card(modifier = Modifier.fillMaxWidth()) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(Dimens.CardPadding),
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
            // AUDIT-2026-06 (D-G9-samples-desktop-ios-09): "Connected" only when the
            // session really is Connected; other live states show their actual name
            // instead of hiding the truth behind a blanket "Connected".
            when {
                sessionState == ConnectionState.Connected ->
                    Text(text = "Connected", style = MaterialTheme.typography.labelSmall)
                sessionState != null ->
                    Text(text = sessionState.name.lowercase(), style = MaterialTheme.typography.labelSmall)
                isConnecting ->
                    Text(text = "Connecting…", style = MaterialTheme.typography.labelSmall)
                else -> TextButton(onClick = onConnect) { Text("Connect") }
            }
        }
    }
}
