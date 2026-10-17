package dev.p2pkit.rpc.windows.loader;

import java.lang.foreign.Arena;
import java.lang.foreign.Linker;
import java.lang.foreign.MemoryLayout;
import java.lang.foreign.MemorySegment;
import java.lang.foreign.ValueLayout;
import java.lang.invoke.MethodHandle;
import java.lang.invoke.MethodHandles;
import java.lang.invoke.MethodType;
import java.lang.reflect.Constructor;
import java.lang.reflect.Field;
import java.lang.reflect.InvocationTargetException;
import java.lang.reflect.Method;
import java.util.concurrent.atomic.AtomicReference;

/** JDK upcall fixtures only: no actual VirtualQuery, ReadProcessMemory, candidate DLL or protected profile. */
public final class ImageReadInvocationTests {
    private ImageReadInvocationTests() {}

    private static final Object BOOTSTRAP = new Object();
    private static final Object MODULE = new Object();
    private static final Object PLAN = new Object();
    private static final Error INVOCATION_ERROR = new LinkageError("synthetic private image read error");
    private static final long IMAGE_BYTES = 65_536;
    private static String mode;
    private static boolean windows;
    private static Arena bootstrapArena;
    private static Arena moduleArena;
    private static MemorySegment allocation;
    private static MemorySegment module;
    private static long rva;
    private static int length;
    private static WindowsImageReadInvocation.Kind kind;
    private static WindowsImageReadInvocation invocation;
    private static Throwable callbackFailure;
    private static int queryCalls;
    private static int readCalls;

