package dev.p2pkit.sample.android.rpclab

import dev.p2pkit.sample.rpc.RpcPhoneSettings
import java.io.File
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertFalse
import kotlin.test.assertNull
import kotlin.test.assertTrue

class RpcLabNetworkSetupTest {
    private val first = RpcLabWifiNetwork(101, "wlan0", 9, "192.168.7.26", "192.168.7.0/24")
    private val second = first.copy(networkHandle = 102, localAddress = "192.168.8.26", subnet = "192.168.8.0/24")
    private fun available(network: RpcLabWifiNetwork = first) = RpcLabWifiObservation.Available(network, "synthetic")

    private class Wifi(var current: RpcLabWifiObservation) : RpcLabWifiObserving {
        val callbacks = mutableListOf<(RpcLabWifiObservation) -> Unit>()
        var stops = 0
        var failStart = false
        var failStop = false
        override fun start(changed: (RpcLabWifiObservation) -> Unit) {
            check(!failStart)
            callbacks += changed
            changed(current)
        }
        override fun currentObservation() = current
        override fun stop() { stops++; check(!failStop) }
        fun emit(observation: RpcLabWifiObservation) { current = observation; callbacks.last()(observation) }
    }

    private inner class Fixture {
        val wifi = Wifi(available())
        var idle = true
        var invalidations = 0
        val setup = RpcLabNetworkSetup(wifi, { idle }, { invalidations++ })
        init { setup.setForeground(true) }
    }

    @Test
    fun confirmationCopiesTheExactObservedNetworkButDoesNotChooseOrStartARole() {
        val f = Fixture()
        assertEquals(RpcLabNetworkFields(), f.setup.state.value.fields)
        assertFalse(f.setup.state.value.wifiApproved)
        assertTrue(f.setup.canConfirm)
        val unconfirmed = assertFailsWith<RpcLabSetupException> { f.setup.settingsForStart("48123") }
        assertTrue(checkNotNull(unconfirmed.message).contains("Use this Wi-Fi"))
        assertTrue(f.setup.confirm())
        val settings = f.setup.settingsForStart("48123")
        assertEquals(first.subnet, settings.subnets)
        assertEquals(first.interfaceName, settings.interfaceName)
        assertEquals(first.localAddress, settings.localAddress)
        assertEquals(48123, settings.port)
        assertTrue(f.setup.state.value.wifiApproved)
        assertFalse(f.setup.canConfirm)
        assertEquals(0, f.invalidations)
    }

    @Test
    fun confirmRereadsTheCurrentNetworkInsteadOfApprovingAStaleCallback() {
        val f = Fixture()
        f.wifi.current = available(second)
        assertFalse(f.setup.confirm())
        assertNull(f.setup.state.value.approved)
        assertEquals(second, f.setup.state.value.observation.network)
        assertEquals(RpcLabNetworkFields(), f.setup.state.value.fields)
        assertTrue(f.setup.confirm())
        assertEquals(second, f.setup.state.value.approved)
    }

    @Test
    fun startupRechecksNetworkIdentityInterfaceAddressPrefixAndAvailability() {
        for (changed in listOf(available(second), available(first.copy(networkHandle = 102)),
            available(first.copy(interfaceIndex = 10)), available(first.copy(interfaceName = "wlan1")),
            available(first.copy(subnet = "192.168.6.0/23")),
            RpcLabWifiObservation.Unavailable(RpcLabWifiIssue.NoDefaultNetwork))) {
            val f = Fixture()
            assertTrue(f.setup.confirm())
            f.wifi.current = changed
            assertFailsWith<RpcLabSetupException> { f.setup.settingsForStart("48123") }
            assertNull(f.setup.state.value.approved)
            assertEquals(RpcLabNetworkFields(), f.setup.state.value.fields)
            assertEquals(1, f.invalidations)
        }
    }

    @Test
    fun backgroundClearsConfirmationAndRejectsRetiredCallbacksAfterForegroundReturns() {
        val f = Fixture()
        val old = f.wifi.callbacks.single()
        assertTrue(f.setup.confirm())
        f.setup.setForeground(false)
        assertEquals(1, f.wifi.stops)
        assertNull(f.setup.state.value.approved)
        assertEquals(RpcLabNetworkFields(), f.setup.state.value.fields)
        assertFailsWith<RpcLabSetupException> { f.setup.settingsForStart("48123") }
        old(available(second))
        assertEquals(RpcLabWifiObservation.Checking, f.setup.state.value.observation)
        f.setup.setForeground(true)
        old(available(second))
        assertEquals(first, f.setup.state.value.observation.network)
        assertFalse(f.setup.state.value.wifiApproved)
        assertEquals(2, f.wifi.callbacks.size)
        f.setup.close()
        assertEquals(2, f.wifi.stops)
    }

