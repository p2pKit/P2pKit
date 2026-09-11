import Foundation
import P2pKitShared

/// Sample-private ownership of the actual Kotlin collection coroutine.
/// Handlers are short, synchronous MainActor work, never arbitrary async work.
/// A handler may request cancellation, but must not await its own finish().
final class OwnedFlowCollection: @unchecked Sendable {
    enum Completion: @unchecked Sendable {
        case completed
        case cancelled
        case failed(Error)
    }

    enum BridgeFailure: Error, Sendable {
        case unexpectedValue(expected: String)
        case overlappingEmit
    }

    struct NativeFailure: Error, @unchecked Sendable {
        let cause: KotlinThrowable
    }

    struct Snapshot: Sendable {
        let nativeCompleted: Bool
        let finished: Bool
        let hasUnacknowledgedDelivery: Bool
        let callbackTaskCount: Int
    }

    private let state: CollectionState

    convenience init<Value>(
        flow: Kotlinx_coroutines_coreFlow,
        of valueType: Value.Type,
        receive: @escaping @MainActor (Value) -> Void
    ) {
        self.init(
            of: valueType,
            makeJob: { collector in
                KotlinOwnedFlowJob(
                    IosOwnedFlowCollectionKt.createIosOwnedFlowCollection(flow: flow, collector: collector)
                )
            },
            receive: receive
        )
    }

    /// The narrow job seam lets ordering tests drive the real adapter without
    /// pretending a Swift stub establishes Native coroutine cancellation.
    init<Value>(
        of valueType: Value.Type,
        makeJob: (Kotlinx_coroutines_coreFlowCollector) -> OwnedFlowJob,
        receive: @escaping @MainActor (Value) -> Void
    ) {
        let state = CollectionState { value in
            guard let decoded = value as? Value else {
                return BridgeFailure.unexpectedValue(expected: String(reflecting: valueType))
            }
            receive(decoded)
            return nil
        }
        self.state = state
        state.install(makeJob(state))
    }

    /// Enroll this lease with its Run BEFORE calling start. The native factory
    /// is lazy; neither construction nor completion registration subscribes.
    func start() {
        state.start()
    }

    /// Closes Swift admission before cancelling the actual Kotlin Job. Sticky
    /// even before registration; cancellation never acknowledges a live handler early.
    func cancel() {
        state.requestCancellation()
        state.register()
    }

    /// Shared, non-cancellation-shortcut barrier: native terminal completion AND
    /// the one owned callback task's actual return, on success/failure/cancel alike.
    /// Waiting does not start a lazy Job, unlike Kotlin Job.join().
    func finish() async -> Completion {
        state.register()
        return await state.waitForRetirement()
    }

    var snapshot: Snapshot { state.snapshot }

    deinit {
        // State retains its bounded retirement work until the real barrier;
        // dropping a UI handle is a cancellation request, not disposal evidence.
        cancel()
    }
}

/// Only these operations are needed from the already-exported Job protocol.
/// Implementations must be thread-safe; this is not an alternative collection token.
protocol OwnedFlowJob: AnyObject, Sendable {
    func start()
    func cancel()
    func observeCompletion(_ handler: @escaping (OwnedFlowCollection.Completion) -> Void) -> () -> Void
}

private final class KotlinOwnedFlowJob: OwnedFlowJob, @unchecked Sendable {
    private let nativeJob: Kotlinx_coroutines_coreJob

    init(_ nativeJob: Kotlinx_coroutines_coreJob) {
        self.nativeJob = nativeJob
    }

    func start() { _ = nativeJob.start() }
    func cancel() { nativeJob.cancel(cause: nil) }

    func observeCompletion(_ handler: @escaping (OwnedFlowCollection.Completion) -> Void) -> () -> Void {
        let registration = nativeJob.invokeOnCompletion { cause in
            if let cause {
                if cause is KotlinCancellationException {
                    handler(.cancelled)
                } else {
                    handler(.failed(OwnedFlowCollection.NativeFailure(cause: cause)))
                }
            } else {
                handler(.completed)
            }
        }
        return { registration.dispose() }
    }
}

