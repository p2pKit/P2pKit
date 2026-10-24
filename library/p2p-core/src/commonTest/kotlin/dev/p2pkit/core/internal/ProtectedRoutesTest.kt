package dev.p2pkit.core.internal

import dev.p2pkit.core.ConnectionState
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
import dev.p2pkit.core.transport.RawConnection
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.flow.emptyFlow
import kotlinx.io.RawSource
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertNotNull
import kotlin.test.assertNotSame
import kotlin.test.assertNull
import kotlin.test.assertSame
import kotlin.test.assertTrue

/** Deterministic leaf ownership/deadline controls; real Noise/registration tests live separately. */
class ProtectedRoutesTest {
    @Test
    fun pendingLeaseIsUnsupportedWithoutConsumingItsCandidateOrMintingGrace() {
        val routes = ProtectedRoutes({ 0L })
        val subject = Subject(routes)
        assertEquals(ProtectedRouteStatus.Unsupported, subject.lease.status)
        assertNull(subject.lease.routeForUse())
        assertNull(subject.lease.beginRecovery())
        assertEquals(ProtectedRouteStatus.Protected, routes.install(subject.lease))
        assertSame(subject.route, subject.lease.routeForUse())
        assertEquals(TransportKind.LAN, subject.lease.transportKind)
    }

    @Test
    fun capacityIsExactly64AndRefusalDoesNotFailTheOrdinarySession() {
        val routes = ProtectedRoutes({ 0L })
        val protected = (1..64).map { Subject(routes, "peer-$it").also { subject ->
            assertEquals(ProtectedRouteStatus.Protected, routes.install(subject.lease))
        } }
        val excess = Subject(routes, "peer-65")
        assertEquals(ProtectedRouteStatus.CapacityUnavailable, routes.install(excess.lease))
        assertEquals(ConnectionState.Connected, excess.session.state.value)
        assertNull(excess.lease.routeForUse())
        assertNull(excess.lease.takeCandidate(), "a refused lease must not retain its route seed")
        routes.retire(protected.first().lease)
        assertEquals(ProtectedRouteStatus.CapacityUnavailable, routes.install(excess.lease))
        val fresh = Subject(routes, "peer-66")
        assertEquals(ProtectedRouteStatus.Protected, routes.install(fresh.lease))
        assertTrue(protected.drop(1).all { it.lease.status == ProtectedRouteStatus.Protected })
    }

    @Test
    fun testCapacityCannotRaiseTheProductionLimit() {
        assertFailsWith<IllegalArgumentException> { ProtectedRoutes({ 0L }, maxRoutes = 0) }
        assertFailsWith<IllegalArgumentException> { ProtectedRoutes({ 0L }, maxRoutes = 65) }
    }

    @Test
    fun admissionPrunesInvalidTransportGenerationBeforeRefusingCapacity() {
        val routes = ProtectedRoutes({ 0L }, maxRoutes = 1)
        val old = Subject(routes, "old")
        routes.install(old.lease)
        old.route.current = false
        val fresh = Subject(routes, "new")
        assertEquals(ProtectedRouteStatus.Protected, routes.install(fresh.lease))
        assertEquals(ProtectedRouteStatus.Retired, old.lease.status)
        old.route.current = true
        assertEquals(ProtectedRouteStatus.Retired, routes.install(old.lease))
        assertNull(old.lease.routeForUse())
    }

    @Test
    fun admissionPrunesRevokedAuthorizationWithoutWaitingForAPeerListPoll() {
        val routes = ProtectedRoutes({ 0L }, maxRoutes = 1)
        val old = Subject(routes, "old")
        routes.install(old.lease)
        old.authorized = false
        val fresh = Subject(routes, "new")
        assertEquals(ProtectedRouteStatus.Protected, routes.install(fresh.lease))
        assertEquals(ProtectedRouteStatus.Retired, old.lease.status)
    }

