package dev.p2pkit.sample.rpc.desktop

import com.sun.nio.file.ExtendedOpenOption
import dev.p2pkit.sample.rpc.RpcPhoneBuildStamp
import java.lang.reflect.InvocationTargetException
import java.lang.reflect.Method
import java.lang.reflect.Modifier
import java.nio.file.OpenOption

/** Fixed runtime diagnostics plus a separately explicit installed native-admission diagnostic. */
public object RpcDesktopWindowsRuntimeReadback {
    /** Existing launcher diagnostic only. Never discover a classpath/ambient adapter or authorize a DLL. */
    public fun runPreviewAdapter(): String {
        // Preserve the ordinary host/source/linked-runtime checks; this does not open a profile.
        run()
        val boot = ModuleLayer.boot()
        val module = boot.findModule("dev.p2pkit.rpc.windows.loader").orElseThrow {
            IllegalStateException("The isolated JDK21 adapter was not resolved")
        }
        val probe = checkNotNull(Class.forName(module, "dev.p2pkit.rpc.windows.loader.Probe")) {
            "Missing named adapter probe"
        }
        check(probe.module === module && module.layer === boot) { "Unexpected adapter module owner" }
        val result = probe.getMethod("readback").invoke(null)
        check(result is String && result.length in 1..2048 && result.startsWith("{\"schema\":1,\"scope\":")) {
            "Unexpected adapter diagnostic"
        }
        return "{\"source\":\"${RpcPhoneBuildStamp.SOURCE_COMMIT}\",\"adapter\":$result}"
    }

    /** Explicit native diagnostic only; ordinary readback and public provider availability are unchanged. */
    public fun runInstalledAdmission(): String {
        var phase = InstalledAdmissionPhase.RUNTIME_PRECHECK
        var failureReader: Method? = null
        try {
            run() // All original source/host/runtime checks remain, before installed acquisition.
            phase = InstalledAdmissionPhase.MODULE_LOOKUP
            val boot = ModuleLayer.boot()
            val module = boot.findModule("dev.p2pkit.rpc.windows.loader").orElseThrow {
                IllegalStateException("The isolated JDK21 adapter was not resolved")
            }
            phase = InstalledAdmissionPhase.MODULE_OWNER
            val system = ClassLoader.getSystemClassLoader()
            check(system != null && module.isNamed && module.layer === boot && !module.descriptor.isAutomatic &&
                module.classLoader === system) { "Unexpected installed diagnostic module owner" }
            phase = InstalledAdmissionPhase.PROBE_LOOKUP
            val probe = checkNotNull(Class.forName(module, "dev.p2pkit.rpc.windows.loader.Probe"))
            phase = InstalledAdmissionPhase.PROBE_OWNER
            check(probe.module === module && probe.classLoader === system && Modifier.isPublic(probe.modifiers) &&
                Modifier.isFinal(probe.modifiers) && !probe.isInterface) { "Unexpected installed diagnostic class" }
            phase = InstalledAdmissionPhase.ENTRY_LOOKUP
            val method = probe.getDeclaredMethod("installedAdmissionReadback")
            val reader = probe.getDeclaredMethod("installedAdmissionFailureStage", Throwable::class.java)
            phase = InstalledAdmissionPhase.ENTRY_OWNER
            for (entry in listOf(method, reader)) {
                check(entry.declaringClass === probe && entry.returnType === String::class.java &&
                    Modifier.isPublic(entry.modifiers) && Modifier.isStatic(entry.modifiers) &&
                    !entry.isBridge && !entry.isSynthetic) { "Unexpected installed diagnostic entry" }
            }
            failureReader = reader // Only the exact admitted module/class owns this read-only method.
            phase = InstalledAdmissionPhase.DESKTOP_RUNTIME_PREPARATION
            WindowsDesktopRuntimePreparation.prepare()
            phase = InstalledAdmissionPhase.NATIVE_ADMISSION
            val result = try {
                method.invoke(null)
            } catch (failure: InvocationTargetException) {
                throw failure.targetException // Original carrier/owners, never a retryable wrapper.
            }
            phase = InstalledAdmissionPhase.RESULT_VALIDATION
            return checkedInstalledAdmissionReadback(RpcPhoneBuildStamp.SOURCE_COMMIT, result)
        } catch (original: Throwable) {
            val operation = if (phase == InstalledAdmissionPhase.NATIVE_ADMISSION) {
                try { failureReader?.invoke(null, original) } catch (_: Throwable) { null }
            } else null
            reportInstalledAdmissionFailure(phase, operation, original) { System.err.println(it) }
        }
    }

