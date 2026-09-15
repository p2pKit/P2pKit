package dev.p2pkit.sample.android.runtime

import android.accessibilityservice.AccessibilityServiceInfo
import android.annotation.TargetApi
import android.app.Activity
import android.app.Application
import android.app.Instrumentation
import android.app.KeyguardManager
import android.content.Context
import android.content.Intent
import android.content.pm.ApplicationInfo
import android.os.Build
import android.os.Bundle
import android.os.PowerManager
import android.os.Process
import android.os.SystemClock
import android.view.View
import android.view.ViewGroup
import androidx.activity.compose.LocalActivityResultRegistryOwner
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.MaterialTheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.SideEffect
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.LocalSaveableStateRegistry
import androidx.compose.runtime.saveable.SaveableStateRegistry
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.ComposeView
import androidx.compose.ui.unit.dp
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.ViewModelStore
import androidx.lifecycle.viewModelScope
import dev.p2pkit.core.BuildInfo
import dev.p2pkit.core.P2pKit
import dev.p2pkit.core.permission.P2pPermission
import dev.p2pkit.core.provisioning.JoinNetworkResult
import dev.p2pkit.sample.android.JoinCredentialInputState
import dev.p2pkit.sample.android.JoinHotspotCard
import dev.p2pkit.sample.android.MainActivity
import dev.p2pkit.sample.android.P2pKitViewModel
import dev.p2pkit.sample.android.SampleKitFactories
import java.io.File
import java.util.concurrent.CopyOnWriteArrayList
import java.util.concurrent.atomic.AtomicBoolean
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.NonCancellable
import kotlinx.coroutines.delay
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withContext
import kotlinx.coroutines.withTimeout
import org.json.JSONArray
import org.json.JSONObject

/** Explicit rendered production-card integration, not whole-app restoration, native provisioning or an OS grant. */
@TargetApi(35)
class CredentialUiInstrumentation : Instrumentation() {
    private lateinit var arguments: Bundle
    private val result = Bundle()
    private val report = JSONObject()
    private val cells = JSONArray()
    private val lifecycleTrace = CopyOnWriteArrayList<JSONObject>()
    private val created = CopyOnWriteArrayList<MainActivity>()
    private val mounts = mutableListOf<Mount>()
    private val store = ViewModelStore()
    private val registry = CredentialPermissionRegistry()
    private var application: Application? = null
    private var activity: MainActivity? = null
    private var originalVm: P2pKitViewModel? = null
    private var model: P2pKitViewModel? = null
    private var modeledApp: CredentialApplication? = null
    private var kit: CredentialKit? = null
    private var probe: CredentialUiProbe? = null
    private var output: File? = null
    private var lifecycleAttached = false
    private var modeledLifecycleEnabled = false
    private val lifecycleViolation = AtomicBoolean()
    private var stage = "admission"
    private lateinit var ssid: String
    private lateinit var secret: String

    override fun onCreate(arguments: Bundle?) {
        super.onCreate(arguments)
        this.arguments = Bundle(arguments ?: Bundle())
        start()
    }

