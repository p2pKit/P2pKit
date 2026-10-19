package dev.p2pkit.rpc.windows.loader;

import java.lang.reflect.Constructor;
import java.lang.reflect.Field;
import java.lang.reflect.InvocationTargetException;
import java.lang.reflect.Method;
import java.lang.reflect.Modifier;
import java.util.Arrays;
import java.util.concurrent.atomic.AtomicReference;

import static dev.p2pkit.rpc.windows.loader.OriginalFileBytesLeaseTests.check;
import static dev.p2pkit.rpc.windows.loader.OriginalFileBytesLeaseTests.expect;
import static dev.p2pkit.rpc.windows.loader.OriginalFileBytesLeaseTests.field;
import static dev.p2pkit.rpc.windows.loader.OriginalFileBytesLeaseTests.invoke;
import static dev.p2pkit.rpc.windows.loader.OriginalFileBytesLeaseTests.value;

/** Fresh JVM per case. No first native completion is invoked, even on Windows. */
public final class InstalledProcessControllerTests {
    static final String INSTALLED_DIAGNOSTIC_RESULT =
        "{\"schema\":1,\"scope\":\"INSTALLED_ADMISSION_ONLY_NOT_PROFILE_PROVIDER_QUALIFICATION\"," +
        "\"admission\":\"REGISTERED\",\"repeat\":\"REUSED\",\"profileStorage\":\"NOT_ENTERED\"," +
        "\"network\":\"NOT_ENTERED\",\"publicProvider\":\"NOT_ENTERED\"}";

    private InstalledProcessControllerTests() {}

    public static void main(String[] arguments) throws Throwable {
        check(arguments.length == 1);
        WindowsLoaderRuntime.requireDiagnosticRuntime();
        check(root() == null);
        publicState();
        switch (arguments[0]) {
            case "diagnostic-contract", "diagnostic-reuse", "diagnostic-failure", "diagnostic-in-progress" ->
                diagnostic(arguments[0]);
            case "diagnostic-stages" -> diagnosticStages();
            case "diagnostic-child-stages" -> diagnosticChildStages();
            case "diagnostic-system-stages" -> diagnosticSystemStages();
            case "contract" -> contract();
            case "public-layout-refusal" -> publicLayoutRefusal();
            case "claim" -> firstClaim();
            case "in-progress" -> inProgress();
            case "virtual-first" -> virtualFirst();
            case "failure" -> failure();
            case "reuse" -> reuse(false);
            case "reuse-virtual" -> reuse(true);
            case "missing-registration" -> incomplete(false);
            case "unfinished-registration" -> incomplete(true);
            case "wrong-thread" -> wrongThread();
            case "wrong-owner" -> wrongOwner();
            default -> throw new AssertionError("Unknown installed controller model");
        }
        publicState();
        // Neither private claim nor any modeled terminal reuse enters the actual bootstrap.
        Field bootstrapRoot = WindowsSystemBootstrapCandidate.class.getDeclaredField("processOwner");
        bootstrapRoot.setAccessible(true);
        check(bootstrapRoot.get(null) == null);
        System.out.println("WINDOWS_INSTALLED_CONTROLLER_MODEL_PASS case=" + arguments[0] +
            " scope=INERT_ONCE_REUSE_NOT_INSTALLED_NATIVE_OR_PROVIDER_EXECUTION");
    }

    static void publicState() throws Throwable {
        Object original = root();
        if (original == null) {
            Throwable failure = expect(WindowsLoader.Unavailable.class, WindowsLoader::openInstalledProvider);
            check(failure.getClass() == WindowsLoader.Unavailable.class && failure.getMessage().equals(WindowsLoader.REFUSAL));
            check(root() == null);
        } else if (value(original, "state").toString().equals("Failed")) {
            check(expect(RuntimeException.class, WindowsLoader::openInstalledProvider) == value(original, "failure"));
        } else if (value(original, "state").toString().equals("Registered")) {
            Object registration = value(original, "registration");
            // Incomplete seeded terminal state must also be rejected by the actual public entry.
            if (registration == null || ((WindowsJniRegistrationOwner) registration).state() !=
                WindowsJniRegistrationOwner.State.Registered) {
                expect(IllegalStateException.class, WindowsLoader::openInstalledProvider);
            } else {
                WindowsLoader.openInstalledProvider();
                WindowsLoader.openInstalledProvider();
                check(value(original, "registration") == registration);
            }
        } else {
            check(!(expect(IllegalStateException.class, WindowsLoader::openInstalledProvider) instanceof WindowsLoader.Unavailable));
        }
        check(root() == original);
    }

