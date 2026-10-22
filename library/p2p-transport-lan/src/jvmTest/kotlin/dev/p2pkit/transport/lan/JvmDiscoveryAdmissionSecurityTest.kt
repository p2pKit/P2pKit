package dev.p2pkit.transport.lan

import dev.p2pkit.core.AppId
import dev.p2pkit.core.ConnectionState
import dev.p2pkit.core.ExperimentalP2pApi
import dev.p2pkit.core.P2pError
import dev.p2pkit.core.P2pKit
import dev.p2pkit.core.P2pLogger
import dev.p2pkit.core.P2pMessage
import dev.p2pkit.core.PeerAuthorizationPolicy
import dev.p2pkit.core.PeerFingerprint
import dev.p2pkit.core.PeerId
import dev.p2pkit.core.Platform
import dev.p2pkit.core.SecurityMode
import dev.p2pkit.core.TransportKind
import dev.p2pkit.core.dsl.jvmSecureIdentityStore
import dev.p2pkit.core.provisioning.NetworkProvisioningFactory
import dev.p2pkit.core.provisioning.NetworkProvisioningManager
import dev.p2pkit.core.provisioning.ProvisioningContext
import dev.p2pkit.core.provisioning.UnsupportedNetworkProvisioningManager
import dev.p2pkit.core.transport.InternalPeer
import dev.p2pkit.core.transport.PeerAuthenticationHint
import dev.p2pkit.core.transport.PeerEvent
import dev.p2pkit.core.transport.TransportSecurityProfile
import dev.p2pkit.transport.lan.internal.jmdns.ServiceInfo
import java.security.MessageDigest
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.CoroutineStart
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.async
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.launch
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.test.runCurrent
import kotlinx.coroutines.test.runTest
import kotlinx.coroutines.withTimeout
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertFalse
import kotlin.test.assertIs
import kotlin.test.assertNotNull
import kotlin.test.assertNull
import kotlin.test.assertTrue

/**
 * #120: occupancy bounds are not fair admission. The first test characterizes
 * the still-open limitation, not a desired security guarantee. The others
 * protect the existing authentication/manual-route escape hatch without
 * mistaking it for automatic discovery fairness.
 *
 * Discovery uses the existing test-only callback backend, production v2 TXT
 * validation, admissions and relay. The kit tests use real TCP and Noise on
 * loopback, not multicast, physical devices or a hostile-network campaign.
 */
