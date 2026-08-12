@file:OptIn(kotlinx.cinterop.ExperimentalForeignApi::class)

package dev.p2pkit.core.internal

import dev.p2pkit.core.AppId
import dev.p2pkit.core.LocalIdentityFailureKind
import dev.p2pkit.core.P2pError
import dev.p2pkit.core.security.EncodedIdentityKeyPair
import dev.p2pkit.core.security.IdentityKeyRecordCodec
import dev.p2pkit.core.security.IdentityNamespace
import dev.p2pkit.core.security.IdentityStateMarkerCodec
import kotlin.random.Random
import kotlin.test.Test
import kotlin.test.assertContentEquals
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertNotNull
import kotlin.test.assertNull
import kotlin.test.assertSame
import kotlinx.coroutines.CancellationException
import kotlinx.cinterop.ExperimentalForeignApi
import platform.Foundation.NSFileManager
import platform.Foundation.NSTemporaryDirectory

class IosSecureIdentityStorageTest {

    @Test
    fun firstCreationCommitsAndReloadsOneDurableIdentity() {
        val keychain = FakeKeychain()
        val markers = FakeMarkerStore()
        val storage = IosSecureIdentityStorage(keychain, markers)
        val namespace = namespace(1)
        var generations = 0

        val first = storage.loadOrCreate(namespace, ::testFingerprint) {
            generations++
            keyPair(11)
        }
        val second = storage.loadOrCreate(namespace, ::testFingerprint) {
            error("durable identity must be reloaded")
        }

        assertEquals(1, generations)
        assertContentEquals(first.privateKeyBytes(), second.privateKeyBytes())
        assertEquals(IdentityKeyRecordCodec.RECORD_SIZE, assertNotNull(keychain.record).size)
        assertEquals(
            IdentityStateMarkerCodec.COMMITTED_MARKER_SIZE,
            assertNotNull(markers.committed).size
        )
        first.clearPrivate()
        second.clearPrivate()
    }

    @Test
    fun duplicateAddDiscardsCandidateAndReloadsConcurrentWinner() {
        val namespace = namespace(2)
        val durableWinner = keyPair(21)
        val winnerRecord = IdentityKeyRecordCodec.encode(namespace, durableWinner)
        durableWinner.clearPrivate()
        val keychain = FakeKeychain(duplicateWinner = winnerRecord)
        val markers = FakeMarkerStore()
        val storage = IosSecureIdentityStorage(keychain, markers)
        val losingCandidate = keyPair(31)

        val loaded = storage.loadOrCreate(namespace, ::testFingerprint) { losingCandidate }

        assertContentEquals(ByteArray(32), losingCandidate.privateKeyBytes())
        assertContentEquals(winnerRecord.copyOfRange(40, 72), loaded.privateKeyBytes())
        assertEquals(1, keychain.addCalls)
        assertNotNull(markers.committed)
        winnerRecord.fill(0)
        loaded.clearPrivate()
    }

    @Test
    fun markerWithoutKeychainItemIsPermanentKeyLoss() {
        val namespace = namespace(3)
        val markers = FakeMarkerStore().apply {
            committed = IdentityStateMarkerCodec.encodeCommitted(namespace, ByteArray(32) { 7 })
        }
        val error = assertFailsWith<P2pError.LocalIdentityUnavailable> {
            IosSecureIdentityStorage(FakeKeychain(), markers)
                .loadOrCreate(namespace, ::testFingerprint) { keyPair(41) }
        }

        assertEquals(LocalIdentityFailureKind.KEY_MATERIAL_LOST, error.kind)
    }

    @Test
    fun keychainItemWithoutMarkerRecreatesMarkerAfterValidation() {
        val namespace = namespace(4)
        val pair = keyPair(51)
        val keychain = FakeKeychain(record = IdentityKeyRecordCodec.encode(namespace, pair))
        pair.clearPrivate()
        val markers = FakeMarkerStore()

        val loaded = IosSecureIdentityStorage(keychain, markers)
            .loadOrCreate(namespace, ::testFingerprint) { error("must not generate") }

        val marker = assertNotNull(markers.committed)
        assertEquals(IdentityStateMarkerCodec.COMMITTED_MARKER_SIZE, marker.size)
        assertContentEquals(testFingerprint(loaded), IdentityStateMarkerCodec.decodeCommitted(namespace, marker))
        loaded.clearPrivate()
    }

