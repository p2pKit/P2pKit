package dev.p2pkit.sample.rpc.profile

import java.security.MessageDigest

/** Test-only actual declaration/manifest bridge. Never a native loader or storage entry point. */
internal object WindowsProfileLoadedNativeFixture {
    @JvmStatic
    fun manifest(library: ByteArray, source: String, tree: String): Array<Any> {
        val bytes = WindowsProfileByteManifest.produce(source, tree, true, library)
        val hash = MessageDigest.getInstance("SHA-256").digest(bytes).joinToString("") { "%02x".format(it) }
        return arrayOf(bytes, hash)
    }

    @JvmStatic
    fun abi(): Int = WindowsProfileCustodyJni.abi()

    @JvmStatic
    fun capabilities(): Long = WindowsProfileCustodyJni.capabilities()
}
