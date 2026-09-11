import Foundation
import P2pKitShared
import XCTest
@testable import P2pKitSample

/// These tests exercise the production Swift adapter with a controlled Job seam.
/// The separate Kotlin tests and isolated native diagnostic case establish real
/// source/coroutine ownership; these inert controls do not claim that evidence.
final class OwnedFlowCollectionTests: XCTestCase {
    @MainActor
    func testCancelBeforeStartClosesAdmissionAndCancelledWaitersStillWaitForNativeRetirement() async {
        let (collection, job) = makeControlledOwnedCollection(String.self, completesOnCancel: false) { _ in
            XCTFail("a cancelled-before-start lease cannot deliver")
        }
        defer { collection.cancel(); job.complete(.cancelled) }
        collection.cancel()
        collection.start()
        XCTAssertEqual(job.snapshot.startCalls, 0)
        var acknowledgements = 0
        job.emit("late") { error in
            XCTAssertNil(error)
            acknowledgements += 1
        }
        XCTAssertEqual(acknowledgements, 1, "closed admission acknowledges without enqueuing work")

        let entered = expectation(description: "both retirement waiters entered")
        entered.expectedFulfillmentCount = 2
        let finished = expectation(description: "both retirement waiters finished")
        finished.expectedFulfillmentCount = 2
        var returns = 0
        let first = Task { @MainActor in
            entered.fulfill()
            assertOwnedCancelled(await collection.finish())
            returns += 1
            finished.fulfill()
        }
        let second = Task { @MainActor in
            entered.fulfill()
            assertOwnedCancelled(await collection.finish())
            returns += 1
            finished.fulfill()
        }
        defer { first.cancel(); second.cancel() }
        guard await waitForOwnedExpectations([entered]) else { return }
        first.cancel()
        second.cancel()
        XCTAssertEqual(returns, 0)
        XCTAssertFalse(collection.snapshot.nativeCompleted)
        XCTAssertFalse(collection.snapshot.finished)
        job.complete(.cancelled)
        guard await waitForOwnedExpectations([finished]) else { return }
        XCTAssertEqual(returns, 2)
        XCTAssertTrue(collection.snapshot.finished)
        XCTAssertEqual(collection.snapshot.callbackTaskCount, 0)
        XCTAssertEqual(job.snapshot.disposeCalls, 1)
    }

    @MainActor
    func testCancellationDuringImmediateCompletionRegistrationIsStickyAndDisposesTheReturnedHandle() async {
        let (collection, job) = makeControlledOwnedCollection(String.self) { _ in
            XCTFail("registration-time cancellation must prevent start")
        }
        defer { collection.cancel(); job.complete(.cancelled) }
        job.whenRegistering { [weak collection, weak job] in
            collection?.start()
            XCTAssertEqual(job?.snapshot.startCalls, 0, "reentrant start must wait for registration to finish")
            collection?.cancel()
        }
        collection.start()
        XCTAssertEqual(job.snapshot.startCalls, 0)
        guard await waitForOwnedCollection(collection, check: { assertOwnedCancelled($0) }) else { return }
        XCTAssertEqual(job.snapshot.observeCalls, 1)
        XCTAssertEqual(job.snapshot.disposeCalls, 1)
        collection.cancel()
        collection.start()
        guard await waitForOwnedCollection(collection, check: { assertOwnedCancelled($0) }) else { return }
        XCTAssertEqual(job.snapshot.startCalls, 0)
        XCTAssertEqual(job.snapshot.observeCalls, 1)
        XCTAssertEqual(job.snapshot.disposeCalls, 1)
    }

    @MainActor
    func testQueuedCallbackIsSkippedAndAcknowledgedBeforeCancelledDrainReturns() async {
        var received: [String] = []
        let (collection, job) = makeControlledOwnedCollection(String.self) { received.append($0) }
        defer { collection.cancel(); job.complete(.cancelled) }
        collection.start()
        var acknowledgements = 0
        job.emit("queued") { error in
            XCTAssertNil(error)
            acknowledgements += 1
        }
        // No actor yield: the accepted ticket is queued against the saved task.
        XCTAssertTrue(collection.snapshot.hasUnacknowledgedDelivery)
        XCTAssertEqual(collection.snapshot.callbackTaskCount, 1)
        collection.cancel()
        XCTAssertTrue(collection.snapshot.nativeCompleted)
        XCTAssertFalse(collection.snapshot.finished, "native completion alone is not callback retirement")
        XCTAssertEqual(acknowledgements, 0)
        guard await waitForOwnedCollection(collection, check: { assertOwnedCancelled($0) }) else { return }
        XCTAssertTrue(received.isEmpty)
        XCTAssertEqual(acknowledgements, 1)
        XCTAssertFalse(collection.snapshot.hasUnacknowledgedDelivery)
        XCTAssertEqual(collection.snapshot.callbackTaskCount, 0)
        job.emit("after-retirement") { error in
            XCTAssertNil(error)
            acknowledgements += 1
        }
        XCTAssertEqual(acknowledgements, 2)
        XCTAssertTrue(received.isEmpty)
    }

