package dev.p2pkit.rpc

import dev.p2pkit.core.AppId
import dev.p2pkit.core.PeerFingerprint
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.NonCancellable
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext

public enum class RpcTrustPurpose { HostClients, SelectedHosts }

/**
 * Application-owned LOCAL durable security configuration. Replacements must be atomic, integrity
 * protected and complete durably before returning. Isolate AppId/purpose namespaces and coordinate
 * multiple processes externally. Never implement this using a cloud-backed preference/sync store.
 * RPC supplies no business database or transactional application-idempotency storage.
 */
public interface RpcTrustStore {
    @Throws(Exception::class)
    public suspend fun load(appId: AppId, purpose: RpcTrustPurpose): Set<PeerFingerprint>

    @Throws(Exception::class)
    public suspend fun replace(appId: AppId, purpose: RpcTrustPurpose, fingerprints: Set<PeerFingerprint>)
}

/** Live trust management. Storage failures latch this runtime closed to admission until recreated. */
public class RpcTrust internal constructor(
    private val appId: AppId,
    private val purpose: RpcTrustPurpose,
    private val store: RpcTrustStore,
    initial: Set<PeerFingerprint>,
) {
    private val lock = Mutex()
    private val pins = MutableStateFlow(initial.toSet())
    private val failed = MutableStateFlow(false)
    internal var onRevoke: (suspend (PeerFingerprint) -> Unit)? = null
    internal var onStorageFailure: (suspend () -> Unit)? = null
    internal val healthy: Boolean get() = !failed.value

    public fun isTrusted(fingerprint: PeerFingerprint): Boolean = healthy && fingerprint in pins.value
    public fun fingerprints(): List<PeerFingerprint> = pins.value.toList()

    /** Denies new work immediately, even if the durable revocation subsequently fails. */
    @Throws(Exception::class)
    public suspend fun revoke(fingerprint: PeerFingerprint) {
        withContext(NonCancellable) {
            var failure = false
            lock.withLock {
                if (!healthy) throw storageFailure()
                pins.value = pins.value - fingerprint
                // A failed transport cleanup must not skip durable revocation. Admission is already
                // denied; either failure also seals ALL admission until the runtime is recreated.
                try { onRevoke?.invoke(fingerprint) } catch (_: Exception) { failure = true }
                try { store.replace(appId, purpose, pins.value.toSet()) } catch (_: Exception) { failure = true }
                if (failure) {
                    failed.value = true
                    pins.value = emptySet()
                }
            }
            if (failure) {
                try { onStorageFailure?.invoke() } catch (_: Exception) { /* Admission remains sealed. */ }
                throw storageFailure()
            }
        }
    }

    internal suspend fun approve(fingerprint: PeerFingerprint) {
        var failure = false
        // Approval is an explicit administrator transaction. Never publish a partially persisted grant.
        withContext(NonCancellable) {
            lock.withLock {
                if (!healthy) throw storageFailure()
                val next = pins.value + fingerprint
                if (next.size > 4096) throw RpcFailure(RpcFailureKind.Overloaded, RpcFailurePhase.Trust)
                try {
                    store.replace(appId, purpose, next.toSet())
                    pins.value = next
                } catch (_: Exception) {
                    failed.value = true
                    pins.value = emptySet()
                    failure = true
                }
            }
            if (failure) {
                try { onStorageFailure?.invoke() } catch (_: Exception) { /* Admission remains sealed. */ }
                throw storageFailure()
            }
        }
    }

    internal companion object {
        suspend fun load(appId: AppId, purpose: RpcTrustPurpose, store: RpcTrustStore): RpcTrust = try {
            val pins = store.load(appId, purpose)
            require(pins.size <= 4096)
            RpcTrust(appId, purpose, store, pins)
        } catch (cancelled: CancellationException) {
            throw cancelled
        } catch (_: Exception) {
            throw storageFailure()
        }

        private fun storageFailure(): RpcFailure = RpcFailure(RpcFailureKind.TrustStorage, RpcFailurePhase.Trust)
    }
}
