package dev.p2pkit.core.internal

import dev.p2pkit.core.AppId
import dev.p2pkit.core.LocalIdentityFailureKind
import dev.p2pkit.core.LocalIdentityRecovery
import dev.p2pkit.core.P2pError
import dev.p2pkit.core.P2pKit
import dev.p2pkit.core.P2pLogger
import dev.p2pkit.core.dsl.P2pKitBuilder
import dev.p2pkit.core.dsl.jvmSecureIdentityStore
import dev.p2pkit.core.security.EncodedIdentityKeyPair
import dev.p2pkit.core.security.IdentityDerivation
import dev.p2pkit.core.security.IdentityKeyRecordCodec
import dev.p2pkit.core.security.IdentityNamespace
import dev.p2pkit.core.security.JvmSecureIdentityStore
import dev.p2pkit.core.security.SecureIdentityService
import dev.p2pkit.core.security.platformSecurityCryptography
import dev.p2pkit.core.security.resetJvmSecureIdentity
import dev.p2pkit.core.testfixtures.FakeDataTransport
import dev.p2pkit.core.transport.TransportContext
import dev.p2pkit.core.transport.TransportFactory
import dev.p2pkit.core.transport.TransportPair
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.runBlocking
import java.util.Collections
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicInteger
import java.util.concurrent.atomic.AtomicReference
import kotlin.concurrent.thread
import kotlin.test.Test
import kotlin.test.assertContentEquals
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertFalse
import kotlin.test.assertNotEquals
import kotlin.test.assertNotNull
import kotlin.test.assertSame
import kotlin.test.assertTrue

class JvmSecureIdentityStoreAdapterTest {
    private val namespace: IdentityNamespace =
        IdentityDerivation.namespace(AppId("jvm-store-test"), platformSecurityCryptography())

    @Test
    fun firstCreationCommitsRereadsAndWipesEveryTransferredSecretArray() {
        val store = RecordingJvmStore()
        val adapter = JvmSecureIdentityStoreAdapter(store)
        val candidate = pair(1)
        var fingerprintCalls = 0

        val loaded = adapter.loadOrCreate(
            namespace,
            fingerprintDigest = {
                fingerprintCalls++
                ByteArray(32) { 3 }
            },
            generate = { candidate }
        )

        assertEquals(1, fingerprintCalls)
        assertEquals(1, store.putCount)
        assertContentEquals(ByteArray(32), candidate.privateKeyBytes())
        assertTrue(assertNotNull(store.retainedPutInput).all { it == 0.toByte() })
        assertTrue(assertNotNull(store.lastReturnedRead).all { it == 0.toByte() })
        assertFalse(loaded.privateKeyBytes().all { it == 0.toByte() })

        val callerCopy = loaded.privateKeyBytes()
        callerCopy.fill(0)
        assertFalse(loaded.privateKeyBytes().all { it == 0.toByte() })

        val reloaded = adapter.loadOrCreate(
            namespace,
            fingerprintDigest = { ByteArray(32) },
            generate = { error("committed identity must win") }
        )
        assertContentEquals(loaded.privateKeyBytes(), reloaded.privateKeyBytes())
    }

    @Test
    fun concurrentFirstCreationTenRoundsReturnsOneWinnerAndClearsEveryCandidate() {
        repeat(10) { round ->
            val store = RecordingJvmStore()
            val adapter = JvmSecureIdentityStoreAdapter(store)
            val workers = 16
            val ready = CountDownLatch(workers)
            val start = CountDownLatch(1)
            val done = CountDownLatch(workers)
            val sequence = AtomicInteger()
            val candidates = Collections.synchronizedList(mutableListOf<EncodedIdentityKeyPair>())
            val outcomes = Collections.synchronizedList(mutableListOf<ByteArray>())
            val failures = Collections.synchronizedList(mutableListOf<Throwable>())

            repeat(workers) { worker ->
                thread(name = "secure-store-creator-$round-$worker") {
                    ready.countDown()
                    try {
                        start.await()
                        val loaded = adapter.loadOrCreate(
                            namespace,
                            fingerprintDigest = { ByteArray(32) },
                            generate = {
                                pair(sequence.incrementAndGet()).also(candidates::add)
                            }
                        )
                        outcomes.add(loaded.privateKeyBytes())
                    } catch (failure: Throwable) {
                        failures.add(failure)
                    } finally {
                        done.countDown()
                    }
                }
            }

            val allReady = ready.await(5, TimeUnit.SECONDS)
            start.countDown()
            val allDone = done.await(10, TimeUnit.SECONDS)
            assertTrue(allReady, "round $round workers did not reach barrier")
            assertTrue(allDone, "round $round workers did not complete")
            assertTrue(failures.isEmpty(), "round $round unexpected failures: $failures")
            assertEquals(workers, outcomes.size)
            outcomes.drop(1).forEach { assertContentEquals(outcomes.first(), it) }
            candidates.forEach { assertContentEquals(ByteArray(32), it.privateKeyBytes()) }
            assertEquals(1, store.entryCount { !it.endsWith(".reset.pending") })
        }
    }

