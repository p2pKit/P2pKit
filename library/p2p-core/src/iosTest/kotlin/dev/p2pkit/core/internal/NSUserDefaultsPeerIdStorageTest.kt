package dev.p2pkit.core.internal

import dev.p2pkit.core.AppId
import dev.p2pkit.core.P2pLogger
import kotlin.test.AfterTest
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertNotEquals
import kotlin.test.assertNotNull
import kotlin.uuid.ExperimentalUuidApi
import kotlin.uuid.Uuid
import platform.Foundation.NSUserDefaults

class NSUserDefaultsPeerIdStorageTest {
    private val suiteName = "dev.p2pkit.core.tests.${uniqueSuffix()}"
    private val defaults = NSUserDefaults(suiteName = suiteName)

    @AfterTest
    fun cleanup() {
        defaults.removePersistentDomainForName(suiteName)
        defaults.synchronize()
    }

    @Test
    fun collidingLegacySuffixesUseIndependentHashBucketEntries() {
        val unique = uniqueSuffix()
        val firstAppId = "tenant/$unique"
        val secondAppId = "tenant?$unique"
        val suffix = sanitizeAppIdForKey(firstAppId)
        assertEquals(suffix, sanitizeAppIdForKey(secondAppId))

        val first = NSUserDefaultsPeerIdStorage(AppId(firstAppId), P2pLogger.NoOp, defaults)
            .loadOrGenerate()
        val second = NSUserDefaultsPeerIdStorage(AppId(secondAppId), P2pLogger.NoOp, defaults)
            .loadOrGenerate()

        assertNotEquals(first, second)
        val bucket = assertNotNull(defaults.dictionaryForKey("dev.p2pkit.peerId.v2.$suffix"))
        assertEquals(first.value, bucket[peerIdStorageKey(firstAppId)])
        assertEquals(second.value, bucket[peerIdStorageKey(secondAppId)])
    }

    @Test
    fun legacyStringMigratesWithoutDeletingRollbackValue() {
        val appId = "legacy-${uniqueSuffix()}"
        val suffix = sanitizeAppIdForKey(appId)
        val legacyKey = "dev.p2pkit.peerId.$suffix"
        defaults.setObject("legacy-peer-id", legacyKey)
        defaults.synchronize()

        val loaded = NSUserDefaultsPeerIdStorage(AppId(appId), P2pLogger.NoOp, defaults)
            .loadOrGenerate()

        assertEquals("legacy-peer-id", loaded.value)
        assertEquals("legacy-peer-id", defaults.stringForKey(legacyKey))
        val bucket = assertNotNull(defaults.dictionaryForKey("dev.p2pkit.peerId.v2.$suffix"))
        assertEquals("legacy-peer-id", bucket[peerIdStorageKey(appId)])
    }

    @Test
    fun failedSynchronizationDoesNotRotateSameStorageInstance() {
        val appId = "sync-failure-${uniqueSuffix()}"
        val suffix = sanitizeAppIdForKey(appId)
        val storage = NSUserDefaultsPeerIdStorage(
            appId = AppId(appId),
            logger = P2pLogger.NoOp,
            defaults = defaults,
            synchronizeDefaults = { false }
        )

        assertEquals(storage.loadOrGenerate(), storage.loadOrGenerate())
    }

    @Test
    fun invalidBucketEntryIsRejectedAndReplacedWithAProtocolValidIdentity() {
        val appId = "invalid-entry-${uniqueSuffix()}"
        val suffix = sanitizeAppIdForKey(appId)
        val bucketKey = "dev.p2pkit.peerId.v2.$suffix"
        val entryKey = peerIdStorageKey(appId)
        val invalid = "x".repeat(MAX_PERSISTED_PEER_ID_BYTES + 1)
        defaults.setObject(mapOf(entryKey to invalid), bucketKey)
        defaults.synchronize()

        val loaded = NSUserDefaultsPeerIdStorage(AppId(appId), P2pLogger.NoOp, defaults)
            .loadOrGenerate()

        assertNotEquals(invalid, loaded.value)
        val bucket = assertNotNull(defaults.dictionaryForKey(bucketKey))
        assertEquals(loaded.value, bucket[entryKey])
        assertEquals(loaded, parsePersistedPeerId(loaded.value))
    }

    @Test
    fun invalidLegacyEntryIsNotMigratedIntoTheHashedBucket() {
        val appId = "invalid-legacy-${uniqueSuffix()}"
        val suffix = sanitizeAppIdForKey(appId)
        val legacyKey = "dev.p2pkit.peerId.$suffix"
        val invalid = "unsafe\u202Epeer-id"
        defaults.setObject(invalid, legacyKey)
        defaults.synchronize()

        val loaded = NSUserDefaultsPeerIdStorage(AppId(appId), P2pLogger.NoOp, defaults)
            .loadOrGenerate()

        assertNotEquals(invalid, loaded.value)
        val bucket = assertNotNull(defaults.dictionaryForKey("dev.p2pkit.peerId.v2.$suffix"))
        assertEquals(loaded.value, bucket[peerIdStorageKey(appId)])
        assertEquals(invalid, defaults.stringForKey(legacyKey))
    }

    @OptIn(ExperimentalUuidApi::class)
    private fun uniqueSuffix(): String = Uuid.random().toString()
}
