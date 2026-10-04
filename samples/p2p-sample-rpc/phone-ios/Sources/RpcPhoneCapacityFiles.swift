import Darwin
import CryptoKit
import Foundation
import P2pKitRpcExample

enum RpcPhoneCapacityIOError: Error { case invalidRecord, filePolicy, io, resourceObservation, resourceRetirement }

/// Private app-container files transferred by an explicitly trusted USB developer connection, not an RPC service.
final class RpcPhoneCapacityFiles {
    private let directory: URL
    private var imported: Set<String> = []
    private static let names: Set<String> = ["prepared.txt", "inbox.txt", "stop.txt", "ready.txt", "telemetry.txt", "closed.txt", "failed.txt"]
    private static let stagingNames: Set<String> = [".incoming-inbox.txt", ".sealed-inbox.txt", ".incoming-stop.txt", ".sealed-stop.txt"]

    init(runLabel: String, requireNew: Bool = false) throws {
        guard let validLabel = runLabel.range(of: "^[a-z0-9-]{1,64}$", options: .regularExpression),
              validLabel == runLabel.startIndex..<runLabel.endIndex else {
            throw RpcPhoneCapacityIOError.invalidRecord
        }
        let base = try FileManager.default.url(for: .applicationSupportDirectory, in: .userDomainMask,
                                               appropriateFor: nil, create: true)
        let home = base.appendingPathComponent("rpc-capacity", isDirectory: true)
        try Self.prepareDirectory(home)
        directory = home.appendingPathComponent(runLabel, isDirectory: true)
        if requireNew && mkdir(directory.path, 0o700) != 0 { throw RpcPhoneCapacityIOError.filePolicy }
        // The app creates the selected slot. Developer copies are untrusted staging,
        // never an assertion that devicectl implements atomic/create-only publication.
        try Self.prepareDirectory(directory)
    }

    private static func withDescriptor<T>(_ descriptor: Int32, _ body: (Int32) throws -> T) throws -> T {
        guard descriptor >= 0 else { throw RpcPhoneCapacityIOError.io }
        let result: Result<T, Error>
        do { result = .success(try body(descriptor)) } catch { result = .failure(error) }
        guard Darwin.close(descriptor) == 0 else { throw RpcPhoneCapacityIOError.resourceRetirement }
        return try result.get()
    }

    private static func info(_ path: String, optional: Bool = false) throws -> stat? {
        var result = stat()
        if lstat(path, &result) != 0 {
            if optional && errno == ENOENT { return nil }
            throw RpcPhoneCapacityIOError.io
        }
        return result
    }

    private static func prepareDirectory(_ url: URL) throws {
        if try info(url.path, optional: true) == nil {
            try FileManager.default.createDirectory(at: url, withIntermediateDirectories: false,
                attributes: [.posixPermissions: 0o700, .protectionKey: FileProtectionType.complete])
        }
        try withDescriptor(open(url.path, O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC)) { fd in
            var current = stat()
            guard fstat(fd, &current) == 0, current.st_uid == getuid(),
                  current.st_mode & S_IFMT == S_IFDIR,
                  [0o700, 0o755].contains(Int(current.st_mode & 0o777)), fchmod(fd, 0o700) == 0 else {
                throw RpcPhoneCapacityIOError.filePolicy
            }
        }
        var excluded = url
        var values = URLResourceValues()
        values.isExcludedFromBackup = true
        try excluded.setResourceValues(values)
    }

    private func path(_ name: String) throws -> String {
        guard Self.names.union(Self.stagingNames).contains(name), let parent = try Self.info(directory.path), parent.st_uid == getuid(),
              parent.st_mode & S_IFMT == S_IFDIR, parent.st_mode & 0o777 == 0o700 else {
            throw RpcPhoneCapacityIOError.filePolicy
        }
        return directory.appendingPathComponent(name).path
    }