    @Test
    fun anUnregisteredOwnerIsReplacedAndOldRetirementCannotRemoveItsSuccessor() {
        val retired = mutableListOf<ProtectedRouteLease>()
        val routes = ProtectedRoutes({ 0L }, onRetired = retired::add, maxRoutes = 1)
        val old = Subject(routes, "same-peer")
        routes.install(old.lease)
        old.registered = false
        val fresh = Subject(routes, "same-peer")
        assertEquals(ProtectedRouteStatus.Protected, routes.install(fresh.lease))
        routes.retire(old.lease)
        assertSame(fresh.route, fresh.lease.routeForUse())
        assertEquals(listOf(old.lease), retired)
    }

    @Test
    fun anotherLiveOwnerWithTheSamePeerIdCannotBeOverwritten() {
        val routes = ProtectedRoutes({ 0L })
        val first = Subject(routes, "same-peer")
        val second = Subject(routes, "same-peer")
        routes.install(first.lease)
        assertEquals(ProtectedRouteStatus.CapacityUnavailable, routes.install(second.lease))
        assertSame(first.route, first.lease.routeForUse())
        routes.retire(second.lease)
        assertEquals(ProtectedRouteStatus.Protected, first.lease.status)
    }

    @Test
    fun terminalStatesRetireBeforeAnyAsynchronousStoreRemoval() {
        listOf(ConnectionState.Closing, ConnectionState.Closed, ConnectionState.Failed).forEach { terminal ->
            val routes = ProtectedRoutes({ 0L }, maxRoutes = 1)
            val subject = Subject(routes, "old")
            routes.install(subject.lease)
            subject.session.state.value = terminal
            // registered remains true: this specifically does not depend on a terminal store watcher.
            assertNull(subject.lease.routeForUse(), "terminal=$terminal")
            assertEquals(ProtectedRouteStatus.Retired, subject.lease.status)
            assertEquals(ProtectedRouteStatus.Protected, routes.install(Subject(routes, "new").lease))
        }
    }

    @Test
    fun unauthenticatedInconsistentEnrollmentAndUnauthorizedCandidatesCannotClaimProtection() {
        val routes = ProtectedRoutes({ 0L })
        val legacy = Subject(routes, "legacy")
        legacy.session.identity = PeerIdentity(legacy.session.peer.id)
        val inconsistent = Subject(routes, "inconsistent")
        inconsistent.session.identity = inconsistent.session.identity.copy(peerId = PeerId("not-the-session-peer"))
        val enrollment = Subject(routes, "enrollment")
        enrollment.session.admission = PeerAdmission.EnrollmentOnly
        val rejected = Subject(routes, "rejected")
        rejected.session.admission = PeerAdmission.Rejected
        val unauthorized = Subject(routes, "unauthorized")
        unauthorized.authorized = false
        listOf(legacy, inconsistent, enrollment, rejected, unauthorized).forEach { subject ->
            assertEquals(ProtectedRouteStatus.NotAuthorized, routes.install(subject.lease))
            assertNull(subject.lease.takeCandidate())
            assertNull(subject.lease.routeForUse())
        }
    }

    @Test
    fun authenticatedIdentityMutationRetiresRatherThanTransferringTheLease() {
        val routes = ProtectedRoutes({ 0L })
        val subject = Subject(routes)
        routes.install(subject.lease)
        subject.session.identity = subject.session.identity.copy(
            fingerprint = PeerFingerprint.fromDigest(ByteArray(32) { 2 })
        )
        assertEquals(ProtectedRouteStatus.Retired, subject.lease.status)
        assertNull(subject.lease.routeForUse())
    }

    @Test
    fun unsupportedInitialRouteIsDroppedAndCannotBeInstalledLater() {
        val routes = ProtectedRoutes({ 0L })
        val subject = Subject(routes)
        subject.route.current = false
        assertEquals(ProtectedRouteStatus.Unsupported, routes.install(subject.lease))
        assertNull(subject.lease.takeCandidate())
        subject.route.current = true
        assertEquals(ProtectedRouteStatus.Unsupported, routes.install(subject.lease))
        assertNull(subject.lease.routeForUse())
    }

