package dev.p2pkit.sample.rpc

import dev.p2pkit.core.AppId
import dev.p2pkit.core.PeerFingerprint
import dev.p2pkit.rpc.RpcFailure
import dev.p2pkit.rpc.RpcFailureKind
import dev.p2pkit.rpc.RpcFailurePhase
import dev.p2pkit.rpc.RpcTrustPurpose
import dev.p2pkit.rpc.RpcTrustStore
import kotlinx.coroutines.CoroutineExceptionHandler
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.awaitCancellation
import kotlinx.coroutines.cancel
import kotlinx.coroutines.launch
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.test.StandardTestDispatcher
import kotlinx.coroutines.test.advanceTimeBy
import kotlinx.coroutines.test.runCurrent
import kotlinx.coroutines.test.runTest
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertFalse
import kotlin.test.assertNull
import kotlin.test.assertSame
import kotlin.test.assertTrue

@OptIn(ExperimentalCoroutinesApi::class)
class RpcDiscoveryTerminalGuardTest {
    private class ReportingError : Error("synthetic private native observer failure")
    private val pin = "p2f1-" + "a".repeat(52)

    private class Store : RpcTrustStore {
        var selection: Set<PeerFingerprint> = emptySet()
        var beforeReplace: suspend () -> Unit = {}
        override suspend fun load(appId: AppId, purpose: RpcTrustPurpose): Set<PeerFingerprint> = selection
        override suspend fun replace(appId: AppId, purpose: RpcTrustPurpose, fingerprints: Set<PeerFingerprint>) {
            beforeReplace()
            selection = fingerprints
        }
    }

    private class Client(private val pin: String) : RpcDiscoveryClient {
        var approved = false
        var dials = 0
        var approvals = 0
        var disconnects = 0
        var revocations = 0
        var onConnect: suspend () -> Unit = {}
        var onApproval: suspend () -> Unit = { approved = true }
        var trustFailure: Throwable? = null
        override fun nearby(): List<RpcNearbyHost> = listOf(RpcNearbyHost(pin, "Synthetic host", "test", approved))
        override fun trusted(pin: String): Boolean { trustFailure?.let { throw it }; return approved }
        override fun ready(): Boolean = false
        override suspend fun discover() = Unit
        override suspend fun disconnect() { disconnects++ }
        override suspend fun connect(pin: String) { dials++; onConnect() }
        override suspend fun requestApproval(pin: String) { approvals++; onApproval() }
        override suspend fun revoke(pin: String) { revocations++; approved = false }
    }

    @Test
    fun fatalDiscoveryPreferenceWriteSealsRetryAndCannotBecomeSuccessfulClose() = runTest {
        val failure = ReportingError()
        val escaped = mutableListOf<Throwable>()
        val scope = CoroutineScope(SupervisorJob() + StandardTestDispatcher(testScheduler) +
            CoroutineExceptionHandler { _, cause -> escaped += cause })
        val store = Store()
        val client = Client(pin)
        store.beforeReplace = { if (client.approved) throw failure }
        val coordinator = RpcDiscoveryCoordinator(scope, client, store)
        try {
            coordinator.start()
            coordinator.select(pin, true)
            runCurrent()
            assertEquals(RpcDiscoveryConnectionState.Failed, coordinator.status.value.state)
            assertEquals("LocalOrProtocolFailure", coordinator.status.value.failure)
            assertTrue(escaped.isEmpty(), "Background errors must not escape to global logging")
            val retained = assertFailsWith<PhoneOperationTerminalFailure> { coordinator.select(pin, true) }
            assertSame(failure, retained.originalFailure)
            assertNull(retained.cause)
            assertFalse(retained.toString().contains("synthetic private"))
            assertFailsWith<PhoneOperationTerminalFailure> { coordinator.forget(pin) }
            advanceTimeBy(60_000); runCurrent()
            assertEquals(1, client.approvals)
            assertEquals(0, client.dials)
            assertEquals(1, client.disconnects)
            assertEquals(0, client.revocations)
            assertTrue(store.selection.isEmpty())
            assertSame(retained, assertFailsWith<PhoneOperationTerminalFailure> { coordinator.close() })
            assertEquals(RpcDiscoveryConnectionState.Failed, coordinator.status.value.state)
        } finally { scope.cancel() }
    }

