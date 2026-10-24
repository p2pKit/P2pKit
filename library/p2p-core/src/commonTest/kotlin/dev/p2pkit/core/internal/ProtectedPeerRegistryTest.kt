package dev.p2pkit.core.internal

import dev.p2pkit.core.ConnectionState
import dev.p2pkit.core.ExperimentalP2pApi
import dev.p2pkit.core.P2pMessage
import dev.p2pkit.core.P2pSession
import dev.p2pkit.core.Peer
import dev.p2pkit.core.PeerAdmission
import dev.p2pkit.core.PeerFingerprint
import dev.p2pkit.core.PeerId
import dev.p2pkit.core.PeerIdentity
import dev.p2pkit.core.Platform
import dev.p2pkit.core.ProtectedRouteStatus
import dev.p2pkit.core.SessionConnectionInfo
import dev.p2pkit.core.TransportKind
import dev.p2pkit.core.transfer.P2pFileOffer
import dev.p2pkit.core.transfer.P2pFileTransfer
import dev.p2pkit.core.transport.DataTransport
import dev.p2pkit.core.transport.InternalPeer
import dev.p2pkit.core.transport.OutboundRoute
import dev.p2pkit.core.transport.PeerAuthenticationHint
import dev.p2pkit.core.transport.PeerEvent
import dev.p2pkit.core.transport.PeerOrigin
import dev.p2pkit.core.transport.RawConnection
import dev.p2pkit.core.transport.TransportHint
import dev.p2pkit.core.transport.TransportSecurityProfile
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.flow.emptyFlow
import kotlinx.coroutines.test.advanceTimeBy
import kotlinx.coroutines.test.runCurrent
import kotlinx.coroutines.test.runTest
import kotlinx.io.RawSource
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertIs
import kotlin.test.assertNotNull
import kotlin.test.assertNull
import kotlin.test.assertSame
import kotlin.test.assertTrue

/** Real manager/registry boundary tests; session authorization and exact registration are controlled fakes. */
@OptIn(ExperimentalCoroutinesApi::class, ExperimentalP2pApi::class)
class ProtectedPeerRegistryTest {
    @Test
    fun saturatedDiscoveryBudgetCannotBlockProtectionOrBorrowItsCapacity() = runTest {
        withFixture(backgroundScope) { fixture ->
            val registry = fixture.registry
            val first = discovered(PeerId("ordinary-first"))
            val second = discovered(PeerId("ordinary-second"))
            val overflow = discovered(PeerId("ordinary-overflow"))
            registry.processEvent(PeerEvent.Found(first))
            registry.processEvent(PeerEvent.Found(second))
            registry.processEvent(PeerEvent.Found(overflow))
            assertEquals(setOf(first.publicPeer, second.publicPeer), registry.peers.value.toSet())

            val subject = fixture.subject()
            fixture.install(subject)
            assertEquals(
                setOf(first.publicPeer, second.publicPeer, subject.session.peer),
                registry.peers.value.toSet()
            )
            assertEquals(
                listOf(TransportHint(TransportKind.LAN)),
                assertNotNull(registry.internalPeer(fixture.peerId)).transportHints
            )
            assertNull(registry.reconnectPeer(fixture.peerId))

            // An already-protected ID still needs ordinary capacity to acquire a discovery contribution.
            registry.processEvent(PeerEvent.Found(discovered(fixture.peerId)))
            assertNull(registry.reconnectPeer(fixture.peerId))
            fixture.routes.retire(subject.lease)
            registry.processEvent(PeerEvent.Found(overflow))
            assertEquals(setOf(first.publicPeer, second.publicPeer), registry.peers.value.toSet())

            registry.processEvent(PeerEvent.Lost(first.publicPeer.id))
            registry.processEvent(PeerEvent.Found(overflow))
            assertEquals(setOf(second.publicPeer, overflow.publicPeer), registry.peers.value.toSet())
        }
    }

