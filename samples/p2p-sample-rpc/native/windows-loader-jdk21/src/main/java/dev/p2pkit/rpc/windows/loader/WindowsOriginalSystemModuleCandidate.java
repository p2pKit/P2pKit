package dev.p2pkit.rpc.windows.loader;

import java.lang.foreign.Arena;
import java.lang.foreign.Linker;
import java.lang.foreign.MemorySegment;

/**
 * One fixed already-loaded module observation and its independent original disk-file chain.
 * The four concrete shared cores are owned here, never borrowed from a JVM/profile facade. Positive
 * hardlink counts are stable system-file metadata, NOT admitted servicing or mapped-section identity.
 * This object cannot load a module, mint a callable address or admit an OS/runtime/package authority.
 */
final class WindowsOriginalSystemModuleCandidate {
    static final class Failure extends RuntimeException {
        private static final long serialVersionUID = 1L;
        final transient WindowsOriginalSystemModuleCandidate retainedCandidate;
        Throwable operationFailure;

        private Failure(WindowsOriginalSystemModuleCandidate candidate) {
            super("Original system module observation failed with ownership retained", null, false, false);
            retainedCandidate = candidate;
        }
    }

    private final Thread thread = Thread.currentThread();
    private final WindowsOriginalSystemModulesCandidate collection;
    private final int slot;
    private final String name;
    private final Failure failure = new Failure(this);
    private long rawModule;
    private MemorySegment module;
    private char[] originalPath;
    private boolean pinned;
    private boolean failed;
    private boolean fileAttempted;
    private boolean securityAttempted;
    private boolean ancestorsAttempted;
    private boolean bytesAttempted;
    private boolean inputAttempted;
    private boolean fileObserved;
    private boolean securityObserved;
    private boolean ancestorsObserved;
    private boolean bytesObserved;
    private boolean leafPolicyRefused;
    private boolean ancestorPolicyRefused;
    private WindowsOriginalFileLease file;
    private WindowsOriginalFileSecurityQuery security;
    private WindowsOriginalFileAncestorsLease ancestors;
    private WindowsOriginalFileBytesLease bytes;
    private WindowsSystemExportPlan.Input exportInput;

    WindowsOriginalSystemModuleCandidate(WindowsOriginalSystemModulesCandidate collection, int slot) {
        this.collection = collection;
        this.slot = slot;
        name = WindowsOriginalSystemModulesCandidate.fixedName(slot);
    }

    private void requireOriginalCollection() {
        if (Thread.currentThread() != thread || collection == null ||
            !name.equals(WindowsOriginalSystemModulesCandidate.fixedName(slot))) {
            throw new IllegalStateException("System module requires its original thread and fixed slot");
        }
        collection.requireOriginalModule(this, slot);
        if (failed) throw failure;
    }

    void requireOriginalNativeInputs() {
        requireOriginalCollection();
        collection.requireOriginalNativeInputs();
        if (leafPolicyRefused || ancestorPolicyRefused) {
            throw new IllegalStateException("Original system file policy refused subsequent native inputs");
        }
    }

    void retainRawModule(long raw) {
        requireOriginalNativeInputs();
        if (rawModule != 0 || pinned || fileAttempted) throw new IllegalStateException("Original module PIN was already retained");
        rawModule = raw; // Original PIN bits retained before constructing any allocating address wrapper.
    }

    void finishPin(Arena originalArena, char[] path) {
        requireOriginalNativeInputs();
        if (pinned || rawModule <= 0 || (rawModule & 65_535) != 0 ||
            rawModule > Long.MAX_VALUE - 65_536 || originalArena == null ||
            !collection.isOriginalModuleArena(originalArena) || path == null || path.length < 11 ||
            path.length > 1024 || path[path.length - 1] != 0) {
            throw new IllegalStateException("Original system module PIN/path is incomplete");
        }
        originalPath = path.clone();
        module = MemorySegment.ofAddress(rawModule).reinterpret(originalArena, null);
        pinned = true;
    }

