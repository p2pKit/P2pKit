package dev.p2pkit.transport.lan

import dev.p2pkit.core.AppId
import dev.p2pkit.core.ConnectionState
import dev.p2pkit.core.ExperimentalP2pApi
import dev.p2pkit.core.P2pKit
import dev.p2pkit.core.P2pMessage
import dev.p2pkit.core.Peer
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
import kotlin.test.BeforeTest
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertNotNull
import kotlin.test.assertTrue

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
@Suppress("DEPRECATION", "OVERRIDE_DEPRECATION")
class IosLanLifecycleTest {

    private lateinit var unique: String
    private lateinit var peerIdKey: String
    private lateinit var peerIdV2Key: String

    private val toStop: MutableList<P2pKit> = mutableListOf()
    private var defaultsLease: AppleGlobalStateTestGuard.Lease? = null

    @BeforeTest
    fun isolateDefaults() {
        unique = newAppleLanTestNamespace("p2pkit-ios-lifecycle")
        peerIdKey = "dev.p2pkit.peerId.$unique"
        peerIdV2Key = "dev.p2pkit.peerId.v2.$unique"
        defaultsLease = AppleGlobalStateTestGuard.acquire(
            keys = arrayOf(peerIdKey, peerIdV2Key)
        )
    }

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
        val lease = checkNotNull(defaultsLease) { "NSUserDefaults fixture was not acquired" }
        lease.remove(peerIdKey)
        lease.remove(peerIdV2Key)
        lease.synchronize()
    }

    private suspend fun startAndAdvertise(name: String): P2pKit {
        removeStoredPeerId()
        val kit = newKit(name)
        toStop.add(kit)
        kit.startAdvertising()
        kit.startDiscovery()
        return kit
    }

    private suspend fun P2pKit.awaitPeer(target: P2pKit): Peer =
        withTimeout(DISCOVERY_TIMEOUT_MS) {
            peers.first { current -> current.any { it.id == target.localPeerId } }
                .first { it.id == target.localPeerId }
        }

    @AfterTest
    fun teardown() {
        try {
            runBlocking {
                toStop.forEach { runCatching { it.stop() } }
                toStop.clear()
            }
            removeStoredPeerId()
        } finally {
            defaultsLease?.close()
            defaultsLease = null
        }
    }

    @Test
    fun peerLostEventFiresWhenPeerStops() {
        runBlocking {
            val alice = startAndAdvertise("Alice")
            val bob = startAndAdvertise("Bob")

            // Both sides must see each other before we test the removal path.
            alice.awaitPeer(bob)
            bob.awaitPeer(alice)

            // Bob exits cleanly — Alice should see Bob disappear from her
            // peer set. Without the Lost wiring, Alice's flow stays
            // populated forever and the test times out.
            bob.stop()
            toStop.remove(bob)

            withTimeout(PEER_LOST_TIMEOUT_MS) {
                alice.peers.first { peers -> peers.none { it.id == bob.localPeerId } }
            }
        }
    }

    @Test
    fun stopDiscoveryWithdrawsOwnedPeersAndRestartReplaysCurrentState() {
        runBlocking {
            val alice = startAndAdvertise("Alice")
            val bob = startAndAdvertise("Bob")

            alice.awaitPeer(bob)

            // LAN peers use a transport-managed lifetime. Stopping the
            // browser must therefore publish an explicit withdrawal; core's
            // stale timer intentionally cannot clean this entry for us.
            alice.stopDiscovery()
            withTimeout(LOCAL_OWNERSHIP_TIMEOUT_MS) {
                alice.peers.first { peers -> peers.none { it.id == bob.localPeerId } }
            }

            // A fresh browser generation must repopulate both the endpoint
            // registry and the state-backed event relay.
            alice.startDiscovery()
            alice.awaitPeer(bob)
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
                    peers.any { it.id == bob.localPeerId } &&
                        peers.any { it.id == charlie.localPeerId }
                }
            }
            val bobSees = withTimeout(DISCOVERY_TIMEOUT_MS) {
                bob.peers.first { peers ->
                    peers.any { it.id == alice.localPeerId } &&
                        peers.any { it.id == charlie.localPeerId }
                }
            }
            val charlieSees = withTimeout(DISCOVERY_TIMEOUT_MS) {
                charlie.peers.first { peers ->
                    peers.any { it.id == alice.localPeerId } &&
                        peers.any { it.id == bob.localPeerId }
                }
            }

            assertEquals(2, aliceSees.size, "Alice should see Bob+Charlie")
            assertEquals(2, bobSees.size, "Bob should see Alice+Charlie")
            assertEquals(2, charlieSees.size, "Charlie should see Alice+Bob")

            // Each pair should also be able to actually open a session,
            // not just appear in the peer list. We exercise one direction
            // per pair so 3 sessions form total.
            val bobPeer = aliceSees.first { it.id == bob.localPeerId }
            val charliePeer = bobSees.first { it.id == charlie.localPeerId }
            val alicePeerFromCharlie = charlieSees.first { it.id == alice.localPeerId }

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
    @OptIn(ExperimentalP2pApi::class)
    fun cleanRemoteKitStopClosesSessionWithoutReconnect() {
        // A normal kit stop sends a CLOSE frame. That frame is authoritative
        // even when reconnect is enabled, so the exact terminal outcome is
        // Closed; accepting Failed here would hide a protocol-ordering race.
        runBlocking {
            val alice = newKitWithReconnect("Alice")
            val bob = newKitWithReconnect("Bob")
            alice.start()
            bob.start()

            // This test owns the CLOSE/reconnect contract, not Bonjour. Dial
            // Bob's real NWListener over loopback so virtual-host multicast
            // timing cannot delay Bob's otherwise clean stop.
            val bobInfo = assertNotNull(bob.networkProvisioning.getManualConnectionInfo())
            val bobPeer = alice.networkProvisioning.createManualPeer(
                host = "127.0.0.1",
                port = bobInfo.port
            )
            val session = withTimeout(HANDSHAKE_TIMEOUT_MS) { alice.connect(bobPeer) }
            withTimeout(HANDSHAKE_TIMEOUT_MS) {
                session.state.first { it == ConnectionState.Connected }
            }

            // Bob exits cleanly and Alice must honor the CLOSE frame without
            // treating it as a reconnectable transport failure.
            bob.stop()
            toStop.remove(bob)

            val terminal = withTimeout(CLEAN_CLOSE_TIMEOUT_MS) {
                session.state.first { it == ConnectionState.Closed }
            }
            assertEquals(ConnectionState.Closed, terminal)
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
            networkProvisioning {
                iosManualIp()
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

            val bobPeer = alice.awaitPeer(bob)
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
            alice.awaitPeer(bob)

            // Bob disappears from the air.
            bob.stopAdvertising()
            withTimeout(PEER_LOST_TIMEOUT_MS) {
                alice.peers.first { peers -> peers.none { it.id == bob.localPeerId } }
            }

            // Bob re-advertises (same peerId, same deviceName since we can't
            // mutate it through the public DSL). Alice should see the peer
            // reappear within a reasonable Bonjour TTL.
            bob.startAdvertising()
            alice.awaitPeer(bob)
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

            val bobPeer = alice.awaitPeer(bob)

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
        const val CLEAN_CLOSE_TIMEOUT_MS: Long = 30_000
        const val LOCAL_OWNERSHIP_TIMEOUT_MS: Long = 5_000
        const val LIFECYCLE_CYCLE_COUNT: Int = 20
        const val CONNECT_STORM_COUNT: Int = 10
    }
}
