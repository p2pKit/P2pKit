import CoreImage.CIFilterBuiltins
import P2pKitRpcExample
import SwiftUI

@main
struct RpcPhoneApp: App {
    @Environment(\.scenePhase) private var scenePhase
    @StateObject private var model: RpcPhoneModel

    init() {
        #if DEBUG
            let unavailable = ProcessInfo.processInfo.arguments.contains("--rpc-ui-network-unavailable")
            _model = StateObject(wrappedValue: RpcPhoneModel(wifi: unavailable ? RpcPhoneUnavailableTestWifi() : nil))
        #else
            _model = StateObject(wrappedValue: RpcPhoneModel())
        #endif
    }

    var body: some Scene {
        WindowGroup {
            #if DEBUG
                if ProcessInfo.processInfo.arguments.contains("--rpc-ui-approval-presentation")
                    && ProcessInfo.processInfo.arguments.contains("--rpc-ui-network-unavailable")
                {
                    RpcPhoneApprovalPresentationProbe()
                } else {
                    applicationView
                }
            #else
                applicationView
            #endif
        }
    }

    private var applicationView: some View {
        RpcPhoneView(model: model)
            .privacySensitive()
            .overlay {
                if scenePhase != .active {
                    Color(.systemBackground).ignoresSafeArea().overlay(Text("RPC lab is not active"))
                }
            }
            .onAppear {
                model.setForeground(scenePhase == .active)
                #if DEBUG
                    if scenePhase == .active {
                        model.beginUsbDeveloperCampaign(arguments: ProcessInfo.processInfo.arguments)
                    }
                #endif
            }
            .onChange(of: scenePhase) {
                model.setForeground($0 == .active)
                #if DEBUG
                    if $0 == .active { model.beginUsbDeveloperCampaign(arguments: ProcessInfo.processInfo.arguments) }
                #endif
            }
            .onReceive(NotificationCenter.default.publisher(for: UIApplication.didReceiveMemoryWarningNotification)) { _ in
                model.testMemoryPressure()
            }
            .onReceive(
                NotificationCenter.default.publisher(for: UIApplication.protectedDataWillBecomeUnavailableNotification)
            ) { _ in
                model.protectedDataUnavailable()
            }
    }
}

struct RpcPhoneView: View {
    @ObservedObject var model: RpcPhoneModel
    @State private var showAdvanced = false
    @State private var showingDeviceTests = false
    @State private var deletingTest: String?
    @StateObject private var presentation = RpcPhoneDecisionPresentation()

