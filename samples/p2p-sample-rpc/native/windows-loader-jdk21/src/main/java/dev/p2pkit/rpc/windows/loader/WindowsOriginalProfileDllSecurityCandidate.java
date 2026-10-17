package dev.p2pkit.rpc.windows.loader;

import java.lang.foreign.Arena;
import java.lang.foreign.Linker;
import java.lang.foreign.MemorySegment;

/**
 * Independent original-DLL OWNER|DACL observation, never JVM, ancestor or loading authority.
 * A completed query may have a refused descriptor policy. Native/retirement failure is terminal;
 * ordinary policy refusal remains observable but blocks the file owner's native-input accessors.
 */
final class WindowsOriginalProfileDllSecurityCandidate {
    static final class Failure extends RuntimeException {
        private static final long serialVersionUID = 1L;
        final transient WindowsOriginalProfileDllSecurityCandidate retainedCandidate;
        Throwable operationFailure;

        private Failure(WindowsOriginalProfileDllSecurityCandidate candidate) {
            super("Original profile DLL security query failed with ownership retained", null, false, false);
            retainedCandidate = candidate;
        }
    }

    private final Thread thread = Thread.currentThread();
    private final WindowsOriginalProfileDllFileCandidate file;
    private final Failure failure = new Failure(this);
    private final WindowsOriginalFileSecurityQuery query;
    private boolean attempted;
    private boolean failed;
    private boolean ancestorsAttempted;
    private WindowsOriginalProfileDllAncestorsCandidate ancestors;

    WindowsOriginalProfileDllSecurityCandidate(WindowsOriginalProfileDllFileCandidate file, Linker linker,
        Arena bootstrapArena, Arena fileArena, MemorySegment fileHandle, MemorySegment pinEntry,
        MemorySegment pathEntry, MemorySegment systemPathEntry, MemorySegment resolveEntry) {
        this.file = file;
        query = WindowsOriginalFileSecurityQuery.forProfileDll(this, linker, bootstrapArena, fileArena, fileHandle,
            pinEntry, pathEntry, systemPathEntry, resolveEntry);
    }

    void observe() {
        requireOriginalFile();
        if (attempted) throw new IllegalStateException("Original profile DLL security query is already consumed");
        attempted = true;
        try {
            query.observe();
        } catch (Throwable caught) {
            failure.operationFailure = caught;
            failed = true;
            throw failure;
        }
    }

    private void requireOriginalFile() {
        if (Thread.currentThread() != thread || file == null) {
            throw new IllegalStateException("Original profile DLL security requires its original platform thread/file");
        }
        file.requireOriginalSecurity(this);
        if (failed) throw failure;
    }

    void requireOriginalQuery(WindowsOriginalFileSecurityQuery candidate) {
        if (candidate == null || candidate != query) {
            throw new IllegalStateException("Security query is not this profile DLL facade's original retained attachment");
        }
        requireOriginalFile(); // No query.completed() recursion during the original query.
    }

    WindowsOriginalProfileDllAncestorsCandidate inspectAncestors() {
        requireOriginalAncestorInputs(); // Leaf policy refusal is diagnostic, before attachment or any new effect.
        if (ancestorsAttempted) throw new IllegalStateException("Original profile DLL ancestors were already attempted");
        ancestorsAttempted = true;
        try {
            ancestors = query.newProfileDllAncestors(this);
            // The concrete child/core and all failure carriers are attached before the first ancestor effect.
            ancestors.observe();
            file.finishOriginalAncestors(this, ancestors);
            return ancestors;
        } catch (Throwable caught) {
            failure.operationFailure = caught;
            failed = true;
            throw file.failOriginalSecurity(this, failure);
        }
    }

    void requireOriginalAncestorInputs() {
        requireOriginalFile();
        query.completed();
        file.requireOriginalNativeInputs();
        if (!query.descriptorPolicyAccepted()) {
            throw new IllegalStateException("Original profile DLL leaf policy refused ancestor acquisition");
        }
    }

    WindowsOriginalProfileDllAncestorsCandidate newOriginalAncestors(WindowsOriginalFileSecurityQuery candidate,
        Arena moduleArena, MemorySegment module, MemorySegment entry, MemorySegment pinEntry, MemorySegment resolveEntry) {
        requireOriginalQuery(candidate);
        requireOriginalAncestorInputs();
        if (!ancestorsAttempted || ancestors != null) {
            throw new IllegalStateException("Original profile DLL ancestor attachment is not pending");
        }
        return file.newOriginalAncestors(this, moduleArena, module, entry, pinEntry, resolveEntry);
    }

    void requireOriginalAncestors(WindowsOriginalProfileDllAncestorsCandidate candidate) {
        requireOriginalFile();
        query.completed();
        if (candidate == null || candidate != ancestors) {
            throw new IllegalStateException("Ancestor candidate is not this profile DLL security's original attachment");
        }
        // Identity only: completed negative ancestor diagnostics must remain readable.
    }

    boolean completed() { requireOriginalFile(); return query.completed(); }
    boolean descriptorPolicyAccepted() { requireOriginalFile(); return query.descriptorPolicyAccepted(); }
}
