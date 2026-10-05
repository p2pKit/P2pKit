import XCTest
import Combine
import Darwin
import Foundation
import CryptoKit
import Network
import UIKit
import P2pKitRpcExample
@testable import P2pKitRpcPhone

private final class SyntheticRuntime { var closes = 0 }
private enum SyntheticFailure: Error { case operation }

@MainActor
private final class SyntheticInvitationClipboard {
    let name = UIPasteboard.Name("dev.p2pkit.rpc.clipboard-test.\(UUID().uuidString)")
    lazy var board = UIPasteboard(name: name, create: true)!
    var now: TimeInterval = 1_000
    var timers: [() -> Void] = []
    var delays: [TimeInterval] = []
    var expirations = 0
    lazy var owner = RpcPhoneInvitationClipboard(pasteboard: board, uptime: { [unowned self] in self.now },
        schedule: { [unowned self] seconds, action in
            self.delays.append(seconds)
            self.timers.append(action)
            return {} // Deliberately permit late callbacks after cancellation.
        })

    func mint(_ value: String, started: TimeInterval? = nil) {
        let start = started ?? owner.beginMinting()
        owner.minted(value, started: start) { [weak self] in self?.expirations += 1 }
    }

    func close() { owner.retire(); UIPasteboard.remove(withName: name) }
}

@MainActor
private final class SyntheticWifiObserver: RpcPhoneWifiObserving {
    var observation: RpcPhoneWifiObservation = .checking
    var network: RpcPhoneWifiNetwork? {
        get { observation.network }
        set {
            observation = newValue.map { .available($0, details: "Synthetic observation.") } ??
                .unavailable(.noWifiAddress, details: "Synthetic observation.")
        }
    }
    var callbacks: [(RpcPhoneWifiObservation) -> Void] = []
    var stops = 0

    func start(_ changed: @escaping (RpcPhoneWifiObservation) -> Void) { callbacks.append(changed) }
    func currentObservation() -> RpcPhoneWifiObservation { observation }
    func stop() { stops += 1 }
    func publish(_ value: RpcPhoneWifiNetwork?) {
        network = value
        callbacks.last?(observation)
    }
    func publishObservation(_ value: RpcPhoneWifiObservation) {
        observation = value
        callbacks.last?(value)
    }
}

@MainActor
private final class Held<Value> {
    private var continuation: CheckedContinuation<Value, Error>?
    private var outcome: Result<Value, Error>?

    func wait() async throws -> Value {
        if let outcome { return try outcome.get() }
        return try await withCheckedThrowingContinuation { continuation = $0 }
    }

    func resolve(_ outcome: Result<Value, Error>) {
        guard self.outcome == nil else { return }
        self.outcome = outcome
        continuation?.resume(with: outcome)
        continuation = nil
    }
}

final class RpcPhoneRunOwnerTests: XCTestCase {
    @MainActor
    func testInvitationCopyIsExactLocalOnlyAndDoesNotExtendMintLifetime() {
        let fixture = SyntheticInvitationClipboard()
        defer { fixture.close() }
        let started = fixture.owner.beginMinting()
        fixture.now += 5
        fixture.mint("synthetic-invitation", started: started)
        XCTAssertFalse(fixture.board.hasStrings, "Minting alone must not copy")
        XCTAssertTrue(fixture.owner.copy())
        XCTAssertEqual(fixture.board.string, "synthetic-invitation")
        XCTAssertEqual(fixture.delays, [115])
        let expiry = Date(timeIntervalSince1970: 12_345)
        let options = RpcPhoneInvitationClipboard.options(expiration: expiry)
        XCTAssertEqual(options[.localOnly] as? Bool, true)
        XCTAssertEqual(options[.expirationDate] as? Date, expiry)
        fixture.now += 114.999
        XCTAssertTrue(fixture.owner.copy())
        fixture.now = started + 120
        XCTAssertFalse(fixture.owner.copy())
        XCTAssertFalse(fixture.board.hasStrings)
    }

    @MainActor
    func testInvitationRetirementPreservesUnrelatedClipboardContents() {
        let fixture = SyntheticInvitationClipboard()
        defer { fixture.close() }
        fixture.mint("synthetic-invitation")
        XCTAssertTrue(fixture.owner.copy())
        fixture.board.string = "synthetic-other-app"
        fixture.owner.retire()
        XCTAssertEqual(fixture.board.string, "synthetic-other-app")
        XCTAssertFalse(fixture.owner.copy())
        XCTAssertEqual(fixture.board.string, "synthetic-other-app")
    }

    @MainActor
    func testInvitationReplacementRejectsLateExpiryAndClearsOnlyItsOwnCopy() {
        let fixture = SyntheticInvitationClipboard()
        defer { fixture.close() }
        fixture.mint("first")
        XCTAssertTrue(fixture.owner.copy())
        let stale = fixture.timers[0]
        let start = fixture.owner.beginMinting()
        XCTAssertFalse(fixture.board.hasStrings)
        fixture.mint("second", started: start)
        XCTAssertTrue(fixture.owner.copy())
        stale()
        XCTAssertEqual(fixture.board.string, "second")
        XCTAssertEqual(fixture.expirations, 0)
        fixture.timers.last?()
        XCTAssertFalse(fixture.board.hasStrings)
        XCTAssertEqual(fixture.expirations, 1)
    }

    @MainActor
    func testSlowInvitationMintCannotPublishAnExpiredCopy() {
        let fixture = SyntheticInvitationClipboard()
        defer { fixture.close() }
        let start = fixture.owner.beginMinting()
        fixture.now += 120
        fixture.mint("synthetic-expired", started: start)
        XCTAssertFalse(fixture.owner.copy())
        XCTAssertTrue(fixture.timers.isEmpty)
        XCTAssertEqual(fixture.expirations, 1)
    }

    @MainActor
    func testModelStopAndBackgroundRetireCopyAndIdleCannotCopy() async {
        let fixture = SyntheticInvitationClipboard()
        defer { fixture.close() }
        let model = RpcPhoneModel(wifi: SyntheticWifiObserver(), invitationClipboard: fixture.owner)
        model.setForeground(true)
        model.invitation = "synthetic-invitation"
        model.revealInvitation = true
        model.copyInvitation()
        XCTAssertFalse(fixture.board.hasStrings, "Idle/client state must not copy a host invitation")
        fixture.mint("first")
        XCTAssertTrue(fixture.owner.copy())
        model.stop()
        XCTAssertFalse(fixture.board.hasStrings)
        XCTAssertTrue(model.invitation.isEmpty)
        XCTAssertFalse(model.revealInvitation)
        fixture.mint("second")
        XCTAssertTrue(fixture.owner.copy())
        model.setForeground(false)
        XCTAssertFalse(fixture.board.hasStrings)
        XCTAssertFalse(fixture.owner.copy())
        // Let the retained idle Stop task complete; no RPC runtime, trust or real clipboard is involved.
        await Task.yield()
    }

    private func wifiAddress(_ address: String = "192.168.1.6", mask: String = "255.255.255.0",
                             name: String = "en7", flags: UInt32 = UInt32(IFF_UP | IFF_RUNNING)) -> RpcPhoneWifiAddress {
        RpcPhoneWifiAddress(interfaceName: name, address: address, netmask: mask, flags: flags)
    }

    func testWifiSubnetDerivationUsesActualMaskAndInterface() {
        for (address, mask, subnet) in [
            ("192.168.1.6", "255.255.255.0", "192.168.1.0/24"),
            ("192.168.5.6", "255.255.254.0", "192.168.4.0/23"),
            ("192.168.5.6", "255.255.0.0", "192.168.0.0/16"),
            ("10.20.30.40", "255.0.0.0", "10.0.0.0/8"),
            ("172.20.30.40", "255.240.0.0", "172.16.0.0/12"),
            ("10.0.0.2", "255.255.255.252", "10.0.0.0/30"),
        ] {
            let network = RpcPhoneWifiSelection.select(wifiDefaultPath: true, wifiInterfaces: ["en7"],
                addresses: [wifiAddress(address, mask: mask), wifiAddress("10.1.2.3", name: "pdp_ip0")])
            XCTAssertEqual(network, RpcPhoneWifiNetwork(interfaceName: "en7", localAddress: address, subnet: subnet))
        }
    }

