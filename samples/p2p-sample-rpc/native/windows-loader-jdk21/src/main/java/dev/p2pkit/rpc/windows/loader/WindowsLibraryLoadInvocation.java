package dev.p2pkit.rpc.windows.loader;

import java.lang.foreign.Arena;
import java.lang.foreign.FunctionDescriptor;
import java.lang.foreign.Linker;
import java.lang.foreign.MemoryLayout;
import java.lang.foreign.MemorySegment;
import java.lang.foreign.ValueLayout;
import java.lang.invoke.MethodHandle;
import java.nio.ByteOrder;

/**
 * Fixed LoadLibraryExW mechanics; the public installed provider remains unavailable.
 * Installed preparation requires its concrete completed input chain; the separate development route
 * cannot acquire that relationship. Neither route itself supplies installed/native qualification.
 * Uses only its original bootstrap/JVM fixed entries. A prior fixed-name PIN probe must observe
 * definite absence; this does not establish startup, installed file or mapped-backing authority.
 * There is no fallback lookup/load, environment search, search-path mutation, FreeLibrary or provider publication.
 */
final class WindowsLibraryLoadInvocation {
    static final int MAXIMUM_PATH_CHARS = WindowsProfileDllPath.MAXIMUM_PATH_CHARS;
    private static final String PROFILE_NAME = "p2pkit-windows-profile.dll";
    private static final MemoryLayout NAME = MemoryLayout.sequenceLayout(PROFILE_NAME.length() + 1, ValueLayout.JAVA_SHORT);
    static final int SEARCH_SYSTEM32 = 0x00000800;
    static final MemoryLayout PATH = MemoryLayout.sequenceLayout(MAXIMUM_PATH_CHARS, ValueLayout.JAVA_SHORT);
    // On the guarded Windows-x64 ABI both an opaque HMODULE pointer and this 64-bit integer return
    // occupy RAX. The primitive carrier preserves returned bits before FFM can allocate a segment view.
    static final FunctionDescriptor DESCRIPTOR = FunctionDescriptor.of(ValueLayout.JAVA_LONG,
        ValueLayout.ADDRESS.withTargetLayout(PATH), ValueLayout.ADDRESS, ValueLayout.JAVA_INT);

    static final class Result {
        final WindowsLibraryLoadInvocation retainedInvocation;

        private Result(WindowsLibraryLoadInvocation invocation) { retainedInvocation = invocation; }

        /** Conditional kernel32-development comparison, using this bootstrap's exact prior resolver. */
        WindowsLoadedProfileImageVerification verifyImage(WindowsSystemBootstrapCandidate bootstrap,
                                                         WindowsPackagedVerifier plan,
                                                         WindowsSystemImportResolution imports) {
            if (imports == null) throw new IllegalArgumentException("Missing original system import resolution");
            return retainedInvocation.verifyImage(bootstrap, plan, imports);
        }

        /** Owned comparison requires that the original plan already bound its original system cohort. */
        WindowsLoadedProfileImageVerification verifyImage(WindowsSystemBootstrapCandidate bootstrap,
                                                         WindowsPackagedVerifier plan) {
            return retainedInvocation.verifyImage(bootstrap, plan, null);
        }

        void requireOriginalVerification(WindowsLoadedProfileImageVerification candidate) {
            module();
            if (candidate == null || candidate != retainedInvocation.imageVerification) {
                throw new IllegalStateException("Mapped verification is not the original load attachment");
            }
        }

        /** Original zero-length HMODULE view only; mapped identity/protections/imports remain unverified. */
        MemorySegment module() {
            retainedInvocation.requireThread();
            if (!retainedInvocation.succeeded) {
                throw new IllegalStateException("Windows library load is not successful");
            }
            retainedInvocation.requireOriginalScope();
            return retainedInvocation.module;
        }
    }

    static final class Failure extends RuntimeException {
        private static final long serialVersionUID = 1L;
        final transient WindowsLibraryLoadInvocation retainedInvocation;
        Throwable preparationFailure;
        Throwable invocationFailure;
        Throwable probeFailure;
        Throwable nameClearFailure;
        Throwable probeClearFailure;
        Throwable readbackFailure;
        Throwable pathClearFailure;
        Throwable stateClearFailure;
        Throwable arenaCloseFailure;

        Failure(WindowsLibraryLoadInvocation invocation) {
            super("Windows library load failed with original ownership retained", null, false, false);
            retainedInvocation = invocation;
        }

