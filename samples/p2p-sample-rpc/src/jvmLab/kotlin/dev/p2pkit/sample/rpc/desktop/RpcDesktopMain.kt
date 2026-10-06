package dev.p2pkit.sample.rpc.desktop

import dev.p2pkit.sample.rpc.RpcPhoneLab
import kotlinx.coroutines.CoroutineDispatcher
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.flow.collect
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.awt.BorderLayout
import java.awt.Component
import java.awt.ComponentOrientation
import java.awt.Dimension
import java.awt.FlowLayout
import java.awt.GraphicsEnvironment
import java.awt.event.WindowAdapter
import java.awt.event.WindowEvent
import javax.swing.BorderFactory
import javax.swing.BoxLayout
import javax.swing.DefaultComboBoxModel
import javax.swing.DefaultListCellRenderer
import javax.swing.DefaultListModel
import javax.swing.JButton
import javax.swing.JComboBox
import javax.swing.JComponent
import javax.swing.JFrame
import javax.swing.JLabel
import javax.swing.JList
import javax.swing.JOptionPane
import javax.swing.JPanel
import javax.swing.JPasswordField
import javax.swing.JScrollPane
import javax.swing.JTextArea
import javax.swing.JTextField
import javax.swing.ListSelectionModel
import javax.swing.SwingUtilities
import javax.swing.WindowConstants
import javax.swing.text.AbstractDocument
import javax.swing.text.AttributeSet
import javax.swing.text.DocumentFilter
import kotlin.coroutines.CoroutineContext

/** Opt-in local developer UI. No capacity campaign, automatic role, discovery or trust import. */
fun main() {
    check(!GraphicsEnvironment.isHeadless()) { "The RPC Desktop sample requires a graphical desktop." }
    SwingUtilities.invokeLater { RpcDesktopWindow().isVisible = true }
}

