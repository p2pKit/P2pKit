package dev.p2pkit.sample.rpc.desktop

import dev.p2pkit.sample.rpc.RpcApplicationExample
import dev.p2pkit.sample.rpc.RpcApplicationInput
import dev.p2pkit.sample.rpc.RpcApplicationProcedure
import dev.p2pkit.sample.rpc.RpcApplicationSession
import dev.p2pkit.sample.rpc.RpcPhoneLab
import dev.p2pkit.sample.rpc.RpcNearbyHost
import dev.p2pkit.sample.rpc.RpcKnownDevice
import java.nio.file.Path
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
    private val applicationSession = RpcApplicationSession()
    private val requestHistory = DesktopRpcRequestHistory(applicationSession.history)
    private val examples = listOf(
        JButton("users.get") to RpcApplicationExample.GetUser,
        JButton("items.list") to RpcApplicationExample.ListItems,
        JButton("message.send") to RpcApplicationExample.SendMessage,
        JButton("Business error") to RpcApplicationExample.BusinessError,
        JButton("Validation error") to RpcApplicationExample.ValidationError,
    )
    private val inputUser = field(11).apply { text = "123" }
    private val inputOffset = field(11).apply { text = "0" }
    private val inputLimit = field(11).apply { text = "20" }
    private val inputMessage = field(512).apply { text = "Hello from the RPC sample" }
    private val requests = listOf(JButton("Send users.get") to RpcApplicationProcedure.GetUser,
        JButton("Send items.list") to RpcApplicationProcedure.ListItems,
        JButton("Send message.send") to RpcApplicationProcedure.SendMessage)
    private val owner = DesktopRpcRunOwner(
        scope,
        readStatus = { runtime: DesktopRpcRuntime, role -> runtime.status(role == "Host") },
        retire = DesktopRpcRuntime::close,
    )
    private val networks = JComboBox<DesktopRpcNetwork>()
    private val refresh = JButton("Check network again")
    private val subnets = field(512)
    private val port = field(5).apply { text = "48123"; columns = 7 }
    private val host = JButton("Start host")
    private val client = JButton("Create client")
    private val stop = JButton("Stop")
    private val cancel = JButton("Cancel operation")
    private val state = JLabel("Idle — select a physical LAN interface, then choose one role.")
    private val liveState = JLabel("Live status appears automatically after a role starts.")
    private val statusCards = DesktopRpcStatusCards()
    private val requestMetrics = DesktopRpcRequestMetrics()
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
    private val approve = JButton("Review selected client")
    private val discovery = DesktopRpcDiscoveryPanel(::selectNearby, ::forgetNearby)
    private var profile: DesktopRpcProfile? = null
    private var unlocking = false
    private var approvalDialog = false
    private var lastOffered: DesktopRpcPending? = null
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
            add(JScrollPane(JPanel().apply {
                layout = BoxLayout(this, BoxLayout.Y_AXIS)
                add(JLabel("Persistent encrypted identity and trust. " +
                    "Unlock your profile once per app launch; Stop preserves it."))
                add(JLabel("The one eligible private IPv4 LAN is selected automatically. " +
                    "Network safety checks remain enforced."))
                add(JLabel("Compiled source: ${RpcPhoneLab.compiledSource}"))
                add(row("Roles", host, client, cancel, stop, refresh))
                add(row("Local fingerprint — compare on the other device", identity))
                add(state)
                add(liveState)
                add(statusCards)
                add(JLabel("Request outcomes — current role lifetime; refused attempts are not admitted requests."))
                add(requestMetrics)
                add(discovery)
                add(row("Host: verify the full client fingerprint before approval", approve))
                add(JScrollPane(pending))

                add(row("User / recipient ID", inputUser))
                add(row("Items offset", inputOffset))
                add(row("Items limit (1–50)", inputLimit))
                add(row("Message (up to 512 UTF-16 units)", inputMessage))
                add(row("Typed API requests", requests[0].first, requests[1].first, requests[2].first))
                add(row("Preset API examples", examples.first().first,
                    *examples.drop(1).map { it.first }.toTypedArray()))
                add(row("Diagnostics", echo))
                add(outcome)
                add(JLabel("Request history: bounded local application data; retained across Stop, not app exit."))
                add(JLabel("Host results describe handler completion, not proof of delivery to the client."))
                add(requestHistory)
                add(JLabel("English-only developer preview; no LAN, capacity or release-readiness claim."))
            }).apply { verticalScrollBar.unitIncrement = 16 }, BorderLayout.CENTER)
        }
        // Network literals, fingerprints and invitations must not visually reorder in an RTL desktop.
        contentPane.applyComponentOrientation(ComponentOrientation.LEFT_TO_RIGHT)
        minimumSize = Dimension(760, 640)
        pack()
        val screen = GraphicsEnvironment.getLocalGraphicsEnvironment().maximumWindowBounds
        setSize(minOf(width, screen.width), minOf(height, screen.height))
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
        approve.addActionListener { pending.selectedValue?.let(::reviewPending) }
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
        requests.forEach { (button, procedure) -> button.addActionListener {
            val input = try {
                RpcApplicationInput.parse(procedure, inputUser.text, inputOffset.text,
                    inputLimit.text, inputMessage.text)
            } catch (_: IllegalArgumentException) {
                outcome.text = "Input validation failed: enter whole 32-bit numbers and bounded text."
                return@addActionListener
            }
            action { runtime ->
                val failure = runtime.request(input)
                publish(runtime) {
                    outcome.text = failure ?: "Reply received. Inspect history for response data or business errors."
                    requestHistory.render()
                }
            }
        } }
        examples.forEach { (button, example) -> button.addActionListener { action { runtime ->
            val failure = runtime.example(example)
            publish(runtime) {
                outcome.text = failure ?: "Reply received. History distinguishes success and business errors."
                requestHistory.render()
            }
        } } }
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
        if (closing || unlocking || owner.snapshot().stage !in setOf(
                DesktopRpcRunOwner.Stage.Idle, DesktopRpcRunOwner.Stage.Stopped)) return
        val unlocked = profile
        if (unlocked == null) { unlockProfile { startRole(host) }; return }
        clearSensitive()
        outcome.text = "Starting selected role on the freshly observed eligible private LAN."
        owner.start(if (host) "Host" else "Client", {
            DesktopRpcRuntime.create(application = applicationSession, profile = unlocked)
        }) { runtime ->
            // Fresh scan on the owned worker, not the earlier advisory UI scan. Never force an interface.
            val settings = desktopRpcAutomaticSettings(desktopRpcNetworks())
            runtime.start(host, settings)
        }
        render()
    }

    private fun unlockProfile(ready: () -> Unit) {
        val input = JPasswordField(32)
        input.accessibleContext.accessibleName = "RPC profile passphrase; not your computer login password"
        val answer = JOptionPane.showConfirmDialog(this, arrayOf(
            "Unlock or create your local encrypted RPC profile (12–128 characters).",
            "Use a separate strong passphrase, NOT your Mac login password. No recovery or reset is automatic.", input,
        ), "RPC profile", JOptionPane.OK_CANCEL_OPTION, JOptionPane.PLAIN_MESSAGE)
        val password = input.password
        input.text = ""
        if (answer != JOptionPane.OK_OPTION) { password.fill('\u0000'); return }
        unlocking = true
        renderButtons()
        scope.launch {
            val result = runCatching {
                DesktopRpcProfile.open(Path.of(System.getProperty("user.home"), ".p2pkit-rpc-desktop"), password)
            }
            withContext(DesktopRpcEdt) {
                unlocking = false
                profile = result.getOrNull()
                if (result.isSuccess) ready()
                else outcome.text = "Profile could not be unlocked " +
                    "(passphrase, ownership, corruption or another app instance). " +
                    "Existing files were preserved. No network role started."
                renderButtons()
            }
        }
    }

    private fun selectNearby(host: RpcNearbyHost) {
        val runtime = owner.current() ?: return
        val answer = JOptionPane.showConfirmDialog(this,
            JTextArea("${host.name} · ${host.platform}\n${host.fingerprint}\n" +
                "Discovery names can be spoofed. Compare the full fingerprint on the other device.\n" +
                "Without comparison this is trust on first use. The host must also approve your identity.").apply {
                isEditable = false
                lineWrap = true
                wrapStyleWord = true
                columns = 64
                rows = 6
            },
            "Select this host identity?", JOptionPane.YES_NO_OPTION, JOptionPane.WARNING_MESSAGE)
        if (answer != JOptionPane.YES_OPTION || !owner.owns(runtime)) return
        if (owner.snapshot().status?.nearby?.count { it.fingerprint == host.fingerprint } != 1) return
        action { current ->
            check(current === runtime)
            val failure = current.select(host.fingerprint)
            publish(current) { outcome.text = failure ?: "Selected host; connection and approval status update live." }
        }
    }

    private fun forgetNearby(device: RpcKnownDevice) {
        val runtime = owner.current() ?: return
        val answer = JOptionPane.showConfirmDialog(this,
            "${device.fingerprint}\nDisconnect and revoke trust? A future connection requires fresh approval.",
            "Forget this identity?", JOptionPane.YES_NO_OPTION, JOptionPane.WARNING_MESSAGE)
        if (answer != JOptionPane.YES_OPTION || !owner.owns(runtime)) return
        action { current -> check(current === runtime); current.forget(device.fingerprint) }
    }

    private fun reviewPending(selected: DesktopRpcPending) {
        if (approvalDialog || !desktopRpcCanApprove(owner.snapshot(), selected)) return
        val runtime = owner.current() ?: return
        lastOffered = selected
        approvalDialog = true
        val answer = try { JOptionPane.showOptionDialog(this,
            "Authenticated client fingerprint:\n${selected.fingerprint}\nOrigin: ${selected.origin}\n" +
                "Compare with the client display. Approval saves this identity, not a name or address.",
            "Client requests approval", JOptionPane.DEFAULT_OPTION, JOptionPane.WARNING_MESSAGE,
            null, arrayOf("Approve exact identity", "Reject", "Later"), "Later")
        } finally { approvalDialog = false }
        if (answer !in 0..1 || !owner.owns(runtime) || !desktopRpcCanApprove(owner.snapshot(), selected)) return
        action { current ->
            check(current === runtime)
            if (answer == 0) current.approve(selected) else current.reject(selected)
        }
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
                    networks.selectedIndex = -1 // Hidden legacy diagnostic selector; normal startup always rescans.
                    subnets.text = ""
                    refreshing = false
                    outcome.text = if (result.isFailure) "Unable to inspect interfaces; no network changes were made."
                    else if (result.getOrThrow().size == 1)
                        "One eligible private LAN observed. Start a role; routing is rechecked then."
                    else "No unique eligible private LAN. Discovery cannot start safely on this topology."
                    renderButtons()
                }
            }
        }
    }

    private fun render() {
        requestHistory.render()
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
        requestMetrics.render(status?.metrics)
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
        discovery.render(status, snapshot.stage == DesktopRpcRunOwner.Stage.Ready && !closing)
        if (requests.isEmpty()) lastOffered = null
        if (!approvalDialog && isActive && snapshot.stage == DesktopRpcRunOwner.Stage.Ready) {
            requests.firstOrNull { it != lastOffered }?.let { request ->
                SwingUtilities.invokeLater { if (!closing && isActive) reviewPending(request) }
            }
        }
        renderButtons(snapshot)
    }

    private fun renderButtons(snapshot: DesktopRpcRunOwner.Snapshot = owner.snapshot()) {
        val idle = snapshot.stage in setOf(DesktopRpcRunOwner.Stage.Idle, DesktopRpcRunOwner.Stage.Stopped)
        val ready = snapshot.stage == DesktopRpcRunOwner.Stage.Ready && !closing
        listOf(networks, subnets, port, host, client, refresh).forEach {
            it.isEnabled = idle && !closing && !refreshing && !unlocking
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
        examples.forEach { it.first.isEnabled = echo.isEnabled }
        requests.forEach { it.first.isEnabled = echo.isEnabled }
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
        outcome.text = "Transient identity display cleared. Saved profile trust is unchanged."
    }

    private fun closeWindow() {
        if (closing) return
        if (unlocking) { outcome.text = "Wait for the bounded profile unlock before closing."; return }
        closing = true
        statusUpdates?.cancel()
        clearSensitive()
        renderButtons()
        val stopped = owner.stop()
        render() // The collector is cancelled: clear live counts and pending identities explicitly before hiding.
        isVisible = false
        scope.launch {
            val roleFailure = stopped.await()
            val failure = roleFailure ?: runCatching { profile?.close() }.exceptionOrNull()
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
