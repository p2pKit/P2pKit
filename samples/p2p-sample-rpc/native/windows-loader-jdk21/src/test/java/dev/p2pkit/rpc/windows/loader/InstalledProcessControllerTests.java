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
    private InstalledProcessControllerTests() {}

    public static void main(String[] arguments) throws Throwable {
        check(arguments.length == 1);
        WindowsLoaderRuntime.requireDiagnosticRuntime();
        check(root() == null);
        publicRefusal();
        switch (arguments[0]) {
            case "contract" -> contract();
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
        publicRefusal();
        // Neither private claim nor any modeled terminal reuse enters the actual bootstrap.
        Field bootstrapRoot = WindowsSystemBootstrapCandidate.class.getDeclaredField("processOwner");
        bootstrapRoot.setAccessible(true);
        check(bootstrapRoot.get(null) == null);
        System.out.println("WINDOWS_INSTALLED_CONTROLLER_MODEL_PASS case=" + arguments[0] +
            " scope=INERT_ONCE_REUSE_NOT_INSTALLED_NATIVE_OR_PROVIDER_EXECUTION");
    }

    private static void publicRefusal() {
        Throwable failure = expect(WindowsLoader.Unavailable.class, WindowsLoader::openInstalledProvider);
        check(failure.getClass() == WindowsLoader.Unavailable.class && failure.getMessage().equals(WindowsLoader.REFUSAL));
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

    private static Object firstClaim() throws Throwable {
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