    public fun run(): String = checkedWindowsRuntimeReadback(
        source = RpcPhoneBuildStamp.SOURCE_COMMIT,
        clean = RpcPhoneBuildStamp.SOURCE_CLEAN,
        os = System.getProperty("os.name"),
        architecture = System.getProperty("os.arch"),
        observe = ::observeRuntime,
    )

    /** Reads actual resolved classes/modules, not the image's release-file metadata or a caller override. */
    internal fun observeRuntime(): WindowsRuntimeObservation {
        val boot = ModuleLayer.boot()
        val options = listOf(
            ExtendedOpenOption.NOSHARE_READ,
            ExtendedOpenOption.NOSHARE_WRITE,
            ExtendedOpenOption.NOSHARE_DELETE,
        )
        val type = ExtendedOpenOption::class.java
        val module = type.module
        val found = boot.findModule("jdk.unsupported").orElse(null)
        val resolved = boot.configuration().findModule("jdk.unsupported").orElse(null)
        return WindowsRuntimeObservation(
            javaFeature = Runtime.version().feature(),
            javaVersion = Runtime.version().toString(),
            moduleName = module.name,
            bootModule = module.isNamed && module.layer === boot && module === found,
            runtimeImageModule = resolved?.reference()?.location()?.orElse(null)?.toString() ==
                "jrt:/jdk.unsupported",
            exported = module.isExported("com.sun.nio.file", RpcDesktopWindowsRuntimeReadback::class.java.module),
            optionType = OpenOption::class.java.isAssignableFrom(type) && options.all { it.javaClass === type },
            optionNames = options.map { it.name },
        )
    }
}

internal data class WindowsRuntimeObservation(
    val javaFeature: Int,
    val javaVersion: String,
    val moduleName: String?,
    val bootModule: Boolean,
    val runtimeImageModule: Boolean,
    val exported: Boolean,
    val optionType: Boolean,
    val optionNames: List<String>,
)

/** Internal deterministic policy seam; production always obtains its observation from the running JVM. */
internal fun checkedWindowsRuntimeReadback(
    source: String,
    clean: Boolean,
    os: String,
    architecture: String,
    observe: () -> WindowsRuntimeObservation,
): String {
    check(clean && source.matches(Regex("[a-f0-9]{40}"))) { "Clean source identity is required" }
    check(os.startsWith("Windows") && architecture in setOf("amd64", "x86_64")) {
        "Actual Windows x64 execution is required"
    }
    val actual = observe()
    check(actual.javaFeature in setOf(17, 21)) { "Unreviewed packaged Java feature" }
    check(actual.javaVersion.length in 1..128 && actual.javaVersion.matches(Regex("[0-9A-Za-z.+_-]+"))) {
        "Unsupported runtime version observation"
    }
    check(Runtime.Version.parse(actual.javaVersion).feature() == actual.javaFeature) {
        "Inconsistent runtime version observation"
    }
    check(actual.moduleName == "jdk.unsupported" && actual.bootModule && actual.runtimeImageModule && actual.exported) {
        "The runtime image did not resolve/export the required module"
    }
    check(actual.optionType && actual.optionNames == listOf("NOSHARE_READ", "NOSHARE_WRITE", "NOSHARE_DELETE")) {
        "Required runtime OpenOption constants did not resolve"
    }
    // The only interpolated strings have the bounded ASCII syntax validated above. No private paths or data.
    return "{\"scope\":\"WINDOWS_RUNTIME_MODULE_RESOLUTION_ONLY_NOT_PROFILE_OR_RELEASE\"," +
        "\"source\":\"$source\",\"javaFeature\":${actual.javaFeature}," +
        "\"javaVersion\":\"${actual.javaVersion}\",\"module\":\"jdk.unsupported\"," +
        "\"options\":[\"NOSHARE_READ\",\"NOSHARE_WRITE\",\"NOSHARE_DELETE\"]," +
        "\"nativeLoad\":\"NOT_PERFORMED\",\"profileAccess\":\"NOT_PERFORMED\"}"
}

/** Bounded result formatting only: supplied text is never installation or native-call authority. */
internal fun checkedInstalledAdmissionReadback(source: String, result: Any?): String {
    check(source.matches(Regex("[a-f0-9]{40}"))) { "Clean source identity is required" }
    val expected = "{\"schema\":1,\"scope\":\"INSTALLED_ADMISSION_ONLY_NOT_PROFILE_PROVIDER_QUALIFICATION\"," +
        "\"admission\":\"REGISTERED\",\"repeat\":\"REUSED\",\"profileStorage\":\"NOT_ENTERED\"," +
        "\"network\":\"NOT_ENTERED\",\"publicProvider\":\"DISABLED\"}"
    check(result is String && result == expected) { "Unexpected installed admission diagnostic result" }
    return "{\"source\":\"$source\",\"admission\":$result}"
}

