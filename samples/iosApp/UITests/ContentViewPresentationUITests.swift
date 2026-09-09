import XCTest

final class ContentViewPresentationUITests: XCTestCase {
    @MainActor
    func testRenderedPortRoundTripsThroughManualInputInEnglishLocale() throws {
        try checkRenderedPort(locale: "en_US")
    }

    @MainActor
    func testRenderedPortRoundTripsThroughManualInputInGermanLocale() throws {
        try checkRenderedPort(locale: "de_DE")
    }

    @MainActor
    func testFirstIncomingOfferRequiresConsentWithoutTransferHistory() {
        withRunningSample(arguments: ["--p2pkit-ui-test-pending-offer"]) { app in
            let incoming = app.staticTexts["Incoming file offers"]
            let transfers = app.staticTexts["File transfers (0)"]
            let accept = app.buttons["Accept"]
            let reject = app.buttons["Reject"]
            let inject = app.buttons["ui-consent-fixture-inject"]
            let empty = app.buttons["ui-consent-fixture-empty"]
            let decisions = app.staticTexts["ui-consent-fixture-decisions"]
            XCTAssertTrue(decisions.waitForExistence(timeout: 5))
            XCTAssertEqual(decisions.label, "accept=0 reject=0")
            XCTAssertFalse(incoming.exists)
            XCTAssertFalse(transfers.exists)
            XCTAssertFalse(accept.exists)
            XCTAssertFalse(reject.exists)

            reveal(inject, in: app, towardBottom: true)
            let enabled = XCTNSPredicateExpectation(predicate: NSPredicate(format: "enabled == true"), object: inject)
            XCTAssertEqual(XCTWaiter.wait(for: [enabled], timeout: 5), .completed)
            inject.tap()
            XCTAssertTrue(incoming.waitForExistence(timeout: 5))
            XCTAssertFalse(app.staticTexts["ui-consent-fixture-error"].exists)
            XCTAssertTrue(transfers.exists, "The first offer must not require a transfer-history row")
            reveal(accept, in: app, towardBottom: true)
            XCTAssertTrue(accept.isHittable)
            XCTAssertTrue(reject.isHittable)
            XCTAssertTrue(app.staticTexts.matching(NSPredicate(format: "label ENDSWITH %@", "— waiting for consent"))
                .firstMatch.exists)
            XCTAssertEqual(decisions.label, "accept=0 reject=0", "Rendering must not call either consent operation")
            let screenshot = XCTAttachment(screenshot: app.screenshot())
            screenshot.name = "synthetic-first-offer-without-transfer-history"
            screenshot.lifetime = .keepAlways
            add(screenshot)

            reject.tap()
            XCTAssertTrue(waitForLabel("accept=0 reject=1", on: decisions))
            XCTAssertTrue(waitForAbsence(incoming))
            XCTAssertFalse(accept.exists)
            XCTAssertFalse(reject.exists)
            XCTAssertFalse(transfers.exists)

            reveal(inject, in: app, towardBottom: false)
            inject.tap()
            XCTAssertTrue(incoming.waitForExistence(timeout: 5))
            XCTAssertEqual(decisions.label, "accept=0 reject=1")
            reveal(empty, in: app, towardBottom: false)
            empty.tap()
            XCTAssertTrue(waitForAbsence(incoming))
            XCTAssertFalse(accept.exists)
            XCTAssertFalse(reject.exists)
            XCTAssertFalse(transfers.exists)
            XCTAssertEqual(decisions.label, "accept=0 reject=1", "Snapshot removal is not a user consent decision")
        }
    }