    func testWifiSelectionRejectsPublicUnsafeAmbiguousOrNonWifiPaths() {
        for address in ["8.8.8.8", "127.0.0.1", "169.254.1.2", "172.15.1.2", "172.32.1.2", "192.169.1.2"] {
            XCTAssertNil(RpcPhoneWifiSelection.select(wifiDefaultPath: true, wifiInterfaces: ["en7"],
                addresses: [wifiAddress(address)]))
        }
        for name in ["utun0", "awdl0", "lo0", "bridge0", "pdp/ip0", "", String(repeating: "e", count: 33)] {
            XCTAssertNil(RpcPhoneWifiSelection.select(wifiDefaultPath: true, wifiInterfaces: [name],
                addresses: [wifiAddress(name: name)]))
        }
        for flags in [UInt32(0), UInt32(IFF_UP), UInt32(IFF_UP | IFF_RUNNING | IFF_LOOPBACK),
                      UInt32(IFF_UP | IFF_RUNNING | IFF_POINTOPOINT)] {
            XCTAssertNil(RpcPhoneWifiSelection.select(wifiDefaultPath: true, wifiInterfaces: ["en7"],
                addresses: [wifiAddress(flags: flags)]))
        }
        for names in [[], ["en8"]] {
            XCTAssertNil(RpcPhoneWifiSelection.select(wifiDefaultPath: true, wifiInterfaces: names,
                addresses: [wifiAddress()]))
        }
        XCTAssertNil(RpcPhoneWifiSelection.select(wifiDefaultPath: false, wifiInterfaces: ["en7"],
            addresses: [wifiAddress()]))
        XCTAssertNil(RpcPhoneWifiSelection.select(wifiDefaultPath: true, wifiInterfaces: ["en7"], addresses: []))
        for alias in ["192.168.1.7", "8.8.8.8"] {
            XCTAssertNil(RpcPhoneWifiSelection.select(wifiDefaultPath: true, wifiInterfaces: ["en7"],
                addresses: [wifiAddress(), wifiAddress(alias)]))
        }
    }

    func testWifiSelectionRejectsMalformedMasksAndNonHostAddresses() {
        for mask in ["255.0.255.0", "0.0.0.0", "255.0.0.0", "255.255.255.254", "255.255.255.255",
                     "255.255.255", "255.255.255.256", "255.255.255.00", "255.255.255.0\n"] {
            XCTAssertNil(RpcPhoneWifiSelection.select(wifiDefaultPath: true, wifiInterfaces: ["en7"],
                addresses: [wifiAddress(mask: mask)]))
        }
        for address in ["192.168.1.0", "192.168.1.255", "192.168.01.6", "192.168.1.6\n", "192.168.1.+6",
                        "192.168.1.256", "192.168.1", "phone.local", "::1"] {
            XCTAssertNil(RpcPhoneWifiSelection.select(wifiDefaultPath: true, wifiInterfaces: ["en7"],
                addresses: [wifiAddress(address)]))
        }
    }

    func testWifiPathDiagnosticsDistinguishUnavailableIpv4NonWifiAndMixedPaths() {
        let cases: [(NWPath.Status, Bool, [NWInterface.InterfaceType], RpcPhoneWifiIssue)] = [
            (.unsatisfied, true, [.wifi], .pathUnavailable),
            (.requiresConnection, true, [.wifi], .pathNeedsConnection),
            (.satisfied, false, [.wifi], .noIPv4),
            (.satisfied, true, [], .notWifiPath),
            (.satisfied, true, [.cellular], .notWifiPath),
            (.satisfied, true, [.wiredEthernet], .notWifiPath),
            (.satisfied, true, [.loopback], .notWifiPath),
            (.satisfied, true, [.other], .notWifiPath),
            (.satisfied, true, [.wifi, .cellular], .mixedPath),
            (.satisfied, true, [.wifi, .wiredEthernet], .mixedPath),
            (.satisfied, true, [.wifi, .loopback], .mixedPath),
            (.satisfied, true, [.wifi, .other], .mixedPath),
        ]
        for (status, ipv4, types, issue) in cases {
            let result = RpcPhoneWifiSelection.observe(status: status, supportsIPv4: ipv4,
                usedTypes: types, wifiInterfaces: ["en7"], systemReason: "notAvailable", readAddresses: {
                    XCTFail("Do not read addresses to rescue a rejected default path")
                    return RpcPhoneWifiAddressRead(rows: [self.wifiAddress()], details: "Synthetic address read.")
                })
            XCTAssertNil(result.network)
            XCTAssertEqual(result.issue, issue)
            XCTAssertEqual(result.explanation, issue.explanation)
            XCTAssertTrue(result.details.contains("Check: \(issue.rawValue)."))
            XCTAssertTrue(result.details.contains("system reason: notAvailable"))
            XCTAssertFalse(result.details.contains("192.168"), "Diagnostics do not include raw network addresses")
        }
        var reads = 0
        let available = RpcPhoneWifiSelection.observe(status: .satisfied, supportsIPv4: true,
            usedTypes: [.wifi], wifiInterfaces: ["en7"], readAddresses: {
                reads += 1
                return RpcPhoneWifiAddressRead(rows: [self.wifiAddress()], details: "Synthetic address read.")
            })
        XCTAssertEqual(reads, 1)
        XCTAssertEqual(available.network, RpcPhoneWifiSelection.select(wifiDefaultPath: true,
            wifiInterfaces: ["en7"], addresses: [wifiAddress()]))
        XCTAssertNil(available.issue)
        XCTAssertTrue(available.details.contains("Default path: satisfied; IPv4: yes; used transports: Wi-Fi"))
    }

    func testWifiAddressDiagnosticsIdentifyEachExistingRejectionWithoutAdmittingIt() {
        let cases: [([String], [RpcPhoneWifiAddress], RpcPhoneWifiIssue)] = [
            ([], [wifiAddress()], .noWifiInterface),
            (["en7", "en8"], [wifiAddress(), wifiAddress("10.1.2.3", name: "en8")], .ambiguousWifiInterfaces),
            (["bad/name"], [wifiAddress(name: "bad/name")], .unsafeInterface),
            (["utun0"], [wifiAddress(name: "utun0")], .unsafeInterface),
            (["en7"], [], .noWifiAddress),
            (["en7"], [wifiAddress(), wifiAddress("192.168.1.7")], .ambiguousWifiAddresses),
            (["en7"], [wifiAddress(flags: UInt32(IFF_UP))], .interfaceInactive),
            (["en7"], [wifiAddress(flags: UInt32(IFF_UP | IFF_RUNNING | IFF_POINTOPOINT))], .nonLanInterface),
            (["en7"], [wifiAddress("192.168.01.6")], .invalidAddress),
            (["en7"], [wifiAddress(mask: "255.255.255.00")], .invalidMask),
            (["en7"], [wifiAddress(mask: "255.0.255.0")], .noncontiguousMask),
            (["en7"], [wifiAddress("8.8.8.8")], .nonPrivateAddress),
            (["en7"], [wifiAddress(mask: "255.0.0.0")], .unsupportedSubnet),
            (["en7"], [wifiAddress("192.168.1.0")], .nonHostAddress),
            (["en7"], [wifiAddress("192.168.1.255")], .nonHostAddress),
        ]
        for (names, rows, issue) in cases {
            let observation = RpcPhoneWifiSelection.observe(status: .satisfied, supportsIPv4: true,
                usedTypes: [.wifi], wifiInterfaces: names,
                readAddresses: { RpcPhoneWifiAddressRead(rows: rows, details: "Synthetic address read.") })
            XCTAssertNil(observation.network)
            XCTAssertEqual(observation.issue, issue)
            XCTAssertTrue(observation.details.contains("Synthetic address read."))
            XCTAssertFalse(observation.details.contains("192.168"))
            XCTAssertNil(RpcPhoneWifiSelection.select(wifiDefaultPath: true, wifiInterfaces: names, addresses: rows))
        }
        for issue in [RpcPhoneWifiIssue.addressReadFailed, .addressListTooLong, .addressDecodeFailed] {
            let observation = RpcPhoneWifiSelection.observe(status: .satisfied, supportsIPv4: true,
                usedTypes: [.wifi], wifiInterfaces: ["en7"], readAddresses: {
                    RpcPhoneWifiAddressRead(rows: [self.wifiAddress()], details: "Synthetic failed read.", failure: issue)
                })
            XCTAssertNil(observation.network, "A failed read cannot use partial rows")
            XCTAssertEqual(observation.issue, issue)
        }
    }