private class RpcDesktopWindow : JFrame("RPC Desktop sample — developer preview") {
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.Default)
    private val owner = DesktopRpcRunOwner(
        scope,
        readStatus = { runtime: DesktopRpcRuntime, role -> runtime.status(role == "Host") },
        retire = DesktopRpcRuntime::close,
    )
    private val networks = JComboBox<DesktopRpcNetwork>()
    private val refresh = JButton("Refresh interfaces")
    private val subnets = field(512)
    private val port = field(5).apply { text = "48123"; columns = 7 }
    private val host = JButton("Start host")
    private val client = JButton("Create client")
    private val stop = JButton("Stop")
    private val cancel = JButton("Cancel operation")
    private val state = JLabel("Idle — select a physical LAN interface, then choose one role.")
    private val liveState = JLabel("Live status appears automatically after a role starts.")
    private val statusCards = DesktopRpcStatusCards()
    private val identity = field(64).apply { isEditable = false }
    private val invitation = JTextArea(3, 54).apply {
        isEditable = false
        lineWrap = true
        accessibleContext.accessibleName = "Local host invitation; secret; share only with the intended client"
    }
    private val invite = JButton("Show new invitation")
    private val pendingModel = DefaultListModel<DesktopRpcPending>()
    private val pending = JList(pendingModel).apply {
        selectionMode = ListSelectionModel.SINGLE_SELECTION
        visibleRowCount = 3
        accessibleContext.accessibleName = "Pending client fingerprints; select explicitly before approval"
        cellRenderer = object : DefaultListCellRenderer() {
            override fun getListCellRendererComponent(
                list: JList<*>?, value: Any?, index: Int, selected: Boolean, focus: Boolean,
            ): Component = super.getListCellRendererComponent(
                list, (value as? DesktopRpcPending)?.fingerprint ?: "", index, selected, focus,
            )
        }
    }
    private val approve = JButton("Approve selected client")
    private val peerInvitation = JPasswordField(54).apply { bound(this, 512) }
    private val pair = JButton("Pair and connect")
    private val echo = JButton("Call 1 KiB echo")
    private val outcome = JTextArea("No RPC performed. Starting a role is not an end-to-end pass.", 3, 54).apply {
        isEditable = false
        lineWrap = true
        wrapStyleWord = true
        isOpaque = false
        accessibleContext.accessibleName = "RPC outcome and network setup guidance"
    }
    private var statusUpdates: Job? = null
    private var closing = false
    private var refreshing = false
    private var invitationEpoch = Any() // EDT-only visibility generation; focus return cannot revive an old request.

    init {
        defaultCloseOperation = WindowConstants.DO_NOTHING_ON_CLOSE
        contentPane = JPanel(BorderLayout(0, 10)).apply {
            border = BorderFactory.createEmptyBorder(12, 12, 12, 12)
            add(JPanel().apply {
                layout = BoxLayout(this, BoxLayout.Y_AXIS)
                add(JLabel("Encrypted ephemeral identity: Stop/exit loses approvals. Re-pair next run."))
                add(JLabel("Select the actual organization LAN; no self, loopback, emulator NAT or tunnels."))
                add(JLabel("Compiled source: ${RpcPhoneLab.compiledSource}"))
                add(row("Physical IPv4 LAN (read-only suggestions)", networks, refresh))
                add(row("Approved private CIDRs (comma separated)", subnets))
                add(row("Host port", port, host, client, cancel, stop))
                add(row("Local fingerprint — compare on the other device", identity))
                add(state)
                add(liveState)
                add(statusCards)
                add(row("Host invitation (expires within two minutes)", invite))
                add(JScrollPane(invitation))
                add(row("Host: verify the full client fingerprint before approval", approve))
                add(JScrollPane(pending))
                add(row("Client: paste invitation from the host's trusted local UI", peerInvitation))
                add(row("Client actions", pair, echo))
                add(outcome)
                add(JLabel("English-only developer preview; no LAN, capacity or release-readiness claim."))
            }, BorderLayout.CENTER)
        }
        // Network literals, fingerprints and invitations must not visually reorder in an RTL desktop.
        contentPane.applyComponentOrientation(ComponentOrientation.LEFT_TO_RIGHT)
        minimumSize = Dimension(760, 640)
        pack()
        setLocationByPlatform(true)
        refresh.addActionListener { refreshNetworks() }
        networks.addActionListener {
            (networks.selectedItem as? DesktopRpcNetwork)?.let {
                subnets.text = it.subnet
                outcome.text = it.startProblem ?: "Review the network, then choose one role. Nothing has started."
            }
        }
        host.addActionListener { startRole(host = true) }
        client.addActionListener { startRole(host = false) }
        stop.addActionListener { clearSensitive(); owner.stop(); render() }
        cancel.addActionListener { owner.cancelAction(); render() }
        invite.addActionListener {
            val epoch = invitationEpoch
            action { runtime ->
                val text = runtime.invitation()
                publish(runtime) {
                    if (desktopRpcInvitationVisible(epoch, invitationEpoch, isActive)) invitation.text = text
                }
            }
        }
        pending.addListSelectionListener { renderButtons() }
        approve.addActionListener {
            val selected = pending.selectedValue ?: return@addActionListener
            val runtime = owner.current() ?: return@addActionListener
            val answer = JOptionPane.showConfirmDialog(this,
                "Approve only if the other device shows this exact fingerprint:\n${selected.fingerprint}",
                "Explicit pairing approval", JOptionPane.YES_NO_OPTION, JOptionPane.WARNING_MESSAGE)
            if (answer == JOptionPane.YES_OPTION) {
                if (!owner.owns(runtime) || !desktopRpcCanApprove(owner.snapshot(), selected)) {
                    outcome.text = "That request is no longer current. Select and verify a pending request again."
                } else action { current ->
                    check(current === runtime)
                    current.approve(selected)
                }
            }
        }
        pair.addActionListener {
            val characters = peerInvitation.password
            val text = try { String(characters) } finally { characters.fill('\u0000'); peerInvitation.text = "" }
            if (text.isEmpty()) outcome.text = "Paste the host invitation first."
            else action { runtime ->
                runtime.pairAndConnect(text)
                publish(runtime) { outcome.text = "Paired and connected. Call echo to verify a real reply." }
            }
        }
        echo.addActionListener { action { runtime ->
            val result = runtime.echo()
            publish(runtime) {
                outcome.text = "Echo ${result.completed}/${result.expected} in ${result.elapsedMillis} ms; " +
                    "failure=${result.failureKind ?: "none"}; execution=${result.executionEvidence ?: "reply checked"}."
            }
        } }
        addWindowListener(object : WindowAdapter() {
            override fun windowClosing(event: WindowEvent) { closeWindow() }
            override fun windowDeactivated(event: WindowEvent) { clearInvitationText() }
        })
        statusUpdates = scope.launch {
            owner.snapshots.collect {
                // Await each EDT delivery: a busy UI gets the newest StateFlow value, not a growing event queue.
                withContext(DesktopRpcEdt) { if (!closing) render() }
            }
        }
        render()
        refreshNetworks()
    }

    private fun startRole(host: Boolean) {
        val selected = networks.selectedItem as? DesktopRpcNetwork
        if (selected == null) { outcome.text = "Select an observed physical LAN interface first."; return }
        // Scan feedback is advisory. Only the explicit Start action reaches fresh transport admission:
        // the portable guard is unchanged; the Mac adapter must independently prove every actual TCP socket.

        val settings = try { desktopRpcSettings(subnets.text, selected.interfaceName, selected.address, port.text) }
        catch (_: IllegalArgumentException) {
            outcome.text = "Invalid private CIDRs, address, interface or port."
            return
        }
        clearSensitive()
        outcome.text = "Starting explicit role; no remote RPC has been performed."
        owner.start(if (host) "Host" else "Client", { DesktopRpcRuntime.create() }) { it.start(host, settings) }
        render()
    }

    private fun action(block: suspend (DesktopRpcRuntime) -> Unit) {
        if (!owner.action(block)) {
            outcome.text = "Wait for the owned operation or Stop; no additional action was queued."
        }
        render()
    }

    private fun publish(runtime: DesktopRpcRuntime, action: () -> Unit) {
        SwingUtilities.invokeLater { if (!closing && owner.owns(runtime)) action() }
    }

    private fun refreshNetworks() {
        if (refreshing || owner.snapshot().stage !in setOf(
                DesktopRpcRunOwner.Stage.Idle, DesktopRpcRunOwner.Stage.Stopped,
            )
        ) return
        refreshing = true
        renderButtons()
        scope.launch {
            val result = runCatching { desktopRpcNetworks() }
            SwingUtilities.invokeLater {
                if (!closing) {
                    networks.model = DefaultComboBoxModel(result.getOrDefault(emptyList()).toTypedArray())
                    networks.selectedIndex = -1 // Observation is not permission to choose an interface automatically.
                    subnets.text = ""
                    refreshing = false
                    outcome.text = if (result.isFailure) "Unable to inspect interfaces; no network changes were made."
                    else "Choose an observed physical interface. This list does not prove routing or peer reachability."
                    renderButtons()
                }
            }
        }
    }

    private fun render() {
        val snapshot = owner.snapshot()
        state.showText("${snapshot.role ?: "No role"}: ${snapshot.stage}" +
            (snapshot.failure?.let { " — ${desktopRpcFailureText(it)}" } ?: ""))
        val status = snapshot.status
        liveState.showText(when {
            snapshot.statusUnavailable -> "Live status unavailable; action results and errors are retained."
            status != null -> "Live ${snapshot.role}: ${status.state} — updates automatically every 500 ms."
            else -> "Live status appears automatically after a role starts."
        })
        statusCards.render(status, DesktopRpcRole.entries.firstOrNull { it.name == snapshot.role })
        val fingerprint = status?.fingerprint ?: ""
        if (identity.text != fingerprint) identity.text = fingerprint
        val requests = status?.pending ?: emptyList()
        val previous = (0 until pendingModel.size()).map { pendingModel[it] }
        if (requests != previous) {
            val selection = pending.selectedValue
            pendingModel.clear()
            requests.forEach(pendingModel::addElement)
            pending.selectedIndex = desktopRpcPendingSelection(selection, requests)
        }
        renderButtons(snapshot)
    }

    private fun renderButtons(snapshot: DesktopRpcRunOwner.Snapshot = owner.snapshot()) {
        val idle = snapshot.stage in setOf(DesktopRpcRunOwner.Stage.Idle, DesktopRpcRunOwner.Stage.Stopped)
        val ready = snapshot.stage == DesktopRpcRunOwner.Stage.Ready && !closing
        listOf(networks, subnets, port, host, client, refresh).forEach {
            it.isEnabled = idle && !closing && !refreshing
        }
        stop.isEnabled = !idle && !closing && snapshot.stage != DesktopRpcRunOwner.Stage.Stopping
        cancel.isEnabled = !closing && snapshot.stage in setOf(
            DesktopRpcRunOwner.Stage.Starting, DesktopRpcRunOwner.Stage.Working,
        )
        invite.isEnabled = ready && snapshot.role == "Host" && snapshot.status?.state == "Running"
        pending.isEnabled = ready && snapshot.role == "Host"
        approve.isEnabled = !closing && desktopRpcCanApprove(snapshot, pending.selectedValue)
        pair.isEnabled = ready && snapshot.role == "Client"
        peerInvitation.isEnabled = pair.isEnabled
        echo.isEnabled = pair.isEnabled && snapshot.status?.state == "Ready"
    }

    private fun clearInvitationText() {
        invitationEpoch = Any()
        invitation.text = ""
        peerInvitation.text = ""
    }

    private fun clearSensitive() {
        clearInvitationText()
        identity.text = ""
        pendingModel.clear()
        outcome.text = "Invitation text hidden; unused invitations may remain valid until expiry or successful Stop."
    }

    private fun closeWindow() {
        if (closing) return
        closing = true
        statusUpdates?.cancel()
        clearSensitive()
        renderButtons()
        val stopped = owner.stop()
        render() // The collector is cancelled: clear live counts and pending identities explicitly before hiding.
        isVisible = false
        scope.launch {
            val failure = stopped.await()
            SwingUtilities.invokeLater {
                if (failure == null) {
                    scope.cancel()
                    dispose()
                } else {
                    isVisible = true
                    render()
                    state.text = "Cleanup failed; runtime retained. Do not treat this role as closed."
                    // No forced JVM exit, unsafe secret erasure or non-idempotent cleanup retry.
                }
            }
        }
    }
}

