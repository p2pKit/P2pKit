package dev.p2pkit.sample.rpc.desktop

import dev.p2pkit.sample.rpc.RpcRequestEntry
import dev.p2pkit.sample.rpc.RpcRequestHistory
import dev.p2pkit.sample.rpc.RpcRequestOutcome
import dev.p2pkit.sample.rpc.RpcRequestSide
import javax.swing.JButton
import javax.swing.JLabel
import javax.swing.JList
import javax.swing.JPanel
import javax.swing.JScrollPane
import javax.swing.SwingUtilities
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse

class DesktopRpcRequestHistoryTest {
    @Test
    fun historyUpdatesKeepExplicitSelectionWithoutPublishingPayloadInListLabels() {
        SwingUtilities.invokeAndWait {
            val history = RpcRequestHistory()
            val panel = DesktopRpcRequestHistory(history)
            @Suppress("UNCHECKED_CAST")
            val list = (panel.components.filterIsInstance<JScrollPane>().single().viewport.view)
                as JList<RpcRequestEntry>
            val first = history.begin(RpcRequestSide.Client, "users.get", 1, "private request")
            panel.render()
            assertEquals(-1, list.selectedIndex)
            list.selectedIndex = 0
            history.finish(first, RpcRequestOutcome.Succeeded, 2, "private response")
            history.begin(RpcRequestSide.Host, "items.list", 1, "another private request")
            panel.render()
            assertEquals(first, list.selectedValue.localId)
            assertEquals(RpcRequestOutcome.Succeeded, list.selectedValue.outcome)
            val label = list.cellRenderer.getListCellRendererComponent(list, list.selectedValue, 1, true, false)
                as JLabel
            assertFalse(label.text.contains("private"))
            assertEquals("users.get/v1 · Succeeded · 2 ms", label.text)
        }
    }

    @Test
    fun clearingCompletedKeepsActiveRowsAndDoesNotAutoSelectAnotherRequest() {
        SwingUtilities.invokeAndWait {
            val history = RpcRequestHistory()
            val panel = DesktopRpcRequestHistory(history)
            val completed = history.begin(RpcRequestSide.Client, "users.get", 1, "{}")
            history.finish(completed, RpcRequestOutcome.Succeeded, 0)
            val active = history.begin(RpcRequestSide.Host, "items.list", 1, "{}")
            panel.render()
            val list = panel.components.filterIsInstance<JScrollPane>().single().viewport.view as JList<*>
            list.selectedIndex = 1
            panel.components.filterIsInstance<JPanel>().single().components.filterIsInstance<JButton>()
                .single { it.text == "Clear completed history" }.doClick()
            assertEquals(1, list.model.size)
            assertEquals(active, (list.model.getElementAt(0) as RpcRequestEntry).localId)
            assertEquals(-1, list.selectedIndex)
        }
    }
}
