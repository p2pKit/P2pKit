package dev.p2pkit.rpc.windows.loader;

import java.lang.foreign.Arena;
import java.lang.foreign.Linker;
import java.lang.foreign.MemorySegment;
import java.lang.foreign.ValueLayout;
import java.lang.invoke.MethodHandles;
import java.lang.invoke.MethodType;
import java.lang.reflect.Field;
import java.util.concurrent.atomic.AtomicReference;

/** Fixed JNI_GetCreatedJavaVMs-shaped FFM round trips to inert JDK upcalls, NOT actual VM lookup. */
public final class VmAcquisitionInvocationTests {
    private VmAcquisitionInvocationTests() {}

    private static final Object RUNTIME_OWNER = new Object();
    private static String mode;
    private static WindowsJvmAcquisitionInvocation invocation;
    private static MemorySegment expectedVm;
    private static Throwable callbackFailure;
    private static int callbacks;

    public static void main(String[] arguments) throws Throwable {
        check(arguments.length == 1);
        mode = arguments[0];
        WindowsLoaderRuntime.requireDiagnosticRuntime();
        Arena runtimeArena = Arena.ofConfined();
        try {
            expectedVm = runtimeArena.allocate(8, 8); // Inert data, never interpreted as a real JavaVM.
            MemorySegment entry = stub(runtimeArena);
            if (mode.equals("arguments")) invalidArguments(entry, runtimeArena);
            if (mode.equals("virtual")) virtualRefusal(entry, runtimeArena);
            invocation = WindowsJvmAcquisitionInvocation.prepare(RUNTIME_OWNER, entry, runtimeArena);
            if (mode.equals("partial-frame-alias")) {
                // A real 4-byte-aligned count buffer need not be 8-byte aligned. Force that valid placement.
                Arena frame = (Arena) field("frameArena");
                Field count = WindowsJvmAcquisitionInvocation.class.getDeclaredField("countBuffer");
                count.setAccessible(true);
                count.set(invocation, frame.allocate(12, 8).asSlice(4, 4));
            }
            WindowsJvmAcquisitionInvocation.Result reserved =
                (WindowsJvmAcquisitionInvocation.Result) field("result");
            expect(IllegalStateException.class, reserved::virtualMachine);
            MemorySegment vmBuffer = (MemorySegment) field("vmBuffer");
            MemorySegment countBuffer = (MemorySegment) field("countBuffer");
            check(vmBuffer.byteSize() == 8 && countBuffer.byteSize() == 4);
            if (mode.equals("thread")) wrongThreadRefusal(reserved);
            if (mode.equals("closed-entry")) runtimeArena.close();
            if (mode.equals("retired-frame")) invocation.retireFrame();
            switch (mode) {
                case "success", "arguments", "virtual", "thread", "reentrant", "close-after-result" -> {
                    WindowsJvmAcquisitionInvocation.Result result = invocation.invoke();
                    check(result == reserved && result.retainedInvocation == invocation &&
                        result.retainedInvocation.runtimeOwner == RUNTIME_OWNER);
                    MemorySegment observed = result.virtualMachine();
                    check(observed.byteSize() == 0 && observed.address() == expectedVm.address() &&
                        observed.scope().equals(runtimeArena.scope()) && observed.scope().isAlive());
                    check(!vmBuffer.scope().isAlive() && !countBuffer.scope().isAlive());
                    System.gc(); // A request, not a guarantee: the result still retains original owners.
                    check(result.virtualMachine().address() == expectedVm.address());
                    if (mode.equals("close-after-result")) {
                        runtimeArena.close();
                        check(!observed.scope().isAlive());
                        expect(IllegalStateException.class, result::virtualMachine);
                    }
                    invocation.retireFrame();
                }
                case "retired-frame" -> expect(IllegalStateException.class, invocation::invoke);
                case "status", "zero-count", "multiple-count", "negative-count", "null-vm", "unaligned-vm",
                     "high-vm", "frame-alias", "partial-frame-alias", "clear-failure", "count-clear-failure", "readback-cleanup",
                     "closed-entry" -> {
                    WindowsJvmAcquisitionInvocation.Failure failure =
                        (WindowsJvmAcquisitionInvocation.Failure)
                            expect(WindowsJvmAcquisitionInvocation.Failure.class, invocation::invoke);
                    check(failure.retainedInvocation == invocation && failure.getCause() == null &&
                        failure.getSuppressed().length == 0 && invocation.runtimeOwner == RUNTIME_OWNER);
                    if (mode.equals("closed-entry")) {
                        check(failure.invocationFailure instanceof IllegalStateException &&
                            failure.readbackFailure == null && !failure.retirementFailed());
                    } else if (mode.equals("clear-failure") || mode.equals("readback-cleanup")) {
                        check(failure.invocationFailure == null &&
                            (mode.equals("readback-cleanup") ? failure.readbackFailure instanceof IllegalStateException :
                                failure.readbackFailure == null) &&
                            failure.vmClearFailure instanceof UnsupportedOperationException &&
                            failure.countClearFailure == null && failure.arenaCloseFailure == null);
                        check(expect(WindowsJvmAcquisitionInvocation.Failure.class, invocation::retireFrame) == failure);
                    } else if (mode.equals("count-clear-failure")) {
                        check(failure.invocationFailure == null && failure.readbackFailure == null &&
                            failure.vmClearFailure == null &&
                            failure.countClearFailure instanceof UnsupportedOperationException &&
                            failure.arenaCloseFailure == null);
                        check(expect(WindowsJvmAcquisitionInvocation.Failure.class, invocation::retireFrame) == failure);
                    } else {
                        check(failure.invocationFailure == null && failure.readbackFailure instanceof IllegalStateException &&
                            !failure.retirementFailed());
                    }
                    expect(IllegalStateException.class, reserved::virtualMachine);
                }
                default -> throw new AssertionError("Unknown original JVM invocation control");
            }
            if (callbackFailure != null) throw new AssertionError("Inert JVM upcall contract failed", callbackFailure);
            int expectedCalls = mode.equals("closed-entry") || mode.equals("retired-frame") ? 0 : 1;
            check(callbacks == expectedCalls && !vmBuffer.scope().isAlive() && !countBuffer.scope().isAlive());
            if (!mode.equals("closed-entry") && !mode.equals("close-after-result")) {
                check(runtimeArena.scope().isAlive() && entry.scope().isAlive() && expectedVm.scope().isAlive());
            }
            expect(IllegalStateException.class, invocation::invoke);
            check(callbacks == expectedCalls);
        } finally {
            // Only the test owns these inert arenas; production invocation never closes runtime ownership.
            if (runtimeArena.scope().isAlive()) runtimeArena.close();
        }
        System.out.println("WINDOWS_JVM_FFM_ACQUISITION_PASS case=" + mode +
            " scope=JDK_UPCALL_MARSHALING_NOT_VM_LOOKUP_OR_AUTHORITY");
    }