    var body: some View {
        NavigationView {
            Form {
                if showingDeviceTests {
                    deviceTests
                } else {
                Section {
                    Button("Device tests") { model.setTestMode(false); showingDeviceTests = true; model.refreshDeviceTests() }
                        .disabled(model.mobileConfig != nil || model.actionBusy)
                        .accessibilityIdentifier("rpc.deviceTests")
                    Button("Multi-device tests") {
                        model.setTestMode(true); showingDeviceTests = true; model.refreshDeviceTests()
                    }.disabled(model.mobileConfig != nil || model.actionBusy || model.deviceTestRunning)
                    VStack(alignment: .leading, spacing: 10) {
                        Label("LOCAL API WORKSPACE", systemImage: "network")
                            .font(.caption.weight(.semibold)).foregroundColor(.secondary)
                        Text("P2pKit RPC").font(.largeTitle.bold())
                        Text(model.activeRoleLabel).font(.headline).accessibilityIdentifier("rpc.activeRole")
                        Text(model.status).font(.callout).accessibilityIdentifier("rpc.status")
                    }
                    .padding(.vertical, 10)
                    Text(
                        "Choose a role on your private LAN. Network selection is automatic; peer trust is not. Return within 25 seconds when switching apps."
                    )
                    .font(.subheadline).accessibilityIdentifier("rpc.introduction")
                    Text(
                        "Switch before pairing or running a test. In-progress operations, manual setup and capacity sessions still stop when you leave."
                    )
                    .font(.footnote).foregroundColor(.secondary)
                }
                Section("Overview · choose a role") {
                    Text(model.status).accessibilityIdentifier("rpc.roleStatus")
                    HStack(spacing: 12) {
                        Button {
                            model.start(host: true, automatic: true)
                        } label: {
                            Label("Start host", systemImage: "antenna.radiowaves.left.and.right")
                                .frame(maxWidth: .infinity, minHeight: 32)
                        }
                        .buttonStyle(.borderedProminent)
                        .disabled(!model.canStart).accessibilityIdentifier("rpc.host")
                        Button {
                            model.start(host: false, automatic: true)
                        } label: {
                            Label("Start client", systemImage: "link")
                                .frame(maxWidth: .infinity, minHeight: 32)
                        }
                        .buttonStyle(.bordered)
                        .disabled(!model.canStart).accessibilityIdentifier("rpc.client")
                    }
                    Button("Stop") { model.stop() }
                        .disabled(!model.owner.hasOwner).accessibilityIdentifier("rpc.stop")
                    if model.owner.phase == .running {
                        Button("Cancel current operation") { model.cancelOperation() }
                            .disabled(!model.operationBusy)
                        Text("Stop waits for cleanup. Cancellation does not undo work already done.").font(.footnote)
                    }
                    Text("Host waits for a client. A client must pair with a host before sending a test message.")
                        .font(.footnote)
                }
                wifiControls
                if !model.fingerprint.isEmpty {
                    Section {
                        DisclosureGroup("Device identity") {
                            Text(model.fingerprint).font(.caption.monospaced()).textSelection(.enabled)
                        }
                    }
                }
                if model.owner.phase == .running {
                    if model.nearbyMode {
                        RpcPhoneNearbyView(model: model, presentation: presentation)
                        if !model.hostRole { Section("Application API examples") { applicationActions } }
                    } else if model.hostRole {
                        if model.mobileConfig == nil { hostControls }
                    } else {
                        clientControls
                    }
                }
                liveControls
                if model.mobileConfig == nil { requestHistory }
                diagnosticControls
                advancedControls
                }
            }
            .navigationTitle(showingDeviceTests ? (model.multiTests ? "Multi-device tests" : "Device tests") : "P2pKit RPC")
            .toolbar {
                ToolbarItem(placement: .navigationBarLeading) {
                    if showingDeviceTests {
                        Button("Back to RPC") {
                            guard !model.deviceTestRunning else { return }
                            model.setAllowHostTests(false)
                            showingDeviceTests = false
                        }.disabled(model.deviceTestRunning)
                    }
                }
            }
            .navigationBarTitleDisplayMode(.inline)
            .tint(Color(red: 0.125, green: 0.369, blue: 0.651))
        }
        .navigationViewStyle(.stack)
        .rpcDecisionSheet(item: $presentation.dialog, onDismiss: { presentation.offerPending(model) }) { decision in
            RpcPhoneDecisionSheet(model: model, presentation: presentation, decision: decision)
        }
        .onChange(of: model.pending.map(\.requestId)) { _ in presentation.offerPending(model) }
        .onAppear { presentation.offerPending(model) }
        .alert(item: $model.startProblem) { problem in
            Alert(title: Text("Cannot start RPC"), message: Text(problem.message), dismissButton: .default(Text("OK")))
        }
        .onChange(of: model.wifiObservation) { observation in
            #if DEBUG
                if let line = RpcPhoneWifiDiagnostic.line(
                    arguments: ProcessInfo.processInfo.arguments,
                    observation: observation, source: model.compiledSource, canConfirm: model.canConfirmWifi)
                {
                    print(line)
                    fflush(stdout)
                }
            #endif
        }
    }

