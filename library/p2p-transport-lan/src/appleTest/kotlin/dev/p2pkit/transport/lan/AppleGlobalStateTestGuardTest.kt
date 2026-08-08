package dev.p2pkit.transport.lan

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertNotEquals
import kotlin.test.assertNull
import kotlin.uuid.ExperimentalUuidApi
import kotlin.uuid.Uuid
import platform.Foundation.NSUserDefaults

class AppleGlobalStateTestGuardTest {

    @Test
    fun testNamespacesDoNotReuseBonjourIdentity() {
        val first = newAppleLanTestNamespace("p2pkit-test")
        val second = newAppleLanTestNamespace("p2pkit-test")

        assertNotEquals(first, second)
    }

    @Test
    fun restoresPresentAndAbsentValuesExactly() {
        val suiteName = "dev.p2pkit.transport.lan.tests.${uniqueSuffix()}"
        val defaults = NSUserDefaults(suiteName = suiteName)
        val present = "present"
        val absent = "absent"
        defaults.setObject("before", present)
        defaults.removeObjectForKey(absent)

        try {
            val lease = AppleGlobalStateTestGuard.acquire(defaults, present, absent)
            try {
                lease.remove(present)
                lease.remove(absent)
                lease.synchronize()
            } finally {
                lease.close()
            }

            assertEquals("before", defaults.stringForKey(present))
            assertNull(defaults.objectForKey(absent))
        } finally {
            defaults.removePersistentDomainForName(suiteName)
            defaults.synchronize()
        }
    }

    @OptIn(ExperimentalUuidApi::class)
    private fun uniqueSuffix(): String = Uuid.random().toString()
}
