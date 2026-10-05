import Foundation
import UIKit

/// A single, non-renewing app-switch allowance, never an unlimited background server.
@MainActor
final class RpcPhoneShareWindow {
    typealias Scheduler = (TimeInterval, @escaping () -> Void) -> (() -> Void)
    private let now: () -> TimeInterval
    private let begin: (@escaping () -> Void) -> UIBackgroundTaskIdentifier
    private let end: (UIBackgroundTaskIdentifier) -> Void
    private let schedule: Scheduler
    private var token: UUID?
    private var deadline: TimeInterval = 0
    private var task: UIBackgroundTaskIdentifier = .invalid
    private var cancelTimer: (() -> Void)?
    private var expired: (() -> Void)?

    init(now: @escaping () -> TimeInterval = { ProcessInfo.processInfo.systemUptime },
         begin: @escaping (@escaping () -> Void) -> UIBackgroundTaskIdentifier = { expired in
             UIApplication.shared.beginBackgroundTask(withName: "Finish RPC invitation transfer", expirationHandler: expired)
         },
         end: @escaping (UIBackgroundTaskIdentifier) -> Void = { UIApplication.shared.endBackgroundTask($0) },
         schedule: @escaping Scheduler = { seconds, action in
             let timer = Task { @MainActor in
                 do { try await Task.sleep(nanoseconds: UInt64(seconds * 1_000_000_000)) }
                 catch { return }
                 action()
             }
             return { timer.cancel() }
         }) {
        self.now = now
        self.begin = begin
        self.end = end
        self.schedule = schedule
    }

    static func eligible(running: Bool, actionBusy: Bool, operationBusy: Bool,
                         cleanupPending: Bool, capacitySession: Bool) -> Bool {
        running && !actionBusy && !operationBusy && !cleanupPending && !capacitySession
    }

    var pending: Bool { token != nil }

    func leave(expired: @escaping () -> Void) -> Bool {
        // Repeated inactive/background notifications cannot renew an existing allowance.
        if pending { return now() < deadline }
        let generation = UUID()
        token = generation
        deadline = now() + 25
        self.expired = expired
        let identifier = begin { [weak self] in self?.expire(generation) }
        guard token == generation else {
            if identifier != .invalid { end(identifier) }
            return false
        }
        guard identifier != .invalid else { cancel(); return false }
        task = identifier
        let remaining = deadline - now()
        guard remaining > 0 else { expire(generation); return false }
        let cancellation = schedule(remaining) { [weak self] in self?.expire(generation) }
        guard token == generation else { cancellation(); return false }
        cancelTimer = cancellation
        return true
    }

    /// Check monotonic time before resuming: a suspended timer is never evidence of an unexpired lease.
    func resume() -> Bool {
        guard pending else { return false }
        let valid = now() < deadline
        let callback = expired
        cancel()
        if !valid { callback?() }
        return valid
    }

    func cancel() {
        token = nil
        deadline = 0
        expired = nil
        cancelTimer?()
        cancelTimer = nil
        let identifier = task
        task = .invalid
        if identifier != .invalid { end(identifier) }
    }

    private func expire(_ generation: UUID) {
        guard token == generation else { return }
        let callback = expired
        cancel()
        callback?()
    }
}
