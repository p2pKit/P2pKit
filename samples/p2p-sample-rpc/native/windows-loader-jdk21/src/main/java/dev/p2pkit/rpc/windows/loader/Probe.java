package dev.p2pkit.rpc.windows.loader;

/** Existing-app diagnostic entry point. It never selects an OS DLL or opens an installed/profile path. */
public final class Probe {
    private Probe() {}

    /** Callable from the existing Java17-compiled application only after explicit modular preview admission. */
    public static String readback() {
        // Direct preview API use makes this entry class itself require the JDK21 preview class-file contract.
        if (!Probe.class.getModule().isNativeAccessEnabled()) {
            throw new IllegalStateException("Named native access was not explicitly enabled");
        }
        return WindowsLoaderRuntime.readback();
    }

    public static void main(String[] arguments) {
        if (arguments.length != 0) {
            System.err.println("JDK21_LOADER_PROBE_REFUSED_ARGUMENTS");
            System.exit(2);
        }
        try {
            System.out.println(readback());
        } catch (RuntimeException failure) {
            System.err.println("JDK21_LOADER_PROBE_REFUSED_RUNTIME_POLICY");
            System.exit(2);
        }
    }
}