    func read(_ name: String, optional: Bool = false) throws -> String? {
        guard Self.names.contains(name) else { throw RpcPhoneCapacityIOError.filePolicy }
        if name == "inbox.txt" || name == "stop.txt" {
            if !imported.contains(name) {
                // Never consume an old, copied-directly or partially committed canonical input.
                guard try Self.info(path(name), optional: true) == nil else { throw RpcPhoneCapacityIOError.filePolicy }
                guard let seal = try readFile(".sealed-" + name, optional: true, developerInput: true) else {
                    if optional { return nil }
                    throw RpcPhoneCapacityIOError.invalidRecord
                }
                // A copied seal itself may be partial. No admission until its complete
                // fixed grammar is present; the coordinator's original deadline still applies.
                guard seal.range(of: "^schema=1\nname=(inbox|stop)\\.txt\nbytes=[1-9][0-9]{0,4}\nsha256=[a-f0-9]{64}\n$",
                                 options: .regularExpression) != nil else {
                    if optional { return nil }
                    throw RpcPhoneCapacityIOError.invalidRecord
                }
                guard let text = try readFile(".incoming-" + name, developerInput: true) else {
                    throw RpcPhoneCapacityIOError.invalidRecord
                }
                let digest = SHA256.hash(data: Data(text.utf8)).map { String(format: "%02x", $0) }.joined()
                let expected = "schema=1\nname=\(name)\nbytes=\(text.utf8.count)\nsha256=\(digest)\n"
                guard seal == expected else { throw RpcPhoneCapacityIOError.invalidRecord }
                try writeAtomic(name, text)
                imported.insert(name)
            }
        }
        return try readFile(name, optional: optional)
    }

    private func readFile(_ name: String, optional: Bool = false, developerInput: Bool = false) throws -> String? {
        let namePath = try path(name)
        guard let before = try Self.info(namePath, optional: optional) else { return nil }
        guard before.st_uid == getuid(), before.st_mode & S_IFMT == S_IFREG, before.st_nlink == 1,
              before.st_size >= 0, before.st_size <= 16_384 else { throw RpcPhoneCapacityIOError.filePolicy }
        guard before.st_mode & 0o777 == 0o600 || (developerInput && before.st_mode & 0o777 == 0o644) else {
            throw RpcPhoneCapacityIOError.filePolicy
        }
        if before.st_size == 0 && developerInput && optional { return nil }
        guard before.st_size > 0 else { throw RpcPhoneCapacityIOError.invalidRecord }
        return try Self.withDescriptor(open(namePath, O_RDONLY | O_NOFOLLOW | O_NONBLOCK | O_CLOEXEC)) { fd in
            var opened = stat()
            guard fstat(fd, &opened) == 0, opened.st_dev == before.st_dev, opened.st_ino == before.st_ino,
                  opened.st_mode == before.st_mode, opened.st_uid == before.st_uid,
                  opened.st_nlink == 1, opened.st_size == before.st_size else { throw RpcPhoneCapacityIOError.filePolicy }
            if developerInput {
                // Strengthen privacy of an exact regular developer-imported input BEFORE consuming it.
                guard fchmod(fd, 0o600) == 0 else { throw RpcPhoneCapacityIOError.filePolicy }
            }
            var bytes = [UInt8](repeating: 0, count: 16_385)
            var total = 0
            try bytes.withUnsafeMutableBytes { buffer in
                guard let start = buffer.baseAddress else { throw RpcPhoneCapacityIOError.io }
                while total < buffer.count {
                    let count = Darwin.read(fd, start.advanced(by: total), buffer.count - total)
                    if count < 0 {
                        if errno == EINTR { continue }
                        throw RpcPhoneCapacityIOError.io
                    }
                    if count == 0 { break }
                    total += count
                }
            }
            var after = stat()
            guard fstat(fd, &after) == 0, let named = try Self.info(namePath),
                  named.st_dev == opened.st_dev, named.st_ino == opened.st_ino, named.st_nlink == 1,
                  after.st_nlink == 1, total <= 16_384, off_t(total) == opened.st_size,
                  after.st_size == opened.st_size, after.st_uid == opened.st_uid, after.st_mode & 0o777 == 0o600,
                  after.st_mtimespec.tv_sec == opened.st_mtimespec.tv_sec,
                  after.st_mtimespec.tv_nsec == opened.st_mtimespec.tv_nsec,
                  bytes.prefix(total).allSatisfy({ $0 == 10 || (32...126).contains($0) }),
                  let text = String(bytes: bytes.prefix(total), encoding: .ascii) else {
                throw RpcPhoneCapacityIOError.invalidRecord
            }
            return text
        }
    }