    @Test
    fun passiveRefreshRetiresTheGenerationAndRequiresAnotherExplicitConfirmation() {
        val f = Fixture()
        assertTrue(f.setup.confirm())
        val old = f.wifi.callbacks.single()
        f.setup.refresh()
        assertEquals(1, f.wifi.stops)
        assertEquals(2, f.wifi.callbacks.size)
        assertFalse(f.setup.state.value.wifiApproved)
        assertEquals(RpcLabNetworkFields(), f.setup.state.value.fields)
        old(available(second))
        assertEquals(first, f.setup.state.value.observation.network)
        assertFailsWith<RpcLabSetupException> { f.setup.settingsForStart("48123") }
        assertEquals(0, f.invalidations)
    }

    @Test
    fun switchingModesCannotTurnAnOldSuggestionOrManualValueIntoAutomaticApproval() {
        val f = Fixture()
        assertTrue(f.setup.confirm())
        f.setup.setManual(true)
        assertEquals(RpcLabNetworkFields(), f.setup.state.value.fields)
        assertNull(f.setup.state.value.approved)
        val manual = RpcLabNetworkFields(second.subnet, second.interfaceName, second.localAddress)
        f.setup.editManual(manual)
        assertEquals(manual.localAddress, f.setup.settingsForStart("48123").localAddress)
        f.setup.setManual(false)
        assertEquals(RpcLabNetworkFields(), f.setup.state.value.fields)
        assertFailsWith<RpcLabSetupException> { f.setup.settingsForStart("48123") }
        assertTrue(f.setup.confirm())
        assertEquals(first.localAddress, f.setup.settingsForStart("48123").localAddress)
    }

    @Test
    fun manualSettingsStaySeparateFromWifiChangesRefreshAndBackground() {
        val f = Fixture()
        f.setup.setManual(true)
        val fields = RpcLabNetworkFields("fd42::/64", "wlan2", "fd42::2")
        f.setup.editManual(fields)
        f.wifi.emit(RpcLabWifiObservation.Unavailable(RpcLabWifiIssue.NotWifi))
        f.setup.refresh()
        assertFalse(f.setup.confirm())
        assertEquals(fields, f.setup.state.value.fields)
        assertEquals(0, f.wifi.stops)
        assertEquals(0, f.invalidations)
        f.setup.setForeground(false)
        f.setup.setForeground(true)
        assertEquals(fields, f.setup.state.value.fields)
        assertEquals(fields.localAddress, f.setup.settingsForStart("48123").localAddress)
    }

    @Test
    fun anOccupiedRuntimePreventsNetworkConfirmationRefreshAndModeOrInputChanges() {
        val f = Fixture()
        f.idle = false
        val before = f.setup.state.value
        assertFalse(f.setup.canConfigure)
        assertFalse(f.setup.canConfirm)
        assertFalse(f.setup.confirm())
        f.setup.refresh()
        f.setup.setManual(true)
        f.setup.editManual(RpcLabNetworkFields("10.0.0.0/8", "wlan1", "10.0.0.2"))
        assertEquals(before, f.setup.state.value)
        assertEquals(0, f.wifi.stops)
        assertEquals(1, f.wifi.callbacks.size)
    }

    @Test
    fun usbSessionLoadingIsExplicitManualConfigurationNeverWifiConfirmation() {
        val f = Fixture()
        assertTrue(f.setup.confirm())
        val settings = RpcPhoneSettings(second.subnet, second.interfaceName, second.localAddress, 48123)
        f.setup.loadSession(settings)
        assertTrue(f.setup.state.value.manual)
        assertTrue(f.setup.state.value.sessionLocked)
        assertNull(f.setup.state.value.approved)
        assertFalse(f.setup.canConfirm)
        assertFalse(f.setup.canConfigure)
        f.setup.setManual(false)
        f.setup.editManual(RpcLabNetworkFields())
        f.setup.refresh()
        assertEquals(second.localAddress, f.setup.settingsForStart("48123").localAddress)
        assertFailsWith<IllegalStateException> { f.setup.loadSession(settings) }
        f.idle = false
        f.setup.clearSession()
        assertTrue(f.setup.state.value.sessionLocked)
        f.idle = true
        f.setup.clearSession()
        assertTrue(f.setup.canConfigure)
        assertFalse(f.setup.state.value.sessionLocked)
        assertEquals(0, f.invalidations)
    }

