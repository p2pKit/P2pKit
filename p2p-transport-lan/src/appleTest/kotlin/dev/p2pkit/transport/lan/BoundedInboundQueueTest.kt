package dev.p2pkit.transport.lan

import kotlinx.coroutines.flow.first
import kotlinx.coroutines.runBlocking
import kotlin.test.Test
import kotlin.test.assertFalse
import kotlin.test.assertSame
import kotlin.test.assertTrue

class BoundedInboundQueueTest {

    private class Resource {
        var released: Boolean = false
    }

    @Test
    fun overflowAndTerminalDrainReleaseOnlyUnconsumedResources() = runBlocking {
        val queue = BoundedInboundQueue<Resource>(capacity = 2) { it.released = true }
        val transferred = Resource()
        val buffered = Resource()
        val overflow = Resource()

        assertTrue(queue.offer(transferred))
        assertTrue(queue.offer(buffered))
        assertFalse(queue.offer(overflow))
        assertTrue(overflow.released, "overflow must be released immediately")

        assertSame(transferred, queue.asFlow().first())
        queue.closeAndDrain()

        assertFalse(transferred.released, "a received resource belongs to the consumer")
        assertTrue(buffered.released, "terminal close must drain and release queued resources")

        val afterClose = Resource()
        assertFalse(queue.offer(afterClose))
        assertTrue(afterClose.released, "post-close hand-off must release the resource")

        queue.closeAndDrain()
    }

}
