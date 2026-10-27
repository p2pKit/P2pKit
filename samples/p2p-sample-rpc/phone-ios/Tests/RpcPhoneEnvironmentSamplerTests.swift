import Foundation
import UIKit
import XCTest
@testable import P2pKitRpcPhone

final class RpcPhoneEnvironmentSamplerTests: XCTestCase {
    @MainActor
    func testAcquiringAndRetiringBatteryMonitoringIsIdempotentAndRestoresItsPriorSetting() throws {
        for initiallyEnabled in [false, true] {
            var enabled = initiallyEnabled
            var changes: [Bool] = []
            var batteryReads = 0
            let sampler = RpcPhoneEnvironmentSampler(monitoring: { enabled }, setMonitoring: {
                enabled = $0
                changes.append($0)
            }, battery: {
                batteryReads += 1
                return (0.55, .charging)
            }, thermal: { .nominal })
            let inactive = try sampler.sample()
            XCTAssertEqual(inactive.batteryState, "unavailable")
            XCTAssertNil(inactive.batteryPercentMilli)
            XCTAssertEqual(batteryReads, 0)
            sampler.acquire()
            sampler.acquire()
            let active = try sampler.sample()
            XCTAssertEqual(active.batteryPercentMilli?.intValue, 55_000)
            XCTAssertEqual(active.batteryState, "charging")
            XCTAssertNil(active.batteryCurrentMicroamps)
            XCTAssertNil(active.batteryTemperatureMilliC)
            XCTAssertEqual(active.batterySource, "ios-uidevice")
            XCTAssertEqual(batteryReads, 1)
            sampler.retire()
            sampler.retire()
            XCTAssertEqual(enabled, initiallyEnabled)
            XCTAssertEqual(changes, initiallyEnabled ? [] : [true, false])
            XCTAssertEqual(try sampler.sample().batteryState, "unavailable")
        }
    }

    @MainActor
    func testUnknownBatteryLevelNeverBecomesAnInventedZeroOrAnEnergyMeasurement() throws {
        let levels: [Float] = [-1, .nan, .infinity, -0.1, 1.1]
        for level in levels {
            let sample = try RpcPhoneEnvironmentSampler.normalize(
                level: level, state: .unknown, monitoring: true, thermal: .nominal)
            XCTAssertNil(sample.batteryPercentMilli)
            XCTAssertNil(sample.batteryCurrentMicroamps)
            XCTAssertNil(sample.batteryTemperatureMilliC)
            XCTAssertEqual(sample.batteryState, "unknown")
            XCTAssertEqual(sample.batterySource, "ios-uidevice")
        }
        let zero = try RpcPhoneEnvironmentSampler.normalize(
            level: 0, state: .unplugged, monitoring: true, thermal: .nominal)
        XCTAssertEqual(zero.batteryPercentMilli?.intValue, 0)
        XCTAssertEqual(zero.batteryState, "unplugged")
        let full = try RpcPhoneEnvironmentSampler.normalize(
            level: 1, state: .full, monitoring: true, thermal: .nominal)
        XCTAssertEqual(full.batteryPercentMilli?.intValue, 100_000)
        XCTAssertEqual(full.batteryState, "full")
    }

    @MainActor
    func testSeriousAndCriticalThermalObservationsAbortTheCampaign() throws {
        let readings: [(ProcessInfo.ThermalState, String, Bool)] = [
            (.nominal, "nominal", false), (.fair, "fair", false),
            (.serious, "serious", true), (.critical, "critical", true)
        ]
        for (state, label, abort) in readings {
            let sample = try RpcPhoneEnvironmentSampler.normalize(
                level: -1, state: .unknown, monitoring: false, thermal: state)
            XCTAssertEqual(sample.thermalState, label)
            XCTAssertEqual(sample.thermalSource, "ios-process-info")
            XCTAssertEqual(sample.requiresThermalStop, abort)
        }
    }
}
