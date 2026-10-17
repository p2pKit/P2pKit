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

/** Independent DLL security diagnostics; no DLL load, ancestor acquisition, SACL request or authority. */
public final class ProfileDllSecurityCandidateTests {
    private static final String LOCATOR = "C:\\fixture\\p2pkit-windows-profile.dll";
    private ProfileDllSecurityCandidateTests() {}

    public static void main(String[] arguments) throws Throwable {
        check(arguments.length >= 1);
        WindowsLoaderRuntime.requireDiagnosticRuntime();
        String mode = arguments[0];
        String scope = "INERT_TYPED_OWNER_AND_REFUSAL_NOT_NATIVE_SECURITY_OR_AUTHORITY";
        String policy = "";
        if (mode.equals("actual")) {
            check(arguments.length == 2);
            boolean accepted = actual(arguments[1]);
            scope = "DEVELOPMENT_DLL_HANDLE_SECURITY_NOT_ANCESTOR_BYTES_MAPPING_OR_LOADING_AUTHORITY";
            policy = " descriptorPolicy=" + (accepted ? "ACCEPTED" : "REFUSED");
        } else {
            check(arguments.length == 1);
            switch (mode) {
                case "owner-refusal" -> ownerRefusal();
                case "substitution" -> substitution();
                case "failure-latch" -> failureLatch();
                case "policy-refusal" -> policyRefusal();
                default -> throw new AssertionError("Unknown profile DLL security control");
            }
        }
        System.out.println("WINDOWS_PROFILE_DLL_SECURITY_PASS case=" + mode + " scope=" + scope + policy);
    }

    private static WindowsOriginalProfileDllSecurityCandidate unattached(WindowsOriginalProfileDllFileCandidate file) {
        return new WindowsOriginalProfileDllSecurityCandidate(file, null, null, null, null, null, null, null, null);
    }

    private static void ownerRefusal() throws Throwable {
        WindowsOriginalProfileDllSecurityCandidate owner = unattached(null);
        WindowsOriginalFileSecurityQuery query = query(owner);
        check(value(query, "originalProfileDllOwner") == owner && value(query, "originalJvmOwner") == null);
        expect(IllegalStateException.class, owner::observe);
        expect(IllegalStateException.class, owner::completed);
        expect(IllegalStateException.class, owner::descriptorPolicyAccepted);
        check(!(boolean) value(owner, "attempted") && !(boolean) value(query, "attempted"));
        check(value(query, "frameArena") == null && value(query, "moduleArena") == null);
        check(((WindowsOriginalFileSecurityQuery.Failure) value(query, "failure")).retainedCandidate == query);
        check(((WindowsOriginalProfileDllSecurityCandidate.Failure) value(owner, "failure")).retainedCandidate == owner);
    }

    private static void substitution() throws Throwable {
        try (Arena bootstrapScope = Arena.ofConfined(); Arena handleScope = Arena.ofConfined()) {
            WindowsOriginalProfileDllFileCandidate file = inertFile(bootstrapScope, handleScope);
            WindowsOriginalFileLease lease = lease(file);
            WindowsOriginalProfileDllSecurityCandidate retained = lease.newProfileDllSecurity(file);
            field(file, "security").set(file, retained);
            WindowsOriginalProfileDllSecurityCandidate other = unattached(file);
            expect(IllegalStateException.class, other::observe);
            expect(IllegalStateException.class, () -> retained.requireOriginalQuery(query(other)));
            expect(IllegalStateException.class, () -> file.requireOriginalSecurity(other));
            expect(IllegalStateException.class, () -> lease.newProfileDllSecurity(null));
            WindowsOriginalJvmSecurityCandidate jvm =
                new WindowsOriginalJvmSecurityCandidate(null, null, null, null, null, null, null, null, null);
            expect(IllegalStateException.class, () -> query(retained).newJvmAncestors(jvm));
            check(!(boolean) value(query(retained), "attempted") && value(query(retained), "frameArena") == null);
            check(value(bootstrap(file), "originalJvm") == null && file.completed());
        }
    }

