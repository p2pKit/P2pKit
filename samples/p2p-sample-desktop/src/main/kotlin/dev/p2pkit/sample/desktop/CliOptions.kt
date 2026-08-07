package dev.p2pkit.sample.desktop

internal const val CLI_USAGE: String =
    "Usage: <deviceName> [<appId>] [reconnect=<attempts>,<delayMs>] [trace=off|frames] " +
        "[test=<ID>] [session=<shared-id>] [role=sender|receiver|both] " +
        "[evidence=<directory>] [log=<jsonl-file>]"

internal sealed interface CliParseResult {
    data object Help : CliParseResult
    data class Error(val message: String) : CliParseResult
    data class Success(val options: CliLaunchOptions) : CliParseResult
}

internal data class CliLaunchOptions(
    val deviceName: String?,
    val appId: String?,
    val reconnectArg: String?,
    val traceMode: String?,
    val testId: String?,
    val sessionId: String?,
    val role: String?,
    val evidenceDirectory: String?,
    val jsonlFile: String?
)

/** Parse named launch options without ever assigning them to identity fields. */
internal fun parseCliOptions(args: Array<String>): CliParseResult {
    if (args.any { it == "--help" || it == "-h" }) return CliParseResult.Help

    val positional = mutableListOf<String>()
    var reconnectArg: String? = null
    var traceMode: String? = null
    var testId: String? = null
    var sessionId: String? = null
    var role: String? = null
    var evidenceDirectory: String? = null
    var jsonlFile: String? = null
    for (raw in args) {
        val token = raw.trim()
        if (token.isEmpty()) continue
        when {
            token.startsWith("reconnect=") -> {
                if (reconnectArg != null) return CliParseResult.Error("reconnect specified more than once")
                reconnectArg = token
            }
            token.startsWith("trace=") -> {
                if (traceMode != null) return CliParseResult.Error("trace specified more than once")
                traceMode = token.substringAfter('=')
                if (traceMode !in setOf("off", "frames")) {
                    return CliParseResult.Error("trace must be 'off' or 'frames'")
                }
            }
            token.startsWith("test=") -> {
                if (testId != null) return CliParseResult.Error("test specified more than once")
                val value = token.substringAfter('=').uppercase()
                if (!value.matches(Regex("[A-Z0-9_-]{2,64}"))) {
                    return CliParseResult.Error("test must use 2-64 letters, digits, '_' or '-'")
                }
                testId = value
            }
            token.startsWith("session=") -> {
                if (sessionId != null) return CliParseResult.Error("session specified more than once")
                val value = token.substringAfter('=')
                if (!value.matches(Regex("[A-Za-z0-9._-]{1,80}"))) {
                    return CliParseResult.Error("session must use 1-80 safe identifier characters")
                }
                sessionId = value
            }
            token.startsWith("role=") -> {
                if (role != null) return CliParseResult.Error("role specified more than once")
                val value = token.substringAfter('=').lowercase()
                if (value !in setOf("sender", "receiver", "both", "client", "server")) {
                    return CliParseResult.Error("role must be sender, receiver, both, client, or server")
                }
                role = value
            }
            token.startsWith("evidence=") -> {
                if (evidenceDirectory != null) {
                    return CliParseResult.Error("evidence specified more than once")
                }
                evidenceDirectory = token.substringAfter('=').takeIf { it.isNotBlank() }
                    ?: return CliParseResult.Error("evidence directory cannot be blank")
            }
            token.startsWith("log=") -> {
                if (jsonlFile != null) return CliParseResult.Error("log specified more than once")
                jsonlFile = token.substringAfter('=').takeIf { it.isNotBlank() }
                    ?: return CliParseResult.Error("log file cannot be blank")
            }
            token.startsWith("-") || '=' in token ->
                return CliParseResult.Error("unknown option '$token'")
            else -> positional += token
        }
    }
    if (positional.size > 2) {
        return CliParseResult.Error("too many positional arguments: ${positional.drop(2).joinToString()}")
    }
    return CliParseResult.Success(
        CliLaunchOptions(
            deviceName = positional.getOrNull(0),
            appId = positional.getOrNull(1),
            reconnectArg = reconnectArg,
            traceMode = traceMode,
            testId = testId,
            sessionId = sessionId,
            role = role,
            evidenceDirectory = evidenceDirectory,
            jsonlFile = jsonlFile
        )
    )
}
