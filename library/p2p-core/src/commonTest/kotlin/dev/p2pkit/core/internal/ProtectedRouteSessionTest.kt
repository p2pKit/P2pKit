package dev.p2pkit.core.internal

import dev.p2pkit.core.AppId
import dev.p2pkit.core.ConnectionState
import dev.p2pkit.core.ExplicitSecurityRisk
import dev.p2pkit.core.P2pError
import dev.p2pkit.core.P2pKit
import dev.p2pkit.core.P2pMessage
import dev.p2pkit.core.P2pSession
import dev.p2pkit.core.P2pSessionProfile
import dev.p2pkit.core.PayloadBudget
import dev.p2pkit.core.PeerAdmission
import dev.p2pkit.core.PeerAdmissionController
import dev.p2pkit.core.PeerAuthorizationPolicy
import dev.p2pkit.core.PeerFingerprint
import dev.p2pkit.core.ProtectedRouteStatus
import dev.p2pkit.core.ReconnectPolicy
import dev.p2pkit.core.SessionFailureKind
import dev.p2pkit.core.TransportKind
import dev.p2pkit.core.dsl.P2pKitBuilder
import dev.p2pkit.core.internal.security.noise.NoiseTransportEofException
import dev.p2pkit.core.security.SecureIdentityService
import dev.p2pkit.core.security.platformSecurityCryptography
import dev.p2pkit.core.testfixtures.CopyingRawConnection
import dev.p2pkit.core.testfixtures.FakeConnectionPair
import dev.p2pkit.core.testfixtures.FakeDataTransport
import dev.p2pkit.core.testfixtures.FakeDiscoveryTransport
import dev.p2pkit.core.testfixtures.MemorySecureIdentityStorage
import dev.p2pkit.core.testfixtures.RecordingLogger
import dev.p2pkit.core.testfixtures.SnapshotList
import dev.p2pkit.core.testfixtures.createSecureTestKit
import dev.p2pkit.core.testfixtures.peerForSecureKit
import dev.p2pkit.core.testfixtures.withTestKit
import dev.p2pkit.core.transport.DataTransport
import dev.p2pkit.core.transport.InternalPeer
import dev.p2pkit.core.transport.OutboundRoute
import dev.p2pkit.core.transport.OutboundRouteConnection
import dev.p2pkit.core.transport.OutboundRouteUnavailable
import dev.p2pkit.core.transport.PeerEvent
import dev.p2pkit.core.transport.RawConnection
import dev.p2pkit.core.transport.TransportHint
import kotlin.concurrent.atomics.AtomicInt
import kotlin.concurrent.atomics.AtomicReference
import kotlin.concurrent.atomics.ExperimentalAtomicApi
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertFalse
import kotlin.test.assertIs
import kotlin.test.assertTrue
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.CoroutineStart
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.async
import kotlinx.coroutines.cancelAndJoin
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.onSubscription
import kotlinx.coroutines.launch
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withTimeout

/** Production builder/Noise/session commitment, with synthetic byte streams and exact route owners. */
@OptIn(ExplicitSecurityRisk::class, ExperimentalAtomicApi::class)
class ProtectedRouteSessionTest {
    @Test
    fun pinnedCommitProjectsKnownPeerWithoutDiscoveryAndCloseRetiresImmediately() = runBlocking {
        withPair { pair ->
            val session = pair.connect()
            assertEquals(ProtectedRouteStatus.Protected, session.protectedRouteStatus)
            assertEquals(pair.bob.localFingerprint, session.peerIdentity.fingerprint)
            assertEquals(listOf(pair.bob.localPeerId), pair.alice.peers.value.map { it.id })
            val inbound = pair.bob.sessions.value.single()
            assertEquals(ProtectedRouteStatus.Unsupported, inbound.protectedRouteStatus)
            session.close()
            assertEquals(ProtectedRouteStatus.Retired, session.protectedRouteStatus)
            assertTrue(pair.alice.peers.value.isEmpty())
            assertEquals(0, pair.probes.load())
        }
    }

