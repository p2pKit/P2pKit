package dev.p2pkit.sample.rpc.profile

import java.nio.file.Files
import java.nio.file.Path
import java.security.MessageDigest
import kotlin.test.Test
import kotlin.test.assertContentEquals
import kotlin.test.assertEquals
import kotlin.test.assertFails
import kotlin.test.assertFalse
import kotlin.test.assertTrue

class WindowsProfilePackageStageTest {
    @Test fun stagesOnlyExactComponentBytesAndCanonicalManifest() = fixture { root, dll, pins ->
        val output = root.resolve("resources/windows/rpc-profile/windows-x64")
        val result = WindowsProfilePackageStage.stage(dll, pins, output)
        assertEquals(WindowsProfileByteManifest.Scope.BYTE_MANIFEST_ONLY, result.scope)
        assertContentEquals(Files.readAllBytes(dll), Files.readAllBytes(output.resolve(dll.fileName)))
        val manifest = Files.readAllBytes(output.resolve("component.manifest"))
        assertEquals(result, WindowsProfileByteManifest.authorize(manifest, Files.readAllBytes(dll),
            WindowsProfileByteManifest.Authority(hash(manifest), SOURCE, TREE)))
        Files.list(output).use { entries -> assertEquals(2, entries.count()) }
        assertFalse(WindowsProfileAvailability.IMPLEMENTED)
        assertFalse(WindowsProfileAvailability.QUALIFIED)
    }

    @Test fun exactByteStageIsIdempotent() = fixture { root, dll, pins ->
        val output = root.resolve("stage")
        val first = WindowsProfilePackageStage.stage(dll, pins, output)
        assertEquals(first, WindowsProfilePackageStage.stage(dll, pins, output))
    }

    @Test fun rejectsCompilerDigestMismatchBeforeCreatingOutput() = fixture { root, dll, pins ->
        val output = root.resolve("stage")
        assertFails { WindowsProfilePackageStage.stage(dll, pins.copy(sha256 = "0".repeat(64)), output) }
        assertFalse(Files.exists(output))
    }

    @Test fun rejectsMalformedPeBeforeCreatingOutput() = fixture { root, dll, pins ->
        val output = root.resolve("stage")
        val bytes = ByteArray(512)
        Files.write(dll, bytes)
        assertFails { WindowsProfilePackageStage.stage(dll, pins.copy(sha256 = hash(bytes)), output) }
        assertFalse(Files.exists(output))
    }

    @Test fun refusesUnrecognizedExistingContentWithoutRemovingIt() = fixture { root, dll, pins ->
        val output = Files.createDirectory(root.resolve("stage"))
        val retained = output.resolve("unexpected.txt")
        Files.writeString(retained, "retain")
        assertFails { WindowsProfilePackageStage.stage(dll, pins, output) }
        assertEquals("retain", Files.readString(retained))
    }

    @Test fun refusesDifferentExistingLibraryAndDoesNotEmitManifest() = fixture { root, dll, pins ->
        val output = Files.createDirectory(root.resolve("stage"))
        val old = Files.readAllBytes(dll).also { it[0] = 0 }
        Files.write(output.resolve(dll.fileName), old)
        assertFails { WindowsProfilePackageStage.stage(dll, pins, output) }
        assertContentEquals(old, Files.readAllBytes(output.resolve(dll.fileName)))
        assertFalse(Files.exists(output.resolve("component.manifest")))
    }

    @Test fun refusesDifferentExistingManifestWithoutReplacingIt() = fixture { root, dll, pins ->
        val output = root.resolve("stage")
        WindowsProfilePackageStage.stage(dll, pins, output)
        val manifest = output.resolve("component.manifest")
        Files.writeString(manifest, "untrusted")
        assertFails { WindowsProfilePackageStage.stage(dll, pins, output) }
        assertEquals("untrusted", Files.readString(manifest))
    }

    @Test fun rejectsWrongFilenameRelativePathAndNonRegularInput() = fixture { root, dll, pins ->
        val output = root.resolve("stage")
        assertFails { WindowsProfilePackageStage.stage(dll, pins, Path.of("relative")) }
        assertFails { WindowsProfilePackageStage.stage(dll.resolveSibling("wrong.dll"), pins, output) }
        Files.delete(dll)
        Files.createDirectory(dll)
        assertFails { WindowsProfilePackageStage.stage(dll, pins, output) }
        assertFalse(Files.exists(output))
    }

    @Test fun compilerReceiptHasExactSchemaAndNoRuntimeAuthorityClaim() {
        val hash = "c".repeat(64)
        val bytes = receipt(hash)
        assertEquals(WindowsProfilePackageStage.CompilerPins(SOURCE, TREE, hash),
            WindowsProfilePackageStage.parseReceipt(bytes))
        assertTrue(bytes.toString(Charsets.US_ASCII).contains("COMPILER_BYTES_ONLY"))
    }

