package dev.p2pkit.sample.diagnostics

/**
 * Closed schema for shareable detail/configuration values. Keys are application-owned literals,
 * never peer input. Keep this policy aligned with the Swift sample's TestDiagnosticDetailPolicy.
 * Raw text and unknown fields are deliberately not admitted, even if their values look like IDs.
 */
internal object DiagnosticDetailPolicy {
    private val booleanFields = setOf(
        "authenticated", "testMode", "directJsonl", "enabled", "synthetic", "syntheticExample",
        "operatorDeclared", "productionBehaviorChanged", "durable", "contentsExported",
        "sessionSnapshot", "restoredTestSession", "persistentAcrossProcessRestart", "testSessionSelected",
        "retainedSession", "senderDigestAvailable"
    )
    private val numericFields = setOf(
        "totalBytes", "keepAlivePingMillis", "keepAliveTimeoutMillis", "maximumSampleFileBytes"
    )
    private val fixedValues = mapOf(
        "match" to setOf("true", "false", "unknown"),
        "platform" to setOf("ANDROID", "JVM_DESKTOP", "IOS", "MACOS", "WINDOWS", "LINUX", "UNKNOWN"),
        "location" to setOf("app-private", "app-scoped-external"),
        "source" to setOf("android-content-uri"),
        "securityPolicy" to setOf("authenticated-same-app-test-only"),
        "identityStorage" to setOf("in-memory-per-kit"),
        "feature" to setOf("file-commit-sha256-v1"),
        "messageType" to setOf("text", "binary"),
        "mimeType" to setOf("test-fixture", "application/octet-stream", "unknown"),
        "observer" to setOf("AndroidNetworkPathObserver"),
        "operatorCommand" to setOf("diag start"),
        "diagnosticsMode" to setOf("explicit-test-harness"),
        "protocolVersion" to setOf("secure-v2", "legacy-v1"),
        "diagnosticRetention" to setOf("5000-events/5MiB-memory/4x2MiB-disk"),
        "faultInjection" to setOf("none"),
        "preset" to setOf("200 KiB", "5 MiB", "49 MiB")
    )

    fun accepts(key: String, value: String): Boolean = when (key) {
        "sha256", "packageSha256" -> value.isLowerHex(64)
        "messageId" -> value.isLowerHex(32)
        "progressPercent" -> value.isUnsignedLong() && value.toLong() <= 100L
        in booleanFields -> value == "true" || value == "false"
        in numericFields -> value.isUnsignedLong()
        else -> fixedValues[key]?.contains(value) == true
    }

    private fun String.isLowerHex(length: Int): Boolean =
        this.length == length && all { it in '0'..'9' || it in 'a'..'f' }

    private fun String.isUnsignedLong(): Boolean =
        length in 1..19 && (length == 1 || first() != '0') &&
            all { it in '0'..'9' } && toLongOrNull() != null
}
