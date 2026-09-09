import Foundation
import P2pKitShared
import XCTest
@testable import P2pKitSample

final class SampleP2pErrorTests: XCTestCase {
    @MainActor
    func testSynchronousCreateActuallyBridgesTheSecureAppIdFailure() async throws {
        let unexpectedlyCreated: P2pKit
        do {
            unexpectedlyCreated = try P2pKitCompanion.shared.create { builder in
                // 512 UTF-16 units / 1536 UTF-8 bytes pass HELLO builder bounds,
                // then fail secure-v2's 1024-byte bound before crypto/store/transport setup.
                builder.appId = String(repeating: "\u{0800}", count: 512)
                builder.deviceName = "Synthetic bridge test"
                builder.transports { $0.lan() }
            }
        } catch {
            let typed = try XCTUnwrap(SampleP2pError.recover(error))
            XCTAssertTrue(typed is P2pError.SecurityConfigurationInvalid)
            XCTAssertFalse(SampleP2pError.isSecurityRejection(typed))
            return
        }
        XCTFail("create must fail before constructing a kit for this secure AppId")
        try await unexpectedlyCreated.stop()
    }

    @MainActor
    func testSynchronousNonP2pBuilderFailureRemainsAnUnhandledKotlinException() async throws {
        let unexpectedlyCreated: P2pKit
        do {
            unexpectedlyCreated = try P2pKitCompanion.shared.create { builder in
                // Nonblank AppId construction is valid; build() rejects the
                // 513-character value inside create's existing @Throws boundary.
                builder.appId = String(repeating: "a", count: 513)
                builder.deviceName = "Synthetic builder test"
                builder.transports { $0.lan() }
            }
        } catch {
            XCTAssertNotNil((error as NSError).kotlinException)
            XCTAssertNil(SampleP2pError.recover(error))
            XCTAssertEqual(SampleP2pError.userMessage(error), error.localizedDescription)
            return
        }
        XCTFail("build must reject the HELLO field length before constructing a kit")
        try await unexpectedlyCreated.stop()
    }

    @MainActor
    func testSuspendInterfaceActuallyBridgesTheClosedManagerFailure() async throws {
        // This public fallback owns only mutex/flow state, not OS networking or identity.
        let manager: NetworkProvisioningManager = UnsupportedNetworkProvisioningManager()
        try await manager.close()
        do {
            _ = try await manager.getManualConnectionInfo()
            XCTFail("closed manager must reject the operation through its suspend error callback")
        } catch {
            let typed = try XCTUnwrap(SampleP2pError.recover(error))
            XCTAssertTrue(typed is NetworkProvisioningError.ManagerClosed)
            XCTAssertFalse(SampleP2pError.isSecurityRejection(typed))
            XCTAssertEqual(
                SampleP2pError.userMessage(typed),
                "Network provisioning is closed. Finish owned cleanup before creating a replacement."
            )
        }
    }

    func testUnexpectedSwiftAndFoundationErrorsDoNotBecomeTypedByParsingText() {
        let namedLikeSdkError = NSError(
            domain: "P2pError.AuthenticationFailed", code: 7,
            userInfo: [NSLocalizedDescriptionKey: "AuthorizationRejected at /private/synthetic-canary"]
        )
        let wrongObject = NSError(domain: "synthetic", code: 8, userInfo: ["KotlinException": "not a Kotlin object"])
        let swift = NativeFailure()
        let unexpected: [Error] = [namedLikeSdkError, wrongObject, swift, CancellationError()]
        for error in unexpected {
            XCTAssertNil(SampleP2pError.recover(error))
            XCTAssertFalse(SampleP2pError.isSecurityRejection(SampleP2pError.recover(error)))
        }
        XCTAssertEqual(SampleP2pError.userMessage(namedLikeSdkError), namedLikeSdkError.localizedDescription)
        XCTAssertEqual(SampleP2pError.userMessage(swift), swift.localizedDescription)
        XCTAssertEqual(SampleConsole.failure(namedLikeSdkError), "errorCode=7 (details omitted)")
        XCTAssertFalse(SampleConsole.failure(namedLikeSdkError).contains("canary"))
    }

    func testSyntheticWrapperRetainsTheExactFileFailureAndItsStructuredContext() throws {
        let canary = "Synthetic Private Name /private/example.txt 192.0.2.9"
        let failure = P2pError.FileTransferFailed(
            kind: .storage, phase: .durableCommit, retryability: .retryAfterUserAction,
            transferId: "synthetic-private-transfer", reason: canary
        )
        let wrapped = syntheticWrapper(failure, description: canary)
        let typed = try XCTUnwrap(SampleP2pError.recover(wrapped) as? P2pError.FileTransferFailed)
        XCTAssertTrue(typed === failure)
        XCTAssertEqual(typed.kind, .storage)
        XCTAssertEqual(typed.phase, .durableCommit)
        XCTAssertEqual(typed.retryability, .retryAfterUserAction)
        XCTAssertEqual(typed.transferId, "synthetic-private-transfer")
        XCTAssertEqual(typed.reason, canary)
        let hint = SampleP2pError.userMessage(wrapped)
        XCTAssertEqual(hint, SampleP2pError.userMessage(failure), "state values use the typed overload directly")
        XCTAssertTrue(hint.contains("STORAGE, DURABLE_COMMIT"))
        XCTAssertFalse(hint.contains(canary))
        XCTAssertFalse(hint.contains("synthetic-private-transfer"))
        XCTAssertEqual(SampleConsole.failure(wrapped), "errorCode=19 (details omitted)")
    }

