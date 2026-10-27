#if DEBUG
import CryptoKit
import Foundation
import P2pKitRpcExample

struct RpcPhoneUsbDeveloperPrepare {
    let runLabel: String
    let clientCount: Int32
    private let sourceSha: String
    private let artifactSha256: String

    init(arguments: [String]) throws {
        var values: [String: String] = [:]
        for flag in ["--rpc-usb-prepare", "--rpc-usb-source-sha", "--rpc-usb-artifact-sha256", "--rpc-usb-client-count"] {
            guard arguments.filter({ $0 == flag }).count == 1,
                  let index = arguments.firstIndex(of: flag), index + 1 < arguments.count else {
                throw RpcPhoneCapacityIOError.invalidRecord
            }
            values[flag] = arguments[index + 1]
        }
        guard usbFullMatch(values["--rpc-usb-prepare"], "[a-z0-9-]{1,64}"),
              usbFullMatch(values["--rpc-usb-source-sha"], "[a-f0-9]{40}"),
              usbFullMatch(values["--rpc-usb-artifact-sha256"], "[a-f0-9]{64}"),
              ["128", "256"].contains(values["--rpc-usb-client-count"] ?? "") else {
            throw RpcPhoneCapacityIOError.invalidRecord
        }
        runLabel = values["--rpc-usb-prepare"]!
        clientCount = Int32(values["--rpc-usb-client-count"]!)!
        sourceSha = values["--rpc-usb-source-sha"]!
        artifactSha256 = values["--rpc-usb-artifact-sha256"]!
    }

    func verify(compiledSource: String, installedArtifact: String) throws {
        guard sourceSha == compiledSource, artifactSha256 == installedArtifact else {
            throw RpcPhoneCapacityIOError.invalidRecord
        }
    }
}

/// Developer-only control over an exact app-owned inbox; the command itself has no pins or network settings.
struct RpcPhoneUsbDeveloperStart {
    let runLabel: String
    let sourceSha: String
    let artifactSha256: String
    let inboxSha256: String

    init(record: String) throws {
        let values = try usbCommandFields(record)
        guard Set(values.keys) == Set(["schema", "scope", "runLabel", "hostSourceSha",
                                      "hostArtifactSha256", "inboxSha256"]),
              values["schema"] == "1", values["scope"] == "mobile-usb-start",
              usbFullMatch(values["runLabel"], "[a-z0-9-]{1,64}"),
              usbFullMatch(values["hostSourceSha"], "[a-f0-9]{40}"),
              usbFullMatch(values["hostArtifactSha256"], "[a-f0-9]{64}"),
              usbFullMatch(values["inboxSha256"], "[a-f0-9]{64}") else {
            throw RpcPhoneCapacityIOError.invalidRecord
        }
        runLabel = values["runLabel"]!
        sourceSha = values["hostSourceSha"]!
        artifactSha256 = values["hostArtifactSha256"]!
        inboxSha256 = values["inboxSha256"]!
    }

    func verify(config: RpcMobileCapacityConfig, inbox: String, compiledSource: String,
                installedArtifact: String) throws {
        guard config.hostPlatform == "Ios", config.runLabel == runLabel,
              sourceSha == compiledSource, config.hostSourceSha == sourceSha,
              artifactSha256 == installedArtifact, config.hostArtifactSha256 == artifactSha256,
              Self.digest(inbox) == inboxSha256 else { throw RpcPhoneCapacityIOError.invalidRecord }
    }

    static func digest(_ inbox: String) -> String {
        SHA256.hash(data: Data(inbox.utf8)).map { String(format: "%02x", $0) }.joined()
    }

    /// No next run until the source-bound Stop receipt says runtime and client approvals both retired.
    static func verifyHealthyClosed(_ record: String, inbox: String) throws {
        let input = try usbCommandFields(inbox)
        let fields = Set(["schema", "scope", "runLabel", "runNonce", "hostPlatform", "hostSourceSha",
                          "hostArtifactSha256"] + (input["schema"] == "2" ? ["clientCount"] : []))
        var expected = input.filter { fields.contains($0.key) }
        expected["runtimeClosed"] = "true"
        expected["clientPinsRemoved"] = "true"
        expected["controlHealthy"] = "true"
        guard try usbCommandFields(record) == expected else { throw RpcPhoneCapacityIOError.invalidRecord }
    }
}

struct RpcPhoneUsbDeveloperNext {
    let nextRunLabel: String
    let clientCount: Int32
    private let values: [String: String]

    init(record: String) throws {
        let parsed = try usbCommandFields(record)
        guard Set(parsed.keys) == Set(["schema", "scope", "runLabel", "nextRunLabel", "clientCount", "hostSourceSha",
                                      "hostArtifactSha256", "inboxSha256"]),
              parsed["schema"] == "1", parsed["scope"] == "mobile-usb-prepare-next",
              usbFullMatch(parsed["runLabel"], "[a-z0-9-]{1,64}"),
              usbFullMatch(parsed["nextRunLabel"], "[a-z0-9-]{1,64}"),
              parsed["nextRunLabel"] != parsed["runLabel"],
              ["128", "256"].contains(parsed["clientCount"] ?? ""),
              usbFullMatch(parsed["hostSourceSha"], "[a-f0-9]{40}"),
              usbFullMatch(parsed["hostArtifactSha256"], "[a-f0-9]{64}"),
              usbFullMatch(parsed["inboxSha256"], "[a-f0-9]{64}") else {
            throw RpcPhoneCapacityIOError.invalidRecord
        }
        values = parsed
        nextRunLabel = parsed["nextRunLabel"]!
        clientCount = Int32(parsed["clientCount"]!)!
    }

    func verify(previous: RpcPhoneUsbDeveloperStart, compiledSource: String, installedArtifact: String) throws {
        guard values["runLabel"] == previous.runLabel, values["hostSourceSha"] == previous.sourceSha,
              values["hostSourceSha"] == compiledSource, values["hostArtifactSha256"] == previous.artifactSha256,
              values["hostArtifactSha256"] == installedArtifact, values["inboxSha256"] == previous.inboxSha256 else {
            throw RpcPhoneCapacityIOError.invalidRecord
        }
    }
}

private func usbFullMatch(_ value: String?, _ pattern: String) -> Bool {
    guard let value, let match = value.range(of: "^" + pattern + "$", options: .regularExpression) else { return false }
    return match == value.startIndex..<value.endIndex
}

private func usbCommandFields(_ record: String) throws -> [String: String] {
    guard (1...16_384).contains(record.utf8.count), record.utf8.allSatisfy({ $0 == 10 || (32...126).contains($0) }) else {
        throw RpcPhoneCapacityIOError.invalidRecord
    }
    var values: [String: String] = [:]
    for line in record.split(separator: "\n") {
        let pair = line.split(separator: "=", maxSplits: 1, omittingEmptySubsequences: false)
        guard pair.count == 2, !pair[0].isEmpty, !pair[1].isEmpty,
              values.updateValue(String(pair[1]), forKey: String(pair[0])) == nil else {
            throw RpcPhoneCapacityIOError.invalidRecord
        }
    }
    return values
}
#endif
