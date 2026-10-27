package dev.p2pkit.sample.rpc

import dev.p2pkit.core.PeerFingerprint
import dev.p2pkit.rpc.RpcHostConfiguration
import dev.p2pkit.rpc.RpcProcedure
import dev.p2pkit.rpc.RpcReply
import kotlinx.coroutines.awaitCancellation
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.serialization.builtins.serializer

/** Fixed synthetic controls enabled only by the explicit schema2 capacity host, never ordinary app mode. */
public object RpcCapacityExercises {
    public const val SLOW_HANDLER_MILLIS: Long = 1_000
    private fun procedure(name: String): RpcProcedure<String, String, String> = RpcProcedure(
        "qualification.exercise.$name", 1, String.serializer(), String.serializer(), String.serializer(),
        requestLimitBytes = 1024, responseLimitBytes = 1024, errorLimitBytes = 256,
    )
    public val echo: RpcProcedure<String, String, String> = procedure("echo")
    public val reject: RpcProcedure<String, String, String> = procedure("reject")
    public val denied: RpcProcedure<String, String, String> = procedure("denied")
    public val hold: RpcProcedure<String, String, String> = procedure("hold")
    public val slow: RpcProcedure<String, String, String> = procedure("slow")
    public val state: RpcProcedure<String, String, String> = procedure("state")
}

internal data class CapacityExerciseCounters(
    val holdEntered: Long = 0,
    val holdRetired: Long = 0,
    val slowEntered: Long = 0,
    val slowRetired: Long = 0,
    val deniedInvocations: Long = 0,
) {
    fun record(): String = "$holdEntered,$holdRetired,$slowEntered,$slowRetired,$deniedInvocations"
}

/** One bounded host ledger proves remote handler entry and retirement, not a local coroutine guess. */
internal class CapacityExerciseHostState {
    private val counters = MutableStateFlow(CapacityExerciseCounters())
    fun snapshot(): CapacityExerciseCounters = counters.value

    private fun update(transform: (CapacityExerciseCounters) -> CapacityExerciseCounters) {
        while (true) {
            val previous = counters.value
            if (counters.compareAndSet(previous, transform(previous))) return
        }
    }

    suspend fun hold(value: String): Nothing {
        require(value in setOf("deadline", "cancel", "disconnect"))
        update { it.copy(holdEntered = it.holdEntered + 1) }
        // The actual RPC request deadline (at most10 seconds in these controls) and host ownership
        // cancel this handler. A disconnect need not immediately undo already-started remote work.
        try { awaitCancellation() } finally { update { it.copy(holdRetired = it.holdRetired + 1) } }
    }

    suspend fun slow(value: String): RpcReply<String, String> {
        update { it.copy(slowEntered = it.slowEntered + 1) }
        return try {
            delay(RpcCapacityExercises.SLOW_HANDLER_MILLIS)
            RpcReply.Success(value)
        } finally { update { it.copy(slowRetired = it.slowRetired + 1) } }
    }

    fun denied(): RpcReply<String, String> {
        update { it.copy(deniedInvocations = it.deniedInvocations + 1) }
        return RpcReply.Success("must-not-execute")
    }
}

internal fun RpcHostConfiguration.registerCapacityExercises(pins: Set<PeerFingerprint>) {
    capacityProfileLimits(pins.size)
    val approved = pins.toSet()
    val state = CapacityExerciseHostState()
    register(RpcCapacityExercises.echo, authorize = { it.fingerprint in approved }) { _, value ->
        RpcReply.Success(value)
    }
    register(RpcCapacityExercises.reject, authorize = { it.fingerprint in approved }) { _, _ ->
        RpcReply.ApplicationError("synthetic")
    }
    register(RpcCapacityExercises.denied, authorize = { false }) { _, _ -> state.denied() }
    register(RpcCapacityExercises.hold, authorize = { it.fingerprint in approved }) { _, value -> state.hold(value) }
    register(RpcCapacityExercises.slow, authorize = { it.fingerprint in approved }) { _, value -> state.slow(value) }
    register(RpcCapacityExercises.state, authorize = { it.fingerprint in approved }) { _, _ ->
        RpcReply.Success(state.snapshot().record())
    }
}
