package dev.p2pkit.rpc.windows.loader;

import java.lang.foreign.Arena;
import java.lang.foreign.Linker;
import java.lang.foreign.MemorySegment;
import java.lang.foreign.ValueLayout;
import java.lang.invoke.MethodHandles;
import java.lang.invoke.MethodType;
import java.util.Arrays;
import java.util.Map;
import java.util.concurrent.atomic.AtomicReference;

import static dev.p2pkit.rpc.windows.loader.OriginalFileBytesLeaseTests.check;
import static dev.p2pkit.rpc.windows.loader.OriginalFileBytesLeaseTests.expect;
import static dev.p2pkit.rpc.windows.loader.OriginalFileBytesLeaseTests.field;
import static dev.p2pkit.rpc.windows.loader.OriginalFileBytesLeaseTests.invoke;
import static dev.p2pkit.rpc.windows.loader.OriginalFileBytesLeaseTests.value;

/** Inert original owners and fixed-call Java handles. No actual process namespace or OS call. */
public final class OriginalApiSetTests {
    private static final long PEB = 0x62000000L, MAP = 0x63000000L;
    private static final String CONTRACT = "api-ms-win-core-example-l1-1-0.dll";
    private static final LinkageError UNKNOWN = new LinkageError("Synthetic unconfirmed native return");
    private OriginalApiSetTests() {}

    public static void main(String[] args) throws Throwable {
        WindowsLoaderRuntime.requireDiagnosticRuntime();
        String mode = args[0];
        if (mode.equals("owner-refusal")) {
            WindowsOriginalApiSetCandidate empty = new WindowsOriginalApiSetCandidate(null);
            expect(IllegalStateException.class, empty::observe);
            check(!(boolean) value(empty, "attempted") && value(empty, "frame") == null);
        } else if (mode.equals("header-bounds")) headerBounds();
        else if (mode.equals("region-bounds")) regionBounds();
        else try (Fixture fixture = new Fixture(mode)) {
            if (mode.equals("owner-substitution")) {
                WindowsOriginalApiSetCandidate other = new WindowsOriginalApiSetCandidate(fixture.core.collection);
                expect(IllegalStateException.class, other::observe);
                check(!(boolean) value(other, "attempted"));
            } else if (mode.equals("thread")) {
                AtomicReference<Throwable> caught = new AtomicReference<>();
                Thread test = Thread.startVirtualThread(() -> {
                    try { expect(IllegalStateException.class, fixture.candidate::finishRoutes); }
                    catch (Throwable failure) { caught.set(failure); }
                });
                test.join(); check(caught.get() == null && fixture.calls == 0);
            } else if (mode.startsWith("process-")) process(fixture);
            else if (mode.startsWith("query-export-")) queryExport(fixture);
            else if (mode.startsWith("read-")) read(fixture);
            else if (mode.startsWith("route-")) route(fixture);
            else if (mode.startsWith("finish-")) finish(fixture);
            else if (mode.equals("owner-scope")) {
                fixture.core.moduleScope.close();
                expect(IllegalStateException.class, fixture.candidate::finishRoutes);
                check(fixture.calls == 0);
            } else if (mode.equals("sealed-required")) {
                expect(IllegalStateException.class, fixture.core.collection::requireSealedApiSetRoutes);
                fixture.candidate.finishRoutes();
                fixture.core.collection.requireSealedApiSetRoutes();
                expect(IllegalStateException.class, fixture.candidate::finishRoutes);
            } else throw new AssertionError("Unknown API-set owner control");
        }
        System.out.println("ORIGINAL_API_SET_MODEL_PASS");
    }

    private static void headerBounds() {
        byte[] data = Arrays.copyOf(ApiSetPlanTests.namespaceData(), 28);
        check(WindowsOriginalApiSetCandidate.checkedHeader(data) == 8192);
        for (int[] change : new int[][] {{0, 5}, {0, 7}, {4, 0}, {4, -1}, {4, 2097153}, {8, 1}}) {
            byte[] image = data.clone(); put(image, change[0], change[1], 4);
            expect(IllegalStateException.class, () -> WindowsOriginalApiSetCandidate.checkedHeader(image));
        }
        expect(IllegalStateException.class, () -> WindowsOriginalApiSetCandidate.checkedHeader(null));
    }