    private static MemorySegment stub(Arena arena) throws ReflectiveOperationException {
        return Linker.nativeLinker().upcallStub(MethodHandles.lookup().findStatic(VmAcquisitionInvocationTests.class,
            "callback", MethodType.methodType(int.class, MemorySegment.class, int.class, MemorySegment.class)),
            WindowsJvmAcquisitionInvocation.DESCRIPTOR, arena);
    }

    private static int callback(MemorySegment vms, int length, MemorySegment count) {
        // No throwable may escape an upcall; report test faults only after the native-shaped call returns.
        try {
            callbacks++;
            check(Thread.currentThread() == field("thread") && length == 1 &&
                vms.byteSize() == 8 && count.byteSize() == 4);
            check(vms.address() + 8 <= count.address() || count.address() + 4 <= vms.address());
            check(vms.get(ValueLayout.ADDRESS, 0).address() == 0 && count.get(ValueLayout.JAVA_INT, 0) == 0);
            if (mode.equals("reentrant")) {
                expect(IllegalStateException.class, invocation::invoke);
                expect(IllegalStateException.class, invocation::retireFrame);
                expect(IllegalStateException.class,
                    ((WindowsJvmAcquisitionInvocation.Result) field("result"))::virtualMachine);
            }
            int number = switch (mode) {
                case "zero-count", "readback-cleanup" -> 0;
                case "multiple-count" -> 2;
                case "negative-count" -> -1;
                default -> 1;
            };
            count.set(ValueLayout.JAVA_INT, 0, number);
            MemorySegment returned = switch (mode) {
                case "null-vm" -> MemorySegment.NULL;
                case "unaligned-vm" -> expectedVm.asSlice(1);
                case "high-vm" -> MemorySegment.ofAddress(Long.MIN_VALUE); // Inert malformed return; never dereferenced.
                case "frame-alias" -> vms;
                // The pointer starts outside the count buffer but its first 8-byte VM word overlaps it.
                case "partial-frame-alias" -> MemorySegment.ofAddress(count.address() - 4);
                default -> expectedVm;
            };
            vms.set(ValueLayout.ADDRESS, 0, returned);
            if (mode.equals("clear-failure") || mode.equals("readback-cleanup") || mode.equals("count-clear-failure")) {
                Field buffer = WindowsJvmAcquisitionInvocation.class.getDeclaredField(
                    mode.equals("count-clear-failure") ? "countBuffer" : "vmBuffer");
                buffer.setAccessible(true);
                buffer.set(invocation, ((MemorySegment) buffer.get(invocation)).asReadOnly());
            }
            return mode.equals("status") ? -1 : 0;
        } catch (Throwable caught) {
            callbackFailure = caught;
            return -1;
        }
    }

