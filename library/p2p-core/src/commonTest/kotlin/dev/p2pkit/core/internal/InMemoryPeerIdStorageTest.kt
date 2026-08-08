package dev.p2pkit.core.internal

import dev.p2pkit.core.PeerId
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertNotEquals

class InMemoryPeerIdStorageTest {

    @Test
    fun loadOrGenerateReturnsTheSameIdAcrossRepeatedCalls() {
        val storage = InMemoryPeerIdStorage()
        val first = storage.loadOrGenerate()
        val second = storage.loadOrGenerate()
        assertEquals(first, second, "InMemoryPeerIdStorage must return a stable id per instance")
    }

    @Test
    fun differentInstancesGenerateDifferentIds() {
        val a = InMemoryPeerIdStorage()
        val b = InMemoryPeerIdStorage()
        assertNotEquals(a.loadOrGenerate(), b.loadOrGenerate())
    }

    @Test
    fun seededInstanceReturnsTheSeed() {
        val seeded = InMemoryPeerIdStorage(seed = PeerId("seeded-id"))
        assertEquals(PeerId("seeded-id"), seeded.loadOrGenerate())
    }
}
