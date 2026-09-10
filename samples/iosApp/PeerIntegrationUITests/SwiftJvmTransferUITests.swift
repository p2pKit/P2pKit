import XCTest

/// A real host JVM CLI is a fixture, not another SDK or simulated wire peer.
/// Run only through run-ios-ui-tests.sh prepare-jvm-transfer / run-jvm-transfer.
final class SwiftJvmTransferUITests: XCTestCase {
    @MainActor
    func testBidirectionalSecure204800ByteTransferWithJvmPeer() throws {
        continueAfterFailure = false
        let environment = ProcessInfo.processInfo.environment
        let nonce = try required("P2PKIT_JVM_NONCE", in: environment, matching: "[0-9a-f]{32}")
        let commit = try required("P2PKIT_JVM_SOURCE_COMMIT", in: environment, matching: "[0-9a-f]{40}")
        let port = try required("P2PKIT_JVM_PORT", in: environment, matching: "[0-9]{1,5}")
        XCTAssertTrue((1...65_535).contains(try XCTUnwrap(Int(port))))
        let qr = try required(
            "P2PKIT_JVM_QR", in: environment,
            matching: "p2pkit:v2:p2a1-[a-z2-7]{52}:p2f1-[a-z2-7]{52}"
        )
        let receiverHash = try required("P2PKIT_JVM_SHA256", in: environment, matching: "[0-9a-f]{64}")
        let incomingName = "jvm-\(nonce).bin"
        let app = XCUIApplication()
        app.launchArguments = ["-AppleLanguages", "(en)", "-AppleLocale", "en_US"]
        // CoreSimulator launches the runner/app through services, not necessarily
        // the controller's process tree. Preserve the admitted ownership markers.
        for key in ["P2PKIT_AUDIT_JOB_ID", "P2PKIT_AUDIT_OWNERSHIP_CHAIN", "P2PKIT_AUDIT_OWNERSHIP_DOMAINS",
                    "P2PKIT_AUDIT_STATE_DIR", "GRADLE_USER_HOME"] {
            let value = try XCTUnwrap(environment[key], "Missing owned invocation: \(key)")
            XCTAssertFalse(value.isEmpty)
            app.launchEnvironment[key] = value
        }
        let monitor = addUIInterruptionMonitor(withDescription: "Local Network permission") { alert in
            for label in ["Allow", "OK"] where alert.buttons[label].exists {
                alert.buttons[label].tap()
                return true
            }
            return false
        }
        var stopAttempted = false
        defer {
            // A failed assertion still attempts the real Stop once. Termination
            // is last-resort cleanup and never substitutes for a passing Stop.
            if !stopAttempted && app.state == .runningForeground {
                let stop = app.buttons["stop-kit"]
                if stop.exists {
                    scrollTo(stop, in: app, towardBottom: false)
                    if stop.isHittable {
                        stop.tap()
                        _ = waitForLabel("Status: Stopped", on: app.staticTexts["sample-status"], timeout: 30)
                    }
                }
            }
            app.terminate()
            removeUIInterruptionMonitor(monitor)
        }
        app.launch()
        XCTAssertTrue(app.staticTexts["sample-title"].waitForExistence(timeout: 10))
        let build = app.staticTexts["sample-build-info"].label
        XCTAssertTrue(build.hasPrefix("p2pkit@\(commit.prefix(7)) "))
        XCTAssertFalse(build.contains("-DIRTY"))
        XCTAssertEqual(app.staticTexts["sample-status"].label, "Status: Not started")
        replace(app.textFields["Device name"], with: "Swift-\(nonce)", in: app)
        dismissMainKeyboard(in: app)

        let diagnostics = app.buttons["test-diagnostics"]
        reveal(diagnostics, in: app, towardBottom: false)
        diagnostics.tap()
        replace(app.textFields["diagnostics-test-id"], with: "SWIFT-JVM", in: app)
        app.textFields["diagnostics-test-id"].typeText("\n")
        replace(app.textFields["diagnostics-session-id"], with: nonce, in: app)
        app.textFields["diagnostics-session-id"].typeText("\n")
        let begin = app.buttons["Begin Test Session"]
        reveal(begin, in: app)
        begin.tap()
        app.navigationBars["Test Diagnostics"].buttons["Done"].tap()

        let start = app.buttons["start-kit"]
        reveal(start, in: app, towardBottom: false)
        start.coordinate(withNormalizedOffset: CGVector(dx: 0.5, dy: 0.5)).tap()
        app.tap() // Deliver an actual Local Network interruption to the monitor.
        XCTAssertTrue(waitForLabel("Status: Running", on: app.staticTexts["sample-status"], timeout: 30))
        replace(app.textFields["Host (e.g. 192.168.1.42)"], with: "127.0.0.1", in: app)
        dismissMainKeyboard(in: app)
        replace(app.textFields["Port"], with: port, in: app)
        dismissMainKeyboard(in: app)
        replace(app.textFields["Peer pairing QR text (p2pkit:v2:…)"], with: qr, in: app)
        dismissMainKeyboard(in: app)
        let dial = app.buttons["Dial manual peer"]
        reveal(dial, in: app)
        XCTAssertTrue(dial.isEnabled)
        dial.tap()
        let session = app.staticTexts["sample-session-state"]
        XCTAssertTrue(session.waitForExistence(timeout: 30))
        XCTAssertTrue(waitForLabel("JVM-\(nonce) — Connected", on: session, timeout: 30))
        XCTAssertEqual(app.staticTexts.matching(identifier: "sample-session-state").count, 1)
        reveal(session, in: app)
        attach(app, named: "real-pinned-swift-jvm-connection")

        let sends = app.staticTexts.matching(NSPredicate(format: "identifier BEGINSWITH %@", "transfer-send-"))
        XCTAssertEqual(sends.count, 0)
        let send = app.buttons["send-test-file"]
        reveal(send, in: app)
        send.tap()
        app.buttons["send-test-file-204800"].tap()
        let sent = sends.firstMatch
        XCTAssertTrue(sent.waitForExistence(timeout: 30))
        XCTAssertEqual(sends.count, 1)
        XCTAssertNotNil(sent.identifier.range(
            of: "^transfer-send-ios-test-200-KiB-[0-9]+\\.bin$", options: .regularExpression
        ))
        XCTAssertTrue(waitForCompleted(sent))
        reveal(sent, in: app)
        attach(app, named: "swift-to-jvm-sender-completed")

        let offeredSize = app.staticTexts["offer-size-\(incomingName)"]
        XCTAssertTrue(offeredSize.waitForExistence(timeout: 30))
        // This is the human-facing rounded label; the controller independently
        // requires both exact 204800-byte committed files and transfer evidence.
        XCTAssertEqual(offeredSize.label, "200 KB — waiting for consent")
        let received = app.staticTexts["transfer-receive-\(incomingName)"]
        XCTAssertFalse(received.exists, "The real incoming offer must await the Accept control")
        let accept = app.buttons["accept-offer-\(incomingName)"]
        reveal(accept, in: app)
        attach(app, named: "jvm-to-swift-real-offer-before-consent")
        accept.tap()
        XCTAssertTrue(received.waitForExistence(timeout: 30))
        XCTAssertTrue(waitForCompleted(received))
        XCTAssertTrue(app.staticTexts["sha256 \(incomingName): \(receiverHash)"].waitForExistence(timeout: 10))
        reveal(received, in: app)
        attach(app, named: "jvm-to-swift-durable-receiver-completed")

        let stop = app.buttons["stop-kit"]
        reveal(stop, in: app, towardBottom: false)
        stopAttempted = true
        stop.tap()
        XCTAssertTrue(waitForLabel("Status: Stopped", on: app.staticTexts["sample-status"], timeout: 30))
        XCTAssertTrue(start.exists)
        attach(app, named: "real-swift-stop-after-bidirectional-transfer")
    }

