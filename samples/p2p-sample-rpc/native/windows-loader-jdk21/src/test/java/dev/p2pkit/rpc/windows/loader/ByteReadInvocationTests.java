package dev.p2pkit.rpc.windows.loader;

import java.lang.foreign.Arena;
import java.lang.foreign.FunctionDescriptor;
import java.lang.foreign.Linker;
import java.lang.foreign.MemoryLayout;
import java.lang.foreign.MemorySegment;
import java.lang.foreign.ValueLayout;
import java.lang.invoke.MethodHandle;
import java.lang.invoke.MethodHandles;
import java.lang.invoke.MethodType;
import java.lang.reflect.Field;
import java.lang.reflect.InvocationTargetException;
import java.lang.reflect.Method;
import java.util.Arrays;
import java.util.concurrent.atomic.AtomicReference;

/**
 * Inert JDK upcalls, never ReadFile on an OS handle, actual pending I/O, stream digest or authority.
 * Windows uses real captured-state preparation; other hosts exercise only the private frame mechanics.
 */
public final class ByteReadInvocationTests {
    private ByteReadInvocationTests() {}

    private static final int CHUNK = 65_536;
    private static final int MAXIMUM_CALLS = 8193;
    private static final MemoryLayout DATA = MemoryLayout.sequenceLayout(CHUNK, ValueLayout.JAVA_BYTE);
    private static final FunctionDescriptor READ = FunctionDescriptor.of(ValueLayout.JAVA_INT,
        ValueLayout.ADDRESS, ValueLayout.ADDRESS.withTargetLayout(DATA), ValueLayout.JAVA_INT,
        ValueLayout.ADDRESS.withTargetLayout(ValueLayout.JAVA_INT), ValueLayout.ADDRESS);
    private static final FunctionDescriptor INFORMATION = FunctionDescriptor.of(ValueLayout.JAVA_INT,
        ValueLayout.ADDRESS, ValueLayout.JAVA_INT, ValueLayout.ADDRESS, ValueLayout.JAVA_INT);
    private static final LinkageError RETURN_FAILURE = new LinkageError("private inert read return failure");
    private static WindowsOriginalJvmBytesCandidate candidate;
    private static WindowsOriginalFileBytesLease core;
    private static String mode;
    private static boolean windows;
    private static int callbacks;
    private static int informationCallbacks;
    private static int wanted;
    private static long expectedHandle;
    private static Throwable callbackFailure;

