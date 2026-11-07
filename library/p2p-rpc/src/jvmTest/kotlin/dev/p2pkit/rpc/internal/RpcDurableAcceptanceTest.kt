package dev.p2pkit.rpc.internal

import dev.p2pkit.core.PayloadBudget
import dev.p2pkit.rpc.RpcLimits
import dev.p2pkit.rpc.RpcProcedure
import dev.p2pkit.rpc.RpcReply
import dev.p2pkit.rpc.RpcRetry
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancelAndJoin
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withContext
import kotlinx.serialization.builtins.serializer
import java.nio.ByteBuffer
import java.nio.channels.ClosedChannelException
import java.nio.channels.FileChannel
import java.nio.file.Files
import java.nio.file.StandardOpenOption
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertIs
import kotlin.test.assertTrue
import kotlin.time.Duration.Companion.seconds

class RpcDurableAcceptanceTest {
    @Test
    fun receiptObservesTheForcedJournalAndActualIoFailureSendsNoReceipt() = runBlocking {
        val directory = Files.createTempDirectory("p2pkit-acceptance-")
        val journal = directory.resolve("journal")
        val budget = PayloadBudget(8L * 1_048_576)
        val clock = MonotonicRpcClock()
        val owner = SupervisorJob(coroutineContext[Job])
        val scope = CoroutineScope(coroutineContext + owner)
        val procedure = RpcProcedure("journal.echo", 1,
            String.serializer(), String.serializer(), String.serializer())
        val descriptor = registeredProcedure(procedure, { true }) { _, value -> RpcReply.Success(value) }
        val host = RpcHostEngine(scope, mapOf(descriptor.key to descriptor), RpcLimits(), budget,
            clock, { true }, TEST_INCARNATION)
        val client = RpcClientEngine(scope, budget, clock, jitter = { 0 })
        val hostLink = RpcTestLink()
        val clientLink = RpcTestLink(1)
        var receipts = 0
        var committedId: String? = null
        try {
            host.attach(hostLink)
            hostLink.onSend = { client.onMessage(clientLink, it) }
            clientLink.onSend = {
                if (it.kind == WireKind.Receipt) {
                    receipts++
                    assertEquals(committedId, it.id)
                    assertEquals(it.id, Files.readString(journal))
                }
                host.onMessage(hostLink, it)
            }
            client.attach(clientLink)
            client.awaitReady()
            val result = client.callWithDetails(procedure, "first", 10.seconds, RpcRetry.RecoverOnly()) { accepted ->
                assertEquals(0, receipts)
                val id = accepted.details.requestId.value
                withContext(Dispatchers.IO) {
                    FileChannel.open(journal, StandardOpenOption.CREATE_NEW, StandardOpenOption.WRITE).use { channel ->
                        val bytes = ByteBuffer.wrap(id.encodeToByteArray())
                        while (bytes.hasRemaining()) channel.write(bytes)
                        channel.force(true)
                    }
                }
                committedId = id
            }
            assertEquals(result.requestId.value, committedId)
            assertEquals(1, receipts)

            val failure = runCatching {
                client.callWithDetails(procedure, "second", 10.seconds, RpcRetry.RecoverOnly()) {
                    withContext(Dispatchers.IO) {
                        val channel = FileChannel.open(journal, StandardOpenOption.WRITE)
                        channel.close()
                        channel.write(ByteBuffer.wrap(byteArrayOf(1)))
                    }
                }
            }.exceptionOrNull()
            assertIs<ClosedChannelException>(failure)
            assertEquals(1, receipts)
            assertEquals(1L, client.requestTotals.value.succeeded)
            assertEquals(1L, client.requestTotals.value.failed)
        } finally {
            try {
                try { client.close() } finally { host.close() }
            } finally {
                owner.cancelAndJoin()
                clientLink.clearSent()
                hostLink.clearSent()
                Files.deleteIfExists(journal)
                Files.deleteIfExists(directory)
            }
        }
        assertEquals(0L, budget.retainedBytes.value)
        assertTrue(Files.notExists(directory))
    }
}
