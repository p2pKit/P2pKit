package dev.p2pkit.core.internal

import dev.p2pkit.core.AppId
import dev.p2pkit.core.LocalIdentityFailureKind
import dev.p2pkit.core.P2pError
import dev.p2pkit.core.P2pKit
import dev.p2pkit.core.TransportKind
import dev.p2pkit.core.security.EncodedIdentityKeyPair
import dev.p2pkit.core.security.IdentityNamespace
import dev.p2pkit.core.transport.TransportContext
import dev.p2pkit.core.transport.TransportDescriptor
import dev.p2pkit.core.transport.TransportFactory
import dev.p2pkit.core.transport.TransportPair
import kotlin.test.Test
import kotlin.test.assertContentEquals
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertSame
import kotlin.test.assertTrue

class SecureIdentityConstructionRollbackTest {
    @Test
    fun identityLoadFailureRemainsPrimaryWhenUsageReleaseAlsoFails() {
        val loadFailure = IllegalStateException("identity store unavailable")
        val releaseFailure = IllegalStateException("identity usage release failed")
        val storage = RollbackIdentityStorage(loadFailure, releaseFailure)

        val thrown = assertFailsWith<P2pError.LocalIdentityUnavailable> {
            createKit(storage, StaticIdentityFactory())
        }

        assertEquals(LocalIdentityFailureKind.TEMPORARILY_UNAVAILABLE, thrown.kind)
        assertSame(loadFailure, thrown.cause)
        assertEquals(1, storage.releaseCalls)
        assertTrue(thrown.suppressedExceptions.any { it === releaseFailure })
    }

    @Test
    fun laterConstructionFailureClearsPrivateKeyAndAttemptsUsageRelease() {
        val factoryFailure = IllegalStateException("transport factory failed")
        val releaseFailure = IllegalStateException("identity usage release failed")
        val storage = RollbackIdentityStorage(loadFailure = null, releaseFailure = releaseFailure)

        val thrown = assertFailsWith<P2pError.TransportInitializationFailed> {
            createKit(storage, StaticIdentityFactory { throw factoryFailure })
        }

        assertSame(factoryFailure, thrown.cause)
        assertEquals(1, storage.releaseCalls)
        assertTrue(thrown.suppressedExceptions.any { it === releaseFailure })
        assertContentEquals(ByteArray(32), checkNotNull(storage.returnedPair).privateKeyBytes())
    }

    @Test
    fun samePrimaryAndReleaseFailureIsNotSelfSuppressedOrReplaced() {
        val sharedFailure = IllegalStateException("shared load and release failure")
        val storage = RollbackIdentityStorage(sharedFailure, sharedFailure)

        val thrown = assertFailsWith<P2pError.LocalIdentityUnavailable> {
            createKit(storage, StaticIdentityFactory())
        }

        assertSame(sharedFailure, thrown.cause)
        assertEquals(1, storage.releaseCalls)
        assertTrue(thrown.suppressedExceptions.isEmpty())
    }

    private fun createKit(
        storage: SecureIdentityStorage,
        factory: TransportFactory
    ): P2pKit = P2pKit.create {
        appId = AppId("secure-construction-rollback")
        deviceName = "Rollback test"
        secureIdentityStorage = storage
        transports { register(factory) }
    }
}

private class RollbackIdentityStorage(
    private val loadFailure: Throwable?,
    private val releaseFailure: Throwable?
) : SecureIdentityStorage {
    var releaseCalls: Int = 0
        private set
    var returnedPair: EncodedIdentityKeyPair? = null
        private set

    override fun acquireUsage(namespace: IdentityNamespace): SecureIdentityUsage =
        SecureIdentityUsage {
            releaseCalls += 1
            releaseFailure?.let { throw it }
        }

    override fun loadOrCreate(
        namespace: IdentityNamespace,
        fingerprintDigest: (EncodedIdentityKeyPair) -> ByteArray,
        generate: () -> EncodedIdentityKeyPair
    ): EncodedIdentityKeyPair {
        loadFailure?.let { throw it }
        return generate().also { returnedPair = it }
    }

    override fun reset(namespace: IdentityNamespace) = Unit
}

private class StaticIdentityFactory(
    private val buildResult: (TransportContext) -> TransportPair = {
        TransportPair(data = dev.p2pkit.core.testfixtures.FakeDataTransport())
    }
) : TransportFactory {
    override val descriptor: TransportDescriptor =
        TransportDescriptor.dataOnly(TransportKind.LAN)

    override fun build(context: TransportContext): TransportPair = buildResult(context)
}
