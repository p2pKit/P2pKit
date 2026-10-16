package dev.p2pkit.rpc.windows.loader;

import java.lang.foreign.Arena;
import java.lang.foreign.Linker;
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

/** Inert FFM upcalls only; no export is resolved from an actual DLL and no candidate DLL pointer is executed. */
public final class ExportLookupInvocationTests {
    private ExportLookupInvocationTests() {}

    private static final Object BOOTSTRAP = new Object();
    private static final Object MODULE = new Object();
    private static final Object PLAN = new Object();
    private static final Error INVOCATION_ERROR = new LinkageError("synthetic private invocation failure");
    private static final long IMAGE_BYTES = 65_536;
    private static final long EXPORT_RVA = 4096;
    private static final long EXPORT_BYTES = 512;
    private static final long FUNCTION_RVA = 1024;
    private static String mode;
    private static String name;
    private static boolean windows;
    private static Arena bootstrapArena;
    private static Arena moduleArena;
    private static MemorySegment allocation;
    private static MemorySegment module;
    private static MemorySegment expectedEntry;
    private static WindowsExportLookupInvocation invocation;
    private static Throwable callbackFailure;
    private static int callbacks;

    public static void main(String[] arguments) throws Throwable {
        check(arguments.length == 1);
        mode = arguments[0];
        name = mode.equals("long-name") ? "A".repeat(255) : "JNI_GetCreatedJavaVMs";
        WindowsLoaderRuntime.requireDiagnosticRuntime();
        windows = Linker.nativeLinker().getClass().getName()
            .equals("jdk.internal.foreign.abi.x64.windows.Windowsx64Linker");
        bootstrapArena = Arena.ofConfined();
        moduleArena = Arena.ofConfined();
        try {
            allocation = moduleArena.allocate(3 * IMAGE_BYTES, IMAGE_BYTES);
            module = allocation.asSlice(IMAGE_BYTES, 0); // Inert aligned storage, not an admitted HMODULE.
            expectedEntry = allocation.asSlice(IMAGE_BYTES + FUNCTION_RVA, 0);
            MemorySegment systemEntry = Linker.nativeLinker().upcallStub(
                MethodHandles.lookup().findStatic(ExportLookupInvocationTests.class, "callback",
                    MethodType.methodType(MemorySegment.class, MemorySegment.class, MemorySegment.class)),
                WindowsExportLookupInvocation.DESCRIPTOR, bootstrapArena);
            if (mode.equals("arguments")) invalidArguments(systemEntry);
            if (mode.equals("forwarder")) forwarderRefusal(systemEntry);
            if (mode.equals("virtual")) virtualRefusal(systemEntry);
            invocation = prepareInert(systemEntry);
            WindowsExportLookupInvocation.Result reserved =
                (WindowsExportLookupInvocation.Result) field("result");
            expect(IllegalStateException.class, reserved::entry);
            MemorySegment originalName = (MemorySegment) field("nameBuffer");
            check(originalName.byteSize() == 256 && originalName.address() > 65_535 &&
                ((MemorySegment) field("nameView")).isReadOnly());
            if (mode.equals("thread")) wrongThreadRefusal(reserved);
            if (mode.equals("partial-frame-alias") || mode.equals("ordinal-buffer")) invalidBufferRefusal(originalName);
            if (mode.equals("closed-bootstrap")) bootstrapArena.close();
            if (mode.equals("closed-module")) moduleArena.close();
            if (mode.equals("retired-frame")) invocation.retireFrame();
            if (mode.equals("invocation-failure")) {
                MethodHandle throwing = MethodHandles.throwException(MemorySegment.class, Error.class)
                    .bindTo(INVOCATION_ERROR);
                setField("call", MethodHandles.dropArguments(throwing, 0, MemorySegment.class, MemorySegment.class));
            }
            if (mode.equals("late-module-close")) {
                MethodHandle afterReturn = MethodHandles.lookup().findStatic(ExportLookupInvocationTests.class,
                    "closeModuleAfterReturn", MethodType.methodType(MemorySegment.class, MemorySegment.class));
                setField("call", MethodHandles.filterReturnValue((MethodHandle) field("call"), afterReturn));
            }
            switch (mode) {
                case "success", "long-name", "arguments", "forwarder", "virtual", "thread", "reentrant",
                     "close-after-result", "partial-frame-alias", "ordinal-buffer" -> {
                    WindowsExportLookupInvocation.Result result = invocation.invoke();
                    check(result == reserved && result.retainedInvocation == invocation);
                    check(result.entry().address() == expectedEntry.address() && result.entry().byteSize() == 0 &&
                        result.entry().scope().equals(moduleArena.scope()));
                    check(!originalName.scope().isAlive() && bootstrapArena.scope().isAlive() && moduleArena.scope().isAlive());
                    System.gc();
                    check(result.entry().address() == expectedEntry.address());
                    if (mode.equals("close-after-result")) {
                        bootstrapArena.close();
                        expect(IllegalStateException.class, result::entry);
                    }
                    invocation.retireFrame();
                }
                case "retired-frame" -> expect(IllegalStateException.class, invocation::invoke);
                case "wrong-address", "null-address", "high-address", "private-alias", "closed-bootstrap",
                     "closed-module", "clear-failure", "invocation-failure", "late-module-close" -> {
                    WindowsExportLookupInvocation.Failure failure = (WindowsExportLookupInvocation.Failure)
                        expect(WindowsExportLookupInvocation.Failure.class, invocation::invoke);
                    check(failure.retainedInvocation == invocation && failure.getCause() == null &&
                        failure.getSuppressed().length == 0 && !failure.getMessage().contains("synthetic"));
                    if (mode.equals("closed-bootstrap") || mode.equals("closed-module") || mode.equals("invocation-failure")) {
                        check(failure.invocationFailure != null && failure.readbackFailure == null && !failure.retirementFailed());
                        if (mode.equals("invocation-failure")) check(failure.invocationFailure == INVOCATION_ERROR);
                    } else if (mode.equals("clear-failure")) {
                        check(failure.invocationFailure == null && failure.readbackFailure == null &&
                            failure.nameClearFailure instanceof UnsupportedOperationException && failure.arenaCloseFailure == null);
                        check(expect(WindowsExportLookupInvocation.Failure.class, invocation::retireFrame) == failure);
                        check(((MemorySegment) field("resolved")).address() == expectedEntry.address());
                    } else {
                        check(failure.invocationFailure == null && failure.readbackFailure != null && !failure.retirementFailed());
                        check(field("resolved") != null); // Preserve the original return even on rejected readback.
                    }
                    expect(IllegalStateException.class, reserved::entry);
                }
                default -> throw new AssertionError("Unknown named-export control");
            }
            check(invocation.bootstrapOwner == BOOTSTRAP && invocation.moduleOwner == MODULE &&
                invocation.originalExportPlan == PLAN);
            if (callbackFailure != null) throw new AssertionError("Inert named-export upcall failed", callbackFailure);
            int expectedCalls = switch (mode) {
                case "closed-bootstrap", "closed-module", "retired-frame", "invocation-failure" -> 0;
                default -> 1;
            };
            check(callbacks == expectedCalls && !originalName.scope().isAlive());
            expect(IllegalStateException.class, invocation::invoke);
            check(callbacks == expectedCalls);
        } finally {
            // Only test-owned arenas retire, after every native callback has returned. No DLL was loaded/unloaded.
            if (bootstrapArena.scope().isAlive()) bootstrapArena.close();
            if (moduleArena.scope().isAlive()) moduleArena.close();
        }
        System.out.println("WINDOWS_EXPORT_FFM_LOOKUP_PASS case=" + mode +
            " scope=JDK_UPCALL_MARSHALING_NOT_EXPORT_LOOKUP_OR_AUTHORITY host=" +
            (windows ? "WINDOWS_X64_LINKER" : "INERT_FRAME_ONLY"));
    }