    public static void main(String[] arguments) throws Throwable {
        check(arguments.length == 1);
        mode = arguments[0];
        WindowsLoaderRuntime.requireDiagnosticRuntime();
        windows = Linker.nativeLinker().getClass().getName()
            .equals("jdk.internal.foreign.abi.x64.windows.Windowsx64Linker");
        rva = mode.equals("maximum") ? 0 : mode.equals("region-short") ? 4032 : 256;
        length = mode.equals("maximum") ? 65_536 : 128;
        kind = mode.startsWith("readonly") ? WindowsImageReadInvocation.Kind.READ_ONLY :
            mode.equals("data") || mode.equals("data-copy") || mode.equals("data-executable")
                ? WindowsImageReadInvocation.Kind.DATA : WindowsImageReadInvocation.Kind.EXECUTABLE;
        bootstrapArena = Arena.ofConfined();
        moduleArena = Arena.ofConfined();
        try {
            allocation = moduleArena.allocate(3 * IMAGE_BYTES, IMAGE_BYTES);
            module = allocation.asSlice(IMAGE_BYTES, 0); // Inert test storage, never a loaded HMODULE.
            MemorySegment queryEntry = Linker.nativeLinker().upcallStub(
                MethodHandles.lookup().findStatic(ImageReadInvocationTests.class, "queryCallback",
                    MethodType.methodType(long.class, MemorySegment.class, MemorySegment.class, long.class)),
                WindowsImageReadInvocation.QUERY, bootstrapArena);
            MemorySegment readEntry = Linker.nativeLinker().upcallStub(
                MethodHandles.lookup().findStatic(ImageReadInvocationTests.class, "readCallback",
                    MethodType.methodType(int.class, MemorySegment.class, MemorySegment.class, MemorySegment.class,
                        long.class, MemorySegment.class)), WindowsImageReadInvocation.READ, bootstrapArena);
            if (mode.equals("arguments")) invalidArguments(queryEntry, readEntry);
            if (mode.equals("virtual")) virtualRefusal(queryEntry, readEntry);
            invocation = prepareInert(queryEntry, readEntry);
            WindowsImageReadInvocation.Result reserved = (WindowsImageReadInvocation.Result) field("result");
            expect(IllegalStateException.class, reserved::bytes);
            MemorySegment[] originalBuffers = buffers().clone();
            if (mode.equals("thread")) wrongThreadRefusal(reserved);
            if (mode.equals("source-frame-alias") || mode.equals("count-frame-alias")) invalidBufferRefusal();
            if (mode.equals("closed-bootstrap")) bootstrapArena.close();
            if (mode.equals("closed-module")) moduleArena.close();
            if (mode.equals("retired-frame")) invocation.retireFrame();
            if (mode.equals("invocation-error")) {
                MethodHandle throwing = MethodHandles.throwException(long.class, Error.class).bindTo(INVOCATION_ERROR);
                setField("query", MethodHandles.dropArguments(throwing, 0, MemorySegment.class, MemorySegment.class,
                    MemorySegment.class, long.class));
            }
            if (mode.equals("late-module-close")) {
                MethodHandle afterReturn = MethodHandles.lookup().findStatic(ImageReadInvocationTests.class,
                    "closeAfterQueryReturn", MethodType.methodType(long.class, long.class));
                setField("query", MethodHandles.filterReturnValue((MethodHandle) field("query"), afterReturn));
            }
            if (mode.equals("query-return-unknown") || mode.equals("last-query-return-unknown") ||
                mode.equals("query-error-readback-failure") || mode.equals("last-query-error-readback-failure")) {
                MethodHandle afterReturn = MethodHandles.lookup().findStatic(ImageReadInvocationTests.class,
                    "afterQueryReturn", MethodType.methodType(long.class, long.class));
                setField("query", MethodHandles.filterReturnValue((MethodHandle) field("query"), afterReturn));
            }
            if (mode.equals("read-return-unknown") || mode.equals("read-error-readback-failure")) {
                MethodHandle afterReturn = MethodHandles.lookup().findStatic(ImageReadInvocationTests.class,
                    "afterReadReturn", MethodType.methodType(int.class, int.class));
                setField("read", MethodHandles.filterReturnValue((MethodHandle) field("read"), afterReturn));
            }
            boolean success = switch (mode) {
                case "success", "data", "data-copy", "readonly", "maximum", "arguments", "virtual", "thread", "reentrant",
                     "padding-change", "close-after-result", "source-frame-alias", "count-frame-alias" -> true;
                default -> false;
            };
            if (success) {
                WindowsImageReadInvocation.Result result = invocation.invoke();
                check(result == reserved && result.retainedInvocation == invocation);
                byte[] copy = result.bytes();
                check(copy.length == length);
                for (int index = 0; index < length; index++) check(copy[index] == pattern(index));
                copy[0] ^= 1;
                check(result.bytes()[0] == pattern(0));
                System.gc();
                check(result.bytes()[length - 1] == pattern(length - 1));
                check(queryCalls == 2 && readCalls == 1 && (long) field("bytesRead") == length);
                for (boolean observed : (boolean[]) field("errorsObserved")) check(observed);
                if (!windows) for (int error : (int[]) field("lastErrors")) check(error == 126);
                if (mode.equals("close-after-result")) {
                    moduleArena.close();
                    expect(IllegalStateException.class, result::bytes);
                }
                invocation.retireFrame();
            } else if (mode.equals("retired-frame")) {
                expect(IllegalStateException.class, invocation::invoke);
                check(queryCalls == 0 && readCalls == 0);
            } else {
                WindowsImageReadInvocation.Failure failure = (WindowsImageReadInvocation.Failure)
                    expect(WindowsImageReadInvocation.Failure.class, invocation::invoke);
                check(failure.retainedInvocation == invocation && failure.getCause() == null &&
                    failure.getSuppressed().length == 0 && !failure.getMessage().contains("synthetic"));
                if (mode.equals("clear-failure")) {
                    check(failure.operationFailure == null && failure.clearFailures[3] instanceof UnsupportedOperationException &&
                        failure.arenaCloseFailure == null && failure.retirementFailed());
                    check(expect(WindowsImageReadInvocation.Failure.class, invocation::retireFrame) == failure);
                } else {
                    check(failure.operationFailure != null && !failure.retirementFailed());
                    if (mode.equals("invocation-error") || mode.endsWith("return-unknown")) check(failure.operationFailure == INVOCATION_ERROR);
                    if (mode.endsWith("error-readback-failure")) check(failure.operationFailure instanceof IndexOutOfBoundsException);
                }
                for (byte value : (byte[]) field("snapshot")) check(value == 0);
                expect(IllegalStateException.class, reserved::bytes);
                int expectedQueries = switch (mode) {
                    case "closed-bootstrap", "closed-module", "invocation-error" -> 0;
                    case "late-query-failed", "mapping-change", "clear-failure", "late-module-close" -> 2;
                    case "last-query-return-unknown", "last-query-error-readback-failure" -> 2;
                    default -> 1;
                };
                int expectedReads = switch (mode) {
                    case "read-failed", "partial-read", "excess-read", "late-query-failed", "mapping-change",
                         "clear-failure", "late-module-close", "readback-failure" -> 1;
                    case "read-return-unknown", "last-query-return-unknown", "read-error-readback-failure",
                         "last-query-error-readback-failure" -> 1;
                    default -> 0;
                };
                check(queryCalls == expectedQueries && readCalls == expectedReads);
                if (expectedReads == 1 && !mode.equals("readback-failure") &&
                    !mode.equals("read-return-unknown") && !mode.equals("read-error-readback-failure")) {
                    check((long) field("bytesRead") == (mode.equals("partial-read") ? length - 1L :
                        mode.equals("excess-read") ? (1L << 32) + length : length));
                }
            }
            if (callbackFailure != null) throw new AssertionError("Inert image observation callback failed", callbackFailure);
            boolean unknown = mode.equals("invocation-error") || mode.endsWith("return-unknown");
            // This assertion is intentionally BEFORE new-field reflection: running the new test against
            // the prior adapter proves its actual premature retirement, not merely a missing new field.
            for (MemorySegment buffer : originalBuffers) check(buffer.scope().isAlive() == unknown);
            check((boolean) field("nativeReturnUnconfirmed") == unknown && (boolean) field("retired") == !unknown);
            check(!(boolean) field("active"));
            if (unknown) retainedUnknown(originalBuffers);
            if (mode.endsWith("error-readback-failure")) {
                check((long) field("firstQuerySize") == 48);
                if (mode.startsWith("read-")) check((int) field("readStatus") == -1 && (long) field("bytesRead") == 0);
                if (mode.startsWith("last-")) check((long) field("lastQuerySize") == 48 && (long) field("bytesRead") == length);
                check(!(boolean) field("succeeded"));
            }
            check(invocation.bootstrapOwner == BOOTSTRAP && invocation.moduleOwner == MODULE && invocation.originalImagePlan == PLAN);
            expect(IllegalStateException.class, invocation::invoke);
        } finally {
            // Only these inert tests own the simulated unknown frame. Their Java return filters run
            // after the real upcall returns; no unknown native request exists when test cleanup runs.
            if (invocation != null) {
                Arena frame = (Arena) field("frameArena");
                if (frame != null && frame.scope().isAlive()) frame.close();
            }
            if (bootstrapArena.scope().isAlive()) bootstrapArena.close();
            if (moduleArena.scope().isAlive()) moduleArena.close();
        }
        System.out.println("WINDOWS_IMAGE_FFM_READ_PASS case=" + mode +
            " scope=JDK_UPCALL_MARSHALING_NOT_OS_MEMORY_READ_OR_AUTHORITY capture=" +
            (windows ? "WINDOWS_GET_LAST_ERROR" : "NOT_EXECUTED"));
    }

