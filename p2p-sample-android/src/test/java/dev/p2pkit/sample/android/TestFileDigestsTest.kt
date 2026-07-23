package dev.p2pkit.sample.android

import java.io.ByteArrayInputStream
import kotlin.test.Test
import kotlin.test.assertEquals

class TestFileDigestsTest {
    @Test
    fun hashesKnownVector() {
        assertEquals(
            "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad",
            TestFileDigests.sha256(ByteArrayInputStream("abc".encodeToByteArray()))
        )
    }
}
