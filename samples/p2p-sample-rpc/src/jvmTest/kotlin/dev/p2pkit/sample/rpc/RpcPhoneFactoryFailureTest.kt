package dev.p2pkit.sample.rpc

import dev.p2pkit.core.AppId
import dev.p2pkit.core.P2pKit
import dev.p2pkit.core.P2pSession
import dev.p2pkit.core.PeerFingerprint
import dev.p2pkit.core.permission.P2pPermission
import dev.p2pkit.core.permission.P2pPermissionManager
import dev.p2pkit.rpc.RpcPlatform
import dev.p2pkit.rpc.RpcTrustPurpose
import dev.p2pkit.rpc.RpcTrustStore
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.ExperimentalForInheritanceCoroutinesApi
import kotlinx.coroutines.Job
import kotlinx.coroutines.awaitCancellation
import kotlinx.coroutines.cancelAndJoin
import kotlinx.coroutines.currentCoroutineContext
import kotlinx.coroutines.flow.FlowCollector
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.test.runTest
import java.lang.reflect.Proxy
import java.util.concurrent.atomic.AtomicInteger
import kotlin.test.Test
import kotlin.test.assertFailsWith
import kotlin.test.assertTrue
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertNotNull
import kotlin.test.assertNull
import kotlin.test.assertSame

/** Actual facade/host factory lifecycle over an inert kit; no native provider, network or filesystem access. */
@OptIn(ExperimentalCoroutinesApi::class, ExperimentalForInheritanceCoroutinesApi::class)
class RpcPhoneFactoryFailureTest {
    @Test
    fun startupErrorRetiresTheAlreadyCreatedHostAndItsExactFactoryScopeBeforeReturning() = runTest {
        val fixture = Fixture()
        try {
            val failure = assertFailsWith<PhoneFactoryOwnershipError> {
                RpcPhoneLab.createApplicationHost(fixture.platform, settings(), EmptyTrust(), RpcApplicationSession())
            }
            assertSame(fixture.original, failure.initialFailure)
            assertNotNull(failure.retainedResource)
            assertSame(fixture.factoryScope.await(), failure.retainedScope.coroutineContext[Job])
            assertNull(failure.cause)
            assertFalse(failure.toString().contains("synthetic private"))
            assertTrue(fixture.stops.get() > 0, "The already allocated host must be physically closed")
            assertTrue(fixture.factoryScope.await().isCompleted, "Factory return must follow actual scope retirement")
        } finally {
            // Explicitly retire only this inert fixture if the original regression leaks its parent scope.
            if (fixture.factoryScope.isCompleted) fixture.factoryScope.await().cancelAndJoin()
        }
    }

    @Test
    fun nearbyClientInitializationErrorRetainsAndRetiresTheRealClientBeforeReturning() = runTest {
        val fixture = Fixture()
        val store = object : RpcTrustStore {
            override suspend fun load(appId: AppId, purpose: RpcTrustPurpose): Set<PeerFingerprint> {
                if (purpose == RpcTrustPurpose.SelectedHostPreference) throw fixture.original
                return emptySet()
            }
            override suspend fun replace(
                appId: AppId, purpose: RpcTrustPurpose, fingerprints: Set<PeerFingerprint>,
            ) = Unit
        }
        val failure = assertFailsWith<PhoneFactoryOwnershipError> {
            RpcPhoneLab.createNearbyApplicationClient(fixture.platform, settings(), store, RpcApplicationSession())
        }
        val original = failure.initialFailure
        if (original is PhoneOperationTerminalFailure) assertSame(fixture.original, original.originalFailure)
        else assertSame(fixture.original, original)
        assertNotNull(failure.retainedResource)
        assertTrue(checkNotNull(failure.retainedScope.coroutineContext[Job]).isCompleted)
        assertTrue(fixture.stops.get() > 0)
        assertNull(failure.cause)
    }

    @Test
    fun unpublishedLibraryFactoryErrorRetainsUncertaintyWithoutInventingAHostOrSkippingScopeDrain() = runTest {
        val fixture = Fixture()
        val store = object : RpcTrustStore {
            override suspend fun load(appId: AppId, purpose: RpcTrustPurpose): Set<PeerFingerprint> =
                throw fixture.original
            override suspend fun replace(
                appId: AppId, purpose: RpcTrustPurpose, fingerprints: Set<PeerFingerprint>,
            ) = Unit
        }
        for (host in listOf(false, true)) {
            val failure = assertFailsWith<PhoneFactoryOwnershipError> {
                if (host) {
                    RpcPhoneLab.createApplicationHost(fixture.platform, settings(), store, RpcApplicationSession())
                } else {
                    RpcPhoneLab.createApplicationClient(fixture.platform, settings(), store, RpcApplicationSession())
                }
            }
            assertSame(fixture.original, failure.initialFailure)
            assertNull(failure.retainedResource)
            assertTrue(checkNotNull(failure.retainedScope.coroutineContext[Job]).isCompleted)
        }
        assertEquals(0, fixture.stops.get())
        assertFalse(fixture.factoryScope.isCompleted)
    }

    private fun settings() = RpcPhoneSettings("192.168.14.0/24", "en0", "192.168.14.2", 48123)

    private class EmptyTrust : RpcTrustStore {
        override suspend fun load(appId: AppId, purpose: RpcTrustPurpose): Set<PeerFingerprint> = emptySet()
        override suspend fun replace(appId: AppId, purpose: RpcTrustPurpose, fingerprints: Set<PeerFingerprint>) = Unit
    }

    private class Fixture {
        val original = LinkageError("synthetic private host start failure")
        val stops = AtomicInteger()
        val factoryScope = CompletableDeferred<Job>()
        private val incoming = object : SharedFlow<P2pSession> {
            override val replayCache: List<P2pSession> = emptyList()
            override suspend fun collect(collector: FlowCollector<P2pSession>): Nothing {
                val hostScope = checkNotNull(currentCoroutineContext()[Job]?.parent)
                factoryScope.complete(checkNotNull(hostScope.parent))
                awaitCancellation()
            }
        }
        private val permissions = object : P2pPermissionManager {
            override suspend fun requiredPermissions(): List<P2pPermission> = emptyList()
            override suspend fun missingPermissions(): List<P2pPermission> = emptyList()
            override suspend fun hasRequiredPermissions() = true
        }
        private val kit = Proxy.newProxyInstance(P2pKit::class.java.classLoader, arrayOf(P2pKit::class.java)) {
                _, method, _ ->
            when (method.name) {
                "getLocalPairingQr" -> "synthetic-unused-qr"
                "getIncomingSessions" -> incoming
                "getSessions" -> MutableStateFlow(emptyList<P2pSession>())
                "getPermissions" -> permissions
                "start" -> throw original
                "stop" -> { stops.incrementAndGet(); Unit }
                else -> throw AssertionError("Unexpected inert-kit operation: ${method.name}")
            }
        } as P2pKit
        val platform: RpcPlatform = RpcPlatform::class.java.declaredConstructors.single { it.parameterCount == 1 }
            .apply { isAccessible = true }.newInstance({ _: Any -> kit }) as RpcPlatform
    }
}
