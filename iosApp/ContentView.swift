import SwiftUI
import P2pKitShared

struct ContentView: View {
    // MARK: - Public state shown in the UI

    @State private var status: String = "Not started"
    @State private var debug: String = ""
    @State private var localPeerId: String = ""
    @State private var localTcpPort: Int = 0
    @State private var localDeviceName: String = "iPhone"
    @State private var peers: [PeerRow] = []
    @State private var sessions: [SessionRow] = []
    @State private var messages: [MessageRow] = []
    @State private var draft: String = "hi from iPhone"
    @State private var manualHost: String = ""
    @State private var manualPort: String = ""
    @State private var logLines: [String] = []
    @State private var showLog: Bool = true

    /// Top-of-screen banner for user-actionable errors. Tap to dismiss.
    @State private var errorBanner: String? = nil

    // MARK: - Kit + background tasks

    @State private var kit: P2pKit?
    @State private var pollTask: Task<Void, Never>?
    @State private var incomingSessionsTask: Task<Void, Never>?
    @State private var debugLogTask: Task<Void, Never>?
    @State private var permissionCheckTask: Task<Void, Never>?

    // MARK: - In-flight guards (prevent rapid double-taps from spawning
    // parallel work).

    @State private var isStarting: Bool = false
    @State private var isStopping: Bool = false
    @State private var isManualDialing: Bool = false
    @State private var pendingConnectPeerIds: Set<String> = []

    /// Session ids whose `incoming` flow we've already subscribed to,
    /// so duplicate Connect taps don't attach a second MessageCollector
    /// and echo every received message.
    @State private var collectedSessionIds: Set<String> = []

    /// True once NWBrowser has transitioned to `.ready` at least once.
    /// Used to detect iOS Local Network permission denial — if the
    /// browser is stuck in `.waiting` for ~6 s we surface a hint.
    @State private var browserEverReady: Bool = false

    // MARK: - Row models

    struct PeerRow: Identifiable, Equatable {
        let id: String
        let name: String
        let peer: Peer
        static func == (lhs: PeerRow, rhs: PeerRow) -> Bool {
            lhs.id == rhs.id && lhs.name == rhs.name
        }
    }

    struct SessionRow: Identifiable, Equatable {
        let id: String          // session.id — unique per session epoch
        let peerId: String      // session.peer.id.value — used to match to PeerRow
        let peerName: String    // session.peer.name — display only
        let state: String       // ConnectionState textual value
        let session: P2pSession
        var isConnected: Bool { state == "Connected" }
        /// Any state where the session is still potentially recoverable —
        /// the kit considers the peer "owned" by this session and the
        /// Connect button should NOT offer a second attempt. Includes
        /// `Idle`, `Connecting`, `Handshaking`, `Connected`, `Reconnecting`.
        /// Excludes `Closing`, `Closed`, `Failed` — terminal states, so a
        /// fresh Connect should be allowed.
        var isLive: Bool {
            switch state {
            case "Idle", "Connecting", "Handshaking", "Connected", "Reconnecting":
                return true
            default:
                return false
            }
        }
        var isTerminal: Bool {
            switch state {
            case "Closing", "Closed", "Failed":
                return true
            default:
                return false
            }
        }
        static func == (lhs: SessionRow, rhs: SessionRow) -> Bool {
            lhs.id == rhs.id && lhs.state == rhs.state &&
                lhs.peerId == rhs.peerId && lhs.peerName == rhs.peerName
        }
    }

    struct MessageRow: Identifiable, Equatable {
        let id = UUID()
        let text: String
        let kind: Kind
        enum Kind { case info, sent, received, error }

        var color: Color {
            switch kind {
            case .info: return .secondary
            case .sent: return .blue
            case .received: return .primary
            case .error: return .red
            }
        }
    }

    private var trimmedDeviceName: String {
        localDeviceName.trimmingCharacters(in: .whitespacesAndNewlines)
    }

