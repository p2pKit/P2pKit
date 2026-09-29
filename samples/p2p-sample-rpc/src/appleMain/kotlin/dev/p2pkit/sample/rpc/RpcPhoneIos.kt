package dev.p2pkit.sample.rpc

import dev.p2pkit.rpc.RpcPlatform
import dev.p2pkit.rpc.ios

/** Thin Swift entry point: existing device-only identity plus this test app's non-synchronizable Keychain approvals. */
public object RpcPhoneIos {
    private val trust = IosRpcPhoneTrustStore()

    @Throws(Exception::class)
    public suspend fun createHost(settings: RpcPhoneSettings, explicitlyApprovedCapacityPins: String): RpcPhoneLab =
        RpcPhoneLab.createHost(RpcPlatform.ios(), settings, trust, explicitlyApprovedCapacityPins)

    @Throws(Exception::class)
    public suspend fun createClient(settings: RpcPhoneSettings): RpcPhoneLab =
        RpcPhoneLab.createClient(RpcPlatform.ios(), settings, trust)
}