    private static void regionBounds() {
        byte[] good = region();
        WindowsOriginalApiSetCandidate.requireRegion(good, MAP, 8192);
        for (int[] change : new int[][] {{0, 4096}, {8, 4096}, {16, 4}, {20, 1}, {24, 4096},
            {24, 8193}, {32, 0x2000}, {36, 4}, {36, 0x102}, {40, 0x20000}, {40, 0x1000000}}) {
            byte[] image = good.clone(); put(image, change[0], change[1], 4);
            expect(IllegalStateException.class, () -> WindowsOriginalApiSetCandidate.requireRegion(image, MAP, 8192));
        }
        expect(IllegalStateException.class, () -> WindowsOriginalApiSetCandidate.requireRegion(good, MAP + 1, 8192));
        expect(IllegalStateException.class, () -> WindowsOriginalApiSetCandidate.requireRegion(good, MAP, -1));
    }

    private static void process(Fixture fixture) throws Throwable {
        boolean success = fixture.mode.equals("process-success");
        if (success) {
            invoke(fixture.candidate, "queryProcess");
            check((long) value(fixture.candidate, "peb") == PEB);
        } else {
            expect(fixture.mode.equals("process-unknown") ? LinkageError.class : IllegalStateException.class,
                () -> invoke(fixture.candidate, "queryProcess"));
        }
        check(fixture.calls == 1);
        unknownRetirement(fixture, fixture.mode.equals("process-unknown"));
    }

    private static void queryExport(Fixture fixture) throws Throwable {
        boolean success = fixture.mode.equals("query-export-success");
        boolean unknown = fixture.mode.equals("query-export-unknown") || fixture.mode.equals("query-export-pin-unknown");
        if (success) {
            invoke(fixture.candidate, "resolveQuery");
            check(value(fixture.candidate, "queryCall") != null);
            check((long) value(fixture.candidate, "rawQueryProvider") == fixture.core.modules[2].originalModuleBits());
        } else {
            expect(unknown ? LinkageError.class : IllegalStateException.class, () -> invoke(fixture.candidate, "resolveQuery"));
        }
        check(fixture.calls == (fixture.mode.equals("query-export-wrong") || fixture.mode.equals("query-export-unknown") ? 1 : 2));
        unknownRetirement(fixture, unknown);
    }

    private static void read(Fixture fixture) throws Throwable {
        if (fixture.mode.equals("read-success")) {
            check((long) invoke(fixture.candidate, "readNamespacePointer") == MAP);
        } else {
            expect(fixture.mode.equals("read-unknown") ? LinkageError.class : IllegalStateException.class,
                () -> invoke(fixture.candidate, "readNamespacePointer"));
        }
        check(fixture.calls == 1);
        unknownRetirement(fixture, fixture.mode.equals("read-unknown"));
    }

    private static void route(Fixture fixture) throws Throwable {
        WindowsSystemExportPlan.ApiRoute route = new WindowsSystemExportPlan.ApiRoute(CONTRACT,
            fixture.mode.equals("route-outside") ? "elsewhere.dll" : "kernelbase.dll");
        if (fixture.mode.equals("route-success")) {
            for (int call = 0; call < 2; call++) {
                invoke(fixture.candidate, "observeRoute", new Class<?>[] {WindowsSystemExportPlan.ApiRoute.class}, route);
            }
            check(fixture.calls == 1 && (int) value(fixture.candidate, "routeCount") == 1);
            check(((long[]) value(fixture.candidate, "rawRouteModules"))[0] == fixture.core.modules[5].originalModuleBits());
            fixture.candidate.finishRoutes();
            fixture.candidate.requireSealed();
            check(!fixture.frame.scope().isAlive() && fixture.core.moduleScope.scope().isAlive());
        } else {
            expect(fixture.mode.equals("route-unknown") ? LinkageError.class : IllegalStateException.class,
                () -> invoke(fixture.candidate, "observeRoute", new Class<?>[] {WindowsSystemExportPlan.ApiRoute.class}, route));
            check(fixture.calls == (fixture.mode.equals("route-outside") ? 0 : 1));
            unknownRetirement(fixture, fixture.mode.equals("route-unknown"));
        }
    }

    private static void finish(Fixture fixture) throws Throwable {
        Throwable failure = expect(WindowsOriginalApiSetCandidate.Failure.class, fixture.candidate::finishRoutes);
        check(((WindowsOriginalApiSetCandidate.Failure) failure).retainedCandidate == fixture.candidate);
        check(expect(WindowsOriginalApiSetCandidate.Failure.class, fixture.candidate::finishRoutes) == failure);
        expect(WindowsOriginalApiSetCandidate.Failure.class, fixture.candidate::requireSealed);
        check(!fixture.frame.scope().isAlive());
    }

    private static void unknownRetirement(Fixture fixture, boolean unknown) throws Throwable {
        check((boolean) value(fixture.candidate, "nativeReturnUnconfirmed") == unknown);
        byte[] before = fixture.buffers[6].toArray(ValueLayout.JAVA_BYTE);
        invoke(fixture.candidate, "retireFrame");
        check(fixture.frame.scope().isAlive() == unknown);
        if (unknown) {
            check(Arrays.equals(before, fixture.buffers[6].toArray(ValueLayout.JAVA_BYTE)));
            check(fixture.candidate.failureOperation().equals("API_SET_RETURN_UNKNOWN"));
        }
        check(fixture.core.moduleScope.scope().isAlive());
    }

