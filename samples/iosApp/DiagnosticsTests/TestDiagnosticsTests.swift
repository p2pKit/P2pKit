import Foundation
import XCTest
@testable import P2pKitSample

final class TestDiagnosticsTests: XCTestCase {
    @MainActor
    func testMultiPeerCorrelationUsesRealSessionAndTransferOwnership() throws {
        let fixture = try Fixture()
        defer { fixture.cleanup() }
        let store = fixture.store()
        _ = store.startSession(
            testId: "PS-T01",
            requestedSessionId: "shared-session",
            role: "both"
        )
        store.setLocalPeerId("local-peer")
        store.connection(
            peerId: "peer-a",
            rawConnectionId: "sdk-session-a",
            state: "Connected",
            previous: nil
        )
        store.connection(
            peerId: "peer-b",
            rawConnectionId: "sdk-session-b",
            state: "Connected",
            previous: nil
        )
        let connectionA = try XCTUnwrap(store.connectionId(for: "peer-a"))
        let connectionB = try XCTUnwrap(store.connectionId(for: "peer-b"))
        XCTAssertNotEqual(connectionA, connectionB)

        let transferA = String(repeating: "a", count: 32)
        let transferB = String(repeating: "b", count: 32)
        store.transfer(
            TestDiagnosticEventName.transferStarted,
            peerId: "peer-a",
            transferId: transferA,
            state: "Transferring",
            size: 64,
            direction: .sent
        )
        store.transfer(
            TestDiagnosticEventName.transferStarted,
            peerId: "peer-b",
            transferId: transferB,
            state: "Transferring",
            size: 64,
            direction: .sent
        )
        store.recordFrame(
            "TX type=FILE_DATA len=64B chunk=0/1 id=\(transferA) LAST"
        )
        let frame = try XCTUnwrap(store.events.last)
        XCTAssertEqual(frame.transferId, transferA)
        XCTAssertEqual(frame.connectionId, connectionA)
        XCTAssertNotEqual(frame.connectionId, connectionB)

        // Same transfer ID on two peers is unresolvable in a process-global
        // frame line, so correlation must become explicitly absent.
        store.transfer(
            TestDiagnosticEventName.transferStarted,
            peerId: "peer-b",
            transferId: transferA,
            state: "Transferring",
            size: 64,
            direction: .received
        )
        store.recordFrame("RX type=FILE_COMMIT len=72B xfer=\(transferA)")
        let ambiguous = try XCTUnwrap(store.events.last)
        XCTAssertEqual(ambiguous.transferId, transferA)
        XCTAssertNil(ambiguous.connectionId)
        XCTAssertNil(ambiguous.peerId)
    }

    @MainActor
    func testBothPeersDeriveSameConnectionAndNewTestSessionRotatesIt() throws {
        let fixtureA = try Fixture()
        let fixtureB = try Fixture()
        defer {
            fixtureA.cleanup()
            fixtureB.cleanup()
        }
        let first = fixtureA.store()
        let second = fixtureB.store()
        _ = first.startSession(
            testId: "ENV-02",
            requestedSessionId: "shared-session",
            role: "client"
        )
        _ = second.startSession(
            testId: "ENV-02",
            requestedSessionId: "shared-session",
            role: "server"
        )
        first.setLocalPeerId("peer-a")
        second.setLocalPeerId("peer-b")
        first.connection(
            peerId: "peer-b",
            rawConnectionId: "sdk-session-a",
            state: "Connected",
            previous: nil
        )
        second.connection(
            peerId: "peer-a",
            rawConnectionId: "sdk-session-b",
            state: "Connected",
            previous: nil
        )
        let matchingA = try XCTUnwrap(first.connectionId(for: "peer-b"))
        let matchingB = try XCTUnwrap(second.connectionId(for: "peer-a"))
        XCTAssertEqual(matchingA, matchingB)

        _ = first.startSession(
            testId: "ENV-02",
            requestedSessionId: "next-session",
            role: "client"
        )
        first.connection(
            peerId: "peer-b",
            rawConnectionId: "sdk-session-next",
            state: "Connected",
            previous: nil
        )
        let rotated = try XCTUnwrap(first.connectionId(for: "peer-b"))
        XCTAssertNotEqual(matchingA, rotated)
    }