    @Test
    fun explicitOriginalPinAuthorizesProtectedRouteUnderRejectUnknown() = runBlocking {
        withPair(authorization = { PeerAuthorizationPolicy.RejectUnknown }) { pair ->
            val session = pair.connect(explicit = true)
            assertEquals(ProtectedRouteStatus.Protected, session.protectedRouteStatus)
        }
    }

    @Test
    fun routeMustBelongToTheExactSelectedTransport() = runBlocking {
        withPair(foreignOwner = true) { pair ->
            val session = pair.connect()
            assertEquals(ProtectedRouteStatus.Unsupported, session.protectedRouteStatus)
            assertTrue(pair.alice.peers.value.isEmpty())
        }
    }

    @Test
    fun knownRouteBypassesUnavailableDiscoverySelectionAndReauthenticates() = runBlocking {
        withPair { pair ->
            val session = pair.connect()
            pair.aliceData.setCanConnect(false)
            pair.loseAndRecover(session)
            assertEquals(1, pair.aliceData.connectCalls.size, "replay never re-enters discovery selection")
            assertEquals(1, pair.probes.load())
            assertEquals(listOf(1_500L), pair.probeBudgets.snapshot())
            assertEquals(ProtectedRouteStatus.Protected, session.protectedRouteStatus)
            assertEquals(pair.bob.localFingerprint, session.peerIdentity.fingerprint)
            assertEquals(2L, session.connectionInfo.value.generation)
            pair.exchange(session)
        }
    }

    @Test
    fun cleanRouteRefusalFallsBackWithinTheOnlyLogicalAttempt() = runBlocking {
        withPair(probeFailure = { OutboundRouteUnavailable("old endpoint retired cleanly") }) { pair ->
            val session = pair.connect()
            pair.loseAndRecover(session)
            assertEquals(1, pair.probes.load())
            assertEquals(2, pair.aliceData.connectCalls.size, "maxAttempts=1 must still allow clean address rotation")
            assertEquals(ProtectedRouteStatus.Protected, session.protectedRouteStatus)
            pair.exchange(session)
        }
    }

    @Test
    fun acceptAnyContinuityPinOnReconnectNeverBecomesOriginalApproval() = runBlocking {
        withPair(authorization = { PeerAuthorizationPolicy.AcceptAnyAuthenticatedSameApp }) { pair ->
            val session = pair.connect()
            assertEquals(ProtectedRouteStatus.NotAuthorized, session.protectedRouteStatus)
            assertTrue(pair.alice.peers.value.isEmpty())
            pair.loseAndRecover(session)
            assertEquals(ProtectedRouteStatus.NotAuthorized, session.protectedRouteStatus)
            assertEquals(0, pair.probes.load())
            assertEquals(2, pair.aliceData.connectCalls.size)
            assertTrue(pair.alice.peers.value.isEmpty())
            pair.exchange(session)
        }
    }

    @Test
    fun enrollmentWithExplicitPinCannotAcquireProtectedPriority() = runBlocking {
        withPair(aliceConfigure = {
            sessionProfile = profile { PeerAdmission.EnrollmentOnly }
        }) { pair ->
            val session = pair.connect(explicit = true)
            assertEquals(PeerAdmission.EnrollmentOnly, session.admission)
            assertEquals(ProtectedRouteStatus.NotAuthorized, session.protectedRouteStatus)
            assertTrue(pair.alice.peers.value.isEmpty())
        }
    }

