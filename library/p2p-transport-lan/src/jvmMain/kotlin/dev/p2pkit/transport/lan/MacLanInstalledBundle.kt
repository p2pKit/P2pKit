package dev.p2pkit.transport.lan

import java.net.JarURLConnection
import java.net.URL
import java.nio.file.Files
import java.nio.file.LinkOption.NOFOLLOW_LINKS
import java.nio.file.Path

/**
 * Opt-in checksum-bound DEVELOPMENT-ADHOC bundles, not Developer ID, notarization or publisher authentication.
 * Root/admin installation is an explicit trust boundary. This never weakens the private producer verifier.
 */
internal object MacLanInstalledBundle {
    const val POLICY_PROPERTY = "dev.p2pkit.lan.macos.installedPolicy"
    const val DEVELOPMENT_POLICY = "development-adhoc-v1"
    const val NATIVE_RELATIVE = "Contents/app/resources/p2pkit-native/macos-arm64"

    fun currentExecutable(): Path = Path.of(checkNotNull(ProcessHandle.current().info().command().orElse(null)) {
        "Cannot establish the actual application executable"
    })

    fun bundleDirectory(executable: Path): Path {
        canonical(executable)
        check(executable.parent?.fileName.toString() == "MacOS" &&
            executable.parent?.parent?.fileName.toString() == "Contents") { "Not a packaged application launcher" }
        return checkNotNull(executable.parent?.parent?.parent).also {
            check(it.fileName.toString().endsWith(".app")) { "Not an application bundle" }
        }
    }

    fun nativeDirectory(executable: Path): Path = bundleDirectory(executable).resolve(NATIVE_RELATIVE)

    /** Testable file/signature preflight; this method never loads the candidate dylib. */
    fun verify(
        executable: Path,
        codeSource: URL,
        manifestResource: URL,
        trusted: ByteArray,
        expectedSource: String,
        command: (List<String>) -> String = ::runCommand,
    ): MacLanArtifact {
        check(System.getProperty("os.name") == "Mac OS X" &&
            System.getProperty("os.arch") in setOf("aarch64", "arm64"))
        val bundle = bundleDirectory(executable)
        val directory = nativeDirectory(executable)
        check(codeSource.protocol == "file")
        val codeJar = Path.of(codeSource.toURI())
        check(manifestResource.protocol == "jar") { "Installed manifest must belong to a bundle JAR" }
        val connection = manifestResource.openConnection() as? JarURLConnection
            ?: error("Not a JAR manifest resource")
        connection.useCaches = false
        check(connection.jarFileURL.protocol == "file" && connection.entryName == MacLanNativeLoader.RESOURCE)
        val manifestJar = Path.of(connection.jarFileURL.toURI())
        for (jar in listOf(codeJar, manifestJar)) {
            canonical(jar)
            check(jar.parent == bundle.resolve("Contents/app") && jar.fileName.toString().endsWith(".jar")) {
                "Native authority is outside the actual executable's application bundle"
            }
        }
        val uid = command(listOf("/usr/bin/id", "-u")).trim().toLongOrNull()
        check(uid != null && uid >= 0)
        val files = listOf(executable, codeJar, manifestJar, bundle.resolve("Contents/Info.plist"),
            directory.resolve("macos-tcp.properties"), directory.resolve("libp2pkit_lan_socket.dylib"))
        val checkedDirectories = linkedSetOf<Path>()
        for (file in files) {
            canonical(file)
            check(file.startsWith(bundle))
            var ancestor = file.parent
            while (ancestor != null) {
                if (checkedDirectories.add(ancestor)) verifyDirectory(ancestor, uid, bundle)
                ancestor = ancestor.parent
            }
            regularFile(file, uid)
        }
        // POSIX bits do not describe allow ACLs. Reject every allow ACL rather than infer effective permissions.
        val acl = command(listOf("/bin/ls", "-lde", "--") + (checkedDirectories + files).map(Path::toString))
        verifyAclListing(acl, (checkedDirectories + files).map(Path::toString).toSet())
        val verified = MacLanArtifact.verifyPinnedFiles(directory, trusted, expectedSource) { regularFile(it, uid) }
        // Verify the complete resource seal and nested code, not only a conveniently signed dylib.
        command(listOf("/usr/bin/codesign", "--verify", "--strict", "--deep", "--all-architectures", bundle.toString()))
        requireAdHoc(command(listOf("/usr/bin/codesign", "--display", "--verbose=4", bundle.toString())))
        command(listOf("/usr/bin/codesign", "--verify", "--strict", "--all-architectures", verified.library.toString()))
        requireAdHoc(command(listOf("/usr/bin/codesign", "--display", "--verbose=4", verified.library.toString())))
        return verified
    }

