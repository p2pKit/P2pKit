package dev.p2pkit.rpc.windows.loader;

import java.lang.foreign.Arena;
import java.lang.foreign.Linker;
import java.lang.foreign.MemoryLayout;
import java.lang.foreign.MemorySegment;
import java.lang.foreign.ValueLayout;
import java.lang.invoke.MethodHandles;
import java.lang.invoke.MethodType;
import java.lang.reflect.Constructor;
import java.lang.reflect.Method;
import java.security.MessageDigest;
import java.util.Arrays;
import java.util.concurrent.atomic.AtomicReference;

import static dev.p2pkit.rpc.windows.loader.OriginalFileBytesLeaseTests.expect;
import static dev.p2pkit.rpc.windows.loader.OriginalFileBytesLeaseTests.field;
import static dev.p2pkit.rpc.windows.loader.OriginalFileBytesLeaseTests.invoke;
import static dev.p2pkit.rpc.windows.loader.OriginalFileBytesLeaseTests.value;

/** Fabricated exact owners and Java MethodHandles exercise real seams, never Windows calls or OS custody. */
public final class OriginalSystemModulesTests {
    private static final String SYSTEM = "C:\\Windows\\System32";
    private static final String[] NAMES = {"kernel32.dll", "advapi32.dll", "ntdll.dll", "shell32.dll",
        "ole32.dll", "kernelbase.dll", "sechost.dll", "combase.dll", "iphlpapi.dll"};
    private static final long BASE = 0x180000000L;
    private static final LinkageError MISSING_RETURN = new LinkageError("inert system call has no primitive return");
    private OriginalSystemModulesTests() {}

    public static void main(String[] arguments) throws Throwable {
        check(arguments.length == 1);
        WindowsLoaderRuntime.requireDiagnosticRuntime();
        String mode = arguments[0];
        switch (mode) {
            case "owner-refusal" -> ownerRefusal();
            case "names" -> names();
            case "bootstrap-substitution", "slot-substitution" -> substitution(mode);
            case "thread" -> thread();
            case "paths", "path-embedded-nul" -> paths(mode);
            case "pin-success", "module-absent", "pin-false", "pin-contradictory", "pin-duplicate",
                "path-mismatch", "system-path-unknown", "pin-unknown", "module-path-unknown" -> pins(mode);
            case "role-links", "role-size" -> roles(mode);
            case "leaf-refusal", "ancestor-refusal" -> policy(mode);
            case "core-substitution", "query-provider" -> cores(mode);
            case "snapshot-input", "snapshot-short", "snapshot-unknown", "snapshot-metadata" -> snapshot(mode);
            case "failure-latch" -> failureLatch();
            default -> throw new AssertionError("Unknown system-module control");
        }
        System.out.println("WINDOWS_ORIGINAL_SYSTEM_MODULES_PASS case=" + mode +
            " scope=INERT_OWNERS_AND_NATIVE_SHAPED_HANDLES_NOT_SYSTEM_CUSTODY_OR_AUTHORITY");
    }

    private static void ownerRefusal() throws Throwable {
        WindowsOriginalSystemModulesCandidate collection = new WindowsOriginalSystemModulesCandidate(null);
        expect(IllegalStateException.class, collection::observe);
        expect(IllegalStateException.class, collection::completed);
        expect(IllegalStateException.class, () -> collection.module(0));
        expect(IllegalStateException.class, () -> collection.resolve("kernel32.dll", "Target"));
        WindowsOriginalSystemModuleCandidate module = new WindowsOriginalSystemModuleCandidate(null, 0);
        expect(IllegalStateException.class, module::observeFile);
        check(!(boolean) value(collection, "attempted") && value(collection, "frameArena") == null);
        check(!(boolean) value(module, "fileAttempted") && value(module, "file") == null);
        check(((WindowsOriginalSystemModulesCandidate.Failure) value(collection, "failure")).retainedCandidate == collection);
        check(((WindowsOriginalSystemModuleCandidate.Failure) value(module, "failure")).retainedCandidate == module);
    }

    private static void names() throws Throwable {
        try (Fixture fixture = new Fixture("pin-success")) {
            for (int index = 0; index < NAMES.length; index++) {
                check(WindowsOriginalSystemModulesCandidate.fixedName(index).equals(NAMES[index]));
                check(fixture.modules[index].name().equals(NAMES[index]));
                check(!fixture.modules[index].pinned() && !fixture.modules[index].fileObserved());
            }
            for (int slot : new int[] {-1, 9, Integer.MIN_VALUE, Integer.MAX_VALUE}) {
                expect(IllegalArgumentException.class, () -> WindowsOriginalSystemModulesCandidate.fixedName(slot));
                expect(IllegalArgumentException.class, () -> new WindowsOriginalSystemModuleCandidate(fixture.collection, slot));
            }
            check(fixture.calls() == 0 && value(fixture.bootstrap, "originalJvm") == null && value(fixture.bootstrap, "profileDll") == null);
        }
    }

