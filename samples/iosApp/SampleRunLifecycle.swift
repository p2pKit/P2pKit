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
        enum CollectionRole: Hashable {
            case diagnostics
            case incomingSessions
            case messages(sessionId: String)
            case pendingOffers(sessionId: String)

            var label: String {
                switch self {
                case .diagnostics: return "diagnostics"
                case .incomingSessions: return "incoming sessions"
                case .messages: return "messages"
                case .pendingOffers: return "pending offers"
                }
            }
        }

        struct CollectionFailure {
            let role: CollectionRole
            let error: Error
        }

        private struct CollectionEntry {
            let role: CollectionRole
            let collection: OwnedFlowCollection
            let retirement: Task<OwnedFlowCollection.Completion, Never>
        }

        private var tracingReleases: [() -> Void] = []
        fileprivate var tracingReleased = false
        private var observersClosed = false
        private var collectionsClosed = false
        private var activeCollections: [CollectionRole: OwnedFlowCollection] = [:]
        // Includes removed/replaced sessions until real terminal + callback drain.
        private var ownedCollections: [ObjectIdentifier: CollectionEntry] = [:]
        private(set) var firstCollectionFailure: CollectionFailure?
        private(set) var collectionFailureCount = 0

        var ownedCollectionCount: Int { ownedCollections.count }

        func collection(for role: CollectionRole) -> OwnedFlowCollection? {
            activeCollections[role]
        }

        fileprivate func ownCollection(
            _ collection: OwnedFlowCollection,
            role: CollectionRole,
            admitted: Bool,
            reportFailure: @escaping @MainActor (CollectionFailure) -> Void
        ) {
            let id = ObjectIdentifier(collection)
            guard ownedCollections[id] == nil else { return }
            let previous = activeCollections.updateValue(collection, forKey: role)
            let retirement = Task { @MainActor [weak self, collection] in
                let outcome = await collection.finish()
                self?.collectionFinished(id, outcome: outcome, reportFailure: reportFailure)
                return outcome
            }
            // Store both identities and the monitor BEFORE native observation/start.
            ownedCollections[id] = CollectionEntry(role: role, collection: collection, retirement: retirement)
            previous?.cancel()
            let roleOpen = role == .diagnostics ? !tracingReleased : !observersClosed
            if admitted && roleOpen && !collectionsClosed {
                collection.start()
            } else {
                collection.cancel()
            }
        }

        /// Removing an active role is not disposal. Its monitor stays registered,
        /// so a later Stop also waits for this retiree and cannot miss its failure.
        @discardableResult
        func retireCollection(for role: CollectionRole) -> Task<OwnedFlowCollection.Completion, Never>? {
            guard let collection = activeCollections.removeValue(forKey: role) else { return nil }
            collection.cancel()
            return ownedCollections[ObjectIdentifier(collection)]?.retirement
        }

        fileprivate func cancelObserverCollections() {
            observersClosed = true
            let observers = ownedCollections.values.filter { $0.role != .diagnostics }
            activeCollections = activeCollections.filter { $0.key == .diagnostics }
            observers.forEach { $0.collection.cancel() }
        }

        fileprivate func drainCollections() async {
            collectionsClosed = true
            while !ownedCollections.isEmpty {
                let entries = Array(ownedCollections.values)
                entries.forEach { $0.collection.cancel() }
                for entry in entries {
                    _ = await entry.retirement.value
                }
                // A rejected lazy lease enrolled during an await is retained too.
            }
        }

        private func collectionFinished(
            _ id: ObjectIdentifier,
            outcome: OwnedFlowCollection.Completion,
            reportFailure: @MainActor (CollectionFailure) -> Void
        ) {
            guard let entry = ownedCollections.removeValue(forKey: id) else { return }
            if activeCollections[entry.role] === entry.collection {
                activeCollections[entry.role] = nil
            }
            if case .failed(let error) = outcome {
                let failure = CollectionFailure(role: entry.role, error: error)
                if firstCollectionFailure == nil { firstCollectionFailure = failure }
                collectionFailureCount += 1
                reportFailure(failure)
            }
        }

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
            retireCollection(for: .diagnostics)
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

    /// Ownership enrollment precedes native completion registration and lazy start.
    /// Even a rejected lease is retained by its captured Run until real retirement.
    func ownCollection(
        _ collection: OwnedFlowCollection,
        role: Run.CollectionRole,
        run: Run,
        reportFailure: @escaping @MainActor (Run.CollectionFailure) -> Void = { _ in }
    ) {
        let admitted = acceptsWork(run) && (role != .diagnostics || ownsTracing(run))
        run.ownCollection(collection, role: role, admitted: admitted, reportFailure: reportFailure)
    }

    /// Only before any SDK kit was acquired. Diagnostics may already be live:
    /// a synchronous defer cannot make this cleanup barrier complete.
    func abandonUnbuilt(_ run: Run) async {
        guard owns(run), phase == .starting else { return }
        phase = .stopping
        run.cancelObserverCollections()
        run.releaseTracing()
        await run.drainCollections()
        guard owns(run) else { return }
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
        run.cancelObserverCollections()
        let sdkResult: Result<Void, Error>
        do {
            try await operation()
            sdkResult = .success(())
        } catch {
            sdkResult = .failure(error)
        }
        // Keep tracing through the SDK cleanup attempt, then independently drain
        // every observer, including removed sessions, even when SDK Stop failed.
        run.releaseTracing()
        await run.drainCollections()
        guard owns(run) else { return }
        if case .failure(let error) = sdkResult {
            phase = .cleanupPending
            failed(error)
            return
        }
        // An observer failure is preserved/reported by Run, but a failed AND
        // drained lease is not an unrecoverable SDK cleanupPending condition.
        succeeded()
        current = nil
        phase = .idle
    }
}
