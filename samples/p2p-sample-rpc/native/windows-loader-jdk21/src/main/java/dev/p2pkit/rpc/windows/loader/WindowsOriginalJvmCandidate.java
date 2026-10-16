package dev.p2pkit.rpc.windows.loader;

import java.lang.foreign.Arena;
import java.lang.foreign.FunctionDescriptor;
import java.lang.foreign.Linker;
import java.lang.foreign.MemoryLayout;
import java.lang.foreign.MemorySegment;
import java.lang.foreign.ValueLayout;
import java.lang.invoke.MethodHandle;

/**
 * Dormant continuation of the actual fixed-system bootstrap candidate, NOT installed-runtime authority.
 * Pins the already-loaded jvm.dll, resolves fixed JNI_GetCreatedJavaVMs with the same physical provider
 * and retains the actual single-VM result. Same-provider checking is not proof of an absent PE forwarder.
 * No explicit library/VM creation or loading API is called; export forwarding can have implicit loader
 * effects and remains conditional on prior runtime/export authority. No environment/java.home identity
 * is assumed, and no JNI registration or profile provider is activated. Exact runtime provenance and
 * original startup/installation admission remain required before this can authorize productive use.
 */
final class WindowsOriginalJvmCandidate {
    private static final int PATH_CHARS = 1024;
    private static final String JVM_NAME = "jvm.dll";
    private static final String JNI_NAME = "JNI_GetCreatedJavaVMs";
    private static final MemoryLayout PATH = MemoryLayout.sequenceLayout(PATH_CHARS, ValueLayout.JAVA_SHORT);
    private static final MemoryLayout NAME = MemoryLayout.sequenceLayout(JVM_NAME.length() + 1, ValueLayout.JAVA_SHORT);
    private static final MemoryLayout EXPORT_NAME = MemoryLayout.sequenceLayout(JNI_NAME.length() + 1, ValueLayout.JAVA_BYTE);

    static final class Failure extends RuntimeException {
        private static final long serialVersionUID = 1L;
        final transient WindowsOriginalJvmCandidate retainedCandidate;
        Throwable operationFailure;
        final Throwable[] clearFailures = new Throwable[5];
        Throwable arenaCloseFailure;

        private Failure(WindowsOriginalJvmCandidate candidate) {
            super("Original JVM candidate failed with original ownership retained", null, false, false);
            retainedCandidate = candidate;
        }

        private boolean retirementFailed() {
            if (arenaCloseFailure != null) return true;
            for (Throwable clearFailure : clearFailures) if (clearFailure != null) return true;
            return false;
        }
    }

    private final Thread thread = Thread.currentThread();
    private final WindowsSystemBootstrapCandidate bootstrap;
    private final Linker linker;
    private final Arena bootstrapArena;
    private final MemorySegment pinEntry;
    private final MemorySegment pathEntry;
    private final MemorySegment resolveEntry;
    private final Failure failure = new Failure(this);
    // HMODULE output, module pathname, fixed JVM name, fixed JNI name, captured Windows error.
    private final MemorySegment[] buffers = new MemorySegment[5];
    private final int[] lastErrors = new int[4];
    private final boolean[] errorObserved = new boolean[4];
    private final char[] observedModulePath = new char[PATH_CHARS];
    private Arena runtimeArena;
    private Arena frameArena;
    private MethodHandle pinCall;
    private MethodHandle pathCall;
    private MethodHandle resolveCall;
    private MemorySegment returnedModule;
    private MemorySegment returnedEntry;
    private MemorySegment returnedProvider;
    private long rawModule;
    private long rawProvider;
    private MemorySegment module;
    private MemorySegment entry;
    private WindowsJvmAcquisitionInvocation acquisition;
    private WindowsJvmAcquisitionInvocation.Result acquired;
    private long errorOffset;
    private long stateBytes;
    private int modulePinReturn;
    private int modulePathReturn;
    private int modulePathLength;
    private int providerPinReturn;
    private int phase;
    private boolean attempted;
    private boolean frameRetired;
    private boolean succeeded;

