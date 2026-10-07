import CoreFoundation
import Foundation
import XCTest

final class LanHostProbeUITests: XCTestCase {
    private let bundleIdentifier = "dev.p2pkit.diagnostics.lanhost"
    private let displayName = "P2pKit LAN Host Probe"
    private let usageDescription = "This diagnostic compares local network discovery between a command-line tool and an installed app."

    @MainActor
    func testApplicationHostProbe() {
        continueAfterFailure = false
        let supplied = ProcessInfo.processInfo.environment["P2PKIT_LAN_HOST_TOKEN"] ?? ""
        let token = supplied.utf8.count == 32 && supplied.allSatisfy { "0123456789abcdef".contains($0) } ? supplied : ""
        let app = XCUIApplication(bundleIdentifier: bundleIdentifier)
        app.launchArguments = ["-AppleLanguages", "(en)", "-AppleLocale", "en_US"]
        app.launchEnvironment["P2PKIT_LAN_HOST_TOKEN"] = token
        var probe: [String: Any]?
        var permission = "notObserved"
        var actionAttempted = false

        func isLocalNetworkAlert(_ alert: XCUIElement) -> Bool {
            let title = alert.staticTexts.matching(NSPredicate(
                format: "label CONTAINS %@ AND (label CONTAINS[c] %@ OR label CONTAINS[c] %@)",
                self.displayName,
                "Find and Connect to Devices on Your Local Network",
                "Access Your Local Network"
            ))
            return title.count == 1 && alert.staticTexts[self.usageDescription].exists
        }

        func handleLocalNetworkAlert(_ alert: XCUIElement) -> Bool {
            guard isLocalNetworkAlert(alert), !actionAttempted else {
                permission = "unhandled"
                return false
            }
            let allow = alert.buttons.matching(NSPredicate(format: "label == %@", "Allow"))
            let okay = alert.buttons.matching(NSPredicate(format: "label == %@", "OK"))
            guard (allow.count == 1 && okay.count == 0) || (okay.count == 1 && allow.count == 0) else {
                permission = "unhandled"
                return false
            }
            actionAttempted = true // Reserve before the action; never retry a consent interaction.
            (allow.count == 1 ? allow.element : okay.element).tap()
            // This records a scoped normal UI action, not proof of a TCC grant.
            if permission != "unhandled" { permission = "handled" }
            return true
        }
        let monitor = addUIInterruptionMonitor(
            withDescription: "Synthetic application Local Network permission", handler: handleLocalNetworkAlert
        )
        defer {
            removeUIInterruptionMonitor(monitor)
            app.terminate()
            let stopped = app.wait(for: .notRunning, timeout: 5)
            let probePayload: Any = probe.map { $0 as Any } ?? NSNull()
            let envelope: [String: Any] = ["schema": 1, "token": token, "probe": probePayload,
                                           "permission": permission, "appNotRunning": stopped]
            let encoded = try? JSONSerialization.data(withJSONObject: envelope, options: [.sortedKeys])
            let text = encoded.flatMap { $0.count <= 8192 ? String(data: $0, encoding: .utf8) : nil }
                ?? "{\"appNotRunning\":false,\"permission\":\"unhandled\",\"probe\":null,\"schema\":1,\"token\":\"\(token)\"}"
            // Private command original: controller joins this token, then removes it from public summaries.
            print("P2PKIT_LAN_APP_V1 \(text)")
        }
        guard !token.isEmpty else { return }
        app.launch()
        guard app.wait(for: .runningForeground, timeout: 10) else { return }
        let begin = app.buttons["lan-probe-begin"]
        let status = app.staticTexts["lan-probe-status"]
        guard begin.waitForExistence(timeout: 5), begin.isHittable, status.label == "READY" else { return }
        begin.tap() // One acknowledged probe attempt only; no alternate tap/relaunch/retry.
        app.tap() // Normal UI interaction delivers an actual interruption to the scoped monitor.
        if !actionAttempted {
            // A prompt may arrive after the normal app tap. Observe only the actual system UI for five seconds.
            // The same handler/one-action guard applies; there is no second Begin, blind tap, or probe-clock reset.
            let system = XCUIApplication(bundleIdentifier: "com.apple.springboard")
            let prompt = XCTNSPredicateExpectation(predicate: NSPredicate { _, _ in
                let alerts = system.alerts
                return alerts.count == 1 && isLocalNetworkAlert(alerts.element)
            }, object: nil)
            if XCTWaiter.wait(for: [prompt], timeout: 5) == .completed {
                _ = handleLocalNetworkAlert(system.alerts.element)
            } else if system.alerts.count > 0 {
                permission = "unhandled"
            }
        }
        let acknowledged = XCTNSPredicateExpectation(predicate: NSPredicate(format: "label != %@", "READY"), object: status)
        guard XCTWaiter.wait(for: [acknowledged], timeout: 5) == .completed else { return }
        let completed = XCTNSPredicateExpectation(predicate: NSPredicate(format: "label == %@", "COMPLETE"), object: status)
        guard XCTWaiter.wait(for: [completed], timeout: 40) == .completed else { return }
        probe = closedProbe(app.staticTexts["lan-probe-result"].label)
        // An unavailable/malformed result remains null and is rejected by the controller, never fabricated.
    }

    private func dictionary(_ value: Any?, keys: Set<String>) -> [String: Any]? {
        guard let value = value as? [String: Any], Set(value.keys) == keys else { return nil }
        return value
    }

    private func boolean(_ value: Any?) -> Bool {
        guard let number = value as? NSNumber else { return false }
        return CFGetTypeID(number) == CFBooleanGetTypeID()
    }

