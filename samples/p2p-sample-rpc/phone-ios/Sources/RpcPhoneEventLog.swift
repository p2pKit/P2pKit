import Foundation

/// Memory-only, fixed-vocabulary diagnostics. Never pass invitations, peer identities or error descriptions here.
struct RpcPhoneEventLog {
    enum Role: String { case host = "Host", client = "Client" }

    struct Failure: Equatable {
        let code: String
        private static let kinds: Set<String> = [
            "NotConnected", "Closed", "PermissionMissing", "Overloaded", "DeadlineExceeded", "Unauthorized",
            "Authentication", "Protocol", "IncompatibleVersion", "UnknownProcedure", "InvalidPayload", "HandlerFailed",
            "ResultUnavailable", "UnknownOutcome", "HostRestarted", "RemoteCancelled", "TrustStorage",
            "LocalOrProtocolFailure", "Cancelled"
        ]
        private static let phases: Set<String> = [
            "Encoding", "Admission", "Negotiation", "Sending", "AwaitingResponse", "Decoding", "Trust"
        ]
        private static let evidence: Set<String> = [
            "NotSent", "RejectedBeforeExecution", "MayHaveExecuted", "HandlerFinished"
        ]

        init(callback: String) {
            guard callback.utf8.count <= 128 else { code = "LocalOrProtocolFailure"; return }
            let parts = callback.split(separator: "/", omittingEmptySubsequences: false).map(String.init)
            if parts.count == 3, Self.kinds.contains(parts[0]), Self.phases.contains(parts[1]),
               Self.evidence.contains(parts[2]) { code = parts.joined(separator: "/") }
            else if Self.kinds.contains(callback) { code = callback }
            else { code = "LocalOrProtocolFailure" }
        }

        init(kind: String, evidence: String?) {
            let knownKind = Self.kinds.contains(kind) ? kind : "LocalOrProtocolFailure"
            let knownEvidence = evidence.flatMap { Self.evidence.contains($0) ? $0 : nil }
            code = knownKind + (knownEvidence.map { "/" + $0 } ?? "")
        }
    }

    struct Snapshot {
        let role: Role
        let state: String
        let clients: Int64
        let pending: Int
        let completed: Int64
        let queued: Int64

        init(host: Bool, state: String, clients: Int64, pending: Int, completed: Int64, queued: Int64) {
            role = host ? .host : .client
            let allowed: Set<String> = host ? ["Idle", "Starting", "Running", "Closed", "Failed"] :
                ["Disconnected", "Connecting", "Negotiating", "Pairing", "Ready", "Reconnecting", "Closed", "Failed"]
            self.state = allowed.contains(state) ? state : "Unknown"
            self.clients = max(0, clients)
            self.pending = max(0, pending)
            self.completed = max(0, completed)
            self.queued = max(0, queued)
        }

        var summary: String {
            let counts = role == .host ? "; clients=\(clients); pending=\(pending)" : ""
            return "\(role.rawValue): \(state)\(counts); completed=\(completed); queued=\(queued)"
        }
    }

    enum Event {
        case startRequested(Role), roleStarted(Role), startRejected
        case mintRequested, invitationMinted, invitationExpired, invitationCopied, copyUnavailable
        case connectRequested(pair: Bool), connected, approveRequested, approved, revokeRequested, revoked
        case echoRequested(large: Bool), echoFinished(completed: Int32, expected: Int32, elapsed: Int64, failure: Failure?)
        case refreshed(Snapshot), failure(Failure), stopRequested, stopped(clean: Bool), cancellationRequested

        var failureCode: String? {
            switch self {
            case .failure(let failure): return failure.code
            case .echoFinished(_, _, _, let failure): return failure?.code
            case .startRejected: return "StartRejected"
            case .stopped(false): return "CleanupFailed"
            default: return nil
            }
        }

        var line: String {
            switch self {
            case .startRequested(let role): return "\(role.rawValue): start requested"
            case .roleStarted(let role): return "\(role.rawValue): started"
            case .startRejected: return "Start rejected; review setup"
            case .mintRequested: return "Host: invitation mint requested"
            case .invitationMinted: return "Host: invitation minted (content omitted)"
            case .invitationExpired: return "Host: invitation expired"
            case .invitationCopied: return "Host: invitation copied locally (content omitted)"
            case .copyUnavailable: return "Host: invitation copy unavailable"
            case .connectRequested(let pair): return pair ? "Client: pair requested" : "Client: reconnect requested"
            case .connected: return "Client: connected to pinned host"
            case .approveRequested: return "Host: exact-client approval requested (identity omitted)"
            case .approved: return "Host: exact-client approval completed (identity omitted)"
            case .revokeRequested: return "Exact-peer revocation requested (identity omitted)"
            case .revoked: return "Exact-peer revocation completed (identity omitted)"
            case .echoRequested(let large): return large ? "Client: large echo requested" : "Client: small echo requested"
            case .echoFinished(let completed, let expected, let elapsed, let failure):
                return "Client: echo replies=\(max(0, completed))/\(max(0, expected)); elapsedMs=\(max(0, elapsed)); " +
                    (failure?.code ?? "complete")
            case .refreshed(let snapshot): return snapshot.summary
            case .failure(let failure): return "Failure: \(failure.code)"
            case .stopRequested: return "Stop requested"
            case .stopped(let clean): return clean ? "Stop: owned cleanup completed" : "Stop: cleanup failed; owner retained"
            case .cancellationRequested: return "Cancellation requested; remote effects are not undone"
            }
        }
    }

    static let limit = 64
    static let pairInstructions = "Client: connecting to the selected host. On the host, tap Refresh and approve " +
        "only the displayed request whose fingerprint you verify. A pending request is not yet confirmed. " +
        "Keep both apps open until connected."
    private(set) var lines: [String] = []
    private(set) var lastFailure: String?

    mutating func append(_ event: Event) {
        if let failure = event.failureCode { lastFailure = failure }
        if lines.count == Self.limit { lines.removeFirst() }
        lines.append(event.line)
    }

    var text: String {
        "RPC iOS sample — last \(Self.limit) local events; not qualification evidence.\n" +
            "Last failure: \(lastFailure ?? "none recorded")\n" + lines.joined(separator: "\n")
    }

    /// Call only with the compiled framework stamp, never a user-entered identifier.
    func export(compiledSource: String) -> String {
        let valid = compiledSource.utf8.count == 40 && compiledSource.utf8.allSatisfy {
            (48...57).contains($0) || (97...102).contains($0)
        }
        return "Compiled source: \(valid ? compiledSource : "unavailable")\n" + text
    }
}
