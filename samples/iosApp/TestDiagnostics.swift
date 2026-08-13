import CryptoKit
import Darwin
import Foundation
import SwiftUI
import UIKit
import P2pKitShared

// Test-harness diagnostics only. This file never participates in protocol
// decisions and never records payload contents, credentials, or raw device IDs.

enum TestDiagnosticSeverity: String, Codable, CaseIterable {
    case debug = "DEBUG"
    case info = "INFO"
    case warning = "WARNING"
    case error = "ERROR"

    var rank: Int {
        switch self {
        case .debug: return 0
        case .info: return 1
        case .warning: return 2
        case .error: return 3
        }
    }
}

enum TestDiagnosticDirection: String, Codable {
    case sent = "SENT"
    case received = "RECEIVED"
    case local = "LOCAL"
}

enum TestDiagnosticOutcome: String, Codable, CaseIterable {
    case success = "SUCCESS"
    case failure = "FAILURE"
    case cancellation = "CANCELLATION"
    case timeout = "TIMEOUT"
    case interruption = "INTERRUPTION"
    case recovery = "RECOVERY"
    case blocked = "BLOCKED"
}

struct TestDiagnosticEvent: Codable, Identifiable, Equatable {
    var id: Int64 { index }

    let schemaVersion: Int
    let index: Int64
    let timestamp: String
    let platform: String
    let operatingSystem: String
    let applicationVersion: String
    let buildNumber: String
    let gitCommitSha: String
    let safeDeviceId: String
    let testSessionId: String
    let testId: String
    let role: String
    let peerId: String?
    let connectionId: String?
    let transferId: String?
    let category: String
    let eventName: String
    let severity: TestDiagnosticSeverity
    let currentState: String?
    let previousState: String?
    let protocolVersion: String?
    let packetType: String?
    let direction: TestDiagnosticDirection
    let payloadSizeBytes: Int64?
    let sequenceNumber: Int64?
    let chunkNumber: Int?
    let chunkCount: Int?
    let retryNumber: Int?
    let timeoutMillis: Int64?
    let retryDelayMillis: Int64?
    let durationMillis: Int64?
    let errorCode: String?
    let errorDescription: String?
    let outcome: TestDiagnosticOutcome?
    let details: [String: String]
    let redactedFields: [String]
}

struct TestDiagnosticConnectionSnapshot {
    let rawConnectionId: String
    let peerId: String
    let state: String
}

struct TestDiagnosticRecord {
    var peerId: String?
    var connectionId: String?
    var transferId: String?
    var category: String
    var eventName: String
    var severity: TestDiagnosticSeverity = .info
    var currentState: String?
    var previousState: String?
    var protocolVersion: String? = "secure-v2"
    var packetType: String?
    var direction: TestDiagnosticDirection = .local
    var payloadSizeBytes: Int64?
    var sequenceNumber: Int64?
    var chunkNumber: Int?
    var chunkCount: Int?
    var retryNumber: Int?
    var timeoutMillis: Int64?
    var retryDelayMillis: Int64?
    var durationMillis: Int64?
    var errorCode: String?
    var errorDescription: String?
    var outcome: TestDiagnosticOutcome?
    var details: [String: String] = [:]
}

enum TestDiagnosticEventName {
    static let applicationStarted = "application.started"
    static let applicationShutdown = "application.shutdown"
    static let applicationBackgrounded = "application.backgrounded"
    static let applicationForegrounded = "application.foregrounded"
    static let testModeActivated = "test.mode.activated"
    static let testSessionCreated = "test.session.created"
    static let testSessionCompleted = "test.session.completed"
    static let peerInitialized = "peer.local.initialized"
    static let discoveryStarted = "discovery.started"
    static let peerDiscovered = "discovery.peer.discovered"
    static let peerLost = "discovery.peer.lost"
    static let discoveryStopped = "discovery.stopped"
    static let connectionAttempted = "connection.attempted"
    static let connectionAuthenticated = "connection.authentication.succeeded"
    static let connectionAuthenticationFailed = "connection.authentication.failed"
    static let connectionStateChanged = "connection.state.changed"
    static let connectionDisconnected = "connection.disconnected"
    static let protocolNegotiated = "protocol.secure_v2.negotiated"
    static let packetSent = "protocol.packet.sent"
    static let packetReceived = "protocol.packet.received"
    static let packetRejected = "protocol.packet.rejected"
    static let metadataCreated = "metadata.envelope.created"
    static let metadataSent = "metadata.envelope.sent"
    static let metadataReceived = "metadata.envelope.received"
    static let metadataValidated = "metadata.envelope.validated"
    static let metadataRejected = "metadata.envelope.rejected"
    static let fileGenerated = "file.generated"
    static let senderHash = "file.sender.sha256"
    static let receiverHash = "file.receiver.sha256"
    static let integrityChecked = "file.integrity.checked"
    static let transferPrepared = "transfer.prepared"
    static let offerReceived = "transfer.offer.received"
    static let offerAccepted = "transfer.offer.accepted"
    static let offerRejected = "transfer.offer.rejected"
    static let transferStarted = "transfer.started"
    static let transferProgress = "transfer.progress.milestone"
    static let transferRetry = "transfer.retry.attempted"
    static let transferAcknowledgment = "transfer.acknowledgment"
    static let transferInterrupted = "transfer.interrupted"
    static let transferCancelled = "transfer.cancelled"
    static let transferResumed = "transfer.resumed"
    static let transferDurableCommitted = "transfer.durable.committed"
    static let transferCompleted = "transfer.completed"
    static let transferFailed = "transfer.failed"
    static let temporaryFileCreated = "storage.temporary_file.created"
    static let temporaryFileCleaned = "storage.temporary_file.cleaned"
    static let networkPathChanged = "network.path.changed"
    static let recoveryStarted = "recovery.started"
    static let recoveryCompleted = "recovery.completed"
    static let timeoutExpired = "timeout.expired"
    static let faultInjected = "fault.injected"
    static let sdkLog = "sdk.log"
    static let transportLog = "transport.log"
    static let evidenceExported = "evidence.exported"
    static let diagnosticFailure = "diagnostics.failure"
}

struct TestDiagnosticTransferSummary: Codable, Equatable {
    let transferId: String
    let connectionIds: [String]
    let peerIds: [String]
    let senderFileSizeBytes: Int64?
    let receiverFileSizeBytes: Int64?
    let senderSha256: String?
    let receiverSha256: String?
    let integrityMatch: Bool?
}

struct TestDiagnosticSummary: Codable {
    let schemaVersion: Int
    let testId: String
    let testSessionId: String
    let role: String
    let platform: String
    let operatingSystem: String
    let applicationVersion: String
    let buildNumber: String
    let gitCommitSha: String
    let safeDeviceId: String
    let startTimestamp: String?
    let endTimestamp: String?
    let protocolVersion: String
    let connectionIds: [String]
    let transferIds: [String]
    let peerIds: [String]
    let transferSummaries: [TestDiagnosticTransferSummary]
    let selectedTransferId: String?
    let senderFileSizeBytes: Int64?
    let receiverFileSizeBytes: Int64?
    let senderSha256: String?
    let receiverSha256: String?
    let integrityMatch: Bool?
    let finalState: String?
    let finalOutcome: TestDiagnosticOutcome?
    let warningCount: Int
    let errorCount: Int
    let eventCount: Int
    let droppedEventCount: Int64
    let configuration: [String: String]
    let manualEvidenceStillRequired: [String]
}

