import XCTest

final class P2pKitSampleUITests: XCTestCase {
    @MainActor
    func testLaunchStartAndStopControls() {
        runStartStopScenario(dropFirstStartAction: false)
    }

    @MainActor
    func testRecoversOneProvablyUnacknowledgedStartInput() {
        runStartStopScenario(dropFirstStartAction: true)
    }

    @MainActor
    func testLocalPairingDisclosureAndStopCleanup() {
        runStartStopScenario(dropFirstStartAction: false, verifyPairing: true)
    }

    @MainActor
    private func runStartStopScenario(dropFirstStartAction: Bool, verifyPairing: Bool = false) {
        continueAfterFailure = false
        let app = XCUIApplication()
        if dropFirstStartAction {
            app.launchArguments.append("--p2pkit-ui-test-drop-first-start-action")
        }
        addUIInterruptionMonitor(withDescription: "Local Network permission") { alert in
            for label in ["Allow", "OK"] where alert.buttons[label].exists {
                alert.buttons[label].tap()
                return true
            }
            return false
        }

        app.launch()

        let title = app.staticTexts["sample-title"]
        XCTAssertTrue(title.waitForExistence(timeout: 10), "sample title should be visible")
        XCTAssertEqual(app.staticTexts["sample-status"].label, "Status: Not started")

        let start = app.buttons["start-kit"]
        XCTAssertTrue(start.exists, "start control should be visible before launch")
        XCTAssertTrue(start.isHittable, "start control should be hittable before launch")
        let status = app.staticTexts["sample-status"]
        tapStartAndRequireAcknowledgement(app: app, start: start, status: status)
        app.tap()

        let stop = app.buttons["stop-kit"]
        guard waitForRunning(status: status, timeout: 30) else {
            XCTFail("start did not finish advertising/discovery; status was \(status.label)")
            return
        }
        XCTAssertTrue(stop.exists, "running kit must retain its Stop control")

        if verifyPairing {
            let show = app.buttons["show-local-pairing"]
            let qr = app.staticTexts["local-pairing-qr"]
            XCTAssertTrue(show.exists)
            XCTAssertFalse(qr.exists, "identity must not be disclosed before an explicit action")
            show.tap()
            XCTAssertTrue(qr.waitForExistence(timeout: 5))
            let text = qr.label
            XCTAssertEqual(text.count, 125, "show the complete canonical QR, never an ellipsized/prefixed value")
            XCTAssertTrue(text.hasPrefix("p2pkit:v2:p2a1-"))
            XCTAssertEqual(text.components(separatedBy: ":").count, 4)
            XCTAssertTrue(text.components(separatedBy: ":").last?.hasPrefix("p2f1-") == true)
            let screenshot = XCTAttachment(screenshot: app.screenshot())
            screenshot.name = "synthetic-simulator-pairing-disclosure"
            screenshot.lifetime = .keepAlways
            add(screenshot)
            show.tap()
            XCTAssertFalse(qr.exists)
        }

        stop.tap()
        XCTAssertTrue(start.waitForExistence(timeout: 30), "stop should release the kit and restore Start")
        XCTAssertEqual(app.staticTexts["sample-status"].label, "Status: Stopped")
        if verifyPairing {
            XCTAssertFalse(app.buttons["show-local-pairing"].exists)
            XCTAssertFalse(app.staticTexts["local-pairing-qr"].exists)
        }
    }

    /// XCTest can report a successful semantic `tap()` even when a heavily
    /// loaded hosted simulator never delivers that input to SwiftUI. Retry
    /// only that proven input-delivery failure through the element's center
    /// coordinate; do not retry an acknowledged application action or any
    /// P2pKit operation. The two acknowledgement waits retain the existing
    /// aggregate ten-second budget.
    @MainActor
    private func tapStartAndRequireAcknowledgement(
        app: XCUIApplication,
        start: XCUIElement,
        status: XCUIElement
    ) {
        start.tap()
        if waitForStartAcknowledgement(status: status, timeout: 2) {
            return
        }

        XCTAssertTrue(
            recoverUnacknowledgedStart(
                acknowledged: { status.label != "Status: Not started" },
                record: {
                    XCTContext.runActivity(named: "Record unacknowledged semantic Start tap") { activity in
                        let screenshot = XCTAttachment(screenshot: app.screenshot())
                        screenshot.name = "unacknowledged-start-tap"
                        screenshot.lifetime = .keepAlways
                        activity.add(screenshot)

                        let hierarchy = XCTAttachment(string: app.debugDescription)
                        hierarchy.name = "unacknowledged-start-accessibility-hierarchy"
                        hierarchy.lifetime = .keepAlways
                        activity.add(hierarchy)
                    }
                },
                ready: { app.state == .runningForeground && start.exists && start.isHittable },
                retry: { start.coordinate(withNormalizedOffset: CGVector(dx: 0.5, dy: 0.5)).tap() },
                wait: { waitForStartAcknowledgement(status: status, timeout: $0) }
            ),
            "Start remained unacknowledged or its alternate input path was not safe"
        )
    }

    /// Accessibility and diagnostic reads can outlive the first wait. An
    /// acknowledgement observed during either is progress, not evidence that
    /// Start must be tapped again. Final running/QR/stop checks remain separate.
    @MainActor
    private func recoverUnacknowledgedStart(
        acknowledged: () -> Bool,
        record: () -> Void,
        ready: () -> Bool,
        retry: () -> Void,
        wait: (TimeInterval) -> Bool
    ) -> Bool {
        if acknowledged() { return true }
        record()
        if acknowledged() { return true }
        let mayRetry = ready()
        if acknowledged() { return true }
        guard mayRetry else { return false }
        retry()
        return wait(8)
    }