    private static void substitution(String mode) throws Throwable {
        try (Fixture fixture = new Fixture("pin-success"); Fixture other = new Fixture("pin-success")) {
            WindowsOriginalSystemModuleCandidate original = fixture.modules[0];
            if (mode.equals("bootstrap-substitution")) {
                WindowsOriginalSystemModulesCandidate unattached = new WindowsOriginalSystemModulesCandidate(fixture.bootstrap);
                expect(IllegalStateException.class, unattached::observe);
                expect(IllegalStateException.class, () -> fixture.bootstrap.requireOriginalSystemModules(other.collection));
                field(fixture.collection, "bootstrap").set(fixture.collection, other.bootstrap);
                expect(IllegalStateException.class, () -> invoke(fixture.collection, "observeSystemPath"));
                expect(IllegalStateException.class, original::name);
                check(!(boolean) value(fixture.collection, "systemPathAttempted"));
            } else {
                WindowsOriginalSystemModuleCandidate foreign = new WindowsOriginalSystemModuleCandidate(fixture.collection, 0);
                expect(IllegalStateException.class, foreign::name);
                expect(IllegalStateException.class, () -> fixture.collection.requireOriginalModule(original, 1));
                fixture.modules[0] = foreign;
                expect(IllegalStateException.class, original::name);
                expect(IllegalStateException.class, original::observeFile);
                check(!(boolean) value(original, "fileAttempted"));
            }
            check(fixture.calls() == 0 && other.calls() == 0);
        }
    }

    private static void thread() throws Throwable {
        try (Fixture fixture = new Fixture("pin-success")) {
            byte[][] before = fixture.bufferCopy();
            AtomicReference<Throwable> unexpected = new AtomicReference<>();
            Thread other = Thread.startVirtualThread(() -> {
                try {
                    expect(IllegalStateException.class, () -> invoke(fixture.collection, "observeSystemPath"));
                    expect(IllegalStateException.class, () -> invoke(fixture.collection, "retireFrame"));
                    expect(IllegalStateException.class, fixture.modules[0]::name);
                } catch (Throwable caught) { unexpected.set(caught); }
            });
            other.join();
            check(unexpected.get() == null && fixture.calls() == 0 && !(boolean) value(fixture.collection, "frameRetired"));
            fixture.unchanged(before);
            fixture.pinAll();
            check(fixture.systemCalls == 1 && fixture.pinCalls == 9 && fixture.pathCalls == 9);
        }
    }

    private static void paths(String mode) throws Throwable {
        try (Fixture fixture = new Fixture("pin-success")) {
            if (mode.equals("path-embedded-nul")) {
                // The original pre-fix parser accepted this nonempty-component embedded terminator.
                String malformed = "C:\\Win\0dows\\System32";
                put(fixture.buffers[2], malformed);
                expect(IllegalStateException.class, () -> validate(fixture.buffers[2], malformed.length()));
                fixture.systemText = malformed;
                expect(IllegalStateException.class, () -> invoke(fixture.collection, "observeSystemPath"));
                check(fixture.systemCalls == 1 && fixture.pinCalls == 0 && fixture.pathCalls == 0);
                check(!(boolean) value(fixture.collection, "nativeReturnUnconfirmed"));
            } else {
                for (String path : new String[] {SYSTEM, "d:\\OS Root\\System32", SYSTEM + "\\kernel32.dll"}) {
                    put(fixture.buffers[2], path);
                    check(validate(fixture.buffers[2], path.length()) == path.length());
                }
                for (String path : new String[] {"", "C:\\", "relative", "\\\\server\\share", "C:/Windows",
                    "C:\\Windows\\", "C:\\Windows\\..\\System32", "C:\\CON\\System32", "C:\\LPT9.txt\\x",
                    "C:\\Windows \\x", "C:\\_Windows\\x", "C:\\W\u00e9ndows\\x", "C:\\a::\\x"}) {
                    put(fixture.buffers[2], path);
                    expect(IllegalStateException.class, () -> validate(fixture.buffers[2], path.length()));
                }
                put(fixture.buffers[2], SYSTEM);
                for (int count : new int[] {-1, 0, 1024, Integer.MAX_VALUE, SYSTEM.length() - 1}) {
                    expect(IllegalStateException.class, () -> validate(fixture.buffers[2], count));
                }
                check(fixture.calls() == 0);
            }
            check(Arrays.stream(fixture.modules).noneMatch(module -> module.fileObserved()));
        }
    }

    private static int validate(MemorySegment buffer, int count) throws Throwable {
        Method method = WindowsOriginalSystemModulesCandidate.class.getDeclaredMethod("validatePath", MemorySegment.class, int.class);
        method.setAccessible(true);
        try { return (int) method.invoke(null, buffer, count); }
        catch (java.lang.reflect.InvocationTargetException failure) { throw failure.getCause(); }
    }