enum TestDiagnosticEvidenceError: LocalizedError {
    case reservedFilename(String)
    case invalidChecksumManifest

    var errorDescription: String? {
        switch self {
        case .reservedFilename(let name):
            return "Diagnostic evidence tried to replace reserved file \(name)"
        case .invalidChecksumManifest:
            return "Diagnostic evidence checksum manifest is incomplete or ambiguous"
        }
    }
}

@MainActor
final class IOSTestDiagnosticStore: ObservableObject {
    private static let maxEvents = 5_000
    private static let maxEncodedBytes = 5 * 1_024 * 1_024
    private static let maxPersistedFileBytes: UInt64 = 2 * 1_024 * 1_024
    private static let maxPersistedFiles = 4
    private static let defaultsTest = "P2pKitDiagnostics.activeTest"
    private static let defaultsSession = "P2pKitDiagnostics.activeSession"
    private static let defaultsRole = "P2pKitDiagnostics.activeRole"

    @Published private(set) var events: [TestDiagnosticEvent] = []
    @Published private(set) var activeTestId: String
    @Published private(set) var activeSessionId: String
    @Published private(set) var activeRole: String
    @Published private(set) var activeConnectionId: String?
    @Published private(set) var activeTransferId: String?
    @Published private(set) var currentConnectionState: String = "idle"
    @Published private(set) var currentTransferState: String = "idle"
    @Published private(set) var progress: Double = 0
    @Published private(set) var senderSha256: String?
    @Published private(set) var receiverSha256: String?
    @Published private(set) var integrityMatch: Bool?
    @Published private(set) var finalOutcome: TestDiagnosticOutcome?
    @Published var displayPaused = false

    let platform = "ios"
    let operatingSystem = "\(UIDevice.current.systemName) \(UIDevice.current.systemVersion)"
    let applicationVersion: String
    let buildNumber: String
    let gitCommitSha = BuildInfo.shared.COMMIT
    let safeDeviceId: String
    let configuration: [String: String] = [
        "testMode": "true",
        "protocolVersion": "secure-v2",
        "keepAlivePingMillis": "2000",
        "keepAliveTimeoutMillis": "6000",
        "maximumSampleFileBytes": "52428800",
        "diagnosticRetention": "5000-events/5MiB-memory/4x2MiB-disk",
        "faultInjection": "none"
    ]

    private var nextIndex: Int64 = 1
    private var encodedBytes = 0
    private var droppedEvents: Int64 = 0
    private var sessionStart = Date()
    private var localPeerId: String?
    private var connectionsBySession: [String: Correlation] = [:]
    private var connectionsByPeer: [String: SessionCorrelation] = [:]
    private var transferCorrelations: [String: TransferOwnership] = [:]
    private var transferEvidence: [String: TransferEvidence] = [:]
    private let encoder: JSONEncoder
    private let logDirectory: URL
    private let evidenceDirectory: URL
    private let defaults: UserDefaults

    private struct TransferEvidence {
        var senderFileSizeBytes: Int64? = nil
        var receiverFileSizeBytes: Int64? = nil
        var senderSha256: String? = nil
        var receiverSha256: String? = nil

        var integrityMatch: Bool? {
            guard let senderSha256, let receiverSha256 else { return nil }
            return senderSha256 == receiverSha256
        }
    }

    private struct Correlation {
        let peerId: String
        let connectionId: String
        let transferId: String?
    }

    private struct TransferOwnership {
        let correlation: Correlation?
        let ambiguous: Bool
    }

    private struct SessionCorrelation {
        let rawConnectionId: String
        let correlation: Correlation
    }

    init(
        baseDirectory: URL? = nil,
        evidenceDirectory: URL? = nil,
        defaults: UserDefaults = .standard
    ) {
        self.defaults = defaults
        applicationVersion = Bundle.main.object(
            forInfoDictionaryKey: "CFBundleShortVersionString"
        ) as? String ?? "0"
        buildNumber = Bundle.main.object(
            forInfoDictionaryKey: "CFBundleVersion"
        ) as? String ?? "0"
        let vendor = UIDevice.current.identifierForVendor?.uuidString ?? "ios-simulator"
        safeDeviceId = "ios-" + String(Self.sha256(Data(vendor.utf8)).prefix(16))
        activeTestId = Self.normalizedTestId(
            defaults.string(forKey: Self.defaultsTest) ?? "UNASSIGNED"
        )
        activeSessionId = Self.normalizedSessionId(
            defaults.string(forKey: Self.defaultsSession)
                ?? "session-\(UUID().uuidString.replacingOccurrences(of: "-", with: "").prefix(12))"
        )
        activeRole = Self.normalizedRole(
            defaults.string(forKey: Self.defaultsRole) ?? "both"
        )
        localPeerId = nil
        encoder = JSONEncoder()
        encoder.outputFormatting = [.sortedKeys, .withoutEscapingSlashes]
        if let baseDirectory {
            logDirectory = baseDirectory
        } else {
            let base = FileManager.default.urls(
                for: .applicationSupportDirectory,
                in: .userDomainMask
            )[0]
            logDirectory = base.appendingPathComponent(
                "P2pKitTestDiagnostics",
                isDirectory: true
            )
        }
        if let evidenceDirectory {
            self.evidenceDirectory = evidenceDirectory
        } else {
            self.evidenceDirectory = FileManager.default.urls(
                for: .documentDirectory,
                in: .userDomainMask
            )[0].appendingPathComponent("P2pKitEvidence", isDirectory: true)
        }
        try? FileManager.default.createDirectory(
            at: logDirectory,
            withIntermediateDirectories: true
        )
        record(TestDiagnosticRecord(
            category: "application",
            eventName: TestDiagnosticEventName.applicationStarted,
            currentState: "running",
            details: ["diagnosticsMode": "explicit-test-harness"]
        ))
        if defaults.string(forKey: Self.defaultsSession) != nil {
            record(TestDiagnosticRecord(
                category: "recovery",
                eventName: TestDiagnosticEventName.recoveryStarted,
                currentState: "process-restarted",
                outcome: .recovery,
                details: ["retainedSession": "true"]
            ))
        }
    }

    @discardableResult
    func startSession(
        testId: String,
        requestedSessionId: String?,
        role: String,
        activeConnections: [TestDiagnosticConnectionSnapshot] = []
    ) -> String {
        activeTestId = Self.normalizedTestId(testId)
        activeSessionId = Self.normalizedSessionId(
            requestedSessionId?.isEmpty == false
                ? requestedSessionId!
                : "session-\(UUID().uuidString.replacingOccurrences(of: "-", with: "").prefix(12))"
        )
        activeRole = Self.normalizedRole(role)
        activeConnectionId = nil
        activeTransferId = nil
        currentConnectionState = "idle"
        currentTransferState = "idle"
        progress = 0
        senderSha256 = nil
        receiverSha256 = nil
        integrityMatch = nil
        transferEvidence.removeAll()
        connectionsBySession.removeAll()
        connectionsByPeer.removeAll()
        transferCorrelations.removeAll()
        finalOutcome = nil
        sessionStart = Date()
        defaults.set(activeTestId, forKey: Self.defaultsTest)
        defaults.set(activeSessionId, forKey: Self.defaultsSession)
        defaults.set(activeRole, forKey: Self.defaultsRole)
        record(TestDiagnosticRecord(
            category: "test",
            eventName: TestDiagnosticEventName.testSessionCreated,
            currentState: "active",
            details: ["testMode": "true"]
        ))
        record(TestDiagnosticRecord(
            category: "test",
            eventName: TestDiagnosticEventName.testModeActivated,
            currentState: "enabled"
        ))
        for connection in activeConnections {
            self.connection(
                peerId: connection.peerId,
                rawConnectionId: connection.rawConnectionId,
                state: connection.state,
                previous: nil,
                sessionSnapshot: true
            )
        }
        return activeSessionId
    }

