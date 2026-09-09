package dev.p2pkit.sample.desktop

import dev.p2pkit.core.ConnectionState
import dev.p2pkit.core.P2pMessage
import dev.p2pkit.core.P2pSession
import dev.p2pkit.core.Peer
import dev.p2pkit.core.PeerId
import dev.p2pkit.core.Platform
import dev.p2pkit.core.transfer.P2pFileOffer
import dev.p2pkit.core.transfer.P2pFileTransfer
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.awaitCancellation
import kotlinx.coroutines.cancelAndJoin
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.runBlocking
import kotlinx.io.RawSource
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertSame
import kotlin.test.assertTrue

class CliAutoMeshTest {
    @Test
    fun stablePeerSessionRemovalTriggersExactlyOneReplacement() = scenario { fixture ->
        val stablePeers = fixture.peers.value
        val first = MeshSession("first", fixture.peer)
        val replacement = MeshSession("replacement", fixture.peer)
        fixture.sessions.value = listOf(first)
        fixture.connect = {
            fixture.sessions.value = listOf(replacement)
            replacement
        }
        fixture.start()
        fixture.enabled.value = true
        assertTrue(fixture.calls.isEmpty())

        // No peer Lost/Found, feature toggle, or local display-map update accompanies this loss.
        fixture.sessions.value = emptyList()
        assertSame(stablePeers, fixture.peers.value)
        assertEquals(listOf(fixture.peer), fixture.calls)
        assertEquals(listOf(replacement), fixture.sessions.value)
        assertTrue(fixture.pending.isEmpty())
    }

    @Test
    fun disabledMeshIgnoresLossAndTheEnableActionUsesCurrentSessions() = scenario { fixture ->
        fixture.sessions.value = listOf(MeshSession("first", fixture.peer))
        fixture.connect = { MeshSession("replacement", fixture.peer).also { fixture.sessions.value = listOf(it) } }
        fixture.start()
        fixture.sessions.value = emptyList()
        assertTrue(fixture.calls.isEmpty())
        fixture.enabled.value = true
        assertEquals(listOf(fixture.peer), fixture.calls)
        fixture.enabled.value = false
        fixture.sessions.value = emptyList()
        assertEquals(listOf(fixture.peer), fixture.calls)
    }

    @Test
    fun onlyTheLexicographicallySmallerOwnerInitiates() = scenario { fixture ->
        val equal = meshPeer("local")
        val smaller = meshPeer("aaa")
        fixture.peers.value = listOf(smaller, equal, fixture.peer)
        fixture.start()
        fixture.enabled.value = true
        assertEquals(listOf(fixture.peer), fixture.calls)
        assertEquals(setOf(fixture.peer.id.value), fixture.pending)
    }

    @Test
    fun activeSdkSessionsSuppressDialingEvenBeforeTheCliMapRegistersThem() = scenario { fixture ->
        fixture.sessions.value = listOf(MeshSession("incoming", fixture.peer))
        fixture.start()
        fixture.enabled.value = true
        assertTrue(fixture.calls.isEmpty())
        fixture.enabled.value = false
        fixture.enabled.value = true
        assertTrue(fixture.calls.isEmpty())
        assertTrue(fixture.pending.isEmpty())
    }

    @Test
    fun sharedCommandMarkerAndInFlightMeshAttemptsPreventDuplicateDials() = scenario { fixture ->
        fixture.pending.add(fixture.peer.id.value)
        fixture.start()
        fixture.enabled.value = true
        assertTrue(fixture.calls.isEmpty())
        fixture.pending.remove(fixture.peer.id.value)
        val unrelated = MeshSession("unrelated", meshPeer("aaa"))
        val release = CompletableDeferred<Unit>()
        fixture.connect = {
            release.await()
            null
        }
        // Existing policy is event-driven; marker removal does not invent a retry timer.
        fixture.sessions.value = listOf(unrelated)
        assertEquals(listOf(fixture.peer), fixture.calls)
        assertEquals(setOf(fixture.peer.id.value), fixture.pending)
        fixture.sessions.value = emptyList()
        fixture.peers.value = listOf(fixture.peer, meshPeer("aaa"))
        assertEquals(listOf(fixture.peer), fixture.calls)
        release.complete(Unit)
        assertTrue(fixture.pending.isEmpty())
        assertEquals(listOf(fixture.peer), fixture.calls)
    }

