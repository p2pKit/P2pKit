package dev.p2pkit.rpc.windows.loader;

import java.lang.foreign.Arena;
import java.lang.foreign.MemorySegment;
import java.nio.file.Files;
import java.nio.file.Path;
import java.security.MessageDigest;
import java.util.Arrays;
import java.util.concurrent.atomic.AtomicReference;

import static dev.p2pkit.rpc.windows.loader.OriginalFileBytesLeaseTests.check;
import static dev.p2pkit.rpc.windows.loader.OriginalFileBytesLeaseTests.core;
import static dev.p2pkit.rpc.windows.loader.OriginalFileBytesLeaseTests.expect;
import static dev.p2pkit.rpc.windows.loader.OriginalFileBytesLeaseTests.field;
import static dev.p2pkit.rpc.windows.loader.OriginalFileBytesLeaseTests.unattached;
import static dev.p2pkit.rpc.windows.loader.OriginalFileBytesLeaseTests.value;

/** Original-DLL snapshot diagnostics; no new channel, load, mapped-image proof or supplied authority. */
public final class ProfileDllBytesCandidateTests {
    private ProfileDllBytesCandidateTests() {}

    public static void main(String[] arguments) throws Throwable {
        check(arguments.length >= 1);
        WindowsLoaderRuntime.requireDiagnosticRuntime();
        String mode = arguments[0];
        String scope = "INERT_TYPED_OWNER_AND_REFUSAL_NOT_NATIVE_BYTES_OR_AUTHORITY";
        String observation = "";
        if (mode.equals("actual")) {
            check(arguments.length == 2);
            observation = " byteObservation=" + actual(arguments[1]);
            scope = "DEVELOPMENT_DLL_SNAPSHOT_NOT_PACKAGE_MAPPING_OR_LOADING_AUTHORITY";
        } else {
            check(arguments.length == 1);
            switch (mode) {
                case "owner-refusal" -> ownerRefusal();
                case "substitution" -> substitution();
                case "missing-security", "leaf-policy-refusal", "missing-ancestors", "ancestor-policy-refusal" -> prerequisite(mode);
                case "failure-latch" -> failureLatch();
                default -> throw new AssertionError("Unknown profile DLL byte control");
            }
        }
        System.out.println("WINDOWS_PROFILE_DLL_BYTES_PASS case=" + mode + " scope=" + scope + observation);
    }

    private static void ownerRefusal() throws Throwable {
        WindowsOriginalProfileDllBytesCandidate bytes = unattached(null, 512);
        WindowsOriginalFileBytesLease core = core(bytes);
        expect(IllegalStateException.class, bytes::observe);
        expect(IllegalStateException.class, bytes::completed);
        expect(IllegalStateException.class, bytes::snapshot);
        expect(IllegalStateException.class, bytes::sha256);
        check(!(boolean) value(bytes, "attempted") && !(boolean) value(core, "attempted"));
        check(value(core, "originalSnapshot") == null && value(core, "frameArena") == null);
        check(value(core, "originalProfileDllOwner") == bytes && value(core, "originalJvmOwner") == null);
    }

    private static void substitution() throws Throwable {
        try (OriginalFileBytesLeaseTests.Fixture fixture = new OriginalFileBytesLeaseTests.Fixture(512, true)) {
            WindowsOriginalProfileDllBytesCandidate other = unattached(fixture.file, 512);
            expect(IllegalStateException.class, other::observe);
            expect(IllegalStateException.class, () -> fixture.file.requireOriginalBytes(other));
            expect(IllegalStateException.class, () -> fixture.bytes.requireOriginalCore(core(other)));
            expect(IllegalStateException.class, () -> fixture.core.snapshot(other));
            expect(IllegalStateException.class, () -> fixture.lease.newProfileDllBytes(null));
            WindowsOriginalProfileDllFileCandidate foreign = new WindowsOriginalProfileDllFileCandidate(null,
                OriginalFileBytesLeaseTests.LOCATOR);
            expect(IllegalStateException.class, () -> fixture.lease.newProfileDllBytes(foreign));
            check(!(boolean) value(fixture.core, "attempted") && !(boolean) value(fixture.bytes, "attempted"));
            check(value(fixture.core, "frameArena") == null && value(fixture.core, "originalSnapshot") == null);
            check(value(fixture.bootstrap, "originalJvm") == null && fixture.file.leaseHeld());
        }
    }