    func complete(_ outcome: TestDiagnosticOutcome, reason: String) {
        finalOutcome = outcome
        let failure = outcome != .success && outcome != .recovery
        record(TestDiagnosticRecord(
            category: "test",
            eventName: TestDiagnosticEventName.testSessionCompleted,
            severity: failure ? .error : .info,
            currentState: outcome.rawValue,
            durationMillis: Int64(Date().timeIntervalSince(sessionStart) * 1_000),
            errorCode: failure ? "TEST_NOT_SUCCESSFUL" : nil,
            errorDescription: failure ? reason : nil,
            outcome: outcome,
            details: ["reason": reason]
        ))
    }

    func setLocalPeerId(_ peerId: String?) {
        let normalized = peerId?.trimmingCharacters(in: .whitespacesAndNewlines)
        let next = normalized?.isEmpty == false ? normalized : nil
        guard localPeerId != next else { return }
        localPeerId = next
        connectionsBySession.removeAll()
        connectionsByPeer.removeAll()
        transferCorrelations.removeAll()
    }

    func connectionId(for peerId: String) -> String? {
        connectionsByPeer[peerId]?.correlation.connectionId
    }

    @discardableResult
    func removeConnection(rawConnectionId: String) -> String? {
        guard let removed = connectionsBySession.removeValue(forKey: rawConnectionId) else {
            return nil
        }
        if connectionsByPeer[removed.peerId]?.rawConnectionId == rawConnectionId {
            connectionsByPeer[removed.peerId] = nil
        }
        // Reconnects to the same peer intentionally share a correlation id
        // within one test session. Keep bounded transfer ownership until the
        // session resets so a late close from the retired SDK session cannot
        // erase transfers owned by its replacement.
        return removed.connectionId
    }

    func record(_ input: TestDiagnosticRecord) {
        let redacted = Self.redact(input.details)
        let event = TestDiagnosticEvent(
            schemaVersion: 1,
            index: nextIndex,
            timestamp: Self.timestamp(),
            platform: platform,
            operatingSystem: operatingSystem,
            applicationVersion: applicationVersion,
            buildNumber: buildNumber,
            gitCommitSha: gitCommitSha,
            safeDeviceId: safeDeviceId,
            testSessionId: activeSessionId,
            testId: activeTestId,
            role: activeRole,
            peerId: input.peerId.map(Self.anonymized),
            connectionId: input.connectionId.flatMap(Self.safeIdentifier),
            transferId: input.transferId.flatMap(Self.safeIdentifier),
            category: Self.stableName(input.category),
            eventName: Self.stableName(input.eventName),
            severity: input.severity,
            currentState: input.currentState.map(Self.redactText),
            previousState: input.previousState.map(Self.redactText),
            protocolVersion: input.protocolVersion,
            packetType: input.packetType.map(Self.stableName),
            direction: input.direction,
            payloadSizeBytes: input.payloadSizeBytes,
            sequenceNumber: input.sequenceNumber,
            chunkNumber: input.chunkNumber,
            chunkCount: input.chunkCount,
            retryNumber: input.retryNumber,
            timeoutMillis: input.timeoutMillis,
            retryDelayMillis: input.retryDelayMillis,
            durationMillis: input.durationMillis,
            errorCode: input.errorCode.map(Self.stableName),
            errorDescription: input.errorDescription.map(Self.redactText),
            outcome: input.outcome,
            details: redacted.values,
            redactedFields: redacted.fields
        )
        nextIndex += 1
        guard let data = try? encoder.encode(event) else {
            droppedEvents += 1
            return
        }
        events.append(event)
        encodedBytes += data.count + 1
        while events.count > Self.maxEvents || encodedBytes > Self.maxEncodedBytes {
            guard let first = events.first,
                  let bytes = try? encoder.encode(first).count else { break }
            events.removeFirst()
            encodedBytes -= bytes + 1
            droppedEvents += 1
        }
        do {
            try persist(data + Data([0x0a]))
        } catch {
            // Diagnostics must never change protocol behavior.
            droppedEvents += 1
        }
    }

    func recordLegacy(tag: String, message: String) {
        let lower = message.lowercased()
        let severity: TestDiagnosticSeverity =
            lower.contains("failed") || lower.contains("threw") ? .error :
            lower.contains("warn") ? .warning : .debug
        record(TestDiagnosticRecord(
            category: "application",
            eventName: "application.\(Self.stableName(tag)).observation",
            severity: severity,
            errorCode: severity == .error ? "APPLICATION_OPERATION_FAILED" : nil,
            errorDescription: severity == .error ? message : nil,
            details: ["message": message]
        ))
    }

    func recordTransport(_ line: String) {
        let lower = line.lowercased()
        var eventName = TestDiagnosticEventName.transportLog
        var severity: TestDiagnosticSeverity = .debug
        if lower.contains("path") {
            eventName = TestDiagnosticEventName.networkPathChanged
        } else if lower.contains("reconnect") && lower.contains("succeeded") {
            eventName = TestDiagnosticEventName.recoveryCompleted
        } else if lower.contains("reconnect") {
            eventName = TestDiagnosticEventName.recoveryStarted
        } else if (lower.contains("file") || lower.contains("transfer")) &&
                    lower.contains("retry") {
            eventName = TestDiagnosticEventName.transferRetry
        } else if lower.contains("timeout") {
            eventName = TestDiagnosticEventName.timeoutExpired
            severity = .warning
        } else if lower.contains("reject") || lower.contains("malformed") ||
                    lower.contains("oversized") || lower.contains("duplicate") ||
                    lower.contains("replay") {
            eventName = TestDiagnosticEventName.packetRejected
            severity = .warning
        } else if lower.contains("auth") && lower.contains("fail") {
            eventName = TestDiagnosticEventName.connectionAuthenticationFailed
            severity = .error
        }
        record(TestDiagnosticRecord(
            category: "transport",
            eventName: eventName,
            severity: severity,
            errorCode: severity == .error ? "TRANSPORT_OPERATION_FAILED" : nil,
            details: ["line": line]
        ))
    }

    func recordFrame(_ line: String) {
        let expression = try? NSRegularExpression(
            pattern: #"^(TX|RX)\s+type=([A-Za-z0-9_]+)\s+len=(\d+)B(?:\s+chunk=(\d+)/(\d+)\s+id=([A-Za-z0-9]+)(?:\s+LAST)?)?(?:\s+xfer=([A-Za-z0-9._-]+))?.*$"#
        )
        let range = NSRange(line.startIndex..., in: line)
        guard let match = expression?.firstMatch(in: line, range: range),
              let directionRange = Range(match.range(at: 1), in: line),
              let packetRange = Range(match.range(at: 2), in: line),
              let lengthRange = Range(match.range(at: 3), in: line) else {
            record(TestDiagnosticRecord(
                category: "protocol",
                eventName: TestDiagnosticEventName.transportLog,
                severity: .debug,
                details: ["frame": line]
            ))
            return
        }
        let sent = line[directionRange] == "TX"
        let packet = String(line[packetRange])
        let size = Int64(line[lengthRange])
        let chunk = match.range(at: 4).location == NSNotFound ? nil :
            Range(match.range(at: 4), in: line).flatMap { Int(line[$0]) }
        let messageId = match.range(at: 6).location == NSNotFound ? nil :
            Range(match.range(at: 6), in: line).map { String(line[$0]) }
        let explicitTransfer = match.range(at: 7).location == NSNotFound ? nil :
            Range(match.range(at: 7), in: line).map { String(line[$0]) }
        let transfer = explicitTransfer ?? (packet == "FILE_DATA" ? messageId : nil)
        let correlation = transfer.flatMap { transferCorrelations[$0]?.correlation }
        record(TestDiagnosticRecord(
            peerId: correlation?.peerId,
            connectionId: correlation?.connectionId,
            transferId: transfer,
            category: "protocol",
            eventName: sent ? TestDiagnosticEventName.packetSent : TestDiagnosticEventName.packetReceived,
            packetType: packet,
            direction: sent ? .sent : .received,
            payloadSizeBytes: size,
            chunkNumber: chunk,
            details: ["rawFrameRedacted": Self.redactText(line)]
        ))
    }

