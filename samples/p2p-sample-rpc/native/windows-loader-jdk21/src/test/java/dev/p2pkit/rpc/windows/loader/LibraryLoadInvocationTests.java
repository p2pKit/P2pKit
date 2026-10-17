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
import java.lang.reflect.Constructor;
import java.lang.reflect.Field;
import java.lang.reflect.InvocationTargetException;
import java.lang.reflect.Method;
import java.util.concurrent.atomic.AtomicReference;

/** Inert JDK upcalls only. Windows executes real capture preparation; other hosts reflectively exercise frames. */
public final class LibraryLoadInvocationTests {
    private LibraryLoadInvocationTests() {}

    private static final Object INSTALLATION = new Object();
    private static WindowsOriginalJvmCandidate runtime;
    private static WindowsSystemBootstrapCandidate bootstrap;
    private static MemorySegment pinEntry;
    private static int probes;
    private static final Object FILE = new Object();
    private static final String PATH = "C:\\Program Files\\P2pKit\\app\\p2pkit-windows-profile.dll";
    private static String mode;
    private static boolean windows;
    private static WindowsLibraryLoadInvocation invocation;
    private static MemorySegment expectedModule;
    private static Throwable callbackFailure;
    private static int callbacks;
    private static Arena originalArena;
    private static byte[] expectedFailureState;
    private static final LinkageError RETURN_FAILURE = new LinkageError("private inert post-return failure");
    // Deliberately independent of the production integer-return descriptor: the inert native stub
    // returns a pointer, proving its actual host ABI return register is received as all 64 raw bits.
    private static final FunctionDescriptor POINTER_RETURN = FunctionDescriptor.of(ValueLayout.ADDRESS,
        ValueLayout.ADDRESS.withTargetLayout(WindowsLibraryLoadInvocation.PATH), ValueLayout.ADDRESS,
        ValueLayout.JAVA_INT);

