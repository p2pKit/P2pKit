package dev.p2pkit.core.internal

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertNull

class JvmSystemPropertyTestGuardTest {

    @Test
    fun restoresPresentAndAbsentValuesAfterFailure() {
        val present = "dev.p2pkit.test.present"
        val absent = "dev.p2pkit.test.absent"
        System.setProperty(present, "before")
        System.clearProperty(absent)

        try {
            assertFailsWith<FixtureProbeFailure> {
                JvmSystemPropertyTestGuard.withValues(
                    mapOf(present to "during", absent to "temporary")
                ) {
                    assertEquals("during", System.getProperty(present))
                    assertEquals("temporary", System.getProperty(absent))
                    throw FixtureProbeFailure()
                }
            }

            assertEquals("before", System.getProperty(present))
            assertNull(System.getProperty(absent))
        } finally {
            System.clearProperty(present)
            System.clearProperty(absent)
        }
    }

    private class FixtureProbeFailure : RuntimeException()
}
