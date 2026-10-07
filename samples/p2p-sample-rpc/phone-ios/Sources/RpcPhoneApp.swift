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
            RpcPhoneView(model: model)
                .privacySensitive()
                .overlay {
                    if scenePhase != .active {
                        Color(.systemBackground).ignoresSafeArea().overlay(Text("RPC lab is not active"))
                    }
                }
                .onAppear { model.setForeground(scenePhase == .active) }
                .onChange(of: scenePhase) { model.setForeground($0 == .active) }
                .onReceive(NotificationCenter.default.publisher(for: UIApplication.protectedDataWillBecomeUnavailableNotification)) { _ in
                    model.protectedDataUnavailable()
                }
        }
    }
}

struct RpcPhoneView: View {
    @ObservedObject var model: RpcPhoneModel
    @State private var showAdvanced = false

    var body: some View {
        NavigationView {
            Form {
                Section {
                    VStack(alignment: .leading, spacing: 10) {
                        Label("LOCAL API WORKSPACE", systemImage: "network")
                            .font(.caption.weight(.semibold)).foregroundColor(.secondary)
                        Text("P2pKit RPC").font(.largeTitle.bold())
                        Text(model.activeRoleLabel).font(.headline).accessibilityIdentifier("rpc.activeRole")
                        Text(model.status).font(.callout).accessibilityIdentifier("rpc.status")
                    }
                    .padding(.vertical, 10)
                    Text("Choose a role on your private LAN. Network selection is automatic; peer trust is not. Return within 25 seconds when switching apps.")
                        .font(.subheadline).accessibilityIdentifier("rpc.introduction")
                    Text("Switch before pairing or running a test. In-progress operations, manual setup and capacity sessions still stop when you leave.")
                        .font(.footnote).foregroundColor(.secondary)
                }
                liveControls
                wifiControls
                Section("Overview · choose a role") {
                    Text(model.status).accessibilityIdentifier("rpc.roleStatus")
                    HStack(spacing: 12) {
                        Button { model.start(host: true, automatic: true) } label: {
                            Label("Start host", systemImage: "antenna.radiowaves.left.and.right")
                                .frame(maxWidth: .infinity, minHeight: 32)
                        }
                        .buttonStyle(.borderedProminent)
                        .disabled(!model.canStart).accessibilityIdentifier("rpc.host")
                        Button { model.start(host: false, automatic: true) } label: {
                            Label("Start client", systemImage: "link")
                                .frame(maxWidth: .infinity, minHeight: 32)
                        }
                        .buttonStyle(.bordered)
                        .disabled(!model.canStart).accessibilityIdentifier("rpc.client")
                    }
                    Button("Stop") { model.stop() }
                        .disabled(!model.owner.hasOwner).accessibilityIdentifier("rpc.stop")
                    if model.owner.phase == .running {
                        Button("Refresh status and pairing requests") { model.refresh() }
                        Button("Cancel current operation") { model.cancelOperation() }
                            .disabled(!model.operationBusy)
                        Text("Stop waits for cleanup. Cancellation does not undo work already done.").font(.footnote)
                    }
                    Text("Host waits for a client. A client must pair with a host before sending a test message.")
                        .font(.footnote)
                }
                if model.owner.phase == .running {
                    if model.nearbyMode {
                        RpcPhoneNearbyView(model: model)
                        if !model.hostRole { Section("Application API examples") { applicationActions } }
                    } else if model.hostRole {
                        if model.mobileConfig == nil { hostControls }
                    } else { clientControls }
                }
                if model.mobileConfig == nil { requestHistory }
                diagnosticControls
                advancedControls
            }
            .navigationTitle("P2pKit RPC")
            .navigationBarTitleDisplayMode(.inline)
            .tint(Color(red: 0.125, green: 0.369, blue: 0.651))
        }
        .navigationViewStyle(.stack)
        .alert(item: $model.startProblem) { problem in
            Alert(title: Text("Cannot start RPC"), message: Text(problem.message), dismissButton: .default(Text("OK")))
        }
        .onChange(of: model.wifiObservation) { observation in
            #if DEBUG
            if let line = RpcPhoneWifiDiagnostic.line(arguments: ProcessInfo.processInfo.arguments,
                observation: observation, source: model.compiledSource, canConfirm: model.canConfirmWifi) {
                print(line)
                fflush(stdout)
            }
            #endif
        }
    }