    private static WindowsExportLookupInvocation prepareInert(MemorySegment entry) throws Throwable {
        if (windows) return prepare(entry, module, name, IMAGE_BYTES, EXPORT_RVA, EXPORT_BYTES, FUNCTION_RVA);
        expect(IllegalStateException.class,
            () -> prepare(entry, module, name, IMAGE_BYTES, EXPORT_RVA, EXPORT_BYTES, FUNCTION_RVA));
        Constructor<WindowsExportLookupInvocation> constructor = WindowsExportLookupInvocation.class.getDeclaredConstructor(
            Object.class, Object.class, Object.class, MemorySegment.class, Arena.class, MemorySegment.class,
            Arena.class, String.class, long.class, long.class);
        constructor.setAccessible(true);
        WindowsExportLookupInvocation candidate = constructor.newInstance(BOOTSTRAP, MODULE, PLAN,
            entry, bootstrapArena, module, moduleArena, name, IMAGE_BYTES, FUNCTION_RVA);
        Method method = WindowsExportLookupInvocation.class.getDeclaredMethod("prepareFrame", MethodHandle.class);
        method.setAccessible(true);
        reflect(method, candidate, Linker.nativeLinker().downcallHandle(entry, WindowsExportLookupInvocation.DESCRIPTOR));
        return candidate;
    }

    private static WindowsExportLookupInvocation prepare(MemorySegment entry, MemorySegment originalModule,
                                                         String exportName, long imageBytes, long directoryRva,
                                                         long directoryBytes, long functionRva) {
        return WindowsExportLookupInvocation.prepare(BOOTSTRAP, MODULE, PLAN, entry, bootstrapArena,
            originalModule, moduleArena, exportName, imageBytes, directoryRva, directoryBytes, functionRva);
    }

