import Foundation
import P2pKitShared
import XCTest
@testable import P2pKitSample

final class TestDiagnosticsTests: XCTestCase {
    func testProductionTransferSelectorsScopeConsentCancelLateUpdatesAndCleanup() {
        final class Handle {
            var actions: [String] = []
            func accept() { actions.append("accept") }
            func reject() { actions.append("reject") }
            func cancel() { actions.append("cancel") }
        }
        struct Row: Identifiable {
            let id: TransferKey
            let handle: Handle
            var bytes = 0
            var digest: String?
            var terminal = false
        }
        let first = Handle()
        let second = Handle()
        let old = TransferKey(sessionId: "old-session", transferId: "same-id")
        let current = TransferKey(sessionId: "new-session", transferId: "same-id")
        var rows = [Row(id: old, handle: first), Row(id: current, handle: second)]
        var offers = [old: first, current: second]
        SessionTransferEntries.take(old, from: &offers)?.accept()
        XCTAssertNil(SessionTransferEntries.take(old, from: &offers))
        SessionTransferEntries.take(current, from: &offers)?.reject()
        SessionTransferEntries.row(old, in: rows)?.handle.cancel()
        XCTAssertEqual(first.actions, ["accept", "cancel"])
        XCTAssertEqual(second.actions, ["reject"])
        SessionTransferEntries.update(current, in: &rows) { $0.bytes = 20; $0.digest = "new" }
        SessionTransferEntries.update(old, in: &rows) {
            $0.bytes = 10; $0.digest = "late-old"; $0.terminal = true
        }
        XCTAssertEqual(SessionTransferEntries.row(current, in: rows)?.bytes, 20)
        XCTAssertEqual(SessionTransferEntries.row(current, in: rows)?.digest, "new")
        XCTAssertEqual(SessionTransferEntries.row(current, in: rows)?.terminal, false)
        rows.removeAll { $0.id == old }
        SessionTransferEntries.update(old, in: &rows) { _ in XCTFail("must not mutate replacement") }
        XCTAssertEqual(rows.map(\.id), [current])
        offers = [old: first, current: second]
        SessionTransferEntries.remove(sessionId: old.sessionId, transferIds: [old.transferId], from: &offers)
        XCTAssertEqual(Set(offers.keys), [current])
    }

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
        XCTAssertNil(frame.connectionId)
        XCTAssertNil(frame.peerId)
        XCTAssertNil(frame.sdkSessionId)

