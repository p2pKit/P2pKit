package dev.p2pkit.sample.rpc.lab

import jdk.jfr.consumer.RecordingFile
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put
import java.nio.file.Files
import java.nio.file.LinkOption
import java.nio.file.attribute.BasicFileAttributes
import java.time.Instant
import kotlin.system.exitProcess

/** Closed categories: never export sampled thread names, arbitrary symbols, addresses or event values. */
internal enum class LabProfileCategory {
    LanInterfaceEnumeration, LanPathValidation, SocketRead, SocketWrite, SocketPoll,
    Crypto, PayloadHash, JsonCodec, RpcHost, RpcClient, RpcLink, CoreSession,
    CoroutineScheduler, CoroutineFlow, Other,
}

/** The first recognized frame attributes the sampled leaf, not every caller on its stack. */
internal fun labProfileCategory(frames: List<Pair<String, String>>): LabProfileCategory {
    for ((type, method) in frames.take(64)) {
        when {
            type == "java.net.NetworkInterface" -> return LabProfileCategory.LanInterfaceEnumeration
            type == "dev.p2pkit.transport.lan.JvmOrganizationLanKt" ||
                type == "dev.p2pkit.transport.lan.JvmRawConnection" && method == "requireAllowedPath" ->
                return LabProfileCategory.LanPathValidation
            type in setOf("sun.nio.ch.SocketDispatcher", "sun.nio.ch.NioSocketImpl", "java.net.SocketInputStream") &&
                method.startsWith("read") -> return LabProfileCategory.SocketRead
            type in setOf("sun.nio.ch.SocketDispatcher", "sun.nio.ch.NioSocketImpl", "java.net.SocketOutputStream") &&
                method.startsWith("write") -> return LabProfileCategory.SocketWrite
            type == "sun.nio.ch.Net" && method.startsWith("poll") -> return LabProfileCategory.SocketPoll
            type.startsWith("dev.p2pkit.core.internal.security.") || type.startsWith("com.southernstorm.noise.") ||
                type.startsWith("com.github.p2pkit.noise.") || type.startsWith("com.google.crypto.") ||
                type.startsWith("com.sun.crypto.") -> return LabProfileCategory.Crypto
            type.startsWith("sun.security.provider.SHA") || type == "java.security.MessageDigest" ||
                type.startsWith("dev.p2pkit.core.security.PayloadDigest") -> return LabProfileCategory.PayloadHash
            type.startsWith("kotlinx.serialization.") || type.startsWith("dev.p2pkit.rpc.internal.RpcBodyCodec") ->
                return LabProfileCategory.JsonCodec
            type.startsWith("dev.p2pkit.rpc.internal.RpcHostEngine") -> return LabProfileCategory.RpcHost
            type.startsWith("dev.p2pkit.rpc.internal.RpcClientEngine") -> return LabProfileCategory.RpcClient
            type.startsWith("dev.p2pkit.rpc.internal.SessionRpcLink") -> return LabProfileCategory.RpcLink
            type.startsWith("dev.p2pkit.core.internal.P2pSessionImpl") -> return LabProfileCategory.CoreSession
            type.startsWith("kotlinx.coroutines.scheduling.") -> return LabProfileCategory.CoroutineScheduler
            type.startsWith("kotlinx.coroutines.flow.") -> return LabProfileCategory.CoroutineFlow
        }
    }
    return LabProfileCategory.Other
}

private class ProfileCount {
    var count = 0L
    var durationNanos = 0L
    var maximumDurationNanos = 0L

    fun add(duration: Long) {
        require(duration in 0..2_400_000_000_000L)
        count++
        durationNanos = Math.addExact(durationNanos, duration)
        maximumDurationNanos = maxOf(maximumDurationNanos, duration)
    }

    fun json(): JsonObject = buildJsonObject {
        put("count", count)
        put("durationNanos", durationNanos)
        put("maximumDurationNanos", maximumDurationNanos)
    }
}

