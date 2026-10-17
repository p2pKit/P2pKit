package dev.p2pkit.rpc.windows.loader;

import java.lang.foreign.Arena;
import java.lang.foreign.Linker;
import java.lang.foreign.MemorySegment;
import java.lang.reflect.Constructor;
import java.lang.reflect.Field;
import java.lang.reflect.InvocationTargetException;
import java.lang.reflect.Method;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Arrays;
import java.util.concurrent.atomic.AtomicReference;

/** Independent DLL file controls; no JNI, DLL loading, storage operation or installation authority. */
public final class ProfileDllFileCandidateTests {
    private static final String LOCATOR = "C:\\fixture\\p2pkit-windows-profile.dll";

    private ProfileDllFileCandidateTests() {}

    public static void main(String[] arguments) throws Throwable {
        check(arguments.length >= 1);
        WindowsLoaderRuntime.requireDiagnosticRuntime();
        String mode = arguments[0];
        String scope = "INERT_LOCATOR_AND_OWNER_NOT_NATIVE_OR_AUTHORITY";
        if (mode.startsWith("actual")) {
            check(arguments.length == 2);
            actual(mode, arguments[1]);
            scope = mode.equals("actual") ?
                "DEVELOPMENT_DLL_FILE_LEASE_NOT_ACL_ANCESTOR_BYTES_OR_LOADING_AUTHORITY" :
                "DEVELOPMENT_DLL_FILE_REFUSAL_NOT_ACL_ANCESTOR_BYTES_OR_LOADING_AUTHORITY";
        } else {
            check(arguments.length == 1);
            switch (mode) {
                case "path-valid" -> validPaths();
                case "path-refusal" -> refusedPaths();
                case "owner-refusal" -> ownerRefusal();
                case "substitution" -> substitution();
                case "failure-latch" -> failureLatch();
                default -> throw new AssertionError("Unknown profile DLL file control");
            }
        }
        System.out.println("WINDOWS_PROFILE_DLL_FILE_PASS case=" + mode + " scope=" + scope);
    }

    private static void validPaths() {
        for (String value : new String[] {LOCATOR, "C:\\p2pkit-windows-profile.dll",
            "z:\\Program Files\\P2pKit-1.2_3\\p2pkit-windows-profile.dll"}) {
            WindowsProfileDllPath.require(value);
        }
        String suffix = "\\p2pkit-windows-profile.dll";
        String maximum = "C:\\" + "a".repeat(259 - 3 - suffix.length()) + suffix;
        check(maximum.length() == WindowsProfileDllPath.MAXIMUM_PATH_CHARS - 1);
        WindowsProfileDllPath.require(maximum);
        expect(IllegalArgumentException.class, () -> WindowsProfileDllPath.require("C:\\a" + maximum.substring(3)));
    }

    private static void refusedPaths() {
        for (String value : new String[] {null, "", "p2pkit-windows-profile.dll", "C:p2pkit-windows-profile.dll",
            "C:/fixture/p2pkit-windows-profile.dll", "\\\\server\\share\\p2pkit-windows-profile.dll",
            "\\\\?\\C:\\fixture\\p2pkit-windows-profile.dll", "C:\\fixture\\..\\p2pkit-windows-profile.dll",
            "C:\\fixture\\\\p2pkit-windows-profile.dll", "C:\\fixture \\p2pkit-windows-profile.dll",
            "C:\\CON.txt\\p2pkit-windows-profile.dll", "C:\\CON .txt\\p2pkit-windows-profile.dll",
            "C:\\LPT9\\p2pkit-windows-profile.dll", "C:\\COM1\\p2pkit-windows-profile.dll",
            "C:\\fixture\\p2pkit-windows-profile.dll:stream", "C:\\fixture\\other.dll",
            "C:\\fixture\\P2PKIT-WINDOWS-PROFILE.DLL", "C:\\f\u0000ixture\\p2pkit-windows-profile.dll"}) {
            expect(IllegalArgumentException.class, () -> WindowsProfileDllPath.require(value));
        }
    }

    private static void ownerRefusal() throws Throwable {
        WindowsOriginalProfileDllFileCandidate missing = new WindowsOriginalProfileDllFileCandidate(null, LOCATOR);
        WindowsOriginalProfileDllFileCandidate.Failure failure = failure(missing);
        check(failure.retainedCandidate == missing && failure.operationFailure == null);
        expect(IllegalStateException.class, missing::observe);
        expect(IllegalStateException.class, missing::completed);
        expect(IllegalStateException.class, missing::leaseHeld);
        expect(IllegalStateException.class, () -> WindowsOriginalFileLease.forProfileDll(missing));
        expect(IllegalArgumentException.class, () -> WindowsOriginalFileLease.forProfileDll(null));
        check(!(boolean) value(missing, "attempted") && value(missing, "lease") == null);
        check(failure(missing) == failure && failure.operationFailure == null);
    }

