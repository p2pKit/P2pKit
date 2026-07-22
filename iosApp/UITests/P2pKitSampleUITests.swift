import XCTest

final class P2pKitSampleUITests: XCTestCase {
    @MainActor
    func testLaunchStartAndStopControls() {
        let app = XCUIApplication()
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
        start.tap()
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
}
