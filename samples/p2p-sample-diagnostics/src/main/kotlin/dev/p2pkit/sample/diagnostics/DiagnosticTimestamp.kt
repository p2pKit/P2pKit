package dev.p2pkit.sample.diagnostics

import kotlin.time.Duration.Companion.days
import kotlin.time.Instant

private val exceptionalIsoTime = Regex(
    "T(23:59:60|24:00:00)(\\.\\d{0,9})?(Z|[+-]\\d{2}:\\d{2}(?::\\d{2})?)$",
    RegexOption.IGNORE_CASE
)
private val emptyIsoFraction = Regex("\\.(?=Z$|[+-]\\d{2}:\\d{2}(?::\\d{2})?$)", RegexOption.IGNORE_CASE)

/** Preserves the previous ISO_INSTANT parser's leap-second/end-of-day normalization. */
private fun parseDiagnosticTimestamp(timestamp: String): Instant {
    val exceptional = exceptionalIsoTime.find(timestamp)
    val endOfDay = exceptional?.groupValues?.get(1) == "24:00:00"
    val normalized = if (exceptional == null) timestamp else {
        val fraction = exceptional.groupValues[2]
        require(!endOfDay || fraction.removePrefix(".").all { it == '0' })
        timestamp.replaceRange(
            exceptional.range,
            "T${if (endOfDay) "00:00:00" else "23:59:59"}$fraction${exceptional.groupValues[3]}"
        )
    }
    val parsed = Instant.parse(normalized.replace(emptyIsoFraction, ""))
    return if (endOfDay) parsed + 1.days else parsed
}

/** UTC naming without java.time, which is absent on supported Android 24/25 runtimes. */
internal fun diagnosticFilenameTimestamp(timestamp: String): String {
    val instant = runCatching { parseDiagnosticTimestamp(timestamp) }.getOrElse { Instant.fromEpochSeconds(0L) }
    val canonical = instant.toString()
    val date = canonical.substringBefore('T')
    val year = date.dropLast(6).toInt()
    // Match the previous formatter's yyyy (year-of-era), including signed extended years.
    val yearOfEra = if (year > 0) year else 1 - year
    val formattedYear = yearOfEra.toString().padStart(4, '0').let { if (yearOfEra > 9_999) "+$it" else it }
    val time = canonical.substringAfter('T').take(8).replace(":", "")
    return "$formattedYear${date.takeLast(6)}T$time"
}
