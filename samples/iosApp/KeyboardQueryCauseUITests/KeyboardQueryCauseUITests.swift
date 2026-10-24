import CoreFoundation
import CoreGraphics
import Foundation
import XCTest

// Investigation only. This target does not replace, retry, or qualify the
// ordinary locale tests. A recorded baseline refusal is data, not a product
// PASS. In particular, no cell types text or substitutes another key for the
// first character of the original Host input.
final class KeyboardQueryCauseUITests: XCTestCase {
    private let readinessSeconds: TimeInterval = 5
    private let originalHostInput = "127.0.0.1"
    // CFNotificationCenter does not retain its observer context or promise a
    // drain of in-flight callbacks on removal. Keep at most 12 removed contexts
    // for this runner process's lifetime, not just one XCTestCase instance.
    @MainActor private static var retainedAcknowledgements: [KeyboardQueryGateAcknowledgements] = []

    private enum Mode: String, CaseIterable {
        case baseline, nativeWait
    }

    private struct Cell {
        let name: String
        let delay: String
        let mustRefuse: Bool
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
        let signalStarted: TimeInterval
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
    func test00PredicateSchedulingCalibration() {
        continueAfterFailure = false
        // Run in the same native UI-test runner/actor, without launching the
        // app or warming a keyboard. A sleeping predicate is a calibration of
        // the waiter, NOT evidence that a native exists query sleeps, samples
        // at its start, or uses the same run-loop/cancellation mechanism.
        for name in ["fastPositive", "alwaysFalse", "sampleBeforeDelay", "sampleAfterDelay"] {
            let publication = KeyboardQueryPublication()
            var evaluations = 0
            var callbacks: [(start: TimeInterval, end: TimeInterval, before: Bool, after: Bool, returned: Bool)] = []
            let expectation = XCTNSPredicateExpectation(predicate: NSPredicate { _, _ in
                evaluations += 1
                let callbackStarted = ProcessInfo.processInfo.systemUptime
                let before = publication.publishedAt != nil
                if evaluations == 1 && (name == "sampleBeforeDelay" || name == "sampleAfterDelay") {
                    Thread.sleep(forTimeInterval: 4.314392833333159)
                }
                let after = publication.publishedAt != nil
                let returned = name == "alwaysFalse" ? false : (name == "sampleBeforeDelay" ? before : after)
                if callbacks.count < 16 {
                    callbacks.append((callbackStarted, ProcessInfo.processInfo.systemUptime, before, after, returned))
                }
                return returned
            }, object: nil)
            let scheduledAt = ProcessInfo.processInfo.systemUptime
            if name != "alwaysFalse" {
                DispatchQueue.global(qos: .userInitiated).asyncAfter(deadline: .now() + 2) {
                    publication.publish()
                }
            }
            let started = ProcessInfo.processInfo.systemUptime
            let result = XCTWaiter.wait(for: [expectation], timeout: 5)
            let ended = ProcessInfo.processInfo.systemUptime
            print("KEYBOARD_QUERY_CAUSE_SCHEDULER name=\(name) scheduledAtUptime=\(scheduledAt) " +
                "waitStartedUptime=\(started) deadlineUptime=\(started + readinessSeconds) " +
                "publishedAtUptime=\(finite(publication.publishedAt)) waitEndedUptime=\(ended) " +
                "waiter=\(result.rawValue) evaluations=\(evaluations) " +
                "nativeQueryProof=false productQualification=false diagnosticOnly=true")
            for (index, callback) in callbacks.enumerated() {
                print("KEYBOARD_QUERY_CAUSE_SCHEDULER_CALLBACK name=\(name) ordinal=\(index + 1) " +
                    "startedUptime=\(callback.start) endedUptime=\(callback.end) " +
                    "before=\(callback.before) after=\(callback.after) returned=\(callback.returned)")
            }
            if name == "fastPositive" { XCTAssertEqual(result, .completed, "The fast scheduler positive control must complete") }
            if name == "alwaysFalse" { XCTAssertEqual(result, .timedOut, "An always-false predicate cannot be admitted") }
        }
    }

