import Foundation
import Darwin
import P2pKitShared
import XCTest
@testable import P2pKitSample

final class SampleTransferStagingTests: XCTestCase {
    func testOlderReceivedNamespaceNameDoesNotDisableNewClaims() throws {
        let inbox = try makeInbox()
        defer { try? FileManager.default.removeItem(at: inbox) }
        let prior = stagingRoot(inbox)
        try Data("valid completed payload".utf8).write(to: prior)
        let lease = try SampleTransferStaging.claim(in: inbox)
        XCTAssertEqual(lease.directory.deletingLastPathComponent().lastPathComponent,
                       ".p2pkit-ios-transfer-staging-v1.1")
        try SampleTransferStaging.reconcile(in: inbox)
        try lease.retire()
        XCTAssertEqual(try Data(contentsOf: prior), Data("valid completed payload".utf8))
    }

    func testPublishedMatchingFilenameSurvivesLifecycleReconciliation() async throws {
        let inbox = try makeInbox()
        defer { try? FileManager.default.removeItem(at: inbox) }
        let target = try XCTUnwrap(claimUniqueDestination(
            in: inbox, rawName: "report.p2pkit-part", fileManager: FileManager.default
        ))
        var information = stat()
        XCTAssertEqual(SampleTransferPOSIX.fileStatus(target.path, &information), 0)
        XCTAssertEqual(information.st_mode & mode_t(S_IFMT), mode_t(S_IFREG))
        let missing = inbox.appendingPathComponent("not-created")
        let missingResult = SampleTransferPOSIX.fileStatus(missing.path, &information)
        let missingError = errno
        XCTAssertEqual(missingResult, -1)
        XCTAssertEqual(missingError, ENOENT)
        let destination = try AtomicFileTransferDestination(target: target)
        let payload = Data("completed received content".utf8)
        let bytes = KotlinByteArray(size: Int32(payload.count))
        for index in payload.indices { bytes.set(index: Int32(index), value: Int8(bitPattern: payload[index])) }
        let buffer = Kotlinx_io_coreBuffer()
        buffer.write(source: bytes, startIndex: 0, endIndex: bytes.size)
        destination.openSink().write(source: buffer, byteCount: Int64(payload.count))
        let failure = await withCheckedContinuation { continuation in
            destination.commit { continuation.resume(returning: $0) }
        }
        XCTAssertNil(failure)
        try SampleTransferStaging.reconcile(in: inbox)
        XCTAssertEqual(try Data(contentsOf: target), payload)
        XCTAssertEqual(try FileManager.default.contentsOfDirectory(atPath: stagingRoot(inbox).path), [])
    }

    func testLiveLeaseSurvivesAndOnlyReleasedRecordedPartIsReclaimed() throws {
        let inbox = try makeInbox()
        defer { try? FileManager.default.removeItem(at: inbox) }
        let completed = inbox.appendingPathComponent("report.p2pkit-part")
        let hidden = inbox.appendingPathComponent(".private")
        try Data("completed".utf8).write(to: completed)
        try Data("unrelated".utf8).write(to: hidden)
        var lease: SampleTransferStaging.Lease? = try SampleTransferStaging.claim(in: inbox)
        let ownedDirectory = try XCTUnwrap(lease?.directory)
        let part = ownedDirectory.appendingPathComponent(".crashed.p2pkit-part")
        try Data("unverified".utf8).write(to: part)
        try SampleTransferStaging.reconcile(in: inbox)
        XCTAssertEqual(try Data(contentsOf: part), Data("unverified".utf8))
        // Actual descriptor ownership is released, not an age/name approximation.
        // This native unit control is not a separate-process or device-crash claim.
        lease = nil
        try SampleTransferStaging.reconcile(in: inbox)
        XCTAssertFalse(FileManager.default.fileExists(atPath: ownedDirectory.path))
        XCTAssertEqual(try Data(contentsOf: completed), Data("completed".utf8))
        XCTAssertEqual(try Data(contentsOf: hidden), Data("unrelated".utf8))
    }

    func testIndependentDescriptorLockPreventsReclamationWithoutLocalRegistry() throws {
        let inbox = try makeInbox()
        defer { try? FileManager.default.removeItem(at: inbox) }
        let directory = try makeAbandonedRecord(inbox)
        let lockURL = directory.appendingPathComponent("lease")
        let descriptor = Darwin.open(lockURL.path, O_RDWR | O_NOFOLLOW)
        XCTAssertGreaterThanOrEqual(descriptor, 0)
        guard descriptor >= 0 else { return }
        defer { Darwin.close(descriptor) }
        let invalidResult = SampleTransferPOSIX.lockFile(-1, LOCK_EX | LOCK_NB)
        let invalidError = errno
        XCTAssertEqual(invalidResult, -1)
        XCTAssertEqual(invalidError, EBADF)
        XCTAssertEqual(SampleTransferPOSIX.lockFile(descriptor, LOCK_EX | LOCK_NB), 0)
        let part = directory.appendingPathComponent(".active.p2pkit-part")
        try Data("live".utf8).write(to: part)
        try SampleTransferStaging.reconcile(in: inbox)
        XCTAssertEqual(try Data(contentsOf: part), Data("live".utf8))
        XCTAssertEqual(SampleTransferPOSIX.lockFile(descriptor, LOCK_UN), 0)
        try SampleTransferStaging.reconcile(in: inbox)
        XCTAssertFalse(FileManager.default.fileExists(atPath: directory.path))
    }

    func testUnknownEntriesAndSymlinksCannotConferCleanupAuthority() throws {
        let inbox = try makeInbox()
        defer { try? FileManager.default.removeItem(at: inbox) }
        let directory = try makeAbandonedRecord(inbox)
        let unknown = directory.appendingPathComponent("not-a-part")
        try Data("do not delete".utf8).write(to: unknown)
        try SampleTransferStaging.reconcile(in: inbox)
        XCTAssertEqual(try Data(contentsOf: unknown), Data("do not delete".utf8))
        try FileManager.default.removeItem(at: unknown)
        let external = inbox.appendingPathComponent("external")
        try Data("external content".utf8).write(to: external)
        let link = directory.appendingPathComponent(".linked.p2pkit-part")
        try FileManager.default.createSymbolicLink(at: link, withDestinationURL: external)
        try SampleTransferStaging.reconcile(in: inbox)
        XCTAssertEqual(try Data(contentsOf: external), Data("external content".utf8))
        XCTAssertTrue(FileManager.default.fileExists(atPath: link.path))
    }

    private func makeInbox() throws -> URL {
        let result = FileManager.default.temporaryDirectory.appendingPathComponent(
            "p2pkit-staging-\(UUID().uuidString)", isDirectory: true
        ).resolvingSymlinksInPath()
        try FileManager.default.createDirectory(at: result, withIntermediateDirectories: true)
        return result
    }

    private func stagingRoot(_ inbox: URL) -> URL {
        inbox.appendingPathComponent(".p2pkit-ios-transfer-staging-v1")
    }

    private func makeAbandonedRecord(_ inbox: URL) throws -> URL {
        var lease: SampleTransferStaging.Lease? = try SampleTransferStaging.claim(in: inbox)
        let directory = try XCTUnwrap(lease?.directory)
        lease = nil
        return directory
    }
}
