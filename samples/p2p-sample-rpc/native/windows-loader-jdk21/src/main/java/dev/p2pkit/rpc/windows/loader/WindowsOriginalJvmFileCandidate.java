package dev.p2pkit.rpc.windows.loader;

import java.lang.foreign.Arena;
import java.lang.foreign.Linker;
import java.lang.foreign.MemorySegment;

/**
 * Original JVM file attachment, retaining one concrete native lease and its original diagnostic children.
 * This facade preserves the original runtime relationship; it cannot be substituted with a DLL pathname
 * or converted into installation/startup authority. Core and failure ownership exist before observation.
 */
final class WindowsOriginalJvmFileCandidate {
    private final Thread thread = Thread.currentThread();
    private final WindowsOriginalJvmCandidate runtime;
    // Fixed constructor inputs from the original runtime, not a new native-entry selection API.
    final Linker originalLinker;
    final Arena originalBootstrapArena;
    final MemorySegment originalCreateEntry;
    final MemorySegment originalInformationEntry;
    final MemorySegment originalFinalPathEntry;
    final char[] originalPath;
    final int originalPathLength;
    private final WindowsOriginalFileLease lease;
    private boolean securityAttempted;
    private WindowsOriginalJvmSecurityCandidate security;
    private boolean bytesAttempted;
    private WindowsOriginalJvmBytesCandidate bytes;

    WindowsOriginalJvmFileCandidate(WindowsOriginalJvmCandidate runtime, Linker linker, Arena bootstrapArena,
                                   MemorySegment createEntry, MemorySegment informationEntry, MemorySegment finalPathEntry,
                                   char[] sourcePath, int sourceLength) {
        this.runtime = runtime;
        originalLinker = linker;
        originalBootstrapArena = bootstrapArena;
        originalCreateEntry = createEntry;
        originalInformationEntry = informationEntry;
        originalFinalPathEntry = finalPathEntry;
        originalPath = sourcePath == null ? null : sourcePath.clone();
        originalPathLength = sourceLength;
        lease = new WindowsOriginalFileLease(this);
    }

    void observe() { lease.observe(); }
    boolean completed() { return lease.completed(); }
    boolean leaseHeld() { return lease.leaseHeld(); }

    void requireOriginalLease(WindowsOriginalFileLease candidate) {
        if (Thread.currentThread() != thread || candidate == null || candidate != lease) {
            throw new IllegalStateException("File lease is not this JVM facade's original retained attachment");
        }
        if (runtime == null) {
            throw new IllegalStateException("Original JVM file requires its original platform thread");
        }
        // Do NOT call lease.completed(): the core uses this guard before checking its own completion.
        runtime.requireOriginalFile(this);
    }

    private void requireCompleted() { lease.completed(); }

    WindowsOriginalJvmBytesCandidate inspectBytes() {
        requireCompleted();
        if (bytesAttempted) throw new IllegalStateException("Original JVM file bytes were already attempted");
        bytesAttempted = true;
        bytes = lease.newJvmBytes(this);
        bytes.observe();
        return bytes;
    }

    void requireOriginalBytes(WindowsOriginalJvmBytesCandidate candidate) {
        requireCompleted();
        if (candidate == null || bytes != candidate) {
            throw new IllegalStateException("Byte candidate is not this file's original retained attachment");
        }
    }

    WindowsOriginalJvmSecurityCandidate inspectSecurity() {
        requireCompleted();
        if (securityAttempted) throw new IllegalStateException("Original JVM file security was already attempted");
        securityAttempted = true;
        security = lease.newJvmSecurity(this);
        security.observe();
        return security;
    }

    void requireOriginalSecurity(WindowsOriginalJvmSecurityCandidate candidate) {
        requireCompleted();
        if (candidate == null || security != candidate) {
            throw new IllegalStateException("Security candidate is not this JVM file's original retained attachment");
        }
    }

    WindowsOriginalJvmAncestorsCandidate newOriginalAncestors(WindowsOriginalJvmSecurityCandidate candidate,
        Arena moduleArena, MemorySegment module, MemorySegment queryEntry, MemorySegment pinEntry,
        MemorySegment resolveEntry) {
        requireOriginalSecurity(candidate);
        return lease.newJvmAncestors(this, candidate, moduleArena, module, queryEntry, pinEntry, resolveEntry);
    }

    MemorySegment originalReadEntry(WindowsOriginalFileLease candidate) {
        requireOriginalLease(candidate);
        return runtime.originalFileReadEntry(this);
    }

    MemorySegment originalSecurityEntry(WindowsOriginalFileLease candidate, int index) {
        requireOriginalLease(candidate);
        return runtime.originalFileSecurityEntry(this, index);
    }

    MemorySegment originalAncestorsEntry(WindowsOriginalFileLease candidate, int index) {
        requireOriginalLease(candidate);
        return runtime.originalFileAncestorsEntry(this, index);
    }
}
