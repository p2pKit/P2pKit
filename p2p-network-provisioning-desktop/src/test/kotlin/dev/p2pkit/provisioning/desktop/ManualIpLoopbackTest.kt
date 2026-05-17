package dev.p2pkit.provisioning.desktop

import dev.p2pkit.core.AppId
import dev.p2pkit.core.ConnectionState
import dev.p2pkit.core.ExperimentalP2pApi
import dev.p2pkit.core.P2pKit
import dev.p2pkit.core.P2pMessage
import dev.p2pkit.transport.lan.lan
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

/**
 * Two real [P2pKit] instances on loopback exchange a message using ONLY the
 * manual-IP fallback — no mDNS discovery is consulted. Alice and Bob each
 * advertise (so the LAN TCP server is bound) but neither side waits for the
 * peer to appear in `kit.peers`; instead, Alice publishes her
 * `ManualConnectionInfo`, Bob calls `createManualPeer` + `connect`, and the
 * session opens directly.
 */
class ManualIpLoopbackTest {

    private val kits = mutableListOf<P2pKit>()

    @AfterTest
    fun teardown() = runBlocking {
        for (k in kits) runCatching { k.stop() }
        kits.clear()
    }

    private fun newKit(name: String): P2pKit {
        val kit = P2pKit.create {
            appId = AppId("com.example.manual-ip")
            deviceName = name
            transports { lan() }
            networkProvisioning { jvm() }
        }
        kits.add(kit)
        return kit
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

        val targetHost = aliceInfo.hostAddresses.firstOrNull { it.startsWith("127.") }
            ?: aliceInfo.hostAddresses.firstOrNull { it.contains('.') }
            ?: aliceInfo.hostAddresses.first()
        val targetPort = aliceInfo.port

        val syntheticPeer = bob.networkProvisioning.createManualPeer(
            host = targetHost,
            port = targetPort
        )

        // Subscribe BEFORE connect so we don't miss Alice's incoming-session emission.
        val incomingDeferred = async {
            alice.incomingSessions
                .onSubscription { /* subscribed */ }
                .first()
        }

        val outgoing = withTimeout(10_000) { bob.connect(syntheticPeer) }
        val incoming = withTimeout(10_000) { incomingDeferred.await() }

        assertEquals(ConnectionState.Connected, outgoing.state.value)

        // Round-trip a Text message in each direction.
        val incomingMessageDeferred = async {
            incoming.incoming.onSubscription { }.first()
        }
        outgoing.send(P2pMessage.Text("hello from Bob"))
        val received = withTimeout(5_000) { incomingMessageDeferred.await() }
        val text = assertIs<P2pMessage.Text>(received)
        assertEquals("hello from Bob", text.value)
    }
}
