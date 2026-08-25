package dev.p2pkit.core

import dev.p2pkit.core.testfixtures.FakeDataTransport
import dev.p2pkit.core.testfixtures.createTestKit
import dev.p2pkit.core.transfer.FileTransferConfig
import dev.p2pkit.core.transport.TransportContext
import dev.p2pkit.core.transport.TransportDescriptor
import dev.p2pkit.core.transport.TransportFactory
import dev.p2pkit.core.transport.TransportPair
import kotlinx.coroutines.runBlocking
import kotlin.test.Test
import kotlin.test.assertContains
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith

class PublicConfigurationValidationTest {

    @Test
    fun keepAliveRejectsNonPositiveAndInvertedDeadlines() {
        assertFailsWith<IllegalArgumentException> { KeepAliveConfig(0, 1) }
        assertFailsWith<IllegalArgumentException> { KeepAliveConfig(1, 1) }
        assertFailsWith<IllegalArgumentException> { KeepAliveConfig(2, 1) }
    }

    @Test
    fun reconnectRejectsInvalidAttemptAndDelayValues() {
        assertFailsWith<IllegalArgumentException> {
            ReconnectPolicy.Enabled(maxAttempts = 0, retryDelayMillis = 0)
        }
        assertFailsWith<IllegalArgumentException> {
            ReconnectPolicy.Enabled(maxAttempts = 1, retryDelayMillis = -1)
        }
    }

    @Test
    fun fileTransferRejectsInvalidBoundsAndUnrepresentableChunkCounts() {
        assertFailsWith<IllegalArgumentException> {
            FileTransferConfig(maxFileSizeBytes = 0)
        }
        assertFailsWith<IllegalArgumentException> {
            FileTransferConfig(maxConcurrentIncomingBytes = 0)
        }
        assertFailsWith<IllegalArgumentException> {
            FileTransferConfig(chunkSizeBytes = 0)
        }
        assertFailsWith<IllegalArgumentException> {
            FileTransferConfig(chunkSizeBytes = 4 * 1024 * 1024 + 1)
        }
        assertFailsWith<IllegalArgumentException> {
            FileTransferConfig(offerTimeoutMillis = 0)
        }
        assertFailsWith<IllegalArgumentException> {
            FileTransferConfig(
                maxFileSizeBytes = Int.MAX_VALUE.toLong() + 1L,
                chunkSizeBytes = 1
            )
        }
    }

    @Test
    fun fileTransferAggregateLimitIsConfigurableWithoutChangingLegacyConstruction() {
        val configured = FileTransferConfig(
            maxFileSizeBytes = 16L,
            chunkSizeBytes = 1,
            offerTimeoutMillis = 1,
            maxConcurrentIncomingBytes = 32L
        )
        val legacy = FileTransferConfig(16L, 1, 1)

        assertEquals(32L, configured.maxConcurrentIncomingBytes)
        assertEquals(8L * 1024 * 1024 * 1024, legacy.maxConcurrentIncomingBytes)
        assertEquals(
            legacy.maxConcurrentIncomingBytes,
            legacy.copy(maxFileSizeBytes = 8L).maxConcurrentIncomingBytes
        )
    }

    @Test
    fun builderRejectsEveryMissingRequiredFieldBeforeConstruction() {
        val missingAppId = assertFailsWith<IllegalStateException> {
            P2pKit.create {
                deviceName = "Device"
                transports { register(ConfigurationTransportFactory) }
            }
        }
        assertContains(missingAppId.message.orEmpty(), "appId must be set")

        val missingDeviceName = assertFailsWith<IllegalStateException> {
            P2pKit.create {
                appId = AppId("configuration-test")
                transports { register(ConfigurationTransportFactory) }
            }
        }
        assertContains(missingDeviceName.message.orEmpty(), "deviceName must be set")

        val missingTransport = assertFailsWith<IllegalStateException> {
            P2pKit.create {
                appId = AppId("configuration-test")
                deviceName = "Device"
            }
        }
        assertContains(missingTransport.message.orEmpty(), "At least one transport")
    }

    @Test
    fun builderRejectsWireInvalidIdentityTextBeforeTransportConstruction() {
        val oversized = "x".repeat(1_025)
        val invalidAppId = assertFailsWith<IllegalArgumentException> {
            P2pKit.create {
                appId = AppId(oversized)
                deviceName = "Device"
                transports { register(ConfigurationTransportFactory) }
            }
        }
        assertContains(invalidAppId.message.orEmpty(), "appId")

        val invalidDeviceName = assertFailsWith<IllegalArgumentException> {
            P2pKit.create {
                appId = AppId("configuration-test")
                deviceName = oversized
                transports { register(ConfigurationTransportFactory) }
            }
        }
        assertContains(invalidDeviceName.message.orEmpty(), "deviceName")
    }

    @Test
    fun repeatedConfigurationBlocksAccumulatePriorValues() = runBlocking<Unit> {
        val kit = createTestKit {
            appId = AppId("repeated-configuration-test")
            deviceName = "Device"
            transports { register(ConfigurationTransportFactory) }
            keepAlive { pingIntervalMillis = 100 }
            keepAlive { timeoutMillis = 200 }
            fileTransfer { maxFileSizeBytes = Int.MAX_VALUE.toLong() }
            fileTransfer { chunkSizeBytes = 1 }
        }

        kit.stop()
    }
}

private object ConfigurationTransportFactory : TransportFactory {
    override val descriptor: TransportDescriptor =
        TransportDescriptor.dataOnly(TransportKind.LAN)

    override fun build(context: TransportContext): TransportPair =
        TransportPair(data = FakeDataTransport())
}
