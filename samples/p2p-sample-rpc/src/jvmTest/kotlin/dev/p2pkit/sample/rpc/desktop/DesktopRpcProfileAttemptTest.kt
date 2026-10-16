package dev.p2pkit.sample.rpc.desktop

import dev.p2pkit.sample.rpc.profile.WindowsProfileCustodyException
import dev.p2pkit.sample.rpc.profile.WindowsProfileFiles
import dev.p2pkit.sample.rpc.profile.WindowsProfileModel
import dev.p2pkit.sample.rpc.profile.WindowsProfileNativeApi
import java.io.IOException
import java.lang.reflect.Proxy
import java.nio.file.Path
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFails
import kotlin.test.assertFailsWith
import kotlin.test.assertNull
import kotlin.test.assertSame
import kotlin.test.assertTrue

/** Actual profile-open error handling over inert storage; not Windows runtime/provider qualification. */
class DesktopRpcProfileAttemptTest {
    private fun password() = "synthetic-open-attempt-passphrase".toCharArray()
    private fun populated(): WindowsProfileModel.Store {
        val model = WindowsProfileModel()
        DesktopRpcProfile.open(WindowsProfileFiles.openForValidation(model), password()).close()
        assertEquals(0, model.remaining)
        return model.store
    }

    /** Synchronous property simulation of refusal only; no AWT, native calls or real filesystem access. */
    @Test fun productionOpenRefusesWindowsBeforeAnyPathAccessAndClearsPassword() {
        for (osName in listOf("Windows 11", "windows Server", "WINDOWS 10", "WiNdOwS")) {
            val path = UntouchedPath()
            val pass = password()
            val failure = withWindowsName(osName) {
                assertFailsWith<IllegalStateException> { DesktopRpcProfile.open(path.value, pass) }
            }
            assertTrue(failure.message.orEmpty().startsWith("Windows protected profile unavailable:"))
            assertEquals(0, path.accesses)
            assertTrue(pass.all { it == '\u0000' })
        }
    }

    @Test fun productionOpenAttemptRefusesWindowsWithoutInventingAFileOrCleanupOwner() {
        for (osName in listOf("Windows 11", "windows Server", "WINDOWS 10", "WiNdOwS")) {
            val path = UntouchedPath()
            val pass = password()
            val attempt = withWindowsName(osName) { DesktopRpcProfile.openAttempt(path.value, pass) }
            val failure = attempt.result.exceptionOrNull()
            assertTrue(failure is IllegalStateException)
            assertTrue(failure.message.orEmpty().startsWith("Windows protected profile unavailable:"))
            assertNull(attempt.cleanupFailure)
            assertNull(attempt.retainedSession)
            assertEquals(0, path.accesses)
            assertTrue(pass.all { it == '\u0000' })
        }
    }

    private class UntouchedPath {
        var accesses = 0
            private set
        val value: Path = Proxy.newProxyInstance(Path::class.java.classLoader, arrayOf(Path::class.java)) { _, _, _ ->
            accesses++
            throw AssertionError("Windows refusal must precede every path/filesystem access")
        } as Path
    }

    private fun <T> withWindowsName(osName: String, action: () -> T): T {
        val properties = System.getProperties()
        return synchronized(properties) {
            val previous = properties["os.name"]
            try {
                System.setProperty("os.name", osName)
                action()
            } finally {
                if (previous == null) properties.remove("os.name") else properties["os.name"] = previous
            }
        }
    }

    @Test fun cleanWrongPasswordRetiresOwnersAndDoesNotPoisonAValidRetry() {
        val store = populated()
        val model = WindowsProfileModel(store)
        val pass = "wrong-synthetic-open-attempt".toCharArray()
        val attempt = DesktopRpcProfile.openAttempt(WindowsProfileFiles.openForValidation(model), pass)
        assertTrue(attempt.result.isFailure)
        assertNull(attempt.cleanupFailure)
        assertNull(attempt.retainedSession)
        assertTrue(pass.all { it == '\u0000' })
        assertEquals(0, model.remaining)
        assertTrue(store.locks.isEmpty())
        val retryModel = WindowsProfileModel(store)
        val retry = DesktopRpcProfile.openAttempt(WindowsProfileFiles.openForValidation(retryModel), password())
        assertNull(retry.cleanupFailure)
        assertNull(retry.retainedSession)
        retry.result.getOrThrow().close()
        assertEquals(0, retryModel.remaining)
        assertTrue(store.locks.isEmpty())
    }

