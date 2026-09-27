package dev.p2pkit.rpc

import dev.p2pkit.core.AppId
import dev.p2pkit.core.P2pKit
import dev.p2pkit.core.P2pSessionProfile
import dev.p2pkit.core.PeerFingerprint
import dev.p2pkit.core.ReconnectPolicy
import dev.p2pkit.core.SecurityMode
import dev.p2pkit.core.dsl.P2pKitBuilder
import dev.p2pkit.transport.lan.LanRole
import dev.p2pkit.transport.lan.OrganizationLan

/** Platform-owned construction only: applications cannot inject a borrowed kit or arbitrary transport. */
public class RpcPlatform internal constructor(internal val createKit: (RpcKitSettings) -> P2pKit) {
    public companion object {}
}

internal class RpcKitSettings(
    val appId: AppId,
    val lan: OrganizationLan,
    val role: LanRole,
    val profile: P2pSessionProfile,
) {
    fun configure(builder: P2pKitBuilder) = with(builder) {
        appId = this@RpcKitSettings.appId
        deviceName = if (role == LanRole.Host) "P2pKit RPC host" else "P2pKit RPC client"
        sessionProfile = profile
        security { mode = SecurityMode.AuthenticatedV2() }
        lifecycle {
            reconnectPolicy = if (role == LanRole.DialOnly) ReconnectPolicy.Enabled(5, 100)
            else ReconnectPolicy.Disabled
        }
    }
}

/** A numeric endpoint is still policy-checked on every connection; this type never resolves a name. */
public class RpcEndpoint(public val address: String, public val port: Int) {
    init {
        require(address.length in 1..39 && address.all { it in "0123456789abcdefABCDEF:." })
        require(port in 1..65_535)
    }
    override fun toString(): String = "RpcEndpoint(redacted)"
}

/** Explicit host selection. connect() also requires this pin to exist in the local durable trust store. */
public class RpcSelectedHost(public val fingerprint: PeerFingerprint, public val endpoint: RpcEndpoint) {
    override fun toString(): String = "RpcSelectedHost(redacted)"
}
