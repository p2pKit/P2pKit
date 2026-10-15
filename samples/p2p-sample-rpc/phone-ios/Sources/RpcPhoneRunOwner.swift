import Combine

/// One foreground runtime, including a creation result that arrives after Stop.
/// A cancelled Swift task is not proof that imported Kotlin work was cancelled.
@MainActor
final class RpcPhoneRunOwner<Runtime: AnyObject>: ObservableObject {
    enum Phase { case idle, starting, running, stopping, cleanupPending }
    enum StartResult { case started, superseded, refused, failed(Error) }

    @MainActor
    private final class Run {
        let creation: Task<Runtime, Error>
        let close: (Runtime) async throws -> Void
        var runtime: Runtime?
        var retirement: Task<Bool, Never>?

        init(create: @escaping () async throws -> Runtime, close: @escaping (Runtime) async throws -> Void) {
            self.close = close
            // Intentionally retained independently of cancellation of the UI caller.
            creation = Task { try await create() }
        }
    }

    @Published private(set) var phase: Phase = .idle
    private var current: Run?

    var hasOwner: Bool { current != nil }
    var runtime: Runtime? { phase == .running ? current?.runtime : nil }

    func accepts(_ runtime: Runtime) -> Bool {
        phase == .running && current?.runtime === runtime
    }

    func start(
        create: @escaping () async throws -> Runtime,
        close: @escaping (Runtime) async throws -> Void
    ) async -> StartResult {
        guard current == nil, phase == .idle else { return .refused }
        let run = Run(create: create, close: close)
        current = run
        phase = .starting
        do {
            let value = try await run.creation.value
            run.runtime = value
            guard current === run, phase == .starting else { return .superseded }
            if Task.isCancelled {
                invalidate()
                _ = await stop()
                return .superseded
            }
            phase = .running
            return .started
        } catch {
            guard current === run, phase == .starting else { return .superseded }
            // Factory failure must already have cleaned any partially created native runtime.
            current = nil
            phase = .idle
            return .failed(error)
        }
    }

    /// Synchronous admission closure precedes cancelling/awaiting any outstanding UI action.
    func invalidate() {
        if current != nil { phase = .stopping }
    }

    /// Await the actual native close. A failure retains ownership and permits an explicit retry.
    func stop() async -> Bool {
        guard let run = current else { phase = .idle; return true }
        if let retirement = run.retirement { return await retirement.value }
        phase = .stopping
        let retirement = Task { @MainActor in
            let value: Runtime
            do {
                value = try await run.creation.value
                run.runtime = value
            } catch {
                if self.current === run { self.current = nil; self.phase = .idle }
                return true
            }
            do {
                try await run.close(value)
            } catch {
                if self.current === run { self.phase = .cleanupPending }
                return false
            }
            run.runtime = nil
            if self.current === run { self.current = nil; self.phase = .idle }
            return true
        }
        // Enrol the barrier before suspension so concurrent Stop callers join it.
        run.retirement = retirement
        let completed = await retirement.value
        run.retirement = nil
        return completed
    }
}
