package dev.p2pkit.sample.rpc.desktop

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertFalse
import kotlin.test.assertTrue

class RpcDesktopWindowsRuntimeReadbackTest {
    private val source = "a".repeat(40)
    private val good = WindowsRuntimeObservation(
        17, "17.0.17+10", "jdk.unsupported", true, true, true, true,
        listOf("NOSHARE_READ", "NOSHARE_WRITE", "NOSHARE_DELETE"),
    )

    @Test fun actualTestJvmResolvesTheRequiredBootModuleAndAllThreeOptions() {
        // Actual class/module resolution in the test JVM, not an installed/bundled Windows-runtime claim.
        val actual = RpcDesktopWindowsRuntimeReadback.observeRuntime()
        assertEquals(Runtime.version().feature(), actual.javaFeature)
        assertEquals(Runtime.version().toString(), actual.javaVersion)
        assertEquals("jdk.unsupported", actual.moduleName)
        assertTrue(actual.bootModule && actual.runtimeImageModule && actual.exported && actual.optionType)
        assertEquals(good.optionNames, actual.optionNames)
    }

    @Test fun reviewedFeaturesEmitTheirActualVersionWithoutClaimingProfileOrInstallation() {
        for (actual in listOf(good, good.copy(javaFeature = 21, javaVersion = "21.0.9+10-LTS"))) {
            val result = read(actual)
            assertTrue(result.startsWith(
                "{\"scope\":\"WINDOWS_RUNTIME_MODULE_RESOLUTION_ONLY_NOT_PROFILE_OR_RELEASE\",",
            ))
            assertTrue(result.contains("\"source\":\"$source\",\"javaFeature\":${actual.javaFeature},"))
            assertTrue(result.contains("\"javaVersion\":\"${actual.javaVersion}\",\"module\":\"jdk.unsupported\""))
            assertTrue(result.endsWith("\"nativeLoad\":\"NOT_PERFORMED\",\"profileAccess\":\"NOT_PERFORMED\"}"))
            assertFalse(result.contains("\n"))
        }
    }

    @Test fun platformAndSourceRefusalsHappenBeforeTheRuntimeResolver() {
        for ((head, clean, os, architecture) in listOf(
            Inputs(source, false, "Windows 11", "amd64"),
            Inputs("bad", true, "Windows 11", "amd64"),
            Inputs(source, true, "Mac OS X", "aarch64"),
            Inputs(source, true, "Linux", "x86_64"),
            Inputs(source, true, "Windows 11", "aarch64"),
        )) {
            var called = false
            assertFailsWith<IllegalStateException> {
                checkedWindowsRuntimeReadback(head, clean, os, architecture) { called = true; good }
            }
            assertFalse(called)
        }
    }

    @Test fun missingWrongOrClasspathModuleAndIncompleteConstantsFailClosed() {
        for (actual in listOf(
            good.copy(moduleName = null), good.copy(moduleName = "java.base"), good.copy(bootModule = false),
            good.copy(runtimeImageModule = false), good.copy(exported = false), good.copy(optionType = false),
            good.copy(optionNames = listOf("NOSHARE_WRITE", "NOSHARE_DELETE")),
            good.copy(optionNames = listOf("NOSHARE_READ", "NOSHARE_WRITE", "NOSHARE_WRITE")),
        )) assertFailsWith<IllegalStateException> { read(actual) }
    }

    @Test fun unreviewedInconsistentOrUnboundedVersionsDoNotBecomeEvidence() {
        for (actual in listOf(
            good.copy(javaFeature = 25, javaVersion = "25.0.1"),
            good.copy(javaFeature = 21), good.copy(javaVersion = ""), good.copy(javaVersion = "17\nPASS"),
            good.copy(javaVersion = "a".repeat(129)),
        )) assertFailsWith<IllegalStateException> { read(actual) }
    }

    @Test fun missingRuntimeClassCannotFallBackToAnotherResolver() {
        var calls = 0
        assertFailsWith<NoClassDefFoundError> {
            checkedWindowsRuntimeReadback(source, true, "Windows 11", "amd64") {
                calls++
                throw NoClassDefFoundError("Synthetic missing jdk.unsupported")
            }
        }
        assertEquals(1, calls)
    }

    private fun read(actual: WindowsRuntimeObservation) =
        checkedWindowsRuntimeReadback(source, true, "Windows 11", "amd64") { actual }

    private data class Inputs(val source: String, val clean: Boolean, val os: String, val architecture: String)
}
