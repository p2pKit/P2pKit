package dev.p2pkit.core.testfixtures

import dev.p2pkit.core.AppId
import dev.p2pkit.core.security.EncodedIdentityKeyPair
import dev.p2pkit.core.security.IdentityDerivation
import dev.p2pkit.core.security.SecureIdentityService
import dev.p2pkit.core.security.platformSecurityCryptography
import kotlin.concurrent.atomics.AtomicInt
import kotlin.concurrent.atomics.ExperimentalAtomicApi
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertNotEquals
import kotlin.test.assertNotSame
import kotlin.test.assertTrue
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.async
import kotlinx.coroutines.awaitAll
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withTimeout

@OptIn(ExperimentalAtomicApi::class)
class MemorySecureIdentityStorageTest {
    @Test
    fun identityCopiesDoNotPoisonTheStoreAndExplicitResetReplacesIdentity() {
        val store = MemorySecureIdentityStorage()
        val service = SecureIdentityService(platformSecurityCryptography(), store)
        val appId = AppId("secure.fixture.copies")
        val first = service.loadOrCreate(appId)
        try {
            first.clearPrivate()
            val second = service.loadOrCreate(appId)
            try {
                assertEquals(first.fingerprint, second.fingerprint)
                assertEquals(first.peerId, second.peerId)
                service.reset(appId)
                val replaced = service.loadOrCreate(appId)
                try {
                    assertNotEquals(second.fingerprint, replaced.fingerprint)
                } finally {
                    replaced.clearPrivate()
                }
            } finally {
                second.clearPrivate()
            }
        } finally {
            first.clearPrivate()
            store.clear()
        }
    }

    @Test
    fun concurrentFixtureLoadsGenerateOneRecordAndReturnIndependentCopies() = runBlocking {
        val store = MemorySecureIdentityStorage()
        val cryptography = platformSecurityCryptography()
        val namespace = IdentityDerivation.namespace(AppId("secure.fixture.concurrent"), cryptography)
        val generated = AtomicInt(0)
        val released = CompletableDeferred<Unit>()
        val returned = SnapshotList<EncodedIdentityKeyPair>()
        try {
            val keys = withTimeout(5_000) {
                val loads = List(8) {
                    async(Dispatchers.Default) {
                        released.await()
                        store.loadOrCreate(
                            namespace,
                            fingerprintDigest = { pair ->
                                val publicKey = pair.publicKeyBytes()
                                try {
                                    IdentityDerivation.fingerprintDigest(publicKey, cryptography)
                                } finally {
                                    publicKey.fill(0)
                                }
                            },
                            generate = {
                                generated.addAndFetch(1)
                                cryptography.generateX25519KeyPair()
                            }
                        ).also(returned::add)
                    }
                }
                released.complete(Unit)
                loads.awaitAll()
            }
            assertEquals(1, generated.load())
            assertEquals(8, keys.size)
            keys.drop(1).forEach { key ->
                assertNotSame(keys.first(), key)
                assertTrue(keys.first().publicKeyBytes().contentEquals(key.publicKeyBytes()))
            }
        } finally {
            returned.snapshot().forEach { it.clearPrivate() }
            store.clear()
        }
    }
}