    private void requirePinned() {
        requireOriginalCollection();
        if (!pinned || originalPath == null || module == null || !module.isNative() || module.byteSize() != 0 ||
            module.address() != rawModule || !module.scope().isAlive() || !module.isAccessibleBy(thread) ||
            !collection.isOriginalModuleScope(module)) {
            throw new IllegalStateException("Original system module has no retained completed PIN observation");
        }
    }

    long originalModuleBits() { requirePinned(); return rawModule; }

    private WindowsOriginalSystemModulesCandidate.Failure fail(Throwable caught) {
        if (!failed) {
            failure.operationFailure = caught;
            failed = true;
        }
        return collection.failOriginalModule(this, slot, failure);
    }

    void observeFile() {
        requirePinned();
        requireOriginalNativeInputs();
        if (fileAttempted) throw new IllegalStateException("Original system file was already attempted");
        fileAttempted = true;
        try {
            file = WindowsOriginalFileLease.forSystemModule(this);
            file.observe();
            file.completed();
            fileObserved = true;
        } catch (Throwable caught) { throw fail(caught); }
    }

    void observeSecurity() {
        requireFileCompleted();
        requireOriginalNativeInputs();
        if (securityAttempted) throw new IllegalStateException("Original system security was already attempted");
        securityAttempted = true;
        try {
            security = file.newSystemModuleSecurity(this);
            security.observe();
            leafPolicyRefused = !security.descriptorPolicyAccepted();
            securityObserved = true;
        } catch (Throwable caught) { throw fail(caught); }
    }

    void observeAncestors() {
        requireOriginalAncestorInputs();
        if (ancestorsAttempted) throw new IllegalStateException("Original system ancestors were already attempted");
        ancestorsAttempted = true;
        try {
            ancestors = security.newSystemModuleAncestors(this);
            ancestors.observe();
            ancestorPolicyRefused = !ancestors.descriptorPoliciesAccepted();
            ancestorsObserved = true;
        } catch (Throwable caught) { throw fail(caught); }
    }

    void observeBytes() {
        requireOriginalByteInputs();
        if (bytesAttempted) throw new IllegalStateException("Original system bytes were already attempted");
        bytesAttempted = true;
        try {
            bytes = file.newSystemModuleBytes(this);
            bytes.observe();
            bytes.completed();
            bytesObserved = true;
        } catch (Throwable caught) { throw fail(caught); }
    }

    WindowsSystemExportPlan.Input originalExportInput() {
        requireOriginalByteInputs();
        if (!bytesObserved || bytes == null || inputAttempted) {
            throw new IllegalStateException("Original system export input is unavailable or already consumed");
        }
        inputAttempted = true;
        try {
            exportInput = bytes.newSystemExportInput(this);
            return exportInput;
        } catch (Throwable caught) { throw fail(caught); }
    }

    void requireOriginalFileLease(WindowsOriginalFileLease candidate) {
        requirePinned();
        if (!fileAttempted || candidate == null || candidate != file) {
            throw new IllegalStateException("System file core is not its original retained attachment");
        }
        // Identity only; this core invokes us while observing. Never consult its own completion here.
    }

    private void requireFileCompleted() {
        requirePinned();
        if (!fileObserved || file == null) throw new IllegalStateException("Original system file is incomplete");
        file.completed();
    }

    void requireOriginalQuery(WindowsOriginalFileSecurityQuery candidate) {
        requireFileCompleted();
        if (!securityAttempted || candidate == null || candidate != security) {
            throw new IllegalStateException("System query core is not its original retained attachment");
        }
    }

    void requireOriginalQueryProvider(WindowsOriginalFileSecurityQuery candidate, long originalQueryModule) {
        requireOriginalQuery(candidate);
        requireOriginalNativeInputs();
        collection.requireOriginalQueryProvider(this, slot, originalQueryModule);
    }

    void requireOriginalAncestorInputs() {
        requireFileCompleted();
        requireOriginalNativeInputs();
        if (!securityObserved || security == null || !security.descriptorPolicyAccepted()) {
            throw new IllegalStateException("System ancestors require original accepted leaf policy");
        }
    }