    @Test
    fun liveProfileRevocationImmediatelyStopsRouteUse() = runBlocking {
        val decision = MutableStateFlow(PeerAdmission.Trusted)
        withPair(aliceConfigure = { sessionProfile = profile { decision.value } }) { pair ->
            val session = pair.connect()
            assertEquals(ProtectedRouteStatus.Protected, session.protectedRouteStatus)
            decision.value = PeerAdmission.Rejected
            assertEquals(ProtectedRouteStatus.Retired, session.protectedRouteStatus)
            assertEquals(0, pair.probes.load())
            withTimeout(3_500) { pair.alice.peers.first { it.isEmpty() } }
        }
    }

    @Test
    fun cancelledPrecommitNeverPublishesOrRetainsCandidateRoute() = runBlocking {
        val beforeCommit = CompletableDeferred<Unit>()
        val release = CompletableDeferred<Unit>()
        withPair(aliceConfigure = {
            beforeSessionCommitForTest = {
                beforeCommit.complete(Unit)
                release.await()
            }
        }) { pair ->
            coroutineScope {
                val connecting = async { pair.connect() }
                try {
                    withTimeout(5_000) { beforeCommit.await() }
                    assertTrue(pair.alice.peers.value.isEmpty())
                    assertTrue(pair.alice.sessions.value.isEmpty())
                    connecting.cancelAndJoin()
                    assertTrue(pair.alice.peers.value.isEmpty())
                    assertTrue(pair.alice.sessions.value.isEmpty())
                    assertEquals(0, pair.probes.load())
                } finally {
                    release.complete(Unit)
                }
            }
        }
    }

    @Test
    fun stopSealsProtectedProjectionAndNoOldRouteCanRepublish() = runBlocking {
        withPair { pair ->
            val session = pair.connect()
            pair.alice.stop()
            assertEquals(ProtectedRouteStatus.Retired, session.protectedRouteStatus)
            assertTrue(pair.alice.peers.value.isEmpty())
            assertTrue(pair.alice.sessions.value.isEmpty())
            assertEquals(0, pair.probes.load())
            assertTrue(pair.aliceData.isClosed)
        }
    }

    @Test
    fun brokenOptionalOwnerMetadataDoesNotLoseTheAuthenticatedStream() = runBlocking {
        withPair(ownerGetterFailureAt = 2) { pair ->
            val session = pair.connect()
            assertEquals(2, pair.ownerReads.load())
            assertEquals(ProtectedRouteStatus.Unsupported, session.protectedRouteStatus)
            assertEquals(ConnectionState.Connected, session.state.value)
            pair.exchange(session)
        }
    }

    @Test
    fun cancelledOptionalOwnerMetadataClosesAlreadyAuthenticatedResources() = runBlocking {
        withPair(ownerGetterFailureAt = 2,
            ownerGetterFailure = { CancellationException("cancel during optional ownership query") }) { pair ->
            assertFailsWith<CancellationException> { pair.connect() }
            assertEquals(2, pair.ownerReads.load())
            assertTrue(pair.alice.sessions.value.isEmpty())
            assertTrue(pair.alice.peers.value.isEmpty())
            assertEquals(ConnectionState.Closed, pair.initial.a.state.value)
        }
    }

    @Test
    fun uncertainProtectedProbeFailureIsTerminalEvenWithMoreAttemptsAvailable() = runBlocking {
        withPair(reconnectAttempts = 3,
            probeFailure = { IllegalStateException("retirement was not observed") }) { pair ->
            val session = pair.connect()
            pair.expectFailure("IllegalStateException: retirement was not observed")
            pair.loseAndFail(session, SessionFailureKind.Transport)
            assertEquals(0, pair.retry.a.writeAttempts)
        }
    }

