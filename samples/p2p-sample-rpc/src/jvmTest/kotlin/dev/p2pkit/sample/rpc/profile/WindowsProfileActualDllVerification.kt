package dev.p2pkit.sample.rpc.profile

import java.nio.ByteBuffer
import java.nio.channels.FileChannel
import java.nio.file.Files
import java.nio.file.LinkOption.NOFOLLOW_LINKS
import java.nio.file.Path
import java.nio.file.StandardOpenOption.CREATE_NEW
import java.nio.file.StandardOpenOption.READ
import java.nio.file.StandardOpenOption.WRITE
import java.nio.file.attribute.BasicFileAttributes
import java.security.MessageDigest
import java.util.concurrent.TimeUnit
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put

/** Opt-in test tooling: inspects bytes, never loads native code or admits a filesystem path for execution. */
internal object WindowsProfileActualDllVerification {
    const val MANIFEST_FILE = "component.manifest"
    const val RECEIPT_FILE = "byte-verification.json"
    private const val DLL_FILE = "p2pkit-windows-profile.dll"
    private val sourcePattern = Regex("[a-f0-9]{40}")
    private val hashPattern = Regex("[a-f0-9]{64}")

    /** Independently captured compiler-receipt values, never read from a candidate sidecar. */
    data class Pins(val source: String, val tree: String, val dllSha256: String) {
        init {
            require(sourcePattern.matches(source) && sourcePattern.matches(tree)) { "Invalid compiler source pins" }
            require(hashPattern.matches(dllSha256)) { "Invalid compiler DLL digest" }
        }
    }

    @JvmStatic fun main(args: Array<String>) {
        require(args.size == 6) { "Expected root, DLL, source, tree, SHA-256 and new output directory" }
        val result = verify(Path.of(args[0]), Path.of(args[1]), Pins(args[2], args[3], args[4]), Path.of(args[5]))
        println("BYTE_MANIFEST_ONLY source=${result.source} dllSha256=${result.dllSha256}")
    }

    fun verify(
        root: Path,
        library: Path,
        pins: Pins,
        output: Path,
        sourceCheck: (Path, Pins) -> Unit = ::verifySource,
    ): WindowsProfileByteManifest.ByteAuthorization {
        require(listOf(root, library, output).all { it.isAbsolute && it == it.normalize() }) {
            "Explicit normalized absolute paths are required"
        }
        require(library.fileName?.toString() == DLL_FILE) { "Unexpected native input filename" }
        require(output.parent != null && output.fileName != null) { "A new output directory name is required" }
        val actualRoot = root.toRealPath()
        val actualOutput = output.parent.toRealPath().resolve(output.fileName)
        require(!actualOutput.startsWith(actualRoot)) { "Byte-verification output must be outside the source tree" }
        sourceCheck(actualRoot, pins)
        val bytes = snapshot(library)
        require(hash(bytes) == pins.dllSha256) { "DLL differs from the independently captured compiler digest" }
        // This is a new producer-side component record and a schema round-trip, not independent loader authority.
        val manifest = WindowsProfileByteManifest.produce(pins.source, pins.tree, true, bytes)
        val result = WindowsProfileByteManifest.authorize(
            manifest, bytes, WindowsProfileByteManifest.Authority(hash(manifest), pins.source, pins.tree),
        )
        sourceCheck(actualRoot, pins)
        Files.createDirectory(actualOutput) // Create-only: an old or partial observation is never overwritten.
        Files.write(actualOutput.resolve(MANIFEST_FILE), manifest, CREATE_NEW, WRITE)
        sourceCheck(actualRoot, pins)
        // No success receipt is emitted if either the source check or manifest write fails. Partial output is retained.
        Files.writeString(actualOutput.resolve(RECEIPT_FILE), receipt(result) + "\n", CREATE_NEW, WRITE)
        return result
    }

