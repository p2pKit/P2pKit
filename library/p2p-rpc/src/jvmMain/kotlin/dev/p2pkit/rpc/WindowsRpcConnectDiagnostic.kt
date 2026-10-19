package dev.p2pkit.rpc

import dev.p2pkit.core.P2pError
import dev.p2pkit.core.P2pKit
import dev.p2pkit.core.P2pSession
import dev.p2pkit.core.Peer
import dev.p2pkit.core.PeerFingerprint
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.TimeoutCancellationException
import java.io.EOFException
import java.io.IOException
import java.net.SocketException
import java.net.SocketTimeoutException
import java.security.GeneralSecurityException
import java.util.Collections
import java.util.IdentityHashMap

/** Observe the original Windows failure before the public RPC boundary deliberately drops its cause. */
internal class WindowsRpcDiagnosticKit(private val delegate: P2pKit) : P2pKit by delegate {
    override suspend fun connect(peer: Peer): P2pSession = windowsRpcConnectDiagnostic { delegate.connect(peer) }

    override suspend fun connect(peer: Peer, expectedFingerprint: PeerFingerprint): P2pSession =
        windowsRpcConnectDiagnostic { delegate.connect(peer, expectedFingerprint) }
}

/** No retry, ownership transfer, authentication decision, exception mutation, or retained throwable. */
internal suspend fun <T> windowsRpcConnectDiagnostic(
    report: (String) -> Unit = { System.err.println(it) },
    connect: suspend () -> T,
): T {
    val started = System.nanoTime()
    try {
        return connect()
    } catch (cancelled: CancellationException) {
        throw cancelled
    } catch (failure: Exception) {
        try {
            val elapsed = ((System.nanoTime() - started) / 1_000_000).coerceIn(0, 999_999)
            report("P2PKIT_RPC_WINDOWS_CONNECT_FAILURE elapsedMs=$elapsed ${windowsRpcFailureCodes(failure)}")
        } catch (_: Exception) {
            // Diagnostic failure must not replace the original failure or its retained cleanup evidence.
        }
        throw failure
    }
}

/** Closed vocabulary only: never exception text, class names, stack text, peer pins, addresses or payload. */
internal fun windowsRpcFailureCodes(failure: Throwable): String {
    val seen = Collections.newSetFromMap(IdentityHashMap<Throwable, Boolean>())
    val codes = ArrayList<String>(8)
    var current: Throwable? = failure
    while (current != null && codes.size < 8 && seen.add(current)) {
        val kind = when (current) {
            is P2pError.AuthenticationFailed -> "AUTHENTICATION"
            is P2pError.AuthenticatedIdentityMismatch -> "IDENTITY_MISMATCH"
            is P2pError.SecurityConfigurationInvalid -> "SECURITY_CONFIGURATION"
            is P2pError.AuthorizationRejected -> "AUTHORIZATION"
            is P2pError.ProtocolError -> "PROTOCOL"
            is P2pError.HandshakeRejected -> "HELLO_REJECTED"
            is TimeoutCancellationException -> "TIMEOUT"
            is EOFException -> "EOF"
            is SocketTimeoutException -> "SOCKET_TIMEOUT"
            is SocketException -> "SOCKET"
            is IOException -> "IO"
            is GeneralSecurityException -> "CRYPTO_PROVIDER"
            is IllegalStateException -> "LOCAL_STATE"
            is IllegalArgumentException -> "LOCAL_ARGUMENT"
            else -> when (current.javaClass.name) {
                "dev.p2pkit.core.internal.security.noise.NoiseAuthenticationException" -> "NOISE_AUTHENTICATION"
                "dev.p2pkit.core.internal.security.noise.NoiseProtocolException" -> "NOISE_PROTOCOL"
                else -> "OTHER"
            }
        }
        val stage = current.stackTrace.asSequence().take(64).firstNotNullOfOrNull { frame ->
            when {
                frame.className == "dev.p2pkit.transport.lan.JvmRawConnection" &&
                    frame.methodName == "requireAllowedPath" -> "LAN_PATH"
                frame.className == "dev.p2pkit.core.internal.security.AuthenticatedV2SecurityEngine" &&
                    frame.methodName == "validateLocalIdentity" -> "LOCAL_IDENTITY"
                frame.className == "dev.p2pkit.core.internal.security.AuthenticatedV2SecurityEngine" &&
                    frame.methodName == "deriveAndAuthorizeRemote" -> "REMOTE_IDENTITY"
                frame.className == "dev.p2pkit.core.internal.security.noise.SecureV2HandshakeDriver" -> "NOISE_SETUP"
                frame.className == "dev.p2pkit.core.internal.security.noise.SingleCollectorRawPump" -> "RAW_PUMP"
                else -> null
            }
        } ?: "UNCLASSIFIED"
        codes.add("$kind:$stage")
        current = current.cause
    }
    return "causes=" + codes.joinToString(",") + if (current != null) ",TRUNCATED" else ""
}
