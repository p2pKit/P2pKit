package dev.p2pkit.rpc.windows.loader;

import java.lang.foreign.Arena;
import java.lang.foreign.MemorySegment;
import java.lang.foreign.ValueLayout;
import java.lang.reflect.Field;
import java.lang.reflect.InvocationTargetException;
import java.lang.reflect.Method;
import java.util.Arrays;
import java.util.HexFormat;
import java.util.concurrent.atomic.AtomicReference;

/** Inert owner/data/frame controls, not native ancestor acquisition or filesystem custody evidence. */
public final class OriginalFileAncestorsLeaseTests {
    private OriginalFileAncestorsLeaseTests() {}

    public static void main(String[] arguments) throws Throwable {
        check(arguments.length == 1);
        WindowsLoaderRuntime.requireDiagnosticRuntime();
        String mode = arguments[0];
        switch (mode) {
            case "owner-refusal" -> ownerRefusal();
            case "substitution" -> substitution();
            case "path-bounds" -> pathBounds();
            case "path-copy" -> pathCopy();
            case "descriptor-bounds" -> descriptorBounds();
            case "descriptor-policy" -> descriptorPolicy();
            case "retirement" -> retirement(false, false);
            case "retirement-failures" -> retirement(true, false);
            case "retirement-unknown" -> retirement(false, true);
            case "thread" -> wrongThread();
            default -> throw new AssertionError("Unknown original ancestor lease control");
        }
        System.out.println("WINDOWS_ORIGINAL_FILE_ANCESTORS_PASS case=" + mode +
            " scope=INERT_OWNER_PATH_DESCRIPTOR_AND_FRAME_NOT_NATIVE_CUSTODY_OR_AUTHORITY");
    }

    private static WindowsOriginalJvmAncestorsCandidate facade(char[] path, int length, long[] metadata) {
        return new WindowsOriginalJvmAncestorsCandidate(null, null, null, null, null, null, null, null,
            null, null, null, null, null, null, null, path, length, metadata);
    }

    private static WindowsOriginalFileAncestorsLease core(String path) throws ReflectiveOperationException {
        return core(facade((path + '\0').toCharArray(), path.length(), new long[] {1, 2, 3, 4096, 512, 1, 0, 0}));
    }

    private static WindowsOriginalFileAncestorsLease core(WindowsOriginalJvmAncestorsCandidate owner)
        throws ReflectiveOperationException { return (WindowsOriginalFileAncestorsLease) value(owner, "core"); }

    private static void ownerRefusal() throws Throwable {
        WindowsOriginalJvmAncestorsCandidate owner = facade(new char[4], 3, new long[8]);
        WindowsOriginalFileAncestorsLease core = core(owner);
        check(value(core, "originalJvmOwner") == owner && value(core, "originalProfileDllOwner") == null);
        WindowsOriginalFileAncestorsLease.Failure failure = failure(core);
        check(failure.retainedCandidate == core && failure.clearFailures.length == 20 && failure.operationFailure == null);
        check(failure.getStackTrace().length == 0 && failure.getSuppressed().length == 0);
        expect(IllegalStateException.class, owner::observe);
        expect(IllegalStateException.class, owner::completed);
        expect(IllegalStateException.class, owner::ancestorCount);
        expect(IllegalStateException.class, owner::descriptorPoliciesAccepted);
        check(!(boolean) value(core, "attempted") && value(core, "frameArena") == null && value(core, "leaseArena") == null);
    }

    private static void substitution() throws Throwable {
        WindowsOriginalJvmAncestorsCandidate owner = facade(new char[4], 3, new long[8]);
        WindowsOriginalFileAncestorsLease original = core(owner);
        WindowsOriginalFileAncestorsLease other = new WindowsOriginalFileAncestorsLease(owner, null, null,
            null, null, null, null, null, null, null, null, null, null, null, null, new char[4], 3, new long[8]);
        expect(IllegalStateException.class, () -> owner.requireOriginalCore(other));
        expect(IllegalStateException.class, other::observe);
        check(core(owner) == original && !(boolean) value(other, "attempted") && value(other, "frameArena") == null);
    }

    private static void pathBounds() throws Throwable {
        for (String path : new String[] {"C:\\jvm.dll", "C:\\\\x\\jvm.dll", "C:\\a.\\jvm.dll", "C:\\a \\jvm.dll",
            "C:\\a/b\\jvm.dll", "C:\\a:b\\jvm.dll", "C:\\a?b\\jvm.dll", "C:\\a\u007f\\jvm.dll",
            "C:\\" + "x".repeat(256) + "\\jvm.dll", "C:\\" + "a\\".repeat(63) + "jvm.dll"}) {
            WindowsOriginalFileAncestorsLease core = core(path);
            expect(IllegalStateException.class, () -> invoke(core, "validateComponents"));
            check(value(core, "frameArena") == null && !(boolean) value(core, "attempted"));
        }
        for (String path : new String[] {"C:\\a\\jvm.dll", "C:\\" + "a\\".repeat(62) + "jvm.dll"}) {
            WindowsOriginalFileAncestorsLease core = core(path);
            invoke(core, "validateComponents");
            check((int) value(core, "componentCount") >= 2 && (int) value(core, "componentCount") <= 63);
            expect(IllegalStateException.class, core::completed);
        }
    }

