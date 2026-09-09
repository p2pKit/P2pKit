package dev.p2pkit.sample.android

import android.content.Context
import android.content.ContextWrapper
import android.content.pm.ApplicationInfo
import android.content.pm.PackageManager
import android.os.Build
import dev.p2pkit.core.AppId
import dev.p2pkit.core.FeatureState
import dev.p2pkit.core.NetworkPathObserver
import dev.p2pkit.core.NetworkPathStatus
import dev.p2pkit.core.P2pError
import dev.p2pkit.core.P2pKit
import dev.p2pkit.core.P2pState
import dev.p2pkit.core.SecurityMode
import dev.p2pkit.core.TransportKind
import dev.p2pkit.core.android.P2pKitAndroid
import dev.p2pkit.core.permission.NoOpP2pPermissionManager
import dev.p2pkit.core.permission.P2pPermission
import dev.p2pkit.core.permission.P2pPermissionManager
import dev.p2pkit.core.transport.DataTransport
import dev.p2pkit.core.transport.DiscoveryTransport
import dev.p2pkit.core.transport.InternalPeer
import dev.p2pkit.core.transport.LocalPeerInfo
import dev.p2pkit.core.transport.PeerEvent
import dev.p2pkit.core.transport.RawConnection
import dev.p2pkit.core.transport.TransportCapability
import dev.p2pkit.core.transport.TransportContext
import dev.p2pkit.core.transport.TransportDescriptor
import dev.p2pkit.core.transport.TransportFactory
import dev.p2pkit.core.transport.TransportPair
import java.io.File
import java.nio.file.Files
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertSame
import kotlin.test.assertTrue
import kotlinx.coroutines.NonCancellable
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withContext
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.RuntimeEnvironment
import org.robolectric.annotation.Config
import org.robolectric.util.ReflectionHelpers

/**
 * Actual Android default-factory and feature-gate coverage on the pinned Robolectric SDK35 host tier.
 * Only device-SDK/app-target policy inputs and permission-service responses are modeled: this is
 * NOT Android17 runtime, permission-dialog, socket, or authenticated-traffic evidence. The fixture
 * explicitly selects test-only legacy identity because this tier has no AndroidKeyStore; it does
 * not change the production authenticated default or substitute for its existing security tests.
 */
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [35], manifest = Config.NONE)
class DefaultLanPermissionTest {
    @Test
    fun sameDefaultManagerObservesDenyGrantRevokeBeforeActualFeatureWork() = runBlocking {
        withKit { fixture ->
            val kit = fixture.kit
            val manager = kit.permissions
            val preflight = SampleLanPermissionManager(fixture.context)
            val transport = fixture.factories.single().transport
            fixture.context.queries.clear()

            assertReported(manager, fixture.context, LOCAL_NETWORK, LOCAL_NETWORK)
            assertReported(preflight, fixture.context, LOCAL_NETWORK, LOCAL_NETWORK)
            assertFeatureDenied(kit)
            assertEquals(P2pState.Idle, kit.state.value)
            assertEquals(0, transport.dataStarts)
            assertEquals(0, transport.advertisingStarts)
            assertEquals(0, transport.discoveryStarts)
            assertEquals(0, fixture.observer.starts)

            fixture.context.granted = true
            assertReported(manager, fixture.context, LOCAL_NETWORK, emptyList())
            assertReported(preflight, fixture.context, LOCAL_NETWORK, emptyList())
            kit.startAdvertising()
            kit.startDiscovery()
            assertEquals(P2pState.Running, kit.state.value)
            assertEquals(FeatureState.Active, kit.advertisingState.value)
            assertEquals(FeatureState.Active, kit.discoveryState.value)
            assertEquals(1, transport.dataStarts)
            assertEquals(1, transport.advertisingStarts)
            assertEquals(1, transport.discoveryStarts)
            assertEquals(1, fixture.observer.starts)

            fixture.context.granted = false
            assertSame(manager, kit.permissions)
            assertReported(manager, fixture.context, LOCAL_NETWORK, LOCAL_NETWORK)
            assertReported(preflight, fixture.context, LOCAL_NETWORK, LOCAL_NETWORK)
            // An already-active start remains a no-op, not a live permission-status probe.
            val queriesBeforeActiveStarts = fixture.context.queries.size
            kit.startAdvertising()
            kit.startDiscovery()
            assertEquals(queriesBeforeActiveStarts, fixture.context.queries.size)
            kit.stopAdvertising()
            kit.stopDiscovery()
            // Revocation must not prevent cleanup, nor allow either fresh feature acquisition.
            assertFeatureDenied(kit)
            assertEquals(1, transport.dataStarts)
            assertEquals(1, transport.advertisingStarts)
            assertEquals(1, transport.discoveryStarts)
            assertEquals(1, fixture.observer.starts)
        }
    }

