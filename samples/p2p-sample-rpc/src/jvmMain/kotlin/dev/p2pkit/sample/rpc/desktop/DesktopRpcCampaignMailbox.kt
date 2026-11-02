package dev.p2pkit.sample.rpc.desktop

import dev.p2pkit.sample.rpc.lab.LabFiles
import kotlinx.coroutines.delay
import kotlinx.coroutines.withTimeout
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.int
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.long
import kotlinx.serialization.json.put
import java.nio.file.Files
import java.nio.file.LinkOption
import java.nio.file.Path
import java.util.UUID

internal data class DesktopRpcCampaignProfile(val platform: String, val clients: Int) {
    override fun toString(): String = "${if (platform == "android") "Android" else "iPhone"} Host · $clients Clients"
}

/** Local owner-only files; this object never launches a process or supplies an RPC endpoint. */
internal class DesktopRpcCampaignMailbox(private val directory: Path, private val source: String) {
    private val context = read("context.json")
    val profiles: List<DesktopRpcCampaignProfile> = context.getValue("profiles").jsonArray.map {
        val value = it.jsonObject
        DesktopRpcCampaignProfile(value.getValue("platform").jsonPrimitive.content,
            value.getValue("clients").jsonPrimitive.int).also { profile ->
            require(profile.platform in setOf("android", "ios") && profile.clients in setOf(128, 256))
        }
    }.also { require(it.size in 1..4 && it.distinct().size == it.size) }
    var activeId: String? = null
        private set
    var lastResult: JsonObject? = null
        private set

    init {
        require(source.matches(Regex("[a-f0-9]{40}")))
        LabFiles.privateDirectory(directory)
        listOf("requests", "cancel", "results").forEach { LabFiles.privateDirectory(directory.resolve(it)) }
        require(context.getValue("sourceSha").jsonPrimitive.content == source)
    }

    private fun read(name: String): JsonObject = Json.parseToJsonElement(
        LabFiles.read(directory.resolve(name), 65_536).decodeToString()).jsonObject.also {
        require(it.getValue("schema").jsonPrimitive.int == 1)
        require(it.getValue("sourceSha").jsonPrimitive.content == source)
    }

    fun start(profile: DesktopRpcCampaignProfile, mode: String, action: String = "run"): String {
        check(activeId == null && profile in profiles)
        require(mode in setOf("large", "correctness", "churn", "steady"))
        require(action in setOf("run", "recover"))
        val status = read("status.json")
        val age = System.currentTimeMillis() - status.getValue("updatedAtEpochMillis").jsonPrimitive.long
        check(age in 0..5_000 && status.getValue("state").jsonPrimitive.content == "Idle") {
            "Prepared worker is unavailable or busy"
        }
        val id = UUID.randomUUID().toString().replace("-", "")
        val body = buildJsonObject {
            put("schema", 1); put("sourceSha", source); put("id", id)
            put("platform", profile.platform); put("clients", profile.clients); put("mode", mode)
            put("action", action)
        }
        LabFiles.write(directory.resolve("requests/$id.json"), body.toString().toByteArray())
        activeId = id
        lastResult = null
        return id
    }

    fun poll(): JsonObject {
        val id = activeId
        if (id != null && Files.exists(directory.resolve("results/$id.json"), LinkOption.NOFOLLOW_LINKS)) {
            val result = read("results/$id.json")
            require(result.getValue("id").jsonPrimitive.content == id)
            require(result.getValue("state").jsonPrimitive.content in
                setOf("NeedsReview", "Failed", "RecoveryRequired", "Rejected"))
            lastResult = result
            activeId = null
            return result
        }
        return read("status.json")
    }

    fun cancel() {
        val id = activeId ?: return
        val path = directory.resolve("cancel/$id.json")
        if (Files.exists(path, LinkOption.NOFOLLOW_LINKS)) {
            val existing = read("cancel/$id.json")
            require(existing.getValue("id").jsonPrimitive.content == id)
            return
        }
        val body = buildJsonObject { put("schema", 1); put("sourceSha", source); put("id", id) }
        LabFiles.write(path, body.toString().toByteArray())
    }

    /** Wait for the original worker's outcome; do not signal guessed processes or infer phone closure. */
    suspend fun retire() {
        if (activeId != null) {
            cancel()
            withTimeout(650_000) {
                while (activeId != null) { poll(); delay(500) }
            }
        }
        check(lastResult == null || lastResult?.getValue("cleanupVerified")?.jsonPrimitive?.content == "true" ||
            lastResult?.getValue("state")?.jsonPrimitive?.content == "Rejected") {
            "Phone cleanup requires recovery; retained ownership blocks navigation"
        }
    }
}
