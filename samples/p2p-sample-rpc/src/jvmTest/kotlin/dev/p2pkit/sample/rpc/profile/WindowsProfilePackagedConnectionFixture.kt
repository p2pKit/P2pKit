package dev.p2pkit.sample.rpc.profile

import java.security.MessageDigest

/** Inert test bytes only; synthetic pins are not source provenance or native loading authority. */
internal object WindowsProfilePackagedConnectionFixture {
    @JvmStatic
    fun data(): Array<Any> {
        val source = "a".repeat(40)
        val tree = "b".repeat(40)
        val library = WindowsProfilePeFixture.create()
        val manifest = WindowsProfileByteManifest.produce(source, tree, true, library)
        val hash = MessageDigest.getInstance("SHA-256").digest(manifest).joinToString("") { "%02x".format(it) }
        return arrayOf(manifest, library, hash, source, tree)
    }
}
