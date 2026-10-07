package dev.p2pkit.sample.rpc

import dev.p2pkit.core.PeerFingerprint
import dev.p2pkit.rpc.RpcFailure
import dev.p2pkit.rpc.RpcFailureKind
import dev.p2pkit.rpc.RpcFailurePhase
import dev.p2pkit.rpc.RpcTrustPurpose
import dev.p2pkit.rpc.RpcTrustStore
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Job
import kotlinx.coroutines.NonCancellable
import kotlinx.coroutines.cancelAndJoin
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext

/** Discovery names are untrusted display text. A selected fingerprint, never a list position, identifies the host. */
public class RpcNearbyHost(
    public val fingerprint: String, public val name: String, public val platform: String,
    public val trusted: Boolean,
)

public enum class RpcDiscoveryConnectionState {
    Discovering, Offline, Connecting, AwaitingApproval, Ready, Reconnecting,
    RequiresApproval, Ambiguous, Failed, Closed,
}

/** No payload data, exception text, device identifiers, or invitation secrets in diagnostic failures. */
public class RpcDiscoveryConnectionStatus(
    public val state: RpcDiscoveryConnectionState,
    public val selectedFingerprint: String?,
    public val nextRetryMillis: Long = 0,
    public val failure: String? = null,
)

/** Test seam uses the same coordinator; production implementation resolves each pin against live discovery. */
internal interface RpcDiscoveryClient {
    fun nearby(): List<RpcNearbyHost>
    fun trusted(pin: String): Boolean
    fun ready(): Boolean
    suspend fun discover()
    suspend fun disconnect()
    suspend fun connect(pin: String)
    suspend fun requestApproval(pin: String)
    suspend fun revoke(pin: String)
}