    private static WindowsImageReadInvocation prepare(MemorySegment query, MemorySegment read, MemorySegment originalModule,
                                                       long imageBytes, long relative, int count,
                                                       WindowsImageReadInvocation.Kind policy) {
        return WindowsImageReadInvocation.prepare(BOOTSTRAP, MODULE, PLAN, query, read, bootstrapArena,
            originalModule, moduleArena, imageBytes, relative, count, policy);
    }

    private static WindowsImageReadInvocation prepareInert(MemorySegment queryEntry, MemorySegment readEntry) throws Throwable {
        if (windows) return prepare(queryEntry, readEntry, module, IMAGE_BYTES, rva, length, kind);
        expect(IllegalStateException.class, () -> prepare(queryEntry, readEntry, module, IMAGE_BYTES, rva, length, kind));
        Constructor<WindowsImageReadInvocation> constructor = WindowsImageReadInvocation.class.getDeclaredConstructor(
            Object.class, Object.class, Object.class, MemorySegment.class, MemorySegment.class, Arena.class,
            MemorySegment.class, Arena.class, long.class, long.class, int.class, WindowsImageReadInvocation.Kind.class);
        constructor.setAccessible(true);
        WindowsImageReadInvocation candidate = constructor.newInstance(BOOTSTRAP, MODULE, PLAN, queryEntry, readEntry,
            bootstrapArena, module, moduleArena, IMAGE_BYTES, rva, length, kind);
        Method method = WindowsImageReadInvocation.class.getDeclaredMethod("prepareFrame", MethodHandle.class,
            MethodHandle.class, MemoryLayout.class, long.class);
        method.setAccessible(true);
        MethodHandle query = MethodHandles.dropArguments(Linker.nativeLinker().downcallHandle(queryEntry,
            WindowsImageReadInvocation.QUERY), 0, MemorySegment.class);
        MethodHandle read = MethodHandles.dropArguments(Linker.nativeLinker().downcallHandle(readEntry,
            WindowsImageReadInvocation.READ), 0, MemorySegment.class);
        reflect(method, candidate, query, read, MemoryLayout.structLayout(ValueLayout.JAVA_INT), 0L);
        return candidate;
    }