    func testWifiSelectionUsesTheSingleAddressedInterfaceNotTheOfferedInterfaceCount() {
        let expected = RpcPhoneWifiNetwork(interfaceName: "en7", localAddress: "192.168.1.6", subnet: "192.168.1.0/24")
        for names in [["en7", "en8"], ["en8", "en7"], ["awdl0", "en7"], ["en7", "llw0", "en8"]] {
            let rows = [wifiAddress(), wifiAddress("10.1.2.3", name: "pdp_ip0")]
            let read = RpcPhoneWifiAddressRead.scanned(rows: rows, wifiRows: 1, wifiDecoded: 1,
                                                      missingMasks: 0, decodeErrors: [])
            let observation = RpcPhoneWifiSelection.observe(status: .satisfied, supportsIPv4: true,
                usedTypes: [.wifi], wifiInterfaces: names, readAddresses: { read })
            XCTAssertEqual(observation.network, expected,
                           "An extra offered Wi-Fi interface without IPv4 is not another IPv4 LAN candidate")
            XCTAssertNil(observation.issue)
            XCTAssertTrue(observation.details.contains("Wi-Fi interfaces: \(names.count)"))
            XCTAssertTrue(observation.details.contains("Wi-Fi IPv4 rows: 1"))
            XCTAssertEqual(RpcPhoneWifiSelection.select(wifiDefaultPath: true, wifiInterfaces: names,
                addresses: rows), expected)
        }
    }

    func testWifiSelectionNeverIgnoresAddressedAlternativesOrIncompleteWifiAddressReads() {
        let alternatives = [
            wifiAddress("192.168.1.7", name: "en8"),
            wifiAddress("8.8.8.8", name: "en8"),
            wifiAddress("invalid", name: "en8"),
            wifiAddress("192.168.1.7", name: "en8", flags: UInt32(IFF_UP)),
            wifiAddress("192.168.1.7", mask: "invalid", name: "en8"),
            wifiAddress("192.168.1.7", name: "awdl0"),
        ]
        for alternative in alternatives {
            let result = RpcPhoneWifiSelection.evaluate(wifiDefaultPath: true,
                wifiInterfaces: ["en7", alternative.interfaceName], addresses: [wifiAddress(), alternative])
            guard case .failure(.ambiguousWifiInterfaces) = result else {
                XCTFail("A public, inactive, invalid or auxiliary addressed alternative is still ambiguous")
                continue
            }
        }
        XCTAssertNil(RpcPhoneWifiSelection.select(wifiDefaultPath: true, wifiInterfaces: ["en7", "en7"],
            addresses: [wifiAddress()]), "Duplicate reported entries must not silently collapse")
        for (raw, decoded, masks, errors) in [(2, 1, 0, Set<Int32>([-6])), (2, 1, 1, []), (2, 1, 0, [])] {
            let read = RpcPhoneWifiAddressRead.scanned(rows: [wifiAddress()], wifiRows: raw, wifiDecoded: decoded,
                                                      missingMasks: masks, decodeErrors: errors)
            XCTAssertEqual(read.failure, .addressDecodeFailed)
            for names in [["en7"], ["en7", "en8"]] {
                let observation = RpcPhoneWifiSelection.observe(status: .satisfied, supportsIPv4: true,
                    usedTypes: [.wifi], wifiInterfaces: names, readAddresses: { read })
                XCTAssertNil(observation.network, "A failed decoder must not hide an alias or addressed alternative")
                XCTAssertEqual(observation.issue, .addressDecodeFailed)
            }
        }
        let empty = RpcPhoneWifiAddressRead.scanned(rows: [], wifiRows: 0, wifiDecoded: 0,
                                                   missingMasks: 0, decodeErrors: [])
        XCTAssertNil(empty.failure)
        let missing = RpcPhoneWifiSelection.observe(status: .satisfied, supportsIPv4: true,
            usedTypes: [.wifi], wifiInterfaces: ["en7", "en8"], readAddresses: { empty })
        XCTAssertEqual(missing.issue, .noWifiAddress)
        XCTAssertNil(missing.network)
    }

    func testWifiInterfaceIdentityCollapsesOnlyVerifiedDuplicateReports() {
        let interface = RpcPhoneWifiInterface(name: "en7", index: 7)
        let other = RpcPhoneWifiInterface(name: "en8", index: 8)
        for entries in [[interface, interface], [interface, other, interface], [other, interface, interface]] {
            var reads = 0
            let observation = RpcPhoneWifiSelection.observeInterfaces(status: .satisfied, supportsIPv4: true,
                usedTypes: [.wifi], interfaces: entries, currentIndex: { $0 == "en7" ? 7 : 8 }, readAddresses: { names in
                    reads += 1
                    XCTAssertEqual(names.filter { $0 == "en7" }.count, 1)
                    return RpcPhoneWifiAddressRead.scanned(rows: [self.wifiAddress()], wifiRows: 1, wifiDecoded: 1,
                                                           missingMasks: 0, decodeErrors: [])
                })
            XCTAssertEqual(reads, 1)
            XCTAssertEqual(observation.network,
                RpcPhoneWifiNetwork(interfaceName: "en7", localAddress: "192.168.1.6", subnet: "192.168.1.0/24"))
            XCTAssertNil(observation.issue)
            XCTAssertTrue(observation.details.contains("repeated entries: 1"))
            XCTAssertTrue(observation.details.contains("en7#7 (system 7)"))
            XCTAssertFalse(observation.details.contains("192.168"))
        }
    }

    func testWifiInterfaceIdentityRejectsConflictingOrUnavailableMappings() {
        let valid = RpcPhoneWifiInterface(name: "en7", index: 7)
        let cases: [([RpcPhoneWifiInterface], UInt32)] = [
            ([valid, valid], 0), ([valid, valid], 8),
            ([valid, RpcPhoneWifiInterface(name: "en7", index: 8)], 7),
            ([valid, RpcPhoneWifiInterface(name: "en8", index: 7)], 7),
            ([RpcPhoneWifiInterface(name: "en7", index: 0)], 0),
            ([RpcPhoneWifiInterface(name: "en7", index: -1)], 7),
            ([RpcPhoneWifiInterface(name: "en7", index: Int(UInt32.max) + 1)], 7),
        ]
        for (entries, registered) in cases {
            let observation = RpcPhoneWifiSelection.observeInterfaces(status: .satisfied, supportsIPv4: true,
                usedTypes: [.wifi], interfaces: entries, currentIndex: { _ in registered }, readAddresses: { _ in
                    XCTFail("An unverified identity must not reach address selection")
                    return RpcPhoneWifiAddressRead(rows: [self.wifiAddress()], details: "Synthetic.")
                })
            XCTAssertNil(observation.network)
            XCTAssertEqual(observation.issue, .interfaceIdentityMismatch)
        }
        let unsafe = RpcPhoneWifiInterface.read([RpcPhoneWifiInterface(name: "en7\nprivate-input", index: 7)],
            currentIndex: { _ in XCTFail("Unsafe names must not enter a C string lookup"); return 7 })
        XCTAssertEqual(unsafe.failure, .unsafeInterface)
        XCTAssertFalse(unsafe.details.contains("private-input"))
        let many = RpcPhoneWifiInterface.read(Array(repeating: valid, count: 20), currentIndex: { _ in 7 })
        XCTAssertTrue(many.details.contains("more omitted"))
        XCTAssertEqual(many.names, ["en7"])
    }