    private fun snapshot(path: Path): ByteArray {
        val before = Files.readAttributes(path, BasicFileAttributes::class.java, NOFOLLOW_LINKS)
        require(before.isRegularFile && !before.isSymbolicLink &&
            before.size() in 512L..WindowsProfilePeImage.MAXIMUM_BYTES.toLong()) { "Unsupported DLL file or size" }
        val bytes = ByteArray(before.size().toInt())
        FileChannel.open(path, READ, NOFOLLOW_LINKS).use { input ->
            require(input.size() == before.size()) { "DLL size changed before read" }
            val target = ByteBuffer.wrap(bytes)
            while (target.hasRemaining()) require(input.read(target) > 0) { "DLL ended before its bounded size" }
            require(input.read(ByteBuffer.allocate(1)) == -1 && input.size() == before.size()) {
                "DLL size changed during read"
            }
        }
        val after = Files.readAttributes(path, BasicFileAttributes::class.java, NOFOLLOW_LINKS)
        require(after.isRegularFile && !after.isSymbolicLink && after.size() == before.size() &&
            after.fileKey() == before.fileKey() && after.lastModifiedTime() == before.lastModifiedTime()) {
            "DLL file observation changed during read"
        }
        return bytes // Hash pins these bytes only; no pathname custody or future-load guarantee is claimed.
    }

    fun requireSource(pins: Pins, source: String, tree: String, status: String) {
        require(source == pins.source && tree == pins.tree && status.isEmpty()) {
            "Byte verification requires the exact clean compiler source and tree"
        }
    }

    private fun verifySource(root: Path, pins: Pins) {
        require(Path.of(git(root, "rev-parse", "--show-toplevel")).toRealPath() == root) {
            "Expected repository root"
        }
        requireSource(pins, git(root, "rev-parse", "HEAD"), git(root, "rev-parse", "HEAD^{tree}"),
            git(root, "status", "--porcelain=v1", "--untracked-files=all"))
    }

    private fun git(root: Path, vararg arguments: String): String {
        // Redirect to an owned temporary file rather than allowing a full stdout pipe to deadlock waitFor.
        // These metadata commands have no hooks; disable fsmonitor and optional index writes explicitly.
        val log = Files.createTempFile("rpc-byte-git-", ".log")
        var process: Process? = null
        try {
            process = ProcessBuilder(listOf("git", "--no-optional-locks", "-c", "core.fsmonitor=false") + arguments)
                .directory(root.toFile()).redirectErrorStream(true).redirectOutput(log.toFile()).start()
            process.outputStream.close()
            check(process.waitFor(10, TimeUnit.SECONDS)) { "Source inspection exceeded its deadline" }
            check(process.exitValue() == 0) { "Source inspection failed" }
            require(Files.size(log) <= 8192) { "Source inspection output exceeds its bound" }
            return Files.newInputStream(log).use { input ->
                val bytes = input.readNBytes(8193)
                require(bytes.size <= 8192) { "Source inspection output exceeds its bound" }
                bytes.toString(Charsets.UTF_8).trimEnd('\r', '\n')
            }
        } finally {
            // Exit and each stream/file cleanup are attempted independently, including failure paths.
            try {
                process?.let {
                    if (it.isAlive) it.destroyForcibly()
                    check(it.waitFor(5, TimeUnit.SECONDS) && !it.isAlive) { "Source process did not retire" }
                }
            } finally {
                try { process?.inputStream?.close() } finally {
                    try { process?.errorStream?.close() } finally {
                        try { process?.outputStream?.close() } finally { Files.deleteIfExists(log) }
                    }
                }
            }
        }
    }

    private fun receipt(result: WindowsProfileByteManifest.ByteAuthorization): String = buildJsonObject {
        put("schema", 1)
        put("scope", result.scope.name)
        put("source", result.source)
        put("tree", result.tree)
        put("clean", true)
        put("file", result.file)
        put("bytes", result.dllBytes)
        put("sha256", result.dllSha256)
        put("manifest", MANIFEST_FILE)
        put("manifestSha256", result.manifestSha256)
        put("peStructure", "PASS")
        put("certificateTablePresent", result.hasCertificateTable)
        put("manifestAuthority", "PRODUCER_ROUND_TRIP_ONLY")
        put("signatureVerification", "NOT_PERFORMED")
        put("nativeLoad", "NOT_PERFORMED")
        put("nativeExecution", "NOT_PERFORMED")
        put("filesystemCustody", "NOT_QUALIFIED")
        put("runtimeQualification", "NOT_PERFORMED")
        put("releaseQualification", "NOT_PERFORMED")
    }.toString()

    private fun hash(bytes: ByteArray): String = MessageDigest.getInstance("SHA-256").digest(bytes)
        .joinToString("") { "%02x".format(it) }
}
