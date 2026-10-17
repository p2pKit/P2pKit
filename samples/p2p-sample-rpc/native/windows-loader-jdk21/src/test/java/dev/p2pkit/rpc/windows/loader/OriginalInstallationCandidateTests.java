package dev.p2pkit.rpc.windows.loader;

import java.lang.foreign.Arena;
import java.lang.foreign.Linker;
import java.lang.foreign.MemorySegment;
import java.lang.foreign.ValueLayout;
import java.lang.invoke.MethodHandles;
import java.lang.invoke.MethodType;
import java.lang.reflect.Constructor;
import java.lang.reflect.InvocationTargetException;
import java.lang.reflect.Method;
import java.util.Arrays;
import java.util.concurrent.atomic.AtomicReference;

import static dev.p2pkit.rpc.windows.loader.OriginalFileBytesLeaseTests.check;
import static dev.p2pkit.rpc.windows.loader.OriginalFileBytesLeaseTests.expect;
import static dev.p2pkit.rpc.windows.loader.OriginalFileBytesLeaseTests.field;
import static dev.p2pkit.rpc.windows.loader.OriginalFileBytesLeaseTests.invoke;
import static dev.p2pkit.rpc.windows.loader.OriginalFileBytesLeaseTests.value;

/** Inert exact-owner models only. Fake addresses are never downcalled; no Windows custody is claimed. */
public final class OriginalInstallationCandidateTests {
    private static final String PATH = "C:\\Program Files\\P2pKit Sample\\P2pKit Sample.exe";
    private static final LinkageError UNKNOWN = new LinkageError("inert missing primitive return");
    private static int calls;
    private static boolean unknown;
    private OriginalInstallationCandidateTests() {}

    public static void main(String[] arguments) throws Throwable {
        check(arguments.length == 1);
        WindowsLoaderRuntime.requireDiagnosticRuntime();
        String mode = arguments[0];
        switch (mode) {
            case "paths" -> paths();
            case "owner-refusal" -> ownerRefusal();
            case "bootstrap-order" -> bootstrapOrder();
            case "thread" -> wrongThread();
            case "fixed-call", "unknown-return" -> call(mode.equals("unknown-return"));
            case "retirement", "retirement-failure" -> retirement(mode.equals("retirement-failure"));
            case "roles" -> roles();
            case "core-substitution" -> coreSubstitution();
            case "leaf-refusal", "ancestor-refusal", "accepted-model" -> policy(mode);
            case "failure-latch" -> failureLatch();
            default -> throw new AssertionError("Unknown installation control");
        }
        System.out.println("WINDOWS_ORIGINAL_INSTALLATION_PASS case=" + mode +
            " scope=INERT_OWNERS_AND_FRAMES_NOT_INSTALLED_CUSTODY_OR_AUTHORITY");
    }

    private static char[] validate(MemorySegment buffer, int returned) throws Throwable {
        Method method = WindowsOriginalInstallationCandidate.class.getDeclaredMethod("validatePath", MemorySegment.class, int.class);
        method.setAccessible(true);
        try { return (char[]) method.invoke(null, buffer, returned); }
        catch (InvocationTargetException failure) { throw failure.getCause(); }
    }

    private static void put(MemorySegment buffer, String text) {
        buffer.fill((byte) 0x7f);
        for (int index = 0; index < text.length(); index++) buffer.setAtIndex(ValueLayout.JAVA_SHORT, index, (short) text.charAt(index));
        buffer.setAtIndex(ValueLayout.JAVA_SHORT, text.length(), (short) 0);
    }

