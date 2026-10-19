package dev.p2pkit.sample.desktop.ui

import dev.p2pkit.core.BuildInfo
import dev.p2pkit.core.PeerFingerprint
import dev.p2pkit.sample.rpc.desktop.RpcDesktopPanel
import dev.p2pkit.sample.rpc.desktop.RpcDesktopWindowsProfileControl
import java.awt.Component
import java.awt.Container
import java.awt.Window
import java.awt.event.WindowEvent
import java.util.Collections
import java.util.IdentityHashMap
import java.util.concurrent.FutureTask
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicBoolean
import javax.accessibility.Accessible
import javax.accessibility.AccessibleContext
import javax.accessibility.AccessibleRole
import javax.accessibility.AccessibleState
import javax.swing.JButton
import javax.swing.JDialog
import javax.swing.JLabel
import javax.swing.JPasswordField
import javax.swing.JTextField
import javax.swing.SwingUtilities

/**
 * Explicit disposable installed UI control. Drives actual controls in the canonical application window;
 * never constructs a replacement panel, injects a provider, approves a peer or changes network selection.
 * The external original-process supervisor must still observe terminal exit and all descendants.
 */
internal class WindowsInstalledUiControl private constructor() {
    private val started = AtomicBoolean()
    private val active = AtomicBoolean(true)
    private val end = System.nanoTime() + TimeUnit.SECONDS.toNanos(10)
    @Volatile private var stage = "WINDOW"
    @Volatile private var window: Window? = null
    private var worker: Thread? = null

    fun start(actualWindow: Window) {
        check(SwingUtilities.isEventDispatchThread())
        check(started.compareAndSet(false, true))
        window = actualWindow
        worker = Thread({
            try {
                await { actualWindow.isShowing && actualWindow.isActive }
                stage = "NAVIGATION"
                val entry = awaitValue { accessibleButton(actualWindow, "RPC") }
                later {
                    check(actualWindow.isShowing && actualWindow.isActive)
                    check(entry.accessibleStateSet.contains(AccessibleState.SHOWING) &&
                        entry.accessibleStateSet.contains(AccessibleState.ENABLED))
                    check(entry.accessibleAction.doAccessibleAction(0))
                }
                val panel = awaitValue { components(actualWindow).filterIsInstance<RpcDesktopPanel>()
                    .singleOrNull()?.takeIf { it.isShowing } }
                stage = "UNLOCK"
                click(panel, "Start host")
                val dialog = awaitValue {
                    actualWindow.ownedWindows.filterIsInstance<JDialog>()
                        .filter { it.isShowing && it.title == "RPC profile" }.singleOrNull()
                }
                edt {
                    val input = components(dialog).filterIsInstance<JPasswordField>().single {
                        it.accessibleContext.accessibleName ==
                            "RPC profile passphrase; not your computer login password"
                    }
                    input.text = "P2pKit installed synthetic control v1"
                }
                click(dialog, "Unlock profile")
                stage = "HOST_START"
                await { hasText(panel, "Host: Ready") && hasText(panel,
                    "Live Host: Running — updates automatically every 500 ms.") }
                val identity = edt { fingerprint(panel) }
                stage = "HOST_STOP"
                click(panel, "Stop")
                await { hasText(panel, "No role: Stopped") }
                stage = "HOST_RESTART"
                click(panel, "Start host")
                await { hasText(panel, "Host: Ready") && hasText(panel,
                    "Live Host: Running — updates automatically every 500 ms.") }
                edt { check(fingerprint(panel) == identity) }
                stage = "BACK"
                click(panel, "Back to samples")
                await { !panel.isShowing && accessibleButton(actualWindow, "RPC") != null }
                // This is provisional UI evidence. Normal terminal cleanup and independently observed
                // process exit remain mandatory; a printed line cannot qualify retirement.
                stage = "TERMINAL_REQUEST"
                checkTime()
                println("{\"source\":\"${BuildInfo.COMMIT}\",\"ui\":{\"schema\":1," +
                    "\"scope\":\"INSTALLED_UI_HOST_CYCLE_NOT_PEER_OR_FULL_QUALIFICATION\"," +
                    "\"navigation\":\"VERIFIED\",\"unlock\":\"ADMITTED\",\"hostStarts\":2," +
                    "\"identityAcrossStop\":\"UNCHANGED\",\"back\":\"ACKNOWLEDGED\"," +
                    "\"terminalClose\":\"REQUESTED\",\"peerOperations\":\"NOT_ENTERED\"}}")
            } catch (_: Throwable) {
                System.err.println("WINDOWS_INSTALLED_UI_CONTROL_FAILED stage=$stage")
            } finally {
                active.set(false)
                // Use the real application's original close listener and terminal owner. A blocked EDT
                // or failed retirement remains nonpassing under the outer watchdog; never force exit0.
                SwingUtilities.invokeLater {
                    actualWindow.dispatchEvent(WindowEvent(actualWindow, WindowEvent.WINDOW_CLOSING))
                }
            }
        }, "p2pkit-installed-ui-control").apply { isDaemon = true; start() }
    }

