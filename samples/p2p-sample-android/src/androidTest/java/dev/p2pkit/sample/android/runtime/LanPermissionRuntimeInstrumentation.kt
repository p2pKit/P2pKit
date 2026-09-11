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
        check(app.checkSelfPermission("android.permission.NEARBY_WIFI_DEVICES") == PackageManager.PERMISSION_DENIED)
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
        coroutineScope {
            val automaticStart = async(Dispatchers.Main.immediate, start = CoroutineStart.UNDISPATCHED) {
                vm.isStarting.first { it }
            }
            try {
                clickPermissionAllow()
                waitText(AVAILABLE)
                // Foreground refresh alone can publish AVAILABLE even if ActivityResult was lost.
                await("request-result-ui-settled") { permissionRequestSettled() }
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
    }

    private suspend fun rawDenied(route: Network, host: String, port: Int): Boolean = withContext(Dispatchers.IO) {
        stage = "pregrant-raw-socket"
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
        putString("test", "permissionRecreationAndPinnedTcp")
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

    private fun permissionRequestSettled(): Boolean {
        val waiting = node {
            it.packageName?.toString() == PACKAGE && it.text?.toString() == "Waiting for LAN access…"
        }
        if (waiting != null) return false
        val refresh = node {
            it.packageName?.toString() == PACKAGE && it.text?.toString() == "Refresh LAN access"
        } ?: return false
        // Compose may expose an enabled Text child of a disabled button; inspect the actual button owner.
        val button = generateSequence(refresh) { it.parent }.take(6)
            .takeWhile { it.packageName?.toString() == PACKAGE }
            .firstOrNull { it.className?.toString() == "android.widget.Button" } ?: return false
        return button.isVisibleToUser && button.isEnabled && button.isClickable
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