    override fun onStart() {
        super.onStart()
        var failure: Throwable? = null
        val cleanup = JSONArray()
        runBlocking {
            try {
                withTimeout(150_000) { exercise() }
            } catch (error: Throwable) {
                failure = error
                report.put("failure", problem(stage, error))
                result.putString("p2pkitFailureStage", stage)
                try { probe?.retainFailure(stage) } catch (retention: Throwable) {
                    report.put("failureDisplayUnavailable", problem(stage, retention))
                }
            } finally {
                suspend fun retire(name: String, block: suspend () -> Unit) {
                    try {
                        withContext(NonCancellable) { withTimeout(10_000) { block() } }
                        cleanup.put(JSONObject().put("step", name).put("outcome", "RETIRED"))
                    } catch (error: Throwable) {
                        cleanup.put(problem(name, error))
                        if (failure == null) failure = error
                    }
                }
                retire("modeled-pending-result") {
                    credentialMain {
                        // Settle only a modeled request; never send a result to an Android system dialog.
                        if (registry.pending != null) registry.answer(false)
                    }
                }
                retire("test-compositions") {
                    credentialMain {
                        var error: Throwable? = null
                        mounts.forEach { mount ->
                            try { mount.view.disposeComposition() } catch (failure: Throwable) {
                                if (error == null) error = failure
                            }
                        }
                        error?.let { throw it }
                        mounts.forEach { mount -> mount.credential?.let { checkCleared(it) } }
                        registry.assertUnregistered()
                    }
                }
                retire("frame-and-window-observers") { probe?.retire() }
                retire("fake-kit-stop") {
                    model?.let { vm ->
                        credentialMain { modeledLifecycleEnabled = false; vm.stop() }
                        credentialAwait { credentialMain { vm.currentRunAdmission().canRunKmpSmoke } }
                    }
                }
                retire("test-viewmodel-store") {
                    credentialMain { modeledLifecycleEnabled = false; store.clear() }
                    credentialAwait {
                        credentialMain {
                            model?.viewModelScope?.coroutineContext?.get(Job)?.isCompleted != false &&
                                kit?.subscriptions()?.all { it == 0 } != false
                        }
                    }
                    kit?.let { check(it.stops == 1 && it.networkProvisioning.closes == 1) }
                }
                retire("owned-activity") {
                    credentialMain { created.filterNot { it.isDestroyed }.forEach { it.finish() } }
                    credentialAwait { credentialMain { created.all { it.isDestroyed } } }
                    originalVm?.let { vm ->
                        check(credentialMain { vm.viewModelScope.coroutineContext[Job]?.isCompleted == true })
                    }
                }
                retire("lifecycle-observer") {
                    credentialMain {
                        if (lifecycleAttached) checkNotNull(application).unregisterActivityLifecycleCallbacks(lifecycle)
                        lifecycleAttached = false
                    }
                }
                retire("retain-diagnostics") {
                    model?.let { vm -> write("events.jsonl", credentialMain { vm.diagnosticRecorder.jsonLines() }) }
                }
                if (lifecycleViolation.get() && failure == null) failure = IllegalStateException("Lifecycle violation")
                if (mounts.any { it.invalidObservation } && failure == null) {
                    failure = IllegalStateException("Credential owner observation violation")
                }
                report.put("cleanup", cleanup).put("cells", cells).put("lifecycle", JSONArray(lifecycleTrace))
                    .put("lifecycleViolation", lifecycleViolation.get())
                    .put("permissionModel", "fakegrant; no OS permission or network acceptance")
                    .put("permissionTrace", registry.trace).put("provisioningCalls", kit?.networkProvisioning?.calls)
                    .put("compositionObservations", JSONArray(mounts.flatMap { it.observations }))
                    .put("captures", probe?.captures).put("actions", probe?.actions)
                    .put("frames", JSONArray(probe?.frames?.map { it.json() } ?: emptyList<JSONObject>()))
                    .put("cleanupScope", "owned UI/fake resources; host must retire exact ART process/guest")
                    .put("outcome", if (failure == null) "HARNESS_PASS_PENDING_REVIEW" else "FAIL")
                try {
                    if (output != null) write("result.json", report.toString(2) + "\n")
                } catch (error: Throwable) {
                    if (failure == null) failure = error
                    result.putString("p2pkitRetention", "FAIL")
                }
            }
        }
        result.putString("p2pkitOutcome", if (failure == null) "HARNESS_PASS_PENDING_REVIEW" else "FAIL")
        result.putString("p2pkitCompleted", "1")
        result.putString("class", javaClass.name)
        result.putString("test", "productionCredentialRestorationAndLifecycle")
        result.putInt("numtests", 1)
        result.putInt("current", 1)
        sendStatus(if (failure == null) 0 else -2, Bundle(result))
        finish(if (failure == null) Activity.RESULT_OK else Activity.RESULT_CANCELED, result)
    }

