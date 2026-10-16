package dev.p2pkit.rpc.windows.loader;

import java.lang.foreign.Arena;
import java.lang.foreign.FunctionDescriptor;
import java.lang.foreign.Linker;
import java.lang.foreign.MemoryLayout;
import java.lang.foreign.MemorySegment;
import java.lang.foreign.ValueLayout;
import java.lang.invoke.MethodHandle;

/**
 * Actual, permanently retained read-only file lease attached to the original JVM observation.
 * NOT installation/runtime authority: final-component no-reparse and handle metadata do not establish
 * ancestor custody, ACL/owner policy, filesystem admission, mapped-module identity or absence of a
 * pre-existing writable mapping. The original observed pathname is not an independent expected identity.
 * No profile operation, write, deletion, privilege change or productive provider activation occurs here.
 */
final class WindowsOriginalJvmFileCandidate {
    private static final int SOURCE_CHARS = 1024;
    private static final int FINAL_CHARS = SOURCE_CHARS + 4;
    private static final long MAXIMUM_FILE_BYTES = 512L * 1024 * 1024;
    private static final MemoryLayout SOURCE_PATH = MemoryLayout.sequenceLayout(SOURCE_CHARS, ValueLayout.JAVA_SHORT);
    private static final MemoryLayout FINAL_PATH = MemoryLayout.sequenceLayout(FINAL_CHARS, ValueLayout.JAVA_SHORT);
    private static final MemoryLayout FILE_ID = MemoryLayout.sequenceLayout(24, ValueLayout.JAVA_BYTE).withByteAlignment(8);
    private static final MemoryLayout ATTRIBUTE_TAG = MemoryLayout.sequenceLayout(8, ValueLayout.JAVA_BYTE).withByteAlignment(4);
    private static final MemoryLayout STANDARD = MemoryLayout.sequenceLayout(24, ValueLayout.JAVA_BYTE).withByteAlignment(8);

    static final class Failure extends RuntimeException {
        private static final long serialVersionUID = 1L;
        final transient WindowsOriginalJvmFileCandidate retainedCandidate;
        Throwable operationFailure;
        final Throwable[] clearFailures = new Throwable[6];
        Throwable arenaCloseFailure;

        private Failure(WindowsOriginalJvmFileCandidate candidate) {
            super("Original JVM file observation failed with handle ownership retained", null, false, false);
            retainedCandidate = candidate;
        }

        private boolean retirementFailed() {
            if (arenaCloseFailure != null) return true;
            for (Throwable clearFailure : clearFailures) if (clearFailure != null) return true;
            return false;
        }
    }

    private final Thread thread = Thread.currentThread();
    private final WindowsOriginalJvmCandidate runtime;
    private final Linker linker;
    private final Arena bootstrapArena;
    private final MemorySegment createEntry;
    private final MemorySegment informationEntry;
    private final MemorySegment finalPathEntry;
    private final char[] sourcePath;
    private final int sourceLength;
    private final Failure failure = new Failure(this);
    // Input path, final path, FILE_ID_INFO, FILE_ATTRIBUTE_TAG_INFO, FILE_STANDARD_INFO, captured error.
    private final MemorySegment[] buffers = new MemorySegment[6];
    private final int[] queryReturns = new int[6];
    private final int[] lastErrors = new int[8];
    private final boolean[] errorObserved = new boolean[8];
    // Volume serial, two 64-bit file-ID words, allocation/EOF sizes, link count, attributes, reparse tag.
    private final long[] first = new long[8];
    private final long[] second = new long[8];
    private final char[] observedFinalPath = new char[FINAL_CHARS];
    private Arena handleArena;
    private Arena frameArena;
    private MethodHandle createCall;
    private MethodHandle informationCall;
    private MethodHandle finalPathCall;
    private long rawHandle;
    private MemorySegment handle;
    private long errorOffset;
    private long stateBytes;
    private int finalPathReturn;
    private int phase;
    private boolean attempted;
    private boolean frameRetired;
    private boolean succeeded;
    private boolean securityAttempted;
    private WindowsOriginalJvmSecurityCandidate security;
    private boolean bytesAttempted;
    private WindowsOriginalJvmBytesCandidate bytes;

    WindowsOriginalJvmFileCandidate(WindowsOriginalJvmCandidate runtime, Linker linker, Arena bootstrapArena,
                                   MemorySegment createEntry, MemorySegment informationEntry, MemorySegment finalPathEntry,
                                   char[] sourcePath, int sourceLength) {
        this.runtime = runtime;
        this.linker = linker;
        this.bootstrapArena = bootstrapArena;
        this.createEntry = createEntry;
        this.informationEntry = informationEntry;
        this.finalPathEntry = finalPathEntry;
        this.sourcePath = sourcePath;
        this.sourceLength = sourceLength;
    }