    @Test
    fun finalAppTargetDeviceSdkAndSelectedTransportAllConstrainTheDefault() = runBlocking {
        val cases = listOf(
            PolicyCase(37, 37, TransportKind.LAN, true),
            PolicyCase(38, 37, TransportKind.LAN, true),
            PolicyCase(37, 38, TransportKind.LAN, true),
            PolicyCase(37, 36, TransportKind.LAN, false),
            PolicyCase(36, 37, TransportKind.LAN, false),
            PolicyCase(36, 36, TransportKind.LAN, false),
            PolicyCase(24, 37, TransportKind.LAN, false),
            PolicyCase(37, 37, TransportKind.RELAY, false)
        )
        for (case in cases) {
            withKit(case.sdk, case.target, listOf(InertFactory(case.kind))) { fixture ->
                val expected = if (case.requiresLocalNetwork) LOCAL_NETWORK else emptyList()
                fixture.context.queries.clear()
                assertReported(fixture.kit.permissions, fixture.context, expected, expected)
                if (case.kind == TransportKind.LAN) {
                    assertReported(SampleLanPermissionManager(fixture.context), fixture.context, expected, expected)
                }
                if (!case.requiresLocalNetwork) {
                    fixture.kit.startAdvertising()
                    fixture.kit.startDiscovery()
                    assertEquals(1, fixture.factories.single().transport.dataStarts, case.toString())
                    assertTrue(fixture.context.queries.isEmpty(), case.toString())
                }
            }
        }
    }

    @Test
    fun explicitCustomManagerIsNotReplacedForAnExemptLanProvider() = runBlocking {
        val customManager = NoOpP2pPermissionManager()
        withKit(permissionOverride = customManager) { fixture ->
            assertSame(customManager, fixture.kit.permissions)
            assertReported(fixture.kit.permissions, fixture.context, emptyList(), emptyList())
            fixture.kit.startAdvertising()
            fixture.kit.startDiscovery()
            assertEquals(1, fixture.factories.single().transport.dataStarts)
            assertTrue(fixture.context.queries.isEmpty(), "An explicit override bypasses the default factory")
        }
    }

    @Test
    fun discoveryOnlyLanStillRequiresPermissionBeforeStartingOtherDataTransports() = runBlocking {
        val lan = InertFactory(TransportKind.LAN, hasData = false)
        val relay = InertFactory(TransportKind.RELAY, hasDiscovery = false)
        withKit(factories = listOf(lan, relay)) { fixture ->
            assertFeatureDenied(fixture.kit)
            assertEquals(P2pState.Idle, fixture.kit.state.value)
            assertEquals(0, relay.transport.dataStarts)
            assertEquals(0, lan.transport.advertisingStarts)
            assertEquals(0, lan.transport.discoveryStarts)
            fixture.context.granted = true
            fixture.kit.startAdvertising()
            fixture.kit.startDiscovery()
            assertEquals(1, relay.transport.dataStarts)
            assertEquals(1, lan.transport.advertisingStarts)
            assertEquals(1, lan.transport.discoveryStarts)
        }
    }