    @MainActor
    func testRetiredSdkSessionCannotEraseReplacementTransferOwnership() throws {
        let fixture = try Fixture()
        defer { fixture.cleanup() }
        let store = fixture.store()
        _ = store.startSession(
            testId: "PS-T01",
            requestedSessionId: "shared-session",
            role: "both"
        )
        store.setLocalPeerId("local-peer")
        store.connection(
            peerId: "peer-a",
            rawConnectionId: "sdk-session-old",
            state: "Connected",
            previous: nil
        )
        store.connection(
            peerId: "peer-a",
            rawConnectionId: "sdk-session-new",
            state: "Connected",
            previous: nil
        )
        let transferId = String(repeating: "a", count: 32)
        store.transfer(
            TestDiagnosticEventName.transferStarted,
            peerId: "peer-a",
            transferId: transferId,
            state: "Transferring",
            size: 64,
            direction: .sent
        )
        let replacementConnection = try XCTUnwrap(store.connectionId(for: "peer-a"))

        XCTAssertNil(store.removeConnection(rawConnectionId: "sdk-session-old"))
        store.recordFrame("TX type=FILE_DATA len=64B chunk=0/1 id=\(transferId) LAST")
        XCTAssertEqual(store.events.last?.connectionId, replacementConnection)
        XCTAssertEqual(store.events.last?.transferId, transferId)
    }

    @MainActor
    func testTransferCorrelationNeverInventsAnUnobservedConnection() throws {
        let fixture = try Fixture()
        defer { fixture.cleanup() }
        let store = fixture.store()
        _ = store.startSession(
            testId: "PS-T01",
            requestedSessionId: "shared-session",
            role: "sender"
        )
        store.setLocalPeerId("local-peer")
        let transferId = String(repeating: "a", count: 32)

        XCTAssertNil(store.connectionId(for: "peer-a"))
        store.transfer(
            TestDiagnosticEventName.transferStarted,
            peerId: "peer-a",
            transferId: transferId,
            state: "Transferring",
            size: 64,
            direction: .sent
        )
        store.recordFrame("TX type=FILE_DATA len=64B chunk=0/1 id=\(transferId) LAST")
        XCTAssertNil(store.events.last?.connectionId)
        XCTAssertNil(store.events.last?.peerId)
        XCTAssertEqual(store.events.last?.transferId, transferId)
    }

    @MainActor
    func testFinalOutcomeAndHashesRemainSessionAndTransferScoped() throws {
        let fixture = try Fixture()
        defer { fixture.cleanup() }
        let store = fixture.store()
        _ = store.startSession(
            testId: "PS-T01",
            requestedSessionId: "session-truth",
            role: "both"
        )
        store.record(TestDiagnosticRecord(
            transferId: "transfer-a",
            category: "transfer",
            eventName: TestDiagnosticEventName.transferCompleted,
            outcome: .success
        ))
        XCTAssertNil(store.makeSummary(store.events, manual: []).finalOutcome)

        store.fileHash(
            peerId: "peer-a",
            transferId: "transfer-a",
            size: 10,
            digest: String(repeating: "a", count: 64),
            receiver: false
        )
        store.fileHash(
            peerId: "peer-a",
            transferId: "transfer-a",
            size: 10,
            digest: String(repeating: "a", count: 64),
            receiver: true
        )
        store.fileHash(
            peerId: "peer-b",
            transferId: "transfer-b",
            size: 20,
            digest: String(repeating: "b", count: 64),
            receiver: false
        )

        let ambiguous = store.makeSummary(store.events, manual: [])
        XCTAssertNil(ambiguous.selectedTransferId)
        XCTAssertNil(ambiguous.senderSha256)
        XCTAssertNil(ambiguous.receiverSha256)
        XCTAssertNil(ambiguous.integrityMatch)
        XCTAssertEqual(ambiguous.transferSummaries.count, 2)
        let first = try XCTUnwrap(
            ambiguous.transferSummaries.first { $0.transferId == "transfer-a" }
        )
        XCTAssertEqual(first.senderSha256, String(repeating: "a", count: 64))
        XCTAssertEqual(first.receiverSha256, String(repeating: "a", count: 64))
        XCTAssertEqual(first.integrityMatch, true)
        let second = try XCTUnwrap(
            ambiguous.transferSummaries.first { $0.transferId == "transfer-b" }
        )
        XCTAssertEqual(second.senderSha256, String(repeating: "b", count: 64))
        XCTAssertNil(second.receiverSha256)
        XCTAssertNil(second.integrityMatch)

        store.complete(.cancellation, reason: "operator cancelled")
        XCTAssertEqual(
            store.makeSummary(store.events, manual: []).finalOutcome,
            .cancellation
        )
    }