/** Post-exit analysis, outside the measured clocks. No attach, signalling, PID selection or remote control. */
public fun main(args: Array<String>) {
    try {
        require(args.size == 2 && args[0] == "--owner-authorized-capacity-profile" &&
            args[1] in setOf("host", "client"))
        val config = LabConfig.load(args[1])
        val file = config.directory.resolve("runtime-profile.jfr")
        val attributes = Files.readAttributes(file, BasicFileAttributes::class.java, LinkOption.NOFOLLOW_LINKS)
        // Reuse the immutable owner/mode/no-follow/size guards. This occurs AFTER the measured JVM exits.
        val inputDigest = LabFiles.sha256(LabFiles.read(file, 64 * 1024 * 1024))
        require(attributes.isRegularFile && attributes.fileKey() != null)
        val kinds = listOf("ExecutionSample", "NativeMethodSample", "ThreadPark", "JavaMonitorEnter")
        val counts = kinds.associateWith { mutableMapOf<LabProfileCategory, ProfileCount>() }
        var events = 0
        var ignored = 0
        var truncated = 0
        var cpuSamples = 0L
        val cpuSums = mutableMapOf("jvmUser" to 0L, "jvmSystem" to 0L, "machineTotal" to 0L)
        val cpuMaxima = cpuSums.toMutableMap()
        var first: Instant? = null
        var last: Instant? = null
        RecordingFile(file).use { recording ->
            while (recording.hasMoreEvents()) {
                require(events++ < 2_000_000) { "Profile event bound" }
                val event = recording.readEvent()
                if (event.eventType.name == "jdk.CPULoad") {
                    cpuSamples++
                    for (name in cpuSums.keys) {
                        val load = event.getFloat(name)
                        require(load.isFinite() && load in 0.0f..1.0f)
                        val partsPerMillion = (load.toDouble() * 1_000_000).toLong()
                        cpuSums[name] = Math.addExact(cpuSums.getValue(name), partsPerMillion)
                        cpuMaxima[name] = maxOf(cpuMaxima.getValue(name), partsPerMillion)
                    }
                    continue
                }
                val kind = kinds.singleOrNull { event.eventType.name == "jdk.$it" }
                if (kind == null) { ignored++; continue }
                val stack = event.stackTrace
                if (stack?.isTruncated == true || (stack?.frames?.size ?: 0) > 64) truncated++
                val category = labProfileCategory(stack?.frames?.take(64)?.map {
                    it.method.type.name to it.method.name
                } ?: emptyList())
                counts.getValue(kind).getOrPut(category, ::ProfileCount).add(event.duration.toNanos())
                first = first?.let { minOf(it, event.startTime) } ?: event.startTime
                last = last?.let { maxOf(it, event.endTime) } ?: event.endTime
            }
        }
        val after = Files.readAttributes(file, BasicFileAttributes::class.java, LinkOption.NOFOLLOW_LINKS)
        require(after.fileKey() == attributes.fileKey() && after.size() == attributes.size() &&
            after.lastModifiedTime() == attributes.lastModifiedTime())
        require(counts.getValue("ExecutionSample").isNotEmpty() && cpuSamples > 0 && first != null && last != null)
        val output = buildJsonObject {
            put("schema", 1)
            put("scope", "BOUNDED_JFR_SAMPLES_AND_CPU_LOAD_NOT_CAPACITY")
            put("capacityQualified", false)
            put("role", args[1])
            put("sourceSha", config.sourceSha)
            put("recordingSha256", inputDigest)
            put("configuredDelaySeconds", 120)
            put("configuredDurationSeconds", 180)
            put("samplingPeriodMillis", 20)
            put("waitThresholdMillis", 20)
            put("firstEventEpochMillis", checkNotNull(first).toEpochMilli())
            put("lastEventEpochMillis", checkNotNull(last).toEpochMilli())
            put("totalEvents", events)
            put("ignoredEvents", ignored)
            put("truncatedStacks", truncated)
            put("cpuLoad", buildJsonObject {
                // JFR's normalized load observations, truncated to integer ppm.
                // These are separate from stack sample counts and aggregate wait durations.
                put("samples", cpuSamples)
                put("sumPpm", JsonObject(cpuSums.mapValues { JsonPrimitive(it.value) }))
                put("maximumPpm", JsonObject(cpuMaxima.mapValues { JsonPrimitive(it.value) }))
            })
            put("events", JsonObject(counts.mapValues { (_, categories) ->
                JsonObject(categories.entries.sortedBy { it.key.name }.associate { it.key.name to it.value.json() })
            }))
        }
        LabFiles.write(config.directory.resolve("runtime-profile.json"), output.toString().toByteArray())
        println("SYNTHETIC_PROFILE_ANALYZED: bounded categories only; not capacity qualification")
    } catch (_: Exception) {
        System.err.println("SYNTHETIC_PROFILE_FAILED: incomplete diagnostic; no raw event data exported")
        exitProcess(1)
    }
}
