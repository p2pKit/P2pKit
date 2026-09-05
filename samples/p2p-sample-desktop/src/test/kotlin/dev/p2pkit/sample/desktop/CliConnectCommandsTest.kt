package dev.p2pkit.sample.desktop

import dev.p2pkit.core.AppId
import dev.p2pkit.core.ConnectionState
import dev.p2pkit.core.P2pError
import dev.p2pkit.core.P2pKit
import dev.p2pkit.core.P2pMessage
import dev.p2pkit.core.P2pSession
import dev.p2pkit.core.Peer
import dev.p2pkit.core.PeerFingerprint
import dev.p2pkit.core.PeerId
import dev.p2pkit.core.PeerPairingQr
import dev.p2pkit.core.Platform
import dev.p2pkit.core.dsl.jvmSecureIdentityStore
import dev.p2pkit.core.transfer.P2pFileTransfer
import dev.p2pkit.core.transfer.P2pFileOffer
import dev.p2pkit.transport.lan.lan
import java.util.concurrent.ConcurrentHashMap
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Job
import kotlinx.coroutines.NonCancellable
import kotlinx.coroutines.awaitCancellation
import kotlinx.coroutines.cancelAndJoin
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withContext
import kotlinx.coroutines.withTimeout
import kotlinx.io.RawSource
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertNotNull
import kotlin.test.assertNull
import kotlin.test.assertSame
import kotlin.test.assertTrue

/** Real REPL routing, synthetic discovered-peer SDK boundary (no manual stored-pin shortcut). */
class CliConnectCommandsTest {
    @Test
    fun pendingUnpinnedAttemptCannotDiscardAWrongPinOrLoseItsPendingMarker() = scenario { fixture ->
        val entered = CompletableDeferred<Unit>()
        val release = CompletableDeferred<Unit>()
        fixture.unpinned = {
            entered.complete(Unit)
            release.await()
            fixture.session
        }
        val commands = fixture.commands(this)
        val unpinned = assertNotNull(commands.execute("connect", "receiver"))
        entered.await()
        assertTrue(fixture.peer.id.value in fixture.pending)
        assertNull(commands.execute("connect", "receiver"))

        val pinned = assertNotNull(commands.execute("connect-pinned", "receiver ${fixture.wrongQr}"))
        pinned.join()
        assertEquals(listOf(null, fixture.wrongFingerprint), fixture.calls)
        assertEquals(1, fixture.errors.size)
        assertTrue(fixture.errors.single().contains("AuthenticatedIdentityMismatch"))
        assertTrue(fixture.connected.isEmpty())
        assertFalse(fixture.output.any { it.startsWith("connected to") })
        assertTrue(fixture.peer.id.value in fixture.pending, "a pinned waiter does not own the unpinned marker")
        assertNull(commands.execute("connect", "receiver"))

        release.complete(Unit)
        unpinned.join()
        assertEquals(listOf(fixture.session), fixture.connected)
        assertTrue(fixture.pending.isEmpty())
        assertFalse((fixture.output + fixture.errors).any { fixture.wrongQr in it })
    }

    @Test
    fun existingDiscoveredSessionStillRoutesBothCorrectAndWrongPinsToTheExplicitOverload() = scenario { fixture ->
        fixture.sessions[fixture.peer.id.value] = fixture.session
        val commands = fixture.commands(this)
        assertNull(commands.execute("connect", "receiver"))
        assertNotNull(commands.execute("connect-pinned", "receiver ${fixture.qr}")).join()
        assertNotNull(commands.execute("connect-pinned", "receiver ${fixture.wrongQr}")).join()
        assertEquals(listOf<PeerFingerprint?>(fixture.fingerprint, fixture.wrongFingerprint), fixture.calls)
        assertEquals(listOf(fixture.session), fixture.connected)
        assertEquals(1, fixture.errors.size)
        assertTrue(fixture.errors.single().contains("AuthenticatedIdentityMismatch"))
        assertSame(fixture.session, fixture.sessions[fixture.peer.id.value])
        assertTrue(fixture.pending.isEmpty())
    }

    @Test
    fun pinnedSuccessAfterTheOwnerFinishesCannotRemoveASuccessorPendingMarker() = scenario { fixture ->
        val unpinnedEntered = CompletableDeferred<Unit>()
        val releaseUnpinned = CompletableDeferred<Unit>()
        val pinnedEntered = CompletableDeferred<Unit>()
        val releasePinned = CompletableDeferred<Unit>()
        fixture.unpinned = {
            unpinnedEntered.complete(Unit)
            releaseUnpinned.await()
            fixture.session
        }
        fixture.pinned = { expected ->
            assertEquals(fixture.fingerprint, expected)
            pinnedEntered.complete(Unit)
            releasePinned.await()
            fixture.session
        }
        val commands = fixture.commands(this)
        val unpinned = assertNotNull(commands.execute("connect", "receiver"))
        unpinnedEntered.await()
        val pinned = assertNotNull(commands.execute("connect-pinned", "receiver ${fixture.qr}"))
        pinnedEntered.await()
        releaseUnpinned.complete(Unit)
        unpinned.join()
        assertTrue(fixture.pending.isEmpty())
        // Models the shared auto-mesh guard acquiring a new marker while the
        // previous pinned caller is still resuming. It must retain ownership.
        assertTrue(fixture.pending.add(fixture.peer.id.value))
        releasePinned.complete(Unit)
        pinned.join()
        assertEquals(listOf(null, fixture.fingerprint), fixture.calls)
        assertEquals(listOf(fixture.session, fixture.session), fixture.connected)
        assertTrue(fixture.errors.isEmpty())
        assertTrue(fixture.peer.id.value in fixture.pending)
        fixture.pending.remove(fixture.peer.id.value)
    }

