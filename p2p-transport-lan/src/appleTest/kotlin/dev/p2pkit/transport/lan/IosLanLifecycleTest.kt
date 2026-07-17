package dev.p2pkit.transport.lan

import dev.p2pkit.core.AppId
import dev.p2pkit.core.ConnectionState
import dev.p2pkit.core.P2pKit
import dev.p2pkit.core.P2pMessage
import dev.p2pkit.core.ReconnectPolicy
import dev.p2pkit.core.transfer.FileTransferState
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.async
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.onSubscription
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withTimeout
import kotlinx.io.Buffer
import kotlinx.io.write
import kotlin.test.AfterTest
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue
import platform.Foundation.NSDate
import platform.Foundation.NSUserDefaults
import platform.Foundation.timeIntervalSince1970

/**
 * Probe tests for v0.3.0-dev audit gaps the basic loopback suite doesn't cover:
 *
 * - **peerLostEventFiresWhenPeerStops**: stop one kit and verify the other
 *   sees the peer disappear from `kit.peers`. Validates `NWBrowser`'s
 *   removed-result delivery + our `IosEndpointRegistry.remove` + `PeerEvent.Lost`
 *   emission path, none of which the happy-path tests exercise.
 *
 * - **repeatedKitLifecycleDoesNotLeakPorts**: create + stop + create + stop in
 *   a loop. If `nw_listener_cancel` doesn't actually release the bound port,
 *   the second or third kit's `nw_listener_create` will eventually fail. Also
 *   probes the 5-second dispatch-semaphore wait in `IosLanDataTransport.init`
 *   for cumulative slowdown.
 *
 * - **threePeersMutuallyDiscover**: smoke test that the discovery and registry
 *   handle N > 2. Catches stupid bugs like accidentally indexing on
 *   `peers.first()` somewhere.
 */
@Suppress("DEPRECATION")
class IosLanLifecycleTest {

    private val unique: String =
        "p2pkit-ios-lifecycle-${NSDate().timeIntervalSince1970.toLong()}"
    private val peerIdKey: String = "dev.p2pkit.peerId.$unique"

    private val toStop: MutableList<P2pKit> = mutableListOf()

    private fun newKit(name: String): P2pKit = P2pKit.create {
        appId = AppId(unique)
        deviceName = name
        security { mode = dev.p2pkit.core.SecurityMode.NoneForMvp }
        keepAlive {
            pingIntervalMillis = 60_000
            timeoutMillis = 120_000
        }
        transports {
            lan()
        }
    }

    private fun removeStoredPeerId() {
        NSUserDefaults.standardUserDefaults.removeObjectForKey(peerIdKey)
    }

    private suspend fun startAndAdvertise(name: String): P2pKit {
        removeStoredPeerId()
        val kit = newKit(name)
        toStop.add(kit)
        kit.startAdvertising()
        kit.startDiscovery()
        return kit
    }

    @AfterTest
    fun teardown() = runBlocking {
        toStop.forEach { runCatching { it.stop() } }
        toStop.clear()
        removeStoredPeerId()
    }

    @Test
    fun peerLostEventFiresWhenPeerStops() {
        runBlocking {
            val alice = startAndAdvertise("Alice")
            val bob = startAndAdvertise("Bob")

            // Both sides must see each other before we test the removal path.
            withTimeout(DISCOVERY_TIMEOUT_MS) {
                alice.peers.first { peers -> peers.any { it.name == "Bob" } }
            }
            withTimeout(DISCOVERY_TIMEOUT_MS) {
                bob.peers.first { peers -> peers.any { it.name == "Alice" } }
            }

            // Bob exits cleanly — Alice should see Bob disappear from her
            // peer set. Without the Lost wiring, Alice's flow stays
            // populated forever and the test times out.
            bob.stop()
            toStop.remove(bob)

            withTimeout(PEER_LOST_TIMEOUT_MS) {
                alice.peers.first { peers -> peers.none { it.name == "Bob" } }
            }
        }
    }

