package dev.p2pkit.core.internal

import dev.p2pkit.core.AppId
import dev.p2pkit.core.LocalIdentityFailureKind
import dev.p2pkit.core.P2pError
import dev.p2pkit.core.security.EncodedIdentityKeyPair
import dev.p2pkit.core.security.IdentityNamespace
import kotlin.test.Test
import kotlin.test.assertContentEquals
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertFalse
import kotlin.test.assertNull
import kotlin.test.assertSame
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.CoroutineDispatcher
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.DelicateCoroutinesApi
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.async
import kotlinx.coroutines.newFixedThreadPoolContext
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.supervisorScope
import kotlinx.coroutines.withTimeout
import kotlinx.coroutines.yield
import platform.Foundation.NSLock

/** Real storage/NSLock code with namespace-aware, thread-safe Keychain/marker substitutes. */
class IosSecureIdentityOperationLocksTest {
    @Test
    fun heldNamespaceDoesNotBlockAnotherStorageInstancesCreateOrReset() = withWorkers { workers, backend ->
        val baseline = IosSecureIdentityOperationLocks.entryCountForTest()
        val first = IosSecureIdentityStorage(backend, backend)
        val second = IosSecureIdentityStorage(backend, backend)
        val namespaceA = namespace(131)
        val namespaceB = namespace(132)
        val entered = CompletableDeferred<Unit>()
        val release = CompletableDeferred<Unit>()
        try {
            val owner = async(workers) {
                loadPublic(first, namespaceA) {
                    entered.complete(Unit)
                    awaitGate(release)
                    keyPair(11)
                }
            }
            withTimeout(5_000) { entered.await() }
            val independent = async(workers) {
                val result = loadPublic(second, namespaceB) { keyPair(21) }
                second.reset(namespaceB)
                result
            }

            assertContentEquals(publicKey(21), withTimeout(5_000) { independent.await() })
            assertFalse(owner.isCompleted, "B must complete while A still owns its namespace")
            assertNull(backend.read(namespaceB.storageKey))
            assertNull(backend.readCommitted(namespaceB))
            assertNull(backend.readResetPending(namespaceB))
            release.complete(Unit)
            assertContentEquals(publicKey(11), withTimeout(5_000) { owner.await() })
            assertEquals(baseline, IosSecureIdentityOperationLocks.entryCountForTest())
        } finally {
            release.complete(Unit)
        }
    }

    @Test
    fun sameNamespaceKeepsQueuedEntryAcrossInstancesAndReloadsOneDurableWinner() = withWorkers { workers, backend ->
        val baseline = IosSecureIdentityOperationLocks.entryCountForTest()
        val firstStorage = IosSecureIdentityStorage(backend, backend)
        val secondStorage = IosSecureIdentityStorage(backend, backend)
        val thirdStorage = IosSecureIdentityStorage(backend, backend)
        val namespace = namespace(133)
        val firstEntered = CompletableDeferred<Unit>()
        val releaseFirst = CompletableDeferred<Unit>()
        val secondEntered = CompletableDeferred<Unit>()
        val releaseSecond = CompletableDeferred<Unit>()
        try {
            val first = async(workers) {
                loadPublic(firstStorage, namespace) {
                    firstEntered.complete(Unit)
                    awaitGate(releaseFirst)
                    keyPair(31)
                }
            }
            withTimeout(5_000) { firstEntered.await() }
            val second = async(workers) {
                loadPublic(
                    storage = secondStorage,
                    namespace = namespace,
                    fingerprintDigest = { pair ->
                        secondEntered.complete(Unit)
                        awaitGate(releaseSecond)
                        fingerprint(pair)
                    },
                    generate = { error("same-namespace contender must not generate") }
                )
            }
            awaitUsers(namespace.storageKey, 2)
            assertFalse(second.isCompleted)
            releaseFirst.complete(Unit)
            assertContentEquals(publicKey(31), withTimeout(5_000) { first.await() })
            withTimeout(5_000) { secondEntered.await() }

            val late = async(workers) {
                loadPublic(thirdStorage, namespace) { error("durable winner must not rotate") }
            }
            awaitUsers(namespace.storageKey, 2)
            assertEquals(baseline + 1, IosSecureIdentityOperationLocks.entryCountForTest())
            assertFalse(late.isCompleted, "late callers must retain the same still-owned entry")
            releaseSecond.complete(Unit)

            assertContentEquals(publicKey(31), withTimeout(5_000) { second.await() })
            assertContentEquals(publicKey(31), withTimeout(5_000) { late.await() })
            assertEquals(1, backend.addCalls(namespace.storageKey))
            assertEquals(baseline, IosSecureIdentityOperationLocks.entryCountForTest())
        } finally {
            releaseFirst.complete(Unit)
            releaseSecond.complete(Unit)
        }
    }