    @Test
    fun admittedSessionLostWhileConnectIsHeldTriggersOneReplacementAfterCompletion() = scenario { fixture ->
        val stablePeers = fixture.peers.value
        val first = MeshSession("first", fixture.peer)
        val replacement = MeshSession("replacement", fixture.peer)
        val published = CompletableDeferred<Unit>()
        val release = CompletableDeferred<Unit>()
        fixture.connect = {
            if (fixture.calls.size == 1) {
                fixture.sessions.value = listOf(first)
                published.complete(Unit)
                release.await()
                first
            } else {
                fixture.sessions.value = listOf(replacement)
                replacement
            }
        }
        fixture.start()
        fixture.enabled.value = true
        published.await()
        assertEquals(listOf(fixture.peer), fixture.calls)
        assertTrue(fixture.peer.id.value in fixture.pending)
        // SessionStore publication precedes connect/registration completion.
        // The Unconfined collector drains this removal before release, so its
        // first attempt to replace the session is held behind our owned marker.
        fixture.sessions.value = emptyList()
        assertEquals(listOf(fixture.peer), fixture.calls)
        assertSame(stablePeers, fixture.peers.value)
        release.complete(Unit)
        assertEquals(listOf(fixture.peer, fixture.peer), fixture.calls)
        assertEquals(listOf(replacement), fixture.sessions.value)
        assertTrue(fixture.pending.isEmpty())
    }

    @Test
    fun returnedSessionAlreadyAbsentStillTriggersOneReplacementWhenSdkPublicationWasConflated() = scenario { fixture ->
        val disappeared = MeshSession("disappeared", fixture.peer)
        val replacement = MeshSession("replacement", fixture.peer)
        fixture.connect = {
            if (fixture.calls.size == 1) {
                // An SDK admission and removal can both precede the next StateFlow
                // snapshot. The successfully returned object still proves admission.
                disappeared
            } else {
                fixture.sessions.value = listOf(replacement)
                replacement
            }
        }
        fixture.start()
        fixture.enabled.value = true
        assertEquals(listOf(fixture.peer, fixture.peer), fixture.calls)
        assertEquals(listOf(replacement), fixture.sessions.value)
        assertTrue(fixture.pending.isEmpty())
    }

    @Test
    fun bareFailureCompletionDoesNotStartARetryLoop() = scenario { fixture ->
        fixture.connect = {
            // A second call installs a session only to bound a broken implementation;
            // the exact assertion below must reject that extra attempt, not hang.
            if (fixture.calls.size == 1) null else {
                MeshSession("unexpected-retry", fixture.peer).also { fixture.sessions.value = listOf(it) }
            }
        }
        fixture.start()
        fixture.enabled.value = true
        assertEquals(listOf(fixture.peer), fixture.calls)
        assertTrue(fixture.sessions.value.isEmpty())
        assertTrue(fixture.pending.isEmpty())
    }

    @Test
    fun completionOnlyRechecksThePeerWhoseRealSessionWasLost() = scenario { fixture ->
        val other = meshPeer("zzz")
        val first = MeshSession("first-other", other)
        val release = CompletableDeferred<Unit>()
        fixture.peers.value = listOf(fixture.peer, other)
        fixture.connect = { peer ->
            if (peer == other && fixture.calls.count { it == other } == 1) {
                fixture.sessions.value = listOf(first)
                release.await()
                first
            } else {
                // Keep a regression from retry-spinning indefinitely if it treats
                // every completion as a full mesh pass instead of a targeted wake.
                if (fixture.calls.count { it == peer } > 4) {
                    MeshSession("unexpected-retry-${peer.id.value}", peer).also {
                        fixture.sessions.value = fixture.sessions.value + it
                    }
                } else {
                    null
                }
            }
        }
        fixture.start()
        fixture.enabled.value = true
        fixture.sessions.value = emptyList()
        val failedPeerCallsBeforeRelease = fixture.calls.count { it == fixture.peer }
        assertEquals(1, fixture.calls.count { it == other })
        release.complete(Unit)
        assertEquals(2, fixture.calls.count { it == other })
        assertEquals(failedPeerCallsBeforeRelease, fixture.calls.count { it == fixture.peer })
        assertTrue(fixture.pending.isEmpty())
        assertTrue(fixture.sessions.value.isEmpty())
    }

