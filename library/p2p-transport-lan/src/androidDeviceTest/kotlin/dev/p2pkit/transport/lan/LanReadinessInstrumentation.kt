package dev.p2pkit.transport.lan

import android.app.Activity
import android.app.Instrumentation
import android.os.Bundle
import android.os.Debug
import android.os.Process
import java.io.File
import java.net.InetAddress
import java.net.InetSocketAddress
import java.net.ServerSocket
import java.nio.channels.ServerSocketChannel
import java.nio.channels.SocketChannel
import java.util.concurrent.atomic.AtomicLongArray
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.NonCancellable
import kotlinx.coroutines.async
import kotlinx.coroutines.awaitAll
import kotlinx.coroutines.cancelAndJoin
import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withContext
import kotlinx.coroutines.withTimeout
import org.json.JSONArray
import org.json.JSONObject

/**
 * Real public NIO and original native accepted-descriptor byte I/O on ART. The native loopback fixture
 * deliberately uses the internal test binding: it does NOT qualify Network marks, authentication,
 * organization-LAN routing, physical links, foreground/background RPC or device capacity.
 */
class LanReadinessInstrumentation : Instrumentation() {
    private var phase = "start"

    override fun onCreate(arguments: Bundle?) {
        super.onCreate(arguments)
        start()
    }

    override fun onStart() {
        super.onStart()
        val results = JSONArray()
        var failure: Throwable? = null
        try {
            runBlocking(Dispatchers.Default) {
                withTimeout(360_000) {
                    for (native in listOf(false, true)) for (clients in listOf(128, 256)) {
                        phase = (if (native) "native" else "nio") + "-$clients"
                        results.put(measure(native, clients))
                    }
                }
            }
        } catch (error: Throwable) { failure = error }
        val receipt = Bundle().apply {
            putString("scope", "RAW_ANDROID_IO_NOT_AUTHENTICATED_RPC_OR_PHYSICAL_QUALIFICATION")
            putString("outcome", if (failure == null) "PASS" else "FAIL")
            putInt("completed", results.length())
            putString("measurements", results.toString())
            if (failure != null) {
                putString("failurePhase", phase)
                putString("failureType", failure.javaClass.simpleName)
                putString("failureFrames", failure.stackTrace.filter {
                    it.className.startsWith("dev.p2pkit.transport.lan.")
                }.take(8).joinToString(";") { "${it.methodName}:${it.lineNumber}" })
            }
        }
        finish(if (failure == null) Activity.RESULT_OK else Activity.RESULT_CANCELED, receipt)
    }

    private fun threads(): Int = checkNotNull(Regex("(?m)^Threads:\\s+([0-9]+)$")
        .find(File("/proc/self/status").readText())).groupValues[1].toInt()

    private fun heap(): Long = Runtime.getRuntime().let { it.totalMemory() - it.freeMemory() }

