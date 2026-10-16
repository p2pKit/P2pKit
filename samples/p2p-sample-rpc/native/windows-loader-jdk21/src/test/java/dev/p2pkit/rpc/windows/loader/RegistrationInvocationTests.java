package dev.p2pkit.rpc.windows.loader;

import java.lang.foreign.Arena;
import java.lang.foreign.Linker;
import java.lang.foreign.MemorySegment;
import java.lang.foreign.ValueLayout;
import java.lang.invoke.MethodHandles;
import java.lang.invoke.MethodType;
import java.lang.reflect.Field;
import java.util.concurrent.atomic.AtomicReference;

/** Real FFM round trips to a JDK-generated inert upcall, never a DLL, JNI runtime or storage entry. */
public final class RegistrationInvocationTests {
    private RegistrationInvocationTests() {}

    private static final WindowsJniRegistrationOwner.Retention ROOTS = new WindowsJniRegistrationOwner.Retention(
        new Object(), new Object(), new Object(), RegistrationInvocationTests.class, new Object());
    private static final long[] EXPECTED = new long[23];
    private static String mode;
    private static WindowsJniRegistrationInvocation invocation;
    private static MemorySegment expectedVm;
    private static Throwable callbackFailure;
    private static int callbacks;

    public static void main(String[] arguments) throws Throwable {
        check(arguments.length == 1);
        mode = arguments[0];
        WindowsLoaderRuntime.requireDiagnosticRuntime();
        for (int index = 0; index < EXPECTED.length; index++) EXPECTED[index] = 4096L + 17L * index;
        Arena vmArena = Arena.ofConfined();
        Arena entryArena = Arena.ofConfined();
        try {
            expectedVm = vmArena.allocate(8, 8); // Inert native data, not an actual JavaVM or permission token.
            MemorySegment entry = stub(entryArena);
            long[] callerAddresses = EXPECTED.clone();
            if (mode.equals("arguments")) invalidArguments(entry);
            if (mode.equals("virtual")) virtualRefusal(entry);
            invocation = WindowsJniRegistrationInvocation.prepare(ROOTS, entry, expectedVm, callerAddresses);
            MemorySegment entries = (MemorySegment) field("entries");
            MemorySegment output = (MemorySegment) field("output");
            check(entries.byteSize() == 184 && output.byteSize() == 32);
            check(((MemorySegment) field("input")).isReadOnly());
            expect(IllegalStateException.class, invocation::invoke); // No process owner yet.
            expect(IllegalStateException.class, invocation::readReport);
            if (mode.equals("snapshot")) {
                for (int index = 0; index < callerAddresses.length; index++) callerAddresses[index] = 999;
            }
            if (mode.equals("thread")) wrongThreadRefusal();
            WindowsJniRegistrationOwner.Invocation selected = invocation;
            WindowsJniRegistrationOwner.FailureKind expectedFailure = null;
            switch (mode) {
                case "success", "snapshot", "arguments", "virtual", "thread", "reentrant" -> {}
                case "refusal" -> expectedFailure = WindowsJniRegistrationOwner.FailureKind.NativeRefusal;
                case "zero-report", "mismatched-result" ->
                    expectedFailure = WindowsJniRegistrationOwner.FailureKind.MalformedReport;
                case "report-clear-failure" -> expectedFailure = WindowsJniRegistrationOwner.FailureKind.FrameRetirement;
                case "closed-entry" -> {
                    entryArena.close();
                    expectedFailure = WindowsJniRegistrationOwner.FailureKind.Invocation;
                }
                case "closed-vm" -> {
                    vmArena.close();
                    expectedFailure = WindowsJniRegistrationOwner.FailureKind.Invocation;
                }
                case "other-invocation" -> {
                    selected = new WindowsJniRegistrationOwner.Invocation() {
                        @Override public int invoke() throws Throwable { return invocation.invoke(); }
                        @Override public WindowsJniRegistrationOwner.Report readReport() { return invocation.readReport(); }
                        @Override public void retireFrame() { invocation.retireFrame(); }
                    };
                    expectedFailure = WindowsJniRegistrationOwner.FailureKind.Invocation;
                }
                default -> throw new AssertionError("Unknown FFM invocation control");
            }
            WindowsJniRegistrationOwner.Invocation registered = selected;
            if (expectedFailure == null) {
                WindowsJniRegistrationOwner owner = WindowsJniRegistrationOwner.registerOnce(ROOTS, registered);
                check(owner.state() == WindowsJniRegistrationOwner.State.Registered && owner.ownsInvocation(invocation));
            } else {
                WindowsJniRegistrationOwner.Failure failure = (WindowsJniRegistrationOwner.Failure)
                    expect(WindowsJniRegistrationOwner.Failure.class,
                        () -> WindowsJniRegistrationOwner.registerOnce(ROOTS, registered));
                check(failure.kind == expectedFailure && failure.retainedOwner.state() == WindowsJniRegistrationOwner.State.Failed);
                if (mode.equals("report-clear-failure")) {
                    WindowsJniRegistrationInvocation.RetirementFailure retirement =
                        (WindowsJniRegistrationInvocation.RetirementFailure) failure.retirementFailure;
                    check(retirement.retainedInvocation == invocation && retirement.entriesClearFailure == null &&
                        retirement.reportClearFailure instanceof UnsupportedOperationException && retirement.arenaCloseFailure == null);
                    check(expect(WindowsJniRegistrationInvocation.RetirementFailure.class, invocation::retireFrame) == retirement);
                }
            }
            if (callbackFailure != null) throw new AssertionError("Inert upcall contract failed", callbackFailure);
            int expectedCalls = mode.startsWith("closed-") || mode.equals("other-invocation") ? 0 : 1;
            check(callbacks == expectedCalls);
            check(!entries.scope().isAlive() && !output.scope().isAlive());
            check(!mode.equals("closed-entry") || !entry.scope().isAlive());
            if (!mode.equals("closed-entry")) check(entry.scope().isAlive());
            if (!mode.equals("closed-vm")) check(expectedVm.scope().isAlive());
            expect(IllegalStateException.class, invocation::invoke);
            expect(IllegalStateException.class, invocation::readReport);
            check(callbacks == expectedCalls);
            if (!mode.equals("report-clear-failure")) invocation.retireFrame();
        } finally {
            // Only inert test scopes are retired, after no callback can still execute. No JNI was registered.
            if (entryArena.scope().isAlive()) entryArena.close();
            if (vmArena.scope().isAlive()) vmArena.close();
        }
        System.out.println("WINDOWS_JNI_FFM_INVOCATION_PASS case=" + mode +
            " scope=JDK_UPCALL_MARSHALING_NOT_WINDOWS_JNI_OR_AUTHORITY");
    }