    @Test
    fun protectedStreamStillRequiresOriginalIdentityAndNeverFallsBackAfterRejection() = runBlocking {
        withPair(reconnectAttempts = 3) { pair ->
            val session = pair.connect()
            val impostorData = FakeDataTransport()
            val impostorStore = MemorySecureIdentityStorage()
            try {
                withTestKit(create = { recorder ->
                    createSecureTestKit(AppId("secure.protected.route"), "Impostor", impostorStore, impostorData,
                        PeerAuthorizationPolicy.PinnedOnly(setOf(checkNotNull(pair.alice.localFingerprint)))) {
                        logger = recorder
                    }
                }, verifyDiagnostics = { recorder ->
                    val failures = recorder.entries.filter {
                        it.level == RecordingLogger.Level.WARN || it.level == RecordingLogger.Level.ERROR
                    }
                    // The owned stop can win the responder's EOF diagnostic after our mandatory
                    // original-identity rejection. At most one controlled incoming attempt exists.
                    assertTrue(failures.size <= 1)
                    failures.forEach { entry ->
                        assertEquals(RecordingLogger.Level.WARN, entry.level)
                        assertEquals("Incoming session setup failed", entry.message)
                        val authentication = assertIs<P2pError.AuthenticationFailed>(entry.throwable)
                        assertEquals("Authenticated protocol v2 setup failed", authentication.reason)
                        assertTrue(authentication.suppressedExceptions.isEmpty())
                        val eof = assertIs<NoiseTransportEofException>(authentication.cause)
                        assertEquals("Raw connection ended before 2 bytes were available", eof.message)
                        assertTrue(eof.suppressedExceptions.isEmpty())
                    }
                }) { impostor ->
                    impostor.start()
                    pair.retryTarget.store(impostorData)
                    pair.expectFailure("AuthenticatedIdentityMismatch: " +
                        "Authenticated remote identity did not match the selected peer")
                    pair.loseAndFail(session, SessionFailureKind.Authentication)
                    assertTrue(impostor.sessions.value.isEmpty())
                    assertEquals(ConnectionState.Closed, pair.retry.a.state.value)
                    assertEquals(pair.bob.localFingerprint, session.peerIdentity.fingerprint)
                }
            } finally {
                impostorStore.clear()
            }
        }
    }

    @Test
    fun cleanProbeRefusalDoesNotRemoveOrdinaryFallbackRetrySemantics() = runBlocking {
        withPair(reconnectAttempts = 2, ordinarySecondFailure = IllegalStateException("first fallback unavailable"),
            probeFailure = { OutboundRouteUnavailable("confirmed clean refusal") }) { pair ->
            val session = pair.connect()
            pair.expectFailure(
                "IllegalStateException: first fallback unavailable", dialed = "LAN:?:?", source = "FALLBACK"
            )
            pair.loseAndRecover(session)
            assertEquals(2, pair.probes.load())
            assertEquals(3, pair.aliceData.connectCalls.size)
            assertEquals(ProtectedRouteStatus.Protected, session.protectedRouteStatus)
            pair.exchange(session)
        }
    }

    @Test
    fun originalEndpointFallbackIsNotShadowedByDisplayOnlyProtection() = runBlocking {
        withPair(probeFailure = { OutboundRouteUnavailable("confirmed clean refusal") }) { pair ->
            val hints = listOf(TransportHint(TransportKind.LAN, host = "192.0.2.7", port = 9123))
            pair.discover(hints)
            val session = pair.connect()
            pair.aliceDiscovery.emit(PeerEvent.Lost(pair.bob.localPeerId))
            // A sentinel supplies a deterministic processing barrier without adding a new Bob record.
            withTimeout(3_500) {
                val marker = peerForSecureKit(pair.bob).copy(id = dev.p2pkit.core.PeerId("lost-barrier"))
                pair.aliceDiscovery.emit(PeerEvent.Found(InternalPeer(marker, emptyList())))
                pair.alice.peers.first { peers -> peers.any { it.id == marker.id } }
            }
            pair.loseAndRecover(session)
            assertEquals(hints, pair.aliceData.connectCalls.last().transportHints)
            pair.exchange(session)
        }
    }

