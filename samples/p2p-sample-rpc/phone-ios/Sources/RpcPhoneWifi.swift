import Darwin
import Foundation
import Network

/// A suggestion from this device, not approval, peer discovery or proof of LAN reachability.
struct RpcPhoneWifiNetwork: Equatable {
    let interfaceName: String
    let localAddress: String
    let subnet: String
}

struct RpcPhoneWifiAddress {
    let interfaceName: String
    let address: String
    let netmask: String
    let flags: UInt32
}

/// Repeated path entries are the same interface only when their OS name and index both agree.
struct RpcPhoneWifiInterface: Hashable {
    let name: String
    let index: Int

    static func safeName(_ name: String) -> Bool {
        (1...32).contains(name.utf8.count) && name.utf8.allSatisfy {
            (65...90).contains($0) || (97...122).contains($0) ||
                (48...57).contains($0) || [45, 46, 95].contains($0)
        }
    }

    static func read(_ interfaces: [RpcPhoneWifiInterface], currentIndex: (String) -> UInt32)
        -> (names: [String], details: String, failure: RpcPhoneWifiIssue?) {
        var unique: [RpcPhoneWifiInterface] = []
        var entries: [String] = []
        var failure: RpcPhoneWifiIssue?
        for interface in interfaces {
            let safe = safeName(interface.name)
            let registered = safe ? currentIndex(interface.name) : 0
            let index = UInt32(exactly: interface.index)
            if !safe { failure = failure ?? .unsafeInterface }
            if registered == 0 || index != registered || unique.contains(where: {
                ($0.name == interface.name && $0.index != interface.index) ||
                    ($0.index == interface.index && $0.name != interface.name)
            }) { failure = failure ?? .interfaceIdentityMismatch }
            if !unique.contains(interface) { unique.append(interface) }
            if entries.count < 8 {
                entries.append("\(safe ? interface.name : "[invalid name]")#\(interface.index) (system \(registered))")
            }
        }
        let details = "Offered Wi-Fi entries: \(interfaces.count); distinct name/index identities: \(unique.count); " +
            "repeated entries: \(interfaces.count - unique.count); identities: " +
            "\(entries.isEmpty ? "none" : entries.joined(separator: ", "))\(interfaces.count > 8 ? "; more omitted" : "")."
        return (unique.map(\.name), details, failure)
    }
}

enum RpcPhoneWifiIssue: String, Error {
    case pathUnavailable, pathNeedsConnection, noIPv4, notWifiPath, mixedPath
    case noWifiInterface, ambiguousWifiInterfaces, unsafeInterface
    case noWifiAddress, ambiguousWifiAddresses, interfaceInactive, nonLanInterface
    case invalidAddress, invalidMask, noncontiguousMask, nonPrivateAddress, unsupportedSubnet, nonHostAddress
    case addressReadFailed, addressListTooLong, addressDecodeFailed, interfaceIdentityMismatch

    var explanation: String {
        switch self {
        case .pathUnavailable: return "iOS is not reporting an available default network path to this app."
        case .pathNeedsConnection: return "iOS reports that the default network path still requires a connection."
        case .noIPv4: return "The app's default network path does not report IPv4 support. Automatic setup needs IPv4."
        case .notWifiPath: return "The app's default network path is not using Wi-Fi, even if a Wi-Fi icon is visible."
        case .mixedPath: return "The app's default path also uses a non-Wi-Fi transport. Automatic setup cannot choose it."
        case .noWifiInterface: return "iOS did not report a Wi-Fi interface on the app's default path."
        case .ambiguousWifiInterfaces: return "More than one Wi-Fi entry has an IPv4 address. Automatic setup will not guess."
        case .unsafeInterface: return "The reported interface is not eligible for automatic private-LAN setup."
        case .noWifiAddress: return "No readable IPv4 address and netmask were found on the reported Wi-Fi interface."
        case .ambiguousWifiAddresses: return "The Wi-Fi interface has multiple IPv4 addresses. Automatic setup will not guess."
        case .interfaceInactive: return "The Wi-Fi interface is not reported as both up and running."
        case .nonLanInterface: return "The reported interface is loopback or point-to-point, not an eligible Wi-Fi LAN."
        case .invalidAddress: return "The Wi-Fi address is not a valid numeric IPv4 address."
        case .invalidMask: return "The Wi-Fi netmask could not be interpreted as an IPv4 mask."
        case .noncontiguousMask: return "The Wi-Fi netmask is noncontiguous. Automatic setup cannot derive a subnet."
        case .nonPrivateAddress: return "The Wi-Fi address is not in a private IPv4 range supported by automatic setup."
        case .unsupportedSubnet: return "The Wi-Fi subnet is not wholly private or has no supported host range."
        case .nonHostAddress: return "The reported Wi-Fi address is a subnet or broadcast address, not a host address."
        case .addressReadFailed: return "The app could not read this device's interface address list."
        case .addressListTooLong: return "The interface address list exceeds the app's existing safety limit."
        case .addressDecodeFailed: return "A Wi-Fi IPv4 address or netmask could not be read. Automatic setup will not ignore it."
        case .interfaceIdentityMismatch:
            return "Wi-Fi names and interface indices do not agree with the system. Check Wi-Fi again; the app will not guess."
        }
    }
}

