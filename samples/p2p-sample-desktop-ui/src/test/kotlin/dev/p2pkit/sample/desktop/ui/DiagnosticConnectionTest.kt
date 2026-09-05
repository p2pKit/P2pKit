package dev.p2pkit.sample.desktop.ui

import dev.p2pkit.sample.diagnostics.DiagnosticEventNames
import dev.p2pkit.sample.diagnostics.anonymizeIdentifier
import java.nio.file.Files
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertNotEquals
import kotlin.test.assertNotNull
import kotlin.test.assertTrue

class DiagnosticConnectionTest {
    @Test
    fun lateStateNotificationsCannotRetireReplacementOrStealItsFirstTransfer() = withHarness { harness ->
        for (lateState in listOf("Closed", "Failed", "Connected", "Reconnecting")) {
            harness.startSession("PS-T06", "both", "test-$lateState")
            harness.registerConnection("old", "peer", "Connected")
            harness.hash("peer", "old-transfer", 1, "a".repeat(64), false, "old")
            harness.registerConnection("new", "peer", "Connected")
            val expected = assertNotNull(harness.connectionIdFor("peer"))

            repeat(2) { harness.connection("old", "peer", lateState, "Connected") }
            harness.transfer("peer", "first-new-transfer", "new", DiagnosticEventNames.TRANSFER_STARTED)
            val current = harness.recorder.snapshot().last()
            assertEquals(expected, current.connectionId, lateState)
            assertEquals(anonymizeIdentifier("new"), current.sdkSessionId)
            assertEquals(expected, harness.connectionIdFor("peer"))

            harness.hash("peer", "old-transfer", 1, "a".repeat(64), true, "old")
            val old = harness.recorder.snapshot().last()
            assertEquals(expected, old.connectionId)
            assertEquals(anonymizeIdentifier("old"), old.sdkSessionId)
        }
    }

    @Test
    fun newDiagnosticSessionSnapshotRegistersOnlyLiveSdkOwners() = withHarness { harness ->
        harness.registerConnection("new", "peer", "Connected")
        val before = assertNotNull(harness.connectionIdFor("peer"))
        harness.startSession("PS-T06", "both", "next-test") {
            listOf(
                DesktopDiagnosticConnectionSnapshot("new", "peer", "Connected"),
                DesktopDiagnosticConnectionSnapshot("old", "peer", "Closed")
            )
        }
        harness.connection("old", "peer", "Failed")
        val after = assertNotNull(harness.connectionIdFor("peer"))
        assertNotEquals(before, after)
        assertEquals(after, harness.transferConnectionId("peer", "new", "first-transfer"))
        assertTrue(harness.recorder.snapshot().any {
            it.sdkSessionId == anonymizeIdentifier("new") && it.details["sessionSnapshot"] == "true"
        })
    }

    @Test
    fun beginTestSamplesOwnersAtClickRatherThanWhenTheUiWasComposed() = withHarness { harness ->
        var live = DesktopDiagnosticConnectionSnapshot("old", "peer", "Connected")
        harness.registerConnection(live.sessionId, live.peerId, live.state)
        // The UI keeps a provider, not an eagerly captured list or state string.
        val fromComposition = { listOf(live) }
        live = DesktopDiagnosticConnectionSnapshot("new", "peer", "Connected")
        harness.registerConnection(live.sessionId, live.peerId, live.state)

        harness.startSession("PS-T06", "both", "clicked-test", fromComposition)
        harness.connection("old", "peer", "Closed")
        val expected = assertNotNull(harness.connectionIdFor("peer"))
        harness.transfer("peer", "first-after-click", "new", DiagnosticEventNames.TRANSFER_STARTED)
        val transfer = harness.recorder.snapshot().last()
        assertEquals(expected, transfer.connectionId)
        assertEquals(anonymizeIdentifier("new"), transfer.sdkSessionId)
        assertTrue(harness.recorder.snapshot().any {
            it.sdkSessionId == anonymizeIdentifier("new") && it.details["sessionSnapshot"] == "true"
        })
    }

    private fun withHarness(block: (DesktopDiagnosticHarness) -> Unit) {
        val home = Files.createTempDirectory("p2pkit-desktop-diagnostic-state").toFile()
        val harness = DesktopDiagnosticHarness(home) {}
        try {
            harness.localPeerId = "synthetic-local-peer"
            block(harness)
        } finally {
            harness.shutdown()
            home.deleteRecursively()
        }
    }
}