    func testWifiInterfaceIdentityDoesNotHideAliasesOtherAddressesOrRejectedPaths() {
        let interface = RpcPhoneWifiInterface(name: "en7", index: 7)
        let other = RpcPhoneWifiInterface(name: "en8", index: 8)
        for (entries, rows, issue) in [
            ([interface, interface], [wifiAddress(), wifiAddress("8.8.8.8")], RpcPhoneWifiIssue.ambiguousWifiAddresses),
            ([interface, other, interface], [wifiAddress(), wifiAddress("8.8.8.8", name: "en8")], .ambiguousWifiInterfaces),
        ] {
            let observation = RpcPhoneWifiSelection.observeInterfaces(status: .satisfied, supportsIPv4: true,
                usedTypes: [.wifi], interfaces: entries, currentIndex: { $0 == "en7" ? 7 : 8 },
                readAddresses: { _ in RpcPhoneWifiAddressRead(rows: rows, details: "Synthetic.") })
            XCTAssertNil(observation.network)
            XCTAssertEqual(observation.issue, issue)
        }
        let incomplete = RpcPhoneWifiSelection.observeInterfaces(status: .satisfied, supportsIPv4: true,
            usedTypes: [.wifi], interfaces: [interface, interface], currentIndex: { _ in 7 }, readAddresses: { _ in
                RpcPhoneWifiAddressRead.scanned(rows: [self.wifiAddress()], wifiRows: 2, wifiDecoded: 1,
                                                missingMasks: 1, decodeErrors: [])
            })
        XCTAssertEqual(incomplete.issue, .addressDecodeFailed)
        XCTAssertNil(incomplete.network)
        for (status, ipv4, types, issue) in [
            (NWPath.Status.unsatisfied, true, [NWInterface.InterfaceType.wifi], RpcPhoneWifiIssue.pathUnavailable),
            (.satisfied, false, [.wifi], .noIPv4),
            (.satisfied, true, [.wifi, .cellular], .mixedPath),
        ] {
            let observation = RpcPhoneWifiSelection.observeInterfaces(status: status, supportsIPv4: ipv4,
                usedTypes: types, interfaces: [interface, interface], currentIndex: { _ in 7 }, readAddresses: { _ in
                    XCTFail("Duplicate identities must not rescue a rejected default path")
                    return RpcPhoneWifiAddressRead(rows: [self.wifiAddress()], details: "Synthetic.")
                })
            XCTAssertEqual(observation.issue, issue)
            XCTAssertNil(observation.network)
        }
    }

    func testWifiDiagnosticRequiresExplicitLaunchAndOmitsNetworkAddresses() throws {
        #if DEBUG
        let source = String(repeating: "a", count: 40)
        let observation = RpcPhoneWifiObservation.available(
            RpcPhoneWifiNetwork(interfaceName: "en7", localAddress: "192.168.1.6", subnet: "192.168.1.0/24"),
            details: "Synthetic interface metadata only.")
        XCTAssertNil(RpcPhoneWifiDiagnostic.line(arguments: [], observation: observation, source: source, canConfirm: true))
        XCTAssertNil(RpcPhoneWifiDiagnostic.line(arguments: ["--rpc-wifi-diagnostic=1"],
            observation: observation, source: source, canConfirm: true))
        XCTAssertNil(RpcPhoneWifiDiagnostic.line(arguments: [RpcPhoneWifiDiagnostic.argument],
            observation: .checking, source: source, canConfirm: false))
        XCTAssertNil(RpcPhoneWifiDiagnostic.line(arguments: [RpcPhoneWifiDiagnostic.argument],
            observation: observation, source: "not-a-source-commit", canConfirm: true))
        let line = try XCTUnwrap(RpcPhoneWifiDiagnostic.line(arguments: [RpcPhoneWifiDiagnostic.argument],
            observation: observation, source: source, canConfirm: true))
        XCTAssertTrue(line.hasPrefix(RpcPhoneWifiDiagnostic.prefix))
        XCTAssertFalse(line.contains("192.168"))
        let data = Data(line.dropFirst(RpcPhoneWifiDiagnostic.prefix.count).utf8)
        let record = try XCTUnwrap(JSONSerialization.jsonObject(with: data) as? [String: Any])
        XCTAssertEqual(record["sourceCommit"] as? String, source)
        XCTAssertEqual(record["canConfirmWifi"] as? Bool, true)
        XCTAssertEqual(record["check"] as? String, "available")
        XCTAssertEqual(record["hasCandidate"] as? Bool, true)
        XCTAssertEqual(Set(record.keys), ["scope", "sourceCommit", "check", "hasCandidate", "canConfirmWifi", "details"])
        let unavailable = RpcPhoneWifiObservation.unavailable(.interfaceIdentityMismatch, details: "Synthetic mismatch.")
        let rejected = try XCTUnwrap(RpcPhoneWifiDiagnostic.line(arguments: [RpcPhoneWifiDiagnostic.argument],
            observation: unavailable, source: source, canConfirm: false))
        let failure = try XCTUnwrap(JSONSerialization.jsonObject(
            with: Data(rejected.dropFirst(RpcPhoneWifiDiagnostic.prefix.count).utf8)) as? [String: Any])
        XCTAssertEqual(failure["check"] as? String, "interfaceIdentityMismatch")
        XCTAssertEqual(failure["canConfirmWifi"] as? Bool, false)
        XCTAssertEqual(failure["hasCandidate"] as? Bool, false)
        #else
        XCTFail("The phone controls must test the Debug diagnostic rather than silently skipping it")
        #endif
    }

    @MainActor
    func testWifiRefreshRetiresCallbacksRevokesApprovalAndPreservesUnrelatedInput() {
        let wifi = SyntheticWifiObserver()
        let model = RpcPhoneModel(wifi: wifi)
        model.setForeground(true)
        defer { model.setForeground(false) }
        let network = RpcPhoneWifiNetwork(interfaceName: "en7", localAddress: "192.168.1.6", subnet: "192.168.1.0/24")
        wifi.publish(network)
        model.confirmWifi()
        XCTAssertTrue(model.wifiApproved)
        XCTAssertFalse(model.canConfirmWifi)
        XCTAssertTrue(model.wifiExplanation.contains("already confirmed"))
        model.invitation = "synthetic-private-invitation"
        model.revealInvitation = true
        model.hostAddress = "10.0.0.2"
        model.hostPin = "synthetic-host-pin"
        model.capacityPins = "synthetic-capacity-pins"
        model.approveImport = true
        model.usbRunLabel = "synthetic-slot"
        model.port = "48124"
        model.refreshWifi()
        XCTAssertEqual(wifi.stops, 1)
        XCTAssertEqual(wifi.callbacks.count, 2)
        XCTAssertEqual(model.wifiObservation, .checking)
        XCTAssertFalse(model.wifiChecked)
        XCTAssertFalse(model.wifiApproved)
        XCTAssertFalse(model.canConfirmWifi)
        XCTAssertTrue(model.canRefreshWifi)
        XCTAssertTrue(model.subnets.isEmpty && model.localAddress.isEmpty && model.interfaceName.isEmpty)
        XCTAssertEqual(model.invitation, "synthetic-private-invitation")
        XCTAssertTrue(model.revealInvitation)
        XCTAssertEqual(model.hostAddress, "10.0.0.2")
        XCTAssertEqual(model.hostPin, "synthetic-host-pin")
        XCTAssertEqual(model.capacityPins, "synthetic-capacity-pins")
        XCTAssertTrue(model.approveImport)
        XCTAssertEqual(model.usbRunLabel, "synthetic-slot")
        XCTAssertEqual(model.port, "48124")
        XCTAssertNil(model.mobileConfig)
        XCTAssertFalse(model.owner.hasOwner || model.actionBusy || model.operationBusy)
        wifi.callbacks[0](.available(network, details: "Retired candidate."))
        wifi.callbacks[0](.unavailable(.noIPv4, details: "Retired failure."))
        XCTAssertEqual(model.wifiObservation, .checking)
        let failure = RpcPhoneWifiObservation.unavailable(.mixedPath, details: "Current mixed path.")
        wifi.publishObservation(failure)
        XCTAssertEqual(model.wifiObservation, failure)
        XCTAssertEqual(model.wifiExplanation, RpcPhoneWifiIssue.mixedPath.explanation)
        wifi.publish(network)
        XCTAssertTrue(model.canConfirmWifi)
        XCTAssertFalse(model.wifiApproved, "A fresh read is not fresh approval")
        XCTAssertFalse(model.owner.hasOwner)
    }

    @MainActor
    func testWifiDiagnosticAndCandidateStayTogetherAtConfirmationAndAcrossForegrounds() {
        let wifi = SyntheticWifiObserver()
        let model = RpcPhoneModel(wifi: wifi)
        model.setForeground(true)
        defer { model.setForeground(false) }
        let network = RpcPhoneWifiNetwork(interfaceName: "en7", localAddress: "192.168.1.6", subnet: "192.168.1.0/24")
        wifi.publish(network)
        let changed = RpcPhoneWifiObservation.unavailable(.noIPv4, details: "Current path lacks IPv4.")
        wifi.observation = changed // No callback yet: confirmation must publish this very read's reason.
        model.confirmWifi()
        XCTAssertEqual(model.wifiObservation, changed)
        XCTAssertNil(model.detectedWifi)
        XCTAssertFalse(model.wifiApproved)
        XCTAssertFalse(model.canConfirmWifi)
        XCTAssertEqual(model.wifiExplanation, changed.explanation)
        wifi.publish(network)
        let fresh = RpcPhoneWifiObservation.available(network, details: "Latest available path.")
        wifi.observation = fresh
        model.confirmWifi()
        XCTAssertTrue(model.wifiApproved)
        XCTAssertEqual(model.wifiObservation, fresh)
        model.setForeground(false)
        XCTAssertEqual(model.wifiObservation, .checking)
        XCTAssertFalse(model.canRefreshWifi || model.canConfirmWifi)
        XCTAssertTrue(model.wifiExplanation.contains("foreground"))
        model.setForeground(true)
        wifi.callbacks[0](changed)
        XCTAssertEqual(model.wifiObservation, .checking, "An old diagnostic cannot describe a new generation")
        wifi.publishObservation(changed)
        XCTAssertEqual(model.wifiObservation, changed)
        XCTAssertFalse(model.owner.hasOwner)
    }