/// The reason and candidate always come from one observation, never two unrelated reads.
enum RpcPhoneWifiObservation: Equatable {
    case checking
    case unavailable(RpcPhoneWifiIssue, details: String)
    case available(RpcPhoneWifiNetwork, details: String)

    var network: RpcPhoneWifiNetwork? {
        if case .available(let network, _) = self { return network }
        return nil
    }

    var issue: RpcPhoneWifiIssue? {
        if case .unavailable(let issue, _) = self { return issue }
        return nil
    }

    var explanation: String {
        switch self {
        case .checking: return "Waiting for this app's Wi-Fi observation. You can check again if it does not update."
        case .unavailable(let issue, _): return issue.explanation
        case .available: return "Private Wi-Fi detected. Review it, then tap Use this Wi-Fi."
        }
    }

    var details: String {
        switch self {
        case .checking: return "Check: waiting. No current path observation."
        case .unavailable(let issue, let details): return "Check: \(issue.rawValue). \(details)"
        case .available(_, let details): return "Check: available. \(details)"
        }
    }
}

struct RpcPhoneWifiAddressRead {
    let rows: [RpcPhoneWifiAddress]
    let details: String
    var failure: RpcPhoneWifiIssue? = nil

    static func scanned(rows: [RpcPhoneWifiAddress], wifiRows: Int, wifiDecoded: Int, missingMasks: Int,
                        decodeErrors: Set<Int32>) -> RpcPhoneWifiAddressRead {
        let errors = decodeErrors.sorted().map { String($0) }.joined(separator: ", ")
        let complete = wifiRows == wifiDecoded && missingMasks == 0 && decodeErrors.isEmpty
        return RpcPhoneWifiAddressRead(rows: rows, details: "Wi-Fi IPv4 rows: \(wifiRows); " +
            "decoded address/mask pairs: \(wifiDecoded); missing IPv4 masks: \(missingMasks); " +
            "numeric decoder errors: \(errors.isEmpty ? "none" : errors).",
            failure: complete ? nil : .addressDecodeFailed)
    }
}

enum RpcPhoneWifiSelection {
    static func observeInterfaces(status: NWPath.Status, supportsIPv4: Bool,
                                  usedTypes: [NWInterface.InterfaceType], interfaces: [RpcPhoneWifiInterface],
                                  systemReason: String = "none", currentIndex: (String) -> UInt32,
                                  readAddresses: ([String]) -> RpcPhoneWifiAddressRead) -> RpcPhoneWifiObservation {
        let identity = RpcPhoneWifiInterface.read(interfaces, currentIndex: currentIndex)
        return observe(status: status, supportsIPv4: supportsIPv4, usedTypes: usedTypes,
            wifiInterfaces: identity.names, systemReason: systemReason, readAddresses: {
                if let failure = identity.failure {
                    return RpcPhoneWifiAddressRead(rows: [], details: identity.details, failure: failure)
                }
                let read = readAddresses(identity.names)
                return RpcPhoneWifiAddressRead(rows: read.rows, details: identity.details + " " + read.details,
                                                failure: read.failure)
            })
    }

