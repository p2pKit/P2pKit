import Foundation
import Network

/// Diagnostic only: two fixed CLI policies share this exact probe and producer.
/// No endpoint, service name, token, path, or free-form error enters its result.
final class LanProbe {
    enum DescriptorPolicy: String, Encodable { case bonjour = "BONJOUR", withTXT = "WITH_TXT" }
    private enum Transport: String, Encodable { case unobserved, none, tcp, other }

    private enum Phase { case idle, observing, cancelling, finished }
    private enum State: String, Encodable {
        case none, setup, waiting, ready, failed, cancelled, unknown
    }
    private enum ErrorDomain: String, Encodable { case none, dns, posix, tls, other }
    private enum Outcome: String, Encodable {
        case discovered, notDiscovered, setupFailed, cleanupUnconfirmed, counterOverflow, timingInvalid
    }
    private struct ErrorObservation: Encodable {
        var domain: ErrorDomain = .none
        var code: Int32 = 0

        init(_ error: Error? = nil) {
            guard let error = error else { return }
            guard let networkError = error as? NWError else { domain = .other; return }
            switch networkError {
            case .dns(let value): domain = .dns; code = value
            case .posix(let value): domain = .posix; code = value.rawValue
            case .tls(let value): domain = .tls; code = value
            // Non-DNS/POSIX/TLS cases, including SDK26 Wi-Fi Aware, keep other/zero.
            default: domain = .other
            }
        }
    }
    private struct ConfigurationObservation: Encodable {
        var listenerObserved = false
        var listenerTransport: Transport = .unobserved
        var listenerNoDelay = false
        var listenerP2P = false
        var listenerCellBan = false
        var browserObserved = false
        var browserTransport: Transport = .unobserved
        var browserP2P = false
        var browserCellBan = false
        var browserIncludesTXT = false
        var advertisementAfterReady = false
        var noAutoRename = false
        var configuredServiceTxtPresent = false
        var configuredServiceTxtReadbackMatches = false
        var configuredServiceTxtShapeValid = false
    }
    private struct PeerObservation: Encodable {
        var configuration = ConfigurationObservation()
        var listenerReady = 0
        var listenerWaiting = 0
        var listenerFailed = 0
        var browserReady = 0
        var browserWaiting = 0
        var browserFailed = 0
        var registrationAdded = 0
        var registrationRemoved = 0
        var resultCallbacks = 0
        var maximumResultCount = 0
        var unexpectedConnections = 0
        var listenerLastState: State = .none
        var browserLastState: State = .none
        var listenerCancelled = false
        var browserCancelled = false
        var ownRegistrationObserved = false
        var registrationNameChanged = false
        var expectedPeerObserved = false
        var listenerError = ErrorObservation()
        var browserError = ErrorObservation()
    }
    private final class Peer {
        var listener: NWListener?
        var browser: NWBrowser?
        var observation = PeerObservation()
        var advertisementAttempted = false
    }
    private struct PackagingObservation: Encodable {
        let readOK: Bool
        let usageDescriptionPresent: Bool
        let requiredBonjourPresent: Bool
        let bundleIdentifierPresent: Bool
        let expectedBundleIdentifier: Bool
        let applicationPackageType: Bool

        init() {
            let bundle = Bundle.main
            let info = bundle.infoDictionary
            let usage = (info?["NSLocalNetworkUsageDescription"] as? String)?
                .trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
            readOK = info != nil
            usageDescriptionPresent = !usage.isEmpty
            requiredBonjourPresent = (info?["NSBonjourServices"] as? [String])?
                .contains(LanProbe.serviceType) ?? false
            bundleIdentifierPresent = !(bundle.bundleIdentifier ?? "").isEmpty
            expectedBundleIdentifier = bundle.bundleIdentifier == "dev.p2pkit.diagnostics.lanhost"
            applicationPackageType = info?["CFBundlePackageType"] as? String == "APPL"
        }
    }
    private struct CleanupObservation: Encodable {
        let listenersCreated: Int
        let listenersCancelled: Int
        let browsersCreated: Int
        let browsersCancelled: Int
        let complete: Bool
    }
    private struct Observation: Encodable {
        let schema = 1
        let diagnosticOnly = true
        let mode = "cli"
        let browserDescriptor: DescriptorPolicy
        let outcome: Outcome
        let windowMilliseconds = 30_000
        let observationElapsedMilliseconds: Int
        let cleanupElapsedMilliseconds: Int
        let isSimulatorBuild: Bool
        let isX86_64Build: Bool
        let counterOverflow: Bool
        let packaging: PackagingObservation
        let peers: [PeerObservation]
        let cleanup: CleanupObservation
    }

