import Foundation
import XCTest
@testable import P2pKitSample

final class SampleBackupPolicyTests: XCTestCase {
    func testNamedRootsKeepExistingBytesAndReapplyExclusionAfterRecreation() throws {
        let fixture = try BackupFixture()
        defer { fixture.cleanup() }
        for directory in [fixture.inbox, fixture.evidence] {
            try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
            let marker = directory.appendingPathComponent("synthetic-existing.bin")
            let payload = Data([0, 1, 2, 255])
            try payload.write(to: marker)
            try setBackupExclusion(false, at: directory)
            XCTAssertEqual(try backupExclusion(at: directory), false)

            try SampleBackupPolicy.prepareDirectory(at: directory)
            XCTAssertEqual(try backupExclusion(at: directory), true)
            XCTAssertEqual(try Data(contentsOf: marker), payload)
            try SampleBackupPolicy.prepareDirectory(at: directory)
            XCTAssertEqual(try Data(contentsOf: marker), payload)

            try FileManager.default.removeItem(at: directory)
            var sawCreatedDirectory = false
            try SampleBackupPolicy.prepareDirectory(at: directory) { created in
                XCTAssertEqual(created, directory)
                var isDirectory: ObjCBool = false
                XCTAssertTrue(FileManager.default.fileExists(atPath: created.path, isDirectory: &isDirectory))
                XCTAssertTrue(isDirectory.boolValue)
                sawCreatedDirectory = true
                try SampleBackupPolicy.excludeDirectoryFromBackup(created)
            }
            XCTAssertTrue(sawCreatedDirectory)
            XCTAssertEqual(try backupExclusion(at: directory), true)
        }
    }

    @MainActor
    func testStartupPreparesBothExistingRootsWithoutReceivingOrExporting() throws {
        let fixture = try BackupFixture()
        defer { fixture.cleanup() }
        let store = fixture.store()
        let bytes = Data("synthetic retained contents".utf8)
        for directory in [fixture.inbox, fixture.evidence] {
            try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
            try bytes.write(to: directory.appendingPathComponent("retained.bin"))
            try setBackupExclusion(false, at: directory)
        }
        XCTAssertNil(try SampleBackupPolicy.prepareAtStartup(
            inbox: { try SampleBackupPolicy.prepareDirectory(at: fixture.inbox) },
            evidence: { try store.prepareEvidenceStorage() }
        ))
        for directory in [fixture.inbox, fixture.evidence] {
            XCTAssertEqual(try backupExclusion(at: directory), true)
            XCTAssertEqual(try Data(contentsOf: directory.appendingPathComponent("retained.bin")), bytes)
            XCTAssertEqual(try FileManager.default.contentsOfDirectory(atPath: directory.path), ["retained.bin"])
        }
        XCTAssertFalse(store.events.contains { $0.eventName == TestDiagnosticEventName.evidenceExported })
    }

    @MainActor
    func testStartupAttemptsTheOtherRootOnEitherFailureAndUsesOnlyFixedWarningText() throws {
        let failure = NSError(
            domain: "synthetic-backup", code: 1,
            userInfo: [NSLocalizedDescriptionKey: "/private/synthetic-canary-secret-path"]
        )
        for failInbox in [true, false] {
            var attempts: [String] = []
            let warning = try SampleBackupPolicy.prepareAtStartup(
                inbox: {
                    attempts.append("inbox")
                    if failInbox { throw failure }
                },
                evidence: {
                    attempts.append("evidence")
                    if !failInbox { throw failure }
                }
            )
            XCTAssertEqual(attempts, ["inbox", "evidence"])
            XCTAssertEqual(warning, SampleBackupPolicy.startupWarning)
            XCTAssertFalse(warning?.contains("canary") ?? true)
            XCTAssertFalse(warning?.contains("/private") ?? true)
        }
    }

