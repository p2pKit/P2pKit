import Foundation
import P2pKitShared

/// Owns this sample's temporary, process-wide LAN diagnostic settings.
/// Overlapping windows restore the first owner's settings only after the
/// last lease is released. Release builds never change console mirroring.
final class IosLanDiagnosticsLease {
    private let token: UUID

    private init(token: UUID) {
        self.token = token
    }

    static func acquire() -> IosLanDiagnosticsLease {
        IosLanDiagnosticsLease(token: IosLanDiagnosticsOwnership.acquire())
    }

    func release() {
        IosLanDiagnosticsOwnership.release(token)
    }

    deinit {
        release()
    }
}

private enum IosLanDiagnosticsOwnership {
    private struct PreviousState {
        let retainHistory: Bool
        #if DEBUG
        let mirrorToConsole: Bool
        #endif
    }

    private static let lock = NSLock()
    private static var activeTokens: Set<UUID> = []
    private static var previousState: PreviousState?

    static func acquire() -> UUID {
        lock.lock()
        defer { lock.unlock() }
        let debug = IosLanDebug.shared
        if activeTokens.isEmpty {
            #if DEBUG
            previousState = PreviousState(retainHistory: debug.retainHistory, mirrorToConsole: debug.mirrorToConsole)
            #else
            previousState = PreviousState(retainHistory: debug.retainHistory)
            #endif
        }
        let token = UUID()
        activeTokens.insert(token)
        // In-app diagnostics and the startup permission probe need replay
        // even in Release: the async collector may attach after the epoch.
        debug.retainHistory = true
        #if DEBUG
        // Console.app/Xcode capture is a Debug-only test-harness opt-in.
        debug.mirrorToConsole = true
        #endif
        return token
    }

    static func release(_ token: UUID) {
        lock.lock()
        defer { lock.unlock() }
        guard activeTokens.remove(token) != nil, activeTokens.isEmpty else { return }
        guard let previous = previousState else { preconditionFailure("Missing diagnostic owner settings") }
        previousState = nil
        let debug = IosLanDebug.shared
        #if DEBUG
        debug.mirrorToConsole = previous.mirrorToConsole
        #endif
        // Disabling retention also clears the sample's bounded replay now,
        // rather than waiting for another transport event after teardown.
        debug.retainHistory = previous.retainHistory
    }
}
