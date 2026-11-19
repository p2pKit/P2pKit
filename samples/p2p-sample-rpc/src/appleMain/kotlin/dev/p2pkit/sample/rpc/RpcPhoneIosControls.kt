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
        val capacity = IosRpcPhoneTrustStore(fixture, mobileCapacity = true)
        val app = RpcCapacityContract.appId
        val pin = PeerFingerprint.parse("p2f1-" + "a".repeat(52))
        var original: Throwable? = null
        try {
            check(store.load(app, RpcTrustPurpose.HostClients).isEmpty())
            store.replace(app, RpcTrustPurpose.HostClients, setOf(pin))
            check(IosRpcPhoneTrustStore(fixture).load(app, RpcTrustPurpose.HostClients) == setOf(pin))
            check(store.load(app, RpcTrustPurpose.SelectedHosts).isEmpty())
            check(capacity.load(app, RpcTrustPurpose.HostClients).isEmpty())
            val wrongNamespace = runCatching {
                store.load(AppId("wrong.namespace"), RpcTrustPurpose.HostClients)
            }.exceptionOrNull()
            check(wrongNamespace is IllegalArgumentException)
            val alphabet = "abcdefghijklmnopqrstuvwxyz234567"
            val tooMany = (0..256).map {
                PeerFingerprint.parse("p2f1-${alphabet[it / 32]}${alphabet[it % 32]}" + "a".repeat(50))
            }.toSet()
            check(tooMany.size == 257)
            store.replace(app, RpcTrustPurpose.SelectedHosts, setOf(pin))
            for (count in listOf(128, 256)) {
                val approved = tooMany.take(count).toSet()
                store.replace(app, RpcTrustPurpose.HostClients, approved)
                check(IosRpcPhoneTrustStore(fixture).load(app, RpcTrustPurpose.HostClients) == approved)
                check(store.load(app, RpcTrustPurpose.SelectedHosts) == setOf(pin))
                capacity.replace(app, RpcTrustPurpose.HostClients, approved)
                check(IosRpcPhoneTrustStore(fixture, mobileCapacity = true)
                    .load(app, RpcTrustPurpose.HostClients) == approved)
                retireMobileCapacityPins(capacity, approved)
                check(capacity.load(app, RpcTrustPurpose.HostClients).isEmpty())
                check(store.load(app, RpcTrustPurpose.HostClients) == approved)
                check(store.load(app, RpcTrustPurpose.SelectedHosts) == setOf(pin))
            }
            val excessive = runCatching {
                store.replace(app, RpcTrustPurpose.HostClients, tooMany)
            }.exceptionOrNull()
            check(excessive is IllegalArgumentException)
            check(store.load(app, RpcTrustPurpose.HostClients) == tooMany.take(256).toSet())
            store.replace(app, RpcTrustPurpose.HostClients, emptySet())
            check(store.load(app, RpcTrustPurpose.HostClients).isEmpty())
        } catch (error: Throwable) {
            original = error
            throw error
        } finally {
            var cleanupFailure: Throwable? = null
            for (fixtureStore in listOf(capacity, store)) {
                try { fixtureStore.deleteSyntheticFixture() }
                catch (cleanup: Throwable) {
                    val failure = original ?: cleanupFailure
                    if (failure == null) cleanupFailure = cleanup else failure.addSuppressed(cleanup)
                }
            }
            if (original == null) cleanupFailure?.let { throw it }
        }
        check(store.load(app, RpcTrustPurpose.HostClients).isEmpty())
        check(store.load(app, RpcTrustPurpose.SelectedHosts).isEmpty())
        check(capacity.load(app, RpcTrustPurpose.HostClients).isEmpty())
    }
}