    private static void invalidArguments(MemorySegment entry, Arena arena) throws Throwable {
        expect(IllegalArgumentException.class, () -> WindowsJvmAcquisitionInvocation.prepare(null, entry, arena));
        expect(IllegalArgumentException.class, () -> WindowsJvmAcquisitionInvocation.prepare(RUNTIME_OWNER, null, arena));
        expect(IllegalArgumentException.class, () -> WindowsJvmAcquisitionInvocation.prepare(RUNTIME_OWNER, entry, null));
        expect(IllegalArgumentException.class,
            () -> WindowsJvmAcquisitionInvocation.prepare(RUNTIME_OWNER, MemorySegment.NULL, arena));
        expect(IllegalArgumentException.class, () -> WindowsJvmAcquisitionInvocation.prepare(
            RUNTIME_OWNER, MemorySegment.ofArray(new byte[8]), arena));
        try (Arena other = Arena.ofConfined()) {
            expect(IllegalArgumentException.class,
                () -> WindowsJvmAcquisitionInvocation.prepare(RUNTIME_OWNER, entry, other));
        }
        MemorySegment globalEntry = stub(Arena.global());
        expect(IllegalArgumentException.class,
            () -> WindowsJvmAcquisitionInvocation.prepare(RUNTIME_OWNER, globalEntry, Arena.global()));
        check(callbacks == 0);
    }

    private static void virtualRefusal(MemorySegment entry, Arena arena) throws InterruptedException {
        AtomicReference<Throwable> failure = new AtomicReference<>();
        Thread other = Thread.ofVirtual().start(() -> {
            try {
                expect(IllegalStateException.class,
                    () -> WindowsJvmAcquisitionInvocation.prepare(RUNTIME_OWNER, entry, arena));
            } catch (Throwable caught) { failure.set(caught); }
        });
        other.join(5000);
        check(!other.isAlive());
        if (failure.get() != null) throw new AssertionError(failure.get());
    }

    private static void wrongThreadRefusal(WindowsJvmAcquisitionInvocation.Result result) throws InterruptedException {
        AtomicReference<Throwable> failure = new AtomicReference<>();
        Thread other = new Thread(() -> {
            try {
                expect(IllegalStateException.class, invocation::invoke);
                expect(IllegalStateException.class, invocation::retireFrame);
                expect(IllegalStateException.class, result::virtualMachine);
            } catch (Throwable caught) { failure.set(caught); }
        }, "jvm-acquisition-wrong-thread");
        other.start();
        other.join(5000);
        check(!other.isAlive());
        if (failure.get() != null) throw new AssertionError(failure.get());
    }

    private static Object field(String name) throws ReflectiveOperationException {
        Field field = WindowsJvmAcquisitionInvocation.class.getDeclaredField(name);
        field.setAccessible(true);
        return field.get(invocation);
    }

    private interface Action { void run() throws Throwable; }

    private static Throwable expect(Class<? extends Throwable> type, Action action) {
        try { action.run(); }
        catch (Throwable caught) {
            if (type.isInstance(caught)) return caught;
            throw new AssertionError("Unexpected original JVM control outcome", caught);
        }
        throw new AssertionError("Expected original JVM control refusal");
    }

    private static void check(boolean condition) {
        if (!condition) throw new AssertionError("Original JVM invocation contract failed");
    }
}
