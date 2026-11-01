package dev.p2pkit.sample.rpc.desktop

import dev.p2pkit.sample.rpc.DeviceTestCommand
import dev.p2pkit.sample.rpc.RpcDeviceTestPhase
import dev.p2pkit.sample.rpc.RpcDeviceTestSession
import dev.p2pkit.sample.rpc.emptyDeviceTestReport
import dev.p2pkit.sample.rpc.lab.LabVault
import dev.p2pkit.sample.rpc.lab.LabVaultTestDirectory
import kotlinx.coroutines.test.runTest
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue

class DesktopRpcTestArchiveDeletionTest {
    private fun report(letter: Char) = emptyDeviceTestReport(
        DeviceTestCommand(letter.toString().repeat(32), "c".repeat(40), RpcDeviceTestPhase.Large),
        "Failed", "SyntheticFailure")

    @Test
    fun selectedDeletionSurvivesReopenAndAnOldRecentIndexCannotResurrectIt() = runTest {
        val files = LabVaultTestDirectory()
        val vault = LabVault(files, ByteArray(32) { 7 })
        val archive = DesktopRpcTestArchive(vault)
        val session = RpcDeviceTestSession()
        val first = report('a')
        val second = report('b')
        session.save(first)
        session.save(second)
        val oldIndex = session.exportJson()
        archive.retain(session, first)
        archive.retain(session, second)
        assertTrue(session.beginResultDeletion(first.runId))
        archive.delete(session, first)
        session.finishResultDeletion(first.runId, true)
        assertEquals(listOf(second), session.reports)
        vault.close()
        val reopenedVault = LabVault(files, ByteArray(32) { 7 })
        val reopenedArchive = DesktopRpcTestArchive(reopenedVault)
        val reopened = RpcDeviceTestSession()
        reopened.restoreJson(oldIndex)
        reopened.unarchivedReports.forEach { reopenedArchive.retain(reopened, it) }
        assertEquals(listOf(second), reopened.reports)
        val exported = mutableListOf<String>()
        reopenedArchive.visitRecords(exported::add)
        assertEquals(listOf(reopened.reportJson(second)), exported)
        reopenedVault.close()
    }

    @Test
    fun interruptedDeletionAfterTombstoneCannotExportOrRestoreTheOldRecord() {
        val files = LabVaultTestDirectory()
        val vault = LabVault(files, ByteArray(32) { 7 })
        val archive = DesktopRpcTestArchive(vault)
        val session = RpcDeviceTestSession()
        val first = report('a')
        session.save(first)
        archive.retain(session, first)
        val oldIndex = session.exportJson()
        vault.replace("device-test-deleted-${first.runId}", "1".toByteArray())
        val restored = RpcDeviceTestSession()
        restored.restoreJson(oldIndex)
        archive.retain(restored, restored.unarchivedReports.single())
        assertTrue(restored.reports.isEmpty())
        var exported = 0
        archive.visitRecords { exported++ }
        assertEquals(0, exported)
        vault.close()
    }
}
