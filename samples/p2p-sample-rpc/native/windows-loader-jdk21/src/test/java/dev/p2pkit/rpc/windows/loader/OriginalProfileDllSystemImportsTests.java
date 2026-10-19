package dev.p2pkit.rpc.windows.loader;

import java.lang.foreign.Arena;
import java.lang.foreign.MemorySegment;
import java.lang.reflect.InvocationTargetException;
import java.lang.reflect.Method;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.nio.charset.StandardCharsets;
import java.nio.file.Path;
import java.security.MessageDigest;
import java.util.Arrays;
import java.util.HexFormat;
import java.util.Map;
import java.util.concurrent.atomic.AtomicReference;

import static dev.p2pkit.rpc.windows.loader.OriginalFileBytesLeaseTests.check;
import static dev.p2pkit.rpc.windows.loader.OriginalFileBytesLeaseTests.expect;
import static dev.p2pkit.rpc.windows.loader.OriginalFileBytesLeaseTests.field;
import static dev.p2pkit.rpc.windows.loader.OriginalFileBytesLeaseTests.value;

/** Real maintained JVM17 PE/IAT comparison; deliberately INERT fabricated owners, never native custody. */
public final class OriginalProfileDllSystemImportsTests {
    private static final long PROFILE_BASE = 0x180000000L;
    private static final String[] LIBRARIES = {"kernel32.dll", "advapi32.dll", "ntdll.dll", "shell32.dll", "ole32.dll"};
    private OriginalProfileDllSystemImportsTests() {}

    public static void main(String[] arguments) throws Throwable {
        check(arguments.length == 4);
        WindowsLoaderRuntime.requireDiagnosticRuntime();
        check(OriginalProfileDllSystemImportsTests.class.getModule().isNamed());
        Path main = Path.of(arguments[1]).toRealPath();
        PackagedVerifierTests.actualClass("WindowsProfilePackagedVerifier", main, arguments[2]);
        PackagedVerifierTests.actualClass("WindowsProfileCustodyJni", main, arguments[3]);
        Class<?> source = Class.forName("dev.p2pkit.sample.rpc.profile.WindowsProfilePackagedConnectionFixture",
            true, ClassLoader.getSystemClassLoader());
        Object[] data = fiveImports((Object[]) source.getDeclaredMethod("data").invoke(null));
        String mode = arguments[0];
        switch (mode) {
            case "unowned" -> unowned(data);
            case "five-libraries", "forwarders", "immutability", "duplicate", "verification", "verification-mismatch" -> success(data, mode);
            case "missing-cohort", "incomplete-cohort", "leaf-refused", "ancestor-refused", "failed-cohort",
                "missing-symbol", "api-set", "cycle", "overflow", "partial" -> refused(data, mode);
            case "foreign-bootstrap", "owner-substitution", "cohort-substitution", "thread", "scope" -> continuity(data, mode);
            default -> throw new AssertionError("Unknown original system import control");
        }
        expect(UnsupportedOperationException.class, WindowsLoader::openInstalledProvider);
        System.out.println("WINDOWS_ORIGINAL_PROFILE_DLL_SYSTEM_IMPORTS_PASS case=" + mode +
            " scope=OWNED_INERT_FIVE_LIBRARY_GRAPH_TO_REAL_JDK17_COMPARISON_NOT_NATIVE_CUSTODY_OR_AUTHORITY");
    }

    private static void unowned(Object[] data) throws Throwable {
        WindowsPackagedVerifier plan = WindowsPackagedVerifier.prepare((byte[]) data[0], (byte[]) data[1],
            (String) data[2], (String) data[3], (String) data[4]);
        expect(IllegalStateException.class, plan::prepareOriginalSystemImports);
        expect(IllegalStateException.class, plan::originalSystemImportTargets);
        check(!(boolean) value(plan, "systemImportsAttempted") && plan.importNames().length == 10);
    }