    private static let serviceType = "_p2pkit._tcp"
    private static let observationNanoseconds: UInt64 = 30_000_000_000
    private static let cancellationNanoseconds: UInt64 = 5_000_000_000
    private let queue = DispatchQueue(label: "dev.p2pkit.diagnostics.lanhost.probe")
    private let policy: DescriptorPolicy
    private let names: [String]
    private let packaging = PackagingObservation()
    private let peers = [Peer(), Peer()]
    private var phase: Phase = .idle
    private var completion: ((String) -> Void)?
    private var startedAt: UInt64 = 0
    private var observationDeadline: UInt64 = 0
    private var cancellationStartedAt: UInt64 = 0
    private var cancellationDeadline: UInt64 = 0
    private var observationElapsed = 0
    private var setupFailed = false
    private var timingInvalid = false
    private var counterOverflow = false
    private var finishScheduled = false

    init?(policy: DescriptorPolicy, token: String) {
        let bytes = Array(token.utf8)
        guard bytes.count == 32, bytes.allSatisfy({ (48...57).contains($0) || (97...102).contains($0) }) else {
            return nil
        }
        self.policy = policy
        names = ["p2pkit-params-\(token)-\(policy.rawValue)-a", "p2pkit-params-\(token)-\(policy.rawValue)-b"]
    }

    /// Call once and retain the instance through completion. Completion is on main.
    /// Even setup failure observes the full 30 seconds; discovering early does not reset or end it.
    /// Empty completion means serialization/bounds failure, NOT a negative network observation.
    @discardableResult
    func start(completion: @escaping (String) -> Void) -> Bool {
        queue.sync {
            guard phase == .idle else { return false }
            phase = .observing
            self.completion = completion
            startedAt = DispatchTime.now().uptimeNanoseconds
            observationDeadline = startedAt + Self.observationNanoseconds
            queue.async { [weak self] in self?.configure() }
            queue.asyncAfter(deadline: DispatchTime(uptimeNanoseconds: observationDeadline)) { [weak self] in
                self?.beginCancellation()
            }
            return true
        }
    }

    private func listenerParameters() -> NWParameters {
        let parameters = NWParameters.tcp
        if let tcp = parameters.defaultProtocolStack.transportProtocol as? NWProtocolTCP.Options {
            tcp.noDelay = true
        }
        parameters.includePeerToPeer = true
        parameters.prohibitedInterfaceTypes = [.cellular]
        return parameters
    }

    private func browserParameters() -> NWParameters {
        // Both descriptor arms use the same bare transport and interface policy.
        let parameters = NWParameters()
        parameters.includePeerToPeer = true
        parameters.prohibitedInterfaceTypes = [.cellular]
        return parameters
    }

    private func transport(_ parameters: NWParameters) -> Transport {
        guard let options = parameters.defaultProtocolStack.transportProtocol else { return .none }
        return options is NWProtocolTCP.Options ? .tcp : .other
    }

    private func txtRecord(index: Int) -> Data? {
        // Fixed legacy producer shape; pid and service identity are the same owned private name.
        let entries = ["pid=\(names[index])", "app=p2pkit-parameter-diagnostic",
                       "name=Probe\(index)", "plat=IOS", "caps=LAN", "pv=1"]
        var data = Data()
        for entry in entries {
            let bytes = Array(entry.utf8)
            guard (1...255).contains(bytes.count), bytes.allSatisfy({ (32...126).contains($0) }) else {
                return nil
            }
            data.append(UInt8(bytes.count))
            data.append(contentsOf: bytes)
        }
        return validTxtShape(data) ? data : nil
    }

