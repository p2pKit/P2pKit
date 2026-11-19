package dev.p2pkit.rpc

import dev.p2pkit.core.AppId
import dev.p2pkit.core.PeerFingerprint
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.NonCancellable
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext

public enum class RpcTrustPurpose {
    HostClients, SelectedHosts,
    /** Application preference only; NEVER consulted as an authorization grant by RpcHost or RpcClient. */
    SelectedHostPreference,
}

/**
 * Application-owned LOCAL durable security configuration. Replacements must be atomic, integrity
 * protected and complete durably before returning. Isolate AppId/purpose namespaces and coordinate
 * multiple processes externally. Never implement this using a cloud-backed preference/sync store.
 * RPC supplies no business database or transactional application-idempotency storage.
 */
public interface RpcTrustStore {
    /** Read one complete committed snapshot. Throw if integrity or completeness cannot be established. */
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

    internal suspend fun reloadFromStore() {
        // The application already committed this update. Cancellation must not leave a partly
        // reconciled runtime, including while waiting for another SDK trust mutation.
        withContext(NonCancellable) {
            val failure = lock.withLock {
                if (!healthy) throw storageFailure()
                try {
                    val next = store.load(appId, purpose).validatedSnapshot()
                    val current = pins.value
                    val removed = current - next
                    if (removed.isNotEmpty()) {
                        // Deny every removal before awaiting any cleanup. Keep old grants only
                        // where the store still trusts that peer. Additions wait for cleanup.
                        pins.value = current - removed
                        for (fingerprint in removed) onRevoke?.invoke(fingerprint)
                    }
                    pins.value = next
                    null
                } catch (caught: Throwable) {
                    sealAdmission()
                    caught
                }
            }
            failure?.let { failMutation(it) }
        }
    }

    /** Denies new work immediately, even if the durable revocation subsequently fails. */
    @Throws(Exception::class)
    public suspend fun revoke(fingerprint: PeerFingerprint) {
        withContext(NonCancellable) {
            var failure: Throwable? = null
            lock.withLock {
                if (!healthy) throw storageFailure()
                val next = pins.value - fingerprint
                pins.value = next
                // A failed transport cleanup must not skip durable revocation. Admission is already
                // denied for this peer; any failure seals ALL grants before another callback or suspension.
                try { onRevoke?.invoke(fingerprint) } catch (caught: Throwable) {
                    sealAdmission()
                    failure = caught
                }
                // Persist the captured intended mutation, not the empty runtime set after failure sealing.
                try { store.replace(appId, purpose, next.toSet()) } catch (caught: Throwable) {
                    sealAdmission()
                    if (failure == null || (failure is Exception && caught !is Exception)) failure = caught
                }
            }
            failure?.let { failMutation(it) }
        }
    }

    internal suspend fun approve(fingerprint: PeerFingerprint) {
        var failure: Throwable? = null
        // Approval is an explicit administrator transaction. Never publish a partially persisted grant.
        withContext(NonCancellable) {
            lock.withLock {
                if (!healthy) throw storageFailure()
                val next = pins.value + fingerprint
                if (next.size > MAX_PINS) throw RpcFailure(RpcFailureKind.Overloaded, RpcFailurePhase.Trust)
                try {
                    store.replace(appId, purpose, next.toSet())
                    pins.value = next
                } catch (caught: Throwable) {
                    sealAdmission()
                    failure = caught
                }
            }
            failure?.let { failMutation(it) }
        }
    }

    private fun sealAdmission() {
        failed.value = true
        pins.value = emptySet()
    }

    /** Outside the trust lock: cleanup may re-enter admission, which must already be sealed. */
    private suspend fun failMutation(failure: Throwable): Nothing {
        var original = failure
        try { onStorageFailure?.invoke() } catch (caught: Throwable) {
            // Preserve the first Error/non-Exception without suppression allocation or translation. JNI
            // reporting errors can retain resource ownership; a later cleanup error cannot replace them.
            if (original is Exception && caught !is Exception) original = caught
        }
        if (original !is Exception) throw original
        // Ordinary storage/cleanup exceptions retain the existing sanitized public failure contract.
        throw storageFailure()
    }

    internal companion object {
        private const val MAX_PINS = 4096

        private fun Set<PeerFingerprint>.validatedSnapshot(): Set<PeerFingerprint> {
            val expectedSize = size
            require(expectedSize in 0..MAX_PINS)
            val snapshot = LinkedHashSet<PeerFingerprint>(expectedSize)
            // Copy even custom or mutable store results. Check the iterator's actual contents,
            // because the reported size alone cannot bound an inconsistent implementation.
            for (pin in this) {
                require(snapshot.size < expectedSize)
                require(snapshot.add(PeerFingerprint.parse(pin.value)))
            }
            require(snapshot.size == expectedSize)
            return snapshot
        }

        suspend fun load(appId: AppId, purpose: RpcTrustPurpose, store: RpcTrustStore): RpcTrust = try {
            RpcTrust(appId, purpose, store, store.load(appId, purpose).validatedSnapshot())
        } catch (cancelled: CancellationException) {
            throw cancelled
        } catch (_: Exception) {
            throw storageFailure()
        }

        private fun storageFailure(): RpcFailure = RpcFailure(RpcFailureKind.TrustStorage, RpcFailurePhase.Trust)
    }
}