    private static void publicLayoutRefusal() throws Throwable {
        String original = System.getProperty("java.home");
        String fake = java.nio.file.Path.of(original).toAbsolutePath().getRoot()
            .resolve("not-an-installation/P2pKit Sample/runtime").toString();
        try {
            for (String hint : new String[] {"", "runtime", original + "/../runtime", fake, "x".repeat(32768)}) {
                System.setProperty("java.home", hint);
                publicState(); // No native reservation, even with a nominal installed directory shape.
            }
            System.clearProperty("java.home");
            publicState();
        } finally {
            System.setProperty("java.home", original);
        }
    }

    private static Object root() throws ReflectiveOperationException {
        Field field = WindowsLoader.class.getDeclaredField("installedAttempt");
        field.setAccessible(true);
        return field.get(null);
    }

    private static Object claim() throws Throwable {
        Method method = WindowsLoader.class.getDeclaredMethod("claimOriginalInstalledProvider");
        method.setAccessible(true);
        try { return method.invoke(null); }
        catch (InvocationTargetException caught) { throw caught.getCause(); }
    }

    private static void contract() throws Throwable {
        Method entry = WindowsLoader.class.getDeclaredMethod("completeOriginalInstalledProvider");
        check(entry.getReturnType() == void.class && entry.getParameterCount() == 0 &&
            Modifier.isStatic(entry.getModifiers()) && !Modifier.isPublic(entry.getModifiers()));
        check(Arrays.stream(WindowsLoader.class.getDeclaredMethods()).filter(method ->
            method.getName().equals("completeOriginalInstalledProvider")).count() == 1);
        check(Arrays.stream(WindowsLoader.class.getDeclaredMethods()).filter(method ->
            Modifier.isPublic(method.getModifiers())).count() == 1);
        check(root() == null);
    }

    static Object firstClaim() throws Throwable {
        Object attempt = claim();
        check(attempt != null && root() == attempt && value(attempt, "ownerThread") == Thread.currentThread());
        check(value(attempt, "state").toString().equals("Reserved"));
        check(value(value(attempt, "failure"), "retainedAttempt") == attempt);
        check(value(value(attempt, "failure"), "operationFailure") == null);
        emptyChildren(attempt);
        return attempt;
    }

    private static void emptyChildren(Object attempt) throws ReflectiveOperationException {
        for (String child : new String[] {"bootstrap", "installation", "profile", "registration"}) {
            check(value(attempt, child) == null);
        }
    }

    private static void inProgress() throws Throwable {
        Object attempt = firstClaim();
        // Same-thread reentry and both other thread kinds cannot replace or fail an active attempt.
        expect(IllegalStateException.class, WindowsLoader::completeOriginalInstalledProvider);
        onThread(false, () -> expect(IllegalStateException.class, WindowsLoader::completeOriginalInstalledProvider));
        onThread(true, () -> expect(IllegalStateException.class, WindowsLoader::completeOriginalInstalledProvider));
        check(root() == attempt && value(attempt, "state").toString().equals("Reserved"));
        emptyChildren(attempt);
        check(value(value(attempt, "failure"), "operationFailure") == null);
    }

    private static void virtualFirst() throws Throwable {
        // Claim only: never call the potentially native first entry in a model, on any host.
        onThread(true, () -> expect(IllegalStateException.class, InstalledProcessControllerTests::claim));
        check(root() == null);
        firstClaim();
    }

    private static void failure() throws Throwable {
        Object attempt = firstClaim();
        Error original = new LinkageError("inert admitted operation failure");
        Object carrier = invoke(attempt, "seal", new Class<?>[] {Throwable.class}, original);
        check(carrier == value(attempt, "failure") && value(carrier, "operationFailure") == original);
        check(value(carrier, "retainedAttempt") == attempt && value(attempt, "state").toString().equals("Failed"));
        check(!(carrier instanceof WindowsLoader.Unavailable));
        check(expect(RuntimeException.class, WindowsLoader::completeOriginalInstalledProvider) == carrier);
        onThread(false, () -> check(expect(RuntimeException.class, WindowsLoader::completeOriginalInstalledProvider) == carrier));
        onThread(true, () -> check(expect(RuntimeException.class, WindowsLoader::completeOriginalInstalledProvider) == carrier));
        expect(IllegalStateException.class, () -> invoke(attempt, "seal", new Class<?>[] {Throwable.class}, new Error()));
        check(value(carrier, "operationFailure") == original && root() == attempt);
        emptyChildren(attempt);
    }