    @Test
    fun missingInvalidManualFieldsAndInvalidPortsHaveActionableFixedErrors() {
        val f = Fixture()
        f.setup.setManual(true)
        val missing = assertFailsWith<RpcLabSetupException> { f.setup.settingsForStart("48123") }
        assertTrue(checkNotNull(missing.message).contains("Advanced → Manual network settings"))
        assertTrue(checkNotNull(missing.message).contains("approved private CIDRs, Wi-Fi interface"))
        val good = RpcLabNetworkFields(first.subnet, first.interfaceName, first.localAddress)
        f.setup.editManual(good)
        for (port in listOf("", "1023", "65536", "48123\n", "+48123", "port")) {
            val error = assertFailsWith<RpcLabSetupException> { f.setup.settingsForStart(port) }
            assertTrue(checkNotNull(error.message).contains("1024 to 65535"))
        }
        for (bad in listOf(good.copy(subnets = "0.0.0.0/0"), good.copy(interfaceName = "tun0"),
            good.copy(localAddress = "example.invalid"))) {
            f.setup.editManual(bad)
            val error = assertFailsWith<RpcLabSetupException> { f.setup.settingsForStart("48123") }
            assertTrue(checkNotNull(error.message).startsWith("Invalid private network settings."))
            assertFalse(checkNotNull(error.message).contains("example.invalid"))
        }
    }

    @Test
    fun identicalObservationsRetainConfirmationButAChangedNetworkInvalidatesOnlyOnce() {
        val f = Fixture()
        assertTrue(f.setup.confirm())
        f.wifi.emit(RpcLabWifiObservation.Available(first, "different diagnostic details"))
        assertTrue(f.setup.state.value.wifiApproved)
        assertEquals(0, f.invalidations)
        f.wifi.emit(available(second))
        assertFalse(f.setup.state.value.wifiApproved)
        assertEquals(1, f.invalidations)
        f.wifi.emit(available(second))
        assertEquals(1, f.invalidations)
    }

    @Test
    fun observerFailuresRemainVisibleAndDoNotStartNewObserversUntilRetirementSucceeds() {
        val f = Fixture()
        assertTrue(f.setup.confirm())
        f.wifi.failStop = true
        f.setup.refresh()
        assertEquals(1, f.wifi.callbacks.size)
        assertFalse(f.setup.canConfirm)
        assertFalse(f.setup.state.value.wifiApproved)
        assertEquals(RpcLabWifiIssue.ObservationFailed,
            (f.setup.state.value.observation as RpcLabWifiObservation.Unavailable).issue)
        f.wifi.failStop = false
        f.wifi.failStart = true
        f.setup.refresh()
        assertFalse(f.setup.canConfirm)
        f.wifi.failStart = false
        f.setup.refresh()
        assertTrue(f.setup.canConfirm)
        assertEquals(2, f.wifi.callbacks.size)
    }

    @Test
    fun boundedAppSwitchKeepsOnlyTheSameApprovedNetworkAndDoesNotStartANewObservation() {
        val f = Fixture()
        assertTrue(f.setup.confirm())
        assertTrue(f.setup.beginAppSwitch())
        assertFalse(f.setup.state.value.foreground)
        assertTrue(f.setup.state.value.wifiApproved)
        assertFalse(f.setup.canConfirm)
        assertFalse(f.setup.canConfigure)
        assertFailsWith<RpcLabSetupException> { f.setup.settingsForStart("48123") }
        f.wifi.emit(available())
        assertTrue(f.setup.resumeAppSwitch())
        assertTrue(f.setup.state.value.foreground)
        assertTrue(f.setup.state.value.wifiApproved)
        assertEquals(1, f.wifi.callbacks.size)
        assertEquals(0, f.wifi.stops)
        assertEquals(0, f.invalidations)
    }

    @Test
    fun networkChangesAreStillObservedAndInvalidateDuringTheBoundedAppSwitch() {
        val f = Fixture()
        assertTrue(f.setup.confirm())
        assertTrue(f.setup.beginAppSwitch())
        f.wifi.emit(available(second))
        assertFalse(f.setup.state.value.wifiApproved)
        assertEquals(1, f.invalidations)
        assertFalse(f.setup.resumeAppSwitch())
        assertEquals(1, f.invalidations)
        assertFalse(f.setup.state.value.wifiApproved)
    }

    @Test
    fun appSwitchEntryAndReturnSynchronouslyRejectAChangedNetworkWithoutWaitingForACallback() {
        val before = Fixture()
        assertTrue(before.setup.confirm())
        before.wifi.current = available(second)
        assertFalse(before.setup.beginAppSwitch())
        assertEquals(1, before.invalidations)
        val after = Fixture()
        assertTrue(after.setup.confirm())
        assertTrue(after.setup.beginAppSwitch())
        after.wifi.current = available(second)
        assertFalse(after.setup.resumeAppSwitch())
        assertFalse(after.setup.state.value.wifiApproved)
        assertEquals(1, after.invalidations)
    }

