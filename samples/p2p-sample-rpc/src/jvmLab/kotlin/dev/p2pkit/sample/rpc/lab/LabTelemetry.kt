package dev.p2pkit.sample.rpc.lab

import com.sun.management.OperatingSystemMXBean
import dev.p2pkit.rpc.RpcDiagnostics
import dev.p2pkit.sample.rpc.RpcCapacityHost
import dev.p2pkit.sample.rpc.RpcCapacityHostSnapshot
import dev.p2pkit.sample.rpc.RpcCapacityHostTelemetry
import java.lang.management.ManagementFactory
import java.nio.file.Files
import java.nio.file.Path
import java.util.concurrent.TimeUnit

internal object LabTelemetry {
    private fun ownProcessOutput(vararg command: String): String {
        val process = ProcessBuilder(*command).redirectErrorStream(true).start()
        // Observation only; no retained PID becomes signaling authority on a timeout.
        check(process.waitFor(2, TimeUnit.SECONDS)) { "Host resource observer did not settle" }
        check(process.exitValue() == 0)
        return process.inputStream.use { input ->
            val bytes = input.readNBytes(65_537)
            check(bytes.size <= 65_536)
            bytes.toString(Charsets.US_ASCII)
        }
    }

    fun sample(host: RpcCapacityHost, sequence: Long, runLabel: String): Map<String, String> {
        val processCpu = (ManagementFactory.getOperatingSystemMXBean() as OperatingSystemMXBean).processCpuTime
        val uptime = ManagementFactory.getRuntimeMXBean().uptime
        val rss: Long
        val threads: Int
        if (System.getProperty("os.name") == "Linux") {
            val status = Files.readString(Path.of("/proc/self/status"))
            rss = checkNotNull(Regex("(?m)^VmRSS:\\s+([0-9]+) kB$").find(status)).groupValues[1].toLong() * 1024
            threads = checkNotNull(Regex("(?m)^Threads:\\s+([0-9]+)$").find(status)).groupValues[1].toInt()
        } else {
            check(System.getProperty("os.name") == "Mac OS X")
            val self = ProcessHandle.current().pid().toString()
            rss = ownProcessOutput("/bin/ps", "-p", self, "-o", "rss=").trim().toLong() * 1024
            val rows = ownProcessOutput("/bin/ps", "-M", "-p", self, "-o", "pid=")
                .lineSequence().map(String::trim).filter(String::isNotEmpty).toList()
            check(rows.isNotEmpty() && rows.all { it == self }) { "Unverifiable actual host thread census" }
            threads = rows.size
        }
        check(processCpu >= 0 && uptime >= 0 && rss > 0 && threads > 0 && sequence >= 0)
        val snapshot = host.snapshot()
        val stats = snapshot.diagnostics
        return linkedMapOf(
            "schema" to "1", "runLabel" to runLabel, "sequence" to sequence.toString(),
            "uptimeMillis" to uptime.toString(), "cpuNanos" to processCpu.toString(),
            "residentBytes" to rss.toString(), "nativeThreads" to threads.toString(),
            "jvmThreads" to ManagementFactory.getThreadMXBean().threadCount.toString(),
            "connected" to snapshot.distinctAuthenticatedClients.toString(),
            "accepted" to stats.acceptedCalls.toString(), "completed" to stats.completedCalls.toString(),
            "refused" to stats.refusedCalls.toString(), "duplicates" to stats.duplicateRequests.toString(),
            "droppedNotifications" to stats.droppedNotifications.toString(),
            "protocolFailures" to stats.protocolFailures.toString(),
            "connectionFailures" to stats.connectionFailures.toString(), "running" to stats.runningCalls.toString(),
            "queued" to stats.queuedCalls.toString(), "records" to stats.retainedRecords.toString(),
            "payloadBytes" to stats.retainedPayloadBytes.toString(),
        )
    }

    fun decode(values: Map<String, String>, runLabel: String): RpcCapacityHostTelemetry {
        require(values.keys == setOf(
            "schema", "runLabel", "sequence", "uptimeMillis", "cpuNanos", "residentBytes", "nativeThreads",
            "jvmThreads",
            "connected", "accepted", "completed", "refused", "duplicates", "droppedNotifications", "protocolFailures",
            "connectionFailures", "running", "queued", "records", "payloadBytes",
        ))
        require(values.getValue("schema") == "1" && values.getValue("runLabel") == runLabel)
        fun long(name: String): Long = values.getValue(name).let {
            require(it.matches(Regex("0|[1-9][0-9]{0,18}")))
            it.toLong().also { value -> require(value >= 0) }
        }
        fun int(name: String): Int = long(name).also { require(it <= Int.MAX_VALUE) }.toInt()
        require(long("sequence") >= 0 && int("connected") in 0..128 && int("jvmThreads") > 0)
        require(int("running") in 0..128 && int("queued") in 0..256 && int("records") in 0..131_072)
        require(long("payloadBytes") in 0..64L * 1_048_576)
        return RpcCapacityHostTelemetry(
            RpcCapacityHostSnapshot(
                int("connected"), RpcDiagnostics(
                    long("accepted"), long("completed"), long("refused"), long("duplicates"),
                    long("droppedNotifications"), long("protocolFailures"), long("connectionFailures"),
                    int("running"), int("queued"), int("records"), long("payloadBytes"),
                ),
            ),
            long("uptimeMillis"), long("cpuNanos"), long("residentBytes"), int("nativeThreads"),
        )
    }
}
