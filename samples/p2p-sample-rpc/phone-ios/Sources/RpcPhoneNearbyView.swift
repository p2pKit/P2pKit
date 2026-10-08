import P2pKitRpcExample
import SwiftUI

/// Local identity view. Dismissing a sheet (including interactive swipe) cannot approve, select or revoke.
struct RpcPhoneNearbyView: View {
    @ObservedObject var model: RpcPhoneModel
    @ObservedObject var presentation: RpcPhoneDecisionPresentation

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
                        if let owner = model.owner.runtime {
                            presentation.dialog = RpcPhoneDecisionPresentation.Decision(owner: owner, request: request)
                        }
                    }.buttonStyle(.borderless).disabled(!model.canAct)
                }
            } else {
                Text(
                    "Names and discovery presence are unverified. Select the intended fingerprint, not the first host."
                )
                .font(.footnote)
                if model.nearbyHosts.isEmpty { Text("No current host records.") }
                ForEach(Array(model.nearbyHosts.enumerated()), id: \.offset) { _, host in
                    VStack(alignment: .leading) {
                        Text("\(host.name) · \(host.platform) · \(host.trusted ? "Trusted identity" : "Untrusted")")
                        Text(host.fingerprint).font(.caption.monospaced()).textSelection(.enabled)
                        Button(host.selectionLabel(connection: model.discoveryConnection)) {
                            if let owner = model.owner.runtime {
                                presentation.dialog = RpcPhoneDecisionPresentation.Decision(owner: owner, host: host)
                            }
                        }.buttonStyle(.borderless).disabled(!model.canAct)
                    }
                }
            }
        }
        Section {
            DisclosureGroup("Trusted devices") {
                if model.trustedDevices.isEmpty { Text("No saved approvals for this role.") }
                ForEach(model.trustedDevices, id: \.fingerprint) { device in
                    VStack(alignment: .leading) {
                        Text("\(device.name) · \(device.presence)")
                        Text(device.fingerprint).font(.caption.monospaced()).textSelection(.enabled)
                        Button("Revoke / Forget device", role: .destructive) {
                            if let owner = model.owner.runtime {
                                presentation.dialog = RpcPhoneDecisionPresentation.Decision(
                                    owner: owner, revoke: device.fingerprint)
                            }
                        }.buttonStyle(.borderless).disabled(!model.canAct)
                    }
                }
            }
        }
    }
}

/// The presenter is owned by the screen, never by a virtualized Form row.
@MainActor
final class RpcPhoneDecisionPresentation: ObservableObject {
    struct Decision: Identifiable {
        let id = UUID()
        let owner: RpcPhoneLab
        var host: RpcNearbyHost?
        var request: RpcPhonePairing?
        var revoke: String?
    }
    @Published var dialog: Decision?
    private weak var observedOwner: RpcPhoneLab?
    private var offers = RpcPhoneApprovalOffers()

    func offerPending(_ model: RpcPhoneModel) {
        guard model.nearbyMode, model.hostRole, let owner = model.owner.runtime else { return }
        if observedOwner !== owner {
            observedOwner = owner
            offers = RpcPhoneApprovalOffers()
        }
        if let id = offers.next(model.pending.map(\.requestId), presenting: dialog != nil),
            let request = model.pending.first(where: { $0.requestId == id })
        {
            dialog = Decision(owner: owner, request: request)
        }
    }
}

/// Only live request IDs are retained. Updates/expiry never dismiss or replace an open decision.
struct RpcPhoneApprovalOffers {
    private(set) var offered: Set<String> = []
    mutating func next(_ pending: [String], presenting: Bool) -> String? {
        offered.formIntersection(pending)
        guard !presenting, let id = pending.first(where: { !offered.contains($0) }) else { return nil }
        offered.insert(id)
        return id
    }
}

struct RpcPhoneDecisionSheet: View {
    @ObservedObject var model: RpcPhoneModel
    @ObservedObject var presentation: RpcPhoneDecisionPresentation
    let decision: RpcPhoneDecisionPresentation.Decision

