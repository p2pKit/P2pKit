package dev.p2pkit.transport.lan

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue

class AppleLanPackagingTest {

    @Test
    fun missingUsageAndServiceProduceActionableIssues() {
        val issues = evaluateAppleLanPackaging(
            snapshot = AppleLanPackagingSnapshot(null, null),
            requiredBonjourService = "_p2pkit2._tcp"
        )

        assertEquals(2, issues.size)
        assertTrue(issues.any { "NSLocalNetworkUsageDescription" in it })
        assertTrue(issues.any { "NSBonjourServices" in it && "_p2pkit2._tcp" in it })
    }

    @Test
    fun exactProfileServiceAndUsagePassPreflight() {
        val issues = evaluateAppleLanPackaging(
            snapshot = AppleLanPackagingSnapshot(
                localNetworkUsageDescription = "Find nearby devices",
                bonjourServices = listOf("_other._tcp", "_p2pkit2._tcp")
            ),
            requiredBonjourService = "_p2pkit2._tcp"
        )

        assertTrue(issues.isEmpty())
    }
}