    @Test
    fun fatalConnectionRetirementPreventsAReplacementSelectionAfterJoining() = runTest {
        val failure = ReportingError()
        val escaped = mutableListOf<Throwable>()
        val scope = CoroutineScope(SupervisorJob() + StandardTestDispatcher(testScheduler) +
            CoroutineExceptionHandler { _, cause -> escaped += cause })
        var retired = false
        val client = Client(pin).apply {
            approved = true
            onConnect = { try { awaitCancellation() } finally { retired = true; throw failure } }
        }
        val store = Store().apply { selection = setOf(PeerFingerprint.parse(pin)) }
        val coordinator = RpcDiscoveryCoordinator(scope, client, store)
        try {
            coordinator.start(); runCurrent()
            var replacement: Throwable? = null
            val selection = launch {
                try { coordinator.select(pin, false) } catch (caught: Throwable) { replacement = caught }
            }
            runCurrent(); selection.join()
            assertTrue(retired)
            assertTrue(replacement is PhoneOperationTerminalFailure)
            assertSame(failure, (replacement as PhoneOperationTerminalFailure).originalFailure)
            assertTrue(escaped.isEmpty())
            assertEquals(1, client.dials)
            assertEquals(0, client.disconnects)
            assertSame(replacement, assertFailsWith<PhoneOperationTerminalFailure> { coordinator.close() })
        } finally { scope.cancel() }
    }

    @Test
    fun fatalFailureWhileClassifyingAProtocolRejectionAlsoRetainsTheOriginalOwner() = runTest {
        val failure = ReportingError()
        val escaped = mutableListOf<Throwable>()
        val scope = CoroutineScope(SupervisorJob() + StandardTestDispatcher(testScheduler) +
            CoroutineExceptionHandler { _, cause -> escaped += cause })
        val client = Client(pin).apply {
            onApproval = {
                trustFailure = failure
                throw RpcFailure(RpcFailureKind.Unauthorized, RpcFailurePhase.Trust)
            }
        }
        val coordinator = RpcDiscoveryCoordinator(scope, client, Store())
        try {
            coordinator.start(); coordinator.select(pin, true); runCurrent()
            assertEquals(RpcDiscoveryConnectionState.Failed, coordinator.status.value.state)
            assertEquals("LocalOrProtocolFailure", coordinator.status.value.failure)
            assertTrue(escaped.isEmpty())
            val closed = assertFailsWith<PhoneOperationTerminalFailure> { coordinator.close() }
            assertSame(failure, closed.originalFailure)
            assertEquals(1, client.approvals)
            assertEquals(0, client.dials)
        } finally { scope.cancel() }
    }

    @Test
    fun queuedDiscoveryAndForegroundEffectsShareOneTerminalOwner() = runTest {
        val failures = PhoneOperationFailureState()
        val failure = ReportingError()
        val client = Client(pin).apply { approved = true }
        val store = Store().apply { selection = setOf(PeerFingerprint.parse(pin)) }
        val coordinator = RpcDiscoveryCoordinator(backgroundScope, client, store, failures)
        coordinator.start()
        failures.retain(failure) // A foreground native effect failed before discovery's first dispatch.
        runCurrent()
        assertEquals(0, client.dials)
        assertEquals(RpcDiscoveryConnectionState.Failed, coordinator.status.value.state)
        var callbacks = 0
        assertSame(failures.terminal, assertFailsWith<PhoneOperationTerminalFailure> {
            startPhoneOperation(backgroundScope, MutableStateFlow(false), { "cancelled" }, { "failed" },
                { callbacks++ }, failures) { error("A sealed effect must not run") }
        })
        assertSame(failures.terminal, assertFailsWith<PhoneOperationTerminalFailure> {
            failures.effect { error("A sealed direct effect must not run") }
        })
        assertSame(failures.terminal, assertFailsWith<PhoneOperationTerminalFailure> { coordinator.close() })
        assertSame(failure, failures.originalFailure)
        assertEquals(0, callbacks)
    }


    @Test
    fun closeBeforeDispatchStillPublishesFailureWithoutDialingOrInventingASelection() = runTest {
        for (selected in listOf(false, true)) {
            val failures = PhoneOperationFailureState()
            val client = Client(pin).apply { approved = true }
            val store = Store().apply {
                if (selected) selection = setOf(PeerFingerprint.parse(pin))
            }
            val coordinator = RpcDiscoveryCoordinator(backgroundScope, client, store, failures)
            coordinator.start()
            failures.retain(ReportingError())
            assertSame(failures.terminal, assertFailsWith<PhoneOperationTerminalFailure> { coordinator.close() })
            assertEquals(RpcDiscoveryConnectionState.Failed, coordinator.status.value.state)
            assertEquals(if (selected) pin else null, coordinator.status.value.selectedFingerprint)
            assertEquals("LocalOrProtocolFailure", coordinator.status.value.failure)
            assertEquals(0, client.dials)
            assertEquals(0, client.approvals)
        }
    }

}