    private static void pins(String mode) throws Throwable {
        boolean unknown = mode.endsWith("-unknown");
        boolean success = mode.equals("pin-success"), absent = mode.equals("module-absent");
        try (Fixture fixture = new Fixture(mode)) {
            if (success || absent) invoke(fixture.collection, "observeLoadedModules");
            else if (unknown) check(expect(LinkageError.class, () -> invoke(fixture.collection, "observeLoadedModules")) == MISSING_RETURN);
            else expect(IllegalStateException.class, () -> invoke(fixture.collection, "observeLoadedModules"));
            check((boolean) value(fixture.collection, "nativeReturnUnconfirmed") == unknown);
            if (success) {
                check(fixture.systemCalls == 1 && fixture.pinCalls == 9 && fixture.pathCalls == 9);
                check((boolean) value(fixture.collection, "pinsComplete"));
                for (int index = 0; index < 9; index++) {
                    check(fixture.modules[index].pinned() && fixture.modules[index].originalModuleBits() == base(index));
                    check(((long[]) value(fixture.collection, "rawModules"))[index] == base(index));
                    char[] path = (char[]) value(fixture.modules[index], "originalPath");
                    check(new String(path, 0, path.length - 1).equals(SYSTEM + "\\" + NAMES[index]));
                    char[] copy = fixture.modules[index].originalPathSnapshot();
                    copy[0] ^= 1;
                    check(path[0] == 'C' && copy != path);
                }
            } else if (absent) {
                check(fixture.pinCalls == 3 && fixture.pathCalls == 2 && !(boolean) value(fixture.collection, "pinsComplete"));
                check(value(fixture.collection, "outcome").equals("MODULE_ABSENT") && (int) value(fixture.collection, "stoppedSlot") == 2);
                check(fixture.collection.failureOperation().equals("SYSTEM_MODULE_ABSENT_SLOT_TWO"));
                check(fixture.modules[0].pinned() && fixture.modules[1].pinned() && !fixture.modules[2].pinned());
            } else if (mode.equals("pin-unknown")) {
                check(fixture.pinCalls == 1 && fixture.pathCalls == 0);
                check(fixture.buffers[0].get(ValueLayout.JAVA_LONG, 0) == base(0));
                check(((long[]) value(fixture.collection, "rawModules"))[0] == 0 && (long) value(fixture.modules[0], "rawModule") == 0);
            } else if (mode.equals("module-path-unknown")) {
                check(fixture.pinCalls == 1 && fixture.pathCalls == 1);
                check(((long[]) value(fixture.collection, "rawModules"))[0] == base(0));
                check((long) value(fixture.modules[0], "rawModule") == base(0) && !fixture.modules[0].pinned());
            } else if (mode.equals("system-path-unknown")) check(fixture.systemCalls == 1 && fixture.pinCalls == 0);
            else if (mode.equals("pin-duplicate") || mode.equals("path-mismatch")) {
                check(fixture.modules[0].pinned() && fixture.pinCalls == 2 && fixture.pathCalls == (mode.equals("pin-duplicate") ? 1 : 2));
                check((long) value(fixture.modules[1], "rawModule") != 0);
            } else {
                check(fixture.pinCalls == 1 && fixture.pathCalls == 0);
                check((long) value(fixture.modules[0], "rawModule") == (mode.equals("pin-contradictory") ? base(0) : 0));
            }
            check(Arrays.stream(fixture.modules).noneMatch(module -> module.fileObserved()));
            if (unknown) check(fixture.collection.failureOperation().equals("SYSTEM_RETURN_UNKNOWN_" +
                (mode.equals("system-path-unknown") ? "NO_SLOT" : "SLOT_ZERO")));
            if (mode.equals("path-mismatch")) check(fixture.collection.failureOperation().equals("SYSTEM_MODULE_PATH_SLOT_ONE"));
            if (mode.equals("pin-false")) check(fixture.collection.failureOperation().equals("SYSTEM_MODULE_PIN_SLOT_ZERO"));
            byte[][] observed = fixture.bufferCopy();
            int calls = fixture.calls();
            expect(IllegalStateException.class, () -> invoke(fixture.collection, "observeLoadedModules"));
            invoke(fixture.collection, "retireFrame");
            invoke(fixture.collection, "retireFrame");
            check(fixture.calls() == calls && fixture.frame.scope().isAlive() == unknown);
            check((boolean) value(fixture.collection, "frameRetired") == !unknown && fixture.moduleScope.scope().isAlive());
            if (unknown) fixture.unchanged(observed);
            else for (MemorySegment backing : fixture.backingViews) for (byte b : backing.toArray(ValueLayout.JAVA_BYTE)) check(b == 0);
            check(value(value(fixture.collection, "failure"), "retainedCandidate") == fixture.collection);
            if (absent) {
                field(fixture.collection, "completed").setBoolean(fixture.collection, true); // Driver's completed negative diagnostic only.
                check(fixture.collection.completed() && fixture.collection.moduleCount() == 9 && fixture.collection.stoppedSlot() == 2);
                expect(IllegalStateException.class, fixture.modules[0]::observeFile);
                expect(IllegalStateException.class, () -> fixture.collection.resolve("kernel32.dll", "Target"));
            }
        }
    }

