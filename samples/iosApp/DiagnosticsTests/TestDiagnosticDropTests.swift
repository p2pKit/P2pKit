import Foundation
import XCTest
@testable import P2pKitSample

final class TestDiagnosticDropTests: XCTestCase {
    @MainActor
    func testSessionEvictionsNeverContaminateTheCleanSessionOrItsActualExport() throws {
        let fixture = try DropFixture()
        defer { fixture.cleanup() }
        let store = fixture.store(maximumEvents: 6)
        store.startSession(testId: "PS-T01", requestedSessionId: "session-a", role: "both")
        for _ in 0..<8 { store.record(Self.event) }
        store.complete(.success, reason: "done")
        XCTAssertEqual(summary(store, session: "session-a").droppedEventCount, 5)
        store.startSession(testId: "PS-T02", requestedSessionId: "session-b", role: "both")
        store.complete(.success, reason: "done")
        XCTAssertEqual(summary(store, session: "session-a").droppedEventCount, 8)
        XCTAssertEqual(summary(store, session: "session-b").droppedEventCount, 0)

        let archive = try Data(contentsOf: store.exportEvidence())
        // SimpleEvidenceZip stores entries uncompressed. droppedEventCount occurs only in summary.json.
        XCTAssertNotNil(archive.range(of: Data("\"droppedEventCount\":0,".utf8)))
        XCTAssertEqual(summary(store, session: "session-a").droppedEventCount, 9)
        XCTAssertEqual(summary(store, session: "session-b").droppedEventCount, 0)
    }

    @MainActor
    func testSinkFailureInOneSessionDoesNotInflateAnotherSession() throws {
        let fixture = try DropFixture()
        defer { fixture.cleanup() }
        let store = fixture.store()
        store.startSession(testId: "PS-T01", requestedSessionId: "session-a", role: "both")
        try fixture.obstructLogs()
        store.record(Self.event)
        XCTAssertEqual(summary(store, session: "session-a").droppedEventCount, 1)
        try fixture.restoreLogs()
        store.complete(.success, reason: "done")
        store.startSession(testId: "PS-T02", requestedSessionId: "session-b", role: "both")
        store.complete(.success, reason: "done")
        XCTAssertEqual(summary(store, session: "session-a").droppedEventCount, 1)
        XCTAssertEqual(summary(store, session: "session-b").droppedEventCount, 0)
        let archive = try Data(contentsOf: store.exportEvidence())
        XCTAssertNotNil(archive.range(of: Data("\"droppedEventCount\":0,".utf8)))
        XCTAssertEqual(summary(store, session: "session-a").droppedEventCount, 1)
    }

    @MainActor
    func testFailedClearRetainsTheCountAndSuccessfulRetryResetsOnlyItsSession() throws {
        let fixture = try DropFixture()
        defer { fixture.cleanup() }
        let store = fixture.store()
        store.startSession(testId: "PS-T01", requestedSessionId: "selected", role: "both")
        try fixture.obstructLogs()
        store.record(Self.event)
        let before = store.events
        XCTAssertEqual(summary(store, session: "selected").droppedEventCount, 1)
        XCTAssertThrowsError(try store.clearCurrentSession())
        XCTAssertEqual(store.events, before)
        XCTAssertEqual(summary(store, session: "selected").droppedEventCount, 1)
        XCTAssertEqual(try Data(contentsOf: fixture.logs), Data("synthetic log obstruction".utf8))
        try fixture.restoreLogs()
        XCTAssertEqual(try store.clearCurrentSession(), before.filter { $0.testSessionId == "selected" }.count)
        XCTAssertEqual(store.makeSummary([], manual: []).droppedEventCount, 0)
        store.record(Self.event)
        XCTAssertEqual(summary(store, session: "selected").droppedEventCount, 0)
    }

    @MainActor
    func testReusingAStillRetainedSessionIdDoesNotHideItsLosses() throws {
        let fixture = try DropFixture()
        defer { fixture.cleanup() }
        let store = fixture.store()
        store.startSession(testId: "PS-T01", requestedSessionId: "session-a", role: "both")
        try fixture.obstructLogs()
        store.record(Self.event)
        try fixture.restoreLogs()
        store.startSession(testId: "PS-T01", requestedSessionId: "session-b", role: "both")
        store.startSession(testId: "PS-T01", requestedSessionId: "session-a", role: "both")
        XCTAssertEqual(summary(store, session: "session-a").droppedEventCount, 1)
        XCTAssertEqual(summary(store, session: "session-b").droppedEventCount, 0)
    }

    @MainActor
    private func summary(_ store: IOSTestDiagnosticStore, session: String) -> TestDiagnosticSummary {
        store.makeSummary(store.events.filter { $0.testSessionId == session }, manual: [])
    }

    private static let event = TestDiagnosticRecord(category: "test", eventName: "test.synthetic")
}

private final class DropFixture {
    let root: URL
    let logs: URL
    let defaults: UserDefaults
    private let suite = "p2pkit-drops-\(UUID().uuidString)"

    init() throws {
        root = FileManager.default.temporaryDirectory.appendingPathComponent(suite, isDirectory: true)
        logs = root.appendingPathComponent("logs", isDirectory: true)
        defaults = UserDefaults(suiteName: suite)!
        defaults.removePersistentDomain(forName: suite)
        try FileManager.default.createDirectory(at: root, withIntermediateDirectories: true)
    }

    @MainActor
    func store(maximumEvents: Int = 100) -> IOSTestDiagnosticStore {
        IOSTestDiagnosticStore(
            baseDirectory: logs,
            evidenceDirectory: root.appendingPathComponent("evidence", isDirectory: true),
            defaults: defaults,
            maximumEvents: maximumEvents
        )
    }

    func obstructLogs() throws {
        try FileManager.default.removeItem(at: logs)
        try Data("synthetic log obstruction".utf8).write(to: logs)
    }

    func restoreLogs() throws {
        try FileManager.default.removeItem(at: logs)
        try FileManager.default.createDirectory(at: logs, withIntermediateDirectories: true)
    }

    func cleanup() {
        try? FileManager.default.removeItem(at: root)
        defaults.removePersistentDomain(forName: suite)
    }
}
