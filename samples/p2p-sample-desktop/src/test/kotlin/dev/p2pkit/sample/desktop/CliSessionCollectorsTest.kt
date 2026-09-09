package dev.p2pkit.sample.desktop

import dev.p2pkit.core.ConnectionState
import dev.p2pkit.core.P2pMessage
import dev.p2pkit.core.P2pSession
import dev.p2pkit.core.Peer
import dev.p2pkit.core.PeerId
import dev.p2pkit.core.Platform
import dev.p2pkit.core.transfer.P2pFileOffer
import dev.p2pkit.core.transfer.P2pFileTransfer
import dev.p2pkit.sample.diagnostics.SessionTransferKey
import java.nio.file.Files
import java.util.ArrayDeque
import java.util.concurrent.ConcurrentHashMap
import kotlinx.coroutines.CoroutineDispatcher
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.runBlocking
import kotlinx.io.RawSink
import kotlinx.io.RawSource
import kotlin.coroutines.CoroutineContext
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertIs
import kotlin.test.assertNotNull
import kotlin.test.assertSame
import kotlin.test.assertTrue

class CliSessionCollectorsTest {
    @Test
    fun terminalStateRetiresCollectorsAndOffersAcrossDuplicateAndReconnect() = withCollectorFixture { fixture ->
        for (terminal in listOf(ConnectionState.Closed, ConnectionState.Failed)) {
            val session = CollectorSession("session-$terminal")
            fixture.register(session)
            assertEquals(listOf(1, 1, 1), session.subscriptionCounts())
            assertSame(session.offer, fixture.offers[session.offerKey])

            fixture.register(session)
            session.state.value = ConnectionState.Reconnecting
            session.state.value = ConnectionState.Connected
            assertEquals(listOf(1, 1, 1), session.subscriptionCounts())
            assertSame(session, fixture.sessions[session.peer.id.value])
            assertEquals(setOf(session.id), fixture.wiredIds)

            session.state.value = terminal

            assertEquals(listOf(0, 0, 0), session.subscriptionCounts())
            assertTrue(fixture.sessions.isEmpty())
            assertTrue(fixture.wiredIds.isEmpty())
            assertTrue(
                fixture.offers.isEmpty(), "Collector finally must remove offers even without an empty SDK snapshot"
            )
            assertTrue(fixture.owner.isActive, "A terminal session must not cancel the CLI")
            assertTrue(fixture.owner.children.none(), "No registration child may survive terminal cleanup")
        }
    }

    @Test
    fun oldRetirementAndLateAcquisitionPreserveReplacementAndItsSameIdOffer() = withCollectorFixture { fixture ->
        val old = CollectorSession("old-session")
        val replacement = CollectorSession("replacement-session", peer = old.peer)
        fixture.register(old)
        fixture.register(replacement)
        val replacementConnection = assertNotNull(CliDiagnostics.connectionIdFor(replacement.peer.id.value))
        assertEquals(setOf(old.offerKey, replacement.offerKey), fixture.offers.keys)
        assertEquals(old.offer.id, replacement.offer.id)

        fixture.register(old)
        assertSame(replacement, fixture.sessions[old.peer.id.value], "A duplicate old wiring is not new ownership")
        old.state.value = ConnectionState.Failed

        assertEquals(listOf(0, 0, 0), old.subscriptionCounts())
        assertEquals(listOf(1, 1, 1), replacement.subscriptionCounts())
        assertSame(replacement, fixture.sessions[old.peer.id.value])
        assertEquals(setOf(replacement.id), fixture.wiredIds)
        assertEquals(setOf(replacement.offerKey), fixture.offers.keys)
        assertSame(replacement.offer, fixture.offers[replacement.offerKey])
        assertEquals(replacementConnection, CliDiagnostics.connectionIdFor(old.peer.id.value))

        fixture.register(old)
        assertSame(
            replacement, fixture.sessions[old.peer.id.value], "An already-terminal acquisition is not new ownership"
        )
        assertEquals(listOf(0, 0, 0), old.subscriptionCounts())
        assertEquals(listOf(1, 1, 1), replacement.subscriptionCounts())
        assertEquals(replacementConnection, CliDiagnostics.connectionIdFor(old.peer.id.value))
        assertEquals(1, fixture.owner.children.count())
    }

    @Test
    fun alreadyTerminalRegistrationNeverPublishesOrSubscribes() = withCollectorFixture { fixture ->
        for (terminal in listOf(ConnectionState.Closed, ConnectionState.Failed)) {
            val session = CollectorSession("initial-$terminal", initialState = terminal)
            fixture.register(session)
            assertEquals(listOf(0, 0, 0), session.subscriptionCounts())
            assertTrue(fixture.sessions.isEmpty())
            assertTrue(fixture.wiredIds.isEmpty())
            assertTrue(fixture.offers.isEmpty())
            assertTrue(fixture.owner.children.none())
            assertTrue(fixture.owner.isActive)
        }
    }