@OptIn(ExperimentalCoroutinesApi::class, ExperimentalP2pApi::class)
class JvmDiscoveryAdmissionSecurityTest {
    @Test
    fun v2ClaimsCanStillOccupyEveryDiscoverySlotUntilOneIsWithdrawn() = runTest {
        // This is a callback/admission test, not a host-interface scan. Keep
        // every resolution deterministic; the TCP/Noise cases below retain
        // the backend's ordinary host snapshot provider.
        var localSnapshotReads = 0
        val backend = JvmDeterministicDiscoveryTestBackend {
            localSnapshotReads += 1
            emptyList()
        }
        val local = syntheticClaim(MAX_TRACKED_LAN_PEERS + 1)
        val registration = LanServiceRegistration(
            appId = appId,
            localPeerId = local.peerId,
            deviceName = "Observer",
            platform = Platform.JVM_DESKTOP,
            securityProfile = TransportSecurityProfile.AuthenticatedV2,
            fingerprint = local.fingerprint
        )
        val discovery = JvmLanDiscoveryTransport(registration, backend)
        val visible = mutableMapOf<PeerId, InternalPeer>()
        backgroundScope.launch {
            discovery.events.collect { event ->
                when (event) {
                    is PeerEvent.Found -> visible[event.peer.publicPeer.id] = event.peer
                    is PeerEvent.Updated -> visible[event.peer.publicPeer.id] = event.peer
                    is PeerEvent.Lost -> visible.remove(event.peerId)
                }
            }
        }
        val occupants = List(MAX_TRACKED_LAN_PEERS, ::syntheticClaim)
        val later = syntheticClaim(MAX_TRACKED_LAN_PEERS)
        try {
            discovery.startDiscovery()
            occupants.forEach { backend.advertise(advertisement(it)) }
            runCurrent()
            assertEquals(occupants.map { it.peerId }.toSet(), visible.keys)
            var expectedSnapshotReads = MAX_TRACKED_LAN_PEERS
            assertEquals(expectedSnapshotReads, localSnapshotReads)

            // A refreshed, canonical v2 claim is still refused. These are
            // distinct, internally consistent id/fingerprint pairs; no
            // private key is required to advertise any of them.
            repeat(3) {
                backend.advertise(advertisement(later))
                discovery.refresh()
                runCurrent()
                assertEquals(MAX_TRACKED_LAN_PEERS, visible.size)
                assertFalse(later.peerId in visible, "known #120 residual, not proof of fairness")
                // One repeated claim, then all 257 currently advertised claims.
                expectedSnapshotReads += MAX_TRACKED_LAN_PEERS + 2
                assertEquals(expectedSnapshotReads, localSnapshotReads)
            }

            backend.withdraw(occupants.first().peerId.value)
            backend.advertise(advertisement(later))
            runCurrent()
            assertEquals(MAX_TRACKED_LAN_PEERS, visible.size)
            assertFalse(occupants.first().peerId in visible)
            assertEquals(
                later.fingerprint,
                assertIs<PeerAuthenticationHint.UntrustedDiscoveryClaim>(
                    assertNotNull(visible[later.peerId]).authenticationHint
                ).fingerprint
            )
            assertEquals(expectedSnapshotReads + 1, localSnapshotReads)
        } finally {
            discovery.stopDiscovery()
            runCurrent()
            assertTrue(visible.isEmpty())
        }
    }

    @Test
    fun fullPinAndManualEndpointStillConnectAfterTheLanDiscoveryCacheIsFull() = runBlocking {
        val diagnostics = KitTestDiagnostics()
        val backend = JvmDeterministicDiscoveryTestBackend()
        var failure: Throwable? = null
        try {
            withTimeout(20_000) {
                val observer = newKit("Observer", backend, diagnostics)
                val remote = newKit(
                    "Remote", backend, diagnostics,
                    PeerAuthorizationPolicy.PinnedOnly(setOf(assertNotNull(observer.kit.localFingerprint)))
                )
                observer.kit.startDiscovery()
                remote.kit.start()
                repeat(MAX_TRACKED_LAN_PEERS) { backend.advertise(advertisement(syntheticClaim(it))) }
                observer.kit.peers.first { it.size == MAX_TRACKED_LAN_PEERS }
                val remoteClaim = remote.claim()
                backend.advertise(advertisement(remoteClaim, remote.port()))

                val registrar = observer.provisioning.context.manualPeerRegistrar
                assertFailsWith<P2pError.SecurityConfigurationInvalid> {
                    registrar.registerManualPeer("127.0.0.1", remote.port())
                }
                val manual = registrar.registerManualPeer(
                    "127.0.0.1", remote.port(), expectedFingerprint = remoteClaim.fingerprint
                )
                assertEquals(remote.kit.localPeerId, manual.id)
                assertEquals(manual.id, registrar.registerManualPeer(
                    "127.0.0.1", remote.port(), expectedFingerprint = remoteClaim.fingerprint
                ).id)
                assertEquals(MAX_TRACKED_LAN_PEERS + 1, observer.kit.peers.value.size)

                val incoming = async(start = CoroutineStart.UNDISPATCHED) { remote.kit.incomingSessions.first() }
                val outgoing = observer.kit.connect(manual)
                val accepted = incoming.await()
                assertEquals(remoteClaim.fingerprint, outgoing.peerIdentity.fingerprint)
                assertEquals(observer.kit.localFingerprint, accepted.peerIdentity.fingerprint)
                assertEquals(ConnectionState.Connected, outgoing.state.value)
                assertEquals(ConnectionState.Connected, accepted.state.value)
                val message = async(start = CoroutineStart.UNDISPATCHED) { accepted.incoming.first() }
                outgoing.send(P2pMessage.Text("pinned manual route"))
                assertEquals("pinned manual route", assertIs<P2pMessage.Text>(message.await()).value)
                // The manual pin did not become a discovery claim, and the
                // full upstream discovery set did not magically admit it.
                assertNull(observer.kit.discoveryClaim(remote.kit.localPeerId))
                assertEquals(MAX_TRACKED_LAN_PEERS + 1, observer.kit.peers.value.size)
            }
        } catch (error: Throwable) {
            failure = error
            throw error
        } finally {
            diagnostics.finish(failure)
        }
    }