    private static void substitution() throws Throwable {
        try (Arena scope = Arena.ofConfined()) {
            WindowsSystemBootstrapCandidate bootstrap = inertBootstrap(scope);
            WindowsOriginalProfileDllFileCandidate owner =
                new WindowsOriginalProfileDllFileCandidate(bootstrap, LOCATOR);
            field(bootstrap, "profileDll").set(bootstrap, owner);
            field(owner, "attempted").setBoolean(owner, true);
            char[] source = (LOCATOR + '\0').toCharArray();
            field(owner, "originalPath").set(owner, source);
            WindowsOriginalFileLease retained = WindowsOriginalFileLease.forProfileDll(owner);
            field(owner, "lease").set(owner, retained);
            WindowsOriginalFileLease replacement = WindowsOriginalFileLease.forProfileDll(owner);
            check(value(retained, "originalOwner") == null && value(retained, "originalProfileDllOwner") == owner);
            check(value(retained, "sourcePath") != source);
            char[] expected = source.clone();
            source[3] ^= 1;
            check(Arrays.equals((char[]) value(retained, "sourcePath"), expected));
            expect(IllegalStateException.class, () -> owner.requireOriginalLease(replacement));
            expect(IllegalStateException.class, replacement::observe);
            check(!(boolean) value(replacement, "attempted") && value(replacement, "frameArena") == null);
            WindowsOriginalJvmFileCandidate jvm = new WindowsOriginalJvmFileCandidate(
                null, null, null, null, null, null, null, 0);
            expect(IllegalStateException.class, () -> retained.newJvmBytes(jvm));
            expect(IllegalStateException.class, () -> retained.newJvmSecurity(jvm));
            expect(IllegalStateException.class,
                () -> retained.newJvmAncestors(jvm, null, null, null, null, null, null));
            WindowsOriginalProfileDllFileCandidate other =
                new WindowsOriginalProfileDllFileCandidate(bootstrap, LOCATOR);
            expect(IllegalStateException.class, other::observe);
            expect(IllegalStateException.class, () -> WindowsOriginalFileLease.forProfileDll(other));
            check(value(bootstrap, "originalJvm") == null && value(bootstrap, "profileDll") == owner);
            for (long bytes : new long[] {512, 513, 32L * 1024 * 1024}) {
                check(!(boolean) invoke(retained, "refusedFileSize", bytes));
            }
            for (long bytes : new long[] {Long.MIN_VALUE, -1, 0, 511, 32L * 1024 * 1024 + 1, Long.MAX_VALUE}) {
                check((boolean) invoke(retained, "refusedFileSize", bytes));
            }
            WindowsOriginalFileLease jvmLease = new WindowsOriginalFileLease(jvm);
            check(!(boolean) invoke(jvmLease, "refusedFileSize", 1L));
            check(!(boolean) invoke(jvmLease, "refusedFileSize", 512L * 1024 * 1024));
            check((boolean) invoke(jvmLease, "refusedFileSize", 512L * 1024 * 1024 + 1));
            check(value(retained, "frameArena") == null && value(retained, "handleArena") == null &&
                scope.scope().isAlive());
        }
    }

    private static void failureLatch() throws Throwable {
        try (Arena scope = Arena.ofConfined()) {
            WindowsSystemBootstrapCandidate bootstrap = inertBootstrap(scope);
            WindowsOriginalProfileDllFileCandidate.Failure failed =
                (WindowsOriginalProfileDllFileCandidate.Failure) expect(
                    WindowsOriginalProfileDllFileCandidate.Failure.class,
                    () -> bootstrap.inspectOriginalProfileDll("not-an-absolute-DLL"));
            WindowsOriginalProfileDllFileCandidate owner = failed.retainedCandidate;
            check(value(bootstrap, "profileDll") == owner && (boolean) value(bootstrap, "profileDllAttempted"));
            check(failed.operationFailure instanceof IllegalArgumentException && (boolean) value(owner, "failed"));
            check(value(owner, "lease") == null && value(owner, "originalPath") == null);
            retainedFailure(owner, failed);
            expect(IllegalStateException.class, () -> bootstrap.inspectOriginalProfileDll(LOCATOR));
            check(value(bootstrap, "originalJvm") == null && scope.scope().isAlive());
        }
        // Missing fixed original system entries also fail before any native frame/call, after core attachment.
        try (Arena scope = Arena.ofConfined()) {
            WindowsSystemBootstrapCandidate bootstrap = inertBootstrap(scope);
            WindowsOriginalProfileDllFileCandidate.Failure failed =
                (WindowsOriginalProfileDllFileCandidate.Failure) expect(
                    WindowsOriginalProfileDllFileCandidate.Failure.class,
                    () -> bootstrap.inspectOriginalProfileDll(LOCATOR));
            WindowsOriginalProfileDllFileCandidate owner = failed.retainedCandidate;
            WindowsOriginalFileLease lease = (WindowsOriginalFileLease) value(owner, "lease");
            check(lease != null && failed.operationFailure instanceof IllegalStateException);
            check(value(lease, "frameArena") == null && !(boolean) value(lease, "attempted"));
            check(((WindowsOriginalFileLease.Failure) value(lease, "failure")).retainedCandidate == lease);
            retainedFailure(owner, failed);
            check(value(bootstrap, "profileDll") == owner && scope.scope().isAlive());
        }
    }