    func connection(
        peerId: String,
        rawConnectionId: String,
        state: String,
        previous: String?,
        sessionSnapshot: Bool = false
    ) {
        guard let correlation = derivedConnection(peerId: peerId) else { return }
        activeConnectionId = correlation.connectionId
        connectionsBySession = connectionsBySession.filter {
            $0.key == rawConnectionId || $0.value.peerId != peerId
        }
        connectionsBySession[rawConnectionId] = correlation
        connectionsByPeer[peerId] = SessionCorrelation(
            rawConnectionId: rawConnectionId,
            correlation: correlation
        )
        currentConnectionState = state
        record(TestDiagnosticRecord(
            peerId: peerId,
            connectionId: activeConnectionId,
            category: "connection",
            eventName: TestDiagnosticEventName.connectionStateChanged,
            currentState: state,
            previousState: previous,
            details: sessionSnapshot ? ["sessionSnapshot": "true"] : [:]
        ))
        if state == "Connected" {
            record(TestDiagnosticRecord(
                peerId: peerId,
                connectionId: activeConnectionId,
                category: "security",
                eventName: TestDiagnosticEventName.connectionAuthenticated,
                currentState: "authenticated"
            ))
            record(TestDiagnosticRecord(
                peerId: peerId,
                connectionId: activeConnectionId,
                category: "protocol",
                eventName: TestDiagnosticEventName.protocolNegotiated,
                currentState: "secure-v2",
                outcome: .success
            ))
        }
    }

    func transfer(
        _ eventName: String,
        peerId: String,
        transferId: String?,
        state: String,
        size: Int64?,
        direction: TestDiagnosticDirection,
        outcome: TestDiagnosticOutcome? = nil,
        error: String? = nil,
        details: [String: String] = [:]
    ) {
        let correlation = transferId.flatMap {
            registerTransfer(peerId: peerId, transferId: $0)
        }
        activeTransferId = transferId
        currentTransferState = state
        let selectedEvidence = transferId.flatMap { transferEvidence[$0] }
        senderSha256 = selectedEvidence?.senderSha256
        receiverSha256 = selectedEvidence?.receiverSha256
        integrityMatch = selectedEvidence?.integrityMatch
        record(TestDiagnosticRecord(
            peerId: peerId,
            connectionId: correlation?.connectionId,
            transferId: transferId,
            category: "transfer",
            eventName: eventName,
            severity: error == nil ? .info : .error,
            currentState: state,
            direction: direction,
            payloadSizeBytes: size,
            errorCode: error == nil ? nil : "FILE_TRANSFER_FAILED",
            errorDescription: error,
            outcome: outcome,
            details: details
        ))
    }

    func transferProgress(peerId: String, transferId: String, bytes: Int64, total: Int64) {
        progress = total > 0 ? min(1, Double(bytes) / Double(total)) : 0
        let percent = Int(progress * 100)
        if percent == 0 || percent == 25 || percent == 50 || percent == 75 || percent == 100 {
            transfer(
                TestDiagnosticEventName.transferProgress,
                peerId: peerId,
                transferId: transferId,
                state: "\(percent)%",
                size: bytes,
                direction: .local,
                details: ["totalBytes": "\(total)", "progressPercent": "\(percent)"]
            )
        }
    }

    func fileHash(
        peerId: String,
        transferId: String,
        size: Int64,
        digest: String,
        receiver: Bool
    ) {
        let correlation = registerTransfer(peerId: peerId, transferId: transferId)
        var evidence = transferEvidence[transferId] ?? TransferEvidence()
        if receiver {
            evidence.receiverFileSizeBytes = size
            evidence.receiverSha256 = digest
        } else {
            evidence.senderFileSizeBytes = size
            evidence.senderSha256 = digest
        }
        transferEvidence[transferId] = evidence
        if activeTransferId == transferId {
            senderSha256 = evidence.senderSha256
            receiverSha256 = evidence.receiverSha256
            integrityMatch = evidence.integrityMatch
        }
        record(TestDiagnosticRecord(
            peerId: peerId,
            connectionId: correlation?.connectionId,
            transferId: transferId,
            category: "file",
            eventName: receiver ? TestDiagnosticEventName.receiverHash : TestDiagnosticEventName.senderHash,
            direction: receiver ? .received : .sent,
            payloadSizeBytes: size,
            details: ["sha256": digest]
        ))
        if let match = evidence.integrityMatch {
            record(TestDiagnosticRecord(
                peerId: peerId,
                connectionId: correlation?.connectionId,
                transferId: transferId,
                category: "file",
                eventName: TestDiagnosticEventName.integrityChecked,
                severity: match ? .info : .error,
                currentState: match ? "matched" : "mismatch",
                outcome: match ? .success : .failure,
                details: ["match": match ? "true" : "false"]
            ))
        }
    }

    private func derivedConnection(peerId: String) -> Correlation? {
        guard let localPeerId else { return nil }
        let peers = [Self.anonymized(localPeerId), Self.anonymized(peerId)].sorted()
        let raw = "\(activeSessionId)|\(peers[0])|\(peers[1])"
        let connectionId = "conn-" + String(Self.sha256(Data(raw.utf8)).prefix(20))
        return Correlation(peerId: peerId, connectionId: connectionId, transferId: nil)
    }

    private func registerTransfer(peerId: String, transferId: String) -> Correlation? {
        guard let connection = connectionsByPeer[peerId]?.correlation else {
            return nil
        }
        let correlation = Correlation(
            peerId: peerId,
            connectionId: connection.connectionId,
            transferId: transferId
        )
        let existing = transferCorrelations[transferId]
        let ambiguous = existing?.ambiguous == true || (
            existing?.correlation != nil &&
                existing?.correlation?.connectionId != correlation.connectionId
        )
        transferCorrelations[transferId] = TransferOwnership(
            correlation: ambiguous ? nil : correlation,
            ambiguous: ambiguous
        )
        if transferCorrelations.count > 1_024, let oldest = transferCorrelations.keys.first {
            transferCorrelations[oldest] = nil
        }
        return correlation
    }

    func filtered(
        testId: String,
        sessionId: String,
        transferId: String,
        severity: TestDiagnosticSeverity?,
        search: String
    ) -> [TestDiagnosticEvent] {
        events.filter { event in
            (testId.isEmpty || event.testId.localizedCaseInsensitiveContains(testId)) &&
            (sessionId.isEmpty || event.testSessionId.localizedCaseInsensitiveContains(sessionId)) &&
            (transferId.isEmpty || event.transferId?.localizedCaseInsensitiveContains(transferId) == true) &&
            (severity == nil || event.severity.rank >= severity!.rank) &&
            (search.isEmpty ||
                event.eventName.localizedCaseInsensitiveContains(search) ||
                event.errorCode?.localizedCaseInsensitiveContains(search) == true ||
                event.peerId?.localizedCaseInsensitiveContains(search) == true)
        }
    }