    @Test
    fun outerCancellationRetiresActiveAndNotYetDispatchedRegistrations() {
        val dispatcher = CollectorQueueDispatcher()
        withCollectorFixture(dispatcher) { fixture ->
            val active = CollectorSession("active")
            fixture.register(active)
            dispatcher.runUntilIdle()
            assertEquals(listOf(1, 1, 1), active.subscriptionCounts())
            assertSame(active.offer, fixture.offers[active.offerKey])

            val queued = CollectorSession("queued")
            fixture.register(queued)
            assertEquals(0, queued.incoming.subscriptionCount.value)
            assertEquals(0, queued.pendingFileOffers.subscriptionCount.value)
            assertTrue(dispatcher.hasTasks, "The second registration's subscribers have not run")
            fixture.owner.cancel()
            dispatcher.runUntilIdle()

            assertEquals(listOf(0, 0, 0), active.subscriptionCounts())
            assertEquals(listOf(0, 0, 0), queued.subscriptionCounts())
            assertTrue(fixture.sessions.isEmpty())
            assertTrue(fixture.wiredIds.isEmpty())
            assertTrue(fixture.offers.isEmpty())
            assertTrue(fixture.owner.isCompleted)
            assertTrue(fixture.owner.children.none())

            val tooLate = CollectorSession("cancelled-outer")
            fixture.register(tooLate)
            dispatcher.runUntilIdle()
            assertEquals(listOf(0, 0, 0), tooLate.subscriptionCounts())
            assertTrue(fixture.sessions.isEmpty())
            assertTrue(fixture.wiredIds.isEmpty())
            assertTrue(fixture.offers.isEmpty())
        }
    }
}

private fun withCollectorFixture(
    dispatcher: CoroutineDispatcher = Dispatchers.Unconfined,
    block: (CollectorFixture) -> Unit,
): Unit = runBlocking {
    val home = Files.createTempDirectory("p2pkit-cli-collectors-test").toFile()
    val owner = SupervisorJob()
    val previousLocalPeerId = CliDiagnostics.localPeerId
    try {
        val options = assertIs<CliParseResult.Success>(parseCliOptions(emptyArray())).options
        CliDiagnostics.configure(options, home)
        CliDiagnostics.localPeerId = "synthetic-local-collector-peer"
        block(CollectorFixture(CoroutineScope(dispatcher + owner), owner))
    } finally {
        try {
            owner.cancel()
            if (dispatcher is CollectorQueueDispatcher) dispatcher.runUntilIdle()
            owner.join()
        } finally {
            try {
                CliDiagnostics.close()
            } finally {
                CliDiagnostics.localPeerId = previousLocalPeerId
                home.deleteRecursively()
            }
        }
    }
}

private class CollectorFixture(val scope: CoroutineScope, val owner: Job) {
    val sessions = ConcurrentHashMap<String, P2pSession>()
    val wiredIds: MutableSet<String> = ConcurrentHashMap.newKeySet()
    val offers = ConcurrentHashMap<SessionTransferKey, P2pFileOffer>()

    fun register(session: P2pSession) {
        registerSession(session, scope, sessions, wiredIds, offers)
    }
}

private class CollectorQueueDispatcher : CoroutineDispatcher() {
    private val tasks = ArrayDeque<Runnable>()
    val hasTasks: Boolean get() = tasks.isNotEmpty()

    override fun dispatch(context: CoroutineContext, block: Runnable) {
        tasks.addLast(block)
    }

    fun runUntilIdle() {
        var steps = 0
        while (tasks.isNotEmpty()) {
            check(++steps <= 100) { "Synthetic collector dispatcher did not settle" }
            tasks.removeFirst().run()
        }
    }
}

private class CollectorSession(
    override val id: String,
    override val peer: Peer = Peer(PeerId("synthetic-$id"), "Synthetic Peer", Platform.UNKNOWN, emptySet()),
    initialState: ConnectionState = ConnectionState.Connected,
) : P2pSession {
    override val state = MutableStateFlow(initialState)
    override val incoming = MutableSharedFlow<P2pMessage>()
    val offer = CollectorOffer(peer)
    val offerKey = SessionTransferKey(id, offer.id)
    override val pendingFileOffers = MutableStateFlow<List<P2pFileOffer>>(listOf(offer))

    @Deprecated("Observe pendingFileOffers")
    override val incomingFiles = MutableSharedFlow<P2pFileOffer>()

    fun subscriptionCounts(): List<Int> = listOf(
        incoming.subscriptionCount.value,
        pendingFileOffers.subscriptionCount.value,
        state.subscriptionCount.value
    )

    override suspend fun send(message: P2pMessage): Unit = error("Not used by collector test")
    override suspend fun close(): Unit = error("Not used by collector test")

    @Deprecated("Legacy only")
    override suspend fun sendFile(
        name: String,
        sizeBytes: Long,
        mimeType: String?,
        source: RawSource,
    ): P2pFileTransfer = error("Not used by collector test")
}

private class CollectorOffer(override val peer: Peer) : P2pFileOffer {
    override val id = "a".repeat(32)
    override val name = "synthetic.txt"
    override val sizeBytes = 1L
    override val mimeType: String? = null

    @Deprecated("Legacy flush-only transfer")
    override suspend fun accept(sink: RawSink): P2pFileTransfer = error("Not used by collector test")

    override suspend fun reject(reason: String?): Unit = error("Not used by collector test")
}
