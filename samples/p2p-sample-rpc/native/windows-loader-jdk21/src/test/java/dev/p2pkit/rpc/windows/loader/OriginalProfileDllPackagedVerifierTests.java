package dev.p2pkit.rpc.windows.loader;

import java.lang.reflect.InvocationTargetException;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.nio.file.Path;
import java.security.MessageDigest;
import java.util.Arrays;
import java.util.concurrent.atomic.AtomicReference;

import static dev.p2pkit.rpc.windows.loader.OriginalFileBytesLeaseTests.check;
import static dev.p2pkit.rpc.windows.loader.OriginalFileBytesLeaseTests.expect;
import static dev.p2pkit.rpc.windows.loader.OriginalFileBytesLeaseTests.field;
import static dev.p2pkit.rpc.windows.loader.OriginalFileBytesLeaseTests.unattached;
import static dev.p2pkit.rpc.windows.loader.OriginalFileBytesLeaseTests.value;

/** Real fixed JVM17 comparison with an explicitly fabricated inert ownership graph, never file custody. */
public final class OriginalProfileDllPackagedVerifierTests {
    private static final long BASE = 0x0000000180000000L;
    private static final long IMPORT = 0x0000000070000000L;
    private OriginalProfileDllPackagedVerifierTests() {}

    public static void main(String[] arguments) throws Throwable {
        check(arguments.length == 4);
        WindowsLoaderRuntime.requireDiagnosticRuntime();
        check(OriginalProfileDllPackagedVerifierTests.class.getModule().isNamed());
        String mode = arguments[0];
        Path main = Path.of(arguments[1]).toRealPath();
        Class<?> helper = PackagedVerifierTests.actualClass("WindowsProfilePackagedVerifier", main, arguments[2]);
        Class<?> declaration = PackagedVerifierTests.actualClass("WindowsProfileCustodyJni", main, arguments[3]);
        Class<?> fixture = Class.forName("dev.p2pkit.sample.rpc.profile.WindowsProfilePackagedConnectionFixture",
            true, ClassLoader.getSystemClassLoader());
        check(!fixture.getModule().isNamed() && fixture.getClassLoader() == ClassLoader.getSystemClassLoader());
        Object[] data = (Object[]) fixture.getDeclaredMethod("data").invoke(null);
        check(data.length == 5 && ((byte[]) data[1]).length == 0x1200);
        switch (mode) {
            case "owner-refusal" -> ownerRefusal(data);
            case "incomplete" -> incomplete(data);
            case "substitution" -> substitution(data);
            case "thread" -> thread(data);
            case "success", "immutability" -> success(data, helper, declaration, mode.equals("immutability"));
            case "hash-mismatch", "invalid-pin", "manifest-pin", "source-pin", "malformed-pe" -> failure(data, mode);
            case "operation-failure" -> operationFailure(data);
            default -> throw new AssertionError("Unknown owned packaged verifier control");
        }
        expect(UnsupportedOperationException.class, WindowsLoader::openInstalledProvider);
        System.out.println("WINDOWS_ORIGINAL_PROFILE_DLL_PACKAGED_PASS case=" + mode +
            " scope=OWNED_INERT_SNAPSHOT_TO_REAL_JDK17_COMPARISON_NOT_NATIVE_CUSTODY_OR_AUTHORITY");
    }

    private static WindowsPackagedVerifier inspect(WindowsOriginalProfileDllBytesCandidate bytes, Object[] data) {
        return bytes.inspectPackagedBytes((byte[]) data[0], (String) data[2], (String) data[3], (String) data[4]);
    }

    private static void ready(OriginalFileBytesLeaseTests.Fixture fixture, byte[] library) throws Exception {
        // Deliberate inert fixture state only. No source HANDLE is read, no policy is actually established,
        // and this test does not replace the separate native same-HANDLE or whole-stream controls.
        field(fixture.bytes, "attempted").setBoolean(fixture.bytes, true);
        field(fixture.core, "attempted").setBoolean(fixture.core, true);
        field(fixture.core, "streamAttempted").setBoolean(fixture.core, true);
        field(fixture.core, "frameRetired").setBoolean(fixture.core, true);
        field(fixture.core, "succeeded").setBoolean(fixture.core, true);
        field(fixture.core, "total").setLong(fixture.core, library.length);
        field(fixture.core, "originalSnapshot").set(fixture.core, library.clone());
        field(fixture.core, "observedDigest").set(fixture.core, MessageDigest.getInstance("SHA-256", "SUN").digest(library));
        check(fixture.bytes.completed());
    }