/** No Swing coroutine dependency or blocking invokeAndWait; the producer awaits one queued render at a time. */
private object DesktopRpcEdt : CoroutineDispatcher() {
    override fun isDispatchNeeded(context: CoroutineContext): Boolean = !SwingUtilities.isEventDispatchThread()
    override fun dispatch(context: CoroutineContext, block: Runnable) = SwingUtilities.invokeLater(block)
}

private fun JLabel.showText(value: String) {
    if (text != value) text = value
}

private fun row(label: String, component: JComponent, vararg others: JComponent): JPanel =
    JPanel(FlowLayout(FlowLayout.LEADING)).apply {
        add(JLabel(label).apply { labelFor = component })
        add(component)
        others.forEach(::add)
    }

private fun field(maximum: Int): JTextField = JTextField(42).also { bound(it, maximum) }

private fun bound(field: JTextField, maximum: Int) {
    (field.document as AbstractDocument).documentFilter = object : DocumentFilter() {
        override fun insertString(bypass: FilterBypass, offset: Int, text: String?, attributes: AttributeSet?) {
            replace(bypass, offset, 0, text, attributes)
        }
        override fun replace(bypass: FilterBypass, offset: Int, length: Int, text: String?, attributes: AttributeSet?) {
            if (bypass.document.length - length + (text?.length ?: 0) <= maximum) {
                bypass.replace(offset, length, text, attributes)
            }
        }
    }
}

/** The EDT invalidates the token on focus loss, Stop and close, even if focus subsequently returns. */
internal fun desktopRpcInvitationVisible(expected: Any, current: Any, active: Boolean): Boolean =
    active && expected === current