    private static long queryCallback(MemorySegment address, MemorySegment information, long capacity) {
        try {
            queryCalls++;
            check(capacity == 48 && information.byteSize() == 48 && address.address() == module.address() + rva);
            check(Thread.currentThread() == field("thread"));
            if (mode.equals("reentrant")) {
                expect(IllegalStateException.class, invocation::invoke);
                expect(IllegalStateException.class, invocation::retireFrame);
                expect(IllegalStateException.class, ((WindowsImageReadInvocation.Result) field("result"))::bytes);
            }
            if (mode.equals("late-module-close") && queryCalls == 2) {
                expect(IllegalStateException.class, moduleArena::close);
                check(moduleArena.scope().isAlive());
            }
            information.set(ValueLayout.JAVA_LONG, 0, mode.equals("region-overflow") ? Long.MAX_VALUE & ~4095L :
                module.address() + (mode.equals("region-gap") ? 4096 : 0));
            information.set(ValueLayout.JAVA_LONG, 8, module.address() + (mode.equals("allocation-mismatch") ? IMAGE_BYTES : 0));
            information.set(ValueLayout.JAVA_INT, 16, mode.equals("mapping-change") && queryCalls == 2 ? 0x04 : 0x80);
            information.set(ValueLayout.JAVA_SHORT, 20, (short) 0);
            information.set(ValueLayout.JAVA_LONG, 24, mode.equals("region-short") || mode.equals("region-overflow")
                ? 4096 : mode.equals("region-gap") ? IMAGE_BYTES - 4096 : IMAGE_BYTES);
            information.set(ValueLayout.JAVA_INT, 32, mode.equals("not-committed") ? 0x2000 : 0x1000);
            int protection = kind == WindowsImageReadInvocation.Kind.EXECUTABLE ? 0x20 :
                kind == WindowsImageReadInvocation.Kind.READ_ONLY ? 0x02 : mode.equals("data-copy") ? 0x08 : 0x04;
            if (mode.equals("readonly-writable")) protection = 0x04;
            if (mode.equals("readonly-copy")) protection = 0x08;
            if (mode.equals("readonly-executable")) protection = 0x20;
            if (mode.equals("code-writable")) protection = 0x40;
            if (mode.equals("data-executable")) protection = 0x20;
            if (mode.equals("guard")) protection |= 0x100;
            information.set(ValueLayout.JAVA_INT, 36, protection);
            information.set(ValueLayout.JAVA_INT, 40, mode.equals("not-image") ? 0x20000 : 0x1000000);
            if (mode.equals("padding-change") && queryCalls == 2) {
                information.set(ValueLayout.JAVA_SHORT, 22, (short) 123);
                information.set(ValueLayout.JAVA_INT, 44, 456);
            }
            buffers()[4].set(ValueLayout.JAVA_INT, (long) field("errorOffset"), 126);
            if (mode.equals("clear-failure") && queryCalls == 2) buffers()[3] = buffers()[3].asReadOnly();
            if (mode.equals("query-failed") || (mode.equals("late-query-failed") && queryCalls == 2)) return 0;
            return mode.equals("query-short") ? 47 : 48;
        } catch (Throwable caught) {
            callbackFailure = caught;
            return 0;
        }
    }

