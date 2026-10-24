#if P2PKIT_KEYBOARD_REFLOW_PROBE
import CoreFoundation
import CoreGraphics
import Foundation
import XCTest

// Optional screening, not the ordinary locale test or product qualification.
// Each method observes only the original first Host key's admission predicate;
// neither method sends a character or repairs a failed interaction. Even a
// native receipt needs independent timing review against the retained app log.
final class KeyboardReflowCauseUITests: XCTestCase {
    private let readinessSeconds: TimeInterval = 5
    private let originalHostInput = "127.0.0.1"
    private var dismissedKeyboardIntroduction = false
    @MainActor private static var startedModes: Set<String> = []
    // Darwin notification removal does not promise to drain callbacks. Retain
    // at most two removed observer contexts for the entire UI-runner lifetime.
    @MainActor private static var retainedReceipts: [KeyboardReflowReceipt] = []

    private enum Mode: String {
        case beforeTarget, duringEditing
    }

    private struct Probe {
        let ordinal: Int
        let started: TimeInterval
        var existsStarted: TimeInterval?
        var existsEnded: TimeInterval?
        var exists: Bool?
        var frameStarted: TimeInterval?
        var frameEnded: TimeInterval?
        var hitStarted: TimeInterval?
        var hitEnded: TimeInterval?
        var ended: TimeInterval?
        var observation: KeyboardInputObservation?
    }

    private struct Measurement {
        let started: TimeInterval
        let ended: TimeInterval
        let result: XCTWaiter.Result
        let evaluations: Int
        let probes: [Probe]
        let last: Probe?

        var completed: Bool { result == .completed }
        var positiveWithinDeadline: Bool {
            guard completed, last?.observation?.state == .hittable,
                  let hitEnded = last?.hitEnded else { return false }
            return hitEnded <= started + 5
        }
    }

    @MainActor
    func test00FirstHostBeforeTargetReflow() throws {
        try screen(.beforeTarget)
    }

    @MainActor
    func test01FirstHostDuringEditingReflow() throws {
        try screen(.duringEditing)
    }

    @MainActor
    private func screen(_ mode: Mode) throws {
        continueAfterFailure = false
        guard Self.startedModes.insert(mode.rawValue).inserted,
              Self.retainedReceipts.count < 2 else {
            XCTFail("Each reflow screening mode must run only once in this UI-runner process")
            return
        }
        let firstCharacter = try XCTUnwrap(originalHostInput.first)
        let nonce = UUID().uuidString
        let receipt = KeyboardReflowReceipt(nonce: nonce)
        Self.retainedReceipts.append(receipt)
        defer { receipt.close() }
        var frozenMeasurement: Measurement?
        var nativeReceiptAccepted = false
        print("KEYBOARD_REFLOW_CAUSE_CELL_BEGIN mode=\(mode.rawValue) nonce=\(nonce) " +
            "uptimeSeconds=\(ProcessInfo.processInfo.systemUptime) locale=en_US " +
            "fixtureTimingVerified=false needsNativeLogReview=true productQualification=false diagnosticOnly=true")

        try withRunningSample(mode: mode, nonce: nonce) { app in
            let host = try originalHostPrefix(in: app, mode: mode, nonce: nonce)
            let tapStarted = ProcessInfo.processInfo.systemUptime
            host.tap()
            let tapEnded = ProcessInfo.processInfo.systemUptime
            print("KEYBOARD_REFLOW_CAUSE_HOST_TAP mode=\(mode.rawValue) nonce=\(nonce) " +
                "startedUptime=\(tapStarted) endedUptime=\(tapEnded) tapCount=1 diagnosticOnly=true")
            dismissKeyboardIntroductionIfPresent(in: app, mode: mode, nonce: nonce)

            let measurement = measure(keyIdentifier: String(firstCharacter), in: app)
            frozenMeasurement = measurement
            emit(measurement, mode: mode, nonce: nonce)
            if !measurement.completed {
                // Do not delay the failed-readiness observation for a receipt.
                recordPostVerdictFailure(in: app, mode: mode, nonce: nonce)
            }

            // This one read-only IPC request happens only after the original
            // verdict is frozen and emitted. It cannot trigger the stimulus,
            // rerun readiness, query a banner through AX, or admit a character.
            nativeReceiptAccepted = readPostVerdictReceipt(receipt, measurement: measurement,
                                                           mode: mode, nonce: nonce)
            if measurement.completed && !nativeReceiptAccepted {
                // The branches are disjoint: at most one failure snapshot.
                recordPostVerdictFailure(in: app, mode: mode, nonce: nonce)
            }
        }

        // Keep normal Stop and owned app termination ahead of these cached
        // assertions. Prefix failures still retain the original fail-fast path.
        guard let measurement = frozenMeasurement else {
            XCTFail("The original first Host readiness predicate was not measured")
            return
        }
        print("KEYBOARD_REFLOW_CAUSE_CELL_COMPLETE mode=\(mode.rawValue) nonce=\(nonce) " +
            "uptimeSeconds=\(ProcessInfo.processInfo.systemUptime) readinessCompleted=\(measurement.completed) " +
            "nativeReceiptAccepted=\(nativeReceiptAccepted) typedCharacters=0 " +
            "fixtureTimingVerified=false needsNativeLogReview=true causeEstablished=false " +
            "productQualification=false diagnosticOnly=true")
        XCTAssertTrue(nativeReceiptAccepted,
                      "A missing, inapplicable or invalid native stimulus receipt is not a successful screening")
        XCTAssertEqual(measurement.result, .completed, "Preserve the original five-second first Host readiness result")
    }

