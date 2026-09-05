package dev.p2pkit.sample.kmp

import dev.p2pkit.core.ConnectionState
import dev.p2pkit.core.P2pKit
import dev.p2pkit.core.P2pMessage
import dev.p2pkit.core.P2pSession
import dev.p2pkit.core.Peer
import dev.p2pkit.core.PeerFingerprint
import dev.p2pkit.core.PeerId
import dev.p2pkit.core.Platform
import dev.p2pkit.core.transfer.P2pFileOffer
import dev.p2pkit.core.transfer.P2pFileTransfer
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.runBlocking
import kotlinx.io.RawSource
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertNotNull
import kotlin.test.assertSame
import kotlin.test.assertTrue

/** Synthetic discovery/session boundary test; the loopback suite separately executes real secure TCP. */
class PairingDemoTest {
    @Test
    fun demoPresentsItsFullQrBeforeDiscoveryAndUsesOnlyTheExplicitPinOverload() = runBlocking {
        val base = createP2pKit("synthetic.pairing.demo", "Synthetic demo")
        try {
            val calls = mutableListOf<String>()
            val fingerprint = assertNotNull(base.localFingerprint)
            val kit = demoKit(base, calls, fingerprint)
            var displayed: String? = null
            val result = runDiscoverAndGreet(kit, "Alice", fingerprint, {
                displayed = it
                calls += "display"
            })
            assertEquals(base.localPairingQr, displayed)
            assertEquals(fingerprint, base.parsePeerPairingQr(assertNotNull(displayed)))
            assertEquals(listOf("display", "advertise", "discover", "pin", "send", "close", "stop"), calls)
            assertTrue(result.startsWith("sent greeting"))
        } finally {
            base.stop()
        }
    }

    @Test
    fun displayFailureStillStopsTheOwnedKitWithoutAdvertising() = runBlocking {
        val base = createP2pKit("synthetic.pairing.demo", "Synthetic demo")
        try {
            val calls = mutableListOf<String>()
            val fingerprint = assertNotNull(base.localFingerprint)
            val failure = IllegalStateException("synthetic presentation failure")
            assertSame(failure, assertFailsWith<IllegalStateException> {
                runDiscoverAndGreet(demoKit(base, calls, fingerprint), "Alice", fingerprint, { throw failure })
            })
            assertEquals(listOf("stop"), calls)
        } finally {
            base.stop()
        }
    }

    @Test
    fun connectCancellationPropagatesAndStopsWithoutSending() = runBlocking {
        val base = createPinnedP2pKit("synthetic.pairing.demo", "Synthetic demo", emptySet())
        try {
            val calls = mutableListOf<String>()
            val fingerprint = assertNotNull(base.localFingerprint)
            val cancellation = CancellationException("synthetic connect cancellation")
            val kit = demoKit(base, calls, fingerprint, cancellation)
            assertSame(cancellation, assertFailsWith<CancellationException> {
                runDiscoverAndGreet(kit, "Alice", fingerprint, {})
            })
            assertEquals(listOf("advertise", "discover", "pin", "stop"), calls)
        } finally {
            base.stop()
        }
    }

    private fun demoKit(
        base: P2pKit,
        calls: MutableList<String>,
        fingerprint: PeerFingerprint,
        failure: Throwable? = null
    ): P2pKit {
        val discovered = Peer(PeerId("synthetic-discovered"), "Synthetic peer", Platform.UNKNOWN, emptySet())
        val session = object : P2pSession {
            override val id = "synthetic-session"
            override val peer = discovered
            override val state = MutableStateFlow(ConnectionState.Connected)
            override val incoming = MutableSharedFlow<P2pMessage>()
            @Deprecated("Observe pendingFileOffers")
            override val incomingFiles = MutableSharedFlow<P2pFileOffer>()
            override suspend fun send(message: P2pMessage) {
                assertEquals(P2pMessage.Text("hello from Alice"), message)
                calls += "send"
            }
            override suspend fun close() { calls += "close" }
            @Deprecated("Legacy only")
            override suspend fun sendFile(
                name: String, sizeBytes: Long, mimeType: String?, source: RawSource
            ): P2pFileTransfer = error("not used")
        }
        return object : P2pKit by base {
            override val peers = MutableStateFlow(listOf(discovered))
            override suspend fun startAdvertising() { calls += "advertise" }
            override suspend fun startDiscovery() { calls += "discover" }
            override suspend fun connect(peer: Peer): P2pSession = error("unpinned connect must never be used")
            override suspend fun connect(peer: Peer, expectedFingerprint: PeerFingerprint): P2pSession {
                assertSame(discovered, peer)
                assertEquals(fingerprint, expectedFingerprint)
                calls += "pin"
                failure?.let { throw it }
                return session
            }
            override suspend fun stop() {
                calls += "stop"
                base.stop()
            }
        }
    }
}