    private static void success(Object[] data, String mode) throws Throwable {
        try (Fixture fixture = new Fixture(data, mode)) {
            WindowsPackagedVerifier plan = fixture.plan;
            expect(IllegalStateException.class, plan::originalSystemImportTargets);
            plan.prepareOriginalSystemImports();
            check(value(plan, "originalSystemModules") == fixture.collection);
            long[] expected = new long[5];
            int[] slots = mode.equals("forwarders") ? new int[] {5, 6, 2, 3, 7} : new int[] {0, 1, 2, 3, 4};
            for (int index = 0; index < 5; index++) expected[index] = base(slots[index]) + 0x1000;
            check(Arrays.equals(expected, plan.originalSystemImportTargets()));
            check(Arrays.equals(plan.importNames(), tuples()));
            WindowsOriginalSystemModuleCandidate[] providers = (WindowsOriginalSystemModuleCandidate[]) value(plan, "originalImportProviders");
            long[] rvas = (long[]) value(plan, "originalImportRvas");
            for (int index = 0; index < 5; index++) check(providers[index] == fixture.modules[slots[index]] && rvas[index] == 0x1000);
            if (mode.equals("immutability")) {
                Arrays.fill(plan.originalSystemImportTargets(), 0);
                Arrays.fill(plan.importNames(), "substituted");
                for (WindowsSystemExportPlan.Input input : fixture.inputs) Arrays.fill(input.image(), (byte) 0);
                Arrays.fill(fixture.dll.bytes.snapshot(), (byte) 0);
                check(Arrays.equals(expected, plan.originalSystemImportTargets()) && Arrays.equals(plan.importNames(), tuples()));
            }
            if (mode.startsWith("verification")) {
                long[] exports = Arrays.stream(plan.exportRvas()).map(rva -> PROFILE_BASE + rva).toArray();
                byte[][] pages = pages((byte[]) data[1], expected);
                if (mode.equals("verification-mismatch")) {
                    long[] wrong = expected.clone(); wrong[3]++;
                    ByteBuffer.wrap(pages[2]).order(ByteOrder.LITTLE_ENDIAN).putLong(3 * 16, wrong[3]);
                    // Caller-controlled pages agree with caller targets, but differ from the original graph.
                    WindowsOriginalProfileDllFileCandidate.Failure failure = (WindowsOriginalProfileDllFileCandidate.Failure)
                        expect(WindowsOriginalProfileDllFileCandidate.Failure.class, () -> plan.verify(PROFILE_BASE, exports, wrong, pages));
                    latched(fixture, failure);
                    return;
                }
                check(plan.verify(PROFILE_BASE, exports, expected, pages).length == 24);
            }
            expect(IllegalStateException.class, plan::prepareOriginalSystemImports);
            check(Arrays.equals(expected, plan.originalSystemImportTargets()) && fixture.dll.file.completed());
            fixture.noNativeEffects();
        }
    }

    private static void refused(Object[] data, String mode) throws Throwable {
        try (Fixture fixture = new Fixture(data, mode)) {
            switch (mode) {
                case "missing-cohort" -> field(fixture.dll.bootstrap, "systemModules").set(fixture.dll.bootstrap, null);
                case "incomplete-cohort" -> field(fixture.collection, "completed").setBoolean(fixture.collection, false);
                case "leaf-refused", "ancestor-refused" -> {
                    field(fixture.collection, "outcome").set(fixture.collection,
                        mode.equals("leaf-refused") ? "LEAF_POLICY_REFUSED" : "ANCESTOR_POLICY_REFUSED");
                    field(fixture.collection, "stoppedSlot").setInt(fixture.collection, 0);
                    if (mode.equals("leaf-refused")) field(value(fixture.modules[0], "security"), "policyAccepted").setBoolean(value(fixture.modules[0], "security"), false);
                    else field(value(fixture.modules[0], "ancestors"), "allPoliciesAccepted").setBoolean(value(fixture.modules[0], "ancestors"), false);
                }
                case "failed-cohort" -> field(fixture.collection, "failed").setBoolean(fixture.collection, true);
                case "overflow" -> {
                    // A valid aligned observed base can still overflow a larger parsed terminal RVA.
                    long nearEnd = (Long.MAX_VALUE & ~65_535L) - 65_536;
                    field(fixture.modules[4], "rawModule").setLong(fixture.modules[4], nearEnd);
                    field(fixture.modules[4], "module").set(fixture.modules[4], MemorySegment.ofAddress(nearEnd).reinterpret(fixture.modulesArena, null));
                }
                default -> { }
            }
            WindowsOriginalProfileDllFileCandidate.Failure failure = (WindowsOriginalProfileDllFileCandidate.Failure)
                expect(WindowsOriginalProfileDllFileCandidate.Failure.class, fixture.plan::prepareOriginalSystemImports);
            check((boolean) value(fixture.plan, "systemImportsAttempted") && !(boolean) value(fixture.plan, "systemImportsPrepared"));
            if (!mode.equals("missing-cohort")) check(value(fixture.plan, "originalSystemModules") == fixture.collection);
            if (mode.equals("partial")) {
                long[] partial = (long[]) value(fixture.plan, "originalImportTargets");
                check(partial[0] == base(0) + 0x1000 && partial[3] == base(3) + 0x1000 && partial[4] == 0);
            }
            if (mode.endsWith("-refused")) check(fixture.collection.completed() && !(boolean) value(fixture.collection, "failed"));
            latched(fixture, failure);
        }
    }

