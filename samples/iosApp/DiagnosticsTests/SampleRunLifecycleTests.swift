import XCTest
@testable import P2pKitSample

final class SampleRunLifecycleTests: XCTestCase {
    @MainActor
    func testStopDuringManualInfoRejectsLateSuccessAndFailureBeforeObserverInstallation() async throws {
        for failInfo in [false, true] {
            let lifecycle = SampleRunLifecycle()
            let first = try XCTUnwrap(lifecycle.begin())
            let manualInfo = HeldRunOperation<Int>()
            let stopOperation = HeldRunOperation<Void>()
            let manualEntered = expectation(description: "manual-info entered")
            let stopEntered = expectation(description: "SDK Stop entered")
            var publications = 0
            var installations = 0
            var releases = 0
            first.ownTracing { releases += 1 }
            let startup = Task { @MainActor in
                defer { first.releaseTracing() }
                return await lifecycle.completeStartup(
                    first,
                    advertise: {}, didAdvertise: {},
                    discover: {}, didDiscover: {},
                    manualInfo: {
                        manualEntered.fulfill()
                        return try await manualInfo.wait()
                    },
                    didReadInfo: { _ in publications += 1 },
                    installObservers: { installations += 1 }
                )
            }
            defer {
                manualInfo.resolve(.failure(SyntheticRunFailure.operation))
                stopOperation.resolve(.success(()))
                startup.cancel()
            }
            await waitFor([manualEntered])
            let stopping = Task { @MainActor in
                await lifecycle.stop(
                    first,
                    cancelObservers: {
                        // This is the same ordering used by ContentView.stop.
                        XCTAssertFalse(lifecycle.acceptsWork(first))
                        XCTAssertEqual(installations, 0)
                    },
                    operation: {
                        stopEntered.fulfill()
                        try await stopOperation.wait()
                    },
                    succeeded: {},
                    failed: { _ in XCTFail("inert Stop should succeed") }
                )
            }
            defer { stopping.cancel() }
            await waitFor([stopEntered])
            manualInfo.resolve(failInfo ? .failure(SyntheticRunFailure.operation) : .success(24680))
            let outcome = await startup.value
            assertSuperseded(outcome)
            XCTAssertEqual(publications, 0)
            XCTAssertEqual(installations, 0)
            XCTAssertNil(lifecycle.begin(), "a stopping owner must still exclude Start")
            stopOperation.resolve(.success(()))
            await stopping.value
            XCTAssertEqual(releases, 1)
            XCTAssertEqual(lifecycle.phase, .idle)

            let second = try XCTUnwrap(lifecycle.begin())
            XCTAssertFalse(lifecycle.withActiveRun(first) { installations += 1 })
            XCTAssertTrue(lifecycle.withActiveRun(second) { installations += 1 })
            XCTAssertEqual(installations, 1)
            await stopSuccessfully(lifecycle, second)
        }
    }

    @MainActor
    func testOldStartupFailureAndTracingReleaseCannotClearOrReleaseReplacement() async throws {
        let lifecycle = SampleRunLifecycle()
        let first = try XCTUnwrap(lifecycle.begin())
        let advertising = HeldRunOperation<Void>()
        let entered = expectation(description: "advertising entered")
        var firstReleases = 0
        var secondReleases = 0
        var stalePublications = 0
        first.ownTracing { firstReleases += 1 }
        let startup = Task { @MainActor in
            defer { first.releaseTracing() }
            return await lifecycle.completeStartup(
                first,
                advertise: {
                    entered.fulfill()
                    try await advertising.wait()
                },
                didAdvertise: { stalePublications += 1 },
                discover: { XCTFail("retired startup must not call discovery") },
                didDiscover: { stalePublications += 1 },
                manualInfo: { XCTFail("retired startup must not request manual info"); return 0 },
                didReadInfo: { _ in stalePublications += 1 },
                installObservers: { stalePublications += 1 }
            )
        }
        defer {
            advertising.resolve(.failure(SyntheticRunFailure.operation))
            startup.cancel()
        }
        await waitFor([entered])
        await stopSuccessfully(lifecycle, first)
        let second = try XCTUnwrap(lifecycle.begin())
        second.ownTracing { secondReleases += 1 }
        advertising.resolve(.failure(SyntheticRunFailure.operation))
        let outcome = await startup.value
        assertSuperseded(outcome)
        // ContentView uses this gate again after awaiting completeStartup, before
        // publishing a failure. An already-produced failure cannot bypass it.
        XCTAssertFalse(lifecycle.withActiveRun(first) { stalePublications += 1 })
        await lifecycle.stop(
            first,
            cancelObservers: { XCTFail("stale Stop must not cancel B's observers") },
            operation: { XCTFail("A's Stop already completed") },
            succeeded: { stalePublications += 1 },
            failed: { _ in stalePublications += 1 }
        )
        first.releaseTracing()
        XCTAssertEqual(stalePublications, 0)
        XCTAssertTrue(lifecycle.owns(second))
        XCTAssertTrue(lifecycle.ownsTracing(second))
        XCTAssertEqual(firstReleases, 1)
        XCTAssertEqual(secondReleases, 0)
        await stopSuccessfully(lifecycle, second)
        XCTAssertEqual(secondReleases, 1)
    }

