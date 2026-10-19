package dev.p2pkit.rpc

import dev.p2pkit.core.P2pError
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.test.runTest
import java.io.IOException
import java.net.SocketException
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertFailsWith
import kotlin.test.assertSame
import kotlin.test.assertTrue

class WindowsRpcConnectDiagnosticTest {
    @Test
    fun originalFailureAndSuppressedCleanupArePreservedWithoutRetry() = runTest {
        val failure = IOException("private endpoint and payload", SocketException("private socket detail"))
        val cleanup = IllegalStateException("private cleanup")
        failure.addSuppressed(cleanup)
        val lines = mutableListOf<String>()
        var attempts = 0
        assertSame(failure, assertFailsWith<IOException> {
            windowsRpcConnectDiagnostic(lines::add) { attempts++; throw failure }
        })
        assertEquals(1, attempts)
        assertSame(cleanup, failure.suppressed.single())
        assertTrue(lines.single().matches(Regex(
            "P2PKIT_RPC_WINDOWS_CONNECT_FAILURE elapsedMs=[0-9]{1,6} causes=IO:UNCLASSIFIED,SOCKET:UNCLASSIFIED")))
        assertFalse(lines.single().contains("private"))
    }

    @Test
    fun cancellationAndSuccessDoNotProduceFailureDiagnostics() = runTest {
        val lines = mutableListOf<String>()
        val cancelled = CancellationException("private cancellation")
        assertSame(cancelled, assertFailsWith<CancellationException> {
            windowsRpcConnectDiagnostic(lines::add) { throw cancelled }
        })
        assertEquals(42, windowsRpcConnectDiagnostic(lines::add) { 42 })
        assertTrue(lines.isEmpty())
    }

    @Test
    fun diagnosticSinkFailureCannotReplaceOriginalFailure() = runTest {
        val original = P2pError.AuthenticatedIdentityMismatch("private pin")
        assertSame(original, assertFailsWith<P2pError.AuthenticatedIdentityMismatch> {
            windowsRpcConnectDiagnostic({ error("sink unavailable") }) { throw original }
        })
    }

    @Test
    fun closedStageVocabularyIgnoresArbitraryStackTextAndDistinguishesPathRefusal() {
        val original = IOException("private endpoint")
        original.stackTrace = arrayOf(
            StackTraceElement("private class", "private method", "private file", 1),
            StackTraceElement("dev.p2pkit.transport.lan.JvmRawConnection", "requireAllowedPath", "private file", 2),
        )
        assertEquals("causes=IO:LAN_PATH", windowsRpcFailureCodes(original))
        assertEquals("causes=SECURITY_CONFIGURATION:UNCLASSIFIED",
            windowsRpcFailureCodes(P2pError.SecurityConfigurationInvalid("private key details")))
    }

    @Test
    fun cyclicAndDeepCausesAreBounded() {
        val cyclic = object : Exception("private") { override val cause: Throwable get() = this }
        assertEquals("causes=OTHER:UNCLASSIFIED,TRUNCATED", windowsRpcFailureCodes(cyclic))
        var deep: Throwable = Exception("private")
        repeat(20) { deep = Exception("private", deep) }
        assertEquals("causes=" + List(8) { "OTHER:UNCLASSIFIED" }.joinToString(",") + ",TRUNCATED",
            windowsRpcFailureCodes(deep))
    }
}