    private func required(_ key: String, in environment: [String: String], matching pattern: String) throws -> String {
        let value = try XCTUnwrap(environment[key], "Required real-peer fixture is missing: \(key)")
        XCTAssertNotNil(value.range(of: "^\(pattern)$", options: .regularExpression), "Invalid fixture: \(key)")
        return value
    }

    @MainActor
    private func replace(_ field: XCUIElement, with value: String, in app: XCUIApplication) {
        reveal(field, in: app)
        field.tap()
        if let previous = field.value as? String, previous != field.placeholderValue {
            field.typeText(String(repeating: XCUIKeyboardKey.delete.rawValue, count: previous.count))
        }
        field.typeText(value)
        XCTAssertEqual(field.value as? String, value)
    }

    @MainActor
    private func dismissMainKeyboard(in app: XCUIApplication) {
        let done = app.buttons["Done"]
        if done.exists { done.tap() }
    }

    @MainActor
    private func waitForLabel(_ label: String, on element: XCUIElement, timeout: TimeInterval) -> Bool {
        let expectation = XCTNSPredicateExpectation(predicate: NSPredicate(format: "label == %@", label), object: element)
        return XCTWaiter.wait(for: [expectation], timeout: timeout) == .completed
    }

    @MainActor
    private func waitForCompleted(_ element: XCUIElement) -> Bool {
        let expectation = XCTNSPredicateExpectation(
            predicate: NSPredicate(format: "label BEGINSWITH %@", "Completed — "), object: element
        )
        return XCTWaiter.wait(for: [expectation], timeout: 30) == .completed
    }

    @MainActor
    private func scrollTo(_ element: XCUIElement, in app: XCUIApplication, towardBottom: Bool) {
        for _ in 0..<6 {
            if element.isHittable { return }
            if towardBottom { app.swipeUp() } else { app.swipeDown() }
        }
    }

    @MainActor
    private func reveal(_ element: XCUIElement, in app: XCUIApplication, towardBottom: Bool = true) {
        scrollTo(element, in: app, towardBottom: towardBottom)
        XCTAssertTrue(element.isHittable, "The actual production control must be reachable")
    }

    @MainActor
    private func attach(_ app: XCUIApplication, named name: String) {
        let screenshot = XCTAttachment(screenshot: app.screenshot())
        screenshot.name = name
        screenshot.lifetime = .keepAlways
        add(screenshot)
    }
}
