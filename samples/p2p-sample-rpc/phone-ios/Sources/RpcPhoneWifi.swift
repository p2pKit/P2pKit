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

enum RpcPhoneWifiSelection {
    static func select(wifiDefaultPath: Bool, wifiInterfaces: [String],
                       addresses: [RpcPhoneWifiAddress]) -> RpcPhoneWifiNetwork? {
        guard wifiDefaultPath, wifiInterfaces.count == 1, let name = wifiInterfaces.first,
              (1...32).contains(name.utf8.count),
              name.utf8.allSatisfy({ (65...90).contains($0) || (97...122).contains($0) ||
                  (48...57).contains($0) || [45, 46, 95].contains($0) }) else { return nil }
        let forbidden = ["lo", "utun", "tun", "tap", "wg", "ppp", "ipsec", "vpn", "awdl", "llw",
                         "gif", "stf", "veth", "docker", "vbox", "vmnet", "bridge"]
        guard !forbidden.contains(where: { name.lowercased().hasPrefix($0) }) else { return nil }
        // Do not guess among aliases or silently ignore another public/invalid IPv4 address.
        let selected = addresses.filter { $0.interfaceName == name }
        guard selected.count == 1, let row = selected.first,
              row.flags & UInt32(IFF_UP | IFF_RUNNING) == UInt32(IFF_UP | IFF_RUNNING),
              row.flags & UInt32(IFF_LOOPBACK | IFF_POINTOPOINT) == 0,
              let address = ipv4(row.address), let mask = ipv4(row.netmask) else { return nil }
        let hostMask = ~mask
        let prefix = mask.nonzeroBitCount
        guard hostMask & (hostMask &+ 1) == 0, let minimum = privatePrefix(address),
              (minimum...30).contains(prefix), address & hostMask != 0,
              address & hostMask != hostMask else { return nil }
        return RpcPhoneWifiNetwork(interfaceName: name, localAddress: row.address,
                                   subnet: "\(text(address & mask))/\(prefix)")
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
    func start(_ changed: @escaping (RpcPhoneWifiNetwork?) -> Void)
    func currentNetwork() -> RpcPhoneWifiNetwork?
    func stop()
}

/// Ordinary default-path observation only: no packets, forced interface, SSID/location access or settings changes.
@MainActor
final class RpcPhoneWifiObserver: RpcPhoneWifiObserving {
    private var monitor: NWPathMonitor?
    private var generation: UUID?
    private let queue = DispatchQueue(label: "dev.p2pkit.rpc.phone.wifi")

    func start(_ changed: @escaping (RpcPhoneWifiNetwork?) -> Void) {
        stop()
        let token = UUID()
        let monitor = NWPathMonitor()
        generation = token
        self.monitor = monitor
        monitor.pathUpdateHandler = { [weak self] _ in
            Task { @MainActor [weak self] in
                guard let self, self.generation == token else { return }
                changed(self.currentNetwork())
            }
        }
        monitor.start(queue: queue)
    }

    func currentNetwork() -> RpcPhoneWifiNetwork? {
        guard let path = monitor?.currentPath else { return nil }
        let wifiOnly = path.status == .satisfied && path.supportsIPv4 && path.usesInterfaceType(.wifi) &&
            ![NWInterface.InterfaceType.cellular, .wiredEthernet, .loopback, .other].contains {
                path.usesInterfaceType($0)
            }
        return RpcPhoneWifiSelection.select(wifiDefaultPath: wifiOnly,
            wifiInterfaces: path.availableInterfaces.filter { $0.type == .wifi }.map(\.name),
            addresses: Self.addresses())
    }

    func stop() {
        generation = nil
        monitor?.pathUpdateHandler = nil
        monitor?.cancel()
        monitor = nil
    }

    deinit { monitor?.cancel() }

    private static func addresses() -> [RpcPhoneWifiAddress] {
        var first: UnsafeMutablePointer<ifaddrs>?
        guard getifaddrs(&first) == 0, let first else { return [] }
        defer { freeifaddrs(first) }
        var result: [RpcPhoneWifiAddress] = []
        var cursor: UnsafeMutablePointer<ifaddrs>? = first
        var count = 0
        while let entry = cursor {
            count += 1
            guard count <= 256 else { return [] }
            let row = entry.pointee
            if let name = row.ifa_name, let address = row.ifa_addr, let mask = row.ifa_netmask,
               address.pointee.sa_family == UInt8(AF_INET), mask.pointee.sa_family == UInt8(AF_INET),
               let numericAddress = numeric(address), let numericMask = numeric(mask) {
                result.append(RpcPhoneWifiAddress(interfaceName: String(cString: name), address: numericAddress,
                                                  netmask: numericMask, flags: row.ifa_flags))
            }
            cursor = row.ifa_next
        }
        return result
    }

    private static func numeric(_ address: UnsafePointer<sockaddr>) -> String? {
        var buffer = [CChar](repeating: 0, count: Int(NI_MAXHOST))
        guard getnameinfo(address, socklen_t(address.pointee.sa_len), &buffer, socklen_t(buffer.count),
                          nil, 0, NI_NUMERICHOST) == 0 else { return nil }
        return String(cString: buffer)
    }
}
