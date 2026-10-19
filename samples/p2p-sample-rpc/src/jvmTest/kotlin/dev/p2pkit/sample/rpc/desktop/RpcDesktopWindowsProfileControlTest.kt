package dev.p2pkit.sample.rpc.desktop

import kotlin.test.Test
import kotlin.test.assertFailsWith

class RpcDesktopWindowsProfileControlTest {
    @Test fun createNeverAdoptsExistingOrInterruptedProfileContents() {
        checkProfileControlInventory(emptySet(), create = true)
        for (names in listOf(setOf("profile.lock"), setOf("profile.header"), setOf("identity"),
            setOf("profile.lock", "profile.header", "identity"), setOf("foreign"), setOf("pending.tmp"))) {
            assertFailsWith<IllegalStateException> { checkProfileControlInventory(names, create = true) }
        }
    }

    @Test fun restartRequiresCompleteInventoryBeforePasswordOrIdentityAccess() {
        val expected = setOf("profile.lock", "profile.header", "identity")
        checkProfileControlInventory(expected, create = false)
        for (names in listOf(emptySet(), expected + "pending.tmp", expected + "foreign") + expected.map { expected - it }) {
            assertFailsWith<IllegalStateException> { checkProfileControlInventory(names, create = false) }
        }
    }
}