    private static void continuity(Object[] data, String mode) throws Throwable {
        try (Fixture fixture = new Fixture(data, "five-libraries"); Fixture other = new Fixture(data, "five-libraries")) {
            if (mode.equals("foreign-bootstrap")) {
                field(fixture.dll.bootstrap, "systemModules").set(fixture.dll.bootstrap, other.collection);
                WindowsOriginalProfileDllFileCandidate.Failure failure = (WindowsOriginalProfileDllFileCandidate.Failure)
                    expect(WindowsOriginalProfileDllFileCandidate.Failure.class, fixture.plan::prepareOriginalSystemImports);
                check(!(boolean) value(other.collection, "failed") && other.dll.file.completed());
                latched(fixture, failure);
            } else if (mode.equals("thread")) {
                AtomicReference<Throwable> error = new AtomicReference<>();
                Thread thread = Thread.startVirtualThread(() -> {
                    try { expect(IllegalStateException.class, fixture.plan::prepareOriginalSystemImports); }
                    catch (Throwable caught) { error.set(caught); }
                });
                thread.join(); check(error.get() == null && !(boolean) value(fixture.plan, "systemImportsAttempted"));
                fixture.plan.prepareOriginalSystemImports();
                Thread reader = Thread.startVirtualThread(() -> {
                    try { allRefused(fixture.plan, IllegalStateException.class); }
                    catch (Throwable caught) { error.set(caught); }
                });
                reader.join(); check(error.get() == null && fixture.plan.originalSystemImportTargets().length == 5);
            } else {
                fixture.plan.prepareOriginalSystemImports();
                if (mode.equals("owner-substitution")) {
                    field(fixture.dll.bytes, "packaged").set(fixture.dll.bytes, other.plan);
                    allRefused(fixture.plan, IllegalStateException.class);
                    field(fixture.dll.bytes, "packaged").set(fixture.dll.bytes, fixture.plan);
                    check(fixture.plan.originalSystemImportTargets().length == 5);
                } else {
                    if (mode.equals("cohort-substitution")) field(fixture.dll.bootstrap, "systemModules").set(fixture.dll.bootstrap, other.collection);
                    else fixture.modulesArena.close();
                    WindowsOriginalProfileDllFileCandidate.Failure failure = (WindowsOriginalProfileDllFileCandidate.Failure)
                        expect(WindowsOriginalProfileDllFileCandidate.Failure.class, fixture.plan::originalSystemImportTargets);
                    latched(fixture, failure);
                }
            }
            fixture.noNativeEffects(); other.noNativeEffects();
        }
    }

    private static void allRefused(WindowsPackagedVerifier plan, Class<? extends Throwable> failure) throws Throwable {
        expect(failure, plan::originalSystemImportTargets);
        expect(failure, plan::declaringClass);
        expect(failure, plan::imageLayout);
        expect(failure, plan::exportNames);
        expect(failure, plan::exportRvas);
        expect(failure, plan::importNames);
        expect(failure, () -> plan.regions(PROFILE_BASE));
        expect(failure, () -> plan.verify(PROFILE_BASE, new long[24], new long[5], new byte[0][]));
    }

