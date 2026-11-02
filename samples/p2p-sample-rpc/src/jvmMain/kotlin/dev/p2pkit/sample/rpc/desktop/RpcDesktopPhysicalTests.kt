package dev.p2pkit.sample.rpc.desktop

import dev.p2pkit.sample.rpc.RpcDeviceTestPhase
import dev.p2pkit.sample.rpc.RpcDeviceTestSession
import dev.p2pkit.sample.rpc.RpcPhoneLab
import dev.p2pkit.sample.rpc.RpcPhysicalTestCase
import dev.p2pkit.sample.rpc.RpcPhysicalTestCatalog
import dev.p2pkit.sample.rpc.RpcDeviceTestReport
import dev.p2pkit.sample.rpc.RpcTestArchivePage
import java.awt.Component
import javax.swing.DefaultListCellRenderer
import javax.swing.JButton
import javax.swing.JCheckBox
import javax.swing.JComboBox
import javax.swing.JList
import javax.swing.JTextArea
import javax.swing.JTextField
import javax.swing.DefaultListModel
import javax.swing.JScrollPane

internal class RpcDesktopPhysicalTests(
    private val tests: RpcDeviceTestSession,
    private val mutate: (() -> Unit) -> Unit,
    private val workload: (RpcDeviceTestPhase) -> Unit,
    export: () -> Unit,
    private val browse: (Long, String) -> Unit,
    exportArchive: (String?) -> Unit,
    private val status: () -> String,
    back: () -> Unit,
) : DesktopRpcColumn() {
    private val cases = JComboBox(RpcPhysicalTestCatalog.cases.toTypedArray()).apply {
        accessibleContext.accessibleName = "Physical test case"
        renderer = object : DefaultListCellRenderer() {
            override fun getListCellRendererComponent(list: JList<*>?, value: Any?, index: Int,
                selected: Boolean, focus: Boolean): Component = super.getListCellRendererComponent(list,
                (value as? RpcPhysicalTestCase)?.summary ?: "", index, selected, focus)
        }
    }
    private val description = DesktopRpcWrappedLabel("")
    private val steps = DesktopRpcColumn()
    private val reference = JTextField(42).apply { accessibleContext.accessibleName = "Private evidence reference or run IDs" }
    private val notes = JTextArea(4, 54).apply {
        accessibleContext.accessibleName = "What happened or missing setup"
        lineWrap = true; wrapStyleWord = true
    }
    private val timing = DesktopRpcWrappedLabel("")
    private val resources = DesktopRpcWrappedLabel("")
    private val message = DesktopRpcWrappedLabel("")
    private val timer = javax.swing.Timer(1_000) { renderMonitor() }
    private val start = JButton("Start guided observation")
    private val run = JButton("Open RPC test controls")
    private val archiveModel = DefaultListModel<RpcDeviceTestReport>()
    private val archived = JList(archiveModel).apply {
        visibleRowCount = 5
        accessibleContext.accessibleName = "Saved test archive page"
        cellRenderer = object : DefaultListCellRenderer() {
            override fun getListCellRendererComponent(list: JList<*>?, value: Any?, index: Int,
                selected: Boolean, focus: Boolean): Component = super.getListCellRendererComponent(list,
                (value as? RpcDeviceTestReport)?.title ?: "", index, selected, focus)
        }
    }
    private val archiveDetails = JTextArea(8, 54).apply {
        isEditable = false
        lineWrap = true
        wrapStyleWord = true
        accessibleContext.accessibleName = "Selected archived test details"
    }
    private var archivePage: RpcTestArchivePage? = null
    private val older = JButton("Older results").apply {
        isEnabled = false
        addActionListener { archivePage?.let { browse(it.beforeMillis, it.beforeRunId) } }
    }

    init {
        add(JButton("Back to RPC").apply { addActionListener { back() } })
        add(DesktopRpcAppearance.heading("Test Center"))
        add(DesktopRpcWrappedLabel("Run built-in tests or follow a physical procedure. " +
            "Required external tools and hardware are listed for each case."))
        add(cases); add(description); add(steps); add(timing); add(run); add(start)
        add(DesktopRpcWrappedLabel("Private evidence reference / saved run IDs (up to 1024 UTF-8 bytes)"))
        add(reference)
        add(DesktopRpcWrappedLabel("What happened / missing setup (up to 4096 UTF-8 bytes)")); add(notes)
        add(JButton("Save checkpoint").apply { addActionListener {
            mutate { tests.physicalTests.checkpoint(reference.text, notes.text) }
        } })
        listOf("AwaitingReview" to "Save for review", "Failed" to "Record failure",
            "Blocked" to "Record missing setup", "Interrupted" to "End observation").forEach { (code, label) ->
            add(JButton(label).apply { addActionListener {
                mutate { tests.physicalTests.finish(code, reference.text, notes.text) }
            } })
        }
        add(resources); add(message)
        add(JButton("Export recent test evidence (up to 100 runs)").apply { addActionListener { export() } })
        add(DesktopRpcAppearance.heading("Saved test archive"))
        add(JButton("Load newest saved results").apply { addActionListener { browse(Long.MAX_VALUE, "") } })
        add(older)
        add(JScrollPane(archived))
        add(JScrollPane(archiveDetails))
        archived.addListSelectionListener { archiveDetails.text = archived.selectedValue?.detail.orEmpty() }
        add(JButton("Export selected output").apply { addActionListener {
            archived.selectedValue?.let { exportArchive(it.runId) }
        } })
        add(JButton("Export all saved outputs").apply { addActionListener { exportArchive(null) } })
        add(DesktopRpcWrappedLabel("Observations are archived separately and require independent evidence review. " +
            "This screen cannot turn missing tooling or checked steps into a qualification PASS."))
        cases.addActionListener { render() }
        start.addActionListener { mutate {
            tests.physicalTests.start(selected().id, RpcPhoneLab.compiledSource, when {
                System.getProperty("os.name").startsWith("Mac") -> "Mac (JVM)"
                System.getProperty("os.name").startsWith("Windows") -> "Windows (JVM)"
                else -> "Linux (JVM)"
            })
        } }
        run.addActionListener { selected().phase?.let(workload) }
        render()
    }

    private fun selected(): RpcPhysicalTestCase = tests.physicalTests.progress?.testCase ?: cases.selectedItem as RpcPhysicalTestCase

    fun render() {
        val active = tests.physicalTests.progress
        cases.isEnabled = active == null
        val test = selected()
        description.showText("${test.title}\n${test.equipment}\nMethod: ${test.tool}\nSave: ${test.evidence}")
        steps.removeAll()
        test.steps.forEachIndexed { index, step ->
            steps.add(JCheckBox("${index + 1}. $step", index in active?.observedSteps.orEmpty()).apply {
                isEnabled = active != null
                addActionListener { val checked = isSelected; mutate { tests.physicalTests.observeStep(index, checked) } }
            })
        }
        start.isEnabled = active == null && test.phase == null
        run.isEnabled = active == null && test.phase != null
        renderMonitor(); revalidate(); repaint()
    }

    private fun renderMonitor() {
        message.showText(status())
        timing.showText("Minimum observation ${selected().minimumSeconds}s · elapsed ${tests.physicalTests.elapsedMillis / 1_000}s")
        resources.showText(tests.liveResources?.let { it.title + "\n" + it.environmentTitle }
            ?: "No live resource sample available.")
    }

    fun renderArchive(page: RpcTestArchivePage) {
        archivePage = page
        archiveModel.clear()
        page.reports.forEach(archiveModel::addElement)
        older.isEnabled = page.olderAvailable
        if (!archiveModel.isEmpty) archived.selectedIndex = 0 else archiveDetails.text = "No saved outputs."
    }
    override fun addNotify() { super.addNotify(); timer.start() }
    override fun removeNotify() { timer.stop(); super.removeNotify() }
}
