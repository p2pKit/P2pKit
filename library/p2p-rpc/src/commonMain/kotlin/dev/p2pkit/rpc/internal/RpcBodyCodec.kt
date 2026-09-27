package dev.p2pkit.rpc.internal

import dev.p2pkit.core.PayloadBudget
import dev.p2pkit.core.PayloadLease
import dev.p2pkit.rpc.RpcFailure
import dev.p2pkit.rpc.RpcFailureKind
import dev.p2pkit.rpc.RpcFailurePhase
import kotlinx.coroutines.CancellationException
import kotlinx.io.Buffer
import kotlinx.io.RawSink
import kotlinx.io.buffered
import kotlinx.io.readByteArray
import kotlinx.serialization.ExperimentalSerializationApi
import kotlinx.serialization.KSerializer
import kotlinx.serialization.builtins.serializer
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.io.encodeToSink

internal object RpcBodyCodec {
    val json: Json = Json {
        encodeDefaults = true
        ignoreUnknownKeys = false
        isLenient = false
        allowStructuredMapKeys = false
        allowSpecialFloatingPointValues = false
        coerceInputValues = false
    }

    fun encodingAllowance(limit: Int): Long = 4L * limit + 32_768

    @OptIn(ExperimentalSerializationApi::class)
    fun <T> encode(
        serializer: KSerializer<T>,
        value: T,
        limit: Int,
        budget: PayloadBudget,
        reservation: PayloadLease? = null,
    ): OwnedBytes {
        val lease = reservation ?: budget.tryReserve(encodingAllowance(limit))
            ?: throw RpcFailure(RpcFailureKind.Overloaded, RpcFailurePhase.Encoding)
        val output = Buffer()
        val raw = object : RawSink {
            override fun write(source: Buffer, byteCount: Long) {
                if (byteCount < 0 || byteCount > limit.toLong() - output.size) invalid(RpcFailurePhase.Encoding)
                output.write(source, byteCount)
            }
            override fun flush() = Unit
            override fun close() = Unit
        }
        val sink = raw.buffered()
        return try {
            json.encodeToSink(serializer, value, sink)
            sink.flush()
            val bytes = output.readByteArray()
            JsonPreflight(bytes.decodeToString(throwOnInvalidSequence = true)).validate()
            lease.shrinkTo(bytes.size.toLong() + 256)
            OwnedBytes.take(bytes, lease)
        } catch (cancelled: CancellationException) {
            lease.release()
            throw cancelled
        } catch (failure: Exception) {
            lease.release()
            if (failure is RpcFailure) throw RpcFailure(failure.kind, RpcFailurePhase.Encoding)
            invalid(RpcFailurePhase.Encoding)
        } finally {
            // A failed serializer never gains a later chance to enqueue its partial output.
            runCatching { sink.close() }
            output.clear()
        }
    }

    fun <T> decode(
        serializer: KSerializer<T>, body: OwnedBytes, limit: Int, budget: PayloadBudget,
        reservation: PayloadLease? = null,
    ): T {
        if (body.size > limit) invalid(RpcFailurePhase.Decoding)
        val scratch = reservation ?: budget.tryReserve(4L * body.size + 32_768)
            ?: throw RpcFailure(RpcFailureKind.Overloaded, RpcFailurePhase.Decoding)
        return try {
            val text = body.bytes.decodeToString(throwOnInvalidSequence = true)
            JsonPreflight(text).validate()
            json.decodeFromString(serializer, text)
        } catch (cancelled: CancellationException) {
            throw cancelled
        } catch (failure: Exception) {
            if (failure is RpcFailure) throw failure
            invalid(RpcFailurePhase.Decoding)
        } finally {
            scratch.release()
        }
    }

    private fun invalid(phase: RpcFailurePhase): Nothing = throw RpcFailure(RpcFailureKind.InvalidPayload, phase)
}

/** Structural preflight before serializers/object graphs: strict grammar, depth, tokens and duplicate keys. */
internal class JsonPreflight(private val text: String) {
    private var at = 0
    private var tokens = 0

    fun validate() {
        value(0)
        whitespace()
        if (at != text.length) invalid()
    }

    private fun value(depth: Int) {
        if (depth > 32 || ++tokens > 131_072) invalid()
        whitespace()
        when (peek()) {
            '{' -> {
                at++
                whitespace()
                val keys = mutableSetOf<String>()
                if (take('}')) return
                while (true) {
                    whitespace()
                    val start = at
                    string()
                    if (at - start > 1_024 || keys.size >= 128) invalid()
                    val key = RpcBodyCodec.json.decodeFromString(String.serializer(), text.substring(start, at))
                    if (key.length > 256 || !keys.add(key)) invalid()
                    whitespace()
                    if (!take(':')) invalid()
                    value(depth + 1)
                    whitespace()
                    if (take('}')) break
                    if (!take(',')) invalid()
                }
            }
            '[' -> {
                at++
                whitespace()
                if (take(']')) return
                while (true) {
                    value(depth + 1)
                    whitespace()
                    if (take(']')) break
                    if (!take(',')) invalid()
                }
            }
            '"' -> string()
            't' -> literal("true")
            'f' -> literal("false")
            'n' -> literal("null")
            '-', in '0'..'9' -> number()
            else -> invalid()
        }
    }

    private fun string() {
        if (!take('"')) invalid()
        while (at < text.length) {
            val char = text[at++]
            when {
                char == '"' -> return
                char < ' ' -> invalid()
                char == '\\' -> {
                    if (at >= text.length) invalid()
                    when (text[at++]) {
                        '"', '\\', '/', 'b', 'f', 'n', 'r', 't' -> Unit
                        'u' -> repeat(4) {
                            if (at >= text.length || text[at++] !in "0123456789abcdefABCDEF") invalid()
                        }
                        else -> invalid()
                    }
                }
            }
        }
        invalid()
    }

    private fun number() {
        val start = at
        take('-')
        if (!take('0')) {
            if (peek() !in '1'..'9') invalid()
            while (peek() in '0'..'9') at++
        }
        if (take('.')) {
            if (peek() !in '0'..'9') invalid()
            while (peek() in '0'..'9') at++
        }
        if (take('e') || take('E')) {
            if (!take('+')) take('-')
            if (peek() !in '0'..'9') invalid()
            while (peek() in '0'..'9') at++
        }
        if (at - start > 128) invalid()
    }

    private fun literal(value: String) {
        if (!text.startsWith(value, at)) invalid()
        at += value.length
    }
    private fun whitespace() { while (peek() in " \t\r\n") at++ }
    private fun peek(): Char = text.getOrNull(at) ?: '\u0000'
    private fun take(char: Char): Boolean = (peek() == char).also { if (it) at++ }
    private fun invalid(): Nothing = throw RpcFailure(RpcFailureKind.InvalidPayload, RpcFailurePhase.Decoding)
}