    private static void failureLatch() throws Throwable {
        try (Arena bootstrapScope = Arena.ofConfined(); Arena handleScope = Arena.ofConfined()) {
            WindowsOriginalProfileDllFileCandidate file = inertFile(bootstrapScope, handleScope);
            WindowsOriginalFileLease lease = lease(file);
            // The four security entries remain absent. Refusal occurs before any native frame/downcall.
            WindowsOriginalProfileDllFileCandidate.Failure failure =
                (WindowsOriginalProfileDllFileCandidate.Failure) expect(
                    WindowsOriginalProfileDllFileCandidate.Failure.class, file::inspectSecurity);
            WindowsOriginalProfileDllSecurityCandidate security =
                (WindowsOriginalProfileDllSecurityCandidate) value(file, "security");
            WindowsOriginalProfileDllSecurityCandidate.Failure securityFailure =
                (WindowsOriginalProfileDllSecurityCandidate.Failure) failure.operationFailure;
            WindowsOriginalFileSecurityQuery query = query(security);
            check(securityFailure.retainedCandidate == security && securityFailure.operationFailure instanceof IllegalStateException);
            check((boolean) value(file, "failed") && (boolean) value(file, "securityAttempted"));
            check((boolean) value(security, "failed") && value(query, "frameArena") == null);
            check(!(boolean) value(query, "attempted") && value(query, "moduleArena") == null);
            check(failure.retainedCandidate == file && value(query, "fileHandle") == value(lease, "handle"));
            check(value(query, "fileArena") == handleScope && bootstrapScope.scope().isAlive() && handleScope.scope().isAlive());
            check(expect(WindowsOriginalProfileDllFileCandidate.Failure.class, file::inspectSecurity) == failure);
            check(expect(WindowsOriginalProfileDllFileCandidate.Failure.class, file::completed) == failure);
            check(expect(WindowsOriginalProfileDllFileCandidate.Failure.class, security::completed) == failure);
            check(expect(WindowsOriginalProfileDllFileCandidate.Failure.class, file::originalLinker) == failure);
            check(expect(WindowsOriginalProfileDllFileCandidate.Failure.class,
                () -> bootstrap(file).originalProfileDllArena(file)) == failure);
            check(value(bootstrap(file), "profileDll") == file && value(bootstrap(file), "originalJvm") == null);
        }
    }

    private static void policyRefusal() throws Throwable {
        try (Arena bootstrapScope = Arena.ofConfined(); Arena handleScope = Arena.ofConfined();
            Arena moduleScope = Arena.ofConfined()) {
            WindowsOriginalProfileDllFileCandidate file = inertFile(bootstrapScope, handleScope);
            MemorySegment[] entries = (MemorySegment[]) value(bootstrap(file), "entries");
            for (int index = 1; index <= 4; index++) entries[index] = bootstrapScope.allocate(1).asSlice(0, 0);
            WindowsOriginalProfileDllSecurityCandidate security = lease(file).newProfileDllSecurity(file);
            field(file, "security").set(file, security);
            field(file, "securityAttempted").setBoolean(file, true);
            field(file, "securityPolicyRefused").setBoolean(file, true);
            WindowsOriginalFileSecurityQuery query = query(security);
            // Inert negative-state control only. No original query or accepted policy is fabricated as evidence.
            field(query, "succeeded").setBoolean(query, true);
            field(query, "frameRetired").setBoolean(query, true);
            field(query, "ntReturned").setBoolean(query, true);
            field(query, "policyEvaluated").setBoolean(query, true);
            field(query, "exactDescriptor").set(query, new byte[20]);
            field(query, "moduleArena").set(query, moduleScope);
            field(query, "entry").set(query, moduleScope.allocate(1).asSlice(0, 0));
            check(file.completed() && security.completed() && !security.descriptorPolicyAccepted());
            nativeInputsRefused(file);
            expect(IllegalStateException.class, file::inspectSecurity);
            check(file.completed() && security.completed() && !security.descriptorPolicyAccepted());
            check(!(boolean) value(file, "failed") && !(boolean) value(security, "failed"));
            check(handleScope.scope().isAlive() && moduleScope.scope().isAlive() && bootstrapScope.scope().isAlive());
        }
    }

