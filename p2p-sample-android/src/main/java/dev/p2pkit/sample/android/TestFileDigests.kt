package dev.p2pkit.sample.android

import java.io.File
import java.io.FileInputStream
import java.io.InputStream
import java.security.MessageDigest

/** Test-harness SHA-256 helpers. They never participate in production protocol decisions. */
internal object TestFileDigests {
    fun sha256(file: File): String = FileInputStream(file).use(::sha256)

    fun sha256(input: InputStream): String {
        val digest = MessageDigest.getInstance("SHA-256")
        val buffer = ByteArray(64 * 1024)
        while (true) {
            val count = input.read(buffer)
            if (count < 0) break
            digest.update(buffer, 0, count)
        }
        return digest.digest().joinToString("") { "%02x".format(it) }
    }
}