    @Test
    fun unconfirmedManualAndCapacitySessionsCannotGetTheWifiLeaseAndExpiryRetiresCallbacks() {
        val f = Fixture()
        assertFalse(f.setup.beginAppSwitch())
        f.setup.setManual(true)
        f.setup.editManual(RpcLabNetworkFields(first.subnet, first.interfaceName, first.localAddress))
        assertFalse(f.setup.beginAppSwitch())
        f.setup.loadSession(RpcPhoneSettings(first.subnet, first.interfaceName, first.localAddress, 48123))
        assertFalse(f.setup.beginAppSwitch())
        val ordinary = Fixture()
        assertTrue(ordinary.setup.confirm())
        assertTrue(ordinary.setup.beginAppSwitch())
        val old = ordinary.wifi.callbacks.single()
        ordinary.setup.close()
        old(available(second))
        assertFalse(ordinary.setup.resumeAppSwitch())
        assertNull(ordinary.setup.state.value.approved)
        assertEquals(RpcLabWifiObservation.Checking, ordinary.setup.state.value.observation)
        assertEquals(1, ordinary.wifi.stops)
    }

    @Test
    fun automaticStartUsesCurrentObservationInsideTheActionGateWithoutConfirmationOrFixedPort() {
        val f = Fixture()
        f.idle = false // The Activity has already acquired its action gate, not a runtime.
        f.wifi.current = available(second)
        val settings = f.setup.settingsForAutomaticStart()
        assertEquals("Private Wi-Fi detected. Choose Host or Client; peer approval is separate.",
            f.setup.state.value.automaticExplanation)
        assertEquals(second.subnet, settings.subnets)
        assertEquals(second.localAddress, settings.localAddress)
        assertEquals(second.interfaceName, settings.interfaceName)
        assertEquals(0, settings.port)
        assertTrue(f.setup.state.value.wifiApproved)
        assertTrue(f.setup.beginAppSwitch())
        f.wifi.emit(available(first))
        assertEquals(1, f.invalidations)
        assertFalse(f.setup.resumeAppSwitch())
    }

    @Test
    fun automaticStartFailsClosedForMissingNetworkManualSessionAndBackground() {
        val missing = Fixture()
        missing.wifi.current = RpcLabWifiObservation.Unavailable(RpcLabWifiIssue.NoDefaultNetwork)
        assertFailsWith<RpcLabSetupException> { missing.setup.settingsForAutomaticStart() }
        assertNull(missing.setup.state.value.approved)
        val manual = Fixture()
        manual.setup.setManual(true)
        assertFailsWith<RpcLabSetupException> { manual.setup.settingsForAutomaticStart() }
        val usb = Fixture()
        usb.setup.loadSession(RpcPhoneSettings(first.subnet, first.interfaceName, first.localAddress, 48123))
        assertFailsWith<RpcLabSetupException> { usb.setup.settingsForAutomaticStart() }
        val background = Fixture()
        background.setup.setForeground(false)
        assertFailsWith<RpcLabSetupException> { background.setup.settingsForAutomaticStart() }
    }

    @Test
    fun actualActivityChecksSetupBeforePermissionOrFactoryAndKeepsRefreshAwayFromOtherInputs() {
        val relative = "src/debug/java/dev/p2pkit/sample/android/rpclab/RpcLabActivity.kt"
        val source = generateSequence(File(checkNotNull(System.getProperty("user.dir")))) { it.parentFile }
            .flatMap { sequenceOf(File(it, relative), File(it, "samples/p2p-sample-android/$relative")) }
            .first(File::isFile).readText()
        val start = source.substringAfter("private fun start(").substringBefore("private fun loadMobile(")
        val validation = start.indexOf("networkSetup.settingsForStart(port)")
        val permissions = start.indexOf("requestPermissions(")
        val factory = start.indexOf("runtimeOwner.beginCreation(")
        assertTrue(validation >= 0 && permissions > validation && factory > permissions)
        assertTrue(start.contains("catch (problem: RpcLabSetupException)"))
        val refresh = source.substringAfter("if (!networkSetup.canRefresh) return@TextButton")
            .substringBefore("enabled = networkSetup.canRefresh")
        assertTrue(refresh.contains("networkSetup.refresh()"))
        for (unrelated in listOf("invitation =", "capacityPins =", "usbRunLabel =", "importApproved =", "start(")) {
            assertFalse(refresh.contains(unrelated))
        }
        assertTrue(source.contains("networkSetup.setForeground(false)"))
        assertTrue(source.substringAfter("override fun onDestroy()").substringBefore("private fun presentStartProblem")
            .contains("networkSetup.close()"))
        assertTrue(source.contains("runtimeOwner.snapshotFor(ownedToken)?.let { stop(it) }"))
        assertTrue(source.contains("title = { Text(\"Cannot start RPC\") }"))
        assertTrue(source.contains("if (showAdvanced) {"))
        assertTrue(source.contains("Text(\"Start client\")"))
    }
}