    static func select(wifiDefaultPath: Bool, wifiInterfaces: [String],
                       addresses: [RpcPhoneWifiAddress]) -> RpcPhoneWifiNetwork? {
        try? evaluate(wifiDefaultPath: wifiDefaultPath, wifiInterfaces: wifiInterfaces, addresses: addresses).get()
    }

    static func evaluate(wifiDefaultPath: Bool, wifiInterfaces: [String],
                         addresses: [RpcPhoneWifiAddress]) -> Result<RpcPhoneWifiNetwork, RpcPhoneWifiIssue> {
        guard wifiDefaultPath else { return .failure(.notWifiPath) }
        guard !wifiInterfaces.isEmpty else { return .failure(.noWifiInterface) }
        // NWPath may offer additional Wi-Fi interfaces with no IPv4 address. Select from the actual address
        // list, not the offered-interface count. Do not discard an addressed alternative because it is unsafe.
        let addressed = wifiInterfaces.filter { name in addresses.contains { $0.interfaceName == name } }
        guard !addressed.isEmpty else { return .failure(.noWifiAddress) }
        guard addressed.count == 1, let name = addressed.first else {
            return .failure(.ambiguousWifiInterfaces)
        }
        guard RpcPhoneWifiInterface.safeName(name) else { return .failure(.unsafeInterface) }
        let forbidden = ["lo", "utun", "tun", "tap", "wg", "ppp", "ipsec", "vpn", "awdl", "llw",
                         "gif", "stf", "veth", "docker", "vbox", "vmnet", "bridge"]
        guard !forbidden.contains(where: { name.lowercased().hasPrefix($0) }) else { return .failure(.unsafeInterface) }
        // Do not guess among aliases or silently ignore another public/invalid IPv4 address.
        let selected = addresses.filter { $0.interfaceName == name }
        guard !selected.isEmpty else { return .failure(.noWifiAddress) }
        guard selected.count == 1, let row = selected.first else { return .failure(.ambiguousWifiAddresses) }
        guard row.flags & UInt32(IFF_UP | IFF_RUNNING) == UInt32(IFF_UP | IFF_RUNNING) else {
            return .failure(.interfaceInactive)
        }
        guard row.flags & UInt32(IFF_LOOPBACK | IFF_POINTOPOINT) == 0 else { return .failure(.nonLanInterface) }
        guard let address = ipv4(row.address) else { return .failure(.invalidAddress) }
        guard let mask = ipv4(row.netmask) else { return .failure(.invalidMask) }
        let hostMask = ~mask
        let prefix = mask.nonzeroBitCount
        guard hostMask & (hostMask &+ 1) == 0 else { return .failure(.noncontiguousMask) }
        guard let minimum = privatePrefix(address) else { return .failure(.nonPrivateAddress) }
        guard (minimum...30).contains(prefix) else { return .failure(.unsupportedSubnet) }
        guard address & hostMask != 0, address & hostMask != hostMask else { return .failure(.nonHostAddress) }
        return .success(RpcPhoneWifiNetwork(interfaceName: name, localAddress: row.address,
                                           subnet: "\(text(address & mask))/\(prefix)"))
    }

    static func observe(status: NWPath.Status, supportsIPv4: Bool, usedTypes: [NWInterface.InterfaceType],
                        wifiInterfaces: [String], systemReason: String = "none",
                        readAddresses: () -> RpcPhoneWifiAddressRead) -> RpcPhoneWifiObservation {
        let statusName: String
        switch status {
        case .satisfied: statusName = "satisfied"
        case .unsatisfied: statusName = "unsatisfied"
        case .requiresConnection: statusName = "requiresConnection"
        @unknown default: statusName = "unknown"
        }
        let transports = usedTypes.map { type -> String in
            switch type {
            case .wifi: return "Wi-Fi"
            case .cellular: return "cellular"
            case .wiredEthernet: return "wired"
            case .loopback: return "loopback"
            case .other: return "other"
            @unknown default: return "unknown"
            }
        }.joined(separator: ", ")
        var details = "Default path: \(statusName); IPv4: \(supportsIPv4 ? "yes" : "no"); " +
            "used transports: \(transports.isEmpty ? "none" : transports); " +
            "Wi-Fi interfaces: \(wifiInterfaces.count); system reason: \(systemReason)."
        if status == .requiresConnection { return .unavailable(.pathNeedsConnection, details: details) }
        guard status == .satisfied else { return .unavailable(.pathUnavailable, details: details) }
        guard supportsIPv4 else { return .unavailable(.noIPv4, details: details) }
        guard usedTypes.contains(.wifi) else { return .unavailable(.notWifiPath, details: details) }
        guard usedTypes.allSatisfy({ $0 == .wifi }) else { return .unavailable(.mixedPath, details: details) }
        let read = readAddresses()
        details += " " + read.details
        if let failure = read.failure { return .unavailable(failure, details: details) }
        switch evaluate(wifiDefaultPath: true, wifiInterfaces: wifiInterfaces, addresses: read.rows) {
        case .success(let network): return .available(network, details: details)
        case .failure(let issue): return .unavailable(issue, details: details)
        }
    }