    private var liveControls: some View {
        Section("Live dashboard") {
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
                    Text("Refused attempts are separate from admitted requests. Host completion does not prove client delivery.")
                        .font(.footnote)
                }
                Text("Updates automatically every half-second while this app is open. " +
                    "Pending requests still require your exact-client approval. No background polling.").font(.footnote)
            } else {
                Text("Refresh status and pairing requests takes an explicit diagnostic snapshot only; " +
                    "manual pairing is unavailable for capacity sessions.").font(.footnote)
            }
        }
    }

    private var diagnosticControls: some View {
        Section("Diagnostic log") {
            Text("Local events only; no invitations, peer identities, network addresses or message contents. " +
                "Refresh keeps the last failure. These logs are not proof that a peer is connected.").font(.footnote)
            Button("Copy diagnostics") { model.copyDiagnostics() }
                .buttonStyle(.borderless)
                .disabled(!model.canCopyDiagnostics)
                .accessibilityIdentifier("rpc.copyDiagnostics")
                .accessibilityHint("Copies the bounded event log locally, replacing anything you copied before.")
            DisclosureGroup("Recent events (last 64)") {
                Text(model.diagnosticText).font(.caption.monospaced()).textSelection(.enabled)
                    .accessibilityIdentifier("rpc.diagnostics")
            }
            Text("Copying diagnostics replaces a copied invitation. Copy the invitation again if you still need it.")
                .font(.footnote)
        }
    }

    private var wifiControls: some View {
        Section("Network · automatic Wi-Fi") {
            if model.manualNetworkSetup {
                Text("Manual network settings selected. Review them under Advanced.")
            } else {
                if let network = model.detectedWifi {
                    Text("This iPhone: \(network.localAddress)").font(.callout.monospaced())
                    Text("Private network: \(network.subnet) · \(network.interfaceName)").font(.caption.monospaced())
                }
                Text(model.wifiExplanation).accessibilityIdentifier("rpc.wifiStatus")
                Text("Starting selects the eligible Wi-Fi automatically. Only use a network you are authorized to use.")
                    .font(.footnote)
                Button("Check Wi-Fi again") { model.refreshWifi() }
                    .buttonStyle(.borderless)
                    .disabled(!model.canRefreshWifi)
                    .accessibilityIdentifier("rpc.refreshWifi")
                    .accessibilityHint("Only re-reads the connection. Does not approve a network or start RPC.")
                DisclosureGroup("Wi-Fi check details") {
                    Text(model.wifiObservation.details).font(.caption)
                        .accessibilityIdentifier("rpc.wifiDetails")
                    Text("These are this app's observations, not proof of peer connectivity or multicast. " +
                        "Advanced offers manual setup for independently verified approved networks.").font(.footnote)
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
                    field("Exactly 128 public synthetic client pins", $model.capacityPins, limit: 8192, id: "rpc.pins")
                    Toggle("I approve replacing this test host's client pins", isOn: $model.approveImport)
                }.disabled(!model.canStart)
                DisclosureGroup("USB capacity session") {
                    field("Prepared USB run label", $model.usbRunLabel, limit: 64, id: "rpc.usbRun")
                    Button("Prepare new USB slot (RPC stays stopped)") { model.prepareMobile() }
                        .disabled(!model.canStart || model.mobileConfig != nil).accessibilityIdentifier("rpc.usbPrepare")
                    Button("Load prepared session (not approval)") { model.loadMobile() }
                        .disabled(!model.canStart || model.mobileConfig != nil).accessibilityIdentifier("rpc.usbLoad")
                    Button("Clear loaded session; preserve evidence") { model.clearMobile() }.disabled(!model.canStart)
                }.disabled(!model.canStart)
                if model.owner.phase == .running, model.mobileConfig == nil {
                    field("Exact peer pin to revoke", $model.hostPin, limit: 64, id: "rpc.revokePin")
                    Button("Revoke this exact peer") { model.revoke() }.disabled(!model.canAct)
                }
                Text("Compiled test source: \(model.compiledSource)").font(.caption.monospaced())
                if !model.fingerprint.isEmpty { Text("Local identity: \(model.fingerprint)").font(.caption.monospaced()) }
                Text("Discovery is advisory; approval uses the cryptographic identity. Wi-Fi detection is not peer connectivity proof.")
                    .font(.footnote)
            }
        }
    }

    private var hostControls: some View {
        Section("Local administrator approval") {
            Text("After the client taps Pair, pending requests appear here automatically. " +
                "Approve only the displayed client fingerprint you verify on the other device.").font(.footnote)
            Button("Create one-use, two-minute invitation") { model.createInvitation() }.disabled(!model.canAct)
            Toggle("Reveal on this trusted local display", isOn: $model.revealInvitation)
            Text("Invitations are secret. Use only a trusted private transfer; never post them publicly or include them in logs.")
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
            Text("Copy works without Reveal and never turns it on. It stays local to this iPhone " +
                "and does not extend the two-minute invitation. " +
                "After switching apps, return within 25 seconds. iOS may stop the role sooner; Stop always ends it.").font(.footnote)
            ForEach(model.pending, id: \.requestId) { request in
                Text("Verify locally: \(request.fingerprint)")
                Button("Approve this exact client") { model.approve(request) }.disabled(!model.canAct)
            }
        }
    }

    private var clientControls: some View {
        Section("One explicitly selected trusted host") {
            Text("The other device must be Host. Tap Pair here, then watch the host for a request; approve a verified " +
                "request if one appears. Previously trusted peers may connect without a new request.").font(.footnote)
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
            field("User / recipient ID", $model.inputUser, limit: 11, id: "rpc.inputUser")
            Button("Send users.get") { model.sendRequest(.getuser) }
            field("Items offset", $model.inputOffset, limit: 11, id: "rpc.inputOffset")
            field("Items limit (1–50)", $model.inputLimit, limit: 11, id: "rpc.inputLimit")
            Button("Send items.list") { model.sendRequest(.listitems) }
            field("Message text (up to 512 UTF-16 units)", $model.inputMessage, limit: 512, id: "rpc.inputMessage")
            Button("Send message.send") { model.sendRequest(.sendmessage) }
            Text("Preset examples and diagnostics").font(.headline)
            Button("users.get") { model.runExample(.getuser) }
            Button("items.list") { model.runExample(.listitems) }
            Button("message.send") { model.runExample(.sendmessage) }
            Button("Business error (unknown user)") { model.runExample(.businesserror) }
            Button("Validation error (invalid user ID)") { model.runExample(.validationerror) }
            Button("Diagnostic 1 KiB echo") { model.echo(large: false) }
        }.disabled(!model.canAct || model.liveSnapshot?.state != "Ready")
    }

    private var requestHistory: some View {
        Section("Request history (application data)") {
            Text("Up to 100 local entries; previews are truncated. Host results describe handler completion, " +
                "not proof the client received them. History survives Stop, not app termination.").font(.footnote)
            Text("History captures omitted at capacity: \(model.applicationSession.history.droppedCaptures)").font(.footnote)
            Button("Clear completed history") { model.clearRequestHistory() }.buttonStyle(.borderless)
            ForEach(model.requestEntries.reversed(), id: \.localId) { entry in
                DisclosureGroup("\(entry.procedure)/v\(entry.version) · \(entry.outcome.name) · \(entry.elapsedMillis) ms") {
                    Text("Application data may be private. Copy details only to a trusted destination.").font(.footnote)
                    Text(entry.details()).font(.caption.monospaced()).textSelection(.enabled)
                    Button("Copy request diagnostics") { model.copyRequest(entry.localId, includeData: false) }
                        .buttonStyle(.borderless)
                    Button("Copy request details (includes data)") { model.copyRequest(entry.localId, includeData: true) }
                        .buttonStyle(.borderless)
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
              let image = CIContext().createCGImage(output, from: output.extent) else { return nil }
        return UIImage(cgImage: image)
    }
}
