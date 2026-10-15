package dev.p2pkit.sample.rpc

import dev.p2pkit.core.AppId
import dev.p2pkit.core.PeerFingerprint
import dev.p2pkit.rpc.RpcTrustPurpose
import platform.Foundation.NSUUID

/**
 * Fixed synthetic test-app control, not a library API or an administrator backdoor.
 * Real Keychain operations require an app-hosted XCTest process. Unbundled Native
 * test executables have no Keychain entitlement and return errSecMissingEntitlement.
 * No caller can choose the fresh fixture namespace or access the UI's stable store.
 */
public object RpcPhoneIosControls {
    @Throws(Exception::class)
    public suspend fun verifySyntheticTrustStore() {
        val fixture = NSUUID().UUIDString
        val store = IosRpcPhoneTrustStore(fixture)
        val app = RpcCapacityContract.appId
        val pin = PeerFingerprint.parse("p2f1-" + "a".repeat(52))
        var original: Throwable? = null
        try {
            check(store.load(app, RpcTrustPurpose.HostClients).isEmpty())
            store.replace(app, RpcTrustPurpose.HostClients, setOf(pin))
            check(IosRpcPhoneTrustStore(fixture).load(app, RpcTrustPurpose.HostClients) == setOf(pin))
            check(store.load(app, RpcTrustPurpose.SelectedHosts).isEmpty())
            val wrongNamespace = runCatching {
                store.load(AppId("wrong.namespace"), RpcTrustPurpose.HostClients)
            }.exceptionOrNull()
            check(wrongNamespace is IllegalArgumentException)
            store.replace(app, RpcTrustPurpose.HostClients, emptySet())
            check(store.load(app, RpcTrustPurpose.HostClients).isEmpty())
        } catch (error: Throwable) {
            original = error
            throw error
        } finally {
            try {
                store.deleteSyntheticFixture()
            } catch (cleanup: Throwable) {
                // Preserve the original failed operation as well as failed cleanup.
                val failure = original
                if (failure == null) throw cleanup
                failure.addSuppressed(cleanup)
            }
        }
        check(store.load(app, RpcTrustPurpose.HostClients).isEmpty())
    }
}
