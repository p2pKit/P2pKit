package dev.p2pkit.core.internal

import dev.p2pkit.core.AppId
import dev.p2pkit.core.ConnectionState
import dev.p2pkit.core.ExperimentalP2pApi
import dev.p2pkit.core.P2pError
import dev.p2pkit.core.P2pKit
import dev.p2pkit.core.Peer
import dev.p2pkit.core.PeerId
import dev.p2pkit.core.Platform
import dev.p2pkit.core.TransportKind
import dev.p2pkit.core.provisioning.ManualPeerRegistrar
import dev.p2pkit.core.provisioning.NetworkProvisioningFactory
import dev.p2pkit.core.provisioning.NetworkProvisioningManager
import dev.p2pkit.core.provisioning.ProvisioningContext
import dev.p2pkit.core.provisioning.UnsupportedNetworkProvisioningManager
import dev.p2pkit.core.testfixtures.FakeConnectionPair
import dev.p2pkit.core.testfixtures.FakeDataTransport
import dev.p2pkit.core.transport.RawConnection
import dev.p2pkit.core.transport.TransportContext
import dev.p2pkit.core.transport.TransportFactory
import dev.p2pkit.core.transport.TransportPair
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withTimeout
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertNotEquals
import kotlin.test.assertSame
import kotlin.test.assertTrue

/**
 * Connect-level coverage for MANUAL-peer identity semantics in
 * [SessionManager.runHandshake] (provenance modeled via
 * [dev.p2pkit.core.transport.PeerOrigin], not the `"manual-"` id prefix).
 *
 * Invariants under test:
 *  - A session dialed via a manual peer keeps the DIALED synthetic identity,
 *    even though the remote's HELLO announces its real (different) PeerId.
 *    Adopting the HELLO identity registered the session under an id the
 *    caller never dials, which broke `connect()` idempotency and let a
 *    healthy session be torn down by Replaced arbitration.
 *  - Repeat `connect(manualPeer)` calls are idempotent: same session
 *    instance, exactly one store entry, no second dial.
 *  - The manual exemption from the HELLO peerId-mismatch check is driven by
 *    PROVENANCE: a DISCOVERED peer whose id merely starts with `"manual-"`
 *    is still rejected on mismatch.
 *  - The own-peerId collision guard still applies to manual connects (there
 *    the mismatch check is skipped, so it is the only line of defense).
 *
 * Harness mirrors [HandshakeIdentityTest]: two real [P2pKit] instances wired
 * over a single [FakeConnectionPair]. The dialer registers a provisioning
 * factory whose only job is to capture the kit's [ManualPeerRegistrar] so
 * the test can mint manual peers exactly the way a provisioning sidecar does.
 */
@OptIn(ExperimentalP2pApi::class)
class ManualPeerIdentityTest {

    /** Captures the kit's [ManualPeerRegistrar] at build time. */
    @OptIn(ExperimentalP2pApi::class)
    private class RegistrarCapture : NetworkProvisioningFactory {
        lateinit var registrar: ManualPeerRegistrar
        override fun build(context: ProvisioningContext): NetworkProvisioningManager {
            registrar = context.manualPeerRegistrar
            return UnsupportedNetworkProvisioningManager()
        }
    }

    private fun dialerKit(
        localId: String,
        transport: FakeDataTransport,
        capture: RegistrarCapture? = null
    ): P2pKit = P2pKit.create {
        appId = AppId("com.example.manualtest")
        deviceName = "Alice"
        peerIdStorage = InMemoryPeerIdStorage(seed = PeerId(localId))
        keepAlive {
            pingIntervalMillis = 60_000
            timeoutMillis = 120_000
        }
        transports {
            register(ManualPeerIdentityFactory(transport))
        }
        if (capture != null) {
            networkProvisioning { register(capture) }
        }
    }

    private fun remoteKit(localId: String, incoming: RawConnection): P2pKit =
        P2pKit.create {
            appId = AppId("com.example.manualtest")
            deviceName = "Bob"
            // The remote announces THIS id in its HELLO.
            peerIdStorage = InMemoryPeerIdStorage(seed = PeerId(localId))
            keepAlive {
                pingIntervalMillis = 60_000
                timeoutMillis = 120_000
            }
            transports {
                register(ManualPeerIdentityFactory(FakeDataTransport(preStagedIncoming = listOf(incoming))))
            }
        }

    private fun peer(id: String, name: String = "Bob"): Peer = Peer(
        id = PeerId(id),
        name = name,
        platform = Platform.JVM_DESKTOP,
        supportedTransports = setOf(TransportKind.LAN)
    )