    @MainActor
    func testSerialBackpressureAcknowledgesOnlyAfterDeliveryWithoutGrowingCallbackTaskOwnership() async {
        var received: [Int] = []
        let (collection, job) = makeControlledOwnedCollection(Int.self) { received.append($0) }
        defer { collection.cancel(); job.complete(.cancelled) }
        collection.start()
        for value in 0..<32 {
            let acknowledged = expectation(description: "ordered emit acknowledged")
            job.emit(value) { error in
                XCTAssertNil(error)
                XCTAssertEqual(received, Array(0...value), "ack must follow the synchronous handler")
                acknowledged.fulfill()
            }
            XCTAssertEqual(received.count, value, "emit must not call MainActor code inline")
            XCTAssertEqual(collection.snapshot.callbackTaskCount, 1)
            guard await waitForOwnedExpectations([acknowledged]) else { return }
            XCTAssertFalse(collection.snapshot.hasUnacknowledgedDelivery)
            XCTAssertEqual(collection.snapshot.callbackTaskCount, 1, "not a growing history of per-value tasks")
        }
        job.complete(.completed)
        guard await waitForOwnedCollection(collection, check: { assertOwnedCompleted($0) }) else { return }
        XCTAssertEqual(received, Array(0..<32))
        XCTAssertEqual(collection.snapshot.callbackTaskCount, 0)
    }

    @MainActor
    func testNormalAndFailedNativeCompletionBothDrainAnAlreadyAcceptedCallback() async {
        for failed in [false, true] {
            let (collection, job) = makeControlledOwnedCollection(String.self) { _ in
                XCTFail("a terminal native collection closes queued handler admission")
            }
            defer { collection.cancel(); job.complete(.cancelled) }
            collection.start()
            var acknowledgements = 0
            job.emit("queued-at-terminal") { error in
                XCTAssertNil(error)
                acknowledgements += 1
            }
            job.complete(failed ? .failed(ControlledOwnedFailure.source) : .completed)
            XCTAssertTrue(collection.snapshot.nativeCompleted)
            XCTAssertFalse(collection.snapshot.finished)
            XCTAssertEqual(acknowledgements, 0)
            guard await waitForOwnedCollection(collection, check: { outcome in
                if failed {
                    guard case .failed(let error) = outcome else {
                        XCTFail("native failure must be preserved")
                        return
                    }
                    XCTAssertEqual(error as? ControlledOwnedFailure, .source)
                } else {
                    assertOwnedCompleted(outcome)
                }
                XCTAssertEqual(acknowledgements, 1)
            }) else { return }
            XCTAssertEqual(job.snapshot.disposeCalls, 1)
            XCTAssertEqual(collection.snapshot.callbackTaskCount, 0)
        }
    }

    @MainActor
    func testTypeMismatchCancelsNativeWithoutThrowingSwiftErrorAcrossKotlinAndPreservesFailure() async {
        let (collection, job) = makeControlledOwnedCollection(String.self) { _ in
            XCTFail("malformed values cannot be published")
        }
        defer { collection.cancel(); job.complete(.cancelled) }
        collection.start()
        var acknowledgements = 0
        job.emit(42) { error in
            XCTAssertNil(error, "arbitrary Swift NSError must never cross the Kotlin suspend boundary")
            acknowledgements += 1
        }
        guard await waitForOwnedCollection(collection, check: { outcome in
            guard case .failed(let error) = outcome,
                  let bridgeError = error as? OwnedFlowCollection.BridgeFailure,
                  case .unexpectedValue = bridgeError else {
                XCTFail("the Swift conversion failure must survive the native CancellationException")
                return
            }
        }) else { return }
        XCTAssertGreaterThan(job.snapshot.cancelCalls, 0)
        XCTAssertEqual(acknowledgements, 1)
        XCTAssertEqual(collection.snapshot.callbackTaskCount, 0)
    }

