package dev.p2pkit.sample.desktop

import dev.p2pkit.sample.diagnostics.SessionTransferKey
import java.util.concurrent.ConcurrentHashMap
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue

class TransferOfferSelectionTest {
    @Test
    fun identicalIdsAcrossSessionsRequireAnExactScopedSelector() {
        val first = SessionTransferKey("session-a", "a".repeat(32))
        val second = SessionTransferKey("session-b", first.transferId)
        val offers = ConcurrentHashMap(mapOf(first to "peer-a", second to "peer-b"))

        assertEquals(listOf(first, second), matchingOfferKeys(offers.keys, "aaaa"))
        assertEquals(listOf(first, second), matchingOfferKeys(offers.keys, first.transferId))
        assertEquals(listOf(second), matchingOfferKeys(offers.keys, second.stableId))
        assertTrue(offers.remove(second, "peer-b"))
        assertEquals(mapOf(first to "peer-a"), offers)
        assertEquals(listOf(first), matchingOfferKeys(offers.keys, "aaaa"))
    }

    @Test
    fun sessionCleanupCannotRemoveAnotherPeersOffer() {
        val first = SessionTransferKey("session-a", "same-id")
        val second = SessionTransferKey("session-b", "same-id")
        val offers = ConcurrentHashMap(mapOf(first to "peer-a", second to "peer-b"))

        setOf(first).forEach(offers::remove)

        assertEquals(mapOf(second to "peer-b"), offers)
        assertTrue(matchingOfferKeys(offers.keys, "missing").isEmpty())
    }
}
