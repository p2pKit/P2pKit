import Foundation
import P2pKitShared
import XCTest
@testable import P2pKitSample

/// Run ALONE and last in the owned cancellation lane. This is the positive
/// production-adapter case, not a relabeling of the retained raw-export probe.
final class SwiftOwnedFlowCancellationTests: XCTestCase {
    @MainActor
    func testOwnedAdapterCancellationFinishesActualDiagnosticCollection() async {
        let diagnostics = IosLanDebug.shared
        let previousMirror = diagnostics.mirrorToConsole
        let previousHistory = diagnostics.retainHistory
        diagnostics.mirrorToConsole = false
        diagnostics.retainHistory = true
        let observation = OwnedFlowProbeObservation()
        let first = OwnedFlowCollection(flow: diagnostics.events, of: String.self) { line in
            observation.receiveOriginal(line)
        }
        var replacement: OwnedFlowCollection?
        defer {
            first.cancel()
            replacement?.cancel()
            diagnostics.mirrorToConsole = previousMirror
            diagnostics.retainHistory = previousHistory
            let report = observation.report
            print(report)
            let attachment = XCTAttachment(string: report)
            attachment.name = "swift-owned-flow-cancellation-observation"
            attachment.lifetime = .keepAlways
            add(attachment)
            // Never use an unbounded await or a rescue emission on failure.
            // The outer owner retains the failed result and retires this host.
        }

        diagnostics.log(tag: observation.tag, message: observation.readyMarker)
        first.start()
        let ready = await XCTWaiter.fulfillment(of: [observation.ready], timeout: 2)
        guard ready == .completed, !first.snapshot.nativeCompleted else {
            observation.outcome = "NOT_ADMITTED_NO_LIVE_OWNED_SUBSCRIPTION"
            XCTFail("a real diagnostic subscription must be live before any cancellation inference")
            return
        }
        diagnostics.log(tag: observation.tag, message: observation.liveMarker)
        let live = await XCTWaiter.fulfillment(of: [observation.live], timeout: 2)
        guard live == .completed, !first.snapshot.nativeCompleted else {
            observation.outcome = "NOT_ADMITTED_NO_NORMAL_LIVE_DELIVERY"
            XCTFail("the production owned bridge must deliver normally before cancellation")
            return
        }
        XCTAssertFalse(first.snapshot.hasUnacknowledgedDelivery)

        // No log/emission between cancel and the combined native+callback
        // barrier. Both observations must fit this ONE original two-second window.
        let firstRetired = await observation.originalRetirement.cancelAndObserve(first)
        guard firstRetired else {
            observation.outcome = "OWNED_NATIVE_OR_CALLBACK_RETIREMENT_NOT_OBSERVED_WITHIN_2S"
            XCTFail("idle cancellation must retire the actual native Job AND accepted callback task within 2s")
            return
        }
        let originalDeliveriesAfterRetirement = observation.originalDeliveries
        let next = OwnedFlowCollection(flow: diagnostics.events, of: String.self) { line in
            observation.receiveReplacement(line)
        }
        replacement = next
        diagnostics.log(tag: observation.tag, message: observation.replacementReadyMarker)
        next.start()
        let replacementReady = await XCTWaiter.fulfillment(of: [observation.replacementReady], timeout: 2)
        guard replacementReady == .completed, !next.snapshot.nativeCompleted else {
            observation.outcome = "OLD_RETIRED_REPLACEMENT_NOT_ADMITTED"
            XCTFail("a replacement subscriber must be demonstrably live after old retirement")
            return
        }
        diagnostics.log(tag: observation.tag, message: observation.postTerminalMarker)
        let postTerminal = await XCTWaiter.fulfillment(of: [observation.replacementMarker], timeout: 2)
        guard postTerminal == .completed else {
            observation.outcome = "OLD_RETIRED_NO_LIVE_REPLACEMENT_MARKER_CONTROL"
            XCTFail("the post-terminal diagnostic marker must reach the live replacement")
            return
        }
        XCTAssertEqual(observation.originalDeliveries, originalDeliveriesAfterRetirement)
        XCTAssertFalse(observation.originalSawPostTerminal)
        XCTAssertTrue(first.snapshot.nativeCompleted)
        XCTAssertTrue(first.snapshot.finished)
        XCTAssertEqual(first.snapshot.callbackTaskCount, 0)
        guard observation.originalDeliveries == originalDeliveriesAfterRetirement,
              !observation.originalSawPostTerminal else {
            observation.outcome = "RETIRED_SUBSCRIPTION_DELIVERED_AGAIN"
            return
        }
        guard await observation.replacementRetirement.cancelAndObserve(next) else {
            observation.outcome = "REPLACEMENT_CLEANUP_NOT_OBSERVED_WITHIN_2S"
            XCTFail("the replacement control must also retire without an emission or host-exit shortcut")
            return
        }
        observation.outcome = "OWNED_NATIVE_JOB_AND_CALLBACK_TASK_RETIRED_WITH_LIVE_REPLACEMENT_CONTROL"
    }
}

