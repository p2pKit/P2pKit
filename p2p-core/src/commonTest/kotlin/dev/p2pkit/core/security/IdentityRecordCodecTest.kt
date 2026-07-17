package dev.p2pkit.core.security

import dev.p2pkit.core.AppId
import kotlin.test.Test
import kotlin.test.assertContentEquals
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertTrue

class IdentityRecordCodecTest {
    private val namespace = IdentityNamespace(
        appId = AppId("codec-app"),
        appIdBytes = "codec-app".encodeToByteArray(),
        hash = ByteArray(32) { it.toByte() }
    )
    private val privateKey = ByteArray(32) { (it + 32).toByte() }
    private val publicKey = ByteArray(32) { (it + 96).toByte() }

    @Test
    fun p2kiEncodingIsExactlyTheFrozen104ByteLayout() {
        val pair = EncodedIdentityKeyPair(privateKey, publicKey)
        val record = IdentityKeyRecordCodec.encode(namespace, pair)

        assertEquals(104, record.size)
        assertContentEquals("P2KI".encodeToByteArray(), record.copyOfRange(0, 4))
        assertEquals(1, record[4].toInt())
        assertEquals(1, record[5].toInt())
        assertEquals(0, record[6].toInt())
        assertEquals(0, record[7].toInt())
        assertContentEquals(namespace.hashBytes(), record.copyOfRange(8, 40))
        assertContentEquals(privateKey, record.copyOfRange(40, 72))
        assertContentEquals(publicKey, record.copyOfRange(72, 104))
    }

    @Test
    fun p2kiRoundTripReturnsDefensiveKeyCopies() {
        val record = IdentityKeyRecordCodec.encode(
            namespace,
            EncodedIdentityKeyPair(privateKey, publicKey)
        )
        val decoded = IdentityKeyRecordCodec.decode(namespace, record)
        record.fill(0)

        assertContentEquals(privateKey, decoded.privateKeyBytes())
        assertContentEquals(publicKey, decoded.publicKeyBytes())

        val exposed = decoded.privateKeyBytes()
        exposed.fill(0)
        assertContentEquals(privateKey, decoded.privateKeyBytes())
    }

    @Test
    fun p2kiStrictlyRejectsEveryStructuralFieldAndLength() {
        val valid = IdentityKeyRecordCodec.encode(
            namespace,
            EncodedIdentityKeyPair(privateKey, publicKey)
        )
        assertCorrupt(valid.copyOf(103))
        assertCorrupt(valid + 0)
        assertCorrupt(valid.copyOf().also { it[0] = 'X'.code.toByte() })
        assertCorrupt(valid.copyOf().also { it[4] = 2 })
        assertCorrupt(valid.copyOf().also { it[5] = 2 })
        assertCorrupt(valid.copyOf().also { it[6] = 1 })
        assertCorrupt(valid.copyOf().also { it[7] = 1 })
        assertCorrupt(valid.copyOf().also { it[8] = (it[8].toInt() xor 1).toByte() })
    }

    @Test
    fun committedMarkerIsExactly72BytesAndStrict() {
        val digest = ByteArray(32) { (255 - it).toByte() }
        val marker = IdentityStateMarkerCodec.encodeCommitted(namespace, digest)

        assertEquals(72, marker.size)
        assertContentEquals("P2KM".encodeToByteArray(), marker.copyOfRange(0, 4))
        assertEquals(1, marker[4].toInt())
        assertEquals(1, marker[5].toInt())
        assertEquals(0, marker[6].toInt())
        assertEquals(0, marker[7].toInt())
        assertContentEquals(namespace.hashBytes(), marker.copyOfRange(8, 40))
        assertContentEquals(digest, IdentityStateMarkerCodec.decodeCommitted(namespace, marker))

        assertMarkerCorrupt { IdentityStateMarkerCodec.decodeCommitted(namespace, marker.copyOf(71)) }
        assertMarkerCorrupt {
            IdentityStateMarkerCodec.decodeCommitted(namespace, marker.copyOf().also { it[5] = 2 })
        }
        val changedDigest = IdentityStateMarkerCodec.decodeCommitted(
            namespace,
            marker.copyOf().also { it[40] = 1 }
        )
        // Fingerprint bytes are data, not structure; the platform compares
        // the returned value with the provider-backed derivation callback.
        assertTrue(changedDigest[0].toInt() == 1)
    }

    @Test
    fun resetMarkerIsExactly40BytesAndStrict() {
        val marker = IdentityStateMarkerCodec.encodeResetPending(namespace)
        assertEquals(40, marker.size)
        assertContentEquals("P2KR".encodeToByteArray(), marker.copyOfRange(0, 4))
        assertEquals(1, marker[4].toInt())
        assertEquals(1, marker[5].toInt())
        assertEquals(0, marker[6].toInt())
        assertEquals(0, marker[7].toInt())
        assertContentEquals(namespace.hashBytes(), marker.copyOfRange(8, 40))
        IdentityStateMarkerCodec.decodeResetPending(namespace, marker)

        assertMarkerCorrupt { IdentityStateMarkerCodec.decodeResetPending(namespace, marker + 0) }
        assertMarkerCorrupt {
            IdentityStateMarkerCodec.decodeResetPending(namespace, marker.copyOf().also { it[4] = 2 })
        }
        assertMarkerCorrupt {
            IdentityStateMarkerCodec.decodeResetPending(namespace, marker.copyOf().also { it[39] = 1 })
        }
    }

    private fun assertCorrupt(record: ByteArray) {
        assertFailsWith<IdentityRecordCorruptException> {
            IdentityKeyRecordCodec.decode(namespace, record)
        }
    }

    private fun assertMarkerCorrupt(block: () -> Unit) {
        assertFailsWith<IdentityRecordCorruptException>(block = block)
    }
}