    @MainActor
    func test01CachedExistencePreservesStrictGeometryGuards() {
        // Pure reducer negatives, explicitly not claims about native key
        // geometry. The actual UI cells below always read the real key frame.
        let invalid = [CGRect.null, CGRect.infinite, CGRect.zero,
                       CGRect(x: CGFloat.nan, y: 0, width: 30, height: 40)]
        for bounds in invalid {
            var hits = 0
            let observation = KeyboardReadiness.observeInput([0], exists: { _ in true }, frame: { _ in bounds },
                isHittable: { _ in hits += 1; return true })
            XCTAssertEqual(observation.state, .indeterminate)
            XCTAssertEqual(observation.invalidGeometry, 1)
            XCTAssertEqual(hits, 0)
        }
        let absent = KeyboardReadiness.observeInput([0], exists: { _ in false }, frame: { _ in
            XCTFail("A negative native existence result must not request a frame")
            return .zero
        }, isHittable: { _ in
            XCTFail("A negative native existence result must not request a hit test")
            return true
        })
        XCTAssertEqual(absent.state, .notHittable)
        XCTAssertEqual(absent.existing, 0)
        let visible = CGRect(x: 10, y: 200, width: 32, height: 40)
        let covered = KeyboardReadiness.observeInput([0], exists: { _ in true }, frame: { _ in visible },
                                                     isHittable: { _ in false })
        XCTAssertEqual(covered.state, .notHittable)
        XCTAssertEqual(covered.hitTests, 1)
        XCTAssertEqual(covered.hittable, 0)
    }

    @MainActor
    func test10ActualProductionHostQueryMatrix() throws {
        continueAfterFailure = false
        guard Self.retainedAcknowledgements.isEmpty else {
            XCTFail("This bounded matrix must not be retried in the same runner process")
            return
        }
        let firstCharacter = try XCTUnwrap(originalHostInput.first)
        let firstKeyIdentifier = String(firstCharacter)
        let cells = [
            Cell(name: "ready", delay: "0", mustRefuse: false),
            Cell(name: "early", delay: "100", mustRefuse: false),
            Cell(name: "middle", delay: "2000", mustRefuse: false),
            Cell(name: "edge", delay: "3500", mustRefuse: false),
            Cell(name: "never", delay: "never", mustRefuse: true),
            Cell(name: "late", delay: "6000", mustRefuse: true),
        ]
        var measured = 0, baselineRefusals = 0, nativeRefusals = 0
        var readyPositives = 0
        // Deliberately fixed order, not a retry-until-green loop. Each cell has
        // one fresh app process, one Host tap, one verdict, and its own nonce.
        for cell in cells {
            for mode in Mode.allCases {
                let nonce = UUID().uuidString
                let acknowledgements = KeyboardQueryGateAcknowledgements(nonce: nonce)
                Self.retainedAcknowledgements.append(acknowledgements)
                defer { acknowledgements.close() }
                print("KEYBOARD_QUERY_CAUSE_CELL_BEGIN cell=\(cell.name) mode=\(mode.rawValue) " +
                    "nonce=\(nonce) delayMs=\(cell.delay) diagnosticOnly=true")
                try withRunningSample(cell: cell, nonce: nonce) { app in
                    let host = try originalHostPrefix(in: app)
                    acknowledgements.post("install")
                    XCTAssertTrue(waitForAcknowledgement("installed", from: acknowledgements, timeout: 5),
                                  "The exact production Host must acknowledge gate installation before its sole tap")
                    XCTAssertFalse(acknowledgements.has("refused"), "The native gate refused this cell")
                    host.tap()
                    dismissKeyboardIntroductionIfPresent(in: app)

                    let measurement = measure(mode: mode, keyIdentifier: firstKeyIdentifier,
                                              in: app, acknowledgements: acknowledgements)
                    measured += 1
                    if !measurement.completed {
                        if mode == .baseline { baselineRefusals += 1 } else { nativeRefusals += 1 }
                    }
                    if cell.name == "ready", measurement.positiveWithinDeadline { readyPositives += 1 }
                    emit(measurement, cell: cell, mode: mode, nonce: nonce)
                    if !measurement.completed && ["ready", "middle", "edge"].contains(cell.name) {
                        recordPostVerdictFailure(in: app, nonce: nonce)
                    }

                    // The readiness result above is final. This separate IPC
                    // wait witnesses an actual late release; it cannot grant
                    // readiness, repeat the predicate, or send any character.
                    if cell.name == "late" {
                        let diagnosticStarted = ProcessInfo.processInfo.systemUptime
                        let released = waitForAcknowledgement("released", from: acknowledgements, timeout: 8)
                        print("KEYBOARD_QUERY_CAUSE_LATE_ATTESTATION nonce=\(nonce) " +
                            "released=\(released) elapsedSeconds=\(ProcessInfo.processInfo.systemUptime - diagnosticStarted) " +
                            "phase=POST_VERDICT verdictUnchanged=true diagnosticOnly=true")
                        XCTAssertTrue(released, "A late-release cell must not silently become a never-release cell")
                    }
                    acknowledgements.emit()
                    XCTAssertTrue(acknowledgements.has("received"), "The app must acknowledge this nonce's wait command")
                    XCTAssertFalse(acknowledgements.has("refused"), "The native gate refused this cell")
                    if cell.delay == "never" {
                        XCTAssertFalse(acknowledgements.has("released"), "The never-release gate must remain held")
                    }
                    if cell.mustRefuse {
                        XCTAssertFalse(measurement.completed,
                                       "Never-ready and late-ready controls must not be admitted")
                    }
                    if mode == .nativeWait, measurement.completed {
                        XCTAssertTrue(measurement.positiveWithinDeadline,
                                      "Every native-wait positive needs actual geometry/hittability within the same five seconds")
                    }
                }
            }
        }
        XCTAssertEqual(measured, 12)
        print("KEYBOARD_QUERY_CAUSE_MATRIX_COMPLETE measuredCells=\(measured) " +
            "baselineRefusals=\(baselineRefusals) nativeWaitRefusals=\(nativeRefusals) " +
            "readyPositiveControls=\(readyPositives)/2 typedCharacters=0 " +
            "productQualification=false causeEstablished=false diagnosticOnly=true")
        XCTAssertEqual(readyPositives, 2, "Both ungated positive controls must establish a usable fixture")
    }

