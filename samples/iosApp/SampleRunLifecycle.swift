import Combine

/// Main-actor ownership for one sample Start/Stop run. SDK cleanup is supplied
/// by the real caller; invalidation must never substitute for stopping the kit.
@MainActor
final class SampleRunLifecycle: ObservableObject {
    enum Phase: Equatable {
        case idle
        case starting
        case running
        case stopping
        case cleanupPending
    }

    enum StartupOutcome {
        case started
        case superseded
        case failed(Error)
    }

    @MainActor
    final class Run {
        private var tracingReleases: [() -> Void] = []
        fileprivate var tracingReleased = false

        fileprivate init() {}

        func ownTracing(_ release: @escaping () -> Void) {
            if tracingReleased {
                release()
            } else {
                tracingReleases.append(release)
            }
        }

        func releaseTracing() {
            guard !tracingReleased else { return }
            tracingReleased = true
            let releases = tracingReleases
            tracingReleases = []
            releases.forEach { $0() }
        }
    }

    @Published private(set) var phase: Phase = .idle
    private(set) var current: Run?

    func begin() -> Run? {
        guard current == nil, phase == .idle else { return nil }
        let run = Run()
        current = run
        phase = .starting
        return run
    }

    func owns(_ run: Run) -> Bool {
        current === run
    }

    func ownsTracing(_ run: Run) -> Bool {
        owns(run) && !run.tracingReleased
    }

    func acceptsWork(_ run: Run) -> Bool {
        owns(run) && (phase == .starting || phase == .running)
    }

    /// Admission and publication are synchronous with invalidation on this actor.
    /// ContentView uses this same boundary for session collector registration.
    @discardableResult
    func withActiveRun(_ run: Run, _ operation: () -> Void) -> Bool {
        guard acceptsWork(run) else { return false }
        operation()
        return true
    }

    /// Capture the owner at the UI action, not when its queued Task eventually runs.
    @discardableResult
    func launchAction(_ operation: @escaping @MainActor (Run) async -> Void) -> Task<Void, Never>? {
        guard let run = current, acceptsWork(run) else { return nil }
        return Task { @MainActor in
            guard self.acceptsWork(run), !Task.isCancelled else { return }
            await operation(run)
        }
    }

    /// Used by the permission probe: neither cancellation nor retirement is a
    /// completed delay. The injected delay also permits a bounded actor test.
    func afterDelay(
        _ run: Run,
        delay: () async throws -> Void,
        perform: () -> Void
    ) async {
        guard acceptsWork(run), !Task.isCancelled else { return }
        do {
            try await delay()
        } catch { return }
        guard !Task.isCancelled else { return }
        withActiveRun(run, perform)
    }

    /// Only for a synchronous create failure, before any SDK kit was acquired.
    func abandonUnbuilt(_ run: Run) {
        guard owns(run), phase == .starting else { return }
        run.releaseTracing()
        current = nil
        phase = .idle
    }

    /// The sample's actual startup sequence. A non-fatal manual-info failure is
    /// delivered only to its still-active owner, just like a successful result.
    func completeStartup<Info>(
        _ run: Run,
        advertise: () async throws -> Void,
        didAdvertise: () -> Void,
        discover: () async throws -> Void,
        didDiscover: () -> Void,
        manualInfo: () async throws -> Info,
        didReadInfo: (Result<Info, Error>) -> Void,
        installObservers: () -> Void
    ) async -> StartupOutcome {
        guard acceptsWork(run), phase == .starting else { return .superseded }
        do {
            try Task.checkCancellation()
            try await advertise()
            guard acceptsWork(run) else { return .superseded }
            try Task.checkCancellation()
            didAdvertise()
            try await discover()
            guard acceptsWork(run) else { return .superseded }
            try Task.checkCancellation()
            didDiscover()
            let info: Result<Info, Error>
            do {
                info = .success(try await manualInfo())
            } catch is CancellationError {
                throw CancellationError()
            } catch {
                info = .failure(error)
            }
            guard acceptsWork(run) else { return .superseded }
            try Task.checkCancellation()
            didReadInfo(info)
            phase = .running
            withActiveRun(run, installObservers)
            return .started
        } catch {
            return acceptsWork(run) ? .failed(error) : .superseded
        }
    }

    /// Invalidate BEFORE the cancellation snapshot. A failure retains ownership
    /// and the Stop retry affordance; caller cancellation cannot skip operation.
    func stop(
        _ run: Run,
        cancelObservers: () -> Void,
        operation: () async throws -> Void,
        succeeded: () -> Void,
        failed: (Error) -> Void
    ) async {
        guard owns(run), phase != .stopping else { return }
        phase = .stopping
        cancelObservers()
        defer { run.releaseTracing() }
        do {
            try await operation()
        } catch {
            guard owns(run) else { return }
            phase = .cleanupPending
            failed(error)
            return
        }
        guard owns(run) else { return }
        succeeded()
        current = nil
        phase = .idle
    }
}