    private func validTxtShape(_ data: Data) -> Bool {
        let bytes = Array(data)
        guard !bytes.isEmpty, bytes.count <= 2048 else { return false }
        let allowed: Set<String> = ["pid", "app", "name", "plat", "caps", "pv"]
        var keys = Set<String>()
        var cursor = 0
        while cursor < bytes.count {
            let length = Int(bytes[cursor])
            cursor += 1
            guard length > 0, cursor + length <= bytes.count else { return false }
            let entry = Array(bytes[cursor..<(cursor + length)])
            guard entry.allSatisfy({ (32...126).contains($0) }),
                  let equal = entry.firstIndex(of: 61), equal > 0, equal + 1 < entry.count,
                  let key = String(bytes: entry[..<equal], encoding: .ascii),
                  allowed.contains(key), keys.insert(key).inserted else { return false }
            cursor += length
        }
        return keys == allowed
    }

    private func configure() {
        for index in peers.indices {
            guard acceptingObservation() else { timingInvalid = true; return }
            let parameters = listenerParameters()
            var observed = peers[index].observation.configuration
            observed.listenerObserved = true
            observed.listenerTransport = transport(parameters)
            let tcp = parameters.defaultProtocolStack.transportProtocol as? NWProtocolTCP.Options
            observed.listenerNoDelay = tcp?.noDelay == true
            observed.listenerP2P = parameters.includePeerToPeer
            observed.listenerCellBan = (parameters.prohibitedInterfaceTypes ?? []).contains(.cellular)
            peers[index].observation.configuration = observed
            guard observed.listenerTransport == .tcp, observed.listenerNoDelay,
                  observed.listenerP2P, observed.listenerCellBan else { setupFailed = true; continue }
            do {
                let listener = try NWListener(using: parameters, on: .any)
                // Service assignment is deliberately deferred until this listener's actual READY callback.
                listener.stateUpdateHandler = { [weak self] state in self?.listenerState(state, index: index) }
                listener.serviceRegistrationUpdateHandler = { [weak self] change in
                    self?.registration(change, index: index)
                }
                listener.newConnectionHandler = { [weak self] connection in
                    connection.cancel()
                    guard let self = self, self.phase != .finished else { return }
                    self.bump(\.unexpectedConnections, index: index)
                }
                peers[index].listener = listener
                listener.start(queue: queue)
            } catch {
                setupFailed = true
                peers[index].observation.listenerLastState = .failed
                peers[index].observation.listenerError = ErrorObservation(error)
                bump(\.listenerFailed, index: index)
            }
        }
    }

    private func advertiseAfterReady(index: Int) {
        guard acceptingObservation(), !peers[index].advertisementAttempted,
              peers[index].observation.listenerReady > 0, let listener = peers[index].listener else { return }
        peers[index].advertisementAttempted = true
        guard let expected = txtRecord(index: index) else { setupFailed = true; return }
        // Explicit Data selects the documented raw-TXT initializer, not the NWTXTRecord overload.
        var service = NWListener.Service(name: names[index], type: Self.serviceType,
                                         domain: nil, txtRecord: expected)
        service.noAutoRename = true
        listener.service = service
        var observed = peers[index].observation.configuration
        observed.advertisementAfterReady = true
        if let configured = listener.service {
            observed.noAutoRename = configured.noAutoRename
            observed.configuredServiceTxtPresent = configured.txtRecord != nil
            if let raw = configured.txtRecord {
                observed.configuredServiceTxtReadbackMatches = raw == expected
                observed.configuredServiceTxtShapeValid = validTxtShape(raw)
            }
        }
        peers[index].observation.configuration = observed
        guard observed.noAutoRename, observed.configuredServiceTxtPresent,
              observed.configuredServiceTxtReadbackMatches, observed.configuredServiceTxtShapeValid else {
            setupFailed = true
            return
        }
        // Configuration getter checks above are NOT native publication or received-TXT proof.
        let parameters = browserParameters()
        let descriptor: NWBrowser.Descriptor
        switch policy {
        case .bonjour:
            descriptor = .bonjour(type: Self.serviceType, domain: nil)
        case .withTXT:
            descriptor = .bonjourWithTXTRecord(type: Self.serviceType, domain: nil)
        }
        observed.browserObserved = true
        observed.browserTransport = transport(parameters)
        observed.browserP2P = parameters.includePeerToPeer
        observed.browserCellBan = (parameters.prohibitedInterfaceTypes ?? []).contains(.cellular)
        switch descriptor {
        case .bonjour: observed.browserIncludesTXT = false
        case .bonjourWithTXTRecord: observed.browserIncludesTXT = true
        default: setupFailed = true; return
        }
        peers[index].observation.configuration = observed
        guard observed.browserTransport == .none, observed.browserP2P, observed.browserCellBan,
              observed.browserIncludesTXT == (policy == .withTXT) else { setupFailed = true; return }
        let browser = NWBrowser(for: descriptor, using: parameters)
        browser.stateUpdateHandler = { [weak self] state in self?.browserState(state, index: index) }
        browser.browseResultsChangedHandler = { [weak self] results, _ in self?.results(results, index: index) }
        peers[index].browser = browser
        browser.start(queue: queue)
    }

