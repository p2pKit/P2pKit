package dev.p2pkit.rpc.windows.loader;

import java.io.IOException;
import java.io.InputStream;
import java.lang.reflect.InvocationTargetException;
import java.lang.reflect.Method;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicReference;

/** Each scenario uses a fresh JVM: the real process slot has no test reset or alternate factory. */
public final class RegistrationOwnerTests {
    private RegistrationOwnerTests() {}

    private static final WindowsJniRegistrationOwner.Retention ROOTS = new WindowsJniRegistrationOwner.Retention(
        new Object(), new Object(), new Object(), RegistrationOwnerTests.class, new Object());
    private static final WindowsJniRegistrationOwner.Report OK =
        new WindowsJniRegistrationOwner.Report(32, 1, 2, 0, 1, 0, 0, 0);
    private static final Error INVOCATION_ERROR = new OutOfMemoryError("inert invocation error");
    private static final Error REPORT_ERROR = new OutOfMemoryError("inert report error");
    private static final Error CLEANUP_ERROR = new OutOfMemoryError("inert frame retirement error");

    private static final class Call implements WindowsJniRegistrationOwner.Invocation {
        int invocations;
        int reads;
        int retirements;
        int result;
        WindowsJniRegistrationOwner.Report report = OK;
        Throwable invocationFailure;
        Throwable reportFailure;
        Throwable cleanupFailure;
        Runnable during = () -> {};

        @Override public int invoke() throws Throwable {
            invocations++;
            WindowsJniRegistrationOwner retained = WindowsJniRegistrationOwner.retainedProcessOwner();
            check(retained != null && retained.retention == ROOTS);
            check(retained.state() == WindowsJniRegistrationOwner.State.Invoking);
            during.run();
            if (invocationFailure != null) throw invocationFailure;
            return result;
        }

        @Override public WindowsJniRegistrationOwner.Report readReport() throws Throwable {
            reads++;
            if (reportFailure != null) throw reportFailure;
            return report;
        }

        @Override public void retireFrame() throws Throwable {
            retirements++;
            check(WindowsJniRegistrationOwner.retainedProcessOwner().retention == ROOTS);
            if (cleanupFailure != null) throw cleanupFailure;
        }
    }

    public static void main(String[] args) throws Exception {
        if (args.length != 1) throw new AssertionError("One fixed scenario required");
        check(WindowsJniRegistrationOwner.retainedProcessOwner() == null);
        Call call = new Call();
        WindowsJniRegistrationOwner.FailureKind expected = null;
        switch (args[0]) {
            case "success" -> {}
            case "reentrant" -> call.during = RegistrationOwnerTests::refuseDuplicate;
            case "concurrent" -> call.during = RegistrationOwnerTests::concurrentRefusal;
            case "invocation" -> {
                call.invocationFailure = INVOCATION_ERROR;
                expected = WindowsJniRegistrationOwner.FailureKind.Invocation;
            }
            case "report" -> {
                call.reportFailure = REPORT_ERROR;
                expected = WindowsJniRegistrationOwner.FailureKind.ReportRead;
            }
            case "cleanup" -> {
                call.cleanupFailure = CLEANUP_ERROR;
                expected = WindowsJniRegistrationOwner.FailureKind.FrameRetirement;
            }
            case "invocation-cleanup" -> {
                call.invocationFailure = INVOCATION_ERROR;
                call.cleanupFailure = CLEANUP_ERROR;
                expected = WindowsJniRegistrationOwner.FailureKind.Invocation;
            }
            case "report-cleanup" -> {
                call.reportFailure = REPORT_ERROR;
                call.cleanupFailure = CLEANUP_ERROR;
                expected = WindowsJniRegistrationOwner.FailureKind.ReportRead;
            }
            case "null-report" -> {
                call.report = null;
                expected = WindowsJniRegistrationOwner.FailureKind.MalformedReport;
            }
            case "virtual" -> virtualRefusal();
            case "copied-owner" -> copiedOwnerRefusal();
            case "null-input" -> {
                expect(NullPointerException.class, () -> WindowsJniRegistrationOwner.registerOnce(null, call));
                expect(NullPointerException.class, () -> WindowsJniRegistrationOwner.registerOnce(ROOTS, null));
                check(WindowsJniRegistrationOwner.retainedProcessOwner() == null);
            }
            default -> {
                if (args[0].startsWith("malformed-")) {
                    int position = Integer.parseInt(args[0].substring("malformed-".length()));
                    int[] words = {32, 1, 2, 0, 1, 0, 0, 0};
                    check(position >= 0 && position < 24);
                    int index = position / 3;
                    words[index] = switch (position % 3) {
                        case 0 -> -1;
                        case 1 -> 10;
                        default -> words[index] == 0 ? 1 : 0;
                    };
                    call.report = report(words);
                    expected = WindowsJniRegistrationOwner.FailureKind.MalformedReport;
                } else if (args[0].startsWith("refusal-")) {
                    int code = Integer.parseInt(args[0].substring("refusal-".length()));
                    check(code >= 1 && code <= 10);
                    call.result = code;
                    call.report = new WindowsJniRegistrationOwner.Report(32, 1,
                        code >= 9 ? 1 : 0, code, code >= 9 ? 1 : 0,
                        code == 10 ? 1 : 0, 0, code == 10 ? 1 : 0);
                    expected = WindowsJniRegistrationOwner.FailureKind.NativeRefusal;
                } else throw new AssertionError("Unknown scenario");
            }
        }
        if (expected == null) {
            WindowsJniRegistrationOwner actual = WindowsJniRegistrationOwner.registerOnce(ROOTS, call);
            check(actual == WindowsJniRegistrationOwner.retainedProcessOwner());
            check(actual.state() == WindowsJniRegistrationOwner.State.Registered);
        } else {
            WindowsJniRegistrationOwner.Failure failure = (WindowsJniRegistrationOwner.Failure)
                expect(WindowsJniRegistrationOwner.Failure.class,
                    () -> WindowsJniRegistrationOwner.registerOnce(ROOTS, call));
            check(failure.kind == expected && failure.retainedOwner == WindowsJniRegistrationOwner.retainedProcessOwner());
            check(failure.retainedOwner.state() == WindowsJniRegistrationOwner.State.Failed);
            check(failure.invocationFailure == call.invocationFailure && failure.reportFailure == call.reportFailure &&
                failure.retirementFailure == call.cleanupFailure && failure.controllerFailure == null &&
                failure.getSuppressed().length == 0);
        }
        check(call.invocations == 1 && call.reads == (call.invocationFailure == null ? 1 : 0) && call.retirements == 1);
        // Direct retained-root identity check, not evidence that GC would otherwise reclaim these objects.
        call.report = null;
        System.gc();
        check(WindowsJniRegistrationOwner.retainedProcessOwner().retention == ROOTS);
        refuseDuplicate();
        check(call.invocations == 1 && call.retirements == 1);
        System.out.println("WINDOWS_JNI_OWNER_PASS case=" + args[0] +
            " scope=PORTABLE_LIFETIME_NOT_NATIVE_REGISTRATION_OR_AUTHORITY");
    }