    // MARK: - View

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 12) {
                Text("P2pKit v0.3 Sample").font(.title)
                Text("Status: \(status)")

                if let err = errorBanner {
                    Text(err)
                        .font(.callout)
                        .foregroundColor(.white)
                        .padding(8)
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .background(Color.red.opacity(0.85))
                        .cornerRadius(6)
                        .textSelection(.enabled)
                        .onTapGesture { errorBanner = nil }
                }

                if !debug.isEmpty {
                    Text(debug).font(.caption2).foregroundColor(.orange).textSelection(.enabled)
                }
                if !localPeerId.isEmpty {
                    Text("localPeerId: \(localPeerId)")
                        .font(.system(.caption, design: .monospaced))
                        .textSelection(.enabled)
                }
                if localTcpPort > 0 {
                    Text("localTcpPort: \(localTcpPort)")
                        .font(.system(.caption, design: .monospaced))
                        .textSelection(.enabled)
                }

                TextField("Device name", text: $localDeviceName)
                    .textFieldStyle(.roundedBorder)
                    .disabled(kit != nil || isStarting)
                    .autocorrectionDisabled()

                HStack {
                    if kit == nil {
                        Button(isStarting ? "Starting…" : "Start") {
                            Task { await start() }
                        }
                        .buttonStyle(.borderedProminent)
                        .disabled(isStarting || trimmedDeviceName.isEmpty)
                    } else {
                        Button(isStopping ? "Stopping…" : "Stop") {
                            Task { await stop() }
                        }
                        .buttonStyle(.borderedProminent)
                        .tint(.red)
                        .disabled(isStopping)
                    }
                }

                Divider()

                // MARK: Discovered peers

                Text("Peers (\(peers.count))").font(.headline)
                if peers.isEmpty && kit != nil {
                    Text("No peers yet. Make sure the other device is on the same Wi-Fi network and Local Network permission is granted.")
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
                ForEach(peers) { row in
                    HStack {
                        VStack(alignment: .leading) {
                            Text(row.name).bold()
                            Text(row.id.prefix(8))
                                .font(.caption2).foregroundColor(.secondary)
                        }
                        Spacer()
                        // Match by peer.id, NOT peer.name. Two devices on the
                        // same Wi-Fi can share a name; peer.id is the
                        // SDK-generated UUID that's guaranteed unique.
                        let pending = pendingConnectPeerIds.contains(row.id)
                        let sessionForPeer = sessions.first { $0.peerId == row.id && $0.isLive }
                        let alreadyConnected = sessionForPeer?.isConnected ?? false
                        let inFlight = sessionForPeer != nil && !alreadyConnected
                        Button(connectButtonLabel(
                            pending: pending,
                            sessionForPeer: sessionForPeer
                        )) {
                            Task { await connect(row) }
                        }
                        .buttonStyle(.bordered)
                        .disabled(alreadyConnected || inFlight || pending || kit == nil || isStopping)
                    }
                    .padding(.vertical, 4)
                }

                Divider()

                // MARK: Manual IP fallback

                Text("Manual connect (skip Bonjour)").font(.headline)
                HStack {
                    TextField("Host (e.g. 192.168.1.42)", text: $manualHost)
                        .textFieldStyle(.roundedBorder)
                        .keyboardType(.numbersAndPunctuation)
                        .autocorrectionDisabled()
                        .disabled(isManualDialing)
                    TextField("Port", text: $manualPort)
                        .textFieldStyle(.roundedBorder)
                        .keyboardType(.numberPad)
                        .frame(width: 80)
                        .disabled(isManualDialing)
                }
                Button(isManualDialing ? "Dialing…" : "Dial manual peer") {
                    Task { await dialManual() }
                }
                .buttonStyle(.bordered)
                .disabled(
                    kit == nil ||
                    isManualDialing ||
                    isStopping ||
                    manualHost.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty ||
                    manualPort.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
                )

                Divider()

                // MARK: Sessions

                let connectedCount = sessions.filter { $0.isConnected }.count
                Text("Sessions (\(sessions.count), \(connectedCount) connected)").font(.headline)
                ForEach(sessions) { row in
                    VStack(alignment: .leading, spacing: 2) {
                        HStack {
                            Circle()
                                .fill(sessionDotColor(for: row))
                                .frame(width: 8, height: 8)
                            Text("\(row.peerName) — \(row.state)").font(.callout)
                            Spacer()
                            Button("Close") {
                                Task { await closeSession(row) }
                            }
                            .buttonStyle(.bordered)
                            .controlSize(.small)
                            .disabled(row.isTerminal || isStopping)
                        }
                        // Surface session-id + peer-id so we can verify the
                        // session matches the peer row above. Mismatched ids
                        // here would mean the SDK created a session against a
                        // different peer than the one in the discovery list.
                        Text("session=\(row.id.prefix(12))  peer=\(row.peerId.prefix(8))")
                            .font(.system(size: 9, design: .monospaced))
                            .foregroundColor(.secondary)
                    }
                    .padding(.vertical, 2)
                }
                if !sessions.isEmpty {
                    HStack {
                        TextField("message", text: $draft)
                            .textFieldStyle(.roundedBorder)
                            .autocorrectionDisabled()
                        Button("Send all (\(connectedCount))") { Task { await sendAll() } }
                            .buttonStyle(.bordered)
                            .disabled(
                                draft.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty ||
                                connectedCount == 0 ||
                                isStopping
                            )
                    }
                }

                Divider()

                // MARK: Messages

                Text("Messages (\(messages.count))").font(.headline)
                ForEach(messages) { m in
                    Text(m.text)
                        .font(.caption)
                        .foregroundColor(m.color)
                        .textSelection(.enabled)
                }

                Divider()

                // MARK: NWBrowser log

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

    /// Label for the per-peer Connect button. Reflects the *actual* session
    /// state on this peer, so an auto-mesh peer mid-handshake shows
    /// "Handshaking…" rather than the previously misleading "Connect".
    private func connectButtonLabel(
        pending: Bool,
        sessionForPeer: SessionRow?
    ) -> String {
        if let s = sessionForPeer {
            if s.isConnected { return "Connected" }
            return "\(s.state)…"      // Connecting / Handshaking / Reconnecting / Idle
        }
        if pending { return "Connecting…" }
        return "Connect"
    }

    private func sessionDotColor(for row: SessionRow) -> Color {
        if row.isConnected { return .green }
        if row.isLive { return .orange }    // Connecting / Handshaking / Reconnecting / Idle
        return .red                          // Closing / Closed / Failed
    }

    // MARK: - Actions

    @MainActor
    private func start() async {
        // Re-entry / preconditions.
        guard !isStarting else { return }
        guard kit == nil else { return }
        let name = trimmedDeviceName
        guard !name.isEmpty else {
            errorBanner = "Device name cannot be empty."
            return
        }

        isStarting = true
        defer { isStarting = false }
        errorBanner = nil
        status = "Starting..."
        debug = ""
        messages = []
        logLines = []
        collectedSessionIds = []
        pendingConnectPeerIds = []
        browserEverReady = false

        // Subscribe to IosLanDebug BEFORE startAdvertising/Discovery so
        // we capture every browser-state and result-change from t=0.
        self.debugLogTask = Task.detached {
            let collector = StringCollector { line in
                await MainActor.run {
                    self.logLines.append(line)
                    if line.contains("state -> ready") {
                        self.browserEverReady = true
                    }
                    if self.logLines.count > 200 {
                        self.logLines.removeFirst(self.logLines.count - 200)
                    }
                }
            }
            _ = try? await IosLanDebug.shared.events.collect(collector: collector)
        }

        // Build the kit. P2pKitCompanion.create is not marked @Throws on
        // the Kotlin side, so a synchronous failure during transport init
        // (e.g., listener binds with port=0) will crash the process —
        // that's an SDK-side gap tracked separately and not fixable from
        // sample code alone.
        let built = P2pKitCompanion.shared.create { (builder: P2pKitBuilder) in
            builder.appId = "p2pkit-desktop-sample"
            builder.deviceName = name
            builder.transports { (tx: TransportsBuilder) in
                tx.lan()
            }
            builder.networkProvisioning { (np: NetworkProvisioningConfigBuilder) in
                np.iosManualIp()
            }
        }
        self.kit = built
        self.localPeerId = "\(built.localPeerId)"

        do {
            try await built.startAdvertising()
            try await built.startDiscovery()
            status = "Running"
        } catch {
            status = "Start failed: \(error.localizedDescription)"
            errorBanner = "Failed to start: \(error.localizedDescription)"
            try? await built.stop()
            self.kit = nil
            debugLogTask?.cancel()
            return
        }

        // Read back the local TCP port for the manual-connect helper UI.
        do {
            if let info = try await built.networkProvisioning.getManualConnectionInfo() {
                self.localTcpPort = Int(info.port)
            }
        } catch {
            // Non-fatal — we just won't display the port.
        }

        self.incomingSessionsTask = Task.detached { [weak built] in
            let collector = SessionCollector { session in
                await self.attachMessageCollector(to: session, label: "incoming")
            }
            _ = try? await built?.incomingSessions.collect(collector: collector)
        }

        self.pollTask = Task { @MainActor in
            while self.kit != nil {
                refreshPeersAndSessions(from: built)
                try? await Task.sleep(nanoseconds: 1_000_000_000)
            }
        }

        // Permission-denial probe: if NWBrowser never reaches `.ready`
        // within 6 s of starting, iOS is almost certainly refusing Local
        // Network permission (or the user dismissed the dialog).
        self.permissionCheckTask = Task { @MainActor in
            try? await Task.sleep(nanoseconds: 6_000_000_000)
            if self.kit != nil && !self.browserEverReady {
                self.errorBanner = "NWBrowser is not ready after 6 s. " +
                    "iOS may have denied Local Network access — open " +
                    "Settings → Privacy & Security → Local Network and " +
                    "enable this app, then tap Stop / Start."
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
            SessionRow(
                id: s.id,
                peerId: "\(s.peer.id)",
                peerName: s.peer.name,
                state: "\(s.state.value)",
                session: s
            )
        }.sorted { $0.peerName < $1.peerName }

        // Surface state transitions in the message log so we can see when
        // an auto-mesh session enters Handshaking → Connected, or flips to
        // Reconnecting after a network blip. Diff against the previous
        // snapshot keyed by session.id.
        // `merging:` rather than `uniqueKeysWithValues:` — the latter
        // crashes on duplicate keys, and even though `session.id` is
        // supposed to be unique we don't want a corner-case crash here.
        let previousById: [String: SessionRow] = Dictionary(
            self.sessions.map { ($0.id, $0) },
            uniquingKeysWith: { first, _ in first }
        )
        for row in sessionRows {
            if let prev = previousById[row.id], prev.state != row.state {
                appendMessage(
                    "[session] \(row.peerName) (\(row.peerId.prefix(8))) → \(row.state)",
                    kind: .info
                )
            } else if previousById[row.id] == nil {
                appendMessage(
                    "[session] new \(row.peerName) (\(row.peerId.prefix(8))) state=\(row.state)",
                    kind: .info
                )
            }
        }

        if sessionRows != self.sessions { self.sessions = sessionRows }

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
            self.appendMessage("[\(label)] session opened: \(session.peer.name)", kind: .info)
        }
        let collector = MessageCollector { msg in
            await MainActor.run {
                if let text = msg as? P2pMessage.Text {
                    self.appendMessage("\(session.peer.name) -> \(text.value)", kind: .received)
                } else if msg != nil {
                    self.appendMessage("\(session.peer.name) -> <binary or other>", kind: .received)
                }
            }
        }
        _ = try? await session.incoming.collect(collector: collector)
    }

    @MainActor
    private func connect(_ row: PeerRow) async {
        guard let k = kit else {
            errorBanner = "Kit not started."
            return
        }
        guard !isStopping else { return }
        let pid = row.id
        guard !pendingConnectPeerIds.contains(pid) else {
            appendMessage("connect already in progress for \(row.name)", kind: .info)
            return
        }
        // Match by peer.id — peer.name is for display only and isn't
        // guaranteed unique across devices on the same Wi-Fi.
        if let existing = sessions.first(where: { $0.peerId == pid && $0.isLive }) {
            appendMessage(
                "already \(existing.state.lowercased()) with \(row.name); skipping duplicate connect",
                kind: .info
            )
            return
        }
        pendingConnectPeerIds.insert(pid)
        defer { pendingConnectPeerIds.remove(pid) }

        appendMessage("connect -> \(row.name)", kind: .info)
        do {
            let session = try await k.connect(peer: row.peer)
            await attachMessageCollector(to: session, label: "outgoing")
        } catch {
            appendMessage("connect failed (\(row.name)): \(error.localizedDescription)", kind: .error)
            errorBanner = "Connect to \(row.name) failed: \(error.localizedDescription)"
        }
    }

    @MainActor
    private func dialManual() async {
        guard let k = kit else {
            errorBanner = "Kit not started."
            return
        }
        guard !isStopping else { return }
        guard !isManualDialing else { return }

        let host = manualHost.trimmingCharacters(in: .whitespacesAndNewlines)
        let portStr = manualPort.trimmingCharacters(in: .whitespacesAndNewlines)

        guard !host.isEmpty else {
            errorBanner = "Manual host cannot be empty."
            return
        }
        guard let portInt = Int32(portStr) else {
            errorBanner = "Port must be a positive integer (got '\(portStr)')."
            return
        }
        guard (1...65535).contains(portInt) else {
            errorBanner = "Port must be between 1 and 65535 (got \(portInt))."
            return
        }
        // Light host-form check — reject obvious garbage so the user sees
        // a useful message instead of waiting on NWConnection to fail.
        let allowed = CharacterSet(charactersIn:
            "0123456789.:-_abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
        )
        guard host.unicodeScalars.allSatisfy({ allowed.contains($0) }) else {
            errorBanner = "Host contains invalid characters."
            return
        }

        isManualDialing = true
        defer { isManualDialing = false }
        errorBanner = nil
        appendMessage("manual: createManualPeer host=\(host) port=\(portInt)", kind: .info)
        do {
            let peer = try await k.networkProvisioning.createManualPeer(host: host, port: portInt)
            appendMessage("manual: created \(peer.name) (\(peer.id))", kind: .info)
            let session = try await k.connect(peer: peer)
            await attachMessageCollector(to: session, label: "manual")
        } catch {
            appendMessage("manual: failed - \(error.localizedDescription)", kind: .error)
            errorBanner = "Manual connect failed: \(error.localizedDescription)"
        }
    }

    @MainActor
    private func sendAll() async {
        let text = draft.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !text.isEmpty else {
            errorBanner = "Cannot send an empty message."
            return
        }
        // Re-read the sessions snapshot now — the UI's [sessions] list is
        // updated once per second by [refreshPeersAndSessions], so it could
        // be up to a second stale when the user taps Send. The live read
        // catches sessions that just transitioned to Connected or just left.
        let liveSessions: [SessionRow]
        if let k = kit {
            let snapshot: [P2pSession] = IosSwiftHelpersKt.sessionsSnapshot(k)
            liveSessions = snapshot.compactMap { s in
                let st = "\(s.state.value)"
                guard st == "Connected" else { return nil }
                return SessionRow(
                    id: s.id,
                    peerId: "\(s.peer.id)",
                    peerName: s.peer.name,
                    state: st,
                    session: s
                )
            }
        } else {
            errorBanner = "Kit not started."
            return
        }
        guard !liveSessions.isEmpty else {
            errorBanner = "No Connected sessions right now. Sessions exist " +
                "(\(sessions.count)) but none are in the Connected state."
            return
        }

        var failures: [String] = []
        for row in liveSessions {
            do {
                try await row.session.send(message: P2pMessage.Text(value: text, metadata: [:]))
                appendMessage("me -> \(row.peerName): \(text)", kind: .sent)
            } catch {
                let msg = error.localizedDescription
                appendMessage(
                    "send failed (\(row.peerName) state=\(row.state)): \(msg)",
                    kind: .error
                )
                failures.append("\(row.peerName): \(msg)")
            }
        }
        // Promote send failures to the top-of-screen banner so they don't
        // get lost in the message timeline. Common cause is a session
        // that's Connected at session.state.value but whose underlying
        // NWConnection has already entered Closed — that surfaces as
        // P2pError.ConnectionFailed thrown from session.send().
        if !failures.isEmpty {
            errorBanner = "send failed: " + failures.joined(separator: "; ")
        }
        let skipped = sessions.filter { !$0.isConnected }
        for row in skipped {
            appendMessage("skipped \(row.peerName) (state=\(row.state))", kind: .info)
        }
        draft = ""
    }

    @MainActor
    private func closeSession(_ row: SessionRow) async {
        do {
            try await row.session.close()
            appendMessage("closed session with \(row.peerName)", kind: .info)
        } catch {
            appendMessage("close failed (\(row.peerName)): \(error.localizedDescription)", kind: .error)
        }
    }

    @MainActor
    private func stop() async {
        guard let k = kit, !isStopping else { return }
        isStopping = true
        defer { isStopping = false }
        status = "Stopping..."

        pollTask?.cancel()
        incomingSessionsTask?.cancel()
        debugLogTask?.cancel()
        permissionCheckTask?.cancel()

        do {
            try await k.stop()
        } catch {
            appendMessage("stop error: \(error.localizedDescription)", kind: .error)
        }
        kit = nil
        peers = []
        sessions = []
        collectedSessionIds = []
        pendingConnectPeerIds = []
        localPeerId = ""
        localTcpPort = 0
        errorBanner = nil
        status = "Stopped"
    }

    // MARK: - Helpers

    @MainActor
    private func appendMessage(_ text: String, kind: MessageRow.Kind) {
        messages.append(MessageRow(text: text, kind: kind))
        if messages.count > 200 {
            messages.removeFirst(messages.count - 200)
        }
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
