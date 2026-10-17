package dev.p2pkit.rpc.windows.loader;

import java.lang.foreign.Arena;
import java.lang.foreign.Linker;
import java.lang.foreign.MemorySegment;

/** Original JVM hash-only attachment; neither a DLL snapshot nor startup/runtime authority. */
final class WindowsOriginalJvmBytesCandidate {
    private final Thread thread = Thread.currentThread();
    private final WindowsOriginalJvmFileCandidate file;
    private final WindowsOriginalFileBytesLease core;

    WindowsOriginalJvmBytesCandidate(WindowsOriginalJvmFileCandidate file, Linker linker,
        Arena bootstrapArena, Arena fileArena, MemorySegment fileHandle, MemorySegment readEntry,
        MemorySegment informationEntry, long[] originalMetadata) {
        this.file = file;
        core = new WindowsOriginalFileBytesLease(this, linker, bootstrapArena, fileArena, fileHandle, readEntry, informationEntry, originalMetadata);
    }

    void observe() { core.observe(); }
    boolean completed() { return core.completed(); }
    long byteCount() { return core.byteCount(); }
    byte[] sha256() { return core.sha256(); }

    void requireOriginalCore(WindowsOriginalFileBytesLease candidate) {
        if (Thread.currentThread() != thread || candidate == null || candidate != core || file == null) {
            throw new IllegalStateException("Original JVM bytes require their original platform thread/file");
        }
        file.requireOriginalBytes(this); // Identity only: the core also uses this guard before completion.
    }
}
