package dev.p2pkit.core.internal

import dev.p2pkit.core.PeerId
import dev.p2pkit.core.protocol.HelloPayload
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
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

    @Test
    fun persistedPeerIdParserPreservesLegacyWhitespaceButEnforcesWireBounds() {
        assertEquals(PeerId("stored-id"), parsePersistedPeerId(" \n stored-id\t "))
        assertEquals(
            PeerId("x".repeat(HelloPayload.MAX_FIELD_LEN)),
            parsePersistedPeerId("x".repeat(HelloPayload.MAX_FIELD_LEN))
        )

        listOf(
            " ",
            "x".repeat(HelloPayload.MAX_FIELD_LEN + 1),
            "unsafe\u202Epeer-id",
            "malformed-\uD800",
            "x".repeat(MAX_PERSISTED_PEER_ID_BYTES + 1)
        ).forEach { invalid ->
            assertFailsWith<IllegalArgumentException> { parsePersistedPeerId(invalid) }
        }
    }

    @Test
    fun persistedPeerIdByteDecoderRejectsMalformedUtf8AndOversizedRecords() {
        assertFailsWith<IllegalArgumentException> {
            decodePersistedPeerId(byteArrayOf(0xC3.toByte(), 0x28))
        }
        assertFailsWith<IllegalArgumentException> {
            decodePersistedPeerId(ByteArray(MAX_PERSISTED_PEER_ID_BYTES + 1) { 'x'.code.toByte() })
        }
    }
}