    @MainActor
    func testReceiveGateRejectsPreparationFailureBeforeAnyDownstreamReservationOrAccept() async throws {
        let fixture = try BackupFixture()
        defer { fixture.cleanup() }
        try FileManager.default.createDirectory(at: fixture.inbox, withIntermediateDirectories: true)
        let marker = fixture.inbox.appendingPathComponent("retained.bin")
        let bytes = Data("prior accepted file".utf8)
        try bytes.write(to: marker)
        let failure = NSError(domain: "synthetic-backup", code: 2)
        var downstreamCalls = 0
        do {
            try await SampleBackupPolicy.withPreparedDirectory(
                at: fixture.inbox, excludeFromBackup: { _ in throw failure }
            ) {
                downstreamCalls += 1
                _ = claimUniqueDestination(in: fixture.inbox, rawName: "new.bin", fileManager: .default)
            }
            XCTFail("exclusion failure must escape to the selected-offer rejection boundary")
        } catch let error as SampleBackupPolicy.PreparationError {
            XCTAssertTrue((error.cause as NSError) === failure)
            XCTAssertEqual(error.localizedDescription, "Could not prepare sample storage for backup exclusion.")
        }
        XCTAssertEqual(downstreamCalls, 0)
        XCTAssertEqual(try FileManager.default.contentsOfDirectory(atPath: fixture.inbox.path), ["retained.bin"])
        XCTAssertEqual(try Data(contentsOf: marker), bytes)
    }

    @MainActor
    func testReceiveGatePreparesRootBeforeTheActualExclusiveClaim() async throws {
        let fixture = try BackupFixture()
        defer { fixture.cleanup() }
        var order: [String] = []
        var observedExclusion: Bool?
        var claimed: URL?
        try await SampleBackupPolicy.withPreparedDirectory(
            at: fixture.inbox, excludeFromBackup: { directory in
                order.append("exclude")
                try SampleBackupPolicy.excludeDirectoryFromBackup(directory)
            }
        ) {
            order.append("claim")
            observedExclusion = try? backupExclusion(at: fixture.inbox)
            claimed = claimUniqueDestination(in: fixture.inbox, rawName: "received.bin", fileManager: .default)
        }
        XCTAssertEqual(order, ["exclude", "claim"])
        XCTAssertEqual(observedExclusion, true)
        XCTAssertEqual(claimed?.lastPathComponent, "received.bin")
    }

    @MainActor
    func testActualExportPreparesAndRecreatesItsRootWithoutChangingJsonlBackupPolicy() throws {
        let fixture = try BackupFixture()
        defer { fixture.cleanup() }
        let store = fixture.store()
        try setBackupExclusion(false, at: fixture.logs)
        let first = try store.exportEvidence()
        XCTAssertEqual(first.deletingLastPathComponent(), fixture.evidence)
        XCTAssertEqual(try backupExclusion(at: fixture.evidence), true)
        XCTAssertEqual(try backupExclusion(at: fixture.logs), false)
        try FileManager.default.removeItem(at: fixture.evidence)
        let recreated = try store.exportEvidence()
        XCTAssertTrue(FileManager.default.fileExists(atPath: recreated.path))
        XCTAssertEqual(try backupExclusion(at: fixture.evidence), true)
        XCTAssertEqual(try backupExclusion(at: fixture.logs), false)
    }

