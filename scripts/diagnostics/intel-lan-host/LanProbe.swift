import Foundation
import Network
import dnssd

/// Diagnostic only: exact-owned concrete TXT, local TXT and local SRV on the same live producers.
/// No endpoint, service name, token, path, or free-form error enters its result.
final class LanProbe {
    enum DescriptorPolicy: String, Encodable { case ownedTXT = "OWNED_TXT" }
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
    private enum QueryRole: Int, CaseIterable { case concreteTXT, localTXT, localSRV }
    private enum InterfaceKind: String, Encodable { case none, wifi, wiredEthernet, loopback, other }
    private enum CallbackInterfaceClass: String, Encodable {
        case none, selectedConcrete, otherConcrete, localOnly, p2p, unicast, ble, any, otherSpecial
    }
    private enum RetirementReason: String, Encodable {
        case none, cutoff, interfaceRemoved, serviceRemoved, browserFailed, queueFailed
        case callbackFailed, invalidCallback
    }
    private final class TXTQueryObservation: Encodable {
        var started = 0
        var callbacks = 0
        var matchingCallbacks = 0
        var removedCallbacks = 0
        var errorCode: Int32 = 0
        var bytes = 0
        var received = false
        var matchesExpected = false
        var malformed = false
        var identityMatched = false
        var interfaceMatched = false
        var retired = true  // No allocated reference is vacuously retired.
        var absenceCallbacks = 0
        var present = false
        var startMilliseconds = -1
        var retirementMilliseconds = -1
        var retirementReason: RetirementReason = .none
        var callbackInterfaceClass: CallbackInterfaceClass = .none
    }
    private final class TXTQueryContext {
        weak var owner: LanProbe?
        let peerIndex: Int
        let role: QueryRole
        let name: String
        let type: String
        let domain: String
        let interfaceIndex: UInt32
        let fullName: [CChar]  // Bounded, NUL-terminated DNSServiceConstructFullName output.
        let expected: Data
        var active = true

