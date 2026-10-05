package dev.p2pkit.sample.android.rpclab

import android.app.Notification
import android.app.Service
import android.content.ComponentName
import android.content.ContextWrapper
import android.content.Intent
import java.io.File
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertNotNull
import kotlin.test.assertTrue
import org.junit.runner.RunWith
import org.robolectric.Robolectric
import org.robolectric.RobolectricTestRunner
import org.robolectric.RuntimeEnvironment
import org.robolectric.Shadows.shadowOf
import org.robolectric.annotation.Config

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [35], manifest = Config.NONE)
class RpcLabShareServiceTest {
    private class Context : ContextWrapper(RuntimeEnvironment.getApplication()) {
        var started: Intent? = null
        var stopped = 0
        var deny = false
        override fun getApplicationContext(): android.content.Context = this
        override fun startForegroundService(service: Intent): ComponentName {
            check(!deny)
            started = service
            return checkNotNull(service.component)
        }
        override fun stopService(service: Intent): Boolean { stopped++; return true }
    }

    @Test
    fun matchingLeaseStartsOnlyShortForegroundExecutionWithASecretFreeNotification() {
        val context = Context()
        val execution = RpcLabShareService.execution(context)
        var expirations = 0
        assertTrue(execution.begin { expirations++ })
        val intent = assertNotNull(context.started)
        assertEquals(1, assertNotNull(intent.extras).size())
        val controller = Robolectric.buildService(RpcLabShareService::class.java).create()
        try {
            val service = controller.get()
            assertEquals(Service.START_NOT_STICKY, service.onStartCommand(intent, 0, 7))
            val notification = assertNotNull(shadowOf(service).lastForegroundNotification)
            assertEquals("P2pKit RPC sharing window", notification.extras.getString(Notification.EXTRA_TITLE))
            assertEquals("Return to RPC within 25 seconds. The role stops automatically.",
                notification.extras.getString(Notification.EXTRA_TEXT))
            assertEquals(0, expirations)
            execution.end()
            assertEquals(1, context.stopped)
        } finally { execution.end(); controller.destroy() }
        assertEquals(0, expirations)
    }

    @Test
    fun anAbsentOrRetiredLeaseCannotRestartAServiceOrRole() {
        val context = Context()
        val execution = RpcLabShareService.execution(context)
        assertTrue(execution.begin { error("Retired lease must not expire again") })
        val old = assertNotNull(context.started)
        execution.end()
        val controller = Robolectric.buildService(RpcLabShareService::class.java).create()
        try {
            val service = controller.get()
            assertEquals(Service.START_NOT_STICKY, service.onStartCommand(old, 0, 1))
            assertTrue(shadowOf(service).isStoppedBySelf)
            assertEquals(Service.START_NOT_STICKY, service.onStartCommand(null, 0, 2))
        } finally { controller.destroy() }
    }

    @Test
    fun serviceDestructionExpiresItsExactLeaseOnceButCannotAffectAReplacement() {
        val context = Context()
        val execution = RpcLabShareService.execution(context)
        var expirations = 0
        assertTrue(execution.begin { expirations++ })
        val controller = Robolectric.buildService(RpcLabShareService::class.java).create()
        controller.get().onStartCommand(context.started, 0, 3)
        controller.destroy()
        assertEquals(1, expirations)
        execution.end()
        assertTrue(execution.begin { expirations++ })
        controller.get().onDestroy()
        assertEquals(1, expirations)
        execution.end()
    }

    @Test
    fun deniedStartDoesNotRetainAProcessLeaseAndTaskRemovalOrSystemTimeoutStopsIt() {
        val context = Context()
        val execution = RpcLabShareService.execution(context)
        context.deny = true
        assertFalse(execution.begin { error("No admitted execution") })
        context.deny = false
        var expirations = 0
        assertTrue(execution.begin { expirations++ })
        val controller = Robolectric.buildService(RpcLabShareService::class.java).create()
        try {
            val service = controller.get()
            service.onStartCommand(context.started, 0, 9)
            service.onTimeout(8)
            assertEquals(0, expirations)
            service.onTaskRemoved(null)
            service.onTimeout(9)
            service.onTimeout(9, 0)
            assertEquals(1, expirations)
            assertTrue(shadowOf(service).isStoppedBySelf)
        } finally { execution.end(); controller.destroy() }
    }

    @Test
    fun actualActivityManifestAndLeaseKeepDebugScopeScreenLockAndOwnershipBoundaries() {
        val root = generateSequence(File(checkNotNull(System.getProperty("user.dir")))) { it.parentFile }
            .first { File(it, "settings.gradle.kts").isFile }
        val sample = File(root, "samples/p2p-sample-android")
        val source = File(sample, "src/debug/java/dev/p2pkit/sample/android/rpclab/RpcLabActivity.kt").readText()
        val pause = source.substringAfter("override fun onPause()").substringBefore("override fun onStop()")
        assertTrue(pause.contains("mobileConfig == null && capacityPins.isEmpty() && !importApproved"))
        assertTrue(pause.contains("creating = snapshot?.creator != null, busy = busy"))
        assertTrue(pause.contains("operationActive = operation?.active == true"))
        assertTrue(pause.contains("PowerManager::class.java).isInteractive"))
        assertTrue(pause.contains("KeyguardManager::class.java).isKeyguardLocked"))
        assertTrue(pause.indexOf("appSwitch.begin(") < pause.indexOf("super.onPause()"))
        val lock = source.substringAfter("private val screenOff").substringBefore("override fun onCreate")
        assertTrue(lock.contains("Intent.ACTION_SCREEN_OFF"))
        assertTrue(lock.contains("stop(runtimeOwner.snapshotFor(ownedToken))"))
        val destroy = source.substringAfter("override fun onDestroy()").substringBefore("private fun presentStartProblem")
        assertTrue(destroy.contains("unregisterReceiver(screenOff)"))
        assertTrue(destroy.contains("appSwitch.close()"))
        assertTrue(destroy.contains("stop(runtimeOwner.snapshotFor(ownedToken))"))
        val manifest = File(sample, "src/debug/AndroidManifest.xml").readText()
        assertTrue(manifest.contains("android.permission.FOREGROUND_SERVICE"))
        assertTrue(manifest.contains("android:foregroundServiceType=\"shortService\""))
        val service = manifest.substringAfter("<service").substringBefore("/>")
        assertTrue(service.contains("android:exported=\"false\""))
        assertTrue(service.contains("android:stopWithTask=\"true\""))
        assertFalse(File(sample, "src/main/AndroidManifest.xml").readText().contains("RpcLabShareService"))
        assertFalse(manifest.contains("POST_NOTIFICATIONS"))
    }
}
