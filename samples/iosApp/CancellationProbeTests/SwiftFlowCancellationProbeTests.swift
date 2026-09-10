import Foundation
import P2pKitShared
import XCTest
@testable import P2pKitSample

/// Private investigation: run this method ALONE in an owned test-host process.
/// A failed cancellation may leave its one collector alive until that process exits.
final class SwiftFlowCancellationProbeTests: XCTestCase {
    @MainActor
    func testSwiftTaskCancellationFinishesActualDiagnosticCollection() async {
        let diagnostics = IosLanDebug.shared
        let previousMirror = diagnostics.mirrorToConsole
        let previousHistory = diagnostics.retainHistory
        let observation = SwiftFlowCancellationObservation()
        diagnostics.mirrorToConsole = false
        diagnostics.retainHistory = true
        diagnostics.log(tag: "swift-flow-probe", message: observation.readyMarker)
        let collector = StringCollector { line in
            await MainActor.run {
                observation.receive(line)
            }
        }
        let collection = Task { @MainActor in
            _ = try? await diagnostics.events.collect(collector: collector)
            observation.collectionReturned(cancelled: Task.isCancelled)
        }
        defer {
            collection.cancel()
            diagnostics.mirrorToConsole = previousMirror
            diagnostics.retainHistory = previousHistory
            let report = observation.report
            print(report)
            let attachment = XCTAttachment(string: report)
            attachment.name = "swift-task-kotlin-flow-cancellation-observation"
            attachment.lifetime = .keepAlways
            add(attachment)
            // Never await collection.value here: that is the behavior under investigation.
            // The outer owner MUST retire this isolated test-host process, even on failure.
        }

        let ready = await XCTWaiter.fulfillment(of: [observation.ready], timeout: 2)
        guard ready == .completed else {
            observation.outcome = "NOT_ADMITTED_NO_READY_CALLBACK"
            XCTFail("Real Flow subscription was not established; no cancellation inference is valid")
            return
        }
        guard !observation.didReturn else {
            observation.outcome = "NOT_ADMITTED_COLLECT_RETURNED_BEFORE_CANCEL"
            XCTFail("Real Flow collection returned before the cancellation observation")
            return
        }
        observation.trace.append("cancel-requested")
        collection.cancel()
        observation.swiftCancelFlag = collection.isCancelled
        observation.trace.append("swift-cancel-flag=\(collection.isCancelled)")
        diagnostics.log(tag: "swift-flow-probe", message: observation.postCancelMarker)
        observation.trace.append("post-cancel-log-returned")

        let finished = await XCTWaiter.fulfillment(of: [observation.finished], timeout: 2)
        observation.trace.append("return-waiter-result=\(finished.rawValue)")
        switch finished {
        case .completed:
            observation.outcome = "EXPORTED_COLLECT_RETURNED_AFTER_CANCEL"
        case .timedOut:
            observation.outcome = observation.sawPostCancel
                ? "POST_CANCEL_CALLBACK_WITH_NO_RETURN_WITHIN_2S"
                : "NO_RETURN_WITHIN_2S_NO_POST_CANCEL_PROGRESS_INCONCLUSIVE"
        default:
            observation.outcome = "RETURN_WAITER_INCONCLUSIVE"
        }
        XCTAssertTrue(collection.isCancelled, "The saved Swift Task must actually be cancelled")
        XCTAssertEqual(
            finished, .completed,
            "Cancellation observation did not complete normally; inspect the retained outcome and waiter result"
        )
    }
}

@MainActor
private final class SwiftFlowCancellationObservation {
    private let token = UUID().uuidString
    let ready = XCTestExpectation(description: "actual diagnostic Flow ready callback")
    let finished = XCTestExpectation(description: "actual exported collect returned")
    var readyMarker: String { "synthetic-ready-\(token)" }
    var postCancelMarker: String { "synthetic-post-cancel-\(token)" }
    var trace: [String] = []
    var outcome = "NOT_FINISHED"
    var swiftCancelFlag = false
    private(set) var sawReady = false
    private(set) var sawPostCancel = false
    private(set) var didReturn = false
    private var cancelledAtReturn: Bool?

    func receive(_ line: String) {
        if line.hasSuffix("[swift-flow-probe] \(readyMarker)"), !sawReady {
            sawReady = true
            trace.append("ready-callback")
            ready.fulfill()
        } else if line.hasSuffix("[swift-flow-probe] \(postCancelMarker)"), !sawPostCancel {
            sawPostCancel = true
            trace.append("post-cancel-callback")
        }
    }

    func collectionReturned(cancelled: Bool) {
        didReturn = true
        cancelledAtReturn = cancelled
        trace.append("collect-returned")
        finished.fulfill()
    }

    var report: String {
        """
        P2PKIT_SWIFT_FLOW_CANCELLATION_PROBE
        outcome=\(outcome)
        readyCallback=\(sawReady)
        swiftCancelFlag=\(swiftCancelFlag)
        postCancelCallback=\(sawPostCancel)
        collectReturned=\(didReturn)
        swiftCancelFlagAtReturn=\(cancelledAtReturn.map { String($0) } ?? "NOT_RETURNED")
        trace=\(trace.joined(separator: " -> "))
        cleanup=ISOLATED_TEST_HOST_RETIREMENT_REQUIRED_NOT_A_CANCELLATION_PASS
        """
    }
}
