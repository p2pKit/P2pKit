import P2pKitRpcExample
import SwiftUI

/// Local identity view. Dismissing a sheet (including interactive swipe) cannot approve, select or revoke.
struct RpcPhoneNearbyView: View {
    @ObservedObject var model: RpcPhoneModel
    @State private var dialog: Decision?
    @State private var lastOfferedRequest: String?

    private struct Decision: Identifiable {
        let id = UUID()
        let owner: RpcPhoneLab
        var host: RpcNearbyHost?
        var request: RpcPhonePairing?
        var revoke: String?
    }

    var body: some View {
        Section(model.hostRole ? "Advertising and approval" : "Nearby hosts") {
            Text("Network activity: \(model.networkActivity)")
            if let connection = model.discoveryConnection {
                Text("Connection: \(connection.state.name); retry delay: \(connection.nextRetryMillis) ms")
                if let failure = connection.failure { Text("Connection issue: \(failure)") }
                if let guidance = connection.approvalGuidance { Text(guidance) }
                if let pin = connection.selectedFingerprint { Text("Selected host: \(pin)").textSelection(.enabled) }
            }
            if model.hostRole {
                Text("Pending approvals: \(model.pending.count)")
                ForEach(model.pending, id: \.requestId) { request in
                    Button("Review \(request.fingerprint)") {
                        if let owner = model.owner.runtime { dialog = Decision(owner: owner, request: request) }
                    }.buttonStyle(.borderless).disabled(!model.canAct)
                }
            } else {
                Text("Names and discovery presence are unverified. Select the intended fingerprint, not the first host.")
                    .font(.footnote)
                if model.nearbyHosts.isEmpty { Text("No current host records.") }
                ForEach(Array(model.nearbyHosts.enumerated()), id: \.offset) { _, host in
                    VStack(alignment: .leading) {
                        Text("\(host.name) · \(host.platform) · \(host.trusted ? "Trusted identity" : "Untrusted")")
                        Text(host.fingerprint).font(.caption.monospaced()).textSelection(.enabled)
                        Button(host.selectionLabel(connection: model.discoveryConnection)) {
                            if let owner = model.owner.runtime { dialog = Decision(owner: owner, host: host) }
                        }.buttonStyle(.borderless).disabled(!model.canAct)
                    }
                }
            }
        }
        Section("Trusted devices") {
            if model.trustedDevices.isEmpty { Text("No saved approvals for this role.") }
            ForEach(model.trustedDevices, id: \.fingerprint) { device in
                VStack(alignment: .leading) {
                    Text("\(device.name) · \(device.presence)")
                    Text(device.fingerprint).font(.caption.monospaced()).textSelection(.enabled)
                    Button("Revoke / Forget device", role: .destructive) {
                        if let owner = model.owner.runtime { dialog = Decision(owner: owner, revoke: device.fingerprint) }
                    }.buttonStyle(.borderless).disabled(!model.canAct)
                }
            }
        }
        .onAppear { offerPending() }
        .onChange(of: model.pending.map(\.requestId)) { _ in offerPending() }
        .sheet(item: $dialog) { decision in
            NavigationView {
                Form {
                    if let host = decision.host {
                        Text("\(host.name) · \(host.platform)")
                        Text(host.fingerprint).font(.caption.monospaced()).textSelection(.enabled)
                        Text("Discovery names can be spoofed. Compare the full fingerprint on the other device. " +
                            "Without comparison this is trust on first use. The host must also approve your identity.")
                        Button(host.selectionLabel(connection: model.discoveryConnection)) {
                            model.selectNearby(host, expected: decision.owner)
                            dialog = nil
                        }.disabled(!eligible(decision) || model.nearbyHosts.filter {
                            $0.fingerprint == host.fingerprint
                        }.count != 1)
                    }
                    if let request = decision.request {
                        Text("Authenticated client fingerprint: \(request.fingerprint)").font(.caption.monospaced())
                            .textSelection(.enabled)
                        Text("Origin: \(request.origin). Compare with the client display. " +
                            "Approval saves this identity, not a device name or address.")
                        Button("Approve exact identity") {
                            model.decideNearby(request, approve: true, expected: decision.owner)
                            dialog = nil
                        }.disabled(!current(request, decision))
                        Button("Reject", role: .destructive) {
                            model.decideNearby(request, approve: false, expected: decision.owner)
                            dialog = nil
                        }.disabled(!current(request, decision))
                    }
                    if let pin = decision.revoke {
                        Text(pin).font(.caption.monospaced()).textSelection(.enabled)
                        Text("Disconnect and revoke trust. Future connections require fresh approval.")
                        Button("Revoke", role: .destructive) {
                            model.forgetNearby(pin, expected: decision.owner)
                            dialog = nil
                        }.disabled(!eligible(decision) || !model.trustedDevices.contains { $0.fingerprint == pin })
                    }
                }
                .navigationTitle("Verify identity")
                .toolbar { ToolbarItem(placement: .cancellationAction) { Button("Cancel") { dialog = nil } } }
            }.navigationViewStyle(.stack)
        }
    }

    private func eligible(_ decision: Decision) -> Bool { model.canAct && model.owner.accepts(decision.owner) }

    private func current(_ request: RpcPhonePairing, _ decision: Decision) -> Bool {
        eligible(decision) && model.pending.contains {
            $0.requestId == request.requestId && $0.fingerprint == request.fingerprint
        }
    }

    private func offerPending() {
        guard dialog == nil, let owner = model.owner.runtime,
              let request = model.pending.first(where: { $0.requestId != lastOfferedRequest }) else { return }
        lastOfferedRequest = request.requestId // One bounded marker, not an ever-growing history of dismissed pins.
        dialog = Decision(owner: owner, request: request)
    }
}