    // Merely constructing an object is not admission: observe requires the actual bootstrap's retained
    // attachment identity before preparing restricted descriptors or executing any supplied entry.
    WindowsOriginalJvmCandidate(WindowsSystemBootstrapCandidate bootstrap, Linker linker, Arena bootstrapArena,
                               MemorySegment pinEntry, MemorySegment pathEntry, MemorySegment resolveEntry) {
        this.bootstrap = bootstrap;
        this.linker = linker;
        this.bootstrapArena = bootstrapArena;
        this.pinEntry = pinEntry;
        this.pathEntry = pathEntry;
        this.resolveEntry = resolveEntry;
    }

    void observe() {
        requireOriginalBootstrap();
        if (attempted) throw new IllegalStateException("Original JVM candidate is already consumed");
        attempted = true;
        boolean accepted = false;
        try {
            prepareFrame();
            phase = 1;
            buffers[0].fill((byte) 0);
            // PIN only, by the one fixed existing module name. This API does not load a missing JVM.
            modulePinReturn = (int) pinCall.invokeExact(buffers[4], 0x00000001, buffers[2], buffers[0]);
            // Preserve the actual permanent PIN effect before allocating a segment wrapper or decoding errors.
            rawModule = buffers[0].get(ValueLayout.JAVA_LONG, 0);
            returnedModule = buffers[0].get(ValueLayout.ADDRESS, 0);
            observeError(0);
            validateModule(returnedModule, modulePinReturn);
            module = returnedModule.reinterpret(runtimeArena, null);

            phase = 2;
            buffers[1].fill((byte) 0x7f);
            modulePathReturn = (int) pathCall.invokeExact(buffers[4], module, buffers[1], PATH_CHARS);
            observeError(1);
            validateModulePath();

            phase = 3;
            // Fixed ASCII name; a private pointer above 0xffff cannot be interpreted as an ordinal.
            returnedEntry = (MemorySegment) resolveCall.invokeExact(buffers[4], module, buffers[3]);
            observeError(2);
            validateReturnedEntry();
            entry = returnedEntry.reinterpret(runtimeArena, null);

            phase = 4;
            buffers[0].fill((byte) 0);
            providerPinReturn = (int) pinCall.invokeExact(buffers[4], 0x00000005, entry, buffers[0]);
            rawProvider = buffers[0].get(ValueLayout.JAVA_LONG, 0);
            returnedProvider = buffers[0].get(ValueLayout.ADDRESS, 0);
            observeError(3);
            validateModule(returnedProvider, providerPinReturn);
            if (returnedProvider.address() != module.address()) {
                throw new IllegalStateException("Original JVM export resolved to another physical provider");
            }
            requireOriginalBootstrap();
            phase = 5;
            // Retain the real invocation before its sole native effect. Its original runtime owner is
            // this permanently attached candidate, not a reconstructed number or nominal caller token.
            acquisition = WindowsJvmAcquisitionInvocation.prepare(this, entry, runtimeArena);
            acquired = acquisition.invoke();
            acquired.virtualMachine(); // Requires the original runtime scope after private frame retirement.
            accepted = true;
        } catch (Throwable caught) {
            failure.operationFailure = caught;
        } finally {
            retireFrame();
            succeeded = accepted && !failure.retirementFailed();
        }
        if (!succeeded) throw failure;
    }

