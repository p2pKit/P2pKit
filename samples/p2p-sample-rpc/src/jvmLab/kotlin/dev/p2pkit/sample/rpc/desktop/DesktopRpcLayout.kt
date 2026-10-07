package dev.p2pkit.sample.rpc.desktop

import java.awt.Component
import java.awt.Container
import java.awt.Dimension
import java.awt.FlowLayout
import java.awt.Rectangle
import javax.swing.BoxLayout
import javax.swing.JComponent
import javax.swing.JLabel
import javax.swing.JPanel
import javax.swing.Scrollable
import javax.swing.SwingConstants

/** One leading-aligned column, constrained to its viewport instead of a hidden horizontal dashboard. */
internal open class DesktopRpcColumn : JPanel(), Scrollable {
    init { layout = BoxLayout(this, BoxLayout.Y_AXIS) }

    override fun addImpl(component: Component, constraints: Any?, index: Int) {
        (component as? JComponent)?.let {
            it.alignmentX = Component.LEFT_ALIGNMENT
            it.minimumSize = Dimension(0, it.minimumSize.height)
        }
        super.addImpl(component, constraints, index)
    }

    override fun getMinimumSize(): Dimension = Dimension(0, super.getMinimumSize().height)
    override fun getPreferredScrollableViewportSize(): Dimension = Dimension(1000, 780)
    override fun getScrollableTracksViewportWidth(): Boolean = true
    override fun getScrollableTracksViewportHeight(): Boolean = false
    override fun getScrollableUnitIncrement(visible: Rectangle, orientation: Int, direction: Int): Int = 16
    override fun getScrollableBlockIncrement(visible: Rectangle, orientation: Int, direction: Int): Int =
        maxOf(16, (if (orientation == SwingConstants.VERTICAL) visible.height else visible.width) - 16)
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
