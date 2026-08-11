package dev.p2pkit.core.internal

import dev.p2pkit.core.AppId
import dev.p2pkit.core.FeatureState
import dev.p2pkit.core.P2pError
import dev.p2pkit.core.P2pState
import dev.p2pkit.core.TransportKind
import dev.p2pkit.core.permission.P2pPermission
import dev.p2pkit.core.permission.P2pPermissionManager
import dev.p2pkit.core.testfixtures.FakeDataTransport
import dev.p2pkit.core.testfixtures.FakeDiscoveryTransport
import dev.p2pkit.core.testfixtures.createTestKit
import dev.p2pkit.core.transport.DataTransport
import dev.p2pkit.core.transport.InternalPeer
import dev.p2pkit.core.transport.RawConnection
import dev.p2pkit.core.transport.TransportCapability
import dev.p2pkit.core.transport.TransportContext
import dev.p2pkit.core.transport.TransportDescriptor
import dev.p2pkit.core.transport.TransportFactory
import dev.p2pkit.core.transport.TransportPair
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.emptyFlow
import kotlinx.coroutines.runBlocking
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertIs
import kotlin.test.assertSame
import kotlin.test.assertTrue

class TransportCapabilityTest {

    @Test
    fun descriptorOwnsImmutableCapabilitySnapshotAndSupportsValueSemantics() {
        val source = mutableSetOf(TransportCapability.DATA)
        val descriptor = TransportDescriptor(TransportKind.LAN, source)
        source += TransportCapability.DISCOVERY

        assertEquals(setOf(TransportCapability.DATA), descriptor.capabilities)
        assertEquals(TransportKind.LAN, descriptor.component1())
        assertEquals(setOf(TransportCapability.DATA), descriptor.component2())
        assertEquals(descriptor, descriptor.copy())
        assertEquals(descriptor.hashCode(), descriptor.copy().hashCode())
        assertTrue(
            runCatching {
                @Suppress("UNCHECKED_CAST")
                (descriptor.capabilities as MutableSet<TransportCapability>) +=
                    TransportCapability.DISCOVERY
            }.isFailure
        )

        assertFailsWith<IllegalArgumentException> {
            TransportDescriptor(TransportKind.LAN, emptySet())
        }
    }

    @Test
    fun transportPairRequiresAtLeastOneDeclaredPath() {
        assertFailsWith<IllegalArgumentException> { TransportPair() }
    }

    @Test
    fun dataOnlyProviderReportsUnsupportedBeforeRuntimePermissionQuery() = runBlocking {
        val permissionManager = CountingMissingPermissionManager()
        val kit = createTestKit {
            appId = AppId("data-only-capability-test")
            deviceName = "Data only"
            this.permissionManager = permissionManager
            transports {
                register(
                    StaticFactory(
                        TransportDescriptor.dataOnly(TransportKind.LAN)
                    ) { TransportPair(data = FakeDataTransport()) }
                )
            }
        }
        try {
            kit.startAdvertising()
            assertIs<FeatureState.Unsupported>(kit.advertisingState.value)
            assertEquals(0, permissionManager.missingQueries)
            assertEquals(P2pState.Idle, kit.state.value)

            kit.startDiscovery()
            assertIs<FeatureState.Unsupported>(kit.discoveryState.value)
            assertEquals(0, permissionManager.missingQueries)
            assertEquals(P2pState.Idle, kit.state.value)

            kit.stopAdvertising()
            kit.stopDiscovery()
            assertEquals(FeatureState.Idle, kit.advertisingState.value)
            assertEquals(FeatureState.Idle, kit.discoveryState.value)
        } finally {
            kit.stop()
        }
    }

    @Test
    fun discoveryOnlyProviderBuildsAndRunsBothDiscoveryFeatures() = runBlocking {
        val discovery = FakeDiscoveryTransport()
        val kit = createTestKit {
            appId = AppId("discovery-only-capability-test")
            deviceName = "Discovery only"
            transports {
                register(
                    StaticFactory(
                        TransportDescriptor.discoveryOnly(TransportKind.LAN)
                    ) { TransportPair(discovery = discovery) }
                )
            }
        }
        try {
            kit.startAdvertising()
            kit.startDiscovery()
            assertEquals(1, discovery.startAdvertisingCalls)
            assertEquals(1, discovery.startDiscoveryCalls)
            assertEquals(FeatureState.Active, kit.advertisingState.value)
            assertEquals(FeatureState.Active, kit.discoveryState.value)
            assertEquals(P2pState.Running, kit.state.value)
        } finally {
            kit.stop()
        }
    }

