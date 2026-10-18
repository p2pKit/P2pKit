package dev.p2pkit.rpc.windows.loader;

import java.lang.foreign.Arena;
import java.lang.foreign.FunctionDescriptor;
import java.lang.foreign.Linker;
import java.lang.foreign.MemoryLayout;
import java.lang.foreign.MemorySegment;
import java.lang.foreign.ValueLayout;
import java.lang.invoke.MethodHandle;

/**
 * Actual permanently retained file acquisition/metadata mechanics for four concrete original owner roles.
 * JVM and profile-DLL ownership are independent: neither can substitute for the other. No authority
 * token, native-entry callback or raw pathname factory exists. Owner identity precedes native effects.
 * NOT installation/runtime authority: final-component no-reparse and handle metadata do not establish
 * ancestor custody, ACL/owner policy, filesystem admission, mapped-module identity or absence of a
 * pre-existing writable mapping. The original observed pathname is not an independent expected identity.
 * An unconfirmed Java/native return retains the private frame without inferring pending OS I/O.
 * No profile operation, write, deletion, privilege change or productive provider activation occurs here.
 */
final class WindowsOriginalFileLease {
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
        final transient WindowsOriginalFileLease retainedCandidate;
        Throwable operationFailure;
        final Throwable[] clearFailures = new Throwable[6];
        Throwable arenaCloseFailure;