    @Test
    fun mismatchedMarkerFailsClosedWithoutMutation() {
        val namespace = namespace(5)
        val pair = keyPair(61)
        val keychain = FakeKeychain(record = IdentityKeyRecordCodec.encode(namespace, pair))
        pair.clearPrivate()
        val originalMarker = IdentityStateMarkerCodec.encodeCommitted(namespace, ByteArray(32) { 99 })
        val markers = FakeMarkerStore().apply { committed = originalMarker.copyOf() }

        val error = assertFailsWith<P2pError.LocalIdentityUnavailable> {
            IosSecureIdentityStorage(keychain, markers)
                .loadOrCreate(namespace, ::testFingerprint) { error("must not generate") }
        }

        assertEquals(LocalIdentityFailureKind.CORRUPT_RECORD, error.kind)
        assertContentEquals(originalMarker, markers.committed)
    }

    @Test
    fun corruptKeychainRecordFailsClosed() {
        val namespace = namespace(6)
        val keychain = FakeKeychain(record = ByteArray(IdentityKeyRecordCodec.RECORD_SIZE))

        val error = assertFailsWith<P2pError.LocalIdentityUnavailable> {
            IosSecureIdentityStorage(keychain, FakeMarkerStore())
                .loadOrCreate(namespace, ::testFingerprint) { error("must not generate") }
        }

        assertEquals(LocalIdentityFailureKind.CORRUPT_RECORD, error.kind)
        assertEquals(0, keychain.addCalls)
    }

    @Test
    fun interruptedResetBlocksConstructionUntilExplicitResetCompletes() {
        val namespace = namespace(7)
        val pair = keyPair(71)
        val keychain = FakeKeychain(record = IdentityKeyRecordCodec.encode(namespace, pair))
        val markers = FakeMarkerStore().apply {
            committed = IdentityStateMarkerCodec.encodeCommitted(namespace, testFingerprint(pair))
            resetPending = IdentityStateMarkerCodec.encodeResetPending(namespace)
        }
        pair.clearPrivate()
        val storage = IosSecureIdentityStorage(keychain, markers)

        val blocked = assertFailsWith<P2pError.LocalIdentityUnavailable> {
            storage.loadOrCreate(namespace, ::testFingerprint) { keyPair(81) }
        }
        assertEquals(LocalIdentityFailureKind.RESET_PENDING, blocked.kind)

        storage.reset(namespace)
        assertNull(keychain.record)
        assertNull(markers.committed)
        assertNull(markers.resetPending)

        val replacement = storage.loadOrCreate(namespace, ::testFingerprint) { keyPair(91) }
        assertContentEquals(ByteArray(32) { (91 + it).toByte() }, replacement.privateKeyBytes())
        replacement.clearPrivate()
    }

    @Test
    fun malformedResetMarkerBlocksLoadButExplicitResetReplacesAndCompletesIt() {
        val namespace = namespace(72)
        val pair = keyPair(72)
        val keychain = FakeKeychain(record = IdentityKeyRecordCodec.encode(namespace, pair))
        val markers = FakeMarkerStore().apply {
            committed = IdentityStateMarkerCodec.encodeCommitted(namespace, testFingerprint(pair))
            resetPending = ByteArray(IdentityStateMarkerCodec.RESET_MARKER_SIZE)
        }
        pair.clearPrivate()
        val storage = IosSecureIdentityStorage(keychain, markers)

        val blocked = assertFailsWith<P2pError.LocalIdentityUnavailable> {
            storage.loadOrCreate(namespace, ::testFingerprint) { error("must not rotate") }
        }
        assertEquals(LocalIdentityFailureKind.CORRUPT_RECORD, blocked.kind)

        storage.reset(namespace)
        assertNull(keychain.record)
        assertNull(markers.committed)
        assertNull(markers.resetPending)
    }