    private static void ownerRefusal(Object[] data) throws Throwable {
        WindowsOriginalProfileDllBytesCandidate owner = unattached(null, 0x1200);
        expect(IllegalStateException.class, () -> inspect(owner, data));
        expect(IllegalArgumentException.class, () -> WindowsPackagedVerifier.forOriginalBytes(null));
        WindowsPackagedVerifier plan = WindowsPackagedVerifier.forOriginalBytes(owner);
        expect(IllegalStateException.class, () -> plan.prepareOriginalBytes((byte[]) data[0],
            (String) data[2], (String) data[3], (String) data[4]));
        allRefused(plan, IllegalStateException.class);
        check(!(boolean) value(owner, "packagedAttempted") && value(owner, "packaged") == null);
        check(!(boolean) value(plan, "attempted") && !(boolean) value(plan, "prepared"));
        check(value(plan, "originalVerifier") == null && value(plan, "originalSnapshotSha256") == null);
    }

    private static void incomplete(Object[] data) throws Throwable {
        for (String mode : new String[] {"unread", "unretired", "native-unknown", "leaf-refused", "ancestor-refused"}) {
            try (OriginalFileBytesLeaseTests.Fixture fixture = new OriginalFileBytesLeaseTests.Fixture(0x1200, true)) {
                if (!mode.equals("unread")) ready(fixture, (byte[]) data[1]);
                switch (mode) {
                    case "unretired" -> field(fixture.core, "frameRetired").setBoolean(fixture.core, false);
                    case "native-unknown" -> field(fixture.core, "nativeReturnUnconfirmed").setBoolean(fixture.core, true);
                    case "leaf-refused" -> {
                        field(fixture.query, "policyAccepted").setBoolean(fixture.query, false);
                        field(fixture.file, "securityPolicyRefused").setBoolean(fixture.file, true);
                    }
                    case "ancestor-refused" -> {
                        Object core = value(fixture.ancestors, "core");
                        field(core, "allPoliciesAccepted").setBoolean(core, false);
                        fixture.file.finishOriginalAncestors(fixture.security, fixture.ancestors);
                    }
                    default -> { }
                }
                expect(IllegalStateException.class, () -> inspect(fixture.bytes, data));
                check(!(boolean) value(fixture.bytes, "packagedAttempted") && value(fixture.bytes, "packaged") == null);
                check(!(boolean) value(fixture.file, "failed") && fixture.file.completed());
                check(fixture.security.completed() && fixture.ancestors.completed());
                retained(fixture);
            }
        }
    }

    private static void substitution(Object[] data) throws Throwable {
        try (OriginalFileBytesLeaseTests.Fixture fixture = new OriginalFileBytesLeaseTests.Fixture(0x1200, true);
             OriginalFileBytesLeaseTests.Fixture other = new OriginalFileBytesLeaseTests.Fixture(0x1200, true)) {
            ready(fixture, (byte[]) data[1]);
            ready(other, (byte[]) data[1]);
            WindowsPackagedVerifier alien = WindowsPackagedVerifier.forOriginalBytes(other.bytes);
            expect(IllegalStateException.class, () -> fixture.bytes.requireOriginalPackagedVerifier(alien));
            expect(IllegalStateException.class, () -> alien.prepareOriginalBytes((byte[]) data[0],
                (String) data[2], (String) data[3], (String) data[4]));
            check(!(boolean) value(alien, "attempted"));
            WindowsPackagedVerifier plan = inspect(fixture.bytes, data);
            field(fixture.bytes, "packaged").set(fixture.bytes, alien);
            allRefused(plan, IllegalStateException.class);
            allRefused(alien, IllegalStateException.class);
            field(fixture.bytes, "packaged").set(fixture.bytes, plan);
            check(plan.imageLayout()[0] == 0x4000 && fixture.bytes.completed());
            check(!(boolean) value(other.bytes, "packagedAttempted"));
            WindowsPackagedVerifier unowned = WindowsPackagedVerifier.prepare((byte[]) data[0], (byte[]) data[1],
                (String) data[2], (String) data[3], (String) data[4]);
            check(value(unowned, "originalBytes") == null);
            expect(IllegalStateException.class, () -> fixture.bytes.requireOriginalPackagedVerifier(unowned));
            expect(IllegalStateException.class, () -> unowned.prepareOriginalBytes((byte[]) data[0],
                (String) data[2], (String) data[3], (String) data[4]));
            check(unowned.imageLayout()[0] == 0x4000);
            retained(fixture);
        }
    }

