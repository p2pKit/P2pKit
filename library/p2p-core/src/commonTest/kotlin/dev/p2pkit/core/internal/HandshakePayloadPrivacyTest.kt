package dev.p2pkit.core.internal

import dev.p2pkit.core.AppId
import dev.p2pkit.core.P2pError
import dev.p2pkit.core.P2pMessage
import dev.p2pkit.core.PeerId
import dev.p2pkit.core.Platform
import dev.p2pkit.core.TransportKind
import dev.p2pkit.core.protocol.DefaultP2pProtocol
import dev.p2pkit.core.protocol.ProtocolConstants
import dev.p2pkit.core.protocol.ProtocolEvent
import dev.p2pkit.core.protocol.ProtocolSessionState
import dev.p2pkit.core.testfixtures.FakeConnectionPair
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.cancelAndJoin
import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.flow.take
import kotlinx.coroutines.flow.toList
import kotlinx.coroutines.launch
import kotlinx.coroutines.test.runTest
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertFalse
import kotlin.test.assertIs
import kotlin.test.assertNull
import kotlin.test.assertTrue

@OptIn(ExperimentalCoroutinesApi::class)
class HandshakePayloadPrivacyTest {
    @Test
    fun preHelloDataIsRejectedWithoutCopyingPayloadIntoDiagnosticsOnEitherWireProfile() = runTest {
        val marker = "private-peer-payload\nforged-line\u001b[31m\u202e"
        val maxPayload = ProtocolConstants.MAX_PAYLOAD_BYTES.toInt()
        val large = "x".repeat(maxPayload - marker.encodeToByteArray().size) + marker
        assertEquals(maxPayload, large.encodeToByteArray().size)
        var firstReason: String? = null
        for (version in listOf(ProtocolConstants.LEGACY_VERSION, ProtocolConstants.SECURE_VERSION)) {
            for (payload in listOf(marker, large)) {
                val pair = FakeConnectionPair()
                val protocol = DefaultP2pProtocol(clock = { testScheduler.currentTime }, version = version)
                val local = ProtocolSessionState("local", secure = version == ProtocolConstants.SECURE_VERSION)
                val remote = ProtocolSessionState("remote", secure = local.secure)
                val events = Channel<ProtocolEvent>(capacity = 1)
                val collector = backgroundScope.launch {
                    protocol.events(pair.a, local).collect { events.send(it) }
                }
                try {
                    // Real framing, strict UTF-8 decode and reassembly, before HELLO negotiation.
                    // For v2 this models plaintext records after the separate Noise layer.
                    protocol.sendMessage(pair.b, P2pMessage.Text(payload), remote)
                    val failure = assertFailsWith<P2pError.HandshakeRejected> {
                        performHandshake(
                            protocol, pair.a, events, AppId("privacy.test"), PeerId("local"),
                            "Local", Platform.JVM_DESKTOP, setOf(TransportKind.LAN),
                            protocolState = local, protocolVersion = version
                        )
                    }
                    assertTrue(failure.reason.length < 128, "Rejection text must be payload-size independent")
                    assertFalse(failure.reason.contains("private-peer-payload"))
                    assertFalse(failure.reason.any { it == '\n' || it == '\u001b' || it == '\u202e' })
                    assertTrue(failure.reason.contains("Message"), "Keep the event kind, not its value")
                    firstReason?.let { assertEquals(it, failure.reason) }
                    firstReason = failure.reason
                    assertNull(local.remotePeerId)
                    assertTrue(local.negotiatedFeatures.isEmpty())

                    val reply = protocol.events(pair.b, remote).take(2).toList()
                    assertIs<ProtocolEvent.Hello>(reply[0])
                    assertEquals("expected HELLO", assertIs<ProtocolEvent.PeerError>(reply[1]).reason)
                } finally {
                    collector.cancelAndJoin()
                    events.cancel()
                    pair.a.close()
                    pair.b.close()
                }
            }
        }
    }
}
