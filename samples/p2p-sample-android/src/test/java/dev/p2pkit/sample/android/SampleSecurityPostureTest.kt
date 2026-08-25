package dev.p2pkit.sample.android

import kotlin.test.Test
import kotlin.test.assertFalse
import kotlin.test.assertTrue

class SampleSecurityPostureTest {
    @Test
    fun autoMeshStartsDisabledUntilTheUserEnablesIt() {
        assertFalse(DEFAULT_AUTO_MESH_ENABLED)
    }

    @Test
    fun warningExplainsTheDevelopmentPolicyAndPinnedProductionAlternative() {
        assertTrue(SECURITY_POSTURE_WARNING.contains("DEVELOPMENT MODE"))
        assertTrue(SECURITY_POSTURE_WARNING.contains("accepting any authenticated peer"))
        assertTrue(SECURITY_POSTURE_WARNING.contains("PinnedOnly"))
    }
}