    @Test
    fun cleanRefusalReadsTheActualNewDiscoveryHintsWithinOneAttempt() = runBlocking {
        withPair(probeFailure = { OutboundRouteUnavailable("confirmed clean refusal") }) { pair ->
            val old = listOf(TransportHint(TransportKind.LAN, host = "192.0.2.7", port = 9123))
            val fresh = listOf(TransportHint(TransportKind.LAN, host = "192.0.2.9", port = 9456))
            pair.discover(old)
            val session = pair.connect()
            pair.discover(fresh)
            pair.loseAndRecover(session)
            assertEquals(old, pair.aliceData.connectCalls.first().transportHints)
            assertEquals(fresh, pair.aliceData.connectCalls.last().transportHints)
            assertEquals(1, pair.probes.load())
            assertEquals(2, pair.aliceData.connectCalls.size)
            pair.exchange(session)
        }
    }

    @Test
    fun synchronousGenerationObserverCannotRetireTheRearmHandoff() = runBlocking {
        withPair { pair ->
            val session = pair.connect()
            coroutineScope {
                val seen = CompletableDeferred<Pair<ConnectionState, ProtectedRouteStatus>>()
                val observer = launch(Dispatchers.Unconfined, start = CoroutineStart.UNDISPATCHED) {
                    session.connectionInfo.first { info ->
                        if (info.generation != 2L) false else {
                            seen.complete(session.state.value to session.protectedRouteStatus)
                            true
                        }
                    }
                }
                try {
                    pair.loseAndRecover(session)
                    assertEquals(ConnectionState.Reconnecting to ProtectedRouteStatus.Protected, seen.await())
                    assertEquals(ProtectedRouteStatus.Protected, session.protectedRouteStatus)
                    pair.exchange(session)
                } finally {
                    observer.cancelAndJoin()
                }
            }
        }
    }

    private fun profile(decide: () -> PeerAdmission): P2pSessionProfile = P2pSessionProfile(
        PeerAdmissionController { decide() }, PayloadBudget(4L * 1_048_576), maxTrustedSessions = 4
    )