    @MainActor
    func testActualExportFailurePreservesPriorArchiveAndSuccessCountAndAllowsRetry() throws {
        let fixture = try BackupFixture()
        defer { fixture.cleanup() }
        let failure = NSError(
            domain: "synthetic-backup", code: 3,
            userInfo: [NSLocalizedDescriptionKey: "/private/synthetic-canary-secret-path"]
        )
        var shouldFail = false
        var preparations = 0
        let store = fixture.store { directory in
            preparations += 1
            if shouldFail { throw failure }
            try SampleBackupPolicy.excludeDirectoryFromBackup(directory)
        }
        try store.prepareEvidenceStorage()
        XCTAssertEqual(preparations, 1)
        let previous = try store.exportEvidence()
        let previousBytes = try Data(contentsOf: previous)
        let names = try FileManager.default.contentsOfDirectory(atPath: fixture.evidence.path).sorted()
        let exports = store.events.filter { $0.eventName == TestDiagnosticEventName.evidenceExported }.count
        try setBackupExclusion(false, at: fixture.evidence)
        shouldFail = true
        XCTAssertThrowsError(try store.exportEvidence()) { error in
            guard let preparation = error as? SampleBackupPolicy.PreparationError else {
                XCTFail("expected the fixed-message wrapper with its retained cause")
                return
            }
            XCTAssertTrue((preparation.cause as NSError) === failure)
            XCTAssertEqual(error.localizedDescription, "Could not prepare sample storage for backup exclusion.")
            XCTAssertFalse(error.localizedDescription.contains("canary"))
        }
        XCTAssertEqual(preparations, 3)
        XCTAssertEqual(try Data(contentsOf: previous), previousBytes)
        XCTAssertEqual(try FileManager.default.contentsOfDirectory(atPath: fixture.evidence.path).sorted(), names)
        XCTAssertEqual(store.events.filter { $0.eventName == TestDiagnosticEventName.evidenceExported }.count, exports)
        XCTAssertEqual(try backupExclusion(at: fixture.evidence), false)

        // A failure of the independent evidence-root policy must not alter the
        // established disk-before-memory current-session clear transaction.
        _ = try store.clearCurrentSession()
        XCTAssertEqual(preparations, 3)
        shouldFail = false
        _ = try store.exportEvidence()
        XCTAssertEqual(preparations, 4)
        XCTAssertEqual(try backupExclusion(at: fixture.evidence), true)
    }

    @MainActor
    func testPreparationCancellationIsNotConvertedIntoStorageFailureOrAnExecutedReceive() async throws {
        let fixture = try BackupFixture()
        defer { fixture.cleanup() }
        var called = false
        do {
            try await SampleBackupPolicy.withPreparedDirectory(
                at: fixture.inbox, excludeFromBackup: { _ in throw CancellationError() }
            ) { called = true }
            XCTFail("cancellation must escape unchanged")
        } catch is CancellationError {
            XCTAssertFalse(called)
        }
        XCTAssertFalse(called)
    }
}

private func setBackupExclusion(_ excluded: Bool, at directory: URL) throws {
    var values = URLResourceValues()
    values.isExcludedFromBackup = excluded
    var mutableDirectory = directory
    try mutableDirectory.setResourceValues(values)
}

private func backupExclusion(at directory: URL) throws -> Bool? {
    var fresh = URL(fileURLWithPath: directory.path, isDirectory: true)
    fresh.removeAllCachedResourceValues()
    return try fresh.resourceValues(forKeys: [.isExcludedFromBackupKey]).isExcludedFromBackup
}

private final class BackupFixture {
    let root: URL
    let defaults: UserDefaults
    private let suite: String
    var inbox: URL { root.appendingPathComponent("P2pKitInbox", isDirectory: true) }
    var evidence: URL { root.appendingPathComponent("P2pKitEvidence", isDirectory: true) }
    var logs: URL { root.appendingPathComponent("logs", isDirectory: true) }

    init() throws {
        root = FileManager.default.temporaryDirectory.appendingPathComponent(
            "p2pkit-backup-policy-\(UUID().uuidString)", isDirectory: true
        )
        try FileManager.default.createDirectory(at: root, withIntermediateDirectories: true)
        suite = "p2pkit-backup-policy-\(UUID().uuidString)"
        defaults = UserDefaults(suiteName: suite)!
        defaults.removePersistentDomain(forName: suite)
    }

    @MainActor
    func store(
        exclude: @escaping (URL) throws -> Void = SampleBackupPolicy.excludeDirectoryFromBackup
    ) -> IOSTestDiagnosticStore {
        IOSTestDiagnosticStore(
            baseDirectory: logs, evidenceDirectory: evidence,
            excludeEvidenceFromBackup: exclude, defaults: defaults
        )
    }

    func cleanup() {
        try? FileManager.default.removeItem(at: root)
        defaults.removePersistentDomain(forName: suite)
    }
}
