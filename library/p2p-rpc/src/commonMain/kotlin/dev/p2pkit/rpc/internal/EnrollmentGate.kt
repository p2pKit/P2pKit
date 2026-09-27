package dev.p2pkit.rpc.internal

import kotlinx.coroutines.flow.MutableStateFlow

internal class EnrollmentGate(private val clock: RpcClock) {
    val until = MutableStateFlow(0L)
    val isOpen: Boolean get() = clock.now() < until.value
}
