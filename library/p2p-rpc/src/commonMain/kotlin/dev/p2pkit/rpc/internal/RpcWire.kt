package dev.p2pkit.rpc.internal

import dev.p2pkit.core.PayloadBudget
import dev.p2pkit.rpc.RpcExecutionEvidence
import dev.p2pkit.rpc.RpcFailure
import dev.p2pkit.rpc.RpcFailureKind
import dev.p2pkit.rpc.RpcFailurePhase
import dev.p2pkit.rpc.validateRpcName

internal enum class WireKind(val code: Int) {
    Hello(1), Ready(2), Invoke(3), Success(4), ApplicationError(5), Failure(6),
    Status(7), Running(8), Cancel(9), Receipt(10), PairRequest(11), PairPending(12),
    PairApproved(13), PairDenied(14), Notify(15),
}

internal enum class WireFailure(val code: Int, val kind: RpcFailureKind, val evidence: RpcExecutionEvidence) {
    Overloaded(1, RpcFailureKind.Overloaded, RpcExecutionEvidence.RejectedBeforeExecution),
    Unauthorized(2, RpcFailureKind.Unauthorized, RpcExecutionEvidence.RejectedBeforeExecution),
    UnknownProcedure(3, RpcFailureKind.UnknownProcedure, RpcExecutionEvidence.RejectedBeforeExecution),
    InvalidPayload(4, RpcFailureKind.InvalidPayload, RpcExecutionEvidence.RejectedBeforeExecution),
    HandlerFailed(5, RpcFailureKind.HandlerFailed, RpcExecutionEvidence.MayHaveExecuted),
    Deadline(6, RpcFailureKind.DeadlineExceeded, RpcExecutionEvidence.MayHaveExecuted),
    Cancelled(7, RpcFailureKind.RemoteCancelled, RpcExecutionEvidence.MayHaveExecuted),
    ResultUnavailable(8, RpcFailureKind.ResultUnavailable, RpcExecutionEvidence.MayHaveExecuted),
    UnknownOutcome(9, RpcFailureKind.UnknownOutcome, RpcExecutionEvidence.MayHaveExecuted),
    HostRestarted(10, RpcFailureKind.HostRestarted, RpcExecutionEvidence.MayHaveExecuted),
    AccessRevoked(11, RpcFailureKind.Unauthorized, RpcExecutionEvidence.MayHaveExecuted),
    CancelledBeforeStart(12, RpcFailureKind.RemoteCancelled, RpcExecutionEvidence.RejectedBeforeExecution),
    DeadlineBeforeStart(13, RpcFailureKind.DeadlineExceeded, RpcExecutionEvidence.RejectedBeforeExecution),
}

/** Ownership: each instance owns exactly one optional body handle. Queue copies must use retained(). */
internal data class WireMessage(
    val kind: WireKind,
    val id: String,
    val incarnation: String = ZERO_ID,
    val name: String = "",
    val version: Int = 0,
    val budgetMillis: Int = 0,
    val attempt: Int = 0,
    val code: Int = 0,
    val body: OwnedBytes? = null,
) {
    val key: String get() = "$name/$version"
    fun retained(): WireMessage = copy(body = body?.retain())
    fun release() { body?.release() }
}

internal object RpcWire {
    const val HEADER_BYTES: Int = 56
    const val MAX_PACKET_BYTES: Int = HEADER_BYTES + 96 + 1_048_576
    const val MAJOR: Int = 1

    fun encode(message: WireMessage): ByteArray {
        validate(message)
        val result = ByteArray(HEADER_BYTES + message.name.length + (message.body?.size ?: 0))
        byteArrayOf(0x50, 0x52, 0x50, 0x43).copyInto(result)
        result[4] = MAJOR.toByte()
        result[5] = message.kind.code.toByte()
        parseHex(message.id, 16).copyInto(result, 8)
        parseHex(message.incarnation, 16).copyInto(result, 24)
        writeInt(result, 40, message.version)
        writeInt(result, 44, message.budgetMillis)
        result[48] = message.attempt.toByte()
        result[49] = message.code.toByte()
        result[50] = (message.name.length ushr 8).toByte()
        result[51] = message.name.length.toByte()
        writeInt(result, 52, message.body?.size ?: 0)
        message.name.encodeToByteArray().copyInto(result, HEADER_BYTES)
        message.body?.bytes?.copyInto(result, HEADER_BYTES + message.name.length)
        return result
    }