    @MainActor
    private func measure(mode: Mode, keyIdentifier: String, in app: XCUIApplication,
                         acknowledgements: KeyboardQueryGateAcknowledgements) -> Measurement {
        var evaluations = 0
        var probes: [Probe] = []
        var last: Probe?
        func retain(_ probe: Probe) {
            last = probe
            // Bound emitted observations, not the number of native snapshots
            // inside a public query, nor a non-preemptible native call's time.
            if probes.count < 64 { probes.append(probe) }
        }
        if mode == .baseline {
            // Same named query, reducer, property order, predicate decision,
            // and five-second XCTWaiter as the original enterText. The wrappers
            // only cache timings/results; there is no additional AX query.
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
                retain(probe)
                return observation.state == .hittable
            }, object: nil)
            let signalStarted = ProcessInfo.processInfo.systemUptime
            acknowledgements.post("wait")
            let started = ProcessInfo.processInfo.systemUptime
            let result = XCTWaiter.wait(for: [ready], timeout: 5)
            return Measurement(signalStarted: signalStarted, started: started,
                               ended: ProcessInfo.processInfo.systemUptime, result: result,
                               evaluations: evaluations, probes: probes, last: last)
        }

        let signalStarted = ProcessInfo.processInfo.systemUptime
        acknowledgements.post("wait")
        let started = ProcessInfo.processInfo.systemUptime
        let deadline = started + readinessSeconds
        var result = XCTWaiter.Result.timedOut
        while ProcessInfo.processInfo.systemUptime < deadline {
            evaluations += 1
            var probe = Probe(ordinal: evaluations, started: ProcessInfo.processInfo.systemUptime)
            let key = app.keyboards.keys.matching(identifier: keyIdentifier).firstMatch
            let existsStarted = ProcessInfo.processInfo.systemUptime
            let remaining = deadline - existsStarted
            guard remaining > 0 else {
                probe.ended = ProcessInfo.processInfo.systemUptime
                retain(probe)
                break
            }
            probe.existsStarted = existsStarted
            // Public nonzero wait, not an assumed existsNoRetry spelling or
            // waitForExistence(0). Its entire allowance comes from ONE deadline.
            let present = key.waitForExistence(timeout: remaining)
            let existsEnded = ProcessInfo.processInfo.systemUptime
            probe.existsEnded = existsEnded
            probe.exists = present
            if !present || existsEnded < deadline {
                let observation = KeyboardReadiness.observeInput([key], exists: { _ in
                    // This is the public native wait's actual return, not a
                    // second ordinary exists getter or fabricated readiness.
                    present
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
            }
            probe.ended = ProcessInfo.processInfo.systemUptime
            retain(probe)
            if probe.observation?.state == .hittable,
               let ended = probe.ended, ended <= deadline {
                result = .completed
                break
            }
            if !present { break }
            // Exists-but-transitioning is not success. A further fresh named
            // probe may use only the remaining original budget, never a new 5s.
        }
        return Measurement(signalStarted: signalStarted, started: started,
                           ended: ProcessInfo.processInfo.systemUptime, result: result,
                           evaluations: evaluations, probes: probes, last: last)
    }

    private func emit(_ measurement: Measurement, cell: Cell, mode: Mode, nonce: String) {
        let deadline = measurement.started + readinessSeconds
        let guardEndedLate = measurement.last?.ended.map { $0 > deadline } ?? false
        let hitStartedLate = measurement.last?.hitStarted.map { $0 > deadline } ?? false
        print("KEYBOARD_QUERY_CAUSE_VERDICT cell=\(cell.name) mode=\(mode.rawValue) nonce=\(nonce) " +
            "signalPostStartedUptime=\(measurement.signalStarted) waitStartedUptime=\(measurement.started) " +
            "deadlineUptime=\(measurement.started + readinessSeconds) waitEndedUptime=\(measurement.ended) " +
            "waiter=\(mode == .baseline ? String(measurement.result.rawValue) : "NOT_USED") " +
            "admissionResult=\(measurement.result.rawValue) admitted=\(measurement.completed) " +
            "positiveWithinDeadline=\(measurement.positiveWithinDeadline) evaluations=\(measurement.evaluations) " +
            "guardEndedAfterDeadline=\(guardEndedLate) hitStartedAfterDeadline=\(hitStartedLate) " +
            "waitOverrunSeconds=\(max(0, measurement.ended - deadline)) " +
            "retainedProbes=\(measurement.probes.count) " +
            "probesTruncated=\(measurement.evaluations > measurement.probes.count) " +
            "typedCharacters=0 productQualification=false diagnosticOnly=true " +
            (measurement.last?.observation?.diagnostic ?? "state=GUARDS_NOT_OBSERVED"))
        for probe in measurement.probes {
            print("KEYBOARD_QUERY_CAUSE_PROBE nonce=\(nonce) ordinal=\(probe.ordinal) " +
                "startedUptime=\(probe.started) existsStartedUptime=\(finite(probe.existsStarted)) " +
                "existsEndedUptime=\(finite(probe.existsEnded)) exists=\(probe.exists.map { String($0) } ?? "UNAVAILABLE") " +
                "frameStartedUptime=\(finite(probe.frameStarted)) frameEndedUptime=\(finite(probe.frameEnded)) " +
                "hitStartedUptime=\(finite(probe.hitStarted)) hitEndedUptime=\(finite(probe.hitEnded)) " +
                "endedUptime=\(finite(probe.ended)) " +
                (probe.observation?.diagnostic ?? "state=GUARDS_NOT_OBSERVED"))
        }
    }

    @MainActor
    private func recordPostVerdictFailure(in app: XCUIApplication, nonce: String) {
        // The verdict is already emitted and immutable. These later native
        // queries can expose a delayed introduction or hierarchy confound but
        // cannot establish the key's state during the preceding five seconds.
        // The investigative runner retains stdout only in encrypted evidence.
        print("KEYBOARD_QUERY_CAUSE_FAILURE_DIAGNOSTIC_BEGIN nonce=\(nonce) " +
            "phase=POST_VERDICT verdictUnchanged=true diagnosticOnly=true")
        let introductionStarted = ProcessInfo.processInfo.systemUptime
        let introductionPresent = app.staticTexts["Type English and German"].exists
        let introductionEnded = ProcessInfo.processInfo.systemUptime
        print("KEYBOARD_QUERY_CAUSE_INTRODUCTION nonce=\(nonce) phase=POST_VERDICT " +
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
        print("KEYBOARD_QUERY_CAUSE_AX_BODY nonce=\(nonce) phase=POST_VERDICT " +
            "bytes=\(prefixLength) truncated=\(truncated) queryElapsedSeconds=\(finite(elapsed)) " +
            "nativeQueryTimeBounded=false diagnosticOnly=true")
        print(String(decoding: snapshotBytes.prefix(prefixLength), as: UTF8.self))
        print("KEYBOARD_QUERY_CAUSE_FAILURE_DIAGNOSTIC_END nonce=\(nonce) diagnosticOnly=true")
    }

    private func finite(_ value: TimeInterval?) -> String {
        guard let value = value, value.isFinite, value >= 0 else { return "UNAVAILABLE" }
        return String(value)
    }

    @MainActor
    private func withRunningSample(cell: Cell, nonce: String,
                                   check: (XCUIApplication) throws -> Void) rethrows {
        let app = XCUIApplication()
        app.launchArguments = ["-AppleLanguages", "(en)", "-AppleLocale", "en_US",
                               "--p2pkit-ui-test-keyboard-cause-probe",
                               "--p2pkit-ui-test-keyboard-query-gate"]
        app.launchEnvironment["P2PKIT_KEYBOARD_QUERY_NONCE"] = nonce
        app.launchEnvironment["P2PKIT_KEYBOARD_QUERY_DELAY_MS"] = cell.delay
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
        app.tap()
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
    private func originalHostPrefix(in app: XCUIApplication) throws -> XCUIElement {
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
        let host = app.textFields["Host (e.g. 192.168.1.42)"]
        reveal(host, in: app, towardBottom: true)
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
    private func dismissKeyboardIntroductionIfPresent(in app: XCUIApplication) {
        let introduction = app.staticTexts["Type English and German"]
        let present = introduction.exists
        print("KEYBOARD_QUERY_CAUSE_INTRODUCTION phase=PRE_WAIT present=\(present) atomicWithReadiness=false diagnosticOnly=true")
        guard present else { return }
        XCTAssertTrue(app.staticTexts["Type both languages on the same keyboard. Customize in Settings."].exists)
        let proceed = app.buttons["Continue"]
        XCTAssertTrue(proceed.isHittable, "The identified keyboard introduction must be reachable")
        XCTContext.runActivity(named: "Dismiss the known first-use bilingual keyboard introduction") { _ in
            proceed.tap()
            let absent = XCTNSPredicateExpectation(predicate: NSPredicate(format: "exists == false"), object: introduction)
            XCTAssertEqual(XCTWaiter.wait(for: [absent], timeout: 5), .completed)
        }
    }

    @MainActor
    private func waitForAcknowledgement(_ event: String, from acknowledgements: KeyboardQueryGateAcknowledgements,
                                        timeout: TimeInterval) -> Bool {
        let received = XCTNSPredicateExpectation(predicate: NSPredicate { _, _ in
            acknowledgements.has(event) || acknowledgements.has("refused")
        }, object: nil)
        return XCTWaiter.wait(for: [received], timeout: timeout) == .completed && acknowledgements.has(event)
    }
}

// Every mutable publication access is protected by the lock; this box alone,
// not XCTest or an XCUIElement, crosses the background scheduling boundary.
private final class KeyboardQueryPublication: @unchecked Sendable {
    private let lock = NSLock()
    private var timestamp: TimeInterval?

    var publishedAt: TimeInterval? {
        lock.lock()
        defer { lock.unlock() }
        return timestamp
    }

    func publish() {
        lock.lock()
        timestamp = ProcessInfo.processInfo.systemUptime
        lock.unlock()
    }
}

private final class KeyboardQueryGateAcknowledgements {
    private let center = CFNotificationCenterGetDarwinNotifyCenter()
    private let lock = NSLock()
    private let nonce: String
    private let prefix: String
    private let events = ["installed", "received", "released", "refused"]
    private var timestamps: [String: TimeInterval] = [:]
    private var counts: [String: Int] = [:]
    private var active = true

    init(nonce: String) {
        self.nonce = nonce
        prefix = "dev.p2pkit.sample.keyboard-query-gate.\(nonce)."
        for event in events {
            CFNotificationCenterAddObserver(center, Unmanaged.passUnretained(self).toOpaque(),
                { _, observer, name, _, _ in
                    guard let observer = observer, let name = name else { return }
                    let receiver = Unmanaged<KeyboardQueryGateAcknowledgements>.fromOpaque(observer).takeUnretainedValue()
                    receiver.receive(name.rawValue as String)
                }, (prefix + event) as CFString, nil, .deliverImmediately)
        }
    }

    func post(_ command: String) {
        precondition(command == "install" || command == "wait")
        CFNotificationCenterPostNotification(center, CFNotificationName(rawValue: (prefix + command) as CFString),
                                             nil, nil, true)
    }

    private func receive(_ name: String) {
        let now = ProcessInfo.processInfo.systemUptime
        lock.lock()
        defer { lock.unlock() }
        guard active, let event = events.first(where: { prefix + $0 == name }) else { return }
        if timestamps[event] == nil { timestamps[event] = now }
        counts[event, default: 0] += 1
    }

    func has(_ event: String) -> Bool {
        lock.lock()
        defer { lock.unlock() }
        return timestamps[event] != nil
    }

    func emit() {
        lock.lock()
        let recordedTimes = timestamps
        let recordedCounts = counts
        lock.unlock()
        for event in events {
            let timestamp = recordedTimes[event].map { String($0) } ?? "UNAVAILABLE"
            print("KEYBOARD_QUERY_CAUSE_ACK nonce=\(nonce) event=\(event) " +
                "runnerObservedUptime=\(timestamp) count=\(recordedCounts[event, default: 0]) " +
                "isAppReceiptOrReleaseClock=false diagnosticOnly=true")
        }
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
