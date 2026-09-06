import Foundation
import XCTest
@testable import P2pKitSample

final class TestDiagnosticClearTests: XCTestCase {
    @MainActor
    func testExactDecodedSessionSelectionPreservesEveryUnrelatedByte() throws {
        let fixture = try ClearFixture()
        defer { fixture.cleanup() }
        let store = fixture.store()
        store.startSession(testId: "PS-T01", requestedSessionId: "selected", role: "both")
        let retained = Data((
            "\r\n{\"testSessionId\":\"Selected\"}\r\n" +
            "{\"testSessionId\":\"selected-other\"}\n" +
            "{\"testSessionId\":null}\n{\"testSessionId\":3}\n[\"selected\"]\n" +
            "{\"testSessionId\":\"other\",\"extra\":{\"testSessionId\":\"selected\"}}\n"
        ).utf8) + Data([0xc3, 0x28]) + Data((
            "{\"testSessionId\":\"selected\"}\ntruncated: \"testSessionId\":\"selected\""
        ).utf8)
        let selected = Data("{\"testSession\\u0049d\" : \"selec\\u0074ed\"}\r\n".utf8)
        for name in fixture.names { try (selected + retained).write(to: fixture.logs.appendingPathComponent(name)) }

        XCTAssertEqual(try store.clearCurrentSession(), 2)

        for name in fixture.names {
            XCTAssertEqual(try Data(contentsOf: fixture.logs.appendingPathComponent(name)), retained)
        }
        XCTAssertTrue(store.events.allSatisfy { $0.testSessionId != "selected" })
    }

    @MainActor
    func testReadFailureKeepsMemoryAndUnrelatedHistoryDespiteEarlierFileCommit() throws {
        let fixture = try ClearFixture()
        defer { fixture.cleanup() }
        let store = fixture.store()
        store.startSession(testId: "PS-T01", requestedSessionId: "selected", role: "both")
        let before = store.events
        let selected = Data("{\"testSessionId\":\"selected\"}\n".utf8)
        let other = Data("{\"testSessionId\":\"other\"}\r\n".utf8)
        let active = fixture.logs.appendingPathComponent("events.jsonl")
        let unreadable = fixture.logs.appendingPathComponent("events.1.jsonl")
        try (selected + other).write(to: active)
        try (selected + other).write(to: unreadable)
        let permissions = try FileManager.default.attributesOfItem(atPath: unreadable.path)[.posixPermissions]!
        defer { try? FileManager.default.setAttributes([.posixPermissions: permissions], ofItemAtPath: unreadable.path) }
        try FileManager.default.setAttributes([.posixPermissions: 0], ofItemAtPath: unreadable.path)

        XCTAssertThrowsError(try store.clearCurrentSession()) { error in
            XCTAssertEqual((error as NSError).code, CocoaError.fileReadNoPermission.rawValue)
        }
        XCTAssertEqual(store.events, before)
        XCTAssertEqual(try Data(contentsOf: active), other, "first file already committed; memory must still be retained")
        try FileManager.default.setAttributes([.posixPermissions: permissions], ofItemAtPath: unreadable.path)
        XCTAssertEqual(try Data(contentsOf: unreadable), selected + other)
        XCTAssertEqual(try store.clearCurrentSession(), before.filter { $0.testSessionId == "selected" }.count)
        XCTAssertEqual(try Data(contentsOf: unreadable), other)
    }