    @Test
    fun lossBeforeRegistrationCannotMintANewGracePeriodAtLateInstallation() {
        val routes = ProtectedRoutes({ 0L })
        val subject = Subject(routes)
        assertNull(subject.lease.beginRecovery())
        subject.session.state.value = ConnectionState.Reconnecting
        assertEquals(ProtectedRouteStatus.Retired, routes.install(subject.lease))
        subject.session.rearm()
        assertEquals(ProtectedRouteStatus.Retired, routes.install(subject.lease))
        assertNull(subject.lease.beginRecovery())
    }

    @Test
    fun closeInsideEligibilityEvaluationFencesThePendingInstallation() {
        var protectedCalls = 0
        val routes = ProtectedRoutes({ 0L }, onProtected = { protectedCalls++ })
        val subject = Subject(routes)
        subject.authorizationQuery = {
            routes.close()
            true
        }
        assertEquals(ProtectedRouteStatus.Retired, routes.install(subject.lease))
        assertEquals(0, protectedCalls)
        assertNull(subject.lease.routeForUse())
        assertEquals(ProtectedRouteStatus.Retired, routes.install(Subject(routes, "later").lease))
    }

    @Test
    fun retirementInsideEligibilityEvaluationFencesThePendingInstallation() {
        var protectedCalls = 0
        val routes = ProtectedRoutes({ 0L }, onProtected = { protectedCalls++ })
        val subject = Subject(routes)
        subject.authorizationQuery = {
            routes.retire(subject.lease)
            true
        }
        assertEquals(ProtectedRouteStatus.Retired, routes.install(subject.lease))
        assertEquals(0, protectedCalls)
        assertNull(subject.lease.routeForUse())
        assertEquals(ProtectedRouteStatus.Protected, routes.install(Subject(routes, "later").lease))
    }

    @Test
    fun installRetireAndCloseAreIdempotentAndNeverRestoreTheSeed() {
        val protected = mutableListOf<ProtectedRouteLease>()
        val retired = mutableListOf<ProtectedRouteLease>()
        val routes = ProtectedRoutes({ 0L }, protected::add, retired::add)
        val subject = Subject(routes)
        repeat(3) { assertEquals(ProtectedRouteStatus.Protected, routes.install(subject.lease)) }
        repeat(3) { routes.retire(subject.lease) }
        repeat(3) { routes.close() }
        assertEquals(listOf(subject.lease), protected)
        assertEquals(listOf(subject.lease), retired)
        assertEquals(ProtectedRouteStatus.Retired, routes.install(subject.lease))
        assertNull(subject.lease.beginRecovery())
        assertNull(subject.lease.takeCandidate())
    }

    @Test
    fun repeatedRecoveryDoesNotMoveTheExact30000MillisecondDeadline() {
        var now = 100L
        val routes = ProtectedRoutes({ now })
        val subject = Subject(routes)
        routes.install(subject.lease)
        val first = assertNotNull(subject.lease.beginRecovery())
        assertSame(first, subject.lease.beginRecovery(), "pre-publication repetition must reuse its token")
        subject.session.state.value = ConnectionState.Reconnecting
        now = 30_099
        assertSame(first, subject.lease.beginRecovery())
        assertSame(subject.route, subject.lease.routeForUse())
        now = 30_100
        assertNull(subject.lease.beginRecovery())
        assertNull(subject.lease.routeForUse())
        assertEquals(ProtectedRouteStatus.Retired, subject.lease.status)
        subject.session.rearm()
        assertEquals(ProtectedRouteStatus.Retired, subject.lease.recovered(first, subject.route))
    }

    @Test
    fun expiredRecoveryIsPrunedWhenAnotherIdentityNeedsCapacity() {
        var now = 0L
        val routes = ProtectedRoutes({ now }, maxRoutes = 1)
        val old = Subject(routes, "old")
        routes.install(old.lease)
        old.beginLoss()
        now = 30_000
        val fresh = Subject(routes, "new")
        assertEquals(ProtectedRouteStatus.Protected, routes.install(fresh.lease))
        assertEquals(ProtectedRouteStatus.Retired, old.lease.status)
    }