    @Test
    fun copiedApprovedFingerprintCannotAuthenticateTheAdvertisedEndpoint() = runBlocking {
        val diagnostics = KitTestDiagnostics()
        val backend = JvmDeterministicDiscoveryTestBackend()
        val rejectedIncoming = CompletableDeferred<Throwable?>()
        val attackerDiagnostics = KitTestDiagnostics.Recording(object : P2pLogger by P2pLogger.NoOp {
            override fun warn(message: String, throwable: Throwable?) {
                if (message == "Incoming session setup failed") rejectedIncoming.complete(throwable)
            }
        })
        var failure: Throwable? = null
        try {
            withTimeout(20_000) {
                val observer = newKit("Observer", backend, diagnostics)
                val allowObserver = PeerAuthorizationPolicy.PinnedOnly(
                    setOf(assertNotNull(observer.kit.localFingerprint))
                )
                val remote = newKit("Remote", backend, diagnostics, allowObserver)
                val attacker = newKit(
                    "Attacker", backend, diagnostics, allowObserver, attackerDiagnostics
                ) { recording ->
                    val warning = recording.entries.single()
                    assertEquals(KitTestDiagnostics.Recording.Level.WARN, warning.level)
                    assertEquals("Incoming session setup failed", warning.message)
                    assertIs<P2pError.AuthenticationFailed>(warning.throwable)
                }
                observer.kit.startDiscovery()
                remote.kit.start()
                attacker.kit.start()
                val approved = remote.claim() // Obtained out of band from the owned remote kit.
                backend.advertise(advertisement(approved, attacker.port(), "Copied identity"))
                val spoofed = observer.kit.peers.first { peers -> peers.any { it.id == approved.peerId } }
                    .single { it.id == approved.peerId }
                assertEquals(approved.fingerprint, observer.kit.discoveryClaim(approved.peerId)?.fingerprint)

                assertFailsWith<P2pError.AuthenticatedIdentityMismatch> {
                    observer.kit.connect(spoofed, approved.fingerprint)
                }
                assertIs<P2pError.AuthenticationFailed>(rejectedIncoming.await())
                assertTrue(observer.kit.sessions.value.isEmpty())
                assertTrue(attacker.kit.sessions.value.isEmpty())
                assertTrue(remote.kit.sessions.value.isEmpty())

                // Positive control: the same pin succeeds when the route
                // reaches its actual key owner. A name update is a causal
                // publication barrier for the core's new routing snapshot.
                backend.advertise(advertisement(approved, remote.port(), "Actual endpoint"))
                val real = observer.kit.peers.first { peers -> peers.any { it.name == "Actual endpoint" } }
                    .single { it.id == approved.peerId }
                val incoming = async(start = CoroutineStart.UNDISPATCHED) { remote.kit.incomingSessions.first() }
                val outgoing = observer.kit.connect(real, approved.fingerprint)
                assertEquals(approved.fingerprint, outgoing.peerIdentity.fingerprint)
                assertEquals(observer.kit.localFingerprint, incoming.await().peerIdentity.fingerprint)
                assertEquals(ConnectionState.Connected, outgoing.state.value)
            }
        } catch (error: Throwable) {
            failure = error
            throw error
        } finally {
            diagnostics.finish(failure)
        }
    }