    private static func ipv4(_ value: String) -> UInt32? {
        let parts = value.split(separator: ".", omittingEmptySubsequences: false)
        guard parts.count == 4 else { return nil }
        var result: UInt32 = 0
        for part in parts {
            guard (1...3).contains(part.utf8.count), part.utf8.allSatisfy({ (48...57).contains($0) }),
                  part.count == 1 || part.first != "0", let octet = UInt8(part) else { return nil }
            result = (result << 8) | UInt32(octet)
        }
        return result
    }

    private static func privatePrefix(_ address: UInt32) -> Int? {
        if address >> 24 == 10 { return 8 }
        if address >> 20 == 0xac1 { return 12 }
        if address >> 16 == 0xc0a8 { return 16 }
        return nil
    }

    private static func text(_ address: UInt32) -> String {
        [24, 16, 8, 0].map { String((address >> $0) & 255) }.joined(separator: ".")
    }
}

@MainActor
protocol RpcPhoneWifiObserving: AnyObject {
    func start(_ changed: @escaping (RpcPhoneWifiObservation) -> Void)
    func currentObservation() -> RpcPhoneWifiObservation
    func stop()
}

/// Ordinary default-path observation only: no packets, forced interface, SSID/location access or settings changes.
@MainActor
final class RpcPhoneWifiObserver: RpcPhoneWifiObserving {
    private var monitor: NWPathMonitor?
    private var generation: UUID?
    private var receivedPath = false
    private let queue = DispatchQueue(label: "dev.p2pkit.rpc.phone.wifi")

    func start(_ changed: @escaping (RpcPhoneWifiObservation) -> Void) {
        stop()
        let token = UUID()
        let monitor = NWPathMonitor()
        generation = token
        self.monitor = monitor
        monitor.pathUpdateHandler = { [weak self] _ in
            Task { @MainActor [weak self] in
                guard let self, self.generation == token else { return }
                self.receivedPath = true
                changed(self.currentObservation())
            }
        }
        monitor.start(queue: queue)
    }

    func currentObservation() -> RpcPhoneWifiObservation {
        guard receivedPath, let path = monitor?.currentPath else { return .checking }
        let types: [NWInterface.InterfaceType] = [.wifi, .cellular, .wiredEthernet, .loopback, .other]
        let interfaces = path.availableInterfaces.filter { $0.type == .wifi }.map {
            RpcPhoneWifiInterface(name: $0.name, index: $0.index)
        }
        let reason: String
        if path.status == .unsatisfied {
            switch path.unsatisfiedReason {
            case .notAvailable: reason = "notAvailable"
            case .cellularDenied: reason = "cellularDenied"
            case .wifiDenied: reason = "wifiDenied"
            case .localNetworkDenied: reason = "localNetworkDenied"
            @unknown default: reason = "unknown"
            }
        } else { reason = "none" }
        return RpcPhoneWifiSelection.observeInterfaces(status: path.status, supportsIPv4: path.supportsIPv4,
            usedTypes: types.filter { path.usesInterfaceType($0) }, interfaces: interfaces, systemReason: reason,
            currentIndex: { if_nametoindex($0) }, readAddresses: { Self.addresses(wifiInterfaces: $0) })
    }

    func stop() {
        generation = nil
        receivedPath = false
        monitor?.pathUpdateHandler = nil
        monitor?.cancel()
        monitor = nil
    }

    deinit { monitor?.cancel() }