    @Test
    fun profileGraceCanOnlyShortenThe30000MillisecondMaximum() {
        listOf(0L to 0L, 5L to 5L, 90_000L to 30_000L).forEach { (requested, bound) ->
            var now = 0L
            val routes = ProtectedRoutes({ now })
            val subject = Subject(routes, grace = requested)
            routes.install(subject.lease)
            val token = subject.lease.beginRecovery()
            if (bound == 0L) {
                assertNull(token)
            } else {
                assertNotNull(token)
                subject.session.state.value = ConnectionState.Reconnecting
                now = bound - 1
                assertEquals(ProtectedRouteStatus.Protected, subject.lease.status)
                now = bound
            }
            assertEquals(ProtectedRouteStatus.Retired, subject.lease.status, "requested=$requested")
        }
    }

    @Test
    fun preLossConnectedObservationAloneCannotPretendThatRearmCompleted() {
        var now = 0L
        val routes = ProtectedRoutes({ now })
        val subject = Subject(routes)
        routes.install(subject.lease)
        val token = assertNotNull(subject.lease.beginRecovery())
        val uninstalled = Route(subject.route.transport)
        now = 29_999
        assertEquals(ProtectedRouteStatus.Protected, subject.lease.recovered(token, uninstalled))
        assertSame(subject.route, subject.lease.routeForUse(), "generation did not advance")
        now = 30_000
        assertEquals(ProtectedRouteStatus.Retired, subject.lease.status)
    }

    @Test
    fun generationPublishedBeforeConnectedRetainsOnlyTheExistingRecoveryDeadline() {
        var now = 0L
        val routes = ProtectedRoutes({ now })
        val subject = Subject(routes)
        routes.install(subject.lease)
        val token = subject.beginLoss()
        now = 29_999
        // Exact production order: a connectionInfo collector can run here, before state publication.
        subject.session.connectionInfo.value = SessionConnectionInfo(2)
        assertEquals(ConnectionState.Reconnecting, subject.session.state.value)
        assertEquals(ProtectedRouteStatus.Protected, subject.lease.status)
        assertSame(token, subject.lease.beginRecovery())
        val notYetCommitted = Route(subject.route.transport)
        assertEquals(ProtectedRouteStatus.Protected, subject.lease.recovered(token, notYetCommitted))
        assertSame(subject.route, subject.lease.routeForUse())
        now = 30_000
        assertEquals(ProtectedRouteStatus.Retired, subject.lease.status, "transient cannot refresh grace")
        subject.session.state.value = ConnectionState.Connected
        assertEquals(ProtectedRouteStatus.Retired, subject.lease.recovered(token, notYetCommitted))
    }

    @Test
    fun recoveryExpiringDuringNewRouteValidationCannotBeRenewed() {
        var now = 0L
        val routes = ProtectedRoutes({ now })
        val subject = Subject(routes)
        routes.install(subject.lease)
        val token = subject.beginLoss()
        subject.session.rearm()
        now = 29_999
        var queries = 0
        subject.authorizationQuery = {
            queries++
            if (queries == 2) now = 30_000 // old entry was valid; validating the new route took time
            true
        }
        assertEquals(ProtectedRouteStatus.Retired, subject.lease.recovered(token, Route(subject.route.transport)))
        assertTrue(queries >= 2)
        assertNull(subject.lease.routeForUse())
    }

    @Test
    fun successfulRearmUpdatesOnlyItsExactEpisodeAndStaleCompletionCannotClearTheNext() {
        var now = 0L
        val routes = ProtectedRoutes({ now })
        val subject = Subject(routes)
        routes.install(subject.lease)
        val first = subject.beginLoss()
        val fresh = Route(subject.route.transport)
        now = 5_000
        subject.session.rearm()
        assertEquals(ProtectedRouteStatus.Protected, subject.lease.recovered(first, fresh))
        assertSame(fresh, subject.lease.routeForUse())
        now = 40_000
        assertEquals(ProtectedRouteStatus.Protected, subject.lease.status, "completed grace must be cleared")
        val second = subject.beginLoss()
        assertNotSame(first, second)
        assertEquals(ProtectedRouteStatus.Protected, subject.lease.recovered(first, null))
        assertSame(fresh, subject.lease.routeForUse())
        now = 69_999
        assertEquals(ProtectedRouteStatus.Protected, subject.lease.status)
        now = 70_000
        assertEquals(ProtectedRouteStatus.Retired, subject.lease.status)
    }

