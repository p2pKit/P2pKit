package dev.p2pkit.core.internal

import dev.p2pkit.core.AppId
import dev.p2pkit.core.FeatureState
import dev.p2pkit.core.P2pError
import dev.p2pkit.core.P2pState
import dev.p2pkit.core.permission.NoOpP2pPermissionManager
import dev.p2pkit.core.permission.P2pPermission
import dev.p2pkit.core.permission.P2pPermissionManager
import dev.p2pkit.core.testfixtures.FakeDataTransport
import dev.p2pkit.core.testfixtures.FakeDiscoveryTransport
import dev.p2pkit.core.testfixtures.createTestKit
import dev.p2pkit.core.transport.TransportContext
import dev.p2pkit.core.transport.TransportFactory
import dev.p2pkit.core.transport.TransportPair
import kotlinx.coroutines.runBlocking
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertTrue

/**
 * Pins the permission-gate contract after the AUDIT-2026-06 permission-gate
 * regression fix:
 *
 * 1. The **default** permission path reports zero missing runtime permissions,
 *    so `startAdvertising()`/`startDiscovery()` are never gated out of the
 *    box. Core LAN needs no runtime-requestable permission on any shipped
 *    platform — Android's Wi-Fi permissions are install-time (normal) and
 *    must not appear on the runtime-request surface.
 * 2. The gate mechanism itself stays intact: a manager that reports genuinely
 *    missing runtime permissions (the provisioning sidecar's
 *    `AndroidP2pPermissionManager` reports `NEARBY_WIFI_DEVICES` /
 *    `ACCESS_FINE_LOCATION`) still makes both entry points throw
 *    [P2pError.PermissionMissing] before any transport is touched.
 * 3. The gate keys on **missing**, not **required**: required-but-granted
 *    permissions never block.
 *
 * A common pure seam pins the exact four-permission manifest diagnostic while
 * the remaining tests pin the runtime gate. Physical-device evidence still
 * verifies PackageManager/logcat behavior: omit each documented normal
 * permission in turn after `P2pKitAndroid.initialize(context)`; construction
 * must warn, while startAdvertising()/startDiscovery() remain ungated because
 * no runtime prompt can grant a missing manifest declaration.
 */
class PermissionGateTest {

    @Test
    fun androidManifestDiagnosticCoversEveryDocumentedInstallTimePermission() {
        assertEquals(
            listOf(
                "android.permission.INTERNET",
                "android.permission.ACCESS_NETWORK_STATE",
                "android.permission.ACCESS_WIFI_STATE",
                "android.permission.CHANGE_WIFI_MULTICAST_STATE"
            ),
            androidLanManifestPermissions
        )
    }

    @Test
    fun noOpManagerReportsNoRuntimePermissions() {
        runBlocking {
            val manager = NoOpP2pPermissionManager()
            assertTrue(manager.requiredPermissions().isEmpty(), "NoOp must require no runtime permissions")
            assertTrue(manager.missingPermissions().isEmpty(), "NoOp must report no missing permissions")
            assertTrue(manager.hasRequiredPermissions(), "NoOp must report all permissions granted")
        }
    }

    @Test
    fun defaultPermissionPathDoesNotGateStartAdvertisingOrDiscovery() {
        runBlocking {
            val discovery = FakeDiscoveryTransport()
            // No permissionManager override: exercises the platform default
            // (NoOp on the JVM/iOS targets this common test runs on; the
            // Android default reports the same empty set — see the manual
            // recipe in the class KDoc).
            val kit = createTestKit {
                appId = AppId("permission-gate-test")
                deviceName = "Default"
                transports { register(FixedTransportFactory(FakeDataTransport(), discovery)) }
            }

            assertTrue(
                kit.permissions.missingPermissions().isEmpty(),
                "Default permission manager must report no missing runtime permissions"
            )
            // The regression made these throw P2pError.PermissionMissing.
            kit.startAdvertising()
            kit.startDiscovery()
            assertEquals(1, discovery.startAdvertisingCalls, "advertising should have reached the transport")
            assertEquals(1, discovery.startDiscoveryCalls, "discovery should have reached the transport")
            assertEquals(FeatureState.Active, kit.advertisingState.value)
            assertEquals(FeatureState.Active, kit.discoveryState.value)

            kit.stop()
        }
    }

    @Test
    fun missingRuntimePermissionStillGatesBothEntryPoints() {
        runBlocking {
            val discovery = FakeDiscoveryTransport()
            val kit = createTestKit {
                appId = AppId("permission-gate-test")
                deviceName = "Gated"
                // Mirrors the provisioning sidecar: a real runtime permission
                // reported as missing must keep gating.
                permissionManager = FixedPermissionManager(
                    required = listOf(P2pPermission.NearbyWifiDevices),
                    missing = listOf(P2pPermission.NearbyWifiDevices)
                )
                transports { register(FixedTransportFactory(FakeDataTransport(), discovery)) }
            }

            val advertiseError = assertFailsWith<P2pError.PermissionMissing> { kit.startAdvertising() }
            assertEquals(listOf(P2pPermission.NearbyWifiDevices), advertiseError.permissions)
            val discoveryError = assertFailsWith<P2pError.PermissionMissing> { kit.startDiscovery() }
            assertEquals(listOf(P2pPermission.NearbyWifiDevices), discoveryError.permissions)
            assertEquals(0, discovery.startAdvertisingCalls, "gated advertising must never reach the transport")
            assertEquals(0, discovery.startDiscoveryCalls, "gated discovery must never reach the transport")
            assertEquals(
                FeatureState.PermissionRequired(listOf(P2pPermission.NearbyWifiDevices)),
                kit.advertisingState.value
            )
            assertEquals(
                FeatureState.PermissionRequired(listOf(P2pPermission.NearbyWifiDevices)),
                kit.discoveryState.value
            )
            assertEquals(P2pState.Idle, kit.state.value)

            kit.stop()
        }
    }

    @Test
    fun requiredButGrantedPermissionsDoNotGate() {
        runBlocking {
            val discovery = FakeDiscoveryTransport()
            val kit = createTestKit {
                appId = AppId("permission-gate-test")
                deviceName = "Granted"
                permissionManager = FixedPermissionManager(
                    required = listOf(P2pPermission.NearbyWifiDevices),
                    missing = emptyList()
                )
                transports { register(FixedTransportFactory(FakeDataTransport(), discovery)) }
            }

            // The gate keys on missingPermissions(), not requiredPermissions().
            kit.startAdvertising()
            kit.startDiscovery()
            assertEquals(1, discovery.startAdvertisingCalls)
            assertEquals(1, discovery.startDiscoveryCalls)
            assertEquals(FeatureState.Active, kit.advertisingState.value)
            assertEquals(FeatureState.Active, kit.discoveryState.value)

            kit.stop()
        }
    }
}

private class FixedTransportFactory(
    private val data: FakeDataTransport,
    private val discovery: FakeDiscoveryTransport
) : TransportFactory {
    override val descriptor =
        dev.p2pkit.core.transport.TransportDescriptor.dataAndDiscovery(data.type)
    override fun build(context: TransportContext): TransportPair =
        TransportPair(data = data, discovery = discovery)
}

/** Reports a fixed required/missing set — stands in for a sidecar manager. */
private class FixedPermissionManager(
    private val required: List<P2pPermission>,
    private val missing: List<P2pPermission>
) : P2pPermissionManager {
    override suspend fun requiredPermissions(): List<P2pPermission> = required
    override suspend fun missingPermissions(): List<P2pPermission> = missing
    override suspend fun hasRequiredPermissions(): Boolean = missing.isEmpty()
}
