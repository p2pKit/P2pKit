package dev.p2pkit.rpc.internal

import dev.p2pkit.core.AppId
import dev.p2pkit.core.PeerFingerprint
import dev.p2pkit.rpc.RpcFailure
import dev.p2pkit.rpc.RpcTrust
import dev.p2pkit.rpc.RpcTrustPurpose
import dev.p2pkit.rpc.RpcTrustStore
import kotlinx.coroutines.test.runTest
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertFalse
import kotlin.test.assertSame
import kotlin.test.assertTrue

/** Error propagation must not leave previously cached authorization live after uncertain persistence. */
class RpcTrustFatalFailureTest {
    private val appId = AppId("rpc.fatal.trust.test")
    private val first = testFingerprint(1)
    private val second = testFingerprint(2)
    private val third = testFingerprint(3)

    // An owned field prevents coroutine stacktrace recovery from copying the reporting error. This
    // exercises exact resource/error ownership without disabling recovery or promising it for plain Error.
    private class ReportingError(message: String) : Error(message) {
        val owner = Any()
    }

    private class Store(initial: Set<PeerFingerprint>) : RpcTrustStore {
        var pins = initial
        var failure: Throwable? = null
        var beforeReplace: (Set<PeerFingerprint>) -> Unit = {}
        var writes = 0
        var attempted: Set<PeerFingerprint>? = null
        override suspend fun load(appId: AppId, purpose: RpcTrustPurpose): Set<PeerFingerprint> = pins.toSet()
        override suspend fun replace(appId: AppId, purpose: RpcTrustPurpose, fingerprints: Set<PeerFingerprint>) {
            writes++
            attempted = fingerprints.toSet()
            beforeReplace(fingerprints)
            failure?.let { throw it }
            pins = fingerprints.toSet()
        }
    }

    private fun assertSealed(trust: RpcTrust) {
        assertFalse(trust.healthy)
        assertTrue(trust.fingerprints().isEmpty())
        for (pin in listOf(first, second, third)) assertFalse(trust.isTrusted(pin))
    }

    @Test fun approvalErrorSealsOldGrantsBeforeCleanupAndPreservesOriginalError() = runTest {
        val store = Store(setOf(first, second))
        val trust = RpcTrust.load(appId, RpcTrustPurpose.HostClients, store)
        val original = ReportingError("synthetic persistence error")
        val cleanup = ReportingError("synthetic reporting error")
        store.failure = original
        var notified = 0
        var sealedAtCleanup = false
        trust.onStorageFailure = {
            notified++
            sealedAtCleanup = !trust.healthy && trust.fingerprints().isEmpty()
            throw cleanup
        }
        val observed = assertFailsWith<ReportingError> { trust.approve(third) }
        assertSealed(trust)
        assertEquals(1, notified)
        assertTrue(sealedAtCleanup)
        assertEquals(1, store.writes)
        assertEquals(setOf(first, second, third), store.attempted)
        assertEquals(setOf(first, second), store.pins)
        assertSame(original, observed)
        assertTrue(original.suppressedExceptions.isEmpty())
        assertTrue(cleanup.suppressedExceptions.isEmpty())
        assertFailsWith<RpcFailure> { trust.approve(third) }
        assertEquals(1, store.writes)
    }

    @Test fun revocationPersistenceErrorSealsEveryGrantBeforeCleanupAndPreservesOriginalError() = runTest {
        val store = Store(setOf(first, second))
        val trust = RpcTrust.load(appId, RpcTrustPurpose.HostClients, store)
        val original = ReportingError("synthetic revocation persistence error")
        val cleanup = ReportingError("synthetic reporting error")
        store.failure = original
        var revoked = 0
        var notified = 0
        var sealedAtCleanup = false
        trust.onRevoke = {
            revoked++
            assertEquals(first, it)
            assertFalse(trust.isTrusted(first))
            assertTrue(trust.isTrusted(second))
        }
        trust.onStorageFailure = {
            notified++
            sealedAtCleanup = !trust.healthy && trust.fingerprints().isEmpty()
            throw cleanup
        }
        val observed = assertFailsWith<ReportingError> { trust.revoke(first) }
        assertSealed(trust)
        assertEquals(1, revoked)
        assertEquals(1, notified)
        assertTrue(sealedAtCleanup)
        assertEquals(1, store.writes)
        assertEquals(setOf(second), store.attempted)
        assertEquals(setOf(first, second), store.pins)
        assertSame(original, observed)
        assertTrue(original.suppressedExceptions.isEmpty())
        assertFailsWith<RpcFailure> { trust.revoke(second) }
        assertEquals(1, store.writes)
    }