    private class CapturedProvisioning : NetworkProvisioningFactory {
        lateinit var context: ProvisioningContext
        override fun build(context: ProvisioningContext): NetworkProvisioningManager {
            this.context = context
            return UnsupportedNetworkProvisioningManager()
        }
    }

    private data class OwnedKit(val kit: P2pKit, val provisioning: CapturedProvisioning) {
        fun port(): Int = assertNotNull(provisioning.context.lanTcpPort())
        fun claim(): Claim = Claim(kit.localPeerId, assertNotNull(kit.localFingerprint))
    }

    private fun newKit(
        name: String,
        backend: JvmDeterministicDiscoveryTestBackend,
        diagnostics: KitTestDiagnostics,
        authorization: PeerAuthorizationPolicy = PeerAuthorizationPolicy.RejectUnknown,
        recording: KitTestDiagnostics.Recording = KitTestDiagnostics.Recording(),
        verify: (KitTestDiagnostics.Recording) -> Unit = { it.assertQuiet() }
    ): OwnedKit {
        val provisioning = CapturedProvisioning()
        val kit = diagnostics.create(recording, verify) { logger ->
            P2pKit.create {
                this.appId = this@JvmDiscoveryAdmissionSecurityTest.appId
                deviceName = name
                this.logger = logger
                jvmSecureIdentityStore(InMemoryTestJvmSecureIdentityStore())
                security { mode = SecurityMode.AuthenticatedV2(authorization) }
                transports { register(JvmDeterministicLanTestFactory(backend)) }
                networkProvisioning { register(provisioning) }
            }
        }
        return OwnedKit(kit, provisioning)
    }

    private data class Claim(val peerId: PeerId, val fingerprint: PeerFingerprint)

    private val appId = AppId("discovery-admission-security-test")

    /** Canonical, AppId-consistent claims need no corresponding private key. */
    private fun syntheticClaim(index: Int): Claim {
        fun hash(bytes: ByteArray): ByteArray = MessageDigest.getInstance("SHA-256").digest(bytes)
        val fingerprintDigest = hash("untrusted-claim-$index".encodeToByteArray())
        val app = appId.value.encodeToByteArray()
        val peerDigest = hash(
            "dev.p2pkit.peer-id.v2\u0000".encodeToByteArray() +
                byteArrayOf((app.size ushr 8).toByte(), app.size.toByte()) + app + fingerprintDigest
        )
        return Claim(PeerId("p2id2-${base32(peerDigest)}"), PeerFingerprint("p2f1-${base32(fingerprintDigest)}"))
    }

    private fun base32(bytes: ByteArray): String = buildString {
        val alphabet = "abcdefghijklmnopqrstuvwxyz234567"
        var accumulator = 0
        var bits = 0
        for (byte in bytes) {
            accumulator = (accumulator shl 8) or (byte.toInt() and 255)
            bits += 8
            while (bits >= 5) {
                bits -= 5
                append(alphabet[(accumulator ushr bits) and 31])
            }
            accumulator = accumulator and ((1 shl bits) - 1)
        }
        if (bits > 0) append(alphabet[(accumulator shl (5 - bits)) and 31])
    }

    private fun advertisement(claim: Claim, port: Int = 45_001, name: String = "Untrusted claim") =
        JvmTestDiscoveryAdvertisement(
            instanceName = claim.peerId.value,
            info = ServiceInfo.create(
                LanConstants.SECURE_SERVICE_TYPE_JMDNS, claim.peerId.value, port, 0, 0,
                buildLanTxtProperties(
                    claim.peerId, appId, name, Platform.JVM_DESKTOP, setOf(TransportKind.LAN),
                    LanConstants.SECURE_PROTOCOL_VERSION, claim.fingerprint
                )
            )
        )
}