    private static void pathCopy() throws Throwable {
        char[] path = "C:\\fixture\\jvm.dll\0".toCharArray();
        long[] metadata = {1, 2, 3, 4096, 512, 1, 0, 0};
        char[] expectedPath = path.clone();
        long[] expectedMetadata = metadata.clone();
        WindowsOriginalFileAncestorsLease core = core(facade(path, path.length - 1, metadata));
        Arrays.fill(path, 'x');
        Arrays.fill(metadata, 99);
        check(Arrays.equals((char[]) value(core, "originalPath"), expectedPath));
        check(Arrays.equals((long[]) value(core, "originalFile"), expectedMetadata));
        invoke(core, "validateComponents");
        check((int) value(core, "componentCount") == 2 && value(core, "frameArena") == null);
    }

    private static void descriptorBounds() throws Throwable {
        for (int status : new int[] {1, 0x103, 0x80000005, 0xc0000023, -1}) {
            WindowsOriginalFileAncestorsLease core = core("C:\\fixture\\jvm.dll");
            ((int[]) value(core, "queryStatuses"))[0] = status;
            ((int[]) value(core, "descriptorLengths"))[0] = 40;
            expect(IllegalStateException.class, () -> preserve(core, WindowsInstallationSecurity.Kind.VOLUME_ROOT));
            check(((byte[][]) value(core, "descriptors"))[0] == null);
        }
        for (int length : new int[] {-1, Integer.MIN_VALUE, 0, 19, 65_537, Integer.MAX_VALUE}) {
            WindowsOriginalFileAncestorsLease core = core("C:\\fixture\\jvm.dll");
            ((int[]) value(core, "descriptorLengths"))[0] = length;
            expect(IllegalStateException.class, () -> preserve(core, WindowsInstallationSecurity.Kind.DIRECTORY));
            check(((byte[][]) value(core, "descriptors"))[0] == null);
        }
        for (int length : new int[] {20, 65_536}) {
            WindowsOriginalFileAncestorsLease core = core("C:\\fixture\\jvm.dll");
            try (Arena frame = Arena.ofConfined()) {
                ((MemorySegment[]) value(core, "buffers"))[7] = frame.allocate(65_536, 4);
                ((int[]) value(core, "descriptorLengths"))[0] = length;
                preserve(core, WindowsInstallationSecurity.Kind.DIRECTORY);
                check(((byte[][]) value(core, "descriptors"))[0].length == length);
                check(!((boolean[]) value(core, "policies"))[0] && !(boolean) value(core, "allPoliciesAccepted"));
            }
        }
    }

    private static void descriptorPolicy() throws Throwable {
        byte[] safe = HexFormat.of().parseHex(
            "01000480140000000000000000000000200000000101000000000005120000000200080000000000");
        for (WindowsInstallationSecurity.Kind kind : new WindowsInstallationSecurity.Kind[] {
            WindowsInstallationSecurity.Kind.VOLUME_ROOT, WindowsInstallationSecurity.Kind.DIRECTORY}) {
            WindowsInstallationSecurity.require(safe, kind);
            for (boolean accepted : new boolean[] {true, false}) {
                WindowsOriginalFileAncestorsLease core = core("C:\\fixture\\jvm.dll");
                byte[] source = safe.clone();
                if (!accepted) source[28] = 19;
                byte[] expected = source.clone();
                try (Arena frame = Arena.ofConfined()) {
                    MemorySegment buffer = frame.allocate(65_536, 4);
                    MemorySegment.copy(source, 0, buffer, ValueLayout.JAVA_BYTE, 0, source.length);
                    ((MemorySegment[]) value(core, "buffers"))[7] = buffer;
                    ((int[]) value(core, "descriptorLengths"))[0] = source.length;
                    preserve(core, kind);
                    byte[] descriptor = ((byte[][]) value(core, "descriptors"))[0];
                    check(descriptor != source && Arrays.equals(descriptor, expected));
                    check(((boolean[]) value(core, "policies"))[0] == accepted);
                    check((boolean) value(core, "allPoliciesAccepted") == accepted);
                    buffer.fill((byte) 0);
                    Arrays.fill(source, (byte) 0);
                    check(Arrays.equals(descriptor, expected));
                    expect(IllegalStateException.class, core::descriptorPoliciesAccepted);
                }
            }
        }
    }