    private static void latched(Fixture fixture, WindowsOriginalProfileDllFileCandidate.Failure failure) throws Throwable {
        WindowsOriginalProfileDllBytesCandidate.Failure child = (WindowsOriginalProfileDllBytesCandidate.Failure) failure.operationFailure;
        Throwable cause = child.operationFailure;
        check(failure.retainedCandidate == fixture.dll.file && child.retainedCandidate == fixture.dll.bytes && cause != null);
        check(cause != failure && cause != child && value(fixture.dll.bytes, "packaged") == fixture.plan);
        check(expect(WindowsOriginalProfileDllFileCandidate.Failure.class, fixture.plan::prepareOriginalSystemImports) == failure);
        check(expect(WindowsOriginalProfileDllFileCandidate.Failure.class, fixture.dll.bytes::snapshot) == failure);
        allRefused(fixture.plan, WindowsOriginalProfileDllFileCandidate.Failure.class);
        check(child.operationFailure == cause && failure.operationFailure == child);
        fixture.noNativeEffects();
    }

    private static final class Fixture implements AutoCloseable {
        final OriginalFileBytesLeaseTests.Fixture dll;
        final Arena modulesArena = Arena.ofConfined(), handlesArena = Arena.ofConfined(), queryArena = Arena.ofConfined(), ancestorsArena = Arena.ofConfined();
        final WindowsOriginalSystemModulesCandidate collection;
        final WindowsOriginalSystemModuleCandidate[] modules;
        final WindowsSystemExportPlan.Input[] inputs = new WindowsSystemExportPlan.Input[9];
        final WindowsPackagedVerifier plan;

        Fixture(Object[] data, String mode) throws Throwable {
            dll = new OriginalFileBytesLeaseTests.Fixture(((byte[]) data[1]).length, true);
            invoke(OriginalProfileDllPackagedVerifierTests.class, "ready",
                new Class<?>[] {OriginalFileBytesLeaseTests.Fixture.class, byte[].class}, dll, data[1]);
            plan = dll.bytes.inspectPackagedBytes((byte[]) data[0], (String) data[2], (String) data[3], (String) data[4]);
            collection = new WindowsOriginalSystemModulesCandidate(dll.bootstrap);
            field(dll.bootstrap, "systemModules").set(dll.bootstrap, collection);
            field(dll.bootstrap, "systemModulesAttempted").setBoolean(dll.bootstrap, true);
            field(collection, "attempted").setBoolean(collection, true);
            field(collection, "bootstrapArena").set(collection, dll.bootstrapScope);
            field(collection, "moduleArena").set(collection, modulesArena);
            modules = (WindowsOriginalSystemModuleCandidate[]) value(collection, "modules");
            // Fabricated completed scopes/ACL/bytes only. This fixture invokes NO native-shaped calls.
            for (int slot = 0; slot < 9; slot++) {
                WindowsOriginalSystemModuleCandidate owner = new WindowsOriginalSystemModuleCandidate(collection, slot);
                modules[slot] = owner;
                field(owner, "rawModule").setLong(owner, base(slot));
                field(owner, "module").set(owner, MemorySegment.ofAddress(base(slot)).reinterpret(modulesArena, null));
                field(owner, "originalPath").set(owner, ("C:\\Windows\\System32\\" + WindowsOriginalSystemModulesCandidate.fixedName(slot) + '\0').toCharArray());
                field(owner, "pinned").setBoolean(owner, true);
            }
            field(collection, "pinsComplete").setBoolean(collection, true);
            for (int slot = 0; slot < 9; slot++) attach(slot, systemImage(slot, mode));
            field(collection, "inputs").set(collection, inputs);
            field(collection, "graph").set(collection, WindowsSystemExportPlan.parse(inputs));
            field(collection, "frameRetired").setBoolean(collection, true);
            field(collection, "completed").setBoolean(collection, true);
            field(collection, "outcome").set(collection, "COMPLETE");
            collection.requireOriginalExportGraph();
        }