        init(owner: LanProbe, peerIndex: Int, role: QueryRole, name: String, type: String, domain: String,
             interfaceIndex: UInt32, fullName: [CChar], expected: Data) {
            self.owner = owner
            self.peerIndex = peerIndex
            self.role = role
            self.name = name
            self.type = type
            self.domain = domain
            self.interfaceIndex = interfaceIndex
            self.fullName = fullName
            self.expected = expected
        }
    }
    private struct PeerObservation: Encodable {
        var configuration = ConfigurationObservation()
        var txtQuery = TXTQueryObservation()
        var localTxtQuery = TXTQueryObservation()
        var localSrvQuery = TXTQueryObservation()
        var selectedInterfaceKind: InterfaceKind = .none
        var candidateInterfaceCount = 0
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
    private final class QuerySlot {
        var attempted = false
        var reference: DNSServiceRef?
        // Strong through same-queue deallocation AND its queued drain; C only borrows it.
        var context: TXTQueryContext?
    }
    private final class Peer {
        var listener: NWListener?
        var browser: NWBrowser?
        var observation = PeerObservation()
        var advertisementAttempted = false
        var queriesAttempted = false
        let queries = [QuerySlot(), QuerySlot(), QuerySlot()]
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
        // Preserve the accepted bare transport and interface policy.
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
        let descriptor = NWBrowser.Descriptor.bonjour(type: Self.serviceType, domain: nil)
        observed.browserObserved = true
        observed.browserTransport = transport(parameters)
        observed.browserP2P = parameters.includePeerToPeer
        observed.browserCellBan = (parameters.prohibitedInterfaceTypes ?? []).contains(.cellular)
        switch descriptor {
        case .bonjour: observed.browserIncludesTXT = false
        default: setupFailed = true; return
        }
        peers[index].observation.configuration = observed
        guard observed.browserTransport == .none, observed.browserP2P, observed.browserCellBan,
              !observed.browserIncludesTXT else { setupFailed = true; return }
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
                retireQueries(index: index, reason: .browserFailed)
            case .cancelled:
                peers[index].observation.browserLastState = .cancelled
                retireQueries(index: index, reason: .browserFailed)
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
        // Only the OTHER owned synthetic service is eligible, never an ambient advertisement.
        // One concrete permitted interface is sampled; this is NOT all-interface production coverage.
        var selected: (name: String, type: String, domain: String, interface: UInt32, rank: Int)?
        var selectedStillPresent = false
        var serviceStillPresent = false
        var interfaceCount = 0
        var eligibleCount = 0
        let frozenContext = peers[index].queries.compactMap { $0.context }.first
        for result in results.prefix(128) where serviceName(result.endpoint) == names[1 - index] {
            peers[index].observation.expectedPeerObserved = true
            guard case .service(let name, let type, let domain, _) = result.endpoint,
                  domain == "local." || domain == "local" else { continue }
            if let context = frozenContext,
               context.name == name, context.type == type, context.domain == domain {
                serviceStillPresent = true
            }
            guard result.interfaces.count <= 128 else { counterOverflow = true; continue }
            for interface in result.interfaces {
                interfaceCount += 1
                guard interfaceCount <= 128 else { counterOverflow = true; continue }
                guard let rank = permittedInterfaceRank(interface),
                      let value = UInt32(exactly: interface.index), value > 0, value <= 0x7fff_ffff else { continue }
                eligibleCount += 1
                if let context = frozenContext,
                   context.name == name, context.type == type, context.domain == domain,
                   context.interfaceIndex == value {
                    selectedStillPresent = true
                }
                if selected == nil || value < selected!.interface ||
                    (value == selected!.interface && (rank < selected!.rank ||
                        (rank == selected!.rank && (type < selected!.type ||
                            (type == selected!.type && domain < selected!.domain))))) {
                    selected = (name, type, domain, value, rank)
                }
            }
        }
        if !counterOverflow, frozenContext != nil {
            if !serviceStillPresent {
                retireQueries(index: index, reason: .serviceRemoved)
            } else if !selectedStillPresent {
                clearCurrent(queryObservation(index: index, role: .concreteTXT))
                retireTXTQuery(index: index, role: .concreteTXT, reason: .interfaceRemoved)
                // LocalOnly queries remain live while their exact owned service remains observed.
            }
        }
        if !counterOverflow, !peers[index].queriesAttempted, let selected = selected {
            peers[index].queriesAttempted = true
            // Count eligible candidate entries in this complete bounded snapshot, not ambient results.
            peers[index].observation.candidateInterfaceCount = eligibleCount
            peers[index].observation.selectedInterfaceKind = interfaceKind(rank: selected.rank)
            for role in QueryRole.allCases {
                startTXTQuery(index: index, role: role, name: selected.name, type: selected.type,
                              domain: selected.domain, interfaceIndex: selected.interface)
            }
        }
    }

    private func interfaceKind(rank: Int) -> InterfaceKind {
        switch rank {
        case 0: return .wifi
        case 1: return .wiredEthernet
        case 2: return .loopback
        default: return .other
        }
    }

    private func permittedInterfaceRank(_ interface: NWInterface) -> Int? {
        switch interface.type {
        case .wifi: return 0
        case .wiredEthernet: return 1
        case .loopback: return 2
        case .other: return 3  // Includes peer-to-peer paths reported by the scoped NWBrowser.
        case .cellular: return nil
        @unknown default: return nil
        }
    }