    private var deviceTests: some View {
        Group {
            Section("Test section") {
                HStack {
                    Button("Two devices") { model.setTestMode(false) }
                    Button("Multiple devices") { model.setTestMode(true) }
                }.buttonStyle(.borderless).disabled(model.deviceTestRunning || model.actionBusy)
                Text(model.multiTests ? "Several trusted Clients → one Host. Each run is saved separately." :
                    "One Client → one Host. The Client sends requests and the Host replies.").font(.footnote)
            }
            Section("Connect devices automatically") {
                Text(model.status).accessibilityIdentifier("rpc.testStatus")
                Text("Use the same private Wi-Fi. Approve fingerprints and enable test permission on each Client.")
                HStack {
                    Button("Host here") { model.startDeviceTestRole(host: true) }
                        .buttonStyle(.borderedProminent).disabled(!model.canStart)
                        .accessibilityIdentifier("rpc.testHost")
                    Button("Client here") { model.startDeviceTestRole(host: false) }
                        .buttonStyle(.bordered).disabled(!model.canStart)
                        .accessibilityIdentifier("rpc.testClient")
                    Button("Stop") { model.stop() }
                        .buttonStyle(.borderless).disabled(!model.owner.hasOwner)
                        .accessibilityIdentifier("rpc.testStop")
                }
                Text("For a brief app switch, return within 25 seconds. iOS may end background time sooner.")
                    .font(.footnote)
            }
            if model.nearbyMode {
                Section("Your device identity · compare on the other device") {
                    Text(model.fingerprint).font(.caption.monospaced()).textSelection(.enabled)
                }
                RpcPhoneNearbyView(model: model, presentation: presentation)
                Section(model.hostRole ? "Select connected Clients" : "Test permission") {
                    if model.hostRole {
                        ForEach(model.trustedDevices.filter { $0.presence == "Connected" }, id: \.fingerprint) { device in
                            Button((testPeerSelected(device.fingerprint) ? "✓ " : "") +
                                device.name + " · " + device.fingerprint.suffix(8)) {
                                if model.multiTests {
                                    if model.selectedTestPeers.contains(device.fingerprint) {
                                        model.selectedTestPeers.remove(device.fingerprint)
                                    } else if model.selectedTestPeers.count < 16 {
                                        model.selectedTestPeers.insert(device.fingerprint)
                                    }
                                } else { model.selectedTestPeer = device.fingerprint }
                            }.disabled(model.deviceTestRunning || model.actionBusy)
                        }
                        if model.multiTests { Text("Up to 16 connected Clients per group.").font(.footnote) }
                    } else {
                        Toggle("Allow selected Host to start tests while this screen is open", isOn: Binding(
                            get: { model.allowHostTests }, set: { model.setAllowHostTests($0) }))
                            .disabled(!model.canAct || model.deviceTestRunning)
                    }
                }
            }
            Section(model.multiTests ? "Start a test on the selected Clients" : "Run a test") {
                Text("Smart Test searches this connected path. Safety ceilings are not a discovered Host capacity.")
                    .font(.footnote)
                ForEach([RpcDeviceTestPhase.large, .correctness, .reconnect, .steady, .deadlines, .adaptive], id: \.name) { phase in
                    Button(phase.title) { model.runDeviceTest(phase) }
                        .disabled(!model.canAct || model.deviceTestRunning || !model.nearbyMode ||
                            (model.hostRole ? !model.trustedDevices.contains {
                                testPeerSelected($0.fingerprint) && $0.presence == "Connected"
                            } : model.owner.runtime?.state != "Ready"))
                }
                DisclosureGroup("Smart safety settings · automatic defaults") {
                    TextField("p95 limit (ms)", text: $model.smartP95).keyboardType(.numberPad)
                    TextField("p99 limit (ms)", text: $model.smartP99).keyboardType(.numberPad)
                    TextField("Memory safety limit (MiB)", text: $model.smartMemory).keyboardType(.numberPad)
                    TextField("Time safety budget (seconds)", text: $model.smartSeconds).keyboardType(.numberPad)
                    Button("Apply safety settings") { model.applySmartSafety() }
                }.disabled(!model.canAct || model.deviceTestRunning)
            }
            Section("Monitor") {
                Text(model.testSummary)
                if let resources = model.liveTestResources {
                    Text(resources.title).monospacedDigit()
                    Text(resources.environmentTitle).font(.footnote)
                } else { Text("Resource sample unavailable") }
                ForEach(model.activeDeviceTests, id: \.runId) { progress in
                    VStack(alignment: .leading) {
                        Text(progress.monitorText).monospacedDigit()
                        if let host = progress.hostResources {
                            Text("Host: " + host.title).font(.footnote)
                            Text(host.environmentTitle).font(.footnote)
                        }
                        Button("Cancel this test") { model.cancelTest(progress.runId) }
                    }
                }
                if model.deviceTestRunning { Button("Cancel all tests") { model.cancelOperation() } }
            }
            Section("Live test activity") {
                HStack {
                    Button("Clear displayed logs") { model.clearTestDisplay() }
                    Button("Show saved results") { model.showSavedTests() }
                }.buttonStyle(.borderless)
                Text("Clearing this display keeps all saved output.").font(.footnote)
                ForEach(Array(model.deviceTestActivity.reversed().enumerated()), id: \.offset) { _, activity in
                    Text(activity.title).font(.footnote)
                }
            }
            Section("Saved results · separate output per run") {
                Text(model.deviceTestStorageIssue ?? "Recent list: 100. Older outputs remain saved privately.")
                ForEach(model.deviceTestReports.reversed(), id: \.runId) { report in
                    DisclosureGroup(report.title) {
                        Text(report.detail).font(.footnote).textSelection(.enabled)
                        if report.startedAtEpochMillis > 0 {
                            Text("Started: " + Date(timeIntervalSince1970: Double(report.startedAtEpochMillis) / 1000)
                                .formatted()).font(.footnote)
                        }
                        if report.endedAtEpochMillis > 0 {
                            Text("Ended: " + Date(timeIntervalSince1970: Double(report.endedAtEpochMillis) / 1000)
                                .formatted()).font(.footnote)
                        }
                        Button("Delete this output…", role: .destructive) { deletingTest = report.runId }
                            .disabled(model.deviceTestRunning || model.actionBusy)
                    }
                }
            }
        }
        .alert("Delete this test output?", isPresented: Binding(
            get: { deletingTest != nil }, set: { if !$0 { deletingTest = nil } })) {
                Button("Delete output", role: .destructive) {
                    if let runId = deletingTest { model.deleteTest(runId) }
                    deletingTest = nil
                }
                Button("Keep output", role: .cancel) { deletingTest = nil }
            } message: {
                Text("Permanently deletes only the selected run on this iPhone. Other devices keep their copies.")
            }
    }

