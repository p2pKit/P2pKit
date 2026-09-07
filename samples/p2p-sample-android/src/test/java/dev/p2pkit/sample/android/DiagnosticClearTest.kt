package dev.p2pkit.sample.android

import android.content.SharedPreferences
import dev.p2pkit.sample.diagnostics.DiagnosticClearAction
import dev.p2pkit.sample.diagnostics.DiagnosticEnvironment
import java.io.File
import java.io.IOException
import java.nio.file.Files
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicReference
import kotlin.concurrent.thread
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertFalse
import kotlin.test.assertNull
import kotlin.test.assertTrue

class DiagnosticClearTest {
    @Test
    fun actualConfirmationKeepsDisplayMemoryPreferencesAndCorrelationsOnStorageFailure() = withDirectory { root ->
        val preferences = TestPreferences()
        val harness = harness(root, preferences)
        harness.beginSession("PS-T01", "both", "selected")
        harness.setLocalPeerId("local-synthetic-peer")
        val correlation = harness.registerConnection("synthetic-sdk-session", "remote-synthetic-peer")
        val before = harness.recorder.snapshot()
        val defaultsBefore = preferences.values.toMap()
        var selected = before.map { it.index }.toSet()
        var pausedEvents = before
        var status: String? = null
        val obstruction = File(root, "logs/diagnostic-events.jsonl.1").apply { assertTrue(mkdir()) }
        val confirmed: (Int) -> Unit = {
            selected = emptySet()
            pausedEvents = emptyList()
            status = "cleared"
        }

        harness.confirmClearCurrentSession(confirmed) { status = it }

        assertEquals(DiagnosticClearAction.FAILURE_MESSAGE, status)
        assertEquals(before.map { it.index }.toSet(), selected)
        assertEquals(before, pausedEvents)
        assertEquals(before, harness.recorder.snapshot())
        assertEquals(defaultsBefore, preferences.values)
        assertEquals(correlation, harness.connectionForPeer("remote-synthetic-peer"))
        assertTrue(obstruction.delete())
        harness.confirmClearCurrentSession(confirmed) { status = it }
        assertEquals("cleared", status)
        assertTrue(selected.isEmpty())
        assertTrue(pausedEvents.isEmpty())
        assertTrue(harness.recorder.snapshot().none { it.testSessionId == "selected" })
        assertTrue(preferences.values.isEmpty())
        assertNull(harness.connectionForPeer("remote-synthetic-peer"))
    }

    @Test
    fun failedPreferenceCommitDoesNotClearRecorderOrCorrelationsAndCanBeRetried() = withDirectory { root ->
        val preferences = TestPreferences()
        val harness = harness(root, preferences)
        harness.beginSession("PS-T01", "both", "selected")
        harness.setLocalPeerId("local-synthetic-peer")
        val correlation = harness.registerConnection("synthetic-sdk-session", "remote-synthetic-peer")
        val before = harness.recorder.snapshot()
        preferences.failCommit = true

        assertFailsWith<IOException> { harness.clearCurrentSession() }
        assertEquals(before, harness.recorder.snapshot())
        assertEquals(correlation, harness.connectionForPeer("remote-synthetic-peer"))
        assertTrue("selected" !in File(root, "logs/diagnostic-events.jsonl").readText())
        preferences.failCommit = false
        assertEquals(before.count { it.testSessionId == "selected" }, harness.clearCurrentSession())
        assertTrue(harness.recorder.snapshot().none { it.testSessionId == "selected" })
        assertNull(harness.connectionForPeer("remote-synthetic-peer"))
    }

    @Test
    fun clearNotifiesSnapshotReadersOnlyAfterSuccessfulRemovalIncludingRepeatClear() = withDirectory { root ->
        val preferences = TestPreferences()
        var revision = 0L
        val harness = harness(root, preferences) { revision++ }
        harness.beginSession("PS-T01", "both", "selected")
        val before = harness.recorder.snapshot()
        val beforeRevision = revision
        preferences.failCommit = true

        assertFailsWith<IOException> { harness.clearCurrentSession() }
        assertEquals(beforeRevision, revision)
        assertEquals(before, harness.recorder.snapshot())

        preferences.failCommit = false
        assertEquals(before.count { it.testSessionId == "selected" }, harness.clearCurrentSession())
        assertEquals(beforeRevision + 1, revision)
        assertTrue(harness.recorder.snapshot().none { it.testSessionId == "selected" })
        assertEquals(0, harness.clearCurrentSession())
        assertEquals(beforeRevision + 2, revision)
    }

