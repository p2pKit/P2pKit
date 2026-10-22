package dev.p2pkit.sample.diagnostics

import dev.p2pkit.core.transfer.durableFileDestination
import java.io.File
import java.io.IOException
import java.nio.file.Files
import java.util.UUID
import java.util.concurrent.Executors
import java.util.concurrent.TimeUnit
import kotlin.test.Test
import kotlin.test.assertContentEquals
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertFalse
import kotlin.test.assertTrue
import kotlinx.coroutines.runBlocking
import kotlinx.io.Buffer

class TransferStagingOwnershipTest {
    @Test
    fun platformFactoryReceivesLiveOwnedDirectoryAndPublishesThroughWrapper() = withInbox { inbox ->
        runBlocking {
            val target = File(inbox, "factory.bin").also { check(it.createNewFile()) }
            var factoryCalls = 0
            val destination = reservedFileDestination(target) { suppliedTarget, stage ->
                factoryCalls++
                assertEquals(target, suppliedTarget)
                assertTrue(stage.isDirectory)
                assertEquals(stagingRoot(inbox), stage.parentFile)
                TransferStagingOwnership.reconcile(inbox)
                assertTrue(stage.isDirectory, "factory runs while staging lease is already held")
                durableFileDestination(suppliedTarget, stage, 0)
            }
            val bytes = "platform factory payload".encodeToByteArray()
            val buffer = Buffer().apply { write(bytes) }
            destination.openSink().write(buffer, buffer.size)
            destination.commit()
            assertContentEquals(bytes, target.readBytes())
            assertEquals(1, factoryCalls)
            assertEquals(emptyList(), stagingRoot(inbox).list()?.toList())
        }
    }

    @Test
    fun throwingPlatformFactoryRetiresItsClaimWithoutDeletingReservedTarget() = withInbox { inbox ->
        val target = File(inbox, "factory-failure.bin").also { check(it.createNewFile()) }
        assertFailsWith<IOException> {
            reservedFileDestination(target) { _, stage ->
                assertTrue(stage.isDirectory)
                throw IOException("injected platform factory failure")
            }
        }
        assertTrue(target.exists(), "the caller still owns the failed-construction reservation")
        assertEquals(emptyList(), stagingRoot(inbox).list()?.toList())
    }

    @Test
    fun existingReceivedNamespaceNameIsPreservedAndDoesNotDisableReceiving() = withInbox { inbox ->
        val prior = stagingRoot(inbox).also { it.writeText("valid old completed payload") }
        val lease = TransferStagingOwnership.claim(inbox)
        assertEquals(".p2pkit-transfer-staging-v1.1", lease.directory.parentFile.name)
        TransferStagingOwnership.reconcile(inbox)
        lease.retire()
        assertEquals("valid old completed payload", prior.readText())
    }

    @Test
    fun matchingCompletedFileSurvivesFreshProcessLifecycleCleanup() = withInbox { inbox ->
        runBlocking {
            val target = File(inbox, ".p2pkit-report.part").also { check(it.createNewFile()) }
            val destination = reservedFileDestination(target)
            val payload = "completed, not staging".encodeToByteArray()
            val buffer = Buffer().apply { write(payload) }
            destination.openSink().write(buffer, buffer.size)
            destination.commit()
            destination.abort(null)
            withChild(inbox, "clean") { process ->
                assertTrue(process.waitFor(10, TimeUnit.SECONDS))
                assertEquals(0, process.exitValue())
            }
            assertContentEquals(payload, target.readBytes())
            assertEquals(emptyList(), stagingRoot(inbox).list()?.toList())
        }
    }

    @Test
    fun liveOtherProcessPartSurvivesAndStillCommits() = withInbox { inbox ->
        withChild(inbox, "hold") { process ->
            awaitReady(process)
            val part = stagingRoot(inbox).walkTopDown().single { it.name.endsWith(".part") }
            assertTrue(part.length() > 0)
            cleanupStaleTransferPartsOnce(inbox)
            assertTrue(part.exists(), "an OS-locked other-process writer must survive reconciliation")
            process.outputStream.bufferedWriter().use { it.write("commit\n"); it.flush() }
            assertTrue(process.waitFor(10, TimeUnit.SECONDS))
            assertEquals(0, process.exitValue())
            assertEquals("cross-process payload", File(inbox, "received.bin").readText())
            assertFalse(part.exists())
            assertEquals(emptyList(), stagingRoot(inbox).list()?.toList())
        }
    }