    @MainActor
    func testWifiRefreshCannotInterruptInactiveManualOrStartingAndStoppingStates() async {
        let wifi = SyntheticWifiObserver()
        let model = RpcPhoneModel(wifi: wifi)
        model.refreshWifi()
        XCTAssertTrue(wifi.callbacks.isEmpty)
        XCTAssertEqual(wifi.stops, 0)
        model.setForeground(true)
        defer { model.setForeground(false) }
        model.setManualNetworkSetup(true)
        model.subnets = "10.0.0.0/24"
        model.refreshWifi()
        XCTAssertFalse(model.canRefreshWifi || model.canConfirmWifi)
        XCTAssertTrue(model.wifiExplanation.contains("Manual"))
        XCTAssertEqual(model.subnets, "10.0.0.0/24")
        XCTAssertEqual(wifi.callbacks.count, 1)
        model.setManualNetworkSetup(false)
        let network = RpcPhoneWifiNetwork(interfaceName: "en7", localAddress: "192.168.1.6", subnet: "192.168.1.0/24")
        wifi.publish(network)
        model.confirmWifi()
        var enteredFactory = false
        let observation = model.owner.$phase.sink { if $0 == .starting { enteredFactory = true } }
        model.start(host: true)
        XCTAssertTrue(model.actionBusy)
        XCTAssertFalse(model.canRefreshWifi || model.canConfirmWifi)
        XCTAssertTrue(model.wifiExplanation.contains("starting"))
        model.refreshWifi()
        XCTAssertEqual(wifi.callbacks.count, 1)
        XCTAssertEqual(wifi.stops, 0)
        model.stop() // Synchronous Stop prevents the scheduled task from entering the real network factory.
        XCTAssertFalse(model.canRefreshWifi || model.canConfirmWifi)
        XCTAssertTrue(model.wifiExplanation.contains("cleanup"))
        model.refreshWifi()
        XCTAssertEqual(wifi.callbacks.count, 1)
        let stopped = expectation(description: "scheduled start and cleanup retire without a Wi-Fi refresh")
        let statusObservation = model.$status.sink {
            if $0 == "Stopped; owned RPC cleanup completed." { stopped.fulfill() }
        }
        await fulfillment(of: [stopped], timeout: 2)
        observation.cancel()
        statusObservation.cancel()
        XCTAssertFalse(enteredFactory)
        XCTAssertFalse(model.owner.hasOwner || model.actionBusy)
        XCTAssertTrue(model.canRefreshWifi)
    }

    @MainActor
    func testWifiSuggestionNeedsConfirmationAndNeverStartsARoleOrImportsTrust() {
        let wifi = SyntheticWifiObserver()
        let model = RpcPhoneModel(wifi: wifi)
        model.setForeground(true)
        defer { model.setForeground(false) }
        let network = RpcPhoneWifiNetwork(interfaceName: "en7", localAddress: "192.168.1.6", subnet: "192.168.1.0/24")
        wifi.publish(network)
        XCTAssertEqual(model.detectedWifi, network)
        XCTAssertFalse(model.wifiApproved)
        XCTAssertEqual(model.subnets, "")
        for host in [true, false] {
            model.start(host: host)
            XCTAssertTrue(model.startProblem?.message.contains("Use this Wi-Fi") == true)
            XCTAssertFalse(model.owner.hasOwner)
            XCTAssertFalse(model.actionBusy)
        }
        model.confirmWifi()
        XCTAssertTrue(model.wifiApproved)
        XCTAssertEqual(model.subnets, network.subnet)
        XCTAssertEqual(model.interfaceName, "en7")
        XCTAssertEqual(model.localAddress, network.localAddress)
        XCTAssertEqual(model.port, "48123")
        XCTAssertEqual(model.hostPin, "")
        XCTAssertEqual(model.hostAddress, "")
        XCTAssertEqual(model.invitation, "")
        XCTAssertEqual(model.capacityPins, "")
        XCTAssertFalse(model.approveImport)
        XCTAssertNil(model.mobileConfig)
        XCTAssertNil(model.startProblem)
        XCTAssertFalse(model.owner.hasOwner)
    }

    @MainActor
    func testWifiConfirmationRechecksCurrentSnapshotBeforeCopyingSettings() {
        let wifi = SyntheticWifiObserver()
        let model = RpcPhoneModel(wifi: wifi)
        model.setForeground(true)
        defer { model.setForeground(false) }
        let old = RpcPhoneWifiNetwork(interfaceName: "en7", localAddress: "192.168.1.6", subnet: "192.168.1.0/24")
        let current = RpcPhoneWifiNetwork(interfaceName: "en7", localAddress: "10.1.2.3", subnet: "10.1.2.0/24")
        wifi.publish(old)
        wifi.network = current // Address/path changed before the queued notification was delivered.
        model.confirmWifi()
        XCTAssertEqual(model.detectedWifi, current)
        XCTAssertFalse(model.wifiApproved)
        XCTAssertTrue(model.subnets.isEmpty)
        XCTAssertTrue(model.startProblem?.message.contains("Wi-Fi changed") == true)
        model.confirmWifi()
        XCTAssertTrue(model.wifiApproved)
        XCTAssertEqual(model.subnets, current.subnet)
        wifi.network = nil
        model.confirmWifi()
        XCTAssertFalse(model.wifiApproved)
        XCTAssertTrue(model.subnets.isEmpty)
        XCTAssertFalse(model.owner.hasOwner)
    }

    @MainActor
    func testWifiChangeAndBackgroundRevokeApprovalAndIgnoreRetiredCallbacks() {
        let wifi = SyntheticWifiObserver()
        let model = RpcPhoneModel(wifi: wifi)
        let network = RpcPhoneWifiNetwork(interfaceName: "en7", localAddress: "192.168.1.6", subnet: "192.168.1.0/24")
        model.setForeground(true)
        model.setForeground(true)
        XCTAssertEqual(wifi.callbacks.count, 1)
        wifi.publish(network)
        model.confirmWifi()
        wifi.publish(network)
        XCTAssertTrue(model.wifiApproved)
        wifi.publish(nil)
        XCTAssertFalse(model.wifiApproved)
        XCTAssertTrue(model.localAddress.isEmpty)
        wifi.publish(network)
        model.confirmWifi()
        model.setForeground(false)
        XCTAssertEqual(wifi.stops, 1)
        XCTAssertFalse(model.wifiApproved)
        XCTAssertNil(model.detectedWifi)
        XCTAssertFalse(model.wifiChecked)
        XCTAssertTrue(model.subnets.isEmpty)
        wifi.callbacks[0](.available(network, details: "Retired observation."))
        XCTAssertNil(model.detectedWifi)
        model.setForeground(true)
        wifi.callbacks[0](.available(network, details: "Retired observation."))
        XCTAssertNil(model.detectedWifi, "A retired observation may not configure the next foreground session")
        wifi.publish(network)
        XCTAssertEqual(model.detectedWifi, network)
        XCTAssertFalse(model.wifiApproved)
        model.setForeground(false)
        XCTAssertEqual(wifi.stops, 2)
    }