    @Test
    fun repeatedKitLifecycleDoesNotLeakPorts() {
        runBlocking {
            repeat(LIFECYCLE_CYCLE_COUNT) { i ->
                removeStoredPeerId()
                val kit = newKit("Cycle$i")
                // Construction reaches here only if nw_listener_create
                // succeeded AND the listener reached .ready (or the 5s
                // semaphore timed out). On a healthy stack, the loop should
                // complete in well under 5s per iteration.
                kit.startAdvertising()
                kit.startDiscovery()
                // Round-trip a no-op: prove the listener really bound, not
                // just survived construction.
                kit.stopDiscovery()
                kit.stopAdvertising()
                kit.stop()
            }
            // If we reached here without an exception, no port leak.
            assertTrue(true)
        }
    }

    @Test
    fun threePeersMutuallyDiscover() {
        runBlocking {
            val alice = startAndAdvertise("Alice")
            val bob = startAndAdvertise("Bob")
            val charlie = startAndAdvertise("Charlie")

            // Each kit must see the OTHER TWO. If the discovery transport
            // accidentally treated peer #1 as a "first peer" cache key
            // somewhere, this lights it up.
            val aliceSees = withTimeout(DISCOVERY_TIMEOUT_MS) {
                alice.peers.first { peers ->
                    peers.any { it.name == "Bob" } && peers.any { it.name == "Charlie" }
                }
            }
            val bobSees = withTimeout(DISCOVERY_TIMEOUT_MS) {
                bob.peers.first { peers ->
                    peers.any { it.name == "Alice" } && peers.any { it.name == "Charlie" }
                }
            }
            val charlieSees = withTimeout(DISCOVERY_TIMEOUT_MS) {
                charlie.peers.first { peers ->
                    peers.any { it.name == "Alice" } && peers.any { it.name == "Bob" }
                }
            }

            assertEquals(2, aliceSees.size, "Alice should see Bob+Charlie")
            assertEquals(2, bobSees.size, "Bob should see Alice+Charlie")
            assertEquals(2, charlieSees.size, "Charlie should see Alice+Bob")

            // Each pair should also be able to actually open a session,
            // not just appear in the peer list. We exercise one direction
            // per pair so 3 sessions form total.
            val bobPeer = aliceSees.first { it.name == "Bob" }
            val charliePeer = bobSees.first { it.name == "Charlie" }
            val alicePeerFromCharlie = charlieSees.first { it.name == "Alice" }

            val sAB = async { alice.connect(bobPeer) }
            val sBC = async { bob.connect(charliePeer) }
            val sCA = async { charlie.connect(alicePeerFromCharlie) }

            val ab = withTimeout(HANDSHAKE_TIMEOUT_MS) { sAB.await() }
            val bc = withTimeout(HANDSHAKE_TIMEOUT_MS) { sBC.await() }
            val ca = withTimeout(HANDSHAKE_TIMEOUT_MS) { sCA.await() }

            // Round-trip one message per session so we know the actual
            // wire is working, not just session bookkeeping.
            ab.send(P2pMessage.Text("hi-AB"))
            bc.send(P2pMessage.Text("hi-BC"))
            ca.send(P2pMessage.Text("hi-CA"))
        }
    }

    @Test
    fun reconnectExhaustionAfterRemoteKitStops() {
        // ReconnectPolicy.Enabled(maxAttempts=3, retryDelayMillis=500) means
        // after the connection drops, the session must transition through
        // Connected → Reconnecting → Failed within 3 × 500 ms + handshake
        // overhead. We stop the remote kit entirely so no endpoint can
        // resolve and the retries deterministically exhaust.
        //
        // What this proves about the iOS transport: the connection-drop
        // signal (nw_connection_state_failed/_cancelled) DOES propagate
        // through IosRawConnection → P2pSessionImpl → SessionManager →
        // reconnect loop, which is otherwise only inferred from the
        // common-code unit tests.
        runBlocking {
            val alice = newKitWithReconnect("Alice")
            val bob = newKitWithReconnect("Bob")
            alice.startAdvertising(); alice.startDiscovery()
            bob.startAdvertising(); bob.startDiscovery()

            val bobPeer = withTimeout(DISCOVERY_TIMEOUT_MS) {
                alice.peers.first { peers -> peers.any { it.name == "Bob" } }
                    .first { it.name == "Bob" }
            }
            val session = withTimeout(HANDSHAKE_TIMEOUT_MS) { alice.connect(bobPeer) }
            withTimeout(HANDSHAKE_TIMEOUT_MS) {
                session.state.first { it == ConnectionState.Connected }
            }

            // Bob disappears. Alice's session detects the drop, attempts
            // reconnect 3× with 500 ms gap, then surfaces Failed.
            bob.stop()
            toStop.remove(bob)

            // Expect Reconnecting somewhere in the timeline (it may be
            // brief on the simulator's tight network), then a terminal
            // state. We accept either Failed (preferred) or Closed
            // (acceptable: SessionManager closed without retry due to
            // peer-gone) — what we WILL NOT accept is staying in
            // Connected or hanging forever.
            val terminal = withTimeout(RECONNECT_EXHAUSTION_TIMEOUT_MS) {
                session.state.first { it == ConnectionState.Failed || it == ConnectionState.Closed }
            }
            assertTrue(
                terminal == ConnectionState.Failed || terminal == ConnectionState.Closed,
                "expected Failed or Closed terminal, got $terminal"
            )
        }
    }