    @Test
    fun failedResetKeepsDurablePendingMarkerAndCanBeRetried() {
        val namespace = namespace(8)
        val pair = keyPair(101)
        val keychain = FakeKeychain(record = IdentityKeyRecordCodec.encode(namespace, pair)).apply {
            deleteFailure = IllegalStateException("injected delete failure")
        }
        val markers = FakeMarkerStore().apply {
            committed = IdentityStateMarkerCodec.encodeCommitted(namespace, testFingerprint(pair))
        }
        pair.clearPrivate()
        val storage = IosSecureIdentityStorage(keychain, markers)

        assertFailsWith<IllegalStateException> { storage.reset(namespace) }
        assertNotNull(markers.resetPending)
        val blocked = assertFailsWith<P2pError.LocalIdentityUnavailable> {
            storage.loadOrCreate(namespace, ::testFingerprint) { keyPair(111) }
        }
        assertEquals(LocalIdentityFailureKind.RESET_PENDING, blocked.kind)

        keychain.deleteFailure = null
        storage.reset(namespace)
        assertNull(markers.resetPending)
        assertNull(keychain.record)
    }

    @Test
    fun resetRejectsLiveUsageAcrossStorageInstancesUntilIdempotentRelease() {
        val namespace = namespace(81)
        val first = IosSecureIdentityStorage(FakeKeychain(), FakeMarkerStore())
        val second = IosSecureIdentityStorage(FakeKeychain(), FakeMarkerStore())
        val usage = first.acquireUsage(namespace)

        val blocked = assertFailsWith<P2pError.LocalIdentityUnavailable> {
            second.reset(namespace)
        }
        assertEquals(LocalIdentityFailureKind.LIVE_IDENTITY_IN_USE, blocked.kind)

        usage.release()
        usage.release()
        second.reset(namespace)
    }

    @Test
    fun resetKeepsPendingMarkerWhenKeychainDeleteDoesNotRemoveIdentity() {
        val namespace = namespace(82)
        val pair = keyPair(17)
        val keychain = FakeKeychain(record = IdentityKeyRecordCodec.encode(namespace, pair)).apply {
            deleteIsNoOp = true
        }
        val markers = FakeMarkerStore().apply {
            committed = IdentityStateMarkerCodec.encodeCommitted(namespace, testFingerprint(pair))
        }
        pair.clearPrivate()
        val storage = IosSecureIdentityStorage(keychain, markers)

        val failure = assertFailsWith<P2pError.LocalIdentityUnavailable> {
            storage.reset(namespace)
        }
        assertEquals(LocalIdentityFailureKind.PERSISTENCE_FAILED, failure.kind)
        assertNotNull(keychain.record)
        assertNotNull(markers.resetPending)
        assertNull(markers.committed)

        val blocked = assertFailsWith<P2pError.LocalIdentityUnavailable> {
            storage.loadOrCreate(namespace, ::testFingerprint) { keyPair(18) }
        }
        assertEquals(LocalIdentityFailureKind.RESET_PENDING, blocked.kind)
    }

    @Test
    fun fingerprintCancellationPropagatesUnchangedAndClearsLoadedPrivateKey() {
        val namespace = namespace(83)
        val pair = keyPair(19)
        val keychain = FakeKeychain(record = IdentityKeyRecordCodec.encode(namespace, pair))
        pair.clearPrivate()
        val cancellation = CancellationException("cancel identity validation")
        var observed: EncodedIdentityKeyPair? = null

        val thrown = assertFailsWith<CancellationException> {
            IosSecureIdentityStorage(keychain, FakeMarkerStore()).loadOrCreate(
                namespace = namespace,
                fingerprintDigest = { loaded ->
                    observed = loaded
                    throw cancellation
                },
                generate = { error("must not generate") }
            )
        }

        assertSame(cancellation, thrown)
        assertContentEquals(ByteArray(32), assertNotNull(observed).privateKeyBytes())
    }

