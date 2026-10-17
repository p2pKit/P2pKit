package dev.p2pkit.rpc.windows.loader;

import java.lang.foreign.Arena;
import java.lang.foreign.MemorySegment;
import java.lang.foreign.ValueLayout;
import java.lang.reflect.Field;
import java.lang.reflect.InvocationTargetException;
import java.lang.reflect.Method;
import java.util.Arrays;
import java.util.concurrent.atomic.AtomicReference;

/** Private original-owner/frame controls only; no Windows file, system entry or native I/O is supplied. */
public final class OriginalFileLeaseTests {
    private OriginalFileLeaseTests() {}

    public static void main(String[] arguments) throws Throwable {
        check(arguments.length == 1);
        WindowsLoaderRuntime.requireDiagnosticRuntime();
        String mode = arguments[0];
        switch (mode) {
            case "owner-refusal" -> ownerRefusal();
            case "substitution" -> substitution();
            case "snapshot" -> snapshot();
            case "retirement" -> retirement(false);
            case "retirement-failures" -> retirement(true);
            case "retirement-unknown" -> retirementUnknown();
            case "thread" -> wrongThread();
            default -> throw new AssertionError("Unknown original file lease control");
        }
        System.out.println("WINDOWS_ORIGINAL_FILE_LEASE_PASS case=" + mode +
            " scope=INERT_ORIGINAL_OWNER_AND_FRAME_NOT_FILE_CUSTODY_OR_AUTHORITY");
    }

    private static WindowsOriginalJvmFileCandidate facade(char[] path) {
        return new WindowsOriginalJvmFileCandidate(null, null, null, null, null, null,
            path, path == null ? 0 : path.length - 1);
    }

    private static WindowsOriginalFileLease core(WindowsOriginalJvmFileCandidate owner)
        throws ReflectiveOperationException {
        Field field = WindowsOriginalJvmFileCandidate.class.getDeclaredField("lease");
        field.setAccessible(true); // Test-patched original module only; no packaged inspection API.
        return (WindowsOriginalFileLease) field.get(owner);
    }

    private static void ownerRefusal() throws Throwable {
        WindowsOriginalFileLease missing = new WindowsOriginalFileLease(null);
        expect(IllegalStateException.class, missing::observe);
        unattempted(missing);
        WindowsOriginalJvmFileCandidate facade = facade(null);
        WindowsOriginalFileLease retained = core(facade);
        check(value(retained, "originalOwner") == facade);
        WindowsOriginalFileLease.Failure failure = (WindowsOriginalFileLease.Failure) value(retained, "failure");
        check(failure.retainedCandidate == retained && failure.operationFailure == null);
        check(failure.clearFailures.length == 6 && failure.arenaCloseFailure == null);
        check(failure.getStackTrace().length == 0 && failure.getSuppressed().length == 0);
        expect(IllegalStateException.class, facade::observe);
        expect(IllegalStateException.class, facade::completed);
        expect(IllegalStateException.class, facade::leaseHeld);
        expect(IllegalStateException.class, facade::inspectBytes);
        expect(IllegalStateException.class, facade::inspectSecurity);
        unattempted(retained);
        check(value(retained, "failure") == failure && failure.retainedCandidate == retained);
    }

    private static void substitution() throws Throwable {
        WindowsOriginalJvmFileCandidate facade = facade(null);
        WindowsOriginalFileLease retained = core(facade);
        WindowsOriginalFileLease substitute = new WindowsOriginalFileLease(facade);
        Throwable refused = expect(IllegalStateException.class, () -> facade.requireOriginalLease(substitute));
        check(refused.getMessage().equals("File lease is not this JVM facade's original retained attachment"));
        expect(IllegalStateException.class, substitute::observe);
        expect(IllegalStateException.class, () -> facade.originalReadEntry(substitute));
        expect(IllegalStateException.class, () -> facade.originalSecurityEntry(substitute, 0));
        expect(IllegalStateException.class, () -> facade.originalAncestorsEntry(substitute, 0));
        WindowsOriginalJvmFileCandidate other = facade(null);
        expect(IllegalStateException.class, () -> retained.newJvmBytes(other));
        expect(IllegalStateException.class, () -> retained.newJvmSecurity(other));
        expect(IllegalStateException.class,
            () -> retained.newJvmAncestors(other, null, null, null, null, null, null));
        check(core(facade) == retained && value(substitute, "originalOwner") == facade);
        unattempted(retained);
        unattempted(substitute);
        unattempted(core(other));
    }

