package dev.p2pkit.sample.android.runtime

import android.accessibilityservice.AccessibilityServiceInfo
import android.app.Activity
import android.app.Application
import android.app.Instrumentation
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.net.ConnectivityManager
import android.net.Network
import android.net.NetworkCapabilities
import android.os.Build
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.os.Process
import android.os.SystemClock
import android.system.ErrnoException
import android.system.OsConstants
import android.view.accessibility.AccessibilityNodeInfo
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.ViewModelProvider
import dev.p2pkit.core.AppId
import dev.p2pkit.core.ConnectionState
import dev.p2pkit.core.ExperimentalP2pApi
import dev.p2pkit.core.P2pError
import dev.p2pkit.core.P2pKit
import dev.p2pkit.core.P2pMessage
import dev.p2pkit.core.PeerFingerprint
import dev.p2pkit.core.permission.P2pPermission
import dev.p2pkit.provisioning.android.android
import dev.p2pkit.sample.android.MainActivity
import dev.p2pkit.sample.android.P2pKitSampleApplication
import dev.p2pkit.sample.android.P2pKitViewModel
import dev.p2pkit.sample.diagnostics.SampleConsole
import dev.p2pkit.transport.lan.lan
import java.net.InetSocketAddress
import java.net.SocketTimeoutException
import java.util.concurrent.CopyOnWriteArrayList
import java.util.concurrent.FutureTask
import java.util.concurrent.TimeUnit
import kotlinx.coroutines.CoroutineStart
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.NonCancellable
import kotlinx.coroutines.async
import kotlinx.coroutines.cancelAndJoin
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withContext
import kotlinx.coroutines.withTimeout

/** A single real API37 case. Never grant permissions by shell identity or replace production implementations. */
class LanPermissionRuntimeInstrumentation : Instrumentation() {
    private lateinit var arguments: Bundle
    private var stage = "admission"
    private val result = Bundle()
    private val witness = Activities()
    private var application: Application? = null
    private var kit: P2pKit? = null
    private val mode: String? get() = arguments.getString("mode")

    override fun onCreate(arguments: Bundle?) {
        super.onCreate(arguments)
        this.arguments = Bundle(arguments ?: Bundle())
        start()
    }

    override fun onStart() {
        super.onStart()
        result.putString("p2pkitToken", arguments.getString("token"))
        result.putString("p2pkitRecreation", "NOT_RUN")
        result.putString("p2pkitRequestSettled", "false")
        result.putString("p2pkitOriginalRequestOutstanding", "false")
        result.putString("p2pkitManager", "NOT_RUN")
        result.putString("p2pkitTraffic", "NOT_RUN")
        result.putString("p2pkitRawRoute", "NOT_COMPLETED")
        result.putString("p2pkitSameInstanceRevocation", "NOT_EXECUTED")
        sendStatus(1, testStatus())
        var failure: Throwable? = null
        runBlocking {
            try {
                withTimeout(90_000) { exercise() }
            } catch (error: Throwable) {
                failure = error
                result.putString("p2pkitFailureStage", stage)
                result.putString("p2pkitFailureType", error.javaClass.simpleName)
                result.putString("p2pkitFailureTypes", generateSequence(error) { it.cause }.take(8)
                    .joinToString(">") { it.javaClass.simpleName })
                val frames = error.stackTrace.filter {
                    it.className.startsWith(LanPermissionRuntimeInstrumentation::class.java.name)
                }
                result.putString("p2pkitFailureFrames", frames.take(8)
                    .joinToString(";") { "${it.methodName}:${it.lineNumber}" })
            } finally {
                // A failed stop must not be hidden by the earlier behavioral outcome.
                try {
                    withContext(NonCancellable) {
                        withTimeout(15_000) { kit?.stop() }
                    }
                    main {
                        witness.created.filterNot { it.isDestroyed }.forEach { it.finish() }
                    }
                    withContext(NonCancellable) {
                        withTimeout(10_000) {
                            while (!main { witness.created.all { it.isDestroyed } }) delay(100)
                        }
                    }
                    result.putString("p2pkitCleanup", "PASS")
                } catch (error: Throwable) {
                    if (failure == null) failure = error
                    result.putString("p2pkitCleanup", "FAIL")
                    result.putString("p2pkitCleanupFailureType", error.javaClass.simpleName)
                } finally {
                    try {
                        main { application?.unregisterActivityLifecycleCallbacks(witness) }
                    } catch (error: Throwable) {
                        if (failure == null) failure = error
                        result.putString("p2pkitCleanup", "FAIL")
                        result.putString("p2pkitCleanupFailureType", error.javaClass.simpleName)
                    }
                }
            }
        }
        result.putString("p2pkitOutcome", if (failure == null) "PASS" else "FAIL")
        result.putString("p2pkitCompleted", "1")
        val terminal = testStatus().apply {
            if (failure != null) {
                putString("stack", "${failure.javaClass.simpleName} at $stage; inspect phase evidence")
            }
        }
        sendStatus(if (failure == null) 0 else -2, terminal)
        finish(if (failure == null) Activity.RESULT_OK else Activity.RESULT_CANCELED, result)
    }