    private static void paths() throws Throwable {
        try (Arena arena = Arena.ofConfined()) {
            MemorySegment buffer = arena.allocate(2048, 2);
            for (String path : new String[] {PATH, "D:\\Protected Apps\\P2pKit Sample\\P2pKit Sample.exe"}) {
                put(buffer, path);
                check(Arrays.equals(validate(buffer, path.length()), (path + '\0').toCharArray()));
                buffer.fill((byte) 0); // Returned observation is an independent bounded snapshot.
            }
            for (String path : new String[] {"", "relative\\P2pKit Sample.exe", "C:\\java.exe", "C:\\P2pKit Sample.exe",
                "C:\\Other\\P2pKit Sample.exe", "C:/P2pKit Sample/P2pKit Sample.exe", "\\\\server\\P2pKit Sample\\P2pKit Sample.exe",
                "C:\\..\\P2pKit Sample\\P2pKit Sample.exe", "C:\\CON\\P2pKit Sample\\P2pKit Sample.exe",
                "C:\\LPT9.txt\\P2pKit Sample\\P2pKit Sample.exe", "C:\\bad \\P2pKit Sample\\P2pKit Sample.exe",
                "C:\\bad.\\P2pKit Sample\\P2pKit Sample.exe", "C:\\\\P2pKit Sample\\P2pKit Sample.exe",
                "C:\\bad:stream\\P2pKit Sample\\P2pKit Sample.exe", "C:\\bad\0name\\P2pKit Sample\\P2pKit Sample.exe",
                "C:\\bad\u00e9\\P2pKit Sample\\P2pKit Sample.exe", "C:\\" + "x".repeat(256) + "\\P2pKit Sample\\P2pKit Sample.exe"}) {
                put(buffer, path);
                expect(IllegalStateException.class, () -> validate(buffer, path.length()));
            }
            put(buffer, PATH);
            for (int count : new int[] {0, -1, 1024, Integer.MAX_VALUE, PATH.length() - 1}) {
                expect(IllegalStateException.class, () -> validate(buffer, count));
            }
        }
    }

    private static void ownerRefusal() throws Throwable {
        WindowsOriginalInstallationCandidate owner = new WindowsOriginalInstallationCandidate(null);
        expect(IllegalStateException.class, owner::observe);
        expect(IllegalStateException.class, owner::completed);
        expect(IllegalStateException.class, owner::custodyAccepted);
        check(!(boolean) value(owner, "attempted") && value(owner, "frameArena") == null);
        check(((WindowsOriginalInstallationCandidate.Failure) value(owner, "failure")).retainedCandidate == owner);
        expect(IllegalArgumentException.class, () -> WindowsOriginalFileLease.forInstallation(null));
        expect(IllegalArgumentException.class, () -> WindowsOriginalFileSecurityQuery.forInstallation(null,
            null, null, null, null, null, null, null, null));
        expect(IllegalStateException.class, () -> WindowsOriginalFileAncestorsLease.forInstallation(null,
            null, null, null, null, null, null, null, null, null, null, null, null, null, null, null, 0, null));
    }

    private static void bootstrapOrder() throws Throwable {
        try (Fixture first = new Fixture(); Fixture other = new Fixture()) {
            WindowsOriginalInstallationCandidate unattached = new WindowsOriginalInstallationCandidate(first.bootstrap);
            expect(IllegalStateException.class, unattached::observe);
            expect(IllegalStateException.class, () -> first.bootstrap.requireOriginalInstallation(other.owner));
            field(first.bootstrap, "profileDllAttempted").set(first.bootstrap, true);
            expect(IllegalStateException.class, first.bootstrap::inspectOriginalInstallation);
            check(!(boolean) value(first.bootstrap, "installationAttempted"));
            field(first.bootstrap, "profileDllAttempted").set(first.bootstrap, false);
            field(first.bootstrap, "installationAttempted").set(first.bootstrap, true);
            expect(IllegalStateException.class, first.bootstrap::inspectOriginalInstallation);
            check(value(first.bootstrap, "installation") == first.owner && calls == 0);
        }
    }

    private static void wrongThread() throws Throwable {
        try (Fixture fixture = new Fixture()) {
            fixture.callFrame();
            byte[] before = fixture.buffers()[0].toArray(ValueLayout.JAVA_BYTE);
            AtomicReference<Throwable> failure = new AtomicReference<>();
            Thread other = Thread.startVirtualThread(() -> {
                try {
                    expect(IllegalStateException.class, fixture.owner::requireOriginalNativeInputs);
                    expect(IllegalStateException.class, () -> invoke(fixture.owner, "callOriginalPath"));
                    expect(IllegalStateException.class, () -> invoke(fixture.owner, "retireFrame"));
                } catch (Throwable caught) { failure.set(caught); }
            });
            other.join();
            check(failure.get() == null && calls == 0 && !(boolean) value(fixture.owner, "frameRetired"));
            check(Arrays.equals(before, fixture.buffers()[0].toArray(ValueLayout.JAVA_BYTE)));
        }
    }

