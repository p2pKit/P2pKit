import Foundation
import P2pKitRpcExample
import XCTest
@testable import P2pKitRpcPhone

final class RpcTestArchiveFilesTests: XCTestCase {
    private func fixture() throws -> (URL, RpcDeviceTestSession) {
        let root = FileManager.default.temporaryDirectory.appendingPathComponent("rpc-archive-" + UUID().uuidString)
        try FileManager.default.createDirectory(at: root, withIntermediateDirectories: false,
            attributes: [.posixPermissions: 0o700])
        addTeardownBlock { try FileManager.default.removeItem(at: root) }
        let session = RpcApplicationSession_().deviceTests
        try session.physicalTests.start(caseId: "core-files", source: String(repeating: "a", count: 40), platform: "iPhone")
        try session.physicalTests.finish(outcome: "Interrupted", evidenceReference: "synthetic-record", notes: "Test fixture")
        for report in session.reports {
            try Data(session.reportJson(report: report).utf8).write(to: root.appendingPathComponent(report.runId + ".json"))
        }
        return (root, session)
    }

    func testBrowseAndExportRetainSeparateOriginalRecords() throws {
        let (root, session) = try fixture()
        let files = RpcTestArchiveFiles(directory: root)
        let page = try files.browse()
        XCTAssertEqual(Set(page.reports.map(\.runId)), Set(session.reports.map(\.runId)))
        XCTAssertFalse(page.olderAvailable)
        var lines: [String] = []
        try files.export { lines.append($0) }
        XCTAssertEqual(lines.count, 4)
        XCTAssertTrue(lines.first?.contains("\"recentOnly\":false") == true)
        XCTAssertEqual(lines.last, "{\"exportComplete\":true,\"records\":2}")
        XCTAssertEqual(try files.browse().reports.count, 2)
    }

    func testSelectedExportContainsOnlyThatRun() throws {
        let (root, session) = try fixture()
        var lines: [String] = []
        let id = session.reports[0].runId
        try RpcTestArchiveFiles(directory: root).export({ lines.append($0) }, runId: id)
        XCTAssertEqual(lines.count, 3)
        XCTAssertTrue(lines[1].contains(id))
        XCTAssertEqual(lines.last, "{\"exportComplete\":true,\"records\":1}")
    }

    func testTruncatedOriginalRefusesAndIsRetained() throws {
        let (root, session) = try fixture()
        let path = root.appendingPathComponent(session.reports[0].runId + ".json")
        let original = Data("{\"runId\":".utf8)
        try original.write(to: path)
        XCTAssertThrowsError(try RpcTestArchiveFiles(directory: root).browse())
        XCTAssertEqual(try Data(contentsOf: path), original)
    }

    func testLinkedRecordAndTraversalSelectionRefuse() throws {
        let (root, session) = try fixture()
        let path = root.appendingPathComponent(session.reports[0].runId + ".json")
        let saved = root.appendingPathComponent("retained-original")
        try FileManager.default.moveItem(at: path, to: saved)
        try FileManager.default.createSymbolicLink(at: path, withDestinationURL: saved)
        let files = RpcTestArchiveFiles(directory: root)
        XCTAssertThrowsError(try files.browse())
        XCTAssertThrowsError(try files.export({ _ in }, runId: "../retained-original"))
        XCTAssertTrue(FileManager.default.fileExists(atPath: saved.path))
    }

    func testDeletionMarkerMustIdentifyTheExactRecord() throws {
        let (root, session) = try fixture()
        let id = session.reports[0].runId
        let marker = root.appendingPathComponent(id + ".deleted")
        try Data("wrong".utf8).write(to: marker)
        let files = RpcTestArchiveFiles(directory: root)
        XCTAssertThrowsError(try files.browse())
        try Data(id.utf8).write(to: marker)
        XCTAssertEqual(try files.browse().reports.count, 1)
        XCTAssertThrowsError(try files.export({ _ in }, runId: id))
    }
}
