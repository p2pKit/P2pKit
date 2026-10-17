package dev.p2pkit.rpc.windows.loader;

import java.lang.reflect.InvocationTargetException;
import java.lang.reflect.Method;
import java.nio.file.Path;

import static dev.p2pkit.rpc.windows.loader.OriginalFileBytesLeaseTests.invoke;
import static dev.p2pkit.rpc.windows.loader.OriginalFileBytesLeaseTests.value;

/** Actual Java17 connections to original typed refusal/seeded diagnostic state, never installed native execution. */
public final class InstalledProviderTests {
    private InstalledProviderTests() {}

    public static void main(String[] args) throws Throwable {
        if (args.length == 4) {
            installedDiagnostic(args);
            return;
        }
        check(args.length == 5);
        WindowsLoaderRuntime.requireDiagnosticRuntime();
        Path main = Path.of(args[0]).toRealPath();
        Class<?> factory = PackagedVerifierTests.actualClass("WindowsProfileInstalledProvider", main, args[1]);
        Class<?> files = PackagedVerifierTests.actualClass("WindowsProfileFiles", main, args[2]);
        Class<?> jni = PackagedVerifierTests.actualClass("WindowsProfileCustodyJni", main, args[3]);
        Class<?> unavailable = PackagedVerifierTests.actualClass("WindowsProfileInstalledProvider$Unavailable",
            main, args[4]);
        check(unavailable.getDeclaringClass() == factory);
        Object originalJni = jni.getField("INSTANCE").get(null);
        Method abi = jni.getDeclaredMethod("abi");
        unbound(abi, originalJni);
        check(WindowsJniRegistrationOwner.retainedProcessOwner() == null);
        Object originalFactory = factory.getField("INSTANCE").get(null);
        Method acquire = factory.getDeclaredMethod("acquireNative");
        Object originalCompanion = files.getField("Companion").get(null);
        Method open = originalCompanion.getClass().getDeclaredMethod("openInstalled");
        for (int attempt = 0; attempt < 2; attempt++) {
            refused(acquire, originalFactory, unavailable);
            refused(open, originalCompanion, unavailable);
            unbound(abi, originalJni);
            check(WindowsJniRegistrationOwner.retainedProcessOwner() == null);
        }
        System.out.println("WINDOWS_INSTALLED_PROVIDER_REFUSAL_PASS" +
            " scope=REAL_JDK21_TO_JDK17_TYPED_REFUSAL_NOT_INSTALLED_OR_NATIVE");
    }

    private static void installedDiagnostic(String[] args) throws Throwable {
        String mode = args[0];
        check(mode.equals("diagnostic-connected-reuse") || mode.equals("diagnostic-connected-failure") ||
            mode.equals("diagnostic-connected-in-progress") || mode.equals("diagnostic-connected-source-or-host-refusal"));
        WindowsLoaderRuntime.requireDiagnosticRuntime();
        OriginalFileBytesLeaseTests.expect(WindowsLoader.Unavailable.class, WindowsLoader::openInstalledProvider);
        Path main = Path.of(args[1]).toRealPath();
        Class<?> readback = PackagedVerifierTests.actualApplicationClass(
            "dev.p2pkit.sample.rpc.desktop.RpcDesktopWindowsRuntimeReadback", main, args[2]);
        Class<?> stamp = PackagedVerifierTests.actualApplicationClass(
            "dev.p2pkit.sample.rpc.RpcPhoneBuildStamp", main, args[3]);
        String source = (String) stamp.getField("SOURCE_COMMIT").get(null);
        boolean clean = stamp.getField("SOURCE_CLEAN").getBoolean(null);
        check(source.matches("[a-f0-9]{40}"));
        boolean windows = System.getProperty("os.name").startsWith("Windows");
        Method method = readback.getDeclaredMethod("runInstalledAdmission");
        Object instance = readback.getField("INSTANCE").get(null);
        Object attempt;
        Object expectedFailure = null;
        if (mode.equals("diagnostic-connected-reuse")) {
            check(windows && clean); // Real Windows clean-source connection, still seeded/inert native state.
            attempt = InstalledProcessControllerTests.seedRegistered();
        } else {
            attempt = InstalledProcessControllerTests.firstClaim(); // Prevent any first native entry even on a bug.
            if (mode.equals("diagnostic-connected-source-or-host-refusal")) check(!windows);
            else check(windows && clean);
            if (mode.equals("diagnostic-connected-failure")) {
                expectedFailure = invoke(attempt, "seal", new Class<?>[] {Throwable.class},
                    new LinkageError("inert original admitted failure"));
            }
        }
        if (mode.equals("diagnostic-connected-reuse")) {
            String expected = "{\"source\":\"" + source + "\",\"admission\":" +
                InstalledProcessControllerTests.INSTALLED_DIAGNOSTIC_RESULT + "}";
            check(method.invoke(instance).equals(expected));
            check(method.invoke(instance).equals(expected));
            check(value(attempt, "state").toString().equals("Registered"));
        } else {
            try { method.invoke(instance); }
            catch (InvocationTargetException failure) {
                Throwable original = failure.getTargetException();
                if (expectedFailure != null) check(original == expectedFailure);
                else check(original instanceof IllegalStateException);
                check(!(original instanceof WindowsLoader.Unavailable));
                check(value(attempt, "bootstrap") == null && value(attempt, "installation") == null && value(attempt, "profile") == null);
                OriginalFileBytesLeaseTests.expect(WindowsLoader.Unavailable.class, WindowsLoader::openInstalledProvider);
                System.out.println("WINDOWS_INSTALLED_DIAGNOSTIC_CONNECTION_PASS case=" + mode +
                    " scope=ACTUAL_APPLICATION_BINDING_TO_INERT_STATE_NOT_INSTALLED_NATIVE_EXECUTION");
                return;
            }
            throw new AssertionError("Installed diagnostic refusal model unexpectedly succeeded");
        }
        check(value(attempt, "bootstrap") == null && value(attempt, "installation") == null && value(attempt, "profile") == null);
        OriginalFileBytesLeaseTests.expect(WindowsLoader.Unavailable.class, WindowsLoader::openInstalledProvider);
        System.out.println("WINDOWS_INSTALLED_DIAGNOSTIC_CONNECTION_PASS case=" + mode +
            " scope=ACTUAL_APPLICATION_BINDING_TO_INERT_STATE_NOT_INSTALLED_NATIVE_EXECUTION");
    }

    private static void refused(Method method, Object instance, Class<?> unavailable) throws Exception {
        try { method.invoke(instance); }
        catch (InvocationTargetException failure) {
            Throwable actual = failure.getTargetException();
            check(actual.getClass() == unavailable && actual.getCause() != null &&
                actual.getCause().getClass() == WindowsLoader.Unavailable.class);
            check(WindowsLoader.REFUSAL.equals(actual.getCause().getMessage()));
            return;
        }
        throw new AssertionError("Installed provider unexpectedly admitted");
    }

    private static void unbound(Method abi, Object instance) throws Exception {
        try { abi.invoke(instance); }
        catch (InvocationTargetException failure) {
            check(failure.getTargetException() instanceof UnsatisfiedLinkError);
            return;
        }
        throw new AssertionError("Unavailable installed provider registered JNI");
    }

    private static void check(boolean value) {
        if (!value) throw new AssertionError("Installed provider refusal control failed");
    }
}
