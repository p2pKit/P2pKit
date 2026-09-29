import XCTest

final class RpcPhonePresentationTests: XCTestCase {
    @MainActor
    func testLaunchDoesNotSelectARoleOrHostAndExplainsQualificationScope() {
        let app = XCUIApplication()
        app.launch()
        defer { app.terminate() }
        XCTAssertTrue(app.staticTexts["rpc.status"].waitForExistence(timeout: 5))
        XCTAssertTrue(app.staticTexts["rpc.status"].label.contains("no capacity qualification"))
        app.swipeUp()
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
        app.swipeUp()
        app.buttons["rpc.client"].tap()
        app.swipeDown()
        let status = app.staticTexts["rpc.status"]
        let failed = NSPredicate(format: "label CONTAINS %@", "Invalid setup")
        expectation(for: failed, evaluatedWith: status)
        waitForExpectations(timeout: 5)
        app.swipeUp()
        XCTAssertFalse(app.buttons["rpc.stop"].isEnabled)
        XCTAssertTrue(app.buttons["rpc.host"].isEnabled)
    }
}