    @Test
    fun corruptCommittedRecordFailsClosedWithoutGenerating() {
        val store = RecordingJvmStore()
        val adapter = JvmSecureIdentityStoreAdapter(store)
        adapter.loadOrCreate(namespace, { ByteArray(32) }, { pair(4) })
        val identityKey = store.keys().single { !it.endsWith(".reset.pending") }
        store.force(identityKey, ByteArray(IdentityKeyRecordCodec.RECORD_SIZE))

        val error = assertFailsWith<P2pError.LocalIdentityUnavailable> {
            adapter.loadOrCreate(namespace, { ByteArray(32) }, { error("must not rotate") })
        }

        assertEquals(LocalIdentityFailureKind.CORRUPT_RECORD, error.kind)
        assertEquals(LocalIdentityRecovery.EXPLICIT_RESET_REQUIRED, error.recovery)
    }

    @Test
    fun putWinnerThatDiffersFromRereadIsStoreContractViolation() {
        val store = RecordingJvmStore().apply { changeDurableValueAfterPut = true }
        val adapter = JvmSecureIdentityStoreAdapter(store)

        val error = assertFailsWith<P2pError.LocalIdentityUnavailable> {
            adapter.loadOrCreate(namespace, { ByteArray(32) }, { pair(5) })
        }

        assertEquals(LocalIdentityFailureKind.STORE_CONTRACT_VIOLATION, error.kind)
        assertEquals(LocalIdentityRecovery.FIX_PLATFORM_CONFIGURATION, error.recovery)
    }

    @Test
    fun invalidFingerprintCallbackClearsDecodedWinner() {
        val store = RecordingJvmStore()
        val adapter = JvmSecureIdentityStoreAdapter(store)
        val candidate = pair(6)

        val error = assertFailsWith<P2pError.LocalIdentityUnavailable> {
            adapter.loadOrCreate(namespace, { ByteArray(31) }, { candidate })
        }

        assertEquals(LocalIdentityFailureKind.STORE_CONTRACT_VIOLATION, error.kind)
        assertContentEquals(ByteArray(32), candidate.privateKeyBytes())
    }

    @Test
    fun interruptedResetBlocksOrdinaryLoadAndOnlyAnotherExplicitResetCompletesIt() {
        val store = RecordingJvmStore()
        val adapter = JvmSecureIdentityStoreAdapter(store)
        val original = adapter.loadOrCreate(namespace, { ByteArray(32) }, { pair(7) })
        store.failIdentityDelete = true

        val resetFailure = assertFailsWith<P2pError.LocalIdentityUnavailable> {
            adapter.reset(namespace)
        }
        assertEquals(LocalIdentityFailureKind.TEMPORARILY_UNAVAILABLE, resetFailure.kind)

        val pending = assertFailsWith<P2pError.LocalIdentityUnavailable> {
            adapter.loadOrCreate(namespace, { ByteArray(32) }, { pair(8) })
        }
        assertEquals(LocalIdentityFailureKind.RESET_PENDING, pending.kind)
        assertEquals(LocalIdentityRecovery.EXPLICIT_RESET_REQUIRED, pending.recovery)

        store.failIdentityDelete = false
        adapter.reset(namespace)
        assertTrue(store.keys().none { it.endsWith(".reset.pending") })
        val replacement = adapter.loadOrCreate(namespace, { ByteArray(32) }, { pair(8) })
        assertNotEquals(original.privateKeyBytes().toList(), replacement.privateKeyBytes().toList())
    }

    @Test
    fun untypedStoreExceptionIsRetryableAndRetainsCause() {
        val cause = IllegalStateException("vault locked")
        val store = object : JvmSecureIdentityStore {
            override fun read(namespace: String): ByteArray? = throw cause
            override fun putIfAbsent(namespace: String, value: ByteArray): ByteArray = error("unused")
            override fun delete(namespace: String): Boolean = error("unused")
        }

        val error = assertFailsWith<P2pError.LocalIdentityUnavailable> {
            JvmSecureIdentityStoreAdapter(store)
                .loadOrCreate(namespace, { ByteArray(32) }, { pair(9) })
        }

        assertEquals(LocalIdentityFailureKind.TEMPORARILY_UNAVAILABLE, error.kind)
        assertEquals(LocalIdentityRecovery.RETRY, error.recovery)
        assertEquals(cause, error.cause)
    }

