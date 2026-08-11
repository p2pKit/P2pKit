package dev.p2pkit.core.internal

import dev.p2pkit.core.AppId
import dev.p2pkit.core.ConnectionState
import dev.p2pkit.core.P2pError
import dev.p2pkit.core.PeerId
import dev.p2pkit.core.Platform
import dev.p2pkit.core.TransportKind
import dev.p2pkit.core.protocol.DefaultP2pProtocol
import dev.p2pkit.core.protocol.HelloPayload
import dev.p2pkit.core.protocol.ProtocolEvent
import dev.p2pkit.core.testfixtures.FakeConnectionPair
import dev.p2pkit.core.transport.RawConnection
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.emptyFlow
import kotlinx.coroutines.launch
import kotlinx.coroutines.runBlocking
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertSame

class HandshakeTest {

    private fun protocol() = DefaultP2pProtocol(clock = { 0L })

    private fun helloFromPeer(
        appId: String = "com.example",
        peerId: String = "remote",
        deviceName: String = "RemoteDev",
        platform: String = Platform.JVM_DESKTOP.name,
        protocolVersion: Int = 1
    ) = HelloPayload(
        appId = appId,
        peerId = peerId,
        deviceName = deviceName,
        platform = platform,
        supportedTransports = listOf("LAN"),
        protocolVersion = protocolVersion
    )

    @Test
    fun handshakeSucceedsWhenAppIdsAndVersionsMatch() = runBlocking {
        val pair = FakeConnectionPair()
        val protocol = protocol()

        val supervisor = SupervisorJob()
        val scope = CoroutineScope(Dispatchers.Default + supervisor)
        try {
            // Remote sends its HELLO first.
            scope.launch { protocol.sendHello(pair.b, helloFromPeer()) }

            val channel = Channel<ProtocolEvent>(Channel.UNLIMITED)
            scope.launch {
                protocol.events(pair.a).collect { channel.send(it) }
                channel.close()
            }

            val result = performHandshake(
                protocol = protocol,
                connection = pair.a,
                events = channel,
                localAppId = AppId("com.example"),
                localPeerId = PeerId("local"),
                localDeviceName = "LocalDev",
                localPlatform = Platform.JVM_DESKTOP,
                localTransports = setOf(TransportKind.LAN)
            )
            assertEquals("remote", result.peerId)
            assertEquals("com.example", result.appId)
        } finally {
            supervisor.cancel()
        }
    }

    @Test
    fun appIdMismatchThrowsHandshakeRejected() = runBlocking {
        val pair = FakeConnectionPair()
        val protocol = protocol()

        val supervisor = SupervisorJob()
        val scope = CoroutineScope(Dispatchers.Default + supervisor)
        try {
            scope.launch { protocol.sendHello(pair.b, helloFromPeer(appId = "wrong-app")) }

            val channel = Channel<ProtocolEvent>(Channel.UNLIMITED)
            scope.launch {
                protocol.events(pair.a).collect { channel.send(it) }
                channel.close()
            }

            val err = assertFailsWith<P2pError.HandshakeRejected> {
                performHandshake(
                    protocol = protocol,
                    connection = pair.a,
                    events = channel,
                    localAppId = AppId("com.example"),
                    localPeerId = PeerId("local"),
                    localDeviceName = "LocalDev",
                    localPlatform = Platform.JVM_DESKTOP,
                    localTransports = setOf(TransportKind.LAN)
                )
            }
            assertEquals(true, err.message!!.contains("appId mismatch"))
        } finally {
            supervisor.cancel()
        }
    }

    @Test
    fun versionMismatchThrowsVersionMismatch() = runBlocking {
        val pair = FakeConnectionPair()
        val protocol = protocol()

        val supervisor = SupervisorJob()
        val scope = CoroutineScope(Dispatchers.Default + supervisor)
        try {
            scope.launch {
                protocol.sendHello(pair.b, helloFromPeer(protocolVersion = 99))
            }

            val channel = Channel<ProtocolEvent>(Channel.UNLIMITED)
            scope.launch {
                protocol.events(pair.a).collect { channel.send(it) }
                channel.close()
            }

            val err = assertFailsWith<P2pError.VersionMismatch> {
                performHandshake(
                    protocol = protocol,
                    connection = pair.a,
                    events = channel,
                    localAppId = AppId("com.example"),
                    localPeerId = PeerId("local"),
                    localDeviceName = "LocalDev",
                    localPlatform = Platform.JVM_DESKTOP,
                    localTransports = setOf(TransportKind.LAN)
                )
            }
            assertEquals(1, err.localVersion)
            assertEquals(99, err.remoteVersion)
        } finally {
            supervisor.cancel()
        }
    }

    @Test
    fun rejectionErrorWritePreservesOwnerCancellation() = runBlocking {
        val cancellation = CancellationException("owner cancelled during rejection write")
        val connection = CancelOnSecondWriteConnection(cancellation)
        val events = Channel<ProtocolEvent>(Channel.UNLIMITED).also {
            it.trySend(ProtocolEvent.Ping).getOrThrow()
        }

        val failure = assertFailsWith<CancellationException> {
            performHandshake(
                protocol = protocol(),
                connection = connection,
                events = events,
                localAppId = AppId("com.example"),
                localPeerId = PeerId("local"),
                localDeviceName = "LocalDev",
                localPlatform = Platform.JVM_DESKTOP,
                localTransports = setOf(TransportKind.LAN)
            )
        }

        assertSame(cancellation, failure)
        assertEquals(2, connection.writeAttempts)
    }
}

private class CancelOnSecondWriteConnection(
    private val cancellation: CancellationException,
) : RawConnection {
    override val state: StateFlow<ConnectionState> = MutableStateFlow(ConnectionState.Connected)
    var writeAttempts: Int = 0
        private set

    override suspend fun write(bytes: ByteArray) {
        writeAttempts++
        if (writeAttempts == 2) throw cancellation
    }

    override fun read(): Flow<ByteArray> = emptyFlow()

    override suspend fun close() = Unit
}