    @Test
    fun copiedPinAndSameIdDiscoveryCannotEarnProtectionOrReplaceAuthenticatedDisplay() = runTest {
        withFixture(backgroundScope) { fixture ->
            val registry = fixture.registry
            val forged = discovered(
                fixture.peerId,
                name = "Forged display",
                hints = listOf(TransportHint(TransportKind.BLE))
            ).copy(
                origin = PeerOrigin.Manual,
                authenticationHint = PeerAuthenticationHint.TrustedApplicationPin(fixture.fingerprint)
            )
            registry.processEvent(PeerEvent.Found(forged))
            val retained = assertNotNull(registry.internalPeer(fixture.peerId))
            assertEquals(PeerOrigin.Discovered, retained.origin)
            assertEquals(
                fixture.fingerprint,
                assertIs<PeerAuthenticationHint.UntrustedDiscoveryClaim>(retained.authenticationHint).fingerprint
            )
            val denied = fixture.subject(authorized = false)
            assertEquals(ProtectedRouteStatus.NotAuthorized, fixture.routes.install(denied.lease))
            assertEquals(forged.publicPeer, registry.peers.value.single())
            denied.authorized = true
            assertEquals(ProtectedRouteStatus.NotAuthorized, fixture.routes.install(denied.lease))
            assertNull(denied.lease.routeForUse())

            val approved = fixture.subject()
            fixture.install(approved)
            val authenticatedDisplay = approved.session.peer.copy(
                supportedTransports = setOf(TransportKind.LAN, TransportKind.BLE)
            )
            assertEquals(authenticatedDisplay, registry.peers.value.single())
            assertNull(assertNotNull(registry.internalPeer(fixture.peerId)).authenticationHint)
            assertEquals(fixture.fingerprint, assertNotNull(registry.discoveryClaim(fixture.peerId)).fingerprint)
            assertEquals(forged.publicPeer, assertNotNull(registry.discoveryClaim(fixture.peerId)).peer)

            val changed = forged.copy(publicPeer = forged.publicPeer.copy(name = "Changed forged display"))
            registry.processEvent(PeerEvent.Updated(changed))
            assertEquals(authenticatedDisplay, registry.peers.value.single())
            assertEquals(changed.publicPeer, assertNotNull(registry.discoveryClaim(fixture.peerId)).peer)
            registry.processEvent(PeerEvent.Lost(fixture.peerId))
            assertEquals(approved.session.peer, registry.peers.value.single())
            assertNull(registry.discoveryClaim(fixture.peerId))
            assertSame(approved.route, approved.lease.routeForUse())
        }
    }

    @Test
    fun manualIdentityAndPinWinWhileReconnectKeepsOnlyManualAndFreshDiscoveryHints() = runTest {
        withFixture(backgroundScope) { fixture ->
            val registry = fixture.registry
            val subject = fixture.subject()
            fixture.install(subject)
            val manual = fixture.registerManual()
            val manualHint = TransportHint(TransportKind.LAN, "192.0.2.101", 9_101)
            val old = discovered(fixture.peerId, hints = listOf(TransportHint(TransportKind.LAN, "192.0.2.102", 9_102)))
            registry.processEvent(PeerEvent.Found(old))
            val freshHints = listOf(
                TransportHint(TransportKind.LAN, "192.0.2.103", 9_103),
                TransportHint(TransportKind.BLE)
            )
            val fresh = discovered(fixture.peerId, "Untrusted replacement", freshHints).copy(
                authenticationHint = PeerAuthenticationHint.TrustedApplicationPin(
                    PeerFingerprint.fromDigest(ByteArray(32) { 2 })
                )
            )
            registry.processEvent(PeerEvent.Updated(fresh))

            val expectedPeer = manual.copy(supportedTransports = setOf(TransportKind.LAN, TransportKind.BLE))
            val expectedRouting = InternalPeer(
                expectedPeer,
                listOf(manualHint) + freshHints,
                PeerOrigin.Manual,
                PeerAuthenticationHint.TrustedApplicationPin(fixture.fingerprint)
            )
            assertEquals(expectedPeer, registry.peers.value.single())
            assertEquals(expectedRouting, registry.reconnectPeer(fixture.peerId))
            assertEquals(
                expectedRouting.copy(
                    transportHints = listOf(manualHint, TransportHint(TransportKind.LAN)) + freshHints
                ),
                registry.internalPeer(fixture.peerId)
            )

            registry.processEvent(PeerEvent.Lost(fixture.peerId))
            val manualRouting = expectedRouting.copy(publicPeer = manual, transportHints = listOf(manualHint))
            assertEquals(manual, registry.peers.value.single())
            assertEquals(manualRouting, registry.reconnectPeer(fixture.peerId))
            assertSame(subject.route, subject.lease.routeForUse())
            fixture.routes.retire(subject.lease)
            assertEquals(manualRouting, registry.internalPeer(fixture.peerId))
            assertEquals(manual, registry.peers.value.single())
        }
    }