    private suspend fun measure(native: Boolean, count: Int): JSONObject = coroutineScope {
        val loopback = InetAddress.getByName("127.0.0.1") // Literal fixture only; production numeric guards unchanged.
        val listener: ServerSocket = if (native) AndroidNetworkServerSocket(null, AndroidOsSocketOps) { }
            else ServerSocketChannel.open().socket()
        val owners = mutableListOf<AndroidRawConnection>()
        val jobs = mutableListOf<Job>()
        val peers = mutableListOf<Pair<AndroidRawConnection, Channel<ByteArray>>>()
        val histogram = AtomicLongArray(30_002)
        val payload = ByteArray(1024) { (it % 127).toByte() }
        val beforeThreads = threads()
        val beforeHeap = heap()
        try {
            listener.bind(InetSocketAddress(loopback, 0), 32)
            repeat(count) {
                val outgoing = SocketChannel.open().socket()
                try {
                    outgoing.tcpNoDelay = true
                    outgoing.connect(InetSocketAddress(loopback, listener.localPort), 5_000)
                    val incoming = listener.accept()
                    try {
                        incoming.tcpNoDelay = true
                        val host = AndroidRawConnection(incoming, io = AndroidLanIo(true)).also { owners += it }
                        jobs += launch { host.read().collect { host.write(it) } }
                    } catch (error: Throwable) { incoming.close(); throw error }
                    val peer = AndroidRawConnection(outgoing, io = AndroidLanIo(true)).also { owners += it }
                    val received = Channel<ByteArray>(1)
                    peers += peer to received
                    jobs += launch {
                        try { peer.read().collect { received.send(it) } } finally { received.close() }
                    }
                } catch (error: Throwable) { outgoing.close(); throw error }
            }
            suspend fun exchange(peer: Pair<AndroidRawConnection, Channel<ByteArray>>) {
                peer.first.write(payload)
                var offset = 0
                while (offset < payload.size) {
                    val returned = peer.second.receive()
                    check(returned.isNotEmpty() && returned.size <= payload.size - offset)
                    returned.forEach { value -> check(value == payload[offset++]) }
                }
            }
            repeat(3) { peers.map { peer -> async { exchange(peer) } }.awaitAll() }
            delay(3_000)
            val idleThreads = threads()
            val idleHeap = heap()
            val idlePss = Debug.getPss() * 1024
            val workerNames = setOf("p2pkit-nio-readiness", "p2pkit-android-readiness")
            val readinessThreads = Thread.getAllStackTraces().keys.count { it.name in workerNames }
            check(readinessThreads == if (native) 2 else 1)
            check(idleThreads - beforeThreads < 80) { "Per-client blocked thread growth" }
            val idleStart = System.nanoTime()
            val cpuStart = Process.getElapsedCpuTime()
            delay(5_000)
            val idleWall = System.nanoTime() - idleStart
            val idleCpu = Process.getElapsedCpuTime() - cpuStart
            val workloadCpuStart = Process.getElapsedCpuTime()
            val workloadStart = System.nanoTime() + 200_000_000
            peers.mapIndexed { index, peer -> async {
                repeat(300) { tick ->
                    val remaining = workloadStart + tick * 100_000_000L + index * 100_000_000L / count -
                        System.nanoTime()
                    if (remaining > 0) delay((remaining + 999_999) / 1_000_000)
                    val sent = System.nanoTime()
                    exchange(peer)
                    histogram.incrementAndGet(minOf(30_001L, (System.nanoTime() - sent + 999_999) / 1_000_000)
                        .toInt())
                }
            } }.awaitAll()
            val workloadWall = System.nanoTime() - workloadStart
            fun percentile(percent: Int): Int {
                val required = (count * 300L * percent + 99) / 100
                var seen = 0L
                for (index in 0 until histogram.length()) {
                    seen += histogram.get(index)
                    if (seen >= required) return index
                }
                error("Incomplete response histogram")
            }
            check((0 until histogram.length()).sumOf { histogram.get(it) } == count * 300L)
            JSONObject().apply {
                put("backend", if (native) "native-os-poll" else "nio-selector")
                put("clients", count); put("responses", count * 300); put("bytesPerResponse", payload.size)
                put("threadsBefore", beforeThreads); put("threadsIdle", idleThreads)
                put("readinessThreads", readinessThreads)
                put("heapBeforeBytes", beforeHeap); put("heapIdleBytes", idleHeap); put("pssIdleBytes", idlePss)
                put("heapAfterBytes", heap()); put("pssAfterBytes", Debug.getPss() * 1024)
                put("idleWallNs", idleWall); put("idleCpuMs", idleCpu)
                put("activeWallNs", workloadWall); put("activeCpuMs", Process.getElapsedCpuTime() - workloadCpuStart)
                put("p95UpperMs", percentile(95)); put("p99UpperMs", percentile(99))
            }
        } finally {
            withContext(NonCancellable) {
                var failure: Throwable? = null
                for (owner in owners) try { owner.close() } catch (error: Throwable) {
                    if (failure == null) failure = error else failure.addSuppressed(error)
                }
                try { listener.close() } catch (error: Throwable) {
                    if (failure == null) failure = error else failure.addSuppressed(error)
                }
                withTimeout(10_000) { jobs.forEach { it.cancelAndJoin() } }
                check(Thread.getAllStackTraces().keys.none {
                    it.name == "p2pkit-nio-readiness" || it.name == "p2pkit-android-readiness"
                }) { "Readiness worker not retired" }
                failure?.let { throw it }
            }
        }
    }
}
