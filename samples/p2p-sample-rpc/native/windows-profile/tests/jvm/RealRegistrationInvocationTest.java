package dev.p2pkit.rpc.windows.loader;

import java.lang.foreign.Arena;
import java.lang.foreign.MemorySegment;
import java.lang.reflect.Field;

/**
 * Test-only connection of the actual dormant FFM call to the statically linked original registrar.
 * The embedding C driver created this development VM and owns its executable/runtime until process exit.
 * Numeric addresses are accepted ONLY at this test boundary, never from a candidate or as load authority.
 * This source is not part of the production adapter, its JAR, or the ordinary model-test source set.
 */
public final class RealRegistrationInvocationTest {
    private RealRegistrationInvocationTest() {}

    private record TestProcessSymbols(Arena scope, MemorySegment registrar, MemorySegment vm) {}

    public static void run(long registrarAddress, long vmAddress, long[] expected, String mode) throws Throwable {
        WindowsLoaderRuntime.requireDiagnosticRuntime();
        check(mode.equals("ffm-success") || mode.equals("ffm-address") || mode.equals("ffm-missing-class"));
        check(registrarAddress > 0 && vmAddress > 0 && expected.length == 23);
        // Deliberate test-only adaptation of the embedding process's own symbols. The C executable
        // and its loaded development runtime outlive these scopes and all registered JNI calls.
        // Do not close the original scopes: the permanent process owner retains them through VM exit.
        Arena originalScope = Arena.ofConfined();
        MemorySegment registrar = MemorySegment.ofAddress(registrarAddress).reinterpret(0, originalScope, null);
        MemorySegment vm = MemorySegment.ofAddress(vmAddress).reinterpret(0, originalScope, null);
        TestProcessSymbols symbols = new TestProcessSymbols(originalScope, registrar, vm);
        Class<?> target = mode.equals("ffm-missing-class") ? RealRegistrationInvocationTest.class :
            Class.forName("dev.p2pkit.sample.rpc.profile.WindowsProfileCustodyJni", false,
                ClassLoader.getSystemClassLoader());
        // These roots describe only test-process lifetime, not installation/module admission.
        WindowsJniRegistrationOwner.Retention roots = new WindowsJniRegistrationOwner.Retention(
            symbols, symbols, symbols, target, expected.clone());
        WindowsJniRegistrationInvocation invocation =
            WindowsJniRegistrationInvocation.prepare(roots, registrar, vm, expected);
        MemorySegment entries = (MemorySegment) field(invocation, "entries");
        MemorySegment output = (MemorySegment) field(invocation, "output");
        check(entries.scope().isAlive() && output.scope().isAlive());
        expect(IllegalStateException.class, invocation::invoke); // Exact owner must precede native entry.
        WindowsJniRegistrationOwner owner;
        if (mode.equals("ffm-success")) {
            owner = WindowsJniRegistrationOwner.registerOnce(roots, invocation);
            check(owner.state() == WindowsJniRegistrationOwner.State.Registered);
        } else {
            WindowsJniRegistrationOwner.Failure failure = (WindowsJniRegistrationOwner.Failure)
                expect(WindowsJniRegistrationOwner.Failure.class,
                    () -> WindowsJniRegistrationOwner.registerOnce(roots, invocation));
            owner = failure.retainedOwner;
            check(owner.state() == WindowsJniRegistrationOwner.State.Failed);
            check(failure.kind == WindowsJniRegistrationOwner.FailureKind.NativeRefusal);
            check(failure.invocationFailure == null && failure.reportFailure == null &&
                failure.retirementFailure == null && failure.controllerFailure == null);
        }
        check(owner == WindowsJniRegistrationOwner.retainedProcessOwner() && owner.retention == roots);
        check(owner.ownsInvocation(invocation));
        WindowsJniRegistrationOwner.Report report = (WindowsJniRegistrationOwner.Report) field(owner, "report");
        int result = mode.equals("ffm-success") ? 0 : (mode.equals("ffm-address") ? 3 : 6);
        int accepted = result == 0 ? 1 : 0;
        int exception = result == 6 ? 1 : 0;
        check(report.equals(new WindowsJniRegistrationOwner.Report(
            32, 1, accepted * 2, result, accepted, exception, exception, 0)));
        check(!entries.scope().isAlive() && !output.scope().isAlive());
        check(registrar.scope().isAlive() && vm.scope().isAlive());
        expect(IllegalStateException.class, invocation::invoke);
        expect(IllegalStateException.class, invocation::readReport);
        expect(IllegalStateException.class, () -> WindowsJniRegistrationOwner.registerOnce(roots, invocation));
        check(owner == WindowsJniRegistrationOwner.retainedProcessOwner());
        check(registrar.scope().isAlive() && vm.scope().isAlive());
        invocation.retireFrame(); // Idempotence applies only to the private, already-retired frame.
    }

    private static Object field(Object owner, String name) throws ReflectiveOperationException {
        Field field = owner.getClass().getDeclaredField(name);
        field.setAccessible(true);
        return field.get(owner);
    }

    private interface Action { void run() throws Throwable; }

    private static Throwable expect(Class<? extends Throwable> type, Action action) {
        try { action.run(); }
        catch (Throwable caught) {
            if (type.isInstance(caught)) return caught;
            throw new AssertionError("Unexpected connected FFM/JNI control outcome", caught);
        }
        throw new AssertionError("Expected connected FFM/JNI refusal");
    }

    private static void check(boolean condition) {
        if (!condition) throw new AssertionError("Connected FFM/JNI contract failed");
    }
}
