package dev.p2pkit.sample.diagnostics

import dev.p2pkit.core.transfer.durableFileDestination
import java.io.File
import java.io.IOException
import java.nio.file.Files
import java.util.UUID
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertFalse
import kotlin.test.assertTrue
import kotlinx.coroutines.runBlocking

class StagingPathChecksTest {
    @Test
    fun plainFilesAndDirectoriesPassButMissingAndNonDirectoryAncestorsDoNot() = withInbox { inbox ->
        val payload = File(inbox, "payload").also { it.writeText("keep") }
        assertTrue(isPlainJvmStagingPath(inbox))
        assertTrue(isPlainJvmStagingPath(payload))
        assertFalse(isPlainJvmStagingPath(File(inbox, "missing")))
        assertFalse(isPlainJvmStagingPath(File(payload, "child")))
        assertEquals("keep", payload.readText())
    }

    @Test
    fun canonicalIdentityDoesNotAuthorizeAnActualSymbolicLink() = withInbox { inbox ->
        val target = File(inbox, "target").also { check(it.mkdir()) }
        val link = File(inbox, "link")
        Files.createSymbolicLink(link.toPath(), target.toPath())
        val opaque = CanonicalIdentityFile(link)
        assertEquals(opaque.absoluteFile, opaque.canonicalFile)
        assertTrue(opaque.isDirectory)
        assertFalse(isPlainJvmStagingPath(opaque))
    }

    @Test
    fun originalLinkedAncestorIncludingBeforeDotDotIsRejected() = withInbox { inbox ->
        val target = File(inbox, "target").also { check(it.mkdir()) }
        File(target, "nested").mkdir()
        val link = File(inbox, "link")
        Files.createSymbolicLink(link.toPath(), target.toPath())
        val nested = CanonicalIdentityFile(File(link, "nested"))
        val traversed = CanonicalIdentityFile(File(link, "../target"))
        assertTrue(nested.isDirectory && traversed.isDirectory)
        assertFalse(isPlainJvmStagingPath(nested))
        assertFalse(isPlainJvmStagingPath(traversed))
    }

    @Test
    fun linkedUuidDirectoryNeverAuthorizesDeletingItsExternalContents() = withInbox { inbox ->
        val root = File(inbox, ".p2pkit-transfer-staging-v1").also { check(it.mkdir()) }
        val token = UUID.randomUUID().toString()
        val outside = File(inbox, "not-owned").also { check(it.mkdir()) }
        recorded(outside, token)
        val part = File(outside, ".p2pkit-keep.part").also { it.writeText("keep outside namespace") }
        val link = File(root, token)
        Files.createSymbolicLink(link.toPath(), outside.toPath())
        cleanupStaleTransferPartsOnce(inbox)
        assertEquals("keep outside namespace", part.readText())
        assertTrue(File(outside, "ownership").exists())
        assertTrue(Files.isSymbolicLink(link.toPath()))
    }

    @Test
    fun linkedRecordLeaseOrPartIsNotCleanupAuthority() = withInbox { inbox ->
        val root = File(inbox, ".p2pkit-transfer-staging-v1").also { check(it.mkdir()) }
        for (name in listOf("ownership", "lease", ".p2pkit-linked.part")) {
            val token = UUID.randomUUID().toString()
            val directory = File(root, token).also { check(it.mkdir()) }
            recorded(directory, token)
            val original = File(directory, name)
            if (!original.exists()) original.writeText("linked payload")
            val outside = File(inbox, "outside-$name").also { it.writeBytes(original.readBytes()) }
            check(original.delete())
            Files.createSymbolicLink(original.toPath(), outside.toPath())
            val part = File(directory, ".p2pkit-keep.part").also { it.writeText("keep") }
            TransferStagingOwnership.reconcile(inbox)
            assertEquals("keep", part.readText())
            assertTrue(Files.isSymbolicLink(original.toPath()))
            assertTrue(outside.exists())
        }
    }

    @Test
    fun explicitPlatformInspectorIsUsedForAdmissionAndTerminalCleanup() = withInbox { inbox ->
        runBlocking {
            val seen = mutableSetOf<String>()
            val inspect: (File) -> Boolean = { seen += it.name; isPlainJvmStagingPath(it) }
            val target = File(inbox, "target").also { check(it.createNewFile()) }
            val destination = reservedFileDestination(target, inspect) { file, stage ->
                durableFileDestination(file, stage, 0)
            }
            destination.openSink()
            cleanupStaleTransferPartsOnce(inbox, inspect)
            destination.abort(null)
            assertFalse(target.exists())
            assertTrue("ownership" in seen && "lease" in seen)
            assertTrue(File(inbox, ".p2pkit-transfer-staging-v1").listFiles()!!.isEmpty())
        }
    }

    @Test
    fun failedPlatformInspectionRefusesAdmissionBeforeCreatingTheFactory() = withInbox { inbox ->
        val target = File(inbox, "target").also { check(it.createNewFile()) }
        var factories = 0
        assertFailsWith<IOException> {
            reservedFileDestination(target, { false }) { _, _ -> factories++; error("must not be called") }
        }
        assertEquals(0, factories)
        assertTrue(target.exists())
        assertEquals(listOf(target), inbox.listFiles()!!.toList())
    }

    private fun recorded(directory: File, token: String) {
        File(directory, "lease").writeText("")
        File(directory, "ownership").writeText("p2pkit-sample-transfer-staging-v1\n$token\n")
    }

    // Real filesystem/NIO, with only java.io canonical spelling modeled like Windows.
    private class CanonicalIdentityFile(file: File) : File(file.absolutePath) {
        override fun getAbsoluteFile(): File = this
        override fun getCanonicalFile(): File = this
    }

    private fun withInbox(block: (File) -> Unit) {
        val inbox = Files.createTempDirectory("p2pkit-no-follow-").toFile().canonicalFile
        try { block(inbox) } finally { check(inbox.deleteRecursively()) }
    }
}