    private static final class InertRegistration implements WindowsJniRegistrationOwner.Invocation {
        int calls;
        int reads;
        int retirements;
        @Override public int invoke() { calls++; return 0; }
        @Override public WindowsJniRegistrationOwner.Report readReport() {
            reads++;
            return new WindowsJniRegistrationOwner.Report(32, 1, 2, 0, 1, 0, 0, 0);
        }
        @Override public void retireFrame() { retirements++; }
    }

    private static WindowsJniRegistrationOwner.Retention inertRetention() {
        return new WindowsJniRegistrationOwner.Retention(new Object(), new Object(), new Object(),
            InstalledProcessControllerTests.class, new Object());
    }

    private static void reuse(boolean virtual) throws Throwable {
        Object attempt = firstClaim();
        InertRegistration call = new InertRegistration();
        // Real registrar state machine with an inert invocation, NOT original installed registration.
        WindowsJniRegistrationOwner owner = WindowsJniRegistrationOwner.registerOnce(inertRetention(), call);
        field(attempt, "registration").set(attempt, owner);
        invoke(attempt, "publishRegistered");
        WindowsLoader.completeOriginalInstalledProvider();
        onThread(virtual, WindowsLoader::completeOriginalInstalledProvider);
        check(claim() == null && root() == attempt && value(attempt, "registration") == owner);
        check(value(attempt, "state").toString().equals("Registered"));
        check(call.calls == 1 && call.reads == 1 && call.retirements == 1);
        check(value(attempt, "bootstrap") == null && value(attempt, "installation") == null && value(attempt, "profile") == null);
        expect(IllegalStateException.class, () -> invoke(attempt, "complete"));
        check(value(attempt, "state").toString().equals("Registered") && value(value(attempt, "failure"), "operationFailure") == null);
    }

    /** Test-only inert terminal-state fixture; it never enters the original installed load chain. */
    static Object seedRegistered() throws Throwable {
        Object attempt = firstClaim();
        WindowsJniRegistrationOwner owner = WindowsJniRegistrationOwner.registerOnce(inertRetention(), new InertRegistration());
        field(attempt, "registration").set(attempt, owner);
        invoke(attempt, "publishRegistered");
        return attempt;
    }

    private static void diagnostic(String mode) throws Throwable {
        Method entry = Probe.class.getDeclaredMethod("installedAdmissionReadback");
        check(entry.getParameterCount() == 0 && entry.getReturnType() == String.class &&
            Modifier.isPublic(entry.getModifiers()) && Modifier.isStatic(entry.getModifiers()));
        if (mode.equals("diagnostic-contract")) return; // Never invoke a fresh native first entry in models.
        if (mode.equals("diagnostic-reuse")) {
            Object attempt = seedRegistered();
            check(Probe.installedAdmissionReadback().equals(INSTALLED_DIAGNOSTIC_RESULT));
            onThread(false, () -> check(Probe.installedAdmissionReadback().equals(INSTALLED_DIAGNOSTIC_RESULT)));
            onThread(true, () -> check(Probe.installedAdmissionReadback().equals(INSTALLED_DIAGNOSTIC_RESULT)));
            check(root() == attempt && value(attempt, "state").toString().equals("Registered"));
            Object call = value(value(attempt, "registration"), "invocation");
            check((int) value(call, "calls") == 1 && (int) value(call, "reads") == 1 &&
                (int) value(call, "retirements") == 1);
            check(value(attempt, "bootstrap") == null && value(attempt, "installation") == null && value(attempt, "profile") == null);
        } else {
            Object attempt = firstClaim();
            if (mode.equals("diagnostic-failure")) {
                Error original = new LinkageError("inert installed diagnostic failure");
                Object carrier = invoke(attempt, "seal", new Class<?>[] {Throwable.class}, original);
                check(expect(RuntimeException.class, Probe::installedAdmissionReadback) == carrier);
                check(value(carrier, "operationFailure") == original && !(carrier instanceof WindowsLoader.Unavailable));
            } else {
                expect(IllegalStateException.class, Probe::installedAdmissionReadback);
                check(value(attempt, "state").toString().equals("Reserved"));
                check(value(value(attempt, "failure"), "operationFailure") == null);
            }
            emptyChildren(attempt);
        }
    }