    func copyText(_ selected: [TestDiagnosticEvent]) -> String {
        selected.compactMap { event in
            guard let data = try? encoder.encode(event) else { return nil }
            return String(data: data, encoding: .utf8)
        }.joined(separator: "\n") + "\n"
    }

    func clearCurrentSession() -> Int {
        let before = events.count
        events.removeAll { $0.testSessionId == activeSessionId }
        encodedBytes = events.reduce(0) {
            $0 + ((try? encoder.encode($1).count) ?? 0) + 1
        }
        rewritePersistentLogsExcluding(sessionId: activeSessionId)
        return before - events.count
    }

    func exportEvidence() throws -> URL {
        let selected = events.filter { $0.testSessionId == activeSessionId }
        let manual = [
            "UI screenshots showing test ID, session ID, connection/transfer state, hashes, and result",
            "Screen recording for interruption, recovery, backgrounding, or path-rotation tests",
            "Peer evidence package with matching testSessionId/connectionId/transferId for two-peer tests",
            "Packet capture and external system logs where the validation-plan row requires them"
        ]
        let summary = makeSummary(selected, manual: manual)
        let jsonl = selected.compactMap { try? encoder.encode($0) }
            .reduce(into: Data()) { result, entry in
                result.append(entry)
                result.append(0x0a)
            }
        let readable = selected.map(Self.readable).joined(separator: "\n") + "\n"
        var files: [String: Data] = [
            "events.jsonl": jsonl,
            "events.txt": Data(readable.utf8),
            "summary.json": try encoder.encode(summary),
            "manual-evidence-required.txt": Data(
                manual.map { "- \($0)" }.joined(separator: "\n").appending("\n").utf8
            )
        ]
        for (name, data) in persistedEvidenceFiles(sessionId: activeSessionId) {
            guard files[name] == nil, name != "checksums.sha256" else {
                throw TestDiagnosticEvidenceError.reservedFilename(name)
            }
            files[name] = data
        }
        files["checksums.sha256"] = try Self.checksumManifest(for: files)
        guard Self.checksumManifestIsComplete(files) else {
            throw TestDiagnosticEvidenceError.invalidChecksumManifest
        }
        let timestamp = Self.filenameTimestamp(summary.startTimestamp ?? Self.timestamp())
        let filename = [
            Self.filenamePart(activeTestId),
            "ios",
            timestamp,
            Self.filenamePart(activeSessionId)
        ].joined(separator: "_") + ".zip"
        try FileManager.default.createDirectory(
            at: evidenceDirectory,
            withIntermediateDirectories: true
        )
        let destination = evidenceDirectory.appendingPathComponent(filename)
        let temporary = destination.appendingPathExtension("part")
        try SimpleEvidenceZip.write(files: files, to: temporary)
        if FileManager.default.fileExists(atPath: destination.path) {
            _ = try FileManager.default.replaceItemAt(destination, withItemAt: temporary)
        } else {
            try FileManager.default.moveItem(at: temporary, to: destination)
        }
        record(TestDiagnosticRecord(
            category: "evidence",
            eventName: TestDiagnosticEventName.evidenceExported,
            details: [
                "filename": filename,
                "packageSha256": Self.sha256((try? Data(contentsOf: destination)) ?? Data())
            ]
        ))
        return destination
    }

    func makeSummary(
        _ selected: [TestDiagnosticEvent],
        manual: [String]
    ) -> TestDiagnosticSummary {
        let transferIds = Self.distinct(selected.compactMap(\.transferId))
        let transferSummaries = transferIds.map { transferId in
            Self.transferSummary(transferId: transferId, events: selected)
        }
        let selectedTransfer = transferSummaries.count == 1 ? transferSummaries[0] : nil
        let terminal = selected.last {
            $0.eventName == TestDiagnosticEventName.testSessionCompleted && $0.outcome != nil
        }
        let first = selected.first
        return TestDiagnosticSummary(
            schemaVersion: 1,
            testId: first?.testId ?? activeTestId,
            testSessionId: first?.testSessionId ?? activeSessionId,
            role: first?.role ?? activeRole,
            platform: platform,
            operatingSystem: operatingSystem,
            applicationVersion: applicationVersion,
            buildNumber: buildNumber,
            gitCommitSha: gitCommitSha,
            safeDeviceId: safeDeviceId,
            startTimestamp: selected.first?.timestamp,
            endTimestamp: selected.last?.timestamp,
            protocolVersion: "secure-v2",
            connectionIds: Self.distinct(selected.compactMap(\.connectionId)),
            transferIds: transferIds,
            peerIds: Self.distinct(selected.compactMap(\.peerId)),
            transferSummaries: transferSummaries,
            selectedTransferId: selectedTransfer?.transferId,
            senderFileSizeBytes: selectedTransfer?.senderFileSizeBytes,
            receiverFileSizeBytes: selectedTransfer?.receiverFileSizeBytes,
            senderSha256: selectedTransfer?.senderSha256,
            receiverSha256: selectedTransfer?.receiverSha256,
            integrityMatch: selectedTransfer?.integrityMatch,
            finalState: terminal?.currentState,
            finalOutcome: terminal?.outcome,
            warningCount: selected.filter { $0.severity == .warning }.count,
            errorCount: selected.filter { $0.severity == .error }.count,
            eventCount: selected.count,
            droppedEventCount: droppedEvents,
            configuration: configuration,
            manualEvidenceStillRequired: manual
        )
    }

    private static func transferSummary(
        transferId: String,
        events: [TestDiagnosticEvent]
    ) -> TestDiagnosticTransferSummary {
        let selected = events.filter { $0.transferId == transferId }
        let sender = selected.last { $0.eventName == TestDiagnosticEventName.senderHash }
        let receiver = selected.last { $0.eventName == TestDiagnosticEventName.receiverHash }
        let integrity = selected.last { $0.eventName == TestDiagnosticEventName.integrityChecked }
        return TestDiagnosticTransferSummary(
            transferId: transferId,
            connectionIds: distinct(selected.compactMap(\.connectionId)),
            peerIds: distinct(selected.compactMap(\.peerId)),
            senderFileSizeBytes: sender?.payloadSizeBytes,
            receiverFileSizeBytes: receiver?.payloadSizeBytes,
            senderSha256: sender?.details["sha256"],
            receiverSha256: receiver?.details["sha256"],
            integrityMatch: integrity?.details["match"].flatMap(Bool.init)
        )
    }

    private func persist(_ data: Data) throws {
        try FileManager.default.createDirectory(
            at: logDirectory,
            withIntermediateDirectories: true
        )
        let active = logDirectory.appendingPathComponent("events.jsonl")
        let size = (try? active.resourceValues(forKeys: [.fileSizeKey]).fileSize) ?? 0
        if UInt64(size) + UInt64(data.count) > Self.maxPersistedFileBytes {
            try rotatePersistentLogs()
        }
        if !FileManager.default.fileExists(atPath: active.path) {
            FileManager.default.createFile(atPath: active.path, contents: nil)
        }
        let handle = try FileHandle(forWritingTo: active)
        defer { try? handle.close() }
        try handle.seekToEnd()
        try handle.write(contentsOf: data)
    }

