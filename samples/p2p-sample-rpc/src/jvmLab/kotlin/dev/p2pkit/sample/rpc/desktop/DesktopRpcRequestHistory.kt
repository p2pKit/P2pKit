package dev.p2pkit.sample.rpc.desktop

import dev.p2pkit.sample.rpc.RpcRequestEntry
import dev.p2pkit.sample.rpc.RpcRequestHistory
import java.awt.BorderLayout
import java.awt.Component
import java.awt.Dimension
import java.awt.Toolkit
import java.awt.datatransfer.StringSelection
import javax.swing.DefaultListCellRenderer
import javax.swing.DefaultListModel
import javax.swing.JButton
import javax.swing.JLabel
import javax.swing.JList
import javax.swing.JOptionPane
import javax.swing.JPanel
import javax.swing.JScrollPane
import javax.swing.JTextArea
import javax.swing.ListSelectionModel

/** Bounded application data panel. Opening/copying data is explicit and separate from safe diagnostics. */
internal class DesktopRpcRequestHistory(private val history: RpcRequestHistory) : JPanel(BorderLayout()) {
    private val model = DefaultListModel<RpcRequestEntry>()
    private val entries = JList(model).apply {
        visibleRowCount = 4
        selectionMode = ListSelectionModel.SINGLE_SELECTION
        accessibleContext.accessibleName = "Application request history; select a request to inspect"
        cellRenderer = object : DefaultListCellRenderer() {
            override fun getListCellRendererComponent(
                list: JList<*>?, value: Any?, index: Int, selected: Boolean, focus: Boolean,
            ): Component = super.getListCellRendererComponent(list,
                (value as? RpcRequestEntry)?.let {
                    "${it.procedure}/v${it.version} · ${it.outcome} · ${it.elapsedMillis} ms"
                }
                    ?: "", index, selected, focus)
        }
    }
    private var renderedRevision = -1L
    private val loss = JLabel("History captures omitted at capacity: 0")
    private var inspected: DesktopRpcRequestDetail? = null

    init {
        add(loss, BorderLayout.NORTH)
        add(JScrollPane(entries), BorderLayout.CENTER)
        add(JPanel().apply {
            add(JButton("Inspect request").apply { addActionListener { inspect() } })
            add(JButton("Clear completed history").apply { addActionListener { history.clearCompleted(); render() } })
        }, BorderLayout.SOUTH)
        preferredSize = Dimension(700, 140)
    }

    fun render() {
        // The existing window/status owner drives this panel, including the nested modal event loop.
        // No second timer, detached snapshot or extra coroutine owns application data.
        inspected?.render()
        val revision = history.revision
        if (revision == renderedRevision) return
        val selected = entries.selectedValue?.localId
        val rows = history.entries().asReversed()
        loss.text = "History captures omitted at capacity: ${history.droppedCaptures}"
        model.clear()
        rows.forEach(model::addElement)
        entries.selectedIndex = rows.indexOfFirst { it.localId == selected }
        renderedRevision = revision
    }

    private fun inspect() {
        val selected = entries.selectedValue ?: return
        if (inspected != null) return
        val detail = DesktopRpcRequestDetail(history, selected.localId)
        inspected = detail
        val options = arrayOf("Close", "Copy diagnostics", "Copy details (includes data)")
        try {
            val choice = JOptionPane.showOptionDialog(this, detail,
                "Application data may be private — copy only to a trusted destination",
                JOptionPane.DEFAULT_OPTION, JOptionPane.INFORMATION_MESSAGE, null, options, options[0])
            // Read again at the action boundary, not the entry captured when the dialog opened.
            val text = when (choice) {
                1 -> detail.copyText(includeData = false)
                2 -> detail.copyText(includeData = true)
                else -> null
            }
            if (text != null) copy(text)
            else if (choice == 1 || choice == 2) {
                JOptionPane.showMessageDialog(this, "This request is no longer retained. Nothing was copied.")
            }
        } finally {
            inspected = null
            detail.clear()
        }
    }

    private fun copy(text: String) {
        try { Toolkit.getDefaultToolkit().systemClipboard.setContents(StringSelection(text), null) }
        catch (_: Exception) {
            JOptionPane.showMessageDialog(this, "Clipboard unavailable. Details remain visible locally.")
        }
    }
}

/** Identity-bound inspection; an evicted/cleared row can never become a different request at the same index. */
internal class DesktopRpcRequestDetail(
    private val history: RpcRequestHistory, private val localId: Long,
) : JPanel(BorderLayout()) {
    private val text = JTextArea(16, 65).apply {
        isEditable = false
        lineWrap = true
        wrapStyleWord = true
        accessibleContext.accessibleName = "Selected request details including application data"
    }
    private var closed = false

    init { add(JScrollPane(text), BorderLayout.CENTER); render() }

    fun render() {
        if (closed) return
        val value = history.entries().firstOrNull { it.localId == localId }?.details()
            ?: "This request is no longer retained. Its application data is unavailable."
        if (text.text != value) {
            val caret = text.caretPosition
            text.text = value
            text.caretPosition = caret.coerceAtMost(value.length)
        }
    }

    fun copyText(includeData: Boolean): String? {
        if (closed) return null
        val entry = history.entries().firstOrNull { it.localId == localId } ?: return null
        return if (includeData) entry.details() else entry.diagnostics()
    }

    fun clear() { closed = true; text.text = "" }
}
