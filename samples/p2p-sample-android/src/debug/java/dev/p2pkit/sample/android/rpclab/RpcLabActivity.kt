package dev.p2pkit.sample.android.rpclab

import android.app.KeyguardManager
import android.content.BroadcastReceiver
import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.os.PowerManager
import android.os.SystemClock
import android.view.WindowManager
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.text.selection.SelectionContainer
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.Checkbox
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.key
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import androidx.core.content.ContextCompat
import dev.p2pkit.rpc.RpcPlatform
import dev.p2pkit.rpc.android
import dev.p2pkit.sample.rpc.RpcApplicationExample
import dev.p2pkit.sample.rpc.RpcApplicationInput
import dev.p2pkit.sample.rpc.RpcApplicationProcedure
import dev.p2pkit.sample.rpc.RpcApplicationSession
import dev.p2pkit.sample.rpc.RpcMobileCapacityConfig
import dev.p2pkit.sample.rpc.RpcPhoneLab
import dev.p2pkit.sample.rpc.RpcPhoneOperation
import dev.p2pkit.sample.rpc.RpcRequestEntry
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.CoroutineStart
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.NonCancellable
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.currentCoroutineContext
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive
import kotlinx.coroutines.job
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import kotlin.time.TimeSource

/** Debug-only test UI with a bounded app-switch lease; no Intent secrets, automatic pairing or background restart. */
public class RpcLabActivity : ComponentActivity() {
    private val ui = CoroutineScope(SupervisorJob() + Dispatchers.Main.immediate)
    private var foreground by mutableStateOf(false)
    private var action: Job? = null
    private var operation: RpcPhoneOperation? = null
    private var lab: RpcPhoneLab? by mutableStateOf(null)
    private val runtimeOwner get() = RpcLabProcessRuntime.owner
    private var ownedToken: RpcLabRuntimeOwner.Token? = null
    private var hostRole by mutableStateOf(false)
    private var busy by mutableStateOf(false)
    private var closing by mutableStateOf(false)
    private val eventLog = RpcLabEventLog()
    private val applicationSession = RpcApplicationSession()
    private var inputUser by mutableStateOf("123")
    private var inputOffset by mutableStateOf("0")
    private var inputLimit by mutableStateOf("20")
    private var inputMessage by mutableStateOf("Hello from the RPC sample")
    private var requestEntries by mutableStateOf<List<RpcRequestEntry>>(emptyList())
    private var inspectedRequest by mutableStateOf<Long?>(null)
    private val liveStatus = RpcLabLiveObserver(ui, changed = {
        eventLog.observed(it)
        requestEntries = applicationSession.history.entries()
    }, failed = {
        eventLog.failure(it) // Keep the action status untouched; the live panel owns observation errors.
    })
    private var showDiagnostics by mutableStateOf(false)
    private var status by mutableStateOf("Stopped; synthetic tests only, not capacity qualification")
    private var localPin by mutableStateOf("")
    private lateinit var networkSetup: RpcLabNetworkSetup
    private val subnets get() = networkSetup.state.value.fields.subnets
    private val selectedInterface get() = networkSetup.state.value.fields.interfaceName
    private val localAddress get() = networkSetup.state.value.fields.localAddress
    private var port by mutableStateOf("48123")
    private var hostAddress by mutableStateOf("")
    private var hostPin by mutableStateOf("")
    private var invitation by mutableStateOf("")
    private var invitationVisible by mutableStateOf(false)
    private lateinit var invitationClipboard: RpcLabInvitationClipboard
    private lateinit var appSwitch: RpcLabAppSwitchWindow
    private var capacityPins by mutableStateOf("")
    private var importApproved by mutableStateOf(false)
    private var usbRunLabel by mutableStateOf("")
    private var mobileConfig: RpcMobileCapacityConfig? by mutableStateOf(null)
    private var mobileFiles: AndroidRpcCapacityFiles? = null
    private var startProblem: String? by mutableStateOf(null)
    private var showAdvanced by mutableStateOf(false)
    private var showWifiDetails by mutableStateOf(false)
    private var showCapacity by mutableStateOf(false)
    private var showUsb by mutableStateOf(false)
    private var showReconnect by mutableStateOf(false)
    private val screenOff = object : BroadcastReceiver() {
        override fun onReceive(context: Context?, intent: Intent?) {
            if (intent?.action == Intent.ACTION_SCREEN_OFF) {
                eventLog.record(RpcLabEventLog.Event.ScreenLocked)
                appSwitch.close()
                networkSetup.close()
                stop(runtimeOwner.snapshotFor(ownedToken))
            }
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        // Pairing secrets/pins belong to a trusted local UI, not screenshots, recents or crash transcripts.
        window.addFlags(WindowManager.LayoutParams.FLAG_SECURE)
        AndroidRpcCapacityFiles.prepareHome(applicationContext)
        invitationClipboard = RpcLabInvitationClipboard(getSystemService(ClipboardManager::class.java), expired = {
            eventLog.record(RpcLabEventLog.Event.InvitationExpired)
            if (hostRole) { invitation = ""; invitationVisible = false }
        })
        networkSetup = RpcLabNetworkSetup(AndroidRpcLabWifiObserver(applicationContext),
            idle = { !busy && !closing && !runtimeOwner.occupied },
            invalidated = {
                eventLog.record(RpcLabEventLog.Event.NetworkChanged)
                runtimeOwner.snapshotFor(ownedToken)?.let { stop(it) }
                status = "Wi-Fi changed. Start again when an eligible network is available."
            })
        appSwitch = RpcLabAppSwitchWindow(SystemClock::elapsedRealtime, schedule = { delay, block ->
            val handler = Handler(Looper.getMainLooper())
            val task = Runnable(block)
            handler.postDelayed(task, delay)
            val cancel: () -> Unit = { handler.removeCallbacks(task) }
            cancel
        }, execution = RpcLabShareService.execution(applicationContext), expired = { token ->
            if (ownedToken === token) {
                eventLog.record(RpcLabEventLog.Event.AppSwitchExpired)
                networkSetup.close()
                stop(runtimeOwner.snapshotFor(ownedToken))
            }
        })
        ContextCompat.registerReceiver(this, screenOff, IntentFilter(Intent.ACTION_SCREEN_OFF),
            ContextCompat.RECEIVER_NOT_EXPORTED)
        setContent { MaterialTheme { Controls() } }
    }

    override fun onStart() {
        super.onStart()
        if (!appSwitch.active) networkSetup.setForeground(true)
    }

    override fun onResume() {
        super.onResume()
        foreground = true
        if (appSwitch.active) {
            val returned = appSwitch.resume(ownedToken) { networkSetup.resumeAppSwitch() }
            if (returned) {
                eventLog.record(RpcLabEventLog.Event.AppSwitchReturned)
                status = "Returned to the same RPC role; invitation expiry is unchanged."
            }
        }
        networkSetup.setForeground(true)
        if (lab != null && !closing) window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        startLiveObservation()
    }

    override fun onPause() {
        liveStatus.stop()
        val snapshot = runtimeOwner.snapshotFor(ownedToken)
        val eligible = RpcLabAppSwitchWindow.eligible(
            ordinary = mobileConfig == null && capacityPins.isEmpty() && !importApproved,
            hasRole = lab != null && snapshot?.current?.lab === lab,
            creating = snapshot?.creator != null, busy = busy, operationActive = operation?.active == true,
            closing = closing, cleanupFailed = runtimeOwner.failure != null,
        )
        // Start foreground execution while this Activity is still visible, never from a background callback.
        val unlocked = getSystemService(PowerManager::class.java).isInteractive &&
            !getSystemService(KeyguardManager::class.java).isKeyguardLocked
        if (eligible && unlocked && networkSetup.beginAppSwitch()) {
            if (!appSwitch.begin(checkNotNull(ownedToken))) {
                networkSetup.close()
                stop(snapshot)
            } else eventLog.record(RpcLabEventLog.Event.AppSwitchStarted)
        }
        foreground = false
        super.onPause()
    }

    override fun onStop() {
        liveStatus.stop()
        foreground = false
        window.clearFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        if (!appSwitch.active) {
            networkSetup.setForeground(false)
            invitation = ""
            invitationVisible = false
            invitationClipboard.retire()
            capacityPins = ""
            importApproved = false
            stop(runtimeOwner.snapshotFor(ownedToken))
        }
        super.onStop()
    }

    override fun onDestroy() {
        liveStatus.stop()
        unregisterReceiver(screenOff)
        networkSetup.close()
        appSwitch.close()
        stop(runtimeOwner.snapshotFor(ownedToken))
        ui.cancel()
        super.onDestroy()
    }

    private fun presentStartProblem(message: String) {
        eventLog.record(RpcLabEventLog.Event.SetupRejected)
        status = message
        startProblem = message
    }

    private fun report(error: Exception) {
        status = eventLog.failure(error) + "; see diagnostic log. No qualification claim."
    }

    private fun doAction(block: suspend () -> Unit) {
        if (busy || !foreground || runtimeOwner.failure != null) return
        busy = true
        action = ui.launch {
            try { block() } catch (cancelled: CancellationException) {
                eventLog.record(RpcLabEventLog.Event.Cancelled)
                status = "Cancelled; a remote side effect may already have happened"
                throw cancelled
            } catch (failure: Exception) { report(failure) }
            finally { busy = closing }
        }
    }

    private fun start(asHost: Boolean) = doAction {
        eventLog.record(if (asHost) RpcLabEventLog.Event.StartHostRequested
            else RpcLabEventLog.Event.StartClientRequested)
        check(lab == null && !runtimeOwner.occupied)
        startProblem = null
        val nearby = mobileConfig == null && capacityPins.isEmpty() && !networkSetup.state.value.manual
        val settings = try {
            if (nearby) networkSetup.settingsForAutomaticStart() else networkSetup.settingsForStart(port)
        }
        catch (problem: RpcLabSetupException) {
            presentStartProblem(checkNotNull(problem.message))
            return@doAction
        }
        if (capacityPins.isNotEmpty() && (!asHost || !importApproved)) {
            presentStartProblem(if (asHost)
                "Capacity pins are optional. Clear them for ordinary pairing, or explicitly approve the test import."
                else "A client cannot import host capacity pins. Clear the optional capacity pins under Advanced.")
            return@doAction
        }
        if (Build.VERSION.SDK_INT >= 37 &&
            checkSelfPermission("android.permission.ACCESS_LOCAL_NETWORK") != PackageManager.PERMISSION_GRANTED
        ) {
            eventLog.record(RpcLabEventLog.Event.PermissionRequested)
            requestPermissions(arrayOf("android.permission.ACCESS_LOCAL_NETWORK"), 510)
            status = "Approve local-network access, then explicitly select the role again"
            return@doAction
        }
        val approved = if (asHost && importApproved) capacityPins else ""
        val mobile = mobileConfig
        val files = if (mobile != null) checkNotNull(mobileFiles) else null
        if (mobile != null) {
            require(asHost && importApproved && approved == mobile.clientPins &&
                subnets == mobile.settings.subnets && selectedInterface == mobile.settings.interfaceName &&
                localAddress == mobile.settings.localAddress && port.toInt() == mobile.settings.port)
        }
        status = "Starting the explicitly selected role…"
        val creation = runtimeOwner.beginCreation(currentCoroutineContext().job)
        ownedToken = creation
        var created: RpcLabOwnedRuntime? = null
        try {
            withContext(Dispatchers.Default) {
                val platform = RpcPlatform.android(applicationContext)
                val trust = AndroidRpcLabTrustStore(applicationContext)
                // Retain before returning across a cancellation-sensitive dispatcher boundary.
                val runtime = if (mobile != null)
                    RpcPhoneLab.createMobileCapacityHost(platform, trust, mobile, "Android")
                    else if (asHost && approved.isNotEmpty()) {
                        RpcPhoneLab.createHost(platform, settings, trust, approved)
                    }
                    else if (nearby && asHost) RpcPhoneLab.createNearbyApplicationHost(
                        platform, settings, trust, applicationSession)
                    else if (nearby) RpcPhoneLab.createNearbyApplicationClient(
                        platform, settings, trust, applicationSession)
                    else if (asHost) RpcPhoneLab.createApplicationHost(platform, settings, trust, applicationSession)
                    else RpcPhoneLab.createApplicationClient(platform, settings, trust, applicationSession)
                created = RpcLabOwnedRuntime(runtime, files)
                runtimeOwner.retain(creation, checkNotNull(created))
            }
            if (foreground) {
                val owned = checkNotNull(created)
                lab = owned.lab
                window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
                hostRole = asHost
                eventLog.record(if (asHost) RpcLabEventLog.Event.HostStarted else RpcLabEventLog.Event.ClientCreated)
                localPin = owned.lab.fingerprint
                status = if (asHost) "Host started; advertising status is shown live"
                    else "Client created; no host selected/connected yet"
                startLiveObservation()
                if (mobile != null) monitorMobile(creation, owned)
            }
        } finally {
            try {
                if (created != null && lab !== created.lab) withContext(NonCancellable) {
                    check(runtimeOwner.current(creation) === created)
                    runtimeOwner.retire(creation) { it.close() }
                }
            } finally { runtimeOwner.finishCreation(creation) }
        }
    }

    /** Loading is not approval: the user reviews the exact network and pins, then explicitly presses Start host. */
    private fun loadMobile() = doAction {
        check(lab == null && !runtimeOwner.occupied && mobileConfig == null)
        val files = AndroidRpcCapacityFiles(applicationContext, usbRunLabel)
        val config = RpcMobileCapacityConfig.parse(checkNotNull(files.read("inbox.txt")))
        require(config.hostPlatform == "Android" && config.hostSourceSha == RpcPhoneLab.compiledSource &&
            config.runLabel == usbRunLabel)
        networkSetup.loadSession(config.settings)
        port = config.settings.port.toString()
        capacityPins = config.clientPins
        importApproved = false
        mobileConfig = config
        mobileFiles = files
        status = "Review this USB run's network and 128 pins. " +
            "Approval also allows its exact Stop request and pin cleanup."
    }

    private fun monitorMobile(token: RpcLabRuntimeOwner.Token, owned: RpcLabOwnedRuntime) {
        val files = checkNotNull(owned.mobileFiles)
        val monitor = ui.launch(start = CoroutineStart.LAZY) {
            try {
                withContext(Dispatchers.IO) {
                    files.publish("ready.txt",
                        owned.lab.mobileReadyRecord(androidRpcInstalledArtifact(applicationContext)))
                    val started = TimeSource.Monotonic.markNow()
                    while (isActive) {
                        check(started.elapsedNow().inWholeSeconds < 2_400)
                        files.publish("telemetry.txt", owned.lab.mobileTelemetry(androidRpcPhoneProcessStats()))
                        val request = files.read("stop.txt", optional = true)
                        if (request != null) {
                            check(owned.lab.mobileStopMatches(request))
                            withContext(Dispatchers.Main.immediate) { owned.approveMobileStop() }
                            break
                        }
                        delay(1_000)
                    }
                }
                if (lab === owned.lab) stop(runtimeOwner.snapshotFor(token))
            } catch (cancelled: CancellationException) {
                throw cancelled
            } catch (_: Exception) {
                owned.failMobile()
                eventLog.record(RpcLabEventLog.Event.CapacityControlFailed)
                // Fixed diagnostic only. The coordinator also rejects missing/stale telemetry or any missing receipt.
                try { files.publish("failed.txt", "failed=true\nphase=mobile-control\n") }
                catch (_: Exception) { status = "USB evidence failed; capacity remains unqualified" }
                if (lab === owned.lab) stop(runtimeOwner.snapshotFor(token))
            }
        }
        owned.bindMonitor(monitor)
        monitor.start()
    }

    private fun stop(
        pendingOwner: RpcLabRuntimeOwner.Snapshot<RpcLabOwnedRuntime>? = runtimeOwner.snapshot(),
    ) {
        liveStatus.stop()
        appSwitch.close()
        if (!foreground) networkSetup.close()
        if (closing) return
        eventLog.record(RpcLabEventLog.Event.StopRequested)
        invitation = ""
        invitationVisible = false
        invitationClipboard.retire()
        closing = true
        busy = true
        val previousAction = action
        previousAction?.cancel()
        pendingOwner?.creator?.takeIf { it !== previousAction }?.cancel()
        operation?.cancel()
        // Enter retained Kotlin cleanup before onDestroy can cancel the UI scope.
        ui.launch(start = CoroutineStart.UNDISPATCHED) {
            try {
                withContext(NonCancellable) {
                    // Join does not propagate a caught creation-finalizer failure.
                    // Never mask that new failure or lose its unpublished runtime.
                    if (pendingOwner != null) runtimeOwner.awaitCreation(pendingOwner)
                    if (previousAction !== pendingOwner?.creator) previousAction?.join()
                    // A different Activity may already have retired this token; clear only its original local view.
                    val owned = pendingOwner?.let { runtimeOwner.current(it.token) ?: it.current }
                    if (pendingOwner != null) runtimeOwner.retire(pendingOwner.token) { it.close() }
                    if (pendingOwner == null || lab === owned?.lab) lab = null
                    if (pendingOwner == null || ownedToken === pendingOwner.token) ownedToken = null
                    window.clearFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
                    localPin = ""
                    eventLog.record(RpcLabEventLog.Event.CleanupCompleted)
                    status = if (owned?.mobileFailed == true) "Stopped; mobile test control failed, no qualification"
                        else "Stopped; owned RPC cleanup completed"
                }
            } catch (failure: Exception) {
                pendingOwner?.let { runtimeOwner.current(it.token)?.failMobile() }
                eventLog.record(RpcLabEventLog.Event.CleanupFailed)
                report(failure)
            }
            finally {
                requestEntries = applicationSession.history.entries()
                closing = false
                busy = false
            }
        }
    }

    private fun call(large: Boolean) {
        val owned = lab ?: return
        if (busy || runtimeOwner.failure != null || operation?.active == true) return
        eventLog.record(RpcLabEventLog.Event.EchoRequested)
        status = "Sending synthetic echo; keep this app open until it completes."
        try {
            operation = owned.echo(large) { result ->
                ui.launch {
                    if (lab === owned) status = eventLog.echo(result.completed, result.expected,
                        result.elapsedMillis, result.failureKind, result.executionEvidence) +
                        "; not capacity qualification"
                }
            }
        } catch (failure: Exception) { report(failure) }
    }

    private fun startLiveObservation() {
        val owned = lab ?: return
        val token = ownedToken ?: return
        if (mobileConfig != null || !foreground || closing || runtimeOwner.failure != null) return
        liveStatus.start(owned) {
            check(foreground && !closing && lab === owned && runtimeOwner.current(token)?.lab === owned)
            val diagnostics = owned.diagnostics
            RpcLabLiveSnapshot(hostRole, owned.state, owned.connectedClients,
                diagnostics.completedCalls, diagnostics.queuedCalls,
                if (hostRole && mobileConfig == null) owned.pending().map {
                    RpcLabPendingRequest(it.requestId, it.fingerprint, it.origin)
                } else null, applicationSession.history.revision,
                owned.nearbyHosts(), owned.trustedDevices(), owned.discoveryConnection, owned.networkActivity)
        }
    }

    private fun refreshStatus() {
        if (!foreground || closing) return
        try {
            if (mobileConfig != null) {
                // Prepared capacity sessions keep their pre-existing explicit-only diagnostic read.
                val owned = lab ?: return
                val diagnostics = owned.diagnostics
                status = eventLog.snapshot(hostRole, owned.state, owned.connectedClients,
                    diagnostics.completedCalls, diagnostics.queuedCalls, null)
                return
            }
            val sample = liveStatus.refresh() ?: return
            // Manual Refresh can record a snapshot, but periodic reads never overwrite action/failure feedback.
            eventLog.snapshot(sample.asHost, sample.state, sample.clients, sample.completed, sample.queued,
                sample.pending?.size)
        } catch (failure: Exception) { eventLog.failure(failure) }
    }

    private fun pair() = doAction {
        eventLog.record(RpcLabEventLog.Event.PairRequested)
        status = RpcLabFeedback.PAIR_STARTED
        val trusted = invitation
        invitation = ""
        checkNotNull(lab).pairAndConnect(trusted)
        eventLog.record(RpcLabEventLog.Event.PairConnected)
        status = "Paired and connected to the explicitly selected host"
    }

    private fun runExample(example: RpcApplicationExample) {
        val owned = lab ?: return
        if (!foreground || closing || busy || hostRole || !owned.applicationAvailable || operation?.active == true) {
            return
        }
        busy = true
        status = "Request running. Open Request history for the application response."
        try {
            operation = owned.beginExample(example) { failure ->
                ui.launch {
                    if (lab === owned && !closing) {
                        busy = false
                        requestEntries = applicationSession.history.entries()
                        status = failure ?: "Reply received. Request history distinguishes success and business errors."
                    }
                }
            }
        } catch (failure: Exception) { busy = false; report(failure) }
    }

    private fun sendRequest(procedure: RpcApplicationProcedure) {
        if (!foreground || closing || busy || operation?.active == true || hostRole) return
        val owned = lab ?: return
        val input = try { RpcApplicationInput.parse(procedure, inputUser, inputOffset, inputLimit, inputMessage) }
        catch (_: IllegalArgumentException) {
            status = "Input validation failed: enter whole 32-bit numbers and bounded text."
            return
        }
        try {
            operation = owned.beginRequest(input) { error ->
                ui.launch {
                    if (lab === owned) {
                        requestEntries = applicationSession.history.entries()
                        status = error ?: "Reply received. Inspect history for response data or business errors."
                    }
                }
            }
        } catch (failure: Exception) { report(failure) }
    }

    @Composable
    private fun ApplicationActions() {
        Text("Editable typed API requests")
        Field("User / recipient ID", inputUser, 11) { inputUser = it }
        Button({ sendRequest(RpcApplicationProcedure.GetUser) }, enabled = !busy && !closing) { Text("Send users.get") }
        Field("Items offset", inputOffset, 11) { inputOffset = it }
        Field("Items limit (1–50)", inputLimit, 11) { inputLimit = it }
        Button({ sendRequest(RpcApplicationProcedure.ListItems) }, enabled = !busy && !closing) {
            Text("Send items.list")
        }
        Field("Message text (up to 512 UTF-16 units)", inputMessage, 512) { inputMessage = it }
        Button({ sendRequest(RpcApplicationProcedure.SendMessage) }, enabled = !busy && !closing) {
            Text("Send message.send")
        }

        // A connection/history tick invalidates only this leaf, never the network/setup composition root.
        val currentLive by liveStatus.view.collectAsState()
        Text("Application API examples", style = MaterialTheme.typography.titleMedium)
        listOf("users.get" to RpcApplicationExample.GetUser, "items.list" to RpcApplicationExample.ListItems,
            "message.send" to RpcApplicationExample.SendMessage,
            "Business error (unknown user)" to RpcApplicationExample.BusinessError,
            "Validation error (invalid user ID)" to RpcApplicationExample.ValidationError,
        ).forEach { (label, value) ->
            Button({ runExample(value) }, enabled = !busy && currentLive.snapshot?.state == "Ready") {
                Text(label)
            }
        }
    }

    @Composable
    private fun ApplicationHistory() {
        Text("Request history (application data)", style = MaterialTheme.typography.titleMedium)
        Text("Up to 100 local entries; previews are truncated. Host results describe handler completion, " +
            "not proof the client received them. History survives Stop, not app termination.",
            style = MaterialTheme.typography.bodySmall)
        Text("History captures omitted at capacity: ${applicationSession.history.droppedCaptures}")
        TextButton({
            inspectedRequest = null
            applicationSession.history.clearCompleted()
            requestEntries = applicationSession.history.entries()
        }) {
            Text("Clear completed history")
        }
        requestEntries.asReversed().forEach { entry ->
            key(entry.localId) {
                Card(Modifier.fillMaxWidth().padding(vertical = 4.dp)) {
                    TextButton({ inspectedRequest = entry.localId }) {
                        Text("${entry.procedure}/v${entry.version} · ${entry.outcome} · ${entry.elapsedMillis} ms")
                    }
                }
            }
        }
        inspectedRequest?.let { selected ->
            val entry = requestEntries.firstOrNull { it.localId == selected }
            AlertDialog(onDismissRequest = { inspectedRequest = null }, title = { Text("Request details") },
                text = { Column(Modifier.verticalScroll(rememberScrollState())) {
                    Text("Application data may be private. Copy details only to a trusted destination.")
                    SelectionContainer {
                        Text(entry?.details() ?: "This request is no longer retained. " +
                            "Its application data is unavailable.")
                    }
                } }, confirmButton = { TextButton({ inspectedRequest = null }) { Text("Close") } },
                dismissButton = { Row {
                    TextButton({ entry?.let { copyRequest(it, false) } }, enabled = entry != null) {
                        Text("Copy diagnostics")
                    }
                    TextButton({ entry?.let { copyRequest(it, true) } }, enabled = entry != null) {
                        Text("Copy details")
                    }
                } })
        }
    }

    private fun copyRequest(entry: RpcRequestEntry, includeData: Boolean) {
        if (!foreground) return
        val current = applicationSession.history.entries().firstOrNull { it.localId == entry.localId }
        if (current == null) { status = "This request is no longer retained. Nothing was copied."; return }
        val clip = ClipData.newPlainText("RPC request", if (includeData) current.details() else current.diagnostics())
        clip.description.extras = android.os.PersistableBundle().apply {
            putBoolean("android.content.extra.IS_SENSITIVE", true)
        }
        try { getSystemService(ClipboardManager::class.java).setPrimaryClip(clip) }
        catch (_: Exception) { status = "Clipboard unavailable. Details remain visible locally." }
    }

    private fun copyDiagnostics() {
        if (!foreground) return
        // Only this strictly filtered bounded log is copied; never read the existing clipboard.
        try {
            getSystemService(ClipboardManager::class.java).setPrimaryClip(ClipData.newPlainText(
                "RPC diagnostic log", "P2pKit Android RPC diagnostic log (latest 80 events; not qualification)\n" +
                    "Source: ${RpcPhoneLab.compiledSource}\n" +
                    "Last failure: ${eventLog.lastFailure.value ?: "none"}\n" +
                    eventLog.lines.value.joinToString("\n")))
            status = "Diagnostic log copied. It excludes invitations, fingerprints, addresses and message contents."
        } catch (_: Exception) {
            eventLog.record(RpcLabEventLog.Event.DiagnosticCopyFailed)
            status = "Diagnostic copy unavailable. The log remains visible in this app."
        }
    }

    @Composable
    private fun LiveStatus() {
        if (mobileConfig != null) {
            Text("Live cards are unavailable during a capacity session. " +
                "Use Refresh status and pairing requests for an explicit diagnostic snapshot.")
            return
        }
        val view by liveStatus.view.collectAsState()
        val sample = view.snapshot
        if (sample == null) {
            Text(if (view.problem == null) "Checking live role state…"
                else "Live status unavailable: ${view.problem}. Existing action results remain above.")
            return
        }
        val colors = MaterialTheme.colorScheme
        Text("Live ${if (sample.asHost) "host" else "client"} state: ${sample.safeState}")
        Text("Updates automatically while this app is open; no Refresh is needed.",
            style = MaterialTheme.typography.bodySmall)
        Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                CounterCard(if (sample.asHost) "Clients" else "Connected host",
                    if (sample.asHost) sample.clients.coerceAtLeast(0).toString()
                    else if (sample.safeState == "Ready") "1" else "0",
                    Modifier.weight(1f), colors.primaryContainer, colors.onPrimaryContainer)
                CounterCard(if (sample.asHost) "Pending" else "Connection",
                    if (sample.asHost) sample.pending?.size?.toString() ?: "—" else sample.safeState,
                    Modifier.weight(1f), colors.secondaryContainer, colors.onSecondaryContainer)
            }
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                CounterCard("Completed", sample.completed.coerceAtLeast(0).toString(), Modifier.weight(1f),
                    colors.tertiaryContainer, colors.onTertiaryContainer)
                CounterCard("Queued", sample.queued.coerceAtLeast(0).toString(), Modifier.weight(1f),
                    colors.surfaceContainerHighest, colors.onSurface)
            }
        }
        if (sample.asHost && sample.pending == null) {
            Text("Manual pairing is unavailable during a capacity session.", style = MaterialTheme.typography.bodySmall)
        }
    }

    @Composable
    private fun CounterCard(label: String, value: String, modifier: Modifier, background: Color, content: Color) {
        Card(modifier.semantics(mergeDescendants = true) {},
            colors = CardDefaults.cardColors(containerColor = background, contentColor = content)) {
            Column(Modifier.fillMaxWidth().padding(12.dp)) {
                Text(label, style = MaterialTheme.typography.labelLarge)
                Text(value, style = MaterialTheme.typography.headlineMedium)
            }
        }
    }

    @Composable
    private fun LivePendingRequests() {
        val view by liveStatus.view.collectAsState()
        val rows = view.snapshot?.pending
        val owned = lab
        Text(RpcLabFeedback.pending(rows?.size))
        rows.orEmpty().forEach { request ->
            key(request.requestId, request.fingerprint) {
                Text("Verify client identity locally: ${request.fingerprint}")
                Button({
                    if (!foreground || closing || lab !== owned || !hostRole) return@Button
                    doAction {
                        // A queued tap cannot approve a row retired by a newer sample or by the actual host.
                        check(liveStatus.view.value.snapshot?.pending?.contains(request) == true)
                        check(checkNotNull(owned).pending().any {
                            it.requestId == request.requestId && it.fingerprint == request.fingerprint
                        })
                        eventLog.record(RpcLabEventLog.Event.ApprovalRequested)
                        checkNotNull(lab).approve(request.requestId)
                        eventLog.record(RpcLabEventLog.Event.ExactClientApproved)
                        status = "Approved this exact client. Live pending requests update automatically."
                        liveStatus.refresh()
                    }
                }, enabled = foreground && !busy && !closing && owned != null) { Text("Approve this exact client") }
            }
        }
    }

    @Composable
    private fun NearbyControls() {
        val view by liveStatus.view.collectAsState()
        val owned = lab ?: return
        RpcLabDiscoveryPanel(view.snapshot, foreground && !busy && !closing,
            select = { host ->
                if (foreground && !closing && lab === owned) doAction {
                    check(lab === owned && owned.nearbyHosts().count { it.fingerprint == host.fingerprint } == 1)
                    operation = owned.beginSelectNearby(host.fingerprint, true) { failure ->
                        ui.launch {
                            if (lab === owned) status = failure ?: "Selection saved; connection status updates live."
                        }
                    }
                }
            }, decide = { request, approve ->
                if (foreground && !closing && lab === owned && hostRole) doAction {
                    check(lab === owned && owned.pending().any {
                        it.requestId == request.requestId && it.fingerprint == request.fingerprint
                    })
                    if (approve) owned.approve(request.requestId) else owned.reject(request.requestId)
                    status = if (approve) "Approved this exact identity." else "Request rejected; no trust was saved."
                    liveStatus.refresh()
                }
            }, forget = { pin ->
                if (foreground && !closing && lab === owned) doAction {
                    check(lab === owned && owned.trustedDevices().any { it.fingerprint == pin })
                    owned.revoke(pin)
                    status = "Trust revoked. A new connection requires fresh approval."
                    liveStatus.refresh()
                }
            })
    }

    @Composable
    private fun Diagnostics() {
        // Hidden diagnostics do not collect log updates into the broad Controls composition.
        val logLines by eventLog.lines.collectAsState()
        val lastFailure by eventLog.lastFailure.collectAsState()
        Text("Latest 80 events in memory only; Refresh and Stop keep this history. " +
            "No invitations, fingerprints, addresses or message contents. No network-root-cause claim.",
            style = MaterialTheme.typography.bodySmall)
        SelectionContainer { Text("Last failure: ${lastFailure ?: "none"}\n" +
            logLines.joinToString("\n").ifEmpty { "No events yet." }) }
        Button({ copyDiagnostics() }, enabled = foreground && logLines.isNotEmpty()) {
            Text("Copy diagnostics")
        }
    }

    @Composable
    private fun Field(
        label: String, value: String, limit: Int = 512, enabled: Boolean = true, update: (String) -> Unit,
    ) {
        OutlinedTextField(value, { if (it.length <= limit) update(it) }, label = { Text(label) },
            modifier = Modifier.fillMaxWidth(), keyboardOptions = KeyboardOptions(autoCorrectEnabled = false),
            enabled = enabled)
    }

    @Composable
    private fun Controls() {
        val ownership by runtimeOwner.state.collectAsState()
        val hasOwner = ownership != null
        val network by networkSetup.state.collectAsState()
        val editable = foreground && !busy && !hasOwner
        Column(Modifier.padding(16.dp).verticalScroll(rememberScrollState()),
            verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text("P2pKit RPC", style = MaterialTheme.typography.headlineSmall)
            Text("Choose a role on your private LAN. Network selection is automatic; peer trust is not.")
            Text(status)
            Text("Synthetic tests only; no capacity qualification.", style = MaterialTheme.typography.bodySmall)
            Text("Wi-Fi — no typing needed", style = MaterialTheme.typography.titleMedium)
            if (network.manual) {
                Text("Manual network settings selected. Review them under Advanced.")
            } else {
                network.observation.network?.let {
                    Text("This Android: ${it.localAddress}")
                    Text("Private network: ${it.subnet} · ${it.interfaceName}",
                        style = MaterialTheme.typography.bodySmall)
                }
                Text(network.observation.explanation)
                Text("Starting selects the eligible Wi-Fi automatically. Only use a network you are authorized to use.",
                    style = MaterialTheme.typography.bodySmall)
                TextButton({
                    if (!networkSetup.canRefresh) return@TextButton
                    networkSetup.refresh()
                    startProblem = null
                    status = "Rechecking Wi-Fi; nothing has started."
                }, enabled = networkSetup.canRefresh) { Text("Check Wi-Fi again") }
                TextButton({ showWifiDetails = !showWifiDetails }) { Text("Wi-Fi check details") }
                if (showWifiDetails) {
                    Text(network.observation.details, style = MaterialTheme.typography.bodySmall)
                    Text("These are this app's observations, not proof of peer connectivity or multicast. " +
                        "Advanced offers manual setup for independently verified approved networks.",
                        style = MaterialTheme.typography.bodySmall)
                }
            }
            Text("Choose a role", style = MaterialTheme.typography.titleMedium)
            Text(status)
            if (lab != null) {
                Text(if (hostRole) "Active role: Host" else "Active role: Client",
                    style = MaterialTheme.typography.titleMedium)
                LiveStatus()
            }
            Button({ start(true) }, enabled = !busy && !hasOwner) { Text("Start host") }
            Button({ start(false) }, enabled = !busy && !hasOwner) { Text("Start client") }
            Button({ stop() }, enabled = !closing && hasOwner) { Text("Stop") }
            Text("Host waits for a client. A client must pair with a host before sending a test message.",
                style = MaterialTheme.typography.bodySmall)
            if (lab != null) {
                Button({ refreshStatus() }) { Text("Refresh status and pairing requests") }
                Button({
                    eventLog.record(RpcLabEventLog.Event.CancelRequested)
                    action?.cancel(); operation?.cancel()
                }) { Text("Cancel current operation") }
                Text("Stop waits for cleanup. Cancellation does not undo work already done.",
                    style = MaterialTheme.typography.bodySmall)
            }
            TextButton({ showDiagnostics = !showDiagnostics }) { Text("Diagnostic log") }
            if (showDiagnostics) Diagnostics()
            if (lab?.nearbyMode == true) {
                key(lab) { NearbyControls() }
                if (!hostRole) {
                    ApplicationActions()
                    Button({ call(false) }, enabled = !busy && !closing) { Text("Diagnostic 1 KiB echo") }
                }
            } else if (hostRole && lab != null && mobileConfig == null) {
                Text("Local administrator approval", style = MaterialTheme.typography.titleMedium)
                Button({ doAction {
                    eventLog.record(RpcLabEventLog.Event.InvitationRequested)
                    status = "Creating a one-use invitation; keep this app open."
                    val started = invitationClipboard.beginMinting()
                    invitation = ""
                    invitationVisible = false
                    val host = checkNotNull(lab)
                    val value = host.invitation()
                    if (foreground && lab === host) {
                        invitation = value
                        invitationClipboard.minted(value, started)
                        if (invitation.isNotEmpty()) {
                            eventLog.record(RpcLabEventLog.Event.InvitationReady)
                            status = "Invitation ready. Copy it to the client using a trusted local transfer."
                        }
                    }
                } },
                    enabled = !busy) { Text("Create one-use, two-minute invitation") }
                Row {
                    Checkbox(invitationVisible, { invitationVisible = it })
                    Text("Reveal on this trusted local display")
                }
                Text("Copy works while hidden. Reveal only on a trusted local display; " +
                    "never send through cloud chat or diagnostics.")
                if (invitationVisible) Text(invitation)
                Button({
                    if (foreground && !busy && !closing && hostRole && lab != null) {
                        val copied = invitationClipboard.copy()
                        eventLog.record(if (copied) RpcLabEventLog.Event.InvitationCopied
                            else RpcLabEventLog.Event.InvitationCopyUnavailable)
                        status = if (copied)
                            "Invitation copied as sensitive. Return within 25 seconds; use a trusted local transfer."
                            else "Invitation expired or copy unavailable. Create a new invitation."
                    }
                }, enabled = foreground && !busy && !closing && invitation.isNotEmpty()) {
                    Text("Copy invitation")
                }
                Text("An idle ordinary role can remain active for up to 25 seconds while you switch apps on " +
                    "confirmed Wi-Fi. Return before the window ends. Device lock, in-flight work, capacity/manual " +
                    "sessions, network changes " +
                    "or OS denial stop the role. The invitation still expires two minutes after creation. " +
                    "Clipboard clearing is best effort; do not use cloud chat or clipboard sync.",
                    style = MaterialTheme.typography.bodySmall)
                LivePendingRequests()
            } else if (!hostRole && lab != null) {
                Text("One explicitly selected trusted host", style = MaterialTheme.typography.titleMedium)
                OutlinedTextField(invitation, { if (it.length <= 512) invitation = it },
                    label = { Text("Trusted local host invitation") },
                    visualTransformation = PasswordVisualTransformation(),
                    keyboardOptions = KeyboardOptions(autoCorrectEnabled = false, keyboardType = KeyboardType.Password))
                Button({ pair() }, enabled = !busy) { Text("Pair and connect; host must approve") }
                ApplicationActions()
                TextButton({ showReconnect = !showReconnect }) { Text("Reconnect or run a larger test") }
                if (showReconnect) {
                    Button({ call(false) }, enabled = !busy) { Text("Diagnostic 1 KiB echo") }
                    Field("Already trusted host's full fingerprint", hostPin, 64) { hostPin = it }
                    Field("Already trusted host's numeric address", hostAddress, 64) { hostAddress = it }
                    Button({ doAction {
                        eventLog.record(RpcLabEventLog.Event.ReconnectRequested)
                        status = "Reconnecting to the selected, already trusted host."
                        checkNotNull(lab).connect(hostPin, hostAddress, port.toInt())
                        eventLog.record(RpcLabEventLog.Event.Reconnected)
                        status = "Reconnected to the selected, already trusted host."
                    } },
                        enabled = !busy) { Text("Reconnect using the same durable pin") }
                    Button({ call(true) }, enabled = !busy) { Text("20 × 1 MiB echoes; concurrency two") }
                }
            }
            if (mobileConfig == null) ApplicationHistory()
            TextButton({ showAdvanced = !showAdvanced }) { Text("Advanced") }
            if (showAdvanced) {
                TextButton({ networkSetup.setManual(!network.manual) }, enabled = networkSetup.canConfigure) {
                    Text(if (network.manual) "Use detected Wi-Fi instead" else "Enter network settings manually")
                }
                if (network.manual) {
                    Text("Manual network settings: use only your approved private LAN.")
                    Field("Approved private CIDRs, comma-separated", subnets, enabled = networkSetup.canConfigure) {
                        networkSetup.editManual(networkSetup.state.value.fields.copy(subnets = it))
                    }
                    Field("Wi-Fi interface, for example wlan0", selectedInterface, 32,
                        enabled = networkSetup.canConfigure) {
                        networkSetup.editManual(networkSetup.state.value.fields.copy(interfaceName = it))
                    }
                    Field("This device's numeric LAN address", localAddress, 64,
                        enabled = networkSetup.canConfigure) {
                        networkSetup.editManual(networkSetup.state.value.fields.copy(localAddress = it))
                    }
                }
                Field("Fixed host port", port, 5, enabled = editable && mobileConfig == null) { port = it }
                TextButton({ showCapacity = !showCapacity }) { Text("Capacity-test provisioning") }
                if (showCapacity) {
                    Field("Optional: exactly 128 public synthetic capacity pins, one per line", capacityPins, 8192,
                        enabled = editable && mobileConfig == null) { capacityPins = it }
                    Row {
                        Checkbox(importApproved, { importApproved = it }, enabled = editable)
                        Text("I explicitly approve importing these synthetic client pins into this test host.")
                    }
                }
                TextButton({ showUsb = !showUsb }) { Text("USB capacity session") }
                if (showUsb) {
                    Field("Optional USB capacity run label", usbRunLabel, 64,
                        enabled = editable && mobileConfig == null) { usbRunLabel = it }
                    Button({ loadMobile() }, enabled = !busy && !hasOwner && mobileConfig == null) {
                        Text("Load prepared USB capacity session (not approval)")
                    }
                    Button({
                        // A queued click can outlive the enabled state from the previous composition.
                        if (busy || runtimeOwner.occupied) return@Button
                        mobileConfig = null; mobileFiles = null; importApproved = false; capacityPins = ""
                        networkSetup.clearSession()
                    }, enabled = !busy && !hasOwner) {
                        Text("Clear loaded session; preserve its evidence files")
                    }
                }
                if (lab != null && mobileConfig == null) {
                    Field("Exact approved peer pin to revoke", hostPin, 64) { hostPin = it }
                    Button({ doAction {
                        checkNotNull(lab).revoke(hostPin)
                        eventLog.record(RpcLabEventLog.Event.PeerRevoked)
                        status = "Peer revoked"
                    } },
                        enabled = !busy) { Text("Revoke this exact peer") }
                }
                Text("Compiled RPC test source: ${RpcPhoneLab.compiledSource}",
                    style = MaterialTheme.typography.bodySmall)
                if (localPin.isNotEmpty()) Text("Local identity (verify privately): $localPin")
                Text("Discovery is advisory; approval uses the cryptographic identity. " +
                    "Wi-Fi detection does not prove multicast or peer connectivity.",
                    style = MaterialTheme.typography.bodySmall)
            }
        }
        startProblem?.let { problem ->
            AlertDialog(onDismissRequest = { startProblem = null }, title = { Text("Cannot start RPC") },
                text = { Text(problem) }, confirmButton = { TextButton({ startProblem = null }) { Text("OK") } })
        }
    }
}