    func testEveryActualRetryabilityValueHasAConservativeNewTransferHint() {
        let cases: [(Retryability, String)] = [
            (.retrySameSession, "After the blocking condition clears, a new transfer may use the still-connected session."),
            (.retryNewSession, "Re-establish an authorized usable session before creating a new transfer."),
            (.retryAfterUserAction, "Resolve the reported local condition or user action before creating a new transfer."),
            (.notRetryable, "Do not retry automatically; investigate and explicitly correct the cause.")
        ]
        for (retryability, expected) in cases {
            let failure = P2pError.FileTransferFailed(
                kind: .storage, phase: .receive, retryability: retryability,
                transferId: nil, reason: "synthetic reason must not choose recovery"
            )
            XCTAssertEqual(SampleP2pError.transferRecoveryHint(failure.retryability), expected)
            XCTAssertEqual(
                SampleP2pError.userMessage(failure), "File transfer failed (STORAGE, RECEIVE). " + expected
            )
            XCTAssertFalse(SampleP2pError.isSecurityRejection(failure))
        }
    }

    func testEveryIdentityRecoveryValueKeepsTheTypedObjectAndNeverSuggestsAutomaticRotation() throws {
        let cases: [(LocalIdentityRecovery, String)] = [
            (.retry, "Preserve the identity and retry creation only after the transient condition ends."),
            (.retryAfterDeviceUnlock, "Unlock the device before retrying; do not weaken storage accessibility."),
            (.configureStore, "Configure the required protected identity store; do not substitute an ephemeral identity."),
            (.fixPlatformConfiguration, "Correct platform permissions, entitlements or provider configuration without deleting the identity."),
            (.explicitResetRequired, "An explicit destructive-reset decision and trusted peer re-pinning are required; never reset automatically.")
        ]
        for (recovery, expected) in cases {
            // Synthetic combinations exercise presentation, not the matrix of
            // platform conditions that can actually produce a particular recovery.
            let failure = P2pError.LocalIdentityUnavailable(
                kind: .temporarilyUnavailable, recovery: recovery, reason: "synthetic-private-identity-reason"
            )
            let wrapped = syntheticWrapper(failure, description: "synthetic-private-localized-description")
            let recovered = try XCTUnwrap(SampleP2pError.recover(wrapped) as? P2pError.LocalIdentityUnavailable)
            XCTAssertTrue(recovered === failure)
            XCTAssertEqual(recovered.kind, .temporarilyUnavailable)
            XCTAssertEqual(recovered.recovery, recovery)
            XCTAssertEqual(SampleP2pError.identityRecoveryHint(recovered.recovery), expected)
            XCTAssertEqual(
                SampleP2pError.userMessage(wrapped), "Local secure identity unavailable (TEMPORARILY_UNAVAILABLE). " + expected
            )
            XCTAssertFalse(SampleP2pError.userMessage(wrapped).contains("synthetic-private"))
        }
    }

    func testOnlyActualSecurityRejectionsSelectTheAuthenticationFailureEvent() {
        let canary = "synthetic-private-error-text"
        let cases: [(P2pError, Bool)] = [
            (P2pError.AuthenticationFailed(reason: canary), true),
            (P2pError.AuthorizationRejected(reason: canary), true),
            (P2pError.AuthenticatedIdentityMismatch(reason: canary), true),
            (P2pError.ConnectionFailed(reason: canary), false),
            (P2pError.HandshakeRejected(reason: canary), false),
            (P2pError.SecurityConfigurationInvalid(reason: canary), false),
            (P2pError.TransportStartFailed(transportKind: .lan, reason: canary, underlying: nil), false),
            (NetworkProvisioningError.ManagerClosed(), false),
            (P2pError.FileTransferFailed(
                kind: .authentication, phase: .accept, retryability: .notRetryable,
                transferId: nil, reason: canary
            ), false)
        ]
        for (failure, securityRejection) in cases {
            let wrapped = syntheticWrapper(failure, description: canary)
            XCTAssertEqual(SampleP2pError.isSecurityRejection(SampleP2pError.recover(wrapped)), securityRejection)
            XCTAssertFalse(SampleP2pError.userMessage(wrapped).contains(canary))
            XCTAssertFalse(SampleConsole.failure(wrapped).contains(canary))
        }
        XCTAssertFalse(SampleP2pError.isSecurityRejection(nil))
    }
}

/// A synthetic dictionary only tests optional recovery/presentation. The three
/// actual throwing-call tests above are the separate native bridge regressions.
private func syntheticWrapper(_ failure: P2pError, description: String) -> NSError {
    NSError(
        domain: "synthetic-bridge", code: 19,
        userInfo: ["KotlinException": failure, NSLocalizedDescriptionKey: description]
    )
}

private struct NativeFailure: LocalizedError {
    var errorDescription: String? { "Synthetic Swift failure requiring the existing UI fallback" }
}
