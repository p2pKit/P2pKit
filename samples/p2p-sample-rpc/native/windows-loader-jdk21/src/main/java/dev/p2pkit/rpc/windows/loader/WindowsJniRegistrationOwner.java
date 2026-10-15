package dev.p2pkit.rpc.windows.loader;

import java.util.Objects;

/**
 * Dormant post-admission lifetime mechanism, NOT bootstrap or native load authority.
 * The productive loader has no caller of this class. References do not establish OS handle custody,
 * immutable mappings, import identity or the right to call an address. The future reviewed loader must
 * establish those facts first and transfer exclusive original owners, never borrowed closeable aliases.
 * This boot-module root prevents Java reclamation; actual OS/module retention is the owners' contract.
 */
final class WindowsJniRegistrationOwner {
    enum State { Reserved, Invoking, Registered, Failed }
    enum FailureKind { Invocation, ReportRead, MalformedReport, NativeRefusal, FrameRetirement, Controller }

    /** Fixed strong references, not an assertion that these objects grant any permission. */
    record Retention(Object installationOwner, Object runtimeOwner, Object moduleOwner,
                     Class<?> declaringClass, Object registrationPlan) {
        Retention {
            Objects.requireNonNull(installationOwner);
            Objects.requireNonNull(runtimeOwner);
            Objects.requireNonNull(moduleOwner);
            Objects.requireNonNull(declaringClass);
            Objects.requireNonNull(registrationPlan);
        }
    }

    /**
     * Internal synchronous integration boundary, not a public callback loader. A future implementation
     * owns its live, disjoint frame and verified original entry; it must not return while native work runs.
     * Retirement clears/closes ONLY invocation buffers, never module/runtime/class/installation owners.
     * The dormant fixed FFM implementation has no productive caller or load authority. Portable tests
     * use inert invocations or a JDK-generated upcall stub, never a candidate DLL or protected storage.
     */
    interface Invocation {
        int invoke() throws Throwable;
        Report readReport() throws Throwable;
        void retireFrame() throws Throwable;
    }

    /** Immutable readback, not a caller-writable array reread after validation. */
    record Report(int size, int version, int phase, int result, int classRetained,
                  int exceptionObserved, int exceptionRetained, int retentionUncertain) {}

    static final class Failure extends RuntimeException {
        private static final long serialVersionUID = 1L;
        final transient WindowsJniRegistrationOwner retainedOwner;
        // Initialize the enum (including its allocating constants table) BEFORE any native effects.
        FailureKind kind = FailureKind.Invocation;
        Throwable invocationFailure;
        Throwable reportFailure;
        Throwable retirementFailure;
        Throwable controllerFailure;

        Failure(WindowsJniRegistrationOwner owner) {
            // Reserve before native effects; no stack/suppression allocation while reporting an Error.
            super("Windows JNI registration sealed with process-lifetime ownership retained", null, false, false);
            retainedOwner = owner;
        }
    }

    private static WindowsJniRegistrationOwner processOwner;
    final Retention retention;
    private final Invocation invocation;
    private final Failure failure = new Failure(this);
    private Report report;
    private volatile State state = State.Reserved;
    private int nativeResult;

    private WindowsJniRegistrationOwner(Retention retention, Invocation invocation) {
        this.retention = Objects.requireNonNull(retention);
        this.invocation = Objects.requireNonNull(invocation);
    }

    /**
     * Reserve before even entering the registrar. Every admitted attempt is permanent, including phase 0,
     * thrown downcalls and malformed reports. There is no reset, unregister, unload, close or Stop method.
     * A rejected duplicate does not consume/retire its caller-owned frame. Success is registration only,
     * never a complete-provider publication or qualification result.
     */
    static WindowsJniRegistrationOwner registerOnce(Retention retention, Invocation invocation) {
        WindowsLoaderRuntime.requireDiagnosticRuntime();
        if (WindowsJniRegistrationOwner.class.getModule() != WindowsLoaderRuntime.class.getModule()) {
            throw new IllegalStateException("Windows JNI lifetime owner must belong to the original boot module");
        }
        if (Thread.currentThread().isVirtual()) {
            throw new IllegalStateException("Windows JNI registration requires its attached platform thread");
        }
        WindowsJniRegistrationOwner candidate = new WindowsJniRegistrationOwner(retention, invocation);
        synchronized (WindowsJniRegistrationOwner.class) {
            if (processOwner != null) throw new IllegalStateException("Windows JNI process attempt already reserved");
            // No callbacks/native work before the static root owns all references and the failure carrier.
            processOwner = candidate;
        }
        candidate.run();
        return candidate;
    }

    static synchronized WindowsJniRegistrationOwner retainedProcessOwner() { return processOwner; }
    State state() { return state; }
    boolean ownsInvocation(Invocation candidate) { return invocation == candidate; }

    private void run() {
        state = State.Invoking;
        failure.kind = null;
        boolean accepted = false;
        try {
            try { nativeResult = invocation.invoke(); }
            catch (Throwable caught) {
                failure.kind = FailureKind.Invocation;
                failure.invocationFailure = caught;
            }
            if (failure.kind == null) {
                try { report = invocation.readReport(); }
                catch (Throwable caught) {
                    failure.kind = FailureKind.ReportRead;
                    failure.reportFailure = caught;
                }
            }
            if (failure.kind == null) {
                if (!wellFormed()) failure.kind = FailureKind.MalformedReport;
                else if (nativeResult != 0) failure.kind = FailureKind.NativeRefusal;
                else accepted = true;
            }
        } catch (Throwable caught) {
            failure.controllerFailure = caught;
            if (failure.kind == null) failure.kind = FailureKind.Controller;
        } finally {
            try { invocation.retireFrame(); }
            catch (Throwable caught) {
                failure.retirementFailure = caught;
                if (failure.kind == null) failure.kind = FailureKind.FrameRetirement;
            }
            // Even successful buffer retirement does not release any original native/module owner.
            state = accepted && failure.kind == null ? State.Registered : State.Failed;
        }
        if (state == State.Failed) throw failure;
    }

    private boolean wellFormed() {
        if (report == null || report.size != 32 || report.version != 1 || report.phase < 0 || report.phase > 2 ||
            report.result != nativeResult || nativeResult < 0 || nativeResult > 10 ||
            !bit(report.classRetained) || !bit(report.exceptionObserved) ||
            !bit(report.exceptionRetained) || !bit(report.retentionUncertain)) return false;
        if (report.exceptionRetained > report.exceptionObserved || (report.phase != 0 && report.classRetained != 1) ||
            (report.exceptionObserved == 1 && report.exceptionRetained == 0 && report.retentionUncertain != 1) ||
            (report.retentionUncertain == 1) != (nativeResult == 10)) return false;
        if (nativeResult == 0) {
            return report.phase == 2 && report.classRetained == 1 && report.exceptionObserved == 0 &&
                report.exceptionRetained == 0 && report.retentionUncertain == 0;
        }
        return report.phase != 2;
    }

    private static boolean bit(int value) { return value == 0 || value == 1; }
}
