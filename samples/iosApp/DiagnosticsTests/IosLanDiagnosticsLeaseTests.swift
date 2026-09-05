import Foundation
import P2pKitShared
import XCTest
@testable import P2pKitSample

final class IosLanDiagnosticsLeaseTests: XCTestCase {
    private var previousMirror = false
    private var previousHistory = false

    override func setUp() {
        super.setUp()
        previousMirror = IosLanDebug.shared.mirrorToConsole
        previousHistory = IosLanDebug.shared.retainHistory
        IosLanDebug.shared.mirrorToConsole = false
        IosLanDebug.shared.retainHistory = false
    }

    override func tearDown() {
        IosLanDebug.shared.mirrorToConsole = previousMirror
        IosLanDebug.shared.retainHistory = previousHistory
        super.tearDown()
    }

    func testConsoleOptInMatchesBuildConfigurationAndDefaultSettingsAreRestored() {
        let lease = IosLanDiagnosticsLease.acquire()
        defer { lease.release() }
        assertActiveSettings()
        IosLanDebug.shared.log(tag: "test", message: "synthetic-startup-epoch")
        XCTAssertFalse(IosLanDebug.shared.events.replayCache.isEmpty)

        lease.release()
        XCTAssertFalse(IosLanDebug.shared.mirrorToConsole)
        XCTAssertFalse(IosLanDebug.shared.retainHistory)
        XCTAssertTrue(IosLanDebug.shared.events.replayCache.isEmpty)
        lease.release()
        XCTAssertFalse(IosLanDebug.shared.mirrorToConsole)
        XCTAssertFalse(IosLanDebug.shared.retainHistory)
    }

    func testOverlappingOwnersAndStaleReleaseDoNotDisableTheActiveRun() {
        let first = IosLanDiagnosticsLease.acquire()
        let second = IosLanDiagnosticsLease.acquire()
        defer { first.release(); second.release() }
        first.release()
        first.release()
        assertActiveSettings()

        second.release()
        XCTAssertFalse(IosLanDebug.shared.mirrorToConsole)
        XCTAssertFalse(IosLanDebug.shared.retainHistory)
        let next = IosLanDiagnosticsLease.acquire()
        defer { next.release() }
        second.release()
        assertActiveSettings()
    }

    func testOutOfOrderReleasePreservesAllOtherOwners() {
        let first = IosLanDiagnosticsLease.acquire()
        let second = IosLanDiagnosticsLease.acquire()
        let third = IosLanDiagnosticsLease.acquire()
        defer { first.release(); second.release(); third.release() }
        third.release()
        second.release()
        assertActiveSettings()
        first.release()
        XCTAssertFalse(IosLanDebug.shared.mirrorToConsole)
        XCTAssertFalse(IosLanDebug.shared.retainHistory)
    }

    func testEachRunRestoresItsOwnHostConfiguration() {
        for mirror in [false, true] {
            for history in [false, true] {
                IosLanDebug.shared.mirrorToConsole = mirror
                IosLanDebug.shared.retainHistory = history
                let lease = IosLanDiagnosticsLease.acquire()
                XCTAssertTrue(IosLanDebug.shared.retainHistory)
                #if DEBUG
                XCTAssertTrue(IosLanDebug.shared.mirrorToConsole)
                #else
                XCTAssertEqual(IosLanDebug.shared.mirrorToConsole, mirror)
                #endif
                lease.release()
                XCTAssertEqual(IosLanDebug.shared.mirrorToConsole, mirror)
                XCTAssertEqual(IosLanDebug.shared.retainHistory, history)
            }
        }
    }

    func testPreRetainingHostHistoryIsNotErasedOnRelease() {
        IosLanDebug.shared.retainHistory = true
        IosLanDebug.shared.log(tag: "test", message: "synthetic-host-history")
        let previousLines = IosLanDebug.shared.events.replayCache.compactMap { $0 as? String }
        XCTAssertFalse(previousLines.isEmpty)
        let lease = IosLanDiagnosticsLease.acquire()
        lease.release()
        XCTAssertTrue(IosLanDebug.shared.retainHistory)
        XCTAssertEqual(IosLanDebug.shared.events.replayCache.compactMap { $0 as? String }, previousLines)
    }

    func testDeinitializationReleasesOnlyItsOwnLease() {
        let first = IosLanDiagnosticsLease.acquire()
        var second: IosLanDiagnosticsLease? = IosLanDiagnosticsLease.acquire()
        XCTAssertNotNil(second)
        second = nil
        assertActiveSettings()
        first.release()
        XCTAssertFalse(IosLanDebug.shared.mirrorToConsole)
        XCTAssertFalse(IosLanDebug.shared.retainHistory)

        var last: IosLanDiagnosticsLease? = IosLanDiagnosticsLease.acquire()
        XCTAssertNotNil(last)
        last = nil
        XCTAssertFalse(IosLanDebug.shared.mirrorToConsole)
        XCTAssertFalse(IosLanDebug.shared.retainHistory)
    }

    func testReleaseBuildNeverTakesOwnershipOfExternalConsoleChanges() {
        let lease = IosLanDiagnosticsLease.acquire()
        defer { lease.release() }
        // An explicit host override is not owned by a Release sample lease.
        IosLanDebug.shared.mirrorToConsole = true
        lease.release()
        #if DEBUG
        XCTAssertFalse(IosLanDebug.shared.mirrorToConsole)
        #else
        XCTAssertTrue(IosLanDebug.shared.mirrorToConsole)
        #endif
    }

    private func assertActiveSettings(file: StaticString = #filePath, line: UInt = #line) {
        XCTAssertTrue(IosLanDebug.shared.retainHistory, file: file, line: line)
        #if DEBUG
        XCTAssertTrue(IosLanDebug.shared.mirrorToConsole, file: file, line: line)
        #else
        XCTAssertFalse(IosLanDebug.shared.mirrorToConsole, file: file, line: line)
        #endif
    }
}