    /// Timestamp every callback before using it as an observation, including queued late callbacks.
    private func acceptingObservation() -> Bool {
        guard phase == .observing else { return false }
        guard DispatchTime.now().uptimeNanoseconds < observationDeadline else {
            beginCancellation()
            return false
        }
        return true
    }

    private func bump(_ key: WritableKeyPath<PeerObservation, Int>, index: Int) {
        if peers[index].observation[keyPath: key] < 65_535 {
            peers[index].observation[keyPath: key] += 1
        } else {
            counterOverflow = true
        }
    }

    private func listenerState(_ state: NWListener.State, index: Int) {
        guard phase != .finished else { return }
        let observing = acceptingObservation()
        if case .cancelled = state, cancellationCallbackInTime() {
            peers[index].observation.listenerCancelled = true
        }
        if observing {
            switch state {
            case .setup: peers[index].observation.listenerLastState = .setup
            case .waiting(let error):
                peers[index].observation.listenerLastState = .waiting
                peers[index].observation.listenerError = ErrorObservation(error)
                bump(\.listenerWaiting, index: index)
            case .ready:
                peers[index].observation.listenerLastState = .ready
                bump(\.listenerReady, index: index)
                advertiseAfterReady(index: index)
            case .failed(let error):
                peers[index].observation.listenerLastState = .failed
                peers[index].observation.listenerError = ErrorObservation(error)
                bump(\.listenerFailed, index: index)
            case .cancelled: peers[index].observation.listenerLastState = .cancelled
            @unknown default: peers[index].observation.listenerLastState = .unknown
            }
        }
        finishWhenCancelled()
    }

    private func browserState(_ state: NWBrowser.State, index: Int) {
        guard phase != .finished else { return }
        let observing = acceptingObservation()
        if case .cancelled = state, cancellationCallbackInTime() {
            peers[index].observation.browserCancelled = true
        }
        if observing {
            switch state {
            case .setup: peers[index].observation.browserLastState = .setup
            case .waiting(let error):
                peers[index].observation.browserLastState = .waiting
                peers[index].observation.browserError = ErrorObservation(error)
                bump(\.browserWaiting, index: index)
            case .ready:
                peers[index].observation.browserLastState = .ready
                bump(\.browserReady, index: index)
            case .failed(let error):
                peers[index].observation.browserLastState = .failed
                peers[index].observation.browserError = ErrorObservation(error)
                bump(\.browserFailed, index: index)
            case .cancelled: peers[index].observation.browserLastState = .cancelled
            @unknown default: peers[index].observation.browserLastState = .unknown
            }
        }
        finishWhenCancelled()
    }

    private func serviceName(_ endpoint: NWEndpoint) -> String? {
        guard case .service(let name, let type, _, _) = endpoint,
              type == Self.serviceType || type == Self.serviceType + "." else { return nil }
        return name
    }

    private func registration(_ change: NWListener.ServiceRegistrationChange, index: Int) {
        guard acceptingObservation() else { return }
        switch change {
        case .add(let endpoint):
            bump(\.registrationAdded, index: index)
            if let name = serviceName(endpoint) {
                if name == names[index] {
                    peers[index].observation.ownRegistrationObserved = true
                } else {
                    peers[index].observation.registrationNameChanged = true
                }
            }
        case .remove:
            bump(\.registrationRemoved, index: index)
        @unknown default:
            counterOverflow = true  // An unrepresented registration event is not silently accepted.
        }
    }

    private func results(_ results: Set<NWBrowser.Result>, index: Int) {
        guard acceptingObservation() else { return }
        bump(\.resultCallbacks, index: index)
        if results.count > 128 { counterOverflow = true }
        peers[index].observation.maximumResultCount = max(
            peers[index].observation.maximumResultCount, min(results.count, 65_535)
        )
        // Only the OTHER owned synthetic name counts; no discovered name leaves this callback.
        for result in results.prefix(128) where serviceName(result.endpoint) == names[1 - index] {
            peers[index].observation.expectedPeerObserved = true
        }
    }