    internal fun verifyAclListing(listing: String, expected: Set<String>) {
        val headers = mutableSetOf<String>()
        var hasHeader = false
        for (line in listing.lineSequence().filter { it.isNotEmpty() }) {
            if (line.first().isWhitespace()) {
                check(hasHeader && line.matches(Regex("\\s+[0-9]+: .+ deny .+")) && " allow " !in line) {
                    "Installed native ancestry has an unsupported ACL"
                }
            } else {
                check(line.matches(Regex("[d-][rwxStTs-]{9}[+@ ]\\s+.+"))) { "Invalid ACL listing header" }
                val matches = expected.filter { line.endsWith(" $it") }
                check(matches.size == 1 && headers.add(matches.single())) { "Unexpected ACL listing path" }
                hasHeader = true
            }
        }
        check(expected.isNotEmpty() && headers == expected) { "Incomplete ACL ancestry inspection" }
    }

    internal fun requireAdHoc(metadata: String) {
        val fields = metadata.lineSequence().filter { '=' in it }
            .map { it.substringBefore('=') to it.substringAfter('=') }.toList()
        check(fields.count { it.first == "Signature" } == 1 &&
            fields.single { it.first == "Signature" }.second == "adhoc")
        check(fields.count { it.first == "TeamIdentifier" } == 1 &&
            fields.single { it.first == "TeamIdentifier" }.second == "not set")
        val flags = Regex("(?m)^CodeDirectory .* flags=0x([0-9a-fA-F]+)(?:\\([^\\r\\n]*\\))? ")
            .findAll(metadata).toList()
        check(flags.size == 1 && (flags.single().groupValues[1].toLong(16) and 2L) != 0L) {
            "Installed development policy requires an explicit ad-hoc signature"
        }
    }

    internal fun allowedDirectory(path: Path, owner: Long, group: Long, mode: Int, uid: Long, bundle: Path): Boolean {
        if (owner != 0L && owner != uid || mode and 0xe00 != 0) return false
        if (mode and 0b10010 == 0) return true
        // Only this exact OS installation directory can delegate replacement to the built-in admin group.
        return path == Path.of("/Applications") && !path.startsWith(bundle) && owner == 0L && group == 80L &&
            mode and 0xfff == 0x1fd // 0775; no special bits, world write, or generalized group-write exception.
    }

    private fun verifyDirectory(path: Path, uid: Long, bundle: Path) {
        check(!Files.isSymbolicLink(path) && Files.isDirectory(path, NOFOLLOW_LINKS))
        check(allowedDirectory(path, unix(path, "uid"), unix(path, "gid"), unix(path, "mode").toInt(), uid, bundle)) {
            "Installed native ancestor ownership or permissions are unsafe"
        }
    }

    private fun regularFile(path: Path, uid: Long) {
        check(!Files.isSymbolicLink(path) && Files.isRegularFile(path, NOFOLLOW_LINKS))
        check(unix(path, "uid") in setOf(0L, uid) && unix(path, "nlink") == 1L)
        check(unix(path, "mode").toInt() and (0b10010 or 0xe00) == 0) {
            "Installed native file is group/world writable"
        }
    }

    private fun canonical(path: Path) {
        check(path.isAbsolute && path.normalize() == path && path.toString().none { it.isISOControl() })
    }

    private fun unix(path: Path, key: String): Long =
        (Files.getAttribute(path, "unix:$key", NOFOLLOW_LINKS) as Number).toLong()

    /** Fixed system tools only; the bounded executor owns every owned process/stream cleanup path. */
    private fun runCommand(arguments: List<String>): String {
        check(arguments.first() in setOf("/usr/bin/id", "/bin/ls", "/usr/bin/codesign"))
        val process = ProcessBuilder(arguments).redirectErrorStream(true).apply {
            environment().clear()
            environment()["LC_ALL"] = "C"
            environment()["PATH"] = "/usr/bin:/bin"
        }.start()
        return MacLanVerificationCommand.collect(process)
    }
}