    private static void diagnosticStages() throws Throwable {
        Method reader = Probe.class.getDeclaredMethod("installedAdmissionFailureStage", Throwable.class);
        check(reader.getReturnType() == String.class && Modifier.isStatic(reader.getModifiers()) &&
            Modifier.isPublic(reader.getModifiers()));
        Throwable privateFailure = new Error("PRIVATE_PATH_SID_ADDRESS_PAYLOAD") {
            @Override public String getMessage() { throw new AssertionError("Private message accessed"); }
            @Override public synchronized Throwable getCause() { throw new AssertionError("Arbitrary cause traversed"); }
        };
        check(Probe.installedAdmissionFailureStage(privateFailure).equals("NO_MATCHING_RETAINED_FAILURE"));
        check(root() == null);
        Object attempt = firstClaim();
        check(Probe.installedAdmissionFailureStage((Throwable) value(attempt, "failure"))
            .equals("NO_MATCHING_RETAINED_FAILURE")); // Reserved is not a sealed failure.
        Throwable carrier = (Throwable) invoke(attempt, "seal", new Class<?>[] {Throwable.class}, privateFailure);
        String[] expected = {"RESERVATION", "BOOTSTRAP", "INSTALLATION", "PROFILE_PREPARATION",
            "JNI_REGISTRATION", "PUBLISH_REGISTERED", "IP_INTERFACE_OBSERVER", "UNKNOWN_RETAINED_OPERATION"};
        for (int phase = 0; phase < expected.length; phase++) {
            field(attempt, "diagnosticPhase").setInt(attempt, phase);
            check(Probe.installedAdmissionFailureStage(carrier).equals(expected[phase]));
            check(Probe.installedAdmissionFailureStage(privateFailure).equals("NO_MATCHING_RETAINED_FAILURE"));
            onThread(false, () -> check(Probe.installedAdmissionFailureStage(carrier).matches("[A-Z_]{1,64}")));
            check(root() == attempt && value(carrier, "operationFailure") == privateFailure);
            check(expect(RuntimeException.class, Probe::installedAdmissionReadback) == carrier);
        }
        emptyChildren(attempt); // No acquisition, retry, cleanup or child getter was invoked.
    }

    private static void diagnosticChildStages() throws Throwable {
        Object attempt = firstClaim();
        Throwable carrier = (Throwable) invoke(attempt, "seal", new Class<?>[] {Throwable.class}, new Error());
        Constructor<WindowsSystemBootstrapCandidate> constructor =
            WindowsSystemBootstrapCandidate.class.getDeclaredConstructor(java.lang.foreign.Linker.class);
        constructor.setAccessible(true);
        WindowsSystemBootstrapCandidate bootstrap = constructor.newInstance(new Object[] {null});
        field(carrier, "operationFailure").set(carrier, value(bootstrap, "failure"));
        field(attempt, "diagnosticPhase").setInt(attempt, 1);
        String[] early = {"BOOTSTRAP_FRAME", "BOOTSTRAP_EXPORTS", "BOOTSTRAP_PROCESS", "BOOTSTRAP_SYSTEM_PATH"};
        for (int phase = 0; phase < 32; phase++) {
            field(bootstrap, "phase").setInt(bootstrap, phase);
            String expected = phase < 4 ? early[phase] : phase % 2 == 0 ?
                "BOOTSTRAP_PROVIDER_PIN" : "BOOTSTRAP_PROVIDER_PATH";
            check(Probe.installedAdmissionFailureStage(carrier).equals(expected));
        }
        WindowsInstalledProfileCandidate profile = new WindowsInstalledProfileCandidate(null);
        field(profile, "failed").setBoolean(profile, true); // Its ordinary guards cannot be used.
        WindowsOriginalInstallationCandidate installation = new WindowsOriginalInstallationCandidate(null);
        Object installationFailure = value(installation, "failure");
        field(installationFailure, "operationFailure").set(installationFailure, value(profile, "failure"));
        String[] operations = {"PROFILE_PRECONDITION", "PROFILE_SYSTEM_MODULES", "PROFILE_KNOWN_FOLDER",
            "PROFILE_PARENT_PIN", "PROFILE_JVM_IMAGE", "PROFILE_JVM_FILE", "PROFILE_JVM_SECURITY",
            "PROFILE_JVM_ANCESTORS", "PROFILE_FILE", "PROFILE_SECURITY", "PROFILE_ANCESTORS",
            "PROFILE_BYTES", "PROFILE_MANIFEST", "PROFILE_PACKAGE", "PROFILE_IMPORTS",
            "PROFILE_PREPARE_LOAD", "PROFILE_LOAD_IMAGE", "PROFILE_VERIFY_IMAGE", "PROFILE_REGISTER_JNI"};
        for (int stage : new int[] {3, 4}) {
            field(attempt, "diagnosticPhase").setInt(attempt, stage);
            field(carrier, "operationFailure").set(carrier, stage == 3 ? installationFailure : value(profile, "failure"));
            for (int phase = 0; phase < operations.length; phase++) {
                field(profile, "diagnosticPhase").setInt(profile, phase);
                check(Probe.installedAdmissionFailureStage(carrier).equals(operations[phase]));
            }
        }
        check(value(profile, "attempted").equals(false) && value(profile, "registrationAttempted").equals(false));
        emptyChildren(attempt);
    }

