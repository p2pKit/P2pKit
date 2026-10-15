package dev.p2pkit.sample.desktop

import java.io.Reader

internal const val CLI_MAX_INPUT_CHARS: Int = 65_536

internal class CliInputTooLongException : IllegalArgumentException(
    "command exceeds $CLI_MAX_INPUT_CHARS characters (input omitted)"
)

/** Drain a rejected line without retaining it or interpreting its tail as another command. */
internal class CliLineReader(private val reader: Reader) {
    private var skipLineFeed = false

    fun readLine(): String? {
        val line = StringBuilder()
        var tooLong = false
        while (true) {
            val next = reader.read()
            if (next == -1) {
                if (line.isEmpty() && !tooLong) return null
                break
            }
            if (skipLineFeed) {
                skipLineFeed = false
                if (next == '\n'.code) continue
            }
            if (next == '\r'.code) {
                skipLineFeed = true
                break
            }
            if (next == '\n'.code) break
            if (line.length == CLI_MAX_INPUT_CHARS) {
                tooLong = true
            } else if (!tooLong) {
                line.append(next.toChar())
            }
        }
        if (tooLong) throw CliInputTooLongException()
        return line.toString()
    }
}
