package dev.p2pkit.core.internal

import dev.p2pkit.core.AppId
import dev.p2pkit.core.ConnectionState
import dev.p2pkit.core.P2pError
import dev.p2pkit.core.P2pKit
import dev.p2pkit.core.Peer
import dev.p2pkit.core.PeerId
import dev.p2pkit.core.Platform
import dev.p2pkit.core.TransportKind
import dev.p2pkit.core.testfixtures.FakeConnectionPair
import dev.p2pkit.core.testfixtures.FakeDataTransport
import dev.p2pkit.core.testfixtures.createTestKit
import dev.p2pkit.core.transport.RawConnection
import dev.p2pkit.core.transport.TransportContext
import dev.p2pkit.core.transport.TransportFactory
import dev.p2pkit.core.transport.TransportPair
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withTimeout
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertTrue

/**
 * Connect-level coverage for the OUTGOING peerId anti-spoof check in
 * [SessionManager.runHandshake]. This complements [HandshakeTest], which
 * unit-tests the pure [performHandshake] protocol exchange — the identity
 * verification itself lives in SessionManager, not in `performHandshake`, so it
 * can only be exercised through a real `connect()`.
 *
 * Why it matters (Spec §; `SecurityMode.NoneForMvp`): any LAN device can answer
 * on the discovery-supplied host:port, so the dialer must verify the remote's
 * HELLO `peerId` matches who it intended to reach, and must reject a remote that
 * claims the dialer's OWN id (which would poison the by-peer slot /
 * simultaneous-open tie-break).
 *
 * Harness mirrors [SessionFlowTest]: two real [P2pKit] instances wired over a
 * single [FakeConnectionPair], each side's persisted PeerId pinned via
 * [InMemoryPeerIdStorage] so the identities under test are deterministic.
 */
class HandshakeIdentityTest {

    private fun outgoingKit(localId: String, outgoing: RawConnection): P2pKit =
        createTestKit {
            appId = AppId("com.example.test")
            deviceName = "Alice"
            peerIdStorage = InMemoryPeerIdStorage(seed = PeerId(localId))
            keepAlive {
                pingIntervalMillis = 60_000
                timeoutMillis = 120_000
            }
            transports {
                register(HandshakeIdentityFactory(FakeDataTransport(outgoingConnection = { outgoing })))
            }
        }

    private fun incomingKit(localId: String, incoming: RawConnection): P2pKit =
        createTestKit {
            appId = AppId("com.example.test")
            deviceName = "Bob"
            // The remote announces THIS id in its HELLO.
            peerIdStorage = InMemoryPeerIdStorage(seed = PeerId(localId))
            keepAlive {
                pingIntervalMillis = 60_000
                timeoutMillis = 120_000
            }
            transports {
                register(HandshakeIdentityFactory(FakeDataTransport(preStagedIncoming = listOf(incoming))))
            }
        }

    private fun peer(id: String, name: String = "Bob"): Peer = Peer(
        id = PeerId(id),
        name = name,
        platform = Platform.JVM_DESKTOP,
        supportedTransports = setOf(TransportKind.LAN)
    )

    @Test
    fun connectSucceedsWhenRemotePeerIdMatchesDialedId() = runBlocking<Unit> {
        val pair = FakeConnectionPair()
        val alice = outgoingKit(localId = "alice-id", outgoing = pair.a)
        val bob = incomingKit(localId = "bob-id", incoming = pair.b)
        try {
            bob.start() // ensure Bob accepts the staged inbound connection
            val session = withTimeout(5_000) { alice.connect(peer("bob-id")) }
            assertEquals(ConnectionState.Connected, session.state.value)
            assertEquals("bob-id", session.peer.id.value)
        } finally {
            alice.stop()
            bob.stop()
        }
    }

    @Test
    fun connectRejectsWhenRemotePeerIdDoesNotMatchDialedId() = runBlocking<Unit> {
        val pair = FakeConnectionPair()
        val alice = outgoingKit(localId = "alice-id", outgoing = pair.a)
        // Alice dials "bob-id" but the device answering actually persists a
        // different identity — a spoof / host:port race.
        val impostor = incomingKit(localId = "impostor-id", incoming = pair.b)
        try {
            impostor.start()
            val err = assertFailsWith<P2pError.HandshakeRejected> {
                withTimeout(5_000) { alice.connect(peer("bob-id")) }
            }
            assertTrue(
                err.reason.contains("peerId mismatch"),
                "expected a peerId-mismatch rejection, got: ${err.reason}"
            )
        } finally {
            alice.stop()
            impostor.stop()
        }
    }

    @Test
    fun connectRejectsWhenRemoteClaimsOurOwnPeerId() = runBlocking<Unit> {
        val pair = FakeConnectionPair()
        // Alice's own id and the dialed id are both "shared-id"; the remote also
        // announces "shared-id". The mismatch check passes (dialed == announced),
        // so the self-collision guard is the one that must reject.
        val alice = outgoingKit(localId = "shared-id", outgoing = pair.a)
        val bob = incomingKit(localId = "shared-id", incoming = pair.b)
        try {
            bob.start()
            val err = assertFailsWith<P2pError.HandshakeRejected> {
                withTimeout(5_000) { alice.connect(peer("shared-id")) }
            }
            assertTrue(
                err.reason.contains("our own peerId"),
                "expected a self-collision rejection, got: ${err.reason}"
            )
        } finally {
            alice.stop()
            bob.stop()
        }
    }
}

private class HandshakeIdentityFactory(private val transport: FakeDataTransport) : TransportFactory {
    override val descriptor =
        dev.p2pkit.core.transport.TransportDescriptor.dataOnly(transport.type)
    override fun build(context: TransportContext): TransportPair =
        TransportPair(data = transport, discovery = null)
}