        boolean retirementFailed() {
            return pathClearFailure != null || stateClearFailure != null || arenaCloseFailure != null ||
                nameClearFailure != null || probeClearFailure != null;
        }
    }

    private static WindowsLibraryLoadInvocation processOwner;
    private WindowsInstalledProfileCandidate installedOwner;
    private final Thread thread = Thread.currentThread();
    final Object installationOwner;
    final WindowsOriginalJvmCandidate runtimeOwner;
    private final WindowsSystemBootstrapCandidate bootstrap;
    private final MemorySegment pinEntry;
    final Object fileOwner;
    private final MemorySegment entry;
    private final Arena originalArena;
    private final String path;
    private final Failure failure = new Failure(this);
    private final Result result = new Result(this);
    private Arena frameArena;
    private MemorySegment pathBuffer;
    private MemorySegment pathView;
    private MemorySegment capturedState;
    private long errorOffset;
    private MethodHandle call;
    private MethodHandle pinCall;
    private MemorySegment nameBuffer;
    private MemorySegment nameView;
    private MemorySegment probeModuleBuffer;
    private int probeStatus;
    private int probeError;
    private long rawPreexistingModule;
    private boolean probeAttempted;
    private boolean probeReturned;
    private boolean probeObservationUnconfirmed;
    private MemorySegment module;
    private long rawModule;
    private boolean nativeReturned;
    private boolean nativeReturnUnconfirmed;
    private int lastError;
    private boolean errorObserved;
    private boolean attempted;
    private boolean active;
    private boolean retired;
    private boolean succeeded;
    private boolean imageVerificationAttempted;
    private WindowsLoadedProfileImageVerification imageVerification;
    private Throwable imageAttachmentFailure;

    private WindowsLibraryLoadInvocation(WindowsSystemBootstrapCandidate bootstrap, Object installationOwner,
                                        WindowsOriginalJvmCandidate runtimeOwner, Object fileOwner,
                                        MemorySegment entry, MemorySegment pinEntry, Arena originalArena, String path) {
        this.bootstrap = bootstrap;
        this.pinEntry = pinEntry;
        this.installationOwner = installationOwner;
        this.runtimeOwner = runtimeOwner;
        this.fileOwner = fileOwner;
        this.entry = entry;
        this.originalArena = originalArena;
        this.path = path;
    }

    private WindowsLoadedProfileImageVerification verifyImage(WindowsSystemBootstrapCandidate bootstrap,
                                                              WindowsPackagedVerifier plan,
                                                              WindowsSystemImportResolution imports) {
        result.module();
        if (installedOwner != null) installedOwner.requireOriginalPackagedPlan(plan);
        if (imageVerificationAttempted) throw new IllegalStateException("Mapped image verification was already attempted");
        imageVerificationAttempted = true;
        try {
            imageVerification = new WindowsLoadedProfileImageVerification(result, bootstrap, plan, imports);
        } catch (Throwable caught) {
            imageAttachmentFailure = caught;
            throw caught;
        }
        // This process-rooted original load retains the entire new child BEFORE its first lookup/read.
        imageVerification.verify();
        return imageVerification;
    }

    void requireOriginalBinding(Result candidate, MemorySegment expectedEntry, Arena expectedArena,
                                WindowsOriginalJvmCandidate expectedJvm) {
        requireThread();
        if (candidate != result || expectedEntry != entry || expectedArena != originalArena ||
            expectedJvm == null || expectedJvm != runtimeOwner) {
            throw new IllegalStateException("Load is not bound to this original bootstrap and JVM");
        }
        result.module();
        expectedJvm.completed();
    }

    void requireOriginalFile(WindowsOriginalProfileDllFileCandidate expectedFile, String expectedPath) {
        requireThread();
        if (expectedFile == null || fileOwner != expectedFile || !path.equals(expectedPath)) {
            throw new IllegalStateException("Load is not bound to the original profile file/path");
        }
        result.module();
    }

    static WindowsLibraryLoadInvocation prepareDevelopment(WindowsSystemBootstrapCandidate bootstrap, Object installationOwner,
                                                WindowsOriginalJvmCandidate runtimeOwner, Object fileOwner, String path) {
        if (installationOwner instanceof WindowsOriginalInstallationCandidate || installationOwner instanceof WindowsInstalledProfileCandidate ||
            fileOwner instanceof WindowsOriginalProfileDllFileCandidate file && file.hasInstalledOwner()) {
            throw new IllegalArgumentException("Installed ownership cannot enter the development load route");
        }
        return prepare(bootstrap, installationOwner, runtimeOwner, fileOwner, path, null);
    }