    private func rotatePersistentLogs() throws {
        for index in stride(
            from: Self.maxPersistedFiles - 1,
            through: 1,
            by: -1
        ) {
            let destination = logDirectory.appendingPathComponent("events.\(index).jsonl")
            let source = index == 1
                ? logDirectory.appendingPathComponent("events.jsonl")
                : logDirectory.appendingPathComponent("events.\(index - 1).jsonl")
            try? FileManager.default.removeItem(at: destination)
            if FileManager.default.fileExists(atPath: source.path) {
                try FileManager.default.moveItem(at: source, to: destination)
            }
        }
    }

    private func rewritePersistentLogsExcluding(sessionId: String) {
        for name in ["events.jsonl", "events.1.jsonl", "events.2.jsonl", "events.3.jsonl"] {
            let url = logDirectory.appendingPathComponent(name)
            guard let contents = try? String(contentsOf: url) else { continue }
            let retained = contents.split(separator: "\n").filter {
                !$0.contains("\"testSessionId\":\"\(sessionId)\"")
            }.joined(separator: "\n")
            try? Data((retained.isEmpty ? "" : retained + "\n").utf8).write(
                to: url,
                options: .atomic
            )
        }
    }

    /// Returns restart-spanning JSONL with only exact decoded session matches.
    /// Malformed or older-schema lines are not copied into a shareable package.
    func persistedEvidenceFiles(sessionId: String) -> [String: Data] {
        let names = ["events.jsonl", "events.1.jsonl", "events.2.jsonl", "events.3.jsonl"]
        var result: [String: Data] = [:]
        for name in names {
            let source = logDirectory.appendingPathComponent(name)
            guard let contents = try? Data(contentsOf: source), !contents.isEmpty else { continue }
            let selected = contents.split(separator: 0x0a).compactMap { line -> Data? in
                let data = Data(line)
                guard let event = try? JSONDecoder().decode(TestDiagnosticEvent.self, from: data),
                      event.testSessionId == sessionId else { return nil }
                return data
            }
            guard !selected.isEmpty else { continue }
            var filtered = Data()
            for line in selected {
                filtered.append(line)
                filtered.append(0x0a)
            }
            result["process-\(name)"] = filtered
        }
        return result
    }

    private static func timestamp() -> String {
        let formatter = ISO8601DateFormatter()
        formatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        formatter.timeZone = TimeZone(secondsFromGMT: 0)
        return formatter.string(from: Date())
    }

    private static func filenameTimestamp(_ value: String) -> String {
        let parsed = ISO8601DateFormatter().date(from: value) ?? Date(timeIntervalSince1970: 0)
        let formatter = DateFormatter()
        formatter.locale = Locale(identifier: "en_US_POSIX")
        formatter.timeZone = TimeZone(secondsFromGMT: 0)
        formatter.dateFormat = "yyyy-MM-dd'T'HHmmss"
        return formatter.string(from: parsed)
    }

    private static func stableName(_ value: String) -> String {
        let lowered = value.lowercased()
        let mapped = lowered.map {
            $0.isLetter || $0.isNumber || $0 == "." || $0 == "_" || $0 == "-" ? $0 : "_"
        }
        return String(mapped).prefix(96).description
    }

    private static func safeIdentifier(_ value: String) -> String? {
        let safe = value.filter {
            $0.isLetter || $0.isNumber || $0 == "." || $0 == "_" || $0 == "-"
        }
        return safe.isEmpty ? nil : String(safe.prefix(96))
    }

    private static func normalizedTestId(_ value: String) -> String {
        let normalized = value.uppercased().filter {
            $0.isLetter || $0.isNumber || $0 == "-"
        }
        return normalized.isEmpty ? "UNASSIGNED" : String(normalized.prefix(48))
    }

    private static func normalizedSessionId(_ value: String) -> String {
        safeIdentifier(value).map { String($0.prefix(80)) } ?? "session-unassigned"
    }

    private static func normalizedRole(_ value: String) -> String {
        let normalized = value.lowercased().filter {
            $0.isLetter || $0.isNumber || $0 == "_" || $0 == "-"
        }
        return normalized.isEmpty ? "unspecified" : String(normalized.prefix(24))
    }

    private static func filenamePart(_ value: String) -> String {
        safeIdentifier(value) ?? "unknown"
    }

    private static func anonymized(_ value: String) -> String {
        "anon-" + String(sha256(Data(value.utf8)).prefix(16))
    }

    private static func redact(_ values: [String: String]) -> (
        values: [String: String],
        fields: [String]
    ) {
        let sensitive = [
            "password", "passphrase", "credential", "secret", "token",
            "privatekey", "signing", "authorization", "cookie", "ssid", "bssid",
            "payload", "content", "filename", "peername", "devicename", "displayname",
            "hostname", "ipaddress", "ipv4address", "ipv6address", "address", "name"
        ]
        var safe: [String: String] = [:]
        var fields: [String] = []
        for (key, value) in values {
            let normalizedKey = key.lowercased().filter { $0.isLetter || $0.isNumber }
            if sensitive.contains(where: {
                normalizedKey.contains($0)
            }) {
                safe[key] = "<redacted>"
                fields.append(key)
            } else {
                safe[key] = redactText(value)
            }
        }
        return (safe, fields.sorted())
    }

    static func redactText(_ value: String) -> String {
        var result = String(value.unicodeScalars.filter {
            $0.value >= 0x20 && $0.value != 0x7f
        }.prefix(1_024))
        let credential = try? NSRegularExpression(
            pattern: #"(?i)\b(bearer\s+[A-Za-z0-9._~+/=-]+|gh[pousr]_[A-Za-z0-9_]+|AKIA[A-Z0-9]{16})\b"#
        )
        result = credential?.stringByReplacingMatches(
            in: result,
            range: NSRange(result.startIndex..., in: result),
            withTemplate: "<redacted-credential>"
        ) ?? result
        let sensitiveAssignment = try? NSRegularExpression(
            pattern: #"(?i)(password|passphrase|credential|secret|token|ssid|bssid|payload|content|body|data|text|message|bytes|raw|file.?name|peer.?name|device.?name|display.?name|name|peer|device|host(?:name)?|ip(?:v[46])?.?address|address)\s*=\s*(?:"[^"]*"|'[^']*'|\S+)"#
        )
        result = sensitiveAssignment?.stringByReplacingMatches(
            in: result,
            range: NSRange(result.startIndex..., in: result),
            withTemplate: "$1=<redacted>"
        ) ?? result
        let mac = try? NSRegularExpression(
            pattern: #"(?i)(?<![0-9a-f])(?:[0-9a-f]{2}[:-]){5}[0-9a-f]{2}(?![0-9a-f])"#
        )
        let macMatches = Array(mac?.matches(
            in: result,
            range: NSRange(result.startIndex..., in: result)
        ) ?? []).reversed()
        for match in macMatches {
            guard let range = Range(match.range, in: result) else { continue }
            let raw = String(result[range])
            result.replaceSubrange(range, with: "<redacted-mac:\(anonymized(raw))>")
        }
        let ipv6 = try? NSRegularExpression(
            pattern: #"(?i)(?<![A-Za-z0-9])(?:\[[0-9a-f:.%_-]+\]|[0-9a-f:.]*:[0-9a-f:.%_-]+)(?![A-Za-z0-9])"#
        )
        let ipv6Matches = Array(ipv6?.matches(
            in: result,
            range: NSRange(result.startIndex..., in: result)
        ) ?? []).reversed()
        for match in ipv6Matches {
            guard let range = Range(match.range, in: result) else { continue }
            let raw = String(result[range])
            guard isIPv6Literal(raw) else { continue }
            result.replaceSubrange(range, with: "<redacted-ip:\(anonymized(raw))>")
        }
        let ipv4 = try? NSRegularExpression(
            pattern: #"(?<![A-Za-z0-9])(?:\d{1,3}\.){3}\d{1,3}(?![A-Za-z0-9])"#
        )
        let matches = Array(ipv4?.matches(
            in: result,
            range: NSRange(result.startIndex..., in: result)
        ) ?? []).reversed()
        for match in matches {
            guard let range = Range(match.range, in: result) else { continue }
            let raw = String(result[range])
            result.replaceSubrange(range, with: "<redacted-ip:\(anonymized(raw))>")
        }
        return result
    }

