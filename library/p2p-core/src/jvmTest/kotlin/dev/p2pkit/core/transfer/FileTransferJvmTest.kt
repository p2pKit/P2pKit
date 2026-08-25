package dev.p2pkit.core.transfer

import dev.p2pkit.core.AppId
import dev.p2pkit.core.ExplicitSecurityRisk
import dev.p2pkit.core.P2pKit
import dev.p2pkit.core.Peer
import dev.p2pkit.core.PeerId
import dev.p2pkit.core.Platform
import dev.p2pkit.core.SecurityMode
import dev.p2pkit.core.TransportKind
import dev.p2pkit.core.internal.InMemoryPeerIdStorage
import dev.p2pkit.core.testfixtures.FakeConnectionPair
import dev.p2pkit.core.testfixtures.FakeDataTransport
import dev.p2pkit.core.transport.RawConnection
import dev.p2pkit.core.transport.TransportContext
import dev.p2pkit.core.transport.TransportFactory
import dev.p2pkit.core.transport.TransportPair
import kotlinx.coroutines.async
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withTimeout
import kotlinx.io.Buffer
import kotlinx.io.readByteArray
import java.io.File
import java.io.IOException
import java.nio.file.Files
import kotlin.test.AfterTest
import kotlin.test.Test
import kotlin.test.assertContentEquals
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertFailsWith
import kotlin.test.assertIs
import kotlin.test.assertSame
import kotlin.test.assertTrue

@OptIn(ExplicitSecurityRisk::class)
@Suppress("DEPRECATION")
class FileTransferJvmTest {

    private val tempFiles: MutableList<File> = mutableListOf()

    @AfterTest
    fun cleanup() {
        tempFiles.forEach { file ->
            runCatching {
                if (file.isDirectory) file.deleteRecursively() else file.delete()
            }
        }
        tempFiles.clear()
    }

    private fun outgoingKit(name: String, outgoing: RawConnection): P2pKit = P2pKit.create {
        appId = AppId("com.example.jvm-ft")
        deviceName = name
        security { mode = SecurityMode.NoneForMvp }
        peerIdStorage = InMemoryPeerIdStorage(seed = PeerId("alice-id"))
        keepAlive {
            pingIntervalMillis = 60_000
            timeoutMillis = 120_000
        }
        transports {
            register(JvmFtFactoryFor(FakeDataTransport(outgoingConnection = { outgoing })))
        }
    }

    private fun incomingKit(name: String, incoming: RawConnection): P2pKit = P2pKit.create {
        appId = AppId("com.example.jvm-ft")
        deviceName = name
        security { mode = SecurityMode.NoneForMvp }
        // Match the dialed id ("bob-id") so the outgoing handshake's peerId
        // verification passes (mirrors production discovery).
        peerIdStorage = InMemoryPeerIdStorage(seed = PeerId("bob-id"))
        keepAlive {
            pingIntervalMillis = 60_000
            timeoutMillis = 120_000
        }
        transports {
            register(JvmFtFactoryFor(FakeDataTransport(preStagedIncoming = listOf(incoming))))
        }
    }

    private fun syntheticPeer(id: String, name: String): Peer = Peer(
        id = PeerId(id),
        name = name,
        platform = Platform.JVM_DESKTOP,
        supportedTransports = setOf(TransportKind.LAN)
    )

    private fun tempFile(content: ByteArray, name: String = "blob.bin"): File {
        val f = Files.createTempFile("p2pkit-jvmft-", "-$name").toFile()
        tempFiles.add(f)
        f.writeBytes(content)
        return f
    }

    @Test
    fun sendFilePopulatesNameAndSizeFromFile() = runBlocking {
        val pair = FakeConnectionPair()
        val alice = outgoingKit("Alice", pair.a)
        val bob = incomingKit("Bob", pair.b)
        try {
            val outgoingDeferred = async { alice.connect(syntheticPeer("bob-id", "Bob")) }
            val incomingSession = withTimeout(5_000) { bob.incomingSessions.first() }
            val outgoing = withTimeout(5_000) { outgoingDeferred.await() }

            val payload = ByteArray(2048) { (it and 0xFF).toByte() }
            val file = tempFile(payload, "data.bin")

            val offerDeferred = async {
                incomingSession.pendingFileOffers.first { it.isNotEmpty() }.first()
            }

            val transfer = outgoing.sendFile(file)
            val offer = withTimeout(5_000) { offerDeferred.await() }
            assertEquals(file.name, offer.name)
            assertEquals(payload.size.toLong(), offer.sizeBytes)

            val sink = Buffer()
            val incoming = offer.accept(sink)
            withTimeout(5_000) {
                transfer.state.first { it is FileTransferState.Completed || it is FileTransferState.Failed }
            }
            withTimeout(5_000) {
                incoming.state.first { it is FileTransferState.Completed || it is FileTransferState.Failed }
            }
            assertIs<FileTransferState.Completed>(transfer.state.value)
            assertContentEquals(payload, sink.readByteArray())
        } finally {
            alice.stop()
            bob.stop()
        }
    }

