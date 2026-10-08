import Foundation
import Network
import dnssd

/// Diagnostic only: one ordinary Bonjour CLI with an independent owned DNS-SD initial-resolution join.
/// No endpoint, service name, token, path, or free-form error enters its result.
final class LanProbe {
    enum DescriptorPolicy: String, Encodable { case bonjour = "BONJOUR", withTXT = "WITH_TXT" }
    enum Mode: String, Encodable { case cli, app }
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
    private enum InterfaceKind: String, Encodable, Hashable { case cellular, loopback, other, unknown, wifi, wiredEthernet }
    private struct InterfaceObservation: Encodable {
        var observed = false
        var count = 0
        var kinds: [InterfaceKind] = []
    }
    private enum MetadataKind: String, Encodable, Hashable { case none, bonjour, other, mixed }
    private struct TXTMetadataObservation: Encodable {
        var observations = 0
        var matchingObservations = 0
        var malformedObservations = 0
        var ownedResults = 0
        var maximumBytes = 0
        var kind: MetadataKind = .none
        var received = false
        var present = false
        var identityMatched = false
        var matchesExpected = false
        var rawMatchesExpected = false
        var malformed = false
    }
    private enum InterfaceRelation: String, Encodable {
        case unobserved, unavailable, equal, different, ambiguous, invalid
    }
    private struct EndpointJoinObservation: Encodable {
        var tupleMatched = false
        var ambiguous = false
        var policyCompatible = false
        var initialResolveJoined = false
        var endpointKind = "none"
        var endpointRelation: InterfaceRelation = .unobserved
        var resultRelation: InterfaceRelation = .unobserved
    }
    // Private callback values, never encoded. A nil identity index means invalid, not Any.
    private struct InterfaceIdentity {
        let index: UInt32?
        let kind: InterfaceKind
    }
    private struct EndpointSnapshot {
        let name: String
        let type: String
        let domain: String
        let endpointInterface: InterfaceIdentity?
        let resultInterfaces: [InterfaceIdentity]
    }
    private struct PeerObservation: Encodable {
        var dnsResolve = DNSResolveObservation()
        var endpointJoin: EndpointJoinObservation?
        var firstResultMilliseconds = -1
        var configuration = ConfigurationObservation()
        var interfaces = InterfaceObservation()
        var txtMetadata = TXTMetadataObservation()
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
        var dnsReference: DNSServiceRef?
        var dnsContext: DNSResolveContext?
        var resolvedInterfaceIndex: UInt32?
        var endpointSnapshot: EndpointSnapshot?
        var observation = PeerObservation()
        var advertisementAttempted = false
        var cutoffInterfaces: InterfaceObservation?
        var cutoffMetadata: TXTMetadataObservation?
        var cutoffEndpointJoin: EndpointJoinObservation?
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
        let mode: Mode
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
        let dnsBrowse: DNSBrowseObservation
    }

    private static let serviceType = "_p2pkit._tcp"
    private static let observationNanoseconds: UInt64 = 30_000_000_000
    private static let cancellationNanoseconds: UInt64 = 5_000_000_000
    private let queue = DispatchQueue(label: "dev.p2pkit.diagnostics.lanhost.probe")
    private let policy: DescriptorPolicy
    private let mode: Mode
    private let names: [String]
    private let packaging = PackagingObservation()
    private let peers = [Peer(), Peer()]
    private var phase: Phase = .idle
    private var dnsBrowse = DNSBrowseObservation()
    private var dnsBrowseReference: DNSServiceRef?
    private var dnsCandidates: [(interface: UInt32, type: String, domain: String)?] = [nil, nil]
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

