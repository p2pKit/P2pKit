package dev.p2pkit.sample.android

import android.app.Application
import android.net.Uri
import android.os.Build
import android.os.storage.StorageManager
import android.util.Log
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.compose.runtime.snapshots.SnapshotStateList
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import dev.p2pkit.core.AndroidNetworkPathObserver
import dev.p2pkit.core.AppId
import dev.p2pkit.core.ConnectionState
import dev.p2pkit.core.NetworkPathStatus
import dev.p2pkit.core.P2pKit
import dev.p2pkit.core.P2pLogger
import dev.p2pkit.core.protocol.FrameTrace
import dev.p2pkit.core.protocol.FrameTraceLease
import dev.p2pkit.core.P2pMessage
import dev.p2pkit.core.P2pSession
import dev.p2pkit.core.P2pState
import dev.p2pkit.core.Peer
import dev.p2pkit.core.ExperimentalP2pApi
import dev.p2pkit.core.ExplicitSecurityRisk
import dev.p2pkit.core.PeerAuthorizationPolicy
import dev.p2pkit.core.ReconnectPolicy
import dev.p2pkit.core.SecurityMode
import dev.p2pkit.core.permission.P2pPermission
import dev.p2pkit.core.provisioning.JoinNetworkResult
import dev.p2pkit.core.provisioning.LocalNetworkConfig
import dev.p2pkit.core.provisioning.LocalNetworkResult
import dev.p2pkit.core.provisioning.WifiCredentials
import dev.p2pkit.core.provisioning.WifiPassword
import dev.p2pkit.core.provisioning.WifiSecurityType
import dev.p2pkit.core.transfer.FileTransferState
import dev.p2pkit.core.transfer.P2pFileOffer
import dev.p2pkit.core.transfer.P2pFileTransfer
import dev.p2pkit.core.transfer.sendFile
import dev.p2pkit.provisioning.android.AndroidP2pPermissionManager
import dev.p2pkit.provisioning.android.android
import dev.p2pkit.sample.diagnostics.DiagnosticEventNames
import dev.p2pkit.sample.diagnostics.DiagnosticDirection
import dev.p2pkit.sample.diagnostics.DiagnosticFilter
import dev.p2pkit.sample.diagnostics.DiagnosticOutcome
import dev.p2pkit.sample.diagnostics.DiagnosticRecord
import dev.p2pkit.sample.diagnostics.DiagnosticRecorder
import dev.p2pkit.sample.diagnostics.DiagnosticSeverity
import dev.p2pkit.sample.diagnostics.StructuredFrameTrace
import dev.p2pkit.sample.diagnostics.StructuredSdkLogger
import dev.p2pkit.sample.kmp.createP2pKit
import dev.p2pkit.sample.kmp.runDiscoverAndGreet
import dev.p2pkit.transport.lan.AndroidLanDiag
import dev.p2pkit.transport.lan.lan
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.NonCancellable
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancelAndJoin
import kotlinx.coroutines.cancel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext
import java.io.File

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
@OptIn(ExplicitSecurityRisk::class)
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

    /** True for the brief duration of [start] (setting up flow collectors). */
    private val _isStarting = MutableStateFlow(false)
    val isStarting: StateFlow<Boolean> = _isStarting.asStateFlow()

    /** True from [stop] until the in-flight kit.stop() coroutine returns. */
    private val _isStopping = MutableStateFlow(false)
    val isStopping: StateFlow<Boolean> = _isStopping.asStateFlow()

    private val _kmpSmokeBusy = MutableStateFlow(false)
    val kmpSmokeBusy: StateFlow<Boolean> = _kmpSmokeBusy.asStateFlow()

    private val _kmpSmokeResult = MutableStateFlow<String?>(null)
    val kmpSmokeResult: StateFlow<String?> = _kmpSmokeResult.asStateFlow()

    /**
     * True while a [startHotspot] / [joinHotspot] / [stopHotspot] call is
     * in-flight, so the UI can disable the relevant buttons and prevent the
     * user from spawning parallel provisioning attempts via rapid taps.
     */
    private val _provisioningBusy = MutableStateFlow(false)
    val provisioningBusy: StateFlow<Boolean> = _provisioningBusy.asStateFlow()

    /**
     * Mirror of [P2pKit.networkPathStatus]. Surfaced in the room screen as
     * a colored chip so manual hardware testing can see "online / offline /
     * recovering" while toggling Wi-Fi during a §4 recovery test.
     *
     * Defaults to [NetworkPathStatus.Unknown] before the kit is running.
     * The collector is launched inside [start] so it tears down with the
     * run scope.
     */
    private val _networkPathStatus = MutableStateFlow<NetworkPathStatus>(NetworkPathStatus.Unknown)
    val networkPathStatus: StateFlow<NetworkPathStatus> = _networkPathStatus.asStateFlow()

    /**
     * Peers whose [connect] coroutine is in-flight. Used to disable their
     * Connect button and surface "Connecting…" while waiting on the SDK.
     */
    val pendingConnectPeerIds: SnapshotStateList<String> = mutableStateListOf()

    private val _kitState = MutableStateFlow<P2pState>(P2pState.Idle)
    val kitState: StateFlow<P2pState> = _kitState.asStateFlow()

    /** User intent; preserved while the default background policy pauses the feature. */
    private val _advertising = MutableStateFlow(false)
    val advertising: StateFlow<Boolean> = _advertising.asStateFlow()

    /** User intent; preserved while the default background policy pauses the feature. */
    private val _discovering = MutableStateFlow(false)
    val discovering: StateFlow<Boolean> = _discovering.asStateFlow()

    /**
     * AUDIT-2026-06: A-G8-samples-android-19 — "is at least one session
     * Connected" derived here once (updated from the per-session state
     * collectors) instead of `collectAsState()` inside a short-circuiting
     * `any {}` in the composable, which churned subscriptions.
     */
    private val _hasConnectedSession = MutableStateFlow(false)
    val hasConnectedSession: StateFlow<Boolean> = _hasConnectedSession.asStateFlow()

    /**
     * Auto-mesh: when ON, the sample auto-connects to every newly discovered
     * peer in the room. The SDK itself arbitrates simultaneous-open (the
     * smaller-peer-id side's outgoing connection wins, see the spec), so
     * duplicate sessions are not a correctness risk — the lexicographic
     * guard below merely avoids redundant dials and UI churn by having
     * exactly one side per pair initiate; the other accepts the incoming
     * session.
     * (AUDIT-2026-06: A-G8-samples-android-09 — comment previously claimed
     * the SDK does not arbitrate.)
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
    val fileTransfers: SnapshotStateList<FileTransferRow> = mutableStateListOf()
    /** Incoming files remain pending until the user explicitly accepts/rejects them. */
    val pendingFileOffers: SnapshotStateList<IncomingFileOffer> = mutableStateListOf()

    // --- diagnostics ------------------------------------------------------

    /** Last N lines from the logger; surfaced under the room timeline. */
    val logTail: SnapshotStateList<String> = mutableStateListOf()

    private val _diagnosticRevision = MutableStateFlow(0L)
    val diagnosticRevision: StateFlow<Long> = _diagnosticRevision.asStateFlow()
    var diagnosticTestId: String by mutableStateOf("PS-T04")
        private set
    var diagnosticRole: String by mutableStateOf("both")
        private set
    private val diagnostics = AndroidDiagnosticHarness(
        getApplication<Application>().applicationContext
    ) {
        _diagnosticRevision.update { it + 1L }
    }
    val diagnosticRecorder: DiagnosticRecorder get() = diagnostics.recorder

    // --- hotspot host (v0.2.1 task 11) ------------------------------------

    /**
     * Latest hotspot-host result. `null` when no host attempt has been made.
     * `LocalNetworkResult.Started` or `StartedWithoutCredentials` while the
     * hotspot is up; `Failed` when start failed or the system stopped it.
     */
    private val _hotspotResult = MutableStateFlow<LocalNetworkResult?>(null)
    val hotspotResult: StateFlow<LocalNetworkResult?> = _hotspotResult.asStateFlow()

    /** Missing perms reported by [AndroidP2pPermissionManager]; sample requests them. */
    private val _missingPermissions = MutableStateFlow<List<P2pPermission>>(emptyList())
    val missingPermissions: StateFlow<List<P2pPermission>> = _missingPermissions.asStateFlow()

    /**
     * Latest hotspot-join result. `null` when no join attempt has been
     * made. `Joined` while the device is connected to a peer's hotspot;
     * `Failed` when the user declined, the network couldn't be reached,
     * or the system released the join.
     */
    private val _joinResult = MutableStateFlow<JoinNetworkResult?>(null)
    val joinResult: StateFlow<JoinNetworkResult?> = _joinResult.asStateFlow()

    // --- internals --------------------------------------------------------

    private var kit: P2pKit? = null
    private var runScope: CoroutineScope? = null
    private val cleanupScope = CoroutineScope(Dispatchers.Default + SupervisorJob())
    private val advertisingToggleMutex = Mutex()
    private val discoveryToggleMutex = Mutex()
    private val foregroundRestoreCoordinator = ForegroundRestoreCoordinator()

    @Volatile
    private var foregroundRestoreJob: Job? = null
    private val connectionIds: MutableMap<String, String> = mutableMapOf()
    private var frameTraceLease: FrameTraceLease? = null

    /**
     * AUDIT-2026-06: A-G8-samples-android-13 — all three per-session
     * collectors (incoming messages, state log, incoming files) are tracked
     * per session id so a dropped session cancels every collector, not just
     * the message one.
     */
    private val sessionJobs: MutableMap<String, List<Job>> = mutableMapOf()

    /**
     * AUDIT-2026-06: ARCH-samples-18 — the in-flight teardown job launched by
     * [stop], so [onCleared] can wait for it instead of cancelling
     * [cleanupScope] underneath it.
     */
    private var pendingStopJob: Job? = null

    private var nextMessageId: Long = 1L

    // --- intents from the UI ----------------------------------------------

    fun updateDeviceName(name: String) {
        deviceName = name
    }

    fun updateDiagnosticTestId(value: String) {
        diagnosticTestId = value
            .filter { it.isLetterOrDigit() || it == '-' || it == '_' }
            .uppercase()
            .take(64)
    }

    fun updateDiagnosticRole(value: String) {
        diagnosticRole = value
            .filter { it.isLetterOrDigit() || it == '-' || it == '_' }
            .lowercase()
            .take(24)
    }

    fun beginDiagnosticSession(requestedSessionId: String? = null) {
        runCatching {
            diagnostics.beginSession(diagnosticTestId, diagnosticRole, requestedSessionId)
        }.onSuccess { id ->
            diagnostics.setLocalPeerId(newKitLocalPeerId().takeIf { it.isNotBlank() })
            connectionIds.clear()
            connectedSessions.forEach { session ->
                val correlation = diagnostics.registerConnection(session.id, session.peer.id.value)
                correlation?.let { connectionIds[session.id] = it.connectionId }
                recordDiagnostic(
                    DiagnosticRecord(
                        peerId = session.peer.id.value,
                        connectionId = correlation?.connectionId,
                        category = "connection",
                        eventName = DiagnosticEventNames.CONNECTION_STATE_CHANGED,
                        currentState = session.state.value.toString(),
                        details = mapOf("sessionSnapshot" to "true")
                    )
                )
            }
            appendSystemMessage(
                "diagnostics active: test=${diagnosticRecorder.activeTestId} " +
                    "session=$id role=${diagnosticRecorder.activeRole}"
            )
        }.onFailure {
            appendSystemMessage("diagnostics could not start: ${it.message ?: it::class.simpleName}")
        }
    }

    fun completeDiagnostic(outcome: DiagnosticOutcome) {
        diagnostics.complete(outcome, "operator selected ${outcome.name}", outcome.name)
        appendSystemMessage("diagnostics completed: ${outcome.name}")
    }

    fun exportDiagnosticEvidence(): File? =
        runCatching { diagnostics.export() }
            .onSuccess { appendSystemMessage("evidence exported: ${it.absolutePath}") }
            .onFailure { appendSystemMessage("evidence export failed: ${it.message ?: it::class.simpleName}") }
            .getOrNull()

    fun clearCurrentDiagnosticSession(): Int = diagnostics.clearCurrentSession()

    fun diagnosticEvents(filter: DiagnosticFilter = DiagnosticFilter()) =
        diagnosticRecorder.snapshot(filter)

    fun diagnosticSummary() = diagnosticRecorder.summary(
        selectedTransferId = diagnosticRecorder.snapshot().lastOrNull { it.transferId != null }?.transferId
    )

    internal fun recordDiagnostic(record: DiagnosticRecord) {
        diagnosticRecorder.record(record)
    }

    fun updateReconnectChoice(choice: ReconnectChoice) {
        if (_isRunning.value) return  // locked at kit construction
        reconnectChoice = choice
    }

    /** Physical-device consumer smoke for PS-T09; unavailable while the room kit owns LAN. */
    fun runKmpConsumerSmoke() {
        if (_isRunning.value || _isStarting.value || _isStopping.value || _kmpSmokeBusy.value) return
        _kmpSmokeBusy.value = true
        _kmpSmokeResult.value = "Running KMP advertise/discover/connect/send/close/stop…"
        viewModelScope.launch {
            val result = runCatchingNonCancel {
                val smoke = createP2pKit(APP_ID, "Android-KMP-${Build.MODEL.take(16)}")
                runDiscoverAndGreet(
                    p2p = smoke,
                    greetingFrom = "Android KMP consumer",
                    discoveryTimeoutMillis = 10_000
                )
            }
            _kmpSmokeResult.value = result.fold(
                onSuccess = { "KMP consumer: $it" },
                onFailure = { "KMP consumer failed: ${it.message ?: it::class.simpleName}" }
            )
            _kmpSmokeBusy.value = false
        }
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
        // AUDIT-2026-06: D-G8-samples-android-02 — also refuse while the
        // previous kit is still stopping, or two kits would overlap (duplicate
        // mDNS advertisements + two TCP listeners).
        if (_isRunning.value || _isStarting.value || _isStopping.value) return  // idempotent + re-entry safe
        val trimmedName = deviceName.trim()
        if (trimmedName.isEmpty()) {
            Log.w(LOG_TAG, "start aborted: deviceName is blank")
            return
        }
        deviceName = trimmedName
        _isStarting.value = true
        val choice = reconnectChoice
        val ctx = getApplication<Application>().applicationContext
        if (diagnosticRecorder.activeSessionId == "session-unassigned") {
            beginDiagnosticSession()
        }
        recordDiagnostic(
            DiagnosticRecord(
                category = "application",
                eventName = DiagnosticEventNames.TEST_MODE_ACTIVATED,
                currentState = "starting"
            )
        )
        // Diagnostic frame-type trace (Issue #2/#3): route decoded frame lines
        // to logcat so they sit alongside the transport's bounded P2pKitLAN
        // lines. Library lifecycle diagnostics are default-off; this official
        // diagnostic harness opts in explicitly.
        AndroidLanDiag.enabled = true
        AndroidLanDiag.retainHistory = true
        frameTraceLease?.release()
        frameTraceLease = FrameTrace.installSink(enabled = true) {
            Log.d("P2pKitFrame", it)
            StructuredFrameTrace.record(
                recorder = diagnosticRecorder,
                line = it,
                correlationForTransfer = diagnostics::correlationForTransfer
            )
        }
        val newKit = try {
            P2pKit.create {
                appId = AppId(APP_ID)
                this.deviceName = this@P2pKitViewModel.deviceName
                security {
                    mode = SecurityMode.AuthenticatedV2(
                        PeerAuthorizationPolicy.AcceptAnyAuthenticatedSameApp
                    )
                }
                transports { lan(ctx) }
                // Sample-only tuning. SDK defaults are pingIntervalMillis=10_000 /
                // timeoutMillis=30_000 — appropriate for general-purpose / battery-
                // conscious apps. The values below are tuned for interactive /
                // real-time use (e.g. local-multiplayer games) where ~6s
                // disconnect detection matters more than the ~24s of extra
                // background pings per session. Apps consuming this library can
                // pick their own values via the same `keepAlive { ... }` block.
                keepAlive {
                    pingIntervalMillis = 2_000
                    timeoutMillis = 6_000
                }
                networkProvisioning {
                    enableLocalHotspot = true
                    enableManualIpFallback = true
                    android(ctx)
                }
                lifecycle {
                    reconnectPolicy = when (choice) {
                        ReconnectChoice.Disabled -> ReconnectPolicy.Disabled
                        is ReconnectChoice.Enabled -> ReconnectPolicy.Enabled(
                            maxAttempts = choice.maxAttempts,
                            retryDelayMillis = choice.retryDelayMillis
                        )
                    }
                    // §4 wire-up. Without this the Android sample would fall
                    // back to NoOpNetworkPathObserver and miss Wi-Fi off/on
                    // events — the kit would still recover via PING timeout
                    // but several seconds slower. ApplicationContext is safe;
                    // AndroidNetworkPathObserver does not hold onto the
                    // calling Activity.
                    networkPathObserver = AndroidNetworkPathObserver(ctx)
                }
                logger = StructuredSdkLogger(
                    recorder = diagnosticRecorder,
                    delegate = TailLogger(this@P2pKitViewModel)
                )
            }
        } catch (t: Throwable) {
            frameTraceLease?.release()
            frameTraceLease = null
            _isStarting.value = false
            Log.e(LOG_TAG, "kit create failed", t)
            appendSystemMessage("start failed: ${t.message ?: t::class.simpleName}")
            return
        }
        kit = newKit
        refreshMissingPermissions()
        _localPeerId.value = newKit.localPeerId.value
        diagnostics.setLocalPeerId(newKit.localPeerId.value)
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
            AndroidLanDiag.events.collect { line ->
                recordDiagnostic(
                    DiagnosticRecord(
                        category = "transport",
                        eventName = DiagnosticEventNames.TRANSPORT_LOG,
                        severity = if ("WARN" in line || "error" in line.lowercase()) {
                            DiagnosticSeverity.WARNING
                        } else {
                            DiagnosticSeverity.DEBUG
                        },
                        details = mapOf("line" to line)
                    )
                )
            }
        }
        scope.launch {
            var previous: Set<String> = emptySet()
            newKit.peers.collect { current ->
                val currentIds = current.map { it.id.value }.toSet()
                current.filter { it.id.value !in previous }.forEach { peer ->
                    recordDiagnostic(
                        DiagnosticRecord(
                            peerId = peer.id.value,
                            category = "discovery",
                            eventName = DiagnosticEventNames.PEER_DISCOVERED,
                            details = mapOf("platform" to peer.platform.toString())
                        )
                    )
                }
                previous.filter { it !in currentIds }.forEach { peerId ->
                    recordDiagnostic(
                        DiagnosticRecord(
                            peerId = peerId,
                            category = "discovery",
                            eventName = DiagnosticEventNames.PEER_LOST
                        )
                    )
                }
                previous = currentIds
                _peers.value = current
            }
        }
        scope.launch {
            var previous: NetworkPathStatus? = null
            newKit.networkPathStatus.collect { current ->
                recordDiagnostic(
                    DiagnosticRecord(
                        category = "network",
                        eventName = DiagnosticEventNames.NETWORK_PATH_CHANGED,
                        previousState = previous?.toString(),
                        currentState = current.toString(),
                        details = mapOf("observer" to "AndroidNetworkPathObserver")
                    )
                )
                previous = current
                _networkPathStatus.value = current
            }
        }
        // Single source of truth for "which peers do we have a session with".
        scope.launch {
            newKit.sessions.collect { current ->
                reconcileSessions(current, scope)
            }
        }
        scope.launch {
            try {
                newKit.startAdvertising()
                _advertising.value = true
                recordDiagnostic(
                    DiagnosticRecord(
                        category = "discovery",
                        eventName = DiagnosticEventNames.DISCOVERY_STARTED,
                        currentState = "advertising"
                    )
                )
                newKit.startDiscovery()
                _discovering.value = true
                recordDiagnostic(
                    DiagnosticRecord(
                        category = "discovery",
                        eventName = DiagnosticEventNames.DISCOVERY_STARTED,
                        currentState = "discovering"
                    )
                )
                _isRunning.value = true
            } catch (cancelled: CancellationException) {
                throw cancelled
            } catch (t: Throwable) {
                _advertising.value = false
                _discovering.value = false
                Log.e(LOG_TAG, "kit startup failed", t)
                appendSystemMessage("start failed: ${t.message ?: t::class.simpleName}")
                runCatchingNonCancel { newKit.stop() }
                if (kit === newKit) kit = null
                runScope = null
                _kitState.value = P2pState.Stopped
                cancel()
            } finally {
                _isStarting.value = false
            }
        }

        // Auto-mesh: react to peer/session changes and connect to anyone we
        // should initiate toward (lexicographic tie-break by peer id).
        // Combining with [autoMesh] means toggling the flag back ON
        // re-evaluates immediately.
        //
        // AUDIT-2026-06: A-G8-samples-android-08 — kit.sessions is a combine
        // input (not read as a snapshot inside collect) so a session dropping
        // while the peer stays discovered re-fires mesh evaluation and the
        // initiator re-dials; previously only peer churn re-triggered it.
        //
        // We route through [connect] (not `newKit.connect` directly) so the
        // auto-mesh path shares [pendingConnectPeerIds] with the user-tap
        // path. Otherwise a user tap during the brief window where auto-mesh
        // has called `kit.connect` but the session hasn't shown up in
        // `connectedSessions` yet would slip past both guards — they'd then
        // race onto the SDK's dedup mutex and the UI would briefly show two
        // "Connecting…" states for the same peer.
        scope.launch {
            combine(_autoMesh, newKit.peers, newKit.sessions) { enabled, peers, sessions ->
                Triple(enabled, peers, sessions)
            }.collect { (enabled, peers, sessions) ->
                if (!enabled || !_isRunning.value) return@collect
                val myId = newKit.localPeerId.value
                val sessionPeerIds = sessions.map { it.peer.id.value }.toSet()
                for (peer in peers) {
                    if (peer.id.value in sessionPeerIds) continue
                    if (pendingConnectPeerIds.contains(peer.id.value)) continue
                    if (myId < peer.id.value) {
                        Log.i(LOG_TAG, "auto-mesh: initiating connect to ${peer.name}")
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
        recordDiagnostic(
            DiagnosticRecord(
                peerId = peerId,
                category = "connection",
                eventName = DiagnosticEventNames.CONNECTION_ATTEMPTED,
                currentState = "Connecting"
            )
        )
        pendingConnectPeerIds.add(peerId)
        scope.launch {
            try {
                runCatchingNonCancel { currentKit.connect(peer) }.onFailure {
                    recordDiagnostic(
                        DiagnosticRecord(
                            peerId = peerId,
                            category = "connection",
                            eventName = DiagnosticEventNames.CONNECTION_AUTHENTICATION_FAILED,
                            severity = DiagnosticSeverity.ERROR,
                            errorCode = it::class.simpleName?.uppercase(),
                            errorDescription = it.message,
                            outcome = DiagnosticOutcome.FAILURE
                        )
                    )
                    Log.w(LOG_TAG, "connect to ${peer.name} failed", it)
                    appendSystemMessage("failed to connect to ${peer.name}: ${it.message ?: it::class.simpleName}")
                }
            } finally {
                pendingConnectPeerIds.remove(peerId)
            }
        }
    }

    /**
     * Refresh missing-permission state. Call this after the user grants or
     * denies a permission so the UI updates.
     */
    fun refreshMissingPermissions() {
        val scope = runScope ?: viewModelScope
        scope.launch {
            val pm = AndroidP2pPermissionManager(getApplication<Application>().applicationContext)
            runCatchingNonCancel { pm.missingPermissions() }
                .onSuccess { _missingPermissions.value = it }
                .onFailure {
                    // An exception is not equivalent to "nothing missing";
                    // preserve the last known list and surface the diagnostic.
                    Log.e(LOG_TAG, "permission check failed", it)
                    appendSystemMessage("permission check failed: ${it.message ?: it::class.simpleName}")
                }
        }
    }

    @OptIn(ExperimentalP2pApi::class)
    fun startHotspot() {
        val currentKit = kit ?: return
        val scope = runScope ?: return
        if (_provisioningBusy.value) {
            Log.i(LOG_TAG, "startHotspot ignored: provisioning busy")
            return
        }
        refreshMissingPermissions()
        _provisioningBusy.value = true
        scope.launch {
            try {
                val result = runCatchingNonCancel {
                    currentKit.networkProvisioning.startLocalNetwork(LocalNetworkConfig())
                }.getOrElse { e ->
                    Log.w(LOG_TAG, "startHotspot threw", e)
                    LocalNetworkResult.Failed(
                        dev.p2pkit.core.NetworkProvisioningError.PlatformError(e)
                    )
                }
                _hotspotResult.value = result
                // Log the full result detail so logcat is self-sufficient. The
                // HotspotCard on-screen already shows error class + message; this
                // mirrors it for non-UI diagnostics (adb logcat -s p2pkit).
                when (result) {
                    is LocalNetworkResult.Started ->
                        Log.i(LOG_TAG, "hotspot Started: ssid=${result.credentials.ssid} " +
                            "port=${result.manualConnectionInfo?.port} " +
                            "hosts=${result.manualConnectionInfo?.hostAddresses}")
                    is LocalNetworkResult.StartedWithoutCredentials ->
                        Log.i(LOG_TAG, "hotspot StartedWithoutCredentials: " +
                            "port=${result.manualConnectionInfo.port} " +
                            "hosts=${result.manualConnectionInfo.hostAddresses}")
                    is LocalNetworkResult.Failed ->
                        Log.w(LOG_TAG, "hotspot Failed: ${result.error::class.simpleName} " +
                            "— ${result.error.message ?: "(no message)"}")
                    is LocalNetworkResult.Unsupported ->
                        Log.w(LOG_TAG, "hotspot Unsupported: ${result.reason}")
                    is LocalNetworkResult.RequiresUserAction ->
                        Log.i(LOG_TAG, "hotspot RequiresUserAction: ${result.instruction}")
                }
            } finally {
                _provisioningBusy.value = false
            }
        }
    }

    fun stopHotspot() {
        val currentKit = kit ?: return
        val scope = runScope ?: return
        if (_provisioningBusy.value) return
        _provisioningBusy.value = true
        scope.launch {
            try {
                // AUDIT-2026-06: D-G8-samples-android-08 — a failed stop no
                // longer clears the card to idle / logs success; the failure
                // is surfaced so the tester knows the hotspot may still be up.
                runCatchingNonCancel { currentKit.networkProvisioning.stopLocalNetwork() }
                    .onSuccess {
                        _hotspotResult.value = null
                        Log.i(LOG_TAG, "hotspot stopped")
                    }
                    .onFailure { e ->
                        Log.w(LOG_TAG, "stopHotspot failed", e)
                        appendSystemMessage("stop hotspot failed: ${e.message ?: e::class.simpleName}")
                        _hotspotResult.value = LocalNetworkResult.Failed(
                            dev.p2pkit.core.NetworkProvisioningError.PlatformError(e)
                        )
                    }
            } finally {
                _provisioningBusy.value = false
            }
        }
    }

    @OptIn(ExperimentalP2pApi::class)
    fun joinHotspot(
        ssid: String,
        passphrase: String,
        // AUDIT-2026-06: A-G8-samples-android-11 — security type is selectable
        // (WPA2 default, WPA3 for SAE-only hotspots) instead of hardcoded WPA2.
        security: WifiSecurityType = WifiSecurityType.WPA2
    ) {
        val currentKit = kit ?: return
        val scope = runScope ?: return
        if (_provisioningBusy.value) {
            Log.i(LOG_TAG, "joinHotspot ignored: provisioning busy")
            return
        }
        refreshMissingPermissions()
        val trimmedSsid = ssid.trim()
        val pass = passphrase.takeIf { it.isNotEmpty() }
        if (trimmedSsid.isEmpty()) {
            Log.w(LOG_TAG, "joinHotspot: SSID is blank")
            appendSystemMessage("join failed: SSID cannot be blank")
            return
        }
        // WPA2/WPA3 minimum passphrase is 8 chars; surface early instead of
        // letting the OS bounce the request silently.
        if (pass != null && pass.length < 8) {
            appendSystemMessage("join failed: passphrase must be 8+ chars (got ${pass.length})")
            return
        }
        _provisioningBusy.value = true
        val creds = WifiCredentials(
            ssid = trimmedSsid,
            password = pass?.let { WifiPassword(it) },
            securityType = if (pass != null) security else WifiSecurityType.OPEN
        )
        scope.launch {
            try {
                val result = runCatchingNonCancel {
                    currentKit.networkProvisioning.joinLocalNetwork(creds)
                }.getOrElse { e ->
                    Log.w(LOG_TAG, "joinHotspot threw", e)
                    JoinNetworkResult.Failed(
                        dev.p2pkit.core.NetworkProvisioningError.PlatformError(e)
                    )
                }
                _joinResult.value = result
                when (result) {
                    is JoinNetworkResult.Joined ->
                        Log.i(LOG_TAG, "join Joined: state=${result.networkState::class.simpleName}")
                    is JoinNetworkResult.Failed ->
                        Log.w(LOG_TAG, "join Failed: ${result.error::class.simpleName} " +
                            "— ${result.error.message ?: "(no message)"}")
                    is JoinNetworkResult.Unsupported ->
                        Log.w(LOG_TAG, "join Unsupported: ${result.reason}")
                    is JoinNetworkResult.RequiresUserAction ->
                        Log.i(LOG_TAG, "join RequiresUserAction: ${result.instruction}")
                    JoinNetworkResult.Pending ->
                        Log.i(LOG_TAG, "join Pending")
                }
            } finally {
                _provisioningBusy.value = false
            }
        }
    }

    fun clearJoinResult() {
        _joinResult.value = null
    }

    // --- file transfer (v0.2.2) -------------------------------------------

    /**
     * Send a file picked from the system file picker (`OpenDocument`) to one
     * connected peer. The Android extension reads name / size / mime from the
     * [Uri]'s `ContentResolver` metadata.
     */
    fun sendFile(peerId: String, uri: Uri) {
        val scope = runScope ?: return
        val session = connectedSessions.firstOrNull { it.peer.id.value == peerId }
        if (session == null) {
            appendSystemMessage("send file failed: peer not in session list")
            return
        }
        val state = session.state.value
        if (state != ConnectionState.Connected) {
            appendSystemMessage("send file to ${session.peer.name} failed: session not Connected (state=$state)")
            return
        }
        val ctx = getApplication<Application>().applicationContext
        scope.launch {
            val preparedHash = withContext(Dispatchers.IO) { sha256Uri(ctx, uri) }
            if (preparedHash != null) {
                val size = runCatching {
                    ctx.contentResolver.openAssetFileDescriptor(uri, "r")?.use { it.length }
                }.getOrNull()
                recordDiagnostic(
                    DiagnosticRecord(
                        peerId = peerId,
                        connectionId = diagnostics.connectionForPeer(peerId)?.connectionId,
                        category = "file",
                        eventName = DiagnosticEventNames.FILE_SELECTED,
                        payloadSizeBytes = size,
                        details = mapOf("source" to "android-content-uri")
                    )
                )
                appendSystemMessage("prepared file sha256=$preparedHash")
            }
            val transfer = runCatchingNonCancel {
                // AUDIT-2026-06: B-G8-samples-android-02 — the SAF extension does
                // ContentResolver getType/query/openInputStream with no internal
                // IO hop; run it off the main thread (cloud DocumentsProviders
                // can block for seconds → ANR risk).
                withContext(Dispatchers.IO) { session.sendFile(ctx, uri) }
            }.getOrElse {
                Log.w(LOG_TAG, "sendFile failed", it)
                appendSystemMessage("send file failed: ${it.message ?: it::class.simpleName}")
                return@launch
            }
            val transferCorrelation = diagnostics.registerTransfer(transfer.id, peerId)
            recordDiagnostic(
                DiagnosticRecord(
                    peerId = peerId,
                    connectionId = transferCorrelation?.connectionId,
                    transferId = transfer.id,
                    category = "transfer",
                    eventName = DiagnosticEventNames.TRANSFER_PREPARED,
                    currentState = transfer.state.value.toString(),
                    payloadSizeBytes = transfer.sizeBytes
                )
            )
            if (preparedHash != null) {
                recordDiagnostic(
                    DiagnosticRecord(
                        peerId = peerId,
                        connectionId = transferCorrelation?.connectionId,
                        transferId = transfer.id,
                        category = "file",
                        eventName = DiagnosticEventNames.FILE_SENDER_HASH,
                        payloadSizeBytes = transfer.sizeBytes,
                        direction = DiagnosticDirection.SENT,
                        details = mapOf("sha256" to preparedHash)
                    )
                )
            }
            registerOutgoingTransfer(transfer, session.peer.name, scope)
        }
    }

    /**
     * Called by the UI when the SAF file picker is dismissed without a
     * selection. Surfaces a system-message line so the user knows the
     * "Send file…" path silently terminated.
     */
    fun notifyFilePickerCancelled(peerId: String?) {
        val peerName = connectedSessions.firstOrNull { it.peer.id.value == peerId }?.peer?.name
            ?: peerId?.take(8)
            ?: "peer"
        appendSystemMessage("file send to $peerName cancelled (no file chosen)")
    }

    /**
     * AUDIT-2026-06: A-G8-samples-android-15 — called by the UI when the SAF
     * picker returned a file but the pending target peer was lost (e.g. the
     * Activity was recreated while the picker was open). Previously the
     * result was dropped with no message at all.
     */
    fun notifySendTargetLost() {
        appendSystemMessage("file picked, but the send target was lost — use Send file… on the peer again")
    }

    /**
     * Called by the UI when the user denies (or has permanently denied) a
     * runtime permission needed for hotspot / join flows. Distinct from the
     * "Grant permission and retry" affordance because the system-permission
     * launcher won't re-prompt if the user has set "Don't ask again".
     */
    fun notifyPermissionDenied(operation: String) {
        appendSystemMessage(
            "$operation: permission denied. Open Settings → App info → Permissions to enable it manually."
        )
    }

    private fun wireIncomingFiles(session: P2pSession, scope: CoroutineScope): Job {
        return scope.launch {
            var previousIds: Set<String> = emptySet()
            try {
                session.pendingFileOffers.collect { offers ->
                    val currentIds = offers.mapTo(mutableSetOf()) { it.id }
                    pendingFileOffers.removeAll { it.id in previousIds && it.id !in currentIds }
                    for (offer in offers) {
                        if (pendingFileOffers.none { it.id == offer.id }) {
                            pendingFileOffers.add(
                                IncomingFileOffer(
                                    id = offer.id,
                                    name = offer.name,
                                    sizeBytes = offer.sizeBytes,
                                    peerName = session.peer.name,
                                    offer = offer
                                )
                            )
                            appendSystemMessage(
                                "incoming file '${offer.name}' from ${session.peer.name} — awaiting consent"
                            )
                            recordDiagnostic(
                                DiagnosticRecord(
                                    peerId = session.peer.id.value,
                                    connectionId = connectionIds[session.id],
                                    transferId = offer.id,
                                    category = "transfer",
                                    eventName = DiagnosticEventNames.TRANSFER_OFFER_RECEIVED,
                                    currentState = "Offered",
                                    payloadSizeBytes = offer.sizeBytes
                                )
                            )
                        }
                    }
                    previousIds = currentIds
                }
            } finally {
                pendingFileOffers.removeAll { it.id in previousIds }
            }
        }
    }

    fun rejectFileOffer(id: String) {
        val pending = pendingFileOffers.firstOrNull { it.id == id } ?: return
        pendingFileOffers.remove(pending)
        cleanupScope.launch { runCatchingNonCancel { pending.offer.reject("rejected by user") } }
        recordDiagnostic(
            DiagnosticRecord(
                peerId = pending.offer.peer.id.value,
                connectionId = diagnostics.registerTransfer(id, pending.offer.peer.id.value)?.connectionId,
                transferId = id,
                category = "transfer",
                eventName = DiagnosticEventNames.TRANSFER_OFFER_REJECTED,
                currentState = "Rejected",
                outcome = DiagnosticOutcome.CANCELLATION,
                details = mapOf("reason" to "operator rejected")
            )
        )
    }

    fun acceptFileOffer(id: String) {
        val scope = runScope ?: return
        val pending = pendingFileOffers.firstOrNull { it.id == id } ?: return
        pendingFileOffers.remove(pending)
        recordDiagnostic(
            DiagnosticRecord(
                peerId = pending.offer.peer.id.value,
                connectionId = diagnostics.registerTransfer(
                    id,
                    pending.offer.peer.id.value
                )?.connectionId,
                transferId = id,
                category = "transfer",
                eventName = DiagnosticEventNames.TRANSFER_OFFER_ACCEPTED,
                currentState = "Accepted"
            )
        )
        scope.launch { acceptIncomingFile(pending, scope) }
    }

    private suspend fun acceptIncomingFile(pending: IncomingFileOffer, scope: CoroutineScope) {
        val ctx = getApplication<Application>().applicationContext
        val maxBytes = 50L * 1024 * 1024
        if (pending.sizeBytes !in 0..maxBytes) {
            runCatchingNonCancel { pending.offer.reject("receiver quota exceeded") }
            appendSystemMessage("rejected '${pending.name}': exceeds 50 MiB sample quota")
            return
        }
        val opened = withContext(Dispatchers.IO) {
            runCatchingNonCancel {
                val baseDir = ctx.getExternalFilesDir(null) ?: ctx.filesDir
                val saveDir = File(baseDir, "p2pkit-incoming/${sanitize(pending.peerName)}")
                    .also { it.mkdirs() }
                cleanupStaleTransferPartsOnce(saveDir)
                val allocatableBytes = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                    val storage = ctx.getSystemService(StorageManager::class.java)
                        ?: error("storage service unavailable")
                    storage.getAllocatableBytes(storage.getUuidForPath(saveDir))
                } else {
                    saveDir.usableSpace
                }
                if (allocatableBytes < pending.sizeBytes + 1L * 1024 * 1024) {
                    error("insufficient free space")
                }
                val saveFile = uniqueDestination(saveDir, pending.name)
                    ?: error("destination namespace exhausted")
                saveFile
            }
        }
        val saveFile = opened.getOrElse { e ->
            runCatchingNonCancel { pending.offer.reject("receiver storage unavailable") }
            appendSystemMessage("rejected '${pending.name}': ${e.message ?: "storage unavailable"}")
            return
        }
        Log.i(LOG_TAG, "incoming file offer ${pending.name} (${pending.sizeBytes}B) → ${saveFile.absolutePath}")
        val destination = runCatchingNonCancel { reservedFileDestination(saveFile) }
            .getOrElse { e ->
                runCatchingNonCancel { pending.offer.reject("destination preparation failed") }
                runCatchingNonCancel { saveFile.delete() }
                appendSystemMessage("receive '${pending.name}' failed: ${e.message ?: e::class.simpleName}")
                return
            }
        val incoming = try {
            pending.offer.accept(destination)
        } catch (cancelled: CancellationException) {
            withContext(NonCancellable) {
                // Cleanup is best effort and must not replace the caller's
                // original cancellation if a broken callback throws its own
                // CancellationException.
                runCatching { destination.abort(null) }
            }
            throw cancelled
        } catch (e: Throwable) {
            withContext(NonCancellable) {
                runCatching { destination.abort(null) }
                runCatching { pending.offer.reject("accept failed on receiver") }
                withContext(Dispatchers.IO) {
                    runCatching { saveFile.delete() }
                }
            }
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
        val correlation = diagnostics.registerTransfer(transfer.id, transfer.peer.id.value)
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
        recordDiagnostic(
            DiagnosticRecord(
                peerId = transfer.peer.id.value,
                connectionId = correlation?.connectionId,
                transferId = transfer.id,
                category = "transfer",
                eventName = DiagnosticEventNames.TRANSFER_PREPARED,
                currentState = transfer.state.value.toString(),
                payloadSizeBytes = transfer.sizeBytes,
                direction = DiagnosticDirection.SENT
            )
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
        val correlation = diagnostics.registerTransfer(transfer.id, transfer.peer.id.value)
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
        recordDiagnostic(
            DiagnosticRecord(
                peerId = transfer.peer.id.value,
                connectionId = correlation?.connectionId,
                transferId = transfer.id,
                category = "transfer",
                eventName = DiagnosticEventNames.TRANSFER_STARTED,
                currentState = transfer.state.value.toString(),
                payloadSizeBytes = transfer.sizeBytes,
                direction = DiagnosticDirection.RECEIVED
            )
        )
        // The transactional destination is SDK-owned and is committed or
        // aborted even if this UI collector is cancelled.
        appendSystemMessage("receiving file '${transfer.name}' from $peerName → $destinationPath")
        watchTransfer(transfer, scope, destinationPath)
    }

    /**
     * Watches one transfer until terminal state, cancels the byte collector,
     * and closes/deletes an incoming destination from a non-cancellable owner.
     * A cancelled run scope therefore cannot strand a writer or partial file.
     */
    private fun watchTransfer(
        transfer: P2pFileTransfer,
        scope: CoroutineScope,
        destinationPath: String? = null
    ) {
        scope.launch {
            var completed = false
            val bytesJob = launch {
                transfer.bytesTransferred.collect { b -> updateRowBytes(transfer.id, b) }
            }
            try {
                transfer.state.first { st ->
                    val previous = fileTransfers.firstOrNull { it.id == transfer.id }?.state?.toString()
                    updateRowState(transfer.id, st)
                    val eventName = when (st) {
                        is FileTransferState.Completed -> DiagnosticEventNames.TRANSFER_COMPLETED
                        is FileTransferState.Failed -> DiagnosticEventNames.TRANSFER_FAILED
                        is FileTransferState.Cancelled -> DiagnosticEventNames.TRANSFER_CANCELLED
                        is FileTransferState.Rejected -> DiagnosticEventNames.TRANSFER_OFFER_REJECTED
                        else -> DiagnosticEventNames.TRANSFER_PROGRESS
                    }
                    recordDiagnostic(
                        DiagnosticRecord(
                            peerId = transfer.peer.id.value,
                            connectionId = diagnostics.registerTransfer(
                                transfer.id,
                                transfer.peer.id.value
                            )?.connectionId,
                            transferId = transfer.id,
                            category = "transfer",
                            eventName = eventName,
                            severity = if (st is FileTransferState.Failed) DiagnosticSeverity.ERROR else DiagnosticSeverity.INFO,
                            previousState = previous,
                            currentState = st.toString(),
                            payloadSizeBytes = transfer.bytesTransferred.value,
                            outcome = when (st) {
                                is FileTransferState.Completed -> DiagnosticOutcome.SUCCESS
                                is FileTransferState.Failed -> DiagnosticOutcome.FAILURE
                                is FileTransferState.Cancelled -> DiagnosticOutcome.CANCELLATION
                                is FileTransferState.Rejected -> DiagnosticOutcome.CANCELLATION
                                else -> null
                            },
                            errorDescription = (st as? FileTransferState.Failed)?.error?.message
                        )
                    )
                    if (st.isTerminal()) {
                        completed = st is FileTransferState.Completed
                        true
                    } else {
                        false
                    }
                }
            } finally {
                withContext(NonCancellable) {
                    bytesJob.cancelAndJoin()
                    if (!completed && destinationPath != null) {
                        withContext(Dispatchers.IO) {
                            runCatching { File(destinationPath).delete() }
                        }
                    } else if (completed && destinationPath != null) {
                        val digest = withContext(Dispatchers.IO) {
                            runCatching { TestFileDigests.sha256(File(destinationPath)) }.getOrNull()
                        }
                        updateRowDigest(transfer.id, digest)
                        if (digest != null) {
                            recordDiagnostic(
                                DiagnosticRecord(
                                    peerId = transfer.peer.id.value,
                                    connectionId = diagnostics.registerTransfer(
                                        transfer.id,
                                        transfer.peer.id.value
                                    )?.connectionId,
                                    transferId = transfer.id,
                                    category = "file",
                                    eventName = DiagnosticEventNames.FILE_RECEIVER_HASH,
                                    payloadSizeBytes = transfer.sizeBytes,
                                    direction = DiagnosticDirection.RECEIVED,
                                    details = mapOf("sha256" to digest)
                                )
                            )
                            val senderDigest = diagnosticRecorder.snapshot()
                                .lastOrNull {
                                    it.transferId == transfer.id &&
                                        it.eventName == DiagnosticEventNames.FILE_SENDER_HASH
                                }?.details?.get("sha256")
                            // The sender and receiver normally export separate
                            // packages. Never report a local receiver hash as
                            // a cross-peer match when the sender package has
                            // not been correlated yet; the operator must
                            // compare both packages (or use the protocol's
                            // authenticated FILE_COMMIT result).
                            recordDiagnostic(
                                DiagnosticRecord(
                                    peerId = transfer.peer.id.value,
                                    connectionId = diagnostics.registerTransfer(
                                        transfer.id,
                                        transfer.peer.id.value
                                    )?.connectionId,
                                    transferId = transfer.id,
                                    category = "file",
                                    eventName = DiagnosticEventNames.FILE_INTEGRITY_CHECKED,
                                    currentState = if (senderDigest == null) {
                                        "awaiting-peer-evidence"
                                    } else if (senderDigest == digest) {
                                        "match"
                                    } else {
                                        "mismatch"
                                    },
                                    severity = if (senderDigest == null) {
                                        DiagnosticSeverity.INFO
                                    } else if (senderDigest == digest) {
                                        DiagnosticSeverity.INFO
                                    } else {
                                        DiagnosticSeverity.ERROR
                                    },
                                    outcome = if (senderDigest == null) null
                                    else if (senderDigest == digest) DiagnosticOutcome.SUCCESS
                                    else DiagnosticOutcome.FAILURE,
                                    details = mapOf(
                                        "match" to if (senderDigest == null) "unknown"
                                        else (senderDigest == digest).toString(),
                                        "senderDigestAvailable" to (senderDigest != null).toString()
                                    )
                                )
                            )
                            appendSystemMessage("received ${transfer.name} sha256=$digest")
                        }
                    }
                }
            }
        }
    }

    private fun addRow(row: FileTransferRow) {
        fileTransfers.add(0, row)
        // Keep the list bounded so the UI stays responsive.
        // AUDIT-2026-06: ARCH-samples-16 — evict only rows whose transfer is
        // terminal; an active (Offered/Accepted/Sending) row keeps its Cancel
        // affordance and live progress even when the history overflows.
        if (fileTransfers.size > FILE_TRANSFER_HISTORY_CAPACITY) {
            for (i in fileTransfers.indices.reversed()) {
                if (fileTransfers.size <= FILE_TRANSFER_HISTORY_CAPACITY) break
                if (fileTransfers[i].state.isTerminal()) fileTransfers.removeAt(i)
            }
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

    private fun sha256Uri(context: android.content.Context, uri: Uri): String? {
        val input = context.contentResolver.openInputStream(uri) ?: return null
        return input.use { TestFileDigests.sha256(it) }
    }

    fun cancelFileTransfer(id: String) {
        val row = fileTransfers.firstOrNull { it.id == id } ?: return
        val scope = runScope ?: return
        scope.launch { runCatchingNonCancel { row.transfer.cancel("user cancelled") } }
    }

    private fun sanitize(raw: String): String {
        val cleaned = raw.filterNot { it.isISOControl() }
            .replace(Regex("""[\\/:*?"<>|]"""), "_")
            .trim()
        return cleaned.takeUnless { it.isEmpty() || it == "." || it == ".." } ?: "untitled"
    }

    /**
     * AUDIT-2026-06: A-G8-samples-android-04 — pick a destination path that
     * does not collide with an existing file. Uses [File.createNewFile] so
     * the claim is atomic even when two offers race; the caller's
     * transactional destination then replaces the claimed file only after a
     * verified durable commit, or removes it on abort. Runs on Dispatchers.IO.
     */
    private fun uniqueDestination(dir: File, rawName: String): File? {
        val base = sanitize(rawName)
        val dot = base.lastIndexOf('.')
        val stem = if (dot > 0) base.substring(0, dot) else base
        val ext = if (dot > 0) base.substring(dot) else ""
        for (n in 0..10_000) {
            val candidate = if (n == 0) File(dir, base) else File(dir, "$stem ($n)$ext")
            if (runCatching { candidate.createNewFile() }.getOrDefault(false)) return candidate
        }
        return null
    }

    fun closeSession(peerId: String) {
        val scope = runScope ?: return
        val target = connectedSessions.firstOrNull { it.peer.id.value == peerId }
        if (target == null) {
            appendSystemMessage("close failed: peer not in session list")
            return
        }
        scope.launch {
            runCatchingNonCancel { target.close() }.onFailure {
                Log.w(LOG_TAG, "close session to ${target.peer.name} failed", it)
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
        // Reconnecting / Closing / Closed all silently drop the send at the
        // SDK level. Filter here so the UI accurately reports who got it.
        val recipients = when (target) {
            SendTarget.All -> sessionsSnapshot.filter { it.state.value == ConnectionState.Connected }
            is SendTarget.Specific -> sessionsSnapshot.filter {
                it.peer.id.value in target.peerIds && it.state.value == ConnectionState.Connected
            }
        }
        if (recipients.isEmpty()) {
            Log.i(LOG_TAG, "room: send skipped (no Connected recipients)")
            val why = if (sessionsSnapshot.isEmpty()) "no sessions"
            else "no peers are Connected (have ${sessionsSnapshot.size} session(s) in non-Connected states)"
            appendSystemMessage("nothing sent — $why")
            return
        }
        val skipped = sessionsSnapshot - recipients.toSet()
        for (s in skipped) {
            // Surface only the peers in the user's target set that we
            // skipped — skipping a Reconnecting peer outside their target
            // is not interesting noise.
            val inTarget = target is SendTarget.Specific && s.peer.id.value in target.peerIds
            val isTargeted = target is SendTarget.All || inTarget
            if (isTargeted) {
                appendSystemMessage("skipped ${s.peer.name} (state=${s.state.value})")
            }
        }

        val body = P2pMessage.Text(trimmed)
        val message = RoomMessage(
            id = nextMessageId++,
            senderName = "(me)",
            body = trimmed,
            timestamp = System.currentTimeMillis(),
            direction = RoomMessage.Direction.Outgoing,
            target = target
        )
        appendRoomMessage(message)
        Log.i(
            LOG_TAG,
            "room: ${if (target is SendTarget.All) "broadcast" else "targeted"} " +
                "→ ${recipients.size} peer(s): ${trimmed.take(60)}"
        )

        for (session in recipients) {
            scope.launch {
                runCatchingNonCancel { session.send(body) }.onFailure {
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
            advertisingToggleMutex.withLock {
                if (_advertising.value) {
                    runCatchingNonCancel { currentKit.stopAdvertising() }
                        .onSuccess { _advertising.value = false }
                        .onFailure { Log.w(LOG_TAG, "stopAdvertising failed", it) }
                } else {
                    runCatchingNonCancel { currentKit.startAdvertising() }
                        .onSuccess { _advertising.value = true }
                        .onFailure { Log.w(LOG_TAG, "startAdvertising failed", it) }
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
                    runCatchingNonCancel { currentKit.stopDiscovery() }
                        .onSuccess { _discovering.value = false }
                        .onFailure { Log.w(LOG_TAG, "stopDiscovery failed", it) }
                } else {
                    runCatchingNonCancel { currentKit.startDiscovery() }
                        .onSuccess { _discovering.value = true }
                        .onFailure { Log.w(LOG_TAG, "startDiscovery failed", it) }
                }
            }
        }
    }

    fun stop() {
        val toStop = kit ?: return
        if (_isStopping.value) return
        retireForegroundRestore()
        recordDiagnostic(
            DiagnosticRecord(
                category = "application",
                eventName = DiagnosticEventNames.APPLICATION_SHUTDOWN,
                currentState = "stopping"
            )
        )
        recordDiagnostic(
            DiagnosticRecord(
                category = "discovery",
                eventName = DiagnosticEventNames.DISCOVERY_STOPPED,
                currentState = "stopping"
            )
        )
        _isStopping.value = true
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
        pendingConnectPeerIds.clear()
        targetedPeerIds.clear()
        roomMessages.clear()
        fileTransfers.clear()
        val offersToReject = pendingFileOffers.toList()
        pendingFileOffers.clear()
        _hasConnectedSession.value = false
        _localPeerId.value = null
        _hotspotResult.value = null
        _joinResult.value = null
        _missingPermissions.value = emptyList()
        _provisioningBusy.value = false
        _networkPathStatus.value = NetworkPathStatus.Unknown
        // Best-effort tear down the hotspot too. Cleared via cleanupScope
        // (not runScope, which we just cancelled) so the stop call survives.
        pendingStopJob = cleanupScope.launch {
            try {
                offersToReject.forEach { pending ->
                    runCatchingNonCancel { pending.offer.reject("sample stopped before consent") }
                }
                runCatchingNonCancel { toStop.networkProvisioning.stopLocalNetwork() }
                val stopped = runCatchingNonCancel { toStop.stop() }
                stopped.onFailure {
                    Log.e(LOG_TAG, "kit.stop failed; ownership retained", it)
                    // Snapshot-backed UI state remains main-thread confined.
                    withContext(Dispatchers.Main.immediate) {
                        // Keep ownership so the user can retry a failed teardown.
                        kit = toStop
                        _isRunning.value = true
                        appendSystemMessage("stop failed: ${it.message ?: it::class.simpleName}")
                    }
                }.onSuccess {
                    connectionIds.clear()
                    frameTraceLease?.release()
                    frameTraceLease = null
                    diagnostics.setLocalPeerId(null)
                }
            } finally {
                _isStopping.value = false
            }
        }
    }

    override fun onCleared() {
        retireForegroundRestore()
        frameTraceLease?.release()
        frameTraceLease = null
        diagnostics.shutdown()
        val toStop = kit
        kit = null
        val offersToReject = pendingFileOffers.toList()
        pendingFileOffers.clear()
        // AUDIT-2026-06: ARCH-samples-18 — never cancel cleanupScope while a
        // stop() teardown launched into it is still in flight; join it first,
        // then finish our own teardown, and only cancel the scope at the end.
        val finalCleanup = cleanupScope.launch {
            pendingStopJob?.join()
            if (toStop != null) {
                offersToReject.forEach { pending ->
                    runCatchingNonCancel { pending.offer.reject("sample cleared before consent") }
                }
                runCatchingNonCancel { toStop.networkProvisioning.stopLocalNetwork() }
                runCatchingNonCancel { toStop.stop() }
            }
        }
        finalCleanup.invokeOnCompletion { cleanupScope.cancel() }
    }

    fun notifyForegrounded() {
        val foregroundLease = foregroundRestoreCoordinator.foregrounded()
        recordDiagnostic(
            DiagnosticRecord(
                category = "application",
                eventName = DiagnosticEventNames.APPLICATION_FOREGROUNDED,
                currentState = "foreground"
            )
        )
        val currentKit = kit ?: return
        currentKit.notifyAppForegrounded()
        val scope = runScope ?: return
        foregroundRestoreJob?.cancel()
        foregroundRestoreJob = scope.launch {
            restoreRequestedFeaturesAfterForeground(currentKit, foregroundLease)
        }
    }

    fun notifyBackgrounded() {
        retireForegroundRestore()
        recordDiagnostic(
            DiagnosticRecord(
                category = "application",
                eventName = DiagnosticEventNames.APPLICATION_BACKGROUNDED,
                currentState = "background"
            )
        )
        kit?.notifyAppBackgrounded()
    }

    private fun retireForegroundRestore() {
        foregroundRestoreCoordinator.backgrounded()
        foregroundRestoreJob?.cancel()
        foregroundRestoreJob = null
    }

    /**
     * The SDK's default background policy intentionally pauses advertising
     * and discovery, while its foreground notification intentionally does not
     * guess host intent. The sample retains each switch as user intent, waits
     * for the asynchronous background stop to settle, then explicitly
     * re-invokes only the requested feature. Waiting for a terminal feature
     * state prevents a rapid stop/start Activity transition from letting an
     * early idempotent start lose to the still-pending background stop.
     */
    private suspend fun restoreRequestedFeaturesAfterForeground(
        currentKit: P2pKit,
        foregroundLease: ForegroundRestoreCoordinator.Lease
    ) {
        advertisingToggleMutex.withLock {
            if (!isForegroundRestoreCurrent(currentKit, foregroundLease, _advertising.value)) {
                return@withLock
            }
            runCatchingNonCancel {
                restoreRequestedFeatureAfterForeground(
                    isStillRequested = {
                        isForegroundRestoreCurrent(
                            currentKit,
                            foregroundLease,
                            _advertising.value
                        )
                    },
                    states = currentKit.advertisingState,
                    start = currentKit::startAdvertising
                )
            }
                .onSuccess { restored ->
                    if (restored) {
                        recordDiagnostic(
                            DiagnosticRecord(
                                category = "discovery",
                                eventName = DiagnosticEventNames.DISCOVERY_STARTED,
                                currentState = "advertising-restored-on-foreground"
                            )
                        )
                    }
                }
                .onFailure { error ->
                    _advertising.value = false
                    Log.w(LOG_TAG, "foreground advertising restore failed", error)
                }
        }
        discoveryToggleMutex.withLock {
            if (!isForegroundRestoreCurrent(currentKit, foregroundLease, _discovering.value)) {
                return@withLock
            }
            runCatchingNonCancel {
                restoreRequestedFeatureAfterForeground(
                    isStillRequested = {
                        isForegroundRestoreCurrent(
                            currentKit,
                            foregroundLease,
                            _discovering.value
                        )
                    },
                    states = currentKit.discoveryState,
                    start = currentKit::startDiscovery
                )
            }
                .onSuccess { restored ->
                    if (restored) {
                        recordDiagnostic(
                            DiagnosticRecord(
                                category = "discovery",
                                eventName = DiagnosticEventNames.DISCOVERY_STARTED,
                                currentState = "discovery-restored-on-foreground"
                            )
                        )
                    }
                }
                .onFailure { error ->
                    _discovering.value = false
                    Log.w(LOG_TAG, "foreground discovery restore failed", error)
                }
        }
    }

    private fun isForegroundRestoreCurrent(
        expectedKit: P2pKit,
        lease: ForegroundRestoreCoordinator.Lease,
        featureRequested: Boolean
    ): Boolean =
        kit === expectedKit &&
            featureRequested &&
            foregroundRestoreCoordinator.isCurrent(lease)

    // --- helpers ----------------------------------------------------------

    private fun reconcileSessions(current: List<P2pSession>, scope: CoroutineScope) {
        val currentIds = current.map { it.id }.toSet()

        // Drop sessions that left the kit.
        val droppedIds = sessionJobs.keys.toList().filter { it !in currentIds }
        for (id in droppedIds) {
            // AUDIT-2026-06: A-G8-samples-android-13 — cancel every collector
            // of the dropped session (messages + state log + incoming files),
            // not just the message one.
            sessionJobs.remove(id)?.forEach { it.cancel() }
            val removed = connectedSessions.firstOrNull { it.id == id }
            if (removed != null) {
                val correlation = diagnostics.removeConnection(id)
                recordDiagnostic(
                    DiagnosticRecord(
                        peerId = removed.peer.id.value,
                        connectionId = correlation?.connectionId ?: connectionIds[id],
                        category = "connection",
                        eventName = DiagnosticEventNames.CONNECTION_DISCONNECTED,
                        previousState = removed.state.value.toString(),
                        currentState = "Closed"
                    )
                )
                connectionIds.remove(id)
                connectedSessions.remove(removed)
                targetedPeerIds.remove(removed.peer.id.value)
                appendSystemMessage("disconnected from ${removed.peer.name}")
                Log.i(LOG_TAG, "room: session removed ${removed.peer.name}")
            }
        }

        // Add sessions that are new in the kit.
        for (session in current) {
            if (sessionJobs.containsKey(session.id)) continue
            val connectionId = diagnostics.registerConnection(
                session.id,
                session.peer.id.value
            )?.connectionId
            if (connectionId != null) connectionIds[session.id] = connectionId
            recordDiagnostic(
                DiagnosticRecord(
                    peerId = session.peer.id.value,
                    connectionId = connectionId,
                    category = "connection",
                    eventName = DiagnosticEventNames.CONNECTION_AUTHENTICATED,
                    currentState = session.state.value.toString(),
                    outcome = DiagnosticOutcome.SUCCESS
                )
            )
            connectedSessions.add(session)
            appendSystemMessage("connected to ${session.peer.name}")
            Log.i(LOG_TAG, "room: session added ${session.peer.name}")
            val incomingJob = scope.launch {
                session.incoming.collect { msg ->
                    Log.i(LOG_TAG, "room: incoming from ${session.peer.name}")
                    appendRoomMessage(
                        RoomMessage(
                            id = nextMessageId++,
                            senderName = session.peer.name,
                            body = msg.displayForTimeline(),
                            timestamp = System.currentTimeMillis(),
                            direction = RoomMessage.Direction.Incoming
                        )
                    )
                }
            }
            // Log session state transitions (Connected / Reconnecting / Failed / Closed)
            // and keep the derived hasConnectedSession flag fresh.
            val stateJob = scope.launch {
                var previousState: ConnectionState? = null
                session.state.collect { st ->
                    Log.i(LOG_TAG, "session ${session.peer.name} → $st")
                    recordDiagnostic(
                        DiagnosticRecord(
                            peerId = session.peer.id.value,
                            connectionId = connectionIds[session.id],
                            category = "connection",
                            eventName = DiagnosticEventNames.CONNECTION_STATE_CHANGED,
                            previousState = previousState?.toString(),
                            currentState = st.toString(),
                            outcome = when (st) {
                                ConnectionState.Connected -> DiagnosticOutcome.SUCCESS
                                ConnectionState.Reconnecting -> DiagnosticOutcome.INTERRUPTION
                                ConnectionState.Failed -> DiagnosticOutcome.FAILURE
                                ConnectionState.Closed -> DiagnosticOutcome.CANCELLATION
                                else -> null
                            }
                        )
                    )
                    if (st == ConnectionState.Connected) {
                        recordDiagnostic(
                            DiagnosticRecord(
                                peerId = session.peer.id.value,
                                connectionId = connectionIds[session.id],
                                category = "protocol",
                                eventName = DiagnosticEventNames.PROTOCOL_NEGOTIATED,
                                currentState = "secure-v2",
                                details = mapOf("feature" to "file-commit-sha256-v1")
                            )
                        )
                    }
                    previousState = st
                    recomputeHasConnectedSession()
                }
            }
            // Queue inbound file offers; the UI must explicitly accept or reject.
            val filesJob = wireIncomingFiles(session, scope)
            sessionJobs[session.id] = listOf(incomingJob, stateJob, filesJob)
        }
        recomputeHasConnectedSession()
    }

    private fun newKitLocalPeerId(): String =
        kit?.localPeerId?.value ?: _localPeerId.value.orEmpty()

    /** Main-thread only (called from runScope collectors / UI intents). */
    private fun recomputeHasConnectedSession() {
        _hasConnectedSession.value =
            connectedSessions.any { it.state.value == ConnectionState.Connected }
    }

    /**
     * AUDIT-2026-06: B-G8-samples-android-04 — single append path that keeps
     * [roomMessages] capped (oldest evicted first) so hours-long rooms don't
     * degrade recomposition.
     */
    private fun appendRoomMessage(message: RoomMessage) {
        roomMessages.add(message)
        while (roomMessages.size > ROOM_MESSAGE_CAPACITY || roomMessages.sumOf { it.body.toByteArray().size } > ROOM_MESSAGE_BYTE_CAPACITY) {
            roomMessages.removeAt(0)
        }
    }

    private fun appendSystemMessage(text: String) {
        appendRoomMessage(
            RoomMessage(
                id = nextMessageId++,
                senderName = "(system)",
                body = text,
                timestamp = System.currentTimeMillis(),
                direction = RoomMessage.Direction.System
            )
        )
    }

    internal fun recordLog(level: String, message: String) {
        // AUDIT-2026-06: ARCH-samples-11 — the SDK invokes the logger from its
        // own threads; marshal onto the main dispatcher so the UI-backing
        // SnapshotStateList is mutated (check-trim-add) from one thread only.
        viewModelScope.launch {
            if (logTail.size >= LOG_TAIL_CAPACITY) {
                logTail.removeAt(0)
            }
            logTail.add("$level  $message")
        }
    }

    private companion object {
        const val APP_ID = "p2pkit-desktop-sample"
        const val LOG_TAG = "p2pkit"
        const val LOG_TAIL_CAPACITY = 30
        const val FILE_TRANSFER_HISTORY_CAPACITY = 24
        // AUDIT-2026-06: B-G8-samples-android-04 — roomMessages cap.
        const val ROOM_MESSAGE_CAPACITY = 500
        const val ROOM_MESSAGE_BYTE_CAPACITY = 256 * 1024
    }
}

/**
 * AUDIT-2026-06: C-G8-samples-android-18 — `runCatching` variant that rethrows
 * [CancellationException]. Plain runCatching around suspend SDK calls caught
 * the CE thrown when [P2pKitViewModel.stop] cancels the run scope, producing
 * ghost "failed …" system messages and letting cancelled coroutines keep
 * executing follow-up statements.
 */
private inline fun <T> runCatchingNonCancel(block: () -> T): Result<T> =
    try {
        Result.success(block())
    } catch (e: CancellationException) {
        throw e
    } catch (t: Throwable) {
        Result.failure(t)
    }

/** Terminal states of a file transfer (safe to evict / close resources). */
private fun FileTransferState.isTerminal(): Boolean =
    this is FileTransferState.Completed ||
        this is FileTransferState.Failed ||
        this is FileTransferState.Rejected ||
        this is FileTransferState.Cancelled

/** Direction of a file transfer row in the sample UI. */
enum class FileTransferDirection { Outgoing, Incoming }

/**
 * Sample-level snapshot of one file transfer for the Compose UI.
 *
 * Updated by the ViewModel as the underlying [P2pFileTransfer]'s
 * `state` / `bytesTransferred` flows emit. Holds the [P2pFileTransfer]
 * reference so the UI can call cancel on it.
 */
data class FileTransferRow(
    val id: String,
    val direction: FileTransferDirection,
    val name: String,
    val sizeBytes: Long,
    val peerName: String,
    val state: FileTransferState,
    val bytesTransferred: Long,
    /** Absolute path on disk for incoming transfers; null for outgoing. */
    val destinationPath: String?,
    /** Test-harness verification digest, populated after durable receive commit. */
    val sha256: String?,
    val transfer: P2pFileTransfer
)

/** User-consent queue entry; holding the offer does not allocate a destination file. */
data class IncomingFileOffer(
    val id: String,
    val name: String,
    val sizeBytes: Long,
    val peerName: String,
    val offer: P2pFileOffer
)

/**
 * Sample-level message envelope rendered in the room timeline.
 *
 * AUDIT-2026-06: B-G8-samples-android-08 — `senderPeerId` (write-only) removed;
 * `timestamp` is now rendered by `RoomLine`.
 */
data class RoomMessage(
    val id: Long,
    val senderName: String,
    /** Timeline text only; binary payload bytes are never retained in UI state. */
    val body: String,
    val timestamp: Long,
    val direction: Direction,
    val target: SendTarget = SendTarget.All
) {
    enum class Direction { Incoming, Outgoing, System }

    val displayBody: String get() = body
}

/** Converts an SDK message to bounded timeline text without retaining payload bytes. */
private fun P2pMessage.displayForTimeline(): String = when (this) {
    is P2pMessage.Text -> value
    is P2pMessage.Binary -> "<binary ${bytes.size}B>"
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
