package dev.p2pkit.core.internal

import dev.p2pkit.core.LocalIdentityFailureKind
import dev.p2pkit.core.LocalIdentityRecovery
import dev.p2pkit.core.P2pError
import dev.p2pkit.core.security.EncodedIdentityKeyPair
import dev.p2pkit.core.security.IdentityKeyRecordCodec
import dev.p2pkit.core.security.IdentityNamespace
import dev.p2pkit.core.security.IdentityRecordCorruptException
import dev.p2pkit.core.security.IdentityStateMarkerCodec
import dev.p2pkit.core.security.JvmSecureIdentityStore
import dev.p2pkit.core.security.constantTimeEquals
import dev.p2pkit.core.security.localIdentityError
import kotlinx.coroutines.CancellationException
import java.util.concurrent.atomic.AtomicBoolean

internal class JvmSecureIdentityStoreAdapter(
    private val store: JvmSecureIdentityStore
) : SecureIdentityStorage {

    override fun acquireUsage(namespace: IdentityNamespace): SecureIdentityUsage =
        JvmSecureIdentityLiveGuard.acquire(store, namespace.storageKey)

    override fun loadOrCreate(
        namespace: IdentityNamespace,
        fingerprintDigest: (EncodedIdentityKeyPair) -> ByteArray,
        generate: () -> EncodedIdentityKeyPair
    ): EncodedIdentityKeyPair {
        rejectPendingReset(namespace)
        val identityKey = identityKey(namespace)
        val existing = read(identityKey)
        if (existing != null) {
            return validateAndReturn(decodeAndClear(namespace, existing), fingerprintDigest)
        }

        val candidate = generate()
        val candidateRecord = IdentityKeyRecordCodec.encode(namespace, candidate)
        val storeInput = candidateRecord.copyOf()
        var winner: ByteArray? = null
        var reread: ByteArray? = null
        try {
            val durableWinner = callStore("atomically persist secure identity") {
                store.putIfAbsent(identityKey, storeInput)
            }
            winner = durableWinner
            if (durableWinner.size != IdentityKeyRecordCodec.RECORD_SIZE) {
                throw corrupt("JVM secure store returned a non-P2KI winner")
            }
            val durableReread = read(identityKey)
                ?: contractViolation("durable winner was absent on immediate reread")
            reread = durableReread
            if (!constantTimeEquals(durableWinner, durableReread)) {
                contractViolation("putIfAbsent winner differed from immediate reread")
            }
            return validateAndReturn(
                IdentityKeyRecordCodec.decode(namespace, durableReread),
                fingerprintDigest
            )
        } catch (e: IdentityRecordCorruptException) {
            throw corrupt(e.message ?: "JVM secure identity record is corrupt", e)
        } finally {
            candidate.clearPrivate()
            candidateRecord.fill(0)
            storeInput.fill(0)
            winner?.fill(0)
            reread?.fill(0)
        }
    }

    override fun reset(namespace: IdentityNamespace): Unit =
        JvmSecureIdentityLiveGuard.runReset(store, namespace.storageKey) {
            resetWhileExclusive(namespace)
        }

    private fun resetWhileExclusive(namespace: IdentityNamespace) {
        val resetKey = resetKey(namespace)
        val marker = IdentityStateMarkerCodec.encodeResetPending(namespace)
        val storeInput = marker.copyOf()
        var winner: ByteArray? = null
        try {
            val durableWinner = callStore("persist secure-identity reset marker") {
                store.putIfAbsent(resetKey, storeInput)
            }
            winner = durableWinner
            try {
                IdentityStateMarkerCodec.decodeResetPending(namespace, durableWinner)
            } catch (e: IdentityRecordCorruptException) {
                throw corrupt("JVM reset marker is corrupt", e)
            }
            val durableMarker = read(resetKey)
                ?: contractViolation("reset marker was absent on immediate reread")
            try {
                IdentityStateMarkerCodec.decodeResetPending(namespace, durableMarker)
                if (!constantTimeEquals(durableWinner, durableMarker)) {
                    contractViolation("reset marker winner differed from immediate reread")
                }
            } finally {
                durableMarker.fill(0)
            }

            delete(identityKey(namespace), "delete secure identity during explicit reset")
            assertAbsent(identityKey(namespace), "secure identity remained after durable reset deletion")
            delete(resetKey, "delete completed secure-identity reset marker")
            assertAbsent(resetKey, "reset marker remained after completed explicit reset")
        } finally {
            marker.fill(0)
            storeInput.fill(0)
            winner?.fill(0)
        }
    }

    private fun rejectPendingReset(namespace: IdentityNamespace) {
        val marker = read(resetKey(namespace)) ?: return
        try {
            try {
                IdentityStateMarkerCodec.decodeResetPending(namespace, marker)
            } catch (e: IdentityRecordCorruptException) {
                throw corrupt("JVM reset marker is corrupt", e)
            }
            throw localIdentityError(
                kind = LocalIdentityFailureKind.RESET_PENDING,
                recovery = LocalIdentityRecovery.EXPLICIT_RESET_REQUIRED,
                reason = "an interrupted local-identity reset requires another explicit reset call"
            )
        } finally {
            marker.fill(0)
        }
    }

    private fun decodeAndClear(
        namespace: IdentityNamespace,
        record: ByteArray
    ): EncodedIdentityKeyPair = try {
        IdentityKeyRecordCodec.decode(namespace, record)
    } catch (e: IdentityRecordCorruptException) {
        throw corrupt(e.message ?: "JVM secure identity record is corrupt", e)
    } finally {
        record.fill(0)
    }

    private fun validateFingerprintDigest(
        keyPair: EncodedIdentityKeyPair,
        fingerprintDigest: (EncodedIdentityKeyPair) -> ByteArray
    ) {
        val digest = fingerprintDigest(keyPair)
        try {
            if (digest.size != 32) {
                contractViolation("fingerprint digest callback returned a non-32-byte value")
            }
        } finally {
            digest.fill(0)
        }
    }

    private fun validateAndReturn(
        keyPair: EncodedIdentityKeyPair,
        fingerprintDigest: (EncodedIdentityKeyPair) -> ByteArray
    ): EncodedIdentityKeyPair {
        var success = false
        return try {
            validateFingerprintDigest(keyPair, fingerprintDigest)
            success = true
            keyPair
        } finally {
            if (!success) keyPair.clearPrivate()
        }
    }

    private fun read(key: String): ByteArray? {
        val raw = callStore("read secure identity") { store.read(key) } ?: return null
        return try {
            raw.copyOf()
        } finally {
            raw.fill(0)
        }
    }

    private fun assertAbsent(key: String, reason: String) {
        val unexpected = read(key) ?: return
        try {
            contractViolation(reason)
        } finally {
            unexpected.fill(0)
        }
    }

    private fun delete(key: String, operation: String) {
        callStore(operation) { store.delete(key) }
    }

    private inline fun <T> callStore(operation: String, block: () -> T): T = try {
        block()
    } catch (e: P2pError.LocalIdentityUnavailable) {
        throw e
    } catch (e: CancellationException) {
        throw e
    } catch (e: Exception) {
        throw localIdentityError(
            kind = LocalIdentityFailureKind.TEMPORARILY_UNAVAILABLE,
            recovery = LocalIdentityRecovery.RETRY,
            reason = "JVM secure store failed to $operation",
            cause = e
        )
    }

    private fun identityKey(namespace: IdentityNamespace): String =
        "dev.p2pkit.identity.v2.${namespace.storageKey}"

    private fun resetKey(namespace: IdentityNamespace): String =
        "${identityKey(namespace)}.reset.pending"

    private fun corrupt(reason: String, cause: Throwable? = null): P2pError.LocalIdentityUnavailable =
        localIdentityError(
            kind = LocalIdentityFailureKind.CORRUPT_RECORD,
            recovery = LocalIdentityRecovery.EXPLICIT_RESET_REQUIRED,
            reason = reason,
            cause = cause
        )

    private fun contractViolation(reason: String): Nothing = throw localIdentityError(
        kind = LocalIdentityFailureKind.STORE_CONTRACT_VIOLATION,
        recovery = LocalIdentityRecovery.FIX_PLATFORM_CONFIGURATION,
        reason = reason
    )
}

