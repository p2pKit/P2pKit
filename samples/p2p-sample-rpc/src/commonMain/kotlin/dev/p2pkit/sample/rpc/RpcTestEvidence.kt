package dev.p2pkit.sample.rpc

import kotlinx.serialization.json.Json

/** Decode one original archived record. Never import it into the current workload/session. */
@Throws(Exception::class)
public fun readRpcTestEvidence(runId: String, text: String): RpcDeviceTestReport {
    require(runId.matches(Regex("[a-f0-9]{32}")) && text.encodeToByteArray().size <= 65_536)
    val report = Json.decodeFromString<RpcDeviceTestReport>(text)
    require(report.runId == runId && validDeviceTestReport(report))
    return report
}

public data class RpcTestArchivePage(
    public val reports: List<RpcDeviceTestReport>,
    public val olderAvailable: Boolean,
    public val beforeMillis: Long,
    public val beforeRunId: String,
)

/** A bounded newest-first page, even when the on-disk enumeration has no order. */
public class RpcTestArchiveScan(public val beforeMillis: Long = Long.MAX_VALUE, public val beforeRunId: String = "") {
    private val rows = mutableListOf<RpcDeviceTestReport>()
    private var eligible = 0
    private var scanned = 0
    private var finished = false

    init {
        require(beforeMillis == Long.MAX_VALUE && beforeRunId.isEmpty() ||
            beforeMillis in 0..4_102_444_800_000 && beforeRunId.matches(Regex("[a-f0-9]{32}")))
    }

    @Throws(Exception::class)
    public fun accept(runId: String, text: String) {
        check(!finished && ++scanned <= 1_000_000)
        val report = readRpcTestEvidence(runId, text)
        if (report.startedAtEpochMillis > beforeMillis ||
            report.startedAtEpochMillis == beforeMillis && report.runId >= beforeRunId) return
        eligible++
        rows.add(report)
        rows.sortWith(compareByDescending<RpcDeviceTestReport> { it.startedAtEpochMillis }.thenByDescending { it.runId })
        if (rows.size > 20) rows.removeAt(rows.lastIndex)
    }

    @Throws(Exception::class)
    public fun finish(): RpcTestArchivePage {
        check(!finished)
        finished = true
        val last = rows.lastOrNull()
        return RpcTestArchivePage(rows.toList(), eligible > rows.size,
            last?.startedAtEpochMillis ?: 0, last?.runId ?: "")
    }
}

/** One validated 64-KiB record at a time. A missing footer always means an incomplete export. */
public class RpcTestEvidenceWriter(recentOnly: Boolean, private val appendLine: (String) -> Unit) {
    private var count = 0
    private var finished = false
    private var failed = false

    init {
        appendLine("{\"format\":\"p2pkit-private-test-evidence\",\"schema\":1,\"recentOnly\":$recentOnly}")
    }

    @Throws(Exception::class)
    public fun append(runId: String, text: String) {
        check(!finished && !failed && count < 1_000_000)
        try {
            val report = readRpcTestEvidence(runId, text)
            // Re-encode to guarantee one JSON object per line even for older pretty-printed files.
            appendLine(Json.encodeToString(report))
            count++
        } catch (failure: Exception) {
            failed = true
            throw failure
        }
    }

    @Throws(Exception::class)
    public fun finish() {
        check(!finished && !failed)
        finished = true
        appendLine("{\"exportComplete\":true,\"records\":$count}")
    }
}
