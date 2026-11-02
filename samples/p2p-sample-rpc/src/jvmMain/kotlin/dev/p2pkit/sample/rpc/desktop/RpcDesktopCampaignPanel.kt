package dev.p2pkit.sample.rpc.desktop

import dev.p2pkit.sample.rpc.RpcPhoneLab
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.jsonPrimitive
import javax.swing.JButton
import javax.swing.JComboBox
import javax.swing.JFileChooser
import javax.swing.JScrollPane
import javax.swing.JTextArea
import javax.swing.SwingUtilities
import javax.swing.Timer

/** Controls a prepared worker in its existing isolated session. It cannot prepare or silently reinstall a phone. */
internal class RpcDesktopCampaignPanel(
    private val scope: CoroutineScope,
    private val canRun: () -> Boolean,
    back: () -> Unit,
) : DesktopRpcColumn() {
    private var mailbox: DesktopRpcCampaignMailbox? = null
    private var io: Job? = null
    @Volatile private var active = false
    val running: Boolean get() = active
    private val profiles = JComboBox<DesktopRpcCampaignProfile>()
    private val recoveryMode = JComboBox(arrayOf("large", "correctness", "churn", "steady"))
    private val reportJson = Json { prettyPrint = true }
    private val status = DesktopRpcWrappedLabel("Attach the prepared campaign folder to enable its phase buttons.")
    private val details = JTextArea(12, 54).apply {
        isEditable = false; lineWrap = true; wrapStyleWord = true
        accessibleContext.accessibleName = "Saved campaign outcome and resource measurements"
    }
    private val timer = Timer(1_000) { refresh() }
    private val buttons = listOf("large", "correctness", "churn", "steady").map { mode ->
        JButton(if (mode == "steady") "Steady · 30 minutes" else mode.replaceFirstChar(Char::uppercase)).apply {
            isEnabled = false
            addActionListener {
                val profile = profiles.selectedItem as? DesktopRpcCampaignProfile ?: return@addActionListener
                if (!canRun() || active || io?.isActive == true) return@addActionListener
                active = true // Reserve before scheduling; another role cannot race a queued campaign request.
                perform {
                    mailbox?.start(profile, mode) ?: error("Prepare and attach the campaign first")
                }
            }
        }
    }
    init {
        add(JButton("Back to Test Center").apply { addActionListener { if (!active) back() } })
        add(DesktopRpcAppearance.heading("Phone capacity campaign"))
        add(DesktopRpcWrappedLabel("Choose the phone and capacity, then run one phase at a time. " +
            "Steady measures 30 minutes after setup. The worker keeps private evidence and verifies cleanup."))
        add(JButton("Attach prepared campaign folder").apply { addActionListener {
            if (active || io?.isActive == true || !canRun()) return@addActionListener
            val chooser = JFileChooser().apply { fileSelectionMode = JFileChooser.DIRECTORIES_ONLY }
            if (chooser.showOpenDialog(this@RpcDesktopCampaignPanel) != JFileChooser.APPROVE_OPTION) {
                return@addActionListener
            }
            val path = chooser.selectedFile.toPath()
            perform {
                val selected = DesktopRpcCampaignMailbox(path, RpcPhoneLab.compiledSource)
                mailbox = selected
                SwingUtilities.invokeLater {
                    profiles.removeAllItems()
                    selected.profiles.forEach(profiles::addItem)
                }
            }
        } })
        add(profiles); buttons.forEach(::add)
        add(DesktopRpcWrappedLabel("If cleanup is unresolved, select the original phase and verify retirement. " +
            "This rechecks original evidence; it does not erase failures or restart a workload."))
        add(recoveryMode)
        add(JButton("Verify original cleanup").apply { addActionListener {
            val profile = profiles.selectedItem as? DesktopRpcCampaignProfile ?: return@addActionListener
            if (!canRun() || active || io?.isActive == true) return@addActionListener
            active = true
            perform { mailbox?.start(profile, recoveryMode.selectedItem as String, "recover") }
        } })
        add(JButton("Cancel campaign phase").apply { addActionListener {
            if (active && io?.isActive != true) perform { mailbox?.cancel() }
        } })
        add(status); add(JScrollPane(details))
        add(DesktopRpcWrappedLabel("Use the matching prepared source on every device. This panel starts the " +
            "maintained 128/256 Mac-client runner; Pair/Multi buttons do not create that cohort. " +
            "Completed workloads need network/resource evidence review. Additional hardware tests remain guided."))
    }
    private fun perform(action: () -> Unit) {
        io = scope.launch(Dispatchers.IO) {
            try { action() }
            catch (_: Exception) {
                active = mailbox?.activeId != null
                SwingUtilities.invokeLater { status.showText("Action refused or worker unavailable; evidence retained. " +
                    "Check the prepared session and its cleanup outcome.") }
            } finally { SwingUtilities.invokeLater { renderButtons() } }
        }
    }
    private fun refresh() {
        if (io?.isActive == true) return
        val selected = mailbox ?: return
        perform {
            val result = selected.poll()
            active = selected.activeId != null
            val state = result.getValue("state").jsonPrimitive.content
            SwingUtilities.invokeLater {
                val elapsed = result["elapsedSeconds"]?.jsonPrimitive?.content?.let { "$it seconds" }.orEmpty()
                status.showText("$state · $elapsed")
                if (selected.lastResult != null) {
                    details.text = reportJson.encodeToString(checkNotNull(selected.lastResult))
                }
                renderButtons()
            }
        }
    }
    private fun renderButtons() { buttons.forEach { it.isEnabled = mailbox != null && !active && canRun() } }
    suspend fun retire() = withContext(Dispatchers.IO) {
        io?.join()
        mailbox?.retire()
        active = false
    }
    override fun addNotify() { super.addNotify(); timer.start() }
    override fun removeNotify() { timer.stop(); super.removeNotify() }
}
