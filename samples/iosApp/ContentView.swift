import SwiftUI
import P2pKitShared
import CryptoKit
import Darwin

/// UI-thread-only selectors shared by consent, cancellation, and watcher updates.
/// Always carry the SDK session; never interpret a transfer ID as process-global.
enum SessionTransferEntries {
    private static let terminalHistoryCapacity = 24

    static func take<Offer>(_ key: TransferKey, from offers: inout [TransferKey: Offer]) -> Offer? {
        offers.removeValue(forKey: key)
    }

    static func row<Row: Identifiable>(_ key: TransferKey, in rows: [Row]) -> Row? where Row.ID == TransferKey {
        rows.first { $0.id == key }
    }

    static func update<Row: Identifiable>(
        _ key: TransferKey, in rows: inout [Row], change: (inout Row) -> Void
    ) where Row.ID == TransferKey {
        guard let index = rows.firstIndex(where: { $0.id == key }) else { return }
        change(&rows[index])
    }

    static func remove<Offer>(
        sessionId: String, transferIds: Set<String>, from offers: inout [TransferKey: Offer]
    ) {
        for id in transferIds {
            offers.removeValue(forKey: TransferKey(sessionId: sessionId, transferId: id))
        }
    }

    /// Keep every active row and the newest 24 terminal rows in insertion order.
    /// History pressure must never remove a live transfer's progress or controls.
    static func trimTerminalHistory<Row>(in rows: inout [Row], isTerminal: (Row) -> Bool) {
        var excess = rows.reduce(0) { $0 + (isTerminal($1) ? 1 : 0) } - terminalHistoryCapacity
        guard excess > 0 else { return }
        rows.removeAll { row in
            guard excess > 0, isTerminal(row) else { return false }
            excess -= 1
            return true
        }
    }
}

/// Atomically claims a sanitized destination; timestamp suffixes are not
/// sufficient because concurrent offers can share the same clock tick.
func claimUniqueDestination(
    in directory: URL,
    rawName: String,
    fileManager: FileManager
) -> URL? {
    let cleaned = rawName
        .replacingOccurrences(of: "/", with: "_")
        .replacingOccurrences(of: "\\", with: "_")
        .replacingOccurrences(of: ":", with: "_")
        .filter { character in
            character.unicodeScalars.allSatisfy { scalar in
                scalar.value >= 0x20 && scalar.value != 0x7f
            }
        }
        .trimmingCharacters(in: .whitespacesAndNewlines)
    let safeName = cleaned.isEmpty || cleaned == "." || cleaned == ".."
        ? "incoming.bin"
        : cleaned
    let ext = (safeName as NSString).pathExtension
    let stem = ext.isEmpty ? safeName : String(safeName.dropLast(ext.count + 1))
    for n in 0...10_000 {
        let candidateName = n == 0
            ? safeName
            : ext.isEmpty ? "\(stem) (\(n))" : "\(stem) (\(n)).\(ext)"
        let candidate = directory.appendingPathComponent(candidateName)
        let descriptor = candidate.path.withCString {
            Darwin.open($0, O_CREAT | O_EXCL | O_WRONLY, S_IRUSR | S_IWUSR)
        }
        if descriptor >= 0 {
            _ = Darwin.close(descriptor)
            return candidate
        }
        if errno != EEXIST {
            return nil
        }
    }
    return nil
}

struct ContentView: View {
    @Environment(\.scenePhase) private var scenePhase
    @StateObject private var diagnostics = IOSTestDiagnosticStore()
    @StateObject private var runLifecycle = SampleRunLifecycle()

    // MARK: - Public state shown in the UI

    @State private var status: String = "Not started"
    @State private var debug: String = ""
    @State private var localPeerId: String = ""
    @State private var localTcpPort: Int = 0
    @State private var localDeviceName: String = "iPhone"
    @State private var peers: [PeerRow] = []
    @State private var sessions: [SessionRow] = []
    @State private var messages: [MessageRow] = []
    @State private var transfers: [TransferRow] = []
    /// Incoming file offers stay pending until the user explicitly accepts or rejects them.
    @State private var pendingOffers: [TransferKey: PendingOffer] = [:]
    #if DEBUG
    private static let consentFixtureSession = "ui-consent-fixture-session"
    private let consentFixtureEnabled = ProcessInfo.processInfo.arguments
        .contains("--p2pkit-ui-test-pending-offer")
    @State private var consentFixtureAccepts = 0
    @State private var consentFixtureRejects = 0
    @State private var consentFixtureError: String?
    #endif
    @State private var draft: String = "hi from iPhone"
    @State private var manualHost: String = ""
    @State private var manualPort: String = ""
    @State private var manualPairingQr: String = ""
    @State private var logLines: [LogLine] = []
    @State private var nextLogId: Int = 0
    @State private var showLog: Bool = true
    @State private var showDiagnostics: Bool = false

    /// Top-of-screen banner for user-actionable errors. Dismissed via the
    /// explicit close button on the banner (AUDIT-2026-06: was tap-to-dismiss
    /// with no visible affordance).
    @State private var errorBanner: String? = nil
    @State private var backupWarning: String? = nil

    // MARK: - Kit + background tasks

    @State private var kit: P2pKit?
    @State private var pollTask: Task<Void, Never>?
    @State private var incomingSessionsTask: Task<Void, Never>?
    @State private var permissionCheckTask: Task<Void, Never>?

    // AUDIT-2026-06 (A-G9-samples-desktop-ios-09): per-session and
    // per-transfer collector Tasks are tracked by id so stop() and
    // session-removal can cancel them. Previously they were fire-and-forget
    // `Task {}` handles that leaked (suspended on a never-completing
    // SharedFlow collect) across every Stop/Start cycle.
    @State private var messageCollectorTasks: [String: Task<Void, Never>] = [:]
    @State private var fileCollectorTasks: [String: Task<Void, Never>] = [:]
    @State private var fileOfferIdsBySession: [String: Set<String>] = [:]
    @State private var cleanedTransferDirectories: Set<String> = []
    @State private var transferWatchTasks: [TransferKey: Task<Void, Never>] = [:]

    // MARK: - In-flight guards (prevent rapid double-taps from spawning
    // parallel work).

    private var isStarting: Bool { runLifecycle.phase == .starting }
    private var isStopping: Bool { runLifecycle.phase == .stopping }
    @State private var isManualDialing: Bool = false
    @State private var pendingConnectPeerIds: Set<String> = []
    @State private var sendingFileSessionIds: Set<String> = []

    /// UI-test-only input-loss seam. This models XCTest reporting a delivered
    /// tap while leaving the application untouched, without changing release
    /// behavior or any P2pKit operation. It is compiled out of Release builds.
    @State private var ignoreNextStartActionForUITest: Bool = {
        #if DEBUG
        ProcessInfo.processInfo.arguments.contains("--p2pkit-ui-test-drop-first-start-action")
        #else
        false
        #endif
    }()

    /// Test-only deterministic file presets. These keep physical-device
    /// transfer runs reproducible without a document-provider fixture.
    private enum TestFilePreset: String, CaseIterable, Identifiable {
        case small = "200 KiB"
        case medium = "5 MiB"
        case boundary = "49 MiB"

        var id: String { rawValue }

        var byteCount: Int {
            switch self {
            case .small: return 200 * 1024
            case .medium: return 5 * 1024 * 1024
            case .boundary: return 49 * 1024 * 1024
            }
        }
    }

    /// Session ids whose `incoming`/`pendingFileOffers` flows we've already
    /// subscribed to, so duplicate Connect taps don't attach a second
    /// collector and echo every received message.
    @State private var collectedSessionIds: Set<String> = []

    /// Signature of the last cross-check warning; identical poll results are
    /// intentionally not emitted once per second.
    @State private var lastCrossCheckSignature: String?

    /// True once NWBrowser has transitioned to `.ready` at least once
    /// in THIS run. Used to detect iOS Local Network permission denial —
    /// if the browser is stuck in `.waiting` for ~6 s we surface a hint.
    @State private var browserEverReady: Bool = false

    // AUDIT-2026-06 (A-G9-samples-desktop-ios-06): IosLanDebug replays up to
    // 200 lines from previous runs to late subscribers. A per-run epoch
    // marker is logged right after we subscribe; every line before it is
    // replayed history and must not satisfy the readiness probe (or pollute
    // the probe after Stop/Start).
    @State private var probeEpoch: String = ""
    @State private var probeEpochSeen: Bool = false

    // AUDIT-2026-06 (D-G9-samples-desktop-ios-19): keyboard focus tracking so
    // the number-pad (which has no return key on iOS 15) can be dismissed via
    // a keyboard-toolbar Done button.
    private enum FocusField: Hashable {
        case deviceName, manualHost, manualPort, manualPairingQr, draft
    }
    @FocusState private var focusedField: FocusField?

    /// AUDIT-2026-06 (D-G9-samples-desktop-ios-14): the permission hint lives
    /// in a constant so the late-readiness handler can recognize and retract
    /// exactly this banner without clobbering unrelated errors.
    private static let localNetworkHint =
        "NWBrowser is not ready after 6 s. " +
        "iOS may have denied Local Network access — open " +
        "Settings → Privacy & Security → Local Network and " +
        "enable this app, then tap Stop / Start."

    private static let messageByteCapacity = 256 * 1024

    // MARK: - Row models