    /** Only inert test-owned private fields are installed. No bootstrap.observe or original system call runs. */
    private static WindowsSystemBootstrapCandidate inertBootstrap(Arena scope) throws ReflectiveOperationException {
        Constructor<WindowsSystemBootstrapCandidate> constructor =
            WindowsSystemBootstrapCandidate.class.getDeclaredConstructor(Linker.class);
        constructor.setAccessible(true);
        WindowsSystemBootstrapCandidate bootstrap = constructor.newInstance((Object) null);
        field(bootstrap, "originalArena").set(bootstrap, scope);
        field(bootstrap, "succeeded").setBoolean(bootstrap, true);
        field(bootstrap, "frameRetired").setBoolean(bootstrap, true);
        return bootstrap;
    }

    private static void actual(String mode, String source) throws Throwable {
        check(mode.equals("actual") || mode.equals("actual-absent") || mode.equals("actual-path-refusal"));
        WindowsProfileDllPath.require(source);
        Path path = Path.of(source);
        check(path.isAbsolute() && path.equals(path.normalize()));
        long fixtureBytes = Files.size(path); // Development-fixture comparison only; no bytes or digest claimed.
        check(fixtureBytes >= 512 && fixtureBytes <= 32L * 1024 * 1024);
        WindowsSystemBootstrapCandidate bootstrap = WindowsSystemBootstrapCandidate.inspect();
        check(value(bootstrap, "originalJvm") == null && !(boolean) value(bootstrap, "originalJvmAttempted"));
        if (!mode.equals("actual")) {
            String refusedPath = source + ":stream";
            if (mode.equals("actual-absent")) {
                Path absent = path.getParent().resolve("missing").resolve(path.getFileName());
                WindowsProfileDllPath.require(absent.toString());
                check(Files.notExists(absent));
                refusedPath = absent.toString();
            }
            final String locator = refusedPath;
            WindowsOriginalProfileDllFileCandidate.Failure failed =
                (WindowsOriginalProfileDllFileCandidate.Failure) expect(
                    WindowsOriginalProfileDllFileCandidate.Failure.class,
                    () -> bootstrap.inspectOriginalProfileDll(locator));
            WindowsOriginalProfileDllFileCandidate owner = failed.retainedCandidate;
            check(value(bootstrap, "profileDll") == owner && value(bootstrap, "originalJvm") == null);
            if (mode.equals("actual-absent")) {
                WindowsOriginalFileLease lease = (WindowsOriginalFileLease) value(owner, "lease");
                check(lease != null && failed.operationFailure instanceof WindowsOriginalFileLease.Failure);
                check((long) value(lease, "rawHandle") == -1 && value(lease, "handle") == null);
                check(!(boolean) value(lease, "nativeReturnUnconfirmed") && (boolean) value(lease, "frameRetired"));
                check(((Arena) value(lease, "handleArena")).scope().isAlive());
            } else {
                check(value(owner, "lease") == null && failed.operationFailure instanceof IllegalArgumentException);
            }
            retainedFailure(owner, failed);
            expect(IllegalStateException.class, () -> bootstrap.inspectOriginalProfileDll(source));
            check(bootstrap.completed());
            productiveRefusal();
            return;
        }
        WindowsOriginalProfileDllFileCandidate owner = bootstrap.inspectOriginalProfileDll(source);
        WindowsOriginalFileLease lease = (WindowsOriginalFileLease) value(owner, "lease");
        MemorySegment handle = (MemorySegment) value(lease, "handle");
        Arena handleArena = (Arena) value(lease, "handleArena");
        long rawHandle = (long) value(lease, "rawHandle");
        check(owner.completed() && owner.leaseHeld() && lease.completed() && handleArena.scope().isAlive());
        check(rawHandle > 0 && handle.address() == rawHandle && handle.scope().equals(handleArena.scope()));
        check(value(bootstrap, "profileDll") == owner && value(lease, "originalProfileDllOwner") == owner &&
            value(lease, "originalOwner") == null && value(bootstrap, "originalJvm") == null);
        long[] metadata = (long[]) value(lease, "first");
        check(Arrays.equals(metadata, (long[]) value(lease, "second")) && metadata[4] == fixtureBytes &&
            metadata[5] == 1 && !(boolean) value(lease, "nativeReturnUnconfirmed"));
        check((boolean) value(lease, "frameRetired") && !((Arena) value(lease, "frameArena")).scope().isAlive());
        check(((WindowsOriginalFileLease.Failure) value(lease, "failure")).retainedCandidate == lease);
        check(failure(owner).retainedCandidate == owner && failure(owner).operationFailure == null);
        WindowsOriginalFileLease substitute = WindowsOriginalFileLease.forProfileDll(owner);
        expect(IllegalStateException.class, substitute::observe);
        check(!(boolean) value(substitute, "attempted") && value(substitute, "frameArena") == null);
        expect(IllegalStateException.class, () -> bootstrap.inspectOriginalProfileDll(source));
        expect(IllegalStateException.class, owner::observe);
        AtomicReference<Throwable> unexpected = new AtomicReference<>();
        Thread worker = Thread.startVirtualThread(() -> {
            try {
                expect(IllegalStateException.class, owner::leaseHeld);
                expect(IllegalStateException.class, owner::completed);
                expect(IllegalStateException.class, lease::completed);
                expect(IllegalStateException.class, () -> bootstrap.inspectOriginalProfileDll(source));
            } catch (Throwable caught) { unexpected.set(caught); }
        });
        worker.join();
        check(unexpected.get() == null);
        System.gc();
        check(value(bootstrap, "profileDll") == owner && value(owner, "lease") == lease &&
            value(lease, "handle") == handle && (long) value(lease, "rawHandle") == rawHandle);
        check(owner.completed() && owner.leaseHeld() && bootstrap.completed() && handleArena.scope().isAlive());
        check(value(bootstrap, "originalJvm") == null && !(boolean) value(bootstrap, "originalJvmAttempted"));
        productiveRefusal();
    }