    @MainActor
    private func checkRenderedPort(locale: String) throws {
        try withRunningSample(locale: locale) { app in
            let prefix = "localTcpPort: "
            let portRow = app.staticTexts.matching(NSPredicate(format: "label BEGINSWITH %@", prefix)).firstMatch
            XCTAssertTrue(portRow.waitForExistence(timeout: 5))
            let rendered = portRow.label
            XCTAssertTrue(rendered.hasPrefix(prefix))
            let token = String(rendered.dropFirst(prefix.count))
            XCTAssertFalse(token.isEmpty)
            XCTAssertTrue(token.unicodeScalars.allSatisfy { (0x30...0x39).contains($0.value) })
            let port = try XCTUnwrap(Int32(token), "The rendered token must parse without stripping separators")
            XCTAssertTrue((1_000...65_535).contains(port), "Use a grouping-sensitive real listener port")
            XCTAssertEqual(token, String(port), "Technical endpoint tokens use canonical ASCII decimal")
            let screenshot = XCTAttachment(screenshot: app.screenshot())
            screenshot.name = "synthetic-simulator-port-\(locale)"
            screenshot.lifetime = .keepAlways
            add(screenshot)

            let host = app.textFields["Host (e.g. 192.168.1.42)"]
            reveal(host, in: app, towardBottom: true)
            host.tap()
            host.typeText("127.0.0.1")
            let inputPort = app.textFields["Port"]
            inputPort.tap()
            inputPort.typeText(token)
            XCTAssertEqual(inputPort.value as? String, token, "Do not repair the displayed token before input")
            dismissKeyboard(in: app)
            let pairing = app.textFields["Peer pairing QR text (p2pkit:v2:…)"]
            reveal(pairing, in: app, towardBottom: true)
            pairing.tap()
            pairing.typeText("invalid-pairing-for-port-parser-probe")
            dismissKeyboard(in: app)
            let dial = app.buttons["Dial manual peer"]
            reveal(dial, in: app, towardBottom: true)
            XCTAssertTrue(dial.isEnabled)
            dial.tap()
            // This later guard proves the actual production port parser/range accepted
            // the unmodified rendered token. No manual peer connection is attempted.
            XCTAssertTrue(app.staticTexts["Enter the peer's full pairing QR text for this AppId."]
                .waitForExistence(timeout: 5))
        }
    }

    @MainActor
    private func withRunningSample(
        locale: String = "en_US",
        arguments: [String] = [],
        check: (XCUIApplication) throws -> Void
    ) rethrows {
        continueAfterFailure = false
        let app = XCUIApplication()
        app.launchArguments = ["-AppleLanguages", "(en)", "-AppleLocale", locale] + arguments
        let monitor = addUIInterruptionMonitor(withDescription: "Local Network permission") { alert in
            for label in ["Allow", "OK"] where alert.buttons[label].exists {
                alert.buttons[label].tap()
                return true
            }
            return false
        }
        defer {
            app.terminate()
            removeUIInterruptionMonitor(monitor)
        }
        app.launch()
        XCTAssertTrue(app.staticTexts["sample-title"].waitForExistence(timeout: 10))
        let status = app.staticTexts["sample-status"]
        XCTAssertEqual(status.label, "Status: Not started")
        let start = app.buttons["start-kit"]
        XCTAssertTrue(start.isHittable)
        // One real coordinate input, not state injection or an operation retry.
        start.coordinate(withNormalizedOffset: CGVector(dx: 0.5, dy: 0.5)).tap()
        app.tap() // Deliver any Local Network interruption to the monitor.
        XCTAssertTrue(waitForLabel("Status: Running", on: status, timeout: 30))
        XCTAssertTrue(app.buttons["stop-kit"].exists)
        try check(app)
        let stop = app.buttons["stop-kit"]
        reveal(stop, in: app, towardBottom: false)
        stop.tap()
        XCTAssertTrue(waitForLabel("Status: Stopped", on: status, timeout: 30))
        XCTAssertTrue(start.exists)
    }

    @MainActor
    private func waitForLabel(_ label: String, on element: XCUIElement, timeout: TimeInterval = 5) -> Bool {
        let expectation = XCTNSPredicateExpectation(predicate: NSPredicate(format: "label == %@", label), object: element)
        return XCTWaiter.wait(for: [expectation], timeout: timeout) == .completed
    }

    @MainActor
    private func waitForAbsence(_ element: XCUIElement) -> Bool {
        let expectation = XCTNSPredicateExpectation(predicate: NSPredicate(format: "exists == false"), object: element)
        return XCTWaiter.wait(for: [expectation], timeout: 5) == .completed
    }

    @MainActor
    private func reveal(_ element: XCUIElement, in app: XCUIApplication, towardBottom: Bool) {
        for _ in 0..<6 {
            if element.isHittable { return }
            if towardBottom {
                app.scrollViews.firstMatch.swipeUp()
            } else {
                app.scrollViews.firstMatch.swipeDown()
            }
        }
        XCTAssertTrue(element.isHittable, "The actual production control must be reachable")
    }

    @MainActor
    private func dismissKeyboard(in app: XCUIApplication) {
        let done = app.buttons["Done"]
        if done.exists { done.tap() }
    }
}
