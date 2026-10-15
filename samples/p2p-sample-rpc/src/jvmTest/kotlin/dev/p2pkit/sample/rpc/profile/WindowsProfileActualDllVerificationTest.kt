package dev.p2pkit.sample.rpc.profile

import java.nio.ByteBuffer
import java.nio.channels.FileChannel
import java.nio.file.FileAlreadyExistsException
import java.nio.file.Files
import java.nio.file.Path
import java.nio.file.StandardOpenOption.CREATE_NEW
import java.nio.file.StandardOpenOption.WRITE
import java.security.MessageDigest
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertFalse
import kotlin.test.assertTrue

/** Synthetic bytes and owned temporary files only; no Git, hosted-runner or Windows runtime prerequisite. */
class WindowsProfileActualDllVerificationTest {
    @Test fun exactPinnedBytesProduceOnlyAByteManifestAndNonRuntimeReceipt() = fixture { root, dll, output ->
        val bytes = Files.readAllBytes(dll)
        var checks = 0
        val result = verify(root, dll, output) { _, _ -> checks++ }
        assertEquals(3, checks)
        assertEquals(WindowsProfileByteManifest.Scope.BYTE_MANIFEST_ONLY, result.scope)
        val manifest = Files.readAllBytes(output.resolve(WindowsProfileActualDllVerification.MANIFEST_FILE))
        assertTrue(manifest.contentEquals(WindowsProfileByteManifest.produce(SOURCE, TREE, true, bytes)))
        val receipt = Json.parseToJsonElement(Files.readString(
            output.resolve(WindowsProfileActualDllVerification.RECEIPT_FILE),
        )).jsonObject
        assertEquals("BYTE_MANIFEST_ONLY", receipt.getValue("scope").jsonPrimitive.content)
        assertEquals(hash(bytes), receipt.getValue("sha256").jsonPrimitive.content)
        assertEquals(hash(manifest), receipt.getValue("manifestSha256").jsonPrimitive.content)
        assertEquals("PRODUCER_ROUND_TRIP_ONLY", receipt.getValue("manifestAuthority").jsonPrimitive.content)
        for (key in listOf("signatureVerification", "nativeLoad", "nativeExecution", "runtimeQualification",
            "releaseQualification")) assertEquals("NOT_PERFORMED", receipt.getValue(key).jsonPrimitive.content)
        assertEquals("NOT_QUALIFIED", receipt.getValue("filesystemCustody").jsonPrimitive.content)
        Files.list(output).use { assertEquals(2L, it.count()) }
    }

    @Test fun wrongCompilerDigestCannotBeReplacedByCandidateSidecarData() = fixture { root, dll, output ->
        Files.writeString(dll.resolveSibling("candidate.manifest"), "sha256=${hash(Files.readAllBytes(dll))}\n")
        assertFailsWith<IllegalArgumentException> {
            WindowsProfileActualDllVerification.verify(root, dll, pins("0".repeat(64)), output) { _, _ -> }
        }
        assertFalse(Files.exists(output))
    }

    @Test fun tooShortAndTruncatedDllsFailWithoutCreatingOutput() = fixture { root, dll, output ->
        val original = WindowsProfilePeFixture.create()
        for (bytes in listOf(ByteArray(511), original.copyOf(original.size - 1), ByteArray(512))) {
            Files.write(dll, bytes)
            assertFailsWith<IllegalArgumentException> { verify(root, dll, output) }
            assertFalse(Files.exists(output))
        }
    }

    @Test fun oversizedSparseInputIsRejectedBeforeBoundedSnapshotAllocation() = fixture { root, dll, output ->
        Files.delete(dll)
        FileChannel.open(dll, CREATE_NEW, WRITE).use {
            it.position(WindowsProfilePeImage.MAXIMUM_BYTES.toLong())
            it.write(ByteBuffer.wrap(byteArrayOf(0)))
        }
        assertFailsWith<IllegalArgumentException> {
            WindowsProfileActualDllVerification.verify(root, dll, pins("0".repeat(64)), output) { _, _ -> }
        }
        assertFalse(Files.exists(output))
    }

    @Test fun directoryCannotBeReadAsADll() = fixture { root, dll, output ->
        Files.delete(dll)
        Files.createDirectory(dll)
        assertFailsWith<IllegalArgumentException> {
            WindowsProfileActualDllVerification.verify(root, dll, pins("0".repeat(64)), output) { _, _ -> }
        }
        assertFalse(Files.exists(output))
    }

    @Test fun existingDirectoryAndFileAreNeverOverwrittenOrDeleted() = fixture { root, dll, output ->
        Files.createDirectory(output)
        val marker = Files.writeString(output.resolve("keep.txt"), "existing evidence")
        assertFailsWith<FileAlreadyExistsException> { verify(root, dll, output) }
        assertEquals("existing evidence", Files.readString(marker))
        Files.delete(marker)
        Files.delete(output)
        Files.writeString(output, "existing file")
        assertFailsWith<FileAlreadyExistsException> { verify(root, dll, output) }
        assertEquals("existing file", Files.readString(output))
    }

