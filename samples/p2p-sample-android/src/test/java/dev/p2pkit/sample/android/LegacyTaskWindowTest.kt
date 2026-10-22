package dev.p2pkit.sample.android

import android.app.Activity
import android.view.WindowManager
import java.io.File
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue
import org.junit.runner.RunWith
import org.robolectric.Robolectric
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

/** API35 host framework only: verifies flag application, not API24/32 snapshot behavior. */
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [35], manifest = Config.NONE)
class LegacyTaskWindowTest {
    @Test
    fun installsSecureWithoutRemovingOtherWindowFlags() {
        val controller = Robolectric.buildActivity(Activity::class.java).setup()
        try {
            val window = controller.get().window
            window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
            val prior = window.attributes.flags
            secureLegacyTaskWindow(window)
            assertEquals(prior or WindowManager.LayoutParams.FLAG_SECURE, window.attributes.flags)
            secureLegacyTaskWindow(window)
            assertEquals(prior or WindowManager.LayoutParams.FLAG_SECURE, window.attributes.flags)
        } finally { controller.pause().stop().destroy() }
    }

    @Test
    fun legacyFlagSurvivesStopAndResume() {
        val controller = Robolectric.buildActivity(Activity::class.java).setup()
        try {
            secureLegacyTaskWindow(controller.get().window)
            controller.pause().stop().restart().start().resume()
            assertTrue(controller.get().window.attributes.flags and WindowManager.LayoutParams.FLAG_SECURE != 0)
        } finally { controller.pause().stop().destroy() }
    }

    @Test
    fun productionInstallsOnlyLegacyBranchBeforeAnyContentAndNeverClearsTheFlag() {
        val source = locateMainActivity().readText()
        val onCreate = source.substringAfter("override fun onCreate(").substringBefore("override fun onStart(")
        assertTrue(onCreate.contains("if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU)"))
        assertTrue(onCreate.contains("setRecentsScreenshotEnabled(false)\n        } else {\n" +
            "            secureLegacyTaskWindow(window)"))
        assertTrue(onCreate.indexOf("secureLegacyTaskWindow(window)") < onCreate.indexOf("setContent {"))
        assertEquals(1, Regex("secureLegacyTaskWindow\\(window\\)").findAll(source).count())
        assertTrue(!source.contains("clearFlags(") && !source.contains("setRecentsScreenshotEnabled(true)"))
    }

    private fun locateMainActivity(): File {
        var root: File? = File(checkNotNull(System.getProperty("user.dir")))
        val relative = "src/main/java/dev/p2pkit/sample/android/MainActivity.kt"
        while (root != null) {
            listOf(File(root, relative), File(root, "samples/p2p-sample-android/$relative"))
                .firstOrNull { it.isFile }?.let { return it }
            root = root.parentFile
        }
        error("MainActivity source missing")
    }
}