    private static void thread(Object[] data) throws Throwable {
        try (OriginalFileBytesLeaseTests.Fixture fixture = new OriginalFileBytesLeaseTests.Fixture(0x1200, true)) {
            ready(fixture, (byte[]) data[1]);
            AtomicReference<Throwable> unexpected = new AtomicReference<>();
            Thread first = Thread.startVirtualThread(() -> {
                try { expect(IllegalStateException.class, () -> inspect(fixture.bytes, data)); }
                catch (Throwable caught) { unexpected.set(caught); }
            });
            first.join();
            check(unexpected.get() == null && !(boolean) value(fixture.bytes, "packagedAttempted"));
            WindowsPackagedVerifier plan = inspect(fixture.bytes, data);
            Thread second = Thread.startVirtualThread(() -> {
                try { allRefused(plan, IllegalStateException.class); }
                catch (Throwable caught) { unexpected.set(caught); }
            });
            second.join();
            check(unexpected.get() == null && plan.imageLayout()[0] == 0x4000 && fixture.bytes.completed());
            retained(fixture);
        }
    }

    private static void success(Object[] data, Class<?> helper, Class<?> declaration, boolean mutate) throws Throwable {
        try (OriginalFileBytesLeaseTests.Fixture fixture = new OriginalFileBytesLeaseTests.Fixture(0x1200, true)) {
            ready(fixture, (byte[]) data[1]);
            byte[][] pages = pages((byte[]) data[1]);
            WindowsPackagedVerifier plan = inspect(fixture.bytes, data);
            check(value(fixture.bytes, "packaged") == plan && value(plan, "originalBytes") == fixture.bytes);
            check(value(plan, "originalVerifier").getClass() == helper && plan.declaringClass() == declaration);
            check((boolean) value(plan, "prepared") && (boolean) value(plan, "attempted"));
            byte[] digest = (byte[]) value(plan, "originalSnapshotSha256");
            check(Arrays.equals(digest, fixture.bytes.sha256()) && digest != value(fixture.core, "observedDigest"));
            check(Arrays.equals(plan.imageLayout(), new long[] {0x4000, 0x2000, 0x800}));
            check(plan.exportNames().length == 24 && plan.exportRvas().length == 24);
            check(Arrays.equals(plan.importNames(), new String[] {"kernel32.dll", "CloseHandle"}));
            check(Arrays.equals(plan.regions(BASE), new long[] {BASE, 4096, 0, BASE + 0x1000, 4096, 1, BASE + 0x2880, 16, 2}));
            long[] targets = targets(plan);
            long[] before = plan.verify(BASE, targets, new long[] {IMPORT}, pages);
            check(before.length == 24 && before[23] == BASE + 0x1017);
            if (mutate) {
                Arrays.fill((byte[]) data[0], (byte) 0);
                Arrays.fill((byte[]) data[1], (byte) 0);
                fixture.bytes.snapshot()[0] = 0;
                fixture.bytes.sha256()[0] ^= 1;
                plan.imageLayout()[0] = 1;
                plan.exportNames()[0] = "substituted";
                plan.exportRvas()[0] = 1;
                plan.importNames()[0] = "substituted";
                plan.regions(BASE)[0] = 1;
                check(Arrays.equals(before, plan.verify(BASE, targets, new long[] {IMPORT}, pages)));
                check(((byte[]) value(fixture.core, "originalSnapshot"))[0] == 'M');
                check(Arrays.equals(digest, fixture.bytes.sha256()));
            }
            expect(IllegalStateException.class, () -> inspect(fixture.bytes, data));
            expect(IllegalStateException.class, () -> plan.prepareOriginalBytes((byte[]) data[0],
                (String) data[2], (String) data[3], (String) data[4]));
            check(value(fixture.bytes, "packaged") == plan && plan.declaringClass() == declaration);
            check(Arrays.equals(plan.verify(BASE, targets, new long[] {IMPORT}, pages), before));
            retained(fixture);
        }
    }

