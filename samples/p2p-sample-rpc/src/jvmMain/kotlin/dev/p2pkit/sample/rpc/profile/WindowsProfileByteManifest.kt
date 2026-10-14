package dev.p2pkit.sample.rpc.profile

import java.security.MessageDigest

/**
 * A private native-component byte-manifest prerequisite, not a release manifest or a secure DLL loader.
 * There are deliberately no filesystem, signature, native-call or application-availability operations here.
 */
internal object WindowsProfileByteManifest {
    const val MAXIMUM_MANIFEST_BYTES = 4096
    private const val FILE = "p2pkit-windows-profile.dll"
    private val keys = listOf(
        "schema", "component", "abi", "platform", "arch", "source", "tree", "clean",
        "file", "bytes", "sha256", "capabilities",
    )
    private val sourcePattern = Regex("[a-f0-9]{40}")
    private val hashPattern = Regex("[a-f0-9]{64}")

    /** Must come from the independently admitted parent application/producer, never the candidate sidecar. */
    data class Authority(val manifestSha256: String, val source: String, val tree: String) {
        init {
            require(hashPattern.matches(manifestSha256)) { "Invalid external native manifest pin" }
            require(sourcePattern.matches(source) && sourcePattern.matches(tree)) {
                "Invalid external native source pin"
            }
        }
    }

    enum class Scope { BYTE_MANIFEST_ONLY }

    /** Immutable observations only: no load path, executable bytes, signature verdict or release-ready flag. */
    data class ByteAuthorization(
        val manifestSha256: String,
        val source: String,
        val tree: String,
        val file: String,
        val dllSha256: String,
        val dllBytes: Int,
        val hasCertificateTable: Boolean,
        /** Immutable byte-table observations for later import-resolution checks, not loaded-module identities. */
        val namedImports: List<WindowsProfilePeImage.NamedImport>,
        /** Exact original export bindings and SizeOfImage; neither is observed native mapping authority. */
        val namedExports: List<WindowsProfilePeImage.NamedExport>,
        val imageBytes: Long,
    ) {
        val scope: Scope get() = Scope.BYTE_MANIFEST_ONLY
    }

    /**
     * Canonical component-manifest bytes for a future existing-app producer. Caller establishes clean Git custody
     * independently. This does not mint Authority; placing an untrusted manifest beside a DLL never admits it.
     */
    fun produce(source: String, tree: String, clean: Boolean, library: ByteArray): ByteArray {
        require(clean && sourcePattern.matches(source) && sourcePattern.matches(tree)) {
            "A clean pinned native source is required"
        }
        // PE verification uses a bounded private snapshot. The array length cannot change while bytes are inspected.
        val image = WindowsProfilePeImage.verify(library)
        val values = listOf(
            "1", "windows-profile-custody", WindowsProfilePeImage.ABI.toString(), "windows", "x86_64",
            source, tree, "true", FILE, library.size.toString(), image.sha256, "0x43",
        )
        return keys.zip(values).joinToString("\n", postfix = "\n") { (key, value) -> "$key=$value" }
            .toByteArray(Charsets.US_ASCII).also { require(it.size <= MAXIMUM_MANIFEST_BYTES) }
    }

    fun authorize(manifest: ByteArray, library: ByteArray, authority: Authority): ByteAuthorization {
        require(manifest.size in 1..MAXIMUM_MANIFEST_BYTES) { "Unsupported native manifest size" }
        require(library.size in 512..WindowsProfilePeImage.MAXIMUM_BYTES) { "Unsupported native DLL size" }
        val snapshot = manifest.copyOf()
        val digest = hash(snapshot)
        require(digest == authority.manifestSha256) { "Native manifest differs from external parent authority" }
        require(snapshot.all { it == 10.toByte() || it.toInt() in 0x20..0x7e }) {
            "Native manifest is not canonical ASCII"
        }
        val text = snapshot.toString(Charsets.US_ASCII)
        require(text.endsWith('\n')) { "Native manifest lacks its final newline" }
        val lines = text.dropLast(1).split('\n')
        require(lines.size == keys.size) { "Native manifest has missing or extra fields" }
        // Exact order/prefixes reject duplicates, unknown fields, escape syntax and alternative encodings.
        val values = keys.mapIndexed { index, key ->
            val prefix = "$key="
            require(lines[index].startsWith(prefix)) { "Native manifest fields are not canonical" }
            lines[index].substring(prefix.length)
        }
        require(values[0] == "1" && values[1] == "windows-profile-custody" &&
            values[2] == WindowsProfilePeImage.ABI.toString() && values[3] == "windows" &&
            values[4] == "x86_64" && values[7] == "true" && values[8] == FILE && values[11] == "0x43") {
            "Unsupported native component manifest policy"
        }
        require(values[5] == authority.source && values[6] == authority.tree) { "Native source pin mismatch" }
        val size = values[9].toIntOrNull()
        require(size != null && size in 512..WindowsProfilePeImage.MAXIMUM_BYTES &&
            size.toString() == values[9] && size == library.size) { "Native DLL size mismatch" }
        require(hashPattern.matches(values[10])) { "Invalid native DLL digest" }
        // Never return raw candidate bytes for execution. Future loader must separately hold/prove file custody,
        // signatures and exact pre/post-load identity; this value is not authority to open a pathname.
        val image = WindowsProfilePeImage.verify(library)
        require(image.sha256 == values[10]) { "Native DLL differs from the pinned component digest" }
        return ByteAuthorization(digest, authority.source, authority.tree, FILE, image.sha256, size,
            image.hasCertificateTable, image.namedImports, image.namedExports, image.imageBytes)
    }

    private fun hash(bytes: ByteArray): String = MessageDigest.getInstance("SHA-256").digest(bytes)
        .joinToString("") { "%02x".format(it) }
}
