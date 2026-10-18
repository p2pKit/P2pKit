package dev.p2pkit.rpc.windows.loader;

/**
 * Public fail-closed implementation boundary. The internal original installed composition below
 * remains unreachable from the public provider entry. The separately explicit installed diagnostic
 * may exercise it; implementation alone is not installed Windows/provider qualification.
 */
public final class WindowsLoader {
    public static final String REFUSAL = "WINDOWS_LOADER_DISABLED_TRUSTED_BOOTSTRAP_NOT_IMPLEMENTED";

    private WindowsLoader() {}

    /**
     * Exact no-effects result of this fixed entry, never a generic native failure classification.
     * Only this class may construct it, before any installed/native acquisition. Future productive
     * failures must retain their actual owner and must not be translated into this retryable refusal.
     */
    public static final class Unavailable extends UnsupportedOperationException {
        private static final long serialVersionUID = 1L;

        private Unavailable() { super(REFUSAL); }
    }

    private enum InstalledState { Reserved, Registered, Failed }

    private static final class InstalledFailure extends RuntimeException {
        private static final long serialVersionUID = 1L;
        final transient InstalledAttempt retainedAttempt;
        Throwable operationFailure;

        InstalledFailure(InstalledAttempt attempt) {
            super("Original installed provider attempt sealed with process ownership retained", null, false, false);
            retainedAttempt = attempt;
        }
    }

    /** All fields are private to this controller; no confined owner escapes on reuse. */
    private static final class InstalledAttempt {
        final Thread ownerThread = Thread.currentThread();
        final InstalledFailure failure = new InstalledFailure(this);
        InstalledState state = InstalledState.Reserved;
        int diagnosticPhase; // Pure metadata only, set before each existing operation.
        WindowsSystemBootstrapCandidate bootstrap;
        WindowsOriginalInstallationCandidate installation;
        WindowsInstalledProfileCandidate profile;
        WindowsJniRegistrationOwner registration;

        private void requireClaimed() {
            synchronized (WindowsLoader.class) {
                if (installedAttempt != this || ownerThread != Thread.currentThread() ||
                    state != InstalledState.Reserved) {
                    throw new IllegalStateException("Original installed attempt is not this thread's reservation");
                }
            }
        }

        private void complete() {
            requireClaimed();
            // No monitor is held across any original native acquisition. Each deeper owner attaches
            // its own partial children before effects, including when a call does not return a child.
            try {
                diagnosticPhase = 1;
                bootstrap = WindowsSystemBootstrapCandidate.inspect();
                diagnosticPhase = 2;
                installation = bootstrap.inspectOriginalInstallation();
                diagnosticPhase = 3;
                profile = installation.prepareProfileLoad();
                diagnosticPhase = 4;
                registration = profile.registerOriginalProfile();
                diagnosticPhase = 5;
                publishRegistered();
            } catch (Throwable caught) {
                throw seal(caught);
            }
        }

        private void publishRegistered() {
            synchronized (WindowsLoader.class) {
                requireClaimed();
                if (registration == null || registration.state() != WindowsJniRegistrationOwner.State.Registered) {
                    throw new IllegalStateException("Original installed registration did not complete");
                }
                // Safe publication of the exact returned owner, after native frame retirement.
                state = InstalledState.Registered;
            }
        }

        private InstalledFailure seal(Throwable caught) {
            synchronized (WindowsLoader.class) {
                requireClaimed();
                failure.operationFailure = caught;
                state = InstalledState.Failed;
                return failure;
            }
        }
    }

    private static InstalledAttempt installedAttempt;

    private static synchronized InstalledAttempt claimOriginalInstalledProvider() {
        if (installedAttempt != null) {
            if (installedAttempt.state == InstalledState.Failed) throw installedAttempt.failure;
            if (installedAttempt.state == InstalledState.Registered) {
                // Only stable Java owner state is read here: never confined child/FFM access.
                if (installedAttempt.registration == null ||
                    installedAttempt.registration.state() != WindowsJniRegistrationOwner.State.Registered) {
                    throw new IllegalStateException("Retained original installed registration is incomplete");
                }
                return null;
            }
            throw new IllegalStateException("Original installed provider attempt is already in progress");
        }
        if (Thread.currentThread().isVirtual()) {
            throw new IllegalStateException("Original installed admission requires a platform thread");
        }
        // Reserve the root and preallocated failure carrier before even the first bootstrap call.
        installedAttempt = new InstalledAttempt();
        return installedAttempt;
    }

    /** Closed original composition; only the explicit diagnostic, not the public provider, calls it. */
    static void completeOriginalInstalledProvider() {
        WindowsLoaderRuntime.requireDiagnosticRuntime();
        InstalledAttempt attempt = claimOriginalInstalledProvider();
        if (attempt != null) attempt.complete();
    }

    /** Pure retained-state readback: never acquire/retire/retry or call a completed-owner guard. */
    static synchronized String installedFailureStage(Throwable original) {
        InstalledAttempt attempt = installedAttempt;
        if (attempt == null || attempt.state != InstalledState.Failed || original != attempt.failure) {
            return "NO_MATCHING_RETAINED_FAILURE";
        }
        Throwable operation = attempt.failure.operationFailure;
        if (attempt.diagnosticPhase == 1 && operation instanceof WindowsSystemBootstrapCandidate.Failure value) {
            return value.retainedCandidate.failureOperation();
        }
        // Only these fixed, source-owned carriers are inspected; no arbitrary getCause/toString walk.
        if (attempt.diagnosticPhase == 3 && operation instanceof WindowsOriginalInstallationCandidate.Failure value) {
            operation = value.operationFailure;
        }
        if ((attempt.diagnosticPhase == 3 || attempt.diagnosticPhase == 4) &&
            operation instanceof WindowsInstalledProfileCandidate.Failure value) {
            return value.retainedCandidate.failureOperation();
        }
        return switch (attempt.diagnosticPhase) {
            case 0 -> "RESERVATION";
            case 1 -> "BOOTSTRAP";
            case 2 -> "INSTALLATION";
            case 3 -> "PROFILE_PREPARATION";
            case 4 -> "JNI_REGISTRATION";
            case 5 -> "PUBLISH_REGISTERED";
            default -> "UNKNOWN_RETAINED_OPERATION";
        };
    }

    /**
     * No caller may supply a path, boolean, manifest or context to bypass the missing trust boundary.
     * A future normal return must retain the actual installed production image/runtime and registered
     * JNI owner for the process lifetime. A development/test DLL registration cannot satisfy this entry.
     */
    public static void openInstalledProvider() {
        WindowsLoaderRuntime.requireDiagnosticRuntime();
        throw new Unavailable();
    }
}