    private static void preserve(WindowsOriginalFileAncestorsLease core, WindowsInstallationSecurity.Kind kind)
        throws Throwable {
        invoke(core, "preserveDescriptor", new Class<?>[] {int.class, WindowsInstallationSecurity.Kind.class}, 0, kind);
    }

    private static void retirement(boolean fail, boolean unknown) throws Throwable {
        WindowsOriginalFileAncestorsLease core = core("C:\\fixture\\jvm.dll");
        WindowsOriginalFileAncestorsLease.Failure failure = failure(core);
        Throwable operation = new LinkageError("inert ancestor original failure");
        failure.operationFailure = operation;
        try (Arena backing = Arena.ofConfined(); Arena original = Arena.ofConfined()) {
            Arena frame = Arena.ofConfined();
            try {
                MemorySegment first = backing.allocate(16);
                MemorySegment second = backing.allocate(16);
                first.fill((byte) 0x5a);
                second.fill((byte) 0x5b);
                MemorySegment[] buffers = (MemorySegment[]) value(core, "buffers");
                buffers[0] = fail ? first.asReadOnly() : first.reinterpret(frame, null);
                buffers[1] = fail ? second : second.reinterpret(frame, null);
                field(core, "frameArena").set(core, frame);
                field(core, "leaseArena").set(core, original);
                field(core, "nativeReturnUnconfirmed").setBoolean(core, unknown);
                if (fail) { buffers[2] = frame.allocate(8); frame.close(); }
                invoke(core, "retireFrame");
                invoke(core, "retireFrame");
                check((boolean) value(core, "frameRetired") == !unknown);
                check(frame.scope().isAlive() == unknown && original.scope().isAlive());
                check(first.get(ValueLayout.JAVA_BYTE, 0) == (fail || unknown ? (byte) 0x5a : 0));
                check(second.get(ValueLayout.JAVA_BYTE, 0) == (unknown ? (byte) 0x5b : 0));
                check((failure.clearFailures[0] != null) == fail && (failure.clearFailures[2] != null) == fail);
                check((failure.arenaCloseFailure != null) == fail);
                check(failure.retainedCandidate == core && failure.operationFailure == operation);
                check(value(core, "failure") == failure && value(core, "leaseArena") == original);
            } finally {
                if (frame.scope().isAlive()) frame.close(); // Inert memory only; never an actual pending OS frame.
            }
        }
    }

    private static void wrongThread() throws Throwable {
        WindowsOriginalFileAncestorsLease core = core("C:\\fixture\\jvm.dll");
        AtomicReference<Throwable> unexpected = new AtomicReference<>();
        Thread worker = Thread.startVirtualThread(() -> {
            try {
                expect(IllegalStateException.class, core::observe);
                expect(IllegalStateException.class, core::completed);
                expect(IllegalStateException.class, () -> invoke(core, "retireFrame"));
            } catch (Throwable caught) { unexpected.set(caught); }
        });
        worker.join();
        check(unexpected.get() == null && !(boolean) value(core, "attempted") && !(boolean) value(core, "frameRetired"));
    }

    private static WindowsOriginalFileAncestorsLease.Failure failure(WindowsOriginalFileAncestorsLease core)
        throws ReflectiveOperationException { return (WindowsOriginalFileAncestorsLease.Failure) value(core, "failure"); }
    private static Field field(Object owner, String name) throws ReflectiveOperationException {
        Field field = owner.getClass().getDeclaredField(name);
        field.setAccessible(true);
        return field;
    }
    private static Object value(Object owner, String name) throws ReflectiveOperationException { return field(owner, name).get(owner); }
    private static Object invoke(Object owner, String name) throws Throwable { return invoke(owner, name, new Class<?>[0]); }
    private static Object invoke(Object owner, String name, Class<?>[] types, Object... arguments) throws Throwable {
        Method method = owner.getClass().getDeclaredMethod(name, types);
        method.setAccessible(true);
        try { return method.invoke(owner, arguments); }
        catch (InvocationTargetException failure) { throw failure.getCause(); }
    }
    private interface Action { void run() throws Throwable; }
    private static Throwable expect(Class<? extends Throwable> type, Action action) {
        try { action.run(); }
        catch (Throwable caught) {
            if (type.isInstance(caught)) return caught;
            throw new AssertionError("Unexpected original ancestor control failure", caught);
        }
        throw new AssertionError("Expected original ancestor refusal");
    }
    private static void check(boolean condition) {
        if (!condition) throw new AssertionError("Original ancestor lease control failed");
    }
}
