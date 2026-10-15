package dev.p2pkit.rpc.internal

import dev.p2pkit.core.P2pError
import dev.p2pkit.rpc.RpcFailure
import dev.p2pkit.rpc.RpcFailureKind
import dev.p2pkit.rpc.RpcFailurePhase
import kotlinx.coroutines.CancellationException

internal suspend inline fun <T> rpcBoundary(action: () -> T): T = try { action() }
catch (cancelled: CancellationException) { throw cancelled }
catch (failure: RpcFailure) { throw failure }
catch (failure: Exception) {
    val kind = when (failure) {
        is P2pError.AuthenticationFailed, is P2pError.AuthenticatedIdentityMismatch,
        is P2pError.SecurityConfigurationInvalid -> RpcFailureKind.Authentication
        is P2pError.AuthorizationRejected -> RpcFailureKind.Unauthorized
        is P2pError.PermissionMissing -> RpcFailureKind.PermissionMissing
        is P2pError.ProtocolError, is P2pError.HandshakeRejected -> RpcFailureKind.Protocol
        is P2pError.VersionMismatch -> RpcFailureKind.IncompatibleVersion
        else -> RpcFailureKind.NotConnected
    }
    throw RpcFailure(kind, RpcFailurePhase.Negotiation)
}
