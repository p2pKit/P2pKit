import Foundation
import UIKit
import XCTest
@testable import P2pKitRpcPhone

final class RpcPhoneEnvironmentSamplerTests: XCTestCase {
    @MainActor
    func testPlatformDefaultsReadAndRestoreActualMainActorDeviceMonitoring() throws {
        let device = UIDevice.current
        let initiallyEnabled = device.isBatteryMonitoringEnabled
        let sampler = RpcPhoneEnvironmentSampler()
        defer {
            sampler.retire()
            XCTAssertEqual(device.isBatteryMonitoringEnabled, initiallyEnabled)
        }
        XCTAssertEqual(try sampler.sample().batteryState, "unavailable")
        sampler.acquire()
        // UIDevice monitoring is an observed capability, not a promised sensor.
        // Keep the real platform constructor covered without inventing support
        // when the OS refuses the requested setting (for example on a simulator).
        let monitoringEnabled = device.isBatteryMonitoringEnabled
        let sample = try sampler.sample()
        XCTAssertEqual(sample.batterySource, monitoringEnabled ? "ios-uidevice" : "unavailable")
        if monitoringEnabled {
            XCTAssertTrue(["unknown", "unplugged", "charging", "full"].contains(sample.batteryState))
            if let percent = sample.batteryPercentMilli {
                XCTAssertTrue((0...100_000).contains(percent.intValue))
            }
        } else {
            XCTAssertEqual(sample.batteryState, "unavailable")
            XCTAssertNil(sample.batteryPercentMilli)
        }
        XCTAssertNil(sample.batteryCurrentMicroamps)
        XCTAssertNil(sample.batteryTemperatureMilliC)
        sampler.retire()
        XCTAssertEqual(device.isBatteryMonitoringEnabled, initiallyEnabled)
        XCTAssertEqual(try sampler.sample().batteryState, "unavailable")
    }

    @MainActor
    func testUnavailableMonitoringAttemptsEnableOnceAndNeverReadsOrInventsBatteryValues() throws {
        var changes: [Bool] = []
        var batteryReads = 0
        let sampler = RpcPhoneEnvironmentSampler(monitoring: { false }, setMonitoring: {
            changes.append($0) // Model the OS refusing to enable this optional capability.
        }, battery: {
            batteryReads += 1
            XCTFail("Unavailable monitoring must not read the battery callback")
            return (0.55, .charging)
        }, thermal: { .fair })
        defer { sampler.retire() }
        sampler.acquire()
        sampler.acquire()
        XCTAssertEqual(changes, [true])
        let sample = try sampler.sample()
        XCTAssertEqual(sample.batterySource, "unavailable")
        XCTAssertEqual(sample.batteryState, "unavailable")
        XCTAssertNil(sample.batteryPercentMilli)
        XCTAssertNil(sample.batteryCurrentMicroamps)
        XCTAssertNil(sample.batteryTemperatureMilliC)
        XCTAssertEqual(sample.thermalState, "fair")
        XCTAssertEqual(batteryReads, 0)
        sampler.retire()
        sampler.retire()
        XCTAssertEqual(changes, [true])
        XCTAssertEqual(try sampler.sample().batteryState, "unavailable")
        XCTAssertEqual(batteryReads, 0)
    }

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
