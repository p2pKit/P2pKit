package dev.p2pkit.rpc.windows.loader;

import java.lang.reflect.InvocationTargetException;
import java.lang.reflect.Method;
import java.nio.file.Path;

/** Actual Java17 factory -> exact boot-module typed refusal, not installed authority or native execution. */
public final class InstalledProviderTests {
    private InstalledProviderTests() {}

    public static void main(String[] args) throws Exception {
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