    private static void roles(String mode) throws Throwable {
        try (Fixture fixture = new Fixture("pin-success"); OriginalFileBytesLeaseTests.Fixture dll = new OriginalFileBytesLeaseTests.Fixture(512, false)) {
            fixture.pinAll();
            WindowsOriginalFileLease system = fixture.attachFile(0, 512, 2);
            WindowsOriginalJvmFileCandidate jvmOwner = new WindowsOriginalJvmFileCandidate(null, null, null, null, null, null, null, 0);
            WindowsOriginalFileLease jvm = (WindowsOriginalFileLease) value(jvmOwner, "lease");
            String method = mode.equals("role-links") ? "refusedLinkCount" : "refusedFileSize";
            long[] values = mode.equals("role-links") ? new long[] {Long.MIN_VALUE, -1, 0, 1, 2, 0x80000000L, 0xffffffffL, 0x100000000L, Long.MAX_VALUE} :
                new long[] {Long.MIN_VALUE, -1, 0, 1, 511, 512, 32L * 1024 * 1024, 32L * 1024 * 1024 + 1, 512L * 1024 * 1024, Long.MAX_VALUE};
            for (long number : values) {
                boolean systemRefused = mode.equals("role-links") ? number <= 0 || number > 0xffffffffL : number < 512 || number > 32L * 1024 * 1024;
                boolean dllRefused = mode.equals("role-links") ? number != 1 : systemRefused;
                boolean jvmRefused = mode.equals("role-links") ? number != 1 : number <= 0 || number > 512L * 1024 * 1024;
                check((boolean) invoke(system, method, new Class<?>[] {long.class}, number) == systemRefused);
                check((boolean) invoke(dll.lease, method, new Class<?>[] {long.class}, number) == dllRefused);
                check((boolean) invoke(jvm, method, new Class<?>[] {long.class}, number) == jvmRefused);
            }
            check(fixture.modules[0].linkCount() == 2 && fixture.modules[0].byteCount() == 512);
            check(value(system, "originalSystemOwner") == fixture.modules[0] && value(dll.lease, "originalSystemOwner") == null);
        }
    }

    private static void policy(String mode) throws Throwable {
        try (Fixture fixture = new Fixture("pin-success")) {
            fixture.pinAll();
            fixture.attachFile(0, 512, 2);
            fixture.attachSecurity(!mode.equals("leaf-refusal"));
            if (mode.equals("ancestor-refusal")) fixture.attachAncestors(false);
            int calls = fixture.calls();
            field(fixture.collection, "outcome").set(fixture.collection, mode.equals("leaf-refusal") ? "LEAF_POLICY_REFUSED" : "ANCESTOR_POLICY_REFUSED");
            field(fixture.collection, "stoppedSlot").setInt(fixture.collection, 0);
            field(fixture.collection, "completed").setBoolean(fixture.collection, true);
            check(fixture.collection.completed() && fixture.modules[0].securityObserved());
            check(fixture.modules[0].descriptorPolicyAccepted() == mode.equals("ancestor-refusal"));
            if (mode.equals("ancestor-refusal")) check(!fixture.modules[0].descriptorPoliciesAccepted());
            else {
                expect(IllegalStateException.class, fixture.modules[0]::observeAncestors);
                check(!(boolean) value(fixture.modules[0], "ancestorsAttempted") && value(fixture.modules[0], "ancestors") == null);
            }
            expect(IllegalStateException.class, fixture.modules[0]::observeBytes);
            expect(IllegalStateException.class, fixture.modules[0]::originalLinker);
            expect(IllegalStateException.class, () -> fixture.file.newSystemModuleBytes(fixture.modules[0]));
            expect(IllegalStateException.class, () -> fixture.collection.resolve("kernel32.dll", "Target"));
            check(!fixture.modules[0].bytesObserved() && !(boolean) value(fixture.modules[0], "bytesAttempted"));
            check(value(fixture.modules[0], "bytes") == null && fixture.calls() == calls);
            check(fixture.query.descriptorPolicyAccepted() == mode.equals("ancestor-refusal"));
        }
    }

    private static void cores(String mode) throws Throwable {
        try (Fixture fixture = new Fixture("pin-success")) {
            fixture.pinAll();
            fixture.attachFile(0, 512, 2);
            fixture.attachSecurity(true);
            if (mode.equals("query-provider")) {
                fixture.modules[0].requireOriginalQueryProvider(fixture.query, base(2));
                expect(IllegalStateException.class, () -> fixture.modules[0].requireOriginalQueryProvider(fixture.query, base(0)));
                expect(IllegalStateException.class, () -> fixture.modules[0].requireOriginalQueryProvider(null, base(2)));
            } else {
                WindowsOriginalFileLease foreign = WindowsOriginalFileLease.forSystemModule(fixture.modules[1]);
                expect(IllegalStateException.class, foreign::observe);
                expect(IllegalStateException.class, () -> fixture.modules[0].requireOriginalFileLease(foreign));
                expect(IllegalStateException.class, () -> fixture.file.newSystemModuleSecurity(fixture.modules[1]));
                expect(IllegalStateException.class, () -> fixture.query.newSystemModuleAncestors(fixture.modules[1]));
                expect(IllegalStateException.class, () -> fixture.modules[0].requireOriginalQuery(null));
                check(!(boolean) value(foreign, "attempted") && value(foreign, "frameArena") == null);
            }
            check(value(fixture.query, "fileHandle") == value(fixture.file, "handle"));
            check(value(fixture.query, "fileArena") == fixture.handleScope && fixture.calls() == 19);
        }
    }

