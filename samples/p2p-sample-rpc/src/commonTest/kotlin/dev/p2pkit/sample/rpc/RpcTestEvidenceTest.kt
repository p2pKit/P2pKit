package dev.p2pkit.sample.rpc

import kotlinx.serialization.json.Json
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertFalse
import kotlin.test.assertTrue

class RpcTestEvidenceTest {
    private fun records(): List<RpcDeviceTestReport> {
        val session = RpcDeviceTestSession()
        session.physicalTests.start("core-files", "a".repeat(40), "Android")
        session.physicalTests.finish("Interrupted", "", "Stopped")
        return (1..51).map { number -> session.reports.last().copy(
            runId = number.toString(16).padStart(32, '0'), startedAtEpochMillis = 1_000,
            endedAtEpochMillis = 1_001,
        ) }
    }

    @Test fun pagesAreBoundedDeterministicAndDoNotSkipRunsWithTheSameTimestamp() {
        val original = records()
        val recovered = mutableListOf<RpcDeviceTestReport>()
        var scan = RpcTestArchiveScan()
        while (true) {
            original.reversed().forEach { scan.accept(it.runId, Json.encodeToString(it)) }
            val page = scan.finish()
            assertTrue(page.reports.size <= 20)
            recovered.addAll(page.reports)
            if (!page.olderAvailable) break
            scan = RpcTestArchiveScan(page.beforeMillis, page.beforeRunId)
        }
        assertEquals(original.reversed(), recovered)
        assertEquals(51, recovered.map { it.runId }.distinct().size)
        assertFalse(RpcTestArchiveScan().finish().olderAvailable)
    }

    @Test fun corruptMismatchedOversizedAndForgedRecordsRefuseWithoutPublishingAPage() {
        val report = records().first()
        assertFailsWith<IllegalArgumentException> { readRpcTestEvidence("b".repeat(32), Json.encodeToString(report)) }
        assertFailsWith<IllegalArgumentException> { readRpcTestEvidence(report.runId, " ".repeat(65_537)) }
        assertFailsWith<IllegalArgumentException> {
            readRpcTestEvidence(report.runId, Json.encodeToString(report.copy(correctResponses = 1)))
        }
        assertFailsWith<IllegalArgumentException> { RpcTestArchiveScan(1, "../escape") }
    }

    @Test fun fullExportIsRecordAtATimeAndHasNoFooterAfterAWriteFailure() {
        val lines = mutableListOf<String>()
        val writer = RpcTestEvidenceWriter(false, lines::add)
        records().forEach { writer.append(it.runId, Json.encodeToString(it)) }
        writer.finish()
        assertTrue(lines.first().contains("\"recentOnly\":false"))
        assertEquals("{\"exportComplete\":true,\"records\":51}", lines.last())
        assertFailsWith<IllegalStateException> { writer.finish() }
        val failing = RpcTestEvidenceWriter(false) { if (it.contains("runId")) error("Provider failed") }
        val report = records().first()
        assertFailsWith<IllegalStateException> { failing.append(report.runId, Json.encodeToString(report)) }
        assertFailsWith<IllegalStateException> { failing.finish() }
    }
}
