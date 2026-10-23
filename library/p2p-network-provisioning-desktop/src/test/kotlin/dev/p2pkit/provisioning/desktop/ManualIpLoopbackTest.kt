package dev.p2pkit.provisioning.desktop

import dev.p2pkit.core.AppId
import dev.p2pkit.core.ConnectionState
import dev.p2pkit.core.ExperimentalP2pApi
import dev.p2pkit.core.ExplicitSecurityRisk
import dev.p2pkit.core.P2pKit
import dev.p2pkit.core.P2pMessage
import dev.p2pkit.core.PeerAuthorizationPolicy
import dev.p2pkit.core.SecurityMode
import dev.p2pkit.core.dsl.jvmSecureIdentityStore
import dev.p2pkit.transport.lan.lan
import java.net.InetAddress
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.async
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.onSubscription
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withTimeout
import kotlin.test.AfterTest
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertIs
import kotlin.test.assertNotNull
import kotlin.test.assertTrue

/**
 * Two real [P2pKit] instances on loopback exchange a message using ONLY the
 * manual-IP fallback — neither advertises nor starts mDNS discovery. Both
 * start their TCP listeners directly. Alice's `ManualConnectionInfo` supplies
 * her bound port and full fingerprint; Bob registers that owned listener at
 * numeric loopback rather than selecting an environment-dependent host address.
 * Neither side waits for a discovered peer before opening the secure session.
 */
@OptIn(ExplicitSecurityRisk::class)
class ManualIpLoopbackTest {

    private val diagnostics = KitTestDiagnostics()

    @AfterTest
    fun teardown() = runBlocking {
        diagnostics.finish()
    }

    private fun newKit(name: String): P2pKit {
        return diagnostics.create { recording ->
            P2pKit.create {
                logger = recording
                appId = AppId("com.example.manual-ip")
                deviceName = name
                jvmSecureIdentityStore(InMemoryTestJvmSecureIdentityStore())
                security {
                    mode = SecurityMode.AuthenticatedV2(
                        PeerAuthorizationPolicy.AcceptAnyAuthenticatedSameApp
                    )
                }
                transports { lan() }
                networkProvisioning { jvm() }
            }
        }
    }

    @OptIn(ExperimentalP2pApi::class)
    @Test
    fun manualPeerConnectsAndRoundTripsAMessage() = runBlocking<Unit> {
        val alice = newKit("Alice")
        val bob = newKit("Bob")

        // Since the v0.3 transport-lifecycle refactor, the LAN data transport
        // binds its server socket in `start()` rather than the factory. Manual
        // IP must work *without discovery* — so we call `start()` directly
        // instead of `startAdvertising()`/`startDiscovery()`, which is the
        // whole point of this test: both ports are bound and reachable, but
        // no mDNS traffic is exchanged.
        alice.start()
        bob.start()

        val aliceInfo = alice.networkProvisioning.getManualConnectionInfo()
        assertNotNull(aliceInfo, "Alice should have a ManualConnectionInfo from JVM provisioning")

        // Provisioning deliberately reports non-loopback candidates for remote
        // users, not a selected route for this same-host fixture. Those candidates
        // need not match the LAN listener's current admitted interface. Keep that
        // production filter intact and use its explicit same-host loopback path.
        val targetHost = "127.0.0.1"
        assertTrue(InetAddress.getByName(targetHost).isLoopbackAddress,
            "The same-host manual-IP fixture must use a loopback destination")
        val targetPort = aliceInfo.port

        val syntheticPeer = bob.networkProvisioning.createManualPeer(
            host = targetHost,
            port = targetPort,
            expectedFingerprint = assertNotNull(aliceInfo.fingerprint)
        )

        // Subscribe BEFORE connect so we don't miss Alice's incoming-session emission.
        val incomingSubscribed = CompletableDeferred<Unit>()
        val incomingDeferred = async {
            alice.incomingSessions
                .onSubscription { incomingSubscribed.complete(Unit) }
                .first()
        }
        withTimeout(5_000) { incomingSubscribed.await() }

        val outgoing = withTimeout(10_000) { bob.connect(syntheticPeer) }
        val incoming = withTimeout(10_000) { incomingDeferred.await() }

        assertEquals(ConnectionState.Connected, outgoing.state.value)
        assertEquals(aliceInfo.fingerprint, outgoing.peerIdentity.fingerprint)

        // Deliver and verify a Text message from Bob to Alice.
        val messageSubscribed = CompletableDeferred<Unit>()
        val incomingMessageDeferred = async {
            incoming.incoming
                .onSubscription { messageSubscribed.complete(Unit) }
                .first()
        }
        withTimeout(5_000) { messageSubscribed.await() }
        outgoing.send(P2pMessage.Text("hello from Bob"))
        val received = withTimeout(5_000) { incomingMessageDeferred.await() }
        val text = assertIs<P2pMessage.Text>(received)
        assertEquals("hello from Bob", text.value)
    }
}
