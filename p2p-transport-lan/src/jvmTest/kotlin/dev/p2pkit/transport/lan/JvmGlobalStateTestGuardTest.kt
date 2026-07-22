package dev.p2pkit.transport.lan

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertNull

class JvmGlobalStateTestGuardTest {

    @Test
    fun restoresDeclaredPropertiesExactly() {
        val present = "dev.p2pkit.lan.test.present"
        val absent = "dev.p2pkit.lan.test.absent"
        System.setProperty(present, "before")
        System.clearProperty(absent)

        try {
            JvmGlobalStateTestGuard.withValues(
                mapOf(present to "during", absent to "temporary")
            ) {
                assertEquals("during", System.getProperty(present))
                assertEquals("temporary", System.getProperty(absent))
            }

            assertEquals("before", System.getProperty(present))
            assertNull(System.getProperty(absent))
        } finally {
            System.clearProperty(present)
            System.clearProperty(absent)
        }
    }
}
