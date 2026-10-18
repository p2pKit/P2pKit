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
import java.util.Arrays;
import java.util.concurrent.atomic.AtomicReference;

/** Fixed production call/retirement gates with inert Java handles, not native bootstrap/completion proof. */
public final class BootstrapReturnTests {
    private static final LinkageError MISSING_RETURN = new LinkageError("inert fixed call did not return");
    private static final long MODULE = 0x180000000L;
    private static final long ENTRY = MODULE + 0x1000;
    private BootstrapReturnTests() {}

    public static void main(String[] arguments) throws Throwable {
        check(arguments.length == 1);
        WindowsLoaderRuntime.requireDiagnosticRuntime();
        String mode = arguments[0];
        if (mode.equals("bootstrap-thread") || mode.equals("jvm-thread")) thread(mode);
        else {
            switch (mode) {
                case "bootstrap-pid-known", "bootstrap-pid-unknown", "bootstrap-system-path-known",
                    "bootstrap-system-path-unknown", "bootstrap-pin-known", "bootstrap-pin-unknown",
                    "bootstrap-module-path-known", "bootstrap-module-path-unknown", "jvm-module-pin-known",
                    "jvm-module-pin-unknown", "jvm-path-known", "jvm-path-unknown", "jvm-resolve-known",
                    "jvm-resolve-unknown", "jvm-provider-pin-known", "jvm-provider-pin-unknown" -> call(mode);
                default -> throw new AssertionError("Unknown fixed-return control");
            }
        }
        System.out.println("WINDOWS_BOOTSTRAP_RETURN_PASS case=" + mode +
            " scope=INERT_FIXED_CALL_RETURN_AND_RETIREMENT_NOT_BOOTSTRAP_OR_NATIVE_COMPLETION");
    }

    private static void thread(String mode) throws Throwable {
        try (Fixture fixture = new Fixture(mode)) {
            byte[][] before = fixture.snapshot();
            AtomicReference<Throwable> observed = new AtomicReference<>();
            Thread other = Thread.startVirtualThread(() -> {
                try { invoke(fixture.owner, "retireFrame"); }
                catch (Throwable caught) { observed.set(caught); }
            });
            other.join();
            check(observed.get() instanceof IllegalStateException);
            check(!(boolean) value(fixture.owner, "frameRetired"));
            fixture.unchanged(before);
            check(fixture.frame.scope().isAlive() && fixture.original.scope().isAlive());
            invoke(fixture.owner, "retireFrame");
            fixture.retired();
        }
    }

    private static void call(String mode) throws Throwable {
        boolean unknown = mode.endsWith("-unknown");
        try (Fixture fixture = new Fixture(mode)) {
            if (unknown) check(expect(LinkageError.class, fixture::invokeCall) == MISSING_RETURN);
            else fixture.invokeCall();
            check(fixture.calls == 1 && (boolean) value(fixture.owner, "nativeReturnUnconfirmed") == unknown);
            check(!(boolean) value(fixture.owner, "succeeded"));
            Object failure = value(fixture.owner, "failure");
            check(value(failure, "retainedCandidate") == fixture.owner);
            byte[][] after = fixture.snapshot();
            if (unknown) {
                expect(IllegalStateException.class, fixture::invokeCall);
                check(fixture.calls == 1);
                invoke(fixture.owner, "retireFrame");
                invoke(fixture.owner, "retireFrame");
                check(!(boolean) value(fixture.owner, "frameRetired") && fixture.frame.scope().isAlive());
                fixture.unchanged(after);
                // A callback ran, but its primitive return was not observed by the original call site.
                if (mode.startsWith("jvm-resolve")) check((long) value(fixture.owner, "rawEntry") == 0);
                if (mode.startsWith("jvm-module-pin")) check((long) value(fixture.owner, "rawModule") == 0);
                if (mode.startsWith("jvm-provider-pin")) check((long) value(fixture.owner, "rawProvider") == 0);
                if (mode.startsWith("bootstrap-pin")) check(((long[]) value(fixture.owner, "rawModules"))[0] == 0);
            } else {
                fixture.primitiveObserved();
                invoke(fixture.owner, "retireFrame");
                fixture.retired();
                expect(IllegalStateException.class, fixture::invokeCall);
                check(fixture.calls == 1);
            }
            check(fixture.original.scope().isAlive() && value(fixture.owner, "failure") == failure);
            check(Arrays.stream((Throwable[]) value(failure, "clearFailures")).allMatch(caught -> caught == null));
            check(value(failure, "arenaCloseFailure") == null);
            // Neither inert frame manipulation nor normal native-shaped return invents startup authority.
            if (fixture.bootstrap) expect(IllegalStateException.class, ((WindowsSystemBootstrapCandidate) fixture.owner)::completed);
            else expect(IllegalStateException.class, ((WindowsOriginalJvmCandidate) fixture.owner)::completed);
        }
    }