    struct PeerRow: Identifiable, Equatable {
        let id: String
        let name: String
        let peer: Peer
        static func == (lhs: PeerRow, rhs: PeerRow) -> Bool {
            lhs.id == rhs.id && lhs.name == rhs.name &&
                String(describing: lhs.peer.platform) == String(describing: rhs.peer.platform) &&
                String(describing: lhs.peer.supportedTransports) ==
                    String(describing: rhs.peer.supportedTransports)
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

    /// AUDIT-2026-06 (B-G9-samples-desktop-ios-06): log lines carry a stable,
    /// monotonically increasing id. The previous `enumerated()` offset
    /// identity shifted every row on each trim, forcing a full re-render of
    /// 200 Text rows per transport event.
    struct LogLine: Identifiable, Equatable {
        let id: Int
        let text: String
    }

    /// AUDIT-2026-06 (D-G9-samples-desktop-ios-03 / A-G9-samples-desktop-ios-07):
    /// one row per file transfer (either direction) so incoming offers and
    /// outgoing sends are visible with live progress instead of silently
    /// timing out after 30 s.
    struct PendingOffer: Identifiable {
        let id: TransferKey
        let offer: P2pFileOffer
    }

    struct TransferRow: Identifiable, Equatable {
        let id: TransferKey
        let peerName: String
        let fileName: String
        let direction: Direction
        var stateLabel: String
        var bytes: Int64
        let totalBytes: Int64
        var isTerminal: Bool
        /// Receive rows: destination file name under Documents/P2pKitInbox.
        let detail: String?
        let transfer: P2pFileTransfer
        enum Direction { case send, receive }
        var progress: Double {
            totalBytes > 0 ? min(1.0, Double(bytes) / Double(totalBytes)) : 0.0
        }
        static func == (lhs: TransferRow, rhs: TransferRow) -> Bool {
            lhs.id == rhs.id && lhs.stateLabel == rhs.stateLabel &&
                lhs.bytes == rhs.bytes && lhs.isTerminal == rhs.isTerminal
        }
    }

    private var trimmedDeviceName: String {
        localDeviceName.trimmingCharacters(in: .whitespacesAndNewlines)
    }

    // MARK: - View

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 12) {
                headerSection
                Divider()
                peersSection
                Divider()
                manualConnectSection
                Divider()
                sessionsSection
                #if DEBUG
                if consentFixtureEnabled {
                    consentFixtureControls
                }
                #endif
                if !pendingOffers.isEmpty || !transfers.isEmpty {
                    Divider()
                    transfersSection
                }
                Divider()
                messagesSection
                Divider()
                logSection
                Spacer()
            }
            .padding()
        }
        // AUDIT-2026-06 (D-G9-samples-desktop-ios-19): keyboard toolbar Done
        // button — the .numberPad keyboard has no return key on the iOS 15
        // deployment target, so without this the Port field's keyboard could
        // only be dismissed by focusing another field.
        .toolbar {
            ToolbarItemGroup(placement: .keyboard) {
                Spacer()
                Button("Done") { focusedField = nil }
            }
        }
        .sheet(isPresented: $showDiagnostics) {
            IOSTestDiagnosticsView(
                diagnostics: diagnostics,
                activeConnections: {
                    sessions.map { session in
                        TestDiagnosticConnectionSnapshot(
                            rawConnectionId: session.id,
                            peerId: session.peerId,
                            state: session.state
                        )
                    }
                }
            )
        }
        .onAppear { prepareManagedStorage() }
        .onChange(of: scenePhase) { phase in
            switch phase {
            case .active:
                diagnostics.record(TestDiagnosticRecord(
                    category: "application",
                    eventName: TestDiagnosticEventName.applicationForegrounded,
                    currentState: "foreground"
                ))
                kit?.notifyAppForegrounded()
            case .background:
                diagnostics.record(TestDiagnosticRecord(
                    category: "application",
                    eventName: TestDiagnosticEventName.applicationBackgrounded,
                    currentState: "background"
                ))
                kit?.notifyAppBackgrounded()
            default:
                break
            }
        }
    }

    @ViewBuilder
    private var headerSection: some View {
        Text("P2pKit Sample")
            .font(.title)
            .accessibilityIdentifier("sample-title")
        Button("Test Diagnostics") {
            showDiagnostics = true
        }
        .buttonStyle(.bordered)
        .accessibilityIdentifier("test-diagnostics")
        // V0.4-PROVENANCE (L2 UI): show the active framework
        // build identity so the operator can visually confirm
        // the deployed SDK version before starting any hardware
        // test, without grepping logs.
        Text(BuildInfo.shared.describe())
            .accessibilityIdentifier("sample-build-info")
            .font(.caption)
            .foregroundColor(.secondary)
            .textSelection(.enabled)
        Text("Status: \(status)")
            .accessibilityIdentifier("sample-status")

        if let backupWarning {
            Text(backupWarning)
                .font(.callout)
                .foregroundColor(.red)
                .accessibilityIdentifier("backup-policy-warning")
            Button("Retry storage setup") { prepareManagedStorage() }
                .buttonStyle(.bordered)
                .accessibilityIdentifier("retry-backup-policy")
        }

        if let err = errorBanner {
            // AUDIT-2026-06 (D-G9-samples-desktop-ios-16): explicit dismiss
            // button with an accessibility label — the old tap-anywhere
            // gesture was undiscoverable and invisible to VoiceOver.
            HStack(alignment: .top, spacing: 8) {
                Text(err)
                    .font(.callout)
                    .foregroundColor(.white)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .textSelection(.enabled)
                Button {
                    errorBanner = nil
                } label: {
                    Image(systemName: "xmark.circle.fill")
                        .foregroundColor(.white)
                }
                .accessibilityLabel("Dismiss error")
            }
            .padding(8)
            .background(Color.red.opacity(0.85))
            .cornerRadius(6)
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
            Text("localTcpPort: \(String(localTcpPort))")
                .font(.system(.caption, design: .monospaced))
                .textSelection(.enabled)
        }

        if !isStopping, let qr = kit?.localPairingQr {
            // Bind disclosure state to this exact kit identity; never retain a stale QR after Stop/Start.
            LocalPairingView(qr: qr).id(qr)
        }

        TextField("Device name", text: $localDeviceName)
            .textFieldStyle(.roundedBorder)
            .disabled(kit != nil || isStarting)
            .autocorrectionDisabled()
            .focused($focusedField, equals: .deviceName)

        HStack {
            if kit == nil {
                Button(isStarting ? "Starting…" : "Start") {
                    if consumeIgnoredStartActionForUITest() {
                        return
                    }
                    Task { await start() }
                }
                .accessibilityIdentifier("start-kit")
                .buttonStyle(.borderedProminent)
                .disabled(isStarting || trimmedDeviceName.isEmpty)
            } else {
                Button(isStopping ? "Stopping…" : "Stop") {
                    if let run = runLifecycle.current {
                        Task { await stop(run: run) }
                    }
                }
                .accessibilityIdentifier("stop-kit")
                .buttonStyle(.borderedProminent)
                .tint(.red)
                .disabled(isStopping)
            }
        }
    }

    // MARK: Discovered peers

    @ViewBuilder
    private var peersSection: some View {
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
                    runLifecycle.launchAction { run in await connect(row, run: run) }
                }
                .buttonStyle(.bordered)
                .disabled(alreadyConnected || inFlight || pending || kit == nil || isStopping)
            }
            .padding(.vertical, 4)
        }
    }

    // MARK: Manual IP fallback

    @ViewBuilder
    private var manualConnectSection: some View {
        Text("Manual connect (skip Bonjour)").font(.headline)
        HStack {
            TextField("Host (e.g. 192.168.1.42)", text: $manualHost)
                .textFieldStyle(.roundedBorder)
                .keyboardType(.numbersAndPunctuation)
                .autocorrectionDisabled()
                .disabled(isManualDialing)
                .focused($focusedField, equals: .manualHost)
            TextField("Port", text: $manualPort)
                .textFieldStyle(.roundedBorder)
                .keyboardType(.numberPad)
                .frame(width: 80)
                .disabled(isManualDialing)
                .focused($focusedField, equals: .manualPort)
        }
        TextField("Peer pairing QR text (p2pkit:v2:…)", text: $manualPairingQr)
            .textFieldStyle(.roundedBorder)
            .textInputAutocapitalization(.never)
            .autocorrectionDisabled()
            .disabled(isManualDialing)
            .focused($focusedField, equals: .manualPairingQr)
        Button(isManualDialing ? "Dialing…" : "Dial manual peer") {
            runLifecycle.launchAction { run in await dialManual(run: run) }
        }
        .buttonStyle(.bordered)
        .disabled(
            kit == nil ||
            isManualDialing ||
            isStopping ||
            manualHost.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty ||
            manualPort.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty ||
            manualPairingQr.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
        )
    }

    // MARK: Sessions

    @ViewBuilder
    private var sessionsSection: some View {
        let connectedCount = sessions.filter { $0.isConnected }.count
        Text("Sessions (\(sessions.count), \(connectedCount) connected)").font(.headline)
        ForEach(sessions) { row in
            VStack(alignment: .leading, spacing: 2) {
                HStack {
                    Circle()
                        .fill(sessionDotColor(for: row))
                        .frame(width: 8, height: 8)
                    Text("\(row.peerName) — \(row.state)").font(.callout)
                        .accessibilityIdentifier("sample-session-state")
                    Spacer()
                    // Test-only deterministic presets cover normal,
                    // multi-megabyte, and near-quota transfers without a
                    // document-provider fixture.
                    Menu(sendingFileSessionIds.contains(row.id) ? "Sending…" : "Send test file") {
                        ForEach(TestFilePreset.allCases) { preset in
                            Button(preset.rawValue) {
                                runLifecycle.launchAction { run in
                                    await sendTestFile(to: row, preset: preset, run: run)
                                }
                            }
                            .accessibilityIdentifier("send-test-file-\(preset.byteCount)")
                        }
                    }
                    .buttonStyle(.bordered)
                    .disabled(!row.isConnected || isStopping || sendingFileSessionIds.contains(row.id))
                    .accessibilityIdentifier("send-test-file")
                    // AUDIT-2026-06 (D-G9-samples-desktop-ios-17): default
                    // control size — .small put the tap target well under
                    // the 44 pt guideline.
                    Button("Close") {
                        runLifecycle.launchAction { run in await closeSession(row, run: run) }
                    }
                    .buttonStyle(.bordered)
                    .disabled(row.isTerminal || isStopping)
                }
                // Surface session-id + peer-id so we can verify the
                // session matches the peer row above. Mismatched ids
                // here would mean the SDK created a session against a
                // different peer than the one in the discovery list.
                // AUDIT-2026-06 (D-G9-samples-desktop-ios-17): .caption2
                // (scales with Dynamic Type) instead of fixed 9 pt.
                Text("session=\(row.id.prefix(12))  peer=\(row.peerId.prefix(8))")
                    .font(.system(.caption2, design: .monospaced))
                    .foregroundColor(.secondary)
            }
            .padding(.vertical, 2)
        }
        if !sessions.isEmpty {
            HStack {
                TextField("message", text: $draft)
                    .textFieldStyle(.roundedBorder)
                    .autocorrectionDisabled()
                    .focused($focusedField, equals: .draft)
                Button("Send all (\(connectedCount))") {
                    runLifecycle.launchAction { run in await sendAll(run: run) }
                }
                .buttonStyle(.bordered)
                .disabled(
                    draft.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty ||
                    connectedCount == 0 ||
                    isStopping
                )
            }
        }
    }

    // MARK: File transfers
    //
    // AUDIT-2026-06 (D-G9-samples-desktop-ios-03 / A-G9-samples-desktop-ios-07):
    // file transfer was previously invisible on iOS — no send affordance and
    // incoming offers auto-rejected after the 30 s timeout with zero UI trace.
    // Incoming offers remain visible until the user explicitly accepts or
    // rejects them; accepted transfers render here with live progress.

    @ViewBuilder
    private var transfersSection: some View {
        if !pendingOffers.isEmpty {
            Text("Incoming file offers").font(.headline)
            ForEach(Array(pendingOffers.values)) { pending in
                let offer = pending.offer
                HStack {
                    VStack(alignment: .leading, spacing: 2) {
                        Text("\(offer.name) from \(offer.peer.name)").font(.caption)
                        Text("\(fmtBytes(offer.sizeBytes)) — waiting for consent")
                            .accessibilityIdentifier("offer-size-\(offer.name)")
                            .font(.system(.caption2, design: .monospaced))
                            .foregroundColor(.secondary)
                    }
                    Spacer()
                    Button("Accept") {
                        runLifecycle.launchAction { run in await acceptIncomingOffer(pending, run: run) }
                    }
                    .buttonStyle(.borderedProminent)
                    .accessibilityIdentifier("accept-offer-\(offer.name)")
                    Button("Reject") {
                        runLifecycle.launchAction { run in await rejectIncomingOffer(pending, run: run) }
                    }
                    .buttonStyle(.bordered)
                }
            }
        }
        Text("File transfers (\(transfers.count))").font(.headline)
        ForEach(transfers) { t in
            VStack(alignment: .leading, spacing: 2) {
                HStack {
                    Image(systemName: t.direction == .send ? "arrow.up.circle" : "arrow.down.circle")
                        .foregroundColor(t.direction == .send ? .blue : .green)
                    Text("\(t.fileName) \(t.direction == .send ? "→" : "←") \(t.peerName)")
                        .font(.caption)
                        .lineLimit(1)
                    Spacer()
                    if !t.isTerminal {
                        Button("Cancel") {
                            runLifecycle.launchAction { run in await cancelTransfer(t, run: run) }
                        }
                        .buttonStyle(.bordered)
                    }
                }
                ProgressView(value: t.progress)
                Text(transferCaption(for: t))
                    .accessibilityIdentifier("transfer-\(t.direction == .send ? "send" : "receive")-\(t.fileName)")
                    .font(.system(.caption2, design: .monospaced))
                    .foregroundColor(.secondary)
                    .textSelection(.enabled)
            }
            .padding(.vertical, 2)
        }
    }

    // MARK: Messages

    @ViewBuilder
    private var messagesSection: some View {
        Text("Messages (\(messages.count))").font(.headline)
        ForEach(messages) { m in
            Text(m.text)
                .font(.caption)
                .foregroundColor(m.color)
                .textSelection(.enabled)
        }
    }

    // MARK: Diagnostic log
    //
    // Every iOS LAN transport event (listener bind, raw
    // connection state transitions, every nw_connection_send /
    // _receive completion, NWBrowser events, manual-IP dial)
    // AND every iOS-sample UI action (Start tap, Connect tap,
    // Send tap, picker dismissal, lifecycle) is pushed into the
    // same `IosLanDebug` SharedFlow and rendered here in time
    // order. The single timeline is the easiest way to see
    // whether the UI thinks it's done one thing but the SDK is
    // doing something else.

    @ViewBuilder
    private var logSection: some View {
        Toggle("Diagnostic log (\(logLines.count))", isOn: $showLog)
            .font(.headline)
        if showLog {
            // AUDIT-2026-06 (B-G9-samples-desktop-ios-06): LazyVStack +
            // stable LogLine ids (the old eager ForEach keyed by enumerated
            // offset re-rendered all 200 rows per appended line once
            // trimming started). Font bumped from fixed 10 pt to .caption2
            // so it scales with Dynamic Type (D-G9-samples-desktop-ios-17).
            LazyVStack(alignment: .leading, spacing: 0) {
                ForEach(logLines) { l in
                    Text(l.text)
                        .font(.system(.caption2, design: .monospaced))
                        .textSelection(.enabled)
                }
            }
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

    private func transferCaption(for t: TransferRow) -> String {
        var caption = "\(t.stateLabel) — \(fmtBytes(t.bytes)) / \(fmtBytes(t.totalBytes))"
        if let detail = t.detail, t.direction == .receive {
            caption += " — Documents/P2pKitInbox/\(detail)"
        }
        return caption
    }

    private func fmtBytes(_ n: Int64) -> String {
        if n >= 1_048_576 { return String(format: "%.1f MB", Double(n) / 1_048_576.0) }
        if n >= 1_024 { return String(format: "%.0f KB", Double(n) / 1_024.0) }
        return "\(n) B"
    }

    private func sha256File(at url: URL) throws -> String {
        let handle = try FileHandle(forReadingFrom: url)
        defer { try? handle.close() }
        var hasher = CryptoKit.SHA256()
        while true {
            let chunk = try handle.read(upToCount: 64 * 1024) ?? Data()
            if chunk.isEmpty { break }
            hasher.update(data: chunk)
        }
        return hasher.finalize().map { String(format: "%02x", $0) }.joined()
    }

    // MARK: - Actions

    private func consumeIgnoredStartActionForUITest() -> Bool {
        guard ignoreNextStartActionForUITest else { return false }
        ignoreNextStartActionForUITest = false
        return true
    }

    @MainActor
    private func start() async {
        diag("ui", "Start tapped")
        // Re-entry / preconditions.
        guard !isStarting else {
            diag("ui", "Start ignored — isStarting already true")
            return
        }
        guard kit == nil else {
            diag("ui", "Start ignored — kit already set")
            return
        }
        let name = trimmedDeviceName
        guard !name.isEmpty else {
            diag("ui", "Start ABORT — device name empty")
            errorBanner = "Device name cannot be empty."
            return
        }

        guard let run = runLifecycle.begin() else { return }
        var startupCompleted = false
        defer {
            // Release even when create/start or the SDK's rollback fails.
            // Retaining a kit for retry does not require global tracing.
            if !startupCompleted { run.releaseTracing() }
        }
        errorBanner = nil
        status = "Starting..."
        debug = ""
        messages = []
        transfers = []
        logLines = []
        collectedSessionIds = []
        pendingConnectPeerIds = []
        sendingFileSessionIds = []
        browserEverReady = false
        lastCrossCheckSignature = nil
        // AUDIT-2026-06 (A-G9-samples-desktop-ios-06): fresh probe epoch per
        // run; replayed lines from previous runs precede the marker and are
        // ignored by the readiness probe.
        probeEpoch = "probe-epoch-\(UUID().uuidString)"
        probeEpochSeen = false
        diag("ui", "Start: cleared local state, building kit")

        // The lease mirrors only in Debug and restores settings on teardown.
        // Bounded in-app replay remains available in both configurations.
        let lanDiagnosticsLease = IosLanDiagnosticsLease.acquire()

        // Decoded frame-type trace (Issue #2/#3). Each
        // TX/RX frame line (PING/PONG/DATA/FILE_*) enters the in-app timeline
        // and recorder. The LAN lease mirrors that timeline only in Debug.
        let frameTraceLease = FrameTrace.shared.installSink(enabled: true) { line in
            Task { @MainActor in
                guard self.runLifecycle.ownsTracing(run) else { return }
                IosLanDebug.shared.log(tag: "frame", message: line)
                self.diagnostics.recordFrame(line)
            }
        }

        // Subscribe to IosLanDebug BEFORE startAdvertising/Discovery so
        // we capture every browser-state and result-change from t=0.
        let debugLogTask = Task {
            guard self.runLifecycle.ownsTracing(run), !Task.isCancelled else { return }
            let collector = StringCollector { line in
                await MainActor.run {
                    guard self.runLifecycle.ownsTracing(run) else { return }
                    self.appendLog(line)
                    self.diagnostics.recordTransport(line)
                    if !self.probeEpochSeen {
                        if line.contains(self.probeEpoch) {
                            self.probeEpochSeen = true
                        }
                        return
                    }
                    // AUDIT-2026-06 (A-G9-samples-desktop-ios-06): match the
                    // tagged NWBrowser line specifically. The TCP listener
                    // logs "[data] listener state -> ready" even when Local
                    // Network permission is denied, so the old bare
                    // "state -> ready" substring always defeated the probe.
                    if line.contains("[browse] state -> ready") {
                        self.browserEverReady = true
                        // AUDIT-2026-06 (D-G9-samples-desktop-ios-14): if the
                        // browser reaches ready after the 6 s probe already
                        // fired, retract the now-stale permission hint.
                        if self.errorBanner == Self.localNetworkHint {
                            self.errorBanner = nil
                        }
                    }
                }
            }
            _ = try? await IosLanDebug.shared.events.collect(collector: collector)
        }
        run.ownTracing {
            frameTraceLease.release()
            debugLogTask.cancel()
            lanDiagnosticsLease.release()
        }
        diag("ui", probeEpoch)

        let built: P2pKit
        do {
            built = try P2pKitCompanion.shared.create { (builder: P2pKitBuilder) in
                builder.appId = "p2pkit-desktop-sample"
                builder.deviceName = name
                // Development harness policy: encryption and authenticated
                // key possession stay mandatory, but any identity scoped to
                // this exact AppId is admitted. Production apps should use a
                // full fingerprint/QR pin policy.
                builder.security { (security: SecurityConfigBuilder) in
                    security.mode = SecurityMode.AuthenticatedV2(
                        authorization: PeerAuthorizationPolicyAcceptAnyAuthenticatedSameApp.shared
                    )
                }
                builder.transports { (tx: TransportsBuilder) in
                    tx.lan()
                }
                // Sample-only tuning. SDK defaults are
                // pingIntervalMillis=10_000 / timeoutMillis=30_000.
                builder.keepAlive { (kaBuilder: KeepAliveConfigBuilder) in
                    kaBuilder.pingIntervalMillis = 2_000
                    kaBuilder.timeoutMillis = 6_000
                }
                builder.networkProvisioning { (np: NetworkProvisioningConfigBuilder) in
                    np.iosManualIp()
                }
            }
        } catch {
            defer { runLifecycle.abandonUnbuilt(run) }
            if Task.isCancelled || error is CancellationError { return }
            let detail = SampleP2pError.userMessage(error)
            status = "Create failed: \(detail)"
            errorBanner = "Could not create P2pKit: \(detail)"
            diag("kit", "create FAILED: \(SampleConsole.failure(error))")
            return
        }
        self.kit = built
        self.localPeerId = "\(built.localPeerId)"
        diagnostics.setLocalPeerId(localPeerId)
        diagnostics.record(TestDiagnosticRecord(
            peerId: localPeerId,
            category: "peer",
            eventName: TestDiagnosticEventName.peerInitialized,
            currentState: "ready"
        ))
        diag("kit", "P2pKit constructed (peerId=\(SampleConsole.identifier(localPeerId)))")

        let outcome = await runLifecycle.completeStartup(
            run,
            advertise: {
                diag("kit", "calling startAdvertising")
                try await built.startAdvertising()
            },
            didAdvertise: { diag("kit", "startAdvertising returned OK") },
            discover: {
                diag("kit", "calling startDiscovery")
                try await built.startDiscovery()
            },
            didDiscover: {
                diagnostics.record(TestDiagnosticRecord(
                    category: "discovery",
                    eventName: TestDiagnosticEventName.discoveryStarted,
                    currentState: "active"
                ))
                diag("kit", "startDiscovery returned OK")
                status = "Running"
            },
            manualInfo: { try await built.networkProvisioning.getManualConnectionInfo() },
            didReadInfo: { result in
                switch result {
                case .success(let info):
                    if let info {
                        self.localTcpPort = Int(info.port)
                        diag("kit", "manual connection info: port=\(info.port)")
                    }
                case .failure(let error):
                    diag("kit", "getManualConnectionInfo failed: \(SampleConsole.failure(error))")
                }
            },
            installObservers: { installRunObservers(for: built, run: run) }
        )
        switch outcome {
        case .started:
            startupCompleted = true
        case .superseded:
            // Stop owns the captured kit's teardown. Never clear a successor.
            return
        case .failed(let error):
            // completeStartup itself is awaited: Stop may have won before this
            // caller resumed, so fence failure publication and rollback too.
            guard runLifecycle.withActiveRun(run, {
                diag("kit", "start FAILED: \(SampleConsole.failure(error))")
                status = "Start failed: \(error.localizedDescription)"
                errorBanner = "Failed to start: \(error.localizedDescription)"
            }) else { return }
            // Even caller cancellation must reach real SDK rollback. Failure
            // retains this run and its kit, so Stop can retry its cleanup.
            await runLifecycle.stop(
                run,
                cancelObservers: { cancelRunObservers() },
                operation: { try await built.stop() },
                succeeded: { retireStoppedRun() },
                failed: { cleanupError in
                    status = "Start failed — cleanup pending"
                    errorBanner = "Start failed and cleanup did not complete: " +
                        cleanupError.localizedDescription + ". Tap Stop to retry."
                    diag("kit", "startup cleanup FAILED; ownership retained: \(SampleConsole.failure(cleanupError))")
                }
            )
        }
    }

    @MainActor
    private func installRunObservers(for built: P2pKit, run: SampleRunLifecycle.Run) {
        runLifecycle.withActiveRun(run) {
            self.incomingSessionsTask = Task { [weak built] in
                guard self.runLifecycle.acceptsWork(run), !Task.isCancelled else { return }
                let collector = SessionCollector { session in
                    self.runLifecycle.withActiveRun(run) {
                        IosLanDebug.shared.log(
                            tag: "ui",
                            message: "incomingSessions emitted: peer=\(SampleConsole.identifier("\(session.peer.id)")) " +
                                "id=\(SampleConsole.identifier(session.id))"
                        )
                        self.attachCollectors(to: session, label: "incoming", run: run)
                    }
                }
                _ = try? await built?.incomingSessions.collect(collector: collector)
            }

            self.pollTask = Task { @MainActor in
                var tick = 0
                while !Task.isCancelled && self.runLifecycle.acceptsWork(run) {
                    refreshPeersAndSessions(from: built, run: run)
                    // The listener can rebind and change port during a run.
                    if tick % 5 == 0 {
                        let info = try? await built.networkProvisioning.getManualConnectionInfo()
                        guard self.runLifecycle.acceptsWork(run), !Task.isCancelled else { break }
                        if let info {
                            let port = Int(info.port)
                            if port > 0 && port != self.localTcpPort {
                                diag("kit", "localTcpPort changed \(self.localTcpPort) -> \(port) (listener rebind)")
                                self.localTcpPort = port
                            }
                        }
                    }
                    tick += 1
                    do {
                        try await Task.sleep(nanoseconds: 1_000_000_000)
                    } catch { return }
                }
            }

            // A cancelled permission probe must not turn Stop into a denial hint.
            self.permissionCheckTask = Task { @MainActor in
                await self.runLifecycle.afterDelay(
                    run,
                    delay: { try await Task.sleep(nanoseconds: 6_000_000_000) },
                    perform: {
                        if !self.browserEverReady {
                            self.errorBanner = Self.localNetworkHint
                        }
                    }
                )
            }
        }
    }

    @MainActor
    private func refreshPeersAndSessions(from kit: P2pKit, run: SampleRunLifecycle.Run) {
        guard runLifecycle.acceptsWork(run) else { return }
        let peerArray: [Peer] = IosSwiftHelpersKt.peersSnapshot(kit)
        let sessionArray: [P2pSession] = IosSwiftHelpersKt.sessionsSnapshot(kit)

        self.debug = "peers=\(peerArray.count) sessions=\(sessionArray.count)"

        let peerRows = peerArray.map { p in
            PeerRow(id: "\(p.id)", name: p.name, peer: p)
        }.sorted { $0.name < $1.name }
        let previousPeerIds = Set(self.peers.map(\.id))
        let currentPeerIds = Set(peerRows.map(\.id))
        for peer in peerRows where !previousPeerIds.contains(peer.id) {
            diagnostics.record(TestDiagnosticRecord(
                peerId: peer.id,
                category: "discovery",
                eventName: TestDiagnosticEventName.peerDiscovered,
                currentState: "available",
                details: ["peerName": peer.name]
            ))
        }
        for peer in self.peers where !currentPeerIds.contains(peer.id) {
            diagnostics.record(TestDiagnosticRecord(
                peerId: peer.id,
                category: "discovery",
                eventName: TestDiagnosticEventName.peerLost,
                currentState: "unavailable",
                previousState: "available"
            ))
        }
        if peerRows != self.peers { self.peers = peerRows }

        let sessionRows = sessionArray.map { s in
            SessionRow(
                id: s.id,
                peerId: "\(s.peer.id)",
                peerName: s.peer.name,
                // Use the Kotlin helper rather than "\(s.state.value)" —
                // the latter returns "Optional(Connected)" because
                // StateFlow<T>.value generic-erases to Any? in the Swift
                // bridge. See IosSwiftHelpers.kt.
                state: IosSwiftHelpersKt.stateName(s),
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
                diagnostics.connection(
                    peerId: row.peerId,
                    rawConnectionId: row.id,
                    state: row.state,
                    previous: prev.state
                )
                appendMessage(
                    "[session] \(row.peerName) (\(row.peerId.prefix(8))) → \(row.state)",
                    kind: .info
                )
                diag(
                    "session",
                    "peer=\(SampleConsole.identifier(row.peerId)) \(prev.state) → \(row.state)"
                )
            } else if previousById[row.id] == nil {
                diagnostics.connection(
                    peerId: row.peerId,
                    rawConnectionId: row.id,
                    state: row.state,
                    previous: nil
                )
                appendMessage(
                    "[session] new \(row.peerName) (\(row.peerId.prefix(8))) state=\(row.state)",
                    kind: .info
                )
                diag(
                    "session",
                    "new id=\(SampleConsole.identifier(row.id)) " +
                        "peer=\(SampleConsole.identifier(row.peerId)) state=\(row.state)"
                )
            }
        }
        // Detect session disappearances (removed from kit.sessions, typically
        // because watchForTerminal cleaned them out after Closed/Failed).
        let currentIds = Set(sessionRows.map { $0.id })
        for prev in self.sessions where !currentIds.contains(prev.id) {
            let connectionId = diagnostics.removeConnection(rawConnectionId: prev.id)
            diagnostics.record(TestDiagnosticRecord(
                peerId: prev.peerId,
                connectionId: connectionId,
                category: "connection",
                eventName: TestDiagnosticEventName.connectionDisconnected,
                currentState: "removed",
                previousState: prev.state,
                outcome: .interruption
            ))
            diag(
                "session",
                "removed id=\(SampleConsole.identifier(prev.id)) " +
                    "peer=\(SampleConsole.identifier(prev.peerId)) lastState=\(prev.state)"
            )
            // AUDIT-2026-06 (A-G9-samples-desktop-ios-09): release the dead
            // session's collector tasks and its dedup entry — they otherwise
            // stay suspended on the never-completing SharedFlow forever.
            messageCollectorTasks[prev.id]?.cancel()
            messageCollectorTasks[prev.id] = nil
            fileCollectorTasks[prev.id]?.cancel()
            fileCollectorTasks[prev.id] = nil
            SessionTransferEntries.remove(
                sessionId: prev.id,
                transferIds: fileOfferIdsBySession.removeValue(forKey: prev.id) ?? [],
                from: &pendingOffers
            )
            collectedSessionIds.remove(prev.id)
        }

        // Watchdog: multiple sessions for the same peer should never persist
        // for more than one poll-tick (1 s) — the SDK's `registerSession` /
        // `connect()` / `watchForTerminal` paths are supposed to keep
        // `_sessions` consistent with `active` (one entry per peerId at most).
        // Log loudly if we observe more than one row for a single peerId so
        // a real bug doesn't hide silently behind the PeerRow's isLive filter.
        let groupedByPeer = Dictionary(grouping: sessionRows, by: { $0.peerId })
        for (peerIdKey, rows) in groupedByPeer where rows.count > 1 {
            let summary = rows.map { "\(SampleConsole.identifier($0.id))[\($0.state)]" }.joined(separator: ", ")
            diag(
                "session",
                "WARN: \(rows.count) sessions for peer=\(SampleConsole.identifier(peerIdKey)): \(summary)"
            )
        }

        // Cross-check: for each PeerRow in self.peers, does at least one
        // SessionRow share its peerId? Surfaces the "messages flow but UI
        // shows Connect" symptom if it's a peer-id mismatch (e.g., a Bonjour
        // vs HELLO disagreement, or a Swift bridge formatting glitch).
        var crossCheckWarnings: [String] = []
        for peerRow in self.peers {
            let matchingSessions = sessionRows.filter { $0.peerId == peerRow.id }
            if matchingSessions.isEmpty && !sessionRows.isEmpty {
                // We have sessions but none match THIS peer's id. Worth
                // logging because the user-reported "shows not connected"
                // symptom looks like this.
                let allSessionPeerIds = sessionRows.map { SampleConsole.identifier($0.peerId) }
                    .joined(separator: ",")
                crossCheckWarnings.append(
                    "peer \(SampleConsole.identifier(peerRow.id)) " +
                        "has no matching session row (sessions exist with peerIds=[\(allSessionPeerIds)])"
                )
            }
        }
        let crossCheckSignature = crossCheckWarnings.joined(separator: "|")
        if crossCheckSignature != lastCrossCheckSignature {
            if !crossCheckWarnings.isEmpty {
                diag("session", "WARN: " + crossCheckWarnings.joined(separator: " | "))
            }
            lastCrossCheckSignature = crossCheckSignature
        }

        if sessionRows != self.sessions { self.sessions = sessionRows }

        for row in sessionRows where !collectedSessionIds.contains(row.id) {
            attachCollectors(to: row.session, label: "tracked", run: run)
        }
    }

    /// Subscribe to a session's `incoming` messages and authoritative retained
    /// `pendingFileOffers` snapshots.
    ///
    /// AUDIT-2026-06 (B-G9-samples-desktop-ios-03): both flows are hot
    /// SharedFlows whose `collect` NEVER completes, so this function spawns
    /// each collect into a stored, cancellable Task and returns immediately.
    /// The old version awaited `incoming.collect` inline, which wedged every
    /// caller that awaited it: connect()'s and dialManual()'s `defer`
    /// cleanups never ran (Connect button stuck on "Connecting…", manual
    /// dial latched forever) and the incomingSessions collector stalled
    /// after its first emission.
    ///
    /// AUDIT-2026-06 (A-G9-samples-desktop-ios-09): the spawned tasks are
    /// tracked in dictionaries keyed by session id and cancelled in stop()
    /// and on session removal.
    @MainActor
    private func attachCollectors(to session: P2pSession, label: String, run: SampleRunLifecycle.Run) {
        runLifecycle.withActiveRun(run) {
            let sid = session.id
            guard !collectedSessionIds.contains(sid) else { return }
            collectedSessionIds.insert(sid)
            appendMessage("[\(label)] session opened: \(session.peer.name)", kind: .info)

            messageCollectorTasks[sid] = Task {
                guard self.runLifecycle.acceptsWork(run), !Task.isCancelled else { return }
                let collector = MessageCollector { msg in
                    await MainActor.run {
                        guard self.runLifecycle.acceptsWork(run) else { return }
                        if let text = msg as? P2pMessage.Text {
                            self.diagnostics.record(TestDiagnosticRecord(
                                peerId: "\(session.peer.id)",
                                connectionId: self.diagnostics.connectionId(for: "\(session.peer.id)"),
                                category: "metadata",
                                eventName: TestDiagnosticEventName.metadataReceived,
                                direction: .received,
                                payloadSizeBytes: Int64(text.value.utf8.count),
                                details: ["metadataKeys": text.metadata.keys.sorted().joined(separator: ",")]
                            ))
                            self.diagnostics.record(TestDiagnosticRecord(
                                peerId: "\(session.peer.id)",
                                connectionId: self.diagnostics.connectionId(for: "\(session.peer.id)"),
                                category: "metadata",
                                eventName: TestDiagnosticEventName.metadataValidated,
                                direction: .received,
                                outcome: .success
                            ))
                            self.diag("ui", SampleConsole.received(
                                peerId: "\(session.peer.id)", isText: true, sizeBytes: Int64(text.value.utf8.count)
                            ))
                            self.appendMessage("\(session.peer.name) -> \(text.value)", kind: .received)
                        } else if let bin = msg as? P2pMessage.Binary {
                            self.appendMessage(
                                "\(session.peer.name) -> <binary \(bin.bytes.size) bytes>",
                                kind: .received
                            )
                        } else if msg != nil {
                            self.appendMessage("\(session.peer.name) -> <other message>", kind: .received)
                        }
                    }
                }
                _ = try? await session.incoming.collect(collector: collector)
            }

            fileCollectorTasks[sid] = Task {
                guard self.runLifecycle.acceptsWork(run), !Task.isCancelled else { return }
                let collector = FileOfferSnapshotCollector { offers in
                    await MainActor.run {
                        guard self.runLifecycle.acceptsWork(run) else { return }
                        self.reconcileIncomingOffers(offers, sessionId: sid)
                    }
                }
                _ = try? await session.pendingFileOffers.collect(collector: collector)
            }
        }
    }

    // MARK: - File transfer

    #if DEBUG
    /// Test input and observations only: the actual body and consent actions above render/handle the offer.
    @ViewBuilder
    private var consentFixtureControls: some View {
        Button("Inject synthetic pending offer") {
            runLifecycle.launchAction { run in await injectConsentFixture(run: run) }
        }
        .accessibilityIdentifier("ui-consent-fixture-inject")
        .disabled(runLifecycle.phase != .running || !pendingOffers.isEmpty || !transfers.isEmpty)
        Button("Remove synthetic offer snapshot") {
            runLifecycle.launchAction { run in
                _ = runLifecycle.withActiveRun(run) {
                    reconcileIncomingOffers([], sessionId: Self.consentFixtureSession)
                }
            }
        }
        .accessibilityIdentifier("ui-consent-fixture-empty")
        .disabled(runLifecycle.phase != .running)
        Text("accept=\(String(consentFixtureAccepts)) reject=\(String(consentFixtureRejects))")
            .accessibilityIdentifier("ui-consent-fixture-decisions")
        if let consentFixtureError {
            Text(consentFixtureError).accessibilityIdentifier("ui-consent-fixture-error")
        }
    }

    @MainActor
    private func injectConsentFixture(run: SampleRunLifecycle.Run) async {
        guard consentFixtureEnabled, runLifecycle.acceptsWork(run), runLifecycle.phase == .running,
              pendingOffers.isEmpty, transfers.isEmpty, (1...65_535).contains(localTcpPort),
              let kit, let qr = kit.localPairingQr,
              let fingerprint = kit.parsePeerPairingQr(value: qr) else { return }
        do {
            // Obtain a real Peer through the existing pinned registration API; never connect or send a file.
            let peer = try await kit.networkProvisioning.createManualPeer(
                host: "127.0.0.1", port: Int32(localTcpPort), expectedFingerprint: fingerprint
            )
            guard !Task.isCancelled else { return }
            _ = runLifecycle.withActiveRun(run) {
                guard pendingOffers.isEmpty, transfers.isEmpty else { return }
                consentFixtureError = nil
                let offer = UIConsentFixtureOffer(peer: peer) { accepted in
                    guard runLifecycle.owns(run) else { return }
                    if accepted { consentFixtureAccepts += 1 } else { consentFixtureRejects += 1 }
                }
                reconcileIncomingOffers([], sessionId: Self.consentFixtureSession)
                reconcileIncomingOffers([offer], sessionId: Self.consentFixtureSession)
            }
        } catch {
            guard !Task.isCancelled else { return }
            _ = runLifecycle.withActiveRun(run) {
                consentFixtureError = "Synthetic offer setup failed."
            }
        }
    }
    #endif

    /// AUDIT-2026-06 (D-G9-samples-desktop-ios-03 / A-G9-samples-desktop-ios-07):
    /// Queue an incoming offer until the user explicitly accepts or rejects it.
    /// The old auto-accept policy let an untrusted peer consume disk space
    /// without consent and bypassed quota/free-space checks.
    @MainActor
    private func reconcileIncomingOffers(_ offers: [P2pFileOffer], sessionId: String) {
        let previous = fileOfferIdsBySession[sessionId] ?? []
        let current = Set(offers.map(\.id))
        SessionTransferEntries.remove(
            sessionId: sessionId, transferIds: previous.subtracting(current), from: &pendingOffers
        )
        for offer in offers {
            if !previous.contains(offer.id) {
                diag(
                    "file",
                    "offer id=\(SampleConsole.identifier(offer.id)) size=\(offer.sizeBytes)"
                )
                self.diagnostics.transfer(
                    TestDiagnosticEventName.offerReceived,
                    peerId: "\(offer.peer.id)",
                    transferId: offer.id,
                    sessionId: sessionId,
                    state: "offered",
                    size: offer.sizeBytes,
                    direction: .received,
                    details: ["name": offer.name, "mimeType": offer.mimeType ?? "unknown"]
                )
                appendMessage("incoming file offer '\(offer.name)' — review to accept or reject", kind: .info)
            }
            let key = TransferKey(sessionId: sessionId, transferId: offer.id)
            pendingOffers[key] = PendingOffer(id: key, offer: offer)
        }
        fileOfferIdsBySession[sessionId] = current
    }

    @MainActor
    private func rejectIncomingOffer(_ pending: PendingOffer, run: SampleRunLifecycle.Run) async {
        guard runLifecycle.acceptsWork(run) else { return }
        guard let pending = SessionTransferEntries.take(pending.id, from: &pendingOffers) else { return }
        let offer = pending.offer
        let sessionId = pending.id.sessionId
        diagnostics.transfer(
            TestDiagnosticEventName.offerRejected,
            peerId: "\(offer.peer.id)",
            transferId: offer.id,
            sessionId: sessionId,
            state: "rejected",
            size: offer.sizeBytes,
            direction: .received,
            outcome: .cancellation,
            details: ["reason": "rejected by user"]
        )
        do {
            try await offer.reject(reason: "rejected by user")
        } catch {
            guard runLifecycle.acceptsWork(run) else { return }
            diag("file", "reject failed for selected file: \(SampleConsole.failure(error))")
        }
    }

    @MainActor
    private func prepareManagedStorage() {
        do {
            backupWarning = try SampleBackupPolicy.prepareAtStartup(
                inbox: { try SampleBackupPolicy.prepareDirectory(at: SampleBackupPolicy.inboxDirectory()) },
                evidence: { try diagnostics.prepareEvidenceStorage() }
            )
        } catch is CancellationError {
            // View/task cancellation is not an ordinary backup-policy failure.
        } catch {
            backupWarning = SampleBackupPolicy.startupWarning
        }
    }

    @MainActor
    private func acceptIncomingOffer(_ pending: PendingOffer, run: SampleRunLifecycle.Run) async {
        guard runLifecycle.acceptsWork(run) else { return }
        guard let pending = SessionTransferEntries.take(pending.id, from: &pendingOffers) else { return }
        let offer = pending.offer
        let maxBytes: Int64 = 50 * 1024 * 1024
        guard offer.sizeBytes >= 0 && offer.sizeBytes <= maxBytes else {
            appendMessage("file offer '\(offer.name)' rejected: exceeds 50 MiB sample quota", kind: .error)
            try? await offer.reject(reason: "receiver quota exceeded")
            return
        }
        let inbox = SampleBackupPolicy.inboxDirectory()
        do {
            try await SampleBackupPolicy.withPreparedDirectory(at: inbox) {
                await acceptPreparedIncomingOffer(pending, in: inbox, run: run)
            }
        } catch is CancellationError {
            // Do not present cancellation as an ordinary storage rejection.
        } catch {
            if runLifecycle.owns(run) {
                appendMessage("Cannot prepare inbox backup policy — rejecting selected file", kind: .error)
            }
            try? await offer.reject(reason: "receiver storage unavailable")
        }
    }

    @MainActor
    private func acceptPreparedIncomingOffer(
        _ pending: PendingOffer, in inbox: URL, run: SampleRunLifecycle.Run
    ) async {
        guard runLifecycle.acceptsWork(run) else {
            try? await pending.offer.reject(reason: "sample stopped before consent")
            return
        }
        let offer = pending.offer
        let sessionId = pending.id.sessionId
        let fm = FileManager.default
        do {
            if !cleanedTransferDirectories.contains(inbox.path) {
                try cleanupStaleTransferParts(in: inbox, fileManager: fm)
                cleanedTransferDirectories.insert(inbox.path)
            }
        } catch {
            appendMessage("file offer '\(offer.name)': cannot prepare inbox dir — rejecting", kind: .error)
            try? await offer.reject(reason: "receiver storage unavailable")
            return
        }
        let required = UInt64(max(0, offer.sizeBytes))
        let attrs = (try? fm.attributesOfFileSystem(forPath: inbox.path)) ?? [:]
        let free = (attrs[.systemFreeSize] as? NSNumber)?.uint64Value ?? 0
        guard free >= required + 1_048_576 else {
            appendMessage("file offer '\(offer.name)' rejected: insufficient free space", kind: .error)
            try? await offer.reject(reason: "receiver free space is insufficient")
            return
        }
        guard let dest = claimUniqueDestination(in: inbox, rawName: offer.name, fileManager: fm) else {
            appendMessage("file offer '\(offer.name)': cannot claim destination — rejecting", kind: .error)
            try? await offer.reject(reason: "receiver could not open destination")
            return
        }
        let destination: AtomicFileTransferDestination
        do {
            destination = try AtomicFileTransferDestination(target: dest)
        } catch {
            try? fm.removeItem(at: dest)
            appendMessage("file offer '\(offer.name)': cannot prepare destination — rejecting", kind: .error)
            try? await offer.reject(reason: "receiver could not prepare destination")
            return
        }
        diagnostics.record(TestDiagnosticRecord(
            peerId: "\(offer.peer.id)",
            connectionId: diagnostics.transferConnectionId(
                peerId: "\(offer.peer.id)", sessionId: sessionId, transferId: offer.id
            ),
            sdkSessionId: sessionId,
            transferId: offer.id,
            category: "storage",
            eventName: TestDiagnosticEventName.temporaryFileCreated,
            currentState: "prepared",
            direction: .received,
            details: ["location": "app-private", "contentsExported": "false"]
        ))
        do {
            let transfer = try await offer.accept(destination: destination)
            guard runLifecycle.acceptsWork(run), !Task.isCancelled else {
                try? await transfer.cancel(reason: "sample stopped")
                return
            }
            diagnostics.transfer(
                TestDiagnosticEventName.offerAccepted,
                peerId: "\(offer.peer.id)",
                transferId: transfer.id,
                sessionId: sessionId,
                state: "accepted",
                size: offer.sizeBytes,
                direction: .received
            )
            appendMessage(
                "receiving '\(dest.lastPathComponent)' (\(fmtBytes(offer.sizeBytes))) from \(offer.peer.name)",
                kind: .info
            )
            watchTransfer(
                transfer, sessionId: sessionId, direction: .receive, detail: dest.lastPathComponent, run: run
            ) { completed in
                let cleanupComplete = !destination.temporaryArtifactExists
                self.diagnostics.record(TestDiagnosticRecord(
                    peerId: "\(offer.peer.id)",
                    connectionId: self.diagnostics.transferConnectionId(
                        peerId: "\(offer.peer.id)", sessionId: sessionId, transferId: transfer.id
                    ),
                    sdkSessionId: sessionId,
                    transferId: transfer.id,
                    category: "storage",
                    eventName: TestDiagnosticEventName.temporaryFileCleaned,
                    severity: cleanupComplete ? .info : .error,
                    currentState: cleanupComplete
                        ? (completed ? "promoted" : "aborted")
                        : "cleanup-failed",
                    direction: .received,
                    errorCode: cleanupComplete ? nil : "TEMPORARY_FILE_RETAINED",
                    errorDescription: cleanupComplete ? nil : "temporary transfer file remains",
                    outcome: cleanupComplete ? .success : .failure,
                    details: ["location": "app-private", "contentsExported": "false"]
                ))
                guard cleanupComplete else { return "temporary cleanup incomplete" }
                guard completed else { return nil }
                do {
                    let digest = try sha256File(at: dest)
                    diagnostics.fileHash(
                        peerId: "\(offer.peer.id)",
                        transferId: transfer.id,
                        size: offer.sizeBytes,
                        digest: digest,
                        receiver: true,
                        sessionId: sessionId
                    )
                    diagnostics.transfer(
                        TestDiagnosticEventName.transferDurableCommitted,
                        peerId: "\(offer.peer.id)",
                        transferId: transfer.id,
                        sessionId: sessionId,
                        state: "durably-persisted",
                        size: offer.sizeBytes,
                        direction: .received,
                        outcome: .success
                    )
                    diag("file", "durable receive committed sha256=\(digest)")
                    appendMessage("sha256 \(dest.lastPathComponent): \(digest)", kind: .info)
                } catch {
                    diag("file", "sha256 read failed for selected file: \(SampleConsole.failure(error))")
                    appendMessage(
                        "sha256 unavailable for \(dest.lastPathComponent): \(error.localizedDescription)",
                        kind: .error
                    )
                }
                return nil
            }
        } catch {
            // The SDK owns the destination only after it wins the retained
            // offer's acceptance transition. Abort defensively on every
            // thrown accept so a pre-transition refusal cannot leave the
            // sample's reservation or temporary file behind.
            let cleanupError = await abortDestination(destination)
            guard runLifecycle.owns(run) else { return }
            if let cleanupError {
                diag(
                    "file",
                    "destination cleanup after failed accept also failed: " +
                        SampleConsole.failure(cleanupError)
                )
            }
            let cleanupComplete = !destination.temporaryArtifactExists
            diagnostics.record(TestDiagnosticRecord(
                peerId: "\(offer.peer.id)",
                connectionId: diagnostics.transferConnectionId(
                    peerId: "\(offer.peer.id)", sessionId: sessionId, transferId: offer.id
                ),
                sdkSessionId: sessionId,
                transferId: offer.id,
                category: "storage",
                eventName: TestDiagnosticEventName.temporaryFileCleaned,
                severity: cleanupComplete ? .info : .error,
                currentState: cleanupComplete ? "aborted" : "cleanup-failed",
                direction: .received,
                errorCode: cleanupComplete ? nil : "TEMPORARY_FILE_RETAINED",
                errorDescription: cleanupComplete ? nil : "temporary transfer file remains",
                outcome: cleanupComplete ? .success : .failure,
                details: ["location": "app-private", "contentsExported": "false"]
            ))
            diagnostics.transfer(
                TestDiagnosticEventName.transferFailed,
                peerId: "\(offer.peer.id)",
                transferId: offer.id,
                sessionId: sessionId,
                state: "failed",
                size: offer.sizeBytes,
                direction: .received,
                outcome: .failure,
                error: error.localizedDescription
            )
            diag("file", "accept THREW for selected file: \(SampleConsole.failure(error))")
            appendMessage("accept failed for '\(offer.name)': \(error.localizedDescription)", kind: .error)
        }
    }

    /// AUDIT-2026-06 (D-G9-samples-desktop-ios-03): demonstrate the outgoing
    /// file path. Generates a deterministic 200 KB blob in memory (the
    /// README's "200KB binary preset") and streams it through
    /// the prepared SHA-256 `sendFile(name:mimeType:source:)` API —
    /// no document picker needed, so the flow is one tap on the test bench.
    @MainActor
    private func sendTestFile(
        to row: SessionRow, preset: TestFilePreset = .small, run: SampleRunLifecycle.Run
    ) async {
        guard runLifecycle.acceptsWork(run) else { return }
        guard !sendingFileSessionIds.contains(row.id) else { return }
        sendingFileSessionIds.insert(row.id)
        defer {
            if runLifecycle.owns(run) { sendingFileSessionIds.remove(row.id) }
        }

        let size = preset.byteCount
        var data = Data(count: size)
        for i in 0..<size {
            data[i] = UInt8(truncatingIfNeeded: i &* 31 &+ 7)   // deterministic pattern
        }
        let name = "ios-test-\(preset.rawValue.replacingOccurrences(of: " ", with: "-"))-\(Int(Date().timeIntervalSince1970)).bin"
        let source = PreparedDataSource(data: data)
        let digest = source.sha256Hex
        diagnostics.record(TestDiagnosticRecord(
            peerId: row.peerId,
            connectionId: diagnostics.connectionId(for: row.peerId),
            category: "file",
            eventName: TestDiagnosticEventName.fileGenerated,
            direction: .sent,
            payloadSizeBytes: Int64(size),
            details: ["name": name, "preset": preset.rawValue]
        ))
        diag("file", "sendFile (\(size) B) sha256=\(digest) -> \(SampleConsole.identifier(row.peerId))")
        appendMessage("prepared \(name): sha256 \(digest)", kind: .info)
        do {
            let transfer = try await row.session.sendFile(
                name: name,
                mimeType: "application/octet-stream",
                source: source
            )
            guard runLifecycle.acceptsWork(run), !Task.isCancelled else {
                try? await transfer.cancel(reason: "sample stopped")
                return
            }
            diagnostics.transfer(
                TestDiagnosticEventName.transferPrepared,
                peerId: row.peerId,
                transferId: transfer.id,
                sessionId: row.id,
                state: "prepared",
                size: Int64(size),
                direction: .sent,
                details: ["name": name, "mimeType": "application/octet-stream"]
            )
            diagnostics.transfer(
                TestDiagnosticEventName.transferStarted,
                peerId: row.peerId,
                transferId: transfer.id,
                sessionId: row.id,
                state: "started",
                size: Int64(size),
                direction: .sent
            )
            diagnostics.fileHash(
                peerId: row.peerId,
                transferId: transfer.id,
                size: Int64(size),
                digest: digest,
                receiver: false,
                sessionId: row.id
            )
            appendMessage("offering file '\(name)' (\(fmtBytes(Int64(size)))) to \(row.peerName)", kind: .sent)
            watchTransfer(transfer, sessionId: row.id, direction: .send, detail: nil, run: run) { completed in
                if completed {
                    diag("file", "sender completed sha256=\(digest)")
                }
                return nil
            }
        } catch {
            guard runLifecycle.acceptsWork(run) else { return }
            diagnostics.transfer(
                TestDiagnosticEventName.transferFailed,
                peerId: row.peerId,
                // sendFile failed before returning an SDK transfer handle, so
                // there is no truthful transfer id to correlate here.
                transferId: nil,
                sessionId: row.id,
                state: "failed",
                size: Int64(size),
                direction: .sent,
                outcome: .failure,
                error: error.localizedDescription
            )
            diag("file", "sendFile THREW for \(SampleConsole.identifier(row.peerId)): \(SampleConsole.failure(error))")
            appendMessage("sendFile failed (\(row.peerName)): \(error.localizedDescription)", kind: .error)
            errorBanner = "Send file to \(row.peerName) failed: \(error.localizedDescription)"
        }
    }

    /// Track one transfer's StateFlows into a UI row until it reaches a
    /// terminal state, then run the sample's UI-only `onTerminal` hook. Secure
    /// source/destination resources are terminalized by the SDK. Polled at 5 Hz rather than collected —
    /// `StateFlow<T>.value` generic-erases to `Any?` across the bridge
    /// (see IosSwiftHelpers.kt), so we cast per read; a poll loop that exits
    /// on terminal/cancel is simpler and self-cleaning compared to two more
    /// never-completing flow collects per transfer.
    @MainActor
    private func watchTransfer(
        _ transfer: P2pFileTransfer,
        sessionId: String,
        direction: TransferRow.Direction,
        detail: String?,
        run: SampleRunLifecycle.Run,
        onTerminal: @escaping (_ completed: Bool) -> String?
    ) {
        guard runLifecycle.acceptsWork(run) else { return }
        let key = TransferKey(sessionId: sessionId, transferId: transfer.id)
        transfers.append(TransferRow(
            id: key,
            peerName: transfer.peer.name,
            fileName: transfer.name,
            direction: direction,
            stateLabel: "Offered",
            bytes: 0,
            totalBytes: transfer.sizeBytes,
            isTerminal: false,
            detail: detail,
            transfer: transfer
        ))
        SessionTransferEntries.trimTerminalHistory(in: &transfers) { $0.isTerminal }
        transferWatchTasks[key] = Task { @MainActor in
            var lastLabel = ""
            var cleanupCompleted = false
            while !Task.isCancelled && self.runLifecycle.owns(run) {
                let (label, terminal) = describeTransferState(transfer.state.value)
                let bytes = (transfer.bytesTransferred.value as? KotlinLong)?.int64Value ?? 0
                SessionTransferEntries.update(key, in: &transfers) { row in
                    row.stateLabel = label
                    row.bytes = bytes
                    row.isTerminal = terminal
                }
                if label != lastLabel {
                    lastLabel = label
                    diag(
                        "file",
                        "transfer \(SampleConsole.identifier(transfer.id)) -> \(SampleConsole.transferState(label)) " +
                            "(\(bytes)/\(transfer.sizeBytes) B)"
                    )
                    self.diagnostics.transferProgress(
                        peerId: "\(transfer.peer.id)",
                        transferId: transfer.id,
                        sessionId: sessionId,
                        bytes: bytes,
                        total: transfer.sizeBytes
                    )
                    if terminal {
                        self.diagnostics.transfer(
                            label == "Completed"
                                ? TestDiagnosticEventName.transferCompleted
                                : (label.hasPrefix("Cancelled")
                                    ? TestDiagnosticEventName.transferCancelled
                                    : TestDiagnosticEventName.transferFailed),
                            peerId: "\(transfer.peer.id)",
                            transferId: transfer.id,
                            sessionId: sessionId,
                            state: label,
                            size: transfer.sizeBytes,
                            direction: direction == .send ? .sent : .received,
                            outcome: label == "Completed"
                                ? .success
                                : (label.hasPrefix("Cancelled") ? .cancellation : .failure),
                            error: label == "Completed" ? nil : label
                        )
                        let localFailure = onTerminal(label == "Completed")
                        cleanupCompleted = true
                        let finalLabel = localFailure.map { "Failed: \($0)" } ?? label
                        SessionTransferEntries.update(key, in: &transfers) { $0.stateLabel = finalLabel }
                        let arrow = direction == .send ? "→" : "←"
                        appendMessage(
                            "file '\(transfer.name)' \(arrow) \(transfer.peer.name): \(finalLabel)",
                            kind: finalLabel == "Completed" ? .info : .error
                        )
                    }
                }
                if terminal {
                    SessionTransferEntries.trimTerminalHistory(in: &transfers) { $0.isTerminal }
                    break
                }
                try? await Task.sleep(nanoseconds: 200_000_000)
            }
            // onTerminal is UI/diagnostics only; SDK source/destination cleanup
            // already ran before Stop retires watchers. Never publish into B.
            if !cleanupCompleted && self.runLifecycle.owns(run) {
                let localFailure = onTerminal(false)
                if let localFailure {
                    let arrow = direction == .send ? "→" : "←"
                    appendMessage(
                        "file '\(transfer.name)' \(arrow) \(transfer.peer.name): Failed: \(localFailure)",
                        kind: .error
                    )
                }
            }
            if self.runLifecycle.owns(run) { transferWatchTasks[key] = nil }
        }
    }

    /// Map the bridged `FileTransferState` (arrives as `Any?` because
    /// `StateFlow`'s generic argument erases) to a UI label + terminal flag.
    private func describeTransferState(_ value: Any?) -> (label: String, terminal: Bool) {
        switch value {
        case is FileTransferState.Offered:
            return ("Offered", false)
        case is FileTransferState.Accepted:
            return ("Accepted", false)
        case let s as FileTransferState.Sending:
            return ("Sending \(Int(s.progress * 100))%", false)
        case is FileTransferState.Completed:
            return ("Completed", true)
        case let s as FileTransferState.Rejected:
            return ("Rejected" + (s.reason.map { ": \($0)" } ?? ""), true)
        case let s as FileTransferState.Cancelled:
            return ("Cancelled" + (s.reason.map { ": \($0)" } ?? ""), true)
        case let s as FileTransferState.Failed:
            // This value is already typed; only a caught Swift Error needs NSError recovery.
            return ("Failed: \(SampleP2pError.userMessage(s.error))", true)
        default:
            // Unknown future SDK states must not leave a transfer watcher
            // suspended forever with an open destination.
            return ("Failed: unknown transfer state", true)
        }
    }

    @MainActor
    private func cancelTransfer(_ row: TransferRow, run: SampleRunLifecycle.Run) async {
        guard runLifecycle.acceptsWork(run) else { return }
        guard let row = SessionTransferEntries.row(row.id, in: transfers) else { return }
        diag("file", "Cancel tapped for transfer \(SampleConsole.identifier(row.id.transferId))")
        diagnostics.transfer(
            TestDiagnosticEventName.transferCancelled,
            peerId: "\(row.transfer.peer.id)",
            transferId: row.id.transferId,
            sessionId: row.id.sessionId,
            state: "cancelling",
            size: row.totalBytes,
            direction: row.direction == .send ? .sent : .received,
            outcome: .cancellation
        )
        do {
            try await row.transfer.cancel(reason: "cancelled from iOS sample UI")
        } catch {
            guard runLifecycle.acceptsWork(run) else { return }
            appendMessage("cancel failed (\(row.fileName)): \(error.localizedDescription)", kind: .error)
        }
    }

    @MainActor
    private func connect(_ row: PeerRow, run: SampleRunLifecycle.Run) async {
        guard runLifecycle.acceptsWork(run) else { return }
        diag("ui", "Connect tapped: peer=\(SampleConsole.identifier(row.id))")
        diagnostics.record(TestDiagnosticRecord(
            peerId: row.id,
            category: "connection",
            eventName: TestDiagnosticEventName.connectionAttempted,
            currentState: "connecting"
        ))
        guard let k = kit else {
            diag("ui", "Connect ABORT — kit not started")
            errorBanner = "Kit not started."
            return
        }
        guard !isStopping else {
            diag("ui", "Connect ignored — kit is stopping")
            return
        }
        let pid = row.id
        guard !pendingConnectPeerIds.contains(pid) else {
            diag("ui", "Connect dedup — pendingConnectPeerIds already has \(SampleConsole.identifier(pid))")
            appendMessage("connect already in progress for \(row.name)", kind: .info)
            return
        }
        if let existing = sessions.first(where: { $0.peerId == pid && $0.isLive }) {
            diag("ui", "Connect dedup — session already \(existing.state) for \(SampleConsole.identifier(pid))")
            appendMessage(
                "already \(existing.state.lowercased()) with \(row.name); skipping duplicate connect",
                kind: .info
            )
            return
        }
        pendingConnectPeerIds.insert(pid)
        // AUDIT-2026-06 (B-G9-samples-desktop-ios-03): this defer now runs as
        // soon as connect() finishes the handshake — attachCollectors returns
        // immediately instead of awaiting a never-completing SharedFlow
        // collect, so the Connect button no longer wedges on "Connecting…"
        // after the session later dies.
        defer {
            if runLifecycle.owns(run) { pendingConnectPeerIds.remove(pid) }
        }

        diag("ui", "calling kit.connect(\(SampleConsole.identifier(pid)))")
        appendMessage("connect -> \(row.name)", kind: .info)
        do {
            let session = try await k.connect(peer: row.peer)
            guard runLifecycle.acceptsWork(run), !Task.isCancelled else {
                try? await session.close()
                return
            }
            diag(
                "ui",
                "kit.connect returned session id=\(SampleConsole.identifier(session.id)) " +
                    "peer=\(SampleConsole.identifier("\(session.peer.id)")) " +
                    "state=\(IosSwiftHelpersKt.stateName(session))"
            )
            attachCollectors(to: session, label: "outgoing", run: run)
        } catch {
            guard runLifecycle.acceptsWork(run) else { return }
            if Task.isCancelled || error is CancellationError { return }
            let typed = SampleP2pError.recover(error)
            let detail: String
            if let typed {
                // Keep the original SDK object; subtype fields, not localized text,
                // determine the hint. The sample never retries or changes a pin here.
                detail = SampleP2pError.userMessage(typed)
            } else {
                detail = error.localizedDescription
            }
            diagnostics.record(TestDiagnosticRecord(
                peerId: row.id,
                category: "connection",
                eventName: SampleP2pError.isSecurityRejection(typed)
                    ? TestDiagnosticEventName.connectionAuthenticationFailed
                    : TestDiagnosticEventName.connectionStateChanged,
                severity: .error,
                currentState: "failed",
                errorCode: "CONNECT_FAILED",
                errorDescription: detail,
                outcome: .failure
            ))
            diag("ui", "kit.connect THREW: \(SampleConsole.failure(error))")
            appendMessage("connect failed (\(row.name)): \(detail)", kind: .error)
            errorBanner = "Connect to \(row.name) failed: \(detail)"
        }
    }

    @MainActor
    private func dialManual(run: SampleRunLifecycle.Run) async {
        guard runLifecycle.acceptsWork(run) else { return }
        diag("ui", "Dial manual tapped")
        guard let k = kit else {
            diag("ui", "Dial ABORT — kit not started")
            errorBanner = "Kit not started."
            return
        }
        guard !isStopping else { diag("ui", "Dial ignored — stopping"); return }
        guard !isManualDialing else { diag("ui", "Dial dedup — already dialing"); return }

        let host = manualHost.trimmingCharacters(in: .whitespacesAndNewlines)
        let portStr = manualPort.trimmingCharacters(in: .whitespacesAndNewlines)
        let pairingQr = manualPairingQr.trimmingCharacters(in: .whitespacesAndNewlines)

        guard !host.isEmpty else {
            diag("ui", "Dial ABORT — empty host")
            errorBanner = "Manual host cannot be empty."
            return
        }
        guard let portInt = Int32(portStr) else {
            diag("ui", "Dial ABORT — port not int:")
            errorBanner = "Port must be a positive integer (got '\(portStr)')."
            return
        }
        guard (1...65535).contains(portInt) else {
            diag("ui", "Dial ABORT — port out of range: \(portInt)")
            errorBanner = "Port must be between 1 and 65535 (got \(portInt))."
            return
        }
        let allowed = CharacterSet(charactersIn:
            "0123456789.:-_abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
        )
        guard host.unicodeScalars.allSatisfy({ allowed.contains($0) }) else {
            diag("ui", "Dial ABORT — invalid chars in host:")
            errorBanner = "Host contains invalid characters."
            return
        }
        guard let expectedFingerprint = k.parsePeerPairingQr(value: pairingQr) else {
            diag("ui", "Dial ABORT — invalid or other-AppId pairing QR")
            errorBanner = "Enter the peer's full pairing QR text for this AppId."
            return
        }

        isManualDialing = true
        // AUDIT-2026-06 (B-G9-samples-desktop-ios-03): with attachCollectors
        // returning immediately, this defer runs when the dial settles —
        // isManualDialing no longer latches true forever after one dial.
        defer {
            if runLifecycle.owns(run) { isManualDialing = false }
        }
        errorBanner = nil
        appendMessage("manual: createManualPeer host=\(host) port=\(portInt)", kind: .info)
        diag("ui", "calling networkProvisioning.createManualPeer(<omitted>:\(portInt))")
        do {
            let peer = try await k.networkProvisioning.createManualPeer(
                host: host,
                port: portInt,
                expectedFingerprint: expectedFingerprint
            )
            guard runLifecycle.acceptsWork(run), !Task.isCancelled else { return }
            diag("ui", "createManualPeer returned: id=\(SampleConsole.identifier("\(peer.id)"))")
            appendMessage("manual: created \(peer.name) (\(peer.id))", kind: .info)
            diag("ui", "calling kit.connect on synthetic peer \(SampleConsole.identifier("\(peer.id)"))")
            let session = try await k.connect(peer: peer)
            guard runLifecycle.acceptsWork(run), !Task.isCancelled else {
                try? await session.close()
                return
            }
            diag(
                "ui",
                "kit.connect (manual) returned session id=\(SampleConsole.identifier(session.id)) " +
                    "state=\(IosSwiftHelpersKt.stateName(session))"
            )
            attachCollectors(to: session, label: "manual", run: run)
        } catch {
            guard runLifecycle.acceptsWork(run) else { return }
            if Task.isCancelled || error is CancellationError { return }
            let detail = SampleP2pError.userMessage(error)
            diag("ui", "manual dial THREW: \(SampleConsole.failure(error))")
            appendMessage("manual: failed - \(detail)", kind: .error)
            errorBanner = "Manual connect failed: \(detail)"
        }
    }

    @MainActor
    private func sendAll(run: SampleRunLifecycle.Run) async {
        guard runLifecycle.acceptsWork(run) else { return }
        diag("ui", "Send All tapped: draft=\(draft.count) chars uiSessions=\(sessions.count)")
        let text = draft.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !text.isEmpty else {
            diag("ui", "Send ABORT — message empty after trim")
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
                let st = IosSwiftHelpersKt.stateName(s)
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
        diag("ui", "Send live snapshot: \(liveSessions.count) Connected session(s)")
        guard !liveSessions.isEmpty else {
            diag("ui", "Send ABORT — no Connected sessions (uiSessions=\(sessions.count))")
            errorBanner = "No Connected sessions right now. Sessions exist " +
                "(\(sessions.count)) but none are in the Connected state."
            return
        }

        var successes = 0
        var failures: [String] = []
        for row in liveSessions {
            guard runLifecycle.acceptsWork(run), !Task.isCancelled else { return }
            diag("ui", SampleConsole.sendingText(recipients: 1, sizeBytes: text.utf8.count))
            do {
                diagnostics.record(TestDiagnosticRecord(
                    peerId: row.peerId,
                    connectionId: diagnostics.connectionId(for: row.peerId),
                    category: "metadata",
                    eventName: TestDiagnosticEventName.metadataCreated,
                    direction: .sent,
                    payloadSizeBytes: Int64(text.utf8.count),
                    details: ["metadataKeys": ""]
                ))
                try await row.session.send(message: P2pMessage.Text(value: text, metadata: [:]))
                guard runLifecycle.acceptsWork(run), !Task.isCancelled else { return }
                diagnostics.record(TestDiagnosticRecord(
                    peerId: row.peerId,
                    connectionId: diagnostics.connectionId(for: row.peerId),
                    category: "metadata",
                    eventName: TestDiagnosticEventName.metadataSent,
                    direction: .sent,
                    payloadSizeBytes: Int64(text.utf8.count),
                    outcome: .success
                ))
                diag("ui", "session.send OK for \(SampleConsole.identifier(row.peerId))")
                appendMessage("me -> \(row.peerName): \(text)", kind: .sent)
                successes += 1
            } catch {
                guard runLifecycle.acceptsWork(run) else { return }
                let msg = error.localizedDescription
                diag("ui", "session.send THREW for \(SampleConsole.identifier(row.peerId)): \(SampleConsole.failure(error))")
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
        // AUDIT-2026-06 (D-G9-samples-desktop-ios-11): keep the draft when
        // every send failed — clearing it forced the operator to retype the
        // message after a transient failure.
        if successes > 0 {
            draft = ""
        }
    }

    @MainActor
    private func closeSession(_ row: SessionRow, run: SampleRunLifecycle.Run) async {
        guard runLifecycle.acceptsWork(run) else { return }
        diag("ui", "Close tapped: session=\(SampleConsole.identifier(row.id)) peer=\(SampleConsole.identifier(row.peerId))")
        do {
            try await row.session.close()
            guard runLifecycle.acceptsWork(run) else { return }
            diag("ui", "session.close OK for \(SampleConsole.identifier(row.peerId))")
            appendMessage("closed session with \(row.peerName)", kind: .info)
        } catch {
            guard runLifecycle.acceptsWork(run) else { return }
            diag("ui", "session.close THREW for \(SampleConsole.identifier(row.peerId)): \(SampleConsole.failure(error))")
            appendMessage("close failed (\(row.peerName)): \(error.localizedDescription)", kind: .error)
        }
    }

    @MainActor
    private func stop(run: SampleRunLifecycle.Run) async {
        guard runLifecycle.owns(run) else { return }
        diag("ui", "Stop tapped")
        guard let k = kit, runLifecycle.owns(run), !isStopping else {
            diag("ui", "Stop ignored — kit=\(kit != nil) isStopping=\(isStopping)")
            return
        }
        await runLifecycle.stop(
            run,
            cancelObservers: {
                status = "Stopping..."
                diagnostics.record(TestDiagnosticRecord(
                    category: "discovery",
                    eventName: TestDiagnosticEventName.discoveryStopped,
                    currentState: "stopping"
                ))
                cancelRunObservers()
            },
            operation: {
                let offers = Array(pendingOffers.values)
                for pending in offers {
                    try? await pending.offer.reject(reason: "sample stopped before consent")
                }
                try await k.stop()
            },
            succeeded: {
                retireStoppedRun()
                errorBanner = nil
                status = "Stopped"
                diagnostics.record(TestDiagnosticRecord(
                    category: "application",
                    eventName: TestDiagnosticEventName.applicationShutdown,
                    currentState: "stopped",
                    outcome: .success
                ))
            },
            failed: { error in
                appendMessage("stop error: \(error.localizedDescription)", kind: .error)
                errorBanner = "Stop failed: \(error.localizedDescription)"
                status = "Stop failed — retry Stop"
                // The coordinator retains this owner and the captured SDK kit.
            }
        )
    }

    @MainActor
    private func retireStoppedRun() {
        // The SDK quiesces its writers before watcher retirement. Never
        // replace this real cleanup with a run-token-only UI reset.
        transferWatchTasks.values.forEach { $0.cancel() }
        transferWatchTasks = [:]
        diagnostics.setLocalPeerId(nil)
        kit = nil
        peers = []
        sessions = []
        transfers = []
        pendingOffers = [:]
        collectedSessionIds = []
        pendingConnectPeerIds = []
        sendingFileSessionIds = []
        isManualDialing = false
        localPeerId = ""
        localTcpPort = 0
    }

    @MainActor
    private func cancelRunObservers() {
        pollTask?.cancel()
        pollTask = nil
        incomingSessionsTask?.cancel()
        incomingSessionsTask = nil
        permissionCheckTask?.cancel()
        permissionCheckTask = nil
        messageCollectorTasks.values.forEach { $0.cancel() }
        fileCollectorTasks.values.forEach { $0.cancel() }
        messageCollectorTasks = [:]
        fileCollectorTasks = [:]
        fileOfferIdsBySession = [:]
    }

    // MARK: - Helpers

    @MainActor
    private func appendMessage(_ text: String, kind: MessageRow.Kind) {
        messages.append(MessageRow(text: text, kind: kind))
        while messages.count > 200 ||
                messages.reduce(0, { $0 + $1.text.utf8.count }) > Self.messageByteCapacity {
            guard !messages.isEmpty else { break }
            messages.removeFirst()
        }
    }

    /// AUDIT-2026-06 (B-G9-samples-desktop-ios-06): append with a stable,
    /// monotonically increasing id so trimming doesn't shift row identities.
    @MainActor
    private func appendLog(_ text: String) {
        logLines.append(LogLine(id: nextLogId, text: text))
        nextLogId += 1
        if logLines.count > 200 {
            logLines.removeFirst(logLines.count - 200)
        }
    }

    /// Only fixed labels, counts, SDK states and SampleConsole fields belong here.
    /// Never interpolate names, payloads, paths, addresses or error descriptions.
    /// Push a Swift-side diagnostic line into the same `IosLanDebug`
    /// timeline that the Kotlin LAN transport writes to. Lets the on-screen
    /// log show "user tapped Send" interleaved with "nw_connection_send
    /// completed OK" so we can confirm UI ↔ SDK alignment.
    private func diag(_ tag: String, _ message: String) {
        diagnostics.recordLegacy(tag: tag, message: message)
        IosLanDebug.shared.log(tag: tag, message: message)
    }
}

// MARK: - FlowCollector adapters

#if DEBUG
/// A UI-only offer input, not an SDK/transport simulator. Never writes or claims successful acceptance.
private final class UIConsentFixtureOffer: NSObject, P2pFileOffer {
    let id = "11111111111111111111111111111111"
    let peer: Peer
    let name = "synthetic-consent.bin"
    let sizeBytes: Int64 = 16
    let mimeType: String? = "application/octet-stream"
    private let onDecision: @MainActor (Bool) -> Void

    init(peer: Peer, onDecision: @escaping @MainActor (Bool) -> Void) {
        self.peer = peer
        self.onDecision = onDecision
    }

    func accept(sink: Kotlinx_io_coreRawSink, completionHandler: @escaping (P2pFileTransfer?, Error?) -> Void) {
        recordUnexpectedAccept(completionHandler)
    }

    func accept(
        destination: FileTransferDestination,
        completionHandler: @escaping (P2pFileTransfer?, Error?) -> Void
    ) {
        recordUnexpectedAccept(completionHandler)
    }

    func reject(reason: String?, completionHandler: @escaping (Error?) -> Void) {
        Task { @MainActor in
            self.onDecision(false)
            completionHandler(nil)
        }
    }

    private func recordUnexpectedAccept(_ completion: @escaping (P2pFileTransfer?, Error?) -> Void) {
        Task { @MainActor in
            self.onDecision(true)
            completion(nil, NSError(domain: "P2pKitSample.UIConsentFixture", code: 1))
        }
    }
}
#endif

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

/// Swift adapter for retained `List<P2pFileOffer>` StateFlow snapshots.
final class FileOfferSnapshotCollector: NSObject, Kotlinx_coroutines_coreFlowCollector {
    private let onOffers: ([P2pFileOffer]) async -> Void
    init(_ onOffers: @escaping ([P2pFileOffer]) async -> Void) {
        self.onOffers = onOffers
    }
    func emit(value: Any?, completionHandler: @escaping (Error?) -> Void) {
        if let offers = value as? [P2pFileOffer] {
            Task {
                await onOffers(offers)
                completionHandler(nil)
            }
        } else if let values = value as? NSArray {
            let offers = values.compactMap { $0 as? P2pFileOffer }
            Task {
                await onOffers(offers)
                completionHandler(nil)
            }
        } else {
            completionHandler(
                NSError(
                    domain: "dev.p2pkit.sample.file",
                    code: 4,
                    userInfo: [NSLocalizedDescriptionKey: "pendingFileOffers emitted a non-list value"]
                )
            )
        }
    }
}

// MARK: - kotlinx-io adapters
//
// Secure-v2 prepares a repeatable `RawSource` plus SHA-256 and receives into a
// transactional destination backed by a `RawSink`. kotlinx-io is not
// export()-ed into the XCFramework,
// so its interfaces surface in Swift with the `Kotlinx_io_core` prefix —
// they are plain (non-suspend) protocols, implementable from Swift. Bytes
// cross the bridge through `KotlinByteArray`, element-by-element via
// get/set — a sample-grade simplification (~tens of ms per MiB), fine for
// the 200 KB preset and multi-MiB test files.

/// Immutable prepared snapshot used by the secure-v2 send API. `open()`
/// returns a fresh source only after the peer accepts the offer.
final class PreparedDataSource: NSObject, PreparedFileSource {
    private let data: Data
    let sizeBytes: Int64
    let sha256: Sha256Digest
    let sha256Hex: String

    init(data: Data) {
        self.data = data
        self.sizeBytes = Int64(data.count)
        let digest = Array(CryptoKit.SHA256.hash(data: data))
        self.sha256Hex = digest.map { String(format: "%02x", $0) }.joined()
        let bytes = KotlinByteArray(size: Int32(digest.count))
        for (index, byte) in digest.enumerated() {
            bytes.set(index: Int32(index), value: Int8(bitPattern: byte))
        }
        self.sha256 = Sha256Digest(bytes: bytes)
    }

    func open() -> Kotlinx_io_coreRawSource {
        DataRawSource(data: data)
    }
}

/// `kotlinx.io.RawSource` over one immutable in-memory snapshot. The SDK pulls
/// chunks sequentially from a background dispatcher, so no locking is needed.
final class DataRawSource: NSObject, Kotlinx_io_coreRawSource {
    private let data: Data
    private var offset: Int = 0
    init(data: Data) {
        self.data = data
    }

    func readAtMostTo(sink: Kotlinx_io_coreBuffer, byteCount: Int64) -> Int64 {
        if offset >= data.count { return -1 }      // exhausted, per RawSource contract
        if byteCount <= 0 { return 0 }
        let n = Int(min(byteCount, Int64(data.count - offset)))
        let arr = KotlinByteArray(size: Int32(n))
        for i in 0..<n {
            arr.set(index: Int32(i), value: Int8(bitPattern: data[offset + i]))
        }
        sink.write(source: arr, startIndex: 0, endIndex: Int32(n))
        offset += n
        return Int64(n)
    }

    func close() {
        // Nothing to release; kept for the RawSource (AutoCloseable) contract.
    }
}

/// `kotlinx.io.RawSink` writing to a local file via `FileHandle`. The durable
/// destination below owns and terminalizes it.
final class FileHandleRawSink: NSObject, Kotlinx_io_coreRawSink {
    private let handle: FileHandle
    private let stateLock = NSLock()
    private var closed = false
    /// RawSink.write cannot throw across the ObjC bridge (no NSError slot in
    /// the kotlinx-io interface), so disk-write failures are remembered,
    /// surfaced by the transfer watcher, and subsequent writes become no-ops.
    private var failed = false
    private var failure: String?

    var failureDescription: String? {
        stateLock.lock()
        defer { stateLock.unlock() }
        return failure
    }

    init(handle: FileHandle) {
        self.handle = handle
    }

    func write(source: Kotlinx_io_coreBuffer, byteCount: Int64) {
        var remaining = byteCount
        while remaining > 0 {
            stateLock.lock()
            let shouldStop = failed || closed
            stateLock.unlock()
            if shouldStop { break }
            let chunk = Int32(min(remaining, 64 * 1024))
            let arr = KotlinByteArray(size: chunk)
            let read = source.readAtMostTo(sink: arr, startIndex: 0, endIndex: chunk)
            if read <= 0 { break }                 // buffer exhausted early
            var data = Data(count: Int(read))
            for i in 0..<Int(read) {
                data[i] = UInt8(bitPattern: arr.get(index: Int32(i)))
            }
            stateLock.lock()
            do {
                if !failed && !closed {
                    try handle.write(contentsOf: data)
                }
            } catch {
                failed = true
                failure = error.localizedDescription
                IosLanDebug.shared.log(
                    tag: "file",
                    message: "sink write FAILED: \(SampleConsole.failure(error))"
                )
            }
            stateLock.unlock()
            remaining -= Int64(read)
        }
    }

    func flush() {
        // FileHandle writes are unbuffered at this layer; nothing to do.
    }

    func synchronizeAndClose() throws {
        stateLock.lock()
        defer { stateLock.unlock() }
        guard !closed else { return }
        if let failure {
            throw NSError(
                domain: "dev.p2pkit.sample.file",
                code: 1,
                userInfo: [NSLocalizedDescriptionKey: failure]
            )
        }
        try handle.synchronize()
        try handle.close()
        closed = true
    }

    func close() {
        stateLock.lock()
        defer { stateLock.unlock() }
        guard !closed else { return }
        closed = true
        try? handle.close()
    }
}

/// Sibling temporary file + fsync + atomic replacement. The empty target file
/// created by `claimUniqueDestination` is a namespace reservation and is
/// replaced only after verification succeeds.
final class AtomicFileTransferDestination: NSObject, FileTransferDestination {
    private enum Phase {
        case active
        case committing
        case published
        case committed
        case abortingReservation
        case abortingAfterCommit
        case aborted
    }

    private let target: URL
    private let temporary: URL
    private let sink: FileHandleRawSink
    private let removeItem: (URL) throws -> Void
    private let synchronizeDirectory: (URL) throws -> Void
    private let stateLock = NSLock()
    private var phase: Phase = .active
    private var opened = false

    var temporaryArtifactExists: Bool {
        FileManager.default.fileExists(atPath: temporary.path)
    }

    init(
        target: URL,
        synchronizeDirectory: @escaping (URL) throws -> Void = fsyncDirectory,
        removeItem: @escaping (URL) throws -> Void = { url in
            try FileManager.default.removeItem(at: url)
        }
    ) throws {
        self.target = target
        self.removeItem = removeItem
        self.synchronizeDirectory = synchronizeDirectory
        let directory = target.deletingLastPathComponent()
        var claimed: URL?
        for attempt in 0...100 {
            let boundedName = String(target.lastPathComponent.prefix(48))
            let candidate = directory.appendingPathComponent(
                ".\(boundedName).\(UUID().uuidString)-\(attempt).p2pkit-part"
            )
            if FileManager.default.createFile(atPath: candidate.path, contents: nil) {
                claimed = candidate
                break
            }
        }
        guard let temporary = claimed else {
            throw NSError(
                domain: "dev.p2pkit.sample.file",
                code: 2,
                userInfo: [NSLocalizedDescriptionKey: "could not claim a temporary destination"]
            )
        }
        self.temporary = temporary
        do {
            self.sink = FileHandleRawSink(handle: try FileHandle(forWritingTo: temporary))
        } catch {
            try? FileManager.default.removeItem(at: temporary)
            throw error
        }
    }

    func openSink() -> Kotlinx_io_coreRawSink {
        stateLock.lock()
        defer { stateLock.unlock() }
        precondition(phase == .active && !opened, "destination opened more than once")
        opened = true
        return sink
    }

    func commit(completionHandler: @escaping (Error?) -> Void) {
        stateLock.lock()
        if phase == .committed {
            stateLock.unlock()
            completionHandler(nil)
            return
        }
        guard phase == .active || phase == .committing || phase == .published else {
            stateLock.unlock()
            completionHandler(destinationError("destination is not commit-ready"))
            return
        }

        do {
            if phase != .published {
                phase = .committing
                try sink.synchronizeAndClose()
                _ = try FileManager.default.replaceItemAt(target, withItemAt: temporary)
                phase = .published
            }
            try synchronizeDirectory(target.deletingLastPathComponent())
            phase = .committed
            stateLock.unlock()
            completionHandler(nil)
        } catch {
            // Retain committing/published state so abort can never delete a
            // possibly published target. A known-published retry performs only
            // the remaining directory durability barrier.
            stateLock.unlock()
            completionHandler(error)
        }
    }

    func abort(cause: P2pError.FileTransferFailed?, completionHandler: @escaping (Error?) -> Void) {
        stateLock.lock()
        if phase == .committed || phase == .aborted {
            stateLock.unlock()
            completionHandler(nil)
            return
        }
        let removeReservation: Bool
        switch phase {
        case .active, .abortingReservation:
            removeReservation = true
        case .committing, .published, .abortingAfterCommit:
            removeReservation = false
        case .committed, .aborted:
            stateLock.unlock()
            completionHandler(destinationError("destination is not abort-ready"))
            return
        }
        phase = removeReservation ? .abortingReservation : .abortingAfterCommit

        sink.close()
        var cleanupError: Error?
        var cleanupTargets = [temporary]
        if removeReservation { cleanupTargets.append(target) }
        for url in cleanupTargets where FileManager.default.fileExists(atPath: url.path) {
            do { try removeItem(url) } catch { cleanupError = error }
        }
        // Cleanup failure remains abort-retryable, but commit/open can never
        // resume after abort begins.
        if cleanupError == nil {
            phase = .aborted
        } else {
            phase = removeReservation ? .abortingReservation : .abortingAfterCommit
        }
        stateLock.unlock()
        completionHandler(cleanupError)
    }
}

private func abortDestination(_ destination: AtomicFileTransferDestination) async -> Error? {
    await withCheckedContinuation { continuation in
        destination.abort(cause: nil) { error in
            continuation.resume(returning: error)
        }
    }
}

private func destinationError(_ message: String) -> NSError {
    NSError(
        domain: "dev.p2pkit.sample.file",
        code: 3,
        userInfo: [NSLocalizedDescriptionKey: message]
    )
}

private func cleanupStaleTransferParts(in directory: URL, fileManager: FileManager) throws {
    let entries = try fileManager.contentsOfDirectory(
        at: directory,
        includingPropertiesForKeys: [.isRegularFileKey],
        options: []
    )
    for entry in entries where entry.lastPathComponent.hasSuffix(".p2pkit-part") {
        let values = try entry.resourceValues(forKeys: [.isRegularFileKey])
        if values.isRegularFile == true {
            try fileManager.removeItem(at: entry)
        }
    }
}

private func fsyncDirectory(_ directory: URL) throws {
    let descriptor = Darwin.open(directory.path, O_RDONLY)
    guard descriptor >= 0 else {
        throw NSError(domain: NSPOSIXErrorDomain, code: Int(errno))
    }
    defer { Darwin.close(descriptor) }
    guard Darwin.fsync(descriptor) == 0 else {
        throw NSError(domain: NSPOSIXErrorDomain, code: Int(errno))
    }
}
