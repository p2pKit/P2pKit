package dev.p2pkit.sample.desktop

import java.io.File
import java.io.FileInputStream
import java.security.MessageDigest

/** Test-harness digest helper; protocol integrity remains owned by p2p-core. */
internal fun testFileSha256(file: File): String =
    FileInputStream(file).use { input ->
        val digest = MessageDigest.getInstance("SHA-256")
        val buffer = ByteArray(64 * 1024)
        while (true) {
            val count = input.read(buffer)
            if (count < 0) break
            digest.update(buffer, 0, count)
        }
        digest.digest().joinToString("") { "%02x".format(it) }
    }