    private static int fakeCall(MemorySegment error, MemorySegment module, MemorySegment path, int capacity) {
        calls++;
        check(module.address() == 0 && capacity == 1024);
        put(path, PATH);
        error.set(ValueLayout.JAVA_INT, 0, 123);
        if (unknown) throw UNKNOWN;
        return PATH.length();
    }

    private static void call(boolean missingReturn) throws Throwable {
        try (Fixture fixture = new Fixture()) {
            fixture.callFrame();
            unknown = missingReturn;
            if (missingReturn) {
                check(expect(LinkageError.class, () -> invoke(fixture.owner, "callOriginalPath")) == UNKNOWN);
                check((boolean) value(fixture.owner, "nativeReturnUnconfirmed"));
                byte[] before = fixture.buffers()[0].toArray(ValueLayout.JAVA_BYTE);
                invoke(fixture.owner, "retireFrame");
                check(!(boolean) value(fixture.owner, "frameRetired") && fixture.frame.scope().isAlive());
                check(Arrays.equals(before, fixture.buffers()[0].toArray(ValueLayout.JAVA_BYTE)));
            } else {
                invoke(fixture.owner, "callOriginalPath");
                check((int) value(fixture.owner, "pathReturn") == PATH.length());
                check(!(boolean) value(fixture.owner, "nativeReturnUnconfirmed"));
            }
            expect(IllegalStateException.class, () -> invoke(fixture.owner, "callOriginalPath"));
            check(calls == 1 && value(fixture.owner, "file") == null);
        }
    }

    private static void retirement(boolean failed) throws Throwable {
        try (Fixture fixture = new Fixture()) {
            fixture.callFrame();
            WindowsOriginalInstallationCandidate.Failure failure =
                (WindowsOriginalInstallationCandidate.Failure) value(fixture.owner, "failure");
            failure.operationFailure = UNKNOWN;
            if (failed) fixture.buffers()[0] = fixture.buffers()[0].asReadOnly();
            invoke(fixture.owner, "retireFrame");
            check((boolean) value(fixture.owner, "frameRetired") && !fixture.frame.scope().isAlive());
            check(fixture.arena.scope().isAlive() && failure.operationFailure == UNKNOWN);
            check((failure.clearFailures[0] != null) == failed && failure.clearFailures[1] == null);
            Throwable retained = failure.clearFailures[0];
            invoke(fixture.owner, "retireFrame");
            check(failure.clearFailures[0] == retained && calls == 0);
            expect(IllegalStateException.class, fixture.owner::originalPathSnapshot);
        }
    }

    private static void roles() throws Throwable {
        try (Fixture fixture = new Fixture()) {
            fixture.file();
            WindowsOriginalFileLease file = fixture.file;
            check(value(file, "originalInstallationOwner") == fixture.owner && value(file, "originalSystemOwner") == null);
            check(!(boolean) invoke(file, "refusedLinkCount", new Class<?>[] {long.class}, 1L));
            for (long count : new long[] {0, 2, -1, 0xffff_ffffL}) {
                check((boolean) invoke(file, "refusedLinkCount", new Class<?>[] {long.class}, count));
            }
            char[] original = fixture.owner.originalPathSnapshot();
            original[3] ^= 1;
            check(!Arrays.equals(original, fixture.owner.originalPathSnapshot()));
            field(file, "originalSystemOwner").set(file, new WindowsOriginalSystemModuleCandidate(null, 0));
            expect(IllegalStateException.class, file::completed);
            field(file, "originalSystemOwner").set(file, null);
            check(file.completed());
        }
    }