    private static func addresses(wifiInterfaces: [String]) -> RpcPhoneWifiAddressRead {
        var first: UnsafeMutablePointer<ifaddrs>?
        let code = getifaddrs(&first)
        let error = errno
        guard code == 0, let first else {
            return RpcPhoneWifiAddressRead(rows: [], details: "getifaddrs: \(code); errno: \(code == 0 ? 0 : error).",
                                            failure: .addressReadFailed)
        }
        defer { freeifaddrs(first) }
        var result: [RpcPhoneWifiAddress] = []
        var cursor: UnsafeMutablePointer<ifaddrs>? = first
        var count = 0
        var wifiRows = 0
        var wifiDecoded = 0
        var missingMask = 0
        var decodeErrors = Set<Int32>()
        while let entry = cursor {
            count += 1
            guard count <= 256 else {
                return RpcPhoneWifiAddressRead(rows: [], details: "More than 256 interface rows.",
                                                failure: .addressListTooLong)
            }
            let row = entry.pointee
            if let name = row.ifa_name, let address = row.ifa_addr, address.pointee.sa_family == UInt8(AF_INET) {
                let interface = String(cString: name)
                let isWifi = wifiInterfaces.contains(interface)
                if isWifi { wifiRows += 1 }
                if let mask = row.ifa_netmask, mask.pointee.sa_family == UInt8(AF_INET) {
                    let decodedAddress = numeric(address)
                    let decodedMask = numeric(mask)
                    if let value = decodedAddress.value, let maskValue = decodedMask.value {
                        result.append(RpcPhoneWifiAddress(interfaceName: interface, address: value,
                                                          netmask: maskValue, flags: row.ifa_flags))
                        if isWifi { wifiDecoded += 1 }
                    } else if isWifi {
                        for code in [decodedAddress.code, decodedMask.code] where code != 0 { decodeErrors.insert(code) }
                    }
                } else if isWifi { missingMask += 1 }
            }
            cursor = row.ifa_next
        }
        return RpcPhoneWifiAddressRead.scanned(rows: result, wifiRows: wifiRows, wifiDecoded: wifiDecoded,
                                               missingMasks: missingMask, decodeErrors: decodeErrors)
    }

    private static func numeric(_ address: UnsafePointer<sockaddr>) -> (value: String?, code: Int32) {
        var buffer = [CChar](repeating: 0, count: Int(NI_MAXHOST))
        let code = getnameinfo(address, socklen_t(address.pointee.sa_len), &buffer, socklen_t(buffer.count),
                               nil, 0, NI_NUMERICHOST)
        return (code == 0 ? String(cString: buffer) : nil, code)
    }
}

#if DEBUG
/// Explicit developer-launch diagnostics only: no addresses, settings, invitations or persistent telemetry.
enum RpcPhoneWifiDiagnostic {
    static let argument = "--rpc-wifi-diagnostic"
    static let prefix = "RPC_WIFI_DIAGNOSTIC "

    static func line(arguments: [String], observation: RpcPhoneWifiObservation, source: String,
                     canConfirm: Bool) -> String? {
        guard arguments.contains(argument), observation != .checking,
              source.utf8.count == 40,
              source.utf8.allSatisfy({ (48...57).contains($0) || (97...102).contains($0) }) else { return nil }
        let record: [String: Any] = [
            "scope": "PASSIVE_APP_WIFI_OBSERVATION_NOT_PEER_OR_MULTICAST_QUALIFICATION",
            "sourceCommit": source, "check": observation.issue?.rawValue ?? "available",
            "hasCandidate": observation.network != nil, "canConfirmWifi": canConfirm,
            "details": observation.details,
        ]
        guard let data = try? JSONSerialization.data(withJSONObject: record, options: [.sortedKeys]),
              let text = String(data: data, encoding: .utf8) else { return nil }
        return prefix + text
    }
}
#endif

#if DEBUG
/// Denial-only UI-test input: cannot inject a network, peer, permission grant or successful connection.
@MainActor
final class RpcPhoneUnavailableTestWifi: RpcPhoneWifiObserving {
    private let value = RpcPhoneWifiObservation.unavailable(.pathUnavailable,
        details: "Synthetic unavailable path for UI rejection tests.")
    func start(_ changed: @escaping (RpcPhoneWifiObservation) -> Void) { changed(value) }
    func currentObservation() -> RpcPhoneWifiObservation { value }
    func stop() {}
}
#endif
