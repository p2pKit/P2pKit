package dev.p2pkit.core.protocol

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertNull

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
    fun unicodeNameSurvives() {
        val payload = FileOfferPayload(
            name = "résumé 🇸🇪.docx",
            sizeBytes = 42L,
            mimeType = "application/vnd.openxmlformats"
        )
        val decoded = FileOfferPayload.decode(FileOfferPayload.encode(payload))
        assertEquals(payload, decoded)
    }
}
