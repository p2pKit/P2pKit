package dev.p2pkit.transport.lan

import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.nio.file.Files
import java.nio.file.Path
import java.nio.file.attribute.PosixFilePermissions
import java.security.MessageDigest
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith

/** Real POSIX staging adversaries; explicitly selected with the native producer task, not skipped in portable check. */
class MacLanArtifactTest {
    private val source = "1".repeat(40)
    private fun fixture(block: (Path, ByteArray) -> Unit) {
        val directory = Files.createTempDirectory(Path.of(System.getProperty("user.home")), ".p2pkit-native-test-")
        try {
            Files.setPosixFilePermissions(directory, PosixFilePermissions.fromString("rwx------"))
            val bytes = ByteBuffer.allocate(128).order(ByteOrder.LITTLE_ENDIAN)
                .putInt(0xfeedfacf.toInt()).putInt(0x0100000c).putInt(0).putInt(6).array()
            val digest = MessageDigest.getInstance("SHA-256").digest(bytes).joinToString("") { "%02x".format(it) }
            val manifest = "abi=1\nplatform=macos\narch=arm64\nsource=$source\ntree=${"2".repeat(40)}\n" +
                "file=libp2pkit_lan_socket.dylib\nbytes=${bytes.size}\nsha256=$digest\n"
            Files.write(directory.resolve("libp2pkit_lan_socket.dylib"), bytes)
            Files.writeString(directory.resolve("macos-tcp.properties"), manifest)
            Files.list(directory).use { it.forEach { file ->
                Files.setPosixFilePermissions(file, PosixFilePermissions.fromString("rw-------"))
            } }
            block(directory, manifest.toByteArray(Charsets.US_ASCII))
        } finally {
            // Test-created files only; no symlink traversal.
            Files.list(directory).use { it.forEach(Files::delete) }; Files.delete(directory)
        }
    }
    @Test fun exactTrustedArm64ManifestAndPrivateFilePassPreflightWithoutExecution() = fixture { dir, trusted ->
        assertEquals(source, MacLanArtifact.verify(dir, trusted, source).source)
    }
    @Test fun changedNativeHashFailsEvenWhenHeaderStillLooksValid() = fixture { dir, trusted ->
        val file = dir.resolve("libp2pkit_lan_socket.dylib")
        Files.write(file, Files.readAllBytes(file).also { it[100] = 1 })
        assertFailsWith<IllegalStateException> { MacLanArtifact.verify(dir, trusted, source) }
    }
    @Test fun jointlyEditedExternalManifestAndNativeStillFailClasspathPin() = fixture { dir, trusted ->
        val manifest = String(trusted).replace("sha256=", "sha256=0")
        Files.writeString(dir.resolve("macos-tcp.properties"), manifest)
        assertFailsWith<IllegalStateException> { MacLanArtifact.verify(dir, trusted, source) }
    }
    @Test fun wrongArchitectureAbiOrSourceCannotPassTrustedMetadata() = fixture { dir, original ->
        for (changed in listOf(String(original).replace("arch=arm64", "arch=x86_64"),
            String(original).replace("abi=1", "abi=2"),
            String(original).replace("source=$source", "source=${"3".repeat(40)}"))) {
            val bytes = changed.toByteArray(); Files.write(dir.resolve("macos-tcp.properties"), bytes)
            assertFailsWith<IllegalStateException> { MacLanArtifact.verify(dir, bytes, source) }
        }
    }
    @Test fun librarySymlinkAndHardlinkCannotPassEvenWithExactBytes() = fixture { dir, trusted ->
        val file = dir.resolve("libp2pkit_lan_socket.dylib"); val original = dir.resolve("original")
        Files.move(file, original); Files.createSymbolicLink(file, original)
        assertFailsWith<IllegalStateException> { MacLanArtifact.verify(dir, trusted, source) }
        Files.delete(file); Files.createLink(file, original)
        assertFailsWith<IllegalStateException> { MacLanArtifact.verify(dir, trusted, source) }
    }
    @Test fun groupWritableNativeOrStagingIsRejected() = fixture { dir, trusted ->
        val file = dir.resolve("libp2pkit_lan_socket.dylib")
        Files.setPosixFilePermissions(file, PosixFilePermissions.fromString("rw-rw----"))
        assertFailsWith<IllegalStateException> { MacLanArtifact.verify(dir, trusted, source) }
        Files.setPosixFilePermissions(file, PosixFilePermissions.fromString("rw-------"))
        Files.setPosixFilePermissions(dir, PosixFilePermissions.fromString("rwxrwx---"))
        assertFailsWith<IllegalStateException> { MacLanArtifact.verify(dir, trusted, source) }
    }
    @Test fun wrongMachHeaderFailsEvenIfTrustedHashMatches() = fixture { dir, original ->
        val file = dir.resolve("libp2pkit_lan_socket.dylib")
        val bytes = Files.readAllBytes(file).also { it[4] = 7 }; Files.write(file, bytes)
        val digest = MessageDigest.getInstance("SHA-256").digest(bytes).joinToString("") { "%02x".format(it) }
        val trusted = String(original).replace(Regex("sha256=[a-f0-9]{64}"), "sha256=$digest").toByteArray()
        Files.write(dir.resolve("macos-tcp.properties"), trusted)
        assertFailsWith<IllegalStateException> { MacLanArtifact.verify(dir, trusted, source) }
    }
}