    private void prepareFrame() {
        MemoryLayout state = Linker.Option.captureStateLayout();
        MemoryLayout error = state.select(MemoryLayout.PathElement.groupElement("GetLastError"));
        errorOffset = state.byteOffset(MemoryLayout.PathElement.groupElement("GetLastError"));
        stateBytes = state.byteSize();
        if (!(error instanceof ValueLayout.OfInt) || error.byteSize() != 4 || error.byteAlignment() != 4 ||
            stateBytes < 4 || stateBytes > 64 || errorOffset < 0 || errorOffset % 4 != 0 || errorOffset > stateBytes - 4) {
            throw new IllegalStateException("Unsupported original JVM captured-error layout");
        }
        // Restricted descriptors are built only after the original completed Windows bootstrap guard.
        FunctionDescriptor pin = FunctionDescriptor.of(ValueLayout.JAVA_INT, ValueLayout.JAVA_INT,
            ValueLayout.ADDRESS, ValueLayout.ADDRESS.withTargetLayout(ValueLayout.JAVA_LONG));
        FunctionDescriptor path = FunctionDescriptor.of(ValueLayout.JAVA_INT, ValueLayout.ADDRESS,
            ValueLayout.ADDRESS.withTargetLayout(PATH), ValueLayout.JAVA_INT);
        FunctionDescriptor resolve = FunctionDescriptor.of(ValueLayout.ADDRESS, ValueLayout.ADDRESS,
            ValueLayout.ADDRESS.withTargetLayout(EXPORT_NAME));
        pinCall = linker.downcallHandle(pinEntry, pin, Linker.Option.captureCallState("GetLastError"));
        pathCall = linker.downcallHandle(pathEntry, path, Linker.Option.captureCallState("GetLastError"));
        resolveCall = linker.downcallHandle(resolveEntry, resolve, Linker.Option.captureCallState("GetLastError"));
        runtimeArena = Arena.ofConfined(); // Original JVM/entry/VM owner: deliberately never closed.
        frameArena = Arena.ofConfined();
        buffers[0] = frameArena.allocate(ValueLayout.JAVA_LONG);
        buffers[1] = frameArena.allocate(PATH);
        buffers[2] = frameArena.allocate(NAME);
        buffers[3] = frameArena.allocate(EXPORT_NAME);
        buffers[4] = frameArena.allocate(state);
        for (int index = 0; index < buffers.length; index++) {
            MemorySegment buffer = buffers[index];
            long size = index == 0 ? 8 : index == 1 ? PATH.byteSize() : index == 2 ? NAME.byteSize() :
                index == 3 ? EXPORT_NAME.byteSize() : stateBytes;
            int alignment = index == 0 ? 8 : index == 1 || index == 2 ? 2 : index == 3 ? 1 : 4;
            if (!buffer.isNative() || buffer.byteSize() != size || buffer.address() <= 65_535 ||
                buffer.address() > Long.MAX_VALUE - size || buffer.address() % alignment != 0 ||
                !buffer.scope().equals(frameArena.scope()) || !buffer.isAccessibleBy(thread)) {
                throw new IllegalStateException("Invalid original JVM private frame");
            }
            for (int prior = 0; prior < index; prior++) {
                if (overlap(buffer.address(), size, buffers[prior].address(), buffers[prior].byteSize())) {
                    throw new IllegalStateException("Original JVM private frame ranges overlap");
                }
            }
            if (overlap(pinEntry.address(), 1, buffer.address(), size) ||
                overlap(pathEntry.address(), 1, buffer.address(), size) ||
                overlap(resolveEntry.address(), 1, buffer.address(), size)) {
                throw new IllegalStateException("Original JVM bootstrap entry aliases a private frame");
            }
        }
        buffers[2].fill((byte) 0);
        for (int index = 0; index < JVM_NAME.length(); index++) {
            buffers[2].setAtIndex(ValueLayout.JAVA_SHORT, index, (short) JVM_NAME.charAt(index));
        }
        buffers[3].fill((byte) 0);
        for (int index = 0; index < JNI_NAME.length(); index++) {
            buffers[3].setAtIndex(ValueLayout.JAVA_BYTE, index, (byte) JNI_NAME.charAt(index));
        }
    }

    private void requireOriginalBootstrap() {
        if (Thread.currentThread() != thread || bootstrap == null) {
            throw new IllegalStateException("Original JVM candidate requires its original platform thread");
        }
        bootstrap.requireOriginalJvm(this);
        if (bootstrapArena == null || !bootstrapArena.scope().isAlive()) {
            throw new IllegalStateException("Original system bootstrap scope is unavailable");
        }
        validateSystemEntry(pinEntry);
        validateSystemEntry(pathEntry);
        validateSystemEntry(resolveEntry);
    }

    private void validateSystemEntry(MemorySegment observed) {
        if (observed == null || !observed.isNative() || observed.byteSize() != 0 || observed.address() <= 65_535 ||
            observed.address() > Long.MAX_VALUE - 1 || !observed.scope().equals(bootstrapArena.scope()) ||
            !observed.scope().isAlive() || !observed.isAccessibleBy(thread)) {
            throw new IllegalStateException("Original JVM candidate lost a scoped system entry");
        }
    }

