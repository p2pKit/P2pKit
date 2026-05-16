package dev.p2pkit.core.protocol

import dev.p2pkit.core.P2pMessage
import dev.p2pkit.core.testfixtures.FakeConnectionPair
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.async
import kotlinx.coroutines.cancel
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.take
import kotlinx.coroutines.flow.toList
import kotlinx.coroutines.runBlocking
import kotlin.test.Test
import kotlin.test.assertContentEquals
import kotlin.test.assertEquals
import kotlin.test.assertIs

class DefaultP2pProtocolTest {

    private fun protocol() = DefaultP2pProtocol(clock = { 0L })

    private fun newScope(): CoroutineScope = CoroutineScope(Dispatchers.Default + SupervisorJob())

    @Test
    fun textRoundsTripViaLoopback() {
        runBlocking {
            val pair = FakeConnectionPair()
            val protocol = protocol()
            val scope = newScope()
            try {
                val deferred = scope.async {
                    protocol.events(pair.b).first { it is ProtocolEvent.Message }
                }
                protocol.sendMessage(pair.a, P2pMessage.Text("hello"))
                val event = deferred.await()
                val msg = assertIs<ProtocolEvent.Message>(event)
                val text = assertIs<P2pMessage.Text>(msg.message)
                assertEquals("hello", text.value)
            } finally {
                scope.cancel()
            }
        }
    }

    @Test
    fun binaryRoundsTripViaLoopback() {
        runBlocking {
            val pair = FakeConnectionPair()
            val protocol = protocol()
            val scope = newScope()
            try {
                val payload = ByteArray(2000) { (it and 0xFF).toByte() }
                val deferred = scope.async {
                    protocol.events(pair.b).first { it is ProtocolEvent.Message }
                }
                protocol.sendMessage(pair.a, P2pMessage.Binary(payload))
                val event = deferred.await()
                val msg = assertIs<ProtocolEvent.Message>(event)
                val bin = assertIs<P2pMessage.Binary>(msg.message)
                assertContentEquals(payload, bin.bytes)
            } finally {
                scope.cancel()
            }
        }
    }

    @Test
    fun largePayloadChunksAndReassembles() {
        runBlocking {
            val pair = FakeConnectionPair()
            val protocol = DefaultP2pProtocol(
                chunker = Chunker(chunkSize = 1024),
                clock = { 0L }
            )
            val scope = newScope()
            try {
                val payload = ByteArray(8 * 1024) { it.toByte() }
                val deferred = scope.async {
                    protocol.events(pair.b).first { it is ProtocolEvent.Message }
                }
                protocol.sendMessage(pair.a, P2pMessage.Binary(payload))
                val msg = (deferred.await() as ProtocolEvent.Message).message
                val bin = assertIs<P2pMessage.Binary>(msg)
                assertContentEquals(payload, bin.bytes)
            } finally {
                scope.cancel()
            }
        }
    }

    @Test
    fun pingAndPongAreDistinctEvents() {
        runBlocking {
            val pair = FakeConnectionPair()
            val protocol = protocol()
            val scope = newScope()
            try {
                val deferred = scope.async {
                    protocol.events(pair.b).take(2).toList()
                }
                protocol.sendPing(pair.a)
                protocol.sendPong(pair.a)
                val events = deferred.await()
                assertEquals(ProtocolEvent.Ping, events[0])
                assertEquals(ProtocolEvent.Pong, events[1])
            } finally {
                scope.cancel()
            }
        }
    }

    @Test
    fun helloRoundTripsAsEvent() {
        runBlocking {
            val pair = FakeConnectionPair()
            val protocol = protocol()
            val scope = newScope()
            try {
                val hello = HelloPayload(
                    appId = "com.example",
                    peerId = "p1",
                    deviceName = "D",
                    platform = "ANDROID",
                    supportedTransports = listOf("LAN")
                )
                val deferred = scope.async {
                    protocol.events(pair.b).first { it is ProtocolEvent.Hello }
                }
                protocol.sendHello(pair.a, hello)
                val event = deferred.await() as ProtocolEvent.Hello
                assertEquals(hello, event.payload)
            } finally {
                scope.cancel()
            }
        }
    }

    @Test
    fun closeEventIsEmitted() {
        runBlocking {
            val pair = FakeConnectionPair()
            val protocol = protocol()
            val scope = newScope()
            try {
                val deferred = scope.async {
                    protocol.events(pair.b).first { it is ProtocolEvent.Close }
                }
                protocol.sendClose(pair.a)
                deferred.await()
            } finally {
                scope.cancel()
            }
        }
    }

    @Test
    fun peerErrorCarriesReason() {
        runBlocking {
            val pair = FakeConnectionPair()
            val protocol = protocol()
            val scope = newScope()
            try {
                val deferred = scope.async {
                    protocol.events(pair.b).first { it is ProtocolEvent.PeerError }
                }
                protocol.sendError(pair.a, "appId mismatch")
                val event = deferred.await() as ProtocolEvent.PeerError
                assertEquals("appId mismatch", event.reason)
            } finally {
                scope.cancel()
            }
        }
    }
}
