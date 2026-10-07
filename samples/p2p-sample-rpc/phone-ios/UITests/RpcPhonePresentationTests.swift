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
    func testLiveCounterCardsAreVisibleAndDoNotInventAConnectionBeforeStarting() {
        let app = XCUIApplication()
        app.launchArguments.append("--rpc-ui-network-unavailable")
        app.launch()
        defer { app.terminate() }
        XCTAssertTrue(app.staticTexts["rpc.activeRole"].waitForExistence(timeout: 5))
        let live = app.staticTexts["rpc.liveState"]
        reveal(live, in: app, up: true)
        XCTAssertEqual(live.label, "No active role; counters not observed")
        for (id, label) in [("clients", "Clients"), ("pending", "Pending"), ("completed", "Completed"), ("queued", "Queued")] {
            let card = app.descendants(matching: .any).matching(identifier: "rpc.card." + id).firstMatch
            reveal(card, in: app, up: true)
            XCTAssertEqual(card.label, label)
            XCTAssertEqual(card.value as? String, "—")
        }
        let screenshot = XCTAttachment(screenshot: app.screenshot())
        screenshot.name = "Live counter cards — stopped, no invented peer or counters"
        screenshot.lifetime = .keepAlways
        add(screenshot)
        reveal(app.buttons["rpc.stop"], in: app, up: true)
        XCTAssertFalse(app.buttons["rpc.stop"].isEnabled)
        let clearHistory = app.buttons["Clear completed history"]
        reveal(clearHistory, in: app, up: true)
        XCTAssertTrue(clearHistory.isEnabled)
        clearHistory.tap()
        XCTAssertFalse(app.buttons["Copy request details (includes data)"].exists,
            "An empty application history must not invent a request or expose copied data")
    }

    @MainActor
    func testSafeDiagnosticsExplainRejectedStartAndCanBeCopiedWithoutSelectingARole() {
        let app = XCUIApplication()
        app.launchArguments.append("--rpc-ui-network-unavailable")
        app.launch()
        defer { app.terminate() }
        XCTAssertTrue(app.staticTexts["rpc.activeRole"].waitForExistence(timeout: 5))
        XCTAssertEqual(app.staticTexts["rpc.activeRole"].label, "No active role")
        reveal(app.buttons["rpc.host"], in: app, up: true)
        app.buttons["rpc.host"].tap()
        let alert = app.alerts["Cannot start RPC"]
        XCTAssertTrue(alert.waitForExistence(timeout: 5))
        alert.buttons["OK"].tap()
        let copy = app.buttons["rpc.copyDiagnostics"]
        reveal(copy, in: app, up: true)
        XCTAssertTrue(copy.isEnabled)
        copy.tap()
        let events = app.buttons["Recent events (last 64)"]
        reveal(events, in: app, up: true)
        events.tap()
        let log = app.staticTexts["rpc.diagnostics"]
        reveal(log, in: app, up: true)
        XCTAssertTrue(log.label.contains("Last failure: StartRejected"))
        XCTAssertTrue(log.label.contains("Host: start requested"))
        XCTAssertFalse(log.label.contains("rpc1|"))
        let screenshot = XCTAttachment(screenshot: app.screenshot())
        screenshot.name = "Safe local diagnostics after rejected startup — no peer or payload"
        screenshot.lifetime = .keepAlways
        add(screenshot)
        reveal(app.staticTexts["rpc.activeRole"], in: app, up: false)
        XCTAssertEqual(app.staticTexts["rpc.activeRole"].label, "No active role")
        reveal(app.buttons["rpc.stop"], in: app, up: true)
        XCTAssertFalse(app.buttons["rpc.stop"].isEnabled)
    }

    @MainActor
    func testLaunchDoesNotSelectARoleOrHostAndExplainsQualificationScope() {
        let app = XCUIApplication()
        app.launchArguments.append("--rpc-ui-network-unavailable")
        app.launch()
        defer { app.terminate() }
        XCTAssertTrue(app.staticTexts["rpc.status"].waitForExistence(timeout: 5))
        XCTAssertTrue(app.staticTexts["rpc.status"].label.contains("no capacity qualification"))
        let appSwitchGuidance = app.staticTexts["rpc.introduction"]
        reveal(appSwitchGuidance, in: app, up: false)
        XCTAssertTrue(appSwitchGuidance.exists, "The short app-switch limit must be visible before selecting a role")
        XCTAssertEqual(appSwitchGuidance.label, "Choose a role on your private LAN. Network selection is automatic; " +
            "peer trust is not. Return within 25 seconds when switching apps.")
        XCTAssertFalse(app.textFields["rpc.subnets"].exists)
        XCTAssertFalse(app.textFields["rpc.interface"].exists)
        XCTAssertFalse(app.textFields["rpc.local"].exists)
        reveal(app.buttons["rpc.refreshWifi"], in: app, up: true)
        XCTAssertTrue(app.buttons["rpc.refreshWifi"].exists)
        XCTAssertFalse(app.buttons["rpc.confirmWifi"].exists, "Normal application setup needs no confirmation step")
        let screenshot = XCTAttachment(screenshot: app.screenshot())
        screenshot.name = "Simple Wi-Fi setup — no manual network fields"
        screenshot.lifetime = .keepAlways
        add(screenshot)
        reveal(app.buttons["rpc.client"], in: app, up: true)
        XCTAssertTrue(app.buttons["rpc.client"].isEnabled)
        reveal(app.buttons["rpc.host"], in: app, up: false)
        XCTAssertTrue(app.buttons["rpc.host"].isEnabled)
        reveal(app.buttons["rpc.stop"], in: app, up: true)
        XCTAssertFalse(app.buttons["rpc.stop"].isEnabled)
    }

    @MainActor
    func testWifiRefreshShowsItsReasonWithoutConfirmingOrStartingARole() {
        let app = XCUIApplication()
        app.launchArguments = ["--rpc-wifi-diagnostic"]
        app.launchArguments.append("--rpc-ui-network-unavailable")
        app.launch()
        defer { app.terminate() }
        XCTAssertTrue(app.staticTexts["rpc.status"].waitForExistence(timeout: 5))
        let reason = app.staticTexts["rpc.wifiStatus"]
        reveal(reason, in: app, up: true)
        XCTAssertFalse(reason.label.isEmpty, "A disabled confirmation must explain the blocking check")
        let refresh = app.buttons["rpc.refreshWifi"]
        reveal(refresh, in: app, up: true)
        XCTAssertTrue(refresh.isEnabled)
        refresh.tap()
        let status = app.staticTexts["rpc.status"]
        reveal(status, in: app, up: false)
        XCTAssertTrue(status.label.contains("Rechecking Wi-Fi"))
        XCTAssertTrue(status.label.contains("nothing has started"))
        XCTAssertFalse(app.buttons["rpc.confirmWifi"].exists, "Normal application setup needs no confirmation step")
        let detailsButton = app.buttons["Wi-Fi check details"]
        reveal(detailsButton, in: app, up: true)
        detailsButton.tap()
        let details = app.staticTexts["rpc.wifiDetails"]
        reveal(details, in: app, up: true)
        XCTAssertTrue(details.label.hasPrefix("Check: "))
        XCTAssertTrue(details.label.contains("Default path:") || details.label.contains("No current path observation."))
        let screenshot = XCTAttachment(screenshot: app.screenshot())
        screenshot.name = "Wi-Fi observation reason and passive refresh"
        screenshot.lifetime = .keepAlways
        add(screenshot)
        for role in ["rpc.host", "rpc.client"] {
            reveal(app.buttons[role], in: app, up: true)
            XCTAssertTrue(app.buttons[role].isEnabled)
        }
        reveal(app.buttons["rpc.stop"], in: app, up: true)
        XCTAssertFalse(app.buttons["rpc.stop"].isEnabled)
        XCTAssertFalse(app.textFields["rpc.subnets"].exists)
    }

    @MainActor
    func testUnavailableWifiExplainsAutomaticStartRejectionWithoutStartingANetworkRuntime() {
        let app = XCUIApplication()
        app.launchArguments.append("--rpc-ui-network-unavailable")
        app.launch()
        defer { app.terminate() }
        XCTAssertTrue(app.staticTexts["rpc.status"].waitForExistence(timeout: 5))
        for role in ["rpc.host", "rpc.client"] {
            reveal(app.buttons[role], in: app, up: true)
            app.buttons[role].tap()
            let alert = app.alerts["Cannot start RPC"]
            XCTAssertTrue(alert.waitForExistence(timeout: 5))
            XCTAssertTrue(alert.isHittable)
            let explanation = alert.staticTexts.matching(NSPredicate(format: "label CONTAINS %@", "No role was started"))
                .firstMatch
            XCTAssertTrue(explanation.exists)
            XCTAssertTrue(explanation.label.contains("No role was started"))
            alert.buttons["OK"].tap()
            reveal(app.buttons["rpc.stop"], in: app, up: true)
            XCTAssertFalse(app.buttons["rpc.stop"].isEnabled)
            reveal(app.buttons["rpc.host"], in: app, up: false)
            XCTAssertTrue(app.buttons["rpc.host"].isEnabled)
            reveal(app.buttons["rpc.client"], in: app, up: true)
            XCTAssertTrue(app.buttons["rpc.client"].isEnabled)
        }
    }

    @MainActor
    func testInvalidEmptyPolicyIsCatchableWithoutStartingANetworkRuntime() {
        let app = XCUIApplication()
        app.launchArguments.append("--rpc-ui-network-unavailable")
        app.launch()
        defer { app.terminate() }
        XCTAssertTrue(app.staticTexts["rpc.status"].waitForExistence(timeout: 5))
        reveal(app.buttons["Advanced"], in: app, up: true)
        app.buttons["Advanced"].tap()
        let manual = app.buttons["rpc.manualNetwork"]
        reveal(manual, in: app, up: true)
        manual.tap()
        XCTAssertEqual(manual.label, "Use detected Wi-Fi instead", "Manual setup must actually be selected")
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
            // Form virtualizes offscreen rows; reveal each control before asserting its state.
            reveal(app.buttons["rpc.host"], in: app, up: false)
            XCTAssertTrue(app.buttons["rpc.host"].isEnabled)
            reveal(app.buttons["rpc.client"], in: app, up: true)
            XCTAssertTrue(app.buttons["rpc.client"].isEnabled)
            reveal(app.buttons["rpc.stop"], in: app, up: true)
            XCTAssertFalse(app.buttons["rpc.stop"].isEnabled)
        }
    }
}