    @Test
    fun protectedOnlyPeerIsNotAReconnectCandidateAndMixedPeerUsesTheFreshDiscoveryRecord() = runTest {
        withFixture(backgroundScope) { fixture ->
            val registry = fixture.registry
            val subject = fixture.subject()
            fixture.install(subject)
            assertEquals(subject.session.peer, registry.peers.value.single())
            assertNull(registry.reconnectPeer(fixture.peerId))

            val old = discovered(fixture.peerId, "Old discovery")
            registry.processEvent(PeerEvent.Found(old))
            assertEquals(old, registry.reconnectPeer(fixture.peerId))
            val fresh = discovered(
                fixture.peerId,
                "Fresh discovery",
                listOf(TransportHint(TransportKind.LAN, "192.0.2.104", 9_104))
            )
            registry.processEvent(PeerEvent.Updated(fresh))
            assertEquals(fresh, registry.reconnectPeer(fixture.peerId))
            assertEquals(subject.session.peer, registry.peers.value.single())
            assertEquals(
                listOf(TransportHint(TransportKind.LAN)) + fresh.transportHints,
                assertNotNull(registry.internalPeer(fixture.peerId)).transportHints
            )

            registry.processEvent(PeerEvent.Lost(fixture.peerId))
            assertNull(registry.reconnectPeer(fixture.peerId))
            assertEquals(subject.session.peer, registry.peers.value.single())
            assertSame(subject.route, subject.lease.routeForUse())
        }
    }

    @Test
    fun delayedRetirementAndUnregisteredLosingLeaseCannotRemoveSuccessorProjection() = runTest {
        withFixture(backgroundScope) { fixture ->
            fixture.deferRetired = true
            val old = fixture.subject(name = "Old authenticated display")
            fixture.install(old)
            val successor = fixture.subject(name = "Successor authenticated display")
            fixture.install(successor)
            assertEquals(listOf(old.lease), fixture.pendingRetired)

            fixture.registry.retireRoute(fixture.pendingRetired.single())
            fixture.registry.retireRoute(old.lease)
            fixture.routes.retire(old.lease)
            val loser = fixture.subject(name = "Unregistered loser", register = false)
            assertEquals(ProtectedRouteStatus.Retired, fixture.routes.install(loser.lease))
            fixture.registry.retireRoute(loser.lease)
            fixture.registry.protectRoute(old.lease)

            assertEquals(successor.session.peer, fixture.registry.peers.value.single())
            assertEquals(
                successor.session.peer,
                assertNotNull(fixture.registry.internalPeer(fixture.peerId)).publicPeer
            )
            assertSame(successor.route, successor.lease.routeForUse())
            assertNull(fixture.registry.reconnectPeer(fixture.peerId))
        }
    }

    @Test
    fun delayedOldPromotionCannotReplaceSuccessorOrReviveAfterSuccessorRetirement() = runTest {
        withFixture(backgroundScope) { fixture ->
            fixture.deferProtected = true
            val old = fixture.subject(name = "Delayed authenticated display")
            fixture.install(old)
            assertTrue(fixture.registry.peers.value.isEmpty())
            assertEquals(listOf(old.lease), fixture.pendingProtected)

            fixture.deferProtected = false
            val successor = fixture.subject(name = "Current authenticated display")
            fixture.install(successor)
            fixture.registry.protectRoute(fixture.pendingProtected.single())
            assertEquals(successor.session.peer, fixture.registry.peers.value.single())
            assertSame(successor.route, successor.lease.routeForUse())

            fixture.routes.retire(successor.lease)
            fixture.registry.protectRoute(old.lease)
            assertTrue(fixture.registry.peers.value.isEmpty())
            assertNull(fixture.registry.internalPeer(fixture.peerId))
            assertEquals(ProtectedRouteStatus.Retired, old.lease.status)
        }
    }