    @Test
    fun sendFileRejectsMissingFile() = runBlocking<Unit> {
        val pair = FakeConnectionPair()
        val alice = outgoingKit("Alice", pair.a)
        val bob = incomingKit("Bob", pair.b)
        try {
            val outgoingDeferred = async { alice.connect(syntheticPeer("bob-id", "Bob")) }
            withTimeout(5_000) { bob.incomingSessions.first() }
            val outgoing = withTimeout(5_000) { outgoingDeferred.await() }
            val nonexistent = File(System.getProperty("java.io.tmpdir"), "p2pkit-does-not-exist.bin")
            assertFailsWith<IllegalArgumentException> { outgoing.sendFile(nonexistent) }
        } finally {
            alice.stop()
            bob.stop()
        }
    }

    @Test
    fun sendFileRejectsDirectory() = runBlocking<Unit> {
        val pair = FakeConnectionPair()
        val alice = outgoingKit("Alice", pair.a)
        val bob = incomingKit("Bob", pair.b)
        try {
            val outgoingDeferred = async { alice.connect(syntheticPeer("bob-id", "Bob")) }
            withTimeout(5_000) { bob.incomingSessions.first() }
            val outgoing = withTimeout(5_000) { outgoingDeferred.await() }
            val dir = Files.createTempDirectory("p2pkit-jvmft-dir-").toFile()
            tempFiles.add(dir)
            assertFailsWith<IllegalArgumentException> { outgoing.sendFile(dir) }
        } finally {
            alice.stop()
            bob.stop()
        }
    }

    @Test
    fun durableDestinationPublishesOnlyAfterCommitAndCommitIsIdempotent() = runBlocking {
        val directory = Files.createTempDirectory("p2pkit-durable-destination-").toFile()
        tempFiles.add(directory)
        val target = File(directory, "received.bin")
        val payload = ByteArray(4096) { (it * 17).toByte() }
        val destination = durableFileDestination(target)
        val sink = destination.openSink()
        val buffer = Buffer().apply { write(payload) }

        sink.write(buffer, buffer.size)
        assertFalse(target.exists())

        destination.commit()
        destination.commit()

        assertContentEquals(payload, target.readBytes())
        assertEquals(listOf(target.name), directory.list()?.sorted())
    }

    @Test
    fun durableDestinationPreflightRetainsConfiguredFreeSpace() = runBlocking {
        val directory = Files.createTempDirectory("p2pkit-durable-capacity-").toFile()
        tempFiles.add(directory)
        val accepted = JvmDurableFileDestination(
            target = File(directory, "accepted.bin"),
            usableSpace = { 9L },
            minimumFreeSpaceBytes = 5L
        )
        val rejected = JvmDurableFileDestination(
            target = File(directory, "rejected.bin"),
            usableSpace = { 9L },
            minimumFreeSpaceBytes = 5L
        )

        accepted.requireAvailableStorage(4L)
        val failure = assertFailsWith<IOException> { rejected.requireAvailableStorage(5L) }

        assertTrue(failure.message.orEmpty().contains("Insufficient usable space"))
        accepted.abort(cause = null)
        rejected.abort(cause = null)
        assertTrue(directory.listFiles().isNullOrEmpty())
    }

    @Test
    fun durableDestinationSkipsUnsupportedWindowsDirectorySync() = runBlocking {
        val directory = Files.createTempDirectory("p2pkit-durable-windows-").toFile()
        tempFiles.add(directory)
        val target = File(directory, "received.bin")
        var directorySyncAttempts = 0
        val destination = JvmDurableFileDestination(
            target = target,
            operatingSystemName = "Windows 11",
            syncDirectory = {
                directorySyncAttempts += 1
                throw IOException("Windows directories cannot be opened as FileChannel")
            }
        )
        val payload = byteArrayOf(1, 2, 3, 4)
        val sink = destination.openSink()
        val buffer = Buffer().apply { write(payload) }
        sink.write(buffer, buffer.size)

        destination.commit()
        destination.commit()

        assertEquals(0, directorySyncAttempts)
        assertContentEquals(payload, target.readBytes())
        assertEquals(listOf(target.name), directory.list()?.sorted())
    }

    @Test
    fun durableDestinationStillFailsAndRetriesWhenPosixDirectorySyncFails() = runBlocking {
        val directory = Files.createTempDirectory("p2pkit-durable-posix-").toFile()
        tempFiles.add(directory)
        val target = File(directory, "received.bin")
        var directorySyncAttempts = 0
        val destination = JvmDurableFileDestination(
            target = target,
            operatingSystemName = "Linux",
            syncDirectory = {
                directorySyncAttempts += 1
                if (directorySyncAttempts == 1) throw IOException("injected directory fsync failure")
            }
        )
        val payload = byteArrayOf(5, 6, 7, 8)
        val sink = destination.openSink()
        val buffer = Buffer().apply { write(payload) }
        sink.write(buffer, buffer.size)

        val failure = assertFailsWith<IOException> { destination.commit() }
        assertEquals("injected directory fsync failure", failure.message)
        assertContentEquals(payload, target.readBytes())

        destination.commit()
        destination.commit()

        assertEquals(2, directorySyncAttempts)
        assertContentEquals(payload, target.readBytes())
        assertEquals(listOf(target.name), directory.list()?.sorted())
    }

