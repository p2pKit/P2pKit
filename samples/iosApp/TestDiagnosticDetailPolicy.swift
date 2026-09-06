/// Closed detail/configuration schema; mirror DiagnosticDetailPolicy in the JVM sample helper.
/// Keys must be application-owned literals. Raw text and unknown fields are never admitted.
enum TestDiagnosticDetailPolicy {
    private static let booleanFields: Set<String> = [
        "authenticated", "testMode", "directJsonl", "enabled", "synthetic", "syntheticExample",
        "operatorDeclared", "productionBehaviorChanged", "durable", "contentsExported",
        "sessionSnapshot", "restoredTestSession", "persistentAcrossProcessRestart", "testSessionSelected",
        "retainedSession", "senderDigestAvailable"
    ]
    private static let numericFields: Set<String> = [
        "totalBytes", "keepAlivePingMillis", "keepAliveTimeoutMillis", "maximumSampleFileBytes"
    ]
    private static let fixedValues: [String: Set<String>] = [
        "match": ["true", "false", "unknown"],
        "platform": ["ANDROID", "JVM_DESKTOP", "IOS", "MACOS", "WINDOWS", "LINUX", "UNKNOWN"],
        "location": ["app-private", "app-scoped-external"],
        "source": ["android-content-uri"],
        "securityPolicy": ["authenticated-same-app-test-only"],
        "identityStorage": ["in-memory-per-kit"],
        "feature": ["file-commit-sha256-v1"],
        "messageType": ["text", "binary"],
        "mimeType": ["test-fixture", "application/octet-stream", "unknown"],
        "observer": ["AndroidNetworkPathObserver"],
        "operatorCommand": ["diag start"],
        "diagnosticsMode": ["explicit-test-harness"],
        "protocolVersion": ["secure-v2", "legacy-v1"],
        "diagnosticRetention": ["5000-events/5MiB-memory/4x2MiB-disk"],
        "faultInjection": ["none"],
        "preset": ["200 KiB", "5 MiB", "49 MiB"]
    ]

    static func accepts(key: String, value: String) -> Bool {
        switch key {
        case "sha256", "packageSha256": return isLowerHex(value, length: 64)
        case "messageId": return isLowerHex(value, length: 32)
        case "progressPercent": return isUnsignedLong(value) && (Int64(value) ?? 101) <= 100
        default:
            if booleanFields.contains(key) { return value == "true" || value == "false" }
            if numericFields.contains(key) { return isUnsignedLong(value) }
            return fixedValues[key]?.contains(value) == true
        }
    }

    private static func isLowerHex(_ value: String, length: Int) -> Bool {
        value.utf8.count == length && value.utf8.allSatisfy {
            ($0 >= 48 && $0 <= 57) || ($0 >= 97 && $0 <= 102)
        }
    }

    private static func isUnsignedLong(_ value: String) -> Bool {
        (1...19).contains(value.utf8.count) && (value.utf8.count == 1 || value.utf8.first != 48) &&
            value.utf8.allSatisfy { $0 >= 48 && $0 <= 57 } && Int64(value) != nil
    }
}