    init?(policy: DescriptorPolicy, token: String, mode: Mode = .cli) {
        let bytes = Array(token.utf8)
        guard (mode == .cli && policy == .bonjour) || (mode == .app && policy == .withTXT),
              bytes.count == 32, bytes.allSatisfy({ (48...57).contains($0) || (97...102).contains($0) }) else {
            return nil
        }
        self.policy = policy
        self.mode = mode
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

    private enum DNSScope: String, Encodable { case none, concrete, localOnly, p2p, any, otherSpecial }
    private struct DNSBrowseObservation: Encodable {
        var attempted = false
        var created = false
        var started = false
        var retired = false
        var errorCode: Int32 = 0
        var callbacks = 0
        var ownedAdds = 0
        var ownedRemoves = 0
        var batches = 0
        var ambiguous = false
        var unsupportedScope = false
        var startMilliseconds = -1
        var retirementMilliseconds = -1
    }
    private struct DNSResolveObservation: Encodable {
        var attempted = false
        var created = false
        var started = false
        var retired = false
        var invalidated = false
        var callbacks = 0
        var matchingCallbacks = 0
        var errorCode: Int32 = 0
        var requestedScope: DNSScope = .none
        var returnedScope: DNSScope = .none
        var scopeMatches = false
        var scopeValid = false
        var identityMatched = false
        var received = false
        var bytes = 0
        var matchesExpected = false
        var portMatches = false
        var startMilliseconds = -1
        var resultMilliseconds = -1
        var retirementMilliseconds = -1
    }
    private final class DNSResolveContext {
        weak var owner: LanProbe?
        let index: Int
        let interfaceIndex: UInt32
        let name: String
        let type: String
        let domain: String
        let fullName: [CChar]
        var active = true
        init(owner: LanProbe, index: Int, interfaceIndex: UInt32, name: String,
             type: String, domain: String, fullName: [CChar]) {
            self.owner = owner; self.index = index; self.interfaceIndex = interfaceIndex
            self.name = name; self.type = type; self.domain = domain; self.fullName = fullName
        }
    }

    private func dnsMilliseconds() -> Int {
        Int((DispatchTime.now().uptimeNanoseconds - startedAt) / 1_000_000)
    }

    private func dnsCount(_ count: Int) -> Int {
        guard count < 256 else { counterOverflow = true; return count }
        return count + 1
    }

    private func dnsScope(_ index: UInt32) -> DNSScope {
        if index == UInt32(kDNSServiceInterfaceIndexAny) { return .any }
        if index == kDNSServiceInterfaceIndexLocalOnly { return .localOnly }
        if index == kDNSServiceInterfaceIndexP2P { return .p2p }
        return index <= 0x7fff_ffff ? .concrete : .otherSpecial
    }

    private func dnsEquals(_ pointer: UnsafePointer<CChar>?, _ expected: [CChar]) -> Bool {
        guard let pointer = pointer else { return false }
        // Short-circuit at the first mismatch (including an earlier NUL); never decode ambient names.
        return expected.indices.allSatisfy { pointer[$0] == expected[$0] }
    }

    private static let dnsBrowseReply: DNSServiceBrowseReply = {
        reference, flags, interfaceIndex, errorCode, name, type, domain, pointer in
        guard let pointer = pointer else { return }
        let owner = Unmanaged<LanProbe>.fromOpaque(pointer).takeUnretainedValue()
        owner.dnsBrowseResult(reference, flags: flags, interfaceIndex: interfaceIndex,
                              errorCode: errorCode, name: name, type: type, domain: domain)
    }

    private static let dnsResolveReply: DNSServiceResolveReply = {
        reference, _, interfaceIndex, errorCode, fullName, _, port, txtLength, txt, pointer in
        guard let pointer = pointer else { return }
        let context = Unmanaged<DNSResolveContext>.fromOpaque(pointer).takeUnretainedValue()
        context.owner?.dnsResolveResult(context, reference: reference, interfaceIndex: interfaceIndex,
                                       errorCode: errorCode, fullName: fullName, port: port,
                                       txtLength: txtLength, txt: txt)
    }

    private func maybeStartDNSBrowse() {
        guard acceptingObservation(), !dnsBrowse.attempted,
              peers.allSatisfy({ $0.observation.listenerLastState == .ready &&
                  $0.observation.browserLastState == .ready && $0.observation.ownRegistrationObserved }) else { return }
        dnsBrowse.attempted = true
        dnsBrowse.startMilliseconds = dnsMilliseconds()
        var reference: DNSServiceRef?
        let code = Self.serviceType.withCString { type in
            "local.".withCString { domain in
                DNSServiceBrowse(&reference, DNSServiceFlags(kDNSServiceFlagsIncludeP2P),
                                 UInt32(kDNSServiceInterfaceIndexAny), type, domain, Self.dnsBrowseReply,
                                 Unmanaged.passUnretained(self).toOpaque())
            }
        }
        guard code == kDNSServiceErr_NoError else { dnsBrowse.errorCode = code; return }
        guard let reference = reference else { setupFailed = true; return }
        dnsBrowseReference = reference
        dnsBrowse.created = true
        let scheduled = DNSServiceSetDispatchQueue(reference, queue)
        guard scheduled == kDNSServiceErr_NoError else {
            dnsBrowse.errorCode = scheduled
            retireDNSBrowse()
            return
        }
        dnsBrowse.started = true
    }

    private func dnsBrowseResult(_ reference: DNSServiceRef?, flags: DNSServiceFlags,
                                 interfaceIndex: UInt32, errorCode: DNSServiceErrorType,
                                 name: UnsafePointer<CChar>?, type: UnsafePointer<CChar>?,
                                 domain: UnsafePointer<CChar>?) {
        guard dnsBrowseReference != nil, acceptingObservation() else { return }
        dnsBrowse.callbacks = dnsCount(dnsBrowse.callbacks)
        // On error all other callback parameters are undefined. Do not inspect them.
        guard errorCode == kDNSServiceErr_NoError else {
            dnsBrowse.errorCode = errorCode
            for index in peers.indices { invalidateDNSResolve(index) }
            retireDNSBrowse()
            return
        }
        guard reference == dnsBrowseReference else {
            counterOverflow = true
            for index in peers.indices { invalidateDNSResolve(index) }
            retireDNSBrowse()
            return
        }
        let allowed = DNSServiceFlags(kDNSServiceFlagsAdd | kDNSServiceFlagsMoreComing)
        guard flags & ~allowed == 0, !counterOverflow else {
            counterOverflow = true
            for index in peers.indices { invalidateDNSResolve(index) }
            retireDNSBrowse()
            return
        }
        let owned = peers.indices.first { dnsEquals(name, names[$0].utf8CString.map { $0 }) }
        if let index = owned {
            let actualType: String?
            if dnsEquals(type, Self.serviceType.utf8CString.map { $0 }) { actualType = Self.serviceType }
            else if dnsEquals(type, (Self.serviceType + ".").utf8CString.map { $0 }) { actualType = Self.serviceType + "." }
            else { actualType = nil }
            let actualDomain: String?
            if dnsEquals(domain, "local.".utf8CString.map { $0 }) { actualDomain = "local." }
            else if dnsEquals(domain, "local".utf8CString.map { $0 }) { actualDomain = "local" }
            else { actualDomain = nil }
            guard let actualType = actualType, let actualDomain = actualDomain else {
                dnsBrowse.ambiguous = true
                for peerIndex in peers.indices { invalidateDNSResolve(peerIndex) }
                retireDNSBrowse()
                return
            }
            if flags & DNSServiceFlags(kDNSServiceFlagsAdd) == 0 {
                dnsBrowse.ownedRemoves = dnsCount(dnsBrowse.ownedRemoves)
                invalidateDNSResolve(index) // No remove/re-add retry or stale admission.
                dnsCandidates[index] = nil
            } else {
                dnsBrowse.ownedAdds = dnsCount(dnsBrowse.ownedAdds)
                let scope = dnsScope(interfaceIndex)
                guard scope == .concrete || scope == .localOnly || scope == .p2p else {
                    dnsBrowse.unsupportedScope = true
                    for peerIndex in peers.indices { invalidateDNSResolve(peerIndex) }
                    retireDNSBrowse()
                    return
                }
                if let previous = dnsCandidates[index], previous.interface != interfaceIndex ||
                    previous.type != actualType || previous.domain != actualDomain {
                    dnsBrowse.ambiguous = true
                    for peerIndex in peers.indices { invalidateDNSResolve(peerIndex) }
                    retireDNSBrowse()
                    return
                }
                dnsCandidates[index] = (interfaceIndex, actualType, actualDomain)
            }
        }
        if flags & DNSServiceFlags(kDNSServiceFlagsMoreComing) == 0 {
            // This ends only the currently available batch, not the subscription or an absence proof.
            dnsBrowse.batches = dnsCount(dnsBrowse.batches)
            for index in peers.indices {
                if let candidate = dnsCandidates[index], !peers[index].observation.dnsResolve.invalidated {
                    startDNSResolve(index, interface: candidate.interface, type: candidate.type,
                                    domain: candidate.domain)
                }
            }
        }
    }

    private func startDNSResolve(_ index: Int, interface: UInt32, type: String, domain: String) {
        guard acceptingObservation(), !counterOverflow, !dnsBrowse.ambiguous, !dnsBrowse.unsupportedScope,
              !peers[index].observation.dnsResolve.attempted else { return }
        peers[index].observation.dnsResolve.attempted = true
        peers[index].observation.dnsResolve.startMilliseconds = dnsMilliseconds()
        peers[index].observation.dnsResolve.requestedScope = dnsScope(interface)
        var fullName = [CChar](repeating: 0, count: Int(kDNSServiceMaxDomainName))
        let built = fullName.withUnsafeMutableBufferPointer { buffer in
            names[index].withCString { name in type.withCString { t in domain.withCString { d in
                DNSServiceConstructFullName(buffer.baseAddress, name, t, d)
            } } }
        }
        guard built == kDNSServiceErr_NoError, let end = fullName.firstIndex(of: 0), end > 0 else {
            setupFailed = true; return
        }
        let context = DNSResolveContext(owner: self, index: index, interfaceIndex: interface,
                                        name: names[index], type: type, domain: domain,
                                        fullName: Array(fullName[...end]))
        peers[index].dnsContext = context
        var reference: DNSServiceRef?
        let code = context.name.withCString { name in context.type.withCString { t in
            context.domain.withCString { d in
                DNSServiceResolve(&reference, 0, interface, name, t, d, Self.dnsResolveReply,
                                  Unmanaged.passUnretained(context).toOpaque())
            }
        } }
        guard code == kDNSServiceErr_NoError else {
            peers[index].observation.dnsResolve.errorCode = code
            context.active = false
            return
        }
        guard let reference = reference else { context.active = false; setupFailed = true; return }
        peers[index].dnsReference = reference
        peers[index].observation.dnsResolve.created = true
        let scheduled = DNSServiceSetDispatchQueue(reference, queue)
        guard scheduled == kDNSServiceErr_NoError else {
            peers[index].observation.dnsResolve.errorCode = scheduled
            retireDNSResolve(index)
            return
        }
        peers[index].observation.dnsResolve.started = true
    }

    private func dnsResolveResult(_ context: DNSResolveContext, reference: DNSServiceRef?,
                                  interfaceIndex: UInt32, errorCode: DNSServiceErrorType,
                                  fullName: UnsafePointer<CChar>?, port: UInt16,
                                  txtLength: UInt16, txt: UnsafePointer<UInt8>?) {
        let index = context.index
        guard context.active, peers[index].dnsContext === context, peers[index].dnsReference != nil,
              acceptingObservation() else { return }
        peers[index].observation.dnsResolve.callbacks = dnsCount(peers[index].observation.dnsResolve.callbacks)
        peers[index].observation.dnsResolve.resultMilliseconds = dnsMilliseconds()
        // Deallocate once after this desired result/error, never use Resolve as TXT monitoring.
        defer { retireDNSResolve(index) }
        guard errorCode == kDNSServiceErr_NoError else {
            peers[index].observation.dnsResolve.errorCode = errorCode
            peers[index].observation.dnsResolve.invalidated = true
            return
        }
        guard reference == peers[index].dnsReference else { counterOverflow = true; return }
        var observed = peers[index].observation.dnsResolve
        observed.returnedScope = dnsScope(interfaceIndex)
        observed.scopeMatches = interfaceIndex == context.interfaceIndex
        observed.scopeValid = (observed.scopeMatches &&
            (observed.requestedScope == .concrete || observed.requestedScope == .localOnly)) ||
            (observed.requestedScope == .p2p && observed.returnedScope == .concrete)
        observed.identityMatched = dnsEquals(fullName, context.fullName)
        // Do not touch hosttarget. Port is only compared in memory, never emitted.
        observed.portMatches = UInt16(bigEndian: port) == peers[index].listener?.port?.rawValue
        if observed.identityMatched && observed.scopeValid && (txtLength == 0 || txt != nil) {
            let received = txtLength == 0 ? Data() : Data(bytes: txt!, count: Int(txtLength))
            observed.received = true
            observed.bytes = received.count
            observed.matchesExpected = txtRecord(index: index).map { received == $0 } == true &&
                observed.portMatches && !observed.invalidated && !counterOverflow
            if observed.matchesExpected { observed.matchingCallbacks = dnsCount(observed.matchingCallbacks) }
        }
        peers[index].observation.dnsResolve = observed
        // Retain only an actual successful returned index; never substitute the requested sentinel.
        peers[index].resolvedInterfaceIndex = observed.matchesExpected ? interfaceIndex : nil
    }

    private func invalidateDNSResolve(_ index: Int) {
        peers[index].resolvedInterfaceIndex = nil
        peers[index].observation.dnsResolve.invalidated = true
        peers[index].observation.dnsResolve.matchesExpected = false
        peers[index].observation.dnsResolve.portMatches = false
        retireDNSResolve(index)
    }

    private func retireDNSResolve(_ index: Int) {
        peers[index].dnsContext?.active = false
        if let reference = peers[index].dnsReference {
            peers[index].dnsReference = nil
            DNSServiceRefDeallocate(reference) // Same serial queue as successful scheduling.
            peers[index].observation.dnsResolve.retired = true
            peers[index].observation.dnsResolve.retirementMilliseconds = dnsMilliseconds()
        }
    }

    private func retireDNSBrowse() {
        if let reference = dnsBrowseReference {
            dnsBrowseReference = nil
            DNSServiceRefDeallocate(reference)
            dnsBrowse.retired = true
            dnsBrowse.retirementMilliseconds = dnsMilliseconds()
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
        decodeOwnedTXT(data) != nil
    }

    private func decodeOwnedTXT(_ data: Data) -> [String: String]? {
        guard !data.isEmpty, data.count <= 2048 else { return nil }
        let bytes = Array(data)
        let allowed: Set<String> = ["pid", "app", "name", "plat", "caps", "pv"]
        var values: [String: String] = [:]
        var cursor = 0
        while cursor < bytes.count {
            let length = Int(bytes[cursor])
            cursor += 1
            guard length > 0, cursor + length <= bytes.count else { return nil }
            let entry = Array(bytes[cursor..<(cursor + length)])
            guard let equal = entry.firstIndex(of: 61), equal > 0, equal + 1 < entry.count,
                  let key = String(bytes: entry[..<equal], encoding: .ascii),
                  allowed.contains(key), values[key] == nil,
                  let value = String(bytes: entry[(equal + 1)...], encoding: .utf8) else { return nil }
            values[key] = value
            cursor += length
        }
        return Set(values.keys) == allowed ? values : nil
    }

    private func configure() {
        // Original API-delivered TXT Data is required; no dictionary reconstruction fallback.
        guard #available(iOS 16.0, *) else { setupFailed = true; return }
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
        case .bonjour: descriptor = .bonjour(type: Self.serviceType, domain: nil)
        case .withTXT: descriptor = .bonjourWithTXTRecord(type: Self.serviceType, domain: nil)
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
        browser.stateUpdateHandler = { [weak self, weak browser] state in
            guard let browser = browser else { return }
            self?.browserState(state, index: index, browser: browser)
        }
        browser.browseResultsChangedHandler = { [weak self, weak browser] results, _ in
            guard let browser = browser else { return }
            self?.results(results, index: index, browser: browser)
        }
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
            case .setup:
                peers[index].observation.listenerLastState = .setup
                if peers[index].observation.ownRegistrationObserved { invalidateDNSResolve(index) }
                clearCurrent(index: index)
                clearCurrent(index: 1 - index)
            case .waiting(let error):
                peers[index].observation.listenerLastState = .waiting
                peers[index].observation.listenerError = ErrorObservation(error)
                bump(\.listenerWaiting, index: index)
                if peers[index].observation.ownRegistrationObserved { invalidateDNSResolve(index) }
                clearCurrent(index: index)
                clearCurrent(index: 1 - index)
            case .ready:
                peers[index].observation.listenerLastState = .ready
                bump(\.listenerReady, index: index)
                advertiseAfterReady(index: index)
            case .failed(let error):
                peers[index].observation.listenerLastState = .failed
                peers[index].observation.listenerError = ErrorObservation(error)
                bump(\.listenerFailed, index: index)
                if peers[index].observation.ownRegistrationObserved { invalidateDNSResolve(index) }
                clearCurrent(index: index)
                clearCurrent(index: 1 - index)
            case .cancelled:
                peers[index].observation.listenerLastState = .cancelled
                if peers[index].observation.ownRegistrationObserved { invalidateDNSResolve(index) }
                clearCurrent(index: index)
                clearCurrent(index: 1 - index)
            @unknown default:
                peers[index].observation.listenerLastState = .unknown
                if peers[index].observation.ownRegistrationObserved { invalidateDNSResolve(index) }
                clearCurrent(index: index)
                clearCurrent(index: 1 - index)
            }
        }
        finishWhenCancelled()
    }