    private static final class Fixture implements AutoCloseable {
        final String mode;
        final boolean bootstrap;
        final Arena original = Arena.ofConfined();
        final Arena backing = Arena.ofConfined();
        final Arena frame = Arena.ofConfined();
        final Object owner;
        final MemorySegment[] buffers;
        final MemorySegment[] backingViews;
        final String method;
        int calls;

        Fixture(String mode) throws ReflectiveOperationException {
            this.mode = mode;
            bootstrap = mode.startsWith("bootstrap-");
            if (bootstrap) {
                Constructor<WindowsSystemBootstrapCandidate> constructor =
                    WindowsSystemBootstrapCandidate.class.getDeclaredConstructor(Linker.class);
                constructor.setAccessible(true);
                owner = constructor.newInstance((Object) null);
                field(owner, "originalArena").set(owner, original);
                ((MemorySegment[]) value(owner, "entries"))[0] = MemorySegment.ofAddress(ENTRY).reinterpret(original, null);
                ((MemorySegment[]) value(owner, "modules"))[0] = MemorySegment.ofAddress(MODULE).reinterpret(original, null);
            } else {
                owner = new WindowsOriginalJvmCandidate(null, null, original, null, null, null);
                field(owner, "runtimeArena").set(owner, original);
                field(owner, "module").set(owner, MemorySegment.ofAddress(MODULE).reinterpret(original, null));
                field(owner, "entry").set(owner, MemorySegment.ofAddress(ENTRY).reinterpret(original, null));
            }
            field(owner, "frameArena").set(owner, frame);
            buffers = (MemorySegment[]) value(owner, "buffers");
            backingViews = new MemorySegment[buffers.length];
            for (int index = 0; index < buffers.length; index++) {
                int size = index == 0 ? 8 : index == buffers.length - 1 ? 4 : 2048;
                backingViews[index] = backing.allocate(size, 8);
                backingViews[index].fill((byte) 0x5a);
                buffers[index] = backingViews[index].reinterpret(size, frame, null);
            }
            method = mode.startsWith("bootstrap-pid") ? "callProcessId" : mode.startsWith("bootstrap-system-path") ?
                "callSystemPath" : mode.startsWith("bootstrap-pin") ? "callProviderPin" :
                mode.startsWith("bootstrap-module-path") || mode.startsWith("jvm-path") ? "callModulePath" :
                mode.startsWith("jvm-module-pin") ? "callModulePin" : mode.startsWith("jvm-resolve") ?
                "callResolve" : "callProviderPin";
            if (!mode.endsWith("-thread")) prepareCall();
        }

        private void prepareCall() throws ReflectiveOperationException {
            String handleField;
            String callback;
            MethodType type;
            if (method.equals("callProcessId")) {
                handleField = "pidCall"; callback = "pid";
                type = MethodType.methodType(int.class, MemorySegment.class);
            } else if (method.equals("callSystemPath")) {
                handleField = "systemPathCall"; callback = "systemPath";
                type = MethodType.methodType(int.class, MemorySegment.class, MemorySegment.class, int.class);
            } else if (method.equals("callModulePath")) {
                handleField = bootstrap ? "modulePathCall" : "pathCall"; callback = "modulePath";
                type = MethodType.methodType(int.class, MemorySegment.class, MemorySegment.class, MemorySegment.class, int.class);
            } else if (method.equals("callResolve")) {
                handleField = "resolveCall"; callback = "resolve";
                type = MethodType.methodType(long.class, MemorySegment.class, MemorySegment.class, MemorySegment.class);
            } else {
                handleField = "pinCall"; callback = "pin";
                type = MethodType.methodType(int.class, MemorySegment.class, int.class, MemorySegment.class, MemorySegment.class);
            }
            MethodHandle handle = MethodHandles.lookup().findVirtual(Fixture.class, callback, type).bindTo(this);
            Class<?> result = type.returnType();
            MethodHandle returned = MethodHandles.lookup().findVirtual(Fixture.class,
                result == long.class ? "returnedLong" : "returnedInt", MethodType.methodType(result, result)).bindTo(this);
            field(owner, handleField).set(owner, MethodHandles.filterReturnValue(handle, returned));
        }

        void invokeCall() throws Throwable {
            if (bootstrap && (method.equals("callProviderPin") || method.equals("callModulePath"))) {
                invoke(owner, method, new Class<?>[] {int.class}, 0);
            } else invoke(owner, method);
        }

