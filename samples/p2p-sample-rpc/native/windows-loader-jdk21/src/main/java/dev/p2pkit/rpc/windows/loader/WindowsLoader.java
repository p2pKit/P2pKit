package dev.p2pkit.rpc.windows.loader;

/**
 * Public fail-closed implementation boundary. There is no installed-root lease, trusted OS bootstrap,
 * constrained DLL load, JNI registration or complete Windows provider behind this API yet.
 */
public final class WindowsLoader {
    public static final String REFUSAL = "WINDOWS_LOADER_DISABLED_TRUSTED_BOOTSTRAP_NOT_IMPLEMENTED";

    private WindowsLoader() {}

    /**
     * Exact no-effects result of this fixed entry, never a generic native failure classification.
     * Only this class may construct it, before any installed/native acquisition. Future productive
     * failures must retain their actual owner and must not be translated into this retryable refusal.
     */
    public static final class Unavailable extends UnsupportedOperationException {
        private static final long serialVersionUID = 1L;

        private Unavailable() { super(REFUSAL); }
    }

    /**
     * No caller may supply a path, boolean, manifest or context to bypass the missing trust boundary.
     * A future normal return must retain the actual installed production image/runtime and registered
     * JNI owner for the process lifetime. A development/test DLL registration cannot satisfy this entry.
     */
    public static void openInstalledProvider() {
        WindowsLoaderRuntime.requireDiagnosticRuntime();
        throw new Unavailable();
    }
}