    @MainActor
    func testOverlappingEmitFailsClosedAndAcknowledgesBothWithoutAddingCallbackTasks() async {
        let (collection, job) = makeControlledOwnedCollection(String.self) { _ in
            XCTFail("invalid overlapping emission closes admission")
        }
        defer { collection.cancel(); job.complete(.cancelled) }
        collection.start()
        var acknowledgements = 0
        let acknowledge: (Error?) -> Void = { error in
            XCTAssertNil(error)
            acknowledgements += 1
        }
        job.emit("first", acknowledge: acknowledge)
        job.emit("illegal-overlap", acknowledge: acknowledge)
        XCTAssertEqual(acknowledgements, 1, "the second emit is rejected, not buffered")
        XCTAssertEqual(collection.snapshot.callbackTaskCount, 1)
        guard await waitForOwnedCollection(collection, check: { outcome in
            guard case .failed(let error) = outcome,
                  let bridgeError = error as? OwnedFlowCollection.BridgeFailure,
                  case .overlappingEmit = bridgeError else {
                XCTFail("overlapping source emission must be an explicit lease failure")
                return
            }
        }) else { return }
        XCTAssertEqual(acknowledgements, 2)
        XCTAssertEqual(collection.snapshot.callbackTaskCount, 0)
    }

    @MainActor
    func testBackgroundCallbacksAndCancellationUseTheSameThreadSafeAdmissionAndRetirement() async {
        let trace = OwnedFlowThreadTrace()
        let (collection, job) = makeControlledOwnedCollection(String.self) { value in
            XCTAssertTrue(Thread.isMainThread)
            trace.record("handler-\(value)")
        }
        defer { collection.cancel(); job.complete(.cancelled) }
        collection.start()
        let admitted = expectation(description: "off-actor emit returned after enrollment")
        let acknowledged = expectation(description: "off-actor emit acknowledged after actor handler")
        DispatchQueue.global().async {
            XCTAssertFalse(Thread.isMainThread)
            job.emit("live") { error in
                XCTAssertNil(error)
                trace.record("ack-live")
                acknowledged.fulfill()
            }
            admitted.fulfill()
        }
        guard await waitForOwnedExpectations([admitted, acknowledged]) else { return }
        XCTAssertEqual(trace.values, ["handler-live", "ack-live"])
        let closed = expectation(description: "off-actor cancellation closes late delivery")
        DispatchQueue.global().async {
            XCTAssertFalse(Thread.isMainThread)
            collection.cancel()
            job.emit("closed") { error in
                XCTAssertNil(error)
                trace.record("ack-closed")
            }
            closed.fulfill()
        }
        guard await waitForOwnedExpectations([closed]) else { return }
        guard await waitForOwnedCollection(collection, check: { assertOwnedCancelled($0) }) else { return }
        XCTAssertEqual(trace.values, ["handler-live", "ack-live", "ack-closed"])
        XCTAssertEqual(job.snapshot.disposeCalls, 1)
        XCTAssertEqual(collection.snapshot.callbackTaskCount, 0)
    }

    @MainActor
    func testRetirementReleasesNativeJobRegistrationAndHandlerCapture() async {
        weak var savedJob: ControlledOwnedFlowJob?
        weak var savedCapture: OwnedFlowCapture?
        let collection: OwnedFlowCollection
        do {
            let capture = OwnedFlowCapture()
            let (created, job) = makeControlledOwnedCollection(String.self) { _ in
                XCTAssertEqual(capture.label, "synthetic-handler-capture")
            }
            savedJob = job
            savedCapture = capture
            collection = created
            collection.start()
            collection.cancel()
        }
        defer { collection.cancel() }
        guard await waitForOwnedCollection(collection, check: { assertOwnedCancelled($0) }) else { return }
        XCTAssertNil(savedJob, "finished lease must drop the actual native job wrapper and registration")
        XCTAssertNil(savedCapture, "finished lease must drop the user handler even if the lease remains retained")
        XCTAssertTrue(collection.snapshot.finished)
    }
}

private final class OwnedFlowThreadTrace: @unchecked Sendable {
    private let lock = NSLock()
    private var recorded: [String] = []

    func record(_ value: String) {
        lock.lock()
        defer { lock.unlock() }
        recorded.append(value)
    }

    var values: [String] {
        lock.lock()
        defer { lock.unlock() }
        return recorded
    }
}

private final class OwnedFlowCapture {
    let label = "synthetic-handler-capture"
}

enum ControlledOwnedFailure: Error, Equatable {
    case source
}

/// Thread-safe inert Job control shared with Run integration tests. It holds the
/// actual production FlowCollector adapter, not an imitation Swift delivery path.
final class ControlledOwnedFlowJob: OwnedFlowJob, @unchecked Sendable {
    struct Snapshot {
        let startCalls: Int
        let cancelCalls: Int
        let observeCalls: Int
        let disposeCalls: Int
    }