    private static void snapshot() throws Throwable {
        char[] source = "C:\\fixture\\jvm.dll\0".toCharArray();
        char[] expected = source.clone();
        WindowsOriginalJvmFileCandidate facade = facade(source);
        WindowsOriginalFileLease retained = core(facade);
        char[] snapshot = (char[]) value(retained, "sourcePath");
        check(snapshot != source && Arrays.equals(snapshot, expected));
        source[3] ^= 1;
        check(Arrays.equals(snapshot, expected));
        check((int) value(retained, "sourceLength") == expected.length - 1);
        expect(IllegalStateException.class, retained::observe); // A pathname copy is not original owner admission.
        unattempted(retained);
    }

    private static void retirement(boolean failed) throws Throwable {
        WindowsOriginalJvmFileCandidate facade = facade(null);
        WindowsOriginalFileLease retained = core(facade);
        WindowsOriginalFileLease.Failure failure = (WindowsOriginalFileLease.Failure) value(retained, "failure");
        Throwable operation = new LinkageError("inert original file operation failure");
        failure.operationFailure = operation;
        try (Arena backing = Arena.ofConfined(); Arena original = Arena.ofConfined()) {
            Arena frame = Arena.ofConfined();
            try {
                MemorySegment first = backing.allocate(16);
                MemorySegment second = backing.allocate(16);
                first.fill((byte) 0x5a);
                second.fill((byte) 0x5b);
                MemorySegment[] buffers = (MemorySegment[]) value(retained, "buffers");
                buffers[0] = failed ? first.asReadOnly() : first.reinterpret(frame, null);
                buffers[1] = failed ? second : second.reinterpret(frame, null);
                field("frameArena").set(retained, frame);
                field("handleArena").set(retained, original);
                if (failed) {
                    buffers[2] = frame.allocate(8);
                    frame.close(); // Native I/O never occurred; force independent clear AND close failures.
                }
                retire(retained);
                check((boolean) value(retained, "frameRetired") && !frame.scope().isAlive());
                check(original.scope().isAlive() && backing.scope().isAlive());
                check(failure.retainedCandidate == retained && value(retained, "originalOwner") == facade);
                check(failure.operationFailure == operation && failure.clearFailures[1] == null);
                check((failure.clearFailures[0] != null) == failed &&
                    (failure.clearFailures[2] != null) == failed && (failure.arenaCloseFailure != null) == failed);
                for (byte actual : first.toArray(ValueLayout.JAVA_BYTE)) check(actual == (failed ? 0x5a : 0));
                for (byte actual : second.toArray(ValueLayout.JAVA_BYTE)) check(actual == 0);
                Throwable[] firstFailures = failure.clearFailures.clone();
                Throwable closeFailure = failure.arenaCloseFailure;
                retire(retained);
                check(Arrays.equals(firstFailures, failure.clearFailures) && failure.arenaCloseFailure == closeFailure);
                check(failure.operationFailure == operation && original.scope().isAlive());
                expect(IllegalStateException.class, retained::completed);
            } finally {
                // Only this inert test owns the arenas; no real or uncertain kernel operation exists.
                if (frame.scope().isAlive()) frame.close();
            }
        }
    }