    /// Only the rotating telemetry slot may replace a file. Other evidence is atomically create-only.
    func publish(_ name: String, _ text: String) throws {
        guard ["prepared.txt", "ready.txt", "telemetry.txt", "closed.txt", "failed.txt"].contains(name) else {
            throw RpcPhoneCapacityIOError.invalidRecord
        }
        try writeAtomic(name, text)
    }

    private func writeAtomic(_ name: String, _ text: String) throws {
        guard Self.names.contains(name),
              (1...16_384).contains(text.utf8.count),
              text.utf8.allSatisfy({ $0 == 10 || (32...126).contains($0) }) else {
            throw RpcPhoneCapacityIOError.invalidRecord
        }
        let target = try path(name)
        if name == "telemetry.txt" { _ = try read(name, optional: true) }
        let temporary = directory.appendingPathComponent(".capacity-" + UUID().uuidString).path
        var owned: stat?
        let writeResult: Result<Void, Error>
        do {
            try Self.withDescriptor(open(temporary, O_WRONLY | O_CREAT | O_EXCL | O_NOFOLLOW | O_CLOEXEC, 0o600)) { fd in
                var current = stat()
                guard fstat(fd, &current) == 0 else { throw RpcPhoneCapacityIOError.io }
                owned = current
                try Array(text.utf8).withUnsafeBytes { buffer in
                    guard let start = buffer.baseAddress else { throw RpcPhoneCapacityIOError.io }
                    var offset = 0
                    while offset < buffer.count {
                        let count = Darwin.write(fd, start.advanced(by: offset), buffer.count - offset)
                        if count < 0 && errno == EINTR { continue }
                        guard count > 0 else { throw RpcPhoneCapacityIOError.io }
                        offset += count
                    }
                }
                guard fsync(fd) == 0 else { throw RpcPhoneCapacityIOError.io }
            }
            let published = name == "telemetry.txt" ? rename(temporary, target) : link(temporary, target)
            guard published == 0 else { throw RpcPhoneCapacityIOError.io }
            try Self.withDescriptor(open(directory.path, O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC)) { fd in
                guard fsync(fd) == 0 else { throw RpcPhoneCapacityIOError.io }
            }
            writeResult = .success(())
        } catch { writeResult = .failure(error) }
        if let owned, let remaining = try Self.info(temporary, optional: true) {
            guard owned.st_dev == remaining.st_dev, owned.st_ino == remaining.st_ino,
                  remaining.st_mode & S_IFMT == S_IFREG, unlink(temporary) == 0 else {
                throw RpcPhoneCapacityIOError.resourceRetirement
            }
        }
        try writeResult.get()
    }
}

/// Actual self-process resource observation. Every acquired Mach send right and array is retired, even on failure.
enum RpcPhoneProcessSampler {
    /// Hash the actual installed signed executable. The owner's expected hash must come from that signed build.
    static func installedArtifact() throws -> String {
        guard let path = Bundle.main.executableURL?.path else { throw RpcPhoneCapacityIOError.resourceObservation }
        var before = stat()
        guard lstat(path, &before) == 0, before.st_mode & S_IFMT == S_IFREG,
              before.st_size > 0, before.st_size <= 128 * 1024 * 1024 else { throw RpcPhoneCapacityIOError.filePolicy }
        let fd = open(path, O_RDONLY | O_NOFOLLOW | O_NONBLOCK | O_CLOEXEC)
        guard fd >= 0 else { throw RpcPhoneCapacityIOError.io }
        let result: Result<String, Error>
        do {
            var opened = stat()
            guard fstat(fd, &opened) == 0, opened.st_dev == before.st_dev, opened.st_ino == before.st_ino,
                  opened.st_size == before.st_size else { throw RpcPhoneCapacityIOError.filePolicy }
            var hash = SHA256()
            var bytes = [UInt8](repeating: 0, count: 65_536)
            var total: Int64 = 0
            while true {
                let count = bytes.withUnsafeMutableBytes { Darwin.read(fd, $0.baseAddress, $0.count) }
                if count < 0 && errno == EINTR { continue }
                guard count >= 0 else { throw RpcPhoneCapacityIOError.io }
                if count == 0 { break }
                total += Int64(count)
                guard total <= before.st_size else { throw RpcPhoneCapacityIOError.filePolicy }
                hash.update(data: Data(bytes.prefix(count)))
            }
            var after = stat()
            guard fstat(fd, &after) == 0, total == before.st_size, after.st_size == before.st_size,
                  after.st_mtimespec.tv_sec == before.st_mtimespec.tv_sec,
                  after.st_mtimespec.tv_nsec == before.st_mtimespec.tv_nsec,
                  after.st_mode == before.st_mode, after.st_uid == before.st_uid else {
                throw RpcPhoneCapacityIOError.filePolicy
            }
            result = .success(hash.finalize().map { String(format: "%02x", $0) }.joined())
        } catch { result = .failure(error) }
        guard Darwin.close(fd) == 0 else { throw RpcPhoneCapacityIOError.resourceRetirement }
        return try result.get()
    }