    @MainActor
    private func measure(keyIdentifier: String, in app: XCUIApplication) -> Measurement {
        var evaluations = 0
        var probes: [Probe] = []
        var last: Probe?
        // Same fresh named query, reducer, property order, predicate decision
        // and five-second XCTWaiter as original enterText. Cache each native
        // property's result/timing without adding a query or changing admission.
        let ready = XCTNSPredicateExpectation(predicate: NSPredicate { _, _ in
            evaluations += 1
            var probe = Probe(ordinal: evaluations, started: ProcessInfo.processInfo.systemUptime)
            let key = app.keyboards.keys.matching(identifier: keyIdentifier).firstMatch
            let observation = KeyboardReadiness.observeInput([key], exists: { key in
                probe.existsStarted = ProcessInfo.processInfo.systemUptime
                let present = key.exists
                probe.existsEnded = ProcessInfo.processInfo.systemUptime
                probe.exists = present
                return present
            }, frame: { key in
                probe.frameStarted = ProcessInfo.processInfo.systemUptime
                let frame = key.frame
                probe.frameEnded = ProcessInfo.processInfo.systemUptime
                return frame
            }, isHittable: { key in
                probe.hitStarted = ProcessInfo.processInfo.systemUptime
                let hittable = key.isHittable
                probe.hitEnded = ProcessInfo.processInfo.systemUptime
                return hittable
            })
            probe.observation = observation
            probe.ended = ProcessInfo.processInfo.systemUptime
            last = probe
            // This bounds retained rows, not native snapshot count or latency.
            if probes.count < 64 { probes.append(probe) }
            return observation.state == .hittable
        }, object: nil)
        let started = ProcessInfo.processInfo.systemUptime
        let result = XCTWaiter.wait(for: [ready], timeout: 5)
        return Measurement(started: started, ended: ProcessInfo.processInfo.systemUptime,
                           result: result, evaluations: evaluations, probes: probes, last: last)
    }

