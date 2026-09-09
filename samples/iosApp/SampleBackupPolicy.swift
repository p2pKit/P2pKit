import Foundation

/// The named inbox/evidence roots retain their paths and default iOS protection.
/// Exclusion affects future backups, not already-backed-up or user-shared copies.
enum SampleBackupPolicy {
    static let startupWarning =
        "Could not exclude sample inbox or evidence storage from backups. " +
        "Existing content may still be backed up; affected receive/export operations " +
        "will be refused until storage setup succeeds."

    static func inboxDirectory() -> URL {
        FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0]
            .appendingPathComponent("P2pKitInbox", isDirectory: true)
    }

    static func excludeDirectoryFromBackup(_ directory: URL) throws {
        var values = URLResourceValues()
        values.isExcludedFromBackup = true
        var mutableDirectory = directory
        try mutableDirectory.setResourceValues(values)
    }

    static func prepareDirectory(
        at directory: URL,
        excludeFromBackup: (URL) throws -> Void = SampleBackupPolicy.excludeDirectoryFromBackup
    ) throws {
        do {
            try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
            try excludeFromBackup(directory)
        } catch let cancelled as CancellationError {
            throw cancelled
        } catch {
            throw PreparationError(cause: error)
        }
    }

    /// Attempt both independent roots at first appearance, even if one fails.
    /// Never infer readiness from a previous pass or from a directory's name.
    @MainActor
    static func prepareAtStartup(
        inbox: () throws -> Void,
        evidence: () throws -> Void
    ) throws -> String? {
        func failed(_ prepare: () throws -> Void) throws -> Bool {
            do {
                try prepare()
                return false
            } catch let cancelled as CancellationError {
                throw cancelled
            } catch {
                return true
            }
        }
        let inboxFailed = try failed(inbox)
        let evidenceFailed = try failed(evidence)
        return inboxFailed || evidenceFailed ? startupWarning : nil
    }

    /// The actual receive's cleanup/reservation/sink/accept action is downstream
    /// of this throwing gate; an exclusion failure must not run any of it.
    @MainActor
    static func withPreparedDirectory(
        at directory: URL,
        excludeFromBackup: (URL) throws -> Void = SampleBackupPolicy.excludeDirectoryFromBackup,
        operation: () async -> Void
    ) async throws {
        try Task.checkCancellation()
        try prepareDirectory(at: directory, excludeFromBackup: excludeFromBackup)
        try Task.checkCancellation()
        await operation()
    }

    struct PreparationError: LocalizedError {
        let cause: Error
        var errorDescription: String? {
            "Could not prepare sample storage for backup exclusion."
        }
    }
}
