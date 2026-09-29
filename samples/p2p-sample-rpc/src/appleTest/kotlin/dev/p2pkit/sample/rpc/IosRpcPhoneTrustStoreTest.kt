package dev.p2pkit.sample.rpc

import dev.p2pkit.core.AppId
import dev.p2pkit.core.PeerFingerprint
import dev.p2pkit.rpc.RpcTrustPurpose
import kotlinx.coroutines.test.runTest
import platform.Foundation.NSUUID
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith

class IosRpcPhoneTrustStoreTest {
    @Test
    fun actualKeychainRoundTripNamespacesRevocationAndFixtureRetirement() = runTest {
        val fixture = NSUUID().UUIDString
        val store = IosRpcPhoneTrustStore(fixture)
        val app = RpcCapacityContract.appId
        val pin = PeerFingerprint.parse("p2f1-" + "a".repeat(52))
        try {
            assertEquals(emptySet(), store.load(app, RpcTrustPurpose.HostClients))
            store.replace(app, RpcTrustPurpose.HostClients, setOf(pin))
            assertEquals(setOf(pin), IosRpcPhoneTrustStore(fixture).load(app, RpcTrustPurpose.HostClients))
            assertEquals(emptySet(), store.load(app, RpcTrustPurpose.SelectedHosts))
            assertFailsWith<IllegalArgumentException> {
                store.load(AppId("wrong.namespace"), RpcTrustPurpose.HostClients)
            }
            store.replace(app, RpcTrustPurpose.HostClients, emptySet())
            assertEquals(emptySet(), store.load(app, RpcTrustPurpose.HostClients))
        } finally { store.deleteSyntheticFixture() }
        assertEquals(emptySet(), store.load(app, RpcTrustPurpose.HostClients))
    }
}
