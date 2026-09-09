import Foundation
import P2pKitShared

/// Sample-local presentation, not a new SDK error taxonomy or retry policy.
/// Keep the original typed object so callers retain its subtype-specific fields and cause.
enum SampleP2pError {
    static func recover(_ error: Error) -> P2pError? {
        (error as NSError).kotlinException as? P2pError
    }

    /// Arbitrary-error presentation is not a safe logging format.
    /// Never pass this text to the code-only console logger.
    static func userMessage(_ error: Error) -> String {
        if let typed = recover(error) { return userMessage(typed) }
        return error.localizedDescription
    }

    /// FileTransferState.Failed.error is already P2pError and uses this overload directly.
    static func userMessage(_ error: P2pError) -> String {
        switch error {
        case let transfer as P2pError.FileTransferFailed:
            return "File transfer failed (\(transfer.kind.name), \(transfer.phase.name)). " +
                transferRecoveryHint(transfer.retryability)
        case let identity as P2pError.LocalIdentityUnavailable:
            return "Local secure identity unavailable (\(identity.kind.name)). " +
                identityRecoveryHint(identity.recovery)
        case is P2pError.AuthenticationFailed:
            return "Authentication failed. Stop and investigate; do not downgrade or replace a trusted pin."
        case is P2pError.AuthorizationRejected:
            return "The authenticated peer is not authorized. Verify approval out of band; do not change policy automatically."
        case is P2pError.AuthenticatedIdentityMismatch:
            return "The authenticated identity does not match the selected peer or trusted pin. Stop and investigate."
        case is P2pError.SecurityConfigurationInvalid:
            return "Secure configuration is invalid. Correct the required identity or pin; do not weaken security."
        case is P2pError.NoTransportAvailable:
            return "No registered transport can currently reach this peer."
        case is P2pError.TransportInitializationFailed:
            return "A transport could not initialize. Check provider configuration before creating a new kit."
        case is P2pError.TransportStartFailed:
            return "A transport could not start. Check platform/network configuration and retained cleanup before retrying."
        case is P2pError.ConnectionFailed:
            return "The connection operation failed. Check session/lifecycle state and retained cleanup before retrying."
        case is P2pError.HandshakeRejected:
            return "The handshake was rejected. Check AppId and compatibility before a new attempt."
        case is P2pError.VersionMismatch:
            return "Protocol versions are incompatible. Use compatible peers without downgrading security."
        case is NetworkProvisioningError.ManagerClosed:
            return "Network provisioning is closed. Finish owned cleanup before creating a replacement."
        default:
            return "P2pKit operation failed. Inspect the typed error and current lifecycle state."
        }
    }

    static func isSecurityRejection(_ error: P2pError?) -> Bool {
        error is P2pError.AuthenticationFailed || error is P2pError.AuthorizationRejected ||
            error is P2pError.AuthenticatedIdentityMismatch
    }

    static func transferRecoveryHint(_ retryability: Retryability) -> String {
        switch retryability {
        case .retrySameSession:
            return "After the blocking condition clears, a new transfer may use the still-connected session."
        case .retryNewSession:
            return "Re-establish an authorized usable session before creating a new transfer."
        case .retryAfterUserAction:
            return "Resolve the reported local condition or user action before creating a new transfer."
        case .notRetryable:
            return "Do not retry automatically; investigate and explicitly correct the cause."
        default:
            return "Unknown recovery disposition; do not retry automatically."
        }
    }

    static func identityRecoveryHint(_ recovery: LocalIdentityRecovery) -> String {
        switch recovery {
        case .retry:
            return "Preserve the identity and retry creation only after the transient condition ends."
        case .retryAfterDeviceUnlock:
            return "Unlock the device before retrying; do not weaken storage accessibility."
        case .configureStore:
            return "Configure the required protected identity store; do not substitute an ephemeral identity."
        case .fixPlatformConfiguration:
            return "Correct platform permissions, entitlements or provider configuration without deleting the identity."
        case .explicitResetRequired:
            return "An explicit destructive-reset decision and trusted peer re-pinning are required; never reset automatically."
        default:
            return "Unknown identity recovery disposition; preserve the identity and request operator review."
        }
    }
}
