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
            await lifecycle.abandonUnbuilt(run)
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
    func testUnbuiltCreateFailureWaitsForOwnedDiagnosticsBeforeAllowingAnotherRun() async throws {
        let lifecycle = SampleRunLifecycle()
        let run = try XCTUnwrap(lifecycle.begin())
        var releases = 0
        var deliveries = 0
        run.ownTracing { releases += 1 }
        let (collection, job) = makeControlledOwnedCollection(String.self, completesOnCancel: false) { _ in
            if lifecycle.ownsTracing(run) { deliveries += 1 }
        }
        lifecycle.ownCollection(collection, role: .diagnostics, run: run)
        defer { collection.cancel(); job.complete(.cancelled) }
        let acknowledged = expectation(description: "diagnostics admitted before create failure")
        job.emit("startup") { error in
            XCTAssertNil(error)
            acknowledged.fulfill()
        }
        guard await waitForOwnedExpectations([acknowledged]) else { return }
        XCTAssertEqual(deliveries, 1)
        let cancelling = expectation(description: "unbuilt cleanup requested native cancellation")
        job.whenCancelling { cancelling.fulfill() }
        let finished = expectation(description: "awaited unbuilt cleanup completed")
        let abandoning = Task { @MainActor in
            await lifecycle.abandonUnbuilt(run)
            finished.fulfill()
        }
        defer { abandoning.cancel() }
        guard await waitForOwnedExpectations([cancelling]) else { return }
        XCTAssertEqual(lifecycle.phase, .stopping)
        XCTAssertTrue(lifecycle.owns(run))
        XCTAssertNil(lifecycle.begin())
        XCTAssertEqual(releases, 1)
        XCTAssertEqual(run.ownedCollectionCount, 1)
        XCTAssertFalse(collection.snapshot.nativeCompleted)
        XCTAssertFalse(collection.snapshot.finished)
        job.complete(.cancelled)
        guard await waitForOwnedExpectations([finished]) else { return }
        XCTAssertEqual(run.ownedCollectionCount, 0)
        XCTAssertTrue(collection.snapshot.finished)
        XCTAssertEqual(collection.snapshot.callbackTaskCount, 0)
        XCTAssertEqual(lifecycle.phase, .idle)
        let replacement = try XCTUnwrap(lifecycle.begin())
        XCTAssertFalse(lifecycle.ownsTracing(run))
        await stopSuccessfully(lifecycle, replacement)
    }

    @MainActor
    func testRemovedSessionRetireesAndLateCompletionCannotEraseReplacementLeases() async throws {
        let lifecycle = SampleRunLifecycle()
        let run = try XCTUnwrap(lifecycle.begin())
        let messages = SampleRunLifecycle.Run.CollectionRole.messages(sessionId: "same-session")
        let offers = SampleRunLifecycle.Run.CollectionRole.pendingOffers(sessionId: "same-session")
        var publications: [String] = []
        let oldMessages = makeControlledOwnedCollection(String.self, completesOnCancel: false) {
            publications.append($0)
        }
        let oldOffers = makeControlledOwnedCollection(String.self, completesOnCancel: false) {
            publications.append($0)
        }
        lifecycle.ownCollection(oldMessages.collection, role: messages, run: run)
        lifecycle.ownCollection(oldOffers.collection, role: offers, run: run)
        defer {
            oldMessages.collection.cancel(); oldMessages.job.complete(.cancelled)
            oldOffers.collection.cancel(); oldOffers.job.complete(.cancelled)
        }
        let messageRetirement = try XCTUnwrap(run.retireCollection(for: messages))
        let offerRetirement = try XCTUnwrap(run.retireCollection(for: offers))
        XCTAssertNil(run.collection(for: messages))
        XCTAssertNil(run.collection(for: offers))
        XCTAssertEqual(run.ownedCollectionCount, 2, "removal must not discard unretired native ownership")
        var staleAcknowledgements = 0
        oldMessages.job.emit("obsolete-message") { error in
            XCTAssertNil(error)
            staleAcknowledgements += 1
        }
        oldOffers.job.emit("obsolete-offers") { error in
            XCTAssertNil(error)
            staleAcknowledgements += 1
        }
        XCTAssertEqual(staleAcknowledgements, 2)
        XCTAssertTrue(publications.isEmpty, "lease gating is required even though this Run is still active")

        let nextMessages = makeControlledOwnedCollection(String.self) { publications.append($0) }
        let nextOffers = makeControlledOwnedCollection(String.self, completesOnCancel: false) {
            publications.append($0)
        }
        lifecycle.ownCollection(nextMessages.collection, role: messages, run: run)
        lifecycle.ownCollection(nextOffers.collection, role: offers, run: run)
        defer {
            nextMessages.collection.cancel()
            nextOffers.collection.cancel(); nextOffers.job.complete(.cancelled)
        }
        XCTAssertEqual(run.ownedCollectionCount, 4)
        oldMessages.job.complete(.cancelled)
        oldOffers.job.complete(.cancelled)
        let retired = expectation(description: "removed-session monitors returned")
        let waiting = Task { @MainActor in
            assertOwnedCancelled(await messageRetirement.value)
            assertOwnedCancelled(await offerRetirement.value)
            retired.fulfill()
        }
        defer { waiting.cancel() }
        guard await waitForOwnedExpectations([retired]) else { return }
        XCTAssertTrue(run.collection(for: messages) === nextMessages.collection)
        XCTAssertTrue(run.collection(for: offers) === nextOffers.collection)
        XCTAssertEqual(run.ownedCollectionCount, 2)
        let delivered = expectation(description: "replacement delivery acknowledged")
        nextMessages.job.emit("replacement") { error in
            XCTAssertNil(error)
            delivered.fulfill()
        }
        guard await waitForOwnedExpectations([delivered]) else { return }
        XCTAssertEqual(publications, ["replacement"])
        // Remove one replacement while its real-lease native barrier is held.
        // Stop must include that retiree even though its active role is absent.
        run.retireCollection(for: offers)
        let stopEntered = expectation(description: "Stop reached SDK operation with a removed-session retiree")
        let stopFinished = expectation(description: "Stop includes removed-session native retirement")
        let stopping = Task { @MainActor in
            await lifecycle.stop(
                run, cancelObservers: {}, operation: { stopEntered.fulfill() }, succeeded: {},
                failed: { _ in XCTFail("inert SDK cleanup should succeed") }
            )
            stopFinished.fulfill()
        }
        defer { stopping.cancel() }
        guard await waitForOwnedExpectations([stopEntered]) else { return }
        XCTAssertNil(run.collection(for: offers))
        XCTAssertFalse(nextOffers.collection.snapshot.nativeCompleted)
        XCTAssertEqual(lifecycle.phase, .stopping)
        XCTAssertNil(lifecycle.begin())
        nextOffers.job.complete(.cancelled)
        guard await waitForOwnedExpectations([stopFinished]) else { return }
        XCTAssertEqual(run.ownedCollectionCount, 0)
        XCTAssertTrue(nextOffers.collection.snapshot.finished)
    }

    @MainActor
    func testStopDrainsAllFourOwnedRolesAfterSdkCleanupAndPreservesObserverFailure() async throws {
        let lifecycle = SampleRunLifecycle()
        let run = try XCTUnwrap(lifecycle.begin())
        let roles: [SampleRunLifecycle.Run.CollectionRole] = [
            .diagnostics, .incomingSessions, .messages(sessionId: "session"), .pendingOffers(sessionId: "session")
        ]
        var fixtures: [(OwnedFlowCollection, ControlledOwnedFlowJob)] = []
        var reportedRoles: [SampleRunLifecycle.Run.CollectionRole] = []
        for role in roles {
            let fixture = makeControlledOwnedCollection(String.self, completesOnCancel: false)
            fixtures.append(fixture)
            lifecycle.ownCollection(fixture.collection, role: role, run: run) { failure in
                reportedRoles.append(failure.role)
            }
        }
        defer { fixtures.forEach { $0.0.cancel(); $0.1.complete(.cancelled) } }
        XCTAssertEqual(fixtures.map { $0.1.snapshot.startCalls }, [1, 1, 1, 1])
        let sdk = HeldRunOperation<Void>()
        let sdkEntered = expectation(description: "SDK cleanup starts before native observer drain")
        let tracingCancelled = expectation(description: "tracing cancellation after SDK cleanup attempt")
        fixtures[0].1.whenCancelling { tracingCancelled.fulfill() }
        var releases = 0
        var successes = 0
        run.ownTracing { releases += 1 }
        let finished = expectation(description: "SDK plus all four role leases retired")
        let stopping = Task { @MainActor in
            await lifecycle.stop(
                run,
                cancelObservers: { XCTAssertFalse(lifecycle.acceptsWork(run)) },
                operation: {
                    sdkEntered.fulfill()
                    try await sdk.wait()
                },
                succeeded: { successes += 1 },
                failed: { _ in XCTFail("a drained observer failure is not an SDK Stop failure") }
            )
            finished.fulfill()
        }
        defer { sdk.resolve(.success(())); stopping.cancel() }
        guard await waitForOwnedExpectations([sdkEntered]) else { return }
        XCTAssertEqual(fixtures[0].1.snapshot.cancelCalls, 0, "keep diagnostics through SDK cleanup")
        XCTAssertTrue(fixtures.dropFirst().allSatisfy { $0.1.snapshot.cancelCalls > 0 })
        XCTAssertEqual(releases, 0)
        XCTAssertNil(lifecycle.begin())
        fixtures[1].1.complete(.cancelled)
        fixtures[2].1.complete(.failed(ControlledOwnedFailure.source))
        fixtures[3].1.complete(.cancelled)
        sdk.resolve(.success(()))
        guard await waitForOwnedExpectations([tracingCancelled]) else { return }
        XCTAssertEqual(releases, 1)
        XCTAssertEqual(lifecycle.phase, .stopping)
        XCTAssertEqual(successes, 0)
        fixtures[0].1.complete(.cancelled)
        guard await waitForOwnedExpectations([finished]) else { return }
        XCTAssertEqual(reportedRoles, [.messages(sessionId: "session")])
        XCTAssertEqual(run.firstCollectionFailure?.error as? ControlledOwnedFailure, .source)
        XCTAssertEqual(run.collectionFailureCount, 1)
        XCTAssertEqual(run.ownedCollectionCount, 0)
        XCTAssertTrue(fixtures.allSatisfy { $0.0.snapshot.finished && $0.0.snapshot.callbackTaskCount == 0 })
        XCTAssertEqual(successes, 1)
        XCTAssertEqual(lifecycle.phase, .idle)
    }

    @MainActor
    func testFailedSdkStopDrainsObserversThenRetriesRealCleanupWithoutRecreatingThem() async throws {
        let lifecycle = SampleRunLifecycle()
        let run = try XCTUnwrap(lifecycle.begin())
        let diagnostics = makeControlledOwnedCollection(String.self, completesOnCancel: false)
        let incoming = makeControlledOwnedCollection(String.self, completesOnCancel: false)
        lifecycle.ownCollection(diagnostics.collection, role: .diagnostics, run: run)
        lifecycle.ownCollection(incoming.collection, role: .incomingSessions, run: run)
        defer {
            diagnostics.collection.cancel(); diagnostics.job.complete(.cancelled)
            incoming.collection.cancel(); incoming.job.complete(.cancelled)
        }
        var attempts = 0
        var failureReports = 0
        var releases = 0
        run.ownTracing { releases += 1 }
        let cancelling = expectation(description: "failed SDK cleanup still cancels diagnostics")
        diagnostics.job.whenCancelling { cancelling.fulfill() }
        let finished = expectation(description: "failed SDK cleanup independently drains observers")
        let stopping = Task { @MainActor in
            await lifecycle.stop(
                run, cancelObservers: {},
                operation: { attempts += 1; throw SyntheticRunFailure.operation },
                succeeded: { XCTFail("SDK failure cannot discard its owner") },
                failed: { _ in failureReports += 1 }
            )
            finished.fulfill()
        }
        defer { stopping.cancel() }
        guard await waitForOwnedExpectations([cancelling]) else { return }
        XCTAssertEqual(attempts, 1)
        XCTAssertEqual(failureReports, 0, "cleanup phase still owns unretired observers")
        XCTAssertEqual(lifecycle.phase, .stopping)
        XCTAssertNil(lifecycle.begin())
        incoming.job.complete(.cancelled)
        diagnostics.job.complete(.cancelled)
        guard await waitForOwnedExpectations([finished]) else { return }
        XCTAssertEqual(failureReports, 1)
        XCTAssertEqual(lifecycle.phase, .cleanupPending)
        XCTAssertTrue(lifecycle.owns(run))
        XCTAssertEqual(run.ownedCollectionCount, 0)
        XCTAssertTrue(diagnostics.collection.snapshot.finished)
        XCTAssertTrue(incoming.collection.snapshot.finished)
        XCTAssertEqual(releases, 1)
        await lifecycle.stop(
            run, cancelObservers: {},
            operation: {
                XCTAssertEqual(run.ownedCollectionCount, 0)
                attempts += 1
            },
            succeeded: {},
            failed: { _ in XCTFail("second real SDK cleanup should succeed") }
        )
        XCTAssertEqual(attempts, 2)
        XCTAssertEqual(diagnostics.job.snapshot.startCalls, 1)
        XCTAssertEqual(incoming.job.snapshot.startCalls, 1)
        XCTAssertEqual(releases, 1)
        XCTAssertEqual(lifecycle.phase, .idle)
    }

    @MainActor
    func testCallerCancellationCannotPublishIdleBeforeOwnedNativeRetirement() async throws {
        let lifecycle = SampleRunLifecycle()
        let run = try XCTUnwrap(lifecycle.begin())
        let (collection, job) = makeControlledOwnedCollection(String.self, completesOnCancel: false)
        lifecycle.ownCollection(collection, role: .incomingSessions, run: run)
        defer { collection.cancel(); job.complete(.cancelled) }
        let entered = expectation(description: "cancelled caller still attempts real SDK Stop")
        let finished = expectation(description: "cancelled caller waits for real observer retirement")
        var attempts = 0
        var successes = 0
        let stopping = Task { @MainActor in
            await lifecycle.stop(
                run, cancelObservers: {},
                operation: {
                    XCTAssertTrue(Task.isCancelled)
                    attempts += 1
                    entered.fulfill()
                },
                succeeded: { successes += 1 },
                failed: { _ in XCTFail("inert SDK operation should succeed") }
            )
            finished.fulfill()
        }
        stopping.cancel()
        defer { stopping.cancel() }
        guard await waitForOwnedExpectations([entered]) else { return }
        XCTAssertEqual(attempts, 1)
        XCTAssertEqual(successes, 0)
        XCTAssertEqual(lifecycle.phase, .stopping)
        XCTAssertNil(lifecycle.begin())
        XCTAssertFalse(collection.snapshot.nativeCompleted)
        job.complete(.cancelled)
        guard await waitForOwnedExpectations([finished]) else { return }
        XCTAssertEqual(successes, 1)
        XCTAssertEqual(run.ownedCollectionCount, 0)
        XCTAssertTrue(collection.snapshot.finished)
        XCTAssertEqual(lifecycle.phase, .idle)
    }

    @MainActor
    func testStopSkipsQueuedOwnedCallbackAndPublishesSuccessOnlyAfterItsAcknowledgement() async throws {
        let lifecycle = SampleRunLifecycle()
        let run = try XCTUnwrap(lifecycle.begin())
        var publications: [String] = []
        let (collection, job) = makeControlledOwnedCollection(String.self) { publications.append($0) }
        lifecycle.ownCollection(collection, role: .messages(sessionId: "session"), run: run)
        defer { collection.cancel(); job.complete(.cancelled) }
        var acknowledgements = 0
        let finished = expectation(description: "Stop waited for the already-admitted callback")
        let stopping = Task { @MainActor in
            await lifecycle.stop(
                run,
                cancelObservers: {
                    XCTAssertFalse(lifecycle.acceptsWork(run), "invalidate before snapshot")
                    // Synchronous snapshot seam: enqueue against the real lease
                    // just before native cancellation, with no actor yield.
                    job.emit("old") { error in
                        XCTAssertNil(error)
                        acknowledgements += 1
                    }
                    XCTAssertTrue(collection.snapshot.hasUnacknowledgedDelivery)
                    XCTAssertEqual(acknowledgements, 0)
                },
                operation: {},
                succeeded: {
                    XCTAssertTrue(collection.snapshot.nativeCompleted)
                    XCTAssertTrue(collection.snapshot.finished)
                    XCTAssertEqual(collection.snapshot.callbackTaskCount, 0)
                    XCTAssertEqual(acknowledgements, 1)
                    XCTAssertTrue(publications.isEmpty)
                },
                failed: { _ in XCTFail("inert SDK cleanup should succeed") }
            )
            finished.fulfill()
        }
        defer { stopping.cancel() }
        guard await waitForOwnedExpectations([finished]) else { return }
        let replacement = try XCTUnwrap(lifecycle.begin())
        let next = makeControlledOwnedCollection(String.self) { value in
            lifecycle.withActiveRun(replacement) { publications.append(value) }
        }
        lifecycle.ownCollection(next.collection, role: .messages(sessionId: "session"), run: replacement)
        defer { next.collection.cancel() }
        let delivered = expectation(description: "replacement owned callback delivered")
        next.job.emit("new") { error in
            XCTAssertNil(error)
            delivered.fulfill()
        }
        guard await waitForOwnedExpectations([delivered]) else { return }
        XCTAssertEqual(publications, ["new"])
        await stopSuccessfully(lifecycle, replacement)
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