    @Test
    fun overlappingPostRearmLossChangesTheTokenWithoutExtendingUncommittedGrace() {
        var now = 0L
        val routes = ProtectedRoutes({ now })
        val subject = Subject(routes)
        routes.install(subject.lease)
        val first = subject.beginLoss()
        now = 20_000
        subject.session.rearm()
        // The new epoch can fail before the previous handler gets to recovered(first, ...).
        val second = subject.beginLoss()
        assertNotSame(first, second)
        assertEquals(ProtectedRouteStatus.Protected, subject.lease.recovered(first, null))
        now = 29_999
        assertSame(second, subject.lease.beginRecovery())
        now = 30_000
        assertEquals(ProtectedRouteStatus.Retired, subject.lease.status)
    }

    @Test
    fun nullAndCounterfeitRecoveryTokensCannotReplaceOrRetireTheCurrentRoute() {
        val routes = ProtectedRoutes({ 0L })
        val first = Subject(routes, "first")
        val second = Subject(routes, "second")
        routes.install(first.lease)
        routes.install(second.lease)
        val token = first.beginLoss()
        val otherToken = second.beginLoss()
        first.session.rearm()
        listOf(null, ProtectedRouteRecovery(), otherToken).forEach { wrong ->
            assertEquals(ProtectedRouteStatus.Protected, first.lease.recovered(wrong, null))
            assertSame(first.route, first.lease.routeForUse())
        }
        val fresh = Route(first.route.transport)
        assertEquals(ProtectedRouteStatus.Protected, first.lease.recovered(token, fresh))
        assertSame(fresh, first.lease.routeForUse())
    }

    @Test
    fun successfulRearmWithoutAnExactRouteOrWithAnotherTransportRetiresProtection() {
        val candidates = listOf<OutboundRoute?>(null, Route(RouteTransport()), Route(RouteTransport(TransportKind.BLE)))
        candidates.forEach { route ->
            val routes = ProtectedRoutes({ 0L })
            val subject = Subject(routes)
            routes.install(subject.lease)
            val token = subject.beginLoss()
            subject.session.rearm()
            assertEquals(ProtectedRouteStatus.Retired, subject.lease.recovered(token, route))
            assertNull(subject.lease.routeForUse())
        }
    }

    @Test
    fun invalidatedOriginalGenerationCannotBeResurrectedByANewCurrentRoute() {
        val routes = ProtectedRoutes({ 0L })
        val subject = Subject(routes)
        routes.install(subject.lease)
        val token = subject.beginLoss()
        subject.session.rearm()
        subject.route.current = false
        val replacement = Route(subject.route.transport)
        assertEquals(ProtectedRouteStatus.Retired, subject.lease.recovered(token, replacement))
        assertNull(subject.lease.routeForUse())
    }

    @Test
    fun staleValidationCannotRetireAFreshlyRecoveredEntryForTheSameLease() {
        val routes = ProtectedRoutes({ 0L })
        val subject = Subject(routes)
        routes.install(subject.lease)
        val token = subject.beginLoss()
        subject.session.rearm()
        val fresh = Route(subject.route.transport)
        subject.route.currentQuery = {
            subject.route.currentQuery = null
            assertEquals(ProtectedRouteStatus.Protected, subject.lease.recovered(token, fresh))
            false
        }
        assertSame(fresh, subject.lease.routeForUse())
        assertEquals(ProtectedRouteStatus.Protected, subject.lease.status)
    }