    @Test
    fun duplicateKindIsRejectedBeforeAnyFactoryBuild() {
        val first = CountingFactory(TransportKind.LAN)
        val second = CountingFactory(TransportKind.LAN)

        assertFailsWith<IllegalArgumentException> {
            createTestKit {
                appId = AppId("duplicate-kind-capability-test")
                deviceName = "Duplicate kind"
                transports {
                    register(first)
                    register(second)
                }
            }
        }
        assertEquals(0, first.buildCalls)
        assertEquals(0, second.buildCalls)
    }

    @Test
    fun factoryThrowIsMappedToTypedInitializationFailure() {
        val cause = IllegalStateException("provider construction failed")
        val failure = assertFailsWith<P2pError.TransportInitializationFailed> {
            createTestKit {
                appId = AppId("factory-throw-capability-test")
                deviceName = "Factory throw"
                transports {
                    register(
                        StaticFactory(
                            TransportDescriptor.dataOnly(TransportKind.LAN)
                        ) { throw cause }
                    )
                }
            }
        }

        assertEquals(TransportKind.LAN, failure.transportKind)
        assertSame(cause, failure.underlying)
        assertTrue(failure.reason.contains("provider construction failed"))
    }

    @Test
    fun descriptorPairCapabilityMismatchIsTyped() {
        val failure = assertFailsWith<P2pError.TransportInitializationFailed> {
            createTestKit {
                appId = AppId("factory-capability-mismatch-test")
                deviceName = "Capability mismatch"
                transports {
                    register(
                        StaticFactory(
                            TransportDescriptor.dataOnly(TransportKind.LAN)
                        ) {
                            TransportPair(discovery = FakeDiscoveryTransport())
                        }
                    )
                }
            }
        }

        assertEquals(TransportKind.LAN, failure.transportKind)
        assertTrue(failure.reason.contains("DATA=true"))
        assertTrue(failure.reason.contains("data path=false"))
    }

    @Test
    fun descriptorPairKindMismatchIsTyped() {
        val failure = assertFailsWith<P2pError.TransportInitializationFailed> {
            createTestKit {
                appId = AppId("factory-kind-mismatch-test")
                deviceName = "Kind mismatch"
                transports {
                    register(
                        StaticFactory(
                            TransportDescriptor.dataOnly(TransportKind.BLE)
                        ) {
                            TransportPair(data = FakeDataTransport(TransportKind.LAN))
                        }
                    )
                }
            }
        }

        assertEquals(TransportKind.BLE, failure.transportKind)
        assertTrue(failure.reason.contains("does not match data kind LAN"))
    }

    @Test
    fun providerGetterFailureDuringPairValidationIsTyped() {
        val cause = IllegalStateException("provider type getter failed")
        val failure = assertFailsWith<P2pError.TransportInitializationFailed> {
            createTestKit {
                appId = AppId("factory-getter-failure-test")
                deviceName = "Getter failure"
                transports {
                    register(
                        StaticFactory(
                            TransportDescriptor.dataOnly(TransportKind.LAN)
                        ) {
                            TransportPair(data = ThrowingTypeDataTransport(cause))
                        }
                    )
                }
            }
        }

        assertEquals(TransportKind.LAN, failure.transportKind)
        assertSame(cause, failure.underlying)
        assertTrue(failure.reason.contains("provider type getter failed"))
    }
}

private class StaticFactory(
    override val descriptor: TransportDescriptor,
    private val buildPair: (TransportContext) -> TransportPair
) : TransportFactory {
    override fun build(context: TransportContext): TransportPair = buildPair(context)
}

private class CountingFactory(kind: TransportKind) : TransportFactory {
    override val descriptor: TransportDescriptor = TransportDescriptor.dataOnly(kind)
    var buildCalls: Int = 0
        private set

    override fun build(context: TransportContext): TransportPair {
        buildCalls += 1
        return TransportPair(data = FakeDataTransport(descriptor.kind))
    }
}

private class ThrowingTypeDataTransport(
    private val failure: Throwable
) : DataTransport {
    override val type: TransportKind get() = throw failure
    override val priority: Int = 0
    override fun canConnect(peer: InternalPeer): Boolean = false
    override suspend fun connect(peer: InternalPeer): RawConnection = error("not used")
    override fun incomingConnections(): Flow<RawConnection> = emptyFlow()
    override suspend fun stop() = Unit
    override suspend fun close() = Unit
}

private class CountingMissingPermissionManager : P2pPermissionManager {
    var missingQueries: Int = 0
        private set

    override suspend fun requiredPermissions(): List<P2pPermission> =
        listOf(P2pPermission.NearbyWifiDevices)

    override suspend fun missingPermissions(): List<P2pPermission> {
        missingQueries += 1
        return listOf(P2pPermission.NearbyWifiDevices)
    }

    override suspend fun hasRequiredPermissions(): Boolean = false
}
