package dev.p2pkit.sample.rpc.profile

import dev.p2pkit.sample.rpc.RpcPhoneBuildStamp
import java.io.IOException
import java.nio.ByteBuffer
import java.nio.channels.FileChannel
import java.nio.file.Files
import java.nio.file.Path
import java.nio.file.StandardCopyOption.ATOMIC_MOVE
import java.nio.file.StandardCopyOption.REPLACE_EXISTING
import java.nio.file.StandardOpenOption.CREATE_NEW
import java.nio.file.StandardOpenOption.READ
import java.nio.file.StandardOpenOption.TRUNCATE_EXISTING
import java.nio.file.StandardOpenOption.WRITE
import java.security.MessageDigest
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put

/**
 * Explicit Windows-only ordinary temporary-file probe. Never loads its synthetic PE bytes or touches profiles.
 * It is not a normal JVM test with an OS skip. Invoke its separately registered Windows verification task.
 */
internal object WindowsProfilePinnedImageWindowsProbe {
    @JvmStatic
    fun main(args: Array<String>) {
        check(System.getProperty("os.name").startsWith("Windows", ignoreCase = true)) {
            "This probe requires actual Windows execution, not a skipped test"
        }
        require(args.size == 1) { "Expected a new absolute external output directory" }
        val output = Path.of(args.single())
        require(output.isAbsolute && output.normalize() == output && output.parent != null)
        Files.createDirectory(output)
        val fixture = Files.createDirectory(output.resolve("synthetic-final-file-pin"))
        val library = fixture.resolve(WindowsProfilePinnedImage.FILE_NAME)
        val moved = fixture.resolve("moved.synthetic")
        val replacement = fixture.resolve("replacement.synthetic")
        val original = WindowsProfilePeFixture.create()
        val manifest = manifest(original)
        val authority = authority(manifest)
        val passed = mutableListOf<String>()
        val created = mutableListOf<Path>()
        fun record(name: String, action: () -> Unit) { action(); passed += name }
        fun open() = WindowsProfilePinnedImage.open(library, manifest, authority)
        fun writeNew(path: Path, bytes: ByteArray) {
            Files.write(path, bytes, CREATE_NEW, WRITE)
            created.add(path)
        }
        var failure: Throwable? = null
        try {
            writeNew(library, original)
            writeNew(replacement, original)
            open().use { pin ->
                record("windows-original-channel-readback") {
                    check(pin.scope == WindowsProfilePinnedImage.Scope.WINDOWS_FINAL_FILE_BYTES_AND_SHARING_ONLY)
                    check(pin.verify().dllSha256 == hash(original))
                }
                record("compatible-reader-allowed") {
                    FileChannel.open(library, READ).use { check(it.size() == original.size.toLong()) }
                }
                record("write-open-denied") { requireIoAcquisitionRefused { FileChannel.open(library, WRITE) } }
                record("truncation-denied") {
                    requireIoAcquisitionRefused { FileChannel.open(library, WRITE, TRUNCATE_EXISTING) }
                    check(pin.verify().dllBytes == original.size)
                }
                record("rename-denied-while-pinned") { ioRefused { Files.move(library, moved) } }
                record("delete-denied-while-pinned") { ioRefused { Files.delete(library) } }
                record("replacement-denied-while-pinned") {
                    ioRefused { Files.move(replacement, library, REPLACE_EXISTING, ATOMIC_MOVE) }
                    check(pin.verify().dllSha256 == hash(original))
                }
            }
            record("same-replacement-succeeds-after-close") {
                Files.move(replacement, library, REPLACE_EXISTING, ATOMIC_MOVE)
                created.remove(replacement)
                check(Files.readAllBytes(library).contentEquals(original))
            }
            record("same-rename-succeeds-after-close") {
                Files.move(library, moved)
                created.remove(library)
                created.add(moved)
                Files.move(moved, library)
                created.remove(moved)
                created.add(library)
            }
            record("preexisting-writer-refuses-pin") {
                FileChannel.open(library, WRITE).use {
                    requireIoAcquisitionRefused({ it is WindowsProfilePinnedImage.OpenFailure }) { open() }
                }
                open().use { check(it.verify().dllBytes == original.size) }
            }
            val changed = original.copyOf().also { it[0x400] = 1 }
            record("changed-bytes-refused-and-failed-pin-retires") {
                Files.write(library, changed, WRITE, TRUNCATE_EXISTING)
                contentRefused { open().use { } }
                // Reopening for write proves the failed pin did not leak its no-write owner.
                FileChannel.open(library, WRITE).use { check(it.size() == changed.size.toLong()) }
            }
            record("joint-sidecar-and-dll-change-cannot-redefine-authority") {
                contentRefused {
                    WindowsProfilePinnedImage.open(library, manifest(changed), authority).use { }
                }
                FileChannel.open(library, WRITE).use { check(it.size() == changed.size.toLong()) }
            }
            record("restored-exact-bytes-allow-fresh-pin") {
                Files.write(library, original, WRITE, TRUNCATE_EXISTING)
                open().use { check(it.verify().dllSha256 == hash(original)) }
            }
            record("wrong-filename-refused") {
                contentRefused { WindowsProfilePinnedImage.open(moved, manifest, authority).use { } }
            }
            record("oversized-file-refused-and-retired") {
                FileChannel.open(library, WRITE).use {
                    it.write(ByteBuffer.wrap(byteArrayOf(0)), WindowsProfilePeImage.MAXIMUM_BYTES.toLong())
                }
                contentRefused { open().use { } }
                FileChannel.open(library, WRITE).use { it.truncate(0) }
            }
            record("empty-file-refused-and-retired") {
                contentRefused { open().use { } }
                FileChannel.open(library, WRITE).use { check(it.size() == 0L) }
            }
            record("ordinary-delete-succeeds-after-pin-retirement") {
                Files.delete(library)
                created.remove(library)
            }
        } catch (caught: Throwable) {
            failure = caught
        } finally {
            // Only this invocation's individually created synthetic files; never walk/delete a directory tree.
            for (path in created.asReversed()) {
                try { Files.delete(path) } catch (cleanup: Throwable) {
                    if (failure == null) failure = cleanup else if (failure !== cleanup) failure.addSuppressed(cleanup)
                }
            }
            try { Files.delete(fixture) } catch (cleanup: Throwable) {
                if (failure == null) failure = cleanup else if (failure !== cleanup) failure.addSuppressed(cleanup)
            }
        }
        val receipt = buildJsonObject {
            put("scope", "WINDOWS_SYNTHETIC_FINAL_FILE_PIN_ONLY_NOT_PROFILE_LOADER_OR_RELEASE")
            put("source", RpcPhoneBuildStamp.SOURCE_COMMIT)
            put("sourceClean", RpcPhoneBuildStamp.SOURCE_CLEAN)
            put("nativeExecution", "NOT_PERFORMED")
            put("profileAccess", "NOT_PERFORMED")
            put("result", if (failure == null) "PASS" else "FAIL")
            put("passedControls", JsonArray(passed.map(::JsonPrimitive)))
            put("cleanup", if (Files.exists(fixture)) "INCOMPLETE" else "RETIRED")
        }
        Files.writeString(output.resolve("final-file-pin-results.json"), "$receipt\n", CREATE_NEW, WRITE)
        failure?.let { throw it }
        println("WINDOWS_SYNTHETIC_FINAL_FILE_PIN_ONLY controls=${passed.size}; no native loading or profile access")
    }