    @Test
    fun manualConnectKeepsDialedSyntheticIdentityDespiteDifferentHelloId() = runBlocking<Unit> {
        val pair = FakeConnectionPair()
        val capture = RegistrarCapture()
        val alice = dialerKit(
            localId = "alice-id",
            transport = FakeDataTransport(outgoingConnection = { pair.a }),
            capture = capture
        )
        val bob = remoteKit(localId = "bob-real-id", incoming = pair.b)
        try {
            bob.start()
            val manualPeer = capture.registrar.registerManualPeer(host = "192.168.7.42", port = 40404)
            // Sanity: the minted id is synthetic, not the remote's real id.
            assertNotEquals("bob-real-id", manualPeer.id.value)

            val session = withTimeout(5_000) { alice.connect(manualPeer) }
            assertEquals(ConnectionState.Connected, session.state.value)
            assertEquals(
                manualPeer.id, session.peer.id,
                "manual session must keep the DIALED synthetic identity, " +
                    "not adopt the remote's HELLO id"
            )
            assertNotEquals("bob-real-id", session.peer.id.value)
        } finally {
            alice.stop()
            bob.stop()
        }
    }

    @Test
    fun manualConnectIsIdempotentAndDoesNotChurnTheSession() = runBlocking<Unit> {
        val pair = FakeConnectionPair()
        val capture = RegistrarCapture()
        val aliceTransport = FakeDataTransport(outgoingConnection = { pair.a })
        val alice = dialerKit(localId = "alice-id", transport = aliceTransport, capture = capture)
        val bob = remoteKit(localId = "bob-real-id", incoming = pair.b)
        try {
            bob.start()
            val manualPeer = capture.registrar.registerManualPeer(host = "192.168.7.42", port = 40404)

            val first = withTimeout(5_000) { alice.connect(manualPeer) }
            val second = withTimeout(5_000) { alice.connect(manualPeer) }

            assertSame(
                first, second,
                "repeat connect(manualPeer) must return the existing session instance"
            )
            assertEquals(1, aliceTransport.connectCalls.size, "second connect must not dial again")
            assertEquals(1, alice.sessions.value.size, "store must hold exactly one session")
            assertSame(first, alice.sessions.value.single())
            // No Replaced churn: the original session is still the live one.
            assertEquals(ConnectionState.Connected, first.state.value)
        } finally {
            alice.stop()
            bob.stop()
        }
    }

    @Test
    fun discoveredPeerWithManualLookingIdIsStillRejectedOnHelloMismatch() = runBlocking<Unit> {
        val pair = FakeConnectionPair()
        // No registrar involved: Alice dials a DISCOVERED-provenance peer whose
        // advertised id happens to start with "manual-". Under the old
        // prefix-sniffing detection this dodged the anti-spoof check; with
        // explicit provenance it must still be rejected on mismatch.
        val alice = dialerKit(
            localId = "alice-id",
            transport = FakeDataTransport(outgoingConnection = { pair.a })
        )
        val impostor = remoteKit(localId = "impostor-id", incoming = pair.b)
        try {
            impostor.start()
            val err = assertFailsWith<P2pError.HandshakeRejected> {
                withTimeout(5_000) { alice.connect(peer("manual-looking-advertised-id")) }
            }
            assertTrue(
                err.reason.contains("peerId mismatch"),
                "expected a peerId-mismatch rejection (provenance, not prefix, drives the " +
                    "manual exemption), got: ${err.reason}"
            )
        } finally {
            alice.stop()
            impostor.stop()
        }
    }

    @Test
    fun manualConnectStillRejectsHelloClaimingOurOwnPeerId() = runBlocking<Unit> {
        val pair = FakeConnectionPair()
        val capture = RegistrarCapture()
        val alice = dialerKit(
            localId = "alice-id",
            transport = FakeDataTransport(outgoingConnection = { pair.a }),
            capture = capture
        )
        // The device answering the manual host:port claims Alice's OWN id. The
        // manual exemption skips the mismatch check, so the self-collision
        // guard is the only remaining defense — it must still reject.
        val evil = remoteKit(localId = "alice-id", incoming = pair.b)
        try {
            evil.start()
            val manualPeer = capture.registrar.registerManualPeer(host = "192.168.7.42", port = 40404)
            val err = assertFailsWith<P2pError.HandshakeRejected> {
                withTimeout(5_000) { alice.connect(manualPeer) }
            }
            assertTrue(
                err.reason.contains("our own peerId"),
                "expected a self-collision rejection, got: ${err.reason}"
            )
        } finally {
            alice.stop()
            evil.stop()
        }
    }
}

private class ManualPeerIdentityFactory(private val transport: FakeDataTransport) : TransportFactory {
    override fun build(context: TransportContext): TransportPair =
        TransportPair(data = transport, discovery = null)
}
