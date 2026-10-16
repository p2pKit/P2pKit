package dev.p2pkit.sample.rpc.desktop

import java.io.File
import java.lang.reflect.Proxy
import java.nio.file.Path
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertNull
import kotlin.test.assertTrue

/** Actual Windows process refusal only; no protected-profile, JNI or installed-application qualification. */
class DesktopRpcWindowsRefusalTest {
    @Test
    fun productionOpenRefusesBeforeAnyPathAccessAndClearsTransferredPassword() {
        requireActualWindowsProcess()
        val path = UntouchedPath()
        val password = "synthetic-windows-refusal-passphrase".toCharArray()

        val failure = assertFailsWith<IllegalStateException> { DesktopRpcProfile.open(path.value, password) }

        assertTrue(failure.message.orEmpty().startsWith("Windows protected profile unavailable:"))
        assertEquals(0, path.accesses)
        assertTrue(password.all { it == '\u0000' })
    }

    @Test
    fun productionOpenAttemptRefusesWithoutInventingAFileOrCleanupOwner() {
        requireActualWindowsProcess()
        val path = UntouchedPath()
        val password = "synthetic-windows-refusal-passphrase".toCharArray()

        val attempt = DesktopRpcProfile.openAttempt(path.value, password)

        val failure = attempt.result.exceptionOrNull()
        assertTrue(failure is IllegalStateException)
        assertTrue(failure.message.orEmpty().startsWith("Windows protected profile unavailable:"))
        assertNull(attempt.cleanupFailure)
        assertNull(attempt.retainedSession)
        assertEquals(0, path.accesses)
        assertTrue(password.all { it == '\u0000' })
    }

    private fun requireActualWindowsProcess() {
        // Fail on a misregistered host, rather than skip or simulate Windows through a property override.
        assertTrue(System.getProperty("os.name").startsWith("Windows", ignoreCase = true))
        assertEquals('\\', File.separatorChar)
    }

    private class UntouchedPath {
        var accesses = 0
            private set

        val value: Path = Proxy.newProxyInstance(Path::class.java.classLoader, arrayOf(Path::class.java)) { _, _, _ ->
            accesses++
            throw AssertionError("Windows refusal must precede every path/filesystem access")
        } as Path
    }
}