    private fun ioRefused(action: () -> Unit) {
        var refused = false
        try { action() } catch (_: IOException) { refused = true }
        check(refused) { "Expected the real Windows filesystem operation to refuse" }
    }

    /** Tests only acquisition refusal. A close failure after successful acquisition must never be a pass. */
    internal fun requireIoAcquisitionRefused(
        accept: (IOException) -> Boolean = { true },
        acquire: () -> AutoCloseable,
    ) {
        val owner = try { acquire() } catch (failure: IOException) {
            if (!accept(failure)) throw failure
            return
        }
        val failure = IllegalStateException("Windows unexpectedly admitted the prohibited acquisition")
        try { owner.close() } catch (cleanup: Throwable) { failure.addSuppressed(cleanup) }
        throw failure
    }

    private fun contentRefused(action: () -> Unit) {
        var refused = false
        try { action() } catch (_: IllegalArgumentException) { refused = true }
        check(refused) { "Expected the bounded image/manifest policy to refuse" }
    }

    private fun manifest(bytes: ByteArray) =
        WindowsProfileByteManifest.produce("a".repeat(40), "b".repeat(40), true, bytes)

    private fun authority(manifest: ByteArray) =
        WindowsProfileByteManifest.Authority(hash(manifest), "a".repeat(40), "b".repeat(40))

    private fun hash(bytes: ByteArray): String = MessageDigest.getInstance("SHA-256").digest(bytes)
        .joinToString("") { "%02x".format(it) }
}
