package dev.p2pkit.sample.android.runtime

import java.security.MessageDigest

/**
 * Recorder shared by the actual ordinary-UID adapter and host tests, not a second flag model.
 * Values are observations only: no loaded-code, cache, compat or permission-enforcement qualification.
 */
internal object LanReadbackCollector {
    const val MODE = "profile-readback"
    const val SCHEMA = "p2pkit-android-lan-readback/1"
    const val PACKAGE = "dev.p2pkit.sample.android"
    const val READER_CLASS = "android.os.flagging.AconfigPackage"
    const val FLAG_PACKAGE = "android.permission.flags"
    const val FLAG_NAME = "access_local_network_permission_enabled"
    const val STORAGE_ERROR = "android.os.flagging.AconfigStorageReadException"
    const val MAX_RECORD_BYTES = 16 * 1024
    const val OBSERVATION_MILLIS = 30_000L

    data class References(
        val token: String,
        val sourceCommit: String,
        val sourceTree: String,
        val appApkSha256: String,
        val testApkSha256: String,
        val profileSha256: String,
        val installId: String,
    ) {
        fun validate() {
            check(hex(token, 32) && hex(installId, 32))
            check(hex(sourceCommit, 40) && hex(sourceTree, 40))
            check(listOf(appApkSha256, testApkSha256, profileSha256).all { hex(it, 64) })
        }
    }

    data class Identity(
        val sourceCommit: String,
        val buildDirty: Boolean,
        val packageName: String,
        val user: Int,
        val uid: Int,
        val applicationUid: Int,
        val pid: Int,
        val processStartElapsedMillis: Long,
        val installEpochMillis: Long,
        val sdkInt: Int,
        val targetSdk: Int,
        val codename: String,
        val previewSdkInt: Int,
    ) {
        fun validate(references: References) {
            check(sourceCommit == references.sourceCommit && !buildDirty) { "Source admission failed" }
            check(packageName == PACKAGE && user == 0 && uid in 10000..19999 && applicationUid == uid)
            check(pid > 0 && processStartElapsedMillis >= 0 && installEpochMillis > 0)
            check(sdkInt == 37 && targetSdk == 37 && codename == "REL" && previewSdkInt == 0)
        }
    }

    data class Stamp(val epochMillis: Long, val elapsedMillis: Long)

    data class ErrorDetails(val type: String, val code: Int?)

    interface Port {
        fun identity(): Identity
        fun stamp(): Stamp
        fun load(packageName: String): Any
        fun read(reader: Any, flagName: String, defaultValue: Boolean): Boolean
        fun errorDetails(error: Throwable): ErrorDetails
    }

    internal class Event(
        val phase: String,
        val identity: Identity,
        val start: Stamp,
        val defaultValue: Boolean?,
    ) {
        var end: Stamp? = null
        var readerId: String? = null
        var kind: String? = null
        var value: Boolean? = null
        var error: ErrorDetails? = null
    }

    class Result internal constructor(
        val complete: Boolean,
        val retained: Boolean,
        val byteCount: Int?,
        val sha256: String?,
        val failureStage: String?,
        val failure: Throwable?,
        internal val events: List<Event>,
    ) {
        // Never accidentally print raw bindings, record bytes or exception messages.
        override fun toString(): String = "LanReadbackResult(complete=$complete, retained=$retained)"
    }

    /**
     * The fixed interval rejects late observations; it cannot interrupt a synchronous platform call.
     * A separately owned, bounded host command must supply that outer execution/retirement contract.
     * A partial/error record is still offered to private retention, but can never produce complete=true.
     */
    fun collect(
        references: References,
        port: Port,
        readerId: String,
        retain: (ByteArray) -> Unit,
    ): Result {
        var stage = "admission"
        var failure: Throwable? = null
        var failureStage: String? = null
        var initial: Identity? = null
        var last: Stamp? = null
        var endElapsed = 0L
        var retained = false
        var encoded: ByteArray? = null
        val events = mutableListOf<Event>()

        fun remember(error: Throwable) {
            if (failure == null) {
                failure = error
                failureStage = stage
            }
        }

        fun clock(): Stamp {
            val current = port.stamp()
            check(current.epochMillis > 0 && current.elapsedMillis >= 0)
            last?.let {
                check(current.epochMillis >= it.epochMillis && current.elapsedMillis >= it.elapsedMillis) {
                    "Clock moved backwards"
                }
            }
            check(current.elapsedMillis < endElapsed) { "Readback observation expired" }
            initial?.let {
                check(current.epochMillis >= it.installEpochMillis)
                check(current.elapsedMillis >= it.processStartElapsedMillis)
            }
            last = current
            return current
        }

        fun boundary(): Stamp {
            clock()
            val identity = port.identity()
            identity.validate(references)
            check(identity == initial) { "Readback process/install binding changed" }
            return clock()
        }

        try {
            references.validate()
            check(hex(readerId, 32))
            val start = port.stamp()
            check(start.epochMillis > 0 && start.elapsedMillis in 0..Long.MAX_VALUE - OBSERVATION_MILLIS)
            last = start
            endElapsed = start.elapsedMillis + OBSERVATION_MILLIS
            initial = port.identity()
            checkNotNull(initial).validate(references)
            var loaded: Any? = null
            for (index in 0..2) {
                stage = when (index) {
                    0 -> "load"
                    1 -> "read-false"
                    else -> "read-true"
                }
                val startStamp = boundary()
                val event = Event(
                    if (index == 0) "load" else "read", checkNotNull(initial), startStamp,
                    if (index == 0) null else index == 2,
                )
                events += event
                if (index != 0) event.readerId = readerId
                try {
                    if (index == 0) {
                        loaded = port.load(FLAG_PACKAGE)
                        event.readerId = readerId
                        event.kind = "LOADED"
                    } else {
                        // The actual reference returned by the sole load is retained through both calls.
                        event.value = port.read(checkNotNull(loaded), FLAG_NAME, index == 2)
                        event.kind = "RETURNED"
                    }
                } catch (error: Throwable) {
                    remember(error) // An error-code/clock/identity failure may not replace this original.
                    event.kind = "ERROR"
                    event.error = port.errorDetails(error)
                }
                event.end = boundary()
                if (failure != null) break // No reload or subsequent read can rehabilitate an error.
            }
        } catch (error: Throwable) {
            remember(error)
        }

        try {
            stage = "retention"
            val bytes = encode(references, initial, events)
            encoded = bytes
            if (failure == null) boundary()
            retain(bytes.copyOf())
            retained = true
            // Include retention in the same original window and re-read the identity after it returns.
            if (failure == null) boundary()
        } catch (error: Throwable) {
            remember(error)
        }
        val complete = failure == null && retained && events.size == 3
        return Result(complete, retained, encoded?.size, encoded?.let(::digest), failureStage, failure, events.toList())
    }