    private static void snapshot(String mode) throws Throwable {
        try (Fixture fixture = new Fixture(mode)) {
            fixture.pinAll();
            fixture.image = synthetic("kernel32.dll");
            fixture.attachFile(0, fixture.image.length, 2);
            fixture.attachSecurity(true);
            fixture.attachAncestors(true);
            fixture.prepareBytes();
            Arena frame = (Arena) value(fixture.bytes, "frameArena");
            if (mode.equals("snapshot-input")) {
                invoke(fixture.bytes, "consumeStream");
                field(fixture.modules[0], "bytesObserved").setBoolean(fixture.modules[0], true);
                check(fixture.modules[0].bytesObserved() && fixture.reads == 2 && fixture.informationCalls == 6 && !frame.scope().isAlive());
                byte[] snapshot = (byte[]) value(fixture.bytes, "originalSnapshot");
                check(Arrays.equals(snapshot, fixture.image) && snapshot != fixture.image);
                check(MessageDigest.isEqual(MessageDigest.getInstance("SHA-256", "SUN").digest(snapshot), fixture.modules[0].sha256()));
                WindowsSystemExportPlan.Input input = fixture.modules[0].originalExportInput();
                check(input.module().equals("kernel32.dll") && input == value(fixture.modules[0], "exportInput"));
                check(value(input, "image") != snapshot && Arrays.equals(input.image(), snapshot));
                byte[] external = input.image(); external[0] = 0;
                check(input.image()[0] == 'M' && snapshot[0] == 'M');
                WindowsSystemExportPlan.Target target = WindowsSystemExportPlan.parse(new WindowsSystemExportPlan.Input[] {input}).resolve("kernel32.dll", "Target");
                check(target.module().equals("kernel32.dll") && target.rva() == 0x1000 && target.ordinal() == 42);
                expect(IllegalStateException.class, fixture.modules[0]::originalExportInput);
                expect(IllegalStateException.class, () -> fixture.bytes.newSystemExportInput(fixture.modules[1]));
                expect(IllegalStateException.class, () -> fixture.bytes.newSystemExportInput(null));
                expect(IllegalStateException.class, () -> fixture.collection.resolve("kernel32.dll", "Target"));
            } else {
                WindowsOriginalFileBytesLease.Failure failure = (WindowsOriginalFileBytesLease.Failure) expect(
                    WindowsOriginalFileBytesLease.Failure.class, () -> invoke(fixture.bytes, "consumeStream"));
                boolean unknown = mode.equals("snapshot-unknown");
                check(failure.retainedCandidate == fixture.bytes && failure.operationFailure != null);
                check(frame.scope().isAlive() == unknown && (boolean) value(fixture.bytes, "nativeReturnUnconfirmed") == unknown);
                check(value(fixture.bytes, "observedDigest") == null && !(boolean) value(fixture.bytes, "succeeded"));
                check(fixture.reads == (mode.equals("snapshot-short") ? 1 : 2));
                check(fixture.informationCalls == (mode.equals("snapshot-metadata") ? 6 : 3));
                expect(IllegalStateException.class, () -> fixture.bytes.newSystemExportInput(fixture.modules[0]));
                check(value(fixture.modules[0], "exportInput") == null);
                invoke(fixture.bytes, "retireFrame");
                check(frame.scope().isAlive() == unknown);
            }
            int reads = fixture.reads;
            expect(IllegalStateException.class, () -> invoke(fixture.bytes, "consumeStream"));
            check(fixture.reads == reads && value(fixture.bytes, "fileHandle") == value(fixture.file, "handle"));
            check(value(fixture.ancestors, "originalFileHandle") == value(fixture.file, "handle"));
            check(value(fixture.bytes, "fileArena") == fixture.handleScope && fixture.handleScope.scope().isAlive());
        }
    }

