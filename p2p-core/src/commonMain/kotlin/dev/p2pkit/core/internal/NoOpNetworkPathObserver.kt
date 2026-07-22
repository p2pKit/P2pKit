package dev.p2pkit.core.internal

import dev.p2pkit.core.NetworkPathObserver
import dev.p2pkit.core.NetworkPathStatus
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow

/**
 * [NetworkPathObserver] that reports nothing. Used as the default on
 * platforms where the SDK can't construct a real observer without external
 * input (JVM desktop, or Android before `P2pKitAndroid.initialize`).
 *
 * The SDK treats a permanent [NetworkPathStatus.Unknown] stream as "no
 * observer" — `SessionManager.applyPathChange` only reacts to `Satisfied`
 * and `Unsatisfied`, so a no-op observer is functionally equivalent to
 * having no observer at all.
 */
internal object NoOpNetworkPathObserver : NetworkPathObserver {
    private val _status = MutableStateFlow<NetworkPathStatus>(NetworkPathStatus.Unknown)
    override val status: StateFlow<NetworkPathStatus> = _status.asStateFlow()
    override suspend fun start() {}
    override suspend fun close() {}
}
