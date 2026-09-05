package dev.p2pkit.sample.desktop

import dev.p2pkit.sample.diagnostics.DiagnosticEventNames
import dev.p2pkit.sample.diagnostics.anonymizeIdentifier
import java.nio.file.Files
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertIs
import kotlin.test.assertNotEquals
import kotlin.test.assertNotNull

class CliDiagnosticConnectionTest {
    @Test
    fun lateStateNotificationsCannotRetireReplacementOrStealItsFirstTransfer() = withHarness {
        for (lateState in listOf("Closed", "Failed", "Connected", "Reconnecting")) {
            CliDiagnostics.startSession("PS-T05", "both", "test-$lateState")
            CliDiagnostics.registerConnection("old", "peer", "Connected")
            CliDiagnostics.fileHash("peer", "old-transfer", 1, "a".repeat(64), false, "old")
            CliDiagnostics.registerConnection("new", "peer", "Connected")
            val expected = assertNotNull(CliDiagnostics.connectionIdFor("peer"))

            repeat(2) { CliDiagnostics.connection("old", "peer", lateState, "Connected") }
            // No B transfer has been registered before A's late callback.
            CliDiagnostics.transfer("peer", "first-new-transfer", "new", DiagnosticEventNames.TRANSFER_STARTED)
            val current = CliDiagnostics.recorder.snapshot().last()
            assertEquals(expected, current.connectionId, lateState)
            assertEquals(anonymizeIdentifier("new"), current.sdkSessionId)
            assertEquals(expected, CliDiagnostics.connectionIdFor("peer"))

            CliDiagnostics.fileHash("peer", "old-transfer", 1, "a".repeat(64), true, "old")
            val old = CliDiagnostics.recorder.snapshot().last()
            assertEquals(expected, old.connectionId)
            assertEquals(anonymizeIdentifier("old"), old.sdkSessionId)
        }
    }

    @Test
    fun newDiagnosticSessionSnapshotRegistersOnlyLiveSdkOwners() = withHarness {
        CliDiagnostics.registerConnection("new", "peer", "Connected")
        val before = assertNotNull(CliDiagnostics.connectionIdFor("peer"))
        CliDiagnostics.startSession("PS-T05", "both", "next-test")
        // Same registrar used by the CLI's `diag start` snapshot loop.
        CliDiagnostics.registerConnection("new", "peer", "Connected")
        CliDiagnostics.registerConnection("old", "peer", "Closed")
        CliDiagnostics.connection("old", "peer", "Failed")
        val after = assertNotNull(CliDiagnostics.connectionIdFor("peer"))
        assertNotEquals(before, after)
        assertEquals(after, CliDiagnostics.transferConnectionId("peer", "new", "first-transfer"))
    }

    private fun withHarness(block: () -> Unit) {
        val home = Files.createTempDirectory("p2pkit-cli-diagnostic-state").toFile()
        try {
            val options = assertIs<CliParseResult.Success>(parseCliOptions(arrayOf("session=initial-test"))).options
            CliDiagnostics.configure(options, home)
            CliDiagnostics.localPeerId = "synthetic-local-peer"
            block()
        } finally {
            CliDiagnostics.close()
            CliDiagnostics.localPeerId = null
            home.deleteRecursively()
        }
    }
}
