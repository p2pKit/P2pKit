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
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.async
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.onSubscription
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withTimeout
import kotlinx.io.Buffer
import kotlinx.io.readByteArray
import java.io.File
import java.nio.file.Files
import kotlin.test.AfterTest
import kotlin.test.Test
import kotlin.test.assertContentEquals
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertIs

@OptIn(ExplicitSecurityRisk::class)
@Suppress("DEPRECATION")
class FileTransferJvmTest {

    private val tempFiles: MutableList<File> = mutableListOf()

    @AfterTest
    fun cleanup() {
        tempFiles.forEach { runCatching { it.delete() } }
        tempFiles.clear()
    }

    private fun outgoingKit(name: String, outgoing: RawConnection): P2pKit = P2pKit.create {
        appId = AppId("com.example.jvm-ft")
        deviceName = name
        security { mode = SecurityMode.NoneForMvp }
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

            val offerReady = CompletableDeferred<Unit>()
            val offerDeferred = async {
                incomingSession.incomingFiles.onSubscription { offerReady.complete(Unit) }.first()
            }
            offerReady.await()

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
}

private class JvmFtFactoryFor(private val transport: FakeDataTransport) : TransportFactory {
    override fun build(context: TransportContext): TransportPair =
        TransportPair(data = transport, discovery = null)
}
