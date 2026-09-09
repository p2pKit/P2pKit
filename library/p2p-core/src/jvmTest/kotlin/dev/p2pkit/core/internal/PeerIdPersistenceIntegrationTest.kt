package dev.p2pkit.core.internal

import dev.p2pkit.core.AppId
import dev.p2pkit.core.ExplicitSecurityRisk
import dev.p2pkit.core.P2pKit
import dev.p2pkit.core.SecurityMode
import dev.p2pkit.core.TransportKind
import dev.p2pkit.core.testfixtures.RecordingLogger
import dev.p2pkit.core.testfixtures.withTestKit
import dev.p2pkit.core.transport.DataTransport
import dev.p2pkit.core.transport.InternalPeer
import dev.p2pkit.core.transport.LocalPeerInfo
import dev.p2pkit.core.transport.PeerEvent
import dev.p2pkit.core.transport.RawConnection
import dev.p2pkit.core.transport.TransportContext
import dev.p2pkit.core.transport.TransportFactory
import dev.p2pkit.core.transport.TransportPair
import java.io.File
import java.io.IOException
import java.nio.channels.FileChannel
import java.nio.file.Files
import java.nio.file.StandardOpenOption
import kotlin.test.assertIs
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
    fun samePeerIdAcrossKitInstancesWhenSharingFilePeerIdStorage() = runBlocking {
        val appId = AppId("persist-itest")
        lateinit var kitOneStorage: FilePeerIdStorage
        val firstId = withTestKit(
            create = { recorder ->
                kitOneStorage = FilePeerIdStorage(tempDir, appId.value, recorder)
                P2pKit.create {
                    logger = recorder
                    this.appId = appId
                    deviceName = "First"
                    peerIdStorage = kitOneStorage
                    security { mode = SecurityMode.NoneForMvp }
                    transports { register(NoopFactory) }
                }
            },
            verifyDiagnostics = { recorder -> assertNewFilePersistenceDiagnostics(recorder, kitOneStorage) }
        ) { kitOne ->
            kitOne.stop()
            kitOneStorage.loadOrGenerate()
        }

        // A brand-new storage and kit read the same durable record. No new file is persisted,
        // so this second scope is strictly quiet even on a filesystem without directory fsync.
        lateinit var kitTwoStorage: FilePeerIdStorage
        val secondId = withTestKit(create = { recorder ->
            kitTwoStorage = FilePeerIdStorage(tempDir, appId.value, recorder)
            P2pKit.create {
                logger = recorder
                this.appId = appId
                deviceName = "Second"
                peerIdStorage = kitTwoStorage
                security { mode = SecurityMode.NoneForMvp }
                transports { register(NoopFactory) }
            }
        }) { kitTwo ->
            kitTwo.stop()
            kitTwoStorage.loadOrGenerate()
        }
        assertEquals(
            firstId,
            secondId,
            "PeerId must persist across kit instances when sharing the same FilePeerIdStorage backing"
        )
    }

    @Test
    fun kitInvokesProvidedPeerIdStorageAtConstruction() = runBlocking {
        var loadCount = 0
        val tracking = object : PeerIdStorage {
            override fun loadOrGenerate(): dev.p2pkit.core.PeerId {
                loadCount++
                return dev.p2pkit.core.PeerId("tracked-peer-id-${System.nanoTime()}")
            }
        }
        withTestKit(create = { recorder ->
            P2pKit.create {
                logger = recorder
                appId = AppId("tracking-test")
                deviceName = "Tracker"
                peerIdStorage = tracking
                security { mode = SecurityMode.NoneForMvp }
                transports { register(NoopFactory) }
            }
        }) { kit ->
            kit.stop()
            assertEquals(1, loadCount, "Kit must call peerIdStorage.loadOrGenerate() exactly once at construction")
        }
    }

    @Test
    fun differentAppIdsGetDifferentPersistedPeerIds() = runBlocking {
        lateinit var storageA: FilePeerIdStorage
        lateinit var storageB: FilePeerIdStorage
        withTestKit(
            create = { recorder ->
                storageA = FilePeerIdStorage(tempDir, "app-A", recorder)
                P2pKit.create {
                    logger = recorder
                    appId = AppId("app-A")
                    deviceName = "A"
                    peerIdStorage = storageA
                    security { mode = SecurityMode.NoneForMvp }
                    transports { register(NoopFactory) }
                }
            },
            verifyDiagnostics = { recorder -> assertNewFilePersistenceDiagnostics(recorder, storageA) }
        ) { _ ->
            withTestKit(
                create = { recorder ->
                    storageB = FilePeerIdStorage(tempDir, "app-B", recorder)
                    P2pKit.create {
                        logger = recorder
                        appId = AppId("app-B")
                        deviceName = "B"
                        peerIdStorage = storageB
                        security { mode = SecurityMode.NoneForMvp }
                        transports { register(NoopFactory) }
                    }
                },
                verifyDiagnostics = { recorder -> assertNewFilePersistenceDiagnostics(recorder, storageB) }
            ) { _ ->
                assertNotEquals(storageA.loadOrGenerate(), storageB.loadOrGenerate())
                assertTrue(File(storageA.storagePath).exists())
                assertTrue(File(storageB.storagePath).exists())
            }
        }
    }

    private fun assertNewFilePersistenceDiagnostics(recorder: RecordingLogger, storage: FilePeerIdStorage) {
        // Production explicitly diagnoses weaker crash durability on filesystems whose Java
        // provider cannot fsync directories (notably Windows). Observe that actual capability,
        // rather than skipping an OS or treating any persistence warning as expected. The
        // file, atomic replacement and persisted identity assertions above remain mandatory.
        val directory = File(storage.storagePath).parentFile
        val directoryFailure = try {
            FileChannel.open(directory.toPath(), StandardOpenOption.READ).use { it.force(true) }
            null
        } catch (failure: IOException) {
            failure
        }
        val diagnostics = recorder.entries.filter {
            it.level == RecordingLogger.Level.WARN || it.level == RecordingLogger.Level.ERROR
        }
        if (directoryFailure == null) {
            assertEquals(emptyList(), diagnostics)
        } else {
            // Exactly one new record is persisted in each calling scope; reload is cached.
            val entry = diagnostics.single()
            assertEquals(RecordingLogger.Level.WARN, entry.level)
            assertEquals("Could not fsync PeerId storage directory ${directory.absolutePath}", entry.message)
            val failure = assertIs<IOException>(entry.throwable)
            assertEquals(directoryFailure::class, failure::class)
            assertEquals(directoryFailure.message, failure.message)
            assertTrue(failure.suppressedExceptions.isEmpty())
        }
    }

}

/** No-op [TransportFactory] just so the builder accepts a non-empty transport list. */
private object NoopFactory : TransportFactory {
    override val descriptor =
        dev.p2pkit.core.transport.TransportDescriptor.dataAndDiscovery(TransportKind.LAN)

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
    override suspend fun stop() = Unit
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