    private static void diagnosticSystemStages() throws Throwable {
        Object attempt = firstClaim();
        Throwable privateFailure = new Error("PRIVATE_PATH_SID_ADDRESS_PAYLOAD") {
            @Override public String getMessage() { throw new AssertionError("Private message accessed"); }
            @Override public synchronized Throwable getCause() { throw new AssertionError("Arbitrary cause traversed"); }
        };
        Throwable carrier = (Throwable) invoke(attempt, "seal", new Class<?>[] {Throwable.class}, privateFailure);
        field(attempt, "diagnosticPhase").setInt(attempt, 4);
        WindowsInstalledProfileCandidate profile = new WindowsInstalledProfileCandidate(null);
        field(profile, "failed").setBoolean(profile, true);
        field(profile, "diagnosticPhase").setInt(profile, 1);
        Object profileFailure = value(profile, "failure");
        field(carrier, "operationFailure").set(carrier, profileFailure);
        WindowsOriginalSystemModulesCandidate systems = new WindowsOriginalSystemModulesCandidate(null);
        field(systems, "failed").setBoolean(systems, true); // All ordinary completion/native guards refuse.
        Object systemFailure = value(systems, "failure");
        field(systemFailure, "operationFailure").set(systemFailure, privateFailure);
        String[] slots = {"NO_SLOT", "SLOT_ZERO", "SLOT_ONE", "SLOT_TWO", "SLOT_THREE", "SLOT_FOUR",
            "SLOT_FIVE", "SLOT_SIX", "SLOT_SEVEN", "SLOT_EIGHT", "UNKNOWN_SLOT"};
        // Both a completed negative cohort and a throw before the assignment to profile.systems must
        // survive the exact original failure chain. Neither path can query or recreate a native owner.
        for (boolean assigned : new boolean[] {false, true}) {
            field(profile, "systems").set(profile, assigned ? systems : null);
            field(profileFailure, "operationFailure").set(profileFailure, assigned ? privateFailure : systemFailure);
            for (int slot = -1; slot <= 9; slot++) {
                field(systems, "activeSlot").setInt(systems, slot);
                field(systems, "stoppedSlot").setInt(systems, slot);
                for (String[] outcome : new String[][] {
                    {"MODULE_ABSENT", "SYSTEM_MODULE_ABSENT_"}, {"LEAF_POLICY_REFUSED", "SYSTEM_LEAF_POLICY_"},
                    {"ANCESTOR_POLICY_REFUSED", "SYSTEM_ANCESTOR_POLICY_"}, {"COMPLETE", "SYSTEM_GRAPH_RECHECK_"},
                    {"PRIVATE_PATH_SID_ADDRESS_PAYLOAD", "SYSTEM_UNKNOWN_OUTCOME_"},
                }) {
                    field(systems, "outcome").set(systems, outcome[0]);
                    diagnosticLabel(carrier, outcome[1] + slots[slot + 1]);
                }
            }
            field(systems, "outcome").set(systems, null);
            field(systems, "activeSlot").setInt(systems, 4);
            String[] operations = {"PRECONDITION", "FRAME", "DIRECTORY", "MODULE_PIN", "MODULE_PATH",
                "FILE", "SECURITY", "ANCESTORS", "BYTE_BOUND", "BYTES", "EXPORT_INPUT", "EXPORT_GRAPH",
                "UNKNOWN_OPERATION"};
            for (int phase = 0; phase < operations.length; phase++) {
                field(systems, "diagnosticPhase").setInt(systems, phase);
                diagnosticLabel(carrier, "SYSTEM_" + operations[phase] + (phase == 11 ? "_NO_SLOT" : "_SLOT_FOUR"));
            }
            field(systems, "nativeReturnUnconfirmed").setBoolean(systems, true);
            diagnosticLabel(carrier, "SYSTEM_RETURN_UNKNOWN_SLOT_FOUR");
            field(systems, "nativeReturnUnconfirmed").setBoolean(systems, false);
            field(systemFailure, "arenaCloseFailure").set(systemFailure, privateFailure);
            diagnosticLabel(carrier, "SYSTEM_RETIREMENT_SLOT_FOUR");
            field(systemFailure, "arenaCloseFailure").set(systemFailure, null);
            check(value(systemFailure, "operationFailure") == privateFailure);
        }
        check(!(boolean) value(systems, "attempted") && !(boolean) value(systems, "frameRetired") &&
            value(systems, "frameArena") == null && value(systems, "moduleArena") == null &&
            Arrays.stream((Object[]) value(systems, "modules")).allMatch(element -> element == null));
        check(!(boolean) value(profile, "attempted") && !(boolean) value(profile, "registrationAttempted"));
        check(expect(RuntimeException.class, Probe::installedAdmissionReadback) == carrier);
        emptyChildren(attempt);
    }

