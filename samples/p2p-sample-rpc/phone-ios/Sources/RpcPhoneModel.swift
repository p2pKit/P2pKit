import Combine
import Foundation
import P2pKitRpcExample
import UIKit

/// No launch-argument/URL configuration, payload logs, clipboard export or automatic network selection.
@MainActor
final class RpcPhoneModel: ObservableObject {
    let owner = RpcPhoneRunOwner<RpcPhoneLab>()
    private var changes: AnyCancellable?
    private var action: Task<Void, Never>?
    private var retirement: Task<Void, Never>?
    private var operation: RpcPhoneOperation?
    private var operationID: UUID?
    private var foreground = false

    @Published var subnets = ""
    @Published var interfaceName = ""
    @Published var localAddress = ""
    @Published var port = "48123"
    @Published var hostAddress = ""
    @Published var hostPin = ""
    @Published var invitation = ""
    @Published var revealInvitation = false
    @Published var capacityPins = ""
    @Published var approveImport = false
    @Published private(set) var hostRole = false
    @Published private(set) var actionBusy = false
    @Published private(set) var operationBusy = false
    @Published private(set) var status = "Stopped. Synthetic tests only; no capacity qualification."
    @Published private(set) var pending: [RpcPhonePairing] = []

    init() {
        changes = owner.$phase.sink { [weak self] phase in
            self?.objectWillChange.send()
            // Only this foreground lab's active role prevents idle sleep; no background entitlement is requested.
            UIApplication.shared.isIdleTimerDisabled = phase == .running
        }
    }

    var canStart: Bool { foreground && !owner.hasOwner && retirement == nil && !actionBusy }
    var canAct: Bool { foreground && owner.phase == .running && !actionBusy && !operationBusy }
    var fingerprint: String { owner.runtime?.fingerprint ?? "" }

    func setForeground(_ active: Bool) {
        foreground = active
        if !active {
            invitation = ""
            revealInvitation = false
            capacityPins = ""
            approveImport = false
            if owner.hasOwner || actionBusy || operationBusy { stop() }
        }
        objectWillChange.send()
    }

    func start(host: Bool) {
        guard canStart else { return }
        do {
            guard let number = Int32(port), capacityPins.isEmpty || (host && approveImport) else {
                status = "Invalid setup or unapproved capacity-pin import."
                return
            }
            // @Throws makes malformed Swift input catchable, not an uncaught Native exception.
            let settings = try RpcPhoneSettings(
                subnets: subnets, interfaceName: interfaceName, localAddress: localAddress, port: number
            )
            let pins = host && approveImport ? capacityPins : ""
            actionBusy = true
            status = "Starting the explicitly selected role…"
            action = Task { @MainActor in
                defer { self.actionBusy = false }
                guard self.foreground else { return }
                let outcome = await self.owner.start(create: {
                    if host {
                        return try await RpcPhoneIos.shared.createHost(
                            settings: settings, explicitlyApprovedCapacityPins: pins
                        )
                    }
                    return try await RpcPhoneIos.shared.createClient(settings: settings)
                }, close: { try await $0.close() })
                switch outcome {
                case .started:
                    self.hostRole = host
                    self.status = host ? "Host started; no discovery or mesh." : "Client created; no host connected."
                case .failed(let error): self.report(error)
                case .superseded, .refused: break
                }
            }
        } catch { report(error) }
    }

    /// Native operations are cancelled explicitly. The Swift factory/action is awaited, not abandoned.
    func stop() {
        guard retirement == nil else { return }
        owner.invalidate()
        cancelOperation()
        let outstanding = action
        invitation = ""
        revealInvitation = false
        pending = []
        retirement = Task { @MainActor in
            await outstanding?.value
            let completed = await self.owner.stop()
            if completed {
                self.operation = nil
                self.operationID = nil
                self.operationBusy = false
            }
            self.status = completed ? "Stopped; owned RPC cleanup completed."
                : "Cleanup failed; owner retained. Retry Stop before starting another role."
            self.action = nil
            self.retirement = nil
        }
    }

