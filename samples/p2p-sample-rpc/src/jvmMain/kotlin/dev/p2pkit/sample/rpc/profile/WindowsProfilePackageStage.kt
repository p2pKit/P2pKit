package dev.p2pkit.sample.rpc.profile

import java.nio.ByteBuffer
import java.nio.channels.FileChannel
import java.nio.file.Files
import java.nio.file.LinkOption.NOFOLLOW_LINKS
import java.nio.file.Path
import java.nio.file.StandardOpenOption.CREATE_NEW
import java.nio.file.StandardOpenOption.READ
import java.nio.file.StandardOpenOption.WRITE
import java.security.MessageDigest

/**
 * Existing Desktop packaging's byte-only producer. The compiler receipt is an input, NOT a runtime load authority.
 * Deliberately neither loads native code nor promotes WindowsProfileAvailability.
 */
internal object WindowsProfilePackageStage {
    private const val LIBRARY = "p2pkit-windows-profile.dll"
    private const val MANIFEST = "component.manifest"
    private const val RECEIPT_LIMIT = 512
    const val PARENT_PIN_RESOURCE = "META-INF/p2pkit/windows-profile-parent.properties"

    data class CompilerPins(val source: String, val tree: String, val sha256: String)

    @JvmStatic fun main(args: Array<String>) {
        require(args.size == 4) { "Expected compiler DLL, receipt, native resources and parent-JAR resources" }
        val receipt = readBounded(Path.of(args[1]), 1, RECEIPT_LIMIT)
        val staged = stage(Path.of(args[0]), parseReceipt(receipt), Path.of(args[2]))
        writeParentPin(Path.of(args[3]), staged)
        println("WINDOWS_PROFILE_PACKAGE_BYTES_STAGED_NOT_LOADED_OR_RUNTIME_QUALIFIED")
    }

    fun parseReceipt(bytes: ByteArray): CompilerPins {
        require(bytes.size in 1..RECEIPT_LIMIT && bytes.all { it == 10.toByte() || it.toInt() in 32..126 }) {
            "Unsupported compiler receipt encoding or size"
        }
        val pattern = Regex(
            "schema=1\\nscope=COMPILER_BYTES_ONLY\\nsource=([a-f0-9]{40})\\n" +
                "tree=([a-f0-9]{40})\\nsha256=([a-f0-9]{64})\\n",
        )
        val match = pattern.matchEntire(bytes.toString(Charsets.US_ASCII))
            ?: error("Unsupported compiler receipt fields")
        return CompilerPins(match.groupValues[1], match.groupValues[2], match.groupValues[3])
    }

    fun stage(library: Path, pins: CompilerPins, output: Path): WindowsProfileByteManifest.ByteAuthorization {
        require(listOf(library, output).all { it.isAbsolute && it == it.normalize() }) {
            "Absolute normalized packaging paths are required"
        }
        require(library.fileName.toString() == LIBRARY) { "Unsupported compiler filename" }
        val bytes = readBounded(library, 512, WindowsProfilePeImage.MAXIMUM_BYTES)
        require(hash(bytes) == pins.sha256) { "DLL differs from the compiler receipt" }
        val manifest = WindowsProfileByteManifest.produce(pins.source, pins.tree, true, bytes)
        val result = WindowsProfileByteManifest.authorize(
            manifest, bytes, WindowsProfileByteManifest.Authority(hash(manifest), pins.source, pins.tree),
        )
        // Idempotent only for an exact prior byte stage. Keep partial/mismatching outputs for inspection.
        // This does not make the directory safe for execution; installed loader admission remains separate.
        Files.createDirectories(output)
        require(Files.isDirectory(output, NOFOLLOW_LINKS)) { "Staging destination is not an ordinary directory" }
        val contents = Files.newDirectoryStream(output).use { entries ->
            val names = mutableSetOf<String>()
            for (entry in entries) {
                val name = entry.fileName.toString()
                require(names.size < 2 && name in setOf(LIBRARY, MANIFEST) && names.add(name)) {
                    "Unexpected existing-app native staging content"
                }
            }
            require(names.isEmpty() || names == setOf(LIBRARY, MANIFEST)) {
                "Partial or unexpected existing-app native staging content"
            }
            names
        }
        if (contents.isEmpty()) {
            writeOrVerify(output.resolve(LIBRARY), bytes)
            writeOrVerify(output.resolve(MANIFEST), manifest)
        } else {
            // Both must match before accepting an existing stage; never fill in or repair partial output.
            require(readBounded(output.resolve(LIBRARY), bytes.size, bytes.size).contentEquals(bytes) &&
                readBounded(output.resolve(MANIFEST), manifest.size, manifest.size).contentEquals(manifest)) {
                "Refusing to replace a different or incomplete native stage"
            }
        }
        return result
    }

    /** Separate parent-JAR data, never accepted from the mutable DLL sidecar or as standalone load authority. */
    fun writeParentPin(output: Path, staged: WindowsProfileByteManifest.ByteAuthorization) {
        require(output.isAbsolute && output == output.normalize()) { "An absolute parent-resource root is required" }
        val pin = output.resolve(PARENT_PIN_RESOURCE)
        Files.createDirectories(pin.parent)
        require(Files.isDirectory(pin.parent, NOFOLLOW_LINKS)) { "Parent pin destination is not a directory" }
        val contents = "schema=1\nscope=PACKAGED_COMPONENT_PIN_NOT_LOAD_AUTHORITY\n" +
            "source=${staged.source}\ntree=${staged.tree}\n" +
            "manifestSha256=${staged.manifestSha256}\ndllSha256=${staged.dllSha256}\n"
        writeOrVerify(pin, contents.toByteArray(Charsets.US_ASCII))
    }

    private fun writeOrVerify(path: Path, bytes: ByteArray) {
        if (Files.exists(path, NOFOLLOW_LINKS)) {
            require(readBounded(path, bytes.size, bytes.size).contentEquals(bytes)) {
                "Refusing to replace a different or incomplete native stage"
            }
        } else {
            Files.write(path, bytes, CREATE_NEW, WRITE)
        }
        require(readBounded(path, bytes.size, bytes.size).contentEquals(bytes)) { "Native stage readback differs" }
    }

    private fun readBounded(path: Path, minimum: Int, maximum: Int): ByteArray {
        require(Files.isRegularFile(path, NOFOLLOW_LINKS)) { "Packaging input is not an ordinary file" }
        FileChannel.open(path, READ, NOFOLLOW_LINKS).use { input ->
            val size = input.size()
            require(size in minimum.toLong()..maximum.toLong()) { "Packaging input exceeds its size bounds" }
            val bytes = ByteArray(size.toInt())
            val buffer = ByteBuffer.wrap(bytes)
            while (buffer.hasRemaining()) require(input.read(buffer) > 0) { "Packaging input ended early" }
            require(input.read(ByteBuffer.allocate(1)) == -1 && input.size() == size) {
                "Packaging input changed size"
            }
            return bytes
        }
    }

    private fun hash(bytes: ByteArray): String = MessageDigest.getInstance("SHA-256").digest(bytes)
        .joinToString("") { "%02x".format(it) }
}