    private func testPeerSelected(_ fingerprint: String) -> Bool {
        model.multiTests ? model.selectedTestPeers.contains(fingerprint) : model.selectedTestPeer == fingerprint
    }

    private var liveControls: some View {
        Section {
            DisclosureGroup("Activity & statistics") {
                Text(model.liveState).font(.headline).accessibilityIdentifier("rpc.liveState")
                if model.mobileConfig == nil {
                    LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible())], spacing: 12) {
                        ForEach(model.liveCounters, id: \.id) { counter in
                            VStack(spacing: 4) {
                                Text(counter.value).font(.title.bold()).monospacedDigit()
                                    .accessibilityIdentifier("rpc.counter." + counter.id)
                                Text(counter.label).font(.subheadline)
                            }
                            .frame(maxWidth: .infinity, minHeight: 72)
                            .background(Color.accentColor.opacity(0.09))
                            .cornerRadius(10)
                            .accessibilityElement(children: .ignore)
                            .accessibilityLabel(counter.label)
                            .accessibilityValue(counter.value)
                            .accessibilityIdentifier("rpc.card." + counter.id)
                        }
                    }
                    if !model.requestMetrics.isEmpty {
                        Text("Request outcomes — current role lifetime").font(.headline)
                        LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible())], spacing: 10) {
                            ForEach(model.requestMetrics, id: \.id) { metric in
                                VStack(spacing: 4) {
                                    Text("\(metric.value)").font(.title.bold()).monospacedDigit()
                                    Text(metric.label).font(.subheadline)
                                }
                                .frame(maxWidth: .infinity, minHeight: 72)
                                .background(Color.accentColor.opacity(0.09)).cornerRadius(10)
                                .accessibilityElement(children: .ignore)
                                .accessibilityLabel(metric.label).accessibilityValue("\(metric.value)")
                                .accessibilityIdentifier("rpc.metric." + metric.id)
                            }
                        }
                        Text(
                            "Refused attempts are separate from admitted requests. Host completion does not prove client delivery."
                        )
                        .font(.footnote)
                    }
                    Text(
                        "Updates automatically every half-second while this app is open. "
                            + "Pending requests still require your exact-client approval. No background polling."
                    ).font(.footnote)
                } else {
                    Text(
                        "Refresh status and pairing requests takes an explicit diagnostic snapshot only; "
                            + "manual pairing is unavailable for capacity sessions."
                    ).font(.footnote)
                }
            }
        }
    }

    private var diagnosticControls: some View {
        Section {
            DisclosureGroup("Diagnostics") {
                Button("Refresh status and pairing requests") { model.refresh() }
                    .disabled(model.owner.phase != .running)
                Text(
                    "Local events only; no invitations, peer identities, network addresses or message contents. "
                        + "Refresh keeps the last failure. These logs are not proof that a peer is connected."
                ).font(.footnote)
                Button("Copy diagnostics") { model.copyDiagnostics() }
                    .buttonStyle(.borderless)
                    .disabled(!model.canCopyDiagnostics)
                    .accessibilityIdentifier("rpc.copyDiagnostics")
                    .accessibilityHint("Copies the bounded event log locally, replacing anything you copied before.")
                DisclosureGroup("Recent events (last 64)") {
                    Text(model.diagnosticText).font(.caption.monospaced()).textSelection(.enabled)
                        .accessibilityIdentifier("rpc.diagnostics")
                }
                Text(
                    "Copying diagnostics replaces a copied invitation. Copy the invitation again if you still need it."
                )
                .font(.footnote)
            }
        }
    }

    private var wifiControls: some View {
        Section("Network · automatic Wi-Fi") {
            if model.manualNetworkSetup {
                Text("Manual network settings selected. Review them under Advanced.")
            } else {
                Text(model.detectedWifi == nil ? model.wifiExplanation : "Wi-Fi ready · network selected automatically")
                    .accessibilityIdentifier("rpc.wifiStatus")
            }
            DisclosureGroup("Network details") {
                if let network = model.detectedWifi {
                    Text("This iPhone: \(network.localAddress)").font(.callout.monospaced())
                    Text("Private network: \(network.subnet) · \(network.interfaceName)").font(
                        .caption.monospaced())
                }
                Button("Check Wi-Fi again") { model.refreshWifi() }
                    .buttonStyle(.borderless)
                    .disabled(!model.canRefreshWifi)
                    .accessibilityIdentifier("rpc.refreshWifi")
                    .accessibilityHint("Only re-reads the connection. Does not approve a network or start RPC.")
                DisclosureGroup("Wi-Fi check details") {
                    Text(model.wifiObservation.details).font(.caption)
                        .accessibilityIdentifier("rpc.wifiDetails")
                    Text(
                        "These are this app's observations, not proof of peer connectivity or multicast. "
                            + "Advanced offers manual setup for independently verified approved networks."
                    ).font(.footnote)
                }
            }
        }
    }

    private var advancedControls: some View {
        Section {
            DisclosureGroup("Advanced", isExpanded: $showAdvanced) {
                Button(model.manualNetworkSetup ? "Use detected Wi-Fi instead" : "Enter network settings manually") {
                    model.setManualNetworkSetup(!model.manualNetworkSetup)
                }
                .buttonStyle(.borderless)
                .disabled(!model.canStart || model.mobileConfig != nil)
                .accessibilityIdentifier("rpc.manualNetwork")
                if model.manualNetworkSetup {
                    Group {
                        Text("Manual network settings: use only your approved private LAN.").font(.footnote)
                        field("Approved private CIDRs, comma-separated", $model.subnets, limit: 512, id: "rpc.subnets")
                        field("Wi-Fi interface, for example en0", $model.interfaceName, limit: 32, id: "rpc.interface")
                        field("This device's numeric LAN address", $model.localAddress, limit: 64, id: "rpc.local")
                    }.disabled(!model.canStart)
                }
                field("Fixed host port", $model.port, limit: 5, id: "rpc.port").disabled(!model.canStart)
                DisclosureGroup("Capacity-test provisioning") {
                    field("Exactly 128 or 256 public synthetic client pins", $model.capacityPins,
                          limit: 16_384, id: "rpc.pins")
                    Toggle("I approve replacing this test host's client pins", isOn: $model.approveImport)
                }.disabled(!model.canStart)
                DisclosureGroup("USB capacity session") {
                    field("Prepared USB run label", $model.usbRunLabel, limit: 64, id: "rpc.usbRun")
                    Button("Prepare new USB slot (RPC stays stopped)") { model.prepareMobile() }
                        .disabled(!model.canStart || model.mobileConfig != nil).accessibilityIdentifier(
                            "rpc.usbPrepare")
                    Button("Load prepared session (not approval)") { model.loadMobile() }
                        .disabled(!model.canStart || model.mobileConfig != nil).accessibilityIdentifier("rpc.usbLoad")
                    Button("Clear loaded session; preserve evidence") { model.clearMobile() }.disabled(!model.canStart)
                }.disabled(!model.canStart)
                if model.owner.phase == .running, model.mobileConfig == nil {
                    field("Exact peer pin to revoke", $model.hostPin, limit: 64, id: "rpc.revokePin")
                    Button("Revoke this exact peer") { model.revoke() }.disabled(!model.canAct)
                }
                Text("Compiled test source: \(model.compiledSource)").font(.caption.monospaced())
                if !model.fingerprint.isEmpty {
                    Text("Local identity: \(model.fingerprint)").font(.caption.monospaced())
                }
                Text(
                    "Discovery is advisory; approval uses the cryptographic identity. Wi-Fi detection is not peer connectivity proof."
                )
                .font(.footnote)
            }
        }
    }

    private var hostControls: some View {
        Section("Local administrator approval") {
            Text(
                "After the client taps Pair, pending requests appear here automatically. "
                    + "Approve only the displayed client fingerprint you verify on the other device."
            ).font(.footnote)
            Button("Create one-use, two-minute invitation") { model.createInvitation() }.disabled(!model.canAct)
            Toggle("Reveal on this trusted local display", isOn: $model.revealInvitation)
            Text(
                "Invitations are secret. Use only a trusted private transfer; never post them publicly or include them in logs."
            )
            if model.revealInvitation, !model.invitation.isEmpty {
                if let qr = qrImage(model.invitation) {
                    Image(uiImage: qr).interpolation(.none).resizable().scaledToFit()
                        .accessibilityLabel("Local single-use pairing invitation")
                }
                Text(model.invitation).font(.caption.monospaced())
            }
            Button("Copy invitation") { model.copyInvitation() }
                .buttonStyle(.borderless)
                .disabled(!model.canCopyInvitation)
                .accessibilityIdentifier("rpc.copyInvitation")
                .accessibilityHint("Copies the secret invitation locally without revealing it on screen.")
            Text(
                "Copy works without Reveal and never turns it on. It stays local to this iPhone "
                    + "and does not extend the two-minute invitation. "
                    + "After switching apps, return within 25 seconds. iOS may stop the role sooner; Stop always ends it."
            ).font(.footnote)
            ForEach(model.pending, id: \.requestId) { request in
                Text("Verify locally: \(request.fingerprint)")
                Button("Approve this exact client") { model.approve(request) }.disabled(!model.canAct)
            }
        }
    }

    private var clientControls: some View {
        Section("One explicitly selected trusted host") {
            Text(
                "The other device must be Host. Tap Pair here, then watch the host for a request; approve a verified "
                    + "request if one appears. Previously trusted peers may connect without a new request."
            ).font(.footnote)
            Text("You may switch apps to copy the host invitation. Return within 25 seconds, then paste below.")
                .font(.footnote)
            SecureField("Invitation obtained through a trusted local channel", text: $model.invitation)
                .textInputAutocapitalization(.never).autocorrectionDisabled()
                .onChange(of: model.invitation) { if $0.count > 512 { model.invitation = String($0.prefix(512)) } }
            Button("Pair and connect; wait for host approval") { model.connect(pair: true) }.disabled(!model.canAct)
            applicationActions
            DisclosureGroup("Reconnect or run a larger test") {
                Button("Diagnostic 1 KiB echo") { model.echo(large: false) }.disabled(!model.canAct)
                field("Already trusted host's full fingerprint", $model.hostPin, limit: 64, id: "rpc.hostPin")
                field("Already trusted host's numeric address", $model.hostAddress, limit: 64, id: "rpc.hostAddress")
                Button("Connect using the same durable pin") { model.connect(pair: false) }.disabled(!model.canAct)
                Button("20 × 1 MiB echoes; concurrency two") { model.echo(large: true) }.disabled(!model.canAct)
            }
        }
    }

    private var applicationActions: some View {
        Group {
            Text("Choose an example. Open Request history to inspect the response.").font(.footnote)
            Button("Get user · users.get") { model.runExample(.getuser) }
            Button("List items · items.list") { model.runExample(.listitems) }
            Button("Send message · message.send") { model.runExample(.sendmessage) }
            DisclosureGroup("Custom request") {
                field("User / recipient ID", $model.inputUser, limit: 11, id: "rpc.inputUser")
                Button("Send users.get") { model.sendRequest(.getuser) }
                field("Items offset", $model.inputOffset, limit: 11, id: "rpc.inputOffset")
                field("Items limit (1–50)", $model.inputLimit, limit: 11, id: "rpc.inputLimit")
                Button("Send items.list") { model.sendRequest(.listitems) }
                field("Message text (up to 512 UTF-16 units)", $model.inputMessage, limit: 512, id: "rpc.inputMessage")
                Button("Send message.send") { model.sendRequest(.sendmessage) }
            }
            DisclosureGroup("Error examples & echo") {
                Button("Business error (unknown user)") { model.runExample(.businesserror) }
                Button("Validation error (invalid user ID)") { model.runExample(.validationerror) }
                Button("Diagnostic 1 KiB echo") { model.echo(large: false) }
            }
        }.disabled(!model.canAct || model.liveSnapshot?.state != "Ready")
    }

    private var requestHistory: some View {
        Section {
            DisclosureGroup("Request history (application data)") {
                Text(
                    "Up to 100 local entries; previews are truncated. Host results describe handler completion, "
                        + "not proof the client received them. History survives Stop, not app termination."
                ).font(.footnote)
                Text("History captures omitted at capacity: \(model.applicationSession.history.droppedCaptures)").font(
                    .footnote)
                Button("Clear completed history") { model.clearRequestHistory() }.buttonStyle(.borderless)
                ForEach(model.requestEntries.reversed(), id: \.localId) { entry in
                    DisclosureGroup(
                        "\(entry.procedure)/v\(entry.version) · \(entry.outcome.name) · \(entry.elapsedMillis) ms"
                    ) {
                        Text("Application data may be private. Copy details only to a trusted destination.").font(
                            .footnote)
                        Text(entry.details()).font(.caption.monospaced()).textSelection(.enabled)
                        Button("Copy request diagnostics") { model.copyRequest(entry.localId, includeData: false) }
                            .buttonStyle(.borderless)
                        Button("Copy request details (includes data)") {
                            model.copyRequest(entry.localId, includeData: true)
                        }
                        .buttonStyle(.borderless)
                    }
                }
            }
        }
    }

    private func field(_ title: String, _ value: Binding<String>, limit: Int, id: String) -> some View {
        TextField(title, text: value)
            .textInputAutocapitalization(.never).autocorrectionDisabled().accessibilityIdentifier(id)
            .onChange(of: value.wrappedValue) { if $0.count > limit { value.wrappedValue = String($0.prefix(limit)) } }
    }

    private func qrImage(_ value: String) -> UIImage? {
        guard value.utf8.count <= 512 else { return nil }
        let filter = CIFilter.qrCodeGenerator()
        filter.message = Data(value.utf8)
        filter.correctionLevel = "M"
        guard let output = filter.outputImage?.transformed(by: CGAffineTransform(scaleX: 4, y: 4)),
            let image = CIContext().createCGImage(output, from: output.extent)
        else { return nil }
        return UIImage(cgImage: image)
    }
}
