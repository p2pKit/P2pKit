package dev.p2pkit.rpc.windows.loader;

/**
 * Public fail-closed implementation boundary. There is no installed-root lease, trusted OS bootstrap,
 * constrained DLL load, JNI registration or complete Windows provider behind this API yet.
 */
public final class WindowsLoader {
    public static final String REFUSAL = "WINDOWS_LOADER_DISABLED_TRUSTED_BOOTSTRAP_NOT_IMPLEMENTED";

    private WindowsLoader() {}

    /** No caller may supply a path, boolean, manifest or context to bypass the missing trust boundary. */
    public static void openInstalledProvider() {
        WindowsLoaderRuntime.requireDiagnosticRuntime();
        throw new UnsupportedOperationException(REFUSAL);
    }
}