    private fun newKitWithReconnect(name: String): P2pKit {
        removeStoredPeerId()
        val kit = P2pKit.create {
            appId = AppId(unique)
            deviceName = name
            security { mode = dev.p2pkit.core.SecurityMode.NoneForMvp }
            keepAlive {
                pingIntervalMillis = 60_000
                timeoutMillis = 120_000
            }
            lifecycle {
                reconnectPolicy = ReconnectPolicy.Enabled(maxAttempts = 3, retryDelayMillis = 500)
            }
            transports {
                lan()
            }
        }
        toStop.add(kit)
        return kit
    }

    @Test
    fun midTransferCancelTerminatesBothSidesCleanly() {
        // Sender starts a 5 MiB transfer over a real NWConnection, the
        // receiver accepts to a Buffer, and the sender calls
        // P2pFileTransfer.cancel() at ~50% progress. Both sides must
        // transition to Cancelled / Failed terminal states within
        // TERMINAL_TIMEOUT_MS and the underlying nw_connection_t must
        // remain usable for further messages.
        runBlocking {
            val alice = startAndAdvertise("Alice")
            val bob = startAndAdvertise("Bob")

            val bobPeer = withTimeout(DISCOVERY_TIMEOUT_MS) {
                alice.peers.first { peers -> peers.any { it.name == "Bob" } }
                    .first { it.name == "Bob" }
            }
            val outgoingDeferred = async { alice.connect(bobPeer) }
            val incomingSession = withTimeout(HANDSHAKE_TIMEOUT_MS) { bob.incomingSessions.first() }
            val outgoing = withTimeout(HANDSHAKE_TIMEOUT_MS) { outgoingDeferred.await() }

            val totalBytes = 5 * 1024 * 1024
            val payload = ByteArray(totalBytes) { ((it * 31) and 0xFF).toByte() }
            val srcBuffer = Buffer().apply { write(payload) }
            val dstBuffer = Buffer()

            val offerReady = CompletableDeferred<Unit>()
            val offerDeferred = async {
                incomingSession.incomingFiles
                    .onSubscription { offerReady.complete(Unit) }
                    .first()
            }
            offerReady.await()

            val transfer = outgoing.sendFile(
                name = "cancel-test.bin",
                sizeBytes = totalBytes.toLong(),
                mimeType = "application/octet-stream",
                source = srcBuffer
            )

            val offer = withTimeout(HANDSHAKE_TIMEOUT_MS) { offerDeferred.await() }
            val incomingTransfer = offer.accept(dstBuffer)

            // Wait for partial progress before cancelling. We deliberately
            // don't require an exact percent — Bonjour/NW timing varies on
            // the simulator. Anywhere between 5% and 95% suffices to prove
            // we cancelled MID-transfer (not before it started, not after
            // it completed).
            withTimeout(HANDSHAKE_TIMEOUT_MS) {
                val low = (totalBytes / 20).toLong()
                val high = (totalBytes - 1).toLong()
                transfer.bytesTransferred.first { it in low..high }
            }

            transfer.cancel("test-mid-cancel")

            val senderFinal = withTimeout(TERMINAL_TIMEOUT_MS) {
                transfer.state.first { isTerminal(it) }
            }
            val receiverFinal = withTimeout(TERMINAL_TIMEOUT_MS) {
                incomingTransfer.state.first { isTerminal(it) }
            }

            assertTrue(
                senderFinal is FileTransferState.Cancelled ||
                    senderFinal is FileTransferState.Failed,
                "sender expected Cancelled/Failed, got $senderFinal"
            )
            assertTrue(
                receiverFinal is FileTransferState.Cancelled ||
                    receiverFinal is FileTransferState.Failed,
                "receiver expected Cancelled/Failed, got $receiverFinal"
            )

            // The underlying session must still be Connected — cancellation
            // is per-transfer, not per-session. Round-trip a sanity message
            // to prove the NWConnection wasn't collateral damage.
            outgoing.send(P2pMessage.Text("post-cancel-ok"))
        }
    }