    private static MemorySegment stub(Arena arena) throws ReflectiveOperationException {
        return Linker.nativeLinker().upcallStub(MethodHandles.lookup().findStatic(RegistrationInvocationTests.class,
            "callback", MethodType.methodType(int.class, MemorySegment.class, MemorySegment.class,
                int.class, MemorySegment.class, int.class)), WindowsJniRegistrationInvocation.DESCRIPTOR, arena);
    }

    private static int callback(MemorySegment vm, MemorySegment entries, int count, MemorySegment report, int bytes) {
        // No Throwable may cross an upcall boundary. Retain it in this test and return an explicit error.
        try {
            callbacks++;
            check(Thread.currentThread() == (Thread) field("thread"));
            check(vm.address() == expectedVm.address() && vm.byteSize() == 0 && count == 23 && bytes == 32);
            check(entries.byteSize() == 184 && report.byteSize() == 32);
            check(entries.address() + 184 <= report.address() || report.address() + 32 <= entries.address());
            for (int index = 0; index < 23; index++) {
                check(entries.getAtIndex(ValueLayout.JAVA_LONG, index) == EXPECTED[index]);
            }
            for (int index = 0; index < 8; index++) check(report.getAtIndex(ValueLayout.JAVA_INT, index) == 0);
            if (mode.equals("reentrant")) {
                expect(IllegalStateException.class, invocation::invoke);
                expect(IllegalStateException.class, invocation::readReport);
                expect(IllegalStateException.class, invocation::retireFrame);
            }
            if (mode.equals("zero-report")) return 0;
            int result = mode.equals("refusal") ? 3 : 0;
            int[] words = {32, 1, result == 0 ? 2 : 0, result, result == 0 ? 1 : 0, 0, 0, 0};
            for (int index = 0; index < words.length; index++) report.setAtIndex(ValueLayout.JAVA_INT, index, words[index]);
            if (mode.equals("report-clear-failure")) {
                // Test-only reflective fault injection, not an extra production hook or escaped native view.
                Field output = WindowsJniRegistrationInvocation.class.getDeclaredField("output");
                output.setAccessible(true);
                output.set(invocation, ((MemorySegment) output.get(invocation)).asReadOnly());
            }
            return mode.equals("mismatched-result") ? 9 : result;
        } catch (Throwable caught) {
            callbackFailure = caught;
            return 9;
        }
    }

