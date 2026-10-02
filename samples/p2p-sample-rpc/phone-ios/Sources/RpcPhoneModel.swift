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
    private var mobileFiles: RpcPhoneCapacityFiles?
    private var mobileMonitor: Task<Void, Never>?
    private var mobileFailed = false
    private var mobileStopRequested = false

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
    @Published var usbRunLabel = ""
    @Published private(set) var mobileConfig: RpcMobileCapacityConfig?
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
    var compiledSource: String { RpcPhoneIos.shared.compiledSource }

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
            let mobile = mobileConfig
            if let mobile {
                guard host, approveImport, pins == mobile.clientPins,
                      subnets == mobile.settings.subnets, interfaceName == mobile.settings.interfaceName,
                      localAddress == mobile.settings.localAddress, number == mobile.settings.port else {
                    throw RpcPhoneCapacityIOError.invalidRecord
                }
            }
            actionBusy = true
            status = "Starting the explicitly selected role…"
            action = Task { @MainActor in
                defer { self.actionBusy = false }
                guard self.foreground else { return }
                let outcome = await self.owner.start(create: {
                    if let mobile { return try await RpcPhoneIos.shared.createCapacityHost(config: mobile) }
                    if host {
                        return try await RpcPhoneIos.shared.createHost(
                            settings: settings, explicitlyApprovedCapacityPins: pins
                        )
                    }
                    return try await RpcPhoneIos.shared.createClient(settings: settings)
                }, close: { lab in
                    try await lab.close()
                    if mobile != nil, let files = self.mobileFiles {
                        let record = try lab.mobileClosedRecord(
                            controlHealthy: !self.mobileFailed && self.mobileStopRequested
                        )
                        // Retrying Stop may verify identical evidence; it may never replace an earlier outcome.
                        if let previous = try files.read("closed.txt", optional: true) {
                            guard previous == record else { throw RpcPhoneCapacityIOError.invalidRecord }
                        } else { try files.publish("closed.txt", record) }
                    }
                })
                switch outcome {
                case .started:
                    self.hostRole = host
                    self.status = host ? "Host started; no discovery or mesh." : "Client created; no host connected."
                    if mobile != nil, let lab = self.owner.runtime, let files = self.mobileFiles {
                        self.monitorMobile(lab, files: files)
                    }
                case .failed(let error): self.report(error)
                case .superseded, .refused: break
                }
            }
        } catch { report(error) }
    }

    /// Explicit local reservation only. Never replace an old run or start RPC from USB input.
    func prepareMobile() {
        guard canStart, mobileConfig == nil else { return }
        do {
            let files = try RpcPhoneCapacityFiles(runLabel: usbRunLabel, requireNew: true)
            let artifact = try RpcPhoneProcessSampler.installedArtifact()
            try files.publish("prepared.txt", "schema=1\nscope=ios-usb-slot\nrunLabel=\(usbRunLabel)\n" +
                "sourceSha=\(compiledSource)\nartifactSha256=\(artifact)\n")
            status = "New private USB slot prepared. Wait for the coordinator, then load and review; RPC is stopped."
        } catch { report(error) }
    }

    /// USB loading does not authorize trust or start a listener. Local approval of the visible values is still required.
    func loadMobile() {
        guard canStart, mobileConfig == nil else { return }
        do {
            let files = try RpcPhoneCapacityFiles(runLabel: usbRunLabel)
            guard let input = try files.read("inbox.txt") else { throw RpcPhoneCapacityIOError.invalidRecord }
            let config = try RpcPhoneIos.shared.parseCapacityConfig(text: input)
            guard config.hostPlatform == "Ios", config.hostSourceSha == compiledSource,
                  config.runLabel == usbRunLabel,
                  config.hostArtifactSha256 == (try RpcPhoneProcessSampler.installedArtifact()) else {
                throw RpcPhoneCapacityIOError.invalidRecord
            }
            subnets = config.settings.subnets
            interfaceName = config.settings.interfaceName
            localAddress = config.settings.localAddress
            port = String(config.settings.port)
            capacityPins = config.clientPins
            approveImport = false
            mobileFiles = files
            mobileConfig = config
            mobileFailed = false
            mobileStopRequested = false
            status = "Review this USB run's network and 128 pins. Approval includes its exact Stop request and pin cleanup."
        } catch { report(error) }
    }

    func clearMobile() {
        guard canStart else { return }
        mobileConfig = nil
        mobileFiles = nil
        capacityPins = ""
        approveImport = false
    }

    private func monitorMobile(_ lab: RpcPhoneLab, files: RpcPhoneCapacityFiles) {
        guard mobileMonitor == nil else { mobileFailed = true; stop(); return }
        mobileMonitor = Task { @MainActor in
            do {
                try files.publish("ready.txt", try await lab.mobileReadyRecord(
                    observedArtifactSha256: RpcPhoneProcessSampler.installedArtifact()
                ))
                let started = ProcessInfo.processInfo.systemUptime
                while !Task.isCancelled {
                    guard ProcessInfo.processInfo.systemUptime - started < 2_400 else {
                        throw RpcPhoneCapacityIOError.resourceObservation
                    }
                    try files.publish("telemetry.txt", lab.mobileTelemetry(resources: RpcPhoneProcessSampler.sample()))
                    if let input = try files.read("stop.txt", optional: true) {
                        guard try lab.mobileStopMatches(record: input) else { throw RpcPhoneCapacityIOError.invalidRecord }
                        self.mobileStopRequested = true
                        break
                    }
                    try await Task.sleep(nanoseconds: 1_000_000_000)
                }
                if !Task.isCancelled, self.owner.accepts(lab) { self.stop() }
            } catch is CancellationError {
                // The retained Stop task below awaits this task and the actual Kotlin close.
            } catch {
                self.mobileFailed = true
                do { try files.publish("failed.txt", "failed=true\nphase=mobile-control\n") }
                catch { self.status = "USB evidence failed; capacity remains unqualified." }
                if self.owner.accepts(lab) { self.stop() }
            }
        }
    }

    /// Native operations are cancelled explicitly. The Swift factory/action is awaited, not abandoned.
    func stop() {
        guard retirement == nil else { return }
        owner.invalidate()
        cancelOperation()
        let outstanding = action
        let monitor = mobileMonitor
        monitor?.cancel()
        invitation = ""
        revealInvitation = false
        pending = []
        retirement = Task { @MainActor in
            await outstanding?.value
            await monitor?.value
            self.mobileMonitor = nil
            let completed = await self.owner.stop()
            if completed {
                self.operation = nil
                self.operationID = nil
                self.operationBusy = false
            }
            if !completed, self.mobileFiles != nil { self.mobileFailed = true }
            self.status = completed ? (self.mobileFailed ? "Stopped; mobile control failed, no qualification."
                : "Stopped; owned RPC cleanup completed.")
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
            pending = hostRole && mobileConfig == nil ? try lab.pending() : []
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