    fun decode(bytes: ByteArray, budget: PayloadBudget): WireMessage {
        if (bytes.size !in HEADER_BYTES..MAX_PACKET_BYTES || bytes[0] != 0x50.toByte() ||
            bytes[1] != 0x52.toByte() || bytes[2] != 0x50.toByte() || bytes[3] != 0x43.toByte()
        ) malformed()
        if (bytes[4].toInt() != MAJOR) {
            throw RpcFailure(RpcFailureKind.IncompatibleVersion, RpcFailurePhase.Negotiation)
        }
        if (bytes[6] != 0.toByte() || bytes[7] != 0.toByte()) malformed()
        val kind = WireKind.entries.firstOrNull { it.code == (bytes[5].toInt() and 255) } ?: malformed()
        val nameSize = ((bytes[50].toInt() and 255) shl 8) or (bytes[51].toInt() and 255)
        val bodySize = readInt(bytes, 52)
        if (nameSize !in 0..96 || bodySize !in 0..bodyMaximum(kind) ||
            HEADER_BYTES.toLong() + nameSize + bodySize != bytes.size.toLong()
        ) malformed()
        val bodyLease = if (bodySize == 0) null else budget.reserve(bodySize.toLong() + 256)
        var message: WireMessage? = null
        try {
            message = WireMessage(
                kind, bytes.copyOfRange(8, 24).toHex(), bytes.copyOfRange(24, 40).toHex(),
                bytes.decodeToString(HEADER_BYTES, HEADER_BYTES + nameSize, throwOnInvalidSequence = true),
                readInt(bytes, 40), readInt(bytes, 44), bytes[48].toInt() and 255, bytes[49].toInt() and 255,
                bodyLease?.let { OwnedBytes.take(bytes.copyOfRange(HEADER_BYTES + nameSize, bytes.size), it) }
            )
            validate(message)
            return message
        } catch (failure: Throwable) {
            message?.release()
            bodyLease?.release()
            if (failure is RpcFailure) throw failure
            malformed()
        }
    }

    private fun bodyMaximum(kind: WireKind): Int = when (kind) {
        WireKind.Invoke, WireKind.Success, WireKind.ApplicationError -> 1_048_576
        WireKind.Notify -> 16_384
        WireKind.Status, WireKind.Cancel, WireKind.Receipt -> 32
        WireKind.PairRequest -> 48
        else -> 0
    }

    private fun validate(message: WireMessage) {
        if (message.id == ZERO_ID || message.id.length != 32 || message.incarnation.length != 32 ||
            (message.body?.size ?: 0) > bodyMaximum(message.kind)
        ) malformed()
        val procedureMessage = message.kind in setOf(
            WireKind.Invoke, WireKind.Success, WireKind.ApplicationError, WireKind.Status,
            WireKind.Running, WireKind.Cancel, WireKind.Receipt, WireKind.Failure, WireKind.Notify
        )
        if (procedureMessage) {
            try { validateRpcName(message.name, message.version) } catch (_: IllegalArgumentException) { malformed() }
        } else if (message.name.isNotEmpty() || message.version != 0) malformed()
        if (message.kind == WireKind.Hello) {
            if (message.incarnation != ZERO_ID) malformed()
        } else if (message.incarnation == ZERO_ID) malformed()
        if (message.kind in setOf(WireKind.Success, WireKind.ApplicationError, WireKind.Notify) &&
            message.body == null
        ) malformed()
        when (message.kind) {
            WireKind.Invoke -> if (message.budgetMillis !in 1..30_000 || message.attempt !in 1..3 ||
                message.code !in 0..1 || message.body == null) malformed()
            WireKind.Status -> if (message.attempt !in 1..3 || message.body?.size != 32 ||
                message.budgetMillis != 0 || message.code != 0) malformed()
            WireKind.Cancel, WireKind.Receipt -> if (message.body?.size != 32 || message.attempt != 0 ||
                message.budgetMillis != 0 || message.code != 0) malformed()
            WireKind.Failure -> if (WireFailure.entries.none { it.code == message.code } ||
                message.budgetMillis !in 0..2_000 || message.attempt != 0) malformed()
            WireKind.Ready -> if (message.code !in 1..2 || message.budgetMillis != 0 || message.attempt != 0) {
                malformed()
            }
            WireKind.PairRequest -> if (message.body?.size != 48 || message.code != 0 ||
                message.budgetMillis != 0 || message.attempt != 0) malformed()
            else -> if (message.code != 0 || message.budgetMillis != 0 || message.attempt != 0) malformed()
        }
    }

    private fun malformed(): Nothing = throw RpcFailure(RpcFailureKind.Protocol, RpcFailurePhase.Decoding)
    private fun readInt(bytes: ByteArray, offset: Int): Int =
        ((bytes[offset].toInt() and 255) shl 24) or ((bytes[offset + 1].toInt() and 255) shl 16) or
            ((bytes[offset + 2].toInt() and 255) shl 8) or (bytes[offset + 3].toInt() and 255)

    private fun writeInt(bytes: ByteArray, offset: Int, value: Int) {
        for (index in 0..3) bytes[offset + index] = (value ushr (24 - index * 8)).toByte()
    }
}
