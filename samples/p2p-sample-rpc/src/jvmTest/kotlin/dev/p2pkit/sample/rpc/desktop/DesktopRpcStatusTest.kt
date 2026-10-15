package dev.p2pkit.sample.rpc.desktop

import javax.swing.JLabel
import javax.swing.JPanel
import javax.swing.SwingUtilities
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertFalse
import kotlin.test.assertTrue

class DesktopRpcStatusTest {
    @Test
    fun pendingUpdatesPreserveOnlyTheExactExplicitSelectionWithoutSelectingNewPeers() {
        val first = DesktopRpcPending("first", "first full fingerprint")
        val second = DesktopRpcPending("second", "second full fingerprint")
        assertEquals(-1, desktopRpcPendingSelection(null, listOf(first, second)))
        assertEquals(1, desktopRpcPendingSelection(first, listOf(second, first.copy())))
        assertEquals(-1, desktopRpcPendingSelection(first, listOf(second)))
        assertEquals(-1, desktopRpcPendingSelection(first, listOf(first.copy(fingerprint = "replacement"))))
    }

    @Test
    fun approvalRequiresAReadyHostAndAnExactCurrentlyObservedRequest() {
        val request = DesktopRpcPending("request", "full fingerprint")
        val status = DesktopRpcStatus(DesktopRpcRole.Host, "Running", "host", 0, 0, 0, listOf(request))
        val snapshot = DesktopRpcRunOwner.Snapshot(DesktopRpcRunOwner.Stage.Ready, "Host", null, status)
        assertTrue(desktopRpcCanApprove(snapshot, request.copy()))
        assertFalse(desktopRpcCanApprove(snapshot, null))
        assertFalse(desktopRpcCanApprove(snapshot, request.copy(fingerprint = "different")))
        assertFalse(desktopRpcCanApprove(snapshot.copy(role = "Client"), request))
        assertFalse(desktopRpcCanApprove(snapshot.copy(stage = DesktopRpcRunOwner.Stage.Working), request))
        assertFalse(desktopRpcCanApprove(snapshot.copy(stage = DesktopRpcRunOwner.Stage.Stopping), request))
        assertFalse(desktopRpcCanApprove(snapshot.copy(status = null, statusUnavailable = true), request))
        assertFalse(desktopRpcCanApprove(snapshot.copy(status = status.copy(state = "Failed")), request))
        assertFalse(desktopRpcCanApprove(snapshot.copy(status = status.copy(pending = emptyList())), request))
    }

    @Test
    fun cardsShowFourDistinctLiveCountsWithoutInventingZerosOrRewritingEqualValues() {
        // Headless Swing component checks only: no JFrame, peer, native GUI, or LAN readiness claim.
        SwingUtilities.invokeAndWait {
            val cards = DesktopRpcStatusCards()
            val panels = cards.components.map { it as JPanel }
            val titles = panels.map { it.getComponent(0) as JLabel }
            val values = panels.map { it.getComponent(1) as JLabel }
            assertEquals(listOf("Clients", "Pending", "Completed", "Queued"), titles.map { it.text })
            assertEquals(4, panels.map { it.background }.toSet().size)
            assertEquals(List(4) { "—" }, values.map { it.text })
            var writes = 0
            values.forEach { value -> value.addPropertyChangeListener("text") { writes++ } }
            val status = DesktopRpcStatus(DesktopRpcRole.Host, "Running", "host", 3, Long.MAX_VALUE, 7,
                listOf(DesktopRpcPending("one", "first"), DesktopRpcPending("two", "second")))
            cards.render(status)
            assertEquals(listOf("3", "2", Long.MAX_VALUE.toString(), "7"), values.map { it.text })
            assertEquals("Completed: ${Long.MAX_VALUE}", values[2].accessibleContext.accessibleName)
            assertEquals(4, writes)
            cards.render(status.copy(pending = status.pending.map { it.copy() }))
            assertEquals(4, writes)
            cards.render(null)
            assertEquals(List(4) { "—" }, values.map { it.text })
            assertEquals("Clients: unavailable", values[0].accessibleContext.accessibleName)
        }
    }

    @Test
    fun clientCardsShowConnectionStateInsteadOfInventingHostClientOrPendingCounts() {
        SwingUtilities.invokeAndWait {
            val cards = DesktopRpcStatusCards()
            val panels = cards.components.map { it as JPanel }
            val titles = panels.map { it.getComponent(0) as JLabel }
            val values = panels.map { it.getComponent(1) as JLabel }
            val status = DesktopRpcStatus(DesktopRpcRole.Client, "Ready", "client", 0, 2, 1, emptyList())
            cards.render(status)
            assertEquals(listOf("Connected host", "Connection", "Completed", "Queued"), titles.map { it.text })
            assertEquals(listOf("1", "Ready", "2", "1"), values.map { it.text })
            cards.render(status.copy(state = "Disconnected"))
            assertEquals(listOf("0", "Disconnected", "2", "1"), values.map { it.text })
            cards.render(null, DesktopRpcRole.Client)
            assertEquals("Connected host", titles[0].text)
            assertEquals(List(4) { "—" }, values.map { it.text })
            assertEquals("Connected host: unavailable", values[0].accessibleContext.accessibleName)
        }
    }

    @Test
    fun snapshotsRejectNegativeCountsUnknownStateAndHostFieldsInAClientRole() {
        val host = DesktopRpcStatus(DesktopRpcRole.Host, "Running", "host", 0, 0, 0, emptyList())
        assertFailsWith<IllegalArgumentException> { host.copy(clients = -1) }
        assertFailsWith<IllegalArgumentException> { host.copy(completed = -1) }
        assertFailsWith<IllegalArgumentException> { host.copy(queued = -1) }
        assertFailsWith<IllegalArgumentException> { host.copy(state = "unrecognized state") }
        assertFailsWith<IllegalArgumentException> { host.copy(state = "Negotiating") }
        val client = host.copy(role = DesktopRpcRole.Client, state = "Ready")
        assertFailsWith<IllegalArgumentException> { client.copy(state = "Running") }
        assertFailsWith<IllegalArgumentException> { client.copy(clients = 1) }
        assertFailsWith<IllegalArgumentException> {
            client.copy(pending = listOf(DesktopRpcPending("request", "fingerprint")))
        }
    }
}