    @Test
    fun permissionServiceFailureIsNeverReportedAsAGrant() = runBlocking {
        withKit { fixture ->
            val failure = SecurityException("synthetic permission service failure")
            fixture.context.lookupFailure = failure
            for (manager in listOf(fixture.kit.permissions, SampleLanPermissionManager(fixture.context))) {
                assertEquals(LOCAL_NETWORK, manager.requiredPermissions())
                assertSame(failure, assertFailsWith<SecurityException> { manager.missingPermissions() })
                assertSame(failure, assertFailsWith<SecurityException> { manager.hasRequiredPermissions() })
            }
            assertEquals(0, fixture.factories.single().transport.dataStarts)
            assertEquals(P2pState.Idle, fixture.kit.state.value)
        }
    }

    private suspend fun assertReported(
        manager: P2pPermissionManager,
        context: PermissionContext,
        required: List<P2pPermission>,
        missing: List<P2pPermission>
    ) {
        val before = context.queries.size
        assertEquals(required, manager.requiredPermissions())
        assertEquals(before, context.queries.size, "Required permissions must not depend on the current grant")
        assertEquals(missing, manager.missingPermissions())
        assertEquals(missing.isEmpty(), manager.hasRequiredPermissions())
        val expectedQueries = if (required.isEmpty()) emptyList() else List(2) { LOCAL_NETWORK_PERMISSION }
        assertEquals(expectedQueries, context.queries.drop(before), "Each missing/has query must read the live grant")
    }

    private suspend fun assertFeatureDenied(kit: P2pKit) {
        assertEquals(
            LOCAL_NETWORK,
            assertFailsWith<P2pError.PermissionMissing> { kit.startAdvertising() }.permissions
        )
        assertEquals(
            LOCAL_NETWORK,
            assertFailsWith<P2pError.PermissionMissing> { kit.startDiscovery() }.permissions
        )
        assertEquals(FeatureState.PermissionRequired(LOCAL_NETWORK), kit.advertisingState.value)
        assertEquals(FeatureState.PermissionRequired(LOCAL_NETWORK), kit.discoveryState.value)
    }

    @Suppress("DEPRECATION") // Permission-only fixture; never opens a socket or changes production security defaults.
    private suspend fun withKit(
        sdk: Int = 37,
        target: Int = 37,
        factories: List<InertFactory> = listOf(InertFactory()),
        permissionOverride: P2pPermissionManager? = null,
        block: suspend (Fixture) -> Unit
    ) {
        val application = RuntimeEnvironment.getApplication()
        val originalSdk = Build.VERSION.SDK_INT
        val originalContext = ReflectionHelpers.getStaticField<Context?>(
            P2pKitAndroid::class.java, "registeredContext"
        )
        val files = Files.createTempDirectory("p2pkit-permission-only-").toFile()
        val context = PermissionContext(application, files, target)
        val observer = InertObserver()
        var kit: P2pKit? = null
        try {
            ReflectionHelpers.setStaticField(Build.VERSION::class.java, "SDK_INT", sdk)
            P2pKitAndroid.initialize(context)
            val created = P2pKit.create {
                appId = AppId(files.name)
                deviceName = "Synthetic permission fixture"
                security { mode = SecurityMode.NoneForMvp }
                lifecycle { networkPathObserver = observer }
                permissionManager = permissionOverride
                transports { factories.forEach { register(it) } }
            }
            kit = created
            assertTrue(factories.all { it.buildCalls == 1 })
            block(Fixture(created, context, observer, factories))
        } finally {
            try {
                withContext(NonCancellable) { kit?.stop() }
            } finally {
                try {
                    ReflectionHelpers.setStaticField(Build.VERSION::class.java, "SDK_INT", originalSdk)
                } finally {
                    try {
                        ReflectionHelpers.setStaticField(
                            P2pKitAndroid::class.java, "registeredContext", originalContext
                        )
                    } finally {
                        assertTrue(files.deleteRecursively(), "Remove only this fixture's temporary identity files")
                    }
                }
            }
        }
    }