    @Test
    fun stalePruningSnapshotCannotRemoveARecoveredEntry() {
        val routes = ProtectedRoutes({ 0L }, maxRoutes = 1)
        val subject = Subject(routes, "old")
        routes.install(subject.lease)
        val token = subject.beginLoss()
        subject.session.rearm()
        val fresh = Route(subject.route.transport)
        subject.route.currentQuery = {
            subject.route.currentQuery = null
            assertEquals(ProtectedRouteStatus.Protected, subject.lease.recovered(token, fresh))
            false
        }
        val excess = Subject(routes, "new")
        assertEquals(ProtectedRouteStatus.CapacityUnavailable, routes.install(excess.lease))
        assertSame(fresh, subject.lease.routeForUse())
    }

    @Test
    fun authorizationExceptionsFailClosedBeforeAndAfterInstallation() {
        val routes = ProtectedRoutes({ 0L }, maxRoutes = 1)
        val pending = Subject(routes, "pending")
        pending.authorizationQuery = { error("policy unavailable") }
        assertEquals(ProtectedRouteStatus.NotAuthorized, routes.install(pending.lease))
        val active = Subject(routes, "active")
        routes.install(active.lease)
        active.authorizationQuery = { error("policy unavailable") }
        assertEquals(ProtectedRouteStatus.Retired, active.lease.status)
        assertEquals(ProtectedRouteStatus.Protected, routes.install(Subject(routes, "later").lease))
    }

    @Test
    fun failedProjectionCallbackRollsBackCapacityWithoutFailingTheSession() {
        var shouldThrow = true
        val retired = mutableListOf<ProtectedRouteLease>()
        val routes = ProtectedRoutes(
            { 0L },
            onProtected = { if (shouldThrow) error("projection failed") },
            onRetired = retired::add,
            maxRoutes = 1
        )
        val first = Subject(routes, "first")
        assertEquals(ProtectedRouteStatus.Retired, routes.install(first.lease))
        assertEquals(ConnectionState.Connected, first.session.state.value)
        assertNull(first.lease.routeForUse())
        assertEquals(listOf(first.lease), retired)
        shouldThrow = false
        assertEquals(ProtectedRouteStatus.Protected, routes.install(Subject(routes, "next").lease))
    }

    @Test
    fun closeAttemptsEveryRetirementEvenWhenACallbackThrows() {
        val retired = mutableListOf<ProtectedRouteLease>()
        val routes = ProtectedRoutes({ 0L }, onRetired = {
            retired += it
            error("retirement projection failed")
        })
        val first = Subject(routes, "first")
        val second = Subject(routes, "second")
        routes.install(first.lease)
        routes.install(second.lease)
        routes.close()
        routes.close()
        assertEquals(setOf(first.lease, second.lease), retired.toSet())
        assertEquals(2, retired.size)
        assertEquals(ProtectedRouteStatus.Retired, first.lease.status)
        assertEquals(ProtectedRouteStatus.Retired, second.lease.status)
    }

    @Test
    fun reentrantProjectionReplacementSurvivesAnOldCallbackFailureAndRetirement() {
        var next: Subject? = null
        lateinit var routes: ProtectedRoutes
        lateinit var original: Subject
        routes = ProtectedRoutes({ 0L }, onProtected = { lease ->
            if (lease === original.lease) {
                routes.retire(lease)
                next = Subject(routes, "same-peer").also { routes.install(it.lease) }
                error("late old projection failure")
            }
        })
        original = Subject(routes, "same-peer")
        assertEquals(ProtectedRouteStatus.Retired, routes.install(original.lease))
        val successor = assertNotNull(next)
        assertSame(successor.route, successor.lease.routeForUse())
        routes.retire(original.lease)
        assertEquals(ProtectedRouteStatus.Protected, successor.lease.status)
    }

    @Test
    fun foreignManagersAndCounterfeitLeasesCannotMutateTheLegitimateOwner() {
        val first = ProtectedRoutes({ 0L })
        val second = ProtectedRoutes({ 0L })
        val subject = Subject(first)
        first.install(subject.lease)
        assertEquals(ProtectedRouteStatus.Retired, second.install(subject.lease))
        second.retire(subject.lease)
        second.close()
        assertSame(subject.route, subject.lease.routeForUse())
        val counterfeit = ProtectedRouteLease(first, Any(), subject.session, subject.route, { true }, { true }, 30_000)
        assertEquals(ProtectedRouteStatus.Retired, first.install(counterfeit))
        first.retire(counterfeit)
        assertNull(counterfeit.routeForUse())
        assertEquals(ProtectedRouteStatus.Protected, subject.lease.status)
    }

