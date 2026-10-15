package dev.p2pkit.sample.android.rpclab

import java.io.File
import kotlin.test.Test
import kotlin.test.assertFalse
import kotlin.test.assertTrue

/** Source-wiring controls supplement state-machine tests; they are not device navigation/Back evidence. */
class RpcLabSectionIntegrationTest {
    private val root get() = generateSequence(File(checkNotNull(System.getProperty("user.dir")))) { it.parentFile }
        .first { File(it, "settings.gradle.kts").isFile }
    private fun source(path: String) = File(root, "samples/p2p-sample-android/src/$path").readText()
    private fun debug(file: String) = source("debug/java/dev/p2pkit/sample/android/rpclab/$file.kt")

    @Test fun mainAppEmbedsRpcAndRechecksAdmissionWithoutLaunchingAnotherActivity() {
        val main = source("main/java/dev/p2pkit/sample/android/MainActivity.kt")
        val app = main.substringAfter("private fun P2pKitSampleApp(")
            .substringBefore("private fun LanPermissionStatus(")
        assertTrue(app.contains("if (entry != null && sampleRpcAvailable)"))
        assertTrue(app.contains("SampleRpcSection(entry, onExit = { if (vm.leaveRpcSection(entry)) " +
            "showDiagnostics = false })"))
        assertTrue(app.contains("vm.enterRpcSection()"))
        assertTrue(app.contains("enabled = admission.canEnterRpc"))
        assertTrue(app.contains("lifecycle.currentState.isAtLeast(Lifecycle.State.RESUMED)"))
        assertTrue(app.contains("AndroidDiagnosticsScreen("))
        assertTrue(app.contains("SetupScreen("))
        assertTrue(app.contains("RoomScreen("))
        assertFalse(app.contains("startActivity"))
        assertTrue(source("debug/java/dev/p2pkit/sample/android/SampleRpcSection.kt")
            .contains("RpcLabContent(activity, entry, onExit)"))
        val release = source("release/java/dev/p2pkit/sample/android/SampleRpcSection.kt")
        assertTrue(release.contains("sampleRpcAvailable = false"))
        assertFalse(release.contains("import dev.p2pkit.rpc"))
        assertFalse(release.contains("import dev.p2pkit.sample.rpc"))
        assertTrue(release.contains("sampleRpcRuntimeOccupied(): Boolean = false"))
        val debugAdapter = source("debug/java/dev/p2pkit/sample/android/SampleRpcSection.kt")
        assertTrue(debugAdapter.contains("sampleRpcRuntimeOccupied(): Boolean = RpcLabProcessRuntime.owner.occupied"))
        assertTrue(debugAdapter.contains("RpcLabProcessRuntime.owner.state.map { it != null }"))
    }

    @Test fun bothEntryPointsShareLifecycleAndSingleConsumingBackPolicy() {
        val content = debug("RpcLabContent")
        assertTrue(content.contains("BackHandler { controller?.requestLeave() }"))
        assertTrue(content.contains("activity.lifecycle.addObserver(owned)"))
        assertTrue(content.contains("activity.lifecycle.removeObserver(owned)"))
        assertTrue(content.contains("owned.detach()"))
        assertTrue(content.contains("if (controller === owned) controller = null"))
        val controller = debug("RpcLabActivity")
        val shortcut = controller.substringBefore("internal class RpcLabController(")
        assertTrue(shortcut.contains("Intent(this, MainActivity::class.java).setAction(SAMPLE_OPEN_RPC_ACTION)"))
        assertFalse(shortcut.contains("setContent"))
        assertFalse(shortcut.contains("RpcLabContent("))
        assertTrue(controller.contains("TextButton(::requestLeave)"))
        assertTrue(controller.contains("foreground && !detached && leave.phase == RpcLabLeaveGate.Phase.Active"))
        assertTrue(controller.contains("if (busy || !interactive || runtimeOwner.failure != null) return"))
        assertTrue(controller.contains("if (!interactive) return@launch"))
        assertTrue(controller.contains("SampleProcessOwnership.owner.withCurrent(sectionToken)"))
        assertTrue(controller.contains("Button({ if (interactive) stop() }"))
        val leave = controller.substringAfter("private fun cleanupBeforeLeave(").substringBefore("fun Content()")
        assertTrue(leave.indexOf("pending?.join()") < leave.indexOf("leave.complete("))
        assertTrue(leave.contains("!runtimeOwner.occupied && !closing && lab == null"))
        assertTrue(leave.contains("foreground && !detached"))
        assertTrue(leave.contains("if (leave.complete(token, succeeded, foreground && !detached)) onExit()"))
    }

    @Test fun entryDisposalInvalidatesCallbacksAndPreservesPreexistingWindowProtection() {
        val controller = debug("RpcLabActivity")
        val detach = controller.substringAfter("fun detach()").substringBefore("private fun presentStartProblem(")
        assertTrue(detach.contains("if (detached) return"))
        assertTrue(detach.indexOf("leave.detach()") < detach.indexOf("stop(runtimeOwner.snapshotFor(ownedToken))"))
        assertTrue(detach.contains("unregisterReceiver(screenOff)"))
        assertTrue(detach.contains("networkSetup.close()"))
        assertTrue(detach.contains("appSwitch.close()"))
        assertTrue(detach.indexOf("stop(runtimeOwner.snapshotFor(ownedToken))") < detach.indexOf("ui.cancel()"))
        assertTrue(detach.contains("previousWindowFlags and WindowManager.LayoutParams.FLAG_SECURE == 0"))
        assertTrue(detach.contains("previousWindowFlags and WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON == 0"))
    }
}
