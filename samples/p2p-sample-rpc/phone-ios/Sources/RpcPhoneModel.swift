import Combine
import Foundation
import P2pKitRpcExample
import UIKit

/// Detected Wi-Fi is only a suggestion; network use and peer approval still require explicit local actions.
@MainActor
final class RpcPhoneModel: ObservableObject {
    struct StartProblem: Identifiable {
        let id = UUID()
        let message: String
    }

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
    private let wifi: RpcPhoneWifiObserving
    private var wifiGeneration: UUID?
    private var approvedWifi: RpcPhoneWifiNetwork?
    private let invitationClipboard: RpcPhoneInvitationClipboard
    private let shareWindow: RpcPhoneShareWindow

    @Published private(set) var wifiObservation: RpcPhoneWifiObservation = .checking
    @Published private(set) var manualNetworkSetup = false
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
    @Published var startProblem: StartProblem?

    init(wifi: RpcPhoneWifiObserving? = nil, invitationClipboard: RpcPhoneInvitationClipboard? = nil,
         shareWindow: RpcPhoneShareWindow? = nil) {
        self.shareWindow = shareWindow ?? RpcPhoneShareWindow()
        self.wifi = wifi ?? RpcPhoneWifiObserver()
        self.invitationClipboard = invitationClipboard ?? RpcPhoneInvitationClipboard()
        changes = owner.$phase.sink { [weak self] phase in
            self?.objectWillChange.send()
            // Only this foreground lab's active role prevents idle sleep; no background entitlement is requested.
            UIApplication.shared.isIdleTimerDisabled = phase == .running
        }
    }

    var canStart: Bool { foreground && !owner.hasOwner && retirement == nil && !actionBusy }
    var canAct: Bool { foreground && owner.phase == .running && !actionBusy && !operationBusy }
    var canCopyInvitation: Bool { canAct && hostRole && !invitation.isEmpty && invitationClipboard.hasLiveInvitation }
    var fingerprint: String { owner.runtime?.fingerprint ?? "" }
    var compiledSource: String { RpcPhoneIos.shared.compiledSource }
    var detectedWifi: RpcPhoneWifiNetwork? { wifiObservation.network }
    var wifiChecked: Bool { wifiObservation != .checking }
    var canRefreshWifi: Bool { canStart && !manualNetworkSetup && mobileConfig == nil }
    var canConfirmWifi: Bool { canRefreshWifi && detectedWifi != nil && !wifiApproved }
    var wifiApproved: Bool {
        guard let network = approvedWifi else { return false }
        return network == detectedWifi && !manualNetworkSetup && subnets == network.subnet &&
            interfaceName == network.interfaceName && localAddress == network.localAddress
    }

    var wifiExplanation: String {
        if !foreground { return "Keep this app open in the foreground to check or confirm Wi-Fi." }
        if manualNetworkSetup { return "Manual network settings are selected under Advanced." }
        if mobileConfig != nil { return "Clear the loaded USB session before using automatic Wi-Fi setup." }
        if owner.phase == .cleanupPending { return "RPC cleanup is pending. Tap Stop to retry before changing Wi-Fi." }
        if retirement != nil || owner.phase == .stopping { return "Wait for RPC cleanup before changing Wi-Fi." }
        if actionBusy || owner.phase == .starting { return "RPC is starting. Wi-Fi settings cannot change during startup." }
        if owner.hasOwner { return "Stop the active RPC role before checking or confirming Wi-Fi again." }
        if wifiApproved { return "Wi-Fi is already confirmed. Choose Start host or Start client." }
        return wifiObservation.explanation
    }

    func setForeground(_ active: Bool) {
        guard foreground != active else { return }
        foreground = active
        if active {
            if shareWindow.pending {
                let resumed = shareWindow.resume()
                if resumed {
                    // Keep the existing monitor, but synchronously revalidate before exposing actions.
                    receiveWifi(wifi.currentObservation())
                    status = owner.phase == .running ? "Returned to the same RPC role. Continue pairing." : status
                } else { startWifiObservation() }
            } else { startWifiObservation() }
            UIApplication.shared.isIdleTimerDisabled = owner.phase == .running
        } else {
            UIApplication.shared.isIdleTimerDisabled = false
            revealInvitation = false // Conceal secrets in the app switcher; preserve only the bounded transfer state.
            if UIApplication.shared.isProtectedDataAvailable, !manualNetworkSetup, wifiApproved,
               RpcPhoneShareWindow.eligible(running: owner.phase == .running, actionBusy: actionBusy,
                operationBusy: operationBusy, cleanupPending: retirement != nil,
                capacitySession: mobileConfig != nil || !capacityPins.isEmpty || approveImport),
               shareWindow.leave(expired: { [weak self] in self?.expireAppSwitch() }) {
                status = "Return within 25 seconds to keep this role. iOS may end background time sooner."
            } else { expireAppSwitch() }
        }
        objectWillChange.send()
    }

    func protectedDataUnavailable() { expireAppSwitch() }

    private func expireAppSwitch() {
        shareWindow.cancel()
        wifiGeneration = nil
        wifi.stop()
        clearWifiApproval()
        wifiObservation = .checking
        invitation = ""
        revealInvitation = false
        invitationClipboard.retire()
        capacityPins = ""
        approveImport = false
        if owner.hasOwner || actionBusy || operationBusy { stop() }
    }

    private func startWifiObservation() {
        let token = UUID()
        wifiGeneration = token
        wifi.start { [weak self] observation in
            guard let self, (self.foreground || self.shareWindow.pending), self.wifiGeneration == token else { return }
            self.receiveWifi(observation)
        }
    }

