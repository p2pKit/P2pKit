package dev.p2pkit.sample.desktop.ui

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertTrue

class DesktopSampleNavigationTest {
    @Test fun samplesAndDiagnosticsKeepTheirExistingReturnPathAndRootEscapeDoesNotExit() {
        val navigation = DesktopSampleNavigation()
        assertFalse(navigation.back { error("Root must not close") })
        assertTrue(navigation.open(DesktopSampleNavigation.Section.Diagnostics))
        assertTrue(navigation.back { error("Diagnostics return does not stop the room") })
        assertEquals(DesktopSampleNavigation.Section.Samples, navigation.section)
    }

    @Test fun rpcCannotReplaceAnActiveOrUnretiredRoomSession() {
        val navigation = DesktopSampleNavigation()
        assertFalse(navigation.open(DesktopSampleNavigation.Section.Rpc, ordinaryIdle = false))
        assertEquals(DesktopSampleNavigation.Section.Samples, navigation.section)
        assertTrue(navigation.open(DesktopSampleNavigation.Section.Rpc, ordinaryIdle = true))
        assertFalse(navigation.open(DesktopSampleNavigation.Section.Diagnostics))
    }

    @Test fun toolbarAndEscapeWaitForOneCloseBeforeReturningAndRejectStaleCallbacks() {
        val navigation = DesktopSampleNavigation()
        navigation.open(DesktopSampleNavigation.Section.Rpc)
        lateinit var completed: (Boolean) -> Unit
        assertTrue(navigation.back { completed = it })
        assertTrue(navigation.leaving)
        assertEquals(DesktopSampleNavigation.Section.Rpc, navigation.section)
        assertTrue(navigation.back { error("Duplicate Back must not close twice") })
        assertFalse(navigation.open(DesktopSampleNavigation.Section.Diagnostics))
        completed(true)
        assertEquals(DesktopSampleNavigation.Section.Samples, navigation.section)
        assertFalse(navigation.leaving)
        navigation.open(DesktopSampleNavigation.Section.Rpc)
        completed(true)
        assertEquals(DesktopSampleNavigation.Section.Rpc, navigation.section)
    }

    @Test fun failedRpcCloseRetainsSectionAndBlocksApplicationExit() {
        val navigation = DesktopSampleNavigation()
        navigation.open(DesktopSampleNavigation.Section.Rpc)
        navigation.back { it(false) }
        assertEquals(DesktopSampleNavigation.Section.Rpc, navigation.section)
        assertTrue(navigation.cleanupFailed)
        var exited = false
        navigation.exit({ it(false) }) { exited = it }
        assertFalse(exited)
        assertEquals(DesktopSampleNavigation.Section.Rpc, navigation.section)
        assertTrue(navigation.cleanupFailed)
    }

    @Test fun windowCloseWaitsAndDoesNotReplayAnExitRequestedDuringBack() {
        val navigation = DesktopSampleNavigation()
        navigation.open(DesktopSampleNavigation.Section.Rpc)
        lateinit var completed: (Boolean) -> Unit
        navigation.back { completed = it }
        navigation.exit({ error("No second physical close") }) { assertFalse(it) }
        completed(true)
        assertEquals(DesktopSampleNavigation.Section.Samples, navigation.section)
        var exits = 0
        navigation.exit({ it(true) }) { if (it) exits++ }
        navigation.exit({ error("Application already closed") }) { exits++ }
        assertEquals(1, exits)
        assertFalse(navigation.open(DesktopSampleNavigation.Section.Rpc))
    }
}