    private fun encode(references: References, identity: Identity?, events: List<Event>): ByteArray {
        val json = Json()
        fun stamp(value: Stamp?) {
            if (value == null) json.add("null") else {
                json.add("{\"epochMillis\":${value.epochMillis},\"elapsedMillis\":${value.elapsedMillis}}")
            }
        }
        fun binding(value: Identity?) {
            if (value == null) {
                json.add("null")
                return
            }
            json.add("{")
            val strings = linkedMapOf(
                "token" to references.token, "sourceCommit" to references.sourceCommit,
                "sourceTree" to references.sourceTree, "appApkSha256" to references.appApkSha256,
                "testApkSha256" to references.testApkSha256, "profileSha256" to references.profileSha256,
                "installId" to references.installId, "packageName" to value.packageName,
            )
            strings.entries.forEachIndexed { index, (key, item) ->
                if (index != 0) json.add(",")
                json.string(key)
                json.add(":")
                json.string(item)
            }
            json.add(",\"user\":${value.user},\"uid\":${value.uid},\"pid\":${value.pid}")
            json.add(",\"processStartElapsedMillis\":${value.processStartElapsedMillis}")
            json.add(",\"installEpochMillis\":${value.installEpochMillis}")
            json.add(",\"sdkInt\":${value.sdkInt},\"targetSdk\":${value.targetSdk},\"codename\":")
            json.string(value.codename)
            json.add(",\"previewSdkInt\":${value.previewSdkInt},\"buildDirty\":${value.buildDirty}}")
        }
        json.add("{\"schema\":")
        json.string(SCHEMA)
        json.add(",\"mode\":")
        json.string(MODE)
        json.add(",\"binding\":")
        binding(identity)
        json.add(",\"readerClass\":")
        json.string(READER_CLASS)
        json.add(",\"flagPackage\":")
        json.string(FLAG_PACKAGE)
        json.add(",\"flagName\":")
        json.string(FLAG_NAME)
        json.add(",\"events\":[")
        events.forEachIndexed { index, event ->
            if (index != 0) json.add(",")
            json.add("{\"phase\":")
            json.string(event.phase)
            json.add(",\"binding\":")
            binding(event.identity)
            json.add(",\"readerId\":")
            event.readerId?.let { json.string(it) } ?: json.add("null")
            if (event.defaultValue != null) json.add(",\"default\":${event.defaultValue}")
            json.add(",\"start\":")
            stamp(event.start)
            json.add(",\"end\":")
            stamp(event.end)
            json.add(",\"outcome\":")
            when (event.kind) {
                "LOADED" -> json.add("{\"kind\":\"LOADED\"}")
                "RETURNED" -> json.add("{\"kind\":\"RETURNED\",\"value\":${checkNotNull(event.value)}}")
                "ERROR" -> {
                    json.add("{\"kind\":\"ERROR\",\"errorType\":")
                    val error = checkNotNull(event.error)
                    check(error.type.matches(Regex("[A-Za-z_$][A-Za-z0-9_$]*(\\.[A-Za-z_$][A-Za-z0-9_$]*)+")))
                    check(error.type.length <= 255)
                    json.string(error.type)
                    json.add(",\"errorCode\":${error.code}}")
                }
                else -> json.add("null") // A partial failed observation is never a complete readback.
            }
            json.add("}")
        }
        json.add("]}\n")
        return json.bytes()
    }

    private class Json {
        private val text = StringBuilder()
        fun add(value: String) {
            check(value.length <= MAX_RECORD_BYTES - text.length) { "Readback record limit" }
            text.append(value)
        }
        fun string(value: String) {
            // All admitted fields are closed ASCII tokens/classes, never arbitrary exception messages.
            check(value.length <= 1024 && value.all { it in ' '..'~' && it != '"' && it != '\\' })
            add("\"$value\"")
        }
        fun bytes(): ByteArray = text.toString().toByteArray(Charsets.UTF_8).also {
            check(it.size <= MAX_RECORD_BYTES)
        }
    }

    private fun hex(value: String, size: Int): Boolean = value.matches(Regex("[0-9a-f]{$size}"))

    private fun digest(value: ByteArray): String = MessageDigest.getInstance("SHA-256").digest(value)
        .joinToString("") { "%02x".format(it.toInt() and 0xff) }
}