    WindowsOriginalFileAncestorsLease newOriginalAncestors(WindowsOriginalFileSecurityQuery candidate,
        Arena moduleArena, MemorySegment queryModule, MemorySegment queryEntry, MemorySegment pinEntry,
        MemorySegment resolveEntry) {
        requireOriginalQuery(candidate);
        requireOriginalAncestorInputs();
        return file.newSystemModuleAncestors(this, candidate, moduleArena, queryModule, queryEntry, pinEntry, resolveEntry);
    }

    void requireOriginalAncestors(WindowsOriginalFileAncestorsLease candidate) {
        requireFileCompleted();
        if (!ancestorsAttempted || candidate == null || candidate != ancestors || security == null || !securityObserved) {
            throw new IllegalStateException("System ancestor core is not its original retained attachment");
        }
        security.completed(); // Preceding stage only; negative ancestor completion stays Java-readable.
    }

    void requireOriginalByteInputs() {
        requireOriginalAncestorInputs();
        if (!ancestorsObserved || ancestors == null || !ancestors.descriptorPoliciesAccepted()) {
            throw new IllegalStateException("System bytes require original accepted ancestor policy");
        }
    }

    void requireOriginalBytes(WindowsOriginalFileBytesLease candidate) {
        requireFileCompleted();
        if (!bytesAttempted || candidate == null || candidate != bytes || ancestors == null || !ancestorsObserved) {
            throw new IllegalStateException("System byte core is not its original retained attachment");
        }
        security.completed();
        ancestors.completed();
    }

    Linker originalLinker() {
        requireOriginalNativeInputs();
        return collection.originalLinker(this, slot);
    }
    Arena originalBootstrapArena() {
        requireOriginalNativeInputs();
        return collection.originalBootstrapArena(this, slot);
    }
    MemorySegment originalFileEntry(int index) {
        requireOriginalNativeInputs();
        return collection.originalFileEntry(this, slot, index);
    }
    char[] originalPathSnapshot() {
        requirePinned();
        requireOriginalNativeInputs();
        return originalPath.clone();
    }
    MemorySegment originalSecurityEntry(WindowsOriginalFileLease candidate, int index) {
        requireOriginalFileLease(candidate);
        requireOriginalNativeInputs();
        return collection.originalSecurityEntry(this, slot, index);
    }
    MemorySegment originalAncestorsEntry(WindowsOriginalFileLease candidate, int index) {
        requireOriginalFileLease(candidate);
        requireOriginalAncestorInputs();
        return collection.originalAncestorsEntry(this, slot, index);
    }
    MemorySegment originalReadEntry(WindowsOriginalFileLease candidate) {
        requireOriginalFileLease(candidate);
        requireOriginalByteInputs();
        return collection.originalReadEntry(this, slot);
    }

    String name() { requireOriginalCollection(); return name; }
    boolean pinned() { requireOriginalCollection(); if (pinned) requirePinned(); return pinned; }
    boolean fileObserved() { requireOriginalCollection(); if (fileObserved) requireFileCompleted(); return fileObserved; }
    boolean securityObserved() { requireOriginalCollection(); if (securityObserved) security.completed(); return securityObserved; }
    boolean ancestorsObserved() { requireOriginalCollection(); if (ancestorsObserved) ancestors.completed(); return ancestorsObserved; }
    boolean bytesObserved() { requireOriginalCollection(); if (bytesObserved) bytes.completed(); return bytesObserved; }
    long byteCount() { requireFileCompleted(); return file.systemByteCount(this); }
    long linkCount() { requireFileCompleted(); return file.systemLinkCount(this); }
    boolean descriptorPolicyAccepted() {
        requireOriginalCollection();
        if (!securityObserved) throw new IllegalStateException("Original system leaf policy was not observed");
        return security.descriptorPolicyAccepted();
    }
    boolean descriptorPoliciesAccepted() {
        requireOriginalCollection();
        if (!ancestorsObserved) throw new IllegalStateException("Original system ancestor policy was not observed");
        return ancestors.descriptorPoliciesAccepted();
    }
    byte[] sha256() {
        requireOriginalCollection();
        if (!bytesObserved) throw new IllegalStateException("Original system bytes were not observed");
        return bytes.sha256();
    }
}