    private static void failure(Object[] data, String mode) throws Throwable {
        try (OriginalFileBytesLeaseTests.Fixture fixture = new OriginalFileBytesLeaseTests.Fixture(0x1200, true)) {
            byte[] library = ((byte[]) data[1]).clone();
            if (mode.equals("malformed-pe")) library[0] ^= 1;
            ready(fixture, library);
            if (mode.equals("hash-mismatch")) ((byte[]) value(fixture.core, "observedDigest"))[0] ^= 1;
            Object[] comparison = data.clone();
            if (mode.equals("invalid-pin")) comparison[2] = "invalid";
            if (mode.equals("manifest-pin")) comparison[2] = "0".repeat(64);
            if (mode.equals("source-pin")) comparison[3] = "c".repeat(40);
            WindowsOriginalProfileDllFileCandidate.Failure root = (WindowsOriginalProfileDllFileCandidate.Failure)
                expect(WindowsOriginalProfileDllFileCandidate.Failure.class, () -> inspect(fixture.bytes, comparison));
            WindowsPackagedVerifier plan = (WindowsPackagedVerifier) value(fixture.bytes, "packaged");
            check(plan != null && value(plan, "originalBytes") == fixture.bytes);
            check((boolean) value(plan, "attempted") && !(boolean) value(plan, "prepared"));
            check(value(plan, "originalVerifier") == null);
            Throwable cause = ((WindowsOriginalProfileDllBytesCandidate.Failure) root.operationFailure).operationFailure;
            if (mode.equals("hash-mismatch")) {
                check(cause instanceof IllegalArgumentException && cause.getMessage().contains("completed original digest"));
            } else if (mode.equals("invalid-pin")) check(cause instanceof IllegalArgumentException);
            else check(cause instanceof InvocationTargetException && cause.getCause() instanceof RuntimeException);
            latched(fixture, plan, root, data);
        }
    }

    private static void operationFailure(Object[] data) throws Throwable {
        for (String mode : new String[] {"regions", "verify", "getter"}) {
            try (OriginalFileBytesLeaseTests.Fixture fixture = new OriginalFileBytesLeaseTests.Fixture(0x1200, true)) {
                ready(fixture, (byte[]) data[1]);
                WindowsPackagedVerifier plan = inspect(fixture.bytes, data);
                WindowsOriginalProfileDllFileCandidate.Failure root;
                if (mode.equals("regions")) {
                    root = (WindowsOriginalProfileDllFileCandidate.Failure)
                        expect(WindowsOriginalProfileDllFileCandidate.Failure.class, () -> plan.regions(1));
                } else if (mode.equals("verify")) {
                    long[] targets = targets(plan);
                    byte[][] pages = pages((byte[]) data[1]);
                    pages[1][0] ^= 1;
                    root = (WindowsOriginalProfileDllFileCandidate.Failure) expect(
                        WindowsOriginalProfileDllFileCandidate.Failure.class, () -> plan.verify(BASE, targets, new long[] {IMPORT}, pages));
                } else {
                    field(plan, "image").set(plan, null); // Inert clone failure: not a claimed real allocation failure.
                    root = (WindowsOriginalProfileDllFileCandidate.Failure)
                        expect(WindowsOriginalProfileDllFileCandidate.Failure.class, plan::imageLayout);
                }
                check((boolean) value(plan, "prepared")); // Completed comparison cannot bypass the terminal owner latch.
                latched(fixture, plan, root, data);
            }
        }
    }

