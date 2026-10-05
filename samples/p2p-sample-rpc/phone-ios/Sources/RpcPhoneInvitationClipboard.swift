import Foundation
import UIKit

/// Explicit device-local copying only. Never read the user's pre-existing clipboard contents.
@MainActor
final class RpcPhoneInvitationClipboard {
    typealias Scheduler = (TimeInterval, @escaping () -> Void) -> (() -> Void)
    private let pasteboard: UIPasteboard
    private let uptime: () -> TimeInterval
    private let wallTime: () -> Date
    private let schedule: Scheduler
    private var invitation = ""
    private var deadline: TimeInterval = 0
    private var generation: UUID?
    private var copiedChange: Int?
    private var cancelExpiry: (() -> Void)?

    init(pasteboard: UIPasteboard = .general,
         uptime: @escaping () -> TimeInterval = { ProcessInfo.processInfo.systemUptime },
         wallTime: @escaping () -> Date = Date.init,
         schedule: @escaping Scheduler = { seconds, action in
             let task = Task { @MainActor in
                 do { try await Task.sleep(nanoseconds: UInt64(seconds * 1_000_000_000)) }
                 catch { return }
                 action()
             }
             return { task.cancel() }
         }) {
        self.pasteboard = pasteboard
        self.uptime = uptime
        self.wallTime = wallTime
        self.schedule = schedule
    }

    /// Capture before the native mint starts; repeated copying cannot restart the two-minute clock.
    func beginMinting() -> TimeInterval { retire(); return uptime() }

    func minted(_ value: String, started: TimeInterval, expired: @escaping () -> Void) {
        retire()
        let remaining = 120 - (uptime() - started)
        guard !value.isEmpty, value.utf8.count <= 512, started >= 0, started <= uptime(),
              remaining > 0 else { expired(); return }
        invitation = value
        deadline = started + 120
        let token = UUID()
        generation = token
        cancelExpiry = schedule(remaining) { [weak self] in
            guard let self, self.generation == token else { return }
            self.retire()
            expired()
        }
    }

    static func options(expiration: Date) -> [UIPasteboard.OptionsKey: Any] {
        [.localOnly: true, .expirationDate: expiration]
    }

    func copy() -> Bool {
        let remaining = deadline - uptime()
        guard !invitation.isEmpty, remaining > 0 else { retire(); return false }
        pasteboard.setItems([["public.utf8-plain-text": invitation]],
            options: Self.options(expiration: wallTime().addingTimeInterval(remaining)))
        copiedChange = pasteboard.changeCount
        return true
    }

    func retire() {
        generation = nil
        cancelExpiry?()
        cancelExpiry = nil
        invitation = ""
        deadline = 0
        if let copiedChange, pasteboard.changeCount == copiedChange { pasteboard.items = [] }
        copiedChange = nil
    }
}
