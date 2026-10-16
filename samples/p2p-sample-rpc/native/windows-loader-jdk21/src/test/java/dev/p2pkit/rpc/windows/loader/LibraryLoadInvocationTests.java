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

/** Inert JDK upcalls only. Windows executes real capture preparation; other hosts reflectively exercise frames. */
public final class LibraryLoadInvocationTests {
    private LibraryLoadInvocationTests() {}

    private static final Object INSTALLATION = new Object();
    private static final Object RUNTIME = new Object();
    private static final Object FILE = new Object();
    private static final String PATH = "C:\\Program Files\\P2pKit\\app\\p2pkit-windows-profile.dll";
    private static String mode;
    private static boolean windows;
    private static WindowsLibraryLoadInvocation invocation;
    private static MemorySegment expectedModule;
    private static Throwable callbackFailure;
    private static int callbacks;

    public static void main(String[] arguments) throws Throwable {
        check(arguments.length == 1);
        mode = arguments[0];
        WindowsLoaderRuntime.requireDiagnosticRuntime();
        windows = Linker.nativeLinker().getClass().getName()
            .equals("jdk.internal.foreign.abi.x64.windows.Windowsx64Linker");
        Arena original = Arena.ofConfined();
        try {
            expectedModule = original.allocate(65_536, 65_536); // Inert storage, not a loaded DLL.
            MemorySegment entry = stub(original);
            if (mode.equals("arguments")) invalidArguments(entry, original);
            if (mode.equals("virtual")) virtualRefusal(entry, original);
            invocation = prepareInert(entry, original);
            WindowsLibraryLoadInvocation.Result reserved = (WindowsLibraryLoadInvocation.Result) field("result");
            expect(IllegalStateException.class, reserved::module);
            MemorySegment path = (MemorySegment) field("pathBuffer");
            MemorySegment state = (MemorySegment) field("capturedState");
            check(path.byteSize() == 520 && state.byteSize() >= 4 && state.byteSize() <= 64);
            check(((MemorySegment) field("pathView")).isReadOnly());
            if (mode.equals("thread")) wrongThreadRefusal(reserved);
            if (mode.equals("closed-entry")) original.close();
            if (mode.equals("retired-frame")) invocation.retireFrame();
            switch (mode) {
                case "success", "arguments", "virtual", "thread", "reentrant", "duplicate", "close-after-result" -> {
                    WindowsLibraryLoadInvocation.Result result = invocation.invoke();
                    check(result == reserved && result.retainedInvocation == invocation);
                    check(result.module().address() == expectedModule.address() && result.module().byteSize() == 0 &&
                        result.module().scope().equals(original.scope()));
                    check((boolean) field("errorObserved"));
                    // The portable frame control explicitly leaves nonzero stale state on success.
                    // Windows captures the real native thread state; an inert upcall does not choose that value.
                    if (!windows) check((int) field("lastError") == 126);
                    check(!path.scope().isAlive() && !state.scope().isAlive());
                    System.gc();
                    check(result.module().address() == expectedModule.address());
                    if (mode.equals("duplicate")) {
                        WindowsLibraryLoadInvocation other = prepareInert(entry, original);
                        expect(IllegalStateException.class, other::invoke);
                        other.retireFrame();
                        check(callbacks == 1 && result.module().scope().isAlive());
                    }
                    if (mode.equals("close-after-result")) {
                        original.close();
                        expect(IllegalStateException.class, result::module);
                    }
                    invocation.retireFrame();
                }
                case "retired-frame" -> expect(IllegalStateException.class, invocation::invoke);
                case "null-module", "unaligned-module", "high-module", "readback-failure", "clear-failure",
                     "closed-entry" -> {
                    WindowsLibraryLoadInvocation.Failure failure = (WindowsLibraryLoadInvocation.Failure)
                        expect(WindowsLibraryLoadInvocation.Failure.class, invocation::invoke);
                    check(failure.retainedInvocation == invocation && failure.getCause() == null &&
                        failure.getSuppressed().length == 0);
                    if (mode.equals("closed-entry")) {
                        check(failure.invocationFailure instanceof IllegalStateException &&
                            failure.readbackFailure == null && !failure.retirementFailed());
                    } else if (mode.equals("clear-failure")) {
                        check(failure.invocationFailure == null && failure.readbackFailure == null &&
                            failure.pathClearFailure instanceof UnsupportedOperationException &&
                            failure.stateClearFailure == null && failure.arenaCloseFailure == null);
                        check(expect(WindowsLibraryLoadInvocation.Failure.class, invocation::retireFrame) == failure);
                        check(((MemorySegment) field("module")).address() == expectedModule.address());
                    } else {
                        check(failure.invocationFailure == null && failure.readbackFailure != null &&
                            !failure.retirementFailed());
                        if (!mode.equals("readback-failure")) check((boolean) field("errorObserved"));
                        else check(((MemorySegment) field("module")).address() == expectedModule.address());
                    }
                    expect(IllegalStateException.class, reserved::module);
                }
                default -> throw new AssertionError("Unknown load invocation control");
            }
            check(invocation.installationOwner == INSTALLATION && invocation.runtimeOwner == RUNTIME &&
                invocation.fileOwner == FILE);
            if (callbackFailure != null) throw new AssertionError("Inert load upcall failed", callbackFailure);
            int expectedCalls = mode.equals("closed-entry") || mode.equals("retired-frame") ? 0 : 1;
            check(callbacks == expectedCalls && !path.scope().isAlive() && !state.scope().isAlive());
            if (!mode.equals("closed-entry") && !mode.equals("close-after-result")) check(original.scope().isAlive());
            expect(IllegalStateException.class, invocation::invoke);
            check(callbacks == expectedCalls);
            if (!mode.equals("retired-frame")) check(staticField("processOwner") == invocation);
        } finally {
            // Only this inert fixture retires its arena after all callbacks return. No module was loaded/unloaded.
            if (original.scope().isAlive()) original.close();
        }
        System.out.println("WINDOWS_LIBRARY_FFM_LOAD_PASS case=" + mode +
            " scope=JDK_UPCALL_MARSHALING_NOT_DLL_LOADING_OR_AUTHORITY capture=" +
            (windows ? "WINDOWS_GET_LAST_ERROR" : "NOT_EXECUTED"));
    }