    @MainActor
    func testManualSetupRemainsExplicitAndIsNotOverwrittenByWifiSuggestions() {
        let wifi = SyntheticWifiObserver()
        let model = RpcPhoneModel(wifi: wifi)
        model.setForeground(true)
        defer { model.setForeground(false) }
        let network = RpcPhoneWifiNetwork(interfaceName: "en7", localAddress: "192.168.1.6", subnet: "192.168.1.0/24")
        wifi.publish(network)
        model.confirmWifi()
        model.setManualNetworkSetup(true)
        XCTAssertTrue(model.subnets.isEmpty, "Detection must not silently approve manual settings")
        XCTAssertFalse(model.wifiApproved)
        model.subnets = "10.1.2.0/24"
        model.interfaceName = "en3"
        model.localAddress = "10.1.2.3"
        wifi.publish(nil)
        wifi.publish(network)
        model.confirmWifi()
        XCTAssertEqual(model.subnets, "10.1.2.0/24")
        XCTAssertEqual(model.interfaceName, "en3")
        XCTAssertEqual(model.localAddress, "10.1.2.3")
        model.setManualNetworkSetup(false)
        XCTAssertTrue(model.subnets.isEmpty)
        XCTAssertFalse(model.wifiApproved)
        XCTAssertFalse(model.owner.hasOwner)
    }

    @MainActor
    func testWifiStartupRejectsUnobservedChangeAndEditedApprovedSettings() {
        let wifi = SyntheticWifiObserver()
        let model = RpcPhoneModel(wifi: wifi)
        model.setForeground(true)
        defer { model.setForeground(false) }
        let network = RpcPhoneWifiNetwork(interfaceName: "en7", localAddress: "192.168.1.6", subnet: "192.168.1.0/24")
        for host in [true, false] {
            wifi.publish(network)
            model.confirmWifi()
            wifi.network = nil
            model.start(host: host)
            XCTAssertFalse(model.wifiApproved)
            XCTAssertTrue(model.startProblem?.message.contains("Use this Wi-Fi") == true)
            XCTAssertFalse(model.owner.hasOwner)
            XCTAssertFalse(model.actionBusy)
        }
        for key in [\RpcPhoneModel.subnets, \RpcPhoneModel.interfaceName, \RpcPhoneModel.localAddress] {
            wifi.publish(network)
            model.confirmWifi()
            model[keyPath: key] = "not-the-confirmed-setting"
            model.start(host: true)
            XCTAssertTrue(model.startProblem?.message.contains("Use this Wi-Fi") == true)
            XCTAssertFalse(model.owner.hasOwner)
            XCTAssertFalse(model.actionBusy)
        }
    }

    @MainActor
    func testStopBeforeScheduledStartupDoesNotEnterTheFactory() async {
        let model = RpcPhoneModel(wifi: SyntheticWifiObserver())
        model.setForeground(true)
        defer { model.setForeground(false) }
        model.setManualNetworkSetup(true)
        model.subnets = "not-a-cidr" // Fail closed even if a regression incorrectly reaches the real factory.
        model.interfaceName = "en0"
        model.localAddress = "192.168.1.6"
        var enteredFactory = false
        let observation = model.owner.$phase.sink { if $0 == .starting { enteredFactory = true } }
        model.start(host: true)
        XCTAssertTrue(model.actionBusy)
        model.stop()
        let stopped = expectation(description: "scheduled startup and Stop retire")
        let statusObservation = model.$status.sink {
            if $0 == "Stopped; owned RPC cleanup completed." { stopped.fulfill() }
        }
        await fulfillment(of: [stopped], timeout: 2)
        observation.cancel()
        statusObservation.cancel()
        XCTAssertFalse(enteredFactory)
        XCTAssertFalse(model.owner.hasOwner)
        XCTAssertFalse(model.actionBusy)
        XCTAssertTrue(model.canStart)
    }

    @MainActor
    func testActualWifiObserverRetiresItsMonitorAndCannotReuseAStoppedPath() async {
        let wifi = RpcPhoneWifiObserver()
        var callbacks = 0
        for _ in 0..<3 {
            wifi.start { _ in callbacks += 1 }
            wifi.stop()
            XCTAssertEqual(wifi.currentObservation(), .checking)
            XCTAssertNil(wifi.currentObservation().network)
        }
        await Task.yield()
        XCTAssertEqual(callbacks, 0, "Queued observations after Stop must be discarded")
    }

    @MainActor
    func testEmptyRoleSetupExplainsEveryMissingFieldWithoutAcquiringAnOwner() {
        let model = RpcPhoneModel(wifi: SyntheticWifiObserver())
        model.setForeground(true)
        defer { model.setForeground(false) }
        model.setManualNetworkSetup(true)
        for host in [true, false] {
            model.start(host: host)
            XCTAssertEqual(model.startProblem?.message, model.status)
            for field in ["approved private CIDRs", "Wi-Fi interface", "this iPhone's numeric LAN address"] {
                XCTAssertTrue(model.status.contains(field))
            }
            XCTAssertFalse(model.owner.hasOwner)
            XCTAssertFalse(model.actionBusy)
            XCTAssertTrue(model.canStart)
        }
    }

    @MainActor
    func testWhitespaceOnlyRoleFieldsStayInvalidAndDiagnosticsDoNotEchoInput() {
        let model = RpcPhoneModel(wifi: SyntheticWifiObserver())
        model.setForeground(true)
        defer { model.setForeground(false) }
        model.setManualNetworkSetup(true)
        let fields: [(ReferenceWritableKeyPath<RpcPhoneModel, String>, String)] = [
            (\RpcPhoneModel.subnets, "approved private CIDRs"),
            (\RpcPhoneModel.interfaceName, "Wi-Fi interface"),
            (\RpcPhoneModel.localAddress, "this iPhone's numeric LAN address"),
        ]
        for (key, name) in fields {
            model.subnets = "192.168.1.0/24"
            model.interfaceName = "en0"
            model.localAddress = "192.168.1.50"
            model[keyPath: key] = " \n\t"
            model.start(host: true)
            XCTAssertTrue(model.startProblem?.message.contains(name) == true)
            XCTAssertFalse(model.status.contains("192.168.1"))
            XCTAssertFalse(model.owner.hasOwner)
            XCTAssertFalse(model.actionBusy)
        }
    }

    @MainActor
    func testInvalidPortAndUnapprovedCapacityImportExplainWhyNeitherRoleStarts() {
        let model = RpcPhoneModel(wifi: SyntheticWifiObserver())
        model.setForeground(true)
        defer { model.setForeground(false) }
        model.setManualNetworkSetup(true)
        model.subnets = "192.168.1.0/24"
        model.interfaceName = "en0"
        model.localAddress = "192.168.1.50"
        for port in ["", "0", "1023", "65536", "not-a-port", "2147483648"] {
            model.port = port
            for host in [true, false] {
                model.start(host: host)
                XCTAssertTrue(model.startProblem?.message.contains("1024 to 65535") == true)
                XCTAssertFalse(model.owner.hasOwner)
                XCTAssertFalse(model.actionBusy)
            }
        }
        model.port = "48123"
        model.capacityPins = "private-input-must-not-be-repeated"
        model.start(host: true)
        XCTAssertTrue(model.startProblem?.message.contains("explicitly approve") == true)
        model.approveImport = true
        model.start(host: false)
        XCTAssertTrue(model.startProblem?.message.contains("client cannot import") == true)
        XCTAssertFalse(model.status.contains(model.capacityPins))
        XCTAssertFalse(model.owner.hasOwner)
        XCTAssertTrue(model.canStart)
    }

    @MainActor
    func testRejectedNonemptyPolicyAlsoPresentsTheAsynchronousStartupFailure() async {
        for host in [true, false] {
            let model = RpcPhoneModel(wifi: SyntheticWifiObserver())
            model.setForeground(true)
            defer { model.setForeground(false) }
            model.setManualNetworkSetup(true)
            // The real shared policy rejects this before a socket or identity is acquired.
            model.subnets = "not-a-cidr"
            model.interfaceName = "en0"
            model.localAddress = "192.168.1.50"
            let reported = expectation(description: "startup rejection is visible")
            let observation = model.$startProblem.sink { problem in
                if problem != nil { reported.fulfill() }
            }
            model.start(host: host)
            await fulfillment(of: [reported], timeout: 2)
            observation.cancel()
            XCTAssertEqual(model.startProblem?.message, model.status)
            XCTAssertTrue(model.status.contains("Invalid setup"))
            XCTAssertFalse(model.status.contains(model.subnets))
            XCTAssertFalse(model.owner.hasOwner)
            XCTAssertFalse(model.actionBusy)
            XCTAssertTrue(model.canStart)
        }
    }

