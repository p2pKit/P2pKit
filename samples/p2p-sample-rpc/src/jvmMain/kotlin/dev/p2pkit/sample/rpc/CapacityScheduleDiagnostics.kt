package dev.p2pkit.sample.rpc

import com.sun.management.OperatingSystemMXBean
import java.lang.management.ManagementFactory
import java.nio.file.Files
import java.nio.file.Path
import java.util.concurrent.atomic.AtomicBoolean
import java.util.concurrent.atomic.AtomicLong
import java.util.concurrent.atomic.AtomicLongArray

/** Diagnostic-only classification. None of these observations waive the original missed-clock gate. */
internal enum class CapacityDispatchStage {
    Considered, TimerLate, PermitUnavailable, Enqueued, WorkerStarted, WorkerLate, Dispatched, Completed, Failed,
}

/** Fixed-size, per-scheduled-second accounting; no request IDs, identities, exceptions or payloads. */
internal class CapacityScheduleDiagnostics {
    private val stages = CapacityDispatchStage.entries.size
    private val bins = AtomicLongArray(RpcCapacityContract.STEADY_SECONDS * stages)
    private val maxTimerDelay = AtomicLongArray(RpcCapacityContract.STEADY_SECONDS)
    private val maxWorkerDelay = AtomicLongArray(RpcCapacityContract.STEADY_SECONDS)
    private val latestObservation = AtomicLongArray(RpcCapacityContract.STEADY_SECONDS)
    val lastClockNanos = AtomicLong()

    fun record(tick: Int, stage: CapacityDispatchStage, elapsedNanos: Long, delayNanos: Long = 0) {
        require(tick in 0 until RpcCapacityContract.STEADY_SECONDS * 10 && elapsedNanos >= 0 && delayNanos >= 0)
        val second = tick / 10
        bins.incrementAndGet(second * stages + stage.ordinal)
        latestObservation.accumulateAndGet(second, elapsedNanos, ::maxOf)
        when (stage) {
            CapacityDispatchStage.Considered -> maxTimerDelay.accumulateAndGet(second, delayNanos, ::maxOf)
            CapacityDispatchStage.WorkerStarted -> maxWorkerDelay.accumulateAndGet(second, delayNanos, ::maxOf)
            else -> Unit
        }
    }

    fun total(stage: CapacityDispatchStage): Long = (0 until RpcCapacityContract.STEADY_SECONDS)
        .sumOf { bins.get(it * stages + stage.ordinal) }

    fun verify(expected: Long, dispatched: Long, completed: Long, failed: Long, missed: Long) {
        check(total(CapacityDispatchStage.Considered) == expected)
        check(total(CapacityDispatchStage.Considered) == total(CapacityDispatchStage.TimerLate) +
            total(CapacityDispatchStage.PermitUnavailable) + total(CapacityDispatchStage.Enqueued))
        check(total(CapacityDispatchStage.Enqueued) == total(CapacityDispatchStage.WorkerStarted))
        check(total(CapacityDispatchStage.WorkerStarted) == total(CapacityDispatchStage.WorkerLate) + dispatched)
        check(total(CapacityDispatchStage.TimerLate) + total(CapacityDispatchStage.PermitUnavailable) +
            total(CapacityDispatchStage.WorkerLate) == missed)
        check(total(CapacityDispatchStage.Dispatched) == dispatched &&
            total(CapacityDispatchStage.Completed) == completed && total(CapacityDispatchStage.Failed) == failed)
        check(dispatched == completed + failed && expected == dispatched + missed)
    }

    fun dump() {
        println("scheduleBins,scheduledSecond," + CapacityDispatchStage.entries.joinToString(",") { it.name } +
            ",maxTimerDelayNs,maxWorkerQueueNs,lastObservedElapsedNs")
        repeat(RpcCapacityContract.STEADY_SECONDS) { second ->
            println("scheduleBins,$second," + (0 until stages).joinToString(",") {
                bins.get(second * stages + it).toString()
            } + ",${maxTimerDelay.get(second)},${maxWorkerDelay.get(second)},${latestObservation.get(second)}")
        }
    }
}

/** An independently owned observer: its sampling clock does not use the coroutine timer/worker pool. */
internal class CapacityRuntimeObserver(private val diagnostics: CapacityScheduleDiagnostics) : AutoCloseable {
    private val stopping = AtomicBoolean()
    private val failed = AtomicBoolean()
    private var worker: Thread? = null