    private static void prerequisite(String mode) throws Throwable {
        try (OriginalFileBytesLeaseTests.Fixture fixture = new OriginalFileBytesLeaseTests.Fixture(512, false)) {
            switch (mode) {
                case "missing-security" -> field(fixture.file, "security").set(fixture.file, null);
                case "leaf-policy-refusal" -> {
                    field(fixture.query, "policyAccepted").setBoolean(fixture.query, false);
                    field(fixture.file, "securityPolicyRefused").setBoolean(fixture.file, true);
                }
                case "missing-ancestors" -> field(fixture.security, "ancestors").set(fixture.security, null);
                case "ancestor-policy-refusal" -> {
                    Object ancestorCore = value(fixture.ancestors, "core");
                    field(ancestorCore, "allPoliciesAccepted").setBoolean(ancestorCore, false);
                    fixture.file.finishOriginalAncestors(fixture.security, fixture.ancestors);
                }
                default -> throw new AssertionError("Unknown prerequisite control");
            }
            expect(IllegalStateException.class, fixture.file::inspectBytes);
            byteInputsRefused(fixture.bootstrap, fixture.file, fixture.lease);
            check(!(boolean) value(fixture.file, "bytesAttempted") && value(fixture.file, "bytes") == null);
            check(!(boolean) value(fixture.file, "failed") && fixture.file.completed() && fixture.file.leaseHeld());
            check(fixture.handleScope.scope().isAlive() && fixture.moduleScope.scope().isAlive() && fixture.ancestorScope.scope().isAlive());
            if (!mode.equals("missing-security")) check(fixture.security.completed());
            if (mode.equals("leaf-policy-refusal")) check(!fixture.security.descriptorPolicyAccepted());
            if (mode.equals("ancestor-policy-refusal")) {
                check(fixture.security.descriptorPolicyAccepted() && fixture.ancestors.completed());
                check(!fixture.ancestors.descriptorPoliciesAccepted() && (boolean) value(fixture.file, "ancestorsPolicyRefused"));
            }
        }
    }

    private static void failureLatch() throws Throwable {
        try (OriginalFileBytesLeaseTests.Fixture fixture = new OriginalFileBytesLeaseTests.Fixture(511, false)) {
            // Inert source metadata is deliberately below the DLL bound. The original byte core is
            // attached and consumed, but no snapshot/frame/downcall is allocated or invoked.
            WindowsOriginalProfileDllFileCandidate.Failure root =
                (WindowsOriginalProfileDllFileCandidate.Failure) expect(
                    WindowsOriginalProfileDllFileCandidate.Failure.class, fixture.file::inspectBytes);
            WindowsOriginalProfileDllBytesCandidate bytes =
                (WindowsOriginalProfileDllBytesCandidate) value(fixture.file, "bytes");
            WindowsOriginalFileBytesLease core = core(bytes);
            WindowsOriginalProfileDllBytesCandidate.Failure child =
                (WindowsOriginalProfileDllBytesCandidate.Failure) root.operationFailure;
            WindowsOriginalFileBytesLease.Failure coreFailure = (WindowsOriginalFileBytesLease.Failure) child.operationFailure;
            check(root.retainedCandidate == fixture.file && child.retainedCandidate == bytes && coreFailure.retainedCandidate == core);
            check(coreFailure.operationFailure instanceof IllegalStateException);
            check((boolean) value(fixture.file, "failed") && (boolean) value(bytes, "failed"));
            check((boolean) value(fixture.file, "bytesAttempted") && (boolean) value(core, "attempted"));
            check(!(boolean) value(core, "streamAttempted") && (int) value(core, "readCalls") == 0);
            check(value(core, "frameArena") == null && value(core, "originalSnapshot") == null && value(core, "observedDigest") == null);
            check((boolean) value(core, "frameRetired") && !(boolean) value(core, "nativeReturnUnconfirmed"));
            check(expect(WindowsOriginalProfileDllFileCandidate.Failure.class, fixture.file::inspectBytes) == root);
            check(expect(WindowsOriginalProfileDllFileCandidate.Failure.class, fixture.file::completed) == root);
            check(expect(WindowsOriginalProfileDllFileCandidate.Failure.class, bytes::completed) == root);
            check(expect(WindowsOriginalProfileDllFileCandidate.Failure.class, bytes::snapshot) == root);
            check(expect(WindowsOriginalProfileDllFileCandidate.Failure.class, fixture.security::completed) == root);
            check(expect(WindowsOriginalProfileDllFileCandidate.Failure.class, fixture.ancestors::completed) == root);
            check(expect(WindowsOriginalProfileDllFileCandidate.Failure.class,
                () -> fixture.bootstrap.originalProfileDllReadEntry(fixture.file)) == root);
            check(root.operationFailure == child && child.operationFailure == coreFailure);
            check(value(core, "fileHandle") == value(fixture.lease, "handle") && value(core, "fileArena") == fixture.handleScope);
            check(fixture.handleScope.scope().isAlive() && fixture.moduleScope.scope().isAlive() && fixture.ancestorScope.scope().isAlive());
        }
    }