    @Test fun rejectsMalformedDuplicatedUnknownAndUnboundedReceiptFields() {
        val canonical = receipt("c".repeat(64)).toString(Charsets.US_ASCII)
        for (invalid in listOf("", canonical.dropLast(1), canonical.replace("\n", "\r\n"),
            canonical + "approved=true\n", canonical.replace("schema=1", "schema=2"),
            canonical.replace("COMPILER_BYTES_ONLY", "RUNTIME_AUTHORITY"),
            canonical.replace(SOURCE, "A".repeat(40)), canonical.replace(TREE, "HEAD"),
            canonical.replace("c".repeat(64), "c".repeat(63)), "x".repeat(513))) {
            assertFails { WindowsProfilePackageStage.parseReceipt(invalid.toByteArray()) }
        }
    }

    @Test fun rejectsDirectoryDestinationFileWithoutDeletingIt() = fixture { root, dll, pins ->
        val output = root.resolve("stage")
        Files.writeString(output, "retain")
        assertFails { WindowsProfilePackageStage.stage(dll, pins, output) }
        assertEquals("retain", Files.readString(output))
    }

    @Test fun refusesDllOnlyAndManifestOnlyStagesWithoutRepairingThem() = fixture { root, dll, pins ->
        val output = root.resolve("stage")
        WindowsProfilePackageStage.stage(dll, pins, output)
        val manifest = Files.readAllBytes(output.resolve("component.manifest"))
        Files.delete(output.resolve("component.manifest"))
        assertFails { WindowsProfilePackageStage.stage(dll, pins, output) }
        assertFalse(Files.exists(output.resolve("component.manifest")))
        Files.delete(output.resolve(dll.fileName))
        Files.write(output.resolve("component.manifest"), manifest)
        assertFails { WindowsProfilePackageStage.stage(dll, pins, output) }
        assertFalse(Files.exists(output.resolve(dll.fileName)))
        assertContentEquals(manifest, Files.readAllBytes(output.resolve("component.manifest")))
    }

    @Test fun parentJarGetsIndependentExactManifestAndDllPins() = fixture { root, dll, pins ->
        val staged = WindowsProfilePackageStage.stage(dll, pins, root.resolve("stage"))
        val parent = root.resolve("parent-resources")
        WindowsProfilePackageStage.writeParentPin(parent, staged)
        val pin = parent.resolve(WindowsProfilePackageStage.PARENT_PIN_RESOURCE)
        val expected = "schema=1\nscope=PACKAGED_COMPONENT_PIN_NOT_LOAD_AUTHORITY\n" +
            "source=$SOURCE\ntree=$TREE\nmanifestSha256=${staged.manifestSha256}\n" +
            "dllSha256=${staged.dllSha256}\n"
        assertEquals(expected, Files.readString(pin))
        WindowsProfilePackageStage.writeParentPin(parent, staged)
        // Changing an adjacent sidecar cannot update the parent resource silently.
        Files.writeString(root.resolve("stage/component.manifest"), "replaced")
        assertEquals(expected, Files.readString(pin))
    }

    @Test fun parentJarPinRefusesDifferentPreviousData() = fixture { root, dll, pins ->
        val staged = WindowsProfilePackageStage.stage(dll, pins, root.resolve("stage"))
        val parent = root.resolve("parent-resources")
        WindowsProfilePackageStage.writeParentPin(parent, staged)
        val pin = parent.resolve(WindowsProfilePackageStage.PARENT_PIN_RESOURCE)
        Files.writeString(pin, "retain")
        assertFails { WindowsProfilePackageStage.writeParentPin(parent, staged) }
        assertEquals("retain", Files.readString(pin))
    }

    private fun fixture(test: (Path, Path, WindowsProfilePackageStage.CompilerPins) -> Unit) {
        val root = Files.createTempDirectory("rpc-package-stage-").toRealPath()
        try {
            val bytes = WindowsProfilePeFixture.create()
            val dll = root.resolve("p2pkit-windows-profile.dll")
            Files.write(dll, bytes)
            test(root, dll, WindowsProfilePackageStage.CompilerPins(SOURCE, TREE, hash(bytes)))
        } finally {
            Files.walk(root).use { paths -> paths.sorted(Comparator.reverseOrder()).forEach(Files::delete) }
        }
    }

    private fun receipt(hash: String) = ("schema=1\nscope=COMPILER_BYTES_ONLY\nsource=$SOURCE\n" +
        "tree=$TREE\nsha256=$hash\n").toByteArray(Charsets.US_ASCII)
    private fun hash(bytes: ByteArray) = MessageDigest.getInstance("SHA-256").digest(bytes)
        .joinToString("") { "%02x".format(it) }

    private companion object {
        const val SOURCE = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
        const val TREE = "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
    }
}
