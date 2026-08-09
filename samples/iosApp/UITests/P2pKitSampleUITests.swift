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
    private func runStartStopScenario(dropFirstStartAction: Bool) {
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
        guard stop.waitForExistence(timeout: 30) else {
            XCTFail("start should reach the running state; status was \(app.staticTexts["sample-status"].label)")
            return
        }
        XCTAssertEqual(app.staticTexts["sample-status"].label, "Status: Running")

        stop.tap()
        XCTAssertTrue(start.waitForExistence(timeout: 30), "stop should release the kit and restore Start")
        XCTAssertEqual(app.staticTexts["sample-status"].label, "Status: Stopped")
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

        XCTAssertEqual(app.state, .runningForeground, "sample must remain foreground for input recovery")
        XCTAssertEqual(
            status.label,
            "Status: Not started",
            "only an input event that left application state untouched may be retried"
        )
        XCTAssertTrue(start.exists, "Start must still exist before the alternate input path")
        XCTAssertTrue(start.isHittable, "Start must still be hittable before the alternate input path")

        start.coordinate(withNormalizedOffset: CGVector(dx: 0.5, dy: 0.5)).tap()
        XCTAssertTrue(
            waitForStartAcknowledgement(status: status, timeout: 8),
            "neither semantic nor center-coordinate Start input reached the application"
        )
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