    private func withCapacityFiles(_ body: (RpcPhoneCapacityFiles, URL) throws -> Void) throws {
        let label = "control-" + UUID().uuidString.lowercased()
        let files = try RpcPhoneCapacityFiles(runLabel: label, requireNew: true)
        let base = try FileManager.default.url(for: .applicationSupportDirectory, in: .userDomainMask,
                                               appropriateFor: nil, create: false)
        let directory = base.appendingPathComponent("rpc-capacity/" + label)
        let result: Result<Void, Error>
        do { try body(files, directory); result = .success(()) } catch { result = .failure(error) }
        let entries = try FileManager.default.contentsOfDirectory(at: directory, includingPropertiesForKeys: nil)
        let allowed = Set(["prepared.txt", "inbox.txt", "stop.txt", "ready.txt", "telemetry.txt", "linked.txt", "target.txt",
                           ".incoming-inbox.txt", ".sealed-inbox.txt", ".incoming-stop.txt", ".sealed-stop.txt"])
        for entry in entries {
            guard allowed.contains(entry.lastPathComponent), unlink(entry.path) == 0 else {
                throw RpcPhoneCapacityIOError.resourceRetirement
            }
        }
        guard rmdir(directory.path) == 0 else { throw RpcPhoneCapacityIOError.resourceRetirement }
        try result.get()
    }

    func testPrivateCapacityFilesAreBoundedAtomicAndCreateOnlyExceptTelemetry() throws {
        try withCapacityFiles { files, directory in
            let inbox = directory.appendingPathComponent(".incoming-inbox.txt")
            try stage("inbox.txt", "schema=1\n", directory)
            XCTAssertEqual(chmod(inbox.path, 0o644), 0)
            XCTAssertEqual(try files.read("inbox.txt"), "schema=1\n")
            var protected = stat()
            XCTAssertEqual(lstat(inbox.path, &protected), 0)
            XCTAssertEqual(protected.st_mode & 0o777, 0o600, "Exact imported input privacy must be strengthened")
            try files.publish("ready.txt", "ready=true\n")
            XCTAssertThrowsError(try files.publish("ready.txt", "ready=false\n"))
            XCTAssertEqual(try files.read("ready.txt"), "ready=true\n")
            try files.publish("telemetry.txt", "sequence=1\n")
            try files.publish("telemetry.txt", "sequence=2\n")
            XCTAssertEqual(try files.read("telemetry.txt"), "sequence=2\n")
            XCTAssertNil(try files.read("stop.txt", optional: true))
            XCTAssertThrowsError(try files.publish("failed.txt", "x=" + String(repeating: "a", count: 16_384)))
            XCTAssertThrowsError(try files.publish("failed.txt", "x=\0\n"))
        }
    }

    func testCapacityRunLabelsRejectTrailingLineEndingsBeforeCreatingASlot() throws {
        let base = try FileManager.default.url(for: .applicationSupportDirectory, in: .userDomainMask,
                                               appropriateFor: nil, create: true)
        let home = base.appendingPathComponent("rpc-capacity", isDirectory: true)
        for suffix in ["\n", "\r\n"] {
            let label = "control-" + UUID().uuidString.lowercased() + suffix
            let directory = home.appendingPathComponent(label, isDirectory: true)
            var before = stat()
            guard lstat(directory.path, &before) == -1, errno == ENOENT else {
                throw RpcPhoneCapacityIOError.filePolicy
            }
            do {
                _ = try RpcPhoneCapacityFiles(runLabel: label, requireNew: true)
            } catch RpcPhoneCapacityIOError.invalidRecord {
                XCTAssertFalse(FileManager.default.fileExists(atPath: directory.path),
                               "Reject the entire invalid label before creating its slot")
                continue
            }
            // Retire only the exact fresh, empty app-owned slot if a regression admitted it.
            var created = stat()
            guard lstat(directory.path, &created) == 0, created.st_uid == getuid(),
                  created.st_mode & S_IFMT == S_IFDIR, created.st_mode & 0o777 == 0o700,
                  rmdir(directory.path) == 0 else { throw RpcPhoneCapacityIOError.resourceRetirement }
            XCTFail("A trailing line ending must not satisfy the ASCII run-label grammar")
        }
    }

    func testCapacityFilesRejectSymlinksHardlinksPermissionsAndUnsafeRunLabels() throws {
        XCTAssertThrowsError(try RpcPhoneCapacityFiles(runLabel: "../unowned"))
        try withCapacityFiles { files, directory in
            let input = directory.appendingPathComponent(".incoming-inbox.txt")
            let target = directory.appendingPathComponent("target.txt")
            try Data("x=private\n".utf8).write(to: target, options: .withoutOverwriting)
            try seal("inbox.txt", "x=private\n", directory)
            XCTAssertEqual(chmod(target.path, 0o600), 0)
            XCTAssertEqual(symlink(target.path, input.path), 0)
            XCTAssertThrowsError(try files.read("inbox.txt"))
            XCTAssertEqual(unlink(input.path), 0)
            XCTAssertEqual(link(target.path, input.path), 0)
            XCTAssertThrowsError(try files.read("inbox.txt"))
            XCTAssertEqual(unlink(input.path), 0)
            try Data("x=invalid-mode\n".utf8).write(to: input, options: .withoutOverwriting)
            XCTAssertEqual(chmod(input.path, 0o666), 0)
            XCTAssertThrowsError(try files.read("inbox.txt"))
            XCTAssertThrowsError(try files.read("../target.txt"))
            XCTAssertEqual(try Data(contentsOf: target), Data("x=private\n".utf8))
        }
    }

    private func seal(_ name: String, _ text: String, _ directory: URL) throws {
        let digest = SHA256.hash(data: Data(text.utf8)).map { String(format: "%02x", $0) }.joined()
        let record = "schema=1\nname=\(name)\nbytes=\(text.utf8.count)\nsha256=\(digest)\n"
        try Data(record.utf8).write(to: directory.appendingPathComponent(".sealed-" + name), options: .withoutOverwriting)
    }

    private func stage(_ name: String, _ text: String, _ directory: URL) throws {
        try Data(text.utf8).write(to: directory.appendingPathComponent(".incoming-" + name), options: .withoutOverwriting)
        try seal(name, text, directory)
    }

    func testUnsealedPartialAndCorruptedStopInputsCannotBeConsumed() throws {
        try withCapacityFiles { files, directory in
            let input = directory.appendingPathComponent(".incoming-stop.txt")
            let marker = directory.appendingPathComponent(".sealed-stop.txt")
            try Data("action=st".utf8).write(to: input, options: .withoutOverwriting)
            XCTAssertNil(try files.read("stop.txt", optional: true), "Unsealed bytes are not a Stop request")
            try Data().write(to: marker, options: .withoutOverwriting)
            XCTAssertNil(try files.read("stop.txt", optional: true), "An empty in-flight seal is not publication")
            try Data("schema=1\n".utf8).write(to: marker)
            XCTAssertNil(try files.read("stop.txt", optional: true), "A partial seal must not admit partial input")
            XCTAssertEqual(unlink(marker.path), 0)
            try seal("stop.txt", "action=stop\n", directory)
            XCTAssertThrowsError(try files.read("stop.txt", optional: true), "A complete seal with mismatched data fails closed")
            XCTAssertFalse(FileManager.default.fileExists(atPath: directory.appendingPathComponent("stop.txt").path))
        }
    }

    func testSealedInputsBecomeAppOwnedCreateOnlyAndCannotReplayIntoANewOwner() throws {
        try withCapacityFiles { files, directory in
            try stage("inbox.txt", "schema=1\n", directory)
            XCTAssertEqual(try files.read("inbox.txt"), "schema=1\n")
            try Data("schema=2\n".utf8).write(to: directory.appendingPathComponent(".incoming-inbox.txt"))
            XCTAssertEqual(try files.read("inbox.txt"), "schema=1\n", "Copied staging cannot replace an admitted record")
            let another = try RpcPhoneCapacityFiles(runLabel: directory.lastPathComponent)
            XCTAssertThrowsError(try another.read("inbox.txt"), "A new owner cannot adopt an old run")
            try stage("stop.txt", "action=stop\n", directory)
            XCTAssertEqual(try files.read("stop.txt"), "action=stop\n")
            XCTAssertThrowsError(try files.publish("inbox.txt", "schema=3\n"))
        }
    }

    func testPreparingAUsbSlotNeverReusesAnExistingDirectoryOrPublishesRpcApproval() throws {
        try withCapacityFiles { files, directory in
            XCTAssertThrowsError(try RpcPhoneCapacityFiles(runLabel: directory.lastPathComponent, requireNew: true))
            try files.publish("prepared.txt", "schema=1\nscope=ios-usb-slot\n")
            XCTAssertThrowsError(try files.publish("prepared.txt", "schema=2\n"))
            XCTAssertNil(try files.read("ready.txt", optional: true))
            XCTAssertNil(try files.read("stop.txt", optional: true))
        }
    }

