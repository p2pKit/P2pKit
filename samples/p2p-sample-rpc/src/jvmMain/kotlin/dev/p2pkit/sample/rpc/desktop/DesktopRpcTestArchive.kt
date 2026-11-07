package dev.p2pkit.sample.rpc.desktop

import dev.p2pkit.sample.rpc.RpcDeviceTestReport
import dev.p2pkit.sample.rpc.RpcDeviceTestSession
import dev.p2pkit.sample.rpc.RpcTestArchivePage
import dev.p2pkit.sample.rpc.RpcTestArchiveScan
import dev.p2pkit.sample.rpc.RpcTestEvidenceWriter
import dev.p2pkit.sample.rpc.readRpcTestEvidence
import dev.p2pkit.sample.rpc.lab.LabVault
import kotlinx.serialization.json.Json

/** Encrypted paged index keeps older records discoverable without retaining all runs in memory. */
internal class DesktopRpcTestArchive(private val vault: LabVault) {
    private fun read(key: String): String? = vault.read(key)?.let { bytes ->
        try { bytes.decodeToString() } finally { bytes.fill(0) }
    }

    private fun write(key: String, text: String) {
        val bytes = text.toByteArray()
        try { vault.replace(key, bytes) } finally { bytes.fill(0) }
    }

    private fun count(): Int = read("device-test-archive-count")?.toInt()?.also {
        check(it in 0..1_000_000)
    } ?: 0

    private fun page(number: Int): List<String> = read("device-test-archive-page-$number")
        ?.let { Json.decodeFromString<List<String>>(it) }?.also { ids ->
            check(ids.size <= 100 && ids.distinct().size == ids.size &&
                ids.all { it.matches(Regex("[a-f0-9]{32}")) })
        }.orEmpty()

    private fun register(runId: String, slot: Int) {
        val bytes = slot.toString().toByteArray()
        val retained = vault.putIfAbsent("device-test-archive-slot-$runId", bytes)
        try { check(retained.contentEquals(bytes)) } finally { retained.fill(0); bytes.fill(0) }
    }

    fun retain(session: RpcDeviceTestSession, report: RpcDeviceTestReport) {
        if (read("device-test-deleted-${report.runId}") != null) {
            session.confirmArchived(report.runId)
            session.forgetDeletedResult(report.runId)
            return
        }
        val bytes = session.reportJson(report).toByteArray()
        check(bytes.size <= 65_536)
        val retained = vault.putIfAbsent("device-test-${report.runId}", bytes)
        try { session.hydrateArchived(report, retained.decodeToString()) }
        finally { retained.fill(0); bytes.fill(0) }
        val existing = read("device-test-archive-slot-${report.runId}")?.toInt()
        if (existing != null) {
            check(existing in 0 until 1_000_000 && page(existing / 100).getOrNull(existing % 100) == report.runId)
            check(count() >= existing)
            if (count() == existing) write("device-test-archive-count", (existing + 1).toString())
            session.confirmArchived(report.runId)
            return
        }
        var current = count()
        // Recover a fully written tail after interruption before publishing its count. Never remove it.
        while (true) {
            check(current < 1_000_000) { "Archive index full; prior runs retained" }
            val ids = page(current / 100)
            check(ids.size in (current % 100)..(current % 100 + 1))
            val tail = ids.getOrNull(current % 100) ?: break
            check(read("device-test-$tail") != null)
            register(tail, current)
            current++
            write("device-test-archive-count", current.toString())
            if (tail == report.runId) { session.confirmArchived(report.runId); return }
        }
        val ids = page(current / 100) + report.runId
        write("device-test-archive-page-${current / 100}", Json.encodeToString(ids))
        register(report.runId, current)
        write("device-test-archive-count", (current + 1).toString())
        session.confirmArchived(report.runId)
    }

    /** Exact selected output only. The durable tombstone prevents compact history from resurrecting it. */
    fun delete(session: RpcDeviceTestSession, report: RpcDeviceTestReport) {
        check(session.resultDeletionInProgress)
        val key = "device-test-${report.runId}"
        val old = read(key)
        if (old != null) check(session.archivedResultMatchesForDeletion(report, old))
        write("device-test-deleted-${report.runId}", "1")
        vault.delete(key)
        check(read(key) == null)
    }

    /** Caller streams each bounded record to its private export; no all-history allocation. */
    fun visitRecords(visit: (String) -> Unit) {
        val total = count()
        for (number in 0 until (total + 99) / 100) {
            val ids = page(number)
            check(ids.size == minOf(100, total - number * 100))
            ids.forEachIndexed { offset, it ->
                check(read("device-test-archive-slot-$it")?.toInt() == number * 100 + offset)
                if (read("device-test-deleted-$it") == null) {
                    val text = checkNotNull(read("device-test-$it"))
                    readRpcTestEvidence(it, text)
                    visit(text)
                }
            }
        }
    }

    fun browse(beforeMillis: Long = Long.MAX_VALUE, beforeRunId: String = ""): RpcTestArchivePage {
        val scan = RpcTestArchiveScan(beforeMillis, beforeRunId)
        visitRecords { text ->
            val report = Json.decodeFromString<RpcDeviceTestReport>(text)
            scan.accept(report.runId, text)
        }
        return scan.finish()
    }

    fun export(appendLine: (String) -> Unit, runId: String? = null) {
        val writer = RpcTestEvidenceWriter(false, appendLine)
        if (runId != null) {
            require(runId.matches(Regex("[a-f0-9]{32}")))
            check(read("device-test-deleted-$runId") == null)
            writer.append(runId, checkNotNull(read("device-test-$runId")))
        } else visitRecords { text ->
            val report = Json.decodeFromString<RpcDeviceTestReport>(text)
            writer.append(report.runId, text)
        }
        writer.finish()
    }
}