    @Test fun identicalCachedInspectionCleanupFailureIsExplicitWithoutSelfSuppressionOrRetry() {
        val model = WindowsProfileModel(populated())
        val failure = IOException("synthetic same-object inspection cleanup")
        var vaultLease = 0L
        val closes = mutableListOf<Long>()
        val native = object : WindowsProfileNativeApi by model {
            override fun lock(directory: Long, name: String, nonBlocking: Boolean): Long =
                model.lock(directory, name, nonBlocking).also { if (name == "vault.lock") vaultLease = it }
            override fun close(handle: Long) {
                closes += handle
                if (handle == vaultLease) throw failure
                model.close(handle)
            }
        }
        val files = WindowsProfileFiles.openForValidation(native)
        val pass = password()
        val attempt = DesktopRpcProfile.openAttempt(files, pass)
        assertSame(failure, attempt.result.exceptionOrNull())
        assertSame(failure, attempt.cleanupFailure)
        assertSame(files, attempt.retainedSession)
        assertTrue(failure.suppressed.isEmpty())
        assertTrue(pass.all { it == '\u0000' })
        assertEquals(1, files.retainedHandleCount)
        assertEquals(1, model.remaining) // Intentionally uncertain inert owner, never called native cleanup success.
        assertEquals(1, closes.count { it == vaultLease })
        val attempted = closes.toList()
        assertSame(failure, assertFails { files.close() })
        assertEquals(attempted, closes)
    }

    @Test fun originalFailureAndDistinctOuterCleanupFailureRemainSeparate() {
        for (physicallyReleased in listOf(false, true)) {
            val model = WindowsProfileModel()
            val original = IOException("synthetic inventory failure")
            val cleanup = IOException("synthetic root cleanup failure")
            var root = 0L
            val closes = mutableListOf<Long>()
            val native = object : WindowsProfileNativeApi by model {
                override fun openRoot(): Long = model.openRoot().also { root = it }
                override fun names(directory: Long): Array<String> = throw original
                override fun close(handle: Long) {
                    closes += handle
                    if (handle == root) {
                        if (physicallyReleased) model.close(handle)
                        throw cleanup
                    }
                    model.close(handle)
                }
            }
            val files = WindowsProfileFiles.openForValidation(native)
            val attempt = DesktopRpcProfile.openAttempt(files, password())
            assertSame(original, attempt.result.exceptionOrNull())
            assertSame(cleanup, attempt.cleanupFailure)
            assertSame(files, attempt.retainedSession)
            assertTrue(original.suppressed.any { it === cleanup })
            assertEquals(1, files.retainedHandleCount)
            assertEquals(if (physicallyReleased) 0 else 1, model.remaining)
            val attempted = closes.toList()
            // The retained owner is sealed; exposing it neither repairs uncertainty nor authorizes a retry.
            assertSame(cleanup, assertFails { checkNotNull(attempt.retainedSession).close() })
            assertEquals(attempted, closes)
        }
    }

    @Test fun failedUnpublishedProviderCleanupIsNotLostWhenOuterOwnersCloseSuccessfully() {
        val model = WindowsProfileModel()
        val original = IOException("synthetic unpublished allocation failure")
        val cleanup = IOException("synthetic unpublished owner cleanup failure")
        original.addSuppressed(cleanup)
        val native = object : WindowsProfileNativeApi by model {
            // No synthetic token is allocated: only the explicitly supplied provider failure is modeled.
            override fun lock(directory: Long, name: String, nonBlocking: Boolean): Long = throw original
        }
        val files = WindowsProfileFiles.openForValidation(native)
        val attempt = DesktopRpcProfile.openAttempt(files, password())
        assertSame(original, attempt.result.exceptionOrNull())
        assertSame(cleanup, attempt.cleanupFailure)
        assertSame(files, attempt.retainedSession)
        assertEquals(0, model.remaining)
    }

    @Test fun nativeCleanupUnknownAndUnknownCodesCannotBecomeAProvenEmptyProfile() {
        for (code in listOf(8, 987)) {
            val model = WindowsProfileModel()
            val original = WindowsProfileCustodyException(code)
            val native = object : WindowsProfileNativeApi by model {
                override fun lock(directory: Long, name: String, nonBlocking: Boolean): Long = throw original
            }
            val files = WindowsProfileFiles.openForValidation(native)
            val attempt = DesktopRpcProfile.openAttempt(files, password())
            assertSame(original, attempt.result.exceptionOrNull())
            assertSame(original, attempt.cleanupFailure)
            assertSame(files, attempt.retainedSession)
            assertEquals(0, model.remaining)
        }
    }
}