    private func cancellationCallbackInTime() -> Bool {
        phase == .observing || (phase == .cancelling && DispatchTime.now().uptimeNanoseconds <= cancellationDeadline)
    }

    private func beginCancellation() {
        guard phase == .observing else { return }
        let now = DispatchTime.now().uptimeNanoseconds
        observationElapsed = Int((now - startedAt) / 1_000_000)
        if peers.contains(where: { $0.listener == nil || $0.browser == nil }) { setupFailed = true }
        phase = .cancelling
        cancellationStartedAt = now
        cancellationDeadline = now + Self.cancellationNanoseconds
        for peer in peers {
            peer.browser?.cancel()
            peer.listener?.cancel()
        }
        queue.asyncAfter(deadline: DispatchTime(uptimeNanoseconds: cancellationDeadline)) { [weak self] in
            self?.finish()
        }
        finishWhenCancelled()
    }

    private func allCancelled() -> Bool {
        peers.allSatisfy {
            ($0.listener == nil || $0.observation.listenerCancelled) &&
                ($0.browser == nil || $0.observation.browserCancelled)
        }
    }

    private func finishWhenCancelled() {
        guard phase == .cancelling, allCancelled(), !finishScheduled else { return }
        finishScheduled = true
        // One serial-queue turn drains already-enqueued callbacks before detaching handlers.
        queue.async { [weak self] in self?.finish() }
    }

    private func finish() {
        guard phase == .cancelling else { return }
        let now = DispatchTime.now().uptimeNanoseconds
        let cleanupElapsed = Int((now - cancellationStartedAt) / 1_000_000)
        let complete = allCancelled() && now <= cancellationDeadline &&
            peers.allSatisfy { $0.observation.unexpectedConnections == 0 }
        let cleanup = CleanupObservation(
            listenersCreated: peers.filter { $0.listener != nil }.count,
            listenersCancelled: peers.filter { $0.listener != nil && $0.observation.listenerCancelled }.count,
            browsersCreated: peers.filter { $0.browser != nil }.count,
            browsersCancelled: peers.filter { $0.browser != nil && $0.observation.browserCancelled }.count,
            complete: complete
        )
        let outcome: Outcome
        if !complete { outcome = .cleanupUnconfirmed }
        else if counterOverflow { outcome = .counterOverflow }
        else if timingInvalid || observationElapsed < 30_000 || cleanupElapsed > 5_000 { outcome = .timingInvalid }
        else if setupFailed { outcome = .setupFailed }
        else if peers.allSatisfy({ $0.observation.expectedPeerObserved }) { outcome = .discovered }
        else { outcome = .notDiscovered }

        #if targetEnvironment(simulator)
        let simulatorBuild = true
        #else
        let simulatorBuild = false
        #endif
        #if arch(x86_64)
        let intelBuild = true
        #else
        let intelBuild = false
        #endif
        let observation = Observation(
            browserDescriptor: policy, outcome: outcome, observationElapsedMilliseconds: observationElapsed,
            cleanupElapsedMilliseconds: cleanupElapsed, isSimulatorBuild: simulatorBuild,
            isX86_64Build: intelBuild, counterOverflow: counterOverflow, packaging: packaging,
            peers: peers.map { $0.observation }, cleanup: cleanup
        )
        phase = .finished
        for peer in peers {
            peer.listener?.stateUpdateHandler = nil
            peer.listener?.serviceRegistrationUpdateHandler = nil
            peer.listener?.newConnectionHandler = nil
            peer.browser?.stateUpdateHandler = nil
            peer.browser?.browseResultsChangedHandler = nil
            peer.listener = nil
            peer.browser = nil
        }
        let callback = completion
        completion = nil
        let encoder = JSONEncoder()
        encoder.outputFormatting = [.sortedKeys]
        var result = ""
        // Do not replace an unrepresentable actual duration with a fabricated in-bounds duration.
        if (0...120_000).contains(observationElapsed), (0...120_000).contains(cleanupElapsed),
           let data = try? encoder.encode(observation), data.count <= 6_144,
           let text = String(data: data, encoding: .utf8) {
            result = text
        }
        DispatchQueue.main.async { callback?(result) }
    }
}