    @OptIn(ExperimentalP2pApi::class)
    private suspend fun exercise() {
        check(mode == null || mode == LanPermissionRevocation.MODE || mode == LanPermissionRevocation.REENTRY)
        val token = argument("token").also { check(it.matches(Regex("[0-9a-f]{32}"))) }
        val host = argument("host").also { check(it == "10.0.2.2") }
        val controlPort = argument("controlPort").toInt().also { check(it in 1024..65535) }
        val cliPort = argument("cliPort").toInt().also { check(it in 1024..65535 && it != controlPort) }
        val fingerprint = checkNotNull(PeerFingerprint.parseOrNull(argument("fingerprint")))
        val app = main { targetContext.applicationContext as P2pKitSampleApplication }
        application = app
        check(Build.VERSION.SDK_INT == 37 && app.applicationInfo.targetSdkVersion == 37)
        check(app.packageName == PACKAGE && Process.myUid() == app.applicationInfo.uid)
        check(app.checkSelfPermission(PERMISSION) == PackageManager.PERMISSION_DENIED)
        if (mode != LanPermissionRevocation.REENTRY) {
            check(app.checkSelfPermission("android.permission.NEARBY_WIFI_DEVICES") == PackageManager.PERMISSION_DENIED)
        }
        if (mode != null) {
            stage = "ordinary-uid-mandatory-flag-readback"
            LanPermissionRevocation.profile(app, arguments)
        }
        val permissionExit = if (mode == LanPermissionRevocation.REENTRY) {
            stage = "permission-driven-os-exit-attribution"
            LanPermissionRevocation.requirePermissionDrivenExit(app, arguments)
        } else null
        val pid = Process.myPid()
        val processStart = Process.getStartElapsedRealtime()
        result.putString("p2pkitPid", pid.toString())
        result.putString("p2pkitProcessStart", processStart.toString())
        result.putString("p2pkitUid", Process.myUid().toString())
        val connectivity = app.getSystemService(Context.CONNECTIVITY_SERVICE) as ConnectivityManager
        val route = checkNotNull(connectivity.activeNetwork)
        val capabilities = checkNotNull(connectivity.getNetworkCapabilities(route))
        check(!capabilities.hasTransport(NetworkCapabilities.TRANSPORT_VPN))
        check(capabilities.hasTransport(NetworkCapabilities.TRANSPORT_WIFI) ||
            capabilities.hasTransport(NetworkCapabilities.TRANSPORT_ETHERNET))
        result.putString("p2pkitNetwork", route.networkHandle.toString())
        val owned = P2pKit.create {
            appId = AppId("p2pkit-art-$token")
            deviceName = "Android ART permission case"
            transports { lan(app) }
            networkProvisioning { android(app) }
        }
        kit = owned
        val manager = owned.permissions
        check(manager.requiredPermissions() == listOf(P2pPermission.LocalNetwork))
        check(manager.missingPermissions() == listOf(P2pPermission.LocalNetwork))
        check(!manager.hasRequiredPermissions())
        try {
            owned.startAdvertising()
            error("Denied feature acquired resources")
        } catch (expected: P2pError.PermissionMissing) {
            check(expected.permissions == listOf(P2pPermission.LocalNetwork))
        }
        phase("default-manager-denied")
        val rawDenied = rawDenied(route, host, controlPort)
        result.putString("p2pkitRawPregrant", if (rawDenied) "DENIED" else "BYPASSED")
        phase(if (rawDenied) "raw-denied" else "raw-bypassed")

        main {
            app.registerActivityLifecycleCallbacks(witness)
            app.startActivity(Intent(app, MainActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
        }
        await("initial-main-activity") { witness.created.size == 1 }
        waitText(MISSING)
        val old = witness.created.single()
        val vm = main { ViewModelProvider(old)[P2pKitViewModel::class.java] }
        check(!vm.isRunning.value && !vm.isStarting.value && !vm.isStopping.value && !vm.cleanupPending.value)
        coroutineScope {
            val started = async(Dispatchers.Main.immediate, start = CoroutineStart.UNDISPATCHED) {
                vm.isStarting.first { it }
            }
            try {
                tap("Start", scroll = true)
                withTimeout(10_000) { started.await() }
                await("denied-sample-start-settled") {
                    !vm.isStarting.value && !vm.isStopping.value && !vm.isRunning.value && !vm.cleanupPending.value
                }
            } finally {
                started.cancelAndJoin()
            }
        }
        waitText(MISSING)
        if (mode == LanPermissionRevocation.REENTRY) {
            check(rawDenied) { "Revoked process reentry raw socket bypassed LAN protection" }
            check(manager.missingPermissions() == listOf(P2pPermission.LocalNetwork) && !manager.hasRequiredPermissions())
            LanPermissionRevocation.retainReentry(app, arguments, checkNotNull(permissionExit)
                .put("defaultManagerDenied", true).put("rawSocketDenied", true).put("sampleStartDenied", true))
            result.putString("p2pkitManager", "PASS")
            result.putString("p2pkitReentry", "DENIED_AFTER_ATTRIBUTABLE_PERMISSION_KILL")
            result.putString("p2pkitSameInstanceRevocation", "OS_PERMISSION_KILL_NOT_SAME_INSTANCE")
            return
        }
        tap("Grant LAN access")
        waitPermissionDialog()
        phase("request-outstanding")
        main { old.recreate() }
        await("recreated-before-answer") {
            witness.created.size == 2 && witness.destroyed.any { it === old }
        }
        val replacement = witness.created.last()
        check(replacement !== old)
        check(main { ViewModelProvider(replacement)[P2pKitViewModel::class.java] === vm })
        check(Process.myPid() == pid && Process.getStartElapsedRealtime() == processStart)
        check(app.checkSelfPermission(PERMISSION) == PackageManager.PERMISSION_DENIED)
        waitPermissionDialog() // Still outstanding, not a callback followed by an unrelated recreation.
        result.putString("p2pkitRetainedVm", "true")
        result.putString("p2pkitActivities", witness.created.size.toString())
        result.putString("p2pkitDestroyed", witness.destroyed.size.toString())
        phase("recreated-still-outstanding")
        check(main { vm.lanPermissionState.value.requestInFlight })
        result.putString("p2pkitOriginalRequestOutstanding", "true")
        coroutineScope {
            val automaticStart = async(Dispatchers.Main.immediate, start = CoroutineStart.UNDISPATCHED) {
                vm.isStarting.first { it }
            }
            try {
                clickPermissionAllow()
                waitText(AVAILABLE)
                // Foreground refresh alone can publish AVAILABLE even if ActivityResult was lost.
                await("request-result-ui-settled") { permissionRequestSettled(vm, replacement) }
                check(app.checkSelfPermission(PERMISSION) == PackageManager.PERMISSION_GRANTED)
                result.putString("p2pkitRequestSettled", "true")
                // Observe transitions too, not just a snapshot before a queued automatic start.
                repeat(10) {
                    check(!automaticStart.isCompleted && !vm.isRunning.value && !vm.isStarting.value &&
                        !vm.isStopping.value && !vm.cleanupPending.value)
                    delay(100)
                }
            } finally {
                automaticStart.cancelAndJoin()
            }
        }
        check(Process.myPid() == pid && Process.getStartElapsedRealtime() == processStart)
        check(main { ViewModelProvider(replacement)[P2pKitViewModel::class.java] === vm })
        result.putString("p2pkitRecreation", "PASS")
        check(kit === owned && owned.permissions === manager)
        check(manager.requiredPermissions() == listOf(P2pPermission.LocalNetwork))
        check(manager.missingPermissions().isEmpty() && manager.hasRequiredPermissions())
        result.putString("p2pkitManager", "PASS")
        phase("same-manager-granted-no-replay")
        check(connectivity.activeNetwork == route)
        rawExchange(route, host, controlPort, token)
        result.putString("p2pkitRawRoute", if (rawDenied) "DENIED_THEN_ADMITTED" else "PREGRANT_BYPASS")
        phase("raw-granted")

        stage = "real-feature-and-pinned-connect"
        owned.startAdvertising()
        val peer = owned.networkProvisioning.createManualPeer(host, cliPort, fingerprint)
        val session = owned.connect(peer, fingerprint)
        withTimeout(20_000) { session.state.first { it == ConnectionState.Connected } }
        check(session.peerIdentity.fingerprint == fingerprint)
        result.putString("p2pkitLocalAlias", SampleConsole.identifier(owned.localPeerId.value))
        result.putString("p2pkitPeerFingerprint", session.peerIdentity.fingerprint?.value)
        coroutineScope {
            val incoming = async(start = CoroutineStart.UNDISPATCHED) { session.incoming.first() }
            try {
                val outbound = "android-$token"
                session.send(P2pMessage.Text(outbound))
                result.putString("p2pkitSentBytes", outbound.toByteArray(Charsets.UTF_8).size.toString())
                phase("message-sent")
                val received = withTimeout(20_000) { incoming.await() }
                check(received is P2pMessage.Text && received.value == "jvm-$token")
                result.putString("p2pkitReceivedBytes", received.value.toByteArray(Charsets.UTF_8).size.toString())
                check(session.state.value == ConnectionState.Connected)
            } finally {
                incoming.cancelAndJoin()
            }
        }
        result.putString("p2pkitTraffic", "PASS")
        phase("bidirectional-delivery")
        // Salvage the independent UI/traffic witnesses above, but NEVER pass an exempt/bypassed route.
        stage = "raw-enforcement-admission"
        check(rawDenied)
        if (mode == LanPermissionRevocation.MODE) {
            LanPermissionRevocation.checkpoint(app, arguments, result, System.identityHashCode(manager))
            phase("awaiting-host-os-revocation")
            await("live-local-network-revocation") {
                app.checkSelfPermission(PERMISSION) == PackageManager.PERMISSION_DENIED
            }
            check(Process.myPid() == pid && Process.getStartElapsedRealtime() == processStart)
            check(kit === owned && owned.permissions === manager)
            check(manager.missingPermissions() == listOf(P2pPermission.LocalNetwork) && !manager.hasRequiredPermissions())
            try {
                owned.startDiscovery() // Not already active: genuine post-revocation feature preflight.
                error("Revoked feature acquired resources")
            } catch (expected: P2pError.PermissionMissing) {
                check(expected.permissions == listOf(P2pPermission.LocalNetwork))
            }
            check(rawDenied(route, host, controlPort, "post-revocation-raw-socket"))
            main { replacement.recreate() }
            await("revoked-activity-reentered") {
                witness.created.size == 3 && witness.destroyed.any { it === replacement }
            }
            waitText(MISSING)
            check(main { ViewModelProvider(witness.created.last())[P2pKitViewModel::class.java] === vm })
            check(!vm.isRunning.value && !vm.isStarting.value && !vm.isStopping.value && !vm.cleanupPending.value)
            result.putString("p2pkitSameInstanceRevocation", "PASS")
            result.putString("p2pkitReentry", "DENIED_SAME_MANAGER_AND_PROCESS")
            result.putString("p2pkitActivities", witness.created.size.toString())
            result.putString("p2pkitDestroyed", witness.destroyed.size.toString())
            phase("same-manager-revoked-and-reentered")
        }
    }

    private suspend fun rawDenied(
        route: Network,
        host: String,
        port: Int,
        label: String = "pregrant-raw-socket"
    ): Boolean = withContext(Dispatchers.IO) {
        stage = label
        try {
            route.socketFactory.createSocket().use { it.connect(InetSocketAddress(host, port), 1_500) }
            false
        } catch (error: Exception) {
            val permissionErrno = generateSequence<Throwable>(error) { it.cause }.take(8)
                .filterIsInstance<ErrnoException>()
                .any { it.errno == OsConstants.EACCES || it.errno == OsConstants.EPERM }
            check(error is SocketTimeoutException || permissionErrno) { "Not a permission-compatible socket failure" }
            result.putString("p2pkitRawDenialType", if (permissionErrno) "PERMISSION_ERRNO" else "TCP_TIMEOUT")
            true
        }
    }

    private suspend fun rawExchange(route: Network, host: String, port: Int, token: String) =
        withContext(Dispatchers.IO) {
            stage = "postgrant-raw-socket"
            route.socketFactory.createSocket().use { socket ->
                socket.soTimeout = 2_000
                socket.connect(InetSocketAddress(host, port), 2_000)
                socket.getOutputStream().write("$token\n".toByteArray(Charsets.US_ASCII))
                val expected = "ack-$token\n".toByteArray(Charsets.US_ASCII)
                val actual = ByteArray(expected.size)
                val input = socket.getInputStream()
                var offset = 0
                while (offset < actual.size) {
                    val read = input.read(actual, offset, actual.size - offset)
                    check(read > 0)
                    offset += read
                }
                check(actual.contentEquals(expected) && input.read() == -1)
            }
        }

    private fun argument(name: String): String = checkNotNull(arguments.getString(name))

    private fun phase(name: String) {
        stage = name
        result.putString("p2pkitPhase", name)
        result.putString("p2pkitElapsed", SystemClock.elapsedRealtime().toString())
        sendStatus(2, testStatus())
    }

    private fun testStatus(): Bundle = Bundle(result).apply {
        putString("class", LanPermissionRuntimeInstrumentation::class.java.name)
        putString("test", when (mode) {
            LanPermissionRevocation.MODE -> "permissionRecreationPinnedTcpAndRevocation"
            LanPermissionRevocation.REENTRY -> "deniedReentryAfterPermissionDrivenExit"
            else -> "permissionRecreationAndPinnedTcp"
        })
        putInt("numtests", 1)
        putInt("current", 1)
    }

    private fun <T> main(block: () -> T): T {
        val task = FutureTask<T> { block() }
        check(Handler(Looper.getMainLooper()).post(task))
        return try {
            task.get(5, TimeUnit.SECONDS)
        } finally {
            task.cancel(false)
        }
    }

    private suspend fun await(label: String, condition: () -> Boolean) {
        stage = label
        withTimeout(15_000) {
            while (!condition()) delay(100)
        }
    }

    private fun node(predicate: (AccessibilityNodeInfo) -> Boolean): AccessibilityNodeInfo? {
        val info = uiAutomation.serviceInfo
        if (info.flags and AccessibilityServiceInfo.FLAG_REPORT_VIEW_IDS == 0) {
            info.flags = info.flags or AccessibilityServiceInfo.FLAG_REPORT_VIEW_IDS
            uiAutomation.serviceInfo = info
        }
        // Refresh only the observer cache, never application layout/state or input.
        check(uiAutomation.clearCache()) { "Fresh accessibility snapshot unavailable" }
        val root = uiAutomation.rootInActiveWindow ?: return null
        val pending = ArrayDeque<AccessibilityNodeInfo>()
        pending.add(root)
        val matches = mutableListOf<AccessibilityNodeInfo>()
        var count = 0
        while (pending.isNotEmpty()) {
            check(++count <= 1_500)
            val current = pending.removeFirst()
            if (current.isVisibleToUser && predicate(current)) matches += current
            repeat(current.childCount) { current.getChild(it)?.let(pending::add) }
        }
        check(matches.size <= 1) { "Ambiguous real UI target" }
        return matches.singleOrNull()
    }

    private suspend fun waitText(text: String) = await("ui-text") {
        node { it.packageName?.toString() == PACKAGE && it.text?.toString() == text } != null
    }

    private fun permissionRequestSettled(vm: P2pKitViewModel, replacement: MainActivity): Boolean {
        val state = vm.lanPermissionState.value
        check(uiAutomation.clearCache()) { "Fresh accessibility snapshot unavailable" }
        val root = uiAutomation.rootInActiveWindow
        val ownedWindow = root?.packageName?.toString() == PACKAGE && root.isVisibleToUser && main {
            replacement.lifecycle.currentState == Lifecycle.State.RESUMED && replacement.hasWindowFocus() &&
                ViewModelProvider(replacement)[P2pKitViewModel::class.java] === vm
        }
        val nodes = mutableListOf<AccessibilityNodeInfo>()
        if (ownedWindow) {
            val pending = ArrayDeque<AccessibilityNodeInfo>()
            pending.add(checkNotNull(root))
            while (pending.isNotEmpty()) {
                val current = pending.removeFirst()
                check(nodes.size < 1_500 && current.packageName?.toString() == PACKAGE)
                nodes += current
                repeat(current.childCount) { current.getChild(it)?.let(pending::add) }
            }
        }
        fun visible(text: String): AccessibilityNodeInfo? = nodes.filter {
            it.isVisibleToUser && it.text?.toString() == text
        }.also { check(it.size <= 1) { "Ambiguous permission UI target" } }.singleOrNull()
        val refresh = visible("Refresh LAN access")
        // Compose may place a legacy Button role on a fake child, not the click owner.
        // Its disabled owner stays clickable while ACTION_CLICK is omitted: locate
        // that structural owner first, so an enabled ancestor cannot hide a denial.
        val chain = mutableListOf<AccessibilityNodeInfo>()
        var ancestor = refresh
        while (ancestor != null && chain.size < 6) {
            val current = ancestor
            chain += current
            if (current == root || current.packageName?.toString() != PACKAGE ||
                current.windowId != root?.windowId || nodes.none { it == current }
            ) break
            ancestor = current.parent
        }
        val actionNodes = chain.map { current ->
            val actions = current.actionList.map { it.id }
            check(actions.size <= 32)
            LanPermissionActionNode(
                owned = current.packageName?.toString() == PACKAGE && current.windowId == root?.windowId &&
                    nodes.any { it == current },
                visible = current.isVisibleToUser,
                enabled = current.isEnabled,
                clickable = current.isClickable,
                clickAction = AccessibilityNodeInfo.ACTION_CLICK in actions,
                otherActivation = current.isLongClickable || AccessibilityNodeInfo.ACTION_LONG_CLICK in actions
            )
        }
        val ownerIndex = nearestLanPermissionActionOwner(actionNodes)
        val buttonReady = ownerIndex?.let { actionNodes[it].ready() } == true
        val observation = LanPermissionUiSettlement(
            originalRequestObserved = result.getString("p2pkitOriginalRequestOutstanding") == "true",
            ownedWindow = ownedWindow,
            visibleAnchor = visible("P2pKit Test Harness") != null,
            stateStable = vm.lanPermissionState.value == state,
            liveGrant = targetContext.checkSelfPermission(PERMISSION) == PackageManager.PERMISSION_GRANTED,
            requestInFlight = state.requestInFlight,
            missingEmpty = state.missing.isEmpty(),
            checkFailed = state.checkFailed,
            card = when (state.message) {
                AVAILABLE -> LanPermissionUiSettlement.Card.AVAILABLE
                null -> LanPermissionUiSettlement.Card.ABSENT
                else -> LanPermissionUiSettlement.Card.OTHER
            },
            waitingVisible = visible("Waiting for LAN access…") != null,
            grantVisible = visible("Grant LAN access") != null,
            missingVisible = visible(MISSING) != null,
            availableVisible = visible(AVAILABLE) != null,
            cardExplanationVisible = visible(
                "Permission results only update access status. Tap Start, KMP smoke, Connect or a switch again."
            ) != null,
            refreshVisible = refresh != null,
            refreshButtonReady = buttonReady
        )
        // Fixed predicate ingredients only: no arbitrary screen text/payloads. Retained
        // in the original encrypted terminal on failure as well as successful handoff.
        result.putString("p2pkitRequestUiObservation", observation.toString())
        result.putString("p2pkitRequestUiButton", "ownerIndex=$ownerIndex;ready=$buttonReady;" +
            chain.indices.joinToString(";") { index ->
                val current = chain[index]
                val role = current.className?.toString().let {
                    if (it in setOf("android.view.View", "android.widget.TextView", "android.widget.Button")) it
                    else "OTHER"
                }
                "$index:role=$role,actions=${current.actionList.map { it.id }},${actionNodes[index]}"
            })
        return observation.settled()
    }

    private suspend fun tap(text: String, scroll: Boolean = false) {
        var scrolls = 0
        var target: AccessibilityNodeInfo? = null
        await("tap-$text") {
            target = node { it.packageName?.toString() == PACKAGE && it.text?.toString() == text }
            if (target == null && scroll && scrolls < 4) {
                node { it.packageName?.toString() == PACKAGE && it.isScrollable && it.isEnabled }?.let {
                    if (it.performAction(AccessibilityNodeInfo.ACTION_SCROLL_FORWARD)) scrolls++
                }
            }
            target != null
        }
        val clickable = generateSequence(target) { it.parent }.take(6).firstOrNull {
            it.packageName?.toString() == PACKAGE && it.isEnabled && it.isClickable
        }
        check(checkNotNull(clickable).performAction(AccessibilityNodeInfo.ACTION_CLICK))
    }

    private fun permissionButton(): AccessibilityNodeInfo? = node {
        it.packageName?.toString() in PERMISSION_PACKAGES &&
            it.viewIdResourceName?.endsWith(":id/permission_allow_button") == true && it.isEnabled && it.isClickable
    }

    private suspend fun waitPermissionDialog() = await("actual-permission-dialog") { permissionButton() != null }

    private fun clickPermissionAllow() {
        check(checkNotNull(permissionButton()).performAction(AccessibilityNodeInfo.ACTION_CLICK))
    }

    private class Activities : Application.ActivityLifecycleCallbacks {
        val created = CopyOnWriteArrayList<MainActivity>()
        val destroyed = CopyOnWriteArrayList<MainActivity>()
        override fun onActivityCreated(activity: Activity, state: Bundle?) {
            if (activity is MainActivity) created += activity
        }
        override fun onActivityDestroyed(activity: Activity) {
            if (activity is MainActivity) destroyed += activity
        }
        override fun onActivityStarted(activity: Activity) = Unit
        override fun onActivityResumed(activity: Activity) = Unit
        override fun onActivityPaused(activity: Activity) = Unit
        override fun onActivityStopped(activity: Activity) = Unit
        override fun onActivitySaveInstanceState(activity: Activity, state: Bundle) = Unit
    }

    private companion object {
        const val PACKAGE = "dev.p2pkit.sample.android"
        const val PERMISSION = "android.permission.ACCESS_LOCAL_NETWORK"
        const val MISSING = "LAN access is missing. Grant access, then tap the intended action again."
        const val AVAILABLE = "LAN access is available. Tap the intended action again."
        val PERMISSION_PACKAGES = setOf("com.android.permissioncontroller", "com.google.android.permissioncontroller")
    }
}
