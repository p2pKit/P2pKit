import XCTest
import P2pKitRpcExample
@testable import P2pKitRpcPhone

private final class SyntheticRuntime { var closes = 0 }
private enum SyntheticFailure: Error { case operation }

@MainActor
private final class Held<Value> {
    private var continuation: CheckedContinuation<Value, Error>?
    private var outcome: Result<Value, Error>?

    func wait() async throws -> Value {
        if let outcome { return try outcome.get() }
        return try await withCheckedThrowingContinuation { continuation = $0 }
    }

    func resolve(_ outcome: Result<Value, Error>) {
        guard self.outcome == nil else { return }
        self.outcome = outcome
        continuation?.resume(with: outcome)
        continuation = nil
    }
}

final class RpcPhoneRunOwnerTests: XCTestCase {
    @MainActor
    func testActualKeychainRoundTripNamespacesRevocationAndFixtureRetirement() async throws {
        // The same real-storage regression runs in the application, not an unentitled CLI binary.
        try await RpcPhoneIosControls.shared.verifySyntheticTrustStore()
    }

    @MainActor
    func testExplicitStartAndCloseOwnExactlyOneRuntime() async {
        let owner = RpcPhoneRunOwner<SyntheticRuntime>()
        let runtime = SyntheticRuntime()
        let result = await owner.start(create: { runtime }, close: { $0.closes += 1 })
        guard case .started = result else { return XCTFail("Runtime was not admitted") }
        XCTAssertTrue(owner.accepts(runtime))
        let refused = await owner.start(create: { XCTFail("Duplicate factory"); return runtime }, close: { _ in })
        guard case .refused = refused else { return XCTFail("Parallel role was admitted") }
        let stopped = await owner.stop()
        XCTAssertTrue(stopped)
        XCTAssertEqual(runtime.closes, 1)
        XCTAssertFalse(owner.hasOwner)
        XCTAssertFalse(owner.accepts(runtime))
        let stoppedAgain = await owner.stop()
        XCTAssertTrue(stoppedAgain)
        XCTAssertEqual(runtime.closes, 1)
    }

    @MainActor
    func testStopDuringCreationWaitsForAndClosesTheLateResult() async {
        let owner = RpcPhoneRunOwner<SyntheticRuntime>()
        let runtime = SyntheticRuntime()
        let creation = Held<SyntheticRuntime>()
        let closure = Held<Void>()
        let entered = expectation(description: "factory entered")
        let closeEntered = expectation(description: "native close entered")
        let start = Task { @MainActor in
            await owner.start(create: { entered.fulfill(); return try await creation.wait() }, close: { value in
                value.closes += 1
                closeEntered.fulfill()
                try await closure.wait()
            })
        }
        defer { creation.resolve(.success(runtime)); closure.resolve(.success(())) }
        await fulfillment(of: [entered], timeout: 2)
        owner.invalidate()
        let stop = Task { @MainActor in await owner.stop() }
        XCTAssertNil(owner.runtime)
        XCTAssertTrue(owner.hasOwner)
        creation.resolve(.success(runtime))
        await fulfillment(of: [closeEntered], timeout: 2)
        let result = await start.value
        guard case .superseded = result else { return XCTFail("Late resource was published") }
        XCTAssertEqual(owner.phase, .stopping)
        XCTAssertFalse(owner.accepts(runtime))
        XCTAssertTrue(owner.hasOwner, "Close has not returned")
        closure.resolve(.success(()))
        let stopped = await stop.value
        XCTAssertTrue(stopped)
        XCTAssertEqual(runtime.closes, 1)
        XCTAssertFalse(owner.hasOwner)
    }

    @MainActor
    func testCreationFailureAfterInvalidationDoesNotPublishOrRequireANonexistentClose() async {
        let owner = RpcPhoneRunOwner<SyntheticRuntime>()
        let creation = Held<SyntheticRuntime>()
        let entered = expectation(description: "factory entered")
        let start = Task { @MainActor in
            await owner.start(create: { entered.fulfill(); return try await creation.wait() },
                              close: { _ in XCTFail("No runtime was acquired") })
        }
        defer { creation.resolve(.failure(SyntheticFailure.operation)) }
        await fulfillment(of: [entered], timeout: 2)
        owner.invalidate()
        let stop = Task { @MainActor in await owner.stop() }
        creation.resolve(.failure(SyntheticFailure.operation))
        let result = await start.value
        guard case .superseded = result else { return XCTFail("Retired failure was published") }
        let stopped = await stop.value
        XCTAssertTrue(stopped)
        XCTAssertEqual(owner.phase, .idle)
    }

    @MainActor
    func testFailedCloseRetainsOwnershipAndRejectsReplacementUntilRetrySucceeds() async {
        let owner = RpcPhoneRunOwner<SyntheticRuntime>()
        let runtime = SyntheticRuntime()
        _ = await owner.start(create: { runtime }, close: { value in
            value.closes += 1
            if value.closes == 1 { throw SyntheticFailure.operation }
        })
        let first = await owner.stop()
        XCTAssertFalse(first)
        XCTAssertEqual(owner.phase, .cleanupPending)
        XCTAssertTrue(owner.hasOwner)
        XCTAssertNil(owner.runtime)
        let refused = await owner.start(create: { XCTFail("Failed owner discarded"); return runtime }, close: { _ in })
        guard case .refused = refused else { return XCTFail("Replacement admitted") }
        let second = await owner.stop()
        XCTAssertTrue(second)
        XCTAssertEqual(runtime.closes, 2)
        XCTAssertFalse(owner.hasOwner)
    }

    @MainActor
    func testConcurrentStopCallersJoinOneRealCleanupBarrier() async {
        let owner = RpcPhoneRunOwner<SyntheticRuntime>()
        let runtime = SyntheticRuntime()
        let closure = Held<Void>()
        let entered = expectation(description: "close entered")
        _ = await owner.start(create: { runtime }, close: { value in
            value.closes += 1
            entered.fulfill()
            try await closure.wait()
        })
        defer { closure.resolve(.success(())) }
        let first = Task { @MainActor in await owner.stop() }
        await fulfillment(of: [entered], timeout: 2)
        let secondEntered = expectation(description: "second stop scheduled")
        let second = Task { @MainActor in secondEntered.fulfill(); return await owner.stop() }
        await fulfillment(of: [secondEntered], timeout: 2)
        XCTAssertEqual(runtime.closes, 1)
        XCTAssertTrue(owner.hasOwner)
        closure.resolve(.success(()))
        let results = await (first.value, second.value)
        XCTAssertTrue(results.0 && results.1)
        XCTAssertEqual(runtime.closes, 1)
    }

    @MainActor
    func testCancellingSwiftStartupCallerStillClosesItsLateNativeResult() async {
        let owner = RpcPhoneRunOwner<SyntheticRuntime>()
        let runtime = SyntheticRuntime()
        let creation = Held<SyntheticRuntime>()
        let entered = expectation(description: "factory entered")
        let start = Task { @MainActor in
            await owner.start(create: { entered.fulfill(); return try await creation.wait() },
                              close: { $0.closes += 1 })
        }
        defer { creation.resolve(.success(runtime)) }
        await fulfillment(of: [entered], timeout: 2)
        start.cancel()
        creation.resolve(.success(runtime))
        let result = await start.value
        guard case .superseded = result else { return XCTFail("Cancelled startup published a runtime") }
        XCTAssertEqual(runtime.closes, 1)
        XCTAssertEqual(owner.phase, .idle)
        XCTAssertFalse(owner.hasOwner)
    }
}