    private static int readCallback(MemorySegment process, MemorySegment address, MemorySegment output,
                                    long requested, MemorySegment count) {
        try {
            readCalls++;
            check(process.address() == -1L && address.address() == module.address() + rva && requested == length &&
                output.byteSize() == 65_536 && count.byteSize() == 8 && queryCalls == 1);
            for (int index = 0; index < length; index++) output.set(ValueLayout.JAVA_BYTE, index, pattern(index));
            count.set(ValueLayout.JAVA_LONG, 0, mode.equals("partial-read") ? length - 1L :
                mode.equals("excess-read") ? (1L << 32) + length : length);
            buffers()[4].set(ValueLayout.JAVA_INT, (long) field("errorOffset"), 126);
            if (mode.equals("readback-failure")) buffers()[2] = buffers()[2].asSlice(0, 1);
            return mode.equals("read-failed") ? 0 : -1; // BOOL success is nonzero, not specifically one.
        } catch (Throwable caught) {
            callbackFailure = caught;
            return 0;
        }
    }

    private static long closeAfterQueryReturn(long result) {
        if (queryCalls == 2) moduleArena.close();
        return result;
    }

    private static long afterQueryReturn(long result) throws ReflectiveOperationException {
        if (mode.startsWith("last-") && queryCalls != 2) return result;
        if (mode.endsWith("return-unknown")) throw INVOCATION_ERROR;
        buffers()[4] = buffers()[4].asSlice(0, 1); // Known return; captured-error readback then refuses.
        return result;
    }

    private static int afterReadReturn(int result) throws ReflectiveOperationException {
        if (mode.equals("read-return-unknown")) throw INVOCATION_ERROR;
        buffers()[4] = buffers()[4].asSlice(0, 1);
        return result;
    }

    private static void retainedUnknown(MemorySegment[] originals) throws ReflectiveOperationException {
        byte[][] before = new byte[originals.length][];
        for (int index = 0; index < originals.length; index++) before[index] = originals[index].toArray(ValueLayout.JAVA_BYTE);
        invocation.retireFrame(); invocation.retireFrame();
        for (int index = 0; index < originals.length; index++) {
            check(originals[index] == buffers()[index] && originals[index].scope().isAlive());
            check(java.util.Arrays.equals(before[index], originals[index].toArray(ValueLayout.JAVA_BYTE)));
        }
        check(!((WindowsImageReadInvocation.Failure) field("failure")).retirementFailed());
        if (mode.equals("query-return-unknown")) check((long) field("firstQuerySize") == 0 && readCalls == 0);
        if (mode.equals("read-return-unknown")) {
            check((long) field("firstQuerySize") == 48 && (int) field("readStatus") == 0 && (long) field("bytesRead") == 0);
            check(originals[2].get(ValueLayout.JAVA_LONG, 0) == length && originals[3].get(ValueLayout.JAVA_BYTE, 0) == pattern(0));
        }
        if (mode.equals("last-query-return-unknown")) {
            check((long) field("firstQuerySize") == 48 && (long) field("lastQuerySize") == 0 && (long) field("bytesRead") == length);
        }
    }

    private static void invalidArguments(MemorySegment query, MemorySegment read) {
        for (long[] invalid : new long[][] {{4095, 0, 1}, {IMAGE_BYTES + 1, 0, 1},
            {128L * 1024 * 1024 + 4096, 0, 1}, {IMAGE_BYTES, -1, 1}, {IMAGE_BYTES, IMAGE_BYTES, 1},
            {IMAGE_BYTES, IMAGE_BYTES - 127, 128}, {IMAGE_BYTES, 0, 0}, {IMAGE_BYTES, 0, 65_537}}) {
            expect(IllegalArgumentException.class,
                () -> prepare(query, read, module, invalid[0], invalid[1], (int) invalid[2], kind));
        }
        expect(IllegalArgumentException.class, () -> prepare(query, query, module, IMAGE_BYTES, rva, length, kind));
        expect(IllegalArgumentException.class, () -> prepare(query, read, module, IMAGE_BYTES, rva, length, null));
        for (MemorySegment invalid : new MemorySegment[] {null, MemorySegment.NULL, MemorySegment.ofArray(new byte[8]),
            module.reinterpret(1).asSlice(1, 0), MemorySegment.ofAddress(Long.MAX_VALUE & ~65_535L).reinterpret(moduleArena, null)}) {
            expect(IllegalArgumentException.class, () -> prepare(query, read, invalid, IMAGE_BYTES, rva, length, kind));
        }
        expect(IllegalArgumentException.class, () -> WindowsImageReadInvocation.prepare(BOOTSTRAP, MODULE, PLAN,
            query, read, bootstrapArena, MemorySegment.ofAddress(module.address()), Arena.global(), IMAGE_BYTES, rva, length, kind));
        expect(IllegalArgumentException.class, () -> WindowsImageReadInvocation.prepare(BOOTSTRAP, MODULE, PLAN,
            query, read, moduleArena, module, moduleArena, IMAGE_BYTES, rva, length, kind));
        expect(IllegalArgumentException.class, () -> WindowsImageReadInvocation.prepare(null, MODULE, PLAN,
            query, read, bootstrapArena, module, moduleArena, IMAGE_BYTES, rva, length, kind));
        expect(IllegalArgumentException.class, () -> WindowsImageReadInvocation.prepare(BOOTSTRAP, null, PLAN,
            query, read, bootstrapArena, module, moduleArena, IMAGE_BYTES, rva, length, kind));
        expect(IllegalArgumentException.class, () -> WindowsImageReadInvocation.prepare(BOOTSTRAP, MODULE, null,
            query, read, bootstrapArena, module, moduleArena, IMAGE_BYTES, rva, length, kind));
        check(queryCalls == 0 && readCalls == 0);
    }

