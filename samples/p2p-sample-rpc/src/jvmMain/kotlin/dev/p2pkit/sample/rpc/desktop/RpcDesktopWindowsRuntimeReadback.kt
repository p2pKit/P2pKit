package dev.p2pkit.sample.rpc.desktop

import com.sun.nio.file.ExtendedOpenOption
import dev.p2pkit.sample.rpc.RpcPhoneBuildStamp
import java.lang.reflect.InvocationTargetException
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
        run() // Existing clean-source and actual runtime/module checks, before any installed acquisition.
        val boot = ModuleLayer.boot()
        val module = boot.findModule("dev.p2pkit.rpc.windows.loader").orElseThrow {
            IllegalStateException("The isolated JDK21 adapter was not resolved")
        }
        val system = ClassLoader.getSystemClassLoader()
        check(system != null && module.isNamed && module.layer === boot && !module.descriptor.isAutomatic &&
            module.classLoader === system) { "Unexpected installed diagnostic module owner" }
        val probe = checkNotNull(Class.forName(module, "dev.p2pkit.rpc.windows.loader.Probe"))
        check(probe.module === module && probe.classLoader === system && Modifier.isPublic(probe.modifiers) &&
            Modifier.isFinal(probe.modifiers) && !probe.isInterface) { "Unexpected installed diagnostic class" }
        val method = probe.getDeclaredMethod("installedAdmissionReadback")
        check(method.declaringClass === probe && method.returnType === String::class.java &&
            Modifier.isPublic(method.modifiers) && Modifier.isStatic(method.modifiers) &&
            !method.isBridge && !method.isSynthetic) { "Unexpected installed diagnostic entry" }
        val result = try {
            method.invoke(null)
        } catch (failure: InvocationTargetException) {
            // Preserve the actual original carrier; never classify admitted failure as Unavailable.
            throw failure.targetException
        }
        return checkedInstalledAdmissionReadback(RpcPhoneBuildStamp.SOURCE_COMMIT, result)
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