    void observe() {
        requireOriginalRuntime();
        if (attempted) throw new IllegalStateException("Original JVM file observation is already consumed");
        attempted = true;
        boolean accepted = false;
        try {
            prepareFrame();
            phase = 1;
            // Fixed Windows x64 HANDLE return bits are captured in RAX as a primitive long BEFORE any
            // segment wrapper/allocation. This is not a caller-supplied address or a memory dereference.
            // GENERIC_READ|READ_CONTROL, FILE_SHARE_READ only, OPEN_EXISTING, OPEN_REPARSE_POINT.
            rawHandle = (long) createCall.invokeExact(buffers[5], buffers[0], 0x80020000, 0x00000001,
                MemorySegment.NULL, 3, 0x00200000, MemorySegment.NULL);
            observeError(0);
            if (rawHandle <= 0 || rawHandle > Long.MAX_VALUE - 1) {
                throw new IllegalStateException("Original JVM read-only file lease could not be acquired");
            }
            for (MemorySegment buffer : buffers) {
                if (overlap(rawHandle, 1, buffer.address(), buffer.byteSize())) {
                    throw new IllegalStateException("Original JVM file handle aliases a private frame");
                }
            }
            handle = MemorySegment.ofAddress(rawHandle).reinterpret(handleArena, null);
            phase = 2;
            inspectMetadata(first, 0, 1);
            phase = 3;
            buffers[1].fill((byte) 0x7f);
            // FILE_NAME_NORMALIZED | VOLUME_NAME_DOS == 0. A missing/truncated path is a refusal.
            finalPathReturn = (int) finalPathCall.invokeExact(buffers[5], handle, buffers[1], FINAL_CHARS, 0);
            observeError(4);
            validateFinalPath();
            phase = 4;
            inspectMetadata(second, 3, 5);
            for (int index = 0; index < first.length; index++) {
                if (first[index] != second[index]) {
                    throw new IllegalStateException("Original JVM file metadata changed during observation");
                }
            }
            requireOriginalRuntime();
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
        if (sourcePath == null || sourceLength < 10 || sourceLength >= SOURCE_CHARS ||
            sourcePath.length < sourceLength + 1 || sourcePath[sourceLength] != 0) {
            throw new IllegalStateException("Original JVM pathname is unavailable");
        }
        MemoryLayout state = Linker.Option.captureStateLayout();
        MemoryLayout error = state.select(MemoryLayout.PathElement.groupElement("GetLastError"));
        errorOffset = state.byteOffset(MemoryLayout.PathElement.groupElement("GetLastError"));
        stateBytes = state.byteSize();
        if (!(error instanceof ValueLayout.OfInt) || error.byteSize() != 4 || error.byteAlignment() != 4 ||
            stateBytes < 4 || stateBytes > 64 || errorOffset < 0 || errorOffset % 4 != 0 || errorOffset > stateBytes - 4) {
            throw new IllegalStateException("Unsupported original JVM file captured-error layout");
        }
        // HANDLE and a 64-bit integer have the same fixed Windows x64 return-register convention.
        // Primitive return avoids allocating an ADDRESS wrapper before retaining the original handle.
        FunctionDescriptor create = FunctionDescriptor.of(ValueLayout.JAVA_LONG,
            ValueLayout.ADDRESS.withTargetLayout(SOURCE_PATH), ValueLayout.JAVA_INT, ValueLayout.JAVA_INT,
            ValueLayout.ADDRESS, ValueLayout.JAVA_INT, ValueLayout.JAVA_INT, ValueLayout.ADDRESS);
        FunctionDescriptor information = FunctionDescriptor.of(ValueLayout.JAVA_INT, ValueLayout.ADDRESS,
            ValueLayout.JAVA_INT, ValueLayout.ADDRESS, ValueLayout.JAVA_INT);
        FunctionDescriptor path = FunctionDescriptor.of(ValueLayout.JAVA_INT, ValueLayout.ADDRESS,
            ValueLayout.ADDRESS.withTargetLayout(FINAL_PATH), ValueLayout.JAVA_INT, ValueLayout.JAVA_INT);
        createCall = linker.downcallHandle(createEntry, create, Linker.Option.captureCallState("GetLastError"));
        informationCall = linker.downcallHandle(informationEntry, information, Linker.Option.captureCallState("GetLastError"));
        finalPathCall = linker.downcallHandle(finalPathEntry, path, Linker.Option.captureCallState("GetLastError"));
        handleArena = Arena.ofConfined(); // Permanent attachment owns the original handle; never closed here.
        frameArena = Arena.ofConfined();
        buffers[0] = frameArena.allocate(SOURCE_PATH);
        buffers[1] = frameArena.allocate(FINAL_PATH);
        buffers[2] = frameArena.allocate(FILE_ID);
        buffers[3] = frameArena.allocate(ATTRIBUTE_TAG);
        buffers[4] = frameArena.allocate(STANDARD);
        buffers[5] = frameArena.allocate(state);
        for (int index = 0; index < buffers.length; index++) {
            MemorySegment buffer = buffers[index];
            long size = index == 0 ? SOURCE_PATH.byteSize() : index == 1 ? FINAL_PATH.byteSize() :
                index == 2 || index == 4 ? 24 : index == 3 ? 8 : stateBytes;
            int alignment = index < 2 ? 2 : index == 2 || index == 4 ? 8 : 4;
            if (!buffer.isNative() || buffer.byteSize() != size || buffer.address() <= 65_535 ||
                buffer.address() > Long.MAX_VALUE - size || buffer.address() % alignment != 0 ||
                !buffer.scope().equals(frameArena.scope()) || !buffer.isAccessibleBy(thread)) {
                throw new IllegalStateException("Invalid original JVM file private frame");
            }
            for (int prior = 0; prior < index; prior++) {
                if (overlap(buffer.address(), size, buffers[prior].address(), buffers[prior].byteSize())) {
                    throw new IllegalStateException("Original JVM file private frame ranges overlap");
                }
            }
            if (overlap(createEntry.address(), 1, buffer.address(), size) ||
                overlap(informationEntry.address(), 1, buffer.address(), size) ||
                overlap(finalPathEntry.address(), 1, buffer.address(), size)) {
                throw new IllegalStateException("Original JVM file entry aliases a private frame");
            }
        }
        buffers[0].fill((byte) 0);
        for (int index = 0; index < sourceLength; index++) {
            char character = sourcePath[index];
            if (character < 32 || character > 126 || character == '/') {
                throw new IllegalStateException("Unsupported original JVM file pathname representation");
            }
            buffers[0].setAtIndex(ValueLayout.JAVA_SHORT, index, (short) character);
        }
    }

    private void inspectMetadata(long[] observed, int statusOffset, int errorIndex) throws Throwable {
        buffers[2].fill((byte) 0);
        queryReturns[statusOffset] = (int) informationCall.invokeExact(buffers[5], handle, 18, buffers[2], 24);
        observeError(errorIndex);
        if (queryReturns[statusOffset] == 0) throw new IllegalStateException("Original JVM file ID is unavailable");
        observed[0] = buffers[2].get(ValueLayout.JAVA_LONG, 0);
        observed[1] = buffers[2].get(ValueLayout.JAVA_LONG, 8);
        observed[2] = buffers[2].get(ValueLayout.JAVA_LONG, 16);
        buffers[3].fill((byte) 0);
        queryReturns[statusOffset + 1] = (int) informationCall.invokeExact(buffers[5], handle, 9, buffers[3], 8);
        observeError(errorIndex + 1);
        if (queryReturns[statusOffset + 1] == 0) {
            throw new IllegalStateException("Original JVM file attributes are unavailable");
        }
        observed[6] = Integer.toUnsignedLong(buffers[3].get(ValueLayout.JAVA_INT, 0));
        observed[7] = Integer.toUnsignedLong(buffers[3].get(ValueLayout.JAVA_INT, 4));
        buffers[4].fill((byte) 0);
        queryReturns[statusOffset + 2] = (int) informationCall.invokeExact(buffers[5], handle, 1, buffers[4], 24);
        observeError(errorIndex + 2);
        if (queryReturns[statusOffset + 2] == 0) {
            throw new IllegalStateException("Original JVM file standard metadata is unavailable");
        }
        observed[3] = buffers[4].get(ValueLayout.JAVA_LONG, 0);
        observed[4] = buffers[4].get(ValueLayout.JAVA_LONG, 8);
        observed[5] = Integer.toUnsignedLong(buffers[4].get(ValueLayout.JAVA_INT, 16));
        // Padding is not identity. Both BOOLEAN fields are checked individually, not as a padded integer.
        if (observed[0] == 0 || (observed[1] == 0 && observed[2] == 0) || observed[3] < 0 ||
            observed[4] <= 0 || observed[4] > MAXIMUM_FILE_BYTES || observed[5] != 1 ||
            (observed[6] & (0x10 | 0x400 | 0x1000)) != 0 || observed[7] != 0 ||
            buffers[4].get(ValueLayout.JAVA_BYTE, 20) != 0 || buffers[4].get(ValueLayout.JAVA_BYTE, 21) != 0) {
            throw new IllegalStateException("Original JVM file has refused identity, type or metadata");
        }
    }

    private void validateFinalPath() {
        long count = Integer.toUnsignedLong(finalPathReturn);
        if (count != sourceLength + 4L || count >= FINAL_CHARS || character((int) count) != 0 ||
            character(0) != '\\' || character(1) != '\\' || character(2) != '?' || character(3) != '\\') {
            throw new IllegalStateException("Original JVM final pathname is incomplete or unsupported");
        }
        for (int index = 0; index < sourceLength; index++) {
            if (fold(character(index + 4)) != fold(sourcePath[index])) {
                throw new IllegalStateException("Original JVM final pathname differs from the module observation");
            }
        }
        for (int index = 0; index < count; index++) observedFinalPath[index] = character(index);
    }

    private void requireOriginalRuntime() {
        if (Thread.currentThread() != thread || runtime == null) {
            throw new IllegalStateException("Original JVM file requires its original platform thread");
        }
        runtime.requireOriginalFile(this);
        if (bootstrapArena == null || !bootstrapArena.scope().isAlive()) {
            throw new IllegalStateException("Original JVM file bootstrap scope is unavailable");
        }
        validateEntry(createEntry);
        validateEntry(informationEntry);
        validateEntry(finalPathEntry);
    }

    private void validateEntry(MemorySegment entry) {
        if (entry == null || !entry.isNative() || entry.byteSize() != 0 || entry.address() <= 65_535 ||
            entry.address() > Long.MAX_VALUE - 1 || !entry.scope().equals(bootstrapArena.scope()) ||
            !entry.scope().isAlive() || !entry.isAccessibleBy(thread)) {
            throw new IllegalStateException("Original JVM file lost a scoped system entry");
        }
    }

    private char character(int index) {
        return (char) Short.toUnsignedInt(buffers[1].getAtIndex(ValueLayout.JAVA_SHORT, index));
    }
    private static char fold(char value) { return value >= 'A' && value <= 'Z' ? (char) (value + ('a' - 'A')) : value; }
    private static boolean overlap(long first, long count, long second, long size) {
        return first < second + size && second < first + count;
    }
    private void observeError(int index) {
        lastErrors[index] = buffers[5].get(ValueLayout.JAVA_INT, errorOffset);
        errorObserved[index] = true; // Success does not require a zero GetLastError value.
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
        // Never CloseHandle or close the original handle scope, even after an observation refusal.
    }

    private void requireCompleted() {
        requireOriginalRuntime();
        if (!succeeded || !frameRetired || handle == null || rawHandle <= 0 ||
            handleArena == null || !handleArena.scope().isAlive() || !handle.scope().equals(handleArena.scope()) ||
            !handle.isAccessibleBy(thread)) {
            throw new IllegalStateException("Original JVM file has no completed retained observation");
        }
    }

    boolean completed() { requireCompleted(); return true; }
    boolean leaseHeld() { requireCompleted(); return true; }

    WindowsOriginalJvmBytesCandidate inspectBytes() {
        requireCompleted();
        if (bytesAttempted) throw new IllegalStateException("Original JVM file bytes were already attempted");
        bytesAttempted = true;
        bytes = new WindowsOriginalJvmBytesCandidate(this, linker, bootstrapArena, handleArena, handle,
            runtime.originalFileReadEntry(this), informationEntry, first);
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
        security = new WindowsOriginalJvmSecurityCandidate(this, linker, bootstrapArena, handleArena, handle,
            runtime.originalFileSecurityEntry(this, 0), runtime.originalFileSecurityEntry(this, 1),
            runtime.originalFileSecurityEntry(this, 2), runtime.originalFileSecurityEntry(this, 3));
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
        return new WindowsOriginalJvmAncestorsCandidate(candidate, linker, bootstrapArena, moduleArena,
            module, queryEntry, pinEntry, resolveEntry, createEntry, informationEntry, finalPathEntry,
            runtime.originalFileAncestorsEntry(this, 0), runtime.originalFileAncestorsEntry(this, 1),
            handleArena, handle, sourcePath, sourceLength, first);
    }
}
