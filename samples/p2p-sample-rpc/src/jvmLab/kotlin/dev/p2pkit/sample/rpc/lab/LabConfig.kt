package dev.p2pkit.sample.rpc.lab

import dev.p2pkit.transport.lan.OrganizationLan
import java.nio.file.Files
import java.nio.file.Path
import java.security.MessageDigest

internal class LabConfig(val directory: Path, val values: Map<String, String>) {
    val role: String = values.getValue("role")
    val runLabel: String = values.getValue("runLabel")
    val sourceSha: String = values.getValue("sourceSha")
    val endpointAddress: String = values.getValue("endpointAddress")
    val port: Int = values.getValue("port").toInt()
    val lan = OrganizationLan(
        values.getValue("subnets").split(','), values.getValue("interface"),
        values.getValue("localAddress"), if (role == "host") port else 0,
    )

    init {
        require(values.keys == setOf(
            "schema", "role", "runLabel", "sourceSha", "endpointAddress", "port", "subnets",
            "interface", "localAddress",
        ))
        require(values.getValue("schema") == "1" && role in setOf("host", "client"))
        require(runLabel.matches(Regex("[a-z0-9-]{1,64}")) && sourceSha.matches(Regex("[a-f0-9]{40}")))
        require(port in 1024..65535 && lan.allows(endpointAddress))
    }

    companion object {
        fun load(expectedRole: String): LabConfig {
            check(System.getenv("RPC_CAPACITY_LAB_AUTHORIZED") == "synthetic-private-network-only")
            val file = Path.of(checkNotNull(System.getenv("RPC_CAPACITY_LAB_CONFIG")))
            require(file.isAbsolute && file.normalize() == file && file.fileName.toString() == "config.txt")
            return LabConfig(LabFiles.privateDirectory(file.parent), LabFiles.parse(LabFiles.read(file))).also {
                require(it.role == expectedRole)
            }
        }
    }
}

/** Digest the real runtime classpath bytes/order, not a caller-invented artifact hash. */
internal fun artifactDigest(directory: Path): String {
    val entries = System.getProperty("java.class.path").split(java.io.File.pathSeparator).map(Path::of)
    val manifest = linkedMapOf<String, String>()
    var total = 0L
    entries.forEachIndexed { index, path ->
        require(!Files.isSymbolicLink(path))
        val files = if (Files.isDirectory(path)) Files.walk(path).use { stream ->
            stream.filter { Files.isRegularFile(it) }.sorted().limit(20_001).toList()
        } else listOf(path)
        require(files.size <= 20_000)
        for ((number, file) in files.withIndex()) {
            require(!Files.isSymbolicLink(file) && Files.isRegularFile(file))
            val digest = MessageDigest.getInstance("SHA-256")
            Files.newInputStream(file).use { input ->
                val buffer = ByteArray(64 * 1024)
                while (true) {
                    val read = input.read(buffer)
                    if (read < 0) break
                    total += read
                    require(total <= 2L * 1024 * 1024 * 1024)
                    digest.update(buffer, 0, read)
                }
            }
            val relative = if (Files.isDirectory(path)) path.relativize(file).toString() else file.fileName.toString()
            manifest["entry${index}file$number"] = relative + ":" +
                digest.digest().joinToString("") { "%02x".format(it) }
        }
    }
    require(manifest.isNotEmpty())
    val bytes = LabFiles.encode(manifest)
    LabFiles.write(directory.resolve("artifact-manifest.txt"), bytes)
    return LabFiles.sha256(bytes)
}
