import Foundation

/// One passive foreground observer. Neither the timer nor its callbacks own the runtime or perform peer actions.
@MainActor
final class RpcPhoneLiveObservation<Runtime: AnyObject, Value: Equatable> {
    typealias Scheduler = (TimeInterval, @escaping () -> Void) -> (() -> Void)
    private let schedule: Scheduler
    private weak var runtime: Runtime?
    private var generation: UUID?
    private var cancel: (() -> Void)?
    private var manualTick: (() -> Void)?
    private var lastValue: Value?
    private var lastFailure: RpcPhoneEventLog.Failure?

    init(schedule: @escaping Scheduler = { seconds, tick in
        let task = Task { @MainActor in
            while !Task.isCancelled {
                do { try await Task.sleep(nanoseconds: UInt64(seconds * 1_000_000_000)) }
                catch { return }
                guard !Task.isCancelled else { return }
                tick()
            }
        }
        return { task.cancel() }
    }) { self.schedule = schedule }

    var observing: Bool { generation != nil }

    func start(_ runtime: Runtime, eligible: @escaping (Runtime) -> Bool,
               read: @escaping (Runtime) throws -> Value, classify: @escaping (Error) -> RpcPhoneEventLog.Failure,
               changed: @escaping (Value) -> Void, failed: @escaping (RpcPhoneEventLog.Failure) -> Void) {
        if generation != nil, self.runtime === runtime {
            if !eligible(runtime) { stop() }
            return
        }
        stop()
        guard eligible(runtime) else { return }
        self.runtime = runtime
        let token = UUID()
        generation = token
        let tick = { [weak self, weak runtime] in
            guard let self, self.generation == token else { return }
            guard let runtime, self.runtime === runtime, eligible(runtime) else { self.stop(); return }
            do {
                let value = try read(runtime)
                guard self.generation == token else { return }
                guard eligible(runtime) else { self.stop(); return }
                let recovered = self.lastFailure != nil
                self.lastFailure = nil
                if self.lastValue != value || recovered {
                    self.lastValue = value
                    changed(value)
                }
            } catch {
                guard self.generation == token else { return }
                guard eligible(runtime) else { self.stop(); return }
                let failure = classify(error)
                if self.lastFailure != failure {
                    self.lastFailure = failure
                    failed(failure)
                }
            }
        }
        manualTick = tick
        tick()
        guard generation == token else { return }
        let cancellation = schedule(0.5, tick)
        // A synchronous injected scheduler can invalidate the generation before returning its cancellation.
        if generation == token { cancel = cancellation } else { cancellation() }
    }

    /// The optional button shares the timer's exact deduplication and recovery state.
    func refresh() { manualTick?() }

    func stop() {
        generation = nil
        runtime = nil
        manualTick = nil
        cancel?()
        cancel = nil
        lastValue = nil
        lastFailure = nil
    }

    deinit { cancel?() }
}

struct RpcPhoneCounter: Equatable {
    static let capacityNotice = "Live cards unavailable during a capacity session; use explicit diagnostic snapshot."
    let id: String
    let label: String
    let value: String

    static func cards(_ snapshot: RpcPhoneEventLog.Snapshot?, host: Bool, busy: Bool) -> [Self] {
        if host {
            return [.init(id: "clients", label: "Clients", value: snapshot.map { String($0.clients) } ?? "—"),
                .init(id: "pending", label: "Pending", value: snapshot.map { String($0.pending) } ?? "—"),
                .init(id: "completed", label: "Completed", value: snapshot.map { String($0.completed) } ?? "—"),
                .init(id: "queued", label: "Queued", value: snapshot.map { String($0.queued) } ?? "—")]
        }
        return [.init(id: "connected", label: "Connected", value: snapshot.map { $0.state == "Ready" ? "1" : "0" } ?? "—"),
            .init(id: "inFlight", label: "In flight", value: snapshot == nil ? "—" : (busy ? "1" : "0")),
            .init(id: "completed", label: "Completed", value: snapshot.map { String($0.completed) } ?? "—"),
            .init(id: "queued", label: "Queued", value: snapshot.map { String($0.queued) } ?? "—")]
    }
}
