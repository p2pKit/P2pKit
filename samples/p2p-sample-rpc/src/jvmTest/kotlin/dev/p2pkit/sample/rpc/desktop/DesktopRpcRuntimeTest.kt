package dev.p2pkit.sample.rpc.desktop

import dev.p2pkit.sample.rpc.RpcPhoneLab
import kotlin.test.Test
import kotlin.test.assertEquals

class DesktopRpcRuntimeTest {
    @Test
    fun explicitLocalReadinessCannotAccidentallyAdvertiseOrStartDiscovery() {
        assertEquals(RpcPhoneLab.Companion::createApplicationHost, desktopRpcApplicationFactory(true, false))
        assertEquals(RpcPhoneLab.Companion::createApplicationClient, desktopRpcApplicationFactory(false, false))
        assertEquals(RpcPhoneLab.Companion::createNearbyApplicationHost, desktopRpcApplicationFactory(true, true))
        assertEquals(RpcPhoneLab.Companion::createNearbyApplicationClient, desktopRpcApplicationFactory(false, true))
    }
}