    private static func nanos(_ time: timeval) throws -> Int64 {
        guard time.tv_sec >= 0, time.tv_sec <= Int64.max / 1_000_000_000,
              time.tv_usec >= 0, time.tv_usec < 1_000_000 else { throw RpcPhoneCapacityIOError.resourceObservation }
        let value = Int64(time.tv_sec) * 1_000_000_000
        let (sum, overflow) = value.addingReportingOverflow(Int64(time.tv_usec) * 1_000)
        guard !overflow else { throw RpcPhoneCapacityIOError.resourceObservation }
        return sum
    }

    static func sample() throws -> RpcPhoneProcessStats {
        var usage = rusage()
        guard getrusage(RUSAGE_SELF, &usage) == 0 else { throw RpcPhoneCapacityIOError.resourceObservation }
        let (cpu, overflow) = try nanos(usage.ru_utime).addingReportingOverflow(nanos(usage.ru_stime))
        guard !overflow else { throw RpcPhoneCapacityIOError.resourceObservation }
        var basic = mach_task_basic_info_data_t()
        var size = mach_msg_type_number_t(MemoryLayout<mach_task_basic_info_data_t>.size / MemoryLayout<integer_t>.size)
        let expected = size
        let read = withUnsafeMutablePointer(to: &basic) { pointer in
            pointer.withMemoryRebound(to: integer_t.self, capacity: Int(size)) {
                task_info(mach_task_self_, task_flavor_t(MACH_TASK_BASIC_INFO), $0, &size)
            }
        }
        guard read == KERN_SUCCESS, size == expected, basic.resident_size > 0,
              basic.resident_size <= UInt64(Int64.max) else { throw RpcPhoneCapacityIOError.resourceObservation }
        var array: thread_act_array_t?
        var count: mach_msg_type_number_t = 0
        guard task_threads(mach_task_self_, &array, &count) == KERN_SUCCESS else {
            throw RpcPhoneCapacityIOError.resourceObservation
        }
        guard let threads = array else { throw RpcPhoneCapacityIOError.resourceObservation }
        var retired = true
        for index in 0..<Int(count) {
            // Do not return on the first failed release: all remaining acquired rights still belong to us.
            if mach_port_deallocate(mach_task_self_, threads[index]) != KERN_SUCCESS { retired = false }
        }
        let bytes = vm_size_t(count) * vm_size_t(MemoryLayout<thread_t>.stride)
        if vm_deallocate(mach_task_self_, vm_address_t(UInt(bitPattern: threads)), bytes) != KERN_SUCCESS { retired = false }
        guard retired else { throw RpcPhoneCapacityIOError.resourceRetirement }
        guard count > 0, count <= 65_535 else { throw RpcPhoneCapacityIOError.resourceObservation }
        return try RpcPhoneProcessStats(cpuNanos: cpu, residentBytes: Int64(basic.resident_size), nativeThreads: Int32(count))
    }
}