    private static final class Fixture implements AutoCloseable {
        final OriginalSystemModulesTests.Fixture core = new OriginalSystemModulesTests.Fixture("pin-success");
        final Arena frame = Arena.ofConfined();
        final WindowsOriginalApiSetCandidate candidate;
        final MemorySegment[] buffers;
        final byte[] namespace;
        final String mode;
        int calls;

        Fixture(String mode) throws Throwable {
            this.mode = mode;
            namespace = mode.equals("route-outside") ? ApiSetPlanTests.namespaceWithHost("elsewhere.dll") : ApiSetPlanTests.namespaceData();
            core.pinAll();
            WindowsSystemExportPlan.Input[] inputs = new WindowsSystemExportPlan.Input[8];
            for (int slot = 0; slot < 8; slot++) {
                byte[] image = SystemExportPlanTests.image(WindowsOriginalSystemModulesCandidate.fixedName(slot),
                    1, new long[] {0x1000}, new String[] {"Target"}, new int[] {0}, Map.of());
                WindowsOriginalSystemModuleCandidate module = core.modules[slot];
                core.attachFile(slot, image.length, 2);
                core.attachSecurity(slot, true);
                core.attachAncestors(slot, true);
                field(module, "bytesAttempted").setBoolean(module, true);
                WindowsOriginalFileBytesLease bytes = core.file.newSystemModuleBytes(module);
                field(module, "bytes").set(module, bytes);
                for (String name : new String[] {"attempted", "streamAttempted", "frameRetired", "succeeded"}) field(bytes, name).setBoolean(bytes, true);
                field(bytes, "total").setLong(bytes, image.length);
                field(bytes, "originalSnapshot").set(bytes, image);
                field(bytes, "observedDigest").set(bytes, java.security.MessageDigest.getInstance("SHA-256").digest(image));
                field(module, "bytesObserved").setBoolean(module, true);
                inputs[slot] = module.originalExportInput();
            }
            field(core.collection, "graph").set(core.collection, WindowsSystemExportPlan.parse(inputs));
            field(core.collection, "completed").setBoolean(core.collection, true);
            field(core.collection, "outcome").set(core.collection, "COMPLETE");
            candidate = new WindowsOriginalApiSetCandidate(core.collection);
            field(core.collection, "apiSets").set(core.collection, candidate);
            field(core.collection, "apiSetAttempted").setBoolean(core.collection, true);
            field(candidate, "attempted").setBoolean(candidate, true);
            field(candidate, "observed").setBoolean(candidate, true);
            field(candidate, "frame").set(candidate, frame);
            field(candidate, "peb").setLong(candidate, PEB);
            field(candidate, "namespaceAddress").setLong(candidate, MAP);
            field(candidate, "snapshot").set(candidate, namespace);
            field(candidate, "plan").set(candidate, WindowsApiSetPlan.parse(namespace));
            field(candidate, "originalRegion").set(candidate, region());
            field(candidate, "originalArena").set(candidate, core.bootstrapScope);
            field(candidate, "ntdll").set(candidate, core.modules[2].originalApiSetModule(candidate));
            field(candidate, "expectedQuery").setLong(candidate, core.modules[2].originalModuleBits() + 0x1000);
            field(candidate, "linker").set(candidate, Linker.nativeLinker());
            buffers = (MemorySegment[]) value(candidate, "buffers");
            long[] sizes = {4, 32, 8, 48, 4, 48, 8, 28, namespace.length, 8, 258};
            for (int index = 0; index < buffers.length; index++) buffers[index] = frame.allocate(sizes[index], 8);
            field(candidate, "queryCall").set(candidate, MethodHandles.lookup().findVirtual(Fixture.class, "process",
                MethodType.methodType(int.class, MemorySegment.class, int.class, MemorySegment.class, int.class, MemorySegment.class)).bindTo(this));
            field(candidate, "resolveCall").set(candidate, MethodHandles.lookup().findVirtual(Fixture.class, "resolve",
                MethodType.methodType(long.class, MemorySegment.class, MemorySegment.class, MemorySegment.class)).bindTo(this));
            field(candidate, "memoryCall").set(candidate, MethodHandles.lookup().findVirtual(Fixture.class, "memory",
                MethodType.methodType(long.class, MemorySegment.class, MemorySegment.class, long.class)).bindTo(this));
            field(candidate, "readCall").set(candidate, MethodHandles.lookup().findVirtual(Fixture.class, "read",
                MethodType.methodType(int.class, MemorySegment.class, MemorySegment.class, MemorySegment.class,
                    MemorySegment.class, long.class, MemorySegment.class)).bindTo(this));
            field(candidate, "pinCall").set(candidate, MethodHandles.lookup().findVirtual(Fixture.class, "pin",
                MethodType.methodType(int.class, MemorySegment.class, int.class, MemorySegment.class, MemorySegment.class)).bindTo(this));
        }

