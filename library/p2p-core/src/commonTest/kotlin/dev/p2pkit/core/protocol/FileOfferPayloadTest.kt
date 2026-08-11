package dev.p2pkit.core.protocol

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertFailsWith
import kotlin.test.assertNull
import kotlin.test.assertTrue

class FileOfferPayloadTest {

    @Test
    fun roundTripWithMime() {
        val payload = FileOfferPayload(
            name = "report.pdf",
            sizeBytes = 1_234_567L,
            mimeType = "application/pdf"
        )
        val decoded = FileOfferPayload.decode(FileOfferPayload.encode(payload))
        assertEquals(payload, decoded)
    }

    @Test
    fun roundTripWithoutMime() {
        val payload = FileOfferPayload(name = "blob.bin", sizeBytes = 0L, mimeType = null)
        val decoded = FileOfferPayload.decode(FileOfferPayload.encode(payload))
        assertEquals(payload, decoded)
        assertNull(decoded.mimeType)
    }

    @Test
    fun wireJsonWithMimeRemainsCanonical() {
        val encoded = FileOfferPayload.encode(
            FileOfferPayload(
                name = "report.pdf",
                sizeBytes = 1_234_567L,
                mimeType = "application/pdf"
            )
        ).decodeToString()

        assertEquals(
            "{\"name\":\"report.pdf\",\"sizeBytes\":1234567,\"mimeType\":\"application/pdf\"}",
            encoded
        )
    }

    @Test
    fun wireJsonWithoutMimeRemainsCanonical() {
        val encoded = FileOfferPayload.encode(
            FileOfferPayload(name = "blob.bin", sizeBytes = 0L)
        ).decodeToString()

        assertEquals("{\"name\":\"blob.bin\",\"sizeBytes\":0,\"mimeType\":null}", encoded)
    }

    @Test
    fun unicodeNameSurvives() {
        val payload = FileOfferPayload(
            name = "résumé 🇸🇪.docx",
            sizeBytes = 42L,
            mimeType = "application/vnd.openxmlformats"
        )
        val decoded = FileOfferPayload.decode(FileOfferPayload.encode(payload))
        assertEquals(payload, decoded)
    }

    @Test
    fun outboundFieldsAreValidatedBeforeSerialization() {
        val invalid = listOf(
            FileOfferPayload(name = "", sizeBytes = 1),
            FileOfferPayload(name = "..", sizeBytes = 1),
            FileOfferPayload(name = "dir/file", sizeBytes = 1),
            FileOfferPayload(name = "dir\\file", sizeBytes = 1),
            FileOfferPayload(name = "bad\u0000name", sizeBytes = 1),
            FileOfferPayload(name = "ok", sizeBytes = -1),
            FileOfferPayload(name = "ok", sizeBytes = 1, mimeType = "bad\nmime")
        )

        invalid.forEach { payload ->
            assertFailsWith<IllegalArgumentException>(payload.toString()) {
                FileOfferPayload.encode(payload)
            }
        }
    }

    @Test
    fun malformedUtf8IsRejectedWithoutReplacement() {
        val invalid = byteArrayOf(0x7B, 0x22, 0xC3.toByte(), 0x28, 0x22, 0x7D)

        val failure = assertFailsWith<IllegalArgumentException> { FileOfferPayload.decode(invalid) }

        assertTrue(failure.message!!.contains("UTF-8"))
    }

    @Test
    fun malformedJsonExceptionDoesNotContainPeerInput() {
        val secret = "FILE_OFFER_SECRET_SENTINEL_DO_NOT_LOG"
        val invalid =
            "{\"name\":{\"peerControlled\":\"$secret\"},\"sizeBytes\":1}".encodeToByteArray()

        val failure = assertFailsWith<IllegalArgumentException> { FileOfferPayload.decode(invalid) }

        assertFalse(failure.message.orEmpty().contains(secret), failure.message)
    }

    @Test
    fun duplicateTopLevelFieldsAreRejectedWithoutExposingTheirValues() {
        val secret = "FILE_OFFER_DUPLICATE_SECRET_DO_NOT_LOG"
        val json = """{
            "name":"safe.bin",
            "name":"$secret",
            "sizeBytes":1
        }""".trimIndent().encodeToByteArray()

        val failure = assertFailsWith<IllegalArgumentException> { FileOfferPayload.decode(json) }

        assertTrue(failure.message.orEmpty().contains("duplicate top-level field"))
        assertFalse(failure.message.orEmpty().contains(secret), failure.message)
    }

    @Test
    fun escapedAndLiteralSpellingsOfTheSameTopLevelFieldAreRejected() {
        val escapedSizeKey = "size\\u0042ytes"
        val json = """{
            "name":"safe.bin",
            "sizeBytes":1,
            "$escapedSizeKey":2
        }""".trimIndent().encodeToByteArray()

        assertFailsWith<IllegalArgumentException> { FileOfferPayload.decode(json) }
    }

    @Test
    fun maximumFieldBoundariesAreExact() {
        val name = "a".repeat(FileOfferPayload.MAX_NAME_LEN)
        val mime = "m".repeat(FileOfferPayload.MAX_MIME_LEN)
        val payload = FileOfferPayload(name, 1, mime)

        assertEquals(payload, FileOfferPayload.decode(FileOfferPayload.encode(payload)))
        assertFailsWith<IllegalArgumentException> {
            FileOfferPayload.encode(payload.copy(name = "$name!"))
        }
        assertFailsWith<IllegalArgumentException> {
            FileOfferPayload.encode(payload.copy(mimeType = "$mime!"))
        }
    }
}
