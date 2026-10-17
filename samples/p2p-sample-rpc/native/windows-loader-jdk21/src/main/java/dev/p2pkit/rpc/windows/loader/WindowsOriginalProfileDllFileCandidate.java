package dev.p2pkit.rpc.windows.loader;

import java.lang.foreign.Arena;
import java.lang.foreign.Linker;
import java.lang.foreign.MemorySegment;

/**
 * Independent read-only profile-DLL file observation attached to the original conditional OS bootstrap.
 * A canonical locator and matching final-file metadata are NOT package, ancestor/ACL, byte, mapped-image
 * or startup authority. No JVM object is repurposed, no DLL is loaded and no profile operation exists.
 * Every attempted failure is terminal for this attachment; its actual core/failure owners stay retained.
 */
final class WindowsOriginalProfileDllFileCandidate {
    static final class Failure extends RuntimeException {
        private static final long serialVersionUID = 1L;
        final transient WindowsOriginalProfileDllFileCandidate retainedCandidate;
        Throwable operationFailure;

        private Failure(WindowsOriginalProfileDllFileCandidate candidate) {
            super("Original profile DLL file observation failed with ownership retained", null, false, false);
            retainedCandidate = candidate;
        }
    }

    private final Thread thread = Thread.currentThread();
    private final WindowsSystemBootstrapCandidate bootstrap;
    private final String candidatePath;
    private final Failure failure = new Failure(this);
    private char[] originalPath;
    private WindowsOriginalFileLease lease;
    private boolean attempted;
    private boolean failed;
    private boolean succeeded;
    private boolean securityAttempted;
    private boolean securityPolicyRefused;
    private boolean ancestorsPolicyRefused;
    private boolean bytesAttempted;
    private WindowsOriginalProfileDllBytesCandidate bytes;
    private WindowsOriginalProfileDllSecurityCandidate security;

    WindowsOriginalProfileDllFileCandidate(WindowsSystemBootstrapCandidate bootstrap, String candidatePath) {
        this.bootstrap = bootstrap;
        this.candidatePath = candidatePath;
    }

    void observe() {
        requireOriginalBootstrap();
        if (attempted) throw new IllegalStateException("Original profile DLL file observation is already consumed");
        attempted = true;
        try {
            WindowsProfileDllPath.require(candidatePath);
            originalPath = new char[candidatePath.length() + 1];
            candidatePath.getChars(0, candidatePath.length(), originalPath, 0);
            lease = WindowsOriginalFileLease.forProfileDll(this);
            // Exact core and its preallocated failure are attached before the first original file effect.
            lease.observe();
            lease.completed();
            succeeded = true;
        } catch (Throwable caught) {
            failure.operationFailure = caught;
            failed = true;
            throw failure;
        }
    }

    private void requireOriginalBootstrap() {
        if (Thread.currentThread() != thread || bootstrap == null) {
            throw new IllegalStateException(
                "Original profile DLL file requires its original platform thread/bootstrap");
        }
        bootstrap.requireOriginalProfileDll(this);
        if (failed) throw failure;
    }

    void requireOriginalLease(WindowsOriginalFileLease candidate) {
        requireOriginalBootstrap();
        if (!attempted || candidate == null || candidate != lease) {
            throw new IllegalStateException("File lease is not this profile DLL facade's original retained attachment");
        }
        // No completed() call here: the original core invokes this guard while it is still observing.
    }

    private void requireCompleted() {
        requireOriginalBootstrap();
        if (!succeeded || lease == null) {
            throw new IllegalStateException("Original profile DLL file has no completed observation");
        }
        lease.completed();
    }

    boolean completed() { requireCompleted(); return true; }
    boolean leaseHeld() { requireCompleted(); return true; }

    WindowsOriginalProfileDllSecurityCandidate inspectSecurity() {
        requireCompleted();
        if (securityAttempted) throw new IllegalStateException("Original profile DLL security was already attempted");
        securityAttempted = true;
        try {
            security = lease.newProfileDllSecurity(this);
            // Both concrete facade/core failure roots exist before any module PIN or security query.
            security.observe();
            securityPolicyRefused = !security.descriptorPolicyAccepted();
            return security;
        } catch (Throwable caught) {
            failure.operationFailure = caught;
            failed = true;
            throw failure;
        }
    }

    void requireOriginalSecurity(WindowsOriginalProfileDllSecurityCandidate candidate) {
        requireCompleted();
        if (candidate == null || candidate != security) {
            throw new IllegalStateException("Security candidate is not this profile DLL file's original attachment");
        }
    }

    void requireOriginalNativeInputs() {
        requireOriginalBootstrap();
        if (securityPolicyRefused || ancestorsPolicyRefused) {
            throw new IllegalStateException("Original profile DLL security policy refused further native inputs");
        }
        // Negative latches are not authorization tokens. Accepted diagnostics do not grant loading authority.
    }