    @Test
    fun durableDestinationAbortRemovesPartialAndPreservesExistingTarget() = runBlocking {
        val directory = Files.createTempDirectory("p2pkit-durable-abort-").toFile()
        tempFiles.add(directory)
        val target = File(directory, "received.bin").also { it.writeText("existing") }
        val destination = durableFileDestination(target)
        val sink = destination.openSink()
        val buffer = Buffer().apply { write(byteArrayOf(1, 2, 3, 4)) }
        sink.write(buffer, buffer.size)

        destination.abort(cause = null)
        destination.abort(cause = null)

        assertEquals("existing", target.readText())
        assertEquals(listOf(target.name), directory.list()?.sorted())
    }

    @Test
    fun durableDestinationAbortReportsAllFailuresAndRetriesOnlyIncompleteCleanup() = runBlocking {
        val directory = Files.createTempDirectory("p2pkit-durable-abort-retry-").toFile()
        tempFiles.add(directory)
        val target = File(directory, "received.bin").also { it.writeText("existing") }
        val closeFailure = IOException("injected sink close failure")
        var closeAttempts = 0
        var deleteAttempts = 0
        val destination = JvmDurableFileDestination(
            target = target,
            closeSink = { opened ->
                closeAttempts += 1
                if (closeAttempts == 1) throw closeFailure
                opened.close()
            },
            deleteTemp = { staging ->
                deleteAttempts += 1
                if (deleteAttempts == 1) false else staging.delete()
            }
        )
        val sink = destination.openSink()
        val buffer = Buffer().apply { write(byteArrayOf(1, 2, 3, 4)) }
        sink.write(buffer, buffer.size)

        val failure = assertFailsWith<IOException> { destination.abort(cause = null) }

        assertTrue(failure.message.orEmpty().contains("staging sink close"))
        assertTrue(failure.message.orEmpty().contains("staging file deletion"))
        assertSame(closeFailure, failure.cause)
        assertEquals(1, failure.suppressedExceptions.size)
        assertTrue(failure.suppressedExceptions.single().message.orEmpty().contains("still exists"))
        assertEquals(1, closeAttempts)
        assertEquals(1, deleteAttempts)
        assertTrue(directory.listFiles().orEmpty().any { it.extension == "part" })
        assertFailsWith<IllegalStateException> { destination.commit() }

        destination.abort(cause = null)
        destination.abort(cause = null)

        assertEquals(2, closeAttempts)
        assertEquals(2, deleteAttempts)
        assertEquals("existing", target.readText())
        assertEquals(listOf(target.name), directory.list()?.sorted())
    }

    @Test
    fun durableDestinationDoesNotCloseAgainWhenOnlyDeletionNeedsRetry() = runBlocking {
        val directory = Files.createTempDirectory("p2pkit-durable-delete-retry-").toFile()
        tempFiles.add(directory)
        val target = File(directory, "received.bin")
        var closeAttempts = 0
        var deleteAttempts = 0
        val destination = JvmDurableFileDestination(
            target = target,
            closeSink = { opened ->
                closeAttempts += 1
                opened.close()
            },
            deleteTemp = { staging ->
                deleteAttempts += 1
                if (deleteAttempts == 1) false else staging.delete()
            }
        )
        destination.openSink()

        assertFailsWith<IOException> { destination.abort(cause = null) }
        assertEquals(1, closeAttempts)
        assertEquals(1, deleteAttempts)

        destination.abort(cause = null)
        assertEquals(1, closeAttempts)
        assertEquals(2, deleteAttempts)
        assertTrue(directory.listFiles().isNullOrEmpty())
    }

    @Test
    fun durableDestinationDoesNotDeleteAgainWhenOnlyCloseNeedsRetry() = runBlocking {
        val directory = Files.createTempDirectory("p2pkit-durable-close-retry-").toFile()
        tempFiles.add(directory)
        val target = File(directory, "received.bin")
        var closeAttempts = 0
        var deleteAttempts = 0
        val destination = JvmDurableFileDestination(
            target = target,
            closeSink = { opened ->
                closeAttempts += 1
                if (closeAttempts == 1) throw IOException("injected sink close failure")
                opened.close()
            },
            deleteTemp = { staging ->
                deleteAttempts += 1
                staging.delete()
            }
        )
        destination.openSink()

        assertFailsWith<IOException> { destination.abort(cause = null) }
        assertEquals(1, closeAttempts)
        assertEquals(1, deleteAttempts)
        assertTrue(directory.listFiles().isNullOrEmpty())

        destination.abort(cause = null)
        assertEquals(2, closeAttempts)
        assertEquals(1, deleteAttempts)
    }
}

private class JvmFtFactoryFor(private val transport: FakeDataTransport) : TransportFactory {
    override val descriptor =
        dev.p2pkit.core.transport.TransportDescriptor.dataOnly(transport.type)

    override fun build(context: TransportContext): TransportPair =
        TransportPair(data = transport, discovery = null)
}