    private static void failureLatch() throws Throwable {
        try (Fixture fixture = new Fixture("pin-success")) {
            fixture.pinAll();
            fixture.attachFile(0, 512, 2);
            Throwable operation = new LinkageError("inert fixed attachment failure");
            Object result = invoke(fixture.modules[0], "fail", new Class<?>[] {Throwable.class}, operation);
            WindowsOriginalSystemModulesCandidate.Failure root = (WindowsOriginalSystemModulesCandidate.Failure) result;
            WindowsOriginalSystemModuleCandidate.Failure child = (WindowsOriginalSystemModuleCandidate.Failure) value(fixture.modules[0], "failure");
            check(root == value(fixture.collection, "failure") && root.operationFailure == child && child.operationFailure == operation);
            check(root.retainedCandidate == fixture.collection && child.retainedCandidate == fixture.modules[0]);
            check(expect(WindowsOriginalSystemModulesCandidate.Failure.class, fixture.collection::completed) == root);
            check(expect(WindowsOriginalSystemModulesCandidate.Failure.class, fixture.modules[1]::observeFile) == root);
            Object second = invoke(fixture.modules[0], "fail", new Class<?>[] {Throwable.class}, new LinkageError("later inert failure"));
            check(second == root && child.operationFailure == operation && fixture.calls() == 19);
            check(fixture.handleScope.scope().isAlive() && fixture.moduleScope.scope().isAlive());
        }
    }

    private static byte[] synthetic(String name) throws Throwable {
        Method method = SystemExportPlanTests.class.getDeclaredMethod("simple", String.class);
        method.setAccessible(true);
        return (byte[]) method.invoke(null, name);
    }

    static final class Fixture implements AutoCloseable {
        final Arena bootstrapScope = Arena.ofConfined(), moduleScope = Arena.ofConfined(), handleScope = Arena.ofConfined();
        final Arena queryScope = Arena.ofConfined(), ancestorScope = Arena.ofConfined(), backing = Arena.ofConfined();
        final Arena frame = Arena.ofConfined();
        final WindowsSystemBootstrapCandidate bootstrap;
        final WindowsOriginalSystemModulesCandidate collection;
        final WindowsOriginalSystemModuleCandidate[] modules;
        final MemorySegment[] buffers, backingViews = new MemorySegment[5];
        final String mode;
        WindowsOriginalFileLease file;
        WindowsOriginalFileSecurityQuery query;
        WindowsOriginalFileAncestorsLease ancestors;
        WindowsOriginalFileBytesLease bytes;
        long[] metadata;
        byte[] image;
        String systemText = SYSTEM;
        int systemCalls, pinCalls, pathCalls, reads, informationCalls, position;

        Fixture(String mode) throws ReflectiveOperationException {
            this.mode = mode;
            Constructor<WindowsSystemBootstrapCandidate> constructor = WindowsSystemBootstrapCandidate.class.getDeclaredConstructor(Linker.class);
            constructor.setAccessible(true);
            bootstrap = constructor.newInstance((Object) null);
            field(bootstrap, "originalArena").set(bootstrap, bootstrapScope);
            field(bootstrap, "succeeded").setBoolean(bootstrap, true);
            field(bootstrap, "frameRetired").setBoolean(bootstrap, true);
            MemorySegment[] entries = (MemorySegment[]) value(bootstrap, "entries");
            for (int index = 1; index <= 13; index++) entries[index] = bootstrapScope.allocate(8).asSlice(0, 0);
            collection = new WindowsOriginalSystemModulesCandidate(bootstrap);
            field(bootstrap, "systemModules").set(bootstrap, collection);
            field(bootstrap, "systemModulesAttempted").setBoolean(bootstrap, true);
            field(collection, "attempted").setBoolean(collection, true);
            field(collection, "bootstrapArena").set(collection, bootstrapScope);
            field(collection, "moduleArena").set(collection, moduleScope);
            field(collection, "frameArena").set(collection, frame);
            modules = (WindowsOriginalSystemModuleCandidate[]) value(collection, "modules");
            for (int index = 0; index < modules.length; index++) modules[index] = new WindowsOriginalSystemModuleCandidate(collection, index);
            buffers = (MemorySegment[]) value(collection, "buffers");
            for (int index = 0; index < buffers.length; index++) {
                int size = index == 0 ? 8 : index < 3 ? 2048 : index == 3 ? 64 : 4;
                backingViews[index] = backing.allocate(size, 8);
                backingViews[index].fill((byte) 0x5a);
                buffers[index] = backingViews[index].reinterpret(size, frame, null);
            }
            field(collection, "systemPathCall").set(collection, MethodHandles.lookup().findVirtual(Fixture.class, "system",
                MethodType.methodType(int.class, MemorySegment.class, MemorySegment.class, int.class)).bindTo(this));
            field(collection, "pinCall").set(collection, MethodHandles.lookup().findVirtual(Fixture.class, "pin",
                MethodType.methodType(int.class, MemorySegment.class, int.class, MemorySegment.class, MemorySegment.class)).bindTo(this));
            field(collection, "pathCall").set(collection, MethodHandles.lookup().findVirtual(Fixture.class, "path",
                MethodType.methodType(int.class, MemorySegment.class, MemorySegment.class, MemorySegment.class, int.class)).bindTo(this));
        }