        private int process(MemorySegment handle, int kind, MemorySegment out, int size, MemorySegment length) {
            calls++; check(handle.address() == -1 && kind == 0 && size == 48);
            out.set(ValueLayout.JAVA_LONG, 8, PEB);
            out.set(ValueLayout.JAVA_LONG, 32, ProcessHandle.current().pid() + (mode.equals("process-pid") ? 1 : 0));
            length.set(ValueLayout.JAVA_INT, 0, mode.equals("process-short") ? 40 : 48);
            if (mode.equals("process-unknown")) throw UNKNOWN;
            return mode.equals("process-status") ? 1 : 0;
        }

        private long memory(MemorySegment address, MemorySegment output, long size) {
            calls++; check(address.address() == MAP && size == 48);
            byte[] bytes = region();
            if (mode.equals("finish-region")) put(bytes, 36, 4, 4);
            MemorySegment.copy(bytes, 0, output, ValueLayout.JAVA_BYTE, 0, bytes.length);
            return 48;
        }

        private int read(MemorySegment error, MemorySegment handle, MemorySegment source,
                         MemorySegment output, long size, MemorySegment count) {
            calls++; check(handle.address() == -1);
            if (source.address() == PEB + 0x68) {
                check(size == 8);
                output.set(ValueLayout.JAVA_LONG, 0, MAP + (mode.equals("finish-pointer") ? 4096 : 0));
            } else {
                check(source.address() == MAP && size == namespace.length);
                MemorySegment.copy(namespace, 0, output, ValueLayout.JAVA_BYTE, 0, namespace.length);
                if (mode.equals("finish-data")) output.set(ValueLayout.JAVA_BYTE, 100, (byte) 1);
            }
            count.set(ValueLayout.JAVA_LONG, 0, mode.equals("read-short") ? size - 1 : size);
            if (mode.equals("read-unknown")) throw UNKNOWN;
            return mode.equals("read-zero") ? 0 : 1;
        }

        private int pin(MemorySegment error, int flags, MemorySegment name, MemorySegment result) {
            calls++;
            if (mode.startsWith("query-export-")) {
                check(flags == 5 && name.address() == core.modules[2].originalModuleBits() + 0x1000);
                result.set(ValueLayout.JAVA_LONG, 0, core.modules[mode.equals("query-export-provider") ? 1 : 2].originalModuleBits());
                if (mode.equals("query-export-pin-unknown")) throw UNKNOWN;
                return 1;
            }
            check(flags == 1);
            for (int index = 0; index < CONTRACT.length(); index++) check(name.getAtIndex(ValueLayout.JAVA_SHORT, index) == CONTRACT.charAt(index));
            check(name.getAtIndex(ValueLayout.JAVA_SHORT, CONTRACT.length()) == 0);
            long expected = core.modules[5].originalModuleBits();
            result.set(ValueLayout.JAVA_LONG, 0, mode.equals("route-wrong") ? expected + 65536 : expected);
            if (mode.equals("route-unknown")) throw UNKNOWN;
            return mode.equals("route-absent") ? 0 : 1;
        }

        private long resolve(MemorySegment error, MemorySegment module, MemorySegment name) {
            calls++; check(module.address() == core.modules[2].originalModuleBits());
            if (mode.equals("query-export-unknown")) throw UNKNOWN;
            return core.modules[2].originalModuleBits() + (mode.equals("query-export-wrong") ? 0x2000 : 0x1000);
        }

        @Override public void close() throws ReflectiveOperationException {
            // Test-owned frames only, including fabricated unknown returns; no real pending native call.
            if (frame.scope().isAlive()) frame.close();
            core.close();
        }
    }

    private static byte[] region() {
        byte[] bytes = new byte[48];
        put(bytes, 0, MAP, 8); put(bytes, 8, MAP, 8); put(bytes, 16, 2, 4); put(bytes, 24, 8192, 8);
        put(bytes, 32, 0x1000, 4); put(bytes, 36, 2, 4); put(bytes, 40, 0x40000, 4);
        return bytes;
    }
    private static void put(byte[] bytes, int at, long value, int size) {
        for (int index = 0; index < size; index++) bytes[at + index] = (byte) (value >>> (index * 8));
    }
}
