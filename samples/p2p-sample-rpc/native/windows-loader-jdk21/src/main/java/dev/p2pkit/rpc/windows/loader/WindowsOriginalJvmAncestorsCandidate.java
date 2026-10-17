package dev.p2pkit.rpc.windows.loader;

import java.lang.foreign.Arena;
import java.lang.foreign.Linker;
import java.lang.foreign.MemorySegment;

/** Original JVM ancestor attachment; shared mechanics neither replace its owner nor grant authority. */
final class WindowsOriginalJvmAncestorsCandidate {
    private final Thread thread = Thread.currentThread();
    private final WindowsOriginalJvmSecurityCandidate security;
    private final WindowsOriginalFileAncestorsLease core;

    WindowsOriginalJvmAncestorsCandidate(WindowsOriginalJvmSecurityCandidate security, Linker linker,
        Arena bootstrapArena, Arena moduleArena, MemorySegment module, MemorySegment queryEntry,
        MemorySegment pinEntry, MemorySegment resolveEntry, MemorySegment createEntry,
        MemorySegment informationEntry, MemorySegment finalPathEntry, MemorySegment volumeEntry,
        MemorySegment driveEntry, Arena originalFileArena, MemorySegment originalFileHandle,
        char[] originalPath, int pathLength, long[] originalFile) {
        this.security = security;
        core = new WindowsOriginalFileAncestorsLease(this, linker, bootstrapArena, moduleArena, module,
            queryEntry, pinEntry, resolveEntry,
            createEntry, informationEntry, finalPathEntry, volumeEntry, driveEntry, originalFileArena,
            originalFileHandle, originalPath, pathLength, originalFile);
    }

    void observe() { core.observe(); }
    boolean completed() { return core.completed(); }
    int ancestorCount() { return core.ancestorCount(); }
    boolean descriptorPoliciesAccepted() { return core.descriptorPoliciesAccepted(); }

    void requireOriginalCore(WindowsOriginalFileAncestorsLease candidate) {
        if (Thread.currentThread() != thread || candidate == null || candidate != core || security == null) {
            throw new IllegalStateException("Original ancestor observation requires its original platform thread");
        }
        // This identity guard must work during observation, without recursively requiring core completion.
        security.requireOriginalAncestors(this);
    }
}
