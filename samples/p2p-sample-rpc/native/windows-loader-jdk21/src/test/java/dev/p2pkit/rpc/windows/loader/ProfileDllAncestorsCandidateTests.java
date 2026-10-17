package dev.p2pkit.rpc.windows.loader;

import java.lang.foreign.Arena;
import java.lang.foreign.Linker;
import java.lang.foreign.MemorySegment;
import java.lang.reflect.Constructor;
import java.lang.reflect.Field;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Arrays;
import java.util.concurrent.atomic.AtomicReference;

/** DLL ancestor diagnostics. Inert state controls and actual observations are deliberately separate. */
public final class ProfileDllAncestorsCandidateTests {
    private static final String LOCATOR = "C:\\fixture\\p2pkit-windows-profile.dll";
    private ProfileDllAncestorsCandidateTests() {}

    public static void main(String[] arguments) throws Throwable {
        check(arguments.length >= 1);
        WindowsLoaderRuntime.requireDiagnosticRuntime();
        String mode = arguments[0];
        String scope = "INERT_TYPED_OWNER_AND_REFUSAL_NOT_NATIVE_ANCESTORS_OR_AUTHORITY";
        String policy = "";
        if (mode.equals("actual")) {
            check(arguments.length == 2);
            policy = " ancestorPolicy=" + actual(arguments[1]);
            scope = "DEVELOPMENT_DLL_ANCESTOR_DIAGNOSTIC_NOT_BYTES_MAPPING_OR_LOADING_AUTHORITY";
        } else {
            check(arguments.length == 1);
            switch (mode) {
                case "owner-refusal" -> ownerRefusal();
                case "substitution" -> substitution();
                case "failure-latch" -> failureLatch();
                case "leaf-policy-refusal" -> leafPolicyRefusal();
                case "ancestor-policy-refusal" -> ancestorPolicyRefusal();
                default -> throw new AssertionError("Unknown profile DLL ancestor control");
            }
        }
        System.out.println("WINDOWS_PROFILE_DLL_ANCESTORS_PASS case=" + mode + " scope=" + scope + policy);
    }

    private static WindowsOriginalProfileDllAncestorsCandidate unattached(WindowsOriginalProfileDllSecurityCandidate security) {
        return new WindowsOriginalProfileDllAncestorsCandidate(security, null, null, null, null, null, null,
            null, null, null, null, null, null, null, null, new char[4], 3, new long[8]);
    }

    private static void ownerRefusal() throws Throwable {
        WindowsOriginalProfileDllAncestorsCandidate owner = unattached(null);
        WindowsOriginalFileAncestorsLease core = core(owner);
        check(value(core, "originalProfileDllOwner") == owner && value(core, "originalJvmOwner") == null);
        expect(IllegalStateException.class, owner::observe);
        expect(IllegalStateException.class, owner::completed);
        expect(IllegalStateException.class, owner::ancestorCount);
        expect(IllegalStateException.class, owner::descriptorPoliciesAccepted);
        check(!(boolean) value(owner, "attempted") && !(boolean) value(core, "attempted"));
        check(value(core, "frameArena") == null && value(core, "leaseArena") == null);
        check(((WindowsOriginalProfileDllAncestorsCandidate.Failure) value(owner, "failure")).retainedCandidate == owner);
        check(((WindowsOriginalFileAncestorsLease.Failure) value(core, "failure")).retainedCandidate == core);
    }