    private suspend fun exercise() {
        check(arguments.keySet() == setOf("case", "token", "sourceCommit", "sourceTree"))
        check(arguments.getString("case") == "324")
        val token = checkNotNull(arguments.getString("token")).also { check(it.matches(Regex("[0-9a-f]{32}"))) }
        val source = checkNotNull(arguments.getString("sourceCommit")).also {
            check(it.matches(Regex("[0-9a-f]{40}")))
        }
        val tree = checkNotNull(arguments.getString("sourceTree")).also { check(it.matches(Regex("[0-9a-f]{40}"))) }
        check(Build.VERSION.SDK_INT >= 35 && BuildInfo.COMMIT == source && !BuildInfo.DIRTY)
        val app = targetContext.applicationContext as Application
        application = app
        check(app.packageName == CredentialUiProbe.PACKAGE && app.applicationInfo.uid == Process.myUid())
        check(app.applicationInfo.targetSdkVersion == 37)
        check(app.applicationInfo.flags and ApplicationInfo.FLAG_DEBUGGABLE != 0)
        check(!(app.getSystemService(Context.KEYGUARD_SERVICE) as KeyguardManager).isKeyguardLocked)
        check((app.getSystemService(Context.POWER_SERVICE) as PowerManager).isInteractive)
        check(!File(app.noBackupFilesDir, "test-diagnostics").exists()) { "A fresh owned install is required" }
        check(app.getSharedPreferences("p2pkit-test-diagnostics", Context.MODE_PRIVATE).all.isEmpty())
        val directory = File(app.noBackupFilesDir.canonicalFile, "ui-324-$token")
        check(!directory.exists() && directory.mkdir() && directory.canonicalFile == directory)
        output = directory
        ssid = "ui324-${token.take(8)}"
        secret = "Ui324-${token.takeLast(10)}"
        result.putString("p2pkitEvidence", "no_backup/${directory.name}")
        result.putString("p2pkitToken", token)
        report.put("case", "324").put("sourceCommit", source).put("declaredSourceTree", tree)
            .put("treeBinding", "outer controller must independently bind clean source and both APK hashes")
            .put("api", Build.VERSION.SDK_INT).put("targetSdk", app.applicationInfo.targetSdkVersion)
            .put("abis", JSONArray(Build.SUPPORTED_ABIS.toList())).put("pid", Process.myPid())
            .put("processStartElapsedMillis", Process.getStartElapsedRealtime())
            .put("boundsMillis", JSONObject().put("body", 150_000).put("setup", 20_000)
                .put("mainCall", 5_000).put("observation", 5_000).put("cleanupAction", 10_000).put("outer", 240_000))
        stage = "setup"
        withTimeout(20_000) {
            val service = uiAutomation.serviceInfo
            service.flags = service.flags or AccessibilityServiceInfo.FLAG_RETRIEVE_INTERACTIVE_WINDOWS
            uiAutomation.serviceInfo = service
            credentialMain {
                app.registerActivityLifecycleCallbacks(lifecycle)
                lifecycleAttached = true
                app.startActivity(Intent(app, MainActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
            }
            credentialAwait { credentialMain { created.size == 1 && created.single().hasWindowFocus() } }
            val current = credentialMain { created.single() }
            activity = current
            credentialMain {
                originalVm = ViewModelProvider(current)[P2pKitViewModel::class.java].also {
                    check(it.currentRunAdmission().canRunKmpSmoke)
                }
                val fixtureDir = File(directory, "fixture").also { check(it.mkdir()) }
                val host = CredentialApplication(app, fixtureDir, token)
                modeledApp = host
                val fake = CredentialKit(CredentialNetworkFixture(ssid, secret))
                kit = fake
                var creations = 0
                val factories = object : SampleKitFactories {
                    override fun createRoomKit(): P2pKit { check(++creations == 1); return fake }
                    override fun createSmokeKit(): P2pKit = error("No smoke kit in a credential UI case")
                }
                val provider = ViewModelProvider(store, object : ViewModelProvider.Factory {
                    override fun <T : ViewModel> create(modelClass: Class<T>): T {
                        check(modelClass == P2pKitViewModel::class.java)
                        val ownedModel = P2pKitViewModel(host, factories, Dispatchers.Main.immediate)
                        return checkNotNull(modelClass.cast(ownedModel))
                    }
                })
                val vm = provider["credential324", P2pKitViewModel::class.java]
                model = vm
                modeledLifecycleEnabled = true
                vm.notifyForegrounded()
                vm.start()
                check(creations == 1)
            }
            credentialAwait { credentialMain { checkNotNull(model).isRunning.value } }
            val ui = CredentialUiProbe(this@CredentialUiInstrumentation, current, directory)
            probe = ui
            val first = ui.frame("initial-card")
            mount(null)
            ui.status("initial-card", CredentialUiProbe.CARD_TITLE, first)
            ui.enter("SSID", ssid)
        }
        defaultRevealAndExpiry()
        saveDisposeRestore()
        stage = "activity-stop-reentry"
        typeSecret("before-stop")
        reveal("before-stop-revealed")
        stopAndReturn("stop-reentry")
        permissionResult(granted = true, stopped = false)
        successfulJoin(conflated = false)
        permissionResult(granted = false, stopped = false)
        permissionResult(granted = true, stopped = true)
        successfulJoin(conflated = true)
        failedJoinKeepsEditableCredential()
        stage = "final-card-disposal"
        val finalFrame = ui().frame(stage)
        val old = credentialMain { credential() }
        credentialMain { mount().show.value = false }
        credentialAwait { credentialMain { old.passphrase.isEmpty() && !old.isRevealed } }
        ui().removed(stage, finalFrame)
        credentialMain { registry.assertUnregistered() }
        passed(stage)
    }

    private suspend fun defaultRevealAndExpiry() {
        stage = "default-masking"
        typeSecret(stage)
        reveal("explicit-reveal")
        val hideFrame = ui().frame("explicit-hide")
        ui().click("Hide")
        ui().field("explicit-hide", secret, mask(), true, hideFrame)
        check(credentialMain { credential().passphrase == secret && !credential().isRevealed })
        passed("default-mask-and-explicit-reveal-hide")
        stage = "real-fifteen-second-expiry"
        val begin = reveal("expiry-start")
        val stable = ui().identity()
        val actions = ui().actions.length()
        val input = ui().inputCount.get()
        val lifecycleCount = lifecycleTrace.size
        val frame = ui().frame("expiry-natural-frame")
        var observed = 0L
        var lastRevealed = 0L
        while (SystemClock.elapsedRealtimeNanos() < begin + 17_000_000_000L) {
            check(ui().identity() == stable && ui().actions.length() == actions && ui().inputCount.get() == input)
            check(lifecycleTrace.size == lifecycleCount)
            val concealed = credentialMain {
                check(credential().passphrase == secret)
                !credential().isRevealed
            }
            val now = SystemClock.elapsedRealtimeNanos()
            if (concealed) { observed = now; break }
            lastRevealed = now
            if (frame.committed.get() != 0L) credentialMain { frame.arm() }
            delay(50)
        }
        check(observed in (begin + 15_000_000_000L)..(begin + 17_000_000_000L)) {
            "Reveal concealed early or did not expire within seventeen seconds"
        }
        ui().field("expired-mask", secret, mask(), true, frame, begin + 15_000_000_000L)
        report.put("revealExpiry", JSONObject().put("showBeginElapsedNanos", begin)
            .put("lastRevealedObservedElapsedNanos", lastRevealed).put("concealedObservedElapsedNanos", observed)
            .put("unchangedInputAndLifecycle", true))
        passed(stage)
        reveal("before-save-revealed")
    }

    private suspend fun saveDisposeRestore() {
        stage = "pre-clear-parcel-save"
        val vm = checkNotNull(model)
        val old = credentialMain { credential() }
        val beforeLifecycle = lifecycleTrace.size
        val values = credentialMain {
            check(checkNotNull(activity).lifecycle.currentState == Lifecycle.State.RESUMED)
            check(old.passphrase == secret && old.isRevealed && vm.joinSuccessCount.value == 0L)
            check(checkNotNull(kit).networkProvisioning.calls.length() == 0 && registry.requests.isEmpty())
            val saved = credentialParcel(checkNotNull(mount().registry), checkNotNull(application).classLoader,
                ssid, secret, checkNotNull(output))
            check(old.passphrase == secret && old.isRevealed && lifecycleTrace.size == beforeLifecycle)
            saved
        }
        passed(stage)
        stage = "disposal-of-original-owner"
        val removed = ui().frame(stage)
        credentialMain { mount().show.value = false }
        credentialAwait { credentialMain { old.passphrase.isEmpty() && !old.isRevealed } }
        check(lifecycleTrace.size == beforeLifecycle)
        ui().removed(stage, removed)
        check(credentialMain { mount().credential === old && vm.joinSuccessCount.value == 0L })
        passed(stage)
        stage = "actual-registry-restoration"
        val restoredFrame = ui().frame(stage)
        mount(values)
        ui().field("restored-empty-secret", "", "", true, restoredFrame)
        ui().field("restored-ssid", ssid, ssid, false, restoredFrame)
        check(credentialMain { credential() !== old && credential().passphrase.isEmpty() && !credential().isRevealed })
        check(joinCalls() == 0 && lifecycleTrace.size == beforeLifecycle)
        passed(stage)
    }

    private suspend fun permissionResult(granted: Boolean, stopped: Boolean) {
        stage = "fakegrant-${if (granted) "true" else "false"}-${if (stopped) "stopped" else "resumed"}"
        val label = stage
        val vm = checkNotNull(model)
        val app = checkNotNull(modeledApp)
        credentialMain { app.nearbyGranted = false; vm.refreshMissingPermissions() }
        credentialAwait { credentialMain { vm.missingPermissions.value == listOf(P2pPermission.NearbyWifiDevices) } }
        typeSecret("$label-input")
        reveal("$label-revealed")
        val original = credentialMain { credential() }
        val calls = joinCalls()
        val notices = credentialMain { vm.roomMessages.size }
        val checks = credentialMain { app.nearbyChecks }
        val lifecycleCount = lifecycleTrace.size
        ui().click("Grant permission and join", "Grant permission and retry")
        check(credentialMain { registry.pending != null && original.passphrase == secret && original.isRevealed })
        val answer = {
            credentialMain {
                app.nearbyGranted = granted
                registry.answer(granted)
            }
        }
        if (stopped) stopAndReturn(label, answer) else {
            val frame = ui().frame(label)
            answer()
            credentialAwait { credentialMain { original.passphrase.isEmpty() && !original.isRevealed } }
            ui().field("$label-cleared", "", "", true, frame)
            check(lifecycleTrace.size == lifecycleCount) { "Another clear cause invalidated result isolation" }
        }
        credentialAwait {
            credentialMain {
                app.nearbyChecks > checks && vm.missingPermissions.value.isEmpty() == granted &&
                    vm.roomMessages.size == notices + 1
            }
        }
        val notice = credentialMain { vm.roomMessages.last().body }
        check(notice == if (granted) {
            "hotspot join: permission granted. Re-enter the passphrase and tap Join hotspot."
        } else {
            "hotspot join: permission denied. Open Settings → App info → Permissions to enable it manually."
        })
        repeat(5) { delay(100); check(joinCalls() == calls) }
        check(credentialMain { credential() === original && original.passphrase.isEmpty() && !original.isRevealed })
        passed(label)
    }

    private suspend fun stopAndReturn(label: String, whileStopped: (() -> Unit)? = null) {
        val current = checkNotNull(activity)
        val old = credentialMain { credential() }
        val view = credentialMain { mount().view }
        val stops = lifecycleTrace.count { it.getString("event") == "stopped" }
        val calls = joinCalls()
        check(credentialMain { old.passphrase == secret && old.isRevealed })
        credentialMain { check(current.moveTaskToBack(true)) }
        credentialAwait {
            lifecycleTrace.count { it.getString("event") == "stopped" } == stops + 1 &&
                credentialMain { current.lifecycle.currentState == Lifecycle.State.CREATED }
        }
        check(credentialMain { credential() === old && old.passphrase.isEmpty() && !old.isRevealed })
        whileStopped?.invoke()
        check(joinCalls() == calls)
        val frame = ui().frame(label)
        credentialMain {
            checkNotNull(application).startActivity(Intent(current, MainActivity::class.java).addFlags(
                Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_REORDER_TO_FRONT or
                    Intent.FLAG_ACTIVITY_SINGLE_TOP
            ))
        }
        credentialAwait {
            credentialMain { created.size == 1 && current.lifecycle.currentState == Lifecycle.State.RESUMED &&
                current.hasWindowFocus() }
        }
        check(credentialMain { mount().view === view && credential() === old })
        ui().field("$label-reentered-empty", "", "", true, frame)
        check(joinCalls() == calls)
        if (whileStopped == null) passed(label)
    }

    private suspend fun successfulJoin(conflated: Boolean) {
        stage = if (conflated) "join-success-then-failure" else "explicit-protected-join-success"
        val label = stage
        val vm = checkNotNull(model)
        val manager = checkNotNull(kit).networkProvisioning
        typeSecret("$label-input")
        reveal("$label-revealed")
        val old = credentialMain { credential() }
        val calls = joinCalls()
        val successes = credentialMain { vm.joinSuccessCount.value }
        val observations = credentialMain { mount().observations.size }
        val lifecycleCount = lifecycleTrace.size
        credentialMain { manager.outcome = if (conflated) CredentialNetworkFixture.Outcome.JOINED_THEN_FAILED
            else CredentialNetworkFixture.Outcome.JOINED }
        val frame = ui().frame(label)
        ui().click("Join hotspot", "Retry join")
        credentialAwait {
            credentialMain { manager.calls.length() == calls + 1 && vm.joinSuccessCount.value == successes + 1 &&
                old.passphrase.isEmpty() && !old.isRevealed && !vm.joinProvisioningBusy.value }
        }
        check(credentialMain { credential() === old } && lifecycleTrace.size == lifecycleCount)
        val call = manager.calls.getJSONObject(calls)
        check(call.getBoolean("protected") && call.getBoolean("ssidMatches") && call.getBoolean("secretMatches"))
        check(call.getString("returned") == "Joined")
        if (conflated) {
            check(call.getJSONArray("signals").toString() == "[\"NetworkJoined\",\"JoinFailed\"]")
            check(credentialMain { vm.joinResult.value is JoinNetworkResult.Failed })
            check(credentialMain { mount().observations.drop(observations).none {
                it.optString("joinResult") == "Joined"
            } }) { "Fixture did not conflate success/release before composition" }
            ui().field("$label-cleared", "", "", true, frame)
        } else {
            check(credentialMain { vm.joinResult.value is JoinNetworkResult.Joined })
            ui().status(label, JOINED_TEXT, frame)
            val dismissed = ui().frame("dismiss-joined")
            ui().click("Dismiss — still joined")
            ui().field("dismiss-joined-empty", "", "", true, dismissed)
        }
        passed(label)
    }

    private suspend fun failedJoinKeepsEditableCredential() {
        stage = "failure-without-success-control"
        val vm = checkNotNull(model)
        val manager = checkNotNull(kit).networkProvisioning
        val successes = credentialMain { vm.joinSuccessCount.value }
        val calls = joinCalls()
        typeSecret("failure-control-input")
        val old = credentialMain { credential() }
        credentialMain { manager.outcome = CredentialNetworkFixture.Outcome.FAILED_ONLY }
        val frame = ui().frame(stage)
        ui().click("Retry join")
        credentialAwait { credentialMain { manager.calls.length() == calls + 1 && !vm.joinProvisioningBusy.value } }
        check(credentialMain {
            vm.joinSuccessCount.value == successes && credential() === old && old.passphrase == secret
        })
        check(manager.calls.getJSONObject(calls).getString("returned") == "Failed")
        ui().field(stage, secret, mask(), true, frame)
        passed(stage)
    }

    private suspend fun typeSecret(label: String) {
        check(credentialMain { credential().passphrase.isEmpty() && !credential().isRevealed })
        val frame = ui().frame(label)
        ui().enter(CredentialUiProbe.PASSPHRASE_LABEL, secret)
        ui().field(label, secret, mask(), true, frame)
        check(credentialMain { credential().passphrase == secret && !credential().isRevealed })
    }

    private suspend fun reveal(label: String): Long {
        val frame = ui().frame(label)
        val begin = ui().click("Show")
        ui().field(label, secret, secret, false, frame)
        check(credentialMain { credential().passphrase == secret && credential().isRevealed })
        return begin
    }

    private suspend fun mount(restored: Map<String, List<Any?>>?) {
        credentialMain {
            val current = checkNotNull(activity)
            fun dispose(view: View) {
                if (view is ComposeView) view.disposeComposition()
                if (view is ViewGroup) repeat(view.childCount) { dispose(view.getChildAt(it)) }
            }
            dispose(current.window.decorView)
            val next = Mount(checkNotNull(model), registry, restored)
            mounts += next
            next.view = ComposeView(current).apply { setContent { CredentialContent(next) } }
            current.setContentView(next.view)
        }
        credentialAwait { credentialMain { mount().credential != null && mount().registry != null } }
    }

    private fun mount(): Mount = mounts.last()
    private fun credential(): JoinCredentialInputState {
        check(!lifecycleViolation.get() && !mount().invalidObservation)
        return checkNotNull(mount().credential)
    }
    private fun ui(): CredentialUiProbe = checkNotNull(probe)
    private fun mask(): String = "\u2022".repeat(secret.length)
    private fun joinCalls(): Int = credentialMain { checkNotNull(kit).networkProvisioning.calls.length() }
    private fun passed(cell: String) {
        cells.put(JSONObject().put("cell", cell).put("outcome", "OBSERVED_PENDING_REVIEW"))
    }
    private fun write(name: String, contents: String) {
        check(contents.toByteArray().size <= 2 * 1024 * 1024)
        val file = File(checkNotNull(output), name)
        check(file.createNewFile())
        file.writeText(contents)
    }

    private val lifecycle = object : Application.ActivityLifecycleCallbacks {
        private fun note(current: Activity, event: String) {
            if (current !is MainActivity || lifecycleTrace.size >= 100) {
                lifecycleViolation.set(true)
                return
            }
            lifecycleTrace += JSONObject().put("event", event).put("activity", System.identityHashCode(current))
                .put("elapsedNanos", SystemClock.elapsedRealtimeNanos())
        }
        override fun onActivityCreated(activity: Activity, state: Bundle?) {
            note(activity, "created")
            if (activity is MainActivity) created += activity
        }
        override fun onActivityStarted(activity: Activity) {
            note(activity, "started")
            if (modeledLifecycleEnabled && activity === this@CredentialUiInstrumentation.activity) {
                model?.notifyForegrounded()
            }
        }
        override fun onActivityResumed(activity: Activity) = note(activity, "resumed")
        override fun onActivityPaused(activity: Activity) = note(activity, "paused")
        override fun onActivityStopped(activity: Activity) {
            note(activity, "stopped")
            if (modeledLifecycleEnabled && activity === this@CredentialUiInstrumentation.activity) {
                model?.notifyBackgrounded()
            }
        }
        override fun onActivitySaveInstanceState(activity: Activity, state: Bundle) = note(activity, "saved")
        override fun onActivityDestroyed(activity: Activity) = note(activity, "destroyed")
    }

    private class Mount(
        val model: P2pKitViewModel,
        val permissions: CredentialPermissionRegistry,
        val restored: Map<String, List<Any?>>?
    ) {
        val show = mutableStateOf(true)
        lateinit var view: ComposeView
        var registry: SaveableStateRegistry? = null
        var credential: JoinCredentialInputState? = null
        var invalidObservation = false
            private set
        val observations = mutableListOf<JSONObject>()
        fun observe(state: JoinCredentialInputState) {
            if ((credential != null && credential !== state) || observations.size >= 1_000) {
                invalidObservation = true
                return
            }
            credential = state
            observations += JSONObject().put("elapsedNanos", SystemClock.elapsedRealtimeNanos())
                .put("credentialIdentity", System.identityHashCode(state)).put("length", state.passphrase.length)
                .put("revealed", state.isRevealed).put("joinSuccessCount", model.joinSuccessCount.value)
                .put("joinResult", model.joinResult.value?.javaClass?.simpleName)
        }
    }

    private companion object {
        const val JOINED_TEXT = "Joined. Routing this app's traffic through the joined network. " +
            "Internet may be unavailable while joined."
        fun checkCleared(state: JoinCredentialInputState) { check(state.passphrase.isEmpty() && !state.isRevealed) }
        fun problem(stage: String, error: Throwable): JSONObject = JSONObject().put("stage", stage)
            .put("type", error.javaClass.name).put("message", error.message?.take(512))

        @Composable
        fun CredentialContent(mount: Mount) {
            val parent = checkNotNull(LocalSaveableStateRegistry.current)
            val child = remember { SaveableStateRegistry(mount.restored, parent::canBeSaved) }
            SideEffect { mount.registry = child }
            CompositionLocalProvider(
                LocalSaveableStateRegistry provides child,
                LocalActivityResultRegistryOwner provides mount.permissions
            ) {
                MaterialTheme {
                    Column(Modifier.fillMaxSize().padding(16.dp)) {
                        if (mount.show.value) JoinHotspotCard(mount.model, mount::observe)
                    }
                }
            }
        }
    }
}