    private suspend fun withPair(
        authorization: (PeerFingerprint) -> PeerAuthorizationPolicy = { PeerAuthorizationPolicy.PinnedOnly(setOf(it)) },
        foreignOwner: Boolean = false,
        probeFailure: (() -> Throwable)? = null,
        aliceConfigure: P2pKitBuilder.() -> Unit = {},
        reconnectAttempts: Int = 1,
        ownerGetterFailureAt: Int? = null,
        ownerGetterFailure: () -> Throwable = { IllegalStateException("broken optional metadata") },
        ordinarySecondFailure: Throwable? = null,
        test: suspend (PairScope) -> Unit
    ) {
        val app = AppId("secure.protected.route")
        val aliceStore = MemorySecureIdentityStorage()
        val bobStore = MemorySecureIdentityStorage()
        val initial = FakeConnectionPair()
        val retry = FakeConnectionPair()
        val bobData = FakeDataTransport()
        val retryTarget = AtomicReference(bobData)
        val aliceDiscovery = FakeDiscoveryTransport(strictDelivery = true)
        val expectedAliceWarnings = SnapshotList<RecordingLogger.Entry>()
        val ownerReads = AtomicInt(0)
        val foreign = FakeDataTransport()
        val probes = AtomicInt(0)
        val dials = AtomicInt(0)
        val retryCount = AtomicInt(0)
        val probeBudgets = SnapshotList<Long>()
        val retryReady = CompletableDeferred<Unit>()
        lateinit var aliceData: FakeDataTransport
        lateinit var firstRoute: OutboundRoute
        lateinit var nextRoute: OutboundRoute
        fun retryConnection(): RawConnection {
            assertEquals(1, retryCount.addAndFetch(1), "exactly one second owned byte stream")
            retryTarget.load().emitIncoming(CopyingRawConnection(retry.b))
            return routed(CopyingRawConnection(retry.a), nextRoute)
        }
        aliceData = FakeDataTransport(outgoingConnection = {
            when (dials.addAndFetch(1)) {
                1 -> {
                    bobData.emitIncoming(CopyingRawConnection(initial.b))
                    routed(CopyingRawConnection(initial.a), firstRoute)
                }
                2 -> ordinarySecondFailure?.let { throw it } ?: retryConnection()
                3 -> if (ordinarySecondFailure != null) retryConnection() else error("unexpected third ordinary dial")
                else -> error("unexpected extra ordinary dial")
            }
        })
        // Block only the synthetic retry until the old responder has retired, rather than racing
        // a still-live old registration. No network or production timeout is bypassed by this gate.
        val selected = object : DataTransport by aliceData {
            override suspend fun connect(peer: InternalPeer): RawConnection {
                if (aliceData.connectCalls.isNotEmpty()) retryReady.await()
                return aliceData.connect(peer)
            }
        }
        val owner = if (foreignOwner) foreign else selected
        firstRoute = object : OutboundRoute {
            override val transport: DataTransport
                get() {
                    if (ownerReads.addAndFetch(1) == ownerGetterFailureAt) throw ownerGetterFailure()
                    return owner
                }
            override val isCurrent: Boolean get() = !aliceData.isClosed
            override suspend fun connect(timeoutMillis: Long): RawConnection {
                probes.addAndFetch(1)
                probeBudgets.add(timeoutMillis)
                retryReady.await()
                probeFailure?.let { throw it() }
                return retryConnection()
            }
        }
        nextRoute = object : OutboundRoute {
            override val transport: DataTransport = owner
            override val isCurrent: Boolean get() = !aliceData.isClosed
            override suspend fun connect(timeoutMillis: Long): RawConnection = error("unexpected third epoch")
        }
        try {
            val alicePin = fingerprint(app, aliceStore)
            val bobPin = fingerprint(app, bobStore)
            withTestKit(create = { recording ->
                createSecureTestKit(app, "Alice", aliceStore, selected, authorization(bobPin),
                    reconnect = ReconnectPolicy.Enabled(reconnectAttempts, 50), discovery = aliceDiscovery) {
                    logger = recording
                    aliceConfigure()
                }
            }, verifyDiagnostics = { recorder ->
                assertEquals(expectedAliceWarnings.snapshot(), recorder.entries.filter {
                    it.level == RecordingLogger.Level.WARN || it.level == RecordingLogger.Level.ERROR
                })
            }) { alice ->
                withTestKit(create = { recording ->
                    createSecureTestKit(
                        app, "Bob", bobStore, bobData, PeerAuthorizationPolicy.PinnedOnly(setOf(alicePin))
                    ) {
                        logger = recording
                    }
                }) { bob ->
                    test(PairScope(
                        alice, bob, aliceData, aliceDiscovery, initial, retry, retryReady, probes,
                        probeBudgets, expectedAliceWarnings, ownerReads, retryTarget, reconnectAttempts
                    ))
                }
            }
        } finally {
            retryReady.complete(Unit)
            initial.a.close()
            initial.b.close()
            retry.a.close()
            retry.b.close()
            foreign.close()
            aliceStore.clear()
            bobStore.clear()
        }
    }

    private fun fingerprint(app: AppId, store: MemorySecureIdentityStorage): PeerFingerprint {
        val local = SecureIdentityService(platformSecurityCryptography(), store).loadOrCreate(app)
        return try { local.fingerprint } finally { local.clearPrivate() }
    }

    private fun routed(raw: RawConnection, route: OutboundRoute): RawConnection =
        object : OutboundRouteConnection, RawConnection by raw {
            override val outboundRoute: OutboundRoute = route
        }