    private func emit(_ measurement: Measurement, mode: Mode, nonce: String) {
        let deadline = measurement.started + readinessSeconds
        let guardEndedLate = measurement.last?.ended.map { $0 > deadline } ?? false
        let hitStartedLate = measurement.last?.hitStarted.map { $0 > deadline } ?? false
        print("KEYBOARD_REFLOW_CAUSE_VERDICT mode=\(mode.rawValue) nonce=\(nonce) " +
            "waitStartedUptime=\(measurement.started) deadlineUptime=\(deadline) " +
            "waitEndedUptime=\(measurement.ended) frozenAtUptime=\(ProcessInfo.processInfo.systemUptime) " +
            "waiter=\(measurement.result.rawValue) admitted=\(measurement.completed) " +
            "positiveWithinDeadline=\(measurement.positiveWithinDeadline) evaluations=\(measurement.evaluations) " +
            "guardEndedAfterDeadline=\(guardEndedLate) hitStartedAfterDeadline=\(hitStartedLate) " +
            "waitOverrunSeconds=\(max(0, measurement.ended - deadline)) retainedProbes=\(measurement.probes.count) " +
            "probesTruncated=\(measurement.evaluations > measurement.probes.count) typedCharacters=0 " +
            "fixtureTimingVerified=false needsNativeLogReview=true causeEstablished=false " +
            "productQualification=false diagnosticOnly=true " +
            (measurement.last?.observation?.diagnostic ?? "state=NOT_OBSERVED"))
        for probe in measurement.probes {
            print("KEYBOARD_REFLOW_CAUSE_PROBE nonce=\(nonce) ordinal=\(probe.ordinal) " +
                "startedUptime=\(probe.started) existsStartedUptime=\(finite(probe.existsStarted)) " +
                "existsEndedUptime=\(finite(probe.existsEnded)) exists=\(probe.exists.map { String($0) } ?? "UNAVAILABLE") " +
                "frameStartedUptime=\(finite(probe.frameStarted)) frameEndedUptime=\(finite(probe.frameEnded)) " +
                "hitStartedUptime=\(finite(probe.hitStarted)) hitEndedUptime=\(finite(probe.hitEnded)) " +
                "endedUptime=\(finite(probe.ended)) " +
                (probe.observation?.diagnostic ?? "state=NOT_OBSERVED"))
        }
    }

    @MainActor
    private func readPostVerdictReceipt(_ receipt: KeyboardReflowReceipt, measurement: Measurement,
                                        mode: Mode, nonce: String) -> Bool {
        let requested = receipt.requestOnce()
        let deadline = requested + 5
        print("KEYBOARD_REFLOW_CAUSE_RECEIPT_REQUEST mode=\(mode.rawValue) nonce=\(nonce) " +
            "requestedUptime=\(requested) deadlineUptime=\(deadline) cachedWaitEndedUptime=\(measurement.ended) " +
            "phase=POST_VERDICT requestCount=1 readOnly=true verdictUnchanged=true diagnosticOnly=true")
        let reply = XCTNSPredicateExpectation(predicate: NSPredicate { _, _ in receipt.hasReply }, object: nil)
        let remaining = deadline - ProcessInfo.processInfo.systemUptime
        let result: XCTWaiter.Result
        if remaining > 0 {
            result = XCTWaiter.wait(for: [reply], timeout: remaining)
        } else {
            result = .timedOut
        }
        let snapshot = receipt.freeze()
        let ended = ProcessInfo.processInfo.systemUptime
        let acceptedAt = snapshot.timestamps["accepted"]
        let accepted = result == .completed && snapshot.counts["accepted", default: 0] == 1 &&
            snapshot.counts["inapplicable", default: 0] == 0 &&
            acceptedAt.map { $0 >= requested && $0 <= deadline } == true
        for event in ["accepted", "inapplicable"] {
            print("KEYBOARD_REFLOW_CAUSE_RECEIPT_EVENT mode=\(mode.rawValue) nonce=\(nonce) event=\(event) " +
                "runnerObservedUptime=\(finite(snapshot.timestamps[event])) count=\(snapshot.counts[event, default: 0]) " +
                "isNativeStimulusClock=false phase=POST_VERDICT diagnosticOnly=true")
        }
        print("KEYBOARD_REFLOW_CAUSE_RECEIPT_RESULT mode=\(mode.rawValue) nonce=\(nonce) " +
            "endedUptime=\(ended) waiter=\(result.rawValue) accepted=\(accepted) " +
            "overrunSeconds=\(max(0, ended - deadline)) phase=POST_VERDICT verdictUnchanged=true " +
            "fixtureTimingVerified=false needsNativeLogReview=true causeEstablished=false " +
            "productQualification=false diagnosticOnly=true")
        return accepted
    }

