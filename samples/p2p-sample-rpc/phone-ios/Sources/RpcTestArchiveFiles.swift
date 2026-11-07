import Darwin
import Foundation
import P2pKitRpcExample

struct RpcTestArchiveFiles {
    enum Failure: Error { case invalidArchive }
    let directory: URL

    private func deleted(_ runId: String) throws -> Bool {
        let marker = directory.appendingPathComponent(runId + ".deleted")
        if !FileManager.default.fileExists(atPath: marker.path) { return false }
        guard try read(marker) == runId else { throw Failure.invalidArchive }
        return true
    }

    private func read(_ file: URL) throws -> String {
        var before = stat()
        guard lstat(file.path, &before) == 0, before.st_mode & S_IFMT == S_IFREG,
            before.st_nlink == 1, before.st_size > 0, before.st_size <= 65_536 else { throw Failure.invalidArchive }
        let descriptor = open(file.path, O_RDONLY | O_NOFOLLOW | O_NONBLOCK)
        guard descriptor >= 0 else { throw Failure.invalidArchive }
        let handle = FileHandle(fileDescriptor: descriptor, closeOnDealloc: false)
        defer { try? handle.close() }
        var opened = stat()
        guard fstat(descriptor, &opened) == 0, opened.st_ino == before.st_ino,
            opened.st_dev == before.st_dev, opened.st_size == before.st_size else { throw Failure.invalidArchive }
        var data = Data()
        while data.count < Int(before.st_size) {
            guard let next = try handle.read(upToCount: Int(before.st_size) - data.count), !next.isEmpty else {
                throw Failure.invalidArchive
            }
            data.append(next)
        }
        guard (try handle.read(upToCount: 1))?.isEmpty != false else { throw Failure.invalidArchive }
        var after = stat()
        guard lstat(file.path, &after) == 0, after.st_ino == before.st_ino, after.st_dev == before.st_dev,
            after.st_size == before.st_size, let text = String(data: data, encoding: .utf8) else {
            throw Failure.invalidArchive
        }
        return text
    }

    private func visit(_ accept: (String, String) throws -> Void) throws {
        if !FileManager.default.fileExists(atPath: directory.path) { return }
        var info = stat()
        guard lstat(directory.path, &info) == 0, info.st_mode & S_IFMT == S_IFDIR else { throw Failure.invalidArchive }
        var scanFailure: Error?
        guard let entries = FileManager.default.enumerator(at: directory,
            includingPropertiesForKeys: nil, options: [.skipsSubdirectoryDescendants], errorHandler: { _, error in
                scanFailure = error
                return false
            }) else { throw Failure.invalidArchive }
        var count = 0
        for case let file as URL in entries {
            try Task.checkCancellation()
            count += 1
            guard count <= 2_000_000 else { throw Failure.invalidArchive }
            let name = file.lastPathComponent
            guard name.range(of: "^[a-f0-9]{32}\\.json$", options: .regularExpression) != nil else { continue }
            let runId = String(name.dropLast(5))
            if try !deleted(runId) {
                try accept(runId, read(file))
            }
        }
        if let error = scanFailure { throw error }
    }

    func browse(beforeMillis: Int64 = Int64.max, beforeRunId: String = "") throws -> RpcTestArchivePage {
        let scan = RpcTestArchiveScan(beforeMillis: beforeMillis, beforeRunId: beforeRunId)
        try visit { id, text in try scan.accept(runId: id, text: text) }
        return try scan.finish()
    }

    func export(_ append: @escaping (String) -> Void, runId: String? = nil) throws {
        let writer = RpcTestEvidenceWriter(recentOnly: false, appendLine: append)
        if let id = runId {
            guard id.range(of: "^[a-f0-9]{32}$", options: .regularExpression) != nil,
                try !deleted(id) else {
                throw Failure.invalidArchive
            }
            try writer.append(runId: id, text: read(directory.appendingPathComponent(id + ".json")))
        } else { try visit { id, text in try writer.append(runId: id, text: text) } }
        try writer.finish()
    }
}