    private static void substitution() throws Throwable {
        try (Fixture fixture = new Fixture(true)) {
            WindowsOriginalProfileDllAncestorsCandidate retained = fixture.attach();
            WindowsOriginalProfileDllAncestorsCandidate other = unattached(fixture.security);
            expect(IllegalStateException.class, other::observe);
            expect(IllegalStateException.class, () -> retained.requireOriginalCore(core(other)));
            expect(IllegalStateException.class, () -> fixture.security.requireOriginalAncestors(other));
            expect(IllegalStateException.class, () -> fixture.query.newProfileDllAncestors(null));
            WindowsOriginalProfileDllSecurityCandidate foreign = new WindowsOriginalProfileDllSecurityCandidate(
                null, null, null, null, null, null, null, null, null);
            expect(IllegalStateException.class, () -> fixture.query.newProfileDllAncestors(foreign));
            expect(IllegalStateException.class, () -> fixture.query.newJvmAncestors(null));
            expect(IllegalStateException.class, () -> fixture.query.newProfileDllAncestors(fixture.security));
            expect(IllegalStateException.class, () -> fixture.lease.newProfileDllAncestors(null, fixture.security,
                fixture.moduleScope, fixture.module, fixture.entry, null, null));
            check(value(core(retained), "originalFileHandle") == value(fixture.lease, "handle"));
            check(value(core(retained), "originalFileArena") == fixture.handleScope);
            check(!(boolean) value(core(retained), "attempted") && value(core(retained), "frameArena") == null);
            check(value(fixture.bootstrap, "originalJvm") == null && fixture.file.completed());
        }
    }

    private static void failureLatch() throws Throwable {
        try (Fixture fixture = new Fixture(true)) {
            // Metadata volume remains zero. All owners/entries are inert but attached; path validation
            // fails after attachment, before native descriptors, lookup, frame allocation or any call.
            WindowsOriginalProfileDllFileCandidate.Failure root =
                (WindowsOriginalProfileDllFileCandidate.Failure) expect(
                    WindowsOriginalProfileDllFileCandidate.Failure.class, fixture.security::inspectAncestors);
            WindowsOriginalProfileDllAncestorsCandidate ancestor =
                (WindowsOriginalProfileDllAncestorsCandidate) value(fixture.security, "ancestors");
            WindowsOriginalFileAncestorsLease core = core(ancestor);
            WindowsOriginalProfileDllSecurityCandidate.Failure securityFailure =
                (WindowsOriginalProfileDllSecurityCandidate.Failure) root.operationFailure;
            WindowsOriginalProfileDllAncestorsCandidate.Failure ancestorFailure =
                (WindowsOriginalProfileDllAncestorsCandidate.Failure) securityFailure.operationFailure;
            WindowsOriginalFileAncestorsLease.Failure coreFailure =
                (WindowsOriginalFileAncestorsLease.Failure) ancestorFailure.operationFailure;
            check(root.retainedCandidate == fixture.file && securityFailure.retainedCandidate == fixture.security);
            check(ancestorFailure.retainedCandidate == ancestor && coreFailure.retainedCandidate == core);
            check(coreFailure.operationFailure instanceof IllegalStateException);
            check((boolean) value(fixture.file, "failed") && (boolean) value(fixture.security, "failed"));
            check((boolean) value(ancestor, "failed") && (boolean) value(core, "attempted"));
            check(value(core, "frameArena") == null && value(core, "leaseArena") == null);
            check((boolean) value(core, "frameRetired") && !(boolean) value(core, "nativeReturnUnconfirmed"));
            check((int) value(core, "errorCount") == 0 && (int) value(core, "openedCount") == 0);
            check(expect(WindowsOriginalProfileDllFileCandidate.Failure.class, fixture.security::inspectAncestors) == root);
            check(expect(WindowsOriginalProfileDllFileCandidate.Failure.class, fixture.security::completed) == root);
            check(expect(WindowsOriginalProfileDllFileCandidate.Failure.class, fixture.file::completed) == root);
            check(expect(WindowsOriginalProfileDllFileCandidate.Failure.class, ancestor::completed) == root);
            check(expect(WindowsOriginalProfileDllFileCandidate.Failure.class, fixture.file::originalLinker) == root);
            check(expect(WindowsOriginalProfileDllFileCandidate.Failure.class,
                () -> fixture.bootstrap.originalProfileDllAncestorsEntry(fixture.file, 0)) == root);
            check(root.operationFailure == securityFailure && securityFailure.operationFailure == ancestorFailure);
            check(fixture.handleScope.scope().isAlive() && fixture.moduleScope.scope().isAlive());
            check(value(fixture.bootstrap, "profileDll") == fixture.file && value(fixture.bootstrap, "originalJvm") == null);
        }
    }

