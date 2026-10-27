#if DEBUG
import CryptoKit
import Foundation
import P2pKitRpcExample
import XCTest
@testable import P2pKitRpcPhone

final class RpcPhoneUsbDeveloperCommandTests: XCTestCase {
    private let source = String(repeating: "2", count: 40)
    private let artifact = String(repeating: "3", count: 64)

    private func inbox(count: Int = 256) -> String {
        let alphabet = Array("abcdefghijklmnopqrstuvwxyz234567")
        let pins = (0..<count).map { "p2f1-\(alphabet[$0 / 32])\(alphabet[$0 % 32])" + String(repeating: "a", count: 50) }
        return "schema=2\nscope=mobile-usb-capacity\nrunLabel=synthetic-mobile\nclientCount=\(count)\n" +
            "runNonce=\(String(repeating: "1", count: 64))\nhostSourceSha=\(source)\nhostPlatform=Ios\n" +
            "hostArtifactSha256=\(artifact)\nsubnets=192.168.14.0/24\nhostInterface=en0\n" +
            "hostAddress=192.168.14.2\nhostPort=48123\nclientPins=\(pins.joined(separator: ","))\n"
    }

    private func command(inbox: String) -> String {
        "schema=1\nscope=mobile-usb-start\nrunLabel=synthetic-mobile\nhostSourceSha=\(source)\n" +
            "hostArtifactSha256=\(artifact)\ninboxSha256=\(RpcPhoneUsbDeveloperStart.digest(inbox))\n"
    }

    private func next(inbox: String) -> String {
        "schema=1\nscope=mobile-usb-prepare-next\nrunLabel=synthetic-mobile\nnextRunLabel=synthetic-next\n" +
            "clientCount=128\nhostSourceSha=\(source)\nhostArtifactSha256=\(artifact)\n" +
            "inboxSha256=\(RpcPhoneUsbDeveloperStart.digest(inbox))\n"
    }

    func testInitialDeveloperPrepareRequiresTheExactSourceArtifactCountAndNewSafeLabel() throws {
        let arguments = ["app", "--rpc-usb-prepare", "synthetic-mobile", "--rpc-usb-source-sha", source,
                         "--rpc-usb-artifact-sha256", artifact, "--rpc-usb-client-count", "256"]
        let request = try RpcPhoneUsbDeveloperPrepare(arguments: arguments)
        try request.verify(compiledSource: source, installedArtifact: artifact)
        XCTAssertEqual(request.clientCount, 256)
        XCTAssertEqual(request.runLabel, "synthetic-mobile")
        XCTAssertThrowsError(try request.verify(compiledSource: "main", installedArtifact: artifact))
        XCTAssertThrowsError(try request.verify(compiledSource: source, installedArtifact: "assumed"))
        for changed in [Array(arguments.dropLast()), arguments + ["--rpc-usb-client-count", "256"],
                        arguments.map { $0 == "synthetic-mobile" ? "../unowned" : $0 },
                        arguments.map { $0 == "256" ? "512" : $0 },
                        arguments.map { $0 == source ? "main" : $0 }] {
            XCTAssertThrowsError(try RpcPhoneUsbDeveloperPrepare(arguments: changed))
        }
    }

    func testExact256SourceArtifactInboxBindingVerifiesWithoutCreatingAnOwnerOrTrustImport() throws {
        let text = inbox()
        let config = try RpcPhoneIos.shared.parseCapacityConfig(text: text)
        let request = try RpcPhoneUsbDeveloperStart(record: command(inbox: text))
        try request.verify(config: config, inbox: text, compiledSource: source, installedArtifact: artifact)
        XCTAssertEqual(config.clientCount, 256)
        XCTAssertLessThanOrEqual(text.utf8.count, 16_384)
        XCTAssertEqual(request.runLabel, "synthetic-mobile")
    }