    private static WindowsLibraryLoadInvocation prepareInert(MemorySegment entry, Arena original) throws Throwable {
        if (windows) return WindowsLibraryLoadInvocation.prepare(INSTALLATION, RUNTIME, FILE, entry, original, PATH);
        // Actual production entry must refuse this host. No production boolean or validation constructor exists.
        expect(IllegalStateException.class,
            () -> WindowsLibraryLoadInvocation.prepare(INSTALLATION, RUNTIME, FILE, entry, original, PATH));
        Constructor<WindowsLibraryLoadInvocation> constructor =
            WindowsLibraryLoadInvocation.class.getDeclaredConstructor(Object.class, Object.class, Object.class,
                MemorySegment.class, Arena.class, String.class);
        constructor.setAccessible(true);
        WindowsLibraryLoadInvocation candidate =
            constructor.newInstance(INSTALLATION, RUNTIME, FILE, entry, original, PATH);
        Method prepare = WindowsLibraryLoadInvocation.class.getDeclaredMethod(
            "prepareFrame", MethodHandle.class, MemoryLayout.class, long.class);
        prepare.setAccessible(true);
        MethodHandle plain = Linker.nativeLinker().downcallHandle(entry, WindowsLibraryLoadInvocation.DESCRIPTOR);
        MethodHandle inertCapture = MethodHandles.dropArguments(plain, 0, MemorySegment.class);
        // Same call/frame mechanics, explicitly no Windows error-state capture on this non-Windows host.
        invoke(prepare, candidate, inertCapture, MemoryLayout.structLayout(ValueLayout.JAVA_INT), 0L);
        return candidate;
    }

    private static MemorySegment stub(Arena arena) throws ReflectiveOperationException {
        return Linker.nativeLinker().upcallStub(
            MethodHandles.lookup().findStatic(LibraryLoadInvocationTests.class, "callback",
                MethodType.methodType(MemorySegment.class, MemorySegment.class, MemorySegment.class, int.class)),
                WindowsLibraryLoadInvocation.DESCRIPTOR, arena);
    }

    private static MemorySegment callback(MemorySegment path, MemorySegment file, int flags) {
        try {
            callbacks++;
            check(Thread.currentThread() == field("thread") && path.byteSize() == 520 && file.address() == 0 &&
                flags == 0x800);
            for (int index = 0; index < 260; index++) {
                int expected = index < PATH.length() ? PATH.charAt(index) : 0;
                check(Short.toUnsignedInt(path.getAtIndex(ValueLayout.JAVA_SHORT, index)) == expected);
            }
            MemorySegment state = (MemorySegment) field("capturedState");
            check(path.address() + path.byteSize() <= state.address() ||
                state.address() + state.byteSize() <= path.address());
            state.set(ValueLayout.JAVA_INT, (long) field("errorOffset"), 126);
            if (mode.equals("reentrant")) {
                expect(IllegalStateException.class, invocation::invoke);
                expect(IllegalStateException.class, invocation::retireFrame);
                expect(IllegalStateException.class, ((WindowsLibraryLoadInvocation.Result) field("result"))::module);
            }
            if (mode.equals("clear-failure")) {
                setField("pathBuffer", ((MemorySegment) field("pathBuffer")).asReadOnly());
            }
            if (mode.equals("readback-failure")) setField("capturedState", state.asSlice(0, 1));
            return switch (mode) {
                case "null-module" -> MemorySegment.NULL;
                case "unaligned-module" -> expectedModule.asSlice(1);
                case "high-module" -> MemorySegment.ofAddress(-65_536L); // Inert return only, never dereferenced.
                default -> expectedModule;
            };
        } catch (Throwable caught) {
            callbackFailure = caught;
            return MemorySegment.NULL;
        }
    }