    private static void coreSubstitution() throws Throwable {
        try (Fixture fixture = new Fixture(); Fixture other = new Fixture()) {
            fixture.file(); other.file();
            expect(IllegalStateException.class, () -> fixture.owner.requireOriginalFileLease(other.file));
            expect(IllegalStateException.class, () -> fixture.file.newInstallationSecurity(other.owner));
            fixture.security(); other.security();
            expect(IllegalStateException.class, () -> fixture.owner.requireOriginalQuery(other.security));
            expect(IllegalStateException.class, () -> fixture.security.newInstallationAncestors(other.owner));
            fixture.ancestors(); other.ancestors();
            expect(IllegalStateException.class, () -> fixture.owner.requireOriginalAncestors(other.ancestors));
            check(value(fixture.security, "originalInstallationOwner") == fixture.owner);
            check(value(fixture.ancestors, "originalInstallationOwner") == fixture.owner);
            field(fixture.security, "originalSystemOwner").set(fixture.security, new WindowsOriginalSystemModuleCandidate(null, 0));
            expect(IllegalStateException.class, fixture.security::completed);
            field(fixture.security, "originalSystemOwner").set(fixture.security, null);
            field(fixture.ancestors, "originalSystemOwner").set(fixture.ancestors, new WindowsOriginalSystemModuleCandidate(null, 0));
            expect(IllegalStateException.class, fixture.ancestors::completed);
            check(calls == 0);
        }
    }

    private static void policy(String mode) throws Throwable {
        try (Fixture fixture = new Fixture()) {
            fixture.file(); fixture.security();
            if (mode.equals("leaf-refusal")) {
                field(fixture.security, "policyAccepted").set(fixture.security, false);
                field(fixture.owner, "leafPolicyRefused").set(fixture.owner, true);
            } else {
                fixture.ancestors();
                if (mode.equals("ancestor-refusal")) {
                    field(fixture.ancestors, "allPoliciesAccepted").set(fixture.ancestors, false);
                    field(fixture.owner, "ancestorPolicyRefused").set(fixture.owner, true);
                }
            }
            field(fixture.owner, "observationCompleted").set(fixture.owner, true);
            check(fixture.owner.completed());
            check(fixture.owner.custodyAccepted() == mode.equals("accepted-model"));
            check(fixture.owner.retainedDirectoryCount() == (mode.equals("leaf-refusal") ? 0 : 3));
            if (!mode.equals("accepted-model")) {
                expect(IllegalStateException.class, fixture.owner::requireOriginalNativeInputs);
                expect(IllegalStateException.class, fixture.owner::requireOriginalAncestorInputs);
            }
            expect(IllegalStateException.class, fixture.owner::observe);
            check(calls == 0 && value(fixture.bootstrap, "profileDll") == null);
        }
    }

    private static void failureLatch() throws Throwable {
        try (Fixture fixture = new Fixture()) {
            WindowsOriginalInstallationCandidate.Failure retained =
                (WindowsOriginalInstallationCandidate.Failure) value(fixture.owner, "failure");
            retained.operationFailure = UNKNOWN;
            field(fixture.owner, "failed").set(fixture.owner, true);
            check(expect(WindowsOriginalInstallationCandidate.Failure.class, fixture.owner::observe) == retained);
            check(expect(WindowsOriginalInstallationCandidate.Failure.class, fixture.owner::requireOriginalNativeInputs) == retained);
            check(retained.retainedCandidate == fixture.owner && retained.operationFailure == UNKNOWN && calls == 0);
        }
    }

    private static final class Fixture implements AutoCloseable {
        final Arena arena = Arena.ofConfined();
        final WindowsSystemBootstrapCandidate bootstrap;
        final WindowsOriginalInstallationCandidate owner;
        Arena frame;
        WindowsOriginalFileLease file;
        WindowsOriginalFileSecurityQuery security;
        WindowsOriginalFileAncestorsLease ancestors;