    @Test
    fun onlyRecordedOsUnlockedCrashStagingIsReclaimed() = withInbox { inbox ->
        val legacy = File(inbox, ".p2pkit-unknown.part").also { it.writeText("may be completed") }
        val hidden = File(inbox, ".notes").also { it.writeText("private note") }
        val ordinary = File(inbox, "report.p2pkit-part").also { it.writeText("received data") }
        withChild(inbox, "crash") { process ->
            awaitReady(process)
            assertTrue(process.waitFor(10, TimeUnit.SECONDS))
            assertEquals(23, process.exitValue(), "fixture must exit without commit/abort/shutdown cleanup")
        }
        val abandoned = stagingRoot(inbox).listFiles()!!.single()
        assertTrue(abandoned.walkTopDown().any { it.name.endsWith(".part") && it.length() > 0 })
        val unknown = File(stagingRoot(inbox), UUID.randomUUID().toString()).also { check(it.mkdir()) }
        File(unknown, "lease").writeText("")
        File(unknown, "ownership").writeText("not our ownership record")
        val unknownPart = File(unknown, ".p2pkit-unknown.part").also { it.writeText("unowned") }
        cleanupStaleTransferPartsOnce(inbox)
        assertFalse(abandoned.exists())
        assertEquals("unowned", unknownPart.readText())
        assertEquals("may be completed", legacy.readText())
        assertEquals("private note", hidden.readText())
        assertEquals("received data", ordinary.readText())
        // Empty final reservations are not name-based staging authority either.
        assertTrue(File(inbox, "received.bin").exists())
    }

    @Test
    fun sameProcessLiveLeaseAndUnknownContentsAreNeverSwept() = withInbox { inbox ->
        val lease = TransferStagingOwnership.claim(inbox)
        val part = File(lease.directory, ".p2pkit-live.part").also { it.writeText("live") }
        TransferStagingOwnership.reconcile(inbox)
        assertEquals("live", part.readText())
        val unexpected = File(lease.directory, "user-file").also { it.writeText("keep") }
        assertFailsWith<IOException> { lease.retire() }
        assertEquals("keep", unexpected.readText())
        check(unexpected.delete())
        lease.retire()
        lease.retire()
        assertFalse(lease.directory.exists())
    }

    @Test
    fun symlinkNamespaceIsRefusedWithoutTouchingItsReferent() = withInbox { inbox ->
        val external = File(inbox, "external").also { check(it.mkdir()) }
        val file = File(external, ".p2pkit-keep.part").also { it.writeText("keep") }
        // This is a real filesystem test, not a swallowed unsupported-symlink skip.
        Files.createSymbolicLink(stagingRoot(inbox).toPath(), external.toPath())
        assertFailsWith<IOException> { TransferStagingOwnership.claim(inbox) }
        assertFailsWith<IOException> { TransferStagingOwnership.reconcile(inbox) }
        assertEquals("keep", file.readText())
    }

    private fun awaitReady(process: Process) {
        val reader = Executors.newSingleThreadExecutor()
        try {
            assertEquals("READY", reader.submit<String> { process.inputStream.bufferedReader().readLine() }
                .get(10, TimeUnit.SECONDS))
        } finally {
            reader.shutdownNow()
        }
    }

    private fun withChild(inbox: File, action: String, block: (Process) -> Unit) {
        val java = File(System.getProperty("java.home"), "bin/java").absolutePath
        val classpath = checkNotNull(System.getProperty("p2pkit.staging.test.classpath"))
        val process = ProcessBuilder(java, "-cp", classpath, StagingOwnerChild::class.java.name, inbox.path, action)
            .redirectError(ProcessBuilder.Redirect.INHERIT).start()
        try {
            block(process)
        } finally {
            if (process.isAlive) process.destroy()
            if (!process.waitFor(5, TimeUnit.SECONDS)) {
                process.destroyForcibly()
                check(process.waitFor(5, TimeUnit.SECONDS)) { "Owned test JVM did not retire" }
            }
            process.inputStream.close()
            process.outputStream.close()
        }
    }

    private fun withInbox(block: (File) -> Unit) {
        val inbox = Files.createTempDirectory("p2pkit-staging-owner-").toFile().canonicalFile
        try { block(inbox) } finally { inbox.deleteRecursively() }
    }

    private fun stagingRoot(inbox: File): File = File(inbox, ".p2pkit-transfer-staging-v1")
}

/** Runs the actual production destination in a separate process with no shared local registry. */
object StagingOwnerChild {
    @JvmStatic
    fun main(args: Array<String>) = runBlocking {
        val inbox = File(args[0])
        if (args[1] == "clean") {
            cleanupStaleTransferPartsOnce(inbox)
            return@runBlocking
        }
        val target = File(inbox, "received.bin").also { check(it.createNewFile()) }
        val destination = reservedFileDestination(target)
        val buffer = Buffer().apply { write("cross-process payload".encodeToByteArray()) }
        val sink = destination.openSink()
        sink.write(buffer, buffer.size)
        sink.flush()
        println("READY")
        System.out.flush()
        if (args[1] == "crash") Runtime.getRuntime().halt(23)
        check(readln() == "commit")
        destination.commit()
    }
}
