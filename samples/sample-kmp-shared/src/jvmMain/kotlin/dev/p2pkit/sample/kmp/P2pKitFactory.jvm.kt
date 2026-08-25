package dev.p2pkit.sample.kmp

import dev.p2pkit.core.AppId
import dev.p2pkit.core.P2pKit
import dev.p2pkit.core.PeerAuthorizationPolicy
import dev.p2pkit.core.SecurityMode
import dev.p2pkit.core.dsl.NetworkProvisioningConfigBuilder
import dev.p2pkit.core.dsl.jvmSecureIdentityStore
import dev.p2pkit.transport.lan.lan

public actual fun createP2pKit(
    appId: String,
    deviceName: String,
    authorization: PeerAuthorizationPolicy
): P2pKit = createJvmP2pKit(appId, deviceName, authorization)

/** JVM-test configuration seam; the public sample factory keeps its defaults. */
internal fun createJvmP2pKit(
    appId: String,
    deviceName: String,
    authorization: PeerAuthorizationPolicy = PeerAuthorizationPolicy.RejectUnknown,
    configureProvisioning: NetworkProvisioningConfigBuilder.() -> Unit = {}
): P2pKit =
    P2pKit.create {
        this.appId = AppId(appId)
        this.deviceName = deviceName
        jvmSecureIdentityStore(DevelopmentOnlyInMemorySecureIdentityStore())
        security {
            mode = SecurityMode.AuthenticatedV2(authorization)
        }
        transports { lan() }
        networkProvisioning(configureProvisioning)
    }
