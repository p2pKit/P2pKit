package dev.p2pkit.transport.lan

import java.io.IOException
import java.util.IdentityHashMap

/** Darwin scoped sockets keep their token registry, IP_BOUND_IF and original close-drain contract. */
internal class MacSocketPoller(private val api: MacLanCalls, private val async: MacLanAsyncCalls) : SocketPoller<Long> {
    private val wakeRead: MacLanHandle
    private val wakeWrite: MacLanHandle

    init {
        val output = LongArray(2)
        var thrown: Throwable? = null
        val result = try { async.wakeOpen(output) } catch (failure: Throwable) { thrown = failure; -1 }
        wakeRead = MacLanHandle(api, output[0])
        wakeWrite = MacLanHandle(api, output[1])
        if (result != 0 || output.any { it == 0L }) {
            val failure = thrown ?: IOException("Scoped TCP readiness creation failed (errno=$result)")
            try { close() } catch (cleanup: Throwable) { failure.addSuppressed(cleanup) }
            throw failure
        }
    }

    override fun wakeup() {
        val result = async.wake(wakeWrite.value())
        if (result != 0) throw macSocketError("readiness wake", result)
    }

    override fun select(interests: List<SocketInterest<Long>>): IntArray {
        val handles = interests.map { it.key }.toLongArray()
        val operations = interests.map { it.operations }.toIntArray()
        val ready = IntArray(interests.size)
        val result = async.pollMany(wakeRead.value(), handles, operations, ready)
        if (result != 0) throw macSocketError("readiness batch", result)
        check(ready.all { it in 0..3 }) { "Invalid native readiness result" }
        return ready
    }

    override fun close() {
        var failure: Throwable? = null
        try { wakeWrite.close() } catch (error: Throwable) { failure = error }
        try { wakeRead.close() } catch (error: Throwable) {
            if (failure == null) failure = error else failure.addSuppressed(error)
        }
        failure?.let { throw it }
    }

    companion object {
        // One loaded production JNI provider. Separate fake providers are deterministic internal tests only.
        private val backends = IdentityHashMap<MacLanCalls, SocketReadiness<Long>>()
        fun forApi(api: MacLanCalls): SocketReadiness<Long>? {
            val async = api as? MacLanAsyncCalls ?: return null
            return synchronized(backends) {
                backends.getOrPut(api) { SocketReadiness("p2pkit-macos-readiness") { MacSocketPoller(api, async) } }
            }
        }
    }
}