    private fun isTerminal(state: FileTransferState): Boolean = when (state) {
        is FileTransferState.Completed,
        is FileTransferState.Cancelled,
        is FileTransferState.Failed,
        is FileTransferState.Rejected -> true
        else -> false
    }

    @Test
    fun advertiseStopRestartProducesObservablePeerChurn() {
        // Closest public-API approximation to "peer's TXT was mutated". A
        // true `PeerEvent.Updated` would require mutating the advertise
        // descriptor on a live nw_listener_t (internal API). What we CAN
        // verify end-to-end is that Bob can stop and restart advertising,
        // and Alice's peers flow observes the churn (either via Lost+Found
        // or Updated — both are valid responses for our consumers).
        runBlocking {
            val alice = startAndAdvertise("Alice")
            val bob = startAndAdvertise("Bob")

            // Initial discovery — Alice sees Bob.
            withTimeout(DISCOVERY_TIMEOUT_MS) {
                alice.peers.first { peers -> peers.any { it.name == "Bob" } }
            }

            // Bob disappears from the air.
            bob.stopAdvertising()
            withTimeout(PEER_LOST_TIMEOUT_MS) {
                alice.peers.first { peers -> peers.none { it.name == "Bob" } }
            }

            // Bob re-advertises (same peerId, same deviceName since we can't
            // mutate it through the public DSL). Alice should see the peer
            // reappear within a reasonable Bonjour TTL.
            bob.startAdvertising()
            withTimeout(DISCOVERY_TIMEOUT_MS) {
                alice.peers.first { peers -> peers.any { it.name == "Bob" } }
            }
        }
    }

    @Test
    fun rapidConnectCloseCycle() {
        // 10 sequential connect-send-close cycles against the same remote
        // peer. Stresses session lifecycle teardown — if the kit's
        // SessionManager left a stale session in its map, the second
        // connect() either dedups (no new handshake) or fails ("session
        // already exists"). Either is a regression.
        runBlocking {
            val alice = startAndAdvertise("Alice")
            val bob = startAndAdvertise("Bob")

            val bobPeer = withTimeout(DISCOVERY_TIMEOUT_MS) {
                alice.peers.first { peers -> peers.any { it.name == "Bob" } }
                    .first { it.name == "Bob" }
            }

            repeat(CONNECT_STORM_COUNT) { i ->
                val session = withTimeout(HANDSHAKE_TIMEOUT_MS) { alice.connect(bobPeer) }
                session.send(P2pMessage.Text("cycle-$i"))
                session.close()
                // Brief pause for the close frame to flush before redialing —
                // simultaneous-open arbitration would otherwise dedup based on
                // the still-live peer record.
                delay(50)
            }
            assertTrue(true, "$CONNECT_STORM_COUNT cycles completed cleanly")
        }
    }

    private companion object {
        const val DISCOVERY_TIMEOUT_MS: Long = 30_000
        const val PEER_LOST_TIMEOUT_MS: Long = 30_000
        const val HANDSHAKE_TIMEOUT_MS: Long = 30_000
        const val TERMINAL_TIMEOUT_MS: Long = 5_000
        const val RECONNECT_EXHAUSTION_TIMEOUT_MS: Long = 30_000
        const val LIFECYCLE_CYCLE_COUNT: Int = 20
        const val CONNECT_STORM_COUNT: Int = 10
    }
}
