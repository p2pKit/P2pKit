import SwiftUI
import P2pKitShared

struct ContentView: View {
    @State private var status: String = "Not started"
    @State private var debug: String = ""
    @State private var localPeerId: String = ""
    @State private var localDeviceName: String = "iPhone"
    @State private var peers: [PeerRow] = []
    @State private var sessions: [SessionRow] = []
    @State private var messages: [String] = []
    @State private var draft: String = "hi from iPhone"
    @State private var kit: P2pKit?
    @State private var pollTask: Task<Void, Never>?
    @State private var incomingSessionsTask: Task<Void, Never>?

    struct PeerRow: Identifiable, Equatable {
        let id: String   // peerId
        let name: String
        let peer: Peer
        static func == (lhs: PeerRow, rhs: PeerRow) -> Bool { lhs.id == rhs.id }
    }

    struct SessionRow: Identifiable, Equatable {
        let id: String   // session id
        let peerName: String
        let state: String
        let session: P2pSession
        static func == (lhs: SessionRow, rhs: SessionRow) -> Bool { lhs.id == rhs.id }
    }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 12) {
                Text("P2pKit v0.3 Sample").font(.title)
                Text("Status: \(status)")
                if !debug.isEmpty {
                    Text(debug).font(.caption2).foregroundColor(.orange)
                        .textSelection(.enabled)
                }
                if !localPeerId.isEmpty {
                    Text("localPeerId: \(localPeerId)")
                        .font(.system(.caption, design: .monospaced))
                        .textSelection(.enabled)
                }

                TextField("Device name", text: $localDeviceName)
                    .textFieldStyle(.roundedBorder)
                    .disabled(kit != nil)

                HStack {
                    if kit == nil {
                        Button("Start") { Task { await start() } }
                            .buttonStyle(.borderedProminent)
                    } else {
                        Button("Stop") { Task { await stop() } }
                            .buttonStyle(.borderedProminent)
                            .tint(.red)
                    }
                }

                Group {
                    Text("Peers (\(peers.count))").font(.headline)
                    ForEach(peers) { row in
                        HStack {
                            VStack(alignment: .leading) {
                                Text(row.name).bold()
                                Text(row.id.prefix(8))
                                    .font(.caption2).foregroundColor(.secondary)
                            }
                            Spacer()
                            Button("Connect") { Task { await connect(row) } }
                                .buttonStyle(.bordered)
                        }
                        .padding(.vertical, 4)
                    }
                }

                Group {
                    Text("Sessions (\(sessions.count))").font(.headline)
                    ForEach(sessions) { row in
                        HStack {
                            Text("\(row.peerName) — \(row.state)").font(.callout)
                        }
                        .padding(.vertical, 2)
                    }
                    if !sessions.isEmpty {
                        HStack {
                            TextField("message", text: $draft)
                                .textFieldStyle(.roundedBorder)
                            Button("Send all") { Task { await sendAll() } }
                                .buttonStyle(.bordered)
                        }
                    }
                }

                Group {
                    Text("Messages (\(messages.count))").font(.headline)
                    ForEach(Array(messages.enumerated()), id: \.offset) { _, m in
                        Text(m).font(.caption).textSelection(.enabled)
                    }
                }

                Spacer()
            }
            .padding()
        }
    }

    @MainActor
    private func start() async {
        status = "Starting…"
        debug = ""
        messages = []
        let built = P2pKitCompanion.shared.create { (builder: P2pKitBuilder) in
            builder.appId = "p2pkit-desktop-sample"
            builder.deviceName = self.localDeviceName
            builder.transports { (tx: TransportsBuilder) in
                tx.lan()
            }
        }
        self.kit = built
        self.localPeerId = "\(built.localPeerId)"

        do {
            try await built.startAdvertising()
            try await built.startDiscovery()
            status = "Running"
        } catch {
            status = "Start failed: \(error)"
            return
        }

        // Subscribe to incoming sessions via FlowCollector. Each newly-emitted
        // session also gets its own message collector attached.
        self.incomingSessionsTask = Task.detached { [weak built] in
            let collector = SessionCollector { session in
                await self.attachMessageCollector(to: session, label: "incoming")
            }
            _ = try? await built?.incomingSessions.collect(collector: collector)
        }

        // Poll peers + sessions StateFlows. Both are exposed as `id<KotlinStateFlow>`
        // from Swift; `.value` returns Any?. The collections come back as
        // NSSet — Set<Peer> / Set<AnyHashable> casts go through but NSSet is
        // the reliable middle layer.
        self.pollTask = Task { @MainActor in
            while self.kit != nil {
                refreshPeersAndSessions(from: built)
                try? await Task.sleep(nanoseconds: 1_000_000_000)
            }
        }
    }

    @MainActor
    private func refreshPeersAndSessions(from kit: P2pKit) {
        let peersValue: Any? = kit.peers.value
        let sessionsValue: Any? = kit.sessions.value

        let peersNs = peersValue as? NSSet
        let sessionsNs = sessionsValue as? NSSet

        // Diagnostic line — type names + raw counts so we can see whether
        // the SDK has populated the flows but our cast is wrong, vs. the
        // SDK genuinely seeing no peers.
        let peersType = String(describing: type(of: peersValue as Any))
        let sessionsType = String(describing: type(of: sessionsValue as Any))
        self.debug = "peers(\(peersType))=\(peersNs?.count ?? -1) sessions(\(sessionsType))=\(sessionsNs?.count ?? -1)"

        if let ns = peersNs {
            let rows: [PeerRow] = ns.allObjects.compactMap { obj in
                guard let p = obj as? Peer else { return nil }
                return PeerRow(id: "\(p.id)", name: p.name, peer: p)
            }.sorted { $0.name < $1.name }
            if rows != self.peers { self.peers = rows }
        }

        if let ns = sessionsNs {
            let rows: [SessionRow] = ns.allObjects.compactMap { obj in
                guard let s = obj as? P2pSession else { return nil }
                let st: Any = s.state.value
                return SessionRow(id: s.id, peerName: s.peer.name, state: "\(st)", session: s)
            }.sorted { $0.peerName < $1.peerName }
            if rows != self.sessions { self.sessions = rows }
        }
    }

    private func attachMessageCollector(to session: P2pSession, label: String) async {
        await MainActor.run {
            self.messages.append("[\(label)] session opened: \(session.peer.name)")
        }
        let collector = MessageCollector { msg in
            await MainActor.run {
                if let text = msg as? P2pMessage.Text {
                    self.messages.append("\(session.peer.name) → \(text.value)")
                } else if msg != nil {
                    self.messages.append("\(session.peer.name) → <binary or other>")
                }
            }
        }
        _ = try? await session.incoming.collect(collector: collector)
    }

    @MainActor
    private func connect(_ row: PeerRow) async {
        guard let k = kit else { return }
        self.messages.append("connect → \(row.name)")
        do {
            let session = try await k.connect(peer: row.peer)
            await attachMessageCollector(to: session, label: "outgoing")
        } catch {
            self.messages.append("connect failed: \(error)")
        }
    }

    @MainActor
    private func sendAll() async {
        let text = draft
        guard !text.isEmpty else { return }
        for row in sessions {
            do {
                try await row.session.send(message: P2pMessage.Text(value: text, metadata: [:]))
                self.messages.append("me → \(row.peerName): \(text)")
            } catch {
                self.messages.append("send failed (\(row.peerName)): \(error)")
            }
        }
    }

    @MainActor
    private func stop() async {
        guard let k = kit else { return }
        status = "Stopping…"
        pollTask?.cancel()
        incomingSessionsTask?.cancel()
        try? await k.stop()
        kit = nil
        peers = []
        sessions = []
        localPeerId = ""
        status = "Stopped"
    }
}

/// Swift adapter for `kotlinx.coroutines.flow.FlowCollector<P2pSession>`.
/// Kotlin/Native exposes it as the Objective-C protocol
/// `Kotlinx_coroutines_coreFlowCollector` with one suspending `emit` method.
final class SessionCollector: NSObject, Kotlinx_coroutines_coreFlowCollector {
    private let onSession: (P2pSession) async -> Void
    init(_ onSession: @escaping (P2pSession) async -> Void) {
        self.onSession = onSession
    }
    func emit(value: Any?, completionHandler: @escaping (Error?) -> Void) {
        if let session = value as? P2pSession {
            Task {
                await onSession(session)
                completionHandler(nil)
            }
        } else {
            completionHandler(nil)
        }
    }
}

/// Swift adapter for `kotlinx.coroutines.flow.FlowCollector<P2pMessage>`.
final class MessageCollector: NSObject, Kotlinx_coroutines_coreFlowCollector {
    private let onMessage: (Any?) async -> Void
    init(_ onMessage: @escaping (Any?) async -> Void) {
        self.onMessage = onMessage
    }
    func emit(value: Any?, completionHandler: @escaping (Error?) -> Void) {
        Task {
            await onMessage(value)
            completionHandler(nil)
        }
    }
}