    private static void invalidArguments(MemorySegment entry, Arena original) throws Throwable {
        for (String invalid : new String[] {"", "p2pkit-windows-profile.dll", "C:p2pkit-windows-profile.dll",
            "C:/Program Files/p2pkit-windows-profile.dll", "\\\\host\\share\\p2pkit-windows-profile.dll",
            "\\\\?\\C:\\app\\p2pkit-windows-profile.dll", "C:\\app\\..\\p2pkit-windows-profile.dll",
            "C:\\app\\\\p2pkit-windows-profile.dll", "C:\\app \\p2pkit-windows-profile.dll",
            "C:\\CON.txt\\p2pkit-windows-profile.dll", "C:\\CON .txt\\p2pkit-windows-profile.dll",
            "C:\\app\\p2pkit-windows-profile.dll:stream", "C:\\app\\other.dll",
            "C:\\a\u0000\\p2pkit-windows-profile.dll",
            "C:\\" + "a".repeat(260) + "\\p2pkit-windows-profile.dll"}) {
            expect(IllegalArgumentException.class,
                () -> WindowsLibraryLoadInvocation.prepare(INSTALLATION, RUNTIME, FILE, entry, original, invalid));
        }
        expect(IllegalArgumentException.class,
            () -> WindowsLibraryLoadInvocation.prepare(null, RUNTIME, FILE, entry, original, PATH));
        expect(IllegalArgumentException.class,
            () -> WindowsLibraryLoadInvocation.prepare(INSTALLATION, null, FILE, entry, original, PATH));
        expect(IllegalArgumentException.class,
            () -> WindowsLibraryLoadInvocation.prepare(INSTALLATION, RUNTIME, null, entry, original, PATH));
        for (MemorySegment bad : new MemorySegment[] {null, MemorySegment.NULL, MemorySegment.ofArray(new byte[8])}) {
            expect(IllegalArgumentException.class,
                () -> WindowsLibraryLoadInvocation.prepare(INSTALLATION, RUNTIME, FILE, bad, original, PATH));
        }
        try (Arena other = Arena.ofConfined()) {
            expect(IllegalArgumentException.class,
                () -> WindowsLibraryLoadInvocation.prepare(INSTALLATION, RUNTIME, FILE, entry, other, PATH));
        }
        MemorySegment global = stub(Arena.global());
        expect(IllegalArgumentException.class,
            () -> WindowsLibraryLoadInvocation.prepare(INSTALLATION, RUNTIME, FILE, global, Arena.global(), PATH));
        check(callbacks == 0 && staticField("processOwner") == null);
    }

    private static void virtualRefusal(MemorySegment entry, Arena original) throws InterruptedException {
        AtomicReference<Throwable> failure = new AtomicReference<>();
        Thread test = Thread.ofVirtual().start(() -> {
            try { expect(IllegalStateException.class,
                () -> WindowsLibraryLoadInvocation.prepare(INSTALLATION, RUNTIME, FILE, entry, original, PATH)); }
            catch (Throwable caught) { failure.set(caught); }
        });
        test.join(5000);
        check(!test.isAlive());
        if (failure.get() != null) throw new AssertionError(failure.get());
    }

    private static void wrongThreadRefusal(WindowsLibraryLoadInvocation.Result result) throws InterruptedException {
        AtomicReference<Throwable> failure = new AtomicReference<>();
        Thread test = new Thread(() -> {
            try {
                expect(IllegalStateException.class, invocation::invoke);
                expect(IllegalStateException.class, invocation::retireFrame);
                expect(IllegalStateException.class, result::module);
            } catch (Throwable caught) { failure.set(caught); }
        }, "load-invocation-wrong-thread");
        test.start();
        test.join(5000);
        check(!test.isAlive());
        if (failure.get() != null) throw new AssertionError(failure.get());
    }

    private static Object field(String name) throws ReflectiveOperationException {
        Field field = WindowsLibraryLoadInvocation.class.getDeclaredField(name);
        field.setAccessible(true);
        return field.get(invocation);
    }

    private static Object staticField(String name) throws ReflectiveOperationException {
        Field field = WindowsLibraryLoadInvocation.class.getDeclaredField(name);
        field.setAccessible(true);
        return field.get(null);
    }

    private static void setField(String name, Object value) throws ReflectiveOperationException {
        Field field = WindowsLibraryLoadInvocation.class.getDeclaredField(name);
        field.setAccessible(true);
        field.set(invocation, value);
    }

    private static void invoke(Method method, Object receiver, Object... arguments) throws Throwable {
        try { method.invoke(receiver, arguments); }
        catch (InvocationTargetException failure) { throw failure.getCause(); }
    }

    private interface Action { void run() throws Throwable; }

    private static Throwable expect(Class<? extends Throwable> type, Action action) {
        try { action.run(); }
        catch (Throwable caught) {
            if (type.isInstance(caught)) return caught;
            throw new AssertionError("Unexpected load control outcome", caught);
        }
        throw new AssertionError("Expected load control refusal");
    }

    private static void check(boolean condition) {
        if (!condition) throw new AssertionError("Load invocation control failed");
    }
}