    private func browserState(_ state: NWBrowser.State, index: Int, browser: NWBrowser) {
        guard phase != .finished, peers[index].browser === browser else { return }
        let observing = acceptingObservation()
        if case .cancelled = state, cancellationCallbackInTime() {
            peers[index].observation.browserCancelled = true
        }
        if observing {
            switch state {
            case .setup:
                peers[index].observation.browserLastState = .setup
                clearCurrent(index: index)
            case .waiting(let error):
                peers[index].observation.browserLastState = .waiting
                peers[index].observation.browserError = ErrorObservation(error)
                bump(\.browserWaiting, index: index)
                clearCurrent(index: index)
            case .ready:
                peers[index].observation.browserLastState = .ready
                maybeStartDNSBrowse()
                bump(\.browserReady, index: index)
            case .failed(let error):
                peers[index].observation.browserLastState = .failed
                peers[index].observation.browserError = ErrorObservation(error)
                bump(\.browserFailed, index: index)
                clearCurrent(index: index)
            case .cancelled:
                peers[index].observation.browserLastState = .cancelled
                clearCurrent(index: index)
            @unknown default:
                peers[index].observation.browserLastState = .unknown
                clearCurrent(index: index)
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
                    maybeStartDNSBrowse()
                } else {
                    peers[index].observation.registrationNameChanged = true
                    invalidateDNSResolve(index)
                }
            }
        case .remove:
            bump(\.registrationRemoved, index: index)
            invalidateDNSResolve(index)
            clearCurrent(index: 1 - index)
        @unknown default:
            counterOverflow = true  // An unrepresented registration event is not silently accepted.
        }
    }

    private func clearCurrent(index: Int) {
        peers[index].endpointSnapshot = nil
        let previous = peers[index].observation.txtMetadata
        var current = TXTMetadataObservation()
        current.observations = previous.observations
        current.matchingObservations = previous.matchingObservations
        current.malformedObservations = previous.malformedObservations
        peers[index].observation.txtMetadata = current
        peers[index].observation.interfaces = InterfaceObservation()
    }

    private func bumpMetadata(_ key: WritableKeyPath<TXTMetadataObservation, Int>,
                              observation: inout TXTMetadataObservation) {
        if observation[keyPath: key] < 65_535 {
            observation[keyPath: key] += 1
        } else {
            counterOverflow = true
        }
    }

    private func interfaceKind(_ interface: NWInterface) -> InterfaceKind {
        switch interface.type {
        case .cellular: return .cellular
        case .loopback: return .loopback
        case .other: return .other
        case .wifi: return .wifi
        case .wiredEthernet: return .wiredEthernet
        default: return .unknown
        }
    }

    private func interfaceIdentity(_ interface: NWInterface) -> InterfaceIdentity {
        var value = UInt32(exactly: interface.index)
        if let index = value, index == 0 || index > 0x7fff_ffff { value = nil }
        return InterfaceIdentity(index: value, kind: interfaceKind(interface))
    }

    private func interfaceRelation(_ identity: InterfaceIdentity?, resolved: UInt32?) -> InterfaceRelation {
        guard let identity = identity else { return .unavailable }
        guard let index = identity.index else { return .invalid }
        guard let resolved = resolved else { return .unavailable }
        // Numeric comparison only. In particular LocalOnly is never translated into loopback.
        return index == resolved ? .equal : .different
    }

    private func endpointJoin(index: Int) -> EndpointJoinObservation {
        var joined = EndpointJoinObservation()
        let peer = peers[index]
        let owned = peer.observation.txtMetadata.ownedResults
        guard owned > 0 else { return joined }
        joined.endpointRelation = .unavailable
        joined.resultRelation = .unavailable
        guard owned == 1 else {
            joined.ambiguous = true
            joined.endpointRelation = .ambiguous
            joined.resultRelation = .ambiguous
            return joined
        }
        guard let snapshot = peer.endpointSnapshot else {
            joined.endpointRelation = .invalid
            joined.resultRelation = .invalid
            return joined
        }
        joined.endpointKind = snapshot.endpointInterface?.kind.rawValue ?? "none"
        let resultIndices = Set(snapshot.resultInterfaces.compactMap { $0.index })
        guard resultIndices.count <= 1 else {
            joined.ambiguous = true
            joined.endpointRelation = .ambiguous
            joined.resultRelation = .ambiguous
            return joined
        }
        let invalidResult = snapshot.resultInterfaces.contains { $0.index == nil }
        let endpoint = snapshot.endpointInterface
        let singleResult = snapshot.resultInterfaces.first
        let consistentKinds = endpoint.map { expected in
            snapshot.resultInterfaces.allSatisfy { $0.kind == expected.kind }
        } == true
        let configuration = peer.observation.configuration
        joined.policyCompatible = endpoint?.index != nil && singleResult?.index != nil &&
            !invalidResult && consistentKinds && endpoint?.kind != .cellular && endpoint?.kind != .unknown &&
            configuration.browserObserved && configuration.browserTransport == .none &&
            configuration.browserP2P && configuration.browserCellBan && !configuration.browserIncludesTXT

        let other = peers[1 - index]
        let resolved = other.observation.dnsResolve
        let live = peers.allSatisfy { current in
            let observed = current.observation
            return observed.ownRegistrationObserved && !observed.registrationNameChanged &&
                observed.registrationRemoved == 0 && observed.listenerReady > 0 && observed.browserReady > 0 &&
                observed.listenerLastState == .ready && observed.browserLastState == .ready
        }
        let usable = live && !counterOverflow && dnsBrowse.errorCode == 0 &&
            !dnsBrowse.ambiguous && !dnsBrowse.unsupportedScope && resolved.matchesExpected &&
            !resolved.invalidated && resolved.errorCode == 0 && resolved.callbacks == 1 &&
            resolved.matchingCallbacks == 1 && resolved.identityMatched && resolved.received &&
            resolved.bytes > 0 && resolved.portMatches && resolved.scopeValid
        let returnedIndex = usable ? other.resolvedInterfaceIndex : nil
        if usable, returnedIndex != nil, let context = other.dnsContext {
            // Both domains/types already passed the closed owned-service callback guards.
            let type = snapshot.type == Self.serviceType + "." ? Self.serviceType : snapshot.type
            let dnsType = context.type == Self.serviceType + "." ? Self.serviceType : context.type
            let domain = snapshot.domain == "local." ? "local" : snapshot.domain
            let dnsDomain = context.domain == "local." ? "local" : context.domain
            joined.tupleMatched = snapshot.name == context.name && context.name == names[1 - index] &&
                type == dnsType && domain == dnsDomain
        }
        joined.endpointRelation = interfaceRelation(endpoint, resolved: returnedIndex)
        joined.resultRelation = invalidResult ? .invalid : interfaceRelation(singleResult, resolved: returnedIndex)
        joined.initialResolveJoined = joined.tupleMatched && joined.policyCompatible &&
            joined.endpointRelation == .equal && joined.resultRelation == .equal && usable
        return joined
    }

    private func results(_ results: Set<NWBrowser.Result>, index: Int, browser: NWBrowser) {
        guard peers[index].browser === browser, acceptingObservation() else { return }
        bump(\.resultCallbacks, index: index)
        if peers[index].observation.firstResultMilliseconds < 0 {
            peers[index].observation.firstResultMilliseconds = dnsMilliseconds()
        }
        peers[index].observation.maximumResultCount = max(
            peers[index].observation.maximumResultCount, min(results.count, 65_535)
        )
        // A complete current result set replaces the prior snapshot, including absence/removal.
        // Stale browser callbacks cannot clear or restore another instance's observations.
        clearCurrent(index: index)
        guard results.count <= 128 else { counterOverflow = true; return }
        guard peers[index].observation.browserLastState == .ready,
              peers[index].observation.listenerLastState == .ready,
              peers[1 - index].observation.listenerLastState == .ready else { return }
        guard let expected = txtRecord(index: 1 - index),
              let expectedValues = decodeOwnedTXT(expected) else { setupFailed = true; return }
        var metadata = peers[index].observation.txtMetadata
        var interfaces = InterfaceObservation()
        var metadataKinds = Set<MetadataKind>()
        var interfaceKinds = Set<InterfaceKind>()
        var allIdentity = true
        var allSemantic = true
        var allRaw = true
        defer {
            metadata.kind = metadataKinds.count > 1 ? .mixed : (metadataKinds.first ?? .none)
            interfaces.kinds = interfaceKinds.sorted { $0.rawValue < $1.rawValue }
            peers[index].observation.txtMetadata = metadata
            peers[index].observation.interfaces = interfaces
        }
        for result in results {
            // Guard the OTHER exact owned endpoint BEFORE metadata, TXT Data or interface access.
            guard case .service(let name, let type, let domain, let endpointInterface) = result.endpoint,
                  name == names[1 - index],
                  type == Self.serviceType || type == Self.serviceType + ".",
                  domain == "local." || domain == "local" else { continue }
            peers[index].observation.expectedPeerObserved = true
            metadata.ownedResults += 1
            bumpMetadata(\.observations, observation: &metadata)
            interfaces.observed = true
            guard result.interfaces.count <= 128,
                  interfaces.count + result.interfaces.count <= 128 else {
                counterOverflow = true
                return
            }
            var resultIdentities: [InterfaceIdentity] = []
            for interface in result.interfaces {
                interfaces.count += 1
                let identity = interfaceIdentity(interface)
                interfaceKinds.insert(identity.kind)
                resultIdentities.append(identity)
            }
            // Never choose one of several current owned results to manufacture a join.
            peers[index].endpointSnapshot = metadata.ownedResults == 1 ? EndpointSnapshot(
                name: name, type: type, domain: domain,
                endpointInterface: endpointInterface.map { interfaceIdentity($0) },
                resultInterfaces: resultIdentities
            ) : nil
            switch result.metadata {
            case .bonjour(let record):
                metadataKinds.insert(.bonjour)
                guard #available(iOS 16.0, *) else { setupFailed = true; return }
                // Preserve actual API-delivered bytes; never reconstruct a dictionary as original Data.
                let received = record.data
                metadata.received = true
                metadata.present = metadata.present || !received.isEmpty
                guard received.count <= 65_535 else { counterOverflow = true; return }
                metadata.maximumBytes = max(metadata.maximumBytes, received.count)
                guard let values = decodeOwnedTXT(received) else {
                    metadata.malformed = true
                    bumpMetadata(\.malformedObservations, observation: &metadata)
                    allIdentity = false
                    allSemantic = false
                    allRaw = false
                    continue
                }
                allIdentity = allIdentity && values["pid"] == expectedValues["pid"]
                let matches = values == expectedValues
                if matches { bumpMetadata(\.matchingObservations, observation: &metadata) }
                allSemantic = allSemantic && matches
                allRaw = allRaw && received == expected
            case .none:
                metadataKinds.insert(.none)
                allIdentity = false
                allSemantic = false
                allRaw = false
            default:
                metadataKinds.insert(.other)
                allIdentity = false
                allSemantic = false
                allRaw = false
            }
        }
        metadata.identityMatched = metadata.ownedResults > 0 && allIdentity
        metadata.matchesExpected = metadata.ownedResults > 0 && allSemantic && !metadata.malformed && !counterOverflow
        metadata.rawMatchesExpected = metadata.matchesExpected && allRaw
        // Equality is an owned API observation, not reachability, permission or wire-capture proof.
    }

    private func cancellationCallbackInTime() -> Bool {
        phase == .observing || (phase == .cancelling && DispatchTime.now().uptimeNanoseconds <= cancellationDeadline)
    }

    private func beginCancellation() {
        guard phase == .observing else { return }
        let now = DispatchTime.now().uptimeNanoseconds
        observationElapsed = Int((now - startedAt) / 1_000_000)
        if peers.contains(where: { $0.listener == nil || $0.browser == nil }) { setupFailed = true }
        for index in peers.indices {
            // Freeze current same-live joins BEFORE retiring either DNS ref or clearing any peer.
            peers[index].cutoffEndpointJoin = endpointJoin(index: index)
            peers[index].cutoffInterfaces = peers[index].observation.interfaces
            peers[index].cutoffMetadata = peers[index].observation.txtMetadata
        }
        phase = .cancelling
        retireDNSBrowse()
        for index in peers.indices { retireDNSResolve(index) }
        cancellationStartedAt = now
        cancellationDeadline = now + Self.cancellationNanoseconds
        for index in peers.indices {
            clearCurrent(index: index)
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
                (peer.browser == nil || peer.observation.browserCancelled)
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
        let complete = allCancelled() && dnsBrowse.created == dnsBrowse.retired &&
            peers.allSatisfy { $0.observation.dnsResolve.created == $0.observation.dnsResolve.retired } &&
            now <= cancellationDeadline &&
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
        else if peers.allSatisfy({ peer in
            let observed = peer.observation
            return observed.ownRegistrationObserved && !observed.registrationNameChanged &&
                observed.expectedPeerObserved && observed.listenerReady > 0 && observed.browserReady > 0 &&
                observed.listenerLastState == .ready && observed.browserLastState == .ready &&
                peer.cutoffMetadata?.matchesExpected == true
        }) { outcome = .discovered }
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
            mode: mode, browserDescriptor: policy, outcome: outcome, observationElapsedMilliseconds: observationElapsed,
            cleanupElapsedMilliseconds: cleanupElapsed, isSimulatorBuild: simulatorBuild,
            isX86_64Build: intelBuild, counterOverflow: counterOverflow, packaging: packaging,
            peers: peers.map { peer in
                var observed = peer.observation
                observed.interfaces = peer.cutoffInterfaces ?? InterfaceObservation()
                observed.txtMetadata = peer.cutoffMetadata ?? TXTMetadataObservation()
                observed.endpointJoin = mode == .cli ? (peer.cutoffEndpointJoin ?? EndpointJoinObservation()) : nil
                return observed
            }, cleanup: cleanup, dnsBrowse: dnsBrowse
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
            peer.dnsContext = nil
            peer.resolvedInterfaceIndex = nil
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