    @Test fun transportErrorSealsBeforePersistenceWithoutSkippingTheRequestedDurableRevocation() = runTest {
        val store = Store(setOf(first, second))
        val trust = RpcTrust.load(appId, RpcTrustPurpose.HostClients, store)
        val original = ReportingError("synthetic transport retirement error")
        var notified = 0
        trust.onRevoke = { throw original }
        store.beforeReplace = { next -> assertSealed(trust); assertEquals(setOf(second), next) }
        trust.onStorageFailure = { notified++; assertSealed(trust) }
        val observed = assertFailsWith<ReportingError> { trust.revoke(first) }
        assertSealed(trust)
        assertEquals(1, notified)
        assertEquals(1, store.writes)
        assertEquals(setOf(second), store.pins)
        assertSame(original, observed)
        assertTrue(original.suppressedExceptions.isEmpty())
    }

    @Test fun transportErrorRemainsPrimaryWhenPersistenceAndFailureCleanupAlsoThrowErrors() = runTest {
        val store = Store(setOf(first, second))
        val trust = RpcTrust.load(appId, RpcTrustPurpose.HostClients, store)
        val transport = ReportingError("synthetic transport error")
        val persistence = ReportingError("synthetic persistence error")
        val cleanup = ReportingError("synthetic cleanup error")
        trust.onRevoke = { throw transport }
        store.failure = persistence
        var notified = 0
        var sealedAtCleanup = false
        trust.onStorageFailure = {
            notified++
            sealedAtCleanup = !trust.healthy && trust.fingerprints().isEmpty()
            throw cleanup
        }
        val observed = assertFailsWith<ReportingError> { trust.revoke(first) }
        assertSealed(trust)
        assertEquals(1, store.writes)
        assertEquals(setOf(second), store.attempted)
        assertEquals(1, notified)
        assertTrue(sealedAtCleanup)
        assertSame(transport, observed)
        assertTrue(transport.suppressedExceptions.isEmpty())
        assertTrue(persistence.suppressedExceptions.isEmpty())
        assertTrue(cleanup.suppressedExceptions.isEmpty())
    }

    @Test fun cleanupErrorAfterOrdinaryStorageFailureIsPreservedAndCallbackCanObserveSealedAdmission() = runTest {
        for (approval in listOf(false, true)) {
            val store = Store(setOf(first, second))
            val trust = RpcTrust.load(appId, RpcTrustPurpose.HostClients, store)
            val cleanup = ReportingError("synthetic cleanup ownership error")
            store.failure = IllegalStateException("synthetic private storage failure")
            var notified = 0
            trust.onStorageFailure = {
                notified++
                assertSealed(trust)
                // A callback outside the trust mutex can re-enter and observe refusal, not deadlock.
                assertFailsWith<RpcFailure> { trust.approve(third) }
                throw cleanup
            }
            val observed = assertFailsWith<ReportingError> {
                if (approval) trust.approve(third) else trust.revoke(first)
            }
            assertSealed(trust)
            assertEquals(1, store.writes)
            assertEquals(1, notified)
            assertSame(cleanup, observed)
            assertTrue(cleanup.suppressedExceptions.isEmpty())
        }
    }

    @Test fun ordinaryTransportFailureAlsoSealsBeforePersistenceAndRetainsSanitizedFailure() = runTest {
        val store = Store(setOf(first, second))
        val trust = RpcTrust.load(appId, RpcTrustPurpose.HostClients, store)
        trust.onRevoke = { throw IllegalStateException("synthetic private transport failure") }
        store.beforeReplace = { next -> assertSealed(trust); assertEquals(setOf(second), next) }
        var notified = 0
        trust.onStorageFailure = { notified++; assertSealed(trust) }
        assertFailsWith<RpcFailure> { trust.revoke(first) }
        assertSealed(trust)
        assertEquals(1, store.writes)
        assertEquals(setOf(second), store.pins)
        assertEquals(1, notified)
    }
}