    static WindowsLibraryLoadInvocation prepareInstalled(WindowsInstalledProfileCandidate owner) {
        if (owner == null) throw new IllegalArgumentException("Missing concrete installed load owner");
        owner.requirePreparedInputs();
        return prepare(owner.originalBootstrap(), owner.originalInstallation(), owner.originalJvm(),
            owner.originalProfile(), owner.fixedProfilePath(), owner);
    }

    private static WindowsLibraryLoadInvocation prepare(WindowsSystemBootstrapCandidate bootstrap, Object installationOwner,
                                                WindowsOriginalJvmCandidate runtimeOwner, Object fileOwner, String path,
                                                WindowsInstalledProfileCandidate installed) {
        WindowsLoaderRuntime.requireDiagnosticRuntime();
        if (WindowsLibraryLoadInvocation.class.getModule() != WindowsLoaderRuntime.class.getModule() ||
            Thread.currentThread().isVirtual()) {
            throw new IllegalStateException("Windows library load requires its original boot module/platform thread");
        }
        validatePath(path);
        if (bootstrap == null || installationOwner == null || runtimeOwner == null || fileOwner == null) {
            throw new IllegalArgumentException("Missing original Windows load owners");
        }
        Arena originalArena = bootstrap.originalLibraryLoadArena(runtimeOwner);
        MemorySegment entry = bootstrap.originalLibraryLoadEntry(runtimeOwner, 1);
        MemorySegment pinEntry = bootstrap.originalLibraryLoadEntry(runtimeOwner, 0);
        if (entry == null || pinEntry == null || !pinEntry.isNative() || pinEntry.address() <= 0 ||
            !pinEntry.scope().equals(originalArena.scope()) || !pinEntry.isAccessibleBy(Thread.currentThread()) ||
            originalArena == null || !entry.isNative() || entry.address() <= 0 ||
            !entry.scope().equals(originalArena.scope()) || originalArena.scope().equals(Arena.global().scope()) ||
            !originalArena.scope().isAlive() || !entry.isAccessibleBy(Thread.currentThread())) {
            throw new IllegalArgumentException("Missing original scoped Windows load entry/owners");
        }
        Linker linker = Linker.nativeLinker();
        // Check the actual boot-runtime implementation and C ABI, not spoofable os.name/os.arch properties.
        if (linker.getClass().getModule() != Object.class.getModule() || linker.getClass().getClassLoader() != null ||
            !linker.getClass().getName().equals("jdk.internal.foreign.abi.x64.windows.Windowsx64Linker") ||
            ValueLayout.ADDRESS.byteSize() != 8 || ByteOrder.nativeOrder() != ByteOrder.LITTLE_ENDIAN ||
            ValueLayout.JAVA_INT.byteSize() != 4 || PATH.byteSize() != 520) {
            throw new IllegalStateException("Windows library load requires the actual Windows x64 linker");
        }
        WindowsLibraryLoadInvocation invocation = new WindowsLibraryLoadInvocation(
            bootstrap, installationOwner, runtimeOwner, fileOwner, entry, pinEntry, originalArena, path);
        if (installed != null) {
            invocation.installedOwner = installed;
            installed.attachOriginalLoad(invocation); // Exact owner/failure precedes private native frame preparation.
            installed.requireOriginalLoad(invocation);
        }
        try {
            MemoryLayout state = Linker.Option.captureStateLayout();
            MemoryLayout error = state.select(MemoryLayout.PathElement.groupElement("GetLastError"));
            if (!(error instanceof ValueLayout.OfInt) || error.byteSize() != 4 || error.byteAlignment() != 4 ||
                state.byteSize() < 4 || state.byteSize() > 64) {
                throw new IllegalStateException("Unsupported Windows captured error layout");
            }
            long offset = state.byteOffset(MemoryLayout.PathElement.groupElement("GetLastError"));
            if (offset < 0 || offset % 4 != 0 || offset > state.byteSize() - 4) {
                throw new IllegalStateException("Invalid Windows captured error offset");
            }
            MethodHandle handle = linker.downcallHandle(entry, DESCRIPTOR,
                Linker.Option.captureCallState("GetLastError"));
            FunctionDescriptor pinDescriptor = FunctionDescriptor.of(ValueLayout.JAVA_INT, ValueLayout.JAVA_INT,
                ValueLayout.ADDRESS.withTargetLayout(NAME), ValueLayout.ADDRESS.withTargetLayout(ValueLayout.JAVA_LONG));
            MethodHandle pin = linker.downcallHandle(pinEntry, pinDescriptor,
                Linker.Option.captureCallState("GetLastError"));
            invocation.prepareFrame(handle, pin, state, offset);
            return invocation;
        } catch (Throwable caught) {
            invocation.failure.preparationFailure = caught;
            try { invocation.retireFrame(); } catch (Failure ignored) { /* Keep independent failure slots. */ }
            throw invocation.failure;
        }
    }

