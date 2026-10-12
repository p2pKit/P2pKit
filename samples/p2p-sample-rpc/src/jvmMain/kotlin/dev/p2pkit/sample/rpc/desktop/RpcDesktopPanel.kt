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
import kotlinx.coroutines.CoroutineStart
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.cancelAndJoin
import kotlinx.coroutines.flow.collect
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.awt.BorderLayout
import java.awt.Component
import java.awt.ComponentOrientation
import java.awt.Point
import java.awt.event.ActionEvent
import java.awt.event.KeyEvent
import javax.swing.AbstractAction
import javax.swing.JDialog
import javax.swing.KeyStroke
import javax.swing.BorderFactory
import javax.swing.DefaultComboBoxModel
import javax.swing.DefaultListCellRenderer
import javax.swing.DefaultListModel
import javax.swing.JButton
import javax.swing.JComboBox
import javax.swing.JComponent
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
import javax.swing.text.AbstractDocument
import javax.swing.text.AttributeSet
import javax.swing.text.DocumentFilter
import kotlin.coroutines.CoroutineContext

/**
 * Embeddable RPC section. Construct and call on the EDT; it never creates an application window.
 * The host must retain this panel until [requestClose] reports [DesktopRpcCloseResult.Closed].
 * Supplying an application session preserves request history across section changes.
 */
