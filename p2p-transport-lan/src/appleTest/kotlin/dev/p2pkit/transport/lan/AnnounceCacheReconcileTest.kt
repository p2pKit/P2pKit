package dev.p2pkit.transport.lan

import dev.p2pkit.core.Peer
import dev.p2pkit.core.PeerId
import dev.p2pkit.core.Platform
import dev.p2pkit.core.TransportKind
import dev.p2pkit.core.transport.InternalPeer
import dev.p2pkit.core.transport.TransportHint
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue

/**
 * AUDIT-2026-06 (#8): unit tests for [reconcileAnnounceCache], the pure
 * per-tick decision logic behind the iOS ghost-peer fix.
 *
 * Scenario being pinned: `refresh()` / the rebind hooks cancel + recreate
 * the NWBrowser without any `result_removed` callbacks for peers that
 * vanished while the browser was being replaced. Before the fix the
 * re-announce loop re-emitted every cached entry unconditionally, so such a
 * ghost kept refreshing its PeerRegistry lastSeen forever. The reconcile
 * step announces only entries confirmed by the CURRENT browser generation,
 * keeps stale-generation entries silently for a grace window (giving the
 * replacement browser time to re-add live peers), and prunes + reports as
 * lost anything the new browser never re-confirms.
 *
 * The transport-side wiring (generation stamping in `emitPeer`, increment
 * in `createBrowserLocked`, Lost emission via `emitLostById`) is exercised
 * by the existing loopback/lifecycle suites; these tests pin the decision
 * table itself.
 */
class AnnounceCacheReconcileTest {

    private fun peer(pid: String): InternalPeer = InternalPeer(
        publicPeer = Peer(
            id = PeerId(pid),
            name = "peer-$pid",
            platform = Platform.UNKNOWN,
            supportedTransports = setOf(TransportKind.LAN)
        ),
        transportHints = listOf(TransportHint(type = TransportKind.LAN))
    )

    @Test
    fun currentGenerationEntryIsAnnouncedAndRetained() {
        val p = peer("alive")
        val cache = mapOf("alive" to AnnounceEntry(p, lastConfirmedGeneration = 3))

        val result = reconcileAnnounceCache(cache, currentGeneration = 3, graceTicks = 2)

        assertEquals(listOf(p), result.announce)
        assertEquals(cache, result.updatedCache)
        assertTrue(result.lostPeerIds.isEmpty())
    }

    @Test
    fun staleEntryWithinGraceIsKeptButNotAnnounced() {
        // Browser was just replaced (gen 2 -> 3); the peer hasn't been
        // re-confirmed yet. It must NOT be announced (that would refresh its
        // PeerRegistry lastSeen — the ghost bug) but must survive this tick.
        val p = peer("pending")
        val cache = mapOf("pending" to AnnounceEntry(p, lastConfirmedGeneration = 2))

        val result = reconcileAnnounceCache(cache, currentGeneration = 3, graceTicks = 2)

        assertTrue(result.announce.isEmpty())
        assertTrue(result.lostPeerIds.isEmpty())
        assertEquals(1, result.updatedCache.getValue("pending").staleTicks)
        assertEquals(2, result.updatedCache.getValue("pending").lastConfirmedGeneration)
    }

    @Test
    fun staleEntryIsPrunedAndReportedLostAfterGraceTicks() {
        // Two consecutive stale ticks with graceTicks=2 — the ghost is
        // pruned on the second tick (~10 s at the 5 s announce cadence).
        val p = peer("ghost")
        var cache = mapOf("ghost" to AnnounceEntry(p, lastConfirmedGeneration = 1))

        val tick1 = reconcileAnnounceCache(cache, currentGeneration = 2, graceTicks = 2)
        assertTrue(tick1.lostPeerIds.isEmpty())
        cache = tick1.updatedCache

        val tick2 = reconcileAnnounceCache(cache, currentGeneration = 2, graceTicks = 2)
        assertEquals(listOf("ghost"), tick2.lostPeerIds)
        assertTrue(tick2.announce.isEmpty())
        assertTrue("ghost" !in tick2.updatedCache)
    }

    @Test
    fun reconfirmedEntrySurvivesBrowserReplacementAndResetsStaleCounter() {
        // A live peer: went stale for one tick after the browser swap, then
        // the new browser re-added it (emitPeer re-stamps with the current
        // generation and a zeroed counter). It must be announced again and
        // carry no stale history forward.
        val p = peer("alive")
        var cache = mapOf("alive" to AnnounceEntry(p, lastConfirmedGeneration = 1))

        val tick1 = reconcileAnnounceCache(cache, currentGeneration = 2, graceTicks = 2)
        assertEquals(1, tick1.updatedCache.getValue("alive").staleTicks)

        // Simulate the emitPeer re-stamp on the new browser's result_added.
        cache = tick1.updatedCache + ("alive" to AnnounceEntry(p, lastConfirmedGeneration = 2))

        val tick2 = reconcileAnnounceCache(cache, currentGeneration = 2, graceTicks = 2)
        assertEquals(listOf(p), tick2.announce)
        assertTrue(tick2.lostPeerIds.isEmpty())
        assertEquals(0, tick2.updatedCache.getValue("alive").staleTicks)
    }

    @Test
    fun staleCounterCarriedAcrossFurtherGenerationBumpsIsNotReset() {
        // Rapid refresh() churn (the ~3 s Reconnecting cadence) keeps
        // bumping the generation. An entry that is never re-confirmed must
        // keep advancing toward the prune — a newer stale generation is not
        // a fresher signal.
        val p = peer("ghost")
        var cache = mapOf("ghost" to AnnounceEntry(p, lastConfirmedGeneration = 5))

        val tick1 = reconcileAnnounceCache(cache, currentGeneration = 6, graceTicks = 3)
        cache = tick1.updatedCache
        val tick2 = reconcileAnnounceCache(cache, currentGeneration = 7, graceTicks = 3)
        cache = tick2.updatedCache
        assertEquals(2, cache.getValue("ghost").staleTicks)

        val tick3 = reconcileAnnounceCache(cache, currentGeneration = 8, graceTicks = 3)
        assertEquals(listOf("ghost"), tick3.lostPeerIds)
    }

    @Test
    fun mixedCachePartitionsIndependently() {
        val alive = peer("alive")
        val pending = peer("pending")
        val ghost = peer("ghost")
        val cache = mapOf(
            "alive" to AnnounceEntry(alive, lastConfirmedGeneration = 4),
            "pending" to AnnounceEntry(pending, lastConfirmedGeneration = 3),
            "ghost" to AnnounceEntry(ghost, lastConfirmedGeneration = 2, staleTicks = 1)
        )

        val result = reconcileAnnounceCache(cache, currentGeneration = 4, graceTicks = 2)

        assertEquals(listOf(alive), result.announce)
        assertEquals(listOf("ghost"), result.lostPeerIds)
        assertEquals(setOf("alive", "pending"), result.updatedCache.keys)
        assertEquals(1, result.updatedCache.getValue("pending").staleTicks)
    }

    @Test
    fun emptyCacheIsANoOp() {
        val result = reconcileAnnounceCache(emptyMap(), currentGeneration = 9, graceTicks = 2)
        assertTrue(result.announce.isEmpty())
        assertTrue(result.updatedCache.isEmpty())
        assertTrue(result.lostPeerIds.isEmpty())
    }
}