    @Test
    fun invalidFingerprintCallbackResultFailsContractAndClearsReturnedKey() {
        val namespace = namespace(9)
        val candidate = keyPair(121)
        val error = assertFailsWith<P2pError.LocalIdentityUnavailable> {
            IosSecureIdentityStorage(FakeKeychain(), FakeMarkerStore()).loadOrCreate(
                namespace = namespace,
                fingerprintDigest = { ByteArray(31) },
                generate = { candidate }
            )
        }

        assertEquals(LocalIdentityFailureKind.STORE_CONTRACT_VIOLATION, error.kind)
        assertContentEquals(ByteArray(32), candidate.privateKeyBytes())
    }

    @Test
    fun foundationMarkerStoreAtomicallyRoundTripsAndDeletesMarkers() {
        val root = "${NSTemporaryDirectory()}/p2pkit-secure-store-test-${Random.nextLong().toString(16)}"
        val namespace = namespace(10)
        val store = FoundationIdentityMarkerStore(root)
        val committed = IdentityStateMarkerCodec.encodeCommitted(namespace, ByteArray(32) { 42 })
        val reset = IdentityStateMarkerCodec.encodeResetPending(namespace)
        try {
            store.writeCommitted(namespace, committed)
            store.writeResetPending(namespace, reset)
            assertContentEquals(committed, store.readCommitted(namespace))
            assertContentEquals(reset, store.readResetPending(namespace))
            store.deleteCommitted(namespace)
            store.deleteResetPending(namespace)
            assertNull(store.readCommitted(namespace))
            assertNull(store.readResetPending(namespace))
        } finally {
            NSFileManager.defaultManager.removeItemAtPath(root, null)
        }
    }

    private fun namespace(seed: Int): IdentityNamespace {
        val appId = AppId("dev.p2pkit.ios-store-test.$seed")
        return IdentityNamespace(
            appId = appId,
            appIdBytes = appId.value.encodeToByteArray(),
            hash = ByteArray(32) { (seed + it).toByte() }
        )
    }

    private fun keyPair(seed: Int): EncodedIdentityKeyPair = EncodedIdentityKeyPair(
        privateKey = ByteArray(32) { (seed + it).toByte() },
        publicKey = ByteArray(32) { (seed + 64 + it).toByte() }
    )

    private fun testFingerprint(keyPair: EncodedIdentityKeyPair): ByteArray =
        keyPair.publicKeyBytes()

    private class FakeKeychain(
        record: ByteArray? = null,
        duplicateWinner: ByteArray? = null
    ) : IosIdentityKeychain {
        var record: ByteArray? = record?.copyOf()
        var duplicateWinner: ByteArray? = duplicateWinner?.copyOf()
        var deleteFailure: RuntimeException? = null
        var deleteIsNoOp: Boolean = false
        var addCalls: Int = 0

        override fun read(account: String): ByteArray? = record?.copyOf()

        override fun add(account: String, record: ByteArray): Boolean {
            addCalls++
            duplicateWinner?.let { winner ->
                this.record = winner.copyOf()
                duplicateWinner = null
                return false
            }
            if (this.record != null) return false
            this.record = record.copyOf()
            return true
        }

        override fun delete(account: String) {
            deleteFailure?.let { throw it }
            if (deleteIsNoOp) return
            record?.fill(0)
            record = null
        }
    }

    private class FakeMarkerStore : IosIdentityMarkerStore {
        var committed: ByteArray? = null
        var resetPending: ByteArray? = null

        override fun readCommitted(namespace: IdentityNamespace): ByteArray? = committed?.copyOf()

        override fun writeCommitted(namespace: IdentityNamespace, marker: ByteArray) {
            committed = marker.copyOf()
        }

        override fun deleteCommitted(namespace: IdentityNamespace) {
            committed?.fill(0)
            committed = null
        }

        override fun readResetPending(namespace: IdentityNamespace): ByteArray? =
            resetPending?.copyOf()

        override fun writeResetPending(namespace: IdentityNamespace, marker: ByteArray) {
            resetPending = marker.copyOf()
        }

        override fun deleteResetPending(namespace: IdentityNamespace) {
            resetPending?.fill(0)
            resetPending = null
        }
    }
}