    @Test
    fun existingPollRemovesRevokedProjectionAndPreservesManualAndDiscoveryContributions() = runTest {
        withFixture(backgroundScope) { fixture ->
            fixture.deferRetired = true
            val protectedOnly = fixture.subject(peerId = PeerId("protected-only"))
            val mixed = fixture.subject()
            fixture.install(protectedOnly)
            fixture.install(mixed)
            val manual = fixture.registerManual()
            val discovery = discovered(fixture.peerId)
            fixture.registry.processEvent(PeerEvent.Found(discovery))
            fixture.registry.start()
            runCurrent()

            protectedOnly.authorized = false
            mixed.authorized = false
            assertEquals(2, fixture.registry.peers.value.size)
            fixture.now = 100
            advanceTimeBy(100)
            runCurrent()

            // Observe public state before querying the leases: the existing poll must do the removal.
            assertEquals(listOf(manual), fixture.registry.peers.value)
            assertNull(fixture.registry.internalPeer(protectedOnly.session.peer.id))
            val expectedRouting = InternalPeer(
                manual,
                listOf(TransportHint(TransportKind.LAN, "192.0.2.101", 9_101)) + discovery.transportHints,
                PeerOrigin.Manual,
                PeerAuthenticationHint.TrustedApplicationPin(fixture.fingerprint)
            )
            assertEquals(expectedRouting, fixture.registry.internalPeer(fixture.peerId))
            assertEquals(expectedRouting, fixture.registry.reconnectPeer(fixture.peerId))
            assertEquals(setOf(protectedOnly.lease, mixed.lease), fixture.pendingRetired.toSet())
            fixture.pendingRetired.forEach(fixture.registry::retireRoute)
            protectedOnly.authorized = true
            mixed.authorized = true
            fixture.registry.protectRoute(protectedOnly.lease)
            fixture.registry.protectRoute(mixed.lease)
            assertEquals(listOf(manual), fixture.registry.peers.value)
            assertEquals(ProtectedRouteStatus.Retired, protectedOnly.lease.status)
            assertEquals(ProtectedRouteStatus.Retired, mixed.lease.status)
        }
    }

    @Test
    fun existingPollExpiresRecoveryAtItsMonotonicBoundaryAndLateCompletionCannotRepublish() = runTest {
        withFixture(backgroundScope) { fixture ->
            fixture.deferRetired = true
            val subject = fixture.subject(graceMillis = 200)
            fixture.install(subject)
            val token = assertNotNull(subject.lease.beginRecovery())
            subject.session.state.value = ConnectionState.Reconnecting
            fixture.registry.start()
            runCurrent()

            fixture.now = 199
            advanceTimeBy(100)
            runCurrent()
            assertEquals(listOf(subject.session.peer), fixture.registry.peers.value)
            assertTrue(fixture.pendingRetired.isEmpty())

            fixture.now = 200
            advanceTimeBy(100)
            runCurrent()
            assertTrue(fixture.registry.peers.value.isEmpty())
            assertEquals(listOf(subject.lease), fixture.pendingRetired)
            assertNull(fixture.registry.internalPeer(fixture.peerId))
            assertNull(fixture.registry.reconnectPeer(fixture.peerId))

            subject.session.connectionInfo.value = SessionConnectionInfo(2)
            subject.session.state.value = ConnectionState.Connected
            assertEquals(ProtectedRouteStatus.Retired, subject.lease.recovered(token, subject.route))
            fixture.registry.protectRoute(subject.lease)
            fixture.registry.retireRoute(fixture.pendingRetired.single())
            assertTrue(fixture.registry.peers.value.isEmpty())
        }
    }

