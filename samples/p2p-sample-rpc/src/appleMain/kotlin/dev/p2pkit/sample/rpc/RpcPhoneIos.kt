package dev.p2pkit.sample.rpc

import dev.p2pkit.rpc.RpcPlatform
import dev.p2pkit.rpc.ios

/** Thin Swift entry point: existing device-only identity plus this test app's non-synchronizable Keychain approvals. */
public object RpcPhoneIos {
    private val trust = IosRpcPhoneTrustStore()

    public val compiledSource: String get() = RpcPhoneLab.compiledSource

    @Throws(Exception::class)
    public fun parseCapacityConfig(text: String): RpcMobileCapacityConfig = RpcMobileCapacityConfig.parse(text)

    @Throws(Exception::class)
    public suspend fun createCapacityHost(config: RpcMobileCapacityConfig): RpcPhoneLab =
        RpcPhoneLab.createMobileCapacityHost(RpcPlatform.ios(), trust, config, "Ios")

    @Throws(Exception::class)
    public suspend fun createHost(settings: RpcPhoneSettings, explicitlyApprovedCapacityPins: String): RpcPhoneLab =
        RpcPhoneLab.createHost(RpcPlatform.ios(), settings, trust, explicitlyApprovedCapacityPins)

    @Throws(Exception::class)
    public suspend fun createClient(settings: RpcPhoneSettings): RpcPhoneLab =
        RpcPhoneLab.createClient(RpcPlatform.ios(), settings, trust)

    @Throws(Exception::class)
    public suspend fun createApplicationHost(
        settings: RpcPhoneSettings, application: RpcApplicationSession,
    ): RpcPhoneLab =
        RpcPhoneLab.createApplicationHost(RpcPlatform.ios(), settings, trust, application)

    @Throws(Exception::class)
    public suspend fun createApplicationClient(
        settings: RpcPhoneSettings, application: RpcApplicationSession,
    ): RpcPhoneLab =
        RpcPhoneLab.createApplicationClient(RpcPlatform.ios(), settings, trust, application)
    @Throws(Exception::class)
    public suspend fun createNearbyApplicationHost(
        settings: RpcPhoneSettings, application: RpcApplicationSession,
    ): RpcPhoneLab = RpcPhoneLab.createNearbyApplicationHost(RpcPlatform.ios(), settings, trust, application)

    @Throws(Exception::class)
    public suspend fun createNearbyApplicationClient(
        settings: RpcPhoneSettings, application: RpcApplicationSession,
    ): RpcPhoneLab = RpcPhoneLab.createNearbyApplicationClient(RpcPlatform.ios(), settings, trust, application)
}
