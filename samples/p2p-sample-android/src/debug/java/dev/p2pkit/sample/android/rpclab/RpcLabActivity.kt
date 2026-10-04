package dev.p2pkit.sample.android.rpclab

import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import android.view.WindowManager
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.Checkbox
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import dev.p2pkit.rpc.RpcFailure
import dev.p2pkit.rpc.RpcPlatform
import dev.p2pkit.rpc.android
import dev.p2pkit.sample.rpc.RpcMobileCapacityConfig
import dev.p2pkit.sample.rpc.RpcPhoneLab
import dev.p2pkit.sample.rpc.RpcPhoneOperation
import dev.p2pkit.sample.rpc.RpcPhonePairing
import dev.p2pkit.sample.rpc.RpcPhoneSettings
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

/** Explicit debug-only foreground test UI. No Intent parameters, background server, automatic pairing or logging. */
public class RpcLabActivity : ComponentActivity() {
    private val ui = CoroutineScope(SupervisorJob() + Dispatchers.Main.immediate)
    private var foreground = false
    private var action: Job? = null
    private var operation: RpcPhoneOperation? = null
    private var lab: RpcPhoneLab? by mutableStateOf(null)
    private val runtimeOwner get() = RpcLabProcessRuntime.owner
    private var ownedToken: RpcLabRuntimeOwner.Token? = null
    private var hostRole by mutableStateOf(false)
    private var busy by mutableStateOf(false)
    private var closing by mutableStateOf(false)
    private var status by mutableStateOf("Stopped; synthetic tests only, not capacity qualification")
    private var localPin by mutableStateOf("")
    private var subnets by mutableStateOf("")
    private var selectedInterface by mutableStateOf("")
    private var localAddress by mutableStateOf("")
    private var port by mutableStateOf("48123")
    private var hostAddress by mutableStateOf("")
    private var hostPin by mutableStateOf("")
    private var invitation by mutableStateOf("")
    private var invitationVisible by mutableStateOf(false)
    private var capacityPins by mutableStateOf("")
    private var importApproved by mutableStateOf(false)
    private var pending by mutableStateOf<List<RpcPhonePairing>>(emptyList())
    private var usbRunLabel by mutableStateOf("")
    private var mobileConfig: RpcMobileCapacityConfig? by mutableStateOf(null)
    private var mobileFiles: AndroidRpcCapacityFiles? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        // Pairing secrets/pins belong to a trusted local UI, not screenshots, recents or crash transcripts.
        window.addFlags(WindowManager.LayoutParams.FLAG_SECURE)
        AndroidRpcCapacityFiles.prepareHome(applicationContext)
        setContent { MaterialTheme { Controls() } }
    }

    override fun onStart() { super.onStart(); foreground = true }

    override fun onStop() {
        foreground = false
        window.clearFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        invitation = ""
        invitationVisible = false
        capacityPins = ""
        stop(runtimeOwner.snapshotFor(ownedToken))
        super.onStop()
    }

    override fun onDestroy() { ui.cancel(); super.onDestroy() }

    private fun report(error: Exception) {
        status = if (error is RpcFailure) "${error.kind.name}/${error.phase.name}/${error.executionEvidence.name}"
            else "Invalid setup or local operation failed; no qualification claim"
    }

    private fun doAction(block: suspend () -> Unit) {
        if (busy || !foreground || runtimeOwner.failure != null) return
        busy = true
        action = ui.launch {
            try { block() } catch (cancelled: CancellationException) {
                status = "Cancelled; a remote side effect may already have happened"
                throw cancelled
            } catch (failure: Exception) { report(failure) }
            finally { busy = closing }
        }
    }

    private fun start(asHost: Boolean) = doAction {
        check(lab == null && !runtimeOwner.occupied)
        if (Build.VERSION.SDK_INT >= 37 &&
            checkSelfPermission("android.permission.ACCESS_LOCAL_NETWORK") != PackageManager.PERMISSION_GRANTED
        ) {
            requestPermissions(arrayOf("android.permission.ACCESS_LOCAL_NETWORK"), 510)
            status = "Approve local-network access, then explicitly select the role again"
            return@doAction
        }
        require(capacityPins.isEmpty() || (asHost && importApproved))
        val settings = RpcPhoneSettings(subnets, selectedInterface, localAddress, port.toInt())
        val approved = if (asHost && importApproved) capacityPins else ""
        val mobile = mobileConfig
        val files = if (mobile != null) checkNotNull(mobileFiles) else null
        if (mobile != null) {
            require(asHost && importApproved && approved == mobile.clientPins &&
                subnets == mobile.settings.subnets && selectedInterface == mobile.settings.interfaceName &&
                localAddress == mobile.settings.localAddress && port.toInt() == mobile.settings.port)
        }
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
                localPin = owned.lab.fingerprint
                status = if (asHost) "Host started; no discovery/mesh"
                    else "Client created; no host selected/connected yet"
                if (mobile != null) monitorMobile(creation, owned)
            }
        } finally {
            try {
                if (created != null && lab !== created?.lab) withContext(NonCancellable) {
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
        subnets = config.settings.subnets
        selectedInterface = config.settings.interfaceName
        localAddress = config.settings.localAddress
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
        if (closing) return
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
                    status = if (owned?.mobileFailed == true) "Stopped; mobile test control failed, no qualification"
                        else "Stopped; owned RPC cleanup completed"
                }
            } catch (failure: Exception) {
                pendingOwner?.let { runtimeOwner.current(it.token)?.failMobile() }
                report(failure)
            }
            finally { closing = false; busy = false }
        }
    }

    private fun call(large: Boolean) {
        val owned = lab ?: return
        if (busy || runtimeOwner.failure != null || operation?.active == true) return
        try {
            operation = owned.echo(large) { result ->
                ui.launch {
                    if (lab === owned) status = "${result.completed}/${result.expected} replies; " +
                        "${result.elapsedMillis} ms; ${result.failureKind ?: "complete"}; " +
                        "${result.executionEvidence ?: "responses received"}; not capacity qualification"
                }
            }
        } catch (failure: Exception) { report(failure) }
    }

    @Composable
    private fun Field(label: String, value: String, limit: Int = 512, update: (String) -> Unit) {
        OutlinedTextField(value, { if (it.length <= limit) update(it) }, label = { Text(label) },
            modifier = Modifier.fillMaxWidth(), keyboardOptions = KeyboardOptions(autoCorrectEnabled = false))
    }

    @Composable
    private fun Controls() {
        val ownership by runtimeOwner.state.collectAsState()
        val hasOwner = ownership != null
        Column(Modifier.padding(16.dp).verticalScroll(rememberScrollState()),
            verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text("P2pKit RPC Lab", style = MaterialTheme.typography.headlineSmall)
            Text("Foreground only. Fixed synthetic procedures; no business data. No readiness/performance claim.")
            Text(status)
            Text("Compiled RPC test source: ${RpcPhoneLab.compiledSource}")
            if (localPin.isNotEmpty()) Text("Local identity (verify privately): $localPin")
            Field("Approved private CIDRs, comma-separated", subnets) { subnets = it }
            Field("Explicit Wi-Fi interface (for example wlan0)", selectedInterface, 32) { selectedInterface = it }
            Field("This device's numeric LAN address", localAddress, 64) { localAddress = it }
            Field("Fixed host port", port, 5) { port = it }
            Field("Optional: exactly 128 public synthetic capacity pins, one per line", capacityPins, 8192) {
                capacityPins = it
            }
            Checkbox(importApproved, { importApproved = it })
            Text("I explicitly approve importing these synthetic client pins into this test host.")
            Field("Optional USB capacity run label", usbRunLabel, 64) { usbRunLabel = it }
            Button({ loadMobile() }, enabled = !busy && !hasOwner && mobileConfig == null) {
                Text("Load prepared USB capacity session (not approval)")
            }
            Button({
                // A queued click can outlive the enabled state from the previous composition.
                if (busy || runtimeOwner.occupied) return@Button
                mobileConfig = null; mobileFiles = null; importApproved = false; capacityPins = ""
            }, enabled = !busy && !hasOwner) {
                Text("Clear loaded session; preserve its evidence files")
            }
            Button({ start(true) }, enabled = !busy && !hasOwner) { Text("Start host") }
            Button({ start(false) }, enabled = !busy && !hasOwner) { Text("Create client") }
            Button({ stop() }, enabled = !closing && hasOwner) { Text("Stop and close") }
            Button({ action?.cancel(); operation?.cancel() }) { Text("Cancel active operation (not rollback)") }
            if (lab != null) {
                Button({
                    val owned = lab ?: return@Button
                    status = "${owned.state}; clients=${owned.connectedClients}; " +
                        "completed=${owned.diagnostics.completedCalls}; queued=${owned.diagnostics.queuedCalls}"
                    if (hostRole && mobileConfig == null) pending = owned.pending()
                }) { Text("Refresh state / pending approvals") }
            }
            if (hostRole && lab != null && mobileConfig == null) {
                Button({ doAction { invitation = checkNotNull(lab).invitation(); invitationVisible = false } },
                    enabled = !busy) { Text("Create one-use, two-minute invitation") }
                Checkbox(invitationVisible, { invitationVisible = it })
                Text("Reveal only on a trusted local display; never send through cloud chat or diagnostics.")
                if (invitationVisible) Text(invitation)
                pending.forEach { request ->
                    Text("Verify client identity locally: ${request.fingerprint}")
                    Button({ doAction { checkNotNull(lab).approve(request.requestId); pending = emptyList() } },
                        enabled = !busy) { Text("Approve this exact client") }
                }
            } else if (!hostRole && lab != null) {
                OutlinedTextField(invitation, { if (it.length <= 512) invitation = it },
                    label = { Text("Trusted local host invitation") },
                    visualTransformation = PasswordVisualTransformation(),
                    keyboardOptions = KeyboardOptions(autoCorrectEnabled = false, keyboardType = KeyboardType.Password))
                Button({
                    doAction {
                        val trusted = invitation
                        invitation = ""
                        checkNotNull(lab).pairAndConnect(trusted)
                        status = "Paired and connected to the explicitly selected host"
                    }
                }, enabled = !busy) { Text("Pair and connect; host must approve") }
                Field("Already trusted host's full fingerprint", hostPin, 64) { hostPin = it }
                Field("Already trusted host's numeric address", hostAddress, 64) { hostAddress = it }
                Button({ doAction { checkNotNull(lab).connect(hostPin, hostAddress, port.toInt()) } },
                    enabled = !busy) { Text("Reconnect using the same durable pin") }
                Button({ call(false) }, enabled = !busy) { Text("One 1 KiB echo") }
                Button({ call(true) }, enabled = !busy) { Text("20 × 1 MiB echoes; concurrency two") }
            }
            if (lab != null && mobileConfig == null) {
                Field("Exact approved peer pin to revoke", hostPin, 64) { hostPin = it }
                Button({ doAction { checkNotNull(lab).revoke(hostPin); status = "Peer revoked" } },
                    enabled = !busy) { Text("Revoke this exact peer") }
            }
        }
    }
}