    @MainActor
    private func recordPostVerdictFailure(in app: XCUIApplication, mode: Mode, nonce: String) {
        // Exactly one later introduction query and one bounded-output AX getter.
        // Neither can establish an earlier key/focus state or rescue readiness.
        // The investigative runner retains this body only in encrypted evidence.
        print("KEYBOARD_REFLOW_CAUSE_FAILURE_DIAGNOSTIC_BEGIN mode=\(mode.rawValue) nonce=\(nonce) " +
            "phase=POST_VERDICT verdictUnchanged=true diagnosticOnly=true")
        let introductionStarted = ProcessInfo.processInfo.systemUptime
        let introductionPresent = app.staticTexts["Type English and German"].exists
        let introductionEnded = ProcessInfo.processInfo.systemUptime
        print("KEYBOARD_REFLOW_CAUSE_INTRODUCTION mode=\(mode.rawValue) nonce=\(nonce) phase=POST_VERDICT " +
            "present=\(introductionPresent) startedUptime=\(introductionStarted) endedUptime=\(introductionEnded) " +
            "atomicWithReadiness=false diagnosticOnly=true")
        let started = ProcessInfo.processInfo.systemUptime
        let snapshot = app.debugDescription
        let elapsed = ProcessInfo.processInfo.systemUptime - started
        let maximumBytes = 128 * 1024
        let snapshotBytes = Array(snapshot.utf8.prefix(maximumBytes + 1))
        let truncated = snapshotBytes.count > maximumBytes
        var prefixLength = min(snapshotBytes.count, maximumBytes)
        if truncated {
            while prefixLength > 0 && (snapshotBytes[prefixLength] & 0xC0) == 0x80 {
                prefixLength -= 1
            }
        }
        print("KEYBOARD_REFLOW_CAUSE_AX_BODY mode=\(mode.rawValue) nonce=\(nonce) phase=POST_VERDICT " +
            "bytes=\(prefixLength) truncated=\(truncated) queryElapsedSeconds=\(finite(elapsed)) " +
            "nativeQueryTimeBounded=false diagnosticOnly=true")
        print(String(decoding: snapshotBytes.prefix(prefixLength), as: UTF8.self))
        print("KEYBOARD_REFLOW_CAUSE_FAILURE_DIAGNOSTIC_END mode=\(mode.rawValue) nonce=\(nonce) diagnosticOnly=true")
    }

    private func finite(_ value: TimeInterval?) -> String {
        guard let value = value, value.isFinite, value >= 0 else { return "UNAVAILABLE" }
        return String(value)
    }

