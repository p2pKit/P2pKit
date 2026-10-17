package dev.p2pkit.rpc.windows.loader;

import java.lang.foreign.Arena;
import java.lang.foreign.Linker;
import java.lang.foreign.MemorySegment;

/** Original DLL ancestor diagnostic; a completed refused policy is not a native continuation grant. */
final class WindowsOriginalProfileDllAncestorsCandidate {
    static final class Failure extends RuntimeException {
        private static final long serialVersionUID = 1L;
        final transient WindowsOriginalProfileDllAncestorsCandidate retainedCandidate;
        Throwable operationFailure;

        private Failure(WindowsOriginalProfileDllAncestorsCandidate candidate) {
            super("Original profile DLL ancestor observation failed with ownership retained", null, false, false);
            retainedCandidate = candidate;
        }
    }

    private final Thread thread = Thread.currentThread();
    private final WindowsOriginalProfileDllSecurityCandidate security;
    private final Failure failure = new Failure(this);
    private final WindowsOriginalFileAncestorsLease core;
    private boolean attempted;
    private boolean failed;

    WindowsOriginalProfileDllAncestorsCandidate(WindowsOriginalProfileDllSecurityCandidate security, Linker linker,
        Arena bootstrapArena, Arena moduleArena, MemorySegment module, MemorySegment queryEntry,
        MemorySegment pinEntry, MemorySegment resolveEntry, MemorySegment createEntry,
        MemorySegment informationEntry, MemorySegment finalPathEntry, MemorySegment volumeEntry,
        MemorySegment driveEntry, Arena originalFileArena, MemorySegment originalFileHandle,
        char[] originalPath, int pathLength, long[] originalFile) {
        this.security = security;
        core = WindowsOriginalFileAncestorsLease.forProfileDll(this, linker, bootstrapArena, moduleArena, module,
            queryEntry, pinEntry, resolveEntry,
            createEntry, informationEntry, finalPathEntry, volumeEntry, driveEntry, originalFileArena,
            originalFileHandle, originalPath, pathLength, originalFile);
    }

    void observe() {
        requireOriginalSecurity();
        if (attempted) throw new IllegalStateException("Original profile DLL ancestors were already attempted");
        attempted = true;
        try {
            core.observe();
        } catch (Throwable caught) {
            failure.operationFailure = caught;
            failed = true;
            throw failure;
        }
    }

    private void requireOriginalSecurity() {
        if (Thread.currentThread() != thread || security == null) {
            throw new IllegalStateException("Original profile DLL ancestors require their original platform thread/security");
        }
        security.requireOriginalAncestors(this);
        if (failed) throw failure;
    }

    void requireInstallationRoot(WindowsInstalledProfileCandidate candidate) {
        candidate.requireOriginalProfileAncestors(this);
        candidate.joinRoot(core);
    }

    void requireOriginalCore(WindowsOriginalFileAncestorsLease candidate) {
        if (candidate == null || candidate != core) {
            throw new IllegalStateException("Ancestor core is not this profile DLL facade's original attachment");
        }
        requireOriginalSecurity();
    }

    void requireOriginalNativeInputs() {
        requireOriginalSecurity();
        security.requireOriginalAncestorInputs();
    }

    boolean completed() { requireOriginalSecurity(); return core.completed(); }
    int ancestorCount() { requireOriginalSecurity(); return core.ancestorCount(); }
    boolean descriptorPoliciesAccepted() { requireOriginalSecurity(); return core.descriptorPoliciesAccepted(); }
}