    private static let txtReply: DNSServiceQueryRecordReply = {
        reference, flags, interfaceIndex, errorCode, fullName, rrtype, rrclass, rdlen, rdata, _, pointer in
        guard let pointer = pointer else { return }
        let context = Unmanaged<TXTQueryContext>.fromOpaque(pointer).takeUnretainedValue()
        guard let owner = context.owner else { return }
        // DNS-SD explicitly leaves ALL result fields undefined on error; do not inspect any.
        if errorCode != kDNSServiceErr_NoError {
            owner.txtQueryFailed(context, errorCode: errorCode)
            return
        }
        owner.txtQueryResult(context, reference: reference, flags: flags, interfaceIndex: interfaceIndex,
                             fullName: fullName, rrtype: rrtype, rrclass: rrclass, rdlen: rdlen, rdata: rdata)
    }

    private func queryObservation(index: Int, role: QueryRole) -> TXTQueryObservation {
        switch role {
        case .concreteTXT: return peers[index].observation.txtQuery
        case .localTXT: return peers[index].observation.localTxtQuery
        case .localSRV: return peers[index].observation.localSrvQuery
        }
    }

    private func startTXTQuery(index: Int, role: QueryRole, name: String, type: String,
                               domain: String, interfaceIndex: UInt32) {
        let slot = peers[index].queries[role.rawValue]
        guard acceptingObservation(), !slot.attempted else { return }
        slot.attempted = true
        let observed = queryObservation(index: index, role: role)
        guard name == names[1 - index], let expected = txtRecord(index: 1 - index) else {
            setupFailed = true
            return
        }
        var fullName = [CChar](repeating: 0, count: Int(kDNSServiceMaxDomainName))
        let construction = fullName.withUnsafeMutableBufferPointer { buffer in
            name.withCString { n in type.withCString { t in domain.withCString { d in
                DNSServiceConstructFullName(buffer.baseAddress, n, t, d)
            } } }
        }
        guard construction == kDNSServiceErr_NoError else {
            observed.errorCode = construction
            return
        }
        guard let end = fullName.firstIndex(of: 0), end > 0 else { setupFailed = true; return }
        let context = TXTQueryContext(owner: self, peerIndex: index, role: role, name: name, type: type, domain: domain,
                                      interfaceIndex: interfaceIndex, fullName: Array(fullName[...end]),
                                      expected: expected)
        slot.context = context
        var reference: DNSServiceRef?
        let requestedInterface = role == .concreteTXT ? interfaceIndex : kDNSServiceInterfaceIndexLocalOnly
        let requestedType = role == .localSRV ? UInt16(kDNSServiceType_SRV) : UInt16(kDNSServiceType_TXT)
        let flags = DNSServiceFlags(kDNSServiceFlagsIncludeP2P | kDNSServiceFlagsReturnIntermediates)
        let code = context.fullName.withUnsafeBufferPointer { buffer in
            DNSServiceQueryRecord(&reference, flags, requestedInterface,
                                  buffer.baseAddress, requestedType, UInt16(kDNSServiceClass_IN),
                                  Self.txtReply, Unmanaged.passUnretained(context).toOpaque())
        }
        guard code == kDNSServiceErr_NoError else {
            // Failure does NOT initialize reference and guarantees no callback; never deallocate it.
            observed.errorCode = code
            context.active = false
            slot.context = nil
            return
        }
        guard let reference = reference else {
            context.active = false
            slot.context = nil
            setupFailed = true
            return
        }
        slot.reference = reference
        observed.started = 1
        observed.retired = false
        // Creation, scheduling, callbacks, retirement and context release all use this same serial queue.
        let scheduled = DNSServiceSetDispatchQueue(reference, queue)
        if scheduled != kDNSServiceErr_NoError {
            observed.errorCode = scheduled
            retireTXTQuery(index: index, role: role, reason: .queueFailed)
        } else {
            // Same-queue callbacks cannot run before scheduling returns. Do not claim allocation time.
            observed.startMilliseconds = elapsedMilliseconds()
        }
    }

    private func currentTXTQuery(_ context: TXTQueryContext) -> Bool {
        let slot = peers[context.peerIndex].queries[context.role.rawValue]
        return context.active && slot.context === context && slot.reference != nil
    }

