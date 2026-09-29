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

    var body: some View {
        NavigationView {
            Form {
                Section("Synthetic lab — not capacity qualification") {
                    Text("Foreground only. One explicitly selected host. No discovery, mesh or business data.")
                    Text(model.status).accessibilityIdentifier("rpc.status")
                    if !model.fingerprint.isEmpty { Text("Local identity: \(model.fingerprint)") }
                }
                Section("Explicit organization network") {
                    field("Approved private CIDRs, comma-separated", $model.subnets, limit: 512, id: "rpc.subnets")
                    field("Wi-Fi interface, for example en0", $model.interfaceName, limit: 32, id: "rpc.interface")
                    field("This device's numeric LAN address", $model.localAddress, limit: 64, id: "rpc.local")
                    field("Fixed host port", $model.port, limit: 5, id: "rpc.port")
                }.disabled(model.owner.hasOwner)
                Section("Optional capacity-test provisioning") {
                    field("Exactly 128 public synthetic client pins", $model.capacityPins, limit: 8192, id: "rpc.pins")
                    Toggle("I approve replacing this test host's client pins", isOn: $model.approveImport)
                }.disabled(model.owner.hasOwner)
                Section("Role and lifecycle") {
                    Button("Start host") { model.start(host: true) }
                        .disabled(!model.canStart).accessibilityIdentifier("rpc.host")
                    Button("Create client") { model.start(host: false) }
                        .disabled(!model.canStart).accessibilityIdentifier("rpc.client")
                    Button("Stop and await cleanup") { model.stop() }
                        .disabled(!model.owner.hasOwner).accessibilityIdentifier("rpc.stop")
                    Button("Cancel active operation (not rollback)") { model.cancelOperation() }
                        .disabled(!model.operationBusy)
                    Button("Refresh state / pending approvals") { model.refresh() }
                        .disabled(model.owner.phase != .running)
                }
                if model.owner.phase == .running {
                    if model.hostRole { hostControls } else { clientControls }
                    Section("Live revocation") {
                        field("Exact peer pin to revoke", $model.hostPin, limit: 64, id: "rpc.revokePin")
                        Button("Revoke this exact peer") { model.revoke() }.disabled(!model.canAct)
                    }
                }
            }
            .navigationTitle("P2pKit RPC Lab")
        }.navigationViewStyle(.stack)
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
            field("Already trusted host's full fingerprint", $model.hostPin, limit: 64, id: "rpc.hostPin")
            field("Already trusted host's numeric address", $model.hostAddress, limit: 64, id: "rpc.hostAddress")
            Button("Connect using the same durable pin") { model.connect(pair: false) }.disabled(!model.canAct)
            Button("One 1 KiB echo") { model.echo(large: false) }.disabled(!model.canAct)
            Button("20 × 1 MiB echoes; concurrency two") { model.echo(large: true) }.disabled(!model.canAct)
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
