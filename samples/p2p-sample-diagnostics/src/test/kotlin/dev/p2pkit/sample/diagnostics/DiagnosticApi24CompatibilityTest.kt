package dev.p2pkit.sample.diagnostics

import java.io.File
import java.io.IOException
import java.lang.reflect.InvocationTargetException
import java.nio.file.Files
import java.time.Instant
import java.time.ZoneOffset
import java.time.format.DateTimeFormatter
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertTrue

class DiagnosticApi24CompatibilityTest {
    @Test
    fun recorderDefaultsWorkWithoutJavaTimeOrNioFile() {
        val timestamp = invokeWithoutApi26("record") as String
        assertTrue(Instant.parse(timestamp) > Instant.EPOCH)
    }

    @Test
    fun pinnedKotlinClockExecutesItsOlderAndroidSdkBranchesWithoutJavaTime() {
        for (sdk in listOf(24, 25)) {
            val timestamp = invokeWithoutApi26("record", sdk = sdk) as String
            assertTrue(Instant.parse(timestamp) > Instant.EPOCH)
        }
    }

    @Test
    fun exportAndRepeatedReplacementWorkWithoutJavaTimeOrNioFile() {
        val directory = Files.createTempDirectory("p2pkit-api24-export").toFile()
        try {
            assertTrue(invokeWithoutApi26("export", directory) in exportResults)
            assertTrue(directory.listFiles().orEmpty().none { it.name.endsWith(".part") })
        } finally {
            directory.deleteRecursively()
        }
    }

    @Test
    fun exportAlsoWorksWhenOnlyNioFileIsUnavailable() {
        val directory = Files.createTempDirectory("p2pkit-no-nio-export").toFile()
        try {
            assertTrue(invokeWithoutApi26("export", directory, blockTime = false) in exportResults)
        } finally {
            directory.deleteRecursively()
        }
    }

    @Test
    fun failedOlderAndroidRenamePreservesBothFiles() {
        val directory = Files.createTempDirectory("p2pkit-api24-rename-failure").toFile()
        try {
            var attempted = false
            val source = object : File(directory, "staged") {
                override fun renameTo(dest: File): Boolean {
                    attempted = true
                    return false
                }
            }
            val target = File(directory, "original")
            source.writeText("new")
            target.writeText("old")
            val loader = WithoutApi26Libraries(javaClass.classLoader, blockTime = true)
            val probe = loader.loadClass("dev.p2pkit.sample.diagnostics.DiagnosticApi24Probe")
            assertFailsWith<IOException> {
                try {
                    probe.getMethod("replace", File::class.java, File::class.java).invoke(null, source, target)
                } catch (failure: InvocationTargetException) {
                    throw failure.targetException
                }
            }
            assertTrue(attempted)
            assertEquals("new", source.readText())
            assertEquals("old", target.readText())
        } finally {
            directory.deleteRecursively()
        }
    }

    @Test
    fun exportFailureWithoutApi26CleansOwnedStagingAndKeepsDestination() {
        val directory = Files.createTempDirectory("p2pkit-api24-export-failure").toFile()
        try {
            assertEquals("preserved", invokeWithoutApi26("failedExport", directory))
            assertTrue(directory.listFiles().orEmpty().none { it.name.endsWith(".part") })
        } finally {
            directory.deleteRecursively()
        }
    }