    Linker originalLinker() {
        requireOriginalNativeInputs();
        return bootstrap.originalProfileDllLinker(this);
    }

    Arena originalBootstrapArena() {
        requireOriginalNativeInputs();
        return bootstrap.originalProfileDllArena(this);
    }

    MemorySegment originalFileEntry(int index) {
        requireOriginalNativeInputs();
        return bootstrap.originalProfileDllFileEntry(this, index);
    }

    char[] originalPathSnapshot() {
        requireOriginalNativeInputs();
        if (!attempted || originalPath == null) {
            throw new IllegalStateException("Original profile DLL pathname has not been validated");
        }
        return originalPath.clone();
    }

    MemorySegment originalSecurityEntry(WindowsOriginalFileLease candidate, int index) {
        requireOriginalNativeInputs();
        requireOriginalLease(candidate);
        return bootstrap.originalProfileDllSecurityEntry(this, index);
    }

    WindowsOriginalProfileDllAncestorsCandidate newOriginalAncestors(WindowsOriginalProfileDllSecurityCandidate candidate,
        Arena moduleArena, MemorySegment module, MemorySegment queryEntry, MemorySegment pinEntry,
        MemorySegment resolveEntry) {
        requireOriginalSecurity(candidate);
        candidate.requireOriginalAncestorInputs();
        return lease.newProfileDllAncestors(this, candidate, moduleArena, module, queryEntry, pinEntry, resolveEntry);
    }

    void finishOriginalAncestors(WindowsOriginalProfileDllSecurityCandidate candidate,
        WindowsOriginalProfileDllAncestorsCandidate ancestors) {
        requireOriginalSecurity(candidate);
        candidate.requireOriginalAncestors(ancestors);
        ancestorsPolicyRefused = !ancestors.descriptorPoliciesAccepted();
        // A full bounded diagnostic walk is complete even on ordinary policy refusal. Its original
        // scopes remain retained; only later native-input factories/continuations are sealed.
    }

    Failure failOriginalSecurity(WindowsOriginalProfileDllSecurityCandidate candidate, Throwable caught) {
        requireOriginalSecurity(candidate);
        failure.operationFailure = caught;
        failed = true;
        return failure;
    }

    MemorySegment originalAncestorsEntry(WindowsOriginalFileLease candidate, int index) {
        requireOriginalNativeInputs();
        requireOriginalLease(candidate);
        return bootstrap.originalProfileDllAncestorsEntry(this, index);
    }

    WindowsOriginalProfileDllBytesCandidate inspectBytes() {
        requireCompleted();
        requireOriginalByteInputs(); // Missing or refused leaf/ancestor observations never consume a read attachment.
        if (bytesAttempted) throw new IllegalStateException("Original profile DLL bytes were already attempted");
        bytesAttempted = true;
        try {
            bytes = lease.newProfileDllBytes(this);
            // Root, concrete child and core failures are retained before metadata or the first ReadFile.
            bytes.observe();
            return bytes;
        } catch (Throwable caught) {
            failure.operationFailure = caught;
            failed = true;
            throw failure;
        }
    }

    void requireOriginalBytes(WindowsOriginalProfileDllBytesCandidate candidate) {
        requireCompleted();
        if (candidate == null || candidate != bytes) {
            throw new IllegalStateException("Byte candidate is not this profile DLL file's original attachment");
        }
    }

    Failure failOriginalBytes(WindowsOriginalProfileDllBytesCandidate candidate, Throwable caught) {
        requireOriginalBytes(candidate);
        failure.operationFailure = caught;
        failed = true;
        return failure;
    }

    WindowsOriginalSystemModulesCandidate originalSystemModules(WindowsOriginalProfileDllBytesCandidate candidate) {
        requireOriginalBytes(candidate);
        requireOriginalByteInputs();
        return bootstrap.originalProfileDllSystemModules(this);
    }

    void requireOriginalLoadedFile(WindowsOriginalProfileDllBytesCandidate candidate,
                                   WindowsLibraryLoadInvocation.Result load) {
        requireOriginalBytes(candidate);
        requireOriginalByteInputs();
        bootstrap.requireOriginalLoadedImage(load);
        load.retainedInvocation.requireOriginalFile(this, candidatePath);
    }

    void requireOriginalByteInputs() {
        requireCompleted();
        requireOriginalNativeInputs();
        if (security == null) throw new IllegalStateException("Original profile DLL bytes lack original security observations");
        security.requireOriginalByteInputs();
    }

    MemorySegment originalReadEntry(WindowsOriginalFileLease candidate) {
        requireOriginalLease(candidate);
        requireOriginalByteInputs();
        return bootstrap.originalProfileDllReadEntry(this);
    }
}