        private int system(MemorySegment error, MemorySegment output, int chars) {
            systemCalls++;
            check(chars == 1024 && output == buffers[2]);
            put(output, systemText);
            error.set(ValueLayout.JAVA_INT, 0, 126); // A successful Win32-shaped call may retain stale error.
            if (mode.equals("system-path-unknown")) throw MISSING_RETURN;
            return systemText.length();
        }
        private int pin(MemorySegment error, int flags, MemorySegment name, MemorySegment output) throws Throwable {
            int slot = pinCalls++;
            check(slot < 9 && flags == 1 && output == buffers[0]);
            check(text(name).equals(NAMES[slot])); // No caller-selected names/addresses/extra module probe.
            expect(IllegalStateException.class, collection::requireOriginalNativeInputs);
            long raw = mode.equals("pin-duplicate") && slot == 1 ? base(0) : base(slot);
            boolean absent = mode.equals("module-absent") && slot == 2;
            if (absent || mode.equals("pin-false")) raw = 0;
            output.set(ValueLayout.JAVA_LONG, 0, raw);
            error.set(ValueLayout.JAVA_INT, 0, absent ? 126 : mode.equals("pin-false") ? 5 : 126);
            if (mode.equals("pin-unknown")) throw MISSING_RETURN;
            return absent || mode.equals("pin-false") || mode.equals("pin-contradictory") ? 0 : 1;
        }
        private int path(MemorySegment error, MemorySegment module, MemorySegment output, int chars) {
            int slot = pathCalls++;
            check(chars == 1024 && module.address() == base(slot));
            String path = SYSTEM + "\\" + (mode.equals("path-mismatch") && slot == 1 ? "different.dll" : NAMES[slot]);
            put(output, path);
            error.set(ValueLayout.JAVA_INT, 0, 126);
            if (mode.equals("module-path-unknown")) throw MISSING_RETURN;
            return path.length();
        }
        void pinAll() throws Throwable {
            invoke(collection, "observeLoadedModules");
            check((boolean) value(collection, "pinsComplete"));
            invoke(collection, "retireFrame");
            check(!frame.scope().isAlive());
        }
        WindowsOriginalFileLease attachFile(int slot, long size, long links) throws Throwable {
            WindowsOriginalSystemModuleCandidate owner = modules[slot];
            field(owner, "fileAttempted").setBoolean(owner, true);
            file = WindowsOriginalFileLease.forSystemModule(owner);
            field(owner, "file").set(owner, file);
            metadata = new long[] {17, 19, 23, (size + 4095) & ~4095L, size, links, 32, 0};
            System.arraycopy(metadata, 0, (long[]) value(file, "first"), 0, 8);
            MemorySegment handle = handleScope.allocate(8).asSlice(0, 0);
            field(file, "handle").set(file, handle);
            field(file, "rawHandle").setLong(file, handle.address());
            field(file, "handleArena").set(file, handleScope);
            field(file, "succeeded").setBoolean(file, true);
            field(file, "frameRetired").setBoolean(file, true);
            field(owner, "fileObserved").setBoolean(owner, true);
            return file;
        }
        void attachSecurity(boolean policy) throws Throwable {
            attachSecurity(0, policy);
        }
        void attachSecurity(int slot, boolean policy) throws Throwable {
            WindowsOriginalSystemModuleCandidate owner = modules[slot];
            field(owner, "securityAttempted").setBoolean(owner, true);
            query = file.newSystemModuleSecurity(owner);
            field(owner, "security").set(owner, query);
            for (String name : new String[] {"succeeded", "frameRetired", "ntReturned", "policyEvaluated"}) field(query, name).setBoolean(query, true);
            field(query, "policyAccepted").setBoolean(query, policy);
            field(query, "exactDescriptor").set(query, new byte[20]); // Fabricated diagnostic state, not a parsed ACL.
            field(query, "moduleArena").set(query, queryScope);
            field(query, "rawModule").setLong(query, base(2));
            field(query, "module").set(query, MemorySegment.ofAddress(base(2)).reinterpret(queryScope, null));
            field(query, "entry").set(query, queryScope.allocate(8).asSlice(0, 0));
            field(owner, "securityObserved").setBoolean(owner, true);
            field(owner, "leafPolicyRefused").setBoolean(owner, !policy);
        }
        void attachAncestors(boolean policy) throws Throwable {
            attachAncestors(0, policy);
        }
        void attachAncestors(int slot, boolean policy) throws Throwable {
            WindowsOriginalSystemModuleCandidate owner = modules[slot];
            field(owner, "ancestorsAttempted").setBoolean(owner, true);
            ancestors = query.newSystemModuleAncestors(owner);
            field(owner, "ancestors").set(owner, ancestors);
            field(ancestors, "succeeded").setBoolean(ancestors, true);
            field(ancestors, "frameRetired").setBoolean(ancestors, true);
            field(ancestors, "componentCount").setInt(ancestors, 3);
            field(ancestors, "directoryCount").setInt(ancestors, 3);
            field(ancestors, "openedCount").setInt(ancestors, 4);
            field(ancestors, "leaseArena").set(ancestors, ancestorScope);
            field(ancestors, "allPoliciesAccepted").setBoolean(ancestors, policy);
            field(owner, "ancestorsObserved").setBoolean(owner, true);
            field(owner, "ancestorPolicyRefused").setBoolean(owner, !policy);
        }
        void prepareBytes() throws Throwable {
            WindowsOriginalSystemModuleCandidate owner = modules[0];
            field(owner, "bytesAttempted").setBoolean(owner, true);
            bytes = file.newSystemModuleBytes(owner);
            field(owner, "bytes").set(owner, bytes);
            invoke(bytes, "prepareData");
            invoke(bytes, "prepareFrame", new Class<?>[] {MemoryLayout.class}, MemoryLayout.structLayout(ValueLayout.JAVA_INT));
            field(bytes, "readCall").set(bytes, MethodHandles.lookup().findVirtual(Fixture.class, "read",
                MethodType.methodType(int.class, MemorySegment.class, MemorySegment.class, MemorySegment.class,
                    int.class, MemorySegment.class, MemorySegment.class)).bindTo(this));
            field(bytes, "informationCall").set(bytes, MethodHandles.lookup().findVirtual(Fixture.class, "information",
                MethodType.methodType(int.class, MemorySegment.class, MemorySegment.class, int.class, MemorySegment.class, int.class)).bindTo(this));
            field(bytes, "attempted").setBoolean(bytes, true);
        }
        private int read(MemorySegment error, MemorySegment handle, MemorySegment output, int wanted,
            MemorySegment count, MemorySegment overlapped) throws Throwable {
            reads++;
            check(handle == value(file, "handle") && overlapped.address() == 0 && informationCalls == 3);
            check(wanted == (position < image.length ? image.length - position : 1));
            int amount = position == image.length ? 0 : wanted;
            if (mode.equals("snapshot-short") && reads == 1) amount--;
            MemorySegment.copy(image, position, output, ValueLayout.JAVA_BYTE, 0, amount);
            position += amount;
            count.set(ValueLayout.JAVA_INT, 0, amount);
            error.set(ValueLayout.JAVA_INT, 0, 126);
            if (mode.equals("snapshot-unknown") && reads == 2) throw MISSING_RETURN;
            return 1;
        }
        private int information(MemorySegment error, MemorySegment handle, int kind, MemorySegment output, int size) throws Throwable {
            informationCalls++;
            check(handle == value(file, "handle"));
            int phase = (informationCalls - 1) % 3;
            check(kind == new int[] {18, 9, 1}[phase] && size == new int[] {24, 8, 24}[phase]);
            output.fill((byte) 0);
            if (kind == 18) for (int index = 0; index < 3; index++) output.set(ValueLayout.JAVA_LONG, index * 8L, metadata[index]);
            else if (kind == 9) {
                output.set(ValueLayout.JAVA_INT, 0, (int) metadata[6]);
                output.set(ValueLayout.JAVA_INT, 4, (int) metadata[7]);
            } else {
                output.set(ValueLayout.JAVA_LONG, 0, metadata[3]);
                output.set(ValueLayout.JAVA_LONG, 8, metadata[4]);
                output.set(ValueLayout.JAVA_INT, 16, (int) metadata[5] + (mode.equals("snapshot-metadata") && informationCalls == 6 ? 1 : 0));
            }
            error.set(ValueLayout.JAVA_INT, 0, 126);
            return 1;
        }
        int calls() { return systemCalls + pinCalls + pathCalls; }
        byte[][] bufferCopy() { return Arrays.stream(backingViews).map(buffer -> buffer.toArray(ValueLayout.JAVA_BYTE)).toArray(byte[][]::new); }
        void unchanged(byte[][] original) { for (int index = 0; index < original.length; index++) check(Arrays.equals(original[index], backingViews[index].toArray(ValueLayout.JAVA_BYTE))); }
        @Override public void close() throws ReflectiveOperationException {
            // These are exclusively test-owned inert scopes; no native/pending request ever existed.
            if (bytes != null) {
                Arena byteFrame = (Arena) value(bytes, "frameArena");
                if (byteFrame != null && byteFrame.scope().isAlive()) byteFrame.close();
            }
            if (frame.scope().isAlive()) frame.close();
            backing.close(); ancestorScope.close(); queryScope.close(); handleScope.close();
            if (moduleScope.scope().isAlive()) moduleScope.close();
            bootstrapScope.close();
        }
    }

    private static long base(int slot) { return BASE + slot * 0x100000L; }
    private static void put(MemorySegment output, String text) {
        output.fill((byte) 0x7f);
        for (int index = 0; index < text.length(); index++) output.setAtIndex(ValueLayout.JAVA_SHORT, index, (short) text.charAt(index));
        output.setAtIndex(ValueLayout.JAVA_SHORT, text.length(), (short) 0);
    }
    private static String text(MemorySegment input) {
        StringBuilder value = new StringBuilder();
        for (int index = 0; index < 32; index++) {
            char c = (char) Short.toUnsignedInt(input.getAtIndex(ValueLayout.JAVA_SHORT, index));
            if (c == 0) return value.toString();
            value.append(c);
        }
        throw new AssertionError("Unterminated inert module name");
    }
    private static void check(boolean condition) { if (!condition) throw new AssertionError("Original system module control failed"); }
}