    /** Test-only original identity graph. These native segments are never invoked or treated as kernel handles. */
    private static WindowsOriginalProfileDllFileCandidate inertFile(Arena bootstrapScope, Arena handleScope)
        throws ReflectiveOperationException {
        Constructor<WindowsSystemBootstrapCandidate> constructor =
            WindowsSystemBootstrapCandidate.class.getDeclaredConstructor(Linker.class);
        constructor.setAccessible(true);
        WindowsSystemBootstrapCandidate bootstrap = constructor.newInstance((Object) null);
        field(bootstrap, "originalArena").set(bootstrap, bootstrapScope);
        field(bootstrap, "succeeded").setBoolean(bootstrap, true);
        field(bootstrap, "frameRetired").setBoolean(bootstrap, true);
        MemorySegment[] entries = (MemorySegment[]) value(bootstrap, "entries");
        for (int index = 8; index <= 10; index++) entries[index] = bootstrapScope.allocate(1).asSlice(0, 0);
        WindowsOriginalProfileDllFileCandidate file = new WindowsOriginalProfileDllFileCandidate(bootstrap, LOCATOR);
        field(bootstrap, "profileDll").set(bootstrap, file);
        field(bootstrap, "profileDllAttempted").setBoolean(bootstrap, true);
        field(file, "attempted").setBoolean(file, true);
        field(file, "originalPath").set(file, (LOCATOR + '\0').toCharArray());
        WindowsOriginalFileLease lease = WindowsOriginalFileLease.forProfileDll(file);
        field(file, "lease").set(file, lease);
        field(file, "succeeded").setBoolean(file, true);
        field(lease, "succeeded").setBoolean(lease, true);
        field(lease, "frameRetired").setBoolean(lease, true);
        MemorySegment handle = handleScope.allocate(1).asSlice(0, 0);
        field(lease, "handle").set(lease, handle);
        field(lease, "rawHandle").setLong(lease, handle.address());
        field(lease, "handleArena").set(lease, handleScope);
        return file;
    }

    private static boolean actual(String source) throws Throwable {
        WindowsProfileDllPath.require(source);
        Path path = Path.of(source);
        check(path.isAbsolute() && path.equals(path.normalize()));
        long length = Files.size(path); // Development fixture locator/size, not an identity or digest proof.
        check(length >= 512 && length <= 32L * 1024 * 1024);
        WindowsSystemBootstrapCandidate bootstrap = WindowsSystemBootstrapCandidate.inspect();
        WindowsOriginalProfileDllFileCandidate file = bootstrap.inspectOriginalProfileDll(source);
        WindowsOriginalFileLease lease = lease(file);
        MemorySegment handle = (MemorySegment) value(lease, "handle");
        Arena handleArena = (Arena) value(lease, "handleArena");
        WindowsOriginalProfileDllSecurityCandidate security = file.inspectSecurity();
        WindowsOriginalFileSecurityQuery query = query(security);
        check(security.completed() && file.completed() && file.leaseHeld() && bootstrap.completed());
        boolean accepted = security.descriptorPolicyAccepted();
        check(value(query, "fileHandle") == handle && value(query, "fileArena") == handleArena);
        check(value(query, "bootstrapArena") == value(bootstrap, "originalArena"));
        MemorySegment[] entries = (MemorySegment[]) value(bootstrap, "entries");
        check(value(query, "pinEntry") == entries[1] && value(query, "pathEntry") == entries[2] &&
            value(query, "systemPathEntry") == entries[3] && value(query, "resolveEntry") == entries[4]);
        check(value(query, "originalProfileDllOwner") == security && value(query, "originalJvmOwner") == null);
        check(value(file, "security") == security && value(security, "file") == file && value(bootstrap, "profileDll") == file);
        check((boolean) value(query, "ntReturned") && (int) value(query, "ntStatus") == 0);
        int required = (int) value(query, "requiredLength");
        byte[] exact = (byte[]) value(query, "exactDescriptor");
        byte[] preserved = (byte[]) value(query, "preservedDescriptor");
        check(required >= 20 && required <= 65_536 && exact.length == required && preserved.length == 65_536);
        check(exact != preserved && Arrays.equals(exact, Arrays.copyOf(preserved, required)));
        boolean independentlyAccepted;
        try {
            WindowsInstallationSecurity.require(exact.clone(), WindowsInstallationSecurity.Kind.FILE);
            independentlyAccepted = true;
        } catch (IllegalArgumentException refused) { independentlyAccepted = false; }
        check(independentlyAccepted == accepted && (boolean) value(file, "securityPolicyRefused") == !accepted);
        check((long) value(query, "rawModule") == (long) value(query, "rawProvider"));
        check((long) value(query, "rawEntry") == ((MemorySegment) value(query, "entry")).address());
        check((boolean) value(query, "frameRetired") && !(boolean) value(query, "nativeReturnUnconfirmed"));
        check(!((Arena) value(query, "frameArena")).scope().isAlive() && ((Arena) value(query, "moduleArena")).scope().isAlive());
        for (boolean observed : (boolean[]) value(query, "errorObserved")) check(observed);
        check(value(bootstrap, "originalJvm") == null && !(boolean) value(bootstrap, "originalJvmAttempted"));
        check(((long[]) value(lease, "first"))[4] == length && handleArena.scope().isAlive());
        expect(IllegalStateException.class, file::inspectSecurity);
        expect(IllegalStateException.class, security::observe);
        expect(IllegalStateException.class, unattached(file)::observe);
        expect(IllegalStateException.class, () -> query.newJvmAncestors(null));
        if (!accepted) nativeInputsRefused(file);
        AtomicReference<Throwable> unexpected = new AtomicReference<>();
        Thread worker = Thread.startVirtualThread(() -> {
            try {
                expect(IllegalStateException.class, security::completed);
                expect(IllegalStateException.class, security::descriptorPolicyAccepted);
                expect(IllegalStateException.class, file::inspectSecurity);
            } catch (Throwable caught) { unexpected.set(caught); }
        });
        worker.join();
        check(unexpected.get() == null);
        System.gc();
        check(security.completed() && security.descriptorPolicyAccepted() == accepted && file.leaseHeld());
        check(value(query, "fileHandle") == handle && handleArena.scope().isAlive());
        check(((WindowsOriginalFileSecurityQuery.Failure) value(query, "failure")).retainedCandidate == query);
        Throwable refusal = expect(WindowsLoader.Unavailable.class, WindowsLoader::openInstalledProvider);
        check(WindowsLoader.REFUSAL.equals(refusal.getMessage()));
        return accepted;
    }

