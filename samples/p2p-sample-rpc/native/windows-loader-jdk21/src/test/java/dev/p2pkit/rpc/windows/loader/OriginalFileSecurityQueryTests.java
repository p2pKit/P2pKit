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

/** Inert shared-query owner, descriptor and retirement controls; never native security or custody proof. */
public final class OriginalFileSecurityQueryTests {
    private OriginalFileSecurityQueryTests() {}

    public static void main(String[] arguments) throws Throwable {
        check(arguments.length == 1);
        WindowsLoaderRuntime.requireDiagnosticRuntime();
        String mode = arguments[0];
        switch (mode) {
            case "owner-refusal" -> ownerRefusal();
            case "substitution" -> substitution();
            case "descriptor-bounds" -> descriptorBounds();
            case "descriptor-policy" -> descriptorPolicy();
            case "retirement" -> retirement(false, false);
            case "retirement-failures" -> retirement(true, false);
            case "retirement-unknown" -> retirement(false, true);
            case "thread" -> wrongThread();
            default -> throw new AssertionError("Unknown original security query control");
        }
        System.out.println("WINDOWS_ORIGINAL_FILE_SECURITY_PASS case=" + mode +
            " scope=INERT_OWNER_DESCRIPTOR_AND_FRAME_NOT_NATIVE_CUSTODY_OR_AUTHORITY");
    }

    private static WindowsOriginalJvmSecurityCandidate facade(Arena original) {
        return new WindowsOriginalJvmSecurityCandidate(null, null, null, original, null, null, null, null, null);
    }

    private static WindowsOriginalFileSecurityQuery query(WindowsOriginalJvmSecurityCandidate owner)
        throws ReflectiveOperationException {
        return (WindowsOriginalFileSecurityQuery) value(owner, "query");
    }

    private static void ownerRefusal() throws Throwable {
        WindowsOriginalJvmSecurityCandidate facade = facade(null);
        WindowsOriginalFileSecurityQuery core = query(facade);
        check(value(core, "originalJvmOwner") == facade && value(core, "originalProfileDllOwner") == null);
        WindowsOriginalFileSecurityQuery.Failure failure = failure(core);
        check(failure.retainedCandidate == core && failure.operationFailure == null && failure.clearFailures.length == 8);
        check(failure.getStackTrace().length == 0 && failure.getSuppressed().length == 0);
        expect(IllegalStateException.class, facade::observe);
        expect(IllegalStateException.class, facade::completed);
        expect(IllegalStateException.class, facade::descriptorPolicyAccepted);
        expect(IllegalStateException.class, facade::inspectAncestors);
        check(!(boolean) value(core, "attempted") && value(core, "frameArena") == null);
        check(value(core, "failure") == failure && failure.operationFailure == null);
    }

    private static void substitution() throws Throwable {
        WindowsOriginalJvmSecurityCandidate owner = facade(null);
        WindowsOriginalFileSecurityQuery original = query(owner);
        WindowsOriginalFileSecurityQuery substitute =
            new WindowsOriginalFileSecurityQuery(owner, null, null, null, null, null, null, null, null);
        expect(IllegalStateException.class, () -> owner.requireOriginalQuery(substitute));
        expect(IllegalStateException.class, substitute::observe);
        expect(IllegalStateException.class, () -> original.newJvmAncestors(facade(null)));
        expect(IllegalStateException.class, () -> original.newJvmAncestors(null));
        check(query(owner) == original && !(boolean) value(substitute, "attempted"));
        check(value(original, "frameArena") == null && value(substitute, "frameArena") == null);
    }

    private static void descriptorBounds() throws Throwable {
        for (int status : new int[] {1, 0x103, 0x80000005, 0xc0000023, -1}) {
            WindowsOriginalFileSecurityQuery core = query(facade(null));
            field(core, "ntStatus").setInt(core, status);
            field(core, "requiredLength").setInt(core, 40);
            expect(IllegalStateException.class, () -> invoke(core, "preserveDescriptor"));
            check(value(core, "exactDescriptor") == null && !(boolean) value(core, "policyEvaluated"));
        }
        for (int length : new int[] {Integer.MIN_VALUE, -1, 0, 19, 65_537, Integer.MAX_VALUE}) {
            WindowsOriginalFileSecurityQuery core = query(facade(null));
            field(core, "requiredLength").setInt(core, length);
            expect(IllegalStateException.class, () -> invoke(core, "preserveDescriptor"));
            check(value(core, "exactDescriptor") == null && !(boolean) value(core, "policyEvaluated"));
        }
        for (int length : new int[] {20, 65_536}) {
            WindowsOriginalFileSecurityQuery core = query(facade(null));
            try (Arena frame = Arena.ofConfined()) {
                ((MemorySegment[]) value(core, "buffers"))[6] = frame.allocate(65_536, 4);
                field(core, "requiredLength").setInt(core, length);
                invoke(core, "preserveDescriptor");
                check(((byte[]) value(core, "exactDescriptor")).length == length);
                check((boolean) value(core, "policyEvaluated") && !(boolean) value(core, "policyAccepted"));
                expect(IllegalStateException.class, core::completed); // Private inert data is not an original query.
            }
        }
    }