    private static MemorySegment callback(MemorySegment originalModule, MemorySegment ascii) {
        try {
            callbacks++;
            check(Thread.currentThread() == field("thread") && originalModule.address() == module.address() &&
                ascii.byteSize() == 256 && ascii.address() > 65_535);
            for (int index = 0; index < 256; index++) {
                check(Byte.toUnsignedInt(ascii.get(ValueLayout.JAVA_BYTE, index)) ==
                    (index < name.length() ? name.charAt(index) : 0));
            }
            if (mode.equals("reentrant")) {
                expect(IllegalStateException.class, invocation::invoke);
                expect(IllegalStateException.class, invocation::retireFrame);
                expect(IllegalStateException.class, ((WindowsExportLookupInvocation.Result) field("result"))::entry);
            }
            if (mode.equals("clear-failure")) setField("nameBuffer", ((MemorySegment) field("nameBuffer")).asReadOnly());
            if (mode.equals("late-module-close")) {
                expect(IllegalStateException.class, moduleArena::close);
                check(moduleArena.scope().isAlive());
            }
            return switch (mode) {
                case "null-address" -> MemorySegment.NULL;
                case "wrong-address" -> MemorySegment.ofAddress(expectedEntry.address() + 1);
                case "high-address" -> MemorySegment.ofAddress(-1L);
                case "private-alias" -> ascii.asSlice(1, 0);
                default -> expectedEntry;
            };
        } catch (Throwable caught) {
            callbackFailure = caught;
            return MemorySegment.NULL;
        }
    }

    /** Test-only return filter: close only after the real downcall has released its argument-scope acquisition. */
    private static MemorySegment closeModuleAfterReturn(MemorySegment returned) {
        check(callbacks == 1);
        moduleArena.close();
        return returned;
    }

    private static void invalidArguments(MemorySegment entry) {
        for (String invalid : new String[] {"", "123", "#1", "A.B", "A-B", "A\u0000B", "A\u00e9", "A".repeat(256)}) {
            expect(IllegalArgumentException.class,
                () -> prepare(entry, module, invalid, IMAGE_BYTES, EXPORT_RVA, EXPORT_BYTES, FUNCTION_RVA));
        }
        for (long[] invalid : new long[][] {
            {0, EXPORT_RVA, EXPORT_BYTES, FUNCTION_RVA}, {128L * 1024 * 1024 + 1, EXPORT_RVA, EXPORT_BYTES, FUNCTION_RVA},
            {IMAGE_BYTES, 0, EXPORT_BYTES, FUNCTION_RVA}, {IMAGE_BYTES, EXPORT_RVA, 39, FUNCTION_RVA},
            {IMAGE_BYTES, IMAGE_BYTES - 1, 40, FUNCTION_RVA}, {IMAGE_BYTES, EXPORT_RVA, Long.MAX_VALUE, FUNCTION_RVA},
            {IMAGE_BYTES, EXPORT_RVA, EXPORT_BYTES, 0}, {IMAGE_BYTES, EXPORT_RVA, EXPORT_BYTES, IMAGE_BYTES}}) {
            expect(IllegalArgumentException.class,
                () -> prepare(entry, module, name, invalid[0], invalid[1], invalid[2], invalid[3]));
        }
        for (MemorySegment invalid : new MemorySegment[] {null, MemorySegment.NULL, MemorySegment.ofArray(new byte[8]),
            module.reinterpret(1).asSlice(1, 0), MemorySegment.ofAddress(Long.MAX_VALUE & ~65_535L).reinterpret(moduleArena, null)}) {
            expect(IllegalArgumentException.class,
                () -> prepare(entry, invalid, name, IMAGE_BYTES, EXPORT_RVA, EXPORT_BYTES, FUNCTION_RVA));
        }
        for (MemorySegment invalid : new MemorySegment[] {null, MemorySegment.NULL, MemorySegment.ofArray(new byte[8])}) {
            expect(IllegalArgumentException.class,
                () -> prepare(invalid, module, name, IMAGE_BYTES, EXPORT_RVA, EXPORT_BYTES, FUNCTION_RVA));
        }
        expect(IllegalArgumentException.class, () -> WindowsExportLookupInvocation.prepare(BOOTSTRAP, MODULE, PLAN,
            MemorySegment.ofAddress(entry.address()), Arena.global(), module, moduleArena,
            name, IMAGE_BYTES, EXPORT_RVA, EXPORT_BYTES, FUNCTION_RVA));
        expect(IllegalArgumentException.class, () -> WindowsExportLookupInvocation.prepare(BOOTSTRAP, MODULE, PLAN,
            entry, bootstrapArena, MemorySegment.ofAddress(module.address()), Arena.global(),
            name, IMAGE_BYTES, EXPORT_RVA, EXPORT_BYTES, FUNCTION_RVA));
        expect(IllegalArgumentException.class, () -> WindowsExportLookupInvocation.prepare(null, MODULE, PLAN,
            entry, bootstrapArena, module, moduleArena, name, IMAGE_BYTES, EXPORT_RVA, EXPORT_BYTES, FUNCTION_RVA));
        expect(IllegalArgumentException.class, () -> WindowsExportLookupInvocation.prepare(BOOTSTRAP, null, PLAN,
            entry, bootstrapArena, module, moduleArena, name, IMAGE_BYTES, EXPORT_RVA, EXPORT_BYTES, FUNCTION_RVA));
        expect(IllegalArgumentException.class, () -> WindowsExportLookupInvocation.prepare(BOOTSTRAP, MODULE, null,
            entry, bootstrapArena, module, moduleArena, name, IMAGE_BYTES, EXPORT_RVA, EXPORT_BYTES, FUNCTION_RVA));
        expect(IllegalArgumentException.class, () -> WindowsExportLookupInvocation.prepare(BOOTSTRAP, MODULE, PLAN,
            entry, moduleArena, module, moduleArena, name, IMAGE_BYTES, EXPORT_RVA, EXPORT_BYTES, FUNCTION_RVA));
        expect(IllegalArgumentException.class, () -> WindowsExportLookupInvocation.prepare(BOOTSTRAP, MODULE, PLAN,
            entry, bootstrapArena, module, bootstrapArena, name, IMAGE_BYTES, EXPORT_RVA, EXPORT_BYTES, FUNCTION_RVA));
        check(callbacks == 0);
    }