/**
 * Process-local reset/kit exclusion for one exact host-store instance.
 * Cross-process exclusion remains part of [JvmSecureIdentityStore]'s host
 * contract and cannot be inferred by core.
 */
private object JvmSecureIdentityLiveGuard {
    private val lock = Any()
    private val states = mutableMapOf<StoreNamespace, State>()

    fun acquire(store: JvmSecureIdentityStore, namespace: String): SecureIdentityUsage {
        val key = StoreNamespace(store, namespace)
        synchronized(lock) {
            val state = states.getOrPut(key) { State() }
            if (state.resetInProgress) {
                throw localIdentityError(
                    kind = LocalIdentityFailureKind.TEMPORARILY_UNAVAILABLE,
                    recovery = LocalIdentityRecovery.RETRY,
                    reason = "JVM secure identity reset is already in progress"
                )
            }
            state.liveUsages++
        }

        val released = AtomicBoolean(false)
        return SecureIdentityUsage {
            if (!released.compareAndSet(false, true)) return@SecureIdentityUsage
            synchronized(lock) {
                val state = checkNotNull(states[key]) {
                    "JVM secure identity usage state disappeared before release"
                }
                check(state.liveUsages > 0) { "JVM secure identity usage count underflow" }
                state.liveUsages--
                if (state.liveUsages == 0 && !state.resetInProgress) states.remove(key)
            }
        }
    }

    fun <T> runReset(
        store: JvmSecureIdentityStore,
        namespace: String,
        block: () -> T
    ): T {
        val key = StoreNamespace(store, namespace)
        synchronized(lock) {
            val state = states.getOrPut(key) { State() }
            if (state.liveUsages != 0) {
                throw localIdentityError(
                    kind = LocalIdentityFailureKind.LIVE_IDENTITY_IN_USE,
                    recovery = LocalIdentityRecovery.RETRY,
                    reason = "a live JVM kit still owns this secure identity"
                )
            }
            if (state.resetInProgress) {
                throw localIdentityError(
                    kind = LocalIdentityFailureKind.TEMPORARILY_UNAVAILABLE,
                    recovery = LocalIdentityRecovery.RETRY,
                    reason = "another JVM secure identity reset is already in progress"
                )
            }
            state.resetInProgress = true
        }

        return try {
            block()
        } finally {
            synchronized(lock) {
                val state = checkNotNull(states[key]) {
                    "JVM secure identity reset state disappeared before completion"
                }
                state.resetInProgress = false
                if (state.liveUsages == 0) states.remove(key)
            }
        }
    }

    private class State(
        var liveUsages: Int = 0,
        var resetInProgress: Boolean = false
    )

    private class StoreNamespace(
        private val store: JvmSecureIdentityStore,
        private val namespace: String
    ) {
        override fun equals(other: Any?): Boolean =
            other is StoreNamespace && store === other.store && namespace == other.namespace

        override fun hashCode(): Int = 31 * System.identityHashCode(store) + namespace.hashCode()
    }
}