    private class PairScope(
        val alice: P2pKit,
        val bob: P2pKit,
        val aliceData: FakeDataTransport,
        val aliceDiscovery: FakeDiscoveryTransport,
        val initial: FakeConnectionPair,
        val retry: FakeConnectionPair,
        val retryReady: CompletableDeferred<Unit>,
        val probes: AtomicInt,
        val probeBudgets: SnapshotList<Long>,
        val expectedAliceWarnings: SnapshotList<RecordingLogger.Entry>,
        val ownerReads: AtomicInt,
        val retryTarget: AtomicReference<FakeDataTransport>,
        val maxAttempts: Int
    ) {
        suspend fun connect(explicit: Boolean = false): P2pSession = withTimeout(5_000) {
            val session = if (explicit) alice.connect(peerForSecureKit(bob), checkNotNull(bob.localFingerprint))
            else alice.connect(peerForSecureKit(bob))
            bob.sessions.first { it.size == 1 }
            session
        }

        suspend fun lose(session: P2pSession): P2pSession {
            val previous = bob.sessions.value.single()
            initial.hangUp(initial.b)
            withTimeout(5_000) {
                previous.state.first { it == ConnectionState.Failed }
                session.state.first { it == ConnectionState.Reconnecting || it == ConnectionState.Failed }
            }
            retryReady.complete(Unit)
            return previous
        }

        suspend fun loseAndRecover(session: P2pSession) {
            val previous = lose(session)
            withTimeout(5_000) {
                session.connectionInfo.first { it.generation == 2L }
                session.state.first { it == ConnectionState.Connected }
                bob.sessions.first { it.singleOrNull()?.let { candidate -> candidate !== previous } == true }
            }
        }

        suspend fun loseAndFail(session: P2pSession, kind: SessionFailureKind) {
            lose(session)
            withTimeout(5_000) { session.state.first { it == ConnectionState.Failed } }
            assertEquals(kind, session.connectionInfo.value.lastFailure?.kind)
            assertEquals(1L, session.connectionInfo.value.generation)
            assertEquals(ProtectedRouteStatus.Retired, session.protectedRouteStatus)
            assertEquals(1, aliceData.connectCalls.size, "failed protected attempt must not fall back later")
            assertEquals(1, probes.load())
        }

        fun expectFailure(reason: String, attempt: Int = 1, dialed: String = "exact-numeric-route",
                          source: String = "PROTECTED") {
            expectedAliceWarnings.add(RecordingLogger.Entry(
                RecordingLogger.Level.WARN,
                "reconnect: attempt=$attempt/$maxAttempts peer=${bob.localPeerId.value.take(8)} " +
                    "name=Bob FAILED dialed=$dialed source=$source reason=$reason"
            ))
        }

        suspend fun discover(hints: List<TransportHint>) {
            withTimeout(3_500) {
                aliceDiscovery.awaitSubscriber()
                aliceDiscovery.emit(PeerEvent.Found(InternalPeer(peerForSecureKit(bob), hints)))
                // A following distinct sentinel on this same ordered source proves registry processing,
                // even if the protected HELLO name means Bob's public projection does not change.
                val marker = peerForSecureKit(bob).copy(id = dev.p2pkit.core.PeerId("route-update-marker"))
                aliceDiscovery.emit(PeerEvent.Found(InternalPeer(marker, emptyList())))
                alice.peers.first { peers -> peers.any { it.id == marker.id } }
                aliceDiscovery.emit(PeerEvent.Lost(marker.id))
                alice.peers.first { peers -> peers.none { it.id == marker.id } }
            }
        }

        suspend fun exchange(session: P2pSession) = coroutineScope {
            val remote = bob.sessions.value.single()
            assertFalse(remote === session)
            assertEquals(bob.localFingerprint, session.peerIdentity.fingerprint)
            val ready = CompletableDeferred<Unit>()
            val receiving = async(start = CoroutineStart.UNDISPATCHED) {
                withTimeout(5_000) { remote.incoming.onSubscription { ready.complete(Unit) }.first() }
            }
            ready.await()
            val message = P2pMessage.Text("authenticated protected-route test")
            session.send(message)
            assertEquals(message, receiving.await())
        }
    }
}
