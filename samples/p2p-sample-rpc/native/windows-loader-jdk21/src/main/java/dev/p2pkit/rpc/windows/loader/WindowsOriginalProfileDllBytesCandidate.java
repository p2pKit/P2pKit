package dev.p2pkit.rpc.windows.loader;

import java.lang.foreign.Arena;
import java.lang.foreign.Linker;
import java.lang.foreign.MemorySegment;

/** Original DLL bytes and digest are copied data, not package, mapped-image or loading authority. */
final class WindowsOriginalProfileDllBytesCandidate {
    static final class Failure extends RuntimeException {
        private static final long serialVersionUID = 1L;
        final transient WindowsOriginalProfileDllBytesCandidate retainedCandidate;
        Throwable operationFailure;

        private Failure(WindowsOriginalProfileDllBytesCandidate candidate) {
            super("Original profile DLL byte observation failed with ownership retained", null, false, false);
            retainedCandidate = candidate;
        }
    }

    private final Thread thread = Thread.currentThread();
    private final WindowsOriginalProfileDllFileCandidate file;
    private final Failure failure = new Failure(this);
    private final WindowsOriginalFileBytesLease core;
    private boolean attempted;
    private boolean failed;

    WindowsOriginalProfileDllBytesCandidate(WindowsOriginalProfileDllFileCandidate file, Linker linker,
        Arena bootstrapArena, Arena fileArena, MemorySegment fileHandle, MemorySegment readEntry,
        MemorySegment informationEntry, long[] originalMetadata) {
        this.file = file;
        core = WindowsOriginalFileBytesLease.forProfileDll(this, linker, bootstrapArena, fileArena, fileHandle, readEntry, informationEntry, originalMetadata);
    }

    void observe() {
        requireOriginalFile();
        if (attempted) throw new IllegalStateException("Original profile DLL bytes were already attempted");
        attempted = true;
        try {
            requireOriginalNativeInputs();
            core.observe();
        } catch (Throwable caught) {
            failure.operationFailure = caught;
            failed = true;
            throw failure;
        }
    }

    private void requireOriginalFile() {
        if (Thread.currentThread() != thread || file == null) {
            throw new IllegalStateException("Original profile DLL bytes require their original platform thread/file");
        }
        file.requireOriginalBytes(this);
        if (failed) throw failure;
    }

    void requireOriginalCore(WindowsOriginalFileBytesLease candidate) {
        if (candidate == null || candidate != core) {
            throw new IllegalStateException("Byte core is not this profile DLL facade's original attachment");
        }
        requireOriginalFile();
    }

    void requireOriginalNativeInputs() {
        requireOriginalFile();
        file.requireOriginalByteInputs();
    }

    boolean completed() { requireOriginalFile(); return core.completed(); }
    long byteCount() { requireOriginalFile(); return core.byteCount(); }
    byte[] sha256() { requireOriginalFile(); return core.sha256(); }
    byte[] snapshot() { requireOriginalFile(); return core.snapshot(this); }
}