    private static void leafPolicyRefusal() throws Throwable {
        try (Fixture fixture = new Fixture(false)) {
            check(fixture.security.completed() && !fixture.security.descriptorPolicyAccepted());
            expect(IllegalStateException.class, fixture.security::inspectAncestors);
            nativeInputsRefused(fixture.file, fixture.security);
            check(!(boolean) value(fixture.security, "ancestorsAttempted") && value(fixture.security, "ancestors") == null);
            check(!(boolean) value(fixture.file, "failed") && !(boolean) value(fixture.security, "failed"));
            check(fixture.security.completed() && fixture.file.leaseHeld());
        }
    }

    private static void ancestorPolicyRefusal() throws Throwable {
        try (Fixture fixture = new Fixture(true); Arena ancestorScope = Arena.ofConfined()) {
            WindowsOriginalProfileDllAncestorsCandidate ancestor = fixture.attach();
            WindowsOriginalFileAncestorsLease core = core(ancestor);
            // Inert state transition only: no call/ACL acceptance/native chain is fabricated as evidence.
            field(core, "succeeded").setBoolean(core, true);
            field(core, "frameRetired").setBoolean(core, true);
            field(core, "componentCount").setInt(core, 2);
            field(core, "directoryCount").setInt(core, 2);
            field(core, "openedCount").setInt(core, 3);
            field(core, "leaseArena").set(core, ancestorScope);
            field(core, "allPoliciesAccepted").setBoolean(core, false);
            fixture.file.finishOriginalAncestors(fixture.security, ancestor);
            check(ancestor.completed() && ancestor.ancestorCount() == 2 && !ancestor.descriptorPoliciesAccepted());
            check((boolean) value(fixture.file, "ancestorsPolicyRefused"));
            check(!(boolean) value(fixture.file, "securityPolicyRefused") && fixture.security.descriptorPolicyAccepted());
            nativeInputsRefused(fixture.file, fixture.security);
            expect(IllegalStateException.class, ancestor::requireOriginalNativeInputs);
            expect(IllegalStateException.class, fixture.security::inspectAncestors);
            check(ancestor.completed() && fixture.security.completed() && fixture.file.leaseHeld());
            check(!(boolean) value(fixture.file, "failed") && !(boolean) value(fixture.security, "failed"));
            check(ancestorScope.scope().isAlive() && fixture.handleScope.scope().isAlive());
        }
    }

    /** Test-owned allocations only. None is passed to native code or classified as an actual OS handle. */
    private static final class Fixture implements AutoCloseable {
        final Arena bootstrapScope = Arena.ofConfined();
        final Arena handleScope = Arena.ofConfined();
        final Arena moduleScope = Arena.ofConfined();
        final WindowsSystemBootstrapCandidate bootstrap;
        final WindowsOriginalProfileDllFileCandidate file;
        final WindowsOriginalFileLease lease;
        final WindowsOriginalProfileDllSecurityCandidate security;
        final WindowsOriginalFileSecurityQuery query;
        final MemorySegment module = moduleScope.allocate(1).asSlice(0, 0);
        final MemorySegment entry = moduleScope.allocate(1).asSlice(0, 0);

        Fixture(boolean leafPolicy) throws ReflectiveOperationException {
            Constructor<WindowsSystemBootstrapCandidate> constructor =
                WindowsSystemBootstrapCandidate.class.getDeclaredConstructor(Linker.class);
            constructor.setAccessible(true);
            bootstrap = constructor.newInstance((Object) null);
            field(bootstrap, "originalArena").set(bootstrap, bootstrapScope);
            field(bootstrap, "succeeded").setBoolean(bootstrap, true);
            field(bootstrap, "frameRetired").setBoolean(bootstrap, true);
            MemorySegment[] entries = (MemorySegment[]) value(bootstrap, "entries");
            for (int index = 1; index <= 12; index++) entries[index] = bootstrapScope.allocate(1).asSlice(0, 0);
            file = new WindowsOriginalProfileDllFileCandidate(bootstrap, LOCATOR);
            field(bootstrap, "profileDll").set(bootstrap, file);
            field(bootstrap, "profileDllAttempted").setBoolean(bootstrap, true);
            field(file, "attempted").setBoolean(file, true);
            field(file, "originalPath").set(file, (LOCATOR + '\0').toCharArray());
            lease = WindowsOriginalFileLease.forProfileDll(file);
            field(file, "lease").set(file, lease);
            field(file, "succeeded").setBoolean(file, true);
            field(lease, "succeeded").setBoolean(lease, true);
            field(lease, "frameRetired").setBoolean(lease, true);
            MemorySegment handle = handleScope.allocate(1).asSlice(0, 0);
            field(lease, "handle").set(lease, handle);
            field(lease, "rawHandle").setLong(lease, handle.address());
            field(lease, "handleArena").set(lease, handleScope);
            security = lease.newProfileDllSecurity(file);
            field(file, "security").set(file, security);
            field(file, "securityAttempted").setBoolean(file, true);
            field(file, "securityPolicyRefused").setBoolean(file, !leafPolicy);
            query = query(security);
            field(query, "succeeded").setBoolean(query, true);
            field(query, "frameRetired").setBoolean(query, true);
            field(query, "ntReturned").setBoolean(query, true);
            field(query, "policyEvaluated").setBoolean(query, true);
            field(query, "policyAccepted").setBoolean(query, leafPolicy);
            field(query, "exactDescriptor").set(query, new byte[20]);
            field(query, "moduleArena").set(query, moduleScope);
            field(query, "module").set(query, module);
            field(query, "entry").set(query, entry);
        }

