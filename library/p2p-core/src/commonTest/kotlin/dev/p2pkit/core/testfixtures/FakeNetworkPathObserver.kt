package dev.p2pkit.core.testfixtures

import dev.p2pkit.core.NetworkPathObserver
import dev.p2pkit.core.NetworkPathStatus
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow

/**
 * Test-controllable [NetworkPathObserver]. Tests construct one, hand it to
 * the kit via `lifecycle { networkPathObserver = fake }`, then call [emit]
 * to drive `Satisfied` / `Unsatisfied` transitions deterministically.
 *
 * Records [startCalled] / [closeCalled] so the kit lifecycle can be
 * verified — the kit must `start()` the observer inside `ensureStarted`
 * and `close()` it during `kit.stop()`.
 */
internal class FakeNetworkPathObserver(
    initial: NetworkPathStatus = NetworkPathStatus.Unknown
) : NetworkPathObserver {
    private val _status = MutableStateFlow(initial)
    override val status: StateFlow<NetworkPathStatus> = _status.asStateFlow()

    var startCalled: Int = 0
        private set

    var closeCalled: Int = 0
        private set

    override suspend fun start() {
        startCalled++
    }

    override suspend fun close() {
        closeCalled++
    }

    fun emit(status: NetworkPathStatus) {
        _status.value = status
    }
}
