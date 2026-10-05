import CoreImage.CIFilterBuiltins
import SwiftUI

@main
struct RpcPhoneApp: App {
    @Environment(\.scenePhase) private var scenePhase
    @StateObject private var model = RpcPhoneModel()

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
        }
    }
}

struct RpcPhoneView: View {
    @ObservedObject var model: RpcPhoneModel
    @State private var showAdvanced = false

    var body: some View {
        NavigationView {
            Form {
                Section("Try RPC on your Wi-Fi") {
                    Text("Confirm your Wi-Fi, then choose a role. Keep this app open while testing.")
                    Text(model.status).accessibilityIdentifier("rpc.status")
                    Text("Synthetic tests only; no capacity qualification.").font(.footnote)
                }
                wifiControls
                Section("Choose a role") {
                    Text(model.status).accessibilityIdentifier("rpc.roleStatus")
                    Button("Start host") { model.start(host: true) }
                        .disabled(!model.canStart).accessibilityIdentifier("rpc.host")
                    Button("Start client") { model.start(host: false) }
                        .disabled(!model.canStart).accessibilityIdentifier("rpc.client")
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
                    if model.hostRole {
                        if model.mobileConfig == nil { hostControls }
                    } else { clientControls }
                }
                advancedControls
            }
            .navigationTitle("P2pKit RPC")
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

    private var wifiControls: some View {
        Section("Wi-Fi — no typing needed") {
            if model.manualNetworkSetup {
                Text("Manual network settings selected. Review them under Advanced.")
            } else {
                if let network = model.detectedWifi {
                    Text("This iPhone: \(network.localAddress)").font(.callout.monospaced())
                    Text("Private network: \(network.subnet) · \(network.interfaceName)").font(.caption.monospaced())
                }
                Text(model.wifiExplanation).accessibilityIdentifier("rpc.wifiStatus")
                Text("Confirm only a network you own or are authorized to test. This does not approve any peer.")
                    .font(.footnote)
                Button(model.wifiApproved ? "Wi-Fi confirmed" : "Use this Wi-Fi") { model.confirmWifi() }
                    .buttonStyle(.borderless)
                    .disabled(!model.canConfirmWifi)
                    .accessibilityIdentifier("rpc.confirmWifi")
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
                Text("No discovery, mesh or business data. Wi-Fi detection does not prove multicast or peer connectivity.")
                    .font(.footnote)
            }
        }
    }

    private var hostControls: some View {
        Section("Local administrator approval") {
            Button("Create one-use, two-minute invitation") { model.createInvitation() }.disabled(!model.canAct)
            Toggle("Reveal on this trusted local display", isOn: $model.revealInvitation)
            Text("Never share invitations through cloud chat, screenshots, logs or general-purpose clipboard sync.")
            if model.revealInvitation, !model.invitation.isEmpty {
                if let qr = qrImage(model.invitation) {
                    Image(uiImage: qr).interpolation(.none).resizable().scaledToFit()
                        .accessibilityLabel("Local single-use pairing invitation")
                }
                Text(model.invitation).font(.caption.monospaced())
            }
            Button("Copy invitation") { model.copyInvitation() }
                .buttonStyle(.borderless)
                .disabled(!model.canAct || !model.revealInvitation || model.invitation.isEmpty)
                .accessibilityIdentifier("rpc.copyInvitation")
            Text("Copy stays on this iPhone and expires with the invitation. Leaving this app stops the host " +
                "and invalidates the invitation; do not switch to cloud chat to send it.").font(.footnote)
            ForEach(model.pending, id: \.requestId) { request in
                Text("Verify locally: \(request.fingerprint)")
                Button("Approve this exact client") { model.approve(request) }.disabled(!model.canAct)
            }
        }
    }

    private var clientControls: some View {
        Section("One explicitly selected trusted host") {
            SecureField("Invitation obtained through a trusted local channel", text: $model.invitation)
                .textInputAutocapitalization(.never).autocorrectionDisabled()
                .onChange(of: model.invitation) { if $0.count > 512 { model.invitation = String($0.prefix(512)) } }
            Button("Pair and connect; wait for host approval") { model.connect(pair: true) }.disabled(!model.canAct)
            Button("Send test message (1 KiB echo)") { model.echo(large: false) }.disabled(!model.canAct)
            DisclosureGroup("Reconnect or run a larger test") {
                field("Already trusted host's full fingerprint", $model.hostPin, limit: 64, id: "rpc.hostPin")
                field("Already trusted host's numeric address", $model.hostAddress, limit: 64, id: "rpc.hostAddress")
                Button("Connect using the same durable pin") { model.connect(pair: false) }.disabled(!model.canAct)
                Button("20 × 1 MiB echoes; concurrency two") { model.echo(large: true) }.disabled(!model.canAct)
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