    private static String actual(String source) throws Throwable {
        WindowsProfileDllPath.require(source);
        Path path = Path.of(source);
        check(path.isAbsolute() && path.equals(path.normalize()));
        long length = Files.size(path); // Development fixture size only; never a second byte channel or independent pin.
        check(length >= 512 && length <= 32L * 1024 * 1024);
        WindowsSystemBootstrapCandidate bootstrap = WindowsSystemBootstrapCandidate.inspect();
        WindowsOriginalProfileDllFileCandidate file = bootstrap.inspectOriginalProfileDll(source);
        WindowsOriginalFileLease lease = (WindowsOriginalFileLease) value(file, "lease");
        MemorySegment handle = (MemorySegment) value(lease, "handle");
        Arena handleArena = (Arena) value(lease, "handleArena");
        WindowsOriginalProfileDllSecurityCandidate security = file.inspectSecurity();
        if (!security.descriptorPolicyAccepted()) {
            refusedActual(bootstrap, file, lease, handle, handleArena);
            check(value(security, "ancestors") == null && !(boolean) value(security, "ancestorsAttempted"));
            check(security.completed() && !security.descriptorPolicyAccepted());
            return "NOT_EXECUTED_LEAF_POLICY_REFUSED";
        }
        WindowsOriginalProfileDllAncestorsCandidate ancestors = security.inspectAncestors();
        if (!ancestors.descriptorPoliciesAccepted()) {
            refusedActual(bootstrap, file, lease, handle, handleArena);
            check(ancestors.completed() && !ancestors.descriptorPoliciesAccepted() && security.completed());
            return "NOT_EXECUTED_ANCESTOR_POLICY_REFUSED";
        }
        WindowsOriginalProfileDllBytesCandidate bytes = file.inspectBytes();
        WindowsOriginalFileBytesLease core = core(bytes);
        check(bytes.completed() && bytes.byteCount() == length);
        check(value(core, "originalProfileDllOwner") == bytes && value(core, "originalJvmOwner") == null);
        check(value(file, "bytes") == bytes && value(bytes, "file") == file);
        check(value(core, "fileHandle") == handle && value(core, "fileArena") == handleArena);
        check(value(core, "bootstrapArena") == value(bootstrap, "originalArena"));
        MemorySegment[] entries = (MemorySegment[]) value(bootstrap, "entries");
        check(value(core, "readEntry") == entries[13] && value(core, "informationEntry") == entries[9]);
        Object ancestorCore = value(ancestors, "core");
        MemorySegment[] ancestorHandles = (MemorySegment[]) value(ancestorCore, "handles");
        check(handle != ancestorHandles[ancestors.ancestorCount()] &&
            handle.address() != ancestorHandles[ancestors.ancestorCount()].address());
        check(value(ancestorCore, "originalFileHandle") == handle && value(ancestorCore, "originalFileArena") == handleArena);
        check(Arrays.equals((long[]) value(core, "originalMetadata"), (long[]) value(lease, "first")));
        check(Arrays.equals((long[]) value(core, "repeatedMetadata"), (long[]) value(lease, "first")));
        check(value(core, "originalMetadata") != value(lease, "first"));
        check((int) value(core, "readCalls") == (length + 65_535) / 65_536 + 1);
        check((int) value(core, "readCalls") <= 513 && (long) value(core, "returnedBytes") == 0 &&
            (int) value(core, "returnedStatus") != 0);
        check((boolean) value(core, "frameRetired") && !(boolean) value(core, "nativeReturnUnconfirmed") &&
            !(boolean) value(core, "readCompletionUnconfirmed"));
        check(!((Arena) value(core, "frameArena")).scope().isAlive());
        byte[] original = (byte[]) value(core, "originalSnapshot");
        byte[] copy = bytes.snapshot(); // At most one bounded public copy, not several 32MiB expected arrays.
        check(original.length == length && copy != original && Arrays.equals(original, copy));
        check(MessageDigest.isEqual(MessageDigest.getInstance("SHA-256", "SUN").digest(copy), bytes.sha256()));
        byte first = original[0];
        copy[0] ^= 1;
        check(original[0] == first);
        byte[] digest = bytes.sha256();
        digest[0] ^= 1;
        check(!MessageDigest.isEqual(digest, bytes.sha256()));
        expect(IllegalStateException.class, file::inspectBytes);
        expect(IllegalStateException.class, bytes::observe);
        expect(IllegalStateException.class, unattached(file, length)::observe);
        AtomicReference<Throwable> unexpected = new AtomicReference<>();
        Thread worker = Thread.startVirtualThread(() -> {
            try {
                expect(IllegalStateException.class, bytes::completed);
                expect(IllegalStateException.class, bytes::snapshot);
                expect(IllegalStateException.class, bytes::sha256);
                expect(IllegalStateException.class, file::inspectBytes);
            } catch (Throwable caught) { unexpected.set(caught); }
        });
        worker.join();
        check(unexpected.get() == null);
        System.gc();
        check(bytes.completed() && bytes.byteCount() == length && security.completed() && ancestors.completed());
        actualContinuity(bootstrap, file, lease, handle, handleArena);
        return "COMPLETED";
    }

