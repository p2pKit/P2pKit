package dev.p2pkit.sample.rpc.desktop

import java.nio.file.Path
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith

class DesktopRpcProfileDirectoryTest {
    @Test fun defaultRemainsTheExistingProfileAndExplicitTestProfileIsIndependent() {
        val home = Path.of("synthetic-owner").toAbsolutePath().normalize()
        val separate = home.resolve(".p2pkit-rpc-test-fixture")
        val original = desktopRpcProfileDirectory(home.toString(), null)
        val test = desktopRpcProfileDirectory("unused", separate.toString())
        assertEquals(home.resolve(".p2pkit-rpc-desktop"), original)
        assertEquals(separate, test)
        assertEquals(original, desktopRpcProfileDirectory(home.toString(), null))
    }

    @Test fun explicitProfileRejectsRelativeAndUnnormalizedPathsBeforeAcquisition() {
        val unnormalized = Path.of("synthetic-owner").toAbsolutePath().resolve("..").resolve("other-profile")
        for (path in listOf("relative-profile", unnormalized.toString(), "")) {
            assertFailsWith<IllegalArgumentException> { desktopRpcProfileDirectory("unused", path) }
        }
    }
}