    public static void main(String[] arguments) throws Throwable {
        check(arguments.length == 1);
        mode = arguments[0];
        WindowsLoaderRuntime.requireDiagnosticRuntime();
        windows = Linker.nativeLinker().getClass().getName()
            .equals("jdk.internal.foreign.abi.x64.windows.Windowsx64Linker");
        Arena original = Arena.ofConfined();
        originalArena = original;
        try {
            expectedModule = original.allocate(65_536, 65_536); // Inert storage, not a loaded DLL.
            MemorySegment entry = stub(original);
            createOriginalInertOwners(entry, original);
            if (mode.equals("arguments")) invalidArguments(entry, original);
            if (mode.equals("virtual")) virtualRefusal(entry, original);
            invocation = prepareInert(entry, original);
            check(WindowsLibraryLoadInvocation.DESCRIPTOR.returnLayout().orElseThrow().equals(ValueLayout.JAVA_LONG));
            if (mode.equals("late-scope-close") || mode.equals("return-failure")) {
                MethodHandle actual = (MethodHandle) field("call");
                MethodHandle after = MethodHandles.lookup().findStatic(LibraryLoadInvocationTests.class,
                    "afterNativeReturn", MethodType.methodType(long.class, long.class));
                setField("call", MethodHandles.filterReturnValue(actual, after));
            }
            if (mode.equals("invocation-failure")) {
                MethodHandle failed = MethodHandles.throwException(long.class, LinkageError.class)
                    .bindTo(RETURN_FAILURE);
                setField("call", MethodHandles.dropArguments(failed, 0,
                    MemorySegment.class, MemorySegment.class, MemorySegment.class, int.class));
            }
            if (mode.equals("probe-invocation-failure")) {
                MethodHandle failed = MethodHandles.throwException(int.class, LinkageError.class).bindTo(RETURN_FAILURE);
                setField("pinCall", MethodHandles.dropArguments(failed, 0,
                    MemorySegment.class, int.class, MemorySegment.class, MemorySegment.class));
            }
            if (mode.equals("probe-stale-output")) {
                ((MemorySegment) field("probeModuleBuffer")).set(ValueLayout.JAVA_LONG, 0, expectedModule.address());
            }
            if (mode.equals("probe-foreign-jvm")) set(runtime, "succeeded", false);
            if (mode.equals("probe-substituted-entry")) {
                ((MemorySegment[]) get(bootstrap, "entries"))[1] = entry;
            }
            WindowsLibraryLoadInvocation.Result reserved = (WindowsLibraryLoadInvocation.Result) field("result");
            expect(IllegalStateException.class, reserved::module);
            MemorySegment path = (MemorySegment) field("pathBuffer");
            MemorySegment state = (MemorySegment) field("capturedState");
            byte[] originalPath = path.toArray(ValueLayout.JAVA_BYTE);
            expectedFailureState = state.toArray(ValueLayout.JAVA_BYTE);
            check(path.byteSize() == 520 && state.byteSize() >= 4 && state.byteSize() <= 64);
            check(((MemorySegment) field("pathView")).isReadOnly());
            if (mode.equals("thread")) wrongThreadRefusal(reserved);
            if (mode.equals("closed-entry")) original.close();
            if (mode.equals("retired-frame")) invocation.retireFrame();
            if (mode.startsWith("probe-")) {
                probeRefusal(reserved, path, state);
                printResult();
                return;
            }
            switch (mode) {
                case "success", "arguments", "virtual", "thread", "reentrant", "duplicate", "close-after-result" -> {
                    WindowsLibraryLoadInvocation.Result result = invocation.invoke();
                    check(result == reserved && result.retainedInvocation == invocation);
                    check(result.module().address() == expectedModule.address() && result.module().byteSize() == 0 &&
                        result.module().scope().equals(original.scope()));
                    check((boolean) field("errorObserved") && (boolean) field("nativeReturned") &&
                        (long) field("rawModule") == expectedModule.address());
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
                     "closed-entry", "late-scope-close", "return-failure", "invocation-failure" -> {
                    WindowsLibraryLoadInvocation.Failure failure = (WindowsLibraryLoadInvocation.Failure)
                        expect(WindowsLibraryLoadInvocation.Failure.class, invocation::invoke);
                    check(failure.retainedInvocation == invocation && failure.getCause() == null &&
                        failure.getSuppressed().length == 0);
                    if (mode.equals("closed-entry")) {
                        check(failure.invocationFailure instanceof IllegalStateException &&
                            failure.readbackFailure == null && !failure.retirementFailed());
                        check(!(boolean) field("nativeReturned") && (long) field("rawModule") == 0 && field("module") == null);
                    } else if (unknownReturn()) {
                        check(failure.invocationFailure == RETURN_FAILURE && failure.readbackFailure == null &&
                            !failure.retirementFailed());
                        // Neither a pre-call throw nor a failed return filter gives the invocation proof
                        // of native return. Its complete frame must remain live, not merely its owners.
                        check(!(boolean) field("nativeReturned") && (long) field("rawModule") == 0 && field("module") == null);
                        check(path.scope().isAlive() && state.scope().isAlive());
                        check(java.util.Arrays.equals(originalPath, path.toArray(ValueLayout.JAVA_BYTE)) &&
                            java.util.Arrays.equals(expectedFailureState, state.toArray(ValueLayout.JAVA_BYTE)));
                        check((boolean) field("nativeReturnUnconfirmed") && !(boolean) field("retired"));
                        invocation.retireFrame();
                        invocation.retireFrame();
                        check(path.scope().isAlive() && state.scope().isAlive() &&
                            java.util.Arrays.equals(originalPath, path.toArray(ValueLayout.JAVA_BYTE)) &&
                            java.util.Arrays.equals(expectedFailureState, state.toArray(ValueLayout.JAVA_BYTE)));
                        WindowsLibraryLoadInvocation other = prepareInert(entry, original);
                        expect(IllegalStateException.class, other::invoke);
                        other.retireFrame();
                        check(staticField("processOwner") == invocation && !(boolean) field("succeeded"));
                    } else if (mode.equals("late-scope-close")) {
                        check(failure.invocationFailure == null && failure.readbackFailure instanceof IllegalStateException &&
                            !failure.retirementFailed() && !(boolean) field("errorObserved"));
                        check((boolean) field("nativeReturned") && (long) field("rawModule") == expectedModule.address() &&
                            field("module") == null);
                    } else if (mode.equals("clear-failure")) {
                        check(failure.invocationFailure == null && failure.readbackFailure == null &&
                            failure.pathClearFailure instanceof UnsupportedOperationException &&
                            failure.stateClearFailure == null && failure.arenaCloseFailure == null);
                        check(expect(WindowsLibraryLoadInvocation.Failure.class, invocation::retireFrame) == failure);
                        check(((MemorySegment) field("module")).address() == expectedModule.address() &&
                            (long) field("rawModule") == expectedModule.address() && (boolean) field("nativeReturned"));
                    } else {
                        check(failure.invocationFailure == null && failure.readbackFailure != null &&
                            !failure.retirementFailed());
                        if (!mode.equals("readback-failure")) check((boolean) field("errorObserved"));
                        else check((long) field("rawModule") == expectedModule.address() && field("module") == null);
                        long expectedRaw = mode.equals("null-module") ? 0 : mode.equals("unaligned-module") ?
                            expectedModule.address() + 1 : mode.equals("high-module") ? -65_536L : expectedModule.address();
                        check((boolean) field("nativeReturned") && (long) field("rawModule") == expectedRaw);
                    }
                    expect(IllegalStateException.class, reserved::module);
                }
                default -> throw new AssertionError("Unknown load invocation control");
            }
            check(invocation.installationOwner == INSTALLATION && invocation.runtimeOwner == runtime &&
                invocation.fileOwner == FILE);
            if (callbackFailure != null) throw new AssertionError("Inert load upcall failed", callbackFailure);
            int expectedCalls = mode.equals("closed-entry") || mode.equals("retired-frame") ||
                mode.equals("invocation-failure") ? 0 : 1;
            check(callbacks == expectedCalls && path.scope().isAlive() == unknownReturn() &&
                state.scope().isAlive() == unknownReturn());
            check((boolean) field("nativeReturnUnconfirmed") == unknownReturn());
            if (!mode.equals("closed-entry") && !mode.equals("close-after-result") && !mode.equals("late-scope-close")) {
                check(original.scope().isAlive());
            }
            expect(IllegalStateException.class, invocation::invoke);
            check(callbacks == expectedCalls);
            if (!mode.equals("retired-frame")) check(staticField("processOwner") == invocation);
        } finally {
            // Only this inert fixture retires its original arena after all callbacks return. Unknown-return
            // private frames stay quarantined until process exit. No module was loaded or unloaded.
            if (original.scope().isAlive()) original.close();
        }
        printResult();
    }

    private static void printResult() {
        System.out.println("WINDOWS_LIBRARY_FFM_LOAD_PASS case=" + mode +
            " scope=JDK_UPCALL_MARSHALING_NOT_DLL_LOADING_OR_AUTHORITY capture=" +
            (windows ? "WINDOWS_GET_LAST_ERROR" : "NOT_EXECUTED"));
    }

    private static boolean unknownReturn() {
        return mode.equals("return-failure") || mode.equals("invocation-failure");
    }

    private static WindowsLibraryLoadInvocation prepareInert(MemorySegment entry, Arena original) throws Throwable {
        WindowsLibraryLoadInvocation candidate;
        if (windows) {
            candidate = WindowsLibraryLoadInvocation.prepare(bootstrap, INSTALLATION, runtime, FILE, PATH);
        } else {
            expect(IllegalStateException.class,
                () -> WindowsLibraryLoadInvocation.prepare(bootstrap, INSTALLATION, runtime, FILE, PATH));
            Constructor<WindowsLibraryLoadInvocation> constructor = WindowsLibraryLoadInvocation.class.getDeclaredConstructor(
                WindowsSystemBootstrapCandidate.class, Object.class, WindowsOriginalJvmCandidate.class, Object.class,
                MemorySegment.class, MemorySegment.class, Arena.class, String.class);
            constructor.setAccessible(true);
            candidate = constructor.newInstance(bootstrap, INSTALLATION, runtime, FILE, entry, pinEntry, original, PATH);
            Method prepare = WindowsLibraryLoadInvocation.class.getDeclaredMethod(
                "prepareFrame", MethodHandle.class, MethodHandle.class, MemoryLayout.class, long.class);
            prepare.setAccessible(true);
            MethodHandle plain = Linker.nativeLinker().downcallHandle(entry, WindowsLibraryLoadInvocation.DESCRIPTOR);
            MethodHandle pin = Linker.nativeLinker().downcallHandle(pinEntry, pinDescriptor());
            // Private reflection models the Windows captured state offhost, not a native Windows observation.
            invoke(prepare, candidate, MethodHandles.dropArguments(plain, 0, MemorySegment.class),
                MethodHandles.dropArguments(pin, 0, MemorySegment.class), MemoryLayout.structLayout(ValueLayout.JAVA_INT), 0L);
        }
        MethodHandle pin = (MethodHandle) get(candidate, "pinCall");
        MethodHandle after = MethodHandles.lookup().findStatic(LibraryLoadInvocationTests.class, "afterProbeReturn",
            MethodType.methodType(int.class, int.class));
        set(candidate, "pinCall", MethodHandles.filterReturnValue(pin, after));
        return candidate;
    }

    private static FunctionDescriptor pinDescriptor() {
        return FunctionDescriptor.of(ValueLayout.JAVA_INT, ValueLayout.JAVA_INT,
            ValueLayout.ADDRESS.withTargetLayout(MemoryLayout.sequenceLayout(
                "p2pkit-windows-profile.dll".length() + 1, ValueLayout.JAVA_SHORT)),
            ValueLayout.ADDRESS.withTargetLayout(ValueLayout.JAVA_LONG));
    }

    private static void createOriginalInertOwners(MemorySegment entry, Arena original) throws Throwable {
        Constructor<WindowsSystemBootstrapCandidate> constructor =
            WindowsSystemBootstrapCandidate.class.getDeclaredConstructor(Linker.class);
        constructor.setAccessible(true);
        bootstrap = constructor.newInstance(Linker.nativeLinker());
        set(bootstrap, "originalArena", original);
        set(bootstrap, "succeeded", true);
        set(bootstrap, "frameRetired", true);
        pinEntry = Linker.nativeLinker().upcallStub(MethodHandles.lookup().findStatic(
            LibraryLoadInvocationTests.class, "probeCallback", MethodType.methodType(int.class,
                int.class, MemorySegment.class, MemorySegment.class)), pinDescriptor(), original);
        MemorySegment[] entries = (MemorySegment[]) get(bootstrap, "entries");
        java.util.Arrays.fill(entries, entry);
        entries[1] = pinEntry;
        // Explicit fabricated bootstrap state, no claim that upcall stubs are trusted system functions.
        runtime = new WindowsOriginalJvmCandidate(bootstrap, Linker.nativeLinker(), original, pinEntry, entry, entry);
        set(bootstrap, "originalJvm", runtime);
        MemorySegment acquireEntry = Linker.nativeLinker().upcallStub(MethodHandles.lookup().findStatic(
            LibraryLoadInvocationTests.class, "acquireCallback", MethodType.methodType(int.class,
                MemorySegment.class, int.class, MemorySegment.class)), WindowsJvmAcquisitionInvocation.DESCRIPTOR, original);
        WindowsJvmAcquisitionInvocation acquisition = WindowsJvmAcquisitionInvocation.prepare(runtime, acquireEntry, original);
        set(runtime, "runtimeArena", original);
        set(runtime, "acquisition", acquisition);
        set(runtime, "acquired", acquisition.invoke());
        set(runtime, "succeeded", true);
        set(runtime, "frameRetired", true);
        check(runtime.completed());
    }

    private static int acquireCallback(MemorySegment vms, int count, MemorySegment found) {
        vms.set(ValueLayout.ADDRESS, 0, expectedModule);
        found.set(ValueLayout.JAVA_INT, 0, count);
        return 0;
    }

    private static int probeCallback(int flags, MemorySegment name, MemorySegment output) {
        try {
            probes++;
            check(flags == 1 && staticField("processOwner") == invocation && (boolean) field("attempted"));
            String fixed = "p2pkit-windows-profile.dll";
            check(name.byteSize() == (fixed.length() + 1) * 2L && output.byteSize() == 8);
            for (int index = 0; index <= fixed.length(); index++) {
                check(Short.toUnsignedInt(name.getAtIndex(ValueLayout.JAVA_SHORT, index)) ==
                    (index == fixed.length() ? 0 : fixed.charAt(index)));
            }
            check(output.get(ValueLayout.JAVA_LONG, 0) == 0);
            expect(IllegalStateException.class, invocation::invoke);
            expect(IllegalStateException.class, invocation::retireFrame);
            expect(IllegalStateException.class, ((WindowsLibraryLoadInvocation.Result) field("result"))::module);
            long value = switch (mode) {
                case "probe-present", "probe-false-handle", "probe-return-failure", "probe-error-readback" -> expectedModule.address();
                case "probe-malformed-present" -> -1L;
                default -> 0L;
            };
            output.set(ValueLayout.JAVA_LONG, 0, value);
            return mode.equals("probe-present") || mode.equals("probe-malformed-present") ||
                mode.equals("probe-true-zero") || mode.equals("probe-return-failure") ||
                mode.equals("probe-error-readback") ? 1 : 0;
        } catch (Throwable caught) {
            callbackFailure = caught;
            return 1; // Any upcall failure refuses, never fabricate absence.
        }
    }

    private static int afterProbeReturn(int returned) throws ReflectiveOperationException {
        // Native upcall cannot choose the thread's GetLastError captured AFTER it returns. Set deterministic
        // comparison data here, after the real downcall, in this explicitly inert fixture only.
        ((MemorySegment) field("capturedState")).set(ValueLayout.JAVA_INT, (long) field("errorOffset"),
            mode.equals("probe-wrong-error") ? 5 : 126);
        if (mode.equals("invocation-failure")) {
            expectedFailureState = ((MemorySegment) field("capturedState")).toArray(ValueLayout.JAVA_BYTE);
        }
        if (mode.equals("probe-return-failure")) throw RETURN_FAILURE;
        if (mode.equals("probe-output-readback")) {
            setField("probeModuleBuffer", ((MemorySegment) field("probeModuleBuffer")).asSlice(0, 1));
        }
        if (mode.equals("probe-error-readback")) {
            setField("capturedState", ((MemorySegment) field("capturedState")).asSlice(0, 1));
        }
        return returned;
    }

    private static void probeRefusal(WindowsLibraryLoadInvocation.Result reserved,
                                     MemorySegment path, MemorySegment state) throws Throwable {
        MemorySegment name = (MemorySegment) field("nameBuffer");
        MemorySegment output = (MemorySegment) field("probeModuleBuffer");
        byte[] pathCopy = path.toArray(ValueLayout.JAVA_BYTE);
        byte[] nameCopy = name.toArray(ValueLayout.JAVA_BYTE);
        check(((MemorySegment) field("nameView")).isReadOnly());
        WindowsLibraryLoadInvocation.Failure failure = (WindowsLibraryLoadInvocation.Failure)
            expect(WindowsLibraryLoadInvocation.Failure.class, invocation::invoke);
        check(failure.retainedInvocation == invocation && failure.getCause() == null &&
            failure.getSuppressed().length == 0 && failure.invocationFailure != failure);
        boolean preflight = mode.equals("probe-foreign-jvm") || mode.equals("probe-substituted-entry");
        boolean noCall = preflight || mode.equals("probe-stale-output") || mode.equals("probe-invocation-failure");
        boolean unknown = mode.equals("probe-invocation-failure") || mode.equals("probe-return-failure");
        boolean partial = mode.equals("probe-output-readback") || mode.equals("probe-error-readback");
        boolean retained = unknown || partial;
        check(callbacks == 0 && probes == (noCall ? 0 : 1));
        check(!(boolean) field("nativeReturned") && (long) field("rawModule") == 0 && field("module") == null &&
            !(boolean) field("succeeded") && staticField("processOwner") == invocation);
        check((boolean) field("probeReturned") == (!noCall && !unknown));
        check((boolean) field("nativeReturnUnconfirmed") == unknown &&
            (boolean) field("probeObservationUnconfirmed") == retained);
        check(preflight ? failure.probeFailure == null && failure.invocationFailure != null : failure.probeFailure != null);
        long expectedRaw = mode.equals("probe-present") || mode.equals("probe-false-handle") ||
            mode.equals("probe-error-readback") ? expectedModule.address() : mode.equals("probe-malformed-present") ? -1L : 0L;
        check((long) field("rawPreexistingModule") == expectedRaw);
        if (mode.equals("probe-return-failure")) check(output.get(ValueLayout.JAVA_LONG, 0) == expectedModule.address());
        if (mode.equals("probe-invocation-failure") || mode.equals("probe-return-failure")) {
            check(failure.probeFailure == RETURN_FAILURE);
        }
        for (int repeat = 0; repeat < 2; repeat++) {
            invocation.retireFrame();
            check(path.scope().isAlive() == retained && state.scope().isAlive() == retained &&
                name.scope().isAlive() == retained && output.scope().isAlive() == retained);
            if (retained) check(java.util.Arrays.equals(pathCopy, path.toArray(ValueLayout.JAVA_BYTE)) &&
                java.util.Arrays.equals(nameCopy, name.toArray(ValueLayout.JAVA_BYTE)));
            expect(IllegalStateException.class, invocation::invoke);
            expect(IllegalStateException.class, reserved::module);
        }
        check(originalArena.scope().isAlive() && invocation.runtimeOwner == runtime && invocation.fileOwner == FILE &&
            invocation.installationOwner == INSTALLATION && callbacks == 0);
        if (callbackFailure != null) throw new AssertionError(callbackFailure);
    }

    private static MemorySegment stub(Arena arena) throws ReflectiveOperationException {
        return Linker.nativeLinker().upcallStub(
            MethodHandles.lookup().findStatic(LibraryLoadInvocationTests.class, "callback",
                MethodType.methodType(MemorySegment.class, MemorySegment.class, MemorySegment.class, int.class)),
                POINTER_RETURN, arena);
    }

    private static long afterNativeReturn(long returned) throws ReflectiveOperationException {
        check(returned == expectedModule.address() && callbacks == 1);
        if (mode.equals("return-failure")) {
            expectedFailureState = ((MemorySegment) field("capturedState")).toArray(ValueLayout.JAVA_BYTE);
            throw RETURN_FAILURE;
        }
        // This filter runs after the actual native downcall returns and releases its acquired sessions.
        // Closing an active callback's arena would be refused and would not model a late scope loss.
        originalArena.close();
        return returned;
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
                () -> WindowsLibraryLoadInvocation.prepare(bootstrap, INSTALLATION, runtime, FILE, invalid));
        }
        expect(IllegalArgumentException.class,
            () -> WindowsLibraryLoadInvocation.prepare(bootstrap, null, runtime, FILE, PATH));
        expect(IllegalArgumentException.class,
            () -> WindowsLibraryLoadInvocation.prepare(bootstrap, INSTALLATION, null, FILE, PATH));
        expect(IllegalArgumentException.class,
            () -> WindowsLibraryLoadInvocation.prepare(bootstrap, INSTALLATION, runtime, null, PATH));
        expect(IllegalArgumentException.class,
            () -> WindowsLibraryLoadInvocation.prepare(null, INSTALLATION, runtime, FILE, PATH));
        MemorySegment[] entries = (MemorySegment[]) get(bootstrap, "entries");
        for (MemorySegment bad : new MemorySegment[] {null, MemorySegment.NULL, MemorySegment.ofArray(new byte[8])}) {
            entries[5] = bad;
            expect(IllegalArgumentException.class,
                () -> WindowsLibraryLoadInvocation.prepare(bootstrap, INSTALLATION, runtime, FILE, PATH));
        }
        entries[5] = entry;
        try (Arena other = Arena.ofConfined()) {
            entries[5] = stub(other);
            expect(IllegalArgumentException.class,
                () -> WindowsLibraryLoadInvocation.prepare(bootstrap, INSTALLATION, runtime, FILE, PATH));
        }
        entries[5] = stub(Arena.global());
        expect(IllegalArgumentException.class,
            () -> WindowsLibraryLoadInvocation.prepare(bootstrap, INSTALLATION, runtime, FILE, PATH));
        entries[5] = entry;
        expect(IllegalArgumentException.class, () -> bootstrap.originalLibraryLoadEntry(runtime, 2));
        WindowsOriginalJvmCandidate foreign = new WindowsOriginalJvmCandidate(bootstrap, Linker.nativeLinker(),
            original, pinEntry, entry, entry);
        expect(IllegalStateException.class,
            () -> WindowsLibraryLoadInvocation.prepare(bootstrap, INSTALLATION, foreign, FILE, PATH));
        check(callbacks == 0 && staticField("processOwner") == null);
    }

    private static void virtualRefusal(MemorySegment entry, Arena original) throws InterruptedException {
        AtomicReference<Throwable> failure = new AtomicReference<>();
        Thread test = Thread.ofVirtual().start(() -> {
            try { expect(IllegalStateException.class,
                () -> WindowsLibraryLoadInvocation.prepare(bootstrap, INSTALLATION, runtime, FILE, PATH)); }
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

    private static Object get(Object owner, String name) throws ReflectiveOperationException {
        Field field = owner.getClass().getDeclaredField(name);
        field.setAccessible(true);
        return field.get(owner);
    }

    private static void set(Object owner, String name, Object value) throws ReflectiveOperationException {
        Field field = owner.getClass().getDeclaredField(name);
        field.setAccessible(true);
        field.set(owner, value);
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
