package dev.p2pkit.sample.kmp

import dev.p2pkit.core.AppId
import dev.p2pkit.core.ExplicitSecurityRisk
import dev.p2pkit.core.P2pKit
import dev.p2pkit.core.PeerAuthorizationPolicy
import dev.p2pkit.core.SecurityMode
import dev.p2pkit.core.dsl.jvmSecureIdentityStore
import dev.p2pkit.transport.lan.lan

@OptIn(ExplicitSecurityRisk::class)
public actual fun createP2pKit(appId: String, deviceName: String): P2pKit =
    P2pKit.create {
        this.appId = AppId(appId)
        this.deviceName = deviceName
        jvmSecureIdentityStore(DevelopmentOnlyInMemorySecureIdentityStore())
        security {
            mode = SecurityMode.AuthenticatedV2(
                PeerAuthorizationPolicy.AcceptAnyAuthenticatedSameApp
            )
        }
        transports { lan() }
    }
