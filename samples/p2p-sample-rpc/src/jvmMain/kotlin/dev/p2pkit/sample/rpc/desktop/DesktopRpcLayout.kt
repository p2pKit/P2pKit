package dev.p2pkit.sample.rpc.desktop

import java.awt.Component
import java.awt.Container
import java.awt.Dimension
import java.awt.FlowLayout
import java.awt.LayoutManager
import java.awt.Rectangle
import javax.swing.JButton
import javax.swing.JComponent
import javax.swing.JLabel
import javax.swing.JPanel
import javax.swing.Scrollable
import javax.swing.SwingConstants
import javax.swing.plaf.basic.BasicHTML
import javax.swing.text.View
import kotlin.math.ceil

/** One leading-aligned column, constrained to its viewport instead of a hidden horizontal dashboard. */
internal open class DesktopRpcColumn : JPanel(), Scrollable {
    init { layout = DesktopRpcColumnLayout() }

    override fun getMinimumSize(): Dimension = Dimension(0, super.getMinimumSize().height)
    override fun getPreferredScrollableViewportSize(): Dimension = Dimension(1000, 780)
    override fun getScrollableTracksViewportWidth(): Boolean = true
    override fun getScrollableTracksViewportHeight(): Boolean = false
    override fun getScrollableUnitIncrement(visible: Rectangle, orientation: Int, direction: Int): Int = 16
    override fun getScrollableBlockIncrement(visible: Rectangle, orientation: Int, direction: Int): Int =
        maxOf(16, (if (orientation == SwingConstants.VERTICAL) visible.height else visible.width) - 16)
}

/** Measure at the assigned width before laying out; cached BoxLayout heights cannot describe wrapped rows. */
private class DesktopRpcColumnLayout : LayoutManager {
    override fun addLayoutComponent(name: String?, component: Component) = Unit
    override fun removeLayoutComponent(component: Component) = Unit
    override fun minimumLayoutSize(target: Container): Dimension = preferredLayoutSize(target).also { it.width = 0 }
    override fun preferredLayoutSize(target: Container): Dimension = measure(target, place = false)
    override fun layoutContainer(target: Container) { measure(target, place = true) }

    private fun measure(target: Container, place: Boolean): Dimension = synchronized(target.treeLock) {
        val insets = target.insets
        val width = (if (target.width > 0) target.width else 1000) - insets.left - insets.right
        val available = maxOf(1, width)
        var y = insets.top
        target.components.filter { it.isVisible }.forEach { child ->
            // Flow rows and nested columns compute their preferred height from this current width.
            child.setSize(available, child.height)
            val html = (child as? JComponent)?.getClientProperty(BasicHTML.propertyKey) as? View
            val height = if (child is JLabel && html != null) {
                val border = child.insets
                html.setSize(maxOf(1, available - border.left - border.right).toFloat(), 0f)
                ceil(html.getPreferredSpan(View.Y_AXIS).toDouble()).toInt() + border.top + border.bottom
            } else child.preferredSize.height
            if (place) child.setBounds(insets.left, y, available, height)
            y += height
        }
        Dimension(available + insets.left + insets.right, y + insets.bottom)
    }
}

/** FlowLayout wraps controls but normally reports only one row's height. Account for the actual available width. */
internal class DesktopRpcWrapLayout : FlowLayout(LEADING) {
    override fun preferredLayoutSize(target: Container): Dimension = measure(target)
    override fun minimumLayoutSize(target: Container): Dimension = measure(target).also { it.width = 0 }

    private fun measure(target: Container): Dimension = synchronized(target.treeLock) {
        var owner: Container? = target
        while (owner != null && owner.width == 0) owner = owner.parent
        val insets = target.insets
        val available = maxOf(1, (owner?.width ?: 1000) - insets.left - insets.right - hgap * 2)
        var width = 0
        var height = 0
        var rowWidth = 0
        var rowHeight = 0
        fun finishRow() {
            width = maxOf(width, rowWidth)
            if (rowHeight > 0) {
                if (height > 0) height += vgap
                height += rowHeight
            }
            rowWidth = 0
            rowHeight = 0
        }
        target.components.filter { it.isVisible }.forEach { child ->
            val size = child.preferredSize
            if (rowWidth > 0 && rowWidth + hgap + size.width > available) finishRow()
            if (rowWidth > 0) rowWidth += hgap
            rowWidth += size.width
            rowHeight = maxOf(rowHeight, size.height)
        }
        finishRow()
        Dimension(
            width + insets.left + insets.right + hgap * 2,
            height + insets.top + insets.bottom + vgap * 2,
        )
    }
}

/** Escaped plain text rendered with wrapping; repeated live snapshots do not reparse the same HTML. */
internal class DesktopRpcWrappedLabel(initial: String = "") : JLabel() {
    private var plain: String? = null
    init { show(initial) }
    fun show(value: String) {
        if (plain == value) return
        plain = value
        text = "<html>" + value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace("\n", "<br>")
        // JLabel lazily creates this context; the inherited protected field can still be null.
        getAccessibleContext().accessibleName = value
    }
}

/** Keep content instances and edits alive when folded; never restart observers or role ownership. */
internal class DesktopRpcDisclosure(title: String, content: JComponent) : DesktopRpcColumn() {
    private val toggle = JButton(title)
    var expanded: Boolean = false
        private set

    init {
        content.isVisible = false
        add(toggle)
        add(content)
        toggle.getAccessibleContext().accessibleDescription = "Collapsed; activate to show details"
        toggle.addActionListener {
            expanded = !expanded
            content.isVisible = expanded
            toggle.text = if (expanded) "Hide $title" else title
            toggle.getAccessibleContext().accessibleDescription = if (expanded)
                "Expanded; activate to hide details" else "Collapsed; activate to show details"
            revalidate()
            repaint()
        }
    }
}