public class RpcDesktopPanel(
    private val applicationSession: RpcApplicationSession = RpcApplicationSession(),
    private val onBackRequested: () -> Unit = {},
) : JPanel(BorderLayout(0, 10)) {
    private val scopeJob = SupervisorJob()
    private val scope = CoroutineScope(scopeJob + Dispatchers.Default)
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
    private val state = JLabel("Idle — choose Host or Client; the eligible LAN is selected automatically.")
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
    private var unlockJob: Job? = null
    private var unlockTask: DesktopRpcPanelUnlockTask? = null
    private var unlockCleanupFailure: Throwable? = null
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
    private val workspaceScroll = JScrollPane()
    private var statusUpdates: Job? = null
    private var networkRefresh: Job? = null
    private var closing = false
    private var windowActive = false
    private val closeOwner = DesktopRpcPanelCloseOwner()
    private var closeFailure: Throwable? = null
    private var dialog: JDialog? = null
    private var dialogEpoch = Any()
    private var refreshing = false
    private var invitationEpoch = Any() // EDT-only visibility generation; focus return cannot revive an old request.

    init {
        check(SwingUtilities.isEventDispatchThread())
        background = DesktopRpcAppearance.background
        border = BorderFactory.createEmptyBorder(12, 12, 12, 12)
        // JPanel lazily constructs this object; never read its inherited protected backing field.
        getAccessibleContext().accessibleName = "RPC application section"
        add(workspaceScroll.apply { setViewportView(DesktopRpcColumn().apply {
                background = DesktopRpcAppearance.background
                border = BorderFactory.createEmptyBorder(4, 8, 20, 8)
                add(JButton("Back to samples").apply { addActionListener { requestBack() } })
                add(DesktopRpcAppearance.hero())
                if (System.getProperty("os.name").startsWith("Windows")) {
                    add(DesktopRpcWrappedLabel("RPC is unavailable on Windows: protected persistent profiles are " +
                        "not implemented on Windows. Host and Client are unavailable; no insecure fallback is used."))
                }
                add(DesktopRpcAppearance.heading("Connect"))
                add(DesktopRpcWrappedLabel("Choose Host on one device and Client on the other. " +
                    "Network selection is automatic; first connections need your approval."))
                add(row("Roles", host, client, stop, cancel))
                add(state)
                add(liveState)
                add(outcome)
                add(DesktopRpcDisclosure("Device identity", DesktopRpcColumn().apply {
                    add(row("Local fingerprint — compare on the other device", identity))
                    add(DesktopRpcWrappedLabel("Your encrypted profile keeps this identity and trust after Stop. " +
                        "Unlock it with your application passphrase, not your computer login password."))
                }))
                add(DesktopRpcAppearance.heading("Nearby devices"))
                add(discovery)
                add(row("Host: review a pending client", approve))
                add(JScrollPane(pending))
                add(DesktopRpcAppearance.heading("Send a request"))
                add(DesktopRpcWrappedLabel("Once the client is Ready, choose an example. " +
                    "Open Request history to inspect the response."))
                add(row("Examples", examples[0].first, examples[1].first, examples[2].first))
                add(DesktopRpcDisclosure("Custom request", DesktopRpcColumn().apply {
                    add(row("User / recipient ID", inputUser))
                    add(row("Items offset", inputOffset))
                    add(row("Items limit (1–50)", inputLimit))
                    add(row("Message (up to 512 UTF-16 units)", inputMessage))
                    add(row("Send", requests[0].first, requests[1].first, requests[2].first))
                }))
                add(DesktopRpcDisclosure("Error examples & echo", DesktopRpcColumn().apply {
                    add(row("Error examples", examples[3].first, examples[4].first))
                    add(row("Diagnostics", echo))
                }))
                add(DesktopRpcDisclosure("Activity & statistics", DesktopRpcColumn().apply {
                    add(statusCards)
                    add(requestMetrics)
                    add(DesktopRpcWrappedLabel("Current role lifetime; refused attempts are not admitted requests. " +
                        "Host completion does not prove client delivery."))
                }))
                add(DesktopRpcDisclosure("Request history (application data)", DesktopRpcColumn().apply {
                    add(DesktopRpcWrappedLabel("Private, bounded request/response previews. " +
                        "History survives Stop, not app exit."))
                    add(requestHistory)
                }))
                add(DesktopRpcDisclosure("Diagnostics", DesktopRpcColumn().apply {
                    add(refresh)
                    add(JLabel("Compiled source: ${RpcPhoneLab.compiledSource}"))
                    add(DesktopRpcWrappedLabel("The eligible private IPv4 LAN is selected automatically. " +
                        "Network safety checks remain enforced."))
                }))
                add(JLabel("English-only sample; running this UI is not qualification evidence."))
            }); verticalScrollBar.unitIncrement = 16 }, BorderLayout.CENTER)
        // Both the Swing focus island and the Compose toolbar delegate to the same host policy.
        getInputMap(WHEN_ANCESTOR_OF_FOCUSED_COMPONENT).put(
            KeyStroke.getKeyStroke(KeyEvent.VK_ESCAPE, 0), "rpc.back")
        actionMap.put("rpc.back", object : AbstractAction() {
            override fun actionPerformed(event: ActionEvent) = requestBack()
        })
        isFocusable = true
        applyComponentOrientation(ComponentOrientation.LEFT_TO_RIGHT)
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
                    if (desktopRpcInvitationVisible(epoch, invitationEpoch, windowActive && isShowing)) invitation.text = text
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
        if (closing || unlocking || unlockCleanupFailure != null || !windowActive || owner.snapshot().stage !in setOf(
                DesktopRpcRunOwner.Stage.Idle, DesktopRpcRunOwner.Stage.Stopped)) return
        val unlocked = profile
        if (unlocked == null) { unlockProfile { startRole(host) }; return }
        clearSensitive()
        outcome.text = "Starting selected role on the freshly observed eligible private LAN."
        owner.start(if (host) "Host" else "Client", {
            DesktopRpcRuntime.create(application = applicationSession, profile = unlocked)
        }) { runtime ->
            // Fresh scan on the owned worker, not the earlier advisory UI scan. Never force an interface.
            val settings = desktopRpcDiscoverySettings(desktopRpcNetworks())
            runtime.start(host, settings)
        }
        render()
    }

    private fun unlockProfile(ready: () -> Unit) {
        val input = JPasswordField(32)
        input.accessibleContext.accessibleName = "RPC profile passphrase; not your computer login password"
        val answer = showOptions(arrayOf(
            "Unlock or create your local encrypted RPC profile (12–128 characters).",
            "Use a separate strong passphrase, NOT your Mac login password. No recovery or reset is automatic.", input,
        ), "RPC profile", arrayOf("Unlock profile", "Cancel"), JOptionPane.PLAIN_MESSAGE)
        val password = input.password
        input.text = ""
        if (answer != 0 || closing) { password.fill('\u0000'); return }
        unlocking = true
        renderButtons()
        val task = createDesktopRpcProfileUnlock(scope, DesktopRpcEdt,
            open = {
                DesktopRpcProfile.openAttempt(Path.of(System.getProperty("user.home"), ".p2pkit-rpc-desktop"), password)
            }, isClosing = { closing }, accept = { attempt ->
                val result = attempt.result
                unlocking = false
                profile = result.getOrNull()
                if (unlockCleanupFailure == null) unlockCleanupFailure = attempt.cleanupFailure
                if (!closing && result.isFailure) {
                    outcome.text = "Profile could not be unlocked " +
                        "(passphrase, ownership, corruption or another app instance). " +
                        "Existing files were preserved. No network role started."
                }
                renderButtons()
            }, ready = ready, completionCleanup = { password.fill('\u0000') },
        )
        unlockTask = task
        unlockJob = task.job
        task.start()
    }

    private fun selectNearby(host: RpcNearbyHost) {
        val runtime = owner.current() ?: return
        val answer = showOptions(JTextArea("${host.name} · ${host.platform}\n${host.fingerprint}\n" +
                "Discovery names can be spoofed. Compare the full fingerprint on the other device.\n" +
                "Without comparison this is trust on first use. The host must also approve your identity.").apply {
                isEditable = false
                lineWrap = true
                wrapStyleWord = true
                columns = 64
                rows = 6
            },
            "Select this host identity?", arrayOf("Select exact identity", "Cancel"))
        if (answer != 0 || closing || !owner.owns(runtime)) return
        if (owner.snapshot().status?.nearby?.count { it.fingerprint == host.fingerprint } != 1) return
        action { current ->
            check(current === runtime)
            val failure = current.select(host.fingerprint)
            publish(current) { outcome.text = failure ?: "Selected host; connection and approval status update live." }
        }
    }

    private fun forgetNearby(device: RpcKnownDevice) {
        val runtime = owner.current() ?: return
        val answer = showOptions("${device.fingerprint}\nDisconnect and revoke trust? A future connection requires fresh approval.",
            "Forget this identity?", arrayOf("Forget device", "Cancel"))
        if (answer != 0 || closing || !owner.owns(runtime)) return
        action { current -> check(current === runtime); current.forget(device.fingerprint) }
    }

    private fun reviewPending(selected: DesktopRpcPending) {
        if (closing || approvalDialog || !desktopRpcCanApprove(owner.snapshot(), selected)) return
        val runtime = owner.current() ?: return
        lastOffered = selected
        approvalDialog = true
        val answer = try { showOptions("Authenticated client fingerprint:\n${selected.fingerprint}\nOrigin: ${selected.origin}\n" +
                "Compare with the client display. Approval saves this identity, not a name or address.",
            "Client requests approval", arrayOf("Approve exact identity", "Reject", "Later"))
        } finally { approvalDialog = false }
        if (answer !in 0..1 || closing || !owner.owns(runtime) || !desktopRpcCanApprove(owner.snapshot(), selected)) return
        action { current ->
            check(current === runtime)
            if (answer == 0) current.approve(selected) else current.reject(selected)
        }
    }

    /** Own only this section's dialog; close invalidates its result before disposing it. */
    private fun showOptions(
        message: Any, title: String, options: Array<String>, messageType: Int = JOptionPane.WARNING_MESSAGE,
    ): Int {
        if (closing || dialog != null) return -1
        val epoch = dialogEpoch
        val pane = JOptionPane(message, messageType, JOptionPane.DEFAULT_OPTION, null, options, options.last())
        val owned = pane.createDialog(this, title)
        dialog = owned
        return try {
            owned.isVisible = true
            if (closing || epoch !== dialogEpoch) -1 else options.indexOf(pane.value)
        } finally {
            if (dialog === owned) dialog = null
            owned.dispose()
        }
    }

    private fun action(block: suspend (DesktopRpcRuntime) -> Unit) {
        if (closing || !owner.action(block)) {
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
        networkRefresh = scope.launch {
            val result = runCatching { desktopRpcNetworks() }
            SwingUtilities.invokeLater {
                if (!closing) {
                    networks.model = DefaultComboBoxModel(result.getOrDefault(emptyList()).toTypedArray())
                    networks.selectedIndex = -1 // Hidden legacy diagnostic selector; normal startup always rescans.
                    subnets.text = ""
                    refreshing = false
                    outcome.text = if (result.isFailure) "Unable to inspect interfaces; no network changes were made."
                    else desktopRpcDiscoveryNetworkSummary(result.getOrThrow())
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
        if (dialog == null && !approvalDialog && windowActive && isShowing && snapshot.stage == DesktopRpcRunOwner.Stage.Ready) {
            requests.firstOrNull { it != lastOffered }?.let { request ->
                SwingUtilities.invokeLater { if (!closing && windowActive && isShowing) reviewPending(request) }
            }
        }
        renderButtons(snapshot)
    }

    private fun renderButtons(snapshot: DesktopRpcRunOwner.Snapshot = owner.snapshot()) {
        val idle = snapshot.stage in setOf(DesktopRpcRunOwner.Stage.Idle, DesktopRpcRunOwner.Stage.Stopped)
        val ready = snapshot.stage == DesktopRpcRunOwner.Stage.Ready && !closing
        listOf(networks, subnets, port, host, client, refresh).forEach {
            it.isEnabled = idle && !closing && !refreshing && !unlocking && unlockCleanupFailure == null
        }
        if (System.getProperty("os.name").startsWith("Windows")) {
            host.isEnabled = false
            client.isEnabled = false
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

    /** Host focus only: an invitation cannot reappear after focus returns. Never changes network settings. */
    public fun onWindowFocusChanged(active: Boolean) {
        check(SwingUtilities.isEventDispatchThread())
        windowActive = active
        if (!active) clearInvitationText()
        if (!closing) render()
    }

    /** Toolbar, Swing Escape and programmatic section Back use this same policy. */
    public fun requestBack() {
        check(SwingUtilities.isEventDispatchThread())
        if (dialog != null) { dialogEpoch = Any(); dialog?.dispose(); return }
        if (!closing) onBackRequested()
    }

    /** Nonblocking, one-attempt close. Failed ownership remains visible and cannot be navigated away. */
    public fun requestClose(completed: (DesktopRpcCloseResult) -> Unit) {
        check(SwingUtilities.isEventDispatchThread())
        closeOwner.request(unlocking, completed, ::beginClose)
    }

    /**
     * Final application exit only. Conceals immediately, joins any actual unlock result, and subscribes to an
     * already-running Back close. Completion is delivered on the EDT only after the panel job tree is drained.
     * A failed physical close stays failed and is never retried; the application owns the terminal deadline.
     */
    public fun requestTerminalClose(completed: (DesktopRpcCloseResult) -> Unit) {
        check(SwingUtilities.isEventDispatchThread())
        concealForClose()
        closeOwner.requestTerminal(completed, ::beginClose)
    }

    private fun concealForClose() {
        closing = true
        windowActive = false
        dialogEpoch = Any()
        dialog?.dispose()
        requestHistory.closeInspection()
        clearSensitive()
        workspaceScroll.isVisible = false
        renderButtons()
    }

    private fun beginClose(finish: (DesktopRpcCloseResult) -> Unit) {
        concealForClose()
        statusUpdates?.cancel()
        val stopped = owner.stop()
        add(state, BorderLayout.NORTH)
        state.text = "Closing RPC and its protected profile…"
        var failure: Throwable? = null
        var physicalFinished = false
        fun retain(caught: Throwable?) {
            if (caught == null) return
            if (failure == null) failure = caught
            else if (failure !== caught && failure.suppressed.none { it === caught }) failure.addSuppressed(caught)
        }
        val work = scope.launch(start = CoroutineStart.LAZY) {
            suspend fun attempt(action: suspend () -> Unit) {
                try { action() } catch (caught: Throwable) { retain(caught) }
            }
            attempt { networkRefresh?.cancelAndJoin() }
            attempt { statusUpdates?.join() }
            // Do not cancel a native unlock or lose its successful late profile. No role can start while closing.
            attempt { unlockTask?.join() }
            retain(unlockTask?.completionFailure)
            retain(unlockCleanupFailure)
            retain(unlockTask?.attempt?.cleanupFailure)
            var roleRetired = false
            attempt {
                val roleFailure = stopped.await()
                retain(roleFailure)
                roleRetired = roleFailure == null
            }
            // The worker's captured profile remains owned even if its EDT delivery failed before publication.
            val acquiredProfile = profile ?: unlockTask?.attempt?.result?.getOrNull()
            if (roleRetired) attempt { acquiredProfile?.close() }
            physicalFinished = true
        }
        work.invokeOnCompletion { cause ->
            retain(cause)
            if (!physicalFinished) retain(IllegalStateException("RPC physical cleanup did not return an outcome"))
            val expected = CancellationException("RPC panel retirement completed")
            val drain = DesktopRpcPanelDrainCompletion(failure, expected) { finalFailure ->
                SwingUtilities.invokeLater {
                    closeFailure = finalFailure
                    val result = if (finalFailure == null) DesktopRpcCloseResult.Closed
                        else DesktopRpcCloseResult.Failed
                    if (result == DesktopRpcCloseResult.Closed) {
                        profile = null
                        removeAll()
                    } else {
                        state.text = "Cleanup failed; RPC ownership retained. Navigation is blocked."
                        revalidate()
                        repaint()
                    }
                    finish(result)
                }
            }
            scopeJob.invokeOnCompletion { parentCause ->
                drain.scopeCompleted(parentCause)
                owner.invokeOnRetirement(drain::ownersCompleted)
            }
            var cancellationFailure: Throwable? = null
            try { scope.cancel(expected) } catch (caught: Throwable) { cancellationFailure = caught }
            finally { drain.cancellationReturned(cancellationFailure) }
        }
        work.start()
    }

    override fun addNotify() {
        super.addNotify()
        windowActive = SwingUtilities.getWindowAncestor(this)?.isActive == true
        SwingUtilities.invokeLater {
            if (!closing && isDisplayable) workspaceScroll.viewport.viewPosition = Point(0, 0)
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
    JPanel(DesktopRpcWrapLayout()).apply {
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