    private static WindowsJniRegistrationOwner.Report report(int[] words) {
        return new WindowsJniRegistrationOwner.Report(words[0], words[1], words[2], words[3],
            words[4], words[5], words[6], words[7]);
    }

    private static void refuseDuplicate() {
        Call duplicate = new Call();
        expect(IllegalStateException.class, () -> WindowsJniRegistrationOwner.registerOnce(ROOTS, duplicate));
        check(duplicate.invocations == 0 && duplicate.reads == 0 && duplicate.retirements == 0);
    }

    private static void concurrentRefusal() {
        AtomicReference<Throwable> failure = new AtomicReference<>();
        CountDownLatch finished = new CountDownLatch(1);
        Thread other = new Thread(() -> {
            try { refuseDuplicate(); } catch (Throwable caught) { failure.set(caught); }
            finally { finished.countDown(); }
        }, "registration-owner-duplicate");
        other.setDaemon(true);
        other.start();
        try { check(finished.await(5, TimeUnit.SECONDS)); }
        catch (InterruptedException interrupted) { throw new AssertionError(interrupted); }
        if (failure.get() != null) throw new AssertionError(failure.get());
    }

    private static void virtualRefusal() throws InterruptedException {
        Call virtual = new Call();
        AtomicReference<Throwable> failure = new AtomicReference<>();
        Thread thread = Thread.ofVirtual().start(() -> {
            try { expect(IllegalStateException.class, () -> WindowsJniRegistrationOwner.registerOnce(ROOTS, virtual)); }
            catch (Throwable caught) { failure.set(caught); }
        });
        thread.join(5000);
        check(!thread.isAlive() && virtual.invocations == 0 && virtual.retirements == 0);
        check(WindowsJniRegistrationOwner.retainedProcessOwner() == null);
        if (failure.get() != null) throw new AssertionError(failure.get());
    }

    private static void copiedOwnerRefusal() throws Exception {
        String name = WindowsJniRegistrationOwner.class.getName();
        ClassLoader copyLoader = new ClassLoader(ClassLoader.getSystemClassLoader()) {
            @Override protected Class<?> loadClass(String requested, boolean resolve) throws ClassNotFoundException {
                if (!requested.equals(name) && !requested.startsWith(name + "$")) return super.loadClass(requested, resolve);
                synchronized (getClassLoadingLock(requested)) {
                    Class<?> type = findLoadedClass(requested);
                    if (type == null) {
                        try (InputStream bytes = WindowsJniRegistrationOwner.class.getResourceAsStream(
                                "/" + requested.replace('.', '/') + ".class")) {
                            if (bytes == null) throw new ClassNotFoundException(requested);
                            byte[] content = bytes.readNBytes(65537);
                            check(content.length <= 65536);
                            type = defineClass(requested, content, 0, content.length);
                        } catch (IOException caught) { throw new ClassNotFoundException(requested, caught); }
                    }
                    if (resolve) resolveClass(type);
                    return type;
                }
            }
        };
        Class<?> copied = copyLoader.loadClass(name);
        check(copied != WindowsJniRegistrationOwner.class && !copied.getModule().isNamed());
        Method entry = copied.getDeclaredMethod("registerOnce", copyLoader.loadClass(name + "$Retention"),
            copyLoader.loadClass(name + "$Invocation"));
        entry.setAccessible(true); // Inert child-loader copy, never access/modify the original module's slot.
        try { entry.invoke(null, new Object[] {null, null}); throw new AssertionError("Copied owner admitted"); }
        catch (InvocationTargetException caught) {
            check(caught.getCause() instanceof IllegalStateException &&
                caught.getCause().getMessage().contains("original boot module"));
        }
        check(WindowsJniRegistrationOwner.retainedProcessOwner() == null);
    }

    private static Throwable expect(Class<? extends Throwable> type, Runnable action) {
        try { action.run(); } catch (Throwable failure) {
            if (type.isInstance(failure)) return failure;
            throw new AssertionError("Unexpected failure type", failure);
        }
        throw new AssertionError("Expected failure");
    }

    private static void check(boolean condition) {
        if (!condition) throw new AssertionError("Registration owner contract failed");
    }
}
