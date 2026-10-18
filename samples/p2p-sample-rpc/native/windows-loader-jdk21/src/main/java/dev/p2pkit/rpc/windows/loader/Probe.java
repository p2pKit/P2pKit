package dev.p2pkit.rpc.windows.loader;

/** Existing-app diagnostics. Ordinary readback is inert; installed admission is separately explicit. */
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

    /**
     * Explicit installed-app diagnostic: original native load/image verification/JNI registration,
     * then same-owner reuse. No profile storage/network/provider entry. Failure propagates unchanged
     * with its process-lifetime owners; neither success nor failure enables the public provider.
     */
    public static String installedAdmissionReadback() {
        WindowsLoader.completeOriginalInstalledProvider();
        WindowsLoader.completeOriginalInstalledProvider();
        return "{\"schema\":1,\"scope\":\"INSTALLED_ADMISSION_ONLY_NOT_PROFILE_PROVIDER_QUALIFICATION\"," +
            "\"admission\":\"REGISTERED\",\"repeat\":\"REUSED\",\"profileStorage\":\"NOT_ENTERED\"," +
            "\"network\":\"NOT_ENTERED\",\"publicProvider\":\"DISABLED\"}";
    }

    /** Read only an exact retained failure; this method grants no runtime or installation authority. */
    public static String installedAdmissionFailureStage(Throwable original) {
        return WindowsLoader.installedFailureStage(original);
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