        Fixture() throws ReflectiveOperationException {
            calls = 0; unknown = false;
            Constructor<WindowsSystemBootstrapCandidate> constructor =
                WindowsSystemBootstrapCandidate.class.getDeclaredConstructor(Linker.class);
            constructor.setAccessible(true);
            bootstrap = constructor.newInstance((Linker) null);
            field(bootstrap, "succeeded").set(bootstrap, true);
            field(bootstrap, "frameRetired").set(bootstrap, true);
            field(bootstrap, "originalArena").set(bootstrap, arena);
            MemorySegment[] entries = (MemorySegment[]) value(bootstrap, "entries");
            for (int index = 0; index < entries.length; index++) {
                entries[index] = MemorySegment.ofAddress(0x100000L + index * 64).reinterpret(arena, null);
            }
            owner = new WindowsOriginalInstallationCandidate(bootstrap);
            field(bootstrap, "installation").set(bootstrap, owner);
        }

        MemorySegment[] buffers() throws ReflectiveOperationException { return (MemorySegment[]) value(owner, "buffers"); }

        void callFrame() throws ReflectiveOperationException {
            frame = Arena.ofConfined();
            buffers()[0] = frame.allocate(2048, 2);
            buffers()[0].fill((byte) 0x7f);
            buffers()[1] = frame.allocate(4, 4);
            field(owner, "attempted").set(owner, true);
            field(owner, "frameArena").set(owner, frame);
            field(owner, "pathCall").set(owner, MethodHandles.lookup().findStatic(OriginalInstallationCandidateTests.class,
                "fakeCall", MethodType.methodType(int.class, MemorySegment.class, MemorySegment.class, MemorySegment.class, int.class)));
        }

        void file() throws ReflectiveOperationException {
            field(owner, "attempted").set(owner, true);
            field(owner, "pathCallAttempted").set(owner, true);
            field(owner, "errorObserved").set(owner, true);
            field(owner, "frameRetired").set(owner, true);
            field(owner, "originalPath").set(owner, (PATH + '\0').toCharArray());
            field(owner, "originalRoot").set(owner, "C:\\Program Files\\P2pKit Sample\0".toCharArray());
            field(owner, "fileAttempted").set(owner, true);
            file = WindowsOriginalFileLease.forInstallation(owner);
            field(owner, "file").set(owner, file);
            field(owner, "fileObserved").set(owner, true);
            field(file, "succeeded").set(file, true);
            field(file, "frameRetired").set(file, true);
            field(file, "rawHandle").set(file, 0x50000L);
            field(file, "handleArena").set(file, arena);
            field(file, "handle").set(file, MemorySegment.ofAddress(0x50000L).reinterpret(arena, null));
        }

        void security() throws ReflectiveOperationException {
            field(owner, "securityAttempted").set(owner, true);
            security = file.newInstallationSecurity(owner);
            field(owner, "security").set(owner, security);
            field(owner, "securityObserved").set(owner, true);
            for (String name : new String[] {"succeeded", "frameRetired", "ntReturned", "policyEvaluated", "policyAccepted"}) {
                field(security, name).set(security, true);
            }
            field(security, "exactDescriptor").set(security, new byte[20]);
            field(security, "moduleArena").set(security, arena);
            MemorySegment entry = MemorySegment.ofAddress(0x200000L).reinterpret(arena, null);
            field(security, "entry").set(security, entry);
            field(security, "module").set(security, entry);
        }

        void ancestors() throws ReflectiveOperationException {
            field(owner, "ancestorsAttempted").set(owner, true);
            ancestors = security.newInstallationAncestors(owner);
            field(owner, "ancestors").set(owner, ancestors);
            field(owner, "ancestorsObserved").set(owner, true);
            field(ancestors, "succeeded").set(ancestors, true);
            field(ancestors, "frameRetired").set(ancestors, true);
            field(ancestors, "componentCount").set(ancestors, 3);
            field(ancestors, "directoryCount").set(ancestors, 3);
            field(ancestors, "openedCount").set(ancestors, 4);
            field(ancestors, "leaseArena").set(ancestors, arena);
        }

        @Override public void close() {
            // Only this inert fixture owns these arenas; no native operation or actual handle exists.
            if (frame != null && frame.scope().isAlive()) frame.close();
            arena.close();
        }
    }
}