    private static void descriptorPolicy() throws Throwable {
        // SYSTEM owner, self-relative OWNER|DACL, empty deny-all ACL; no SACL or grants.
        byte[] safe = HexFormat.of().parseHex(
            "01000480140000000000000000000000200000000101000000000005120000000200080000000000");
        WindowsInstallationSecurity.require(safe, WindowsInstallationSecurity.Kind.FILE);
        for (boolean accepted : new boolean[] {true, false}) {
            WindowsOriginalFileSecurityQuery core = query(facade(null));
            byte[] source = safe.clone();
            if (!accepted) source[28] = 19; // Untrusted owner, still a complete bounded native-shaped descriptor.
            byte[] expected = source.clone();
            try (Arena frame = Arena.ofConfined()) {
                MemorySegment buffer = frame.allocate(65_536, 4);
                MemorySegment.copy(source, 0, buffer, ValueLayout.JAVA_BYTE, 0, source.length);
                ((MemorySegment[]) value(core, "buffers"))[6] = buffer;
                field(core, "requiredLength").setInt(core, source.length);
                invoke(core, "preserveDescriptor");
                byte[] exact = (byte[]) value(core, "exactDescriptor");
                byte[] preserved = (byte[]) value(core, "preservedDescriptor");
                check(exact != source && exact != preserved && Arrays.equals(exact, expected));
                check(preserved.length == 65_536 && (boolean) value(core, "policyEvaluated"));
                check((boolean) value(core, "policyAccepted") == accepted && (int) value(core, "phase") == 6);
                source[0] = 0;
                buffer.fill((byte) 0);
                check(Arrays.equals(exact, expected) && failure(core).operationFailure == null);
                expect(IllegalStateException.class, core::descriptorPolicyAccepted);
            }
        }
    }

    private static void retirement(boolean fail, boolean unknown) throws Throwable {
        try (Arena original = Arena.ofConfined(); Arena backing = Arena.ofConfined(); Arena module = Arena.ofConfined()) {
            WindowsOriginalJvmSecurityCandidate facade = facade(original);
            WindowsOriginalFileSecurityQuery core = query(facade);
            WindowsOriginalFileSecurityQuery.Failure failure = failure(core);
            Throwable operation = new LinkageError("inert security original failure");
            failure.operationFailure = operation;
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
                field(core, "moduleArena").set(core, module);
                field(core, "nativeReturnUnconfirmed").setBoolean(core, unknown);
                if (fail) {
                    buffers[2] = frame.allocate(8);
                    frame.close();
                }
                invoke(core, "retireFrame");
                check((boolean) value(core, "frameRetired") == !unknown && frame.scope().isAlive() == unknown);
                check(original.scope().isAlive() && module.scope().isAlive() && backing.scope().isAlive());
                check(value(core, "fileArena") == original && failure.retainedCandidate == core);
                check(value(core, "originalJvmOwner") == facade && failure.operationFailure == operation);
                for (byte value : first.toArray(ValueLayout.JAVA_BYTE)) check(value == (fail || unknown ? 0x5a : 0));
                for (byte value : second.toArray(ValueLayout.JAVA_BYTE)) check(value == (unknown ? 0x5b : 0));
                check((failure.clearFailures[0] != null) == fail && (failure.clearFailures[2] != null) == fail);
                check((failure.arenaCloseFailure != null) == fail && failure.clearFailures[1] == null);
                Throwable[] errors = failure.clearFailures.clone();
                Throwable closeFailure = failure.arenaCloseFailure;
                invoke(core, "retireFrame");
                check(Arrays.equals(errors, failure.clearFailures) && closeFailure == failure.arenaCloseFailure);
                check(failure.operationFailure == operation && (boolean) value(core, "nativeReturnUnconfirmed") == unknown);
                expect(IllegalStateException.class, core::completed);
            } finally {
                if (frame.scope().isAlive()) frame.close(); // Inert test ownership only; no native call was made.
            }
        }
    }

    private static void wrongThread() throws Throwable {
        WindowsOriginalJvmSecurityCandidate facade = facade(null);
        WindowsOriginalFileSecurityQuery core = query(facade);
        AtomicReference<Throwable> unexpected = new AtomicReference<>();
        Thread worker = Thread.startVirtualThread(() -> {
            try {
                expect(IllegalStateException.class, core::observe);
                expect(IllegalStateException.class, facade::completed);
                expect(IllegalStateException.class, facade::inspectAncestors);
            } catch (Throwable caught) { unexpected.set(caught); }
        });
        worker.join();
        check(unexpected.get() == null && !(boolean) value(core, "attempted") && value(core, "frameArena") == null);
    }

    private static WindowsOriginalFileSecurityQuery.Failure failure(WindowsOriginalFileSecurityQuery core)
        throws ReflectiveOperationException {
        return (WindowsOriginalFileSecurityQuery.Failure) value(core, "failure");
    }
    private static Field field(Object owner, String name) throws ReflectiveOperationException {
        Field field = owner.getClass().getDeclaredField(name);
        field.setAccessible(true);
        return field;
    }
    private static Object value(Object owner, String name) throws ReflectiveOperationException {
        return field(owner, name).get(owner);
    }
    private static void invoke(Object owner, String name) throws Throwable {
        Method method = owner.getClass().getDeclaredMethod(name);
        method.setAccessible(true);
        try { method.invoke(owner); }
        catch (InvocationTargetException failure) { throw failure.getCause(); }
    }
    private interface Action { void run() throws Throwable; }
    private static Throwable expect(Class<? extends Throwable> type, Action action) {
        try { action.run(); }
        catch (Throwable caught) {
            if (type.isInstance(caught)) return caught;
            throw new AssertionError("Unexpected security query control failure", caught);
        }
        throw new AssertionError("Expected security query refusal");
    }
    private static void check(boolean condition) {
        if (!condition) throw new AssertionError("Original file security query control failed");
    }
}
