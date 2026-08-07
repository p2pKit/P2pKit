package dev.p2pkit.sample.desktop.ui

import java.nio.file.Files
import kotlin.test.Test
import kotlin.test.assertEquals

class TestFileDigestTest {
    @Test
    fun hashesKnownVector() {
        val file = Files.createTempFile("p2pkit-ui-digest-", ".bin").toFile()
        try {
            file.writeText("abc")
            assertEquals(
                "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad",
                testFileSha256(file)
            )
        } finally {
            file.delete()
        }
    }
}