    /** Private frame mechanics also exercised reflectively by inert tests; no production validation entry exists. */
    private void prepareFrame(MethodHandle handle, MethodHandle pin, MemoryLayout state, long offset) {
        call = handle;
        pinCall = pin;
        errorOffset = offset;
        frameArena = Arena.ofConfined();
        pathBuffer = frameArena.allocate(PATH);
        capturedState = frameArena.allocate(state);
        nameBuffer = frameArena.allocate(NAME);
        probeModuleBuffer = frameArena.allocate(ValueLayout.JAVA_LONG);
        long first = pathBuffer.address();
        long second = capturedState.address();
        if (first <= 0 || first > Long.MAX_VALUE - PATH.byteSize() || second <= 0 ||
            second > Long.MAX_VALUE - state.byteSize() || (first & 1) != 0 || (second & 3) != 0 ||
            (first < second + state.byteSize() && second < first + PATH.byteSize())) {
            throw new IllegalStateException("Invalid or overlapping Windows library call buffers");
        }
        MemorySegment[] buffers = {pathBuffer, capturedState, nameBuffer, probeModuleBuffer};
        for (int index = 0; index < buffers.length; index++) {
            MemorySegment buffer = buffers[index];
            long address = buffer.address();
            if (address <= 0 || address > Long.MAX_VALUE - buffer.byteSize() ||
                (address & (index == 0 || index == 2 ? 1 : index == 1 ? 3 : 7)) != 0) {
                throw new IllegalStateException("Invalid fixed-name probe buffer");
            }
            for (int earlier = 0; earlier < index; earlier++) {
                MemorySegment other = buffers[earlier];
                if (address < other.address() + other.byteSize() && other.address() < address + buffer.byteSize()) {
                    throw new IllegalStateException("Overlapping fixed-name probe buffer");
                }
            }
        }
        for (int index = 0; index < PROFILE_NAME.length(); index++) {
            nameBuffer.setAtIndex(ValueLayout.JAVA_SHORT, index, (short) PROFILE_NAME.charAt(index));
        }
        nameView = nameBuffer.asReadOnly();
        for (int index = 0; index < path.length(); index++) {
            pathBuffer.setAtIndex(ValueLayout.JAVA_SHORT, index, (short) path.charAt(index));
        }
        pathView = pathBuffer.asReadOnly(); // Zero-initialized terminator and unused tail remain private.
    }

    private static void validatePath(String path) { WindowsProfileDllPath.require(path); }

    private void requireThread() {
        if (Thread.currentThread() != thread) {
            throw new IllegalStateException("Windows library load accessed outside its owning platform thread");
        }
    }

    private void requireOriginalScope() {
        if (installedOwner != null) installedOwner.requireOriginalLoad(this);
        else if (installationOwner instanceof WindowsOriginalInstallationCandidate || installationOwner instanceof WindowsInstalledProfileCandidate ||
            fileOwner instanceof WindowsOriginalProfileDllFileCandidate file && file.hasInstalledOwner()) {
            throw new IllegalStateException("Installed ownership cannot continue through the development load route");
        }
        bootstrap.requireOriginalLibraryLoadInputs(runtimeOwner);
        if (bootstrap.originalLibraryLoadArena(runtimeOwner) != originalArena ||
            bootstrap.originalLibraryLoadEntry(runtimeOwner, 0) != pinEntry ||
            bootstrap.originalLibraryLoadEntry(runtimeOwner, 1) != entry) {
            throw new IllegalStateException("Windows library load lost its exact original entries");
        }
        if (!pinEntry.scope().isAlive() || !pinEntry.scope().equals(originalArena.scope()) ||
            !pinEntry.isAccessibleBy(thread) || !originalArena.scope().isAlive() || !entry.scope().isAlive() ||
            !entry.scope().equals(originalArena.scope()) || !entry.isAccessibleBy(thread)) {
            throw new IllegalStateException("Original Windows library load scope is unavailable");
        }
    }

