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
        val detail = JTextArea(selected.details(), 16, 65).apply {
            isEditable = false
            lineWrap = true
            wrapStyleWord = true
            caretPosition = 0
            accessibleContext.accessibleName = "Selected request details including application data"
        }
        val options = arrayOf("Close", "Copy diagnostics", "Copy details (includes data)")
        when (JOptionPane.showOptionDialog(this, JScrollPane(detail),
            "Application data may be private — copy only to a trusted destination",
            JOptionPane.DEFAULT_OPTION, JOptionPane.INFORMATION_MESSAGE, null, options, options[0])) {
            1 -> copy(selected.diagnostics())
            2 -> copy(selected.details())
        }
    }

    private fun copy(text: String) {
        try { Toolkit.getDefaultToolkit().systemClipboard.setContents(StringSelection(text), null) }
        catch (_: Exception) {
            JOptionPane.showMessageDialog(this, "Clipboard unavailable. Details remain visible locally.")
        }
    }
}
