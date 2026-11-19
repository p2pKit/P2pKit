package dev.p2pkit.rpc.internal

import dev.p2pkit.core.AppId
import dev.p2pkit.core.PeerFingerprint
import dev.p2pkit.rpc.RpcFailure
import dev.p2pkit.rpc.RpcFailureKind
import dev.p2pkit.rpc.RpcFailurePhase
import dev.p2pkit.rpc.RpcTrust
import dev.p2pkit.rpc.RpcTrustPurpose
import dev.p2pkit.rpc.RpcTrustStore
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.CoroutineStart
import kotlinx.coroutines.async
import kotlinx.coroutines.test.runTest
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertFalse
import kotlin.test.assertSame
import kotlin.test.assertTrue

class RpcTrustReloadTest {
    private val appId = AppId("trust.reload.test")
    private val a = testFingerprint(1)
    private val b = testFingerprint(2)
    private val c = testFingerprint(3)
    private val d = testFingerprint(4)

    private inner class Store(var snapshot: Set<PeerFingerprint> = setOf(a, b)) : RpcTrustStore {
        var reads = 0
        val writes = mutableListOf<Set<PeerFingerprint>>()
        var readSnapshot: suspend () -> Set<PeerFingerprint> = { snapshot }

        override suspend fun load(appId: AppId, purpose: RpcTrustPurpose): Set<PeerFingerprint> {
            assertEquals(this@RpcTrustReloadTest.appId, appId)
            assertEquals(RpcTrustPurpose.HostClients, purpose)
            reads++
            return readSnapshot()
        }

        override suspend fun replace(appId: AppId, purpose: RpcTrustPurpose, fingerprints: Set<PeerFingerprint>) {
            assertEquals(this@RpcTrustReloadTest.appId, appId)
            assertEquals(RpcTrustPurpose.HostClients, purpose)
            writes += fingerprints.toSet()
            snapshot = fingerprints.toSet()
        }

        suspend fun open() = RpcTrust.load(appId, RpcTrustPurpose.HostClients, this)
    }

    @Test
    fun removesAllWithdrawnBeforeCleanupAndPublishesAdditionsAfterwardsWithoutWriting() = runTest {
        val store = Store(setOf(a, b, c))
        val trust = store.open()
        val committed = mutableSetOf(b, d)
        store.snapshot = committed
        val retired = mutableListOf<PeerFingerprint>()
        trust.onRevoke = { retired += it; assertEquals(listOf(b), trust.fingerprints()) }

        trust.reloadFromStore()
        assertEquals(setOf(a, c), retired.toSet())
        assertEquals(2, retired.size)
        assertEquals(setOf(b, d), trust.fingerprints().toSet())
        assertEquals(2, store.reads)
        assertTrue(store.writes.isEmpty())

        trust.reloadFromStore()
        assertEquals(2, retired.size)
        committed.clear()
        assertTrue(trust.isTrusted(d))

        trust.onRevoke = { retired += it; assertTrue(trust.fingerprints().isEmpty()) }
        trust.reloadFromStore()
        assertEquals(setOf(a, b, c, d), retired.toSet())
        assertTrue(trust.healthy)
        assertTrue(trust.fingerprints().isEmpty())
        assertTrue(store.writes.isEmpty())
    }

    @Test
    fun readsTheExistingPinLimitAndLatchesClosedOnOverflow() = runTest {
        val store = Store(emptySet())
        val trust = store.open()
        store.snapshot = (0 until 4096).map(::testFingerprint).toSet()
        trust.reloadFromStore()
        assertEquals(4096, trust.fingerprints().size)
        assertTrue(trust.healthy)
        store.snapshot = store.snapshot + testFingerprint(4096)
        assertStorageFailure(trust)
        assertEquals(4097, store.snapshot.size)
        assertTrue(store.writes.isEmpty())
    }

    @Test
    fun readFailureAndInconsistentSnapshotsCloseBeforeAnyRetirementOrNewGrant() = runTest {
        val malformed = object : Set<PeerFingerprint> by setOf(c) {
            override val size = 2
        }
        val unexpectedEntry = object : Set<PeerFingerprint> by setOf(c) {
            override val size = 0
        }
        val duplicateEntry = object : Set<PeerFingerprint> by setOf(c, d) {
            override fun iterator() = listOf(c, c).iterator()
        }
        val iteratorFailure = object : Set<PeerFingerprint> by setOf(c, d) {
            override fun iterator(): Iterator<PeerFingerprint> = error("Incomplete snapshot")
        }
        @Suppress("UNCHECKED_CAST")
        val invalidEntry = setOf("invalid pin") as Set<PeerFingerprint>
        val readers: List<suspend () -> Set<PeerFingerprint>> = listOf(
            { error("Private storage detail") },
            { throw CancellationException("Store did not return a complete snapshot") },
            { malformed },
            { unexpectedEntry },
            { duplicateEntry },
            { iteratorFailure },
            { invalidEntry },
        )
        for (read in readers) {
            val store = Store()
            val trust = store.open()
            store.readSnapshot = read
            var retirements = 0
            trust.onRevoke = { retirements++ }
            var sealed = false
            trust.onStorageFailure = {
                assertTrue(trust.fingerprints().isEmpty())
                assertFalse(trust.healthy)
                sealed = true
            }
            assertStorageFailure(trust)
            assertTrue(sealed)
            assertEquals(0, retirements)
            assertTrue(store.writes.isEmpty())
            store.readSnapshot = { setOf(b) }
            assertStorageFailure(trust)
            assertEquals(2, store.reads)
        }
    }