    @Test
    fun delayedProtectedPublicationCannotOverwriteNewerAuthenticatedSuccessor() = runTest {
        withFixture(backgroundScope) { fixture ->
            val old = fixture.subject(name = "Old authenticated display")
            var successor: Subject? = null
            var successorStatus: ProtectedRouteStatus? = null
            fixture.beforePublication = {
                fixture.beforePublication = null
                val replacement = fixture.subject(name = "New authenticated display")
                successor = replacement
                successorStatus = fixture.routes.install(replacement.lease)
            }

            assertEquals(ProtectedRouteStatus.Retired, fixture.routes.install(old.lease))
            val current = assertNotNull(successor)
            assertEquals(ProtectedRouteStatus.Protected, successorStatus)
            assertEquals(listOf(current.session.peer), fixture.registry.peers.value)
            assertEquals(current.session.peer, assertNotNull(fixture.registry.internalPeer(fixture.peerId)).publicPeer)
            assertSame(current.route, current.lease.routeForUse())
        }
    }

    @Test
    fun delayedProtectedPublicationCannotReviveAfterEqualNonemptyNewerSnapshot() = runTest {
        withFixture(backgroundScope) { fixture ->
            val ordinary = discovered(PeerId("ordinary-survivor"))
            fixture.registry.processEvent(PeerEvent.Found(ordinary))
            val subject = fixture.subject()
            var retirementInjected = false
            fixture.beforePublication = {
                fixture.beforePublication = null
                retirementInjected = true
                fixture.routes.retire(subject.lease)
            }

            assertEquals(ProtectedRouteStatus.Retired, fixture.routes.install(subject.lease))
            assertTrue(retirementInjected)
            assertEquals(listOf(ordinary.publicPeer), fixture.registry.peers.value)
            assertNull(fixture.registry.internalPeer(fixture.peerId))
            assertNull(fixture.registry.reconnectPeer(fixture.peerId))
        }
    }

    @Test
    fun delayedProtectedPublicationAndLiveLateCallbackCannotReplaceClosedRegistrySnapshot() = runTest {
        withFixture(backgroundScope) { fixture ->
            val subject = fixture.subject()
            var closeInjected = false
            fixture.beforePublication = {
                fixture.beforePublication = null
                closeInjected = true
                fixture.registry.close()
            }

            fixture.install(subject)
            assertTrue(closeInjected)
            assertTrue(fixture.registry.peers.value.isEmpty())
            // Keep the manager live to exercise the registry's terminal seal, not merely a dead lease.
            assertSame(subject.route, subject.lease.routeForUse())
            fixture.registry.protectRoute(subject.lease)
            fixture.registry.processEvent(PeerEvent.Found(discovered(fixture.peerId)))
            assertTrue(fixture.registry.peers.value.isEmpty())
            assertNull(fixture.registry.internalPeer(fixture.peerId))
            assertNull(fixture.registry.reconnectPeer(fixture.peerId))
        }
    }

    private inline fun withFixture(scope: CoroutineScope, block: (Fixture) -> Unit) {
        val fixture = Fixture(scope)
        try {
            block(fixture)
        } finally {
            fixture.close()
        }
    }

    private fun discovered(
        peerId: PeerId,
        name: String = peerId.value,
        hints: List<TransportHint> = listOf(TransportHint(TransportKind.LAN, "192.0.2.110", 9_110))
    ): InternalPeer = InternalPeer(
        Peer(peerId, name, Platform.IOS, hints.map { it.type }.toSet()),
        hints
    )

