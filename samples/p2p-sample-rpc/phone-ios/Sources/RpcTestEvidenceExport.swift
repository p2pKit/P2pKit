import Foundation
import P2pKitRpcExample
import SwiftUI
import UIKit

enum RpcTestEvidenceExport {
    enum Failure: Error { case unavailable }

    static func write(_ session: RpcDeviceTestSession) throws -> URL {
        let root = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask)[0]
        var directory = root.appendingPathComponent("rpc-export-" + UUID().uuidString, isDirectory: true)
        try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: false,
            attributes: [.posixPermissions: 0o700, .protectionKey: FileProtectionType.complete])
        var values = URLResourceValues()
        values.isExcludedFromBackup = true
        try directory.setResourceValues(values)
        let partial = directory.appendingPathComponent("recent-results.partial")
        guard FileManager.default.createFile(atPath: partial.path, contents: nil,
            attributes: [.posixPermissions: 0o600, .protectionKey: FileProtectionType.complete]) else {
            throw Failure.unavailable
        }
        let handle = try FileHandle(forWritingTo: partial)
        var writeFailure: Error?
        do {
            try session.writeRecentEvidence { line in
                guard writeFailure == nil else { return }
                do { try handle.write(contentsOf: Data((line + "\n").utf8)) }
                catch { writeFailure = error }
            }
            if let failure = writeFailure { throw failure }
            try handle.synchronize()
            try handle.close()
        } catch { try? handle.close(); throw error }
        let target = directory.appendingPathComponent("recent-results.jsonl")
        try FileManager.default.moveItem(at: partial, to: target)
        return target
    }
}

struct RpcTestEvidenceShare: UIViewControllerRepresentable {
    let file: URL
    func makeUIViewController(context: Context) -> UIActivityViewController {
        UIActivityViewController(activityItems: [file], applicationActivities: nil)
    }
    func updateUIViewController(_ controller: UIActivityViewController, context: Context) {}
}