    @Test
    fun movingTheMonotonicClockBackwardCannotExtendRecovery() {
        var now = 50L
        val routes = ProtectedRoutes({ now })
        val subject = Subject(routes)
        routes.install(subject.lease)
        subject.beginLoss()
        now = 49
        assertEquals(ProtectedRouteStatus.Retired, subject.lease.status)
    }

    @Test
    fun elapsedSubtractionPreservesTheBoundAcrossSignedClockWrap() {
        var now = Long.MAX_VALUE - 100
        val routes = ProtectedRoutes({ now })
        val subject = Subject(routes)
        routes.install(subject.lease)
        subject.beginLoss()
        now += 29_999
        assertEquals(ProtectedRouteStatus.Protected, subject.lease.status)
        now += 1
        assertEquals(ProtectedRouteStatus.Retired, subject.lease.status)
    }

    private class Subject(
        routes: ProtectedRoutes,
        peerId: String = "peer",
        grace: Long = 30_000
    ) {
        val session = RouteSession(peerId)
        val route = Route(RouteTransport())
        var authorized = true
        var registered = true
        var authorizationQuery: (() -> Boolean)? = null
        val lease = routes.newLease(
            session,
            route,
            isAuthorized = { authorizationQuery?.invoke() ?: authorized },
            isRegistered = { registered },
            recoveryGraceMillis = grace
        )

        fun beginLoss(): ProtectedRouteRecovery {
            val token = assertNotNull(lease.beginRecovery())
            session.state.value = ConnectionState.Reconnecting
            return token
        }
    }

    private class Route(override val transport: DataTransport) : OutboundRoute {
        var current = true
        var currentQuery: (() -> Boolean)? = null
        override val isCurrent: Boolean get() = currentQuery?.invoke() ?: current
        override suspend fun connect(timeoutMillis: Long): RawConnection = error("leaf tests never dial")
    }

    private class RouteTransport(override val type: TransportKind = TransportKind.LAN) : DataTransport {
        override val priority: Int = 0
        override fun canConnect(peer: InternalPeer): Boolean = false
        override suspend fun connect(peer: InternalPeer): RawConnection = error("leaf tests never dial")
        override fun incomingConnections(): Flow<RawConnection> = emptyFlow()
        override suspend fun stop() = Unit
        override suspend fun close() = Unit
    }

    private class RouteSession(peerId: String) : P2pSession {
        override val peer = Peer(PeerId(peerId), peerId, Platform.JVM_DESKTOP, setOf(TransportKind.LAN))
        override val id: String = "session-$peerId"
        var identity = PeerIdentity(peer.id, PeerFingerprint.fromDigest(ByteArray(32) { 1 }))
        override val peerIdentity: PeerIdentity get() = identity
        override var admission: PeerAdmission = PeerAdmission.Trusted
        override val state = MutableStateFlow(ConnectionState.Connected)
        override val connectionInfo = MutableStateFlow(SessionConnectionInfo(1))
        override val incoming: SharedFlow<P2pMessage> = MutableSharedFlow()

        @Deprecated("Observe pendingFileOffers")
        override val incomingFiles: SharedFlow<P2pFileOffer> = MutableSharedFlow()

        fun rearm() {
            connectionInfo.value = SessionConnectionInfo(connectionInfo.value.generation + 1)
            state.value = ConnectionState.Connected
        }

        override suspend fun send(message: P2pMessage): Unit = error("leaf tests never send")

        @Deprecated("Legacy fixture overload")
        override suspend fun sendFile(
            name: String,
            sizeBytes: Long,
            mimeType: String?,
            source: RawSource
        ): P2pFileTransfer = error("leaf tests never transfer files")

        override suspend fun close() {
            state.value = ConnectionState.Closed
        }
    }
}
