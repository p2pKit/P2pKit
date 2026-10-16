package dev.p2pkit.sample.android.rpclab

import dev.p2pkit.sample.rpc.RpcPhoneSettings
import dev.p2pkit.transport.lan.OrganizationLan
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow

internal data class RpcLabNetworkFields(
    val subnets: String = "",
    val interfaceName: String = "",
    val localAddress: String = "",
)

internal data class RpcLabNetworkState(
    val foreground: Boolean = false,
    val manual: Boolean = false,
    val sessionLocked: Boolean = false,
    val observation: RpcLabWifiObservation = RpcLabWifiObservation.Checking,
    val approved: RpcLabWifiNetwork? = null,
    val fields: RpcLabNetworkFields = RpcLabNetworkFields(),
) {
    val automaticExplanation: String get() = if (observation.network == null) observation.explanation
        else "Private Wi-Fi detected. Choose Host or Client; peer approval is separate."

    val wifiApproved: Boolean get() = !manual && approved != null && approved == observation.network &&
        fields == RpcLabNetworkFields(approved.subnet, approved.interfaceName, approved.localAddress)
}

internal class RpcLabSetupException(message: String) : IllegalArgumentException(message)

/** Main-thread controller. Approval belongs to one observed network and one foreground generation. */
internal class RpcLabNetworkSetup(
    private val wifi: RpcLabWifiObserving,
    private val idle: () -> Boolean,
    private val invalidated: () -> Unit,
) {
    private val mutable = MutableStateFlow(RpcLabNetworkState())
    val state = mutable.asStateFlow()
    private var generation: Any? = null
    private var appSwitch = false
    val canConfigure: Boolean get() = state.value.foreground && idle() && !state.value.sessionLocked
    val canRefresh: Boolean get() = canConfigure && !state.value.manual
    val canConfirm: Boolean get() = canRefresh && state.value.observation.network != null && !state.value.wifiApproved

    fun setForeground(active: Boolean) {
        if (state.value.foreground == active) return
        mutable.value = state.value.copy(foreground = active)
        if (active) startObservation() else close()
    }

    /** Retain only the explicitly confirmed, still-identical automatic Wi-Fi while the OS lease is held. */
    fun beginAppSwitch(): Boolean {
        if (!state.value.foreground || state.value.sessionLocked || !state.value.wifiApproved) return false
        receive(wifi.currentObservation())
        if (!state.value.wifiApproved) return false
        appSwitch = true
        mutable.value = state.value.copy(foreground = false)
        return true
    }

    fun resumeAppSwitch(): Boolean {
        if (!appSwitch) return false
        receive(wifi.currentObservation())
        appSwitch = false
        mutable.value = state.value.copy(foreground = true)
        return state.value.wifiApproved
    }

    fun close() {
        appSwitch = false
        generation = null
        clearApproval()
        mutable.value = state.value.copy(foreground = false, observation = RpcLabWifiObservation.Checking)
        stopObservation()
    }

    fun refresh() {
        if (!canRefresh) return
        generation = null
        clearApproval()
        mutable.value = state.value.copy(observation = RpcLabWifiObservation.Checking)
        if (stopObservation()) startObservation()
    }

    fun setManual(manual: Boolean) {
        if (!canConfigure || manual == state.value.manual) return
        mutable.value = state.value.copy(manual = manual, approved = null, fields = RpcLabNetworkFields())
    }

    fun editManual(fields: RpcLabNetworkFields) {
        if (canConfigure && state.value.manual) mutable.value = state.value.copy(fields = fields)
    }

    /** Called only by the Activity's serialized, source-verified USB loader; loading never approves or starts RPC. */
    fun loadSession(settings: RpcPhoneSettings) {
        check(state.value.foreground && !state.value.sessionLocked)
        mutable.value = state.value.copy(manual = true, sessionLocked = true, approved = null,
            fields = RpcLabNetworkFields(settings.subnets, settings.interfaceName, settings.localAddress))
    }

    fun clearSession() {
        if (state.value.foreground && idle()) mutable.value = state.value.copy(sessionLocked = false)
    }

    fun confirm(): Boolean {
        if (!canConfirm) return false
        val suggested = state.value.observation.network
        receive(wifi.currentObservation())
        if (suggested == null || suggested != state.value.observation.network) return false
        mutable.value = state.value.copy(approved = suggested,
            fields = RpcLabNetworkFields(suggested.subnet, suggested.interfaceName, suggested.localAddress))
        return true
    }

    /** Called inside the Activity's owned action gate, before any permission request, factory or socket. */
    fun settingsForStart(port: String): RpcPhoneSettings {
        if (!state.value.foreground) throw RpcLabSetupException("Keep this app open before choosing an RPC role.")
        if (!state.value.manual) {
            receive(wifi.currentObservation())
            if (!state.value.wifiApproved) throw RpcLabSetupException(
                "Tap Use this Wi-Fi to confirm the detected network, then choose a role. " +
                    "Advanced offers manual setup if Wi-Fi cannot be detected safely. No role was started.",
            )
        }
        val fields = state.value.fields
        val missing = listOf("approved private CIDRs" to fields.subnets, "Wi-Fi interface" to fields.interfaceName,
            "this device's numeric LAN address" to fields.localAddress).filter { it.second.isBlank() }.map { it.first }
        if (missing.isNotEmpty()) throw RpcLabSetupException(
            "Fill in ${missing.joinToString()} under Advanced → Manual network settings. No role was started.",
        )
        val number = port.toIntOrNull()
        if (number == null || number !in 1024..65535 || port.any { it !in '0'..'9' }) {
            throw RpcLabSetupException("Enter a fixed host port from 1024 to 65535 under Advanced. " +
                "No role was started.")
        }
        try {
            OrganizationLan(fields.subnets.split(',').map(String::trim), fields.interfaceName, fields.localAddress)
            return RpcPhoneSettings(fields.subnets, fields.interfaceName, fields.localAddress, number)
        } catch (_: IllegalArgumentException) {
            throw RpcLabSetupException("Invalid private network settings. Review the CIDRs, interface and numeric " +
                "LAN address under Advanced. No role was started.")
        }
    }

    /** Normal app start: select only the current eligible observation, not a stale suggestion or manual field. */
    fun settingsForAutomaticStart(): RpcPhoneSettings {
        if (!state.value.foreground || state.value.manual || state.value.sessionLocked) {
            throw RpcLabSetupException("Automatic LAN setup is unavailable in this lifecycle or test session.")
        }
        receive(wifi.currentObservation())
        val network = state.value.observation.network
            ?: throw RpcLabSetupException(state.value.observation.explanation + " No role was started.")
        try {
            OrganizationLan(listOf(network.subnet), network.interfaceName, network.localAddress)
            val settings = RpcPhoneSettings.automatic(network.subnet, network.interfaceName, network.localAddress)
            // Retain the observation for existing network-change and bounded app-switch guards; no peer is trusted.
            mutable.value = state.value.copy(approved = network,
                fields = RpcLabNetworkFields(network.subnet, network.interfaceName, network.localAddress))
            return settings
        } catch (_: IllegalArgumentException) {
            throw RpcLabSetupException("No eligible private LAN is available. No role was started.")
        }
    }

    private fun receive(observation: RpcLabWifiObservation) {
        val changed = state.value.approved?.let { it != observation.network } == true
        if (changed) clearApproval()
        mutable.value = state.value.copy(observation = observation)
        if (changed) invalidated()
    }

    private fun clearApproval() {
        mutable.value = state.value.copy(approved = null,
            fields = if (state.value.manual) state.value.fields else RpcLabNetworkFields())
    }

    private fun startObservation() {
        val token = Any()
        generation = token
        try {
            wifi.start { observation ->
                if ((state.value.foreground || appSwitch) && generation === token) receive(observation)
            }
        } catch (_: Exception) {
            generation = null
            receive(RpcLabWifiObservation.Unavailable(RpcLabWifiIssue.ObservationFailed))
        }
    }

    private fun stopObservation(): Boolean = try {
        wifi.stop()
        true
    } catch (_: Exception) {
        mutable.value = state.value.copy(observation =
            RpcLabWifiObservation.Unavailable(RpcLabWifiIssue.ObservationFailed))
        false
    }
}