    public static void main(String[] arguments) throws Throwable {
        check(arguments.length == 1);
        mode = arguments[0];
        check(Arrays.asList("full", "short", "eof", "false", "pending", "throw-after-return", "excess-count",
            "unsigned-count", "thread", "bounds", "limit").contains(mode));
        WindowsLoaderRuntime.requireDiagnosticRuntime();
        Linker linker = Linker.nativeLinker();
        windows = linker.getClass().getName().equals("jdk.internal.foreign.abi.x64.windows.Windowsx64Linker");
        wanted = mode.equals("full") ? CHUNK : mode.equals("limit") ? 1 : 64;
        try (Arena bootstrap = Arena.ofConfined(); Arena file = Arena.ofConfined(); Arena backing = Arena.ofConfined()) {
            MemorySegment handle = file.allocate(8).asSlice(0, 0); // Inert opaque value, not a file HANDLE.
            expectedHandle = handle.address();
            MemorySegment read = linker.upcallStub(MethodHandles.lookup().findStatic(ByteReadInvocationTests.class,
                "read", MethodType.methodType(int.class, MemorySegment.class, MemorySegment.class, int.class,
                    MemorySegment.class, MemorySegment.class)), READ, bootstrap);
            MemorySegment information = linker.upcallStub(MethodHandles.lookup().findStatic(ByteReadInvocationTests.class,
                "information", MethodType.methodType(int.class, MemorySegment.class, int.class,
                    MemorySegment.class, int.class)), INFORMATION, bootstrap);
            candidate = new WindowsOriginalJvmBytesCandidate(null, linker, bootstrap, file, handle,
                read, information, new long[8]);
            Field attachment = WindowsOriginalJvmBytesCandidate.class.getDeclaredField("core");
            attachment.setAccessible(true);
            core = (WindowsOriginalFileBytesLease) attachment.get(candidate);
            expect(IllegalStateException.class, candidate::observe);
            expect(IllegalStateException.class, candidate::completed);
            expect(IllegalStateException.class, candidate::byteCount);
            expect(IllegalStateException.class, candidate::sha256);
            check(callbacks == 0 && informationCallbacks == 0 && value("frameArena") == null && !(boolean) value("attempted"));
            prepare(linker, read);
            Arena frame = (Arena) value("frameArena");
            try {
                MemorySegment[] buffers = (MemorySegment[]) value("buffers");
                MemorySegment[] storage = new MemorySegment[buffers.length];
                for (int index = 0; index < buffers.length; index++) {
                    // Independent backing remains alive after the frame views retire, so clearing can
                    // be inspected without dereferencing freed storage. All pointers are inert allocations.
                    storage[index] = backing.allocate(buffers[index].byteSize(), 8);
                    storage[index].copyFrom(buffers[index]);
                    buffers[index] = storage[index].reinterpret(frame, null);
                }
                if (mode.equals("thread")) wrongThread();
                if (mode.equals("bounds")) {
                    byte[][] before = snapshot(buffers);
                    expect(IllegalStateException.class, () -> invoke("readOnce", 0));
                    expect(IllegalStateException.class, () -> invoke("readOnce", CHUNK + 1));
                    check((int) value("readCalls") == 0 && callbacks == 0 && !(boolean) value("readCompletionUnconfirmed"));
                    unchanged(buffers, before);
                }
                if (mode.equals("limit")) field("readCalls").setInt(core, MAXIMUM_CALLS - 1);
                if (mode.equals("throw-after-return")) {
                    MethodHandle after = MethodHandles.lookup().findStatic(ByteReadInvocationTests.class,
                        "throwAfterReturn", MethodType.methodType(int.class, int.class));
                    field("readCall").set(core, MethodHandles.filterReturnValue((MethodHandle) value("readCall"), after));
                }
                boolean unknown = Arrays.asList("false", "pending", "throw-after-return", "excess-count", "unsigned-count").contains(mode);
                if (unknown) {
                    Throwable refused = expect(mode.equals("throw-after-return") ? LinkageError.class : IllegalStateException.class,
                        () -> invoke("readOnce", wanted));
                    if (mode.equals("throw-after-return")) check(refused == RETURN_FAILURE);
                    check((boolean) value("readCompletionUnconfirmed") && !(boolean) value("frameRetired"));
                    if (!mode.equals("throw-after-return")) {
                        check((int) value("returnedStatus") == (mode.equals("false") || mode.equals("pending") ? 0 : 1));
                        long expectedCount = mode.equals("unsigned-count") ? 0xffff_ffffL :
                            mode.equals("excess-count") ? wanted + 1L : wanted / 2L;
                        check((long) value("returnedBytes") == expectedCount);
                        if (!windows && mode.equals("pending")) check((int) value("lastError") == 997);
                    }
                    byte[][] original = snapshot(buffers);
                    int calls = (int) value("readCalls");
                    expect(IllegalStateException.class, () -> invoke("readOnce", wanted));
                    invoke("retireFrame");
                    invoke("retireFrame");
                    check((int) value("readCalls") == calls && callbacks == 1 && frame.scope().isAlive() &&
                        !(boolean) value("frameRetired") && (boolean) value("readCompletionUnconfirmed"));
                    unchanged(buffers, original);
                    unchanged(storage, original);
                } else {
                    invoke("readOnce", wanted);
                    long expectedCount = mode.equals("short") ? wanted - 1L : mode.equals("eof") ? 0 : wanted;
                    check((int) value("returnedStatus") == 1 && (long) value("returnedBytes") == expectedCount &&
                        !(boolean) value("readCompletionUnconfirmed"));
                    if (!windows) check((int) value("lastError") == 126); // Stale error does not negate TRUE.
                    if (mode.equals("limit")) {
                        check((int) value("readCalls") == MAXIMUM_CALLS);
                        byte[][] before = snapshot(buffers);
                        expect(IllegalStateException.class, () -> invoke("readOnce", 1));
                        check((int) value("readCalls") == MAXIMUM_CALLS && callbacks == 1);
                        unchanged(buffers, before);
                    }
                    // A known short/EOF call is not success for a complete expected-length digest.
                    check(!(boolean) value("succeeded") && (long) value("total") == 0);
                    invoke("retireFrame");
                    invoke("retireFrame");
                    check((boolean) value("frameRetired") && !frame.scope().isAlive());
                    for (int index = 0; index < storage.length; index++) {
                        for (byte value : storage[index].toArray(ValueLayout.JAVA_BYTE)) check(value == 0);
                        MemorySegment retired = buffers[index];
                        expect(IllegalStateException.class, () -> retired.get(ValueLayout.JAVA_BYTE, 0));
                    }
                    expect(IllegalStateException.class, () -> invoke("readOnce", wanted));
                }
                check(callbacks == 1 && informationCallbacks == 0 && callbackFailure == null &&
                    bootstrap.scope().isAlive() && file.scope().isAlive() && backing.scope().isAlive());
                expect(IllegalStateException.class, candidate::observe);
                expect(IllegalStateException.class, candidate::completed);
            } finally {
                // Only the inert fixture may retire this memory: no kernel I/O or actual pending request
                // occurred. The production quarantine path itself never closes an uncertain read frame.
                if (frame.scope().isAlive()) frame.close();
            }
        }
        System.out.println("WINDOWS_FILE_BYTE_READ_PASS case=" + mode +
            " scope=INERT_READ_AND_RETIREMENT_NOT_FILE_CUSTODY_OR_AUTHORITY capture=" +
            (windows ? "WINDOWS_GET_LAST_ERROR" : "NOT_EXECUTED"));
    }

