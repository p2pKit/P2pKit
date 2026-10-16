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
 * Dormant fixed LoadLibraryExW mechanics, not bootstrap, installed authority or a productive loader.
 * The later reviewed caller must transfer exclusive original installation/runtime/file owners and the
 * independently resolved system entry before use. References/scopes/path syntax cannot establish those facts.
 * There is no lookup, environment search, global search-path mutation, FreeLibrary or provider publication.
 */
final class WindowsLibraryLoadInvocation {
    static final int MAXIMUM_PATH_CHARS = WindowsProfileDllPath.MAXIMUM_PATH_CHARS;
    static final int SEARCH_SYSTEM32 = 0x00000800;
    static final MemoryLayout PATH = MemoryLayout.sequenceLayout(MAXIMUM_PATH_CHARS, ValueLayout.JAVA_SHORT);
    // On the guarded Windows-x64 ABI both an opaque HMODULE pointer and this 64-bit integer return
    // occupy RAX. The primitive carrier preserves returned bits before FFM can allocate a segment view.
    static final FunctionDescriptor DESCRIPTOR = FunctionDescriptor.of(ValueLayout.JAVA_LONG,
        ValueLayout.ADDRESS.withTargetLayout(PATH), ValueLayout.ADDRESS, ValueLayout.JAVA_INT);

    static final class Result {
        final WindowsLibraryLoadInvocation retainedInvocation;

        private Result(WindowsLibraryLoadInvocation invocation) { retainedInvocation = invocation; }

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
        Throwable readbackFailure;
        Throwable pathClearFailure;
        Throwable stateClearFailure;
        Throwable arenaCloseFailure;

        Failure(WindowsLibraryLoadInvocation invocation) {
            super("Windows library load failed with original ownership retained", null, false, false);
            retainedInvocation = invocation;
        }

        boolean retirementFailed() {
            return pathClearFailure != null || stateClearFailure != null || arenaCloseFailure != null;
        }
    }

    private static WindowsLibraryLoadInvocation processOwner;
    private final Thread thread = Thread.currentThread();
    final Object installationOwner;
    final Object runtimeOwner;
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
    private MemorySegment module;
    private long rawModule;
    private boolean nativeReturned;
    private int lastError;
    private boolean errorObserved;
    private boolean attempted;
    private boolean active;
    private boolean retired;
    private boolean succeeded;

    private WindowsLibraryLoadInvocation(Object installationOwner, Object runtimeOwner, Object fileOwner,
                                        MemorySegment entry, Arena originalArena, String path) {
        this.installationOwner = installationOwner;
        this.runtimeOwner = runtimeOwner;
        this.fileOwner = fileOwner;
        this.entry = entry;
        this.originalArena = originalArena;
        this.path = path;
    }

    static WindowsLibraryLoadInvocation prepare(Object installationOwner, Object runtimeOwner, Object fileOwner,
                                                MemorySegment entry, Arena originalArena, String path) {
        WindowsLoaderRuntime.requireDiagnosticRuntime();
        if (WindowsLibraryLoadInvocation.class.getModule() != WindowsLoaderRuntime.class.getModule() ||
            Thread.currentThread().isVirtual()) {
            throw new IllegalStateException("Windows library load requires its original boot module/platform thread");
        }
        validatePath(path);
        if (installationOwner == null || runtimeOwner == null || fileOwner == null || entry == null ||
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
            installationOwner, runtimeOwner, fileOwner, entry, originalArena, path);
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
            invocation.prepareFrame(handle, state, offset);
            return invocation;
        } catch (Throwable caught) {
            invocation.failure.preparationFailure = caught;
            try { invocation.retireFrame(); } catch (Failure ignored) { /* Keep independent failure slots. */ }
            throw invocation.failure;
        }
    }

    /** Private frame mechanics also exercised reflectively by inert tests; no production validation entry exists. */
    private void prepareFrame(MethodHandle handle, MemoryLayout state, long offset) {
        call = handle;
        errorOffset = offset;
        frameArena = Arena.ofConfined();
        pathBuffer = frameArena.allocate(PATH);
        capturedState = frameArena.allocate(state);
        long first = pathBuffer.address();
        long second = capturedState.address();
        if (first <= 0 || first > Long.MAX_VALUE - PATH.byteSize() || second <= 0 ||
            second > Long.MAX_VALUE - state.byteSize() || (first & 1) != 0 || (second & 3) != 0 ||
            (first < second + state.byteSize() && second < first + PATH.byteSize())) {
            throw new IllegalStateException("Invalid or overlapping Windows library call buffers");
        }
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
        if (!originalArena.scope().isAlive() || !entry.scope().isAlive() ||
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
            processOwner = this; // Reserve permanent original ownership BEFORE any native load attempt.
        }
        boolean accepted = false;
        try {
            try {
                requireOriginalScope();
                active = true;
                try {
                    rawModule = (long) call.invokeExact(
                        capturedState, pathView, MemorySegment.NULL, SEARCH_SYSTEM32);
                    nativeReturned = true;
                }
                finally { active = false; }
            } catch (Throwable caught) {
                failure.invocationFailure = caught;
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
            finally { succeeded = accepted && !failure.retirementFailed(); }
        }
        return result;
    }

    /** Only private call buffers retire. No original arena, loaded module, file or installation owner is closed. */
    void retireFrame() {
        requireThread();
        if (active) throw new IllegalStateException("Windows library load is still active");
        if (retired) {
            if (failure.retirementFailed()) throw failure;
            return;
        }
        retired = true;
        try { if (pathBuffer != null) pathBuffer.fill((byte) 0); }
        catch (Throwable caught) { failure.pathClearFailure = caught; }
        try { if (capturedState != null) capturedState.fill((byte) 0); }
        catch (Throwable caught) { failure.stateClearFailure = caught; }
        try { if (frameArena != null) frameArena.close(); }
        catch (Throwable caught) { failure.arenaCloseFailure = caught; }
        if (failure.retirementFailed()) throw failure;
    }
}