    func testChangedSourceArtifactCapacityAndInboxCannotAuthorizeStart() throws {
        let text = inbox()
        let config = try RpcPhoneIos.shared.parseCapacityConfig(text: text)
        let original = command(inbox: text)
        for changed in [original.replacingOccurrences(of: "runLabel=synthetic-mobile", with: "runLabel=another-run"),
                        original.replacingOccurrences(of: source, with: String(repeating: "4", count: 40)),
                        original.replacingOccurrences(of: artifact, with: String(repeating: "4", count: 64)),
                        original.replacingOccurrences(of: RpcPhoneUsbDeveloperStart.digest(text),
                                                      with: String(repeating: "4", count: 64))] {
            let request = try RpcPhoneUsbDeveloperStart(record: changed)
            XCTAssertThrowsError(try request.verify(config: config, inbox: text, compiledSource: source,
                                                    installedArtifact: artifact))
        }
        let request = try RpcPhoneUsbDeveloperStart(record: original)
        XCTAssertThrowsError(try request.verify(config: config, inbox: text, compiledSource: "main",
                                                installedArtifact: artifact))
        XCTAssertThrowsError(try request.verify(config: config, inbox: text, compiledSource: source,
                                                installedArtifact: "assumed"))
        let changed = inbox(count: 128)
        XCTAssertThrowsError(try request.verify(config: RpcPhoneIos.shared.parseCapacityConfig(text: changed),
                                                inbox: changed, compiledSource: source, installedArtifact: artifact))
    }

    func testMalformedDuplicateUnexpectedNonAsciiAndUnsafeLabelsCannotBecomeCommands() {
        let original = command(inbox: inbox())
        for text in [original + "schema=1\n", original + "pins=arbitrary\n", original + "x=\0\n",
                     original.replacingOccurrences(of: "runLabel=synthetic-mobile", with: "runLabel=../unowned"),
                     original.replacingOccurrences(of: "runLabel=synthetic-mobile", with: "runLabel=synthetic-mobile\r"),
                     original.replacingOccurrences(of: source, with: "main"), "x=" + String(repeating: "a", count: 16_384)] {
            XCTAssertThrowsError(try RpcPhoneUsbDeveloperStart(record: text))
        }
    }

    func testNextRunIsBoundToPreviousInboxAndCannotReuseTheSlotOrRequestUnsupportedCapacity() throws {
        let text = inbox()
        let previous = try RpcPhoneUsbDeveloperStart(record: command(inbox: text))
        let original = next(inbox: text)
        let request = try RpcPhoneUsbDeveloperNext(record: original)
        try request.verify(previous: previous, compiledSource: source, installedArtifact: artifact)
        XCTAssertEqual(request.nextRunLabel, "synthetic-next")
        XCTAssertEqual(request.clientCount, 128)
        for changed in [original.replacingOccurrences(of: "nextRunLabel=synthetic-next", with: "nextRunLabel=synthetic-mobile"),
                        original.replacingOccurrences(of: "nextRunLabel=synthetic-next", with: "nextRunLabel=../unowned"),
                        original.replacingOccurrences(of: "clientCount=128", with: "clientCount=512"), original + "schema=1\n"] {
            XCTAssertThrowsError(try RpcPhoneUsbDeveloperNext(record: changed))
        }
        let wrong = try RpcPhoneUsbDeveloperNext(record: original.replacingOccurrences(
            of: RpcPhoneUsbDeveloperStart.digest(text), with: String(repeating: "4", count: 64)))
        XCTAssertThrowsError(try wrong.verify(previous: previous, compiledSource: source, installedArtifact: artifact))
    }

    func testNextRunRequiresCompleteMatchingHealthyStopReceiptRatherThanOnlyAnExistingFile() throws {
        let text = inbox()
        let closed = "schema=2\nscope=mobile-usb-capacity\nrunLabel=synthetic-mobile\nclientCount=256\n" +
            "runNonce=\(String(repeating: "1", count: 64))\nhostSourceSha=\(source)\nhostPlatform=Ios\n" +
            "hostArtifactSha256=\(artifact)\nruntimeClosed=true\nclientPinsRemoved=true\ncontrolHealthy=true\n"
        try RpcPhoneUsbDeveloperStart.verifyHealthyClosed(closed, inbox: text)
        for changed in [closed.replacingOccurrences(of: "runtimeClosed=true", with: "runtimeClosed=false"),
                        closed.replacingOccurrences(of: "clientPinsRemoved=true", with: "clientPinsRemoved=false"),
                        closed.replacingOccurrences(of: "controlHealthy=true", with: "controlHealthy=false"),
                        closed.replacingOccurrences(of: "clientCount=256", with: "clientCount=128"),
                        closed + "extra=unqualified\n"] {
            XCTAssertThrowsError(try RpcPhoneUsbDeveloperStart.verifyHealthyClosed(changed, inbox: text))
        }
    }
}
#endif