    private static void invalidArguments(MemorySegment entry) throws Throwable {
        expect(IllegalArgumentException.class, () -> WindowsJniRegistrationInvocation.prepare(ROOTS, null, expectedVm, EXPECTED));
        expect(IllegalArgumentException.class, () -> WindowsJniRegistrationInvocation.prepare(ROOTS, entry, null, EXPECTED));
        expect(IllegalArgumentException.class, () -> WindowsJniRegistrationInvocation.prepare(ROOTS, entry, MemorySegment.NULL, EXPECTED));
        expect(IllegalArgumentException.class, () -> WindowsJniRegistrationInvocation.prepare(ROOTS,
            MemorySegment.ofArray(new byte[8]), expectedVm, EXPECTED));
        expect(IllegalArgumentException.class, () -> WindowsJniRegistrationInvocation.prepare(ROOTS, entry, expectedVm, null));
        expect(IllegalArgumentException.class, () -> WindowsJniRegistrationInvocation.prepare(ROOTS, entry, expectedVm, new long[22]));
        expect(IllegalArgumentException.class, () -> WindowsJniRegistrationInvocation.prepare(ROOTS, entry, expectedVm, new long[24]));
        for (long invalid : new long[] {0, -1, Long.MIN_VALUE}) {
            long[] addresses = EXPECTED.clone();
            addresses[22] = invalid;
            expect(IllegalArgumentException.class,
                () -> WindowsJniRegistrationInvocation.prepare(ROOTS, entry, expectedVm, addresses));
        }
        MemorySegment globalStub = stub(Arena.global());
        expect(IllegalArgumentException.class,
            () -> WindowsJniRegistrationInvocation.prepare(ROOTS, globalStub, expectedVm, EXPECTED));
        expect(IllegalArgumentException.class,
            () -> WindowsJniRegistrationInvocation.prepare(ROOTS, entry, expectedVm.asSlice(1), EXPECTED));
        check(WindowsJniRegistrationOwner.retainedProcessOwner() == null && callbacks == 0);
    }

    private static void virtualRefusal(MemorySegment entry) throws InterruptedException {
        AtomicReference<Throwable> failure = new AtomicReference<>();
        Thread thread = Thread.ofVirtual().start(() -> {
            try { expect(IllegalStateException.class,
                () -> WindowsJniRegistrationInvocation.prepare(ROOTS, entry, expectedVm, EXPECTED)); }
            catch (Throwable caught) { failure.set(caught); }
        });
        thread.join(5000);
        check(!thread.isAlive());
        if (failure.get() != null) throw new AssertionError(failure.get());
    }

    private static void wrongThreadRefusal() throws InterruptedException {
        AtomicReference<Throwable> failure = new AtomicReference<>();
        Thread thread = new Thread(() -> {
            try {
                expect(IllegalStateException.class, invocation::invoke);
                expect(IllegalStateException.class, invocation::readReport);
                expect(IllegalStateException.class, invocation::retireFrame);
            } catch (Throwable caught) { failure.set(caught); }
        }, "jni-invocation-wrong-thread");
        thread.start();
        thread.join(5000);
        check(!thread.isAlive());
        if (failure.get() != null) throw new AssertionError(failure.get());
    }

    private static Object field(String name) throws ReflectiveOperationException {
        Field field = WindowsJniRegistrationInvocation.class.getDeclaredField(name);
        field.setAccessible(true);
        return field.get(invocation);
    }

    private interface Action { void run() throws Throwable; }

    private static Throwable expect(Class<? extends Throwable> type, Action action) {
        try { action.run(); }
        catch (Throwable caught) {
            if (type.isInstance(caught)) return caught;
            throw new AssertionError("Unexpected control outcome", caught);
        }
        throw new AssertionError("Expected control refusal");
    }

    private static void check(boolean condition) {
        if (!condition) throw new AssertionError("FFM invocation contract failed");
    }
}