        WindowsOriginalProfileDllAncestorsCandidate attach() throws ReflectiveOperationException {
            field(security, "ancestorsAttempted").setBoolean(security, true);
            WindowsOriginalProfileDllAncestorsCandidate ancestor = query.newProfileDllAncestors(security);
            field(security, "ancestors").set(security, ancestor);
            return ancestor;
        }

        @Override public void close() { moduleScope.close(); handleScope.close(); bootstrapScope.close(); }
    }

    private static String actual(String source) throws Throwable {
        WindowsProfileDllPath.require(source);
        Path path = Path.of(source);
        check(path.isAbsolute() && path.equals(path.normalize()));
        long length = Files.size(path); // Development locator/size only; no second byte channel or authority.
        check(length >= 512 && length <= 32L * 1024 * 1024);
        WindowsSystemBootstrapCandidate bootstrap = WindowsSystemBootstrapCandidate.inspect();
        WindowsOriginalProfileDllFileCandidate file = bootstrap.inspectOriginalProfileDll(source);
        WindowsOriginalFileLease lease = lease(file);
        MemorySegment handle = (MemorySegment) value(lease, "handle");
        Arena handleArena = (Arena) value(lease, "handleArena");
        WindowsOriginalProfileDllSecurityCandidate security = file.inspectSecurity();
        WindowsOriginalFileSecurityQuery query = query(security);
        check(security.completed() && value(query, "fileHandle") == handle && value(query, "fileArena") == handleArena);
        check(((long[]) value(lease, "first"))[4] == length && file.leaseHeld());
        if (!security.descriptorPolicyAccepted()) {
            expect(IllegalStateException.class, security::inspectAncestors);
            nativeInputsRefused(file, security);
            check(!(boolean) value(security, "ancestorsAttempted") && value(security, "ancestors") == null);
            check(!(boolean) value(file, "failed") && !(boolean) value(security, "failed"));
            actualContinuity(bootstrap, file, security, handle, handleArena);
            return "NOT_EXECUTED_LEAF_POLICY_REFUSED";
        }
        WindowsOriginalProfileDllAncestorsCandidate ancestor = security.inspectAncestors();
        WindowsOriginalFileAncestorsLease core = core(ancestor);
        boolean accepted = ancestor.descriptorPoliciesAccepted();
        check(ancestor.completed() && ancestor.ancestorCount() >= 1 && ancestor.ancestorCount() <= 63);
        check(value(security, "ancestors") == ancestor && value(ancestor, "security") == security);
        check(value(core, "originalProfileDllOwner") == ancestor && value(core, "originalJvmOwner") == null);
        check(value(core, "originalFileHandle") == handle && value(core, "originalFileArena") == handleArena);
        check(value(core, "moduleArena") == value(query, "moduleArena") && value(core, "module") == value(query, "module"));
        check(value(core, "queryEntry") == value(query, "entry") && value(core, "bootstrapArena") == value(bootstrap, "originalArena"));
        MemorySegment[] entries = (MemorySegment[]) value(bootstrap, "entries");
        MemorySegment[] originalEntries = (MemorySegment[]) value(core, "systemEntries");
        int[] expected = {1, 4, 8, 9, 10, 11, 12};
        for (int index = 0; index < expected.length; index++) check(originalEntries[index] == entries[expected[index]]);
        check((boolean) value(core, "frameRetired") && !(boolean) value(core, "nativeReturnUnconfirmed"));
        check(!(boolean) value(core, "ntCompletionUnconfirmed") && !((Arena) value(core, "frameArena")).scope().isAlive());
        check(((Arena) value(core, "leaseArena")).scope().isAlive());
        check((long) value(core, "rawEntry") == ((MemorySegment) value(core, "ntCreateEntry")).address());
        check((long) value(core, "rawProvider") == ((MemorySegment) value(query, "module")).address());
        int count = ancestor.ancestorCount();
        check((int) value(core, "openedCount") == count + 1 && (int) value(core, "componentCount") == count);
        MemorySegment[] handles = (MemorySegment[]) value(core, "handles");
        long[] rawHandles = (long[]) value(core, "rawHandles");
        for (int index = 0; index <= count; index++) {
            check(handles[index] != null && handles[index].address() == rawHandles[index] && handles[index] != handle);
            check(handles[index].scope().equals(((Arena) value(core, "leaseArena")).scope()));
            if (index > 0) {
                check(((int[]) value(core, "nativeStatuses"))[index] == 0 && ((int[]) value(core, "ioStatuses"))[index] == 0);
                check(((long[]) value(core, "ioInformation"))[index] == 1);
            }
        }
        check(Arrays.equals(((long[][]) value(core, "metadata"))[count], (long[]) value(lease, "first")));
        check(Arrays.equals((long[]) value(core, "originalFile"), (long[]) value(lease, "first")));
        check(value(core, "originalFile") != value(lease, "first"));
        check(Arrays.equals((char[]) value(core, "originalPath"), (char[]) value(lease, "sourcePath")));
        check(value(core, "originalPath") != value(lease, "sourcePath"));
        boolean allAccepted = true;
        for (int index = 0; index < count; index++) {
            check(((int[]) value(core, "queryStatuses"))[index] == 0);
            byte[] descriptor = ((byte[][]) value(core, "descriptors"))[index];
            check(descriptor.length >= 20 && descriptor.length <= 65_536);
            check(descriptor.length == ((int[]) value(core, "descriptorLengths"))[index]);
            boolean independentlyAccepted;
            try {
                WindowsInstallationSecurity.require(descriptor.clone(), index == 0 ?
                    WindowsInstallationSecurity.Kind.VOLUME_ROOT : WindowsInstallationSecurity.Kind.DIRECTORY);
                independentlyAccepted = true;
            } catch (IllegalArgumentException refused) { independentlyAccepted = false; }
            check(((boolean[]) value(core, "policies"))[index] == independentlyAccepted);
            allAccepted &= independentlyAccepted;
        }
        check(accepted == allAccepted && (boolean) value(file, "ancestorsPolicyRefused") == !accepted);
        expect(IllegalStateException.class, security::inspectAncestors);
        expect(IllegalStateException.class, ancestor::observe);
        expect(IllegalStateException.class, unattached(security)::observe);
        if (!accepted) nativeInputsRefused(file, security);
        AtomicReference<Throwable> unexpected = new AtomicReference<>();
        Thread worker = Thread.startVirtualThread(() -> {
            try {
                expect(IllegalStateException.class, ancestor::completed);
                expect(IllegalStateException.class, ancestor::descriptorPoliciesAccepted);
                expect(IllegalStateException.class, security::inspectAncestors);
            } catch (Throwable caught) { unexpected.set(caught); }
        });
        worker.join();
        check(unexpected.get() == null);
        System.gc();
        check(ancestor.completed() && ancestor.ancestorCount() == count && ancestor.descriptorPoliciesAccepted() == accepted);
        actualContinuity(bootstrap, file, security, handle, handleArena);
        return accepted ? "ACCEPTED" : "REFUSED";
    }