    private void validateModule(MemorySegment observed, int status) {
        if (status == 0 || observed == null || !observed.isNative() || observed.byteSize() != 0 ||
            observed.address() <= 0 || (observed.address() & 65_535) != 0 ||
            observed.address() > Long.MAX_VALUE - 65_536) {
            throw new IllegalStateException("Original JVM module pin is invalid");
        }
        for (MemorySegment buffer : buffers) {
            if (overlap(observed.address(), 65_536, buffer.address(), buffer.byteSize())) {
                throw new IllegalStateException("Original JVM module aliases a private frame");
            }
        }
    }

    private void validateReturnedEntry() {
        if (returnedEntry == null || !returnedEntry.isNative() || returnedEntry.byteSize() != 0 ||
            returnedEntry.address() <= 65_535 || returnedEntry.address() > Long.MAX_VALUE - 1) {
            throw new IllegalStateException("Original JVM named export is unavailable");
        }
        for (MemorySegment buffer : buffers) {
            if (overlap(returnedEntry.address(), 1, buffer.address(), buffer.byteSize())) {
                throw new IllegalStateException("Original JVM export aliases a private frame");
            }
        }
    }

    private void validateModulePath() {
        long count = Integer.toUnsignedLong(modulePathReturn);
        if (count < 3 + JVM_NAME.length() || count >= PATH_CHARS || character((int) count) != 0 ||
            !letter(character(0)) || character(1) != ':' || character(2) != '\\') {
            throw new IllegalStateException("Original JVM pathname observation is incomplete or unsupported");
        }
        // Deliberately bounded absolute-ASCII subset. The observed path is NOT an independent expected
        // runtime path/hash and does not admit its ancestors, ownership, activation context or installed bytes.
        for (int index = 0; index < count; index++) {
            char value = character(index);
            if (value < 32 || value > 126 || value == '/') {
                throw new IllegalStateException("Unsupported original JVM pathname representation");
            }
        }
        int nameStart = (int) count - JVM_NAME.length();
        if (character(nameStart - 1) != '\\') {
            throw new IllegalStateException("Original JVM pathname has another basename");
        }
        for (int index = 0; index < JVM_NAME.length(); index++) {
            char value = character(nameStart + index);
            if (value >= 'A' && value <= 'Z') value += 'a' - 'A';
            if (value != JVM_NAME.charAt(index)) throw new IllegalStateException("Original JVM basename differs");
        }
        for (int index = 0; index < count; index++) observedModulePath[index] = character(index);
        modulePathLength = (int) count; // Private original observation, never an independently expected identity.
    }

    private char character(int index) {
        return (char) Short.toUnsignedInt(buffers[1].getAtIndex(ValueLayout.JAVA_SHORT, index));
    }
    private static boolean letter(char value) { return value >= 'A' && value <= 'Z' || value >= 'a' && value <= 'z'; }
    private static boolean overlap(long first, long count, long second, long size) {
        return first < second + size && second < first + count;
    }
    private void observeError(int index) {
        lastErrors[index] = buffers[4].get(ValueLayout.JAVA_INT, errorOffset);
        errorObserved[index] = true; // A successful API may leave stale nonzero error state.
    }

    private void retireFrame() {
        if (frameRetired) return;
        frameRetired = true;
        for (int index = 0; index < buffers.length; index++) {
            if (buffers[index] != null) {
                try { buffers[index].fill((byte) 0); }
                catch (Throwable caught) { failure.clearFailures[index] = caught; }
            }
        }
        if (frameArena != null) {
            try { frameArena.close(); }
            catch (Throwable caught) { failure.arenaCloseFailure = caught; }
        }
    }

    private void requireCompleted() {
        requireOriginalBootstrap();
        if (!succeeded || !frameRetired || runtimeArena == null || !runtimeArena.scope().isAlive() || acquired == null) {
            throw new IllegalStateException("Original JVM candidate has no completed observation");
        }
        acquired.virtualMachine();
    }

    boolean completed() { requireCompleted(); return true; }
    boolean singleVirtualMachineObserved() { requireCompleted(); return true; }
}
