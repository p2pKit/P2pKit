package dev.p2pkit.sample.diagnostics

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertNull

class SessionTransferListTest {
    @Test
    fun consentCancellationLateUpdatesAndCleanupUseTheExactSessionOwner() {
        val old = SessionTransferKey("old-session", "same-id")
        val replacement = SessionTransferKey("new-session", "same-id")
        val first = Handle()
        val second = Handle()
        val rows = mutableListOf(Row(old, first), Row(replacement, second))
        val offers = rows.toMutableList()
        val rowState = SessionTransferList(rows) { it.key }
        val pending = SessionTransferList(offers) { it.key }

        // These are the production Android/Desktop consent and cancel selectors.
        pending.take(old)?.handle?.accept()
        assertNull(pending.take(old), "a repeated consent click cannot act again")
        pending.take(replacement)?.handle?.reject()
        rowState[old]?.handle?.cancel()
        assertEquals(listOf("accept", "cancel"), first.actions)
        assertEquals(listOf("reject"), second.actions)
        assertEquals(2, rows.size)

        rowState.update(replacement) { it.copy(bytes = 20, digest = "new") }
        rowState.update(old) { it.copy(bytes = 10, digest = "late-old", terminal = true) }
        assertEquals(20, rowState[replacement]?.bytes)
        assertEquals("new", rowState[replacement]?.digest)
        assertEquals(false, rowState[replacement]?.terminal)
        rowState.remove(old.sessionId, setOf(old.transferId))
        rowState.update(old) { error("removed old row must not update replacement") }
        assertEquals(listOf(replacement), rows.map { it.key })

        offers.addAll(listOf(Row(old, first), Row(replacement, second)))
        pending.remove(old.sessionId, setOf(old.transferId))
        assertEquals(listOf(replacement), offers.map { it.key })
    }

    private class Handle {
        val actions = mutableListOf<String>()
        fun accept() { actions += "accept" }
        fun reject() { actions += "reject" }
        fun cancel() { actions += "cancel" }
    }

    private data class Row(
        val key: SessionTransferKey,
        val handle: Handle,
        val bytes: Int = 0,
        val digest: String? = null,
        val terminal: Boolean = false
    )
}