/** Diagnostic vocabulary only, never admission permission or private exception classification. */
internal enum class InstalledAdmissionPhase {
    RUNTIME_PRECHECK, MODULE_LOOKUP, MODULE_OWNER, PROBE_LOOKUP, PROBE_OWNER,
    ENTRY_LOOKUP, ENTRY_OWNER, DESKTOP_RUNTIME_PREPARATION, NATIVE_ADMISSION, RESULT_VALIDATION,
}

private val installedFailureOperations = setOf(
    "NO_MATCHING_RETAINED_FAILURE", "UNKNOWN_RETAINED_OPERATION", "RESERVATION", "BOOTSTRAP",
    "INSTALLATION", "PROFILE_PREPARATION", "JNI_REGISTRATION", "PUBLISH_REGISTERED",
    "BOOTSTRAP_FRAME", "BOOTSTRAP_EXPORTS", "BOOTSTRAP_PROCESS", "BOOTSTRAP_SYSTEM_PATH",
    "BOOTSTRAP_PROVIDER_PIN", "BOOTSTRAP_PROVIDER_PATH", "PROFILE_PRECONDITION",
    "PROFILE_SYSTEM_MODULES",
    "PROFILE_KNOWN_FOLDER",
    "PROFILE_PARENT_PIN",
    "PROFILE_JVM_IMAGE",
    "PROFILE_JVM_FILE",
    "PROFILE_JVM_SECURITY",
    "PROFILE_JVM_ANCESTORS",
    "PROFILE_FILE",
    "PROFILE_SECURITY",
    "PROFILE_ANCESTORS",
    "PROFILE_BYTES",
    "PROFILE_MANIFEST",
    "PROFILE_PACKAGE",
    "PROFILE_IMPORTS",
    "PROFILE_PREPARE_LOAD",
    "PROFILE_LOAD_IMAGE",
    "PROFILE_VERIFY_IMAGE",
    "PROFILE_REGISTER_JNI",
    "API_SET_PRECONDITION", "API_SET_FRAME", "API_SET_QUERY_EXPORT", "API_SET_PROCESS_QUERY",
    "API_SET_NAMESPACE_POINTER", "API_SET_NAMESPACE_REGION", "API_SET_NAMESPACE_HEADER",
    "API_SET_NAMESPACE_DATA", "API_SET_NAMESPACE_RECHECK", "API_SET_ROUTE_PIN",
    "API_SET_RETURN_UNKNOWN", "API_SET_RETIREMENT",
) + buildSet {
    // Fixed diagnostic vocabulary shared with the retained JDK21 cohort. No arbitrary suffix/text
    // is accepted, and none of these labels changes the original failure or grants admission.
    val operations = listOf(
        "SYSTEM_MODULE_ABSENT", "SYSTEM_LEAF_POLICY", "SYSTEM_ANCESTOR_POLICY", "SYSTEM_GRAPH_RECHECK",
        "SYSTEM_UNKNOWN_OUTCOME", "SYSTEM_RETURN_UNKNOWN", "SYSTEM_RETIREMENT", "SYSTEM_PRECONDITION",
        "SYSTEM_FRAME", "SYSTEM_DIRECTORY", "SYSTEM_MODULE_PIN", "SYSTEM_MODULE_PATH", "SYSTEM_FILE",
        "SYSTEM_SECURITY", "SYSTEM_ANCESTORS", "SYSTEM_BYTE_BOUND", "SYSTEM_BYTES", "SYSTEM_EXPORT_INPUT",
        "SYSTEM_EXPORT_GRAPH", "SYSTEM_UNKNOWN_OPERATION",
    )
    val slots = listOf(
        "NO_SLOT", "SLOT_ZERO", "SLOT_ONE", "SLOT_TWO", "SLOT_THREE", "SLOT_FOUR",
        "SLOT_FIVE", "SLOT_SIX", "SLOT_SEVEN", "UNKNOWN_SLOT",
    )
    for (operation in operations) for (slot in slots) add("${operation}_$slot")
}

/** Secondary readback/output failures never replace the original retained failure. */
internal fun reportInstalledAdmissionFailure(
    phase: InstalledAdmissionPhase,
    operation: Any?,
    original: Throwable,
    emit: (String) -> Unit,
): Nothing {
    try {
        val bounded = if (phase == InstalledAdmissionPhase.NATIVE_ADMISSION && operation is String &&
            operation.length <= 64 && operation in installedFailureOperations) operation else "DIAGNOSTIC_UNAVAILABLE"
        emit("WINDOWS_INSTALLED_ADMISSION_FAILURE stage=${phase.name} operation=$bounded")
    } catch (_: Throwable) {
        // Reporting is best effort, but failure propagation and process exit remain mandatory.
    }
    throw original
}