    @Test
    fun newSessionCannotHaveItsRestartPreferencesErasedByAnOlderClear() = withDirectory { root ->
        val preferences = TestPreferences()
        val harness = harness(root, preferences)
        harness.beginSession("PS-T01", "both", "old-session")
        val committing = CountDownLatch(1)
        val release = CountDownLatch(1)
        val starting = CountDownLatch(1)
        val started = CountDownLatch(1)
        val clearResult = AtomicReference<Result<Int>>()
        val startResult = AtomicReference<Result<String>>()
        preferences.onCommit = {
            committing.countDown()
            check(release.await(5, TimeUnit.SECONDS))
        }
        val clearing = thread(name = "android-diagnostic-clear") {
            clearResult.set(runCatching { harness.clearCurrentSession() })
        }
        val beginning = thread(name = "android-diagnostic-new-session") {
            startResult.set(runCatching {
                check(committing.await(5, TimeUnit.SECONDS))
                starting.countDown()
                harness.beginSession("PS-T02", "receiver", "new-session").also { started.countDown() }
            })
        }
        try {
            assertTrue(committing.await(5, TimeUnit.SECONDS))
            assertTrue(starting.await(5, TimeUnit.SECONDS))
            assertFalse(started.await(100, TimeUnit.MILLISECONDS), "begin must serialize with preference clear")
        } finally {
            preferences.onCommit = {}
            release.countDown()
            clearing.join(5_000)
            beginning.join(5_000)
            assertFalse(clearing.isAlive)
            assertFalse(beginning.isAlive)
        }
        assertTrue(clearResult.get().getOrThrow() > 0)
        assertEquals("new-session", startResult.get().getOrThrow())
        assertEquals("new-session", harness.recorder.activeSessionId)
        assertEquals("new-session", preferences.getString("sessionId", null))
        assertEquals("PS-T02", preferences.getString("testId", null))
        assertEquals("receiver", preferences.getString("role", null))
    }

    private fun harness(
        root: File,
        preferences: TestPreferences,
        onChanged: () -> Unit = {}
    ): AndroidDiagnosticHarness = AndroidDiagnosticHarness(
        preferences, File(root, "logs"), File(root, "evidence"),
        DiagnosticEnvironment("android", "synthetic-host", "test", "test", "test", "synthetic")
    ) { onChanged() }

    private fun withDirectory(action: (File) -> Unit) {
        val root = Files.createTempDirectory("p2pkit-android-clear").toFile()
        try {
            action(root)
        } finally {
            assertTrue(root.deleteRecursively())
        }
    }
}

/** Host seam for session metadata only; recorder, files and confirmation callback are production code. */
private class TestPreferences : SharedPreferences {
    val values = mutableMapOf<String, String>()
    var failCommit = false
    @Volatile
    var onCommit: () -> Unit = {}

    override fun getAll(): Map<String, *> = values.toMap()
    override fun getString(key: String?, defValue: String?): String? = values[key] ?: defValue
    override fun contains(key: String?): Boolean = key in values
    override fun getStringSet(key: String?, defValues: MutableSet<String>?): MutableSet<String>? = error("unused")
    override fun getInt(key: String?, defValue: Int): Int = error("unused")
    override fun getLong(key: String?, defValue: Long): Long = error("unused")
    override fun getFloat(key: String?, defValue: Float): Float = error("unused")
    override fun getBoolean(key: String?, defValue: Boolean): Boolean = error("unused")
    override fun registerOnSharedPreferenceChangeListener(
        listener: SharedPreferences.OnSharedPreferenceChangeListener?
    ): Unit = error("unused")
    override fun unregisterOnSharedPreferenceChangeListener(
        listener: SharedPreferences.OnSharedPreferenceChangeListener?
    ): Unit = error("unused")

    override fun edit(): SharedPreferences.Editor = object : SharedPreferences.Editor {
        private var cleared = false
        private val changes = mutableMapOf<String, String?>()

        override fun putString(key: String?, value: String?): SharedPreferences.Editor = apply {
            changes[requireNotNull(key)] = value
        }
        override fun remove(key: String?): SharedPreferences.Editor = putString(key, null)
        override fun clear(): SharedPreferences.Editor = apply { cleared = true }
        override fun commit(): Boolean {
            onCommit()
            if (failCommit) return false
            if (cleared) values.clear()
            changes.forEach { (key, value) -> if (value == null) values.remove(key) else values[key] = value }
            return true
        }
        override fun apply() { check(commit()) }
        override fun putStringSet(key: String?, values: MutableSet<String>?): SharedPreferences.Editor = error("unused")
        override fun putInt(key: String?, value: Int): SharedPreferences.Editor = error("unused")
        override fun putLong(key: String?, value: Long): SharedPreferences.Editor = error("unused")
        override fun putFloat(key: String?, value: Float): SharedPreferences.Editor = error("unused")
        override fun putBoolean(key: String?, value: Boolean): SharedPreferences.Editor = error("unused")
    }
}