        private Failure(WindowsOriginalFileLease candidate) {
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
    private final WindowsOriginalJvmFileCandidate originalOwner;
    private final WindowsOriginalProfileDllFileCandidate originalProfileDllOwner;
    private final WindowsOriginalSystemModuleCandidate originalSystemOwner;
    private final WindowsOriginalInstallationCandidate originalInstallationOwner;
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
    private boolean nativeReturnUnconfirmed;
    private boolean succeeded;

    // Retain the original JVM constructor/signature, including null-owner refusal before native effects.
    WindowsOriginalFileLease(WindowsOriginalJvmFileCandidate owner) { this(owner, null, null, null); }

    static WindowsOriginalFileLease forProfileDll(WindowsOriginalProfileDllFileCandidate owner) {
        if (owner == null) throw new IllegalArgumentException("Missing original profile DLL file owner");
        return new WindowsOriginalFileLease(null, owner, null, null);
    }

    static WindowsOriginalFileLease forSystemModule(WindowsOriginalSystemModuleCandidate owner) {
        if (owner == null) throw new IllegalArgumentException("Missing original system module file owner");
        return new WindowsOriginalFileLease(null, null, owner, null);
    }

    static WindowsOriginalFileLease forInstallation(WindowsOriginalInstallationCandidate owner) {
        if (owner == null) throw new IllegalArgumentException("Missing original installation file owner");
        return new WindowsOriginalFileLease(null, null, null, owner);
    }

    private WindowsOriginalFileLease(WindowsOriginalJvmFileCandidate jvm,
        WindowsOriginalProfileDllFileCandidate dll, WindowsOriginalSystemModuleCandidate system,
        WindowsOriginalInstallationCandidate installation) {
        originalOwner = jvm;
        originalProfileDllOwner = dll;
        originalSystemOwner = system;
        originalInstallationOwner = installation;
        // Only these four fixed constructors select a role. No caller chooses limits, permissions or entries.
        if (installation != null) {
            linker = installation.originalLinker();
            bootstrapArena = installation.originalBootstrapArena();
            createEntry = installation.originalFileEntry(0);
            informationEntry = installation.originalFileEntry(1);
            finalPathEntry = installation.originalFileEntry(2);
            sourcePath = installation.originalPathSnapshot();
            sourceLength = sourcePath.length - 1;
        } else if (system != null) {
            linker = system.originalLinker();
            bootstrapArena = system.originalBootstrapArena();
            createEntry = system.originalFileEntry(0);
            informationEntry = system.originalFileEntry(1);
            finalPathEntry = system.originalFileEntry(2);
            sourcePath = system.originalPathSnapshot();
            sourceLength = sourcePath.length - 1;
        } else if (dll != null) {
            linker = dll.originalLinker();
            bootstrapArena = dll.originalBootstrapArena();
            createEntry = dll.originalFileEntry(0);
            informationEntry = dll.originalFileEntry(1);
            finalPathEntry = dll.originalFileEntry(2);
            sourcePath = dll.originalPathSnapshot();
            sourceLength = sourcePath.length - 1;
        } else {
            linker = jvm == null ? null : jvm.originalLinker;
            bootstrapArena = jvm == null ? null : jvm.originalBootstrapArena;
            createEntry = jvm == null ? null : jvm.originalCreateEntry;
            informationEntry = jvm == null ? null : jvm.originalInformationEntry;
            finalPathEntry = jvm == null ? null : jvm.originalFinalPathEntry;
            sourcePath = jvm == null || jvm.originalPath == null ? null : jvm.originalPath.clone();
            sourceLength = jvm == null ? 0 : jvm.originalPathLength;
        }
    }

    void observe() {
        requireOriginalOwner();
        if (attempted) throw new IllegalStateException("Original JVM file observation is already consumed");
        attempted = true;
        boolean accepted = false;
        try {
            prepareFrame();
            phase = 1;
            // Fixed Windows x64 HANDLE return bits are captured in RAX as a primitive long BEFORE any
            // segment wrapper/allocation. This is not a caller-supplied address or a memory dereference.
            // GENERIC_READ|READ_CONTROL, FILE_SHARE_READ only, OPEN_EXISTING, OPEN_REPARSE_POINT.
            nativeReturnUnconfirmed = true;
            rawHandle = (long) createCall.invokeExact(buffers[5], buffers[0], 0x80020000, 0x00000001,
                MemorySegment.NULL, 3, 0x00200000, MemorySegment.NULL);
            nativeReturnUnconfirmed = false; // Retained primitive return, including INVALID_HANDLE_VALUE.
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
            nativeReturnUnconfirmed = true;
            finalPathReturn = (int) finalPathCall.invokeExact(buffers[5], handle, buffers[1], FINAL_CHARS, 0);
            nativeReturnUnconfirmed = false;
            observeError(4);
            validateFinalPath();
            phase = 4;
            inspectMetadata(second, 3, 5);
            for (int index = 0; index < first.length; index++) {
                if (first[index] != second[index]) {
                    throw new IllegalStateException("Original JVM file metadata changed during observation");
                }
            }
            requireOriginalOwner();
            accepted = true;
        } catch (Throwable caught) {
            failure.operationFailure = caught;
        } finally {
            retireFrame();
            succeeded = accepted && frameRetired && !failure.retirementFailed();
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
        nativeReturnUnconfirmed = true;
        queryReturns[statusOffset] = (int) informationCall.invokeExact(buffers[5], handle, 18, buffers[2], 24);
        nativeReturnUnconfirmed = false;
        observeError(errorIndex);
        if (queryReturns[statusOffset] == 0) throw new IllegalStateException("Original JVM file ID is unavailable");
        observed[0] = buffers[2].get(ValueLayout.JAVA_LONG, 0);
        observed[1] = buffers[2].get(ValueLayout.JAVA_LONG, 8);
        observed[2] = buffers[2].get(ValueLayout.JAVA_LONG, 16);
        buffers[3].fill((byte) 0);
        nativeReturnUnconfirmed = true;
        queryReturns[statusOffset + 1] = (int) informationCall.invokeExact(buffers[5], handle, 9, buffers[3], 8);
        nativeReturnUnconfirmed = false;
        observeError(errorIndex + 1);
        if (queryReturns[statusOffset + 1] == 0) {
            throw new IllegalStateException("Original JVM file attributes are unavailable");
        }
        observed[6] = Integer.toUnsignedLong(buffers[3].get(ValueLayout.JAVA_INT, 0));
        observed[7] = Integer.toUnsignedLong(buffers[3].get(ValueLayout.JAVA_INT, 4));
        buffers[4].fill((byte) 0);
        nativeReturnUnconfirmed = true;
        queryReturns[statusOffset + 2] = (int) informationCall.invokeExact(buffers[5], handle, 1, buffers[4], 24);
        nativeReturnUnconfirmed = false;
        observeError(errorIndex + 2);
        if (queryReturns[statusOffset + 2] == 0) {
            throw new IllegalStateException("Original JVM file standard metadata is unavailable");
        }
        observed[3] = buffers[4].get(ValueLayout.JAVA_LONG, 0);
        observed[4] = buffers[4].get(ValueLayout.JAVA_LONG, 8);
        observed[5] = Integer.toUnsignedLong(buffers[4].get(ValueLayout.JAVA_INT, 16));
        // Padding is not identity. Both BOOLEAN fields are checked individually, not as a padded integer.
        if (observed[0] == 0 || (observed[1] == 0 && observed[2] == 0) || observed[3] < 0 ||
            refusedFileSize(observed[4]) || refusedLinkCount(observed[5]) ||
            (observed[6] & (0x10 | 0x400 | 0x1000)) != 0 || observed[7] != 0 ||
            buffers[4].get(ValueLayout.JAVA_BYTE, 20) != 0 || buffers[4].get(ValueLayout.JAVA_BYTE, 21) != 0) {
            throw new IllegalStateException("Original JVM file has refused identity, type or metadata");
        }
    }

    private boolean refusedFileSize(long bytes) {
        if (originalProfileDllOwner != null || originalSystemOwner != null) return bytes < 512 || bytes > 32L * 1024 * 1024;
        return bytes <= 0 || bytes > MAXIMUM_FILE_BYTES;
    }

    private boolean refusedLinkCount(long links) {
        // System servicing links are observed metadata ONLY. JVM/profile/installation policy remains exactly one.
        return originalSystemOwner == null ? links != 1 : links <= 0 || links > 0xffff_ffffL;
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

    private void requireOriginalOwner() {
        if (Thread.currentThread() != thread || ((originalOwner == null ? 0 : 1) + (originalProfileDllOwner == null ? 0 : 1) +
            (originalSystemOwner == null ? 0 : 1) + (originalInstallationOwner == null ? 0 : 1) != 1)) {
            throw new IllegalStateException("Original JVM file requires its original platform thread");
        }
        if (originalInstallationOwner != null) originalInstallationOwner.requireOriginalFileLease(this);
        else if (originalSystemOwner != null) originalSystemOwner.requireOriginalFileLease(this);
        else if (originalProfileDllOwner != null) originalProfileDllOwner.requireOriginalLease(this);
        else originalOwner.requireOriginalLease(this);
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
        // Conservative return-evidence gate, not a claim that these synchronous APIs returned pending I/O.
        if (frameRetired || nativeReturnUnconfirmed) return;
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
        requireOriginalOwner();
        if (!succeeded || !frameRetired || nativeReturnUnconfirmed || handle == null || rawHandle <= 0 ||
            handleArena == null || !handleArena.scope().isAlive() || !handle.scope().equals(handleArena.scope()) ||
            !handle.isAccessibleBy(thread)) {
            throw new IllegalStateException("Original JVM file has no completed retained observation");
        }
    }

    boolean completed() { requireCompleted(); return true; }
    boolean leaseHeld() { requireCompleted(); return true; }

    private void requireRequester(WindowsOriginalJvmFileCandidate requester) {
        if (requester == null || requester != originalOwner) {
            throw new IllegalStateException("Original file lease belongs to another JVM facade");
        }
        requireCompleted();
    }

    private void requireSystemRequester(WindowsOriginalSystemModuleCandidate requester) {
        if (requester == null || requester != originalSystemOwner) {
            throw new IllegalStateException("Original file lease belongs to another system module");
        }
        requireCompleted();
    }

    private void requireInstallationRequester(WindowsOriginalInstallationCandidate requester) {
        if (requester == null || requester != originalInstallationOwner) {
            throw new IllegalStateException("Original file lease belongs to another installation owner");
        }
        requireCompleted();
    }

    WindowsOriginalFileSecurityQuery newInstallationSecurity(WindowsOriginalInstallationCandidate requester) {
        requireInstallationRequester(requester);
        requester.requireOriginalNativeInputs();
        return WindowsOriginalFileSecurityQuery.forInstallation(requester, linker, bootstrapArena, handleArena, handle,
            requester.originalSecurityEntry(this, 0), requester.originalSecurityEntry(this, 1),
            requester.originalSecurityEntry(this, 2), requester.originalSecurityEntry(this, 3));
    }

    WindowsOriginalFileAncestorsLease newInstallationAncestors(WindowsOriginalInstallationCandidate requester,
        WindowsOriginalFileSecurityQuery security, Arena moduleArena, MemorySegment module,
        MemorySegment queryEntry, MemorySegment pinEntry, MemorySegment resolveEntry) {
        requireInstallationRequester(requester);
        requester.requireOriginalQuery(security);
        requester.requireOriginalAncestorInputs();
        return WindowsOriginalFileAncestorsLease.forInstallation(requester, linker, bootstrapArena, moduleArena,
            module, queryEntry, pinEntry, resolveEntry, createEntry, informationEntry, finalPathEntry,
            requester.originalAncestorsEntry(this, 0), requester.originalAncestorsEntry(this, 1),
            handleArena, handle, sourcePath, sourceLength, first);
    }

    long systemByteCount(WindowsOriginalSystemModuleCandidate requester) {
        requireSystemRequester(requester);
        return first[4];
    }

    long systemLinkCount(WindowsOriginalSystemModuleCandidate requester) {
        requireSystemRequester(requester);
        return first[5];
    }

    WindowsOriginalFileSecurityQuery newSystemModuleSecurity(WindowsOriginalSystemModuleCandidate requester) {
        requireSystemRequester(requester);
        requester.requireOriginalNativeInputs();
        return WindowsOriginalFileSecurityQuery.forSystemModule(requester, linker, bootstrapArena, handleArena, handle,
            requester.originalSecurityEntry(this, 0), requester.originalSecurityEntry(this, 1),
            requester.originalSecurityEntry(this, 2), requester.originalSecurityEntry(this, 3));
    }

    WindowsOriginalFileAncestorsLease newSystemModuleAncestors(WindowsOriginalSystemModuleCandidate requester,
        WindowsOriginalFileSecurityQuery security, Arena moduleArena, MemorySegment module,
        MemorySegment queryEntry, MemorySegment pinEntry, MemorySegment resolveEntry) {
        requireSystemRequester(requester);
        requester.requireOriginalQuery(security);
        requester.requireOriginalAncestorInputs();
        return WindowsOriginalFileAncestorsLease.forSystemModule(requester, linker, bootstrapArena, moduleArena,
            module, queryEntry, pinEntry, resolveEntry, createEntry, informationEntry, finalPathEntry,
            requester.originalAncestorsEntry(this, 0), requester.originalAncestorsEntry(this, 1),
            handleArena, handle, sourcePath, sourceLength, first);
    }

    WindowsOriginalFileBytesLease newSystemModuleBytes(WindowsOriginalSystemModuleCandidate requester) {
        requireSystemRequester(requester);
        requester.requireOriginalByteInputs();
        return WindowsOriginalFileBytesLease.forSystemModule(requester, linker, bootstrapArena, handleArena, handle,
            requester.originalReadEntry(this), informationEntry, first);
    }

    WindowsOriginalJvmBytesCandidate newJvmBytes(WindowsOriginalJvmFileCandidate requester) {
        requireRequester(requester);
        return new WindowsOriginalJvmBytesCandidate(requester, linker, bootstrapArena, handleArena, handle,
            requester.originalReadEntry(this), informationEntry, first);
    }

    WindowsOriginalJvmSecurityCandidate newJvmSecurity(WindowsOriginalJvmFileCandidate requester) {
        requireRequester(requester);
        return new WindowsOriginalJvmSecurityCandidate(requester, linker, bootstrapArena, handleArena, handle,
            requester.originalSecurityEntry(this, 0), requester.originalSecurityEntry(this, 1),
            requester.originalSecurityEntry(this, 2), requester.originalSecurityEntry(this, 3));
    }

    WindowsOriginalProfileDllSecurityCandidate newProfileDllSecurity(WindowsOriginalProfileDllFileCandidate requester) {
        if (requester == null || requester != originalProfileDllOwner) {
            throw new IllegalStateException("Original file lease belongs to another profile DLL facade");
        }
        requireCompleted();
        // No caller supplies a HANDLE or chooses native exports. These are this lease's exact originals.
        return new WindowsOriginalProfileDllSecurityCandidate(requester, linker, bootstrapArena, handleArena, handle,
            requester.originalSecurityEntry(this, 0), requester.originalSecurityEntry(this, 1),
            requester.originalSecurityEntry(this, 2), requester.originalSecurityEntry(this, 3));
    }

    WindowsOriginalJvmAncestorsCandidate newJvmAncestors(WindowsOriginalJvmFileCandidate requester,
        WindowsOriginalJvmSecurityCandidate security, Arena moduleArena, MemorySegment module,
        MemorySegment queryEntry, MemorySegment pinEntry, MemorySegment resolveEntry) {
        requireRequester(requester);
        requester.requireOriginalSecurity(security);
        return new WindowsOriginalJvmAncestorsCandidate(security, linker, bootstrapArena, moduleArena,
            module, queryEntry, pinEntry, resolveEntry, createEntry, informationEntry, finalPathEntry,
            requester.originalAncestorsEntry(this, 0), requester.originalAncestorsEntry(this, 1),
            handleArena, handle, sourcePath, sourceLength, first);
    }

    WindowsOriginalProfileDllAncestorsCandidate newProfileDllAncestors(WindowsOriginalProfileDllFileCandidate requester,
        WindowsOriginalProfileDllSecurityCandidate security, Arena moduleArena, MemorySegment module,
        MemorySegment queryEntry, MemorySegment pinEntry, MemorySegment resolveEntry) {
        if (requester == null || requester != originalProfileDllOwner) {
            throw new IllegalStateException("Original file lease belongs to another profile DLL facade");
        }
        requireCompleted();
        requester.requireOriginalSecurity(security);
        security.requireOriginalAncestorInputs();
        return new WindowsOriginalProfileDllAncestorsCandidate(security, linker, bootstrapArena, moduleArena,
            module, queryEntry, pinEntry, resolveEntry, createEntry, informationEntry, finalPathEntry,
            requester.originalAncestorsEntry(this, 0), requester.originalAncestorsEntry(this, 1),
            handleArena, handle, sourcePath, sourceLength, first);
    }

    WindowsOriginalProfileDllBytesCandidate newProfileDllBytes(WindowsOriginalProfileDllFileCandidate requester) {
        if (requester == null || requester != originalProfileDllOwner) {
            throw new IllegalStateException("Original file lease belongs to another profile DLL facade");
        }
        requireCompleted();
        requester.requireOriginalByteInputs();
        return new WindowsOriginalProfileDllBytesCandidate(requester, linker, bootstrapArena, handleArena, handle,
            requester.originalReadEntry(this), informationEntry, first);
    }
}
