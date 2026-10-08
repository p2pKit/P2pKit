package dev.p2pkit.sample.rpc.desktop

import dev.p2pkit.sample.rpc.RpcDiscoveryConnectionStatus
import dev.p2pkit.sample.rpc.RpcKnownDevice
import dev.p2pkit.sample.rpc.RpcNearbyHost
import java.awt.Component
import java.awt.FlowLayout
import javax.swing.DefaultListCellRenderer
import javax.swing.DefaultListModel
import javax.swing.JButton
import javax.swing.JLabel
import javax.swing.JList
import javax.swing.JPanel
import javax.swing.JScrollPane
import javax.swing.ListSelectionModel

/** EDT-only projection. Retain selections by exact pin, never choose the first discovery record. */
internal class DesktopRpcDiscoveryPanel(
    select: (RpcNearbyHost) -> Unit,
    forget: (RpcKnownDevice) -> Unit,
) : DesktopRpcColumn() {
    private val activity = DesktopRpcWrappedLabel("Network activity: not observed")
    private val connection = DesktopRpcWrappedLabel("Connection: no selected host")
    private val guidance = DesktopRpcWrappedLabel("")
    private var currentConnection: RpcDiscoveryConnectionStatus? = null
    private val hostModel = DefaultListModel<RpcNearbyHost>()
    private val hosts = JList(hostModel).apply {
        selectionMode = ListSelectionModel.SINGLE_SELECTION
        visibleRowCount = 4
        accessibleContext.accessibleName = "Nearby hosts; discovery names and presence are unverified"
        cellRenderer = renderer { row ->
            val host = row as? RpcNearbyHost
            host?.let { "${it.name} · ${it.platform} · " +
                "${if (it.trusted) "Trusted" else "Untrusted"} · ${it.fingerprint}" }
        }
    }
    private val choose = JButton("Select host / Request first-time approval")
    private val knownModel = DefaultListModel<RpcKnownDevice>()
    private val known = JList(knownModel).apply {
        selectionMode = ListSelectionModel.SINGLE_SELECTION
        visibleRowCount = 4
        accessibleContext.accessibleName = "Trusted devices and observed presence"
        cellRenderer = renderer { row ->
            (row as? RpcKnownDevice)?.let { "${it.name} · ${it.presence} · ${it.fingerprint}" }
        }
    }
    private val revoke = JButton("Revoke / Forget selected device")
    private var enabled = false
    private var client = false

    init {
        add(activity)
        add(connection)
        add(guidance)
        add(JLabel("<html>Nearby hosts — compare full fingerprints; " +
            "names and discovery presence are not authentication."))
        add(JScrollPane(hosts))
        add(JPanel(FlowLayout(FlowLayout.LEADING)).apply { add(choose) })
        add(DesktopRpcDisclosure("Trusted devices", DesktopRpcColumn().apply {
            add(JLabel("<html>Offline means no current observed presence, not a revoked identity."))
            add(JScrollPane(known))
            add(JPanel(FlowLayout(FlowLayout.LEADING)).apply { add(revoke) })
        }))
        hosts.addListSelectionListener { buttons() }
        known.addListSelectionListener { buttons() }
        choose.addActionListener { if (enabled && client) hosts.selectedValue?.let(select) }
        revoke.addActionListener { if (enabled) known.selectedValue?.let(forget) }
    }

    fun render(status: DesktopRpcStatus?, canAct: Boolean) {
        enabled = canAct
        client = status?.role == DesktopRpcRole.Client
        currentConnection = status?.connection
        guidance.show(currentConnection?.approvalGuidance.orEmpty())
        val network = "Network activity: ${status?.networkActivity ?: "Not observed"}"
        activity.show(network)
        val text = status?.connection?.let {
            "${it.state.name} · retry ${it.nextRetryMillis} ms · ${it.failure ?: "no connection error"}" +
                (it.selectedFingerprint?.let { pin -> " · selected: $pin" } ?: "")
        } ?: "No selected client host"
        connection.show(text)
        val nearby = status?.nearby.orEmpty()
        if ((0 until hostModel.size()).map { hostModel[it] } != nearby) {
            val selected = hosts.selectedValue?.fingerprint
            hostModel.clear()
            nearby.forEach(hostModel::addElement)
            hosts.selectedIndex = if (selected != null && nearby.count { it.fingerprint == selected } == 1)
                nearby.indexOfFirst { it.fingerprint == selected } else -1
        }
        val trusted = status?.trusted.orEmpty()
        if ((0 until knownModel.size()).map { knownModel[it] } != trusted) {
            val selected = known.selectedValue?.fingerprint
            knownModel.clear()
            trusted.forEach(knownModel::addElement)
            known.selectedIndex = trusted.indexOfFirst { it.fingerprint == selected }
        }
        buttons()
    }

    private fun buttons() {
        choose.isEnabled = enabled && client && hosts.selectedValue != null
        choose.text = hosts.selectedValue?.selectionLabel(currentConnection) ?: "Select a host identity"
        revoke.isEnabled = enabled && known.selectedValue != null
    }

    private fun renderer(text: (Any?) -> String?): DefaultListCellRenderer = object : DefaultListCellRenderer() {
        override fun getListCellRendererComponent(
            list: JList<*>?, value: Any?, index: Int, selected: Boolean, focus: Boolean,
        ): Component {
            // Disable BEFORE setText can parse HTML or load untrusted image references.
            putClientProperty("html.disable", true)
            return super.getListCellRendererComponent(list, text(value).orEmpty(), index, selected, focus)
        }
    }
}
