package dev.p2pkit.sample.android

import android.app.Application
import android.net.Uri
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
import dev.p2pkit.core.P2pMessage
import dev.p2pkit.core.P2pSession
import dev.p2pkit.core.P2pState
import dev.p2pkit.core.Peer
import dev.p2pkit.core.ExperimentalP2pApi
import dev.p2pkit.core.ReconnectPolicy
import dev.p2pkit.core.permission.P2pPermission
import dev.p2pkit.core.provisioning.JoinNetworkResult
import dev.p2pkit.core.provisioning.LocalNetworkConfig
import dev.p2pkit.core.provisioning.LocalNetworkResult
import dev.p2pkit.core.provisioning.WifiCredentials
import dev.p2pkit.core.provisioning.WifiPassword
import dev.p2pkit.core.provisioning.WifiSecurityType
import dev.p2pkit.core.transfer.FileTransferState
import dev.p2pkit.core.transfer.P2pFileTransfer
import dev.p2pkit.core.transfer.sendFile
import dev.p2pkit.provisioning.android.AndroidP2pPermissionManager
import dev.p2pkit.provisioning.android.android
import dev.p2pkit.transport.lan.lan
import kotlinx.coroutines.CancellationException
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
import kotlinx.coroutines.withContext
import kotlinx.io.asSink
import java.io.File
import java.io.OutputStream

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

    /** True for the brief duration of [start] (setting up flow collectors). */
    private val _isStarting = MutableStateFlow(false)
    val isStarting: StateFlow<Boolean> = _isStarting.asStateFlow()

    /** True from [stop] until the in-flight kit.stop() coroutine returns. */
    private val _isStopping = MutableStateFlow(false)
    val isStopping: StateFlow<Boolean> = _isStopping.asStateFlow()

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

    private val _advertising = MutableStateFlow(false)
    val advertising: StateFlow<Boolean> = _advertising.asStateFlow()

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

    // --- diagnostics ------------------------------------------------------

    /** Last N lines from the logger; surfaced under the room timeline. */
    val logTail: SnapshotStateList<String> = mutableStateListOf()

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

    /**
     * AUDIT-2026-06: A-G8-samples-android-13 — all three per-session
     * collectors (incoming messages, state log, incoming files) are tracked
     * per session id so a dropped session cancels every collector, not just
     * the message one.
     */
    private val sessionJobs: MutableMap<String, List<Job>> = mutableMapOf()

    /**
     * AUDIT-2026-06: A-G8-samples-android-07 — open destination streams of
     * in-flight incoming transfers, keyed by transfer id. Normally closed by
     * the per-transfer state collector on a terminal state; [stop] /
     * [onCleared] close whatever is left after cancelling those collectors.
     * Main-thread confined (registered/removed from runScope + stop()).
     */
    private val activeIncomingStreams: MutableMap<String, OutputStream> = mutableMapOf()

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
        val newKit = P2pKit.create {
            appId = AppId(APP_ID)
            this.deviceName = this@P2pKitViewModel.deviceName
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
            logger = TailLogger(this@P2pKitViewModel)
        }
        kit = newKit
        refreshMissingPermissions()
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
        scope.launch {
            newKit.networkPathStatus.collect { _networkPathStatus.value = it }
        }
        // Single source of truth for "which peers do we have a session with".
        scope.launch {
            newKit.sessions.collect { current ->
                reconcileSessions(current, scope)
            }
        }
        scope.launch {
            runCatchingNonCancel { newKit.startAdvertising() }
                .onSuccess { _advertising.value = true }
                .onFailure {
                    Log.w(LOG_TAG, "startAdvertising failed", it)
                    appendSystemMessage("advertise failed: ${it.message ?: it::class.simpleName}")
                }
            runCatchingNonCancel { newKit.startDiscovery() }
                .onSuccess { _discovering.value = true }
                .onFailure {
                    Log.w(LOG_TAG, "startDiscovery failed", it)
                    appendSystemMessage("discovery failed: ${it.message ?: it::class.simpleName}")
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
                if (!enabled) return@collect
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

        _isRunning.value = true
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
                runCatchingNonCancel { currentKit.connect(peer) }.onFailure {
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
            _missingPermissions.value =
                runCatchingNonCancel { pm.missingPermissions() }.getOrElse { emptyList() }
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
        val ctx = getApplication<Application>().applicationContext
        return scope.launch {
            session.incomingFiles.collect { offer ->
                // AUDIT-2026-06: B-G8-samples-android-02 — mkdirs / create /
                // open run on Dispatchers.IO, not the main-thread run scope.
                val opened = withContext(Dispatchers.IO) {
                    runCatchingNonCancel {
                        val baseDir = ctx.getExternalFilesDir(null) ?: ctx.filesDir
                        val saveDir = File(baseDir, "p2pkit-incoming/${sanitize(session.peer.name)}")
                            .also { it.mkdirs() }
                        // AUDIT-2026-06: A-G8-samples-android-04 — uniquify the
                        // destination so two offers with the same name (re-send,
                        // duplicate, concurrent) never truncate/interleave one path.
                        val saveFile = uniqueDestination(saveDir, offer.name)
                        saveFile to saveFile.outputStream()
                    }
                }
                val (saveFile, out) = opened.getOrElse { e ->
                    Log.w(LOG_TAG, "cannot open destination for ${offer.name}", e)
                    runCatchingNonCancel { offer.reject("cannot open destination") }
                    appendSystemMessage("rejected '${offer.name}' from ${session.peer.name}: cannot open destination")
                    return@collect
                }
                Log.i(LOG_TAG, "incoming file offer ${offer.name} (${offer.sizeBytes}B) → ${saveFile.absolutePath}")
                val incoming = runCatchingNonCancel { offer.accept(out.asSink()) }
                    .getOrElse { e ->
                        Log.w(LOG_TAG, "accept ${offer.name} failed", e)
                        // AUDIT-2026-06: D-G8-samples-android-09 — on accept
                        // failure, reject the offer (so the sender doesn't wait
                        // out the 30s offer timeout), remove the empty file, and
                        // surface the failure in the timeline.
                        runCatchingNonCancel { offer.reject("accept failed on receiver") }
                        withContext(Dispatchers.IO) {
                            runCatchingNonCancel { out.close() }
                            runCatchingNonCancel { saveFile.delete() }
                        }
                        appendSystemMessage(
                            "receive '${offer.name}' from ${session.peer.name} failed: ${e.message ?: e::class.simpleName}"
                        )
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
        scope.launch {
            transfer.state.collect { st -> updateRowState(transfer.id, st) }
        }
        scope.launch {
            transfer.bytesTransferred.collect { b -> updateRowBytes(transfer.id, b) }
        }
    }

    private fun registerIncomingTransfer(
        transfer: P2pFileTransfer,
        peerName: String,
        destinationPath: String,
        scope: CoroutineScope,
        out: OutputStream
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
        // AUDIT-2026-06: A-G8-samples-android-07 — track the stream so stop()
        // can close it if this collector is cancelled mid-transfer.
        activeIncomingStreams[transfer.id] = out
        appendSystemMessage("receiving file '${transfer.name}' from $peerName → $destinationPath")
        scope.launch {
            transfer.state.collect { st ->
                updateRowState(transfer.id, st)
                if (st.isTerminal()) {
                    activeIncomingStreams.remove(transfer.id)
                    // AUDIT-2026-06: B-G8-samples-android-02 — close (flush) off main.
                    withContext(Dispatchers.IO) { runCatchingNonCancel { out.close() } }
                }
            }
        }
        scope.launch {
            transfer.bytesTransferred.collect { b -> updateRowBytes(transfer.id, b) }
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

    fun cancelFileTransfer(id: String) {
        val row = fileTransfers.firstOrNull { it.id == id } ?: return
        val scope = runScope ?: return
        scope.launch { runCatchingNonCancel { row.transfer.cancel("user cancelled") } }
    }

    private fun sanitize(raw: String): String {
        val cleaned = raw.replace(Regex("""[\\/:*?"<>|]"""), "_").trim()
        return cleaned.ifEmpty { "untitled" }
    }

    /**
     * AUDIT-2026-06: A-G8-samples-android-04 — pick a destination path that
     * does not collide with an existing file. Uses [File.createNewFile] so
     * the claim is atomic even when two offers race; the caller's
     * `outputStream()` then opens the (empty) claimed file. Runs on
     * Dispatchers.IO.
     */
    private fun uniqueDestination(dir: File, rawName: String): File {
        val base = sanitize(rawName)
        val dot = base.lastIndexOf('.')
        val stem = if (dot > 0) base.substring(0, dot) else base
        val ext = if (dot > 0) base.substring(dot) else ""
        var candidate = File(dir, base)
        var n = 1
        while (!candidate.createNewFile() && n < 10_000) {
            candidate = File(dir, "$stem ($n)$ext")
            n++
        }
        return candidate
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
            body = body,
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

    fun toggleDiscovery() {
        val currentKit = kit ?: return
        val scope = runScope ?: return
        scope.launch {
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

    fun stop() {
        val toStop = kit ?: return
        if (_isStopping.value) return
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
        _hasConnectedSession.value = false
        _localPeerId.value = null
        _hotspotResult.value = null
        _joinResult.value = null
        _missingPermissions.value = emptyList()
        _provisioningBusy.value = false
        _networkPathStatus.value = NetworkPathStatus.Unknown
        // AUDIT-2026-06: A-G8-samples-android-07 — cancelling runScope killed
        // the collectors that close incoming-file streams; close the leftovers
        // here (after kit.stop() has quiesced the writers).
        val streamsToClose = activeIncomingStreams.values.toList()
        activeIncomingStreams.clear()
        // Best-effort tear down the hotspot too. Cleared via cleanupScope
        // (not runScope, which we just cancelled) so the stop call survives.
        pendingStopJob = cleanupScope.launch {
            try {
                runCatchingNonCancel { toStop.networkProvisioning.stopLocalNetwork() }
                runCatchingNonCancel { toStop.stop() }
                withContext(Dispatchers.IO) {
                    streamsToClose.forEach { s -> runCatchingNonCancel { s.close() } }
                }
            } finally {
                _isStopping.value = false
            }
        }
    }

    override fun onCleared() {
        super.onCleared()
        val toStop = kit
        kit = null
        val streamsToClose = activeIncomingStreams.values.toList()
        activeIncomingStreams.clear()
        // AUDIT-2026-06: ARCH-samples-18 — never cancel cleanupScope while a
        // stop() teardown launched into it is still in flight; join it first,
        // then finish our own teardown, and only cancel the scope at the end.
        val finalCleanup = cleanupScope.launch {
            pendingStopJob?.join()
            if (toStop != null) {
                runCatchingNonCancel { toStop.networkProvisioning.stopLocalNetwork() }
                runCatchingNonCancel { toStop.stop() }
            }
            if (streamsToClose.isNotEmpty()) {
                withContext(Dispatchers.IO) {
                    streamsToClose.forEach { s -> runCatchingNonCancel { s.close() } }
                }
            }
        }
        finalCleanup.invokeOnCompletion { cleanupScope.cancel() }
    }

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
            val incomingJob = scope.launch {
                session.incoming.collect { msg ->
                    Log.i(LOG_TAG, "room: incoming from ${session.peer.name}")
                    appendRoomMessage(
                        RoomMessage(
                            id = nextMessageId++,
                            senderName = session.peer.name,
                            body = msg,
                            timestamp = System.currentTimeMillis(),
                            direction = RoomMessage.Direction.Incoming
                        )
                    )
                }
            }
            // Log session state transitions (Connected / Reconnecting / Failed / Closed)
            // and keep the derived hasConnectedSession flag fresh.
            val stateJob = scope.launch {
                session.state.collect { st ->
                    Log.i(LOG_TAG, "session ${session.peer.name} → $st")
                    recomputeHasConnectedSession()
                }
            }
            // Auto-accept inbound file offers and stream to external-files dir.
            val filesJob = wireIncomingFiles(session, scope)
            sessionJobs[session.id] = listOf(incomingJob, stateJob, filesJob)
        }
        recomputeHasConnectedSession()
    }

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
        while (roomMessages.size > ROOM_MESSAGE_CAPACITY) {
            roomMessages.removeAt(0)
        }
    }

    private fun appendSystemMessage(text: String) {
        appendRoomMessage(
            RoomMessage(
                id = nextMessageId++,
                senderName = "(system)",
                body = P2pMessage.Text(text),
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
    val transfer: P2pFileTransfer
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