    @MainActor
    func testLateStartAcknowledgementBeforeDiagnosticsDoesNotRetry() {
        var recordings = 0
        var readinessReads = 0
        var retries = 0
        var waits: [TimeInterval] = []
        let result = recoverUnacknowledgedStart(
            acknowledged: { true },
            record: { recordings += 1 },
            ready: { readinessReads += 1; return true },
            retry: { retries += 1 },
            wait: { waits.append($0); return true }
        )
        XCTAssertTrue(result)
        XCTAssertEqual(recordings, 0)
        XCTAssertEqual(readinessReads, 0)
        XCTAssertEqual(retries, 0)
        XCTAssertTrue(waits.isEmpty)
    }

    @MainActor
    func testLateStartAcknowledgementDuringDiagnosticsDoesNotRetry() {
        var acknowledged = false
        var recordings = 0
        var readinessReads = 0
        var retries = 0
        var waits: [TimeInterval] = []
        let result = recoverUnacknowledgedStart(
            acknowledged: { acknowledged },
            record: { recordings += 1; acknowledged = true },
            ready: { readinessReads += 1; return true },
            retry: { retries += 1 },
            wait: { waits.append($0); return true }
        )
        XCTAssertTrue(result)
        XCTAssertEqual(recordings, 1)
        XCTAssertEqual(readinessReads, 0)
        XCTAssertEqual(retries, 0)
        XCTAssertTrue(waits.isEmpty)
    }

    @MainActor
    func testLateStartAcknowledgementDuringReadinessDoesNotRetry() {
        var acknowledged = false
        var recordings = 0
        var readinessReads = 0
        var retries = 0
        var waits: [TimeInterval] = []
        let result = recoverUnacknowledgedStart(
            acknowledged: { acknowledged },
            record: { recordings += 1 },
            ready: { readinessReads += 1; acknowledged = true; return false },
            retry: { retries += 1 },
            wait: { waits.append($0); return true }
        )
        XCTAssertTrue(result)
        XCTAssertEqual(recordings, 1)
        XCTAssertEqual(readinessReads, 1)
        XCTAssertEqual(retries, 0)
        XCTAssertTrue(waits.isEmpty)
    }

    @MainActor
    func testOnlyUnacknowledgedReadyStartGetsOneBoundedRetry() {
        for (isReady, waitResult) in [(false, true), (true, false), (true, true)] {
            var recordings = 0
            var readinessReads = 0
            var retries = 0
            var waits: [TimeInterval] = []
            let result = recoverUnacknowledgedStart(
                acknowledged: { false },
                record: { recordings += 1 },
                ready: { readinessReads += 1; return isReady },
                retry: { retries += 1 },
                wait: { waits.append($0); return waitResult }
            )
            XCTAssertEqual(result, isReady && waitResult)
            XCTAssertEqual(recordings, 1)
            XCTAssertEqual(readinessReads, 1)
            XCTAssertEqual(retries, isReady ? 1 : 0)
            XCTAssertEqual(waits, isReady ? [8] : [])
        }
    }

    /// Stop is present as soon as a kit exists, BEFORE async startup finishes.
    /// Use one existing 30-second budget for the semantic readiness boundary.
    @MainActor
    private func waitForRunning(status: Any, timeout: TimeInterval) -> Bool {
        let expectation = XCTNSPredicateExpectation(
            predicate: NSPredicate(format: "label == %@", "Status: Running"),
            object: status
        )
        return XCTWaiter.wait(for: [expectation], timeout: timeout) == .completed
    }

    @MainActor
    func testRunningOracleWaitsForDelayedStartupPublicationWithoutAnotherTap() {
        let status = StartupStatusFixture()
        XCTAssertTrue(status.stopExists)
        XCTAssertEqual(status.label, "Status: Starting")
        // The same wait must process a later main-actor readiness publication.
        // No synthetic Start tap, SDK retry, or extra startup budget is granted.
        DispatchQueue.main.async { status.label = "Status: Running" }
        XCTAssertTrue(waitForRunning(status: status, timeout: 2))
    }

    @MainActor
    func testRunningOracleRejectsStartingEvenWhenStopIsAlreadyPresent() {
        let status = StartupStatusFixture()
        // Models the real state after kit assignment while advertise/discover wait.
        XCTAssertTrue(status.stopExists)
        XCTAssertFalse(waitForRunning(status: status, timeout: 0.01),
                       "a startup that never completes must fail its bounded wait")
        status.label = "Status: Running"
        XCTAssertTrue(waitForRunning(status: status, timeout: 0.01))
        for label in ["Status: Not started", "Status: Stopped", "Status: Starting", "Status: Failed"] {
            status.label = label
            XCTAssertFalse(waitForRunning(status: status, timeout: 0.01))
        }
    }

    @MainActor
    private func waitForStartAcknowledgement(status: XCUIElement, timeout: TimeInterval) -> Bool {
        let expectation = XCTNSPredicateExpectation(
            predicate: NSPredicate(format: "label != %@", "Status: Not started"),
            object: status
        )
        return XCTWaiter.wait(for: [expectation], timeout: timeout) == .completed
    }
}

@MainActor
private final class StartupStatusFixture: NSObject {
    @objc dynamic var label = "Status: Starting"
    let stopExists = true
}
