package dev.p2pkit.rpc.windows.loader;

import java.lang.foreign.Arena;
import java.lang.foreign.MemorySegment;
import java.lang.foreign.ValueLayout;
import java.net.URI;

/** Actual preview/module diagnostics. None of these observations establishes installed DLL authority. */
public final class WindowsLoaderRuntime {
    public static final String MODULE = "dev.p2pkit.rpc.windows.loader";
    public static final String SCOPE = "JDK21_PREVIEW_MODULE_DIAGNOSTIC_NOT_DLL_OR_PROFILE";

    private WindowsLoaderRuntime() {}

    /** No supplied observations or override properties are accepted as permission to enter this module. */
    public static void requireDiagnosticRuntime() {
        Module own = WindowsLoaderRuntime.class.getModule();
        ModuleLayer boot = ModuleLayer.boot();
        Module base = Object.class.getModule();
        URI baseLocation = boot.configuration().findModule("java.base").orElseThrow()
            .reference().location().orElseThrow();
        if (Runtime.version().feature() != 21 || !own.isNamed() || !MODULE.equals(own.getName()) ||
            own.getLayer() != boot || boot.findModule(MODULE).orElse(null) != own ||
            own.getDescriptor().isAutomatic() || !own.isNativeAccessEnabled() ||
            ClassLoader.getSystemClassLoader().getUnnamedModule().isNativeAccessEnabled() ||
            Arena.class.getModule() != base || MemorySegment.class.getModule() != base ||
            ValueLayout.class.getModule() != base || base.getLayer() != boot ||
            !URI.create("jrt:/java.base").equals(baseLocation)) {
            throw new IllegalStateException("JDK21 preview named-module/native-access policy refused");
        }
    }

    static String readback() {
        requireDiagnosticRuntime();
        String version = Runtime.version().toString();
        if (version.length() > 128 || !version.matches("[0-9A-Za-z.+_-]+")) {
            throw new IllegalStateException("Unrepresentable runtime version");
        }
        // Platform properties are diagnostic hints only. No native/installed authority follows from them.
        boolean windowsX64 = System.getProperty("os.name", "").startsWith("Windows") &&
            (System.getProperty("os.arch", "").equals("amd64") ||
                System.getProperty("os.arch", "").equals("x86_64"));
        return "{\"schema\":1,\"scope\":\"" + SCOPE + "\",\"javaFeature\":21," +
            "\"javaVersion\":\"" + version + "\",\"module\":\"" + MODULE + "\"," +
            "\"javaVendor\":" + quotedMetadata(System.getProperty("java.vendor")) + "," +
            "\"javaRuntimeVersion\":" + quotedMetadata(System.getProperty("java.runtime.version")) + "," +
            "\"javaVmVersion\":" + quotedMetadata(System.getProperty("java.vm.version")) + "," +
            "\"previewEnabled\":true,\"namedNativeAccess\":true,\"unnamedNativeAccess\":false," +
            "\"ffmFromJavaBase\":true,\"windowsX64Hint\":" + windowsX64 + "," +
            "\"productionAvailable\":false,\"nativeLoad\":\"NOT_PERFORMED\"," +
            "\"profileAccess\":\"NOT_PERFORMED\"}";
    }

    /** Bounded diagnostic metadata only; control/non-ASCII bytes fail instead of escaping private data. */
    static String quotedMetadata(String value) {
        if (value == null || value.isEmpty() || value.length() > 128) {
            throw new IllegalStateException("Unsupported runtime metadata");
        }
        StringBuilder out = new StringBuilder(value.length() + 2).append('"');
        for (int i = 0; i < value.length(); i++) {
            char character = value.charAt(i);
            if (character < 32 || character > 126) throw new IllegalStateException("Unsupported runtime metadata");
            if (character == '\\' || character == '"') out.append('\\');
            out.append(character);
        }
        return out.append('"').toString();
    }
}
