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
import androidx.compose.material3.Checkbox
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import androidx.core.content.ContextCompat
import dev.p2pkit.rpc.RpcPlatform
import dev.p2pkit.rpc.android
import dev.p2pkit.sample.rpc.RpcMobileCapacityConfig
import dev.p2pkit.sample.rpc.RpcPhoneLab
import dev.p2pkit.sample.rpc.RpcPhoneOperation
import dev.p2pkit.sample.rpc.RpcPhonePairing
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
    private var showDiagnostics by mutableStateOf(false)
    private var pendingCount: Int? by mutableStateOf(null)
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
    private var pending by mutableStateOf<List<RpcPhonePairing>>(emptyList())
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
                status = "Wi-Fi changed. Confirm the current Wi-Fi before starting again."
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
    }

    override fun onPause() {
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
        val settings = try { networkSetup.settingsForStart(port) }
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
                    else if (asHost) RpcPhoneLab.createHost(platform, settings, trust, approved)
                    else RpcPhoneLab.createClient(platform, settings, trust)
                created = RpcLabOwnedRuntime(runtime, files)
                runtimeOwner.retain(creation, checkNotNull(created))
            }
            if (foreground) {
                val owned = checkNotNull(created)
                lab = owned.lab
                window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
                hostRole = asHost
                pending = emptyList()
                pendingCount = null
                eventLog.record(if (asHost) RpcLabEventLog.Event.HostStarted else RpcLabEventLog.Event.ClientCreated)
                localPin = owned.lab.fingerprint
                status = if (asHost) "Host started; no discovery/mesh"
                    else "Client created; no host selected/connected yet"
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
                    pending = emptyList()
                    pendingCount = null
                    eventLog.record(RpcLabEventLog.Event.CleanupCompleted)
                    status = if (owned?.mobileFailed == true) "Stopped; mobile test control failed, no qualification"
                        else "Stopped; owned RPC cleanup completed"
                }
            } catch (failure: Exception) {
                pendingOwner?.let { runtimeOwner.current(it.token)?.failMobile() }
                eventLog.record(RpcLabEventLog.Event.CleanupFailed)
                report(failure)
            }
            finally { closing = false; busy = false }
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

    private fun refreshStatus() {
        val owned = lab ?: return
        try {
            if (hostRole && mobileConfig == null) {
                pending = owned.pending()
                pendingCount = pending.size
            }
            val diagnostics = owned.diagnostics
            status = eventLog.snapshot(hostRole, owned.state, owned.connectedClients,
                diagnostics.completedCalls, diagnostics.queuedCalls, pendingCount)
        } catch (failure: Exception) { report(failure) }
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
    private fun Field(
        label: String, value: String, limit: Int = 512, enabled: Boolean = true, update: (String) -> Unit,
    ) {
        OutlinedTextField(value, { if (it.length <= limit) update(it) }, label = { Text(label) },
            modifier = Modifier.fillMaxWidth(), keyboardOptions = KeyboardOptions(autoCorrectEnabled = false),
            enabled = enabled)
    }

    @Composable
    private fun Controls() {
        val logLines by eventLog.lines.collectAsState()
        val lastFailure by eventLog.lastFailure.collectAsState()
        val ownership by runtimeOwner.state.collectAsState()
        val hasOwner = ownership != null
        val network by networkSetup.state.collectAsState()
        val editable = foreground && !busy && !hasOwner
        Column(Modifier.padding(16.dp).verticalScroll(rememberScrollState()),
            verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text("P2pKit RPC", style = MaterialTheme.typography.headlineSmall)
            Text("Confirm your Wi-Fi, then choose a role. Return within 25 seconds when switching apps.")
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
                Text(when {
                    !foreground -> "Keep this app open in the foreground to check or confirm Wi-Fi."
                    closing -> "Wait for RPC cleanup before changing Wi-Fi."
                    runtimeOwner.failure != null -> "RPC cleanup is pending. Tap Stop to retry."
                    busy -> "An RPC action is in progress. Wi-Fi settings cannot change yet."
                    hasOwner -> "Stop the active RPC role before checking or confirming Wi-Fi again."
                    network.wifiApproved -> "Wi-Fi is already confirmed. Choose Start host or Start client."
                    else -> network.observation.explanation
                })
                Text("Confirm only a network you own or are authorized to test. This does not approve any peer.",
                    style = MaterialTheme.typography.bodySmall)
                Button({
                    if (!networkSetup.canConfirm) return@Button
                    if (networkSetup.confirm()) {
                        startProblem = null
                        status = "Wi-Fi confirmed. Choose Start host or Start client; nothing has started yet."
                    } else presentStartProblem("Wi-Fi changed or is unavailable. " +
                        "Review the detected Wi-Fi and try again.")
                }, enabled = networkSetup.canConfirm) {
                    Text(if (network.wifiApproved) "Wi-Fi confirmed" else "Use this Wi-Fi")
                }
                TextButton({
                    if (!networkSetup.canRefresh) return@TextButton
                    networkSetup.refresh()
                    startProblem = null
                    status = "Rechecking Wi-Fi. Confirm it again before choosing a role; nothing has started."
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
            if (lab != null) Text(if (hostRole) "Active role: Host" else "Active role: Client",
                style = MaterialTheme.typography.titleMedium)
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
            if (showDiagnostics) {
                Text("Latest 80 events in memory only; Refresh and Stop keep this history. " +
                    "No invitations, fingerprints, addresses or message contents. No network-root-cause claim.",
                    style = MaterialTheme.typography.bodySmall)
                SelectionContainer { Text("Last failure: ${lastFailure ?: "none"}\n" +
                    logLines.joinToString("\n").ifEmpty { "No events yet." }) }
                Button({ copyDiagnostics() }, enabled = foreground && logLines.isNotEmpty()) {
                    Text("Copy diagnostics")
                }
            }
            if (hostRole && lab != null && mobileConfig == null) {
                Text(RpcLabFeedback.pending(pendingCount))
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
                pending.forEach { request ->
                    Text("Verify client identity locally: ${request.fingerprint}")
                    Button({ doAction {
                        eventLog.record(RpcLabEventLog.Event.ApprovalRequested)
                        checkNotNull(lab).approve(request.requestId)
                        eventLog.record(RpcLabEventLog.Event.ExactClientApproved)
                        pending = emptyList()
                        pendingCount = null
                        status = "Approved this exact client. Refresh to check remaining requests."
                    } },
                        enabled = !busy) { Text("Approve this exact client") }
                }
            } else if (!hostRole && lab != null) {
                Text("One explicitly selected trusted host", style = MaterialTheme.typography.titleMedium)
                OutlinedTextField(invitation, { if (it.length <= 512) invitation = it },
                    label = { Text("Trusted local host invitation") },
                    visualTransformation = PasswordVisualTransformation(),
                    keyboardOptions = KeyboardOptions(autoCorrectEnabled = false, keyboardType = KeyboardType.Password))
                Button({ pair() }, enabled = !busy) { Text("Pair and connect; host must approve") }
                Button({ call(false) }, enabled = !busy) { Text("Send test message (1 KiB echo)") }
                TextButton({ showReconnect = !showReconnect }) { Text("Reconnect or run a larger test") }
                if (showReconnect) {
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
                Text("No discovery, mesh or business data. " +
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