    private static func isIPv6Literal(_ candidate: String) -> Bool {
        let unwrapped = candidate.hasPrefix("[") && candidate.hasSuffix("]")
            ? String(candidate.dropFirst().dropLast())
            : candidate
        let address = String(unwrapped.split(separator: "%", maxSplits: 1)[0])
        guard address.contains(":") else { return false }
        var parsed = in6_addr()
        return address.withCString { inet_pton(AF_INET6, $0, &parsed) == 1 }
    }

    static func checksumManifest(for files: [String: Data]) throws -> Data {
        guard files["checksums.sha256"] == nil else {
            throw TestDiagnosticEvidenceError.reservedFilename("checksums.sha256")
        }
        let manifest = files.keys.sorted().map { name in
            "\(sha256(files[name]!))  \(name)"
        }.joined(separator: "\n") + "\n"
        return Data(manifest.utf8)
    }

    static func checksumManifestIsComplete(_ files: [String: Data]) -> Bool {
        guard let manifestData = files["checksums.sha256"],
              let manifestText = String(data: manifestData, encoding: .utf8) else { return false }
        let dataFiles = files.filter { $0.key != "checksums.sha256" }
        var listed: [String: String] = [:]
        for line in manifestText.split(separator: "\n", omittingEmptySubsequences: true) {
            let parts = line.split(separator: " ", maxSplits: 2, omittingEmptySubsequences: true)
            guard parts.count == 2 else { return false }
            let digest = String(parts[0])
            let name = String(parts[1])
            guard digest.range(of: #"^[0-9a-f]{64}$"#, options: .regularExpression) != nil,
                  name != "checksums.sha256",
                  listed.updateValue(digest, forKey: name) == nil else { return false }
        }
        guard Set(listed.keys) == Set(dataFiles.keys) else { return false }
        return listed.allSatisfy { name, digest in
            guard let data = dataFiles[name] else { return false }
            return sha256(data) == digest
        }
    }

    private static func readable(_ event: TestDiagnosticEvent) -> String {
        var parts = [
            event.timestamp,
            event.severity.rawValue.padding(
                toLength: 7,
                withPad: " ",
                startingAt: 0
            ),
            event.eventName,
            "test=\(event.testId)",
            "session=\(event.testSessionId)"
        ]
        if let connectionId = event.connectionId { parts.append("connection=\(connectionId)") }
        if let transferId = event.transferId { parts.append("transfer=\(transferId)") }
        if let packetType = event.packetType { parts.append("packet=\(packetType)") }
        if let state = event.currentState { parts.append("state=\(state)") }
        if let error = event.errorCode { parts.append("error=\(error)") }
        if let outcome = event.outcome { parts.append("outcome=\(outcome.rawValue)") }
        return parts.joined(separator: " ")
    }

    static func sha256(_ data: Data) -> String {
        SHA256.hash(data: data).map { String(format: "%02x", $0) }.joined()
    }

    private static func distinct(_ values: [String]) -> [String] {
        var seen = Set<String>()
        return values.filter { seen.insert($0).inserted }
    }
}

private struct DiagnosticValueRow: View {
    let label: String
    let value: String

    init(_ label: String, _ value: String) {
        self.label = label
        self.value = value
    }

    var body: some View {
        HStack(alignment: .firstTextBaseline) {
            Text(label).foregroundColor(.secondary)
            Spacer()
            Text(value)
                .font(.system(.caption, design: .monospaced))
                .multilineTextAlignment(.trailing)
                .textSelection(.enabled)
        }
    }
}

struct IOSTestDiagnosticsView: View {
    @ObservedObject var diagnostics: IOSTestDiagnosticStore
    let activeConnections: [TestDiagnosticConnectionSnapshot]
    @Environment(\.dismiss) private var dismiss
    @State private var testId = ""
    @State private var requestedSessionId = ""
    @State private var role = "both"
    @State private var sessionFilter = ""
    @State private var transferFilter = ""
    @State private var search = ""
    @State private var severity: TestDiagnosticSeverity?
    @State private var selected = Set<Int64>()
    @State private var confirmClear = false
    @State private var exportURL: URL?
    @State private var exportError: String?

    private var visible: [TestDiagnosticEvent] {
        diagnostics.filtered(
            testId: testId,
            sessionId: sessionFilter,
            transferId: transferFilter,
            severity: severity,
            search: search
        )
    }