    Result invoke() {
        requireThread();
        if (attempted || retired) throw new IllegalStateException("Windows library load is already consumed");
        synchronized (WindowsLibraryLoadInvocation.class) {
            if (processOwner != null) throw new IllegalStateException("Windows library process attempt is reserved");
            attempted = true;
            processOwner = this; // Reserve permanent original ownership BEFORE even the first fixed-name PIN probe.
        }
        boolean accepted = false;
        try {
            try {
                requireOriginalScope();
                active = true;
                try {
                    probeOriginalAbsence();
                    requireOriginalScope();
                    nativeReturnUnconfirmed = true;
                    rawModule = (long) call.invokeExact(
                        capturedState, pathView, MemorySegment.NULL, SEARCH_SYSTEM32);
                    nativeReturned = true;
                    nativeReturnUnconfirmed = false;
                }
                finally { active = false; }
            } catch (Throwable caught) {
                if (caught != failure) failure.invocationFailure = caught;
                throw failure;
            }
            try {
                // rawModule is already retained even if this scope/error read or later view allocation fails.
                requireOriginalScope();
                lastError = capturedState.get(ValueLayout.JAVA_INT, errorOffset);
                errorObserved = true;
                if (rawModule <= 0 || (rawModule & 65_535) != 0) {
                    throw new IllegalStateException("Windows library load returned no valid original module");
                }
                // Success does not require lastError==0: successful Windows calls may leave stale error state.
                module = MemorySegment.ofAddress(rawModule).reinterpret(originalArena, null);
                accepted = true;
            } catch (Throwable caught) {
                failure.readbackFailure = caught;
                throw failure;
            }
        } finally {
            try { retireFrame(); }
            finally { succeeded = accepted && retired && !nativeReturnUnconfirmed &&
                !probeObservationUnconfirmed && !failure.retirementFailed(); }
        }
        return result;
    }

    private void probeOriginalAbsence() {
        try {
            // A stale/nonzero output is never absence. The original output starts zero and is not reused.
            if (probeModuleBuffer.get(ValueLayout.JAVA_LONG, 0) != 0) {
                throw new IllegalStateException("Fixed-name module output was not originally empty");
            }
            probeAttempted = true;
            probeObservationUnconfirmed = true;
            nativeReturnUnconfirmed = true;
            probeStatus = (int) pinCall.invokeExact(capturedState, 1, nameView, probeModuleBuffer);
            probeReturned = true;
            nativeReturnUnconfirmed = false;
            // Retain raw bits before error readback or any segment-wrapper allocation; never unpin.
            rawPreexistingModule = probeModuleBuffer.get(ValueLayout.JAVA_LONG, 0);
            probeError = capturedState.get(ValueLayout.JAVA_INT, errorOffset);
            probeObservationUnconfirmed = false;
            if (probeStatus != 0 || rawPreexistingModule != 0 || probeError != 126) {
                throw new IllegalStateException("Fixed profile DLL absence was not established");
            }
        } catch (Throwable caught) {
            failure.probeFailure = caught;
            throw failure;
        }
    }

    /**
     * Only confirmed-unused private call buffers retire. An unobserved native return quarantines the
     * complete frame; no original arena, loaded module, file or installation owner is closed or unloaded.
     */
    void retireFrame() {
        requireThread();
        if (active) throw new IllegalStateException("Windows library load is still active");
        if (nativeReturnUnconfirmed || probeObservationUnconfirmed) return; // Java unwinding is not proof that native arguments retired.
        if (retired) {
            if (failure.retirementFailed()) throw failure;
            return;
        }
        retired = true;
        try { if (nameBuffer != null) nameBuffer.fill((byte) 0); }
        catch (Throwable caught) { failure.nameClearFailure = caught; }
        try { if (probeModuleBuffer != null) probeModuleBuffer.fill((byte) 0); }
        catch (Throwable caught) { failure.probeClearFailure = caught; }
        try { if (pathBuffer != null) pathBuffer.fill((byte) 0); }
        catch (Throwable caught) { failure.pathClearFailure = caught; }
        try { if (capturedState != null) capturedState.fill((byte) 0); }
        catch (Throwable caught) { failure.stateClearFailure = caught; }
        try { if (frameArena != null) frameArena.close(); }
        catch (Throwable caught) { failure.arenaCloseFailure = caught; }
        if (failure.retirementFailed()) throw failure;
    }
}
