package dev.p2pkit.sample.desktop

internal const val CLI_USAGE: String =
    "Usage: <deviceName> [<appId>] [reconnect=<attempts>,<delayMs>] [trace=off|frames]"

internal sealed interface CliParseResult {
    data object Help : CliParseResult
    data class Error(val message: String) : CliParseResult
    data class Success(val options: CliLaunchOptions) : CliParseResult
}

internal data class CliLaunchOptions(
    val deviceName: String?,
    val appId: String?,
    val reconnectArg: String?,
    val traceMode: String?
)

/** Parse named launch options without ever assigning them to identity fields. */
internal fun parseCliOptions(args: Array<String>): CliParseResult {
    if (args.any { it == "--help" || it == "-h" }) return CliParseResult.Help

    val positional = mutableListOf<String>()
    var reconnectArg: String? = null
    var traceMode: String? = null
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
            traceMode = traceMode
        )
    )
}
