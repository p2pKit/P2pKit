package dev.p2pkit.rpc.windows.loader;

import java.lang.foreign.Arena;
import java.lang.foreign.Linker;
import java.lang.foreign.MemorySegment;

/** Original JVM security attachment; shared query mechanics do not substitute a DLL or grant authority. */
final class WindowsOriginalJvmSecurityCandidate {
    private final Thread thread = Thread.currentThread();
    private final WindowsOriginalJvmFileCandidate file;
    private final WindowsOriginalFileSecurityQuery query;
    private boolean ancestorsAttempted;
    private WindowsOriginalJvmAncestorsCandidate ancestors;

    WindowsOriginalJvmSecurityCandidate(WindowsOriginalJvmFileCandidate file, Linker linker, Arena bootstrapArena,
                                        Arena fileArena, MemorySegment fileHandle, MemorySegment pinEntry,
                                        MemorySegment pathEntry, MemorySegment systemPathEntry, MemorySegment resolveEntry) {
        this.file = file;
        query = new WindowsOriginalFileSecurityQuery(this, linker, bootstrapArena, fileArena, fileHandle,
            pinEntry, pathEntry, systemPathEntry, resolveEntry);
    }

    void observe() { query.observe(); }
    boolean completed() { return query.completed(); }
    boolean descriptorPolicyAccepted() { return query.descriptorPolicyAccepted(); }

    void requireOriginalQuery(WindowsOriginalFileSecurityQuery candidate) {
        if (Thread.currentThread() != thread || candidate == null || candidate != query) {
            throw new IllegalStateException("Security query is not this JVM facade's original retained attachment");
        }
        if (file == null) {
            throw new IllegalStateException("Original JVM security requires its original platform thread");
        }
        // No query.completed(): the core invokes this exact guard before and during its own observation.
        file.requireOriginalSecurity(this);
    }

    WindowsOriginalJvmAncestorsCandidate inspectAncestors() {
        query.completed();
        if (ancestorsAttempted) throw new IllegalStateException("Original JVM ancestors candidate was already attempted");
        ancestorsAttempted = true;
        ancestors = query.newJvmAncestors(this);
        ancestors.observe();
        return ancestors;
    }

    WindowsOriginalJvmAncestorsCandidate newOriginalAncestors(WindowsOriginalFileSecurityQuery candidate,
        Arena moduleArena, MemorySegment module, MemorySegment entry, MemorySegment pinEntry, MemorySegment resolveEntry) {
        requireOriginalQuery(candidate);
        return file.newOriginalAncestors(this, moduleArena, module, entry, pinEntry, resolveEntry);
    }

    void requireOriginalAncestors(WindowsOriginalJvmAncestorsCandidate candidate) {
        query.completed();
        if (candidate == null || ancestors != candidate) {
            throw new IllegalStateException("Ancestors candidate is not the original security attachment");
        }
    }
}
