package dev.p2pkit.core.internal

import dev.p2pkit.core.AppId
import dev.p2pkit.core.ExplicitSecurityRisk
import dev.p2pkit.core.P2pKit
import dev.p2pkit.core.P2pLogger
import dev.p2pkit.core.SecurityMode
import dev.p2pkit.core.TransportKind
import dev.p2pkit.core.transport.DataTransport
import dev.p2pkit.core.transport.InternalPeer
import dev.p2pkit.core.transport.LocalPeerInfo
import dev.p2pkit.core.transport.PeerEvent
import dev.p2pkit.core.transport.RawConnection
import dev.p2pkit.core.transport.TransportContext
import dev.p2pkit.core.transport.TransportFactory
import dev.p2pkit.core.transport.TransportPair
import java.io.File
import java.nio.file.Files
import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.asSharedFlow
import kotlinx.coroutines.flow.receiveAsFlow
import kotlinx.coroutines.runBlocking
import kotlin.test.AfterTest
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertNotEquals
import kotlin.test.assertTrue

/**
 * Drives the kit through a "start → stop → start again with same storage"
 * cycle to verify the PeerId is the same on the second launch.
 *
 * Uses a tracking [PeerIdStorage] so the assertion is "the kit loaded my
 * storage" (not just "the storage happens to be deterministic").
 */
@OptIn(ExplicitSecurityRisk::class)
@Suppress("DEPRECATION")
class PeerIdPersistenceIntegrationTest {

    private val tempDir: File = Files.createTempDirectory("p2pkit-pidpersist-itest").toFile()

    @AfterTest
    fun cleanup() {
        tempDir.deleteRecursively()
    }

    @Test
    fun samePeerIdAcrossKitInstancesWhenSharingFilePeerIdStorage() {
        val appId = AppId("persist-itest")

        val kitOneStorage = FilePeerIdStorage(tempDir, appId.value, P2pLogger.NoOp)
        val kitOne = P2pKit.create {
            this.appId = appId
            deviceName = "First"
            peerIdStorage = kitOneStorage
            security { mode = SecurityMode.NoneForMvp }
            transports { register(NoopFactory) }
        }
        runBlocking { kitOne.stop() }

        // A brand-new file storage pointing at the same backing directory
        // and a fresh kit should both observe the same persisted id.
        val kitTwoStorage = FilePeerIdStorage(tempDir, appId.value, P2pLogger.NoOp)
        val kitTwo = P2pKit.create {
            this.appId = appId
            deviceName = "Second"
            peerIdStorage = kitTwoStorage
            security { mode = SecurityMode.NoneForMvp }
            transports { register(NoopFactory) }
        }
        runBlocking { kitTwo.stop() }

        assertEquals(
            kitOneStorage.loadOrGenerate(),
            kitTwoStorage.loadOrGenerate(),
            "PeerId must persist across kit instances when sharing the same FilePeerIdStorage backing"
        )
    }

    @Test
    fun kitInvokesProvidedPeerIdStorageAtConstruction() {
        var loadCount = 0
        val tracking = object : PeerIdStorage {
            override fun loadOrGenerate(): dev.p2pkit.core.PeerId {
                loadCount++
                return dev.p2pkit.core.PeerId("tracked-peer-id-${System.nanoTime()}")
            }
        }

        val kit = P2pKit.create {
            appId = AppId("tracking-test")
            deviceName = "Tracker"
            peerIdStorage = tracking
            security { mode = SecurityMode.NoneForMvp }
            transports { register(NoopFactory) }
        }
        runBlocking { kit.stop() }

        assertEquals(1, loadCount, "Kit must call peerIdStorage.loadOrGenerate() exactly once at construction")
    }

    @Test
    fun differentAppIdsGetDifferentPersistedPeerIds() {
        val storageA = FilePeerIdStorage(tempDir, "app-A", P2pLogger.NoOp)
        val storageB = FilePeerIdStorage(tempDir, "app-B", P2pLogger.NoOp)
        val kitA = P2pKit.create {
            appId = AppId("app-A")
            deviceName = "A"
            peerIdStorage = storageA
            security { mode = SecurityMode.NoneForMvp }
            transports { register(NoopFactory) }
        }
        val kitB = P2pKit.create {
            appId = AppId("app-B")
            deviceName = "B"
            peerIdStorage = storageB
            security { mode = SecurityMode.NoneForMvp }
            transports { register(NoopFactory) }
        }
        try {
            assertNotEquals(storageA.loadOrGenerate(), storageB.loadOrGenerate())
            // Sanity: the per-appId directory exists for each.
            assertTrue(File(storageA.storagePath).exists())
            assertTrue(File(storageB.storagePath).exists())
        } finally {
            runBlocking {
                kitA.stop()
                kitB.stop()
            }
        }
    }
}

/** No-op [TransportFactory] just so the builder accepts a non-empty transport list. */
private object NoopFactory : TransportFactory {
    override fun build(context: TransportContext): TransportPair =
        TransportPair(data = NoopDataTransport(), discovery = NoopDiscoveryTransport())
}

private class NoopDataTransport : DataTransport {
    override val type = TransportKind.LAN
    override val priority = 0
    private val incoming = Channel<RawConnection>(Channel.UNLIMITED)
    override fun canConnect(peer: InternalPeer) = false
    override suspend fun connect(peer: InternalPeer): RawConnection = error("unused")
    override fun incomingConnections(): Flow<RawConnection> = incoming.receiveAsFlow()
    override suspend fun close() { incoming.close() }
}

private class NoopDiscoveryTransport : dev.p2pkit.core.transport.DiscoveryTransport {
    override val type = TransportKind.LAN
    private val flow = MutableSharedFlow<PeerEvent>(extraBufferCapacity = 8)
    override val events: Flow<PeerEvent> = flow.asSharedFlow()
    override suspend fun startAdvertising(localPeer: LocalPeerInfo) = Unit
    override suspend fun stopAdvertising() = Unit
    override suspend fun startDiscovery() = Unit
    override suspend fun stopDiscovery() = Unit
}