    private static void retirementUnknown() throws Throwable {
        WindowsOriginalJvmFileCandidate facade = facade(null);
        WindowsOriginalFileLease retained = core(facade);
        WindowsOriginalFileLease.Failure failure = (WindowsOriginalFileLease.Failure) value(retained, "failure");
        Throwable operation = new LinkageError("inert original file return uncertainty");
        failure.operationFailure = operation;
        try (Arena backing = Arena.ofConfined(); Arena original = Arena.ofConfined()) {
            Arena frame = Arena.ofConfined();
            try {
                MemorySegment storage = backing.allocate(32);
                storage.fill((byte) 0x5a);
                MemorySegment view = storage.reinterpret(frame, null);
                ((MemorySegment[]) value(retained, "buffers"))[0] = view;
                field("frameArena").set(retained, frame);
                field("handleArena").set(retained, original);
                field("nativeReturnUnconfirmed").setBoolean(retained, true);
                retire(retained);
                retire(retained);
                check(!(boolean) value(retained, "frameRetired") &&
                    (boolean) value(retained, "nativeReturnUnconfirmed") && frame.scope().isAlive());
                check(original.scope().isAlive() && view.scope().isAlive() && backing.scope().isAlive());
                for (byte actual : storage.toArray(ValueLayout.JAVA_BYTE)) check(actual == 0x5a);
                for (Throwable clear : failure.clearFailures) check(clear == null);
                check(failure.operationFailure == operation && failure.arenaCloseFailure == null &&
                    failure.retainedCandidate == retained && value(retained, "originalOwner") == facade);
            } finally {
                // This fixture alone owns inert memory. No native call or pending OS I/O occurred.
                if (frame.scope().isAlive()) frame.close();
            }
        }
    }

    private static void wrongThread() throws Throwable {
        WindowsOriginalJvmFileCandidate facade = facade(null);
        WindowsOriginalFileLease retained = core(facade);
        AtomicReference<Throwable> failed = new AtomicReference<>();
        Thread worker = new Thread(() -> {
            try {
                expect(IllegalStateException.class, retained::observe);
                expect(IllegalStateException.class, retained::completed);
                expect(IllegalStateException.class, retained::leaseHeld);
                expect(IllegalStateException.class, () -> facade.requireOriginalLease(retained));
                expect(IllegalStateException.class, () -> retained.newJvmBytes(facade));
                expect(IllegalStateException.class, () -> retained.newJvmSecurity(facade));
            } catch (Throwable caught) { failed.set(caught); }
        }, "original-file-lease-wrong-thread");
        worker.start();
        worker.join(5000);
        check(!worker.isAlive());
        if (failed.get() != null) throw new AssertionError(failed.get());
        unattempted(retained);
    }

    private static void unattempted(WindowsOriginalFileLease retained) throws ReflectiveOperationException {
        check(!(boolean) value(retained, "attempted") && !(boolean) value(retained, "frameRetired") &&
            !(boolean) value(retained, "succeeded") && (long) value(retained, "rawHandle") == 0);
        for (String name : new String[] {
            "frameArena", "handleArena", "createCall", "informationCall", "finalPathCall"
        }) {
            check(value(retained, name) == null);
        }
        for (MemorySegment buffer : (MemorySegment[]) value(retained, "buffers")) check(buffer == null);
    }

    private static Field field(String name) throws ReflectiveOperationException {
        Field field = WindowsOriginalFileLease.class.getDeclaredField(name);
        field.setAccessible(true);
        return field;
    }
    private static Object value(WindowsOriginalFileLease retained, String name) throws ReflectiveOperationException {
        return field(name).get(retained);
    }
    private static void retire(WindowsOriginalFileLease retained) throws Throwable {
        Method method = WindowsOriginalFileLease.class.getDeclaredMethod("retireFrame");
        method.setAccessible(true);
        try { method.invoke(retained); }
        catch (InvocationTargetException failure) { throw failure.getCause(); }
    }
    private interface Action { void run() throws Throwable; }
    private static Throwable expect(Class<? extends Throwable> type, Action action) {
        try { action.run(); }
        catch (Throwable caught) {
            if (type.isInstance(caught)) return caught;
            throw new AssertionError("Unexpected original file lease control failure", caught);
        }
        throw new AssertionError("Expected original file lease refusal");
    }
    private static void check(boolean value) {
        if (!value) throw new AssertionError("Original file lease control failed");
    }
}
