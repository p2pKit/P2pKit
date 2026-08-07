package dev.p2pkit.core.testfixtures

import dev.p2pkit.core.P2pLogger

/**
 * [P2pLogger] that records every entry for assertions (fixture change F7 /
 * TST-13). Production surfaces many soft failures as `warn`-level
 * diagnostics instead of crashing; suites that run a NoOp logger cannot
 * observe them. Handing this logger to the component under test turns those
 * diagnostics into assertable state.
 *
 * Teardown convention for heavyweight suites: call
 * [assertNoUnexpectedWarnOrError] at the end of a test to fail on any
 * warn/error diagnostic the test did not explicitly expect.
 */
internal class RecordingLogger : P2pLogger {

    enum class Level { DEBUG, INFO, WARN, ERROR }

    data class Entry(val level: Level, val message: String, val throwable: Throwable? = null)

    private val _entries = SnapshotList<Entry>()

    /** Every recorded entry, oldest first. */
    val entries: List<Entry> get() = _entries.snapshot()

    /** Messages recorded at warn level, oldest first. */
    val warnings: List<String> get() = entries.filter { it.level == Level.WARN }.map { it.message }

    /** Messages recorded at error level, oldest first. */
    val errors: List<String> get() = entries.filter { it.level == Level.ERROR }.map { it.message }

    override fun debug(message: String) {
        _entries.add(Entry(Level.DEBUG, message))
    }

    override fun info(message: String) {
        _entries.add(Entry(Level.INFO, message))
    }

    override fun warn(message: String, throwable: Throwable?) {
        _entries.add(Entry(Level.WARN, message, throwable))
    }

    override fun error(message: String, throwable: Throwable?) {
        _entries.add(Entry(Level.ERROR, message, throwable))
    }

    /**
     * Fail if any warn/error entry was recorded that [isExpected] does not
     * account for. Default: no warn/error is expected.
     */
    fun assertNoUnexpectedWarnOrError(isExpected: (Entry) -> Boolean = { false }) {
        val unexpected = entries.filter {
            (it.level == Level.WARN || it.level == Level.ERROR) && !isExpected(it)
        }
        if (unexpected.isNotEmpty()) {
            throw AssertionError(
                "Unexpected warn/error diagnostics recorded:\n" +
                    unexpected.joinToString("\n") { "  [${it.level}] ${it.message}" }
            )
        }
    }
}