    private static void invalidBufferRefusal() throws Throwable {
        MemorySegment[] buffers = buffers();
        int index = mode.equals("source-frame-alias") ? 3 : 2;
        MemorySegment original = buffers[index];
        Arena frame = (Arena) field("frameArena");
        buffers[index] = index == 3 ? allocation.asSlice(IMAGE_BYTES - 8, 65_536).reinterpret(frame, null)
            : buffers[0].asSlice(40, 8);
        Method method = WindowsImageReadInvocation.class.getDeclaredMethod("validateBuffers");
        method.setAccessible(true);
        try { expect(IllegalStateException.class, () -> reflect(method, invocation)); }
        finally { buffers[index] = original; }
        check(queryCalls == 0 && readCalls == 0);
    }

    private static void virtualRefusal(MemorySegment query, MemorySegment read) throws InterruptedException {
        AtomicReference<Throwable> failure = new AtomicReference<>();
        Thread test = Thread.ofVirtual().start(() -> {
            try { expect(IllegalStateException.class, () -> prepare(query, read, module, IMAGE_BYTES, rva, length, kind)); }
            catch (Throwable caught) { failure.set(caught); }
        });
        test.join(5000);
        check(!test.isAlive());
        if (failure.get() != null) throw new AssertionError(failure.get());
    }

    private static void wrongThreadRefusal(WindowsImageReadInvocation.Result result) throws InterruptedException {
        AtomicReference<Throwable> failure = new AtomicReference<>();
        Thread test = new Thread(() -> {
            try {
                expect(IllegalStateException.class, invocation::invoke);
                expect(IllegalStateException.class, invocation::retireFrame);
                expect(IllegalStateException.class, result::bytes);
            } catch (Throwable caught) { failure.set(caught); }
        }, "image-read-wrong-thread");
        test.start();
        test.join(5000);
        check(!test.isAlive());
        if (failure.get() != null) throw new AssertionError(failure.get());
    }

    private static byte pattern(int index) { return (byte) (index * 37 + 13); }
    private static MemorySegment[] buffers() throws ReflectiveOperationException { return (MemorySegment[]) field("buffers"); }
    private static Object field(String name) throws ReflectiveOperationException {
        Field field = WindowsImageReadInvocation.class.getDeclaredField(name);
        field.setAccessible(true);
        return field.get(invocation);
    }
    private static void setField(String name, Object value) throws ReflectiveOperationException {
        Field field = WindowsImageReadInvocation.class.getDeclaredField(name);
        field.setAccessible(true);
        field.set(invocation, value);
    }
    private static void reflect(Method method, Object receiver, Object... arguments) throws Throwable {
        try { method.invoke(receiver, arguments); }
        catch (InvocationTargetException failure) { throw failure.getCause(); }
    }
    private interface Action { void run() throws Throwable; }
    private static Throwable expect(Class<? extends Throwable> type, Action action) {
        try { action.run(); }
        catch (Throwable caught) {
            if (type.isInstance(caught)) return caught;
            throw new AssertionError("Unexpected image observation outcome", caught);
        }
        throw new AssertionError("Expected image observation refusal");
    }
    private static void check(boolean condition) {
        if (!condition) throw new AssertionError("Image observation control failed");
    }
}