    private fun checkTime() { check(active.get() && System.nanoTime() < end) }

    private fun <T> edt(action: () -> T): T {
        checkTime()
        val task = FutureTask { checkTime(); action() }
        SwingUtilities.invokeLater(task)
        return try { task.get(maxOf(1, end - System.nanoTime()), TimeUnit.NANOSECONDS).also { checkTime() } }
        finally { task.cancel(false) } // Never interrupt the EDT or discard an already running owner.
    }

    private fun later(action: () -> Unit) {
        checkTime()
        SwingUtilities.invokeLater {
            if (active.get() && System.nanoTime() < end) {
                try { action() } catch (_: Throwable) { active.set(false) }
            }
        }
    }

    private fun await(condition: () -> Boolean) { awaitValue { Unit.takeIf { condition() } } }

    private fun <T : Any> awaitValue(observe: () -> T?): T {
        while (true) {
            edt(observe)?.let { return it }
            Thread.sleep(20)
        }
    }

    private fun click(parent: Container, label: String) {
        val button = awaitValue { components(parent).filterIsInstance<JButton>()
            .filter { it.text == label && it.isShowing && it.isEnabled }.singleOrNull() }
        later {
            check(parent.isShowing && button.isShowing && button.isEnabled)
            check(SwingUtilities.isDescendingFrom(button, parent))
            val host = SwingUtilities.getWindowAncestor(button)
            check(host != null && host.isActive && (host === window || host.owner === window))
            button.doClick(0)
        }
    }

    private fun hasText(parent: Container, value: String): Boolean =
        components(parent).filterIsInstance<JLabel>().any { it.text == value }

    private fun fingerprint(parent: Container): String = components(parent).filterIsInstance<JTextField>()
        .filter { !it.isEditable && PeerFingerprint.parseOrNull(it.text) != null }.single().text

    companion object {
        fun prepare(): WindowsInstalledUiControl {
            // Admits the original installed provider and this fixed synthetic encrypted fixture.
            // An absent/unrelated/ambiguous profile refuses; this never creates or resets a fixture.
            val readback = RpcDesktopWindowsProfileControl.reopen()
            check(BuildInfo.COMMIT.matches(Regex("[0-9a-f]{40}")))
            check(readback.startsWith("{\"source\":\"${BuildInfo.COMMIT}\","))
            return WindowsInstalledUiControl()
        }

        private fun components(root: Container): List<Component> {
            check(SwingUtilities.isEventDispatchThread())
            val result = mutableListOf<Component>()
            fun visit(component: Component, depth: Int) {
                check(depth <= 32 && result.size < 2048)
                result.add(component)
                if (component is Container) component.components.forEach { visit(it, depth + 1) }
            }
            visit(root, 0)
            return result
        }

        private fun accessibleButton(root: Accessible, name: String): AccessibleContext? {
            check(SwingUtilities.isEventDispatchThread())
            val visited = Collections.newSetFromMap(IdentityHashMap<AccessibleContext, Boolean>())
            val matches = mutableListOf<AccessibleContext>()
            fun visit(node: AccessibleContext, depth: Int) {
                check(depth <= 32 && visited.size < 2048 && visited.add(node))
                if (node.accessibleName == name && node.accessibleRole == AccessibleRole.PUSH_BUTTON &&
                    node.accessibleStateSet.contains(AccessibleState.SHOWING) &&
                    node.accessibleStateSet.contains(AccessibleState.ENABLED)) matches.add(node)
                val count = node.accessibleChildrenCount
                check(count in 0..2048)
                repeat(count) { visit(checkNotNull(node.getAccessibleChild(it)?.accessibleContext), depth + 1) }
            }
            visit(root.accessibleContext, 0)
            check(matches.size <= 1)
            return matches.singleOrNull()?.also { check(it.accessibleAction?.accessibleActionCount == 1) }
        }
    }
}