    @MainActor
    func testRedactionCoversCredentialsNamesAddressesAndMacs() throws {
        let fixture = try Fixture()
        defer { fixture.cleanup() }
        let store = fixture.store()
        _ = store.startSession(
            testId: "ENV-02",
            requestedSessionId: "session-redaction",
            role: "receiver"
        )
        store.record(TestDiagnosticRecord(
            category: "security",
            eventName: "security.redaction.checked",
            errorDescription:
                "peer=Alice filename=private.txt host=[fe80::1%en0] " +
                "route=2001:db8::42 mac=aa:bb:cc:dd:ee:ff token=ghp_secretvalue",
            details: [
                "peerName": "Alice's phone",
                "filename": "private.txt",
                "note": "192.0.2.1 [fe80::abcd%en0] 00:11:22:33:44:55"
            ]
        ))

        let event = try XCTUnwrap(store.events.last)
        XCTAssertEqual(event.details["peerName"], "<redacted>")
        XCTAssertEqual(event.details["filename"], "<redacted>")
        let exported = (event.errorDescription ?? "") + event.details.values.joined()
        for secret in [
            "Alice", "private.txt", "fe80::1", "2001:db8::42",
            "aa:bb:cc:dd:ee:ff", "ghp_secretvalue", "192.0.2.1",
            "00:11:22:33:44:55"
        ] {
            XCTAssertFalse(exported.contains(secret), "leaked \(secret)")
        }
        XCTAssertTrue(exported.contains("<redacted-ip:"))
        XCTAssertTrue(exported.contains("<redacted-mac:"))
    }

    @MainActor
    func testRestartEvidenceExportContainsOnlyTheSelectedSession() throws {
        let fixture = try Fixture()
        defer { fixture.cleanup() }
        let firstProcess = fixture.store()
        _ = firstProcess.startSession(
            testId: "PS-T01",
            requestedSessionId: "session-unrelated",
            role: "sender"
        )
        firstProcess.record(TestDiagnosticRecord(
            category: "test",
            eventName: "test.unrelated.marker"
        ))
        _ = firstProcess.startSession(
            testId: "PS-T01",
            requestedSessionId: "session-selected",
            role: "sender"
        )
        firstProcess.record(TestDiagnosticRecord(
            category: "test",
            eventName: "test.selected.marker"
        ))

        let restarted = fixture.store()
        XCTAssertEqual(restarted.activeSessionId, "session-selected")
        let persisted = restarted.persistedEvidenceFiles(sessionId: "session-selected")
        XCTAssertFalse(persisted.isEmpty)
        let persistedText = persisted.values.compactMap {
            String(data: $0, encoding: .utf8)
        }.joined()
        XCTAssertTrue(persistedText.contains("test.selected.marker"))
        XCTAssertFalse(persistedText.contains("test.unrelated.marker"))
        XCTAssertFalse(persistedText.contains("session-unrelated"))

        let archive = try restarted.exportEvidence()
        let archiveBytes = try Data(contentsOf: archive)
        let archiveText = String(decoding: archiveBytes, as: UTF8.self)
        XCTAssertTrue(archiveText.contains("process-events.jsonl"))
        XCTAssertTrue(archiveText.contains("test.selected.marker"))
        XCTAssertFalse(archiveText.contains("test.unrelated.marker"))
        XCTAssertFalse(archiveText.contains("session-unrelated"))
        let replacement = try restarted.exportEvidence()
        XCTAssertEqual(replacement, archive)
        XCTAssertFalse((try Data(contentsOf: replacement)).isEmpty)
    }

    @MainActor
    func testChecksumManifestIsACompleteOneToOneMapping() throws {
        let files = [
            "events.jsonl": Data("events".utf8),
            "summary.json": Data("summary".utf8)
        ]
        var complete = files
        complete["checksums.sha256"] = try IOSTestDiagnosticStore.checksumManifest(for: files)
        XCTAssertTrue(IOSTestDiagnosticStore.checksumManifestIsComplete(complete))

        var unlisted = complete
        unlisted["extra.txt"] = Data("extra".utf8)
        XCTAssertFalse(IOSTestDiagnosticStore.checksumManifestIsComplete(unlisted))

        var duplicate = complete
        duplicate["checksums.sha256"]?.append(complete["checksums.sha256"]!)
        XCTAssertFalse(IOSTestDiagnosticStore.checksumManifestIsComplete(duplicate))

        XCTAssertThrowsError(
            try IOSTestDiagnosticStore.checksumManifest(for: complete)
        )
    }
}

private final class Fixture {
    let root: URL
    let defaults: UserDefaults
    private let defaultsSuiteName: String

    init() throws {
        root = FileManager.default.temporaryDirectory.appendingPathComponent(
            "p2pkit-diagnostics-\(UUID().uuidString)",
            isDirectory: true
        )
        try FileManager.default.createDirectory(at: root, withIntermediateDirectories: true)
        defaultsSuiteName = "p2pkit-diagnostics-\(UUID().uuidString)"
        defaults = UserDefaults(suiteName: defaultsSuiteName)!
        defaults.removePersistentDomain(forName: defaultsSuiteName)
    }

    @MainActor
    func store() -> IOSTestDiagnosticStore {
        IOSTestDiagnosticStore(
            baseDirectory: root.appendingPathComponent("logs", isDirectory: true),
            evidenceDirectory: root.appendingPathComponent("evidence", isDirectory: true),
            defaults: defaults
        )
    }

    func cleanup() {
        try? FileManager.default.removeItem(at: root)
        defaults.removePersistentDomain(forName: defaultsSuiteName)
    }
}