    var body: some View {
        NavigationView {
            Form {
                if let host = decision.host {
                    Text("\(host.name) · \(host.platform)")
                    Text(host.fingerprint).font(.caption.monospaced()).textSelection(.enabled)
                    Text(
                        "Discovery names can be spoofed. Compare the full fingerprint on the other device. "
                            + "Without comparison this is trust on first use. The host must also approve your identity."
                    )
                    Button(host.selectionLabel(connection: model.discoveryConnection)) {
                        model.selectNearby(host, expected: decision.owner)
                        presentation.dialog = nil
                    }.disabled(
                        !eligible(decision)
                            || model.nearbyHosts.filter {
                                $0.fingerprint == host.fingerprint
                            }.count != 1)
                }
                if let request = decision.request {
                    RpcPhoneApprovalReview(
                        fingerprint: request.fingerprint, origin: request.origin,
                        availability: .check(
                            ownerCurrent: model.owner.accepts(decision.owner),
                            requestCurrent: model.pending.contains {
                                $0.requestId == request.requestId && $0.fingerprint == request.fingerprint
                            }, canAct: model.canAct),
                        approve: {
                            model.decideNearby(request, approve: true, expected: decision.owner)
                            presentation.dialog = nil
                        },
                        reject: {
                            model.decideNearby(request, approve: false, expected: decision.owner)
                            presentation.dialog = nil
                        })
                }
                if let pin = decision.revoke {
                    Text(pin).font(.caption.monospaced()).textSelection(.enabled)
                    Text("Disconnect and revoke trust. Future connections require fresh approval.")
                    Button("Revoke", role: .destructive) {
                        model.forgetNearby(pin, expected: decision.owner)
                        presentation.dialog = nil
                    }.disabled(!eligible(decision) || !model.trustedDevices.contains { $0.fingerprint == pin })
                }
            }
            .navigationTitle("Verify identity")
            .toolbar { ToolbarItem(placement: .cancellationAction) { Button("Close") { presentation.dialog = nil } } }
        }.navigationViewStyle(.stack)
            .overlay {
                if !model.isForeground {
                    Color(.systemBackground).ignoresSafeArea().overlay(Text("RPC app is not active"))
                }
            }
    }

    private func eligible(_ decision: RpcPhoneDecisionPresentation.Decision) -> Bool {
        model.canAct && model.owner.accepts(decision.owner)
    }

}

/// Availability never implies approval; the action boundary independently revalidates the live runtime.
enum RpcPhoneApprovalAvailability: Equatable {
    case ready, busy, expired
    static func check(ownerCurrent: Bool, requestCurrent: Bool, canAct: Bool) -> Self {
        guard ownerCurrent && requestCurrent else { return .expired }
        return canAct ? .ready : .busy
    }
    var message: String {
        switch self {
        case .ready: return "Compare the fingerprint, then approve or reject."
        case .busy: return "The host is busy. Wait for the current operation; no approval was sent."
        case .expired:
            return "This request ended or expired. No approval was sent. Close this sheet; "
                + "the client can request approval again."
        }
    }
}

struct RpcPhoneApprovalReview: View {
    let fingerprint: String
    let origin: String
    let availability: RpcPhoneApprovalAvailability
    let approve: () -> Void
    let reject: () -> Void
    var body: some View {
        Text(availability.message).accessibilityIdentifier("rpc.approvalAvailability")
        Text("Authenticated client fingerprint: \(fingerprint)").font(.caption.monospaced())
            .textSelection(.enabled)
        Text(
            "Origin: \(origin). Compare with the client display. "
                + "Approval saves this identity, not a device name or address.")
        Button("Approve exact identity", action: approve).disabled(availability != .ready)
            .accessibilityIdentifier("rpc.approve")
        Button("Reject", role: .destructive, action: reject).disabled(availability != .ready)
            .accessibilityIdentifier("rpc.reject")
    }
}

extension View {
    /// Attach to a stable screen ancestor, not a lazy/conditional row. Close is always explicit.
    func rpcDecisionSheet<Item: Identifiable, Content: View>(
        item: Binding<Item?>,
        onDismiss: @escaping () -> Void, @ViewBuilder content: @escaping (Item) -> Content
    ) -> some View {
        sheet(item: item, onDismiss: onDismiss) { value in
            content(value).interactiveDismissDisabled()
        }
    }
}

#if DEBUG
    /// Deterministic UI regression fixture only. No runtime, sockets, trust store or peer approval actions.
    struct RpcPhoneApprovalPresentationProbe: View {
        private struct Item: Identifiable { let id = UUID() }
        @State private var item: Item?
        @State private var ticks = 0
        @State private var availability = RpcPhoneApprovalAvailability.ready
        @State private var decisions = 0
        var body: some View {
            NavigationView {
                Form {
                    Text("Synthetic approval UI — no RPC").accessibilityIdentifier("rpc.synthetic")
                    Button("Show synthetic approval") { item = Item() }
                    ForEach(0..<60) { i in Text("Live row \(i) · update \(ticks)") }
                }
            }
            .rpcDecisionSheet(item: $item, onDismiss: {}) { _ in
                NavigationView {
                    Form {
                        Text("Updates: \(ticks)").accessibilityIdentifier("rpc.syntheticTicks")
                        RpcPhoneApprovalReview(
                            fingerprint: String(repeating: "a", count: 64), origin: "Synthetic UI only",
                            availability: availability, approve: { decisions += 1 }, reject: { decisions += 1 })
                        Button("Expire synthetic request") { availability = .expired }
                        Text("Decisions: \(decisions)").accessibilityIdentifier("rpc.syntheticDecisions")
                    }
                    .navigationTitle("Verify identity")
                    .toolbar { ToolbarItem(placement: .cancellationAction) { Button("Close") { item = nil } } }
                }
            }
            .task {
                while !Task.isCancelled {
                    do { try await Task.sleep(nanoseconds: 100_000_000) } catch { return }
                    ticks += 1
                }
            }
        }
    }
#endif