@MainActor
private final class OwnedFlowProbeRetirement {
    private let finished = XCTestExpectation(description: "actual native terminal and callback task drain")
    private(set) var nativeCompleted = false
    private(set) var callbacksDrained = false
    private(set) var cancelledCompletion = false
    private(set) var elapsed: TimeInterval?
    private(set) var waiterResult = "NOT_WAITED"

    func cancelAndObserve(_ collection: OwnedFlowCollection) async -> Bool {
        let requestedAt = ProcessInfo.processInfo.systemUptime
        collection.cancel()
        let waiting = Task { @MainActor in
            let completion = await collection.finish()
            let snapshot = collection.snapshot
            self.nativeCompleted = snapshot.nativeCompleted
            self.callbacksDrained = snapshot.finished && !snapshot.hasUnacknowledgedDelivery &&
                snapshot.callbackTaskCount == 0
            if case .cancelled = completion { self.cancelledCompletion = true }
            self.elapsed = ProcessInfo.processInfo.systemUptime - requestedAt
            self.finished.fulfill()
        }
        defer { waiting.cancel() }
        let remaining = max(0, 2 - (ProcessInfo.processInfo.systemUptime - requestedAt))
        let result = await XCTWaiter.fulfillment(of: [finished], timeout: remaining)
        waiterResult = String(result.rawValue)
        guard result == .completed, let elapsed else { return false }
        return elapsed <= 2 && nativeCompleted && callbacksDrained && cancelledCompletion
    }

    var report: String {
        "nativeTerminal=\(nativeCompleted) callbacksDrained=\(callbacksDrained) " +
            "nativeCancelledCompletion=\(cancelledCompletion) waiter=\(waiterResult) " +
            "cancelToCombinedRetirementSeconds=\(elapsed.map { String($0) } ?? "NOT_OBSERVED")"
    }
}

@MainActor
private final class OwnedFlowProbeObservation {
    let tag = "swift-owned-flow-probe"
    private let token = UUID().uuidString
    let ready = XCTestExpectation(description: "real owned diagnostic readiness callback")
    let live = XCTestExpectation(description: "normal owned diagnostic live delivery")
    let replacementReady = XCTestExpectation(description: "replacement actual diagnostic readiness callback")
    let replacementMarker = XCTestExpectation(description: "post-terminal marker reached live replacement")
    let originalRetirement = OwnedFlowProbeRetirement()
    let replacementRetirement = OwnedFlowProbeRetirement()
    var readyMarker: String { "synthetic-owned-ready-\(token)" }
    var liveMarker: String { "synthetic-owned-live-\(token)" }
    var replacementReadyMarker: String { "synthetic-owned-replacement-\(token)" }
    var postTerminalMarker: String { "synthetic-owned-post-terminal-\(token)" }
    var outcome = "NOT_FINISHED"
    private(set) var originalDeliveries = 0
    private(set) var originalSawReady = false
    private(set) var originalSawLive = false
    private(set) var originalSawPostTerminal = false
    private(set) var replacementSawReady = false
    private(set) var replacementSawMarker = false

    func receiveOriginal(_ line: String) {
        originalDeliveries += 1
        if matches(line, readyMarker), !originalSawReady {
            originalSawReady = true
            ready.fulfill()
        }
        if matches(line, liveMarker), !originalSawLive {
            originalSawLive = true
            live.fulfill()
        }
        if matches(line, postTerminalMarker) { originalSawPostTerminal = true }
    }

    func receiveReplacement(_ line: String) {
        if matches(line, replacementReadyMarker), !replacementSawReady {
            replacementSawReady = true
            replacementReady.fulfill()
        }
        if matches(line, postTerminalMarker), !replacementSawMarker {
            replacementSawMarker = true
            replacementMarker.fulfill()
        }
    }

    private func matches(_ line: String, _ marker: String) -> Bool {
        line.hasSuffix("[\(tag)] \(marker)")
    }

    var report: String {
        """
        P2PKIT_SWIFT_OWNED_FLOW_CANCELLATION
        outcome=\(outcome)
        originalReady=\(originalSawReady) normalLiveDelivery=\(originalSawLive)
        originalRetirement=\(originalRetirement.report)
        replacementReady=\(replacementSawReady) replacementPostTerminalMarker=\(replacementSawMarker)
        originalPostTerminalMarker=\(originalSawPostTerminal)
        replacementRetirement=\(replacementRetirement.report)
        scope=OWNED_PRODUCTION_ADAPTER_ONLY_RAW_EXPORT_BASELINE_UNCHANGED
        cleanup=OUTER_HOST_RETIREMENT_IS_SEPARATE_AND_NEVER_A_CANCELLATION_PASS
        """
    }
}
