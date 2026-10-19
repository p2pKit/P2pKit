package dev.p2pkit.sample.rpc.desktop

import dev.p2pkit.sample.rpc.RpcApplicationSession
import java.awt.Component
import java.awt.Container
import java.awt.Window
import java.awt.event.ActionEvent
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit
import javax.swing.JButton
import javax.swing.SwingUtilities
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertNull
import kotlin.test.assertTrue

class RpcDesktopPanelTest {
    @Test fun embeddedWorkspaceUsesHostBackPolicyWithoutCreatingAWindowOrStartingARole() {
        val windows = Window.getWindows().toSet()
        var backRequests = 0
        lateinit var panel: RpcDesktopPanel
        val closed = CountDownLatch(1)
        var result: DesktopRpcCloseResult? = null
        SwingUtilities.invokeAndWait {
            panel = RpcDesktopPanel(RpcApplicationSession()) { backRequests++ }
            assertNull(SwingUtilities.getWindowAncestor(panel))
            assertEquals("RPC application section", panel.getAccessibleContext().accessibleName)
            val buttons = descendants(panel).filterIsInstance<JButton>().toList()
            for (label in listOf("Start host", "Create client", "users.get", "items.list", "message.send")) {
                assertEquals(1, buttons.count { it.text == label }, label)
            }
            assertTrue(buttons.filter { it.text in setOf("users.get", "items.list", "message.send") }
                .none { it.isEnabled })
            buttons.single { it.text == "Back to samples" }.doClick()
            panel.actionMap.get("rpc.back").actionPerformed(ActionEvent(panel, 0, "rpc.back"))
            assertEquals(2, backRequests)
            assertEquals(windows, Window.getWindows().toSet())
            panel.requestClose { result = it; closed.countDown() }
        }
        assertTrue(closed.await(5, TimeUnit.SECONDS), "Idle section close must finish without a UI-thread wait")
        assertEquals(DesktopRpcCloseResult.Closed, result)
        SwingUtilities.invokeAndWait {
            assertEquals(0, panel.componentCount)
            panel.requestBack()
            assertEquals(2, backRequests, "A retired panel cannot navigate a replacement section")
            panel.requestClose { assertEquals(DesktopRpcCloseResult.Closed, it) }
        }
        assertEquals(windows, Window.getWindows().toSet())
    }

    @Test fun finalExitConcealsThePanelAndSubscribesToAnAlreadyOwnedBackClose() {
        val completed = CountDownLatch(2)
        val outcomes = mutableListOf<DesktopRpcCloseResult>()
        var backRequests = 0
        lateinit var panel: RpcDesktopPanel
        SwingUtilities.invokeAndWait {
            panel = RpcDesktopPanel(RpcApplicationSession()) { backRequests++ }
            val roles = descendants(panel).filterIsInstance<JButton>()
                .filter { it.text in setOf("Start host", "Create client") }.toList()
            panel.requestClose { outcomes += it; completed.countDown() }
            panel.requestTerminalClose { outcomes += it; completed.countDown() }
            panel.requestTerminalClose { assertEquals(DesktopRpcCloseResult.Busy, it) }
            panel.requestBack()
            assertEquals(0, backRequests)
            assertTrue(roles.none { it.isEnabled })
        }
        assertTrue(completed.await(5, TimeUnit.SECONDS), "Both callers must observe the same completed close")
        SwingUtilities.invokeAndWait {
            assertEquals(List(2) { DesktopRpcCloseResult.Closed }, outcomes)
            assertEquals(0, panel.componentCount)
            panel.requestTerminalClose { assertEquals(DesktopRpcCloseResult.Closed, it) }
        }
    }

    private fun descendants(component: Component): Sequence<Component> = sequence {
        yield(component)
        if (component is Container) component.components.forEach { yieldAll(descendants(it)) }
    }
}