    /// A passive re-read only. Do not simulate backgrounding or clear unrelated pairing/capacity input.
    func refreshWifi() {
        guard canRefreshWifi else { return }
        wifiGeneration = nil
        wifi.stop()
        clearWifiApproval()
        wifiObservation = .checking
        startProblem = nil
        status = "Rechecking Wi-Fi. Confirm it again before choosing a role; nothing has started."
        startWifiObservation()
    }

    func setManualNetworkSetup(_ manual: Bool) {
        guard canStart, mobileConfig == nil, manual != manualNetworkSetup else { return }
        clearWifiApproval()
        manualNetworkSetup = manual
        // A mode change must not turn a previous suggestion into manual approval, or vice versa.
        subnets = ""
        interfaceName = ""
        localAddress = ""
    }

    func confirmWifi() {
        guard canStart, !manualNetworkSetup, mobileConfig == nil else { return }
        let current = wifi.currentObservation()
        guard let network = detectedWifi, current.network == network else {
            receiveWifi(current)
            presentStartProblem("Wi-Fi changed or is unavailable. Review the detected Wi-Fi and try again. " +
                "No role was started.")
            return
        }
        receiveWifi(current)
        approvedWifi = network
        subnets = network.subnet
        interfaceName = network.interfaceName
        localAddress = network.localAddress
        startProblem = nil
        status = "Wi-Fi confirmed. Choose Start host or Start client; nothing has started yet."
    }

    private func clearWifiApproval() {
        approvedWifi = nil
        if !manualNetworkSetup {
            subnets = ""
            interfaceName = ""
            localAddress = ""
        }
    }

    private func receiveWifi(_ observation: RpcPhoneWifiObservation) {
        if let approvedWifi, observation.network != approvedWifi {
            clearWifiApproval()
            if owner.hasOwner || actionBusy || operationBusy { stop() }
            status = "Wi-Fi changed. Confirm the current Wi-Fi before starting again."
        }
        wifiObservation = observation
    }

    func start(host: Bool) {
        guard canStart else { return }
        startProblem = nil
        if !manualNetworkSetup {
            // Re-read both the default path and addresses at the tap, not just an earlier monitor callback.
            receiveWifi(wifi.currentObservation())
            guard let network = approvedWifi, network == detectedWifi, subnets == network.subnet,
                  interfaceName == network.interfaceName, localAddress == network.localAddress else {
                presentStartProblem("Tap Use this Wi-Fi to confirm your detected network, then choose a role. " +
                    "If Wi-Fi cannot be detected safely, Advanced offers manual setup. No role was started.")
                return
            }
        }
        let required = [("approved private CIDRs", subnets), ("Wi-Fi interface", interfaceName),
                        ("this iPhone's numeric LAN address", localAddress)]
        let missing = required.filter { $0.1.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty }.map { $0.0 }
        guard missing.isEmpty else {
            presentStartProblem("Invalid setup. Fill in \(missing.joined(separator: ", ")) under " +
                "Advanced → Manual network settings, then try again. No role was started.")
            return
        }
        guard let number = Int32(port), (1024...65535).contains(number) else {
            presentStartProblem("Invalid setup. Enter a fixed host port from 1024 to 65535. No role was started.")
            return
        }
        guard capacityPins.isEmpty || (host && approveImport) else {
            presentStartProblem(host
                ? "Capacity pins are optional. Clear them for ordinary pairing, or explicitly approve the test import."
                : "A client cannot import host capacity pins. Clear the optional capacity pins before creating a client.")
            return
        }
        do {
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
                guard self.foreground, self.retirement == nil else { return }
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
                case .failed(let error): self.presentStartProblem(self.safeError(error))
                case .superseded, .refused: break
                }
            }
        } catch { presentStartProblem(safeError(error)) }
    }

    private func presentStartProblem(_ message: String) {
        status = message
        startProblem = StartProblem(message: message)
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
            setManualNetworkSetup(true)
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
        shareWindow.cancel()
        guard retirement == nil else { return }
        owner.invalidate()
        cancelOperation()
        let outstanding = action
        let monitor = mobileMonitor
        monitor?.cancel()
        invitation = ""
        revealInvitation = false
        invitationClipboard.retire()
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

    private enum ActionResult { case message(String), invitation(String, TimeInterval) }

    private func runAction(_ work: @escaping (RpcPhoneLab) async throws -> ActionResult) {
        guard canAct, let lab = owner.runtime else { return }
        actionBusy = true
        // Retain the in-flight action; the later expiry callback must not retain the model.
        action = Task { @MainActor [self] in
            defer { self.actionBusy = false }
            do {
                let result = try await work(lab)
                guard self.owner.accepts(lab), self.foreground else { return }
                switch result {
                case .message(let text): self.status = text
                case .invitation(let text, let started):
                    self.invitation = text
                    self.revealInvitation = false
                    self.invitationClipboard.minted(text, started: started) { [weak self] in
                        self?.invitation = ""
                        self?.revealInvitation = false
                    }
                }
            } catch {
                if self.owner.accepts(lab) { self.report(error) }
            }
        }
    }

    func createInvitation() {
        guard canAct, hostRole else { return }
        let started = invitationClipboard.beginMinting()
        invitation = ""
        revealInvitation = false
        runAction { .invitation(try await $0.invitation(), started) }
    }

    func copyInvitation() {
        guard canCopyInvitation else { return }
        status = invitationClipboard.copy()
            ? "Invitation copied on this iPhone. You may switch apps briefly; return within 25 seconds."
            : "Invitation expired or copy unavailable. Create a new invitation."
    }

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
