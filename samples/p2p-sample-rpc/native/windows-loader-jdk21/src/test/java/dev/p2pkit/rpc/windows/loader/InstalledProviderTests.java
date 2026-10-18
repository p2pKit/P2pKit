package dev.p2pkit.rpc.windows.loader;

import java.lang.reflect.InvocationTargetException;
import java.lang.reflect.Method;
import java.lang.reflect.Modifier;
import java.nio.file.Path;
import java.util.Arrays;
import java.util.List;

import static dev.p2pkit.rpc.windows.loader.OriginalFileBytesLeaseTests.field;
import static dev.p2pkit.rpc.windows.loader.OriginalFileBytesLeaseTests.invoke;
import static dev.p2pkit.rpc.windows.loader.OriginalFileBytesLeaseTests.value;

/** Actual Java17 connections to original typed refusal/seeded diagnostic state, never installed native execution. */
public final class InstalledProviderTests {
    private InstalledProviderTests() {}

    public static void main(String[] args) throws Throwable {
        if (args.length == 3) {
            runtimeModule(args);
            return;
        }
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

    private static void runtimeModule(String[] args) throws Throwable {
        String mode = args[0];
        check(mode.equals("diagnostic-runtime-module-absent") || mode.equals("diagnostic-runtime-module-present"));
        WindowsLoaderRuntime.requireDiagnosticRuntime();
        requireNoInstalledAttempt();
        InstalledProcessControllerTests.publicState();
        Class<?> readback = PackagedVerifierTests.actualApplicationClass(
            "dev.p2pkit.sample.rpc.desktop.RpcDesktopWindowsRuntimeReadback", Path.of(args[1]).toRealPath(), args[2]);
        // Internal Kotlin method names include the actual compiler module suffix. Constrain the original
        // declared method, not caller text; never open application internals or invoke its native entry.
        Method[] observers = Arrays.stream(readback.getDeclaredMethods()).filter(method ->
            (method.getName().equals("observeRuntime") || method.getName().startsWith("observeRuntime$")) &&
            method.getParameterCount() == 0 && method.getReturnType().getName().equals(
                "dev.p2pkit.sample.rpc.desktop.WindowsRuntimeObservation")).toArray(Method[]::new);
        check(observers.length == 1);
        Method observer = observers[0];
        check(observer.getDeclaringClass() == readback && Modifier.isPublic(observer.getModifiers()) &&
            Modifier.isFinal(observer.getModifiers()) && !Modifier.isStatic(observer.getModifiers()) &&
            !observer.isBridge() && !observer.isSynthetic());
        Object instance = readback.getField("INSTANCE").get(null);
        ModuleLayer boot = ModuleLayer.boot();
        if (mode.equals("diagnostic-runtime-module-absent")) {
            check(boot.findModule("jdk.unsupported").isEmpty());
            boolean refused = false;
            try { observer.invoke(instance); }
            catch (InvocationTargetException caught) {
                Throwable original = caught.getTargetException();
                check(original.getClass() == NoClassDefFoundError.class &&
                    "com/sun/nio/file/ExtendedOpenOption".equals(original.getMessage()));
                refused = true;
            }
            check(refused);
        } else {
            Module module = boot.findModule("jdk.unsupported").orElseThrow();
            check(boot.configuration().findModule("jdk.unsupported").orElseThrow().reference()
                .location().orElseThrow().toString().equals("jrt:/jdk.unsupported"));
            Class<?> options = Class.forName(module, "com.sun.nio.file.ExtendedOpenOption");
            check(options != null && options.getModule() == module && module.getLayer() == boot &&
                module.isExported("com.sun.nio.file", readback.getModule()));
            Object actual = observer.invoke(instance);
            Class<?> observation = observer.getReturnType();
            check(actual != null && actual.getClass() == observation &&
                observation.getClassLoader() == readback.getClassLoader() &&
                observation.getModule() == readback.getModule());
            check(observation.getMethod("getJavaFeature").invoke(actual).equals(Runtime.version().feature()) &&
                observation.getMethod("getJavaVersion").invoke(actual).equals(Runtime.version().toString()) &&
                observation.getMethod("getModuleName").invoke(actual).equals("jdk.unsupported"));
            for (String getter : List.of("getBootModule", "getRuntimeImageModule", "getExported", "getOptionType"))
                check(observation.getMethod(getter).invoke(actual).equals(Boolean.TRUE));
            check(observation.getMethod("getOptionNames").invoke(actual).equals(
                List.of("NOSHARE_READ", "NOSHARE_WRITE", "NOSHARE_DELETE")));
        }
        requireNoInstalledAttempt();
        InstalledProcessControllerTests.publicState();
        System.out.println("WINDOWS_RUNTIME_MODULE_CONNECTION_PASS case=" + mode +
            " scope=ACTUAL_JVM_MODULE_RESOLUTION_NOT_WINDOWS_OR_INSTALLED_NATIVE");
    }

    private static void requireNoInstalledAttempt() throws ReflectiveOperationException {
        // Test-patched module's existing private-state inspection only; no access override on application code.
        var installed = WindowsLoader.class.getDeclaredField("installedAttempt");
        var bootstrap = WindowsSystemBootstrapCandidate.class.getDeclaredField("processOwner");
        installed.setAccessible(true);
        bootstrap.setAccessible(true);
        check(installed.get(null) == null && bootstrap.get(null) == null &&
            WindowsJniRegistrationOwner.retainedProcessOwner() == null);
    }

    private static void installedDiagnostic(String[] args) throws Throwable {
        String mode = args[0];
        check(mode.equals("diagnostic-connected-reuse") || mode.equals("diagnostic-connected-failure") ||
            mode.equals("diagnostic-connected-system-absent") || mode.equals("diagnostic-connected-system-unknown") ||
            mode.equals("diagnostic-connected-in-progress") || mode.equals("diagnostic-connected-source-or-host-refusal"));
        WindowsLoaderRuntime.requireDiagnosticRuntime();
        InstalledProcessControllerTests.publicState();
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
            } else if (mode.startsWith("diagnostic-connected-system-")) {
                WindowsInstalledProfileCandidate profile = new WindowsInstalledProfileCandidate(null);
                field(profile, "failed").setBoolean(profile, true);
                field(profile, "diagnosticPhase").setInt(profile, 1);
                WindowsOriginalSystemModulesCandidate systems = new WindowsOriginalSystemModulesCandidate(null);
                field(systems, "failed").setBoolean(systems, true);
                if (mode.equals("diagnostic-connected-system-absent")) {
                    field(systems, "outcome").set(systems, "MODULE_ABSENT");
                    field(systems, "stoppedSlot").setInt(systems, 4);
                    field(profile, "systems").set(profile, systems);
                } else {
                    field(systems, "activeSlot").setInt(systems, 1);
                    field(systems, "nativeReturnUnconfirmed").setBoolean(systems, true);
                    Object profileFailure = value(profile, "failure");
                    field(profileFailure, "operationFailure").set(profileFailure, value(systems, "failure"));
                }
                field(attempt, "diagnosticPhase").setInt(attempt, 4);
                expectedFailure = invoke(attempt, "seal", new Class<?>[] {Throwable.class}, value(profile, "failure"));
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
                InstalledProcessControllerTests.publicState();
                System.out.println("WINDOWS_INSTALLED_DIAGNOSTIC_CONNECTION_PASS case=" + mode +
                    " scope=ACTUAL_APPLICATION_BINDING_TO_INERT_STATE_NOT_INSTALLED_NATIVE_EXECUTION");
                return;
            }
            throw new AssertionError("Installed diagnostic refusal model unexpectedly succeeded");
        }
        check(value(attempt, "bootstrap") == null && value(attempt, "installation") == null && value(attempt, "profile") == null);
        InstalledProcessControllerTests.publicState();
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
