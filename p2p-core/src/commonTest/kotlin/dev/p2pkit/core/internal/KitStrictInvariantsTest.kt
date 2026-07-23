package dev.p2pkit.core.internal

import dev.p2pkit.core.AppId
import dev.p2pkit.core.ConnectionState
import dev.p2pkit.core.ExplicitSecurityRisk
import dev.p2pkit.core.P2pKit
import dev.p2pkit.core.P2pMessage
import dev.p2pkit.core.P2pSession
import dev.p2pkit.core.Peer
import dev.p2pkit.core.PeerId
import dev.p2pkit.core.Platform
import dev.p2pkit.core.SecurityMode
import dev.p2pkit.core.TransportKind
import dev.p2pkit.core.testfixtures.FakeDataTransport
import dev.p2pkit.core.testfixtures.RecordingLogger
import dev.p2pkit.core.testfixtures.createTestKit
import dev.p2pkit.core.transfer.P2pFileOffer
import dev.p2pkit.core.transfer.P2pFileTransfer
import dev.p2pkit.core.transport.TransportContext
import dev.p2pkit.core.transport.TransportFactory
import dev.p2pkit.core.transport.TransportPair
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.runBlocking
import kotlinx.io.RawSource
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertIs
import kotlin.test.assertTrue

/**
 * Meta-test for the strict-invariants suite wiring (2026-07 TST-9 / P1-03,
 * decision #15a): proves the safety net the kit-level behavioral suites now
 * run under is actually armed, end to end through the construction path the
 * suites use — `createTestKit` → [P2pKit.create] →
 * `P2pKitBuilder.strictSessionInvariants` → `newP2pKit` → [P2pKitImpl] →
 * [SessionManager] → [SessionStore].
 *
 *  1. a forced bookkeeping violation inside a **kit-built** store THROWS
 *     [IllegalStateException] when the kit is built via the strict test
 *     fixture — so a store regression fails a behavioral suite loudly;
 *  2. the same violation only `logger.warn`s (never throws) when the kit is
 *     built via plain [P2pKit.create] with the explicit legacy migration
 *     mode — pinning the production invariant disposition independently from
 *     the authenticated-v2 default and its JVM secure-store requirement.
 *
 * The violation is forced through the TEST-ONLY seam chain
 * ([P2pKitImpl.forceSessionStoreInvariantViolationForTest]) because the
 * store's public mutators maintain the invariants and cannot produce one
 * (see [SessionStore.forceInvariantViolationForTest]).
 */
@OptIn(ExplicitSecurityRisk::class)
@Suppress("DEPRECATION")
class KitStrictInvariantsTest {

    @Test
    fun strictTestKitThrowsOnForcedStoreInconsistency() = runBlocking {
        val kit = createTestKit {
            appId = AppId("com.example.test")
            deviceName = "StrictKit"
            transports { register(KitFactoryFor(FakeDataTransport())) }
        }
        try {
            val impl = assertIs<P2pKitImpl>(kit)
            val failure = assertFailsWith<IllegalStateException> {
                impl.forceSessionStoreInvariantViolationForTest(
                    KitStubSession(peer = syntheticPeer("peer-a", "A"))
                )
            }
            val message = failure.message ?: ""
            assertTrue(
                message.contains("INVARIANT"),
                "strict-mode failure should identify itself as an invariant violation, was: $message"
            )
        } finally {
            kit.stop()
        }
    }

    @Test
    fun explicitLegacyKitKeepsProductionWarnOnlyInvariantDisposition() = runBlocking {
        val logger = RecordingLogger()
        val kit = P2pKit.create {
            appId = AppId("com.example.test")
            deviceName = "DefaultKit"
            this.logger = logger
            security { mode = SecurityMode.NoneForMvp }
            transports { register(KitFactoryFor(FakeDataTransport())) }
        }
        try {
            val impl = assertIs<P2pKitImpl>(kit)
            assertEquals(
                0,
                logger.warnings.count { it.contains("INVARIANT") },
                "no invariant warning expected before the violation is forced"
            )
            // Must NOT throw — production default is log-don't-crash.
            impl.forceSessionStoreInvariantViolationForTest(
                KitStubSession(peer = syntheticPeer("peer-a", "A"))
            )
            // ...but the violation must have been detected and warned,
            // proving the store still looks (the wiring changed only the
            // strict-mode disposition, not the production one).
            assertEquals(
                1,
                logger.warnings.count { it.contains("INVARIANT") },
                "expected exactly one invariant warning, warnings were: ${logger.warnings}"
            )
        } finally {
            kit.stop()
        }
    }

    private fun syntheticPeer(id: String, name: String): Peer = Peer(
        id = PeerId(id),
        name = name,
        platform = Platform.JVM_DESKTOP,
        supportedTransports = setOf(TransportKind.LAN)
    )
}

private class KitFactoryFor(private val transport: FakeDataTransport) : TransportFactory {
    override val descriptor =
        dev.p2pkit.core.transport.TransportDescriptor.dataOnly(transport.type)
    override fun build(context: TransportContext): TransportPair =
        TransportPair(data = transport, discovery = null)
}

/**
 * Minimal [P2pSession] stand-in: the store only reads [peer], [state], and
 * instance identity (same shape as the stub in [SessionStoreInvariantTest]).
 */
private class KitStubSession(
    override val peer: Peer,
    override val id: String = "session-${peer.id.value}",
    initialState: ConnectionState = ConnectionState.Connected
) : P2pSession {
    private val _state = MutableStateFlow(initialState)
    override val state: StateFlow<ConnectionState> = _state
    override val incoming: SharedFlow<P2pMessage> = MutableSharedFlow()
    @Deprecated("Observe pendingFileOffers")
    override val incomingFiles: SharedFlow<P2pFileOffer> = MutableSharedFlow()

    override suspend fun send(message: P2pMessage): Unit =
        error("KitStubSession.send is not supported")

    override suspend fun sendFile(
        name: String,
        sizeBytes: Long,
        mimeType: String?,
        source: RawSource
    ): P2pFileTransfer = error("KitStubSession.sendFile is not supported")

    override suspend fun close() {
        _state.value = ConnectionState.Closed
    }
}