    func testActualSelfResourceSamplerRetiresEveryAcquiredMachThreadRight() throws {
        let installed = try RpcPhoneProcessSampler.installedArtifact()
        XCTAssertNotNil(installed.range(of: "^[a-f0-9]{64}$", options: .regularExpression))
        XCTAssertEqual(try RpcPhoneProcessSampler.installedArtifact(), installed)
        let thread = mach_thread_self() // This test owns one retained send right throughout the observations.
        defer { XCTAssertEqual(mach_port_deallocate(mach_task_self_, thread), KERN_SUCCESS) }
        var before: mach_port_urefs_t = 0
        XCTAssertEqual(mach_port_get_refs(mach_task_self_, thread, mach_port_right_t(MACH_PORT_RIGHT_SEND), &before),
                       KERN_SUCCESS)
        var previousCpu: Int64 = 0
        for _ in 0..<64 {
            let sample = try RpcPhoneProcessSampler.sample()
            XCTAssertGreaterThan(sample.residentBytes, 0)
            XCTAssertGreaterThan(sample.nativeThreads, 0)
            XCTAssertGreaterThanOrEqual(sample.cpuNanos, previousCpu)
            previousCpu = sample.cpuNanos
            var after: mach_port_urefs_t = 0
            XCTAssertEqual(mach_port_get_refs(mach_task_self_, thread, mach_port_right_t(MACH_PORT_RIGHT_SEND), &after),
                           KERN_SUCCESS)
            XCTAssertEqual(after, before, "Sampling must not leak a send right on the actual Apple runtime")
        }
    }

    @MainActor
    func testActualKeychainRoundTripNamespacesRevocationAndFixtureRetirement() async throws {
        // The same real-storage regression runs in the application, not an unentitled CLI binary.
        try await RpcPhoneIosControls.shared.verifySyntheticTrustStore()
    }

    @MainActor
    func testExplicitStartAndCloseOwnExactlyOneRuntime() async {
        let owner = RpcPhoneRunOwner<SyntheticRuntime>()
        let runtime = SyntheticRuntime()
        let result = await owner.start(create: { runtime }, close: { $0.closes += 1 })
        guard case .started = result else { return XCTFail("Runtime was not admitted") }
        XCTAssertTrue(owner.accepts(runtime))
        let refused = await owner.start(create: { XCTFail("Duplicate factory"); return runtime }, close: { _ in })
        guard case .refused = refused else { return XCTFail("Parallel role was admitted") }
        let stopped = await owner.stop()
        XCTAssertTrue(stopped)
        XCTAssertEqual(runtime.closes, 1)
        XCTAssertFalse(owner.hasOwner)
        XCTAssertFalse(owner.accepts(runtime))
        let stoppedAgain = await owner.stop()
        XCTAssertTrue(stoppedAgain)
        XCTAssertEqual(runtime.closes, 1)
    }

    @MainActor
    func testStopDuringCreationWaitsForAndClosesTheLateResult() async {
        let owner = RpcPhoneRunOwner<SyntheticRuntime>()
        let runtime = SyntheticRuntime()
        let creation = Held<SyntheticRuntime>()
        let closure = Held<Void>()
        let entered = expectation(description: "factory entered")
        let closeEntered = expectation(description: "native close entered")
        let start = Task { @MainActor in
            await owner.start(create: { entered.fulfill(); return try await creation.wait() }, close: { value in
                value.closes += 1
                closeEntered.fulfill()
                try await closure.wait()
            })
        }
        defer { creation.resolve(.success(runtime)); closure.resolve(.success(())) }
        await fulfillment(of: [entered], timeout: 2)
        owner.invalidate()
        let stop = Task { @MainActor in await owner.stop() }
        XCTAssertNil(owner.runtime)
        XCTAssertTrue(owner.hasOwner)
        creation.resolve(.success(runtime))
        await fulfillment(of: [closeEntered], timeout: 2)
        let result = await start.value
        guard case .superseded = result else { return XCTFail("Late resource was published") }
        XCTAssertEqual(owner.phase, .stopping)
        XCTAssertFalse(owner.accepts(runtime))
        XCTAssertTrue(owner.hasOwner, "Close has not returned")
        closure.resolve(.success(()))
        let stopped = await stop.value
        XCTAssertTrue(stopped)
        XCTAssertEqual(runtime.closes, 1)
        XCTAssertFalse(owner.hasOwner)
    }

    @MainActor
    func testCreationFailureAfterInvalidationDoesNotPublishOrRequireANonexistentClose() async {
        let owner = RpcPhoneRunOwner<SyntheticRuntime>()
        let creation = Held<SyntheticRuntime>()
        let entered = expectation(description: "factory entered")
        let start = Task { @MainActor in
            await owner.start(create: { entered.fulfill(); return try await creation.wait() },
                              close: { _ in XCTFail("No runtime was acquired") })
        }
        defer { creation.resolve(.failure(SyntheticFailure.operation)) }
        await fulfillment(of: [entered], timeout: 2)
        owner.invalidate()
        let stop = Task { @MainActor in await owner.stop() }
        creation.resolve(.failure(SyntheticFailure.operation))
        let result = await start.value
        guard case .superseded = result else { return XCTFail("Retired failure was published") }
        let stopped = await stop.value
        XCTAssertTrue(stopped)
        XCTAssertEqual(owner.phase, .idle)
    }

    @MainActor
    func testFailedCloseRetainsOwnershipAndRejectsReplacementUntilRetrySucceeds() async {
        let owner = RpcPhoneRunOwner<SyntheticRuntime>()
        let runtime = SyntheticRuntime()
        _ = await owner.start(create: { runtime }, close: { value in
            value.closes += 1
            if value.closes == 1 { throw SyntheticFailure.operation }
        })
        let first = await owner.stop()
        XCTAssertFalse(first)
        XCTAssertEqual(owner.phase, .cleanupPending)
        XCTAssertTrue(owner.hasOwner)
        XCTAssertNil(owner.runtime)
        let refused = await owner.start(create: { XCTFail("Failed owner discarded"); return runtime }, close: { _ in })
        guard case .refused = refused else { return XCTFail("Replacement admitted") }
        let second = await owner.stop()
        XCTAssertTrue(second)
        XCTAssertEqual(runtime.closes, 2)
        XCTAssertFalse(owner.hasOwner)
    }

    @MainActor
    func testConcurrentStopCallersJoinOneRealCleanupBarrier() async {
        let owner = RpcPhoneRunOwner<SyntheticRuntime>()
        let runtime = SyntheticRuntime()
        let closure = Held<Void>()
        let entered = expectation(description: "close entered")
        _ = await owner.start(create: { runtime }, close: { value in
            value.closes += 1
            entered.fulfill()
            try await closure.wait()
        })
        defer { closure.resolve(.success(())) }
        let first = Task { @MainActor in await owner.stop() }
        await fulfillment(of: [entered], timeout: 2)
        let secondEntered = expectation(description: "second stop scheduled")
        let second = Task { @MainActor in secondEntered.fulfill(); return await owner.stop() }
        await fulfillment(of: [secondEntered], timeout: 2)
        XCTAssertEqual(runtime.closes, 1)
        XCTAssertTrue(owner.hasOwner)
        closure.resolve(.success(()))
        let results = await (first.value, second.value)
        XCTAssertTrue(results.0 && results.1)
        XCTAssertEqual(runtime.closes, 1)
    }

    @MainActor
    func testCancellingSwiftStartupCallerStillClosesItsLateNativeResult() async {
        let owner = RpcPhoneRunOwner<SyntheticRuntime>()
        let runtime = SyntheticRuntime()
        let creation = Held<SyntheticRuntime>()
        let entered = expectation(description: "factory entered")
        let start = Task { @MainActor in
            await owner.start(create: { entered.fulfill(); return try await creation.wait() },
                              close: { $0.closes += 1 })
        }
        defer { creation.resolve(.success(runtime)) }
        await fulfillment(of: [entered], timeout: 2)
        start.cancel()
        creation.resolve(.success(runtime))
        let result = await start.value
        guard case .superseded = result else { return XCTFail("Cancelled startup published a runtime") }
        XCTAssertEqual(runtime.closes, 1)
        XCTAssertEqual(owner.phase, .idle)
        XCTAssertFalse(owner.hasOwner)
    }
}