/// One locked rendezvous, not an AsyncStream or a queue. Every admitted emit is
/// covered by an already-owned MainActor task. Keeping that one task until it
/// returns avoids both unbounded per-value Task history and prune-before-return races.
private final class CollectionState: NSObject, Kotlinx_coroutines_coreFlowCollector, @unchecked Sendable {
    typealias Completion = OwnedFlowCollection.Completion
    typealias Handler = @MainActor (Any?) -> Error?

    private struct Delivery: @unchecked Sendable {
        let value: Any?
        let acknowledge: (Error?) -> Void
    }

    private struct Resources {
        let job: OwnedFlowJob?
        let registration: (() -> Void)?
        let callbacks: Task<Void, Never>?
        let retirement: Task<Void, Never>?
        let handler: Handler?
    }

    private let lock = NSLock()
    private var nativeJob: OwnedFlowJob?
    private var registration: (() -> Void)?
    private var registered = false
    private var registrationComplete = false
    private var registrationWaiter: CheckedContinuation<Void, Never>?
    private var startRequested = false
    private var started = false
    private var cancellationRequested = false
    private var swiftFailure: Error?
    private var nativeCompletion: Completion?
    private var nativeWaiter: CheckedContinuation<Completion, Never>?
    private var completion: Completion?
    private var finishWaiters: [CheckedContinuation<Completion, Never>] = []
    private var handler: Handler?
    private var pending: Delivery?
    private var unacknowledged = false
    private var deliveryWaiter: CheckedContinuation<Delivery?, Never>?
    private var callbackTask: Task<Void, Never>?
    private var retirementTask: Task<Void, Never>?

    init(handler: @escaping Handler) {
        self.handler = handler
        super.init()
    }

    func install(_ job: OwnedFlowJob) {
        locked { nativeJob = job }
    }

    func register() {
        let job: OwnedFlowJob? = locked {
            guard !registered else { return nil }
            registered = true
            let callbacks = Task { @MainActor [self] in
                while let delivery = await nextDelivery() {
                    // Claiming execution linearizes against closing admission.
                    // Once claimed, synchronous actor work is allowed to finish.
                    let receive = admittedHandler()
                    if let error = receive?(delivery.value) {
                        requestCancellation(failure: error)
                    }
                    acknowledge(delivery)
                }
            }
            callbackTask = callbacks
            retirementTask = Task { [self] in
                let native = await waitForNativeCompletion()
                await callbacks.value
                // observeCompletion may call back synchronously before it has
                // returned its disposable. Never publish retirement before that
                // registration has also been acquired and disposed.
                await waitForRegistration()
                retire(native)
            }
            return nativeJob
        }
        guard let job else { return }
        let handle = job.observeCompletion { [weak self] outcome in
            self?.nativeFinished(outcome)
        }
        let waiter = locked {
            registration = handle
            registrationComplete = true
            let waiter = registrationWaiter
            registrationWaiter = nil
            return waiter
        }
        waiter?.resume()
        startIfReady()
    }

    func start() {
        locked { startRequested = true }
        register()
        startIfReady()
    }

    private func startIfReady() {
        let job: OwnedFlowJob? = locked {
            guard registrationComplete, startRequested, !started,
                  !cancellationRequested, nativeCompletion == nil else { return nil }
            // Start admission is committed here. A racing cancellation after
            // this point still closes delivery and cancels this same native Job.
            started = true
            return nativeJob
        }
        job?.start()
    }

    func requestCancellation(failure: Error? = nil) {
        let action: (OwnedFlowJob?, CheckedContinuation<Delivery?, Never>?) = locked {
            guard completion == nil else { return (nil, nil) }
            if swiftFailure == nil { swiftFailure = failure }
            cancellationRequested = true
            let waiter = deliveryWaiter
            deliveryWaiter = nil
            return (nativeJob, waiter)
        }
        action.1?.resume(returning: nil)
        action.0?.cancel()
    }