    private static void diagnosticLabel(Throwable carrier, String expected) throws Throwable {
        check(Probe.installedAdmissionFailureStage(carrier).equals(expected));
        check(expected.matches("[A-Z_]{1,64}"));
        onThread(true, () -> check(Probe.installedAdmissionFailureStage(carrier).equals(expected)));
    }

    private static void incomplete(boolean unfinished) throws Throwable {
        Object attempt = firstClaim();
        if (unfinished) {
            Constructor<WindowsJniRegistrationOwner> constructor = WindowsJniRegistrationOwner.class.getDeclaredConstructor(
                WindowsJniRegistrationOwner.Retention.class, WindowsJniRegistrationOwner.Invocation.class);
            constructor.setAccessible(true);
            field(attempt, "registration").set(attempt, constructor.newInstance(inertRetention(), new InertRegistration()));
        }
        expect(IllegalStateException.class, () -> invoke(attempt, "publishRegistered"));
        check(value(attempt, "state").toString().equals("Reserved"));
        // Deliberately corrupt only private model state to exercise the separate reuse guard.
        Field state = field(attempt, "state");
        for (Object choice : state.getType().getEnumConstants()) {
            if (choice.toString().equals("Registered")) state.set(attempt, choice);
        }
        expect(IllegalStateException.class, WindowsLoader::completeOriginalInstalledProvider);
        check(root() == attempt);
    }

    private static void wrongThread() throws Throwable {
        Object attempt = firstClaim();
        onThread(false, () -> expect(IllegalStateException.class, () -> invoke(attempt, "complete")));
        onThread(true, () -> expect(IllegalStateException.class, () -> invoke(attempt, "complete")));
        check(value(attempt, "state").toString().equals("Reserved"));
        emptyChildren(attempt);
    }

    private static void wrongOwner() throws Throwable {
        Object attempt = firstClaim();
        Constructor<?> constructor = attempt.getClass().getDeclaredConstructor();
        constructor.setAccessible(true);
        Object copy = constructor.newInstance();
        expect(IllegalStateException.class, () -> invoke(copy, "complete"));
        check(root() == attempt && value(copy, "state").toString().equals("Reserved"));
        emptyChildren(attempt);
        emptyChildren(copy);
    }

    private static void onThread(boolean virtual, OriginalFileBytesLeaseTests.Action action) throws Throwable {
        AtomicReference<Throwable> caught = new AtomicReference<>();
        Runnable body = () -> {
            try { action.run(); }
            catch (Throwable failure) { caught.set(failure); }
        };
        Thread thread = virtual ? Thread.ofVirtual().unstarted(body) : new Thread(body);
        thread.start();
        thread.join(5000);
        check(!thread.isAlive());
        if (caught.get() != null) throw caught.get();
    }
}