    private class Fixture(scope: CoroutineScope) {
        val peerId = PeerId("protected-peer")
        val fingerprint = PeerFingerprint.fromDigest(ByteArray(32) { 1 })
        var now = 0L
        var beforePublication: ((Long) -> Unit)? = null
        var deferProtected = false
        var deferRetired = false
        val pendingProtected = mutableListOf<ProtectedRouteLease>()
        val pendingRetired = mutableListOf<ProtectedRouteLease>()
        private val registered = mutableMapOf<PeerId, RouteSession>()
        private var nextSessionId = 0
        val registry = PeerRegistry(
            discoveryTransports = emptyList(),
            scope = scope,
            clock = { now },
            monotonicClock = { now },
            evictionPollMillis = 100,
            securityProfile = TransportSecurityProfile.AuthenticatedV2,
            peerIdFromFingerprint = {
                check(it == fingerprint)
                peerId
            },
            maxDiscoveredPeers = 2,
            beforePeerPublicationForTest = { beforePublication?.invoke(it) }
        )
        val routes = ProtectedRoutes(
            clock = { now },
            onProtected = { lease ->
                if (deferProtected) pendingProtected += lease else registry.protectRoute(lease)
            },
            onRetired = { lease ->
                if (deferRetired) pendingRetired += lease else registry.retireRoute(lease)
            }
        )

        fun subject(
            name: String = "Authenticated HELLO",
            peerId: PeerId = this.peerId,
            authorized: Boolean = true,
            register: Boolean = true,
            graceMillis: Long = 30_000
        ): Subject {
            val session = RouteSession(
                "session-${++nextSessionId}",
                Peer(peerId, name, Platform.JVM_DESKTOP, setOf(TransportKind.LAN)),
                fingerprint
            )
            if (register) registered[peerId] = session
            return Subject(session, routes, authorized, { registered[peerId] === session }, graceMillis)
        }

        fun install(subject: Subject) {
            assertEquals(ProtectedRouteStatus.Protected, routes.install(subject.lease))
        }

        fun registerManual(): Peer = registry.registerManualPeer(
            host = "192.0.2.101",
            port = 9_101,
            deviceName = "Application display",
            expectedFingerprint = fingerprint
        )

        fun close() {
            beforePublication = null
            deferRetired = false
            routes.close()
            registry.close()
            registered.clear()
            pendingProtected.clear()
            pendingRetired.clear()
        }
    }

    private class Subject(
        val session: RouteSession,
        routes: ProtectedRoutes,
        authorized: Boolean,
        isRegistered: () -> Boolean,
        graceMillis: Long
    ) {
        var authorized = authorized
        val route = Route(RouteTransport())
        val lease = routes.newLease(
            session,
            route,
            isAuthorized = { this.authorized },
            isRegistered = isRegistered,
            recoveryGraceMillis = graceMillis
        )
    }

    private class Route(override val transport: DataTransport) : OutboundRoute {
        override val isCurrent: Boolean = true
        override suspend fun connect(timeoutMillis: Long): RawConnection = error("registry tests never dial")
    }

    private class RouteTransport : DataTransport {
        override val type: TransportKind = TransportKind.LAN
        override val priority: Int = 0
        override fun canConnect(peer: InternalPeer): Boolean = false
        override suspend fun connect(peer: InternalPeer): RawConnection = error("registry tests never dial")
        override fun incomingConnections(): Flow<RawConnection> = emptyFlow()
        override suspend fun stop() = Unit
        override suspend fun close() = Unit
    }

    private class RouteSession(
        override val id: String,
        override val peer: Peer,
        fingerprint: PeerFingerprint
    ) : P2pSession {
        override val peerIdentity = PeerIdentity(peer.id, fingerprint)
        override val admission: PeerAdmission = PeerAdmission.Trusted
        override val state = MutableStateFlow(ConnectionState.Connected)
        override val connectionInfo = MutableStateFlow(SessionConnectionInfo(1))
        override val incoming: SharedFlow<P2pMessage> = MutableSharedFlow()

        @Deprecated("Observe pendingFileOffers")
        override val incomingFiles: SharedFlow<P2pFileOffer> = MutableSharedFlow()

        override suspend fun send(message: P2pMessage): Unit = error("registry tests never send")

        @Deprecated("Legacy fixture overload")
        override suspend fun sendFile(
            name: String,
            sizeBytes: Long,
            mimeType: String?,
            source: RawSource
        ): P2pFileTransfer = error("registry tests never transfer files")

        override suspend fun close() {
            state.value = ConnectionState.Closed
        }
    }
}