        private void attach(int slot, byte[] image) throws Throwable {
            WindowsOriginalSystemModuleCandidate owner = modules[slot];
            field(owner, "fileAttempted").setBoolean(owner, true);
            WindowsOriginalFileLease file = WindowsOriginalFileLease.forSystemModule(owner);
            field(owner, "file").set(owner, file);
            MemorySegment handle = handlesArena.allocate(8).asSlice(0, 0);
            field(file, "handle").set(file, handle); field(file, "rawHandle").setLong(file, handle.address());
            field(file, "handleArena").set(file, handlesArena);
            long[] metadata = {17, 19, 23 + slot, (image.length + 4095) & ~4095L, image.length, 2, 32, 0};
            System.arraycopy(metadata, 0, (long[]) value(file, "first"), 0, 8);
            for (String name : new String[] {"succeeded", "frameRetired"}) field(file, name).setBoolean(file, true);
            field(owner, "fileObserved").setBoolean(owner, true);
            field(owner, "securityAttempted").setBoolean(owner, true);
            WindowsOriginalFileSecurityQuery query = file.newSystemModuleSecurity(owner);
            field(owner, "security").set(owner, query);
            for (String name : new String[] {"succeeded", "frameRetired", "ntReturned", "policyEvaluated", "policyAccepted"}) field(query, name).setBoolean(query, true);
            field(query, "exactDescriptor").set(query, new byte[20]);
            field(query, "moduleArena").set(query, queryArena);
            field(query, "rawModule").setLong(query, base(2));
            field(query, "module").set(query, MemorySegment.ofAddress(base(2)).reinterpret(queryArena, null));
            field(query, "entry").set(query, queryArena.allocate(8).asSlice(0, 0));
            field(owner, "securityObserved").setBoolean(owner, true);
            field(owner, "ancestorsAttempted").setBoolean(owner, true);
            WindowsOriginalFileAncestorsLease ancestors = query.newSystemModuleAncestors(owner);
            field(owner, "ancestors").set(owner, ancestors);
            for (String name : new String[] {"succeeded", "frameRetired", "allPoliciesAccepted"}) field(ancestors, name).setBoolean(ancestors, true);
            field(ancestors, "componentCount").setInt(ancestors, 3); field(ancestors, "directoryCount").setInt(ancestors, 3);
            field(ancestors, "openedCount").setInt(ancestors, 4); field(ancestors, "leaseArena").set(ancestors, ancestorsArena);
            field(owner, "ancestorsObserved").setBoolean(owner, true);
            field(owner, "bytesAttempted").setBoolean(owner, true);
            WindowsOriginalFileBytesLease bytes = file.newSystemModuleBytes(owner);
            field(owner, "bytes").set(owner, bytes);
            for (String name : new String[] {"attempted", "streamAttempted", "frameRetired", "succeeded"}) field(bytes, name).setBoolean(bytes, true);
            field(bytes, "total").setLong(bytes, image.length); field(bytes, "originalSnapshot").set(bytes, image.clone());
            field(bytes, "observedDigest").set(bytes, MessageDigest.getInstance("SHA-256", "SUN").digest(image));
            field(owner, "bytesObserved").setBoolean(owner, true);
            inputs[slot] = owner.originalExportInput(); // Actual production snapshot→copied Input seam.
        }

        void noNativeEffects() throws Exception {
            check(dll.reads == 0 && dll.informationCalls == 0 && value(dll.bootstrap, "imports") == null);
            check(value(collection, "frameArena") == null && value(collection, "pinCall") == null);
            for (WindowsOriginalSystemModuleCandidate module : modules) {
                for (String name : new String[] {"file", "security", "ancestors", "bytes"}) check(value(value(module, name), "frameArena") == null);
            }
            check(dll.handleScope.scope().isAlive() && handlesArena.scope().isAlive() && queryArena.scope().isAlive() && ancestorsArena.scope().isAlive());
        }

        @Override public void close() throws ReflectiveOperationException {
            if (modulesArena.scope().isAlive()) modulesArena.close();
            handlesArena.close(); queryArena.close(); ancestorsArena.close(); dll.close();
        }
    }

