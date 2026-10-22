import CryptoKit
import Foundation
import XCTest
@testable import P2pKitSample

final class SampleFilePreparationTests: XCTestCase {
    func testPresetKeepsExactBytesAndDigestAcrossChunkBoundaries() throws {
        for count in [0, 1, 65535, 65536, 65537, 200 * 1024] {
            let snapshot = try SampleFilePreparation.preset(byteCount: count)
            let expected = Data((0..<count).map { UInt8(truncatingIfNeeded: $0 &* 31 &+ 7) })
            XCTAssertEqual(snapshot.data, expected)
            XCTAssertEqual(snapshot.digest, Array(SHA256.hash(data: expected)))
        }
    }

    func testGenerationAndReadbackCheckCancellationBetweenChunks() throws {
        let url = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        defer { try? FileManager.default.removeItem(at: url) }
        let snapshot = try SampleFilePreparation.preset(byteCount: 200 * 1024)
        try snapshot.data.write(to: url)
        XCTAssertEqual(try SampleFilePreparation.sha256File(at: url), snapshot.sha256Hex)
        for failAt in [1, 2, 3, 4, 5] {
            var generationChecks = 0
            XCTAssertThrowsError(try SampleFilePreparation.preset(byteCount: 49 * 1024 * 1024) {
                generationChecks += 1
                if generationChecks == failAt { throw CancellationError() }
            }) { XCTAssertTrue($0 is CancellationError) }
            XCTAssertEqual(generationChecks, failAt)
            var readChecks = 0
            XCTAssertThrowsError(try SampleFilePreparation.sha256File(at: url) {
                readChecks += 1
                if readChecks == failAt { throw CancellationError() }
            }) { XCTAssertTrue($0 is CancellationError) }
            XCTAssertEqual(readChecks, failAt)
        }
        // A cancelled read closes its handle; the next full read still works.
        XCTAssertEqual(try SampleFilePreparation.sha256File(at: url), snapshot.sha256Hex)
        XCTAssertThrowsError(try SampleFilePreparation.sha256File(
            at: url.appendingPathComponent("missing")
        ))
    }

    @MainActor
    func testFullBoundaryPresetRunsOffMainAndKeepsIntegrity() async throws {
        let lifecycle = SampleRunLifecycle()
        let run = try XCTUnwrap(lifecycle.begin())
        let valid = try await lifecycle.prepare(run) {
            XCTAssertFalse(Thread.isMainThread)
            let snapshot = try SampleFilePreparation.preset(byteCount: 49 * 1024 * 1024)
            return snapshot.data.count == 49 * 1024 * 1024 &&
                snapshot.digest == Array(SHA256.hash(data: snapshot.data)) &&
                snapshot.data.enumerated().allSatisfy {
                    $0.element == UInt8(truncatingIfNeeded: $0.offset &* 31 &+ 7)
                }
        }
        XCTAssertTrue(valid)
        await stop(lifecycle, run)
    }

    @MainActor
    func testStopSchedulesDuringLargePreparationAndJoinsBeforeAllowingReplacement() async throws {
        let lifecycle = SampleRunLifecycle()
        let run = try XCTUnwrap(lifecycle.begin())
        let entered = expectation(description: "worker generated first chunk off-main")
        let stopping = expectation(description: "main actor ran Stop while worker held")
        let gate = PreparationGate()
        var publications = 0
        let action = Task { @MainActor in
            do {
                _ = try await lifecycle.prepare(run) {
                    XCTAssertFalse(Thread.isMainThread)
                    var checkpoints = 0
                    return try SampleFilePreparation.preset(byteCount: 49 * 1024 * 1024) {
                        checkpoints += 1
                        if checkpoints == 3 {
                            entered.fulfill()
                            try gate.wait()
                        }
                        try Task.checkCancellation()
                    }
                }
                publications += 1 // actual downstream diagnostic/send boundary
                XCTFail("retired preparation must not reach sendFile")
            } catch { XCTAssertTrue(error is CancellationError) }
        }
        defer { gate.release(); action.cancel() }
        await require([entered])
        let stopTask = Task { @MainActor in
            await lifecycle.stop(
                run, cancelObservers: {}, operation: { stopping.fulfill() },
                succeeded: {}, failed: { _ in XCTFail("inert SDK Stop failed") }
            )
        }
        defer { stopTask.cancel() }
        await require([stopping])
        XCTAssertEqual(lifecycle.phase, .stopping)
        XCTAssertNil(lifecycle.begin(), "Stop must retain its worker before releasing ownership")
        gate.release()
        await action.value
        await stopTask.value
        XCTAssertEqual(publications, 0)
        XCTAssertEqual(lifecycle.phase, .idle)
        let replacement = try XCTUnwrap(lifecycle.begin())
        await stop(lifecycle, replacement)
    }

    @MainActor
    func testLateSuccessfulWorkerAndCallerCancellationCannotPublish() async throws {
        for cancelCaller in [false, true] {
            let lifecycle = SampleRunLifecycle()
            let run = try XCTUnwrap(lifecycle.begin())
            let entered = expectation(description: "held worker entered")
            let gate = PreparationGate()
            var publications = 0
            let action = Task { @MainActor in
                do {
                    _ = try await lifecycle.prepare(run) {
                        entered.fulfill()
                        try gate.wait()
                        return 7 // deliberately ignores cancellation: fence still required
                    }
                    publications += 1
                } catch { XCTAssertTrue(error is CancellationError) }
            }
            defer { gate.release(); action.cancel() }
            await require([entered])
            if cancelCaller {
                action.cancel()
                gate.release()
                await action.value
                await stop(lifecycle, run)
            } else {
                await lifecycle.stop(
                    run, cancelObservers: {}, operation: { gate.release() },
                    succeeded: {}, failed: { _ in XCTFail("inert SDK Stop failed") }
                )
                await action.value
            }
            XCTAssertEqual(publications, 0)
        }
    }

    @MainActor
    private func require(_ expectations: [XCTestExpectation]) async {
        let result = await XCTWaiter.fulfillment(of: expectations, timeout: 2)
        XCTAssertEqual(result, .completed)
    }

    @MainActor
    private func stop(_ lifecycle: SampleRunLifecycle, _ run: SampleRunLifecycle.Run) async {
        await lifecycle.stop(run, cancelObservers: {}, operation: {}, succeeded: {}, failed: {
            _ in XCTFail("inert SDK Stop failed")
        })
    }
}

/// Only a test worker blocks; MainActor always remains free. Finite even if an
/// assertion fails, and every caller releases in defer before leaving its scope.
private final class PreparationGate: @unchecked Sendable {
    private let condition = NSCondition()
    private var released = false

    func wait() throws {
        condition.lock()
        defer { condition.unlock() }
        let deadline = Date().addingTimeInterval(2)
        while !released {
            guard condition.wait(until: deadline) else {
                throw NSError(domain: "synthetic-preparation-gate-timeout", code: 1)
            }
        }
    }

    func release() {
        condition.lock()
        released = true
        condition.broadcast()
        condition.unlock()
    }
}