    @Test
    fun cancellationIsNotReportedAsConnectFailureAndReleasesTheOwnedMarker() = scenario { fixture ->
        val entered = CompletableDeferred<Unit>()
        fixture.pinned = {
            entered.complete(Unit)
            awaitCancellation()
        }
        val job = assertNotNull(fixture.commands(this).execute("connect-pinned", "receiver ${fixture.qr}"))
        entered.await()
        job.cancelAndJoin()
        assertTrue(job.isCancelled)
        assertTrue(fixture.connected.isEmpty())
        assertTrue(fixture.errors.isEmpty())
        assertTrue(fixture.pending.isEmpty())
    }

    @Test
    fun cancellationBeforeDispatchReleasesOnlyTheMarkerOwnedByThatCommand() = scenario { fixture ->
        val cancelledScope = CoroutineScope(Job().also { it.cancel() })
        val commands = fixture.commands(cancelledScope)
        assertNotNull(commands.execute("connect-pinned", "receiver ${fixture.qr}")).join()
        assertTrue(fixture.pending.isEmpty())
        assertTrue(fixture.pending.add(fixture.peer.id.value))
        assertNotNull(commands.execute("connect-pinned", "receiver ${fixture.qr}")).join()
        assertTrue(fixture.peer.id.value in fixture.pending)
        assertTrue(fixture.calls.isEmpty())
        assertTrue(fixture.connected.isEmpty())
        assertTrue(fixture.errors.isEmpty())
        fixture.pending.remove(fixture.peer.id.value)
    }

    @Test
    fun invalidCommandQrNeverConnectsOrEchoesOperatorInput() = scenario { fixture ->
        val commands = fixture.commands(this)
        assertNull(commands.execute("connect-pinned", "receiver ${fixture.qr} extra"))
        assertTrue(fixture.calls.isEmpty())
        assertTrue(fixture.pending.isEmpty())
        assertTrue(fixture.connected.isEmpty())
        assertFalse(fixture.output.any { fixture.qr in it })
    }

    private fun scenario(block: suspend CoroutineScope.(Fixture) -> Unit): Unit = runBlocking {
        withTimeout(5_000) {
            val fixture = Fixture()
            try {
                block(fixture)
            } finally {
                withContext(NonCancellable) { fixture.base.stop() }
            }
        }
    }

    private class Fixture {
        val base = P2pKit.create {
            appId = AppId("synthetic.cli-routing")
            deviceName = "Synthetic CLI fixture"
            jvmSecureIdentityStore(DevelopmentOnlyInMemorySecureIdentityStore())
            transports { lan() }
        }
        val fingerprint = assertNotNull(base.localFingerprint)
        val qr = assertNotNull(base.localPairingQr)
        private val alternateFirstDigit = if (fingerprint.value[5] == 'a') 'b' else 'a'
        val wrongFingerprint = PeerFingerprint("p2f1-$alternateFirstDigit${fingerprint.value.substring(6)}")
        val wrongQr = PeerPairingQr(PeerPairingQr.parse(qr).appBinding, wrongFingerprint).encode()
        val peer = Peer(PeerId("synthetic-discovered"), "receiver", Platform.UNKNOWN, emptySet())
        val session = object : P2pSession {
            override val id = "synthetic-session"
            override val peer = this@Fixture.peer
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
        val sessions = ConcurrentHashMap<String, P2pSession>()
        val pending: MutableSet<String> = ConcurrentHashMap.newKeySet()
        val calls = mutableListOf<PeerFingerprint?>()
        val connected = mutableListOf<P2pSession>()
        val output = mutableListOf<String>()
        val errors = mutableListOf<String>()
        var unpinned: suspend () -> P2pSession = { session }
        var pinned: suspend (PeerFingerprint) -> P2pSession = { expected ->
            if (expected != fingerprint) throw P2pError.AuthenticatedIdentityMismatch("synthetic mismatch")
            session
        }
        private val kit = object : P2pKit by base {
            override val peers = MutableStateFlow(listOf(peer))
            override suspend fun connect(peer: Peer): P2pSession {
                assertSame(this@Fixture.peer, peer)
                calls += null
                return unpinned()
            }
            override suspend fun connect(peer: Peer, expectedFingerprint: PeerFingerprint): P2pSession {
                assertSame(this@Fixture.peer, peer)
                calls += expectedFingerprint
                return pinned(expectedFingerprint)
            }
        }

        fun commands(scope: CoroutineScope) = CliConnectCommands(
            kit = kit, scope = scope, sessions = sessions, pendingConnects = pending,
            onAttempt = {}, onConnected = { connected += it; sessions[it.peer.id.value] = it },
            output = output::add, error = errors::add
        )
    }
}
