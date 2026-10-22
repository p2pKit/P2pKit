import Foundation
import Darwin

/// Keep the SDK C functions distinct from their same-named imported structs.
/// The return value and errno belong to the original stat/flock call.
enum SampleTransferPOSIX {
    static func fileStatus(_ path: String, _ information: UnsafeMutablePointer<stat>) -> Int32 {
        path.withCString { p2pkit_sample_file_status($0, information) }
    }

    static func lockFile(_ descriptor: Int32, _ operation: Int32) -> Int32 {
        p2pkit_sample_lock_file(descriptor, operation)
    }
}

/// Only recorded, OS-unlocked staging directories may be reclaimed. Inbox
/// filenames and legacy sibling parts never confer deletion authority.
enum SampleTransferStaging {
    private static let rootName = ".p2pkit-ios-transfer-staging-v1"
    private static let magic = "p2pkit-ios-transfer-staging-v1\n"
    private static let monitor = NSLock()
    private static var active: Set<String> = []

    static func claim(in inbox: URL) throws -> Lease {
        monitor.lock()
        defer { monitor.unlock() }
        let root = try claimRoot(in: inbox)
        let token = UUID().uuidString.lowercased()
        let directory = root.appendingPathComponent(token, isDirectory: true)
        guard Darwin.mkdir(directory.path, S_IRWXU) == 0 else { throw posixError() }
        let lockURL = directory.appendingPathComponent("lease")
        let descriptor = Darwin.open(lockURL.path, O_CREAT | O_EXCL | O_RDWR | O_NOFOLLOW | O_CLOEXEC, S_IRUSR | S_IWUSR)
        guard descriptor >= 0 else {
            let failure = posixError()
            _ = Darwin.rmdir(directory.path)
            throw failure
        }
        do {
            guard SampleTransferPOSIX.lockFile(descriptor, LOCK_EX | LOCK_NB) == 0 else { throw posixError() }
            let record = directory.appendingPathComponent("ownership")
            try Data((magic + token + "\n").utf8).write(to: record, options: .withoutOverwriting)
            active.insert(directory.path)
            return Lease(directory: directory, descriptor: descriptor)
        } catch {
            _ = Darwin.close(descriptor)
            try? FileManager.default.removeItem(at: directory.appendingPathComponent("ownership"))
            _ = Darwin.unlink(lockURL.path)
            _ = Darwin.rmdir(directory.path)
            throw error
        }
    }

    static func reconcile(in inbox: URL) throws {
        monitor.lock()
        defer { monitor.unlock() }
        let fm = FileManager.default
        for root in try fm.contentsOfDirectory(
            at: inbox.resolvingSymlinksInPath(), includingPropertiesForKeys: nil
        ) where isRootName(root.lastPathComponent) {
            if isPlain(root, directory: false) { continue }
            guard isPlain(root, directory: true) else { throw stagingError("staging root is not a plain directory") }
            try reconcileRoot(root)
        }
    }

    private static func reconcileRoot(_ root: URL) throws {
        let fm = FileManager.default
        for directory in try fm.contentsOfDirectory(at: root, includingPropertiesForKeys: nil) {
            guard isPlain(directory, directory: true), !active.contains(directory.path),
                  UUID(uuidString: directory.lastPathComponent)?.uuidString.lowercased() == directory.lastPathComponent else {
                continue
            }
            let record = directory.appendingPathComponent("ownership")
            let lockURL = directory.appendingPathComponent("lease")
            guard isPlain(record, directory: false), isPlain(lockURL, directory: false) else { continue }
            let expected = Data((magic + directory.lastPathComponent + "\n").utf8)
            let input = try FileHandle(forReadingFrom: record)
            let actual: Data?
            do {
                actual = try input.read(upToCount: expected.count + 1)
                try input.close()
            } catch {
                try? input.close()
                throw error
            }
            guard actual == expected else { continue }
            let descriptor = Darwin.open(lockURL.path, O_RDWR | O_NOFOLLOW | O_CLOEXEC)
            guard descriptor >= 0 else { throw posixError() }
            defer { Darwin.close(descriptor) }
            if SampleTransferPOSIX.lockFile(descriptor, LOCK_EX | LOCK_NB) != 0 {
                if errno == EWOULDBLOCK { continue }
                throw posixError()
            }
            guard try safeContents(directory) else { continue }
            try removeParts(directory)
            try fm.removeItem(at: record)
            // Darwin permits unlink of our locked inode; no UUID directory is reused.
            try fm.removeItem(at: lockURL)
            guard Darwin.rmdir(directory.path) == 0 else { throw posixError() }
        }
    }

