package dev.p2pkit.sample.rpc

/**
 * Foreground development-app observations. Poll the real public sensors at 1 Hz and durably
 * publish each returned checkpoint. An interrupted checkpoint is never a complete recording.
 */
public class RpcDischargeRecorder internal constructor(
    runLabel: String,
    platform: String,
    artifactSha256: String,
    sourceSha: String,
) {
    @Throws(Exception::class)
    public constructor(runLabel: String, platform: String, artifactSha256: String) :
        this(runLabel, platform, artifactSha256, RpcPhoneLab.compiledSource) {
        require(RpcPhoneBuildStamp.SOURCE_CLEAN)
    }

    private val binding = linkedMapOf(
        "schema" to "1", "scope" to "foreground-unplugged-observations",
        "runLabel" to runLabel, "platform" to platform, "sourceSha" to sourceSha,
        "artifactSha256" to artifactSha256, "requiredMillis" to DURATION.toString(),
    )
    private val rows = mutableListOf<String>()
    private var lastObserved = -1L
    private var lastSaved = -1L
    public var status: String = "recording"
        private set
    public val active: Boolean get() = status == "recording"

    init {
        require(runLabel.matches(Regex("discharge-[a-f0-9]{32}")))
        require(platform in setOf("Android", "Ios"))
        require(artifactSha256.matches(Regex("[a-f0-9]{64}")))
        require(sourceSha.matches(Regex("[a-f0-9]{40}")))
    }

    @Throws(Exception::class)
    public fun observe(elapsedMillis: Long, observation: RpcPhoneEnvironmentStats): String? {
        check(active)
        require(elapsedMillis > lastObserved && (lastObserved != -1L || elapsedMillis == 0L))
        val row = observation.record(binding.getValue("platform"))
        status = when {
            observation.requiresThermalStop -> "thermal-stop"
            observation.batteryState != "unplugged" -> "power-changed"
            lastObserved != -1L && elapsedMillis - lastObserved > 3_000L -> "sample-gap"
            elapsedMillis >= DURATION -> "complete"
            else -> "recording"
        }
        lastObserved = elapsedMillis
        if (rows.isNotEmpty() && active && elapsedMillis - lastSaved < 10_000L) return null
        check(rows.size < 182)
        lastSaved = elapsedMillis
        rows += listOf(elapsedMillis.toString(), row.getValue("batteryPercentMilli"),
            row.getValue("batteryCurrentMicroamps"), row.getValue("batteryTemperatureMilliC"),
            observation.batteryState, observation.thermalState).joinToString(",")
        return checkpoint()
    }

    @Throws(Exception::class)
    public fun interrupt(): String? {
        if (!active || rows.isEmpty()) return null
        status = "interrupted"
        return checkpoint()
    }

    private fun checkpoint(): String = encodeMobileRecord(
        binding + ("status" to status) + rows.mapIndexed { index, row ->
            "sample" + index.toString().padStart(3, '0') to row
        },
    )

    private companion object {
        const val DURATION = 1_800_000L
    }
}