    private static void retainedFailure(WindowsOriginalProfileDllFileCandidate owner,
        WindowsOriginalProfileDllFileCandidate.Failure failed) {
        check(expect(WindowsOriginalProfileDllFileCandidate.Failure.class, owner::observe) == failed);
        check(expect(WindowsOriginalProfileDllFileCandidate.Failure.class, owner::completed) == failed);
        check(expect(WindowsOriginalProfileDllFileCandidate.Failure.class, owner::leaseHeld) == failed);
        check(expect(WindowsOriginalProfileDllFileCandidate.Failure.class, owner::originalPathSnapshot) == failed);
        check(expect(WindowsOriginalProfileDllFileCandidate.Failure.class,
            () -> WindowsOriginalFileLease.forProfileDll(owner)) == failed);
    }

    private static void productiveRefusal() {
        Throwable refused = expect(WindowsLoader.Unavailable.class, WindowsLoader::openInstalledProvider);
        check(WindowsLoader.REFUSAL.equals(refused.getMessage()));
    }
    private static WindowsOriginalProfileDllFileCandidate.Failure failure(WindowsOriginalProfileDllFileCandidate owner)
        throws ReflectiveOperationException {
        return (WindowsOriginalProfileDllFileCandidate.Failure) value(owner, "failure");
    }
    private static Field field(Object owner, String name) throws ReflectiveOperationException {
        Field field = owner.getClass().getDeclaredField(name);
        field.setAccessible(true);
        return field;
    }
    private static Object value(Object owner, String name) throws ReflectiveOperationException {
        return field(owner, name).get(owner);
    }
    private static Object invoke(WindowsOriginalFileLease owner, String name, long input) throws Throwable {
        Method method = WindowsOriginalFileLease.class.getDeclaredMethod(name, long.class);
        method.setAccessible(true);
        try { return method.invoke(owner, input); }
        catch (InvocationTargetException failure) { throw failure.getCause(); }
    }
    private interface Action { void run() throws Throwable; }
    private static Throwable expect(Class<? extends Throwable> type, Action action) {
        try { action.run(); }
        catch (Throwable caught) {
            if (type.isInstance(caught)) return caught;
            throw new AssertionError("Unexpected profile DLL file control failure", caught);
        }
        throw new AssertionError("Expected profile DLL file refusal");
    }
    private static void check(boolean value) {
        if (!value) throw new AssertionError("Profile DLL file control failed");
    }
}
