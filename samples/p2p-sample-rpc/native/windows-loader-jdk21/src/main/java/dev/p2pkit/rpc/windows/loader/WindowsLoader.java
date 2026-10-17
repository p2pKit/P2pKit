package dev.p2pkit.rpc.windows.loader;

/**
 * Public fail-closed implementation boundary. The internal original installed composition below
 * remains unreachable from the public API and is not installed Windows/provider qualification.
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
                bootstrap = WindowsSystemBootstrapCandidate.inspect();
                installation = bootstrap.inspectOriginalInstallation();
                profile = installation.prepareProfileLoad();
                registration = profile.registerOriginalProfile();
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

    /** Closed source composition only; the public entry deliberately does not call this method. */
    static void completeOriginalInstalledProvider() {
        WindowsLoaderRuntime.requireDiagnosticRuntime();
        InstalledAttempt attempt = claimOriginalInstalledProvider();
        if (attempt != null) attempt.complete();
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
