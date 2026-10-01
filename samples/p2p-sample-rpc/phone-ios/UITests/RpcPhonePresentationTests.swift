import XCTest

final class RpcPhonePresentationTests: XCTestCase {
    @MainActor
    private func reveal(_ element: XCUIElement, in app: XCUIApplication, up: Bool) {
        // The optional USB section extends the form; navigate to the actual control, never tap an offscreen guess.
        for _ in 0..<8 {
            if element.exists && element.isHittable { return }
            if up { app.swipeUp() } else { app.swipeDown() }
        }
        XCTAssertTrue(element.exists && element.isHittable, "Required control was not reachable")
    }
    @MainActor
    func testLaunchDoesNotSelectARoleOrHostAndExplainsQualificationScope() {
        let app = XCUIApplication()
        app.launch()
        defer { app.terminate() }
        XCTAssertTrue(app.staticTexts["rpc.status"].waitForExistence(timeout: 5))
        XCTAssertTrue(app.staticTexts["rpc.status"].label.contains("no capacity qualification"))
        reveal(app.buttons["rpc.client"], in: app, up: true)
        XCTAssertTrue(app.buttons["rpc.client"].isEnabled)
        XCTAssertTrue(app.buttons["rpc.host"].isEnabled)
        XCTAssertFalse(app.buttons["rpc.stop"].isEnabled)
    }

    @MainActor
    func testInvalidEmptyPolicyIsCatchableWithoutStartingANetworkRuntime() {
        let app = XCUIApplication()
        app.launch()
        defer { app.terminate() }
        XCTAssertTrue(app.staticTexts["rpc.status"].waitForExistence(timeout: 5))
        reveal(app.buttons["rpc.client"], in: app, up: true)
        app.buttons["rpc.client"].tap()
        let status = app.staticTexts["rpc.status"]
        reveal(status, in: app, up: false)
        let failed = NSPredicate(format: "label CONTAINS %@", "Invalid setup")
        expectation(for: failed, evaluatedWith: status)
        waitForExpectations(timeout: 5)
        reveal(app.buttons["rpc.client"], in: app, up: true)
        XCTAssertFalse(app.buttons["rpc.stop"].isEnabled)
        XCTAssertTrue(app.buttons["rpc.host"].isEnabled)
    }
}
