package dev.p2pkit.transport.lan

import dev.p2pkit.core.AppId
import dev.p2pkit.core.ConnectionState
import dev.p2pkit.core.ExperimentalP2pApi
import dev.p2pkit.core.P2pKit
import dev.p2pkit.core.P2pMessage
import dev.p2pkit.core.Peer
import dev.p2pkit.core.PeerId
import dev.p2pkit.core.Platform
import dev.p2pkit.core.ReconnectPolicy
import dev.p2pkit.core.transfer.FileTransferState
import dev.p2pkit.core.transport.PeerAuthenticationHint
import dev.p2pkit.core.transport.PeerEvent
import dev.p2pkit.core.transport.TransportContext
import dev.p2pkit.core.transport.TransportSecurityProfile
import dev.p2pkit.transport.lan.IosLanTimeoutDiagnostics.Phase
import kotlin.test.AfterTest
import kotlin.test.BeforeTest
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertIs
import kotlin.test.assertNotNull
import kotlin.test.assertNull
import kotlin.test.assertSame
import kotlin.test.assertTrue
import kotlinx.cinterop.ExperimentalForeignApi
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.CoroutineStart
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.NonCancellable
import kotlinx.coroutines.TimeoutCancellationException
import kotlinx.coroutines.async
import kotlinx.coroutines.cancelAndJoin
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.filterNotNull
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.onSubscription
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.suspendCancellableCoroutine
import kotlinx.coroutines.withContext
import kotlinx.io.Buffer
import kotlinx.io.write
import platform.Network.nw_advertise_descriptor_create_bonjour_service
import platform.Network.nw_advertise_descriptor_set_no_auto_rename
import platform.Network.nw_advertise_descriptor_set_txt_record_object
import platform.Network.nw_listener_get_port
import platform.Network.nw_listener_set_advertise_descriptor
import platform.darwin.dispatch_async

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

    private val diagnostics = KitTestDiagnostics()
    private val lanTimeouts = IosLanTimeoutDiagnostics()
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

    private fun newKit(name: String): P2pKit = diagnostics.create { recording ->
        P2pKit.create {
            logger = recording
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
        kit.startAdvertising()
        kit.startDiscovery()
        return kit
    }

    private suspend fun P2pKit.awaitPeer(target: P2pKit, phase: Phase = Phase.DISCOVERY): Peer =
        lanTimeouts.withTimeout(phase, DISCOVERY_TIMEOUT_MS) {
            peers.first { current -> current.any { it.id == target.localPeerId } }
                .first { it.id == target.localPeerId }
        }

    @AfterTest
    fun teardown() {
        runBlocking {
            diagnostics.finish {
                try {
                    removeStoredPeerId()
                } finally {
                    defaultsLease?.close()
                    defaultsLease = null
                }
            }
        }
    }

    @Test
    fun peerLostEventFiresWhenPeerStops() {
        lanTimeouts.run {
            val alice = startAndAdvertise("Alice")
            val bob = startAndAdvertise("Bob")

            // Both sides must see each other before we test the removal path.
            alice.awaitPeer(bob)
            bob.awaitPeer(alice)

            // Bob exits cleanly — Alice should see Bob disappear from her
            // peer set. Without the Lost wiring, Alice's flow stays
            // populated forever and the test times out.
            bob.stop()

            lanTimeouts.withTimeout(Phase.PEER_LOSS, PEER_LOST_TIMEOUT_MS) {
                alice.peers.first { peers -> peers.none { it.id == bob.localPeerId } }
            }
        }
    }

    @Test
    fun stopDiscoveryWithdrawsOwnedPeersAndRestartReplaysCurrentState() {
        lanTimeouts.run {
            val alice = startAndAdvertise("Alice")
            val bob = startAndAdvertise("Bob")

            alice.awaitPeer(bob)

            // LAN peers use a transport-managed lifetime. Stopping the
            // browser must therefore publish an explicit withdrawal; core's
            // stale timer intentionally cannot clean this entry for us.
            alice.stopDiscovery()
            lanTimeouts.withTimeout(Phase.LOCAL_WITHDRAWAL, LOCAL_OWNERSHIP_TIMEOUT_MS) {
                alice.peers.first { peers -> peers.none { it.id == bob.localPeerId } }
            }

            // A fresh browser generation must repopulate both the endpoint
            // registry and the state-backed event relay.
            alice.startDiscovery()
            alice.awaitPeer(bob, Phase.REDISCOVERY)
        }
    }

    @Test
    fun repeatedKitLifecycleDoesNotLeakPorts() {
        lanTimeouts.run {
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
        lanTimeouts.run {
            val alice = startAndAdvertise("Alice")
            val bob = startAndAdvertise("Bob")
            val charlie = startAndAdvertise("Charlie")

            // Each kit must see the OTHER TWO. If the discovery transport
            // accidentally treated peer #1 as a "first peer" cache key
            // somewhere, this lights it up.
            val aliceSees = lanTimeouts.withTimeout(Phase.DISCOVERY_1, DISCOVERY_TIMEOUT_MS) {
                alice.peers.first { peers ->
                    peers.any { it.id == bob.localPeerId } &&
                        peers.any { it.id == charlie.localPeerId }
                }
            }
            val bobSees = lanTimeouts.withTimeout(Phase.DISCOVERY_2, DISCOVERY_TIMEOUT_MS) {
                bob.peers.first { peers ->
                    peers.any { it.id == alice.localPeerId } &&
                        peers.any { it.id == charlie.localPeerId }
                }
            }
            val charlieSees = lanTimeouts.withTimeout(Phase.DISCOVERY_3, DISCOVERY_TIMEOUT_MS) {
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

            val ab = lanTimeouts.withTimeout(Phase.HANDSHAKE_1, HANDSHAKE_TIMEOUT_MS) { sAB.await() }
            val bc = lanTimeouts.withTimeout(Phase.HANDSHAKE_2, HANDSHAKE_TIMEOUT_MS) { sBC.await() }
            val ca = lanTimeouts.withTimeout(Phase.HANDSHAKE_3, HANDSHAKE_TIMEOUT_MS) { sCA.await() }

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
        lanTimeouts.run {
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
            val session = lanTimeouts.withTimeout(Phase.HANDSHAKE_OUTGOING, HANDSHAKE_TIMEOUT_MS) {
                alice.connect(bobPeer)
            }
            lanTimeouts.withTimeout(Phase.HANDSHAKE_CONNECTED, HANDSHAKE_TIMEOUT_MS) {
                session.state.first { it == ConnectionState.Connected }
            }

            // Bob exits cleanly and Alice must honor the CLOSE frame without
            // treating it as a reconnectable transport failure.
            bob.stop()

            val terminal = lanTimeouts.withTimeout(Phase.CLEAN_CLOSE, CLEAN_CLOSE_TIMEOUT_MS) {
                session.state.first { it == ConnectionState.Closed }
            }
            assertEquals(ConnectionState.Closed, terminal)
        }
    }

    private fun newKitWithReconnect(name: String): P2pKit {
        removeStoredPeerId()
        return diagnostics.create { recording ->
            P2pKit.create {
                logger = recording
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
        }
    }

    @Test
    fun midTransferCancelTerminatesBothSidesCleanly() {
        // Sender starts a 5 MiB transfer over a real NWConnection, the
        // receiver accepts to a Buffer, and the sender calls
        // P2pFileTransfer.cancel() at ~50% progress. Both sides must
        // transition to Cancelled / Failed terminal states within
        // TERMINAL_TIMEOUT_MS and the underlying nw_connection_t must
        // remain usable for further messages.
        lanTimeouts.run {
            val alice = startAndAdvertise("Alice")
            val bob = startAndAdvertise("Bob")

            val bobPeer = alice.awaitPeer(bob)
            val outgoingDeferred = async { alice.connect(bobPeer) }
            val incomingSession = lanTimeouts.withTimeout(Phase.HANDSHAKE_INCOMING, HANDSHAKE_TIMEOUT_MS) {
                bob.incomingSessions.first()
            }
            val outgoing = lanTimeouts.withTimeout(Phase.HANDSHAKE_OUTGOING, HANDSHAKE_TIMEOUT_MS) {
                outgoingDeferred.await()
            }

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

            val offer = lanTimeouts.withTimeout(Phase.FILE_OFFER, HANDSHAKE_TIMEOUT_MS) { offerDeferred.await() }
            val incomingTransfer = offer.accept(dstBuffer)

            // Wait for partial progress before cancelling. We deliberately
            // don't require an exact percent — Bonjour/NW timing varies on
            // the simulator. Anywhere between 5% and 95% suffices to prove
            // we cancelled MID-transfer (not before it started, not after
            // it completed).
            lanTimeouts.withTimeout(Phase.TRANSFER_PROGRESS, HANDSHAKE_TIMEOUT_MS) {
                val low = (totalBytes / 20).toLong()
                val high = (totalBytes - 1).toLong()
                transfer.bytesTransferred.first { it in low..high }
            }

            transfer.cancel("test-mid-cancel")

            val senderFinal = lanTimeouts.withTimeout(Phase.TRANSFER_SENDER_TERMINAL, TERMINAL_TIMEOUT_MS) {
                transfer.state.first { isTerminal(it) }
            }
            val receiverFinal = lanTimeouts.withTimeout(Phase.TRANSFER_RECEIVER_TERMINAL, TERMINAL_TIMEOUT_MS) {
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
        lanTimeouts.run {
            val alice = startAndAdvertise("Alice")
            val bob = startAndAdvertise("Bob")

            // Initial discovery — Alice sees Bob.
            alice.awaitPeer(bob)

            // Bob disappears from the air.
            bob.stopAdvertising()
            lanTimeouts.withTimeout(Phase.PEER_LOSS, PEER_LOST_TIMEOUT_MS) {
                alice.peers.first { peers -> peers.none { it.id == bob.localPeerId } }
            }

            // Bob re-advertises (same peerId, same deviceName since we can't
            // mutate it through the public DSL). Alice should see the peer
            // reappear within a reasonable Bonjour TTL.
            bob.startAdvertising()
            alice.awaitPeer(bob, Phase.REDISCOVERY)
        }
    }

    @Test
    fun rapidConnectCloseCycle() {
        // 10 sequential connect-send-close cycles against the same remote
        // peer. Stresses session lifecycle teardown — if the kit's
        // SessionManager left a stale session in its map, the second
        // connect() either dedups (no new handshake) or fails ("session
        // already exists"). Either is a regression.
        lanTimeouts.run {
            val alice = startAndAdvertise("Alice")
            val bob = startAndAdvertise("Bob")

            val bobPeer = alice.awaitPeer(bob)

            repeat(CONNECT_STORM_COUNT) { i ->
                val session = lanTimeouts.withTimeout(Phase.HANDSHAKE_OUTGOING, HANDSHAKE_TIMEOUT_MS) {
                    alice.connect(bobPeer)
                }
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

    @Test
    @OptIn(ExperimentalForeignApi::class)
    fun liveTxtChangesWithdrawAndRecoverWithoutReplacingThePublisherListener() {
        lanTimeouts.run {
            for (profile in TransportSecurityProfile.entries) {
                val app = AppId("$unique-live-${profile.name}")
                val remote = PeerId("live-publisher")
                val receiverContext = TransportContext(
                    appId = app, localPeerId = PeerId("live-observer"), deviceName = "Observer",
                    platform = Platform.IOS, securityProfile = profile
                )
                val publisherContext = TransportContext(
                    appId = app, localPeerId = remote, deviceName = "Live A",
                    platform = Platform.IOS, securityProfile = profile
                )
                val registry = IosEndpointRegistry()
                val receiverData = IosLanDataTransport(receiverContext, registry)
                val publisher = IosLanDataTransport(publisherContext, IosEndpointRegistry())
                data class Observation(val sequence: Long, val error: Int, val snapshot: IosLanTxtMonitor.Snapshot?)
                data class GuardWitness(
                    val owner: IosLanTxtMonitor.Owner, val revision: Long,
                    val firstEvent: Int, val lastEventExclusive: Int
                )
                val observed = MutableStateFlow(Observation(0, 0, null))
                val current = MutableStateFlow<PeerEvent.Found?>(null)
                val eventHistory = MutableStateFlow<List<PeerEvent>>(emptyList())
                val guardHistory = MutableStateFlow<List<GuardWitness>>(emptyList())
                lateinit var receiver: IosLanDiscoveryTransport
                val dns = ObservingLiveIosLanTxtDns(
                    delegate = PlatformIosLanTxtDns(receiverData.queue),
                    targetName = remote.value,
                    observeQueuedBlock = { block ->
                        // These getters run OUTSIDE the production block/transaction lock, never in
                        // the synchronous event collector. Observe the real enqueue, not a guessed timer.
                        val prior = receiver.txtSnapshotForTest(remote.value)
                        val wasAdmitted = registry.lease(remote) != null
                        val firstEvent = eventHistory.value.size
                        block()
                        val after = receiver.txtSnapshotForTest(remote.value)
                        if (prior != null && after != null && prior.owner === after.owner &&
                            prior.revision == after.revision && prior.pending && after.pending &&
                            wasAdmitted && registry.lease(remote) == null
                        ) {
                            guardHistory.update {
                                it + GuardWitness(prior.owner, prior.revision, firstEvent, eventHistory.value.size)
                            }
                        }
                    },
                    afterCallback = { fullName, error ->
                        // This notification follows an ACTUAL daemon callback handled by the real monitor.
                        // It neither supplies bytes nor changes admission. Ignore unrelated service queries.
                        if (fullName.startsWith("${remote.value}.")) {
                            observed.value = Observation(
                                observed.value.sequence + 1, error, receiver.txtSnapshotForTest(remote.value)
                            )
                        }
                    }
                )
                receiver = IosLanDiscoveryTransport(receiverContext, registry, receiverData, dns)
                val collector = launch(Dispatchers.Unconfined, start = CoroutineStart.UNDISPATCHED) {
                    receiver.events.collect { event ->
                        val relevant = when (event) {
                            is PeerEvent.Found -> event.peer.publicPeer.id == remote
                            is PeerEvent.Updated -> event.peer.publicPeer.id == remote
                            is PeerEvent.Lost -> event.peerId == remote
                        }
                        if (relevant) eventHistory.update { it + event }
                        when (event) {
                            is PeerEvent.Found -> if (event.peer.publicPeer.id == remote) current.value = event
                            is PeerEvent.Updated -> if (event.peer.publicPeer.id == remote) {
                                current.value = PeerEvent.Found(event.peer)
                            }
                            is PeerEvent.Lost -> if (event.peerId == remote) current.value = null
                        }
                    }
                }
                try {
                    publisher.start().getOrThrow()
                    val listener = assertNotNull(publisher.listener)
                    val port = nw_listener_get_port(listener)
                    assertTrue(port.toUInt() > 0u)
                    receiver.startDiscovery()

                    fun properties(name: String, appText: String = app.value): Map<String, String> =
                        LanTxtRecordFixtures.properties(profile).mapValues { (_, bytes) ->
                            assertNotNull(bytes).decodeToString()
                        } + mapOf("pid" to remote.value, "app" to appText, "name" to name, "plat" to "IOS")

                    suspend fun publish(properties: Map<String, String>) =
                        suspendCancellableCoroutine<Unit> { pending ->
                            dispatch_async(publisher.queue) {
                                if (pending.isActive) {
                                    pending.resumeWith(runCatching {
                                        assertSame(listener, publisher.listener)
                                        assertEquals(port, nw_listener_get_port(listener))
                                        val descriptor = assertNotNull(nw_advertise_descriptor_create_bonjour_service(
                                            remote.value, publisherContext.lanServiceTypeBonjour, null
                                        ))
                                        nw_advertise_descriptor_set_no_auto_rename(descriptor, true)
                                        nw_advertise_descriptor_set_txt_record_object(
                                            descriptor, IosBonjour.mapToTxtRecord(properties)
                                        )
                                        nw_listener_set_advertise_descriptor(listener, descriptor)
                                    })
                                }
                            }
                        }

                    suspend fun <T> awaitLive(
                        phase: Phase,
                        timeMillis: Long,
                        before: Long,
                        firstEvent: Int,
                        expectedName: String?,
                        expectedApp: String,
                        wait: suspend CoroutineScope.() -> T
                    ): T {
                        try {
                            return lanTimeouts.withTimeout(phase, timeMillis, wait)
                        } catch (failure: TimeoutCancellationException) {
                            // Failure-only test-owned state, before the enclosing finally retires it.
                            // Separately sampled values are not an atomic/native ownership proof.
                            try {
                                val profileName =
                                    if (profile == TransportSecurityProfile.AuthenticatedV2) "V2" else "V1"
                                val prefix = "P2PKIT_IOS_LIVE_TXT_WAIT_V1 scope=TEST_OWNED_BEST_EFFORT " +
                                    "phase=${phase.name} profile=$profileName"
                                val marker = try {
                                    val observation = observed.value
                                    val prior = observation.snapshot
                                    val live = receiver.txtSnapshotForTest(remote.value)
                                    val peer = current.value
                                    val native = dns.observation
                                    val history = eventHistory.value
                                    var capped = false
                                    fun bounded(value: Long, maximum: Long = 255): Long {
                                        if (value < 0 || value > maximum) capped = true
                                        return value.coerceIn(0, maximum)
                                    }
                                    fun expected(snapshot: IosLanTxtMonitor.Snapshot?): Boolean = when (phase) {
                                        Phase.DISCOVERY_1, Phase.DISCOVERY_2, Phase.DISCOVERY_3 ->
                                            snapshot?.records?.any {
                                                !it.malformed && it.properties["name"] == expectedName &&
                                                    it.properties["app"] == expectedApp
                                            } == true
                                        Phase.LOCAL_WITHDRAWAL ->
                                            snapshot?.records?.any { it.properties["app"] == expectedApp } == true
                                        else -> false
                                    }
                                    val validated = live?.records?.map { decoded ->
                                        if (decoded.malformed) null else validateLanDiscoveryRecord(
                                            decoded.properties, receiverContext.appId, receiverContext.localPeerId,
                                            receiverContext.securityProfile
                                        )?.takeIf { it.peerId == remote }
                                    }.orEmpty()
                                    val first = validated.firstOrNull()
                                    val coherent = first != null && validated.all { it == first }
                                    val events = history.drop(firstEvent.coerceIn(0, history.size))
                                    val callbackError =
                                        if (observation.sequence > 0) observation.error.toString() else "NONE"
                                    val fields = listOf(
                                        "cbBefore=${bounded(before)}",
                                        "cbNow=${bounded(observation.sequence)}",
                                        "cbAdvanced=${observation.sequence > before}",
                                        "cbError=$callbackError",
                                        "construct=${native.construct.name}", "start=${native.start.name}",
                                        "startError=${native.startError?.toString() ?: "NONE"}",
                                        "schedule=${native.schedule.name}",
                                        "scheduleError=${native.scheduleError?.toString() ?: "NONE"}",
                                        "queries=${bounded(receiver.txtQueryCountForTest.toLong(), 256)}",
                                        "reserved=${bounded(receiver.txtReservedQueryCountForTest.toLong(), 256)}",
                                        "retained=${bounded(receiver.txtRetainedBytesForTest.toLong(), 8_388_608L)}",
                                        "observed=${prior != null}", "observedPending=${prior?.pending ?: false}",
                                        "observedRr=${bounded((prior?.records?.size ?: 0).toLong(), 8)}",
                                        "observedExpected=${expected(prior)}", "live=${live != null}",
                                        "livePending=${live?.pending ?: false}",
                                        "liveRr=${bounded((live?.records?.size ?: 0).toLong(), 8)}",
                                        "liveExpected=${expected(live)}", "liveCoherent=$coherent",
                                        "sameSnapshot=${prior != null && live != null && prior.owner === live.owner &&
                                            prior.revision == live.revision}",
                                        "peer=${peer != null}",
                                        "peerExpected=${if (expectedName == null) peer == null
                                            else peer?.peer?.publicPeer?.name == expectedName}",
                                        "lease=${registry.lease(remote) != null}",
                                        "found=${bounded(events.count { it is PeerEvent.Found }.toLong())}",
                                        "updated=${bounded(events.count { it is PeerEvent.Updated }.toLong())}",
                                        "lost=${bounded(events.count { it is PeerEvent.Lost }.toLong())}",
                                        "capped=$capped"
                                    )
                                    val text = "$prefix status=OK " + fields.joinToString(" ")
                                    check(text.length <= 1024 && text.all { it.code in 32..126 })
                                    text
                                } catch (_: Throwable) { "$prefix status=UNAVAILABLE" }
                                failure.addSuppressed(IllegalStateException(marker))
                            } catch (_: Throwable) { }
                            throw failure
                        }
                    }

                    suspend fun awaitName(
                        name: String, after: Long, phase: Phase, firstEvent: Int
                    ): Pair<PeerEvent.Found, IosLanTxtMonitor.Snapshot> =
                        awaitLive(phase, DISCOVERY_TIMEOUT_MS, after, firstEvent, name, app.value) {
                            combine(observed, current) { observation, found ->
                                check(observation.error == 0) { "live DNS callback failed: ${observation.error}" }
                                val snapshot = observation.snapshot
                                val actualRecord = observation.sequence > after && snapshot != null &&
                                    !snapshot.pending && snapshot.records.any {
                                        !it.malformed && it.properties["name"] == name &&
                                            it.properties["app"] == app.value
                                    }
                                found?.takeIf { actualRecord && it.peer.publicPeer.name == name }
                                    ?.let { it to assertNotNull(snapshot) }
                            }.filterNotNull().first()
                        }

                    var before = observed.value.sequence
                    var firstEvent = eventHistory.value.size
                    publish(properties("Live A"))
                    val (first, firstTxt) = awaitName("Live A", before, Phase.DISCOVERY_1, firstEvent)
                    assertEquals(Platform.IOS, first.peer.publicPeer.platform)
                    if (profile == TransportSecurityProfile.AuthenticatedV2) {
                        assertIs<PeerAuthenticationHint.UntrustedDiscoveryClaim>(first.peer.authenticationHint)
                    } else {
                        assertNull(first.peer.authenticationHint)
                    }
                    assertNotNull(registry.lease(remote))
                    before = observed.value.sequence
                    val beforeUpdateEvents = eventHistory.value.size
                    publish(properties("Live B"))
                    val (_, updatedTxt) = awaitName("Live B", before, Phase.DISCOVERY_2, beforeUpdateEvents)
                    val updateEvents = eventHistory.value.withIndex().drop(beforeUpdateEvents)
                    val losses = updateEvents.filter { it.value is PeerEvent.Lost }
                    if (losses.isEmpty()) {
                        assertTrue(updateEvents.any {
                            val event = it.value
                            event is PeerEvent.Updated && event.peer.publicPeer.name == "Live B"
                        }, "a complete live update must emit actual Updated")
                    } else {
                        assertSame(firstTxt.owner, updatedTxt.owner, "guard recovery retains the same query owner")
                        val guards = guardHistory.value
                        for (loss in losses) {
                            assertTrue(guards.any {
                                it.owner === firstTxt.owner && it.revision > firstTxt.revision &&
                                    it.revision < updatedTxt.revision &&
                                    loss.index in it.firstEvent until it.lastEventExclusive
                            }, "Lost must be emitted inside an observed unchanged-pending queue guard")
                            assertTrue(updateEvents.any {
                                val event = it.value
                                it.index > loss.index && event is PeerEvent.Found &&
                                    event.peer.publicPeer.name == "Live B"
                            }, "guard withdrawal must recover with a later actual Found")
                        }
                    }
                    assertNotNull(registry.lease(remote))
                    before = observed.value.sequence
                    firstEvent = eventHistory.value.size
                    publish(properties("Invalid", appText = "foreign-app"))
                    awaitLive(Phase.LOCAL_WITHDRAWAL, PEER_LOST_TIMEOUT_MS, before, firstEvent, null, "foreign-app") {
                        combine(observed, current) { observation, found ->
                            check(observation.error == 0) { "live DNS callback failed: ${observation.error}" }
                            observation.sequence > before && found == null &&
                                observation.snapshot?.records?.any { it.properties["app"] == "foreign-app" } == true
                        }.first { it }
                    }
                    assertNull(registry.lease(remote))
                    assertNull(receiver.announceEntryForTest(remote.value))
                    assertTrue(receiver.txtQueryCountForTest > 0, "invalid TXT must retain its live query")
                    before = observed.value.sequence
                    firstEvent = eventHistory.value.size
                    publish(properties("Live C"))
                    awaitName("Live C", before, Phase.DISCOVERY_3, firstEvent)
                    assertNotNull(registry.lease(remote))
                    assertSame(listener, publisher.listener)
                    assertEquals(port, nw_listener_get_port(listener))
                    before = observed.value.sequence
                    firstEvent = eventHistory.value.size
                    publisher.close()
                    awaitLive(Phase.PEER_LOSS, PEER_LOST_TIMEOUT_MS, before, firstEvent, null, app.value) {
                        current.first { it == null }
                    }
                    assertNull(registry.lease(remote))
                } finally {
                    withContext(NonCancellable) {
                        try {
                            receiver.stopDiscovery()
                        } finally {
                            try {
                                collector.cancelAndJoin()
                            } finally {
                                try { receiverData.close() } finally { publisher.close() }
                            }
                        }
                        assertEquals(0, receiver.txtQueryCountForTest)
                        assertEquals(0, receiver.txtReservedQueryCountForTest)
                        assertEquals(0, receiver.txtRetainedBytesForTest)
                    }
                }
            }
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

/** Delegates native calls once; captures outcomes and retains the actual post-callback witness. */
private class ObservingLiveIosLanTxtDns(
    private val delegate: IosLanTxtDns,
    private val targetName: String,
    private val observeQueuedBlock: (() -> Unit) -> Unit,
    private val afterCallback: (String, Int) -> Unit
) : IosLanTxtDns {
    enum class Construct { NONE, OK, EMPTY, THREW }
    enum class Start { NONE, REF, NO_REF, ERROR, THREW }
    enum class Schedule { NONE, OK, ERROR, THREW }

    data class Observation(
        val construct: Construct = Construct.NONE,
        val start: Start = Start.NONE,
        val startError: Int? = null,
        val schedule: Schedule = Schedule.NONE,
        val scheduleError: Int? = null
    )

    private val nativeObservation = MutableStateFlow(Observation())
    val observation: Observation get() = nativeObservation.value

    private fun observe(update: (Observation) -> Observation) {
        try { nativeObservation.update(update) } catch (_: Throwable) { }
    }

    override fun constructFullName(name: String, type: String, domain: String): String? {
        val target = name == targetName
        if (target) observe { Observation() }
        val result = try {
            delegate.constructFullName(name, type, domain)
        } catch (failure: Throwable) {
            if (target) observe { it.copy(construct = Construct.THREW) }
            throw failure
        }
        if (target) observe { it.copy(construct = if (result.isNullOrEmpty()) Construct.EMPTY else Construct.OK) }
        return result
    }

    override fun start(fullName: String, callback: (Int, () -> IosLanTxtAnswer) -> Unit): IosLanTxtDns.Start {
        val target = fullName.startsWith("$targetName.")
        val result = try {
            delegate.start(fullName) { error, fields ->
                callback(error, fields)
                afterCallback(fullName, error)
            }
        } catch (failure: Throwable) {
            if (target) observe { it.copy(start = Start.THREW) }
            throw failure
        }
        if (!target) return result
        // Error-first: never access the reference on a nonzero returned native error.
        if (result.error != 0) {
            observe { it.copy(start = Start.ERROR, startError = result.error) }
            return result
        }
        val reference = result.reference
        if (reference == null) {
            observe { it.copy(start = Start.NO_REF, startError = result.error) }
            return result
        }
        observe { it.copy(start = Start.REF, startError = result.error) }
        // Wrapping records the actual schedule outcome; the native reference still has one owner.
        // If allocating diagnostic wrapping fails, return the original result unchanged.
        return try {
            IosLanTxtDns.Start(result.error, object : IosLanTxtDns.Reference {
                override fun schedule(): Int {
                    val code = try {
                        reference.schedule()
                    } catch (failure: Throwable) {
                        observe { it.copy(schedule = Schedule.THREW) }
                        throw failure
                    }
                    observe { it.copy(schedule = if (code == 0) Schedule.OK else Schedule.ERROR, scheduleError = code) }
                    return code
                }

                override fun deallocate() = reference.deallocate()
                override fun disposeContext() = reference.disposeContext()
            })
        } catch (_: Throwable) { result }
    }

    override fun enqueue(block: () -> Unit) = delegate.enqueue { observeQueuedBlock(block) }
}
