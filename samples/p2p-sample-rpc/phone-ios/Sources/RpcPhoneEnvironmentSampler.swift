import Foundation
import P2pKitRpcExample
import UIKit

/// Public iOS observations only. There is no public exact battery current, temperature or energy counter here.
@MainActor
final class RpcPhoneEnvironmentSampler {
    private let monitoring: @MainActor () -> Bool
    private let setMonitoring: @MainActor (Bool) -> Void
    private let battery: @MainActor () -> (Float, UIDevice.BatteryState)
    private let thermal: @MainActor () -> ProcessInfo.ThermalState
    private var previousMonitoring: Bool?

    // Default argument expressions are evaluated outside the initializer's
    // actor. Construct the UIKit callbacks inside this MainActor initializer
    // instead, and retain the actor contract in the injected function types.
    convenience init() {
        self.init(monitoring: { UIDevice.current.isBatteryMonitoringEnabled },
                  setMonitoring: { UIDevice.current.isBatteryMonitoringEnabled = $0 },
                  battery: { (UIDevice.current.batteryLevel, UIDevice.current.batteryState) },
                  thermal: { ProcessInfo.processInfo.thermalState })
    }

    init(monitoring: @escaping @MainActor () -> Bool,
         setMonitoring: @escaping @MainActor (Bool) -> Void,
         battery: @escaping @MainActor () -> (Float, UIDevice.BatteryState),
         thermal: @escaping @MainActor () -> ProcessInfo.ThermalState) {
        self.monitoring = monitoring
        self.setMonitoring = setMonitoring
        self.battery = battery
        self.thermal = thermal
    }

    func acquire() {
        guard previousMonitoring == nil else { return }
        previousMonitoring = monitoring()
        if !monitoring() { setMonitoring(true) }
    }

    func retire() {
        guard let previousMonitoring else { return }
        if monitoring() != previousMonitoring { setMonitoring(previousMonitoring) }
        self.previousMonitoring = nil
    }

    func sample() throws -> RpcPhoneEnvironmentStats {
        let active = previousMonitoring != nil && monitoring()
        let (level, state) = active ? battery() : (-1, .unknown)
        return try Self.normalize(level: level, state: state, monitoring: active, thermal: thermal())
    }

    static func normalize(level: Float, state: UIDevice.BatteryState, monitoring: Bool,
                          thermal: ProcessInfo.ThermalState) throws -> RpcPhoneEnvironmentStats {
        let percent: KotlinInt?
        if monitoring, level.isFinite, (0...1).contains(level) {
            // Retain the public API's level; scaling to milli-percent does not assert sensor precision.
            percent = KotlinInt(int: Int32((Double(level) * 100_000).rounded()))
        } else { percent = nil }
        let batteryState: String
        if !monitoring { batteryState = "unavailable" }
        else {
            switch state {
            case .unknown: batteryState = "unknown"
            case .unplugged: batteryState = "unplugged"
            case .charging: batteryState = "charging"
            case .full: batteryState = "full"
            @unknown default: batteryState = "unknown"
            }
        }
        let thermalState: String
        switch thermal {
        case .nominal: thermalState = "nominal"
        case .fair: thermalState = "fair"
        case .serious: thermalState = "serious"
        case .critical: thermalState = "critical"
        @unknown default: thermalState = "unavailable"
        }
        return try RpcPhoneEnvironmentStats(
            batteryPercentMilli: percent, batteryCurrentMicroamps: nil, batteryTemperatureMilliC: nil,
            batteryState: batteryState, batterySource: monitoring ? "ios-uidevice" : "unavailable",
            thermalState: thermalState,
            thermalSource: thermalState == "unavailable" ? "unavailable" : "ios-process-info"
        )
    }
}