    @MainActor
    func testFailedRollbackRetainsOwnerRejectsAdmissionAndRetriesStopOperation() async throws {
        let lifecycle = SampleRunLifecycle()
        let run = try XCTUnwrap(lifecycle.begin())
        var cleanupAttempts = 0
        var releases = 0
        var failureReports = 0
        run.ownTracing { releases += 1 }
        let outcome = await lifecycle.completeStartup(
            run,
            advertise: { throw SyntheticRunFailure.operation },
            didAdvertise: { XCTFail("failed startup must not publish success") },
            discover: { XCTFail("failed startup must not call discovery") },
            didDiscover: {}, manualInfo: { 0 }, didReadInfo: { _ in },
            installObservers: { XCTFail("failed startup must not install observers") }
        )
        guard case .failed = outcome else {
            XCTFail("startup failure must reach the caller's rollback boundary")
            lifecycle.abandonUnbuilt(run)
            return
        }
        await lifecycle.stop(
            run,
            cancelObservers: { XCTAssertFalse(lifecycle.acceptsWork(run)) },
            operation: {
                cleanupAttempts += 1
                throw SyntheticRunFailure.operation
            },
            succeeded: { XCTFail("failed cleanup cannot clear its SDK owner") },
            failed: { _ in failureReports += 1 }
        )
        XCTAssertTrue(lifecycle.owns(run))
        XCTAssertEqual(lifecycle.phase, .cleanupPending)
        XCTAssertNil(lifecycle.begin())
        XCTAssertFalse(lifecycle.withActiveRun(run) { XCTFail("cleanup-pending run cannot admit collectors") })
        XCTAssertNil(lifecycle.launchAction { _ in XCTFail("cleanup-pending run cannot accept UI work") })
        XCTAssertFalse(lifecycle.ownsTracing(run))
        XCTAssertEqual(releases, 1)
        await lifecycle.stop(
            run,
            cancelObservers: {},
            operation: { cleanupAttempts += 1 },
            succeeded: {},
            failed: { _ in XCTFail("retry should succeed") }
        )
        XCTAssertEqual(cleanupAttempts, 2)
        XCTAssertEqual(failureReports, 1)
        XCTAssertEqual(releases, 1)
        XCTAssertNil(lifecycle.current)
    }

    @MainActor
    func testCallerCancellationReachesRollbackInsteadOfAbandoningTheAcquiredKit() async throws {
        let lifecycle = SampleRunLifecycle()
        let run = try XCTUnwrap(lifecycle.begin())
        let advertising = HeldRunOperation<Void>()
        let entered = expectation(description: "startup operation entered")
        var cleanupAttempts = 0
        var cleanupSawCancelledCaller = false
        let startup = Task { @MainActor in
            let outcome = await lifecycle.completeStartup(
                run,
                advertise: {
                    entered.fulfill()
                    try await advertising.wait()
                },
                didAdvertise: { XCTFail("cancelled startup cannot publish success") },
                discover: { XCTFail("cancelled startup cannot start another feature") },
                didDiscover: {}, manualInfo: { 0 }, didReadInfo: { _ in },
                installObservers: { XCTFail("cancelled startup cannot install observers") }
            )
            if case .failed(let error) = outcome {
                XCTAssertTrue(error is CancellationError)
                // This is the same real cleanup boundary used by the caller's
                // failure branch. It deliberately has no cancellation shortcut.
                await lifecycle.stop(
                    run,
                    cancelObservers: {},
                    operation: {
                        cleanupSawCancelledCaller = Task.isCancelled
                        cleanupAttempts += 1
                    },
                    succeeded: {},
                    failed: { _ in XCTFail("inert cleanup should succeed") }
                )
            } else {
                XCTFail("cancellation after acquisition must request rollback")
            }
        }
        defer {
            advertising.resolve(.success(()))
            startup.cancel()
        }
        await waitFor([entered])
        startup.cancel()
        advertising.resolve(.success(()))
        await startup.value
        XCTAssertEqual(cleanupAttempts, 1)
        XCTAssertTrue(cleanupSawCancelledCaller)
        XCTAssertNil(lifecycle.current)
    }