    private let lock = NSLock()
    private let completesOnCancel: Bool
    private var collector: Kotlinx_coroutines_coreFlowCollector?
    private var handler: ((OwnedFlowCollection.Completion) -> Void)?
    private var outcome: OwnedFlowCollection.Completion?
    private var registering: (() -> Void)?
    private var cancelling: (() -> Void)?
    private var startCalls = 0
    private var cancelCalls = 0
    private var observeCalls = 0
    private var disposeCalls = 0

    init(completesOnCancel: Bool) {
        self.completesOnCancel = completesOnCancel
    }

    func attach(_ collector: Kotlinx_coroutines_coreFlowCollector) {
        locked { self.collector = collector }
    }

    func start() {
        locked { startCalls += 1 }
    }

    func cancel() {
        let hook = locked {
            cancelCalls += 1
            let hook = cancelling
            cancelling = nil
            return hook
        }
        hook?()
        if completesOnCancel { complete(.cancelled) }
    }

    func whenRegistering(_ hook: @escaping () -> Void) {
        locked { registering = hook }
    }

    func whenCancelling(_ hook: @escaping () -> Void) {
        locked { cancelling = hook }
    }

    func observeCompletion(_ handler: @escaping (OwnedFlowCollection.Completion) -> Void) -> () -> Void {
        let initial = locked {
            observeCalls += 1
            self.handler = handler
            let initial = (outcome, registering)
            registering = nil
            return initial
        }
        initial.1?()
        if let outcome = initial.0 { handler(outcome) }
        return { [weak self] in
            guard let self else { return }
            self.locked {
                self.disposeCalls += 1
                self.handler = nil
            }
        }
    }

    func complete(_ outcome: OwnedFlowCollection.Completion) {
        let callback: ((OwnedFlowCollection.Completion) -> Void)? = locked {
            guard self.outcome == nil else { return nil }
            self.outcome = outcome
            return handler
        }
        callback?(outcome)
    }

    func emit(_ value: Any?, acknowledge: @escaping (Error?) -> Void) {
        let collector = locked { self.collector }
        guard let collector else { preconditionFailure("test source has no collection adapter") }
        collector.emit(value: value, completionHandler: acknowledge)
    }

    var snapshot: Snapshot {
        locked {
            Snapshot(
                startCalls: startCalls, cancelCalls: cancelCalls,
                observeCalls: observeCalls, disposeCalls: disposeCalls
            )
        }
    }

    private func locked<Value>(_ operation: () -> Value) -> Value {
        lock.lock()
        defer { lock.unlock() }
        return operation()
    }
}

@MainActor
func makeControlledOwnedCollection<Value>(
    _ valueType: Value.Type,
    completesOnCancel: Bool = true,
    receive: @escaping @MainActor (Value) -> Void = { _ in }
) -> (collection: OwnedFlowCollection, job: ControlledOwnedFlowJob) {
    let job = ControlledOwnedFlowJob(completesOnCancel: completesOnCancel)
    let collection = OwnedFlowCollection(
        of: valueType,
        makeJob: { collector in job.attach(collector); return job },
        receive: receive
    )
    return (collection, job)
}

@MainActor
@discardableResult
func waitForOwnedCollection(
    _ collection: OwnedFlowCollection,
    check: @escaping @MainActor (OwnedFlowCollection.Completion) -> Void,
    file: StaticString = #filePath,
    line: UInt = #line
) async -> Bool {
    let finished = XCTestExpectation(description: "real adapter native and callback retirement")
    let waiting = Task { @MainActor in
        let outcome = await collection.finish()
        check(outcome)
        finished.fulfill()
    }
    defer { waiting.cancel() }
    return await waitForOwnedExpectations([finished], file: file, line: line)
}

@MainActor
@discardableResult
func waitForOwnedExpectations(
    _ expectations: [XCTestExpectation], file: StaticString = #filePath, line: UInt = #line
) async -> Bool {
    let result = await XCTWaiter.fulfillment(of: expectations, timeout: 2)
    XCTAssertEqual(result, .completed, file: file, line: line)
    return result == .completed
}

func assertOwnedCancelled(
    _ outcome: OwnedFlowCollection.Completion, file: StaticString = #filePath, line: UInt = #line
) {
    guard case .cancelled = outcome else {
        XCTFail("expected actual native cancellation completion", file: file, line: line)
        return
    }
}

func assertOwnedCompleted(
    _ outcome: OwnedFlowCollection.Completion, file: StaticString = #filePath, line: UInt = #line
) {
    guard case .completed = outcome else {
        XCTFail("expected actual normal native completion", file: file, line: line)
        return
    }
}