    func cancelOperation() {
        operation?.cancel()
        // Native close is the completion barrier. Never infer remote rollback from cancel().
        if operation != nil { status = "Cancellation requested; remote effects may already have happened." }
    }

    func refresh() {
        guard let lab = owner.runtime, !actionBusy else { return }
        do {
            pending = hostRole ? try lab.pending() : []
            status = "\(lab.state); clients=\(lab.connectedClients); " +
                "completed=\(lab.diagnostics.completedCalls); queued=\(lab.diagnostics.queuedCalls)"
        } catch { report(error) }
    }

    private enum ActionResult { case message(String), invitation(String) }

    private func runAction(_ work: @escaping (RpcPhoneLab) async throws -> ActionResult) {
        guard canAct, let lab = owner.runtime else { return }
        actionBusy = true
        action = Task { @MainActor in
            defer { self.actionBusy = false }
            do {
                let result = try await work(lab)
                guard self.owner.accepts(lab), self.foreground else { return }
                switch result {
                case .message(let text): self.status = text
                case .invitation(let text): self.invitation = text; self.revealInvitation = false
                }
            } catch {
                if self.owner.accepts(lab) { self.report(error) }
            }
        }
    }

    func createInvitation() { runAction { .invitation(try await $0.invitation()) } }

    func approve(_ request: RpcPhonePairing) {
        runAction { lab in
            try await lab.approve(requestId: request.requestId)
            return .message("Approved this exact client; refresh pending requests.")
        }
    }

    func revoke() {
        let pin = hostPin
        runAction { lab in
            try await lab.revoke(fingerprint: pin)
            return .message("Revoked the selected peer. This does not undo completed side effects.")
        }
    }

    private func complete(_ lab: RpcPhoneLab, _ id: UUID, _ text: String) {
        guard operationID == id else { return }
        operation = nil
        operationID = nil
        operationBusy = false
        if owner.accepts(lab), foreground { status = text }
    }

    func connect(pair: Bool) {
        guard canAct, let lab = owner.runtime, let number = Int32(port) else { return }
        let id = UUID()
        let callback: (String?) -> Void = { [weak self, lab] error in
            Task { @MainActor in
                self?.complete(lab, id, error ?? "Connected to the explicitly selected, durably pinned host.")
            }
        }
        do {
            operationID = id
            operationBusy = true
            if pair {
                let trusted = invitation
                invitation = ""
                operation = try lab.beginPairAndConnect(qr: trusted, onComplete: callback)
            } else {
                operation = try lab.beginConnect(
                    fingerprint: hostPin, address: hostAddress, port: number, onComplete: callback
                )
            }
        } catch { complete(lab, id, safeError(error)) }
    }

    func echo(large: Bool) {
        guard canAct, let lab = owner.runtime else { return }
        let id = UUID()
        do {
            operationID = id
            operationBusy = true
            operation = try lab.echo(large: large) { [weak self, lab] result in
                let text = "\(result.completed)/\(result.expected) replies; \(result.elapsedMillis) ms; " +
                    "\(result.failureKind ?? "complete"); \(result.executionEvidence ?? "responses received"). " +
                    "Not capacity qualification."
                Task { @MainActor in self?.complete(lab, id, text) }
            }
        } catch { complete(lab, id, safeError(error)) }
    }

    private func safeError(_ error: Error) -> String {
        if let failure = (error as NSError).kotlinException as? RpcFailure {
            return "\(failure.kind.name)/\(failure.phase.name)/\(failure.executionEvidence.name)"
        }
        // Raw localizedDescription, exception text, payloads and pins are never diagnostics.
        return "Invalid setup or local operation failed; no qualification claim."
    }

    private func report(_ error: Error) { status = safeError(error) }
}
