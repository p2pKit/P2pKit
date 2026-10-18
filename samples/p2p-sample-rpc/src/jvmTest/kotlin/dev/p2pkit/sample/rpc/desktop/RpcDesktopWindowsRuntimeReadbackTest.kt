package dev.p2pkit.sample.rpc.desktop

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertFalse
import kotlin.test.assertTrue
import kotlin.test.assertSame

class RpcDesktopWindowsRuntimeReadbackTest {
    private val source = "a".repeat(40)
    private val good = WindowsRuntimeObservation(
        17, "17.0.17+10", "jdk.unsupported", true, true, true, true,
        listOf("NOSHARE_READ", "NOSHARE_WRITE", "NOSHARE_DELETE"),
    )

    @Test fun installedAdmissionResultIsExactBoundedFormattingNotCallerAuthority() {
        val result = "{\"schema\":1,\"scope\":\"INSTALLED_ADMISSION_ONLY_NOT_PROFILE_PROVIDER_QUALIFICATION\"," +
            "\"admission\":\"REGISTERED\",\"repeat\":\"REUSED\",\"profileStorage\":\"NOT_ENTERED\"," +
            "\"network\":\"NOT_ENTERED\",\"publicProvider\":\"DISABLED\"}"
        assertEquals("{\"source\":\"$source\",\"admission\":$result}", checkedInstalledAdmissionReadback(source, result))
        for (invalid in listOf(null, 1, "", result + "\n", result + "extra", result.replace("DISABLED", "ENABLED"),
            result.replace("REUSED", "NEW"), result.replace("NOT_ENTERED", "ENTERED"))) {
            assertFailsWith<IllegalStateException> { checkedInstalledAdmissionReadback(source, invalid) }
        }
        assertFailsWith<IllegalStateException> { checkedInstalledAdmissionReadback("not-source", result) }
    }

    @Test fun actualTestJvmResolvesTheRequiredBootModuleAndAllThreeOptions() {
        // Actual class/module resolution in the test JVM, not an installed/bundled Windows-runtime claim.
        val actual = RpcDesktopWindowsRuntimeReadback.observeRuntime()
        assertEquals(Runtime.version().feature(), actual.javaFeature)
        assertEquals(Runtime.version().toString(), actual.javaVersion)
        assertEquals("jdk.unsupported", actual.moduleName)
        assertTrue(actual.bootModule && actual.runtimeImageModule && actual.exported && actual.optionType)
        assertEquals(good.optionNames, actual.optionNames)
    }

    @Test fun desktopPreparationRequiresExactOriginalBootClassesWithoutInitializingAToolkit() {
        requireOriginalDesktopClass(java.awt.Toolkit::class.java, "java.awt.Toolkit")
        assertFailsWith<IllegalStateException> {
            requireOriginalDesktopClass(String::class.java, "java.lang.String")
        }
        assertFailsWith<IllegalStateException> {
            requireOriginalDesktopClass(java.awt.Toolkit::class.java, "sun.awt.windows.WToolkit")
        }
        assertFailsWith<IllegalStateException> {
            requireOriginalDesktopClass(RpcDesktopWindowsRuntimeReadbackTest::class.java,
                RpcDesktopWindowsRuntimeReadbackTest::class.java.name)
        }
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

    @Test fun failureStagesAreBoundedAndPreserveTheOriginalError() {
        val original = LinkageError("PRIVATE_PATH_SID_ADDRESS_PAYLOAD")
        for (phase in InstalledAdmissionPhase.entries) {
            val lines = mutableListOf<String>()
            val actual = assertFailsWith<LinkageError> {
                reportInstalledAdmissionFailure(phase, "PROFILE_PARENT_PIN", original, lines::add)
            }
            assertSame(original, actual)
            assertEquals(1, lines.size)
            val code = if (phase == InstalledAdmissionPhase.NATIVE_ADMISSION) "PROFILE_PARENT_PIN" else "DIAGNOSTIC_UNAVAILABLE"
            assertEquals("WINDOWS_INSTALLED_ADMISSION_FAILURE stage=${phase.name} operation=$code", lines.single())
            assertTrue(lines.single().length < 192)
            assertFalse(lines.single().contains("PRIVATE"))
        }
    }

    @Test fun systemCohortFailureLabelsSurviveApplicationReportingWithoutReplacingTheCarrier() {
        val original = LinkageError("PRIVATE_PATH_SID_ADDRESS_PAYLOAD")
        for (operation in listOf(
            "SYSTEM_MODULE_ABSENT_SLOT_FOUR", "SYSTEM_LEAF_POLICY_SLOT_ZERO",
            "SYSTEM_ANCESTOR_POLICY_SLOT_THREE", "SYSTEM_RETURN_UNKNOWN_SLOT_ONE",
            "SYSTEM_RETIREMENT_NO_SLOT", "SYSTEM_FILE_SLOT_SIX", "SYSTEM_BYTES_SLOT_SEVEN",
            "SYSTEM_EXPORT_GRAPH_NO_SLOT", "SYSTEM_UNKNOWN_OPERATION_UNKNOWN_SLOT",
        )) {
            val lines = mutableListOf<String>()
            assertSame(original, assertFailsWith<LinkageError> {
                reportInstalledAdmissionFailure(InstalledAdmissionPhase.NATIVE_ADMISSION, operation, original, lines::add)
            })
            assertEquals(listOf("WINDOWS_INSTALLED_ADMISSION_FAILURE stage=NATIVE_ADMISSION operation=$operation"), lines)
            assertTrue(lines.single().length < 192)
        }
    }

    @Test fun untrustedOrMissingOperationCannotEscapeTheClosedVocabulary() {
        val original = IllegalStateException("PRIVATE")
        val badObject = object { override fun toString(): String = error("Private object stringified") }
        for (operation in listOf(
            null, badObject, 1, "", "PRIVATE", "BOOTSTRAP\nPASS", "X".repeat(10000),
            "SYSTEM_MODULE_ABSENT_SLOT_EIGHT", "SYSTEM_MODULE_ABSENT_SLOT_FOUR\nPRIVATE",
            "SYSTEM_FILE_C:\\PRIVATE", "SYSTEM_FILE_SLOT_ZERO ", "SYSTEM_FILE_SLOT_ZERO\u0000",
        )) {
            val lines = mutableListOf<String>()
            assertSame(original, assertFailsWith<IllegalStateException> {
                reportInstalledAdmissionFailure(InstalledAdmissionPhase.NATIVE_ADMISSION, operation, original, lines::add)
            })
            assertEquals(listOf("WINDOWS_INSTALLED_ADMISSION_FAILURE stage=NATIVE_ADMISSION operation=DIAGNOSTIC_UNAVAILABLE"), lines)
        }
    }

    @Test fun secondaryDiagnosticOutputFailureCannotReplaceTheOriginalCarrier() {
        val original = LinkageError("ORIGINAL_PRIVATE")
        assertSame(original, assertFailsWith<LinkageError> {
            reportInstalledAdmissionFailure(InstalledAdmissionPhase.RUNTIME_PRECHECK, null, original) {
                throw OutOfMemoryError("SECONDARY_PRIVATE")
            }
        })
    }

    private fun read(actual: WindowsRuntimeObservation) =
        checkedWindowsRuntimeReadback(source, true, "Windows 11", "amd64") { actual }

    private data class Inputs(val source: String, val clean: Boolean, val os: String, val architecture: String)
}