    @Test
    fun peerCleanupFailureSealsBeforeWholeHostCleanupAndNeverPublishesAdditions() = runTest {
        val store = Store()
        val trust = store.open()
        store.snapshot = setOf(b, c)
        var retired = false
        trust.onRevoke = {
            assertEquals(a, it)
            assertFalse(trust.isTrusted(a))
            assertTrue(trust.isTrusted(b))
            assertFalse(trust.isTrusted(c))
            retired = true
            error("Private transport detail")
        }
        var sealed = false
        trust.onStorageFailure = {
            assertTrue(trust.fingerprints().isEmpty())
            // This would deadlock if cleanup were called under the trust lock.
            assertFailsWith<RpcFailure> { trust.approve(d) }
            sealed = true
        }
        assertStorageFailure(trust)
        assertTrue(retired)
        assertTrue(sealed)
        assertTrue(store.writes.isEmpty())
    }

    @Test
    fun fatalRetirementPreservesTheOriginalErrorWhileSealingAllTrust() = runTest {
        val store = Store()
        val trust = store.open()
        store.snapshot = setOf(b)
        val original = object : Error("Test fatal retirement") { val cleanupOwner = Any() }
        trust.onRevoke = { throw original }
        trust.onStorageFailure = { assertFalse(trust.healthy); throw Error("Test fatal cleanup") }
        assertSame(original, assertFailsWith<Error> { trust.reloadFromStore() })
        assertTrue(trust.fingerprints().isEmpty())
    }

    @Test
    fun reloadsAndSdkMutationsSerializeWithConcurrentExternalCommits() = runTest {
        val store = Store()
        val trust = store.open()
        store.snapshot = setOf(b, c)
        val entered = CompletableDeferred<Unit>()
        val release = CompletableDeferred<Unit>()
        store.readSnapshot = {
            val observed = store.snapshot
            if (store.reads == 2) {
                entered.complete(Unit)
                release.await()
            }
            observed
        }
        val reload = async { trust.reloadFromStore() }
        entered.await()
        store.snapshot = setOf(c, d)
        val latest = async(start = CoroutineStart.UNDISPATCHED) { trust.reloadFromStore() }
        val revoke = async(start = CoroutineStart.UNDISPATCHED) { trust.revoke(c) }
        val approve = async(start = CoroutineStart.UNDISPATCHED) { trust.approve(a) }
        assertEquals(2, store.reads)
        assertTrue(store.writes.isEmpty())
        assertEquals(setOf(a, b), trust.fingerprints().toSet())
        release.complete(Unit)
        reload.await()
        latest.await()
        revoke.await()
        approve.await()
        assertEquals(3, store.reads)
        assertEquals(listOf(setOf(d), setOf(a, d)), store.writes)
        assertEquals(store.snapshot, trust.fingerprints().toSet())
    }

    @Test
    fun callerCancellationDuringRetirementCannotStrandAnExternallyCommittedUpdate() = runTest {
        val store = Store()
        val trust = store.open()
        store.snapshot = setOf(b, c)
        val entered = CompletableDeferred<Unit>()
        val release = CompletableDeferred<Unit>()
        trust.onRevoke = {
            entered.complete(Unit)
            release.await()
        }
        val reload = async { trust.reloadFromStore() }
        entered.await()
        reload.cancel()
        assertEquals(listOf(b), trust.fingerprints())
        release.complete(Unit)
        assertFailsWith<CancellationException> { reload.await() }
        assertTrue(trust.healthy)
        assertEquals(setOf(b, c), trust.fingerprints().toSet())
        assertTrue(store.writes.isEmpty())
    }

    private suspend fun assertStorageFailure(trust: RpcTrust) {
        val failure = assertFailsWith<RpcFailure> { trust.reloadFromStore() }
        assertEquals(RpcFailureKind.TrustStorage, failure.kind)
        assertEquals(RpcFailurePhase.Trust, failure.phase)
        assertFalse(trust.healthy)
        assertTrue(trust.fingerprints().isEmpty())
    }
}