        private void entered(MemorySegment error) throws Throwable {
            calls++;
            check(calls == 1 && error == buffers[buffers.length - 1]);
            check((boolean) value(owner, "nativeReturnUnconfirmed"));
            expect(IllegalStateException.class, this::invokeCall);
            check(calls == 1);
            error.set(ValueLayout.JAVA_INT, 0, 126);
        }
        private int pid(MemorySegment error) throws Throwable { entered(error); return 17; }
        private int systemPath(MemorySegment error, MemorySegment output, int count) throws Throwable {
            entered(error); check(output == buffers[2] && count == 1024);
            output.set(ValueLayout.JAVA_SHORT, 0, (short) 'C'); return 1;
        }
        private int modulePath(MemorySegment error, MemorySegment module, MemorySegment output, int count) throws Throwable {
            entered(error); check(module.address() == MODULE && output == buffers[1] && count == 1024);
            output.set(ValueLayout.JAVA_SHORT, 0, (short) 'C'); return 1;
        }
        private int pin(MemorySegment error, int flags, MemorySegment target, MemorySegment output) throws Throwable {
            entered(error); check(output == buffers[0]);
            if (method.equals("callModulePin")) check(flags == 1 && target == buffers[2]);
            else check(flags == 5 && target.address() == ENTRY);
            output.set(ValueLayout.JAVA_LONG, 0, MODULE); return 1;
        }
        private long resolve(MemorySegment error, MemorySegment module, MemorySegment name) throws Throwable {
            entered(error); check(module.address() == MODULE && name == buffers[3]); return ENTRY;
        }
        private int returnedInt(int value) { if (mode.endsWith("-unknown")) throw MISSING_RETURN; return value; }
        private long returnedLong(long value) { if (mode.endsWith("-unknown")) throw MISSING_RETURN; return value; }

        void primitiveObserved() throws ReflectiveOperationException {
            switch (method) {
                case "callProcessId" -> check((int) value(owner, "pidReturn") == 17);
                case "callSystemPath" -> check((int) value(owner, "systemPathReturn") == 1);
                case "callModulePath" -> check(bootstrap ? ((int[]) value(owner, "pathReturns"))[0] == 1 :
                    (int) value(owner, "modulePathReturn") == 1);
                case "callModulePin" -> check((int) value(owner, "modulePinReturn") == 1 && (long) value(owner, "rawModule") == MODULE &&
                    value(owner, "returnedModule") == null);
                case "callResolve" -> check((long) value(owner, "rawEntry") == ENTRY && value(owner, "returnedEntry") == null);
                case "callProviderPin" -> {
                    if (bootstrap) check(((int[]) value(owner, "pinReturns"))[0] == 1 && ((long[]) value(owner, "rawModules"))[0] == MODULE);
                    else check((int) value(owner, "providerPinReturn") == 1 && (long) value(owner, "rawProvider") == MODULE &&
                        value(owner, "returnedProvider") == null);
                }
                default -> throw new AssertionError("Unknown primitive observation");
            }
        }
        byte[][] snapshot() {
            byte[][] result = new byte[buffers.length][];
            for (int index = 0; index < buffers.length; index++) result[index] = backingViews[index].toArray(ValueLayout.JAVA_BYTE);
            return result;
        }
        void unchanged(byte[][] expected) {
            for (int index = 0; index < buffers.length; index++) {
                check(Arrays.equals(expected[index], backingViews[index].toArray(ValueLayout.JAVA_BYTE)));
            }
        }
        void retired() throws ReflectiveOperationException {
            check((boolean) value(owner, "frameRetired") && !frame.scope().isAlive() && original.scope().isAlive());
            for (MemorySegment backingView : backingViews) {
                for (byte value : backingView.toArray(ValueLayout.JAVA_BYTE)) check(value == 0);
            }
        }
        @Override public void close() {
            // Only synchronous test-owned Java callbacks were invoked. Never retire real unknown native work.
            if (frame.scope().isAlive()) frame.close();
            backing.close(); original.close();
        }
    }

    private static Field field(Object owner, String name) throws ReflectiveOperationException {
        Field field = owner.getClass().getDeclaredField(name); field.setAccessible(true); return field;
    }
    private static Object value(Object owner, String name) throws ReflectiveOperationException { return field(owner, name).get(owner); }
    private static Object invoke(Object owner, String name) throws Throwable { return invoke(owner, name, new Class<?>[0]); }
    private static Object invoke(Object owner, String name, Class<?>[] types, Object... arguments) throws Throwable {
        Method method = owner.getClass().getDeclaredMethod(name, types); method.setAccessible(true);
        try { return method.invoke(owner, arguments); }
        catch (InvocationTargetException failure) { throw failure.getCause(); }
    }
    private interface Action { void run() throws Throwable; }
    private static Throwable expect(Class<? extends Throwable> type, Action action) {
        try { action.run(); }
        catch (Throwable caught) {
            if (type.isInstance(caught)) return caught;
            throw new AssertionError("Unexpected fixed-return control failure", caught);
        }
        throw new AssertionError("Expected fixed-return refusal");
    }
    private static void check(boolean condition) { if (!condition) throw new AssertionError("Fixed-return control failed"); }
}
