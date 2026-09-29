package dev.p2pkit.sample.rpc.lab

import java.nio.ByteBuffer
import java.nio.channels.FileChannel
import java.nio.file.Files
import java.nio.file.LinkOption
import java.nio.file.Path
import java.nio.file.StandardCopyOption
import java.nio.file.StandardOpenOption
import java.nio.file.attribute.PosixFilePermissions
import java.security.MessageDigest

/** POSIX-only synthetic lab files. Nothing in this source set is a production storage default. */
internal object LabFiles {
    private val directoryMode = PosixFilePermissions.fromString("rwx------")
    private val fileMode = PosixFilePermissions.fromString("rw-------")
    private val directoryAttribute = PosixFilePermissions.asFileAttribute(directoryMode)
    private val fileAttribute = PosixFilePermissions.asFileAttribute(fileMode)

    fun privateDirectory(path: Path): Path {
        require(path.isAbsolute && path.normalize() == path)
        var cursor: Path? = path
        while (cursor != null) {
            require(!Files.isSymbolicLink(cursor)) { "Symlinked lab directory" }
            cursor = cursor.parent
        }
        require(Files.isDirectory(path, LinkOption.NOFOLLOW_LINKS))
        require(Files.getPosixFilePermissions(path, LinkOption.NOFOLLOW_LINKS) == directoryMode)
        require(Files.getOwner(path) == Files.getOwner(Path.of(System.getProperty("user.home"))))
        return path
    }

    fun newDirectory(parent: Path, name: String): Path {
        privateDirectory(parent)
        require(name.matches(Regex("[a-z0-9-]{1,64}")))
        return privateDirectory(Files.createDirectory(parent.resolve(name), directoryAttribute))
    }

    fun read(path: Path, maximum: Int = 262_144): ByteArray {
        privateDirectory(path.parent)
        require(!Files.isSymbolicLink(path) && Files.isRegularFile(path, LinkOption.NOFOLLOW_LINKS))
        require(Files.getPosixFilePermissions(path, LinkOption.NOFOLLOW_LINKS) == fileMode)
        require(Files.getOwner(path) == Files.getOwner(path.parent))
        FileChannel.open(path, StandardOpenOption.READ, LinkOption.NOFOLLOW_LINKS).use { channel ->
            require(channel.size() in 0..maximum.toLong())
            val buffer = ByteBuffer.allocate(maximum + 1)
            while (buffer.hasRemaining() && channel.read(buffer) != -1) { /* bounded owned read */ }
            require(buffer.position() <= maximum)
            return buffer.array().copyOf(buffer.position())
        }
    }

    fun write(path: Path, bytes: ByteArray, replace: Boolean = false) {
        privateDirectory(path.parent)
        require(bytes.size <= 262_144 && !Files.isSymbolicLink(path))
        require(replace || !Files.exists(path, LinkOption.NOFOLLOW_LINKS))
        val temporary = Files.createTempFile(path.parent, ".lab-", ".tmp", fileAttribute)
        try {
            FileChannel.open(temporary, StandardOpenOption.WRITE, LinkOption.NOFOLLOW_LINKS).use { channel ->
                val buffer = ByteBuffer.wrap(bytes)
                while (buffer.hasRemaining()) channel.write(buffer)
                channel.force(true)
            }
            // ATOMIC_MOVE may replace an existing target even without REPLACE_EXISTING.
            // A hard link publishes the already-fsynced inode with atomic create-if-absent
            // semantics. Both cases fail closed when the POSIX filesystem cannot honor them.
            if (replace) {
                if (Files.exists(path, LinkOption.NOFOLLOW_LINKS)) read(path)
                Files.move(temporary, path, StandardCopyOption.ATOMIC_MOVE, StandardCopyOption.REPLACE_EXISTING)
            } else {
                Files.createLink(path, temporary)
            }
            syncDirectory(path.parent)
        } finally { Files.deleteIfExists(temporary) }
    }

    fun syncDirectory(path: Path) {
        FileChannel.open(privateDirectory(path), StandardOpenOption.READ).use { it.force(true) }
    }

    fun lockChannel(path: Path): FileChannel = FileChannel.open(
        path, setOf(StandardOpenOption.CREATE, StandardOpenOption.WRITE, LinkOption.NOFOLLOW_LINKS), fileAttribute,
    )

    fun parse(bytes: ByteArray): Map<String, String> {
        require(bytes.size <= 262_144 && bytes.all { it == 10.toByte() || it.toInt() in 32..126 })
        val values = linkedMapOf<String, String>()
        for (line in bytes.toString(Charsets.US_ASCII).split('\n').filter { it.isNotEmpty() }) {
            val pair = line.split('=', limit = 2)
            require(pair.size == 2 && pair[0].matches(Regex("[a-zA-Z][a-zA-Z0-9]{0,63}")))
            require(pair[1].isNotEmpty() && values.put(pair[0], pair[1]) == null) { "Duplicate/empty lab field" }
        }
        return values
    }

    fun encode(values: Map<String, String>): ByteArray = values.entries.joinToString("\n", postfix = "\n") {
        require(it.value.isNotEmpty() && it.value.all { c -> c.code in 32..126 })
        "${it.key}=${it.value}"
    }.toByteArray(Charsets.US_ASCII).also { require(parse(it) == values) }

    fun sha256(bytes: ByteArray): String = MessageDigest.getInstance("SHA-256").digest(bytes)
        .joinToString("") { "%02x".format(it) }
}
