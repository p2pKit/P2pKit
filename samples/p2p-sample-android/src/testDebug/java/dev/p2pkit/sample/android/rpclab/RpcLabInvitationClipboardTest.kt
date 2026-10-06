package dev.p2pkit.sample.android.rpclab

import android.content.ClipData
import android.content.ClipboardManager
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertTrue
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.RuntimeEnvironment
import org.robolectric.annotation.Config

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [35], manifest = Config.NONE)
class RpcLabInvitationClipboardTest {
    private val clipboard = RuntimeEnvironment.getApplication().getSystemService(ClipboardManager::class.java)
    private var now = 1_000L
    private val tasks = mutableListOf<() -> Unit>()
    private val delays = mutableListOf<Long>()
    private var expirations = 0
    private val owner = RpcLabInvitationClipboard(clipboard, clock = { now }, schedule = { delay, task ->
        delays += delay
        tasks += task
        val cancel: () -> Unit = {} // Exercise even a late callback that cancellation could not retract.
        cancel
    }, expired = { expirations++ })

    @Test
    fun explicitCopyIsExactAndSensitiveWithoutExtendingMintLifetime() {
        val start = owner.beginMinting()
        now += 5_000
        owner.minted("synthetic-invitation", start)
        assertFalse(clipboard.hasPrimaryClip(), "Minting alone must not touch the clipboard")
        assertTrue(owner.copy())
        assertEquals("synthetic-invitation", clipboard.primaryClip!!.getItemAt(0).text)
        assertTrue(clipboard.primaryClipDescription!!.extras!!.getBoolean("android.content.extra.IS_SENSITIVE"))
        assertEquals(listOf(115_000L), delays)
        now += 114_999
        assertTrue(owner.copy())
        now++
        assertFalse(owner.copy())
        assertFalse(clipboard.hasPrimaryClip())
    }

    @Test
    fun stopAndNewInvitationRetireOnlyTheOwnedCopy() {
        owner.minted("first", owner.beginMinting())
        assertTrue(owner.copy())
        val next = owner.beginMinting()
        assertFalse(clipboard.hasPrimaryClip())
        owner.minted("second", next)
        assertTrue(owner.copy())
        owner.retire()
        owner.retire()
        assertFalse(clipboard.hasPrimaryClip())
        assertFalse(owner.copy())
    }

    @Test
    fun retiringPreservesAnUnrelatedClipboardReplacement() {
        owner.minted("synthetic-invitation", owner.beginMinting())
        assertTrue(owner.copy())
        clipboard.setPrimaryClip(ClipData.newPlainText("unrelated", "synthetic-other-app"))
        owner.retire()
        assertEquals("synthetic-other-app", clipboard.primaryClip!!.getItemAt(0).text)
    }

    @Test
    fun staleExpiryCannotEraseANewInvitationOrItsCopy() {
        owner.minted("first", owner.beginMinting())
        assertTrue(owner.copy())
        val stale = tasks.single()
        owner.minted("second", owner.beginMinting())
        assertTrue(owner.copy())
        stale()
        assertEquals("second", clipboard.primaryClip!!.getItemAt(0).text)
        assertEquals(0, expirations)
        tasks.last()()
        assertEquals(1, expirations)
        assertFalse(clipboard.hasPrimaryClip())
    }

    @Test
    fun slowMintCannotPublishOrCopyAnAlreadyExpiredInvitation() {
        val start = owner.beginMinting()
        now += 120_000
        owner.minted("synthetic-expired", start)
        assertFalse(owner.copy())
        assertFalse(clipboard.hasPrimaryClip())
        assertTrue(tasks.isEmpty())
        assertEquals(1, expirations)
    }

    @Test
    @Config(sdk = [35])
    fun activityStopAndHiddenCopyRemainExplicitForegroundHostOnlyAndExpiryBound() {
        val root = generateSequence(java.io.File(checkNotNull(System.getProperty("user.dir")))) { it.parentFile }
            .first { java.io.File(it, "settings.gradle.kts").isFile }
        val source = java.io.File(root, "samples/p2p-sample-android/src/debug/java/" +
            "dev/p2pkit/sample/android/rpclab/RpcLabActivity.kt").readText()
        assertTrue(source.contains("foreground && !busy && !closing && hostRole && lab != null"))
        val copy = source.substringAfter("if (invitationVisible) Text(invitation)")
            .substringBefore("Text(\"An idle ordinary role")
        assertFalse(copy.contains("invitationVisible"))
        assertTrue(copy.contains("invitationClipboard.copy()"))
        assertTrue(copy.contains("invitation.isNotEmpty()"))
        assertTrue(copy.contains("Text(\"Copy invitation\")"))
        assertTrue(source.substringAfter("private fun stop(").substringBefore("closing = true")
            .contains("invitationClipboard.retire()"))
        assertTrue(source.substringAfter("override fun onStop()").substringBefore("super.onStop()")
            .contains("if (!appSwitch.active)"))
        assertTrue(source.substringAfter("override fun onStop()").substringBefore("super.onStop()")
            .contains("invitationClipboard.retire()"))
        assertTrue(source.contains("WindowManager.LayoutParams.FLAG_SECURE"))
    }
}
