package dev.p2pkit.sample.desktop.ui

internal data class ManualEndpoint(val host: String, val port: Int)

internal sealed interface ManualEndpointResult {
    data class Valid(val endpoint: ManualEndpoint) : ManualEndpointResult
    data class Invalid(val reason: String) : ManualEndpointResult
}

/** Parses DNS, IPv4, bracketed IPv6, and unbracketed local IPv6 endpoints. */
internal fun parseManualEndpoint(raw: String): ManualEndpointResult {
    val separator = raw.lastIndexOf(':')
    val host = (if (separator >= 0) raw.substring(0, separator) else raw)
        .trim().removeSurrounding("[", "]")
    val portToken = if (separator >= 0) raw.substring(separator + 1).trim() else ""
    if (host.isEmpty()) return ManualEndpointResult.Invalid("host cannot be empty (expected host:port)")
    val port = portToken.toIntOrNull()
    if (port == null || port !in 1..65_535) {
        return ManualEndpointResult.Invalid("port must be 1..65535 (got '$portToken')")
    }
    if (!host.all { it.isLetterOrDigit() || it in ".:_-%" }) {
        return ManualEndpointResult.Invalid("host contains invalid characters: '$host'")
    }
    return ManualEndpointResult.Valid(ManualEndpoint(host, port))
}