    private static void actualContinuity(WindowsSystemBootstrapCandidate bootstrap, WindowsOriginalProfileDllFileCandidate file,
        WindowsOriginalProfileDllSecurityCandidate security, MemorySegment handle, Arena handleArena) throws Throwable {
        check(file.completed() && file.leaseHeld() && security.completed() && bootstrap.completed());
        check(value(lease(file), "handle") == handle && handleArena.scope().isAlive());
        check(value(bootstrap, "profileDll") == file && value(bootstrap, "originalJvm") == null);
        check(!(boolean) value(bootstrap, "originalJvmAttempted"));
        Throwable refusal = expect(WindowsLoader.Unavailable.class, WindowsLoader::openInstalledProvider);
        check(WindowsLoader.REFUSAL.equals(refusal.getMessage()));
    }

    private static void nativeInputsRefused(WindowsOriginalProfileDllFileCandidate file,
        WindowsOriginalProfileDllSecurityCandidate security) throws Throwable {
        WindowsSystemBootstrapCandidate bootstrap = (WindowsSystemBootstrapCandidate) value(file, "bootstrap");
        WindowsOriginalFileLease lease = lease(file);
        WindowsOriginalFileSecurityQuery query = query(security);
        expect(IllegalStateException.class, file::originalLinker);
        expect(IllegalStateException.class, file::originalBootstrapArena);
        expect(IllegalStateException.class, file::originalPathSnapshot);
        expect(IllegalStateException.class, () -> file.originalFileEntry(0));
        expect(IllegalStateException.class, () -> file.originalSecurityEntry(lease, 0));
        expect(IllegalStateException.class, () -> file.originalAncestorsEntry(lease, 0));
        expect(IllegalStateException.class, () -> bootstrap.originalProfileDllLinker(file));
        expect(IllegalStateException.class, () -> bootstrap.originalProfileDllArena(file));
        expect(IllegalStateException.class, () -> bootstrap.originalProfileDllFileEntry(file, 0));
        expect(IllegalStateException.class, () -> bootstrap.originalProfileDllSecurityEntry(file, 0));
        expect(IllegalStateException.class, () -> bootstrap.originalProfileDllAncestorsEntry(file, 0));
        expect(IllegalStateException.class, () -> lease.newProfileDllSecurity(file));
        expect(IllegalStateException.class, () -> WindowsOriginalFileLease.forProfileDll(file));
        expect(IllegalStateException.class, security::requireOriginalAncestorInputs);
        expect(IllegalStateException.class, () -> query.newProfileDllAncestors(security));
        expect(IllegalStateException.class, () -> file.newOriginalAncestors(security, null, null, null, null, null));
        expect(IllegalStateException.class, () -> lease.newProfileDllAncestors(file, security, null, null, null, null, null));
    }
    private static WindowsOriginalFileLease lease(WindowsOriginalProfileDllFileCandidate file)
        throws ReflectiveOperationException { return (WindowsOriginalFileLease) value(file, "lease"); }
    private static WindowsOriginalFileSecurityQuery query(WindowsOriginalProfileDllSecurityCandidate security)
        throws ReflectiveOperationException { return (WindowsOriginalFileSecurityQuery) value(security, "query"); }
    private static WindowsOriginalFileAncestorsLease core(WindowsOriginalProfileDllAncestorsCandidate ancestor)
        throws ReflectiveOperationException { return (WindowsOriginalFileAncestorsLease) value(ancestor, "core"); }
    private static Field field(Object owner, String name) throws ReflectiveOperationException {
        Field field = owner.getClass().getDeclaredField(name);
        field.setAccessible(true);
        return field;
    }
    private static Object value(Object owner, String name) throws ReflectiveOperationException { return field(owner, name).get(owner); }
    private interface Action { void run() throws Throwable; }
    private static Throwable expect(Class<? extends Throwable> type, Action action) {
        try { action.run(); }
        catch (Throwable caught) {
            if (type.isInstance(caught)) return caught;
            throw new AssertionError("Unexpected profile DLL ancestor failure", caught);
        }
        throw new AssertionError("Expected profile DLL ancestor refusal");
    }
    private static void check(boolean condition) {
        if (!condition) throw new AssertionError("Profile DLL ancestor control failed");
    }
}