    @Test
    fun pinnedWaiterAdmissionNeverReleasesTheOwnerButItsLossSurvivesTheOwnersFailure() = scenario { fixture ->
        val admitted = MeshSession("pinned-waiter", fixture.peer)
        val replacement = MeshSession("replacement", fixture.peer)
        fixture.pending.add(fixture.peer.id.value)
        fixture.connect = {
            fixture.sessions.value = listOf(replacement)
            replacement
        }
        fixture.start()
        fixture.enabled.value = true
        // The waiter got a real SDK session which is already absent; unlike the
        // owner, a pinned waiter must not release the shared pending marker.
        fixture.pending.complete(fixture.peer.id.value, ownsMarker = false, admitted)
        assertTrue(fixture.peer.id.value in fixture.pending)
        assertTrue(fixture.calls.isEmpty())
        fixture.pending.complete(fixture.peer.id.value, ownsMarker = true, admittedSession = null)
        assertEquals(listOf(fixture.peer), fixture.calls)
        assertEquals(listOf(replacement), fixture.sessions.value)
        assertTrue(fixture.pending.isEmpty())
    }

    @Test
    fun disabledMeshDefersCompletedSessionLossUntilEnabled() = scenario { fixture ->
        val first = MeshSession("first", fixture.peer)
        val replacement = MeshSession("replacement", fixture.peer)
        val release = CompletableDeferred<Unit>()
        fixture.connect = {
            if (fixture.calls.size == 1) {
                fixture.sessions.value = listOf(first)
                release.await()
                first
            } else {
                fixture.sessions.value = listOf(replacement)
                replacement
            }
        }
        fixture.start()
        fixture.enabled.value = true
        fixture.sessions.value = emptyList()
        fixture.enabled.value = false
        release.complete(Unit)
        assertEquals(listOf(fixture.peer), fixture.calls)
        assertTrue(fixture.pending.isEmpty())
        fixture.enabled.value = true
        assertEquals(listOf(fixture.peer, fixture.peer), fixture.calls)
        assertEquals(listOf(replacement), fixture.sessions.value)
    }

    @Test
    fun ownerCancellationReleasesInFlightMarkersAndStopsTheCollector() = scenario { fixture ->
        fixture.start()
        fixture.enabled.value = true
        assertEquals(listOf(fixture.peer), fixture.calls)
        assertFalse(fixture.pending.isEmpty())
        fixture.owner.cancelAndJoin()
        assertTrue(fixture.pending.isEmpty())
        fixture.sessions.value = listOf(MeshSession("unrelated", meshPeer("aaa")))
        fixture.peers.value = listOf(fixture.peer, meshPeer("zzz"))
        assertEquals(listOf(fixture.peer), fixture.calls)
    }

    private fun scenario(block: suspend (Fixture) -> Unit) = runBlocking {
        val fixture = Fixture()
        try {
            block(fixture)
        } finally {
            fixture.owner.cancelAndJoin()
        }
    }

    private class Fixture {
        val owner = SupervisorJob()
        // State changes and their collectors drain on this one thread; no network or real-time waits.
        private val scope = CoroutineScope(Dispatchers.Unconfined + owner)
        val peer = meshPeer("remote")
        val enabled = MutableStateFlow(false)
        val peers = MutableStateFlow(listOf(peer))
        val sessions = MutableStateFlow<List<P2pSession>>(emptyList())
        val pending = CliPendingConnects()
        val calls = mutableListOf<Peer>()
        var connect: suspend (Peer) -> P2pSession? = { awaitCancellation() }

        fun start() = launchCliAutoMesh(scope, enabled, peers, sessions, "local", pending) { selected ->
            calls += selected
            connect(selected)
        }
    }
}

private fun meshPeer(id: String) = Peer(PeerId(id), "Synthetic peer", Platform.UNKNOWN, emptySet())

private class MeshSession(override val id: String, override val peer: Peer) : P2pSession {
    override val state = MutableStateFlow(ConnectionState.Connected)
    override val incoming = MutableSharedFlow<P2pMessage>()
    @Deprecated("Observe pendingFileOffers")
    override val incomingFiles = MutableSharedFlow<P2pFileOffer>()
    override suspend fun close() = error("not used")
    override suspend fun send(message: P2pMessage) = error("not used")
    @Deprecated("Legacy only")
    override suspend fun sendFile(
        name: String, sizeBytes: Long, mimeType: String?, source: RawSource
    ): P2pFileTransfer = error("not used")
}
