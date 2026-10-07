package dev.p2pkit.sample.rpc.desktop

import dev.p2pkit.sample.rpc.RpcDiscoveryConnectionState
import dev.p2pkit.sample.rpc.RpcDiscoveryConnectionStatus
import dev.p2pkit.sample.rpc.RpcKnownDevice
import dev.p2pkit.sample.rpc.RpcNearbyHost
import java.awt.Component
import java.awt.Container
import javax.swing.JButton
import javax.swing.JComponent
import javax.swing.JList
import javax.swing.SwingUtilities
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertNull
import kotlin.test.assertTrue

class DesktopRpcDiscoveryPanelTest {
    private val pin = "p2f1-" + "a".repeat(52)
    private val host = RpcNearbyHost(pin, "Synthetic host", "JVM_DESKTOP", false)
    private val known = RpcKnownDevice(pin, "Known device", "Offline")
    private fun status(hosts: List<RpcNearbyHost> = listOf(host)) = DesktopRpcStatus(
        DesktopRpcRole.Client, "Disconnected", "local", 0, 0, 0, emptyList(), nearby = hosts, trusted = listOf(known),
    )
    private fun descendants(parent: Container): List<Component> = parent.components.flatMap {
        listOf(it) + if (it is Container) descendants(it) else emptyList()
    }

    @Test
    fun discoveryNeverSelectsAutomaticallyAndLossDisablesStaleActions() = SwingUtilities.invokeAndWait {
        val selected = mutableListOf<RpcNearbyHost>()
        val revoked = mutableListOf<RpcKnownDevice>()
        val panel = DesktopRpcDiscoveryPanel(selected::add, revoked::add)
        panel.render(status(), true)
        val lists = descendants(panel).filterIsInstance<JList<*>>()
        val buttons = descendants(panel).filterIsInstance<JButton>()
        assertEquals(-1, lists[0].selectedIndex)
        assertFalse(buttons[0].isEnabled)
        assertTrue(selected.isEmpty() && revoked.isEmpty())
        lists[0].selectedIndex = 0
        assertTrue(buttons[0].isEnabled)
        buttons[0].doClick()
        assertEquals(listOf(host), selected)
        panel.render(status().copy(connection = RpcDiscoveryConnectionStatus(
            RpcDiscoveryConnectionState.RequiresApproval, pin)), true)
        assertEquals("Request approval again", buttons[0].text)
        assertEquals(1, selected.size, "Rendering a renewal action must not request approval")
        panel.render(status(emptyList()), true)
        assertEquals(-1, lists[0].selectedIndex)
        assertFalse(buttons[0].isEnabled)
        buttons[0].doClick()
        assertEquals(1, selected.size)
        lists[1].selectedIndex = 0
        panel.render(status(emptyList()), false)
        assertFalse(buttons[1].isEnabled)
        buttons[1].doClick()
        assertTrue(revoked.isEmpty())
    }

    @Test
    fun selectionFollowsTheExactPinNotRowPositionAndAmbiguousIdentityClearsIt() = SwingUtilities.invokeAndWait {
        val panel = DesktopRpcDiscoveryPanel({}, {})
        panel.render(status(), true)
        val list = descendants(panel).filterIsInstance<JList<*>>()[0]
        list.selectedIndex = 0
        val other = host.copy(fingerprint = "p2f1-" + "b".repeat(51) + "a")
        panel.render(status(listOf(other, host)), true)
        assertEquals(1, list.selectedIndex)
        panel.render(status(listOf(host, host.copy(name = "Conflicting record"))), true)
        assertEquals(-1, list.selectedIndex)
    }

    @Test
    @Suppress("UNCHECKED_CAST")
    fun untrustedNamesAreRenderedAsPlainTextNotSwingHtml() = SwingUtilities.invokeAndWait {
        val panel = DesktopRpcDiscoveryPanel({}, {})
        val untrusted = host.copy(name = "<html><b>Not markup</b>")
        panel.render(status(listOf(untrusted)), true)
        val list = descendants(panel).filterIsInstance<JList<*>>()[0] as JList<RpcNearbyHost>
        val rendered = list.cellRenderer.getListCellRendererComponent(list, untrusted, 0, false, false) as JComponent
        assertEquals(true, rendered.getClientProperty("html.disable"))
        assertNull(rendered.getClientProperty("html"))
    }
}