    private static byte[] systemImage(int slot, String mode) throws Throwable {
        String forward = null;
        if (mode.equals("forwarders")) forward = switch (slot) {
            case 0 -> "kernelbase.CloseHandle";
            case 1 -> "sechost.#42";
            case 4 -> "combase.CloseHandle";
            default -> null;
        };
        if (mode.equals("api-set") && slot == 4) forward = "api-ms-win-core-example-l1-1-0.CloseHandle";
        if (mode.equals("cycle") && slot == 4) forward = "ole32.CloseHandle";
        String symbol = ((mode.equals("missing-symbol") && slot == 0) || (mode.equals("partial") && slot == 4)) ? "Missing" : "CloseHandle";
        byte[] image = (byte[]) invoke(SystemExportPlanTests.class, "image",
            new Class<?>[] {String.class, long.class, long[].class, String[].class, int[].class, Map.class},
            WindowsOriginalSystemModulesCandidate.fixedName(slot), 42L, new long[] {0x1000}, new String[] {symbol},
            new int[] {0}, forward == null ? Map.of() : Map.of(0, forward));
        if (mode.equals("overflow") && slot == 4) {
            // Move the synthetic RX section to RVA 0x20000 and its terminal to 0x20000.
            put32(image, 0x98 + 56, 0x21000);
            put32(image, 0x188 + 12, 0x20000);
            put32(image, 0x440, 0x20000);
        }
        return image;
    }

    private static Object[] fiveImports(Object[] original) throws Exception {
        Object[] result = original.clone(); byte[] image = ((byte[]) original[1]).clone();
        Arrays.fill(image, 0xe00, 0x1000, (byte) 0);
        put32(image, 0x98 + 120, 0x2800); put32(image, 0x98 + 124, 120);
        put32(image, 0x98 + 208, 0x2950); put32(image, 0x98 + 212, 80);
        for (int index = 0; index < 5; index++) {
            int descriptor = 0xe00 + index * 20;
            put32(image, descriptor, 0x2900 + index * 16); put32(image, descriptor + 12, 0x2880 + index * 16);
            put32(image, descriptor + 16, 0x2950 + index * 16);
            byte[] name = LIBRARIES[index].getBytes(StandardCharsets.US_ASCII);
            System.arraycopy(name, 0, image, 0xe80 + index * 16, name.length);
            put64(image, 0xf00 + index * 16, 0x28d0); put64(image, 0xf50 + index * 16, 0x28d0);
        }
        byte[] symbol = "CloseHandle".getBytes(StandardCharsets.US_ASCII);
        System.arraycopy(symbol, 0, image, 0xed2, symbol.length);
        put64(image, 0xfe0, PROFILE_BASE + 0x1000); image[0x1008] = (byte) 0xe0; image[0x1009] = (byte) 0xa9;
        String oldHash = hash((byte[]) original[1]), newHash = hash(image);
        String manifest = new String((byte[]) original[0], StandardCharsets.US_ASCII);
        check(manifest.contains("sha256=" + oldHash + "\n"));
        result[0] = manifest.replace("sha256=" + oldHash + "\n", "sha256=" + newHash + "\n").getBytes(StandardCharsets.US_ASCII);
        result[1] = image; result[2] = hash((byte[]) result[0]);
        return result;
    }

    private static byte[][] pages(byte[] image, long[] targets) {
        byte[][] pages = {new byte[4096], new byte[4096], Arrays.copyOfRange(image, 0xf50, 0xfa0)};
        System.arraycopy(image, 0, pages[0], 0, 0x400); System.arraycopy(image, 0x400, pages[1], 0, 0x200);
        for (int index = 0; index < 5; index++) ByteBuffer.wrap(pages[2]).order(ByteOrder.LITTLE_ENDIAN).putLong(index * 16, targets[index]);
        return pages;
    }
    private static String[] tuples() {
        String[] tuples = new String[10];
        for (int index = 0; index < 5; index++) { tuples[index * 2] = LIBRARIES[index]; tuples[index * 2 + 1] = "CloseHandle"; }
        return tuples;
    }
    private static long base(int slot) { return 0x70000000L + slot * 0x01000000L; }
    private static String hash(byte[] bytes) throws Exception { return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256", "SUN").digest(bytes)); }
    private static void put32(byte[] bytes, int at, long number) { ByteBuffer.wrap(bytes).order(ByteOrder.LITTLE_ENDIAN).putInt(at, (int) number); }
    private static void put64(byte[] bytes, int at, long number) { ByteBuffer.wrap(bytes).order(ByteOrder.LITTLE_ENDIAN).putLong(at, number); }
    private static Object invoke(Class<?> owner, String name, Class<?>[] types, Object... arguments) throws Throwable {
        Method method = owner.getDeclaredMethod(name, types); method.setAccessible(true);
        try { return method.invoke(null, arguments); }
        catch (InvocationTargetException caught) { throw caught.getCause(); }
    }
}