    var body: some View {
        NavigationView {
            List {
                Section("Active evidence correlation") {
                    DiagnosticValueRow("Test ID", diagnostics.activeTestId)
                    DiagnosticValueRow("Session ID", diagnostics.activeSessionId)
                    DiagnosticValueRow("Role", diagnostics.activeRole)
                    DiagnosticValueRow("Connection ID", diagnostics.activeConnectionId ?? "—")
                    DiagnosticValueRow("Transfer ID", diagnostics.activeTransferId ?? "—")
                    DiagnosticValueRow("Protocol", "secure-v2")
                    DiagnosticValueRow("Connection", diagnostics.currentConnectionState)
                    DiagnosticValueRow("Transfer", diagnostics.currentTransferState)
                    DiagnosticValueRow("Progress", "\(Int(diagnostics.progress * 100))%")
                    DiagnosticValueRow("Sender SHA-256", diagnostics.senderSha256 ?? "—")
                    DiagnosticValueRow("Receiver SHA-256", diagnostics.receiverSha256 ?? "—")
                    DiagnosticValueRow(
                        "Integrity",
                        diagnostics.integrityMatch.map { $0 ? "MATCH" : "MISMATCH" } ?? "awaiting both peers"
                    )
                    DiagnosticValueRow("Final result", diagnostics.finalOutcome?.rawValue ?? "IN PROGRESS")
                }

                Section("Test session") {
                    TextField("Test ID (for example PS-T01)", text: $testId)
                        .textInputAutocapitalization(.characters)
                        .accessibilityIdentifier("diagnostics-test-id")
                    TextField("Shared session ID (optional)", text: $requestedSessionId)
                        .textInputAutocapitalization(.never)
                        .accessibilityIdentifier("diagnostics-session-id")
                    Picker("Role", selection: $role) {
                        Text("Both").tag("both")
                        Text("Sender").tag("sender")
                        Text("Receiver").tag("receiver")
                        Text("Client").tag("client")
                        Text("Server").tag("server")
                    }
                    Button("Begin Test Session") {
                        _ = diagnostics.startSession(
                            testId: testId,
                            requestedSessionId: requestedSessionId.isEmpty ? nil : requestedSessionId,
                            role: role,
                            activeConnections: activeConnections
                        )
                        sessionFilter = diagnostics.activeSessionId
                    }
                    .disabled(testId.trimmingCharacters(in: .whitespaces).isEmpty)
                    HStack {
                        Button("Complete Success") {
                            diagnostics.complete(.success, reason: "operator confirmed expected UI result")
                        }
                        Button("Complete Failure") {
                            diagnostics.complete(.failure, reason: "operator observed unexpected result")
                        }
                        .foregroundColor(.red)
                    }
                }

                Section("Filter and display") {
                    TextField("Session ID filter", text: $sessionFilter)
                    TextField("Transfer ID filter", text: $transferFilter)
                    TextField("Event, error code, or peer ID", text: $search)
                    Picker("Minimum severity", selection: $severity) {
                        Text("All").tag(nil as TestDiagnosticSeverity?)
                        ForEach(TestDiagnosticSeverity.allCases, id: \.self) {
                            Text($0.rawValue).tag($0 as TestDiagnosticSeverity?)
                        }
                    }
                    Button(diagnostics.displayPaused ? "Resume Live Display" : "Pause Live Display") {
                        diagnostics.displayPaused.toggle()
                    }
                }

                Section("Evidence") {
                    Button("Copy Selected Log Entries") {
                        let chosen = visible.filter { selected.contains($0.index) }
                        UIPasteboard.general.string = diagnostics.copyText(chosen)
                    }
                    .disabled(selected.isEmpty)
                    Button("Copy Complete Current Session") {
                        let current = diagnostics.events.filter {
                            $0.testSessionId == diagnostics.activeSessionId
                        }
                        UIPasteboard.general.string = diagnostics.copyText(current)
                    }
                    Button("Export Test Evidence") {
                        do {
                            exportURL = try diagnostics.exportEvidence()
                        } catch {
                            exportError = error.localizedDescription
                        }
                    }
                    .accessibilityIdentifier("export-test-evidence")
                    Button("Clear Current Session…", role: .destructive) {
                        confirmClear = true
                    }
                }

                if let exportError {
                    Section("Export error") { Text(exportError).foregroundColor(.red) }
                }

                Section("Live structured events (\(visible.count))") {
                    if diagnostics.displayPaused {
                        Text("Display paused; recording continues.")
                            .foregroundColor(.orange)
                    } else {
                        ForEach(visible) { event in
                            Button {
                                if selected.contains(event.index) {
                                    selected.remove(event.index)
                                } else {
                                    selected.insert(event.index)
                                }
                            } label: {
                                VStack(alignment: .leading, spacing: 3) {
                                    HStack {
                                        Image(systemName: selected.contains(event.index)
                                            ? "checkmark.circle.fill" : "circle")
                                        Text(event.eventName).font(.system(.caption, design: .monospaced))
                                        Spacer()
                                        Text(event.severity.rawValue).font(.caption2)
                                    }
                                    Text("\(event.timestamp)  \(event.testSessionId)")
                                        .font(.caption2)
                                        .foregroundColor(.secondary)
                                    if let transferId = event.transferId {
                                        Text("transfer=\(transferId)")
                                            .font(.caption2)
                                    }
                                    if let error = event.errorCode {
                                        Text("error=\(error)").font(.caption2).foregroundColor(.red)
                                    }
                                }
                            }
                            .buttonStyle(.plain)
                        }
                    }
                }
            }
            .navigationTitle("Test Diagnostics")
            .toolbar {
                ToolbarItem(placement: .navigationBarLeading) {
                    Button("Done") { dismiss() }
                }
            }
            .confirmationDialog(
                "Clear only \(diagnostics.activeSessionId)?",
                isPresented: $confirmClear,
                titleVisibility: .visible
            ) {
                Button("Clear Current Session", role: .destructive) {
                    _ = diagnostics.clearCurrentSession()
                    selected.removeAll()
                }
                Button("Cancel", role: .cancel) {}
            }
            .sheet(
                isPresented: Binding(
                    get: { exportURL != nil },
                    set: { if !$0 { exportURL = nil } }
                )
            ) {
                if let exportURL {
                    EvidenceActivityView(items: [exportURL])
                }
            }
            .onAppear {
                if testId.isEmpty && diagnostics.activeTestId != "UNASSIGNED" {
                    testId = diagnostics.activeTestId
                }
                if sessionFilter.isEmpty {
                    sessionFilter = diagnostics.activeSessionId
                }
            }
        }
    }
}

private struct EvidenceActivityView: UIViewControllerRepresentable {
    let items: [Any]

    func makeUIViewController(context: Context) -> UIActivityViewController {
        UIActivityViewController(activityItems: items, applicationActivities: nil)
    }

    func updateUIViewController(
        _ uiViewController: UIActivityViewController,
        context: Context
    ) {}
}

private enum SimpleEvidenceZip {
    private struct Entry {
        let name: Data
        let data: Data
        let checksum: UInt32
        let offset: UInt32
    }

    static func write(files: [String: Data], to url: URL) throws {
        var output = Data()
        var entries: [Entry] = []
        for name in files.keys.sorted() {
            guard let contents = files[name] else { continue }
            let nameData = Data(name.utf8)
            let offset = UInt32(output.count)
            let checksum = crc32(contents)
            output.appendUInt32(0x04034b50)
            output.appendUInt16(20)
            output.appendUInt16(0x0800)
            output.appendUInt16(0)
            output.appendUInt16(0)
            output.appendUInt16(0)
            output.appendUInt32(checksum)
            output.appendUInt32(UInt32(contents.count))
            output.appendUInt32(UInt32(contents.count))
            output.appendUInt16(UInt16(nameData.count))
            output.appendUInt16(0)
            output.append(nameData)
            output.append(contents)
            entries.append(Entry(name: nameData, data: contents, checksum: checksum, offset: offset))
        }
        let centralOffset = UInt32(output.count)
        for entry in entries {
            output.appendUInt32(0x02014b50)
            output.appendUInt16(20)
            output.appendUInt16(20)
            output.appendUInt16(0x0800)
            output.appendUInt16(0)
            output.appendUInt16(0)
            output.appendUInt16(0)
            output.appendUInt32(entry.checksum)
            output.appendUInt32(UInt32(entry.data.count))
            output.appendUInt32(UInt32(entry.data.count))
            output.appendUInt16(UInt16(entry.name.count))
            output.appendUInt16(0)
            output.appendUInt16(0)
            output.appendUInt16(0)
            output.appendUInt16(0)
            output.appendUInt32(0)
            output.appendUInt32(entry.offset)
            output.append(entry.name)
        }
        let centralSize = UInt32(output.count) - centralOffset
        output.appendUInt32(0x06054b50)
        output.appendUInt16(0)
        output.appendUInt16(0)
        output.appendUInt16(UInt16(entries.count))
        output.appendUInt16(UInt16(entries.count))
        output.appendUInt32(centralSize)
        output.appendUInt32(centralOffset)
        output.appendUInt16(0)
        try output.write(to: url, options: .atomic)
    }

    private static func crc32(_ data: Data) -> UInt32 {
        var value = UInt32.max
        for byte in data {
            value ^= UInt32(byte)
            for _ in 0..<8 {
                value = (value >> 1) ^ (0xedb88320 & (0 &- (value & 1)))
            }
        }
        return value ^ UInt32.max
    }
}

private extension Data {
    mutating func appendUInt16(_ value: UInt16) {
        var little = value.littleEndian
        Swift.withUnsafeBytes(of: &little) { append(contentsOf: $0) }
    }

    mutating func appendUInt32(_ value: UInt32) {
        var little = value.littleEndian
        Swift.withUnsafeBytes(of: &little) { append(contentsOf: $0) }
    }
}
