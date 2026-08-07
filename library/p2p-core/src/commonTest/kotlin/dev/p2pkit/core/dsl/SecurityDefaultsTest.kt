package dev.p2pkit.core.dsl

import dev.p2pkit.core.AppId
import dev.p2pkit.core.PeerAuthorizationPolicy
import dev.p2pkit.core.PeerId
import dev.p2pkit.core.Platform
import dev.p2pkit.core.SecurityMode
import dev.p2pkit.core.transport.TransportContext
import dev.p2pkit.core.transport.TransportSecurityProfile
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertIs

class SecurityDefaultsTest {

    @Test
    fun kitDefaultsToAuthenticatedV2AndRejectsUnknownPeers() {
        val mode = assertIs<SecurityMode.AuthenticatedV2>(
            P2pKitBuilder().securityMode,
        )

        assertEquals(PeerAuthorizationPolicy.RejectUnknown, mode.authorization)
    }

    @Test
    fun thirdPartyTransportContextRetainsLegacyDefaultForSourceCompatibility() {
        val context = TransportContext(
            appId = AppId("dev.p2pkit.compatibility-test"),
            localPeerId = PeerId("legacy-compatible-peer"),
            deviceName = "Compatibility test",
            platform = Platform.JVM_DESKTOP,
        )

        assertEquals(
            TransportSecurityProfile.LegacyPlaintextV1,
            context.securityProfile,
        )
    }
}
