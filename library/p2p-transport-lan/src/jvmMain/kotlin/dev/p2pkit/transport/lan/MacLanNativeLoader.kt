package dev.p2pkit.transport.lan

import java.io.IOException
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.nio.file.Files
import java.nio.file.LinkOption.NOFOLLOW_LINKS
import java.nio.file.Path
import java.security.MessageDigest

/** Explicit local ARM64 producer only. No library search, extraction, unsigned fallback, or discovery scope claim. */
internal object MacLanNativeLoader {
    const val DIRECTORY_PROPERTY = "dev.p2pkit.lan.macos.nativeDir"
    const val RESOURCE = "META-INF/p2pkit/macos-tcp.properties"
    private var loaded: Pair<Path, MacLanErrnos>? = null
    private var poisoned: Throwable? = null

    @Synchronized fun configuredBinding(policy: OrganizationLan): MacLanBinding? {
        val configured = System.getProperty(DIRECTORY_PROPERTY) ?: return null
        poisoned?.let {
            if (it is Error && it !is LinkageError) throw it
            throw IOException("Scoped TCP native load previously failed", it)
        }
        try {
            val path = Path.of(configured)
            val existing = loaded
            if (existing != null) {
                check(existing.first == path) { "Scoped TCP native directory changed" }
                return MacLanBinding(policy, MacLanNative, existing.second)
            }
            check(System.getProperty("os.name") == "Mac OS X" &&
                System.getProperty("os.arch") in setOf("aarch64", "arm64")) { "Scoped TCP requires macOS ARM64" }
            check(MacLanBuildStamp.SOURCE_CLEAN) { "Scoped TCP requires a clean compiled source identity" }
            val resources = MacLanNativeLoader::class.java.classLoader.getResources(RESOURCE).toList()
            check(resources.size == 1) { "Scoped TCP requires one trusted classpath manifest" }
            val trusted = resources.single().openStream().use { stream ->
                stream.readNBytes(4097).also { check(it.size <= 4096) }
            }
            val verified = MacLanArtifact.verify(path, trusted, MacLanBuildStamp.SOURCE_COMMIT)
            System.load(verified.library.toString())
            // Recheck file identity/content after dyld. Same-user classpath/build compromise is outside this boundary.
            check(MacLanArtifact.verify(path, trusted, MacLanBuildStamp.SOURCE_COMMIT) == verified)
            check(MacLanNative.abi() == 1) { "Scoped TCP native ABI mismatch" }
            check(MacLanNative.source() == "${verified.source}:${verified.tree}") {
                "Scoped TCP native source mismatch"
            }
            val errors = MacLanErrnos(MacLanNative.constants())
            loaded = path to errors
            return MacLanBinding(policy, MacLanNative, errors)
        } catch (failure: Throwable) {
            poisoned = failure
            if (failure is Error && failure !is LinkageError) throw failure
            throw IOException("Scoped TCP native admission failed; no portable fallback", failure)
        }
    }
}

/** Pure file preflight is separately testable; it never calls System.load. */
internal data class MacLanArtifact(
    val library: Path,
    val source: String,
    val tree: String,
    val key: Any,
    val digest: String,
) {
    companion object {
        fun verify(directory: Path, trusted: ByteArray, expectedSource: String): MacLanArtifact {
            check(directory.isAbsolute && directory.normalize() == directory) {
                "Native path must be absolute/canonical"
            }
            val uid = (Files.getAttribute(Path.of(System.getProperty("user.home")), "unix:uid") as Number).toLong()
            var ancestor: Path? = directory
            while (ancestor != null) {
                check(!Files.isSymbolicLink(ancestor) && Files.isDirectory(ancestor, NOFOLLOW_LINKS))
                val owner = (Files.getAttribute(ancestor, "unix:uid", NOFOLLOW_LINKS) as Number).toLong()
                val mode = (Files.getAttribute(ancestor, "unix:mode", NOFOLLOW_LINKS) as Number).toInt()
                check(owner == 0L || owner == uid)
                check(mode and 0b10010 == 0) { "Native ancestor is group/world writable" }
                ancestor = ancestor.parent
            }
            val manifest = directory.resolve("macos-tcp.properties")
            secureFile(manifest, uid)
            check(trusted.size in 1..4096 && Files.size(manifest) == trusted.size.toLong())
            check(Files.readAllBytes(manifest).contentEquals(trusted)) { "Native manifest is not classpath-pinned" }
            val text = trusted.toString(Charsets.US_ASCII)
            check(text.toByteArray(Charsets.US_ASCII).contentEquals(trusted) && text.endsWith('\n'))
            val entries = text.dropLast(1).split('\n').map {
                val pieces = it.split('='); check(pieces.size == 2); pieces[0] to pieces[1]
            }
            check(entries.map { it.first }.toSet().size == entries.size)
            val values = entries.toMap()
            check(values.keys == setOf("abi", "platform", "arch", "source", "tree", "file", "bytes", "sha256"))
            check(values["abi"] == "1" && values["platform"] == "macos" && values["arch"] == "arm64")
            val source = checkNotNull(values["source"])
            val tree = checkNotNull(values["tree"])
            check(source == expectedSource && source.matches(Regex("[a-f0-9]{40}")))
            check(tree.matches(Regex("[a-f0-9]{40}")))
            check(values["file"] == "libp2pkit_lan_socket.dylib")
            val file = directory.resolve(checkNotNull(values["file"]))
            secureFile(file, uid)
            val size = values["bytes"]?.toLongOrNull()
            check(size != null && size in 32..4_194_304 && Files.size(file) == size)
            val digest = checkNotNull(values["sha256"])
            check(digest.matches(Regex("[a-f0-9]{64}")))
            val bytes = Files.readAllBytes(file)
            val header = ByteBuffer.wrap(bytes).order(ByteOrder.LITTLE_ENDIAN)
            check(header.int == 0xfeedfacf.toInt() && header.int == 0x0100000c)
            header.int // CPU subtype may be ARM64_ALL; universal/x86 or arbitrary executables are not admitted.
            check(header.int == 6) { "Native file is not an ARM64 Mach-O dylib" }
            check(MessageDigest.getInstance("SHA-256").digest(bytes).joinToString("") { "%02x".format(it) } == digest)
            val key = checkNotNull(Files.readAttributes(file, java.nio.file.attribute.BasicFileAttributes::class.java,
                NOFOLLOW_LINKS).fileKey())
            return MacLanArtifact(file, source, tree, key, digest)
        }

        private fun secureFile(file: Path, uid: Long) {
            check(!Files.isSymbolicLink(file) && Files.isRegularFile(file, NOFOLLOW_LINKS))
            check((Files.getAttribute(file, "unix:uid", NOFOLLOW_LINKS) as Number).toLong() == uid)
            check((Files.getAttribute(file, "unix:nlink", NOFOLLOW_LINKS) as Number).toInt() == 1)
            check((Files.getAttribute(file, "unix:mode", NOFOLLOW_LINKS) as Number).toInt() and 0b111111 == 0)
        }
    }
}
