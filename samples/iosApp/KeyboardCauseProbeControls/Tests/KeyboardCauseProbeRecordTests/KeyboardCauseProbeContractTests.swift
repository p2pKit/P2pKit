import CoreGraphics
import Foundation
import XCTest
@testable import KeyboardCauseProbeRecord

final class KeyboardCauseProbeContractTests: XCTestCase {
    func testFieldVocabularyCannotExposeUnexpectedPlaceholders() {
        XCTAssertEqual(KeyboardCauseProbeField(placeholder: "Host (e.g. 192.168.1.42)"), .host)
        XCTAssertEqual(KeyboardCauseProbeField(placeholder: "Port"), .port)
        XCTAssertEqual(KeyboardCauseProbeField(placeholder: "Peer pairing QR text (p2pkit:v2:…)"), .pairing)
        for value in [nil, "untrusted-private-value"] {
            let field = KeyboardCauseProbeField(placeholder: value)
            XCTAssertEqual(field, .other)
            XCTAssertFalse(record(field: field).line.contains("untrusted-private-value"))
        }
    }

    func testEventBudgetEmitsOneTerminalMarkerWithoutRearming() {
        var budget = KeyboardCauseProbeBudget()
        for sequence in 1...KeyboardCauseProbeBudget.maximumEvents {
            let admitted = budget.admit(.keyboardWillChangeFrame)
            XCTAssertEqual(admitted?.0, sequence)
            XCTAssertEqual(admitted?.1, .keyboardWillChangeFrame)
        }
        let terminal = budget.admit(.editingBegan)
        XCTAssertEqual(terminal?.0, KeyboardCauseProbeBudget.maximumEvents + 1)
        XCTAssertEqual(terminal?.1, .limitReached)
        for _ in 0..<100 {
            XCTAssertNil(budget.admit(.keyboardDidShow))
        }
    }

    func testGeometryIsObservationOnlyAndNeverPrintsNonfiniteNumbers() {
        for bounds in [CGRect.null, CGRect.infinite,
                       CGRect(x: CGFloat.nan, y: 0, width: 1, height: 1),
                       CGRect(x: 0, y: 0, width: CGFloat.infinity, height: 1),
                       CGRect(x: 0, y: 0, width: 1, height: -1)] {
            let line = record(frame: bounds).line
            XCTAssertTrue(line.contains("keyboardFrame=INVALID"))
            XCTAssertFalse(line.contains("nan"))
            XCTAssertFalse(line.contains("inf"))
        }
        // Offscreen or zero-height frames are meaningful hardware/transition
        // observations, not positive proof of an interactive software key.
        XCTAssertTrue(record(frame: CGRect(x: 0, y: 900, width: 400, height: 0)).line
            .contains("keyboardFrame=0.0,900.0,400.0,0.0"))
        XCTAssertTrue(record().line.contains("keyboardFrame=UNAVAILABLE"))
    }

    func testClockAndFocusUseExplicitUnknownValues() {
        for uptime in [Double.nan, Double.infinity, -1] {
            XCTAssertTrue(record(uptime: uptime).line.contains("uptimeSeconds=UNAVAILABLE"))
        }
        let line = record(uptime: 12.5).line
        XCTAssertTrue(line.contains("uptimeSeconds=12.5"))
        XCTAssertTrue(line.contains("firstResponder=UNAVAILABLE"))
        XCTAssertTrue(line.contains("keyboardIsLocal=UNAVAILABLE"))
        XCTAssertTrue(line.contains("windowBounds=UNAVAILABLE"))
    }

    private func record(
        field: KeyboardCauseProbeField = .none,
        frame: CGRect? = nil,
        uptime: TimeInterval = 0
    ) -> KeyboardCauseProbeRecord {
        KeyboardCauseProbeRecord(sequence: 1, event: .armed, uptime: uptime, field: field,
            firstResponder: nil, keyboardIsLocal: nil, keyboardFrame: frame, windowBounds: nil)
    }
}