    private data class PolicyCase(
        val sdk: Int,
        val target: Int,
        val kind: TransportKind,
        val requiresLocalNetwork: Boolean
    )

    private data class Fixture(
        val kit: P2pKit,
        val context: PermissionContext,
        val observer: InertObserver,
        val factories: List<InertFactory>
    )

    private class PermissionContext(base: Context, private val files: File, target: Int) : ContextWrapper(base) {
        private val info = ApplicationInfo(base.applicationInfo).apply { targetSdkVersion = target }
        val queries = mutableListOf<String>()
        var granted = false
        var lookupFailure: SecurityException? = null

        override fun getApplicationContext(): Context = this
        override fun getApplicationInfo(): ApplicationInfo = info
        override fun getFilesDir(): File = files

        override fun checkSelfPermission(permission: String): Int {
            queries += permission
            if (permission == LOCAL_NETWORK_PERMISSION) {
                lookupFailure?.let { throw it }
                return if (granted) PackageManager.PERMISSION_GRANTED else PackageManager.PERMISSION_DENIED
            }
            // Normal declarations are present. Provisioning-only and unexpected runtime queries are denied.
            return if (permission in NORMAL_PERMISSIONS) {
                PackageManager.PERMISSION_GRANTED
            } else {
                PackageManager.PERMISSION_DENIED
            }
        }
    }

    private class InertObserver : NetworkPathObserver {
        override val status = MutableStateFlow<NetworkPathStatus>(NetworkPathStatus.Unknown)
        var starts = 0
        override suspend fun start() { starts++ }
        override suspend fun close() = Unit
    }

    private class InertFactory(
        kind: TransportKind = TransportKind.LAN,
        private val hasData: Boolean = true,
        private val hasDiscovery: Boolean = true
    ) : TransportFactory {
        val transport = InertTransport(kind)
        var buildCalls = 0
        override val descriptor = TransportDescriptor(
            kind,
            buildSet {
                if (hasData) add(TransportCapability.DATA)
                if (hasDiscovery) add(TransportCapability.DISCOVERY)
            }
        )

        override fun build(context: TransportContext): TransportPair {
            buildCalls++
            return TransportPair(
                data = transport.takeIf { hasData },
                discovery = transport.takeIf { hasDiscovery }
            )
        }
    }

    private class InertTransport(override val type: TransportKind) : DataTransport, DiscoveryTransport {
        override val priority = 1
        override val events = MutableSharedFlow<PeerEvent>()
        private val incoming = MutableSharedFlow<RawConnection>()
        var dataStarts = 0
        var advertisingStarts = 0
        var discoveryStarts = 0

        override suspend fun start(): Result<Unit> {
            dataStarts++
            return Result.success(Unit)
        }

        override suspend fun stop() = Unit
        override suspend fun close() = Unit
        override fun canConnect(peer: InternalPeer): Boolean = false
        override suspend fun connect(peer: InternalPeer): RawConnection =
            error("No network work in a permission fixture")
        override fun incomingConnections(): Flow<RawConnection> = incoming
        override suspend fun startAdvertising(localPeer: LocalPeerInfo) { advertisingStarts++ }
        override suspend fun stopAdvertising() = Unit
        override suspend fun startDiscovery() { discoveryStarts++ }
        override suspend fun stopDiscovery() = Unit
    }

    private companion object {
        const val LOCAL_NETWORK_PERMISSION = "android.permission.ACCESS_LOCAL_NETWORK"
        val LOCAL_NETWORK = listOf(P2pPermission.LocalNetwork)
        val NORMAL_PERMISSIONS = setOf(
            "android.permission.INTERNET",
            "android.permission.ACCESS_NETWORK_STATE",
            "android.permission.ACCESS_WIFI_STATE",
            "android.permission.CHANGE_WIFI_MULTICAST_STATE"
        )
    }
}