    func emit(value: Any?, completionHandler: @escaping (Error?) -> Void) {
        lock.lock()
        guard started, !cancellationRequested, nativeCompletion == nil else {
            lock.unlock()
            completionHandler(nil)
            return
        }
        guard !unacknowledged else {
            // FlowCollector forbids overlapping emit. Fail closed rather than
            // create a buffer or inject an arbitrary Swift NSError into Kotlin.
            if swiftFailure == nil { swiftFailure = OwnedFlowCollection.BridgeFailure.overlappingEmit }
            cancellationRequested = true
            let job = nativeJob
            let waiter = deliveryWaiter
            deliveryWaiter = nil
            lock.unlock()
            waiter?.resume(returning: nil)
            job?.cancel()
            completionHandler(nil)
            return
        }
        unacknowledged = true
        let delivery = Delivery(value: value, acknowledge: completionHandler)
        let waiter = deliveryWaiter
        deliveryWaiter = nil
        if waiter == nil { pending = delivery }
        lock.unlock()
        waiter?.resume(returning: delivery)
    }

    private func nextDelivery() async -> Delivery? {
        await withCheckedContinuation { waiter in
            lock.lock()
            if let delivery = pending {
                pending = nil
                lock.unlock()
                waiter.resume(returning: delivery)
            } else if cancellationRequested || nativeCompletion != nil {
                lock.unlock()
                waiter.resume(returning: nil)
            } else {
                deliveryWaiter = waiter
                lock.unlock()
            }
        }
    }

    private func admittedHandler() -> Handler? {
        locked { cancellationRequested || nativeCompletion != nil ? nil : handler }
    }

    private func acknowledge(_ delivery: Delivery) {
        // The callback is owned only by the single delivery task. Clear its
        // slot before ack, since Kotlin may synchronously emit the next value.
        locked { unacknowledged = false }
        delivery.acknowledge(nil)
    }

    private func nativeFinished(_ outcome: Completion) {
        let waiters: (CheckedContinuation<Delivery?, Never>?, CheckedContinuation<Completion, Never>?) = locked {
            guard nativeCompletion == nil else { return (nil, nil) }
            nativeCompletion = outcome
            let waiters = (deliveryWaiter, nativeWaiter)
            deliveryWaiter = nil
            nativeWaiter = nil
            return waiters
        }
        waiters.0?.resume(returning: nil)
        waiters.1?.resume(returning: outcome)
    }

    private func waitForNativeCompletion() async -> Completion {
        await withCheckedContinuation { waiter in
            let ready: Completion? = locked {
                if let nativeCompletion { return nativeCompletion }
                nativeWaiter = waiter
                return nil
            }
            if let ready { waiter.resume(returning: ready) }
        }
    }

    private func waitForRegistration() async {
        await withCheckedContinuation { waiter in
            let ready = locked {
                if registrationComplete { return true }
                registrationWaiter = waiter
                return false
            }
            if ready { waiter.resume() }
        }
    }

    private func retire(_ native: Completion) {
        let outcome: Completion = locked { swiftFailure.map { .failed($0) } ?? native }
        var resources: Resources? = locked {
            let resources = Resources(
                job: nativeJob, registration: registration, callbacks: callbackTask,
                retirement: retirementTask, handler: handler
            )
            nativeJob = nil
            registration = nil
            callbackTask = nil
            retirementTask = nil
            handler = nil
            swiftFailure = nil
            return resources
        }
        resources?.registration?()
        // Dropping captured user/native references must also happen outside the
        // lock, before even a late finish() caller can observe completed cleanup.
        resources = nil
        let waiters = locked {
            completion = outcome
            let waiters = finishWaiters
            finishWaiters = []
            return waiters
        }
        waiters.forEach { $0.resume(returning: outcome) }
    }

    func waitForRetirement() async -> Completion {
        await withCheckedContinuation { waiter in
            let ready: Completion? = locked {
                if let completion { return completion }
                finishWaiters.append(waiter)
                return nil
            }
            if let ready { waiter.resume(returning: ready) }
        }
    }

    var snapshot: OwnedFlowCollection.Snapshot {
        locked {
            OwnedFlowCollection.Snapshot(
                nativeCompleted: nativeCompletion != nil,
                finished: completion != nil,
                hasUnacknowledgedDelivery: unacknowledged,
                callbackTaskCount: callbackTask == nil ? 0 : 1
            )
        }
    }

    private func locked<Value>(_ operation: () -> Value) -> Value {
        lock.lock()
        defer { lock.unlock() }
        return operation()
    }
}
