package dev.p2pkit.sample.rpc.desktop

import dev.p2pkit.sample.rpc.DeviceTestCommand
import dev.p2pkit.sample.rpc.RpcDeviceTestPhase
import dev.p2pkit.sample.rpc.RpcDeviceTestReport
import dev.p2pkit.sample.rpc.RpcDeviceTestSession
import dev.p2pkit.sample.rpc.emptyDeviceTestReport
import dev.p2pkit.sample.rpc.lab.LabVault
import kotlinx.serialization.json.Json
import java.nio.file.Files
import java.nio.file.Path
import java.nio.file.attribute.PosixFilePermissions
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertTrue

class DesktopRpcTestArchiveTest {
    private fun report(index: Int) = emptyDeviceTestReport(
        DeviceTestCommand(index.toString(16).padStart(32, '0'), "a".repeat(40), RpcDeviceTestPhase.Large),
        "Failed", "SyntheticInterruptedRun").copy(clientPlatform = "Android", hostPlatform = "Mac (JVM)",
        startedAtEpochMillis = 1_793_510_000_000)

    @Test
    fun encryptedArchiveSurvivesReopenAndRecentHistoryEviction() = fixture { root ->
        val key = LabVault.randomKey()
        val vault = LabVault(root, key)
        val session = RpcDeviceTestSession()
        val archive = DesktopRpcTestArchive(vault)
        repeat(125) { index ->
            val result = report(index)
            session.save(result)
            archive.retain(session, result)
        }
        assertEquals(100, session.reports.size)
        assertTrue(session.unarchivedReports.isEmpty())
        vault.close()
        val reopened = LabVault(root, key)
        val recovered = mutableListOf<RpcDeviceTestReport>()
        DesktopRpcTestArchive(reopened).visitRecords { recovered += Json.decodeFromString<RpcDeviceTestReport>(it) }
        assertEquals((0 until 125).map(::report), recovered)
        reopened.close()
        key.fill(0)
    }

    @Test
    fun interruptedIndexAppendRecoversItsWrittenTailWithoutDuplicatingOrOverwritingResults() = fixture { root ->
        val vault = LabVault(root)
        val session = RpcDeviceTestSession()
        val archive = DesktopRpcTestArchive(vault)
        val first = report(1)
        session.save(first)
        archive.retain(session, first)
        // Simulate the durable record/page existing before count and registration publication.
        vault.replace("device-test-archive-count", "0".toByteArray())
        vault.delete("device-test-archive-slot-${first.runId}")
        archive.retain(session, first)
        archive.retain(session, first)
        val second = report(2)
        session.save(second)
        archive.retain(session, second)
        assertFailsWith<IllegalStateException> { archive.retain(session, first.copy(failureCode = "DifferentFailure")) }
        val recovered = mutableListOf<RpcDeviceTestReport>()
        archive.visitRecords { recovered += Json.decodeFromString<RpcDeviceTestReport>(it) }
        assertEquals(listOf(first, second), recovered)
        vault.close()
    }

    private fun fixture(block: (Path) -> Unit) {
        val root = Files.createTempDirectory("rpc-test-archive-", PosixFilePermissions.asFileAttribute(
            PosixFilePermissions.fromString("rwx------"))).toRealPath()
        try { block(root) } finally {
            Files.walk(root).use { paths -> paths.sorted(Comparator.reverseOrder()).forEach(Files::delete) }
        }
    }
}