    @Test
    fun generationFailuresCancellationAndTransientNamespacesReleaseEntries() {
        val baseline = IosSecureIdentityOperationLocks.entryCountForTest()
        val backend = ConcurrentIdentityBackend()
        val storage = IosSecureIdentityStorage(backend, backend)
        try {
            val failedNamespace = namespace(134)
            val failure = IllegalStateException("injected identity generation failure")
            val error = assertFailsWith<P2pError.LocalIdentityUnavailable> {
                loadPublic(storage, failedNamespace) { throw failure }
            }
            assertEquals(LocalIdentityFailureKind.KEY_GENERATION_FAILED, error.kind)
            assertSame(failure, error.cause)
            val cancellation = CancellationException("cancel identity generation")
            assertSame(cancellation, assertFailsWith<CancellationException> {
                loadPublic(storage, failedNamespace) { throw cancellation }
            })
            assertEquals(baseline, IosSecureIdentityOperationLocks.entryCountForTest())

            repeat(32) { index ->
                val transient = namespace(160 + index)
                assertContentEquals(publicKey(index), loadPublic(storage, transient) { keyPair(index) })
                storage.reset(transient)
                assertEquals(baseline, IosSecureIdentityOperationLocks.entryCountForTest())
            }
        } finally {
            backend.clear()
        }
    }

    private fun loadPublic(
        storage: IosSecureIdentityStorage,
        namespace: IdentityNamespace,
        fingerprintDigest: (EncodedIdentityKeyPair) -> ByteArray = ::fingerprint,
        generate: () -> EncodedIdentityKeyPair
    ): ByteArray {
        val loaded = storage.loadOrCreate(namespace, fingerprintDigest, generate)
        return try {
            loaded.publicKeyBytes()
        } finally {
            loaded.clearPrivate()
        }
    }

    private suspend fun awaitUsers(storageKey: String, count: Int) {
        withTimeout(5_000) {
            while (IosSecureIdentityOperationLocks.usersForTest(storageKey) != count) yield()
        }
    }

    private fun awaitGate(gate: CompletableDeferred<Unit>) = runBlocking {
        withTimeout(5_000) { gate.await() }
    }

    @OptIn(DelicateCoroutinesApi::class, ExperimentalCoroutinesApi::class)
    private fun withWorkers(
        block: suspend CoroutineScope.(CoroutineDispatcher, ConcurrentIdentityBackend) -> Unit
    ) = runBlocking {
        // Blocking NSLock callers need distinct owned threads, independent of
        // the host's Default dispatcher width; no workers survive the test.
        val workers = newFixedThreadPoolContext(3, "ios-identity-lock-test")
        val backend = ConcurrentIdentityBackend()
        try {
            supervisorScope { block(workers, backend) }
        } finally {
            // supervisorScope drains all children before either resource is released.
            try {
                workers.close()
            } finally {
                backend.clear()
            }
        }
    }

    private fun namespace(seed: Int): IdentityNamespace {
        val appId = AppId("dev.p2pkit.ios-operation-locks.$seed")
        return IdentityNamespace(appId, appId.value.encodeToByteArray(), ByteArray(32) { (seed + it).toByte() })
    }

    private fun keyPair(seed: Int): EncodedIdentityKeyPair =
        EncodedIdentityKeyPair(ByteArray(32) { (seed + it).toByte() }, publicKey(seed))

    private fun publicKey(seed: Int): ByteArray = ByteArray(32) { (seed + 64 + it).toByte() }

    private fun fingerprint(pair: EncodedIdentityKeyPair): ByteArray = pair.publicKeyBytes()

    private class ConcurrentIdentityBackend : IosIdentityKeychain, IosIdentityMarkerStore {
        private val guard = NSLock()
        private val records = mutableMapOf<String, ByteArray>()
        private val committed = mutableMapOf<String, ByteArray>()
        private val resetPending = mutableMapOf<String, ByteArray>()
        private val adds = mutableMapOf<String, Int>()

        override fun read(account: String): ByteArray? = guarded { records[account]?.copyOf() }

        override fun add(account: String, record: ByteArray): Boolean = guarded {
            adds[account] = (adds[account] ?: 0) + 1
            if (account in records) {
                false
            } else {
                records[account] = record.copyOf()
                true
            }
        }

        override fun delete(account: String) {
            guarded { records.remove(account)?.fill(0) }
        }

        override fun readCommitted(namespace: IdentityNamespace): ByteArray? =
            guarded { committed[namespace.storageKey]?.copyOf() }

        override fun writeCommitted(namespace: IdentityNamespace, marker: ByteArray) {
            guarded { committed.put(namespace.storageKey, marker.copyOf())?.fill(0) }
        }

        override fun deleteCommitted(namespace: IdentityNamespace) {
            guarded { committed.remove(namespace.storageKey)?.fill(0) }
        }

        override fun readResetPending(namespace: IdentityNamespace): ByteArray? =
            guarded { resetPending[namespace.storageKey]?.copyOf() }

        override fun writeResetPending(namespace: IdentityNamespace, marker: ByteArray) {
            guarded { resetPending.put(namespace.storageKey, marker.copyOf())?.fill(0) }
        }

        override fun deleteResetPending(namespace: IdentityNamespace) {
            guarded { resetPending.remove(namespace.storageKey)?.fill(0) }
        }

        fun addCalls(account: String): Int = guarded { adds[account] ?: 0 }

        fun clear() {
            guarded {
                listOf(records, committed, resetPending).forEach { map ->
                    map.values.forEach { it.fill(0) }
                    map.clear()
                }
                adds.clear()
            }
        }

        private fun <T> guarded(block: () -> T): T {
            guard.lock()
            return try {
                block()
            } finally {
                guard.unlock()
            }
        }
    }
}