    @MainActor
    func testActualCollectorQueuedCallbackCompletesWithoutPublishingIntoReplacement() async throws {
        let lifecycle = SampleRunLifecycle()
        let first = try XCTUnwrap(lifecycle.begin())
        let callback = HeldRunOperation<Void>()
        let entered = expectation(description: "actual MessageCollector callback entered")
        let completed = expectation(description: "actual collector completion called")
        var values: [String] = []
        let collector = MessageCollector { value in
            entered.fulfill()
            _ = try? await callback.wait()
            await MainActor.run {
                _ = lifecycle.withActiveRun(first) { values.append(value as? String ?? "wrong-type") }
            }
        }
        defer { callback.resolve(.success(())) }
        collector.emit(value: "old-run") { error in
            XCTAssertNil(error)
            completed.fulfill()
        }
        await waitFor([entered])
        await stopSuccessfully(lifecycle, first)
        let second = try XCTUnwrap(lifecycle.begin())
        callback.resolve(.success(()))
        await waitFor([completed])
        XCTAssertTrue(values.isEmpty)
        let nextCompleted = expectation(description: "replacement collector completion called")
        let nextCollector = MessageCollector { value in
            await MainActor.run {
                _ = lifecycle.withActiveRun(second) { values.append(value as? String ?? "wrong-type") }
            }
        }
        nextCollector.emit(value: "new-run") { error in
            XCTAssertNil(error)
            nextCompleted.fulfill()
        }
        await waitFor([nextCompleted])
        XCTAssertEqual(values, ["new-run"])
        await stopSuccessfully(lifecycle, second)
    }

    @MainActor
    func testPermissionDelayRejectsCancellationAndStopEvenWhenTheDelayReturnsLate() async throws {
        let lifecycle = SampleRunLifecycle()
        let first = try XCTUnwrap(lifecycle.begin())
        let delay = HeldRunOperation<Void>()
        let entered = expectation(description: "permission delay entered")
        var hints = 0
        let probe = Task { @MainActor in
            await lifecycle.afterDelay(
                first,
                delay: {
                    entered.fulfill()
                    try await delay.wait()
                },
                perform: { hints += 1 }
            )
        }
        defer { delay.resolve(.success(())); probe.cancel() }
        await waitFor([entered])
        await lifecycle.stop(
            first,
            cancelObservers: { probe.cancel() },
            operation: {}, succeeded: {},
            failed: { _ in XCTFail("inert Stop should succeed") }
        )
        let second = try XCTUnwrap(lifecycle.begin())
        delay.resolve(.success(()))
        await probe.value
        XCTAssertEqual(hints, 0)
        await lifecycle.afterDelay(
            second,
            delay: { throw CancellationError() },
            perform: { hints += 1 }
        )
        XCTAssertEqual(hints, 0)
        await lifecycle.afterDelay(second, delay: {}, perform: { hints += 1 })
        XCTAssertEqual(hints, 1, "an active successful probe must not be disabled")
        await stopSuccessfully(lifecycle, second)
    }

    @MainActor
    private func waitFor(
        _ expectations: [XCTestExpectation], file: StaticString = #filePath, line: UInt = #line
    ) async {
        let result = await XCTWaiter.fulfillment(of: expectations, timeout: 2)
        XCTAssertEqual(result, .completed, file: file, line: line)
    }

    @MainActor
    private func stopSuccessfully(_ lifecycle: SampleRunLifecycle, _ run: SampleRunLifecycle.Run) async {
        await lifecycle.stop(
            run, cancelObservers: {}, operation: {}, succeeded: {},
            failed: { _ in XCTFail("inert Stop should succeed") }
        )
    }

    @MainActor
    private func assertSuperseded(
        _ outcome: SampleRunLifecycle.StartupOutcome, file: StaticString = #filePath, line: UInt = #line
    ) {
        guard case .superseded = outcome else {
            XCTFail("retired startup must not report success or failure to its successor", file: file, line: line)
            return
        }
    }
}

private enum SyntheticRunFailure: Error {
    case operation
}

/// One-shot inert operation. Tests always resolve it, including failed assertions;
/// no native jobs, sockets, filesystem work, sleeps, or project test hooks are used.
@MainActor
private final class HeldRunOperation<Value> {
    private var result: Result<Value, Error>?
    private var continuation: CheckedContinuation<Value, Error>?

    func wait() async throws -> Value {
        if let result { return try result.get() }
        return try await withCheckedThrowingContinuation { continuation in
            precondition(self.continuation == nil, "test operation may only have one waiter")
            self.continuation = continuation
        }
    }

    func resolve(_ result: Result<Value, Error>) {
        guard self.result == nil else { return }
        self.result = result
        let waiter = continuation
        continuation = nil
        waiter?.resume(with: result)
    }
}
