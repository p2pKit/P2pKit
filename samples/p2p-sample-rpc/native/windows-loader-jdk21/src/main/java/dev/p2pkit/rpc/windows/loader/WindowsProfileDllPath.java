package dev.p2pkit.rpc.windows.loader;

import java.util.Locale;

/** Fixed bounded DLL locator syntax only; no file, runtime, package or native-call authority. */
final class WindowsProfileDllPath {
    static final int MAXIMUM_PATH_CHARS = 260;

    private WindowsProfileDllPath() {}

    static void require(String path) {
        if (path == null || path.length() < 4 || path.length() >= MAXIMUM_PATH_CHARS ||
            !path.matches("[A-Za-z]:\\\\[A-Za-z0-9 ._\\\\-]+") ||
            !path.endsWith("\\p2pkit-windows-profile.dll")) {
            throw new IllegalArgumentException("Unsupported canonical Windows library path");
        }
        String[] components = path.substring(3).split("\\\\", -1);
        for (String component : components) {
            if (component.isEmpty() || component.length() > 255 ||
                !component.matches("[A-Za-z0-9][A-Za-z0-9 ._-]*") || component.endsWith(".") ||
                component.endsWith(" ")) {
                throw new IllegalArgumentException("Unsupported Windows library path component");
            }
            String stem = component.split("\\.", 2)[0].stripTrailing().toUpperCase(Locale.ROOT);
            if (stem.equals("CON") || stem.equals("PRN") || stem.equals("AUX") || stem.equals("NUL") ||
                stem.matches("(?:COM|LPT)[1-9]")) {
                throw new IllegalArgumentException("Reserved Windows library path component");
            }
        }
    }

}