    @Test
    fun filenameNormalizationRetainsUtcAndInvalidInputBehavior() {
        val formatter = DateTimeFormatter.ofPattern("yyyy-MM-dd'T'HHmmss").withZone(ZoneOffset.UTC)
        listOf(
            "2026-09-06T12:34:56Z",
            "2026-09-06T12:34:56.123456789Z",
            "2026-09-06T12:34:56.Z",
            "2026-09-06T00:30:00+02:00",
            "2026-09-06T23:30:00-02:00",
            "2026-09-06T00:30:00+00:00",
            "2026-09-06T00:30:00-00:00",
            "2026-09-06T00:30:00+02:30:15",
            "2026-09-06T00:30:00-00:00:15",
            "2000-02-29T12:00:00Z",
            "1500-02-28T12:00:00Z",
            "0000-01-01T00:00:00Z",
            "-0001-01-01T00:00:00Z",
            "-00001-01-01T00:00:00Z",
            "+00001-01-01T00:00:00Z",
            "+00000-01-01T00:00:00Z",
            "+10000-01-01T00:00:00Z",
            "2016-12-31T23:59:60Z",
            "2016-12-31T23:59:60.123+01:00",
            "2026-09-06T24:00:00Z",
            "2026-09-06T24:00:00.000-02:00",
            "2026-09-06T24:00:00.001Z",
            "2026-09-06t12:34:56z",
            "2026-09-06T12:34:56.1234567890Z",
            "1900-02-29T00:00:00Z",
            "2026-09-06",
            "invalid"
        ).forEach { timestamp ->
            val instant = runCatching { Instant.parse(timestamp) }.getOrDefault(Instant.EPOCH)
            assertEquals(
                "test_android_${formatter.format(instant)}_session.zip",
                DiagnosticEvidenceExporter.evidenceFilename("test", "android", timestamp, "session"),
                timestamp
            )
        }
    }

    @Test
    fun filenameNormalizationRejectsNegativeZeroYearAndIncompleteOffsets() {
        val timestamps = listOf(
            "2026-09-06T00:30:00+02",
            "2026-09-06T00:30:00-02",
            "2026-09-06T00:30:00+00",
            "2026-09-06T00:30:00-00",
            "-0000-01-01T00:00:00Z",
            "-00000-01-01T00:00:00Z"
        )
        timestamps.forEach { timestamp ->
            assertTrue(runCatching { Instant.parse(timestamp) }.isFailure, timestamp)
        }
        assertEquals(
            timestamps.associateWith { "test_android_1970-01-01T000000_session.zip" },
            timestamps.associateWith {
                DiagnosticEvidenceExporter.evidenceFilename("test", "android", it, "session")
            }
        )
    }

    private fun invokeWithoutApi26(
        method: String,
        directory: File? = null,
        blockTime: Boolean = true,
        sdk: Int? = null
    ): Any? {
        val loader = WithoutApi26Libraries(javaClass.classLoader, blockTime, sdk)
        val probe = loader.loadClass("dev.p2pkit.sample.diagnostics.DiagnosticApi24Probe")
        return try {
            if (directory == null) probe.getMethod(method).invoke(null)
            else probe.getMethod(method, File::class.java).invoke(null, directory)
        } catch (failure: InvocationTargetException) {
            throw failure.targetException
        }
    }

    private companion object {
        val exportResults = setOf("verified-replacement", "verified-preserved-failure")
    }
}

/** Missing-class/SDK model, not ART. The optional SDK also isolates the pinned Kotlin clock implementation. */
private class WithoutApi26Libraries(
    parent: ClassLoader,
    private val blockTime: Boolean,
    sdk: Int? = null
) : ClassLoader(parent) {
    private val sdkClasses: Map<String, ByteArray> = sdk?.let(::syntheticAndroidSdkClasses).orEmpty()

    override fun loadClass(name: String, resolve: Boolean): Class<*> = synchronized(getClassLoadingLock(name)) {
        if ((blockTime && name.startsWith("java.time.")) || name.startsWith("java.nio.file.")) {
            throw ClassNotFoundException("Unavailable before Android API26: $name")
        }
        val isolatedClock = sdkClasses.isNotEmpty() &&
            (name.startsWith("kotlin.time.") || name.startsWith("kotlin.internal."))
        if (name !in sdkClasses && !isolatedClock && !name.startsWith("dev.p2pkit.sample.diagnostics.")) {
            return super.loadClass(name, resolve)
        }
        val type = findLoadedClass(name) ?: run {
            val bytes = sdkClasses[name] ?: parent.getResourceAsStream(name.replace('.', '/') + ".class").use {
                requireNotNull(it) { "Missing diagnostic test class: $name" }.readBytes()
            }
            defineClass(name, bytes, 0, bytes.size)
        }
        if (resolve) resolveClass(type)
        type
    }
}
