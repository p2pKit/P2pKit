package dev.p2pkit.rpc.internal

import kotlinx.coroutines.flow.MutableStateFlow

internal class EnrollmentGate(private val clock: RpcClock) {
    val until = MutableStateFlow(0L)
    val nearbyApproval = MutableStateFlow(false)
    val isOpen: Boolean get() = nearbyApproval.value || clock.now() < until.value
}