    @MainActor
    func testAtomicWriteFailurePreservesOriginalAndCleansOnlyOwnedStaging() throws {
        let fixture = try ClearFixture()
        defer { fixture.cleanup() }
        let store = fixture.store()
        store.startSession(testId: "PS-T01", requestedSessionId: "selected", role: "both")
        let active = fixture.logs.appendingPathComponent("events.jsonl")
        let beforeBytes = try Data(contentsOf: active)
        let beforeEvents = store.events
        let unrelated = fixture.logs.appendingPathComponent("unrelated-staging.tmp")
        try Data("preserve unrelated".utf8).write(to: unrelated)
        let names = try FileManager.default.contentsOfDirectory(atPath: fixture.logs.path).sorted()
        let permissions = try FileManager.default.attributesOfItem(atPath: fixture.logs.path)[.posixPermissions]!
        defer { try? FileManager.default.setAttributes([.posixPermissions: permissions], ofItemAtPath: fixture.logs.path) }
        try FileManager.default.setAttributes([.posixPermissions: 0o500], ofItemAtPath: fixture.logs.path)

        XCTAssertThrowsError(try store.clearCurrentSession()) { error in
            XCTAssertEqual((error as NSError).code, CocoaError.fileWriteNoPermission.rawValue)
        }
        XCTAssertEqual(store.events, beforeEvents)
        XCTAssertEqual(try Data(contentsOf: active), beforeBytes)
        XCTAssertEqual(try Data(contentsOf: unrelated), Data("preserve unrelated".utf8))
        XCTAssertEqual(try FileManager.default.contentsOfDirectory(atPath: fixture.logs.path).sorted(), names)
        try FileManager.default.setAttributes([.posixPermissions: permissions], ofItemAtPath: fixture.logs.path)
        XCTAssertEqual(try store.clearCurrentSession(), beforeEvents.filter { $0.testSessionId == "selected" }.count)
    }

    @MainActor
    func testActualConfirmationPreservesSelectionAndPausedStateOnFailureAndSupportsRetry() throws {
        let fixture = try ClearFixture()
        defer { fixture.cleanup() }
        let store = fixture.store()
        store.startSession(testId: "PS-T01", requestedSessionId: "selected", role: "both")
        let before = store.events
        var selected = Set(before.map(\.index))
        store.displayPaused = true
        var failure: String?
        let obstruction = fixture.logs.appendingPathComponent("events.1.jsonl", isDirectory: true)
        try FileManager.default.createDirectory(at: obstruction, withIntermediateDirectories: false)
        let confirmed: (Int) -> Void = { count in
            XCTAssertEqual(count, before.filter { $0.testSessionId == "selected" }.count)
            selected.removeAll()
            failure = nil
        }

        try store.confirmClearCurrentSession(onCleared: confirmed, onFailure: { failure = $0 })

        XCTAssertEqual(failure, TestDiagnosticClearAction.failureMessage)
        XCTAssertEqual(selected, Set(before.map(\.index)))
        XCTAssertEqual(store.events, before)
        XCTAssertTrue(store.displayPaused)
        try FileManager.default.removeItem(at: obstruction)
        try store.confirmClearCurrentSession(onCleared: confirmed, onFailure: { failure = $0 })
        XCTAssertNil(failure)
        XCTAssertTrue(selected.isEmpty)
        XCTAssertTrue(store.displayPaused)
        XCTAssertTrue(store.events.allSatisfy { $0.testSessionId != "selected" })
        XCTAssertTrue(store.persistedEvidenceFiles(sessionId: "selected").isEmpty)
    }

    @MainActor
    func testSuccessfulClearCannotResurrectOldRecordsThroughExport() throws {
        let fixture = try ClearFixture()
        defer { fixture.cleanup() }
        let store = fixture.store()
        store.startSession(testId: "PS-T01", requestedSessionId: "other-session", role: "both")
        let other = store.events.filter { $0.testSessionId == "other-session" }
        store.startSession(testId: "PS-T01", requestedSessionId: "selected", role: "both")
        store.record(TestDiagnosticRecord(category: "test", eventName: "test.before_clear"))
        XCTAssertFalse(store.persistedEvidenceFiles(sessionId: "selected").isEmpty)

        XCTAssertEqual(try store.clearCurrentSession(), 3)
        XCTAssertEqual(store.events.filter { $0.testSessionId == "other-session" }, other)
        XCTAssertTrue(store.persistedEvidenceFiles(sessionId: "selected").isEmpty)
        XCTAssertFalse(store.persistedEvidenceFiles(sessionId: "other-session").isEmpty)
        let archive = try store.exportEvidence()
        XCTAssertFalse(String(decoding: try Data(contentsOf: archive), as: UTF8.self).contains("test.before_clear"))
        XCTAssertEqual(try store.clearCurrentSession(), 1, "the later export event is new history")
        XCTAssertEqual(try store.clearCurrentSession(), 0)
    }