    private func integer(_ value: Any?, _ bounds: ClosedRange<Int64>) -> Bool {
        guard let number = value as? NSNumber, !boolean(number),
              ["c", "s", "i", "l", "q", "C", "S", "I", "L", "Q"].contains(String(cString: number.objCType)),
              number.stringValue == String(number.int64Value) else { return false }
        return bounds.contains(number.int64Value)
    }

    private func closedProbe(_ text: String) -> [String: Any]? {
        guard let data = text.data(using: .utf8), data.count <= 6144,
              let object = try? JSONSerialization.jsonObject(with: data),
              let top = dictionary(object, keys: ["schema", "diagnosticOnly", "mode", "browserDescriptor", "outcome", "windowMilliseconds",
                  "observationElapsedMilliseconds", "cleanupElapsedMilliseconds", "isSimulatorBuild", "isX86_64Build",
                  "counterOverflow", "packaging", "peers", "cleanup"]),
              integer(top["schema"], 1...1), boolean(top["diagnosticOnly"]),
              (top["diagnosticOnly"] as? NSNumber)?.boolValue == true, top["mode"] as? String == "app",
              top["browserDescriptor"] as? String == "WITH_TXT",
              ["discovered", "notDiscovered", "setupFailed", "cleanupUnconfirmed", "counterOverflow", "timingInvalid"].contains(top["outcome"] as? String ?? ""),
              integer(top["windowMilliseconds"], 30000...30000),
              integer(top["observationElapsedMilliseconds"], 0...120000), integer(top["cleanupElapsedMilliseconds"], 0...120000),
              ["isSimulatorBuild", "isX86_64Build", "counterOverflow"].allSatisfy({ boolean(top[$0]) }),
              let packaging = dictionary(top["packaging"], keys: ["readOK", "usageDescriptionPresent", "requiredBonjourPresent",
                  "bundleIdentifierPresent", "expectedBundleIdentifier", "applicationPackageType"]),
              packaging.values.allSatisfy({ boolean($0) }),
              let cleanup = dictionary(top["cleanup"], keys: ["listenersCreated", "listenersCancelled", "browsersCreated", "browsersCancelled", "complete"]),
              ["listenersCreated", "listenersCancelled", "browsersCreated", "browsersCancelled"].allSatisfy({ integer(cleanup[$0], 0...2) }),
              boolean(cleanup["complete"]), let peers = top["peers"] as? [Any], peers.count == 2 else { return nil }
        let counts: Set<String> = ["listenerReady", "listenerWaiting", "listenerFailed", "browserReady", "browserWaiting", "browserFailed",
            "registrationAdded", "registrationRemoved", "resultCallbacks", "maximumResultCount", "unexpectedConnections"]
        let flags: Set<String> = ["listenerCancelled", "browserCancelled", "ownRegistrationObserved", "registrationNameChanged", "expectedPeerObserved"]
        let states: Set<String> = ["none", "setup", "waiting", "ready", "failed", "cancelled", "unknown"]
        let configurationFlags: Set<String> = ["listenerObserved", "listenerNoDelay", "listenerP2P", "listenerCellBan",
            "browserObserved", "browserP2P", "browserCellBan", "browserIncludesTXT", "advertisementAfterReady", "noAutoRename",
            "configuredServiceTxtPresent", "configuredServiceTxtReadbackMatches", "configuredServiceTxtShapeValid"]
        let transports: Set<String> = ["unobserved", "none", "tcp", "other"]
        let metadataCounts: Set<String> = ["observations", "matchingObservations", "malformedObservations"]
        let metadataFlags: Set<String> = ["received", "present", "identityMatched", "matchesExpected", "rawMatchesExpected", "malformed"]
        let interfaceKinds: Set<String> = ["cellular", "loopback", "other", "unknown", "wifi", "wiredEthernet"]
        for row in peers {
            guard let peer = dictionary(row, keys: counts.union(flags).union(["listenerLastState", "browserLastState", "listenerError", "browserError",
                      "configuration", "interfaces", "txtMetadata"])),
                  counts.allSatisfy({ integer(peer[$0], 0...65535) }), flags.allSatisfy({ boolean(peer[$0]) }),
                  states.contains(peer["listenerLastState"] as? String ?? ""), states.contains(peer["browserLastState"] as? String ?? ""),
                  let configuration = dictionary(peer["configuration"], keys: configurationFlags.union(["listenerTransport", "browserTransport"])),
                  configurationFlags.allSatisfy({ boolean(configuration[$0]) }),
                  transports.contains(configuration["listenerTransport"] as? String ?? ""),
                  transports.contains(configuration["browserTransport"] as? String ?? ""),
                  let interfaces = dictionary(peer["interfaces"], keys: ["observed", "count", "kinds"]),
                  boolean(interfaces["observed"]), integer(interfaces["count"], 0...128),
                  let kinds = interfaces["kinds"] as? [String], kinds.count <= 6,
                  kinds.allSatisfy({ interfaceKinds.contains($0) }), kinds == Set(kinds).sorted(),
                  let metadata = dictionary(peer["txtMetadata"], keys: metadataCounts.union(metadataFlags).union(["ownedResults", "maximumBytes", "kind"])),
                  metadataCounts.allSatisfy({ integer(metadata[$0], 0...65535) }),
                  metadataFlags.allSatisfy({ boolean(metadata[$0]) }),
                  integer(metadata["ownedResults"], 0...128), integer(metadata["maximumBytes"], 0...65535),
                  ["none", "bonjour", "other", "mixed"].contains(metadata["kind"] as? String ?? "") else { return nil }
            for name in ["listenerError", "browserError"] {
                guard let error = dictionary(peer[name], keys: ["domain", "code"]),
                      ["none", "dns", "posix", "tls", "other"].contains(error["domain"] as? String ?? ""),
                      integer(error["code"], -2147483648...2147483647) else { return nil }
            }
        }
        return top
    }
}