        // B's first colliding FILE_OFFER trace arrives before its structured
        // offer callback. Even the sole observed owner A is not proof.
        store.recordFrame("RX type=FILE_OFFER len=64B xfer=\(transferA)")
        let beforeRegistration = try XCTUnwrap(store.events.last)
        XCTAssertNil(beforeRegistration.connectionId)
        XCTAssertNil(beforeRegistration.peerId)
        XCTAssertNil(beforeRegistration.sdkSessionId)
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
        XCTAssertNil(ambiguous.sdkSessionId)
        XCTAssertEqual(store.events.first { $0.index == beforeRegistration.index }, beforeRegistration)
        XCTAssertEqual(store.makeSummary(store.events, manual: []).transferSummaries.count, 3)
    }

    @MainActor
    func testSameTransferIdOnTwoSessionsKeepsHashesSeparate() throws {
        let fixture = try Fixture()
        defer { fixture.cleanup() }
        let store = fixture.store()
        _ = store.startSession(testId: "PS-T01", requestedSessionId: "collision-test", role: "both")
        store.setLocalPeerId("local-peer")
        let transferId = String(repeating: "a", count: 32)
        let digest = String(repeating: "b", count: 64)
        let first = TransferKey(sessionId: "session-a", transferId: transferId)
        let second = TransferKey(sessionId: "session-b", transferId: transferId)

        for (peer, session) in [("peer-a", first.sessionId), ("peer-b", second.sessionId)] {
            store.connection(peerId: peer, rawConnectionId: session, state: "Connected", previous: nil)
            store.transfer(
                TestDiagnosticEventName.transferStarted,
                peerId: peer,
                transferId: transferId,
                sessionId: session,
                state: "Transferring",
                size: 64,
                direction: .local
            )
        }
        store.fileHash(
            peerId: "peer-a", transferId: transferId, size: 64, digest: digest,
            receiver: false, sessionId: first.sessionId
        )
        store.fileHash(
            peerId: "peer-b", transferId: transferId, size: 64, digest: digest,
            receiver: true, sessionId: second.sessionId
        )
        XCTAssertNil(store.senderSha256)
        XCTAssertEqual(store.receiverSha256, digest)
        XCTAssertNil(store.integrityMatch)
        let summary = store.makeSummary(store.events, manual: [])
        XCTAssertEqual(summary.transferSummaries.count, 2)
        XCTAssertNil(summary.selectedTransferId)
        XCTAssertNil(summary.integrityMatch)
        let firstSummary = try XCTUnwrap(summary.transferSummaries.first {
            $0.connectionIds == [store.connectionId(for: "peer-a")!]
        })
        XCTAssertEqual(firstSummary.senderSha256, digest)
        XCTAssertNil(firstSummary.receiverSha256)
        let secondSummary = try XCTUnwrap(summary.transferSummaries.first {
            $0.connectionIds == [store.connectionId(for: "peer-b")!]
        })
        XCTAssertNil(secondSummary.senderSha256)
        XCTAssertEqual(secondSummary.receiverSha256, digest)
        XCTAssertTrue(summary.transferSummaries.allSatisfy { $0.integrityMatch == nil })

        store.recordFrame("RX type=FILE_COMMIT len=72B xfer=\(transferId)")
        XCTAssertNil(store.events.last?.connectionId)
        XCTAssertNil(store.events.last?.peerId)
    }

    @MainActor
    func testSamePeerReplacementRetainsSeparateSdkTransferOwners() throws {
        let fixture = try Fixture()
        defer { fixture.cleanup() }
        let store = fixture.store()
        _ = store.startSession(testId: "PS-T01", requestedSessionId: "replacement-test", role: "both")
        store.setLocalPeerId("local-peer")
        let transferId = String(repeating: "a", count: 32)
        for session in ["old-session", "new-session"] {
            store.connection(peerId: "peer-a", rawConnectionId: session, state: "Connected", previous: nil)
            store.transfer(
                TestDiagnosticEventName.transferStarted,
                peerId: "peer-a",
                transferId: transferId,
                sessionId: session,
                state: "Transferring",
                size: 64,
                direction: .sent
            )
        }
        let oldDigest = String(repeating: "b", count: 64)
        let newDigest = String(repeating: "c", count: 64)
        store.fileHash(
            peerId: "peer-a", transferId: transferId, size: 64, digest: oldDigest,
            receiver: false, sessionId: "old-session"
        )
        store.fileHash(
            peerId: "peer-a", transferId: transferId, size: 64, digest: newDigest,
            receiver: true, sessionId: "new-session"
        )
        XCTAssertNil(store.senderSha256)
        XCTAssertEqual(store.receiverSha256, newDigest)
        XCTAssertNil(store.integrityMatch)
        let initial = store.makeSummary(store.events, manual: [])
        XCTAssertEqual(initial.transferSummaries.count, 2)
        XCTAssertNil(initial.selectedTransferId)
        XCTAssertTrue(initial.transferSummaries.allSatisfy { $0.integrityMatch == nil })

        // A delayed hash for the retired session cannot mutate the active
        // replacement's hashes or produce a false integrity result for it.
        store.fileHash(
            peerId: "peer-a", transferId: transferId, size: 64, digest: oldDigest,
            receiver: true, sessionId: "old-session"
        )
        XCTAssertNil(store.senderSha256)
        XCTAssertEqual(store.receiverSha256, newDigest)
        XCTAssertNil(store.integrityMatch)
        let final = store.makeSummary(store.events, manual: [])
        XCTAssertEqual(final.transferSummaries.count, 2)
        XCTAssertEqual(final.connectionIds.count, 1, "public connection ID stays symmetric across reconnects")
        let old = try XCTUnwrap(final.transferSummaries.first { $0.senderSha256 == oldDigest })
        let current = try XCTUnwrap(final.transferSummaries.first { $0.receiverSha256 == newDigest })
        XCTAssertNotEqual(old.sdkSessionId, current.sdkSessionId)
        XCTAssertNotEqual(old.sdkSessionId, "old-session")
        XCTAssertNotEqual(current.sdkSessionId, "new-session")
        XCTAssertEqual(old.receiverSha256, oldDigest)
        XCTAssertEqual(old.integrityMatch, true)
        XCTAssertNil(current.senderSha256)
        XCTAssertNil(current.integrityMatch)
        XCTAssertNil(final.senderSha256)
        XCTAssertNil(final.receiverSha256)
        XCTAssertNil(final.integrityMatch)
        XCTAssertNil(store.transferConnectionId(
            peerId: "peer-a", sessionId: "old-session", transferId: "unobserved"
        ))
        XCTAssertNotNil(store.transferConnectionId(
            peerId: "peer-a", sessionId: "old-session", transferId: transferId
        ))
        store.recordFrame("TX type=FILE_DATA len=64B chunk=0/1 id=\(transferId) LAST")
        XCTAssertNil(store.events.last?.connectionId)
        XCTAssertNil(store.events.last?.peerId)
        XCTAssertEqual(store.makeSummary(store.events, manual: []).transferSummaries.count, 2)
    }

    @MainActor
    func testLegacyOwnerlessEvidenceDecodesButCannotEstablishOwnedSummary() throws {
        let fixture = try Fixture()
        defer { fixture.cleanup() }
        let store = fixture.store()
        store.record(TestDiagnosticRecord(
            peerId: "peer-a",
            connectionId: "connection-a",
            transferId: "same-transfer",
            category: "file",
            eventName: TestDiagnosticEventName.senderHash,
            details: ["sha256": String(repeating: "a", count: 64)]
        ))
        let event = try XCTUnwrap(store.events.last)
        var legacy = try XCTUnwrap(JSONSerialization.jsonObject(with: JSONEncoder().encode(event)) as? [String: Any])
        legacy.removeValue(forKey: "sdkSessionId")
        let decoded = try JSONDecoder().decode(
            TestDiagnosticEvent.self, from: JSONSerialization.data(withJSONObject: legacy)
        )
        XCTAssertEqual(event, decoded)
        XCTAssertTrue(store.makeSummary(store.events, manual: []).transferSummaries.isEmpty)
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
        XCTAssertEqual(store.transferConnectionId(
            peerId: "peer-a", sessionId: "sdk-session-new", transferId: transferId
        ), replacementConnection)
        store.recordFrame("TX type=FILE_DATA len=64B chunk=0/1 id=\(transferId) LAST")
        XCTAssertNil(store.events.last?.connectionId)
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
        store.setLocalPeerId("local-peer")
        store.connection(peerId: "peer-a", rawConnectionId: "session-a", state: "Connected", previous: nil)
        store.connection(peerId: "peer-b", rawConnectionId: "session-b", state: "Connected", previous: nil)
        store.record(TestDiagnosticRecord(
            peerId: "peer-a",
            connectionId: store.connectionId(for: "peer-a"),
            sdkSessionId: "session-a",
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

    @MainActor
    func testTransportLogsSeparateRecoveryFromTransferRetry() throws {
        let fixture = try Fixture()
        defer { fixture.cleanup() }
        let store = fixture.store()
        _ = store.startSession(
            testId: "PS-T05",
            requestedSessionId: "session-retry-classification",
            role: "both"
        )

        store.recordTransport("reconnect: attempt=2")
        store.recordTransport("reconnect: attempt=2 succeeded")
        store.recordTransport("file transfer retry attempt=3")

        XCTAssertEqual(
            Array(store.events.suffix(3).map(\.eventName)),
            [
                TestDiagnosticEventName.recoveryStarted,
                TestDiagnosticEventName.recoveryCompleted,
                TestDiagnosticEventName.transferRetry
            ]
        )
    }

    func testAtomicDestinationAbortFailureRemainsRetryableAndBlocksCommit() async throws {
        let root = FileManager.default.temporaryDirectory.appendingPathComponent(
            "p2pkit-destination-abort-\(UUID().uuidString)",
            isDirectory: true
        )
        let target = root.appendingPathComponent("reserved")
        try FileManager.default.createDirectory(at: root, withIntermediateDirectories: true)
        XCTAssertTrue(FileManager.default.createFile(atPath: target.path, contents: Data()))
        defer { try? FileManager.default.removeItem(at: root) }

        var rejectFirstTargetRemoval = true
        let destination = try AtomicFileTransferDestination(target: target, removeItem: { url in
            if url == target && rejectFirstTargetRemoval {
                rejectFirstTargetRemoval = false
                throw NSError(
                    domain: "dev.p2pkit.sample.tests",
                    code: 1,
                    userInfo: [NSLocalizedDescriptionKey: "injected target cleanup failure"]
                )
            }
            try FileManager.default.removeItem(at: url)
        })
        let firstAbort = await withCheckedContinuation { continuation in
            destination.abort(cause: nil) { continuation.resume(returning: $0) }
        }
        XCTAssertNotNil(firstAbort)
        XCTAssertFalse(destination.temporaryArtifactExists)

        let commitAfterAbort = await withCheckedContinuation { continuation in
            destination.commit { continuation.resume(returning: $0) }
        }
        XCTAssertNotNil(commitAfterAbort)

        let secondAbort = await withCheckedContinuation { continuation in
            destination.abort(cause: nil) { continuation.resume(returning: $0) }
        }
        XCTAssertNil(secondAbort)
        XCTAssertFalse(FileManager.default.fileExists(atPath: target.path))
    }

    func testAtomicDestinationPostPublicationFailurePreservesTarget() async throws {
        let root = FileManager.default.temporaryDirectory.appendingPathComponent(
            "p2pkit-destination-published-\(UUID().uuidString)",
            isDirectory: true
        )
        let target = root.appendingPathComponent("reserved")
        try FileManager.default.createDirectory(at: root, withIntermediateDirectories: true)
        XCTAssertTrue(FileManager.default.createFile(atPath: target.path, contents: Data()))
        defer { try? FileManager.default.removeItem(at: root) }

        let destination = try AtomicFileTransferDestination(
            target: target,
            synchronizeDirectory: { _ in
                throw NSError(
                    domain: "dev.p2pkit.sample.tests",
                    code: 2,
                    userInfo: [NSLocalizedDescriptionKey: "injected directory sync failure"]
                )
            }
        )
        let payload = Data("published payload".utf8)
        writePayload(payload, to: destination)
        let commitError = await withCheckedContinuation { continuation in
            destination.commit { continuation.resume(returning: $0) }
        }
        XCTAssertNotNil(commitError)
        XCTAssertTrue(FileManager.default.fileExists(atPath: target.path))
        XCTAssertEqual(try Data(contentsOf: target), payload)
        XCTAssertFalse(destination.temporaryArtifactExists)

        let abortError = await withCheckedContinuation { continuation in
            destination.abort(cause: nil) { continuation.resume(returning: $0) }
        }
        XCTAssertNil(abortError)
        XCTAssertTrue(FileManager.default.fileExists(atPath: target.path))
        XCTAssertEqual(try Data(contentsOf: target), payload)
    }

    func testAtomicDestinationCancellationAfterPublicationPreservesTarget() async throws {
        let root = FileManager.default.temporaryDirectory.appendingPathComponent(
            "p2pkit-destination-cancelled-\(UUID().uuidString)",
            isDirectory: true
        )
        let target = root.appendingPathComponent("reserved")
        try FileManager.default.createDirectory(at: root, withIntermediateDirectories: true)
        XCTAssertTrue(FileManager.default.createFile(atPath: target.path, contents: Data()))
        defer { try? FileManager.default.removeItem(at: root) }

        let destination = try AtomicFileTransferDestination(
            target: target,
            synchronizeDirectory: { _ in throw CancellationError() }
        )
        let payload = Data("cancelled after publication".utf8)
        writePayload(payload, to: destination)
        let commitError = await withCheckedContinuation { continuation in
            destination.commit { continuation.resume(returning: $0) }
        }
        XCTAssertTrue(commitError is CancellationError)

        let abortError = await withCheckedContinuation { continuation in
            destination.abort(cause: nil) { continuation.resume(returning: $0) }
        }
        XCTAssertNil(abortError)
        XCTAssertTrue(FileManager.default.fileExists(atPath: target.path))
        XCTAssertEqual(try Data(contentsOf: target), payload)
        XCTAssertFalse(destination.temporaryArtifactExists)
    }

    func testAtomicDestinationRetriesOnlyDurabilityAfterPublication() async throws {
        let root = FileManager.default.temporaryDirectory.appendingPathComponent(
            "p2pkit-destination-commit-retry-\(UUID().uuidString)",
            isDirectory: true
        )
        let target = root.appendingPathComponent("reserved")
        try FileManager.default.createDirectory(at: root, withIntermediateDirectories: true)
        XCTAssertTrue(FileManager.default.createFile(atPath: target.path, contents: Data()))
        defer { try? FileManager.default.removeItem(at: root) }

        var syncAttempts = 0
        let destination = try AtomicFileTransferDestination(
            target: target,
            synchronizeDirectory: { _ in
                syncAttempts += 1
                if syncAttempts == 1 {
                    throw NSError(
                        domain: "dev.p2pkit.sample.tests",
                        code: 3,
                        userInfo: [NSLocalizedDescriptionKey: "injected directory sync failure"]
                    )
                }
            }
        )
        let payload = Data("retry preserves publication".utf8)
        writePayload(payload, to: destination)

        let firstCommit = await withCheckedContinuation { continuation in
            destination.commit { continuation.resume(returning: $0) }
        }
        XCTAssertNotNil(firstCommit)
        let secondCommit = await withCheckedContinuation { continuation in
            destination.commit { continuation.resume(returning: $0) }
        }

        XCTAssertNil(secondCommit)
        XCTAssertEqual(syncAttempts, 2)
        XCTAssertTrue(FileManager.default.fileExists(atPath: target.path))
        XCTAssertEqual(try Data(contentsOf: target), payload)
        XCTAssertFalse(destination.temporaryArtifactExists)
    }

    func testUniqueDestinationPreservesExistingFileAndUsesSuffix() throws {
        let root = FileManager.default.temporaryDirectory.appendingPathComponent(
            "p2pkit-unique-destination-\(UUID().uuidString)",
            isDirectory: true
        )
        try FileManager.default.createDirectory(at: root, withIntermediateDirectories: true)
        defer { try? FileManager.default.removeItem(at: root) }

        let first = try XCTUnwrap(
            claimUniqueDestination(in: root, rawName: "photo.png", fileManager: .default)
        )
        let original = Data("first transfer".utf8)
        try original.write(to: first)

        let second = try XCTUnwrap(
            claimUniqueDestination(in: root, rawName: "photo.png", fileManager: .default)
        )

        XCTAssertEqual(first.lastPathComponent, "photo.png")
        XCTAssertEqual(second.lastPathComponent, "photo (1).png")
        XCTAssertNotEqual(first, second)
        XCTAssertEqual(try Data(contentsOf: first), original)
    }

    func testConcurrentUniqueDestinationClaimsNeverCollide() throws {
        let root = FileManager.default.temporaryDirectory.appendingPathComponent(
            "p2pkit-concurrent-destination-\(UUID().uuidString)",
            isDirectory: true
        )
        try FileManager.default.createDirectory(at: root, withIntermediateDirectories: true)
        defer { try? FileManager.default.removeItem(at: root) }

        let lock = NSLock()
        var claimed: [URL] = []
        DispatchQueue.concurrentPerform(iterations: 32) { _ in
            let destination = claimUniqueDestination(
                in: root,
                rawName: "report.pdf",
                fileManager: .default
            )
            lock.lock()
            if let destination { claimed.append(destination) }
            lock.unlock()
        }

        XCTAssertEqual(claimed.count, 32)
        XCTAssertEqual(Set(claimed).count, 32)
    }

    func testUniqueDestinationFailsImmediatelyForMissingDirectory() {
        let missing = FileManager.default.temporaryDirectory.appendingPathComponent(
            "p2pkit-missing-destination-\(UUID().uuidString)",
            isDirectory: true
        )

        XCTAssertNil(
            claimUniqueDestination(in: missing, rawName: "photo.png", fileManager: .default)
        )
    }
}

private func writePayload(_ payload: Data, to destination: AtomicFileTransferDestination) {
    let bytes = KotlinByteArray(size: Int32(payload.count))
    for index in payload.indices {
        bytes.set(index: Int32(index), value: Int8(bitPattern: payload[index]))
    }
    let buffer = Kotlinx_io_coreBuffer()
    buffer.write(source: bytes, startIndex: 0, endIndex: bytes.size)
    destination.openSink().write(source: buffer, byteCount: Int64(payload.count))
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