    @Test fun dirtyOrDifferentSourceFailsBeforeInputReading() = fixture { root, dll, output ->
        val pinned = pins(hash(Files.readAllBytes(dll)))
        Files.delete(dll)
        assertFailsWith<IllegalStateException> {
            WindowsProfileActualDllVerification.verify(root, dll, pinned, output) { _, _ -> error("Source rejected") }
        }
        assertFalse(Files.exists(output))
    }

    @Test fun sourceChangeAfterReadingPreventsOutputCreation() = fixture { root, dll, output ->
        var checks = 0
        assertFailsWith<IllegalStateException> {
            verify(root, dll, output) { _, _ -> check(++checks < 2) }
        }
        assertEquals(2, checks)
        assertFalse(Files.exists(output))
    }

    @Test fun sourceChangeAfterManifestRetainsPartialEvidenceWithoutSuccessReceipt() = fixture { root, dll, output ->
        var checks = 0
        assertFailsWith<IllegalStateException> {
            verify(root, dll, output) { _, _ -> check(++checks < 3) }
        }
        assertEquals(3, checks)
        assertTrue(Files.isRegularFile(output.resolve(WindowsProfileActualDllVerification.MANIFEST_FILE)))
        assertFalse(Files.exists(output.resolve(WindowsProfileActualDllVerification.RECEIPT_FILE)))
    }

    @Test fun cleanHeadAndTreeAreExactNotLabels() {
        val pinned = pins("0".repeat(64))
        WindowsProfileActualDllVerification.requireSource(pinned, SOURCE, TREE, "")
        for ((source, tree, status) in listOf(
            Triple("c".repeat(40), TREE, ""), Triple(SOURCE, "d".repeat(40), ""),
            Triple(SOURCE, TREE, "?? unexpected-file"), Triple(SOURCE, TREE, " M tracked-file"),
        )) assertFailsWith<IllegalArgumentException> {
            WindowsProfileActualDllVerification.requireSource(pinned, source, tree, status)
        }
    }

    @Test fun malformedExternalPinsAreRejected() {
        for (value in listOf("", "HEAD", "A".repeat(40), "a".repeat(39), "a".repeat(41))) {
            assertFailsWith<IllegalArgumentException> {
                WindowsProfileActualDllVerification.Pins(value, TREE, "0".repeat(64))
            }
            assertFailsWith<IllegalArgumentException> {
                WindowsProfileActualDllVerification.Pins(SOURCE, value, "0".repeat(64))
            }
        }
        for (value in listOf("", "A".repeat(64), "a".repeat(63), "a".repeat(65))) {
            assertFailsWith<IllegalArgumentException> { pins(value) }
        }
    }

    @Test fun relativePathsWrongFileNameAndSourceTreeOutputsAreRejected() = fixture { root, dll, output ->
        val pinned = pins(hash(Files.readAllBytes(dll)))
        for ((candidateRoot, candidateDll, candidateOutput) in listOf(
            Triple(Path.of("relative"), dll, output), Triple(root, Path.of("relative.dll"), output),
            Triple(root, dll, Path.of("relative-output")), Triple(root, dll.resolveSibling("wrong.dll"), output),
            Triple(root, dll, root.resolve("not-evidence")),
        )) assertFailsWith<IllegalArgumentException> {
            WindowsProfileActualDllVerification.verify(candidateRoot, candidateDll, pinned, candidateOutput) { _, _ -> }
        }
        assertFalse(Files.exists(output))
    }

    private fun verify(
        root: Path,
        dll: Path,
        output: Path,
        sourceCheck: (Path, WindowsProfileActualDllVerification.Pins) -> Unit = { _, _ -> },
    ) = WindowsProfileActualDllVerification.verify(
        root, dll, pins(hash(Files.readAllBytes(dll))), output, sourceCheck,
    )

    private fun fixture(test: (Path, Path, Path) -> Unit) {
        val directory = Files.createTempDirectory("rpc-byte-control-").toRealPath()
        try {
            val root = Files.createDirectory(directory.resolve("source"))
            val dll = Files.write(directory.resolve("p2pkit-windows-profile.dll"), WindowsProfilePeFixture.create())
            test(root, dll, directory.resolve("observation"))
        } finally {
            Files.walk(directory).use { paths ->
                paths.sorted(Comparator.reverseOrder()).forEach { Files.delete(it) }
            }
        }
    }

    private fun pins(hash: String) = WindowsProfileActualDllVerification.Pins(SOURCE, TREE, hash)
    private fun hash(bytes: ByteArray): String = MessageDigest.getInstance("SHA-256").digest(bytes)
        .joinToString("") { "%02x".format(it) }

    companion object {
        private const val SOURCE = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
        private const val TREE = "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
    }
}
