package dev.p2pkit.sample.rpc

import kotlinx.serialization.Serializable
import dev.p2pkit.rpc.RpcCallStage
import dev.p2pkit.rpc.RpcExecutionEvidence

internal val deviceTestPlatforms = setOf("Unknown", "Android", "iPhone", "Mac (JVM)", "Windows (JVM)", "Linux (JVM)")
internal val deviceTestProcedures = setOf("qualification.echo", "qualification.large-echo", "users.get",
    "device-tests.source", "device-tests.begin", "device-tests.progress", "device-tests.ack",
    "device-tests.report", "device-tests.delayed")

/** Safe test observations: no body, network address, key, fingerprint or engine request identifier. */
@Serializable
public data class RpcDeviceTestObservation(
    public val side: RpcRequestSide,
    public val procedure: String,
    public val outcome: RpcRequestOutcome,
    public val elapsedMillis: Long,
    public val encodedBytes: Int? = null,
    public val executionEvidence: String? = null,
    public val clientStage: String? = null,
) {
    public val title: String get() =
        "${if (side == RpcRequestSide.Host) "Received here" else "Sent from here"}: $procedure · $outcome" +
            (encodedBytes?.let { " · $it encoded bytes" } ?: "") + " · $elapsedMillis ms" +
            (clientStage?.let { " · $it" } ?: "") +
            (executionEvidence?.let { " · execution: $it" } ?: "")
}

internal fun RpcRequestEntry.testObservation(): RpcDeviceTestObservation = RpcDeviceTestObservation(
    side, procedure, outcome, elapsedMillis,
    Regex("\\[generated test body; encodedBytes=([0-9]+)]").matchEntire(requestPreview)
        ?.groupValues?.get(1)?.toIntOrNull(), executionEvidence?.name, clientStage,
)

internal fun validTestObservation(value: RpcDeviceTestObservation): Boolean =
    value.procedure in deviceTestProcedures && value.elapsedMillis in 0..1_850_000 &&
        (value.encodedBytes == null || value.encodedBytes in 0..RpcCapacityContract.MAXIMUM_BODY_BYTES) &&
        (value.executionEvidence == null || RpcExecutionEvidence.entries.any { it.name == value.executionEvidence }) &&
        (value.clientStage == null || RpcCallStage.entries.any { it.name == value.clientStage })