    private static void refusedActual(WindowsSystemBootstrapCandidate bootstrap, WindowsOriginalProfileDllFileCandidate file,
        WindowsOriginalFileLease lease, MemorySegment handle, Arena handleArena) throws Throwable {
        expect(IllegalStateException.class, file::inspectBytes);
        byteInputsRefused(bootstrap, file, lease);
        check(value(file, "bytes") == null && !(boolean) value(file, "bytesAttempted"));
        check(!(boolean) value(file, "failed"));
        actualContinuity(bootstrap, file, lease, handle, handleArena);
    }

    private static void byteInputsRefused(WindowsSystemBootstrapCandidate bootstrap, WindowsOriginalProfileDllFileCandidate file,
        WindowsOriginalFileLease lease) throws Throwable {
        expect(IllegalStateException.class, file::requireOriginalByteInputs);
        expect(IllegalStateException.class, () -> file.originalReadEntry(lease));
        expect(IllegalStateException.class, () -> bootstrap.originalProfileDllReadEntry(file));
        expect(IllegalStateException.class, () -> lease.newProfileDllBytes(file));
    }

    private static void actualContinuity(WindowsSystemBootstrapCandidate bootstrap, WindowsOriginalProfileDllFileCandidate file,
        WindowsOriginalFileLease lease, MemorySegment handle, Arena handleArena) throws Throwable {
        check(file.completed() && file.leaseHeld() && bootstrap.completed());
        check(value(lease, "handle") == handle && handleArena.scope().isAlive());
        check(value(bootstrap, "profileDll") == file && value(bootstrap, "originalJvm") == null &&
            !(boolean) value(bootstrap, "originalJvmAttempted"));
        Throwable refusal = expect(WindowsLoader.Unavailable.class, WindowsLoader::openInstalledProvider);
        check(WindowsLoader.REFUSAL.equals(refusal.getMessage()));
    }
}