    @MainActor
    func testConfiguredFileLimitIsAcceptedAndOneByteOverFailsWithoutChangingAuthority() throws {
        for extra in 0...1 {
            let fixture = try ClearFixture()
            defer { fixture.cleanup() }
            let store = fixture.store()
            store.startSession(testId: "PS-T01", requestedSessionId: "selected", role: "both")
            let before = store.events
            let prefix = Data("{\"testSessionId\":\"selected\",\"padding\":\"".utf8)
            let suffix = Data("\"}\n".utf8)
            let bytes = prefix + Data(repeating: 0x61, count: 2 * 1024 * 1024 - prefix.count - suffix.count + extra) + suffix
            let file = fixture.logs.appendingPathComponent("events.jsonl")
            try bytes.write(to: file)
            if extra == 0 {
                XCTAssertEqual(try store.clearCurrentSession(), 2)
                XCTAssertEqual(try Data(contentsOf: file), Data())
            } else {
                XCTAssertThrowsError(try store.clearCurrentSession())
                XCTAssertEqual(store.events, before)
                XCTAssertEqual(try Data(contentsOf: file), bytes)
            }
        }
    }

    @MainActor
    func testMissingDirectoryIsEmptyButAnInvalidLogDirectoryIsAnExplicitFailure() throws {
        let fixture = try ClearFixture()
        defer { fixture.cleanup() }
        let store = fixture.store()
        store.startSession(testId: "PS-T01", requestedSessionId: "selected", role: "both")
        let before = store.events
        try FileManager.default.removeItem(at: fixture.logs)
        try Data("not a directory".utf8).write(to: fixture.logs)
        XCTAssertThrowsError(try store.clearCurrentSession())
        XCTAssertEqual(store.events, before)
        try FileManager.default.removeItem(at: fixture.logs)
        XCTAssertEqual(try store.clearCurrentSession(), 2)
    }

    @MainActor
    func testCancellationPropagatesWithoutPresentationCallbacks() throws {
        var callback = false
        XCTAssertThrowsError(try TestDiagnosticClearAction.confirm(
            clear: { throw CancellationError() }, onCleared: { _ in callback = true }, onFailure: { _ in callback = true }
        )) { error in XCTAssertTrue(error is CancellationError) }
        XCTAssertFalse(callback)
    }

    @MainActor
    func testAlreadyCancelledTaskDoesNotStartClearingOrChangePresentation() async {
        var started = false
        var callback = false
        let task = Task { @MainActor in
            try TestDiagnosticClearAction.confirm(
                clear: { started = true; return 0 },
                onCleared: { _ in callback = true }, onFailure: { _ in callback = true }
            )
        }
        task.cancel()
        if case .failure(let error) = await task.result { XCTAssertTrue(error is CancellationError) }
        else { XCTFail("cancelled operation must propagate cancellation") }
        XCTAssertFalse(started)
        XCTAssertFalse(callback)
    }
}

private final class ClearFixture {
    let root: URL
    let defaults: UserDefaults
    let names = ["events.jsonl", "events.1.jsonl", "events.2.jsonl", "events.3.jsonl"]
    private let suite: String
    var logs: URL { root.appendingPathComponent("logs", isDirectory: true) }

    init() throws {
        suite = "p2pkit-clear-\(UUID().uuidString)"
        root = FileManager.default.temporaryDirectory.appendingPathComponent(suite, isDirectory: true)
        try FileManager.default.createDirectory(at: root, withIntermediateDirectories: true)
        defaults = UserDefaults(suiteName: suite)!
        defaults.removePersistentDomain(forName: suite)
    }

    @MainActor
    func store() -> IOSTestDiagnosticStore {
        IOSTestDiagnosticStore(
            baseDirectory: logs, evidenceDirectory: root.appendingPathComponent("evidence", isDirectory: true),
            defaults: defaults
        )
    }

    func cleanup() {
        do { try FileManager.default.removeItem(at: root) }
        catch { XCTFail("could not remove owned synthetic fixture") }
        defaults.removePersistentDomain(forName: suite)
    }
}