    private static func claimRoot(in inbox: URL) throws -> URL {
        for index in 0...1000 {
            let name = index == 0 ? rootName : "\(rootName).\(index)"
            let root = inbox.resolvingSymlinksInPath().appendingPathComponent(name)
            if Darwin.mkdir(root.path, S_IRWXU) != 0 && errno != EEXIST { throw posixError() }
            if isPlain(root, directory: false) { continue } // Never reject/delete an older completed filename.
            guard isPlain(root, directory: true) else { throw stagingError("staging root is not a plain directory") }
            return root
        }
        throw stagingError("could not claim an available staging namespace")
    }

    private static func isRootName(_ name: String) -> Bool {
        if name == rootName { return true }
        guard name.hasPrefix(rootName + "."), let index = Int(name.dropFirst(rootName.count + 1)) else { return false }
        return (1...1000).contains(index) && name == "\(rootName).\(index)"
    }

    private static func isPlain(_ url: URL, directory: Bool) -> Bool {
        var information = stat()
        guard Darwin.lstat(url.path, &information) == 0 else { return false }
        let expected = directory ? S_IFDIR : S_IFREG
        return information.st_mode & S_IFMT == expected &&
            url.resolvingSymlinksInPath().standardizedFileURL.path == url.standardizedFileURL.path
    }

    private static func isPart(_ url: URL) -> Bool { url.lastPathComponent.hasSuffix(".p2pkit-part") }

    private static func safeContents(_ directory: URL) throws -> Bool {
        try FileManager.default.contentsOfDirectory(at: directory, includingPropertiesForKeys: nil).allSatisfy {
            isPlain($0, directory: false) &&
                ($0.lastPathComponent == "ownership" || $0.lastPathComponent == "lease" || isPart($0))
        }
    }

    private static func removeParts(_ directory: URL) throws {
        for entry in try FileManager.default.contentsOfDirectory(at: directory, includingPropertiesForKeys: nil)
            where isPart(entry) {
            try FileManager.default.removeItem(at: entry)
        }
    }

    private static func posixError() -> NSError { NSError(domain: NSPOSIXErrorDomain, code: Int(errno)) }
    private static func stagingError(_ message: String) -> NSError {
        NSError(domain: "dev.p2pkit.sample.staging", code: 1, userInfo: [NSLocalizedDescriptionKey: message])
    }

    final class Lease {
        let directory: URL
        private var descriptor: Int32
        private var retired = false

        fileprivate init(directory: URL, descriptor: Int32) {
            self.directory = directory
            self.descriptor = descriptor
        }

        /// Invoke only once the transfer sink has been closed by commit/abort.
        func retire() throws {
            monitor.lock()
            defer { monitor.unlock() }
            if retired { return }
            guard try safeContents(directory) else { throw stagingError("unexpected staging entry") }
            try removeParts(directory)
            let fm = FileManager.default
            let record = directory.appendingPathComponent("ownership")
            if fm.fileExists(atPath: record.path) { try fm.removeItem(at: record) }
            if descriptor >= 0 {
                let owned = descriptor
                descriptor = -1
                guard Darwin.close(owned) == 0 else { throw posixError() }
            }
            let lockURL = directory.appendingPathComponent("lease")
            if fm.fileExists(atPath: lockURL.path) { try fm.removeItem(at: lockURL) }
            guard Darwin.rmdir(directory.path) == 0 else { throw posixError() }
            active.remove(directory.path)
            retired = true
        }

        deinit {
            // No recursive/unproven deletion from deinit. A process that loses
            // this object releases its lease; the next lifecycle can reconcile.
            if descriptor >= 0 { Darwin.close(descriptor) }
            monitor.lock()
            active.remove(directory.path)
            monitor.unlock()
        }
    }
}
