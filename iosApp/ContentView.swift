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
    @State private var manualHost: String = ""
    @State private var manualPort: String = ""
    @State private var logLines: [String] = []
    @State private var showLog: Bool = true

    @State private var kit: P2pKit?
    @State private var pollTask: Task<Void, Never>?
    @State private var incomingSessionsTask: Task<Void, Never>?
    @State private var debugLogTask: Task<Void, Never>?

    /// Tracks session ids whose `incoming` flow we've already subscribed
    /// to. Without this, tapping Connect on the same peer twice attaches
    /// two MessageCollectors to the same SharedFlow, and every received
    /// message appears in the UI twice.
    @State private var collectedSessionIds: Set<String> = []

    struct PeerRow: Identifiable, Equatable {
        let id: String
        let name: String
        let peer: Peer
        static func == (lhs: PeerRow, rhs: PeerRow) -> Bool { lhs.id == rhs.id && lhs.name == rhs.name }
    }

    struct SessionRow: Identifiable, Equatable {
        let id: String
        let peerName: String
        let state: String
        let session: P2pSession
        static func == (lhs: SessionRow, rhs: SessionRow) -> Bool {
            lhs.id == rhs.id && lhs.state == rhs.state && lhs.peerName == rhs.peerName
        }
    }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 12) {
                Text("P2pKit v0.3 Sample").font(.title)
                Text("Status: \(status)")
                if !debug.isEmpty {
                    Text(debug).font(.caption2).foregroundColor(.orange).textSelection(.enabled)
                }
                if !localPeerId.isEmpty {
                    Text("localPeerId: \(localPeerId)")
                        .font(.system(.caption, design: .monospaced))
                        .textSelection(.enabled)
                }

                TextField("Device name", text: $localDeviceName)
                    .textFieldStyle(.roundedBorder)
                    .disabled(kit != nil)
                    .autocorrectionDisabled()

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

                Divider()

                // Discovered peers (from NWBrowser).
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
                            .disabled(sessions.contains { $0.peerName == row.name })
                    }
                    .padding(.vertical, 4)
                }

                Divider()

                // Manual IP — bypasses NWBrowser entirely. Useful when
                // discovery fails (corporate Wi-Fi blocking multicast,
                // simulator network sandbox, etc.).
                Text("Manual connect (skip Bonjour)").font(.headline)
                HStack {
                    TextField("Host (e.g. 192.168.1.42)", text: $manualHost)
                        .textFieldStyle(.roundedBorder)
                        .keyboardType(.numbersAndPunctuation)
                        .autocorrectionDisabled()
                    TextField("Port", text: $manualPort)
                        .textFieldStyle(.roundedBorder)
                        .keyboardType(.numberPad)
                        .frame(width: 80)
                }
                Button("Dial manual peer") {
                    Task { await dialManual() }
                }
                .buttonStyle(.bordered)
                .disabled(kit == nil || manualHost.isEmpty || manualPort.isEmpty)

                Divider()

                Text("Sessions (\(sessions.count))").font(.headline)
                ForEach(sessions) { row in
                    HStack {
                        Text("\(row.peerName) — \(row.state)").font(.callout)
                        Spacer()
                        Button("Close") {
                            Task { try? await row.session.close() }
                        }
                        .buttonStyle(.bordered)
                        .controlSize(.small)
                    }
                    .padding(.vertical, 2)
                }
                if !sessions.isEmpty {
                    HStack {
                        TextField("message", text: $draft)
                            .textFieldStyle(.roundedBorder)
                            .autocorrectionDisabled()
                        Button("Send all") { Task { await sendAll() } }
                            .buttonStyle(.bordered)
                    }
                }

                Divider()

                Text("Messages (\(messages.count))").font(.headline)
                ForEach(Array(messages.enumerated()), id: \.offset) { _, m in
                    Text(m).font(.caption).textSelection(.enabled)
                }

                Divider()

                Toggle("Show NWBrowser log (\(logLines.count))", isOn: $showLog)
                    .font(.headline)
                if showLog {
                    ForEach(Array(logLines.enumerated()), id: \.offset) { _, l in
                        Text(l).font(.system(size: 10, design: .monospaced))
                            .textSelection(.enabled)
                    }
                }

                Spacer()
            }
            .padding()
        }
    }

    @MainActor
    private func start() async {
        status = "Starting..."
        debug = ""
        messages = []
        logLines = []
        collectedSessionIds = []

        let built = P2pKitCompanion.shared.create { (builder: P2pKitBuilder) in
            builder.appId = "p2pkit-desktop-sample"
            builder.deviceName = self.localDeviceName
            builder.transports { (tx: TransportsBuilder) in
                tx.lan()
            }
            // Register the iOS manual-IP provisioning module so we can
            // bypass discovery via kit.networkProvisioning.createManualPeer
            // when NWBrowser doesn't pick up the peer.
            builder.networkProvisioning { (np: NetworkProvisioningConfigBuilder) in
                np.iosManualIp()
            }
        }
        self.kit = built
        self.localPeerId = "\(built.localPeerId)"

        // Subscribe to IosLanDebug BEFORE startAdvertising/Discovery so we
        // see every browser-state and result event from t=0.
        self.debugLogTask = Task.detached {
            let collector = StringCollector { line in
                await MainActor.run {
                    self.logLines.append(line)
                    // Cap to last 200 to keep the UI responsive.
                    if self.logLines.count > 200 {
                        self.logLines.removeFirst(self.logLines.count - 200)
                    }
                }
            }
            _ = try? await IosLanDebug.shared.events.collect(collector: collector)
        }

        do {
            try await built.startAdvertising()
            try await built.startDiscovery()
            status = "Running"
        } catch {
            status = "Start failed: \(error)"
            return
        }

        // Subscribe to incoming sessions.
        self.incomingSessionsTask = Task.detached { [weak built] in
            let collector = SessionCollector { session in
                await self.attachMessageCollector(to: session, label: "incoming")
            }
            _ = try? await built?.incomingSessions.collect(collector: collector)
        }

        // Poll peers + sessions StateFlows via the snapshot helpers.
        self.pollTask = Task { @MainActor in
            while self.kit != nil {
                refreshPeersAndSessions(from: built)
                try? await Task.sleep(nanoseconds: 1_000_000_000)
            }
        }
    }

    @MainActor
    private func refreshPeersAndSessions(from kit: P2pKit) {
        let peerArray: [Peer] = IosSwiftHelpersKt.peersSnapshot(kit)
        let sessionArray: [P2pSession] = IosSwiftHelpersKt.sessionsSnapshot(kit)

        self.debug = "peers=\(peerArray.count) sessions=\(sessionArray.count)"

        let peerRows = peerArray.map { p in
            PeerRow(id: "\(p.id)", name: p.name, peer: p)
        }.sorted { $0.name < $1.name }
        if peerRows != self.peers { self.peers = peerRows }

        let sessionRows = sessionArray.map { s in
            SessionRow(id: s.id, peerName: s.peer.name, state: "\(s.state.value)", session: s)
        }.sorted { $0.peerName < $1.peerName }
        if sessionRows != self.sessions { self.sessions = sessionRows }

        // For every session in the kit that we haven't subscribed to yet,
        // attach a message collector. This matters for sessions that arrive
        // through some path other than incomingSessions (e.g., our own
        // outgoing connect via the manual-IP dial).
        for row in sessionRows where !collectedSessionIds.contains(row.id) {
            Task { await attachMessageCollector(to: row.session, label: "tracked") }
        }
    }

    private func attachMessageCollector(to session: P2pSession, label: String) async {
        let sid = session.id
        let alreadySubscribed = await MainActor.run { () -> Bool in
            if collectedSessionIds.contains(sid) { return true }
            collectedSessionIds.insert(sid)
            return false
        }
        if alreadySubscribed { return }
        await MainActor.run {
            self.messages.append("[\(label)] session opened: \(session.peer.name)")
        }
        let collector = MessageCollector { msg in
            await MainActor.run {
                if let text = msg as? P2pMessage.Text {
                    self.messages.append("\(session.peer.name) -> \(text.value)")
                } else if msg != nil {
                    self.messages.append("\(session.peer.name) -> <binary or other>")
                }
            }
        }
        _ = try? await session.incoming.collect(collector: collector)
    }

    @MainActor
    private func connect(_ row: PeerRow) async {
        guard let k = kit else { return }
        // The kit dedupes by peer id at SessionManager level; calling
        // connect twice for the same peer should return the same P2pSession.
        // We additionally guard the message-collector attachment in
        // attachMessageCollector via collectedSessionIds.
        self.messages.append("connect -> \(row.name)")
        do {
            let session = try await k.connect(peer: row.peer)
            await attachMessageCollector(to: session, label: "outgoing")
        } catch {
            self.messages.append("connect failed: \(error)")
        }
    }

    @MainActor
    private func dialManual() async {
        guard let k = kit else { return }
        guard let portInt = Int32(manualPort.trimmingCharacters(in: .whitespaces)),
              portInt > 0 else {
            self.messages.append("manual: invalid port '\(manualPort)'")
            return
        }
        let host = manualHost.trimmingCharacters(in: .whitespaces)
        guard !host.isEmpty else {
            self.messages.append("manual: empty host")
            return
        }
        self.messages.append("manual: createManualPeer host=\(host) port=\(portInt)")
        do {
            // kit.networkProvisioning is wired to IosManualNetworkProvisioningManager
            // (registered via builder.networkProvisioning { iosManualIp() }).
            // createManualPeer registers a synthetic peer in PeerRegistry
            // with a TransportHint(host, port); IosLanDataTransport's
            // connect() then uses the manual-IP fallback branch to dial.
            let peer = try await k.networkProvisioning.createManualPeer(host: host, port: portInt)
            self.messages.append("manual: created \(peer.name) (\(peer.id))")
            let session = try await k.connect(peer: peer)
            await attachMessageCollector(to: session, label: "manual")
        } catch {
            self.messages.append("manual: failed - \(error)")
        }
    }

    @MainActor
    private func sendAll() async {
        let text = draft
        guard !text.isEmpty else { return }
        for row in sessions {
            do {
                try await row.session.send(message: P2pMessage.Text(value: text, metadata: [:]))
                self.messages.append("me -> \(row.peerName): \(text)")
            } catch {
                self.messages.append("send failed (\(row.peerName)): \(error)")
            }
        }
    }

    @MainActor
    private func stop() async {
        guard let k = kit else { return }
        status = "Stopping..."
        pollTask?.cancel()
        incomingSessionsTask?.cancel()
        debugLogTask?.cancel()
        try? await k.stop()
        kit = nil
        peers = []
        sessions = []
        collectedSessionIds = []
        localPeerId = ""
        status = "Stopped"
    }
}

// MARK: - FlowCollector adapters

/// Swift adapter for `kotlinx.coroutines.flow.FlowCollector<P2pSession>`.
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

/// Swift adapter for `kotlinx.coroutines.flow.FlowCollector<String>` —
/// used for the IosLanDebug.events log line stream.
final class StringCollector: NSObject, Kotlinx_coroutines_coreFlowCollector {
    private let onString: (String) async -> Void
    init(_ onString: @escaping (String) async -> Void) {
        self.onString = onString
    }
    func emit(value: Any?, completionHandler: @escaping (Error?) -> Void) {
        if let s = value as? String {
            Task {
                await onString(s)
                completionHandler(nil)
            }
        } else {
            completionHandler(nil)
        }
    }
}
