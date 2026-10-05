import XCTest

final class RpcPhonePresentationTests: XCTestCase {
    @MainActor
    private func reveal(_ element: XCUIElement, in app: XCUIApplication, up: Bool) {
        // Navigate to the actual control, never tap an offscreen guess.
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
        XCTAssertFalse(app.textFields["rpc.subnets"].exists)
        XCTAssertFalse(app.textFields["rpc.interface"].exists)
        XCTAssertFalse(app.textFields["rpc.local"].exists)
        XCTAssertTrue(app.buttons["rpc.confirmWifi"].exists)
        let screenshot = XCTAttachment(screenshot: app.screenshot())
        screenshot.name = "Simple Wi-Fi setup — no manual network fields"
        screenshot.lifetime = .keepAlways
        add(screenshot)
        reveal(app.buttons["rpc.client"], in: app, up: true)
        XCTAssertTrue(app.buttons["rpc.client"].isEnabled)
        XCTAssertTrue(app.buttons["rpc.host"].isEnabled)
        XCTAssertFalse(app.buttons["rpc.stop"].isEnabled)
    }

    @MainActor
    func testUnconfirmedWifiExplainsNextTapWithoutStartingANetworkRuntime() {
        let app = XCUIApplication()
        app.launch()
        defer { app.terminate() }
        XCTAssertTrue(app.staticTexts["rpc.status"].waitForExistence(timeout: 5))
        for role in ["rpc.host", "rpc.client"] {
            reveal(app.buttons[role], in: app, up: true)
            app.buttons[role].tap()
            let alert = app.alerts["Cannot start RPC"]
            XCTAssertTrue(alert.waitForExistence(timeout: 5))
            XCTAssertTrue(alert.isHittable)
            let explanation = alert.staticTexts.matching(NSPredicate(format: "label CONTAINS %@", "Use this Wi-Fi"))
                .firstMatch
            XCTAssertTrue(explanation.exists)
            XCTAssertTrue(explanation.label.contains("No role was started"))
            alert.buttons["OK"].tap()
            reveal(app.buttons["rpc.stop"], in: app, up: true)
            XCTAssertFalse(app.buttons["rpc.stop"].isEnabled)
            XCTAssertTrue(app.buttons["rpc.host"].isEnabled)
            XCTAssertTrue(app.buttons["rpc.client"].isEnabled)
        }
    }

    @MainActor
    func testInvalidEmptyPolicyIsCatchableWithoutStartingANetworkRuntime() {
        let app = XCUIApplication()
        app.launch()
        defer { app.terminate() }
        XCTAssertTrue(app.staticTexts["rpc.status"].waitForExistence(timeout: 5))
        reveal(app.buttons["rpc.advanced"], in: app, up: true)
        app.buttons["rpc.advanced"].tap()
        reveal(app.switches["rpc.manualNetwork"], in: app, up: true)
        app.switches["rpc.manualNetwork"].tap()
        for role in ["rpc.host", "rpc.client"] {
            reveal(app.buttons[role], in: app, up: false)
            app.buttons[role].tap()
            let alert = app.alerts["Cannot start RPC"]
            XCTAssertTrue(alert.waitForExistence(timeout: 5))
            XCTAssertTrue(alert.isHittable, "A failed tap must explain itself without scrolling away from the button")
            let explanation = alert.staticTexts.matching(NSPredicate(format: "label CONTAINS %@", "Invalid setup"))
                .firstMatch
            XCTAssertTrue(explanation.label.contains("approved private CIDRs"))
            XCTAssertTrue(explanation.label.contains("Wi-Fi interface"))
            XCTAssertTrue(explanation.label.contains("this iPhone's numeric LAN address"))
            alert.buttons["OK"].tap()
            let status = app.staticTexts["rpc.status"]
            reveal(status, in: app, up: false)
            let failed = NSPredicate(format: "label CONTAINS %@", "Invalid setup")
            expectation(for: failed, evaluatedWith: status)
            waitForExpectations(timeout: 5)
            let nearbyStatus = app.staticTexts["rpc.roleStatus"]
            reveal(nearbyStatus, in: app, up: true)
            XCTAssertTrue(nearbyStatus.label.contains("Invalid setup"))
            reveal(app.buttons["rpc.client"], in: app, up: true)
            XCTAssertFalse(app.buttons["rpc.stop"].isEnabled)
            XCTAssertTrue(app.buttons["rpc.host"].isEnabled)
            XCTAssertTrue(app.buttons["rpc.client"].isEnabled)
        }
    }
}