    private static void prepare(Linker linker, MemorySegment read) throws Throwable {
        if (windows) {
            invoke("prepare"); // Actual Windows capture layout/downcall descriptors, still only inert upcalls.
        } else {
            invoke("prepareFrame", MemoryLayout.structLayout(ValueLayout.JAVA_INT));
            MethodHandle call = linker.downcallHandle(read, READ);
            field("readCall").set(core, MethodHandles.dropArguments(call, 0, MemorySegment.class));
        }
    }

    private static int read(MemorySegment handle, MemorySegment output, int count, MemorySegment returned,
                            MemorySegment overlapped) {
        try {
            callbacks++;
            check(handle.address() == expectedHandle && count == wanted && overlapped.address() == 0 &&
                output.byteSize() == CHUNK && returned.byteSize() == 4 &&
                returned.get(ValueLayout.JAVA_INT, 0) == -1);
            for (byte value : output.toArray(ValueLayout.JAVA_BYTE)) check(value == 0);
            check(Thread.currentThread() == value("thread"));
            int resultCount = mode.equals("unsigned-count") ? -1 : mode.equals("excess-count") ? count + 1 :
                mode.equals("short") ? count - 1 : mode.equals("eof") ? 0 :
                mode.equals("false") || mode.equals("pending") ? count / 2 : count;
            int changed = resultCount < 0 ? count : Math.min(count, resultCount);
            output.asSlice(0, changed).fill((byte) 0x5a);
            returned.set(ValueLayout.JAVA_INT, 0, resultCount);
            MemorySegment state = ((MemorySegment[]) value("buffers"))[0];
            state.set(ValueLayout.JAVA_INT, (long) value("errorOffset"), mode.equals("pending") ? 997 : 126);
            return mode.equals("false") || mode.equals("pending") ? 0 : 1;
        } catch (Throwable caught) {
            callbackFailure = caught;
            return 0; // Never throw through an upcall boundary.
        }
    }

    private static int information(MemorySegment handle, int kind, MemorySegment output, int bytes) {
        informationCallbacks++;
        return 0; // This focused read-frame control must never query metadata or claim whole-stream completion.
    }

    private static int throwAfterReturn(int returned) {
        check(callbacks == 1 && returned == 1);
        throw RETURN_FAILURE;
    }

    private static void wrongThread() throws InterruptedException {
        AtomicReference<Throwable> failed = new AtomicReference<>();
        Thread other = new Thread(() -> {
            try {
                expect(IllegalStateException.class, () -> invoke("readOnce", wanted));
                expect(IllegalStateException.class, () -> invoke("retireFrame"));
                check(callbacks == 0 && (int) value("readCalls") == 0);
            } catch (Throwable caught) { failed.set(caught); }
        }, "inert-read-wrong-thread");
        other.start();
        other.join(5000);
        check(!other.isAlive());
        if (failed.get() != null) throw new AssertionError("Wrong-thread read control failed", failed.get());
    }

    private static byte[][] snapshot(MemorySegment[] buffers) {
        byte[][] copies = new byte[buffers.length][];
        for (int index = 0; index < buffers.length; index++) copies[index] = buffers[index].toArray(ValueLayout.JAVA_BYTE);
        return copies;
    }
    private static void unchanged(MemorySegment[] buffers, byte[][] copies) {
        for (int index = 0; index < buffers.length; index++) {
            check(buffers[index].scope().isAlive() && Arrays.equals(buffers[index].toArray(ValueLayout.JAVA_BYTE), copies[index]));
        }
    }
    private static Field field(String name) throws ReflectiveOperationException {
        Field field = WindowsOriginalFileBytesLease.class.getDeclaredField(name);
        field.setAccessible(true);
        return field;
    }
    private static Object value(String name) throws ReflectiveOperationException { return field(name).get(core); }
    private static Object invoke(String name, Object... arguments) throws Throwable {
        Class<?>[] types = arguments.length == 0 ? new Class<?>[0] :
            new Class<?>[] {arguments[0] instanceof Integer ? int.class : MemoryLayout.class};
        Method method = WindowsOriginalFileBytesLease.class.getDeclaredMethod(name, types);
        method.setAccessible(true);
        try { return method.invoke(core, arguments); }
        catch (InvocationTargetException failure) { throw failure.getCause(); }
    }
    private interface Action { void run() throws Throwable; }
    private static Throwable expect(Class<? extends Throwable> type, Action action) {
        try { action.run(); }
        catch (Throwable caught) {
            if (type.isInstance(caught)) return caught;
            throw new AssertionError("Unexpected byte-read control outcome", caught);
        }
        throw new AssertionError("Expected byte-read control refusal");
    }
    private static void check(boolean condition) {
        if (!condition) throw new AssertionError("Byte-read invocation control failed");
    }
}
