import CryptoKit
import Foundation

/// CPU/file work only: never capture a kit, transfer, diagnostic store or view.
/// The caller must use SampleRunLifecycle.prepare so Stop cancels AND joins it.
enum SampleFilePreparation {
    static let chunkSize = 64 * 1024

    struct Snapshot: Sendable {
        let data: Data
        let digest: [UInt8]
        var sha256Hex: String { digest.map { String(format: "%02x", $0) }.joined() }
    }

    static func preset(
        byteCount: Int,
        checkCancellation: () throws -> Void = { try Task.checkCancellation() }
    ) throws -> Snapshot {
        precondition(byteCount >= 0)
        try checkCancellation()
        var data = Data()
        var hasher = SHA256()
        while data.count < byteCount {
            try checkCancellation()
            let offset = data.count
            let count = min(chunkSize, byteCount - offset)
            var chunk = Data(count: count)
            for index in 0..<count {
                chunk[index] = UInt8(truncatingIfNeeded: (offset + index) &* 31 &+ 7)
            }
            try checkCancellation()
            hasher.update(data: chunk)
            data.append(chunk)
        }
        try checkCancellation()
        return Snapshot(data: data, digest: Array(hasher.finalize()))
    }

    static func sha256File(
        at url: URL,
        checkCancellation: () throws -> Void = { try Task.checkCancellation() }
    ) throws -> String {
        try checkCancellation()
        let handle = try FileHandle(forReadingFrom: url)
        defer { try? handle.close() }
        var hasher = SHA256()
        while true {
            try checkCancellation()
            let chunk = try handle.read(upToCount: chunkSize) ?? Data()
            if chunk.isEmpty { break }
            try checkCancellation()
            hasher.update(data: chunk)
        }
        try checkCancellation()
        return hasher.finalize().map { String(format: "%02x", $0) }.joined()
    }
}