    @Test
    fun cancellationFromJvmStorePropagatesUnchanged() {
        val cancellation = CancellationException("cancel JVM store read")
        val store = object : JvmSecureIdentityStore {
            override fun read(namespace: String): ByteArray? = throw cancellation
            override fun putIfAbsent(namespace: String, value: ByteArray): ByteArray = error("unused")
            override fun delete(namespace: String): Boolean = error("unused")
        }

        val thrown = assertFailsWith<CancellationException> {
            JvmSecureIdentityStoreAdapter(store)
                .loadOrCreate(namespace, { ByteArray(32) }, { pair(10) })
        }

        assertSame(cancellation, thrown)
    }

    @Test
    fun jvmBuilderExtensionInstallsProtectedStoreAdapter() {
        val builder = P2pKitBuilder()
        builder.jvmSecureIdentityStore(RecordingJvmStore())

        assertTrue(builder.secureIdentityStorage is JvmSecureIdentityStoreAdapter)
    }

    @Test
    fun builderStoreFeedsSecureKitAndResetRemainsBlockedUntilTerminalStop() = runBlocking {
        val appId = AppId("jvm-builder-secure-kit")
        val store = RecordingJvmStore()
        val kit = P2pKit.create {
            this.appId = appId
            deviceName = "secure-jvm-test"
            jvmSecureIdentityStore(store)
            transports { register(JvmIdentityTestFactory(FakeDataTransport())) }
        }

        try {
            assertTrue(kit.localPeerId.value.startsWith("p2id2-"))
            assertNotNull(kit.localFingerprint)
            val blocked = assertFailsWith<P2pError.LocalIdentityUnavailable> {
                resetJvmSecureIdentity(appId, store)
            }
            assertEquals(LocalIdentityFailureKind.LIVE_IDENTITY_IN_USE, blocked.kind)
        } finally {
            kit.stop()
        }

        resetJvmSecureIdentity(appId, store)
        assertTrue(store.keys().isEmpty())
    }

    @Test
    fun explicitJvmResetRejectsLiveUsageThenAllowsIdempotentReleaseAndReset() {
        val store = RecordingJvmStore()
        val adapter = JvmSecureIdentityStoreAdapter(store)
        adapter.loadOrCreate(namespace, { ByteArray(32) }, { pair(11) })
        val usage = adapter.acquireUsage(namespace)

        try {
            val error = assertFailsWith<P2pError.LocalIdentityUnavailable> {
                resetJvmSecureIdentity(AppId("jvm-store-test"), store)
            }
            assertEquals(LocalIdentityFailureKind.LIVE_IDENTITY_IN_USE, error.kind)
            assertEquals(LocalIdentityRecovery.RETRY, error.recovery)
        } finally {
            usage.release()
            usage.release()
        }

        resetJvmSecureIdentity(AppId("jvm-store-test"), store)
        assertTrue(store.keys().isEmpty())
    }

    @Test
    fun resetInProgressRejectsNewUsageAndReleasesGuardAfterCompletion() {
        val store = RecordingJvmStore()
        val adapter = JvmSecureIdentityStoreAdapter(store)
        adapter.loadOrCreate(namespace, { ByteArray(32) }, { pair(12) })
        val deleteEntered = CountDownLatch(1)
        val allowDelete = CountDownLatch(1)
        val resetDone = CountDownLatch(1)
        val resetFailure = AtomicReference<Throwable?>(null)
        store.blockIdentityDelete = deleteEntered to allowDelete

        thread(name = "secure-identity-reset") {
            try {
                resetJvmSecureIdentity(AppId("jvm-store-test"), store)
            } catch (failure: Throwable) {
                resetFailure.set(failure)
            } finally {
                resetDone.countDown()
            }
        }

        assertTrue(deleteEntered.await(5, TimeUnit.SECONDS), "reset did not reach deletion")
        try {
            val blocked = assertFailsWith<P2pError.LocalIdentityUnavailable> {
                adapter.acquireUsage(namespace)
            }
            assertEquals(LocalIdentityFailureKind.TEMPORARILY_UNAVAILABLE, blocked.kind)
            assertEquals(LocalIdentityRecovery.RETRY, blocked.recovery)
        } finally {
            allowDelete.countDown()
        }
        assertTrue(resetDone.await(5, TimeUnit.SECONDS), "reset did not complete")
        assertEquals(null, resetFailure.get())

        val usage = adapter.acquireUsage(namespace)
        usage.release()
    }