    private func bumpTXT(_ key: ReferenceWritableKeyPath<TXTQueryObservation, Int>,
                         observation: TXTQueryObservation) {
        if observation[keyPath: key] < 65_535 {
            observation[keyPath: key] += 1
        } else {
            counterOverflow = true
        }
    }

    private func txtQueryFailed(_ context: TXTQueryContext, errorCode: DNSServiceErrorType) {
        guard currentTXTQuery(context), acceptingObservation() else { return }
        let index = context.peerIndex
        let observed = queryObservation(index: index, role: context.role)
        bumpTXT(\.callbacks, observation: observed)
        clearCurrent(observed)
        observed.identityMatched = false
        observed.interfaceMatched = false
        observed.callbackInterfaceClass = .none
        if errorCode == kDNSServiceErr_NoSuchRecord {
            bumpTXT(\.absenceCallbacks, observation: observed)
            return  // ReturnIntermediates absence is not fatal; a later add may arrive on this ref.
        }
        if observed.errorCode == 0 { observed.errorCode = errorCode }
        retireTXTQuery(index: index, role: context.role, reason: .callbackFailed)
    }

    private func callbackInterface(_ value: UInt32, selected: UInt32) -> CallbackInterfaceClass {
        if value == selected { return .selectedConcrete }
        if value > 0 && value <= 0x7fff_ffff { return .otherConcrete }
        switch value {
        case UInt32(kDNSServiceInterfaceIndexAny): return .any
        case kDNSServiceInterfaceIndexLocalOnly: return .localOnly
        case kDNSServiceInterfaceIndexP2P: return .p2p
        case kDNSServiceInterfaceIndexUnicast: return .unicast
        case kDNSServiceInterfaceIndexBLE: return .ble
        default: return .otherSpecial
        }
    }

    private func txtQueryResult(_ context: TXTQueryContext, reference: DNSServiceRef?, flags: DNSServiceFlags,
                                interfaceIndex: UInt32, fullName: UnsafePointer<CChar>?, rrtype: UInt16,
                                rrclass: UInt16, rdlen: UInt16, rdata: UnsafeRawPointer?) {
        guard currentTXTQuery(context), acceptingObservation() else { return }
        let index = context.peerIndex
        let observed = queryObservation(index: index, role: context.role)
        bumpTXT(\.callbacks, observation: observed)
        // Compare only the expected bounded C name, including its NUL; never decode arbitrary names.
        let identity = fullName.map { pointer in
            context.fullName.indices.allSatisfy { pointer[$0] == context.fullName[$0] }
        } ?? false
        observed.identityMatched = identity
        observed.interfaceMatched = interfaceIndex == context.interfaceIndex
        observed.callbackInterfaceClass = callbackInterface(interfaceIndex, selected: context.interfaceIndex)
        clearCurrent(observed)
        let expectedType = context.role == .localSRV ? UInt16(kDNSServiceType_SRV) : UInt16(kDNSServiceType_TXT)
        guard identity, (context.role != .concreteTXT || observed.interfaceMatched),
              reference == peers[index].queries[context.role.rawValue].reference,
              rrtype == expectedType, rrclass == UInt16(kDNSServiceClass_IN) else {
            observed.malformed = true
            retireTXTQuery(index: index, role: context.role, reason: .invalidCallback)
            return  // No unrelated RDATA is copied or inspected.
        }
        if flags & DNSServiceFlags(kDNSServiceFlagsAdd) == 0 {
            bumpTXT(\.removedCallbacks, observation: observed)
            return  // Last admitted TXT is no longer live; a later valid add may replace it.
        }
        if context.role == .localSRV {
            guard rdlen >= 7, rdata != nil else { observed.malformed = true; return }
            observed.received = true
            observed.present = true
            observed.bytes = Int(rdlen)
            return  // Availability control only: NEVER dereference, copy or parse the SRV payload.
        }
        guard rdlen == 0 || rdata != nil else {
            observed.malformed = true
            return
        }
        // rdlen is an unsigned 16-bit API value: copy at most 65,535 bytes during the callback.
        let received = rdlen == 0 ? Data() : Data(bytes: rdata!, count: Int(rdlen))
        observed.received = true
        observed.present = true
        observed.bytes = received.count
        guard validTxtShape(received) else {
            observed.malformed = true
            return
        }
        let matches = received == context.expected
        if matches { bumpTXT(\.matchingCallbacks, observation: observed) }
        observed.matchesExpected = matches && !observed.malformed && observed.errorCode == 0
        // This proves an API-delivered value (possibly cached), NOT an observed network packet.
    }

