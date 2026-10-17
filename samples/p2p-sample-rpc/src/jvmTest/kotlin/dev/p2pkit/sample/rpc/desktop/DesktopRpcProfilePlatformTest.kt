package dev.p2pkit.sample.rpc.desktop

import dev.p2pkit.sample.rpc.profile.WindowsProfileInstalledProvider
import java.nio.file.InvalidPathException
import java.util.Properties
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertIs
import kotlin.test.assertNull
import kotlin.test.assertSame
import kotlin.test.assertTrue

/**
 * Synchronous platform/path controls under the maintained serial JUnit runner, not a parallel-safe fixture.
 * No filesystem, native provider or AWT is exercised; process-global properties are always restored.
 */
class DesktopRpcProfilePlatformTest {
    private fun password() = "synthetic-platform-passphrase".toCharArray()

    @Test fun windowsRefusalNeverEvaluatesHomeAndImmediatelyClearsThePassword() {
        for (os in listOf("Windows 11", "windows Server", "WINDOWS 10", "WiNdOwS")) {
            val password = password()
            var homeReads = 0
            val attempt = withProperties(os = { os }, home = {
                homeReads++
                throw AssertionError("Windows must not resolve a POSIX home")
            }) { DesktopRpcProfile.openApplicationAttempt(password) }
            val failure = assertIs<WindowsProfileInstalledProvider.Unavailable>(attempt.result.exceptionOrNull())
            assertTrue(failure.message.orEmpty().startsWith("Windows protected profile unavailable:"))
            assertNull(attempt.cleanupFailure)
            assertNull(attempt.retainedSession)
            assertEquals(0, homeReads)
            assertTrue(password.all { it == '\u0000' })
        }
    }

    @Test fun invalidPasswordNeverEvaluatesPlatformOrHome() {
        for (size in listOf(0, 11, 129)) {
            val password = CharArray(size) { 'x' }
            var reads = 0
            val forbidden = { reads++; throw AssertionError("Invalid password must precede resolution") }
            val attempt = withProperties(forbidden, forbidden) {
                DesktopRpcProfile.openApplicationAttempt(password)
            }
            assertIs<IllegalArgumentException>(attempt.result.exceptionOrNull())
            assertNull(attempt.cleanupFailure)
            assertNull(attempt.retainedSession)
            assertEquals(0, reads)
            assertTrue(password.all { it == '\u0000' })
        }
    }

    @Test fun platformReadFailureKeepsOriginalErrorAndClearsPasswordBeforeReturning() {
        val failure = SecurityException("synthetic platform read refusal")
        val password = password()
        var homeReads = 0
        val attempt = withProperties(os = { throw failure }, home = {
            homeReads++
            throw AssertionError("Home must not be evaluated")
        }) { DesktopRpcProfile.openApplicationAttempt(password) }
        assertSame(failure, attempt.result.exceptionOrNull())
        assertNull(attempt.cleanupFailure)
        assertNull(attempt.retainedSession)
        assertEquals(0, homeReads)
        assertTrue(password.all { it == '\u0000' })
    }

    @Test fun homeReadFailureKeepsOriginalErrorWithoutInventingCleanupOwnership() {
        val failure = SecurityException("synthetic home read refusal")
        val password = password()
        var homeReads = 0
        val attempt = withProperties(os = { "Linux" }, home = { homeReads++; throw failure }) {
            DesktopRpcProfile.openApplicationAttempt(password)
        }
        assertSame(failure, attempt.result.exceptionOrNull())
        assertNull(attempt.cleanupFailure)
        assertNull(attempt.retainedSession)
        assertEquals(1, homeReads)
        assertTrue(password.all { it == '\u0000' })
    }

    @Test fun malformedHomePathRefusesBeforeProviderAcquisitionAndClearsPassword() {
        val password = password()
        val attempt = withProperties(os = { "Linux" }, home = { "synthetic\u0000home" }) {
            DesktopRpcProfile.openApplicationAttempt(password)
        }
        assertIs<InvalidPathException>(attempt.result.exceptionOrNull())
        assertNull(attempt.cleanupFailure)
        assertNull(attempt.retainedSession)
        assertTrue(password.all { it == '\u0000' })
    }

    @Test fun relativePosixPathKeepsExistingAcquisitionFailureSemanticsAndClearsPassword() {
        val password = password()
        val attempt = withProperties(os = { "Linux" }, home = { "synthetic-relative-home" }) {
            DesktopRpcProfile.openApplicationAttempt(password)
        }
        val failure = assertIs<IllegalArgumentException>(attempt.result.exceptionOrNull())
        assertSame(failure, attempt.cleanupFailure)
        assertNull(attempt.retainedSession)
        assertTrue(password.all { it == '\u0000' })
    }

    private fun <T> withProperties(os: () -> String, home: () -> String, action: () -> T): T {
        val original = System.getProperties()
        return synchronized(original) {
            val scoped = object : Properties(original) {
                init { putAll(original) }
                override fun getProperty(key: String): String? = when (key) {
                    "os.name" -> os()
                    "user.home" -> home()
                    else -> super.getProperty(key)
                }
            }
            try {
                System.setProperties(scoped)
                action()
            } finally { System.setProperties(original) }
        }
    }
}