/** One joinable worker, one explicitly selected pin, no request replay, no automatic first-use approval. */
internal class RpcDiscoveryCoordinator(
    private val scope: CoroutineScope,
    private val client: RpcDiscoveryClient,
    private val store: RpcTrustStore,
) {
    private val lock = Mutex()
    private var worker: Job? = null
    private var closed = false
    private var started = false
    private val mutableStatus = MutableStateFlow(
        RpcDiscoveryConnectionStatus(RpcDiscoveryConnectionState.Discovering, null),
    )
    val status: StateFlow<RpcDiscoveryConnectionStatus> = mutableStatus.asStateFlow()

    suspend fun start() = lock.withLock {
        check(!closed && !started)
        val selected = readSelection()
        client.discover()
        started = true
        if (selected != null) launchWorker(selected, firstUse = false)
    }

    /** The UI must show the pin and explain first-use trust BEFORE passing firstUseConfirmed=true. */
    suspend fun select(pin: String, firstUseConfirmed: Boolean) = lock.withLock {
        check(started && !closed)
        PeerFingerprint.parse(pin)
        check(client.nearby().count { it.fingerprint == pin } == 1) { "Host disappeared or discovery is ambiguous" }
        check(client.trusted(pin) || firstUseConfirmed) { "First-use fingerprint confirmation required" }
        worker?.cancelAndJoin()
        client.disconnect()
        // Persist only an already trusted selection. Pending approval isn't a grant or a reconnect preference.
        if (client.trusted(pin)) saveSelection(pin)
        else saveSelection(null)
        launchWorker(pin, firstUse = !client.trusted(pin))
    }

    suspend fun forget(pin: String) = lock.withLock {
        check(started && !closed)
        PeerFingerprint.parse(pin)
        val selected = mutableStatus.value.selectedFingerprint == pin
        if (selected) worker?.cancelAndJoin()
        // Deny/cancel RPC before a storage failure can leave stale reconnect authorization.
        try {
            client.revoke(pin)
        } finally {
            if (selected) {
                withContext(NonCancellable) {
                    try { saveSelection(null) } finally {
                        mutableStatus.value = RpcDiscoveryConnectionStatus(
                            RpcDiscoveryConnectionState.Discovering, null,
                        )
                    }
                }
            }
        }
    }

    suspend fun close() = lock.withLock {
        closed = true
        worker?.cancelAndJoin()
        worker = null
        mutableStatus.value = RpcDiscoveryConnectionStatus(RpcDiscoveryConnectionState.Closed,
            mutableStatus.value.selectedFingerprint)
    }

    private fun launchWorker(pin: String, firstUse: Boolean) {
        worker = scope.launch {
            try {
                if (firstUse) {
                    update(RpcDiscoveryConnectionState.AwaitingApproval, pin)
                    client.requestApproval(pin) // Exactly one attempt: rejection/timeout NEVER opens another popup.
                    check(client.trusted(pin))
                    saveSelection(pin)
                }
                reconnect(pin)
            } catch (cancelled: CancellationException) {
                throw cancelled
            } catch (failure: Exception) {
                update(RpcDiscoveryConnectionState.Failed, pin, failure = safeFailure(failure))
            }
        }
    }

    private suspend fun reconnect(pin: String) {
        var failures = 0
        while (true) {
            if (!client.trusted(pin)) {
                update(RpcDiscoveryConnectionState.RequiresApproval, pin)
                return // Revoke requires a NEW explicit first-use confirmation, never silent re-pairing.
            }
            if (client.ready()) {
                failures = 0
                update(RpcDiscoveryConnectionState.Ready, pin)
                delay(500)
                continue
            }
            val matches = client.nearby().count { it.fingerprint == pin }
            if (matches != 1) {
                update(if (matches == 0) RpcDiscoveryConnectionState.Offline
                    else RpcDiscoveryConnectionState.Ambiguous, pin)
                delay(1_000)
                continue
            }
            update(if (failures == 0) RpcDiscoveryConnectionState.Connecting
                else RpcDiscoveryConnectionState.Reconnecting, pin)
            try {
                client.connect(pin)
                check(client.ready())
            } catch (cancelled: CancellationException) {
                throw cancelled
            } catch (failure: Exception) {
                if (failure is RpcFailure && failure.kind in setOf(RpcFailureKind.TrustStorage,
                        RpcFailureKind.Authentication, RpcFailureKind.Unauthorized, RpcFailureKind.Closed)
                ) throw failure
                val wait = BACKOFF[failures.coerceAtMost(BACKOFF.lastIndex)]
                failures = (failures + 1).coerceAtMost(BACKOFF.size)
                update(RpcDiscoveryConnectionState.Reconnecting, pin, wait, safeFailure(failure))
                delay(wait)
            }
        }
    }

    private fun update(state: RpcDiscoveryConnectionState, pin: String, wait: Long = 0, failure: String? = null) {
        val old = mutableStatus.value
        if (old.state != state || old.selectedFingerprint != pin ||
            old.nextRetryMillis != wait || old.failure != failure
        ) {
            mutableStatus.value = RpcDiscoveryConnectionStatus(state, pin, wait, failure)
        }
    }

    private suspend fun readSelection(): String? = selectionBoundary {
        val saved = store.load(RpcCapacityContract.appId, RpcTrustPurpose.SelectedHostPreference)
        check(saved.size <= 1)
        saved.singleOrNull()?.value
    }

    private suspend fun saveSelection(pin: String?) = selectionBoundary {
        val saved = pin?.let { setOf(PeerFingerprint.parse(it)) }.orEmpty()
        withContext(NonCancellable) {
            store.replace(RpcCapacityContract.appId, RpcTrustPurpose.SelectedHostPreference, saved)
            check(store.load(RpcCapacityContract.appId, RpcTrustPurpose.SelectedHostPreference) == saved)
        }
    }

    private suspend fun <T> selectionBoundary(block: suspend () -> T): T = try { block() }
    catch (cancelled: CancellationException) { throw cancelled }
    catch (_: Exception) { throw RpcFailure(RpcFailureKind.TrustStorage, RpcFailurePhase.Trust) }

    private fun safeFailure(failure: Exception): String = if (failure is RpcFailure) {
        "${failure.kind}/${failure.phase}/${failure.executionEvidence}"
    } else "LocalOrProtocolFailure"

    private companion object {
        val BACKOFF = longArrayOf(1_000, 2_000, 4_000, 8_000, 16_000, 30_000)
    }
}
