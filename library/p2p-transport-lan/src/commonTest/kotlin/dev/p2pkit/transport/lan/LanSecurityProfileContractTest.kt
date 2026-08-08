package dev.p2pkit.transport.lan

import dev.p2pkit.core.transport.TransportSecurityProfile
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertNotEquals

class LanSecurityProfileContractTest {

    @Test
    fun authenticatedAndLegacyProfilesUseDistinctNamespacesAndVersions() {
        assertEquals(
            "_p2pkit2._tcp.local.",
            LanConstants.serviceTypeJmdns(TransportSecurityProfile.AuthenticatedV2),
        )
        assertEquals(
            "_p2pkit2._tcp",
            LanConstants.serviceTypeBonjour(TransportSecurityProfile.AuthenticatedV2),
        )
        assertEquals(
            2,
            LanConstants.protocolVersion(TransportSecurityProfile.AuthenticatedV2),
        )

        assertEquals(
            "_p2pkit._tcp.local.",
            LanConstants.serviceTypeJmdns(TransportSecurityProfile.LegacyPlaintextV1),
        )
        assertEquals(
            "_p2pkit._tcp",
            LanConstants.serviceTypeBonjour(TransportSecurityProfile.LegacyPlaintextV1),
        )
        assertEquals(
            1,
            LanConstants.protocolVersion(TransportSecurityProfile.LegacyPlaintextV1),
        )

        assertNotEquals(
            LanConstants.serviceTypeJmdns(TransportSecurityProfile.AuthenticatedV2),
            LanConstants.serviceTypeJmdns(TransportSecurityProfile.LegacyPlaintextV1),
        )
    }
}
