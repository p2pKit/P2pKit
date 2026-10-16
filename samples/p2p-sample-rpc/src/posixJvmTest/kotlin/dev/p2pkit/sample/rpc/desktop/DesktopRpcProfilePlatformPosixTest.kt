package dev.p2pkit.sample.rpc.desktop

import java.nio.file.Files
import java.util.Comparator
import kotlin.test.Test
import kotlin.test.assertContentEquals
import kotlin.test.assertNull
import kotlin.test.assertTrue

/** Actual existing POSIX backend through the application's platform-dispatch entry. */
class DesktopRpcProfilePlatformPosixTest {
    @Test fun applicationEntryPreservesDefaultPathEncryptedPersistenceAndOwnerTransfer() {
        val directory = Files.createTempDirectory("rpc-platform-profile-").toRealPath()
        val properties = System.getProperties()
        val value = byteArrayOf(12, 34, 56)
        try {
            synchronized(properties) {
                val original = properties["user.home"]
                try {
                    System.setProperty("user.home", directory.toString())
                    val password = "synthetic-posix-platform-passphrase".toCharArray()
                    val attempt = DesktopRpcProfile.openApplicationAttempt(password)
                    val profile = attempt.result.getOrThrow()
                    try {
                        assertNull(attempt.cleanupFailure)
                        assertNull(attempt.retainedSession)
                        assertTrue(password.all { it == '\u0000' })
                        val stored = profile.vault.putIfAbsent("synthetic-platform-identity", value)
                        try { assertContentEquals(value, stored) } finally { stored.fill(0) }
                        assertTrue(Files.isDirectory(directory.resolve(".p2pkit-rpc-desktop").resolve("identity")))
                    } finally { profile.close() }
                    val reopenedPassword = "synthetic-posix-platform-passphrase".toCharArray()
                    val reopened = DesktopRpcProfile.openApplicationAttempt(reopenedPassword)
                    val reopenedProfile = reopened.result.getOrThrow()
                    try {
                        assertNull(reopened.cleanupFailure)
                        assertNull(reopened.retainedSession)
                        assertTrue(reopenedPassword.all { it == '\u0000' })
                        val stored = reopenedProfile.vault.read("synthetic-platform-identity")
                        try { assertContentEquals(value, stored) } finally { stored?.fill(0) }
                    } finally { reopenedProfile.close() }
                } finally {
                    if (original == null) properties.remove("user.home") else properties["user.home"] = original
                }
            }
        } finally {
            value.fill(0)
            Files.walk(directory).use { it.sorted(Comparator.reverseOrder()).forEach(Files::delete) }
        }
    }
}