    private static void latched(OriginalFileBytesLeaseTests.Fixture fixture, WindowsPackagedVerifier plan,
        WindowsOriginalProfileDllFileCandidate.Failure root, Object[] data) throws Throwable {
        WindowsOriginalProfileDllBytesCandidate.Failure child =
            (WindowsOriginalProfileDllBytesCandidate.Failure) root.operationFailure;
        check(root.retainedCandidate == fixture.file && child.retainedCandidate == fixture.bytes);
        Throwable cause = child.operationFailure;
        check(cause != null && cause != root && cause != child);
        check((boolean) value(fixture.bytes, "failed") && (boolean) value(fixture.file, "failed"));
        check(expect(WindowsOriginalProfileDllFileCandidate.Failure.class, () -> inspect(fixture.bytes, data)) == root);
        check(expect(WindowsOriginalProfileDllFileCandidate.Failure.class, fixture.bytes::snapshot) == root);
        check(expect(WindowsOriginalProfileDllFileCandidate.Failure.class, fixture.bytes::sha256) == root);
        check(expect(WindowsOriginalProfileDllFileCandidate.Failure.class, fixture.security::completed) == root);
        check(expect(WindowsOriginalProfileDllFileCandidate.Failure.class, fixture.ancestors::completed) == root);
        check(expect(WindowsOriginalProfileDllFileCandidate.Failure.class,
            () -> fixture.bootstrap.originalProfileDllReadEntry(fixture.file)) == root);
        allRefused(plan, WindowsOriginalProfileDllFileCandidate.Failure.class);
        check(expect(WindowsOriginalProfileDllFileCandidate.Failure.class, plan::declaringClass) == root);
        check(root.operationFailure == child && child.operationFailure == cause && value(fixture.bytes, "packaged") == plan);
        retained(fixture);
    }

    private static void allRefused(WindowsPackagedVerifier plan, Class<? extends Throwable> failure) throws Throwable {
        expect(failure, plan::declaringClass);
        expect(failure, plan::imageLayout);
        expect(failure, plan::exportNames);
        expect(failure, plan::exportRvas);
        expect(failure, plan::importNames);
        expect(failure, () -> plan.regions(BASE));
        expect(failure, () -> plan.verify(BASE, new long[24], new long[1], new byte[0][]));
    }

    private static void retained(OriginalFileBytesLeaseTests.Fixture fixture) throws Throwable {
        check(value(fixture.bootstrap, "originalJvm") == null && value(fixture.file, "bytes") == fixture.bytes);
        check(value(fixture.bytes, "core") == fixture.core && value(fixture.core, "fileHandle") == value(fixture.lease, "handle"));
        check(value(fixture.core, "fileArena") == fixture.handleScope && value(fixture.core, "originalProfileDllOwner") == fixture.bytes);
        check(fixture.bootstrapScope.scope().isAlive() && fixture.handleScope.scope().isAlive());
        check(fixture.moduleScope.scope().isAlive() && fixture.ancestorScope.scope().isAlive());
        check(fixture.reads == 0 && fixture.informationCalls == 0 && value(fixture.core, "frameArena") == null);
    }

    private static long[] targets(WindowsPackagedVerifier plan) {
        long[] result = plan.exportRvas();
        for (int index = 0; index < result.length; index++) result[index] += BASE;
        return result;
    }

    private static byte[][] pages(byte[] library) {
        byte[][] result = {new byte[4096], new byte[4096], new byte[16]};
        System.arraycopy(library, 0, result[0], 0, 0x400);
        System.arraycopy(library, 0x400, result[1], 0, 0x200);
        System.arraycopy(library, 0xe80, result[2], 0, 16);
        ByteBuffer.wrap(result[2]).order(ByteOrder.LITTLE_ENDIAN).putLong(IMPORT);
        return result; // Independent established synthetic fixture geometry, not parser-produced expected pages.
    }
}
