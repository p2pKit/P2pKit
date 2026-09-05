import Foundation
import XCTest
@testable import P2pKitSample

final class SampleConsoleTests: XCTestCase {
    func testMessageSummariesHaveSizeAndOpaqueIdentityNotPayload() {
        let body = "synthetic private text 👋"
        let peerId = "synthetic-stable-peer-id"
        let received = SampleConsole.received(peerId: peerId, isText: true, sizeBytes: Int64(body.utf8.count))
        let sent = SampleConsole.sendingText(recipients: 2, sizeBytes: body.utf8.count)
        for line in [received, sent] {
            XCTAssertTrue(line.contains("<text \(body.utf8.count)B>"))
            XCTAssertFalse(line.contains(body))
            XCTAssertFalse(line.contains(peerId))
        }
        XCTAssertTrue(sent.contains("not remote processing"))
        XCTAssertEqual(SampleConsole.identifier("abc"), "anon-ba7816bf8f01cfea")
    }

    func testFailureDescriptionsAndPeerControlledTransferReasonsAreOmitted() {
        let canary = "Synthetic Private Name /private/example.txt 192.0.2.9"
        let error = NSError(domain: canary, code: 7, userInfo: [NSLocalizedDescriptionKey: canary])
        XCTAssertEqual(SampleConsole.failure(error), "errorCode=7 (details omitted)")
        for state in ["Cancelled", "Rejected", "Failed"] {
            XCTAssertEqual(SampleConsole.transferState(state + ": " + canary), state)
        }
        XCTAssertEqual(SampleConsole.transferState("Sending 50%"), "Sending")
        XCTAssertEqual(SampleConsole.transferState(canary), "Unknown")
    }
}
