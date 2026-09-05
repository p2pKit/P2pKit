package dev.p2pkit.sample.desktop

import dev.p2pkit.sample.diagnostics.DiagnosticEventNames
import dev.p2pkit.sample.diagnostics.anonymizeIdentifier
import java.lang.management.ManagementFactory
import java.nio.file.Files
import java.util.concurrent.CountDownLatch
import java.util.concurrent.FutureTask
import java.util.concurrent.TimeUnit
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertIs
import kotlin.test.assertNotEquals
import kotlin.test.assertNotNull
import kotlin.test.assertTrue

class CliDiagnosticConnectionTest {
    @Test
    fun lateStateNotificationsCannotRetireReplacementOrStealItsFirstTransfer() = withHarness {
        for (lateState in listOf("Closed", "Failed", "Connected", "Reconnecting")) {
            CliDiagnostics.startSession("PS-T05", "both", "test-$lateState")
            CliDiagnostics.registerConnection("old", "peer", "Connected")
            CliDiagnostics.fileHash("peer", "old-transfer", 1, "a".repeat(64), false, "old")
            CliDiagnostics.registerConnection("new", "peer", "Connected")
            val expected = assertNotNull(CliDiagnostics.connectionIdFor("peer"))

            repeat(2) { CliDiagnostics.connection("old", "peer", lateState, "Connected") }
            // No B transfer has been registered before A's late callback.
            CliDiagnostics.transfer("peer", "first-new-transfer", "new", DiagnosticEventNames.TRANSFER_STARTED)
            val current = CliDiagnostics.recorder.snapshot().last()
            assertEquals(expected, current.connectionId, lateState)
            assertEquals(anonymizeIdentifier("new"), current.sdkSessionId)
            assertEquals(expected, CliDiagnostics.connectionIdFor("peer"))

            CliDiagnostics.fileHash("peer", "old-transfer", 1, "a".repeat(64), true, "old")
            val old = CliDiagnostics.recorder.snapshot().last()
            assertEquals(expected, old.connectionId)
            assertEquals(anonymizeIdentifier("old"), old.sdkSessionId)
        }
    }

    @Test
    fun newDiagnosticSessionSnapshotRegistersOnlyLiveSdkOwners() = withHarness {
        CliDiagnostics.registerConnection("new", "peer", "Connected")
        val before = assertNotNull(CliDiagnostics.connectionIdFor("peer"))
        CliDiagnostics.startSession("PS-T05", "both", "next-test") {
            listOf(
                CliDiagnosticConnectionSnapshot("new", "peer", "Connected"),
                CliDiagnosticConnectionSnapshot("old", "peer", "Closed")
            )
        }
        CliDiagnostics.connection("old", "peer", "Failed")
        val after = assertNotNull(CliDiagnostics.connectionIdFor("peer"))
        assertNotEquals(before, after)
        assertEquals(after, CliDiagnostics.transferConnectionId("peer", "new", "first-transfer"))
    }

    @Test
    fun diagnosticSnapshotCannotBeAppliedAfterConcurrentReplacementRegistration() = withHarness {
        CliDiagnostics.registerConnection("old", "peer", "Connected")
        val sampled = CountDownLatch(1)
        val resumeSnapshot = CountDownLatch(1)
        val snapshotTask = FutureTask {
            CliDiagnostics.startSession("PS-T05", "both", "concurrent-test") {
                val captured = CliDiagnosticConnectionSnapshot("old", "peer", "Connected")
                sampled.countDown()
                check(resumeSnapshot.await(5, TimeUnit.SECONDS))
                listOf(captured)
            }
        }
        val snapshotThread = Thread(snapshotTask, "diagnostic-snapshot")
        val replacementTask = FutureTask { CliDiagnostics.registerConnection("new", "peer", "Connected") }
        val replacementThread = Thread(replacementTask, "replacement-registration")
        try {
            snapshotThread.start()
            assertTrue(sampled.await(5, TimeUnit.SECONDS))
            replacementThread.start()
            // Observe the actual monitor owner instead of hoping a short delay excludes registration.
            val threads = ManagementFactory.getThreadMXBean()
            val deadline = System.nanoTime() + TimeUnit.SECONDS.toNanos(5)
            while (threads.getThreadInfo(replacementThread.id)?.lockOwnerId != snapshotThread.id &&
                !replacementTask.isDone && System.nanoTime() < deadline
            ) Thread.yield()
            assertEquals(snapshotThread.id, threads.getThreadInfo(replacementThread.id)?.lockOwnerId)
            resumeSnapshot.countDown()
            snapshotTask.get(5, TimeUnit.SECONDS)
            replacementTask.get(5, TimeUnit.SECONDS)

            CliDiagnostics.connection("old", "peer", "Closed")
            val expected = assertNotNull(CliDiagnostics.connectionIdFor("peer"))
            assertEquals(expected, CliDiagnostics.transferConnectionId("peer", "new", "first-after-snapshot"))
        } finally {
            resumeSnapshot.countDown()
            snapshotThread.interrupt()
            replacementThread.interrupt()
            snapshotThread.join(5_000)
            replacementThread.join(5_000)
            assertTrue(!snapshotThread.isAlive && !replacementThread.isAlive)
        }
    }

    private fun withHarness(block: () -> Unit) {
        val home = Files.createTempDirectory("p2pkit-cli-diagnostic-state").toFile()
        try {
            val options = assertIs<CliParseResult.Success>(parseCliOptions(arrayOf("session=initial-test"))).options
            CliDiagnostics.configure(options, home)
            CliDiagnostics.localPeerId = "synthetic-local-peer"
            block()
        } finally {
            CliDiagnostics.close()
            CliDiagnostics.localPeerId = null
            home.deleteRecursively()
        }
    }
}