    @Test
    fun publicJvmResetRotatesAValidatedProviderIdentity() {
        val appId = AppId("jvm-reset-rotation")
        val store = RecordingJvmStore()
        val service = SecureIdentityService(
            platformSecurityCryptography(),
            JvmSecureIdentityStoreAdapter(store)
        )
        val before = service.loadOrCreate(appId)
        try {
            resetJvmSecureIdentity(appId, store)
            val after = service.loadOrCreate(appId)
            try {
                assertNotEquals(before.peerId, after.peerId)
                assertNotEquals(before.fingerprint, after.fingerprint)
            } finally {
                after.clearPrivate()
            }
        } finally {
            before.clearPrivate()
        }
    }

    @Test
    fun absentJvmDefaultFailsClosedInsteadOfUsingPlaintextStorage() {
        val error = assertFailsWith<P2pError.LocalIdentityUnavailable> {
            defaultSecureIdentityStorage(AppId("requires-store"), P2pLogger.NoOp)
        }
        assertEquals(LocalIdentityFailureKind.STORE_NOT_CONFIGURED, error.kind)
        assertEquals(LocalIdentityRecovery.CONFIGURE_STORE, error.recovery)
    }

    @Test
    fun missingJvmStoreFailsBeforeAnyTransportFactoryRuns() {
        var factoryBuilds = 0
        val error = assertFailsWith<P2pError.LocalIdentityUnavailable> {
            P2pKit.create {
                appId = AppId("missing-jvm-secure-store")
                deviceName = "must-not-build-transport"
                transports {
                    register(object : TransportFactory {
                        override fun build(context: TransportContext): TransportPair {
                            factoryBuilds++
                            return TransportPair(data = FakeDataTransport(), discovery = null)
                        }
                    })
                }
            }
        }

        assertEquals(LocalIdentityFailureKind.STORE_NOT_CONFIGURED, error.kind)
        assertEquals(0, factoryBuilds)
    }

    private fun pair(seed: Int): EncodedIdentityKeyPair {
        val privateKey = ByteArray(32) { (seed + it).toByte() }
        val publicKey = ByteArray(32) { (seed * 3 + it).toByte() }
        return EncodedIdentityKeyPair(privateKey, publicKey)
    }

    private class RecordingJvmStore : JvmSecureIdentityStore {
        private val entries = linkedMapOf<String, ByteArray>()
        var retainedPutInput: ByteArray? = null
            private set
        var lastReturnedRead: ByteArray? = null
            private set
        var putCount: Int = 0
            private set
        var changeDurableValueAfterPut: Boolean = false
        var failIdentityDelete: Boolean = false
        var blockIdentityDelete: Pair<CountDownLatch, CountDownLatch>? = null

        @Synchronized
        override fun read(namespace: String): ByteArray? =
            entries[namespace]?.copyOf()?.also { lastReturnedRead = it }

        @Synchronized
        override fun putIfAbsent(namespace: String, value: ByteArray): ByteArray {
            putCount++
            retainedPutInput = value
            val winner = entries.getOrPut(namespace) { value.copyOf() }
            val result = winner.copyOf()
            if (changeDurableValueAfterPut && !namespace.endsWith(".reset.pending")) {
                entries[namespace] = winner.copyOf().also {
                    it[it.lastIndex] = (it.last().toInt() xor 1).toByte()
                }
            }
            return result
        }

        @Synchronized
        override fun delete(namespace: String): Boolean {
            if (failIdentityDelete && !namespace.endsWith(".reset.pending")) {
                throw IllegalStateException("simulated identity delete failure")
            }
            if (!namespace.endsWith(".reset.pending")) {
                blockIdentityDelete?.let { (entered, proceed) ->
                    entered.countDown()
                    check(proceed.await(5, TimeUnit.SECONDS)) {
                        "timed out waiting to continue identity deletion"
                    }
                }
            }
            return entries.remove(namespace) != null
        }

        @Synchronized
        fun force(namespace: String, value: ByteArray) {
            entries[namespace] = value.copyOf()
        }

        @Synchronized
        fun keys(): Set<String> = entries.keys.toSet()

        @Synchronized
        fun entryCount(predicate: (String) -> Boolean): Int = entries.keys.count(predicate)
    }

    private class JvmIdentityTestFactory(
        private val transport: FakeDataTransport
    ) : TransportFactory {
        override fun build(context: TransportContext): TransportPair =
            TransportPair(data = transport, discovery = null)
    }
}