    @MainActor
    private func withRunningSample(mode: Mode, nonce: String,
                                   check: (XCUIApplication) throws -> Void) rethrows {
        let app = XCUIApplication()
        app.launchArguments = ["-AppleLanguages", "(en)", "-AppleLocale", "en_US",
                               "--p2pkit-ui-test-keyboard-cause-probe",
                               "--p2pkit-ui-test-keyboard-reflow-probe"]
        app.launchEnvironment["P2PKIT_KEYBOARD_REFLOW_NONCE"] = nonce
        app.launchEnvironment["P2PKIT_KEYBOARD_REFLOW_MODE"] = mode.rawValue
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
        start.coordinate(withNormalizedOffset: CGVector(dx: 0.5, dy: 0.5)).tap()
        app.tap() // Deliver any Local Network interruption to the original monitor.
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
    private func originalHostPrefix(in app: XCUIApplication, mode: Mode, nonce: String) throws -> XCUIElement {
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
        screenshot.name = "synthetic-simulator-port-en_US"
        screenshot.lifetime = .keepAlways
        add(screenshot)
        let targetingStarted = ProcessInfo.processInfo.systemUptime
        let host = app.textFields["Host (e.g. 192.168.1.42)"]
        reveal(host, in: app, towardBottom: true)
        print("KEYBOARD_REFLOW_CAUSE_HOST_TARGET mode=\(mode.rawValue) nonce=\(nonce) " +
            "targetingStartedUptime=\(targetingStarted) revealEndedUptime=\(ProcessInfo.processInfo.systemUptime) " +
            "atomicWithNativeLayout=false diagnosticOnly=true")
        return host
    }

    @MainActor
    private func reveal(_ element: XCUIElement, in app: XCUIApplication, towardBottom: Bool) {
        for _ in 0..<6 {
            if element.isHittable { return }
            if towardBottom { app.scrollViews.firstMatch.swipeUp() }
            else { app.scrollViews.firstMatch.swipeDown() }
        }
        XCTAssertTrue(element.isHittable, "The actual production control must be reachable")
    }

    @MainActor
    private func waitForLabel(_ label: String, on element: XCUIElement, timeout: TimeInterval) -> Bool {
        let expectation = XCTNSPredicateExpectation(predicate: NSPredicate(format: "label == %@", label), object: element)
        return XCTWaiter.wait(for: [expectation], timeout: timeout) == .completed
    }

    @MainActor
    private func dismissKeyboardIntroductionIfPresent(in app: XCUIApplication, mode: Mode, nonce: String) {
        let introduction = app.staticTexts["Type English and German"]
        let started = ProcessInfo.processInfo.systemUptime
        let present = introduction.exists
        let ended = ProcessInfo.processInfo.systemUptime
        print("KEYBOARD_REFLOW_CAUSE_INTRODUCTION mode=\(mode.rawValue) nonce=\(nonce) phase=PRE_WAIT " +
            "present=\(present) startedUptime=\(started) endedUptime=\(ended) " +
            "atomicWithReadiness=false diagnosticOnly=true")
        guard present else { return }
        XCTAssertFalse(dismissedKeyboardIntroduction, "An acknowledged system introduction must not be retried")
        XCTAssertTrue(app.staticTexts["Type both languages on the same keyboard. Customize in Settings."].exists)
        let proceed = app.buttons["Continue"]
        XCTAssertTrue(proceed.isHittable, "The identified keyboard introduction must be reachable")
        XCTContext.runActivity(named: "Dismiss the known first-use bilingual keyboard introduction") { _ in
            proceed.tap()
            let absent = XCTNSPredicateExpectation(predicate: NSPredicate(format: "exists == false"), object: introduction)
            XCTAssertEqual(XCTWaiter.wait(for: [absent], timeout: 5), .completed)
        }
        dismissedKeyboardIntroduction = true
    }
}

private final class KeyboardReflowReceipt {
    struct Snapshot {
        let timestamps: [String: TimeInterval]
        let counts: [String: Int]
    }

    private let center = CFNotificationCenterGetDarwinNotifyCenter()
    private let lock = NSLock()
    private let prefix: String
    private let events = ["accepted", "inapplicable"]
    private var timestamps: [String: TimeInterval] = [:]
    private var counts: [String: Int] = [:]
    private var active = true
    private var requested = false

    init(nonce: String) {
        prefix = "dev.p2pkit.sample.keyboard-reflow-probe.\(nonce)."
        for event in events {
            CFNotificationCenterAddObserver(center, Unmanaged.passUnretained(self).toOpaque(),
                { _, observer, name, _, _ in
                    guard let observer, let name else { return }
                    let receiver = Unmanaged<KeyboardReflowReceipt>.fromOpaque(observer).takeUnretainedValue()
                    receiver.receive(name.rawValue as String)
                }, (prefix + event) as CFString, nil, .deliverImmediately)
        }
    }

    func requestOnce() -> TimeInterval {
        lock.lock()
        precondition(active && !requested)
        requested = true
        lock.unlock()
        let started = ProcessInfo.processInfo.systemUptime
        CFNotificationCenterPostNotification(center, CFNotificationName(rawValue: (prefix + "receipt") as CFString),
                                             nil, nil, true)
        return started
    }

    private func receive(_ name: String) {
        let now = ProcessInfo.processInfo.systemUptime
        lock.lock()
        defer { lock.unlock() }
        guard active, let event = events.first(where: { prefix + $0 == name }) else { return }
        if timestamps[event] == nil { timestamps[event] = now }
        counts[event, default: 0] += 1
    }

    var hasReply: Bool {
        lock.lock()
        defer { lock.unlock() }
        return !timestamps.isEmpty
    }

    func freeze() -> Snapshot {
        close()
        lock.lock()
        defer { lock.unlock() }
        return Snapshot(timestamps: timestamps, counts: counts)
    }

    func close() {
        lock.lock()
        let wasActive = active
        active = false
        lock.unlock()
        if wasActive {
            CFNotificationCenterRemoveEveryObserver(center, Unmanaged.passUnretained(self).toOpaque())
        }
    }

    deinit { close() }
}
#endif