    private static void nativeInputsRefused(WindowsOriginalProfileDllFileCandidate file) throws Throwable {
        WindowsSystemBootstrapCandidate bootstrap = bootstrap(file);
        expect(IllegalStateException.class, file::originalLinker);
        expect(IllegalStateException.class, file::originalBootstrapArena);
        expect(IllegalStateException.class, file::originalPathSnapshot);
        expect(IllegalStateException.class, () -> file.originalFileEntry(0));
        expect(IllegalStateException.class, () -> file.originalSecurityEntry(lease(file), 0));
        expect(IllegalStateException.class, () -> bootstrap.originalProfileDllLinker(file));
        expect(IllegalStateException.class, () -> bootstrap.originalProfileDllArena(file));
        expect(IllegalStateException.class, () -> bootstrap.originalProfileDllFileEntry(file, 0));
        expect(IllegalStateException.class, () -> bootstrap.originalProfileDllSecurityEntry(file, 0));
        expect(IllegalStateException.class, () -> lease(file).newProfileDllSecurity(file));
        expect(IllegalStateException.class, () -> WindowsOriginalFileLease.forProfileDll(file));
    }
    private static WindowsSystemBootstrapCandidate bootstrap(WindowsOriginalProfileDllFileCandidate file)
        throws ReflectiveOperationException { return (WindowsSystemBootstrapCandidate) value(file, "bootstrap"); }
    private static WindowsOriginalFileLease lease(WindowsOriginalProfileDllFileCandidate file)
        throws ReflectiveOperationException { return (WindowsOriginalFileLease) value(file, "lease"); }
    private static WindowsOriginalFileSecurityQuery query(WindowsOriginalProfileDllSecurityCandidate owner)
        throws ReflectiveOperationException { return (WindowsOriginalFileSecurityQuery) value(owner, "query"); }
    private static Field field(Object owner, String name) throws ReflectiveOperationException {
        Field field = owner.getClass().getDeclaredField(name);
        field.setAccessible(true);
        return field;
    }
    private static Object value(Object owner, String name) throws ReflectiveOperationException {
        return field(owner, name).get(owner);
    }
    private interface Action { void run() throws Throwable; }
    private static Throwable expect(Class<? extends Throwable> type, Action action) {
        try { action.run(); }
        catch (Throwable caught) {
            if (type.isInstance(caught)) return caught;
            throw new AssertionError("Unexpected profile DLL security failure", caught);
        }
        throw new AssertionError("Expected profile DLL security refusal");
    }
    private static void check(boolean condition) {
        if (!condition) throw new AssertionError("Profile DLL security control failed");
    }
}