    private static void forwarderRefusal(MemorySegment entry) {
        for (long rva : new long[] {EXPORT_RVA, EXPORT_RVA + EXPORT_BYTES - 1}) {
            expect(IllegalArgumentException.class,
                () -> prepare(entry, module, name, IMAGE_BYTES, EXPORT_RVA, EXPORT_BYTES, rva));
        }
        check(callbacks == 0);
    }

    private static void invalidBufferRefusal(MemorySegment original) throws Throwable {
        Arena frame = (Arena) field("frameArena");
        MemorySegment invalid = mode.equals("ordinal-buffer")
            ? MemorySegment.ofAddress(65_535).reinterpret(256, frame, null)
            : allocation.asSlice(IMAGE_BYTES - 128, 256).reinterpret(frame, null);
        setField("nameBuffer", invalid);
        Method method = WindowsExportLookupInvocation.class.getDeclaredMethod("validateNameBuffer");
        method.setAccessible(true);
        try {
            expect(IllegalStateException.class, () -> reflect(method, invocation));
            check(callbacks == 0);
        } finally {
            // Never dereference the deliberately invalid numeric ordinal fixture, including during cleanup.
            setField("nameBuffer", original);
        }
    }

    private static void virtualRefusal(MemorySegment entry) throws InterruptedException {
        AtomicReference<Throwable> failure = new AtomicReference<>();
        Thread test = Thread.ofVirtual().start(() -> {
            try { expect(IllegalStateException.class,
                () -> prepare(entry, module, name, IMAGE_BYTES, EXPORT_RVA, EXPORT_BYTES, FUNCTION_RVA)); }
            catch (Throwable caught) { failure.set(caught); }
        });
        test.join(5000);
        check(!test.isAlive());
        if (failure.get() != null) throw new AssertionError(failure.get());
    }

    private static void wrongThreadRefusal(WindowsExportLookupInvocation.Result result) throws InterruptedException {
        AtomicReference<Throwable> failure = new AtomicReference<>();
        Thread test = new Thread(() -> {
            try {
                expect(IllegalStateException.class, invocation::invoke);
                expect(IllegalStateException.class, invocation::retireFrame);
                expect(IllegalStateException.class, result::entry);
            } catch (Throwable caught) { failure.set(caught); }
        }, "export-lookup-wrong-thread");
        test.start();
        test.join(5000);
        check(!test.isAlive());
        if (failure.get() != null) throw new AssertionError(failure.get());
    }

    private static Object field(String name) throws ReflectiveOperationException {
        Field field = WindowsExportLookupInvocation.class.getDeclaredField(name);
        field.setAccessible(true);
        return field.get(invocation);
    }

    private static void setField(String name, Object value) throws ReflectiveOperationException {
        Field field = WindowsExportLookupInvocation.class.getDeclaredField(name);
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
            throw new AssertionError("Unexpected named-export control outcome", caught);
        }
        throw new AssertionError("Expected named-export control refusal");
    }

    private static void check(boolean condition) {
        if (!condition) throw new AssertionError("Named-export invocation control failed");
    }
}