    private func clearCurrent(_ observed: TXTQueryObservation) {
        observed.present = false
        observed.matchesExpected = false
    }

    private func elapsedMilliseconds() -> Int {
        Int((DispatchTime.now().uptimeNanoseconds - startedAt) / 1_000_000)
    }

    private func retireQueries(index: Int, reason: RetirementReason) {
        for role in QueryRole.allCases {
            // At cutoff freeze the last accepted window state, as the original concrete probe did.
            if reason != .cutoff { clearCurrent(queryObservation(index: index, role: role)) }
            retireTXTQuery(index: index, role: role, reason: reason)
        }
    }

    private func retireTXTQuery(index: Int, role: QueryRole, reason: RetirementReason) {
        let slot = peers[index].queries[role.rawValue]
        guard let reference = slot.reference else { return }
        let observed = queryObservation(index: index, role: role)
        slot.context?.active = false
        observed.retirementMilliseconds = elapsedMilliseconds()
        observed.retirementReason = reason  // First logical retirement wins via the reference guard.
        slot.reference = nil  // Exact once; subsequent retirement cannot schedule another free.
        // Defer one turn so callback-triggered cancellation never deallocates inside DNS-SD dispatch.
        queue.async { [self] in
            DNSServiceRefDeallocate(reference)
            queue.async { [self] in
                // Native free and this serial drain both precede retired=true/context release.
                observed.retired = true
                finishWhenCancelled()
            }
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
        for index in peers.indices {
            retireQueries(index: index, reason: .cutoff)
            peers[index].browser?.cancel()
            peers[index].listener?.cancel()
        }
        queue.asyncAfter(deadline: DispatchTime(uptimeNanoseconds: cancellationDeadline)) { [weak self] in
            self?.finish()
        }
        finishWhenCancelled()
    }

    private func allCancelled() -> Bool {
        peers.indices.allSatisfy { index in
            let peer = peers[index]
            return (peer.listener == nil || peer.observation.listenerCancelled) &&
                (peer.browser == nil || peer.observation.browserCancelled) &&
                QueryRole.allCases.allSatisfy { role in
                    peer.queries[role.rawValue].reference == nil && queryObservation(index: index, role: role).retired
                }
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
        // One origin avoids a 1 ms gap from summing two separately floored intervals.
        // The actual cancellation deadline below remains the unchanged nanosecond 5 s bound.
        let cleanupElapsed = Int((now - startedAt) / 1_000_000) - observationElapsed
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
        else if peers.allSatisfy({ $0.observation.expectedPeerObserved &&
            $0.observation.txtQuery.matchesExpected }) { outcome = .discovered }
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
        for index in peers.indices {
            let peer = peers[index]
            peer.listener?.stateUpdateHandler = nil
            peer.listener?.serviceRegistrationUpdateHandler = nil
            peer.listener?.newConnectionHandler = nil
            peer.browser?.stateUpdateHandler = nil
            peer.browser?.browseResultsChangedHandler = nil
            peer.listener = nil
            peer.browser = nil
            // Each retired flag includes exact DNS-SD deallocation AND its queued drain.
            for role in QueryRole.allCases where queryObservation(index: index, role: role).retired {
                peer.queries[role.rawValue].context = nil
            }
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