    fun start(origin: Long, clock: Thread) {
        check(worker == null)
        diagnostics.lastClockNanos.set(origin)
        val thread = Thread({
            try {
                observe(origin, clock)
            } catch (_: InterruptedException) {
                if (!stopping.get()) failed.set(true)
            } catch (_: Exception) {
                // Never expose raw JVM/proc observation errors or environment information.
                failed.set(true)
            }
        }, "rpc-capacity-observer")
        worker = thread
        thread.start()
    }

    private fun observe(origin: Long, clock: Thread) {
        val threads = ManagementFactory.getThreadMXBean()
        val runtime = ManagementFactory.getRuntimeMXBean()
        val process = ManagementFactory.getOperatingSystemMXBean() as OperatingSystemMXBean
        check(threads.isThreadCpuTimeSupported && threads.isThreadCpuTimeEnabled)
        var priorSample = origin
        var count = 0
        println("runtime,elapsedNs,uptimeMs,sampleGapNs,cpuNs,heapBytes,clockLagNs,clockCpuNs,clockState," +
            "workerThreads,runnableWorkers,workerCpuNs,defaultTimerCpuNs,defaultTimerState," +
            "selfMinorFaults,selfMajorFaults,availableKiB,scanDirect,scanKswapd,allocstall,stealJiffies," +
            "balloonInflate,balloonDeflate,balloonMigrate")
        while (!stopping.get()) {
            check(count++ < 2400)
            val now = System.nanoTime()
            val all = threads.getThreadInfo(threads.allThreadIds).filterNotNull()
            val pool = all.filter { it.threadName.startsWith("DefaultDispatcher-worker-") }
            val timer = all.singleOrNull { it.threadName == "kotlinx.coroutines.DefaultExecutor" }
            val clockInfo = threads.getThreadInfo(clock.id)
            val system = linuxCounters()
            println("runtime,${now - origin},${runtime.uptime},${now - priorSample},${process.processCpuTime}," +
                "${ManagementFactory.getMemoryMXBean().heapMemoryUsage.used}," +
                "${(now - diagnostics.lastClockNanos.get()).coerceAtLeast(0)}," +
                "${threads.getThreadCpuTime(clock.id)},${clockInfo?.threadState?.name ?: "ABSENT"}," +
                "${pool.size},${pool.count { it.threadState == Thread.State.RUNNABLE }}," +
                "${pool.sumOf { threads.getThreadCpuTime(it.threadId).coerceAtLeast(0) }}," +
                "${timer?.let { threads.getThreadCpuTime(it.threadId) } ?: -1}," +
                "${timer?.threadState?.name ?: "ABSENT"}," + system.joinToString(","))
            priorSample = now
            Thread.sleep(1000)
        }
    }

    private fun linuxCounters(): List<Long> {
        if (System.getProperty("os.name") != "Linux") return List(10) { -1 }
        val own = Files.readString(Path.of("/proc/self/stat")).substringAfterLast(") ").trim().split(Regex("\\s+"))
        val mem = Files.readString(Path.of("/proc/meminfo"))
        val available = checkNotNull(Regex("(?m)^MemAvailable:\\s+([0-9]+) kB$").find(mem)).groupValues[1].toLong()
        val vm = Files.readString(Path.of("/proc/vmstat")).lineSequence().filter(String::isNotBlank).associate {
            val (key, value) = it.split(' ')
            key to value.toLong()
        }
        val cpu = Files.readString(Path.of("/proc/stat")).lineSequence().first().trim().split(Regex("\\s+"))
        return listOf(own[7].toLong(), own[9].toLong(), available, vm["pgscan_direct"] ?: -1,
            vm["pgscan_kswapd"] ?: -1, vm.filterKeys { it.startsWith("allocstall_") }.values.sum(), cpu[8].toLong(),
            vm["balloon_inflate"] ?: -1, vm["balloon_deflate"] ?: -1, vm["balloon_migrate"] ?: -1)
    }

    override fun close() {
        stopping.set(true)
        worker?.let {
            it.interrupt()
            it.join(5_000)
            check(!it.isAlive) { "Capacity runtime observer did not retire" }
        }
        check(!failed.get()) { "Capacity runtime observer failed" }
    }
}
