package dev.p2pkit.rpc.windows.loader;

import java.lang.foreign.Arena;
import java.lang.foreign.FunctionDescriptor;
import java.lang.foreign.Linker;
import java.lang.foreign.MemoryLayout;
import java.lang.foreign.MemorySegment;
import java.lang.foreign.ValueLayout;
import java.lang.invoke.MethodHandle;

/**
 * Read-only handle-relative observation of the original JVM file's existing ancestor chain.
 * This remains conditional on the original startup/system-export boundary: resolving NtCreateFile
 * may have implicit forwarding effects before its same-ntdll-provider check. No caller supplies a
 * path, root classification, expected identity or authority. Accepted binary ACL policy is not an
 * approved Program Files installation, runtime provenance, mapped-file correspondence, effective
 * access/SACL guarantee, or proof against pre-existing delete handles or writable mappings.
 *
 * Original handles are retained without DELETE sharing until process exit. Directories permit READ
 * and WRITE sharing; ACL observations, not sharing alone, constrain namespace writers. A final
 * handle-relative file open must identify the already-held original JVM file. Any unconfirmed
 * NtCreateFile completion quarantines the entire native frame and all owners, without retry,
 * further native calls, clearing or closure. Only exact synchronous completion permits frame reuse.
 */
final class WindowsOriginalJvmAncestorsCandidate {
    private static final int LIMIT = 64;
    private static final int PATH_CHARS = 1024;
    private static final int GUID_PATH_CHARS = PATH_CHARS + 46;
    private static final int DESCRIPTOR_BYTES = 65_536;
    private static final String EXPORT = "NtCreateFile";
    // Error, root/path, ID/tag/standard/case, descriptor/length, component/UNICODE/OA/IOSB/HANDLE,
    // export, filesystem/serial/component-limit/flags, provider pin output.
    private static final long[] SIZES = {
        0, 8, GUID_PATH_CHARS * 2L, 24, 8, 24, 4, DESCRIPTOR_BYTES, 4, 512, 16, 48, 16, 8,
        EXPORT.length() + 1, 64, 4, 4, 4, 8
    };
    private static final long[] ALIGNMENTS = {
        4, 2, 2, 8, 4, 8, 4, 4, 4, 2, 8, 8, 8, 8, 1, 2, 4, 4, 4, 8
    };

    static final class Failure extends RuntimeException {
        private static final long serialVersionUID = 1L;
        final transient WindowsOriginalJvmAncestorsCandidate retainedCandidate;
        Throwable operationFailure;
        final Throwable[] clearFailures = new Throwable[SIZES.length];
        Throwable arenaCloseFailure;

        private Failure(WindowsOriginalJvmAncestorsCandidate candidate) {
            super("Original JVM ancestors observation failed with original ownership retained", null, false, false);
            retainedCandidate = candidate;
        }

        private boolean retirementFailed() {
            if (arenaCloseFailure != null) return true;
            for (Throwable caught : clearFailures) if (caught != null) return true;
            return false;
        }
    }

    private final Thread thread = Thread.currentThread();
    private final WindowsOriginalJvmSecurityCandidate security;
    private final Linker linker;
    private final Arena bootstrapArena;
    private final Arena moduleArena;
    private final MemorySegment module;
    private final MemorySegment queryEntry;
    private final Arena originalFileArena;
    private final MemorySegment originalFileHandle;
    private final char[] rootGuid = new char[49];
    private final MemorySegment[] systemEntries;
    private final char[] originalPath;
    private final int pathLength;
    private final long[] originalFile;
    private final Failure failure = new Failure(this);
    private final MemorySegment[] buffers = new MemorySegment[SIZES.length];
    private final long[] rawHandles = new long[LIMIT];
    private final MemorySegment[] handles = new MemorySegment[LIMIT];
    private final long[][] metadata = new long[LIMIT][8];
    private final long[] repeatedMetadata = new long[8];
    private final int[] nativeStatuses = new int[LIMIT];
    private final int[] ioStatuses = new int[LIMIT];
    private final long[] ioInformation = new long[LIMIT];
    private final int[] queryStatuses = new int[LIMIT];
    private final int[] descriptorLengths = new int[LIMIT];
    private final byte[][] descriptors = new byte[LIMIT][];
    private final boolean[] policies = new boolean[LIMIT];
    private final int[] componentStarts = new int[LIMIT - 1];
    private final int[] componentLengths = new int[LIMIT - 1];
    private final int[] lastErrors = new int[8 + LIMIT * 10];
    private int errorCount;
    private int componentCount;
    private int directoryCount;
    private int openedCount;
    private Arena leaseArena;
    private Arena frameArena;
    private MethodHandle createCall;
    private MethodHandle informationCall;
    private MethodHandle finalPathCall;
    private MethodHandle volumeCall;
    private MethodHandle driveCall;
    private MethodHandle resolveCall;
    private MethodHandle pinCall;
    private MethodHandle ntCreateCall;
    private MethodHandle queryCall;
    private MemorySegment returnedEntry;
    private MemorySegment ntCreateEntry;
    private long rawProvider;
    private int providerPinReturn;
    private long errorOffset;
    private boolean ntCompletionUnconfirmed;
    private boolean attempted;
    private boolean frameRetired;
    private boolean succeeded;
    private boolean allPoliciesAccepted = true;

    WindowsOriginalJvmAncestorsCandidate(WindowsOriginalJvmSecurityCandidate security, Linker linker,
        Arena bootstrapArena, Arena moduleArena, MemorySegment module, MemorySegment queryEntry,
        MemorySegment pinEntry, MemorySegment resolveEntry, MemorySegment createEntry,
        MemorySegment informationEntry, MemorySegment finalPathEntry, MemorySegment volumeEntry,
        MemorySegment driveEntry, Arena originalFileArena, MemorySegment originalFileHandle,
        char[] originalPath, int pathLength, long[] originalFile) {
        this.security = security;
        this.linker = linker;
        this.bootstrapArena = bootstrapArena;
        this.moduleArena = moduleArena;
        this.module = module;
        this.queryEntry = queryEntry;
        this.originalFileArena = originalFileArena;
        this.originalFileHandle = originalFileHandle;
        systemEntries = new MemorySegment[] {
            pinEntry, resolveEntry, createEntry, informationEntry, finalPathEntry, volumeEntry, driveEntry
        };
        this.originalPath = originalPath.clone();
        this.pathLength = pathLength;
        this.originalFile = originalFile.clone();
    }

    void observe() {
        requireOriginalSecurity();
        if (attempted) throw new IllegalStateException("Original JVM ancestors observation is already consumed");
        attempted = true;
        boolean accepted = false;
        try {
            validateComponents();
            prepareFrame();
            resolveOriginalNtCreate();
            // Root CreateFileW has no asynchronous creation contract. Preserve its actual opaque x64
            // HANDLE bits before any allocating wrapper/readback; never close the original lease.
            rawHandles[0] = (long) createCall.invokeExact(buffers[0], buffers[1], 0x001200a1, 3,
                MemorySegment.NULL, 3, 0x02200000, MemorySegment.NULL);
            observeError();
            retainHandle(0);
            inspectMetadata(0, true, metadata[0]);
            verifyRootVolume();
            inspectPolicy(0, WindowsInstallationSecurity.Kind.VOLUME_ROOT);
            directoryCount = 1;
            for (int component = 0; component < componentCount; component++) {
                boolean directory = component + 1 < componentCount;
                int index = component + 1;
                openRelative(index, component, directory);
                inspectMetadata(index, directory, metadata[index]);
                if (directory) {
                    directoryCount++;
                    inspectPolicy(index, WindowsInstallationSecurity.Kind.DIRECTORY);
                } else {
                    // Same original file identity, not an equal spelling of a different directory tree.
                    for (int item = 0; item < originalFile.length; item++) {
                        if (metadata[index][item] != originalFile[item]) {
                            throw new IllegalStateException("Relative JVM leaf differs from the original file lease");
                        }
                    }
                }
            }
            // Re-observe every original directory handle after the complete relative chain. Directory
            // allocation/size may change under legitimate create activity; they are not custody identity.
            for (int index = 0; index < directoryCount; index++) {
                inspectMetadata(index, true, repeatedMetadata);
                for (int item : new int[] {0, 1, 2, 5, 6, 7}) {
                    if (metadata[index][item] != repeatedMetadata[item]) {
                        throw new IllegalStateException("Original directory metadata changed during observation");
                    }
                }
            }
            requireOriginalSecurity();
            accepted = true;
        } catch (Throwable caught) {
            failure.operationFailure = caught;
        } finally {
            if (!ntCompletionUnconfirmed) retireFrame();
            succeeded = accepted && frameRetired && !failure.retirementFailed();
        }
        if (!succeeded) throw failure;
    }

    private void validateComponents() {
        if (pathLength < 10 || pathLength >= PATH_CHARS || originalPath.length <= pathLength ||
            originalPath[pathLength] != 0 || !letter(originalPath[0]) || originalPath[1] != ':' ||
            originalPath[2] != '\\' || originalFile.length != 8 || originalFile[0] == 0) {
            throw new IllegalStateException("Unsupported original JVM ancestor pathname");
        }
        int start = 3;
        for (int index = start; index <= pathLength; index++) {
            if (index < pathLength && originalPath[index] != '\\') {
                char c = originalPath[index];
                if (c < 32 || c > 126 || c == ':' || c == '/' || c == '"' || c == '<' || c == '>' ||
                    c == '|' || c == '?' || c == '*') {
                    throw new IllegalStateException("Unsupported original ancestor component");
                }
                continue;
            }
            int length = index - start;
            if (length < 1 || length > 255 || originalPath[index - 1] == '.' || originalPath[index - 1] == ' ' ||
                componentCount >= componentStarts.length) {
                throw new IllegalStateException("Original ancestor component is not bounded and canonical");
            }
            componentStarts[componentCount] = start;
            componentLengths[componentCount++] = length;
            start = index + 1;
        }
        if (componentCount < 2) throw new IllegalStateException("Original JVM has no bounded installation directories");
    }

    private void prepareFrame() {
        MemoryLayout state = Linker.Option.captureStateLayout();
        MemoryLayout error = state.select(MemoryLayout.PathElement.groupElement("GetLastError"));
        errorOffset = state.byteOffset(MemoryLayout.PathElement.groupElement("GetLastError"));
        if (!(error instanceof ValueLayout.OfInt) || error.byteAlignment() != 4 || state.byteSize() < 4 ||
            state.byteSize() > 64 || errorOffset < 0 || errorOffset % 4 != 0 || errorOffset > state.byteSize() - 4) {
            throw new IllegalStateException("Unsupported original ancestor captured-error layout");
        }
        // Actual Windows-x64 bootstrap was guarded before these restricted descriptor initializations.
        createCall = captured(2, FunctionDescriptor.of(ValueLayout.JAVA_LONG, ValueLayout.ADDRESS,
            ValueLayout.JAVA_INT, ValueLayout.JAVA_INT, ValueLayout.ADDRESS, ValueLayout.JAVA_INT,
            ValueLayout.JAVA_INT, ValueLayout.ADDRESS));
        informationCall = captured(3, FunctionDescriptor.of(ValueLayout.JAVA_INT, ValueLayout.ADDRESS,
            ValueLayout.JAVA_INT, ValueLayout.ADDRESS, ValueLayout.JAVA_INT));
        finalPathCall = captured(4, FunctionDescriptor.of(ValueLayout.JAVA_INT, ValueLayout.ADDRESS,
            ValueLayout.ADDRESS, ValueLayout.JAVA_INT, ValueLayout.JAVA_INT));
        volumeCall = captured(5, FunctionDescriptor.of(ValueLayout.JAVA_INT, ValueLayout.ADDRESS,
            ValueLayout.ADDRESS, ValueLayout.JAVA_INT, ValueLayout.ADDRESS, ValueLayout.ADDRESS,
            ValueLayout.ADDRESS, ValueLayout.ADDRESS, ValueLayout.JAVA_INT));
        driveCall = captured(6, FunctionDescriptor.of(ValueLayout.JAVA_INT, ValueLayout.ADDRESS));
        pinCall = captured(0, FunctionDescriptor.of(ValueLayout.JAVA_INT, ValueLayout.JAVA_INT,
            ValueLayout.ADDRESS, ValueLayout.ADDRESS));
        resolveCall = captured(1, FunctionDescriptor.of(ValueLayout.ADDRESS, ValueLayout.ADDRESS, ValueLayout.ADDRESS));
        queryCall = linker.downcallHandle(queryEntry, FunctionDescriptor.of(ValueLayout.JAVA_INT,
            ValueLayout.ADDRESS, ValueLayout.JAVA_INT, ValueLayout.ADDRESS, ValueLayout.JAVA_INT, ValueLayout.ADDRESS));
        leaseArena = Arena.ofConfined();
        frameArena = Arena.ofConfined();
        for (int index = 0; index < buffers.length; index++) {
            buffers[index] = index == 0 ? frameArena.allocate(state) : frameArena.allocate(SIZES[index], ALIGNMENTS[index]);
            MemorySegment buffer = buffers[index];
            long size = index == 0 ? state.byteSize() : SIZES[index];
            if (!buffer.isNative() || buffer.byteSize() != size || buffer.address() <= 65_535 ||
                buffer.address() > Long.MAX_VALUE - size || buffer.address() % ALIGNMENTS[index] != 0 ||
                !buffer.scope().equals(frameArena.scope()) || !buffer.isAccessibleBy(thread)) {
                throw new IllegalStateException("Invalid private ancestor observation frame");
            }
            for (int prior = 0; prior < index; prior++) {
                if (overlap(buffer.address(), size, buffers[prior].address(), buffers[prior].byteSize())) {
                    throw new IllegalStateException("Private ancestor frame ranges overlap");
                }
            }
            for (MemorySegment entry : systemEntries) rejectAlias(entry.address(), 1, buffer);
            rejectAlias(module.address(), 65_536, buffer);
            rejectAlias(queryEntry.address(), 1, buffer);
            rejectAlias(originalFileHandle.address(), 1, buffer);
            buffer.fill((byte) 0);
        }
        for (int index = 0; index < 3; index++) buffers[1].setAtIndex(ValueLayout.JAVA_SHORT, index, (short) originalPath[index]);
        for (int index = 0; index < EXPORT.length(); index++) buffers[14].setAtIndex(ValueLayout.JAVA_BYTE, index, (byte) EXPORT.charAt(index));
    }

    private MethodHandle captured(int index, FunctionDescriptor descriptor) {
        return linker.downcallHandle(systemEntries[index], descriptor, Linker.Option.captureCallState("GetLastError"));
    }

    private void resolveOriginalNtCreate() throws Throwable {
        returnedEntry = (MemorySegment) resolveCall.invokeExact(buffers[0], module, buffers[14]);
        observeError();
        if (returnedEntry == null || !returnedEntry.isNative() || returnedEntry.byteSize() != 0 ||
            returnedEntry.address() <= 65_535 || returnedEntry.address() > Long.MAX_VALUE - 1) {
            throw new IllegalStateException("Original NtCreateFile entry is unavailable");
        }
        for (MemorySegment buffer : buffers) rejectAlias(returnedEntry.address(), 1, buffer);
        ntCreateEntry = returnedEntry.reinterpret(moduleArena, null);
        providerPinReturn = (int) pinCall.invokeExact(buffers[0], 5, ntCreateEntry, buffers[19]);
        rawProvider = buffers[19].get(ValueLayout.JAVA_LONG, 0);
        observeError();
        if (providerPinReturn == 0 || rawProvider != module.address()) {
            throw new IllegalStateException("Original NtCreateFile has another physical provider");
        }
        ntCreateCall = linker.downcallHandle(ntCreateEntry, FunctionDescriptor.of(ValueLayout.JAVA_INT,
            ValueLayout.ADDRESS, ValueLayout.JAVA_INT, ValueLayout.ADDRESS, ValueLayout.ADDRESS,
            ValueLayout.ADDRESS, ValueLayout.JAVA_INT, ValueLayout.JAVA_INT, ValueLayout.JAVA_INT,
            ValueLayout.JAVA_INT, ValueLayout.ADDRESS, ValueLayout.JAVA_INT));
    }

    private void openRelative(int index, int component, boolean directory) throws Throwable {
        requireOriginalSecurity();
        buffers[9].fill((byte) 0);
        int length = componentLengths[component];
        for (int offset = 0; offset < length; offset++) {
            buffers[9].setAtIndex(ValueLayout.JAVA_SHORT, offset, (short) originalPath[componentStarts[component] + offset]);
        }
        buffers[10].fill((byte) 0);
        buffers[10].set(ValueLayout.JAVA_SHORT, 0, (short) (length * 2));
        buffers[10].set(ValueLayout.JAVA_SHORT, 2, (short) ((length + 1) * 2));
        buffers[10].set(ValueLayout.ADDRESS, 8, buffers[9]);
        buffers[11].fill((byte) 0);
        buffers[11].set(ValueLayout.JAVA_INT, 0, 48);
        buffers[11].set(ValueLayout.ADDRESS, 8, handles[index - 1]);
        buffers[11].set(ValueLayout.ADDRESS, 16, buffers[10]);
        // Documented OBJECT_ATTRIBUTES: OBJ_DONT_REPARSE | OBJ_CASE_INSENSITIVE. The parent directory
        // itself was opened/checked and is still held without DELETE sharing; this is one component.
        buffers[11].set(ValueLayout.JAVA_INT, 24, 0x1040);
        buffers[12].fill((byte) 0xff);
        buffers[13].fill((byte) 0);
        int access = directory ? 0x001200a1 : 0x80120080;
        int share = directory ? 3 : 1;
        int options = directory ? 0x00200021 : 0x00200060;
        // All potentially asynchronous output/input storage and original parent ownership are retained
        // before entry. Even a thrown call or nonzero final-looking status remains quarantined here.
        ntCompletionUnconfirmed = true;
        nativeStatuses[index] = (int) ntCreateCall.invokeExact(buffers[13], access, buffers[11], buffers[12],
            MemorySegment.NULL, 0, share, 1, options, MemorySegment.NULL, 0);
        rawHandles[index] = buffers[13].get(ValueLayout.JAVA_LONG, 0);
        ioStatuses[index] = buffers[12].get(ValueLayout.JAVA_INT, 0);
        ioInformation[index] = buffers[12].get(ValueLayout.JAVA_LONG, 8);
        if (nativeStatuses[index] != 0 || ioStatuses[index] != 0 || ioInformation[index] != 1 ||
            rawHandles[index] <= 0 || (rawHandles[index] & 3) != 0) {
            throw new IllegalStateException("Original relative open has no confirmed synchronous completion");
        }
        ntCompletionUnconfirmed = false;
        retainHandle(index);
    }

    private void retainHandle(int index) {
        long raw = rawHandles[index];
        if (raw <= 0 || (raw & 3) != 0 || raw > Long.MAX_VALUE - 1) {
            throw new IllegalStateException("Original ancestor handle was not opened");
        }
        for (MemorySegment buffer : buffers) rejectAlias(raw, 1, buffer);
        for (int prior = 0; prior < index; prior++) {
            if (rawHandles[prior] == raw) throw new IllegalStateException("Original ancestor handle identity was reused");
        }
        handles[index] = MemorySegment.ofAddress(raw).reinterpret(leaseArena, null);
        openedCount = index + 1;
    }

    private void inspectMetadata(int index, boolean directory, long[] observation) throws Throwable {
        information(index, 18, 3, 24);
        information(index, 9, 4, 8);
        information(index, 1, 5, 24);
        observation[0] = buffers[3].get(ValueLayout.JAVA_LONG, 0);
        observation[1] = buffers[3].get(ValueLayout.JAVA_LONG, 8);
        observation[2] = buffers[3].get(ValueLayout.JAVA_LONG, 16);
        observation[3] = buffers[5].get(ValueLayout.JAVA_LONG, 0);
        observation[4] = buffers[5].get(ValueLayout.JAVA_LONG, 8);
        observation[5] = Integer.toUnsignedLong(buffers[5].get(ValueLayout.JAVA_INT, 16));
        observation[6] = Integer.toUnsignedLong(buffers[4].get(ValueLayout.JAVA_INT, 0));
        observation[7] = Integer.toUnsignedLong(buffers[4].get(ValueLayout.JAVA_INT, 4));
        int deleted = Byte.toUnsignedInt(buffers[5].get(ValueLayout.JAVA_BYTE, 20));
        int isDirectory = Byte.toUnsignedInt(buffers[5].get(ValueLayout.JAVA_BYTE, 21));
        if (observation[0] != originalFile[0] || (observation[1] == 0 && observation[2] == 0) ||
            observation[3] < 0 || observation[4] < 0 || observation[5] == 0 ||
            (observation[6] & (0x400 | 0x1000)) != 0 || observation[7] != 0 || deleted != 0 ||
            isDirectory != (directory ? 1 : 0) || ((observation[6] & 0x10) != 0) != directory) {
            throw new IllegalStateException("Original ancestor metadata is unsafe or has another volume");
        }
        if (directory) {
            information(index, 23, 6, 4);
            if (buffers[6].get(ValueLayout.JAVA_INT, 0) != 0) {
                throw new IllegalStateException("Original directory uses unsupported case-sensitive semantics");
            }
        }
    }

    private void information(int index, int kind, int bufferIndex, int size) throws Throwable {
        buffers[bufferIndex].fill((byte) 0xff);
        int result = (int) informationCall.invokeExact(buffers[0], handles[index], kind, buffers[bufferIndex], size);
        observeError();
        if (result == 0) throw new IllegalStateException("Original ancestor metadata observation failed");
    }

    private void verifyRootVolume() throws Throwable {
        buffers[2].fill((byte) 0x7f);
        int count = (int) finalPathCall.invokeExact(buffers[0], handles[0], buffers[2], GUID_PATH_CHARS, 1);
        observeError();
        String prefix = "\\\\?\\Volume{";
        if (count != 49 || character(buffers[2], count) != 0) {
            throw new IllegalStateException("Original root is not a bare volume GUID root");
        }
        for (int index = 0; index < prefix.length(); index++) {
            if (fold(character(buffers[2], index)) != fold(prefix.charAt(index))) {
                throw new IllegalStateException("Original root is not a volume GUID root");
            }
        }
        for (int index = 11; index < 47; index++) {
            char value = character(buffers[2], index);
            boolean hyphen = index == 19 || index == 24 || index == 29 || index == 34;
            if (hyphen ? value != '-' : !(value >= '0' && value <= '9' || fold(value) >= 'a' && fold(value) <= 'f')) {
                throw new IllegalStateException("Original root has an invalid volume GUID");
            }
        }
        if (character(buffers[2], 47) != '}' || character(buffers[2], 48) != '\\') {
            throw new IllegalStateException("Original root has additional path components");
        }
        for (int index = 0; index < rootGuid.length; index++) rootGuid[index] = character(buffers[2], index);
        int drive = (int) driveCall.invokeExact(buffers[0], buffers[2]);
        observeError();
        if (drive != 3) throw new IllegalStateException("Original runtime volume is not a fixed drive");
        for (int index = 15; index <= 18; index++) buffers[index].fill((byte) 0);
        int result = (int) volumeCall.invokeExact(buffers[0], handles[0], MemorySegment.NULL, 0, buffers[16],
            buffers[17], buffers[18], buffers[15], 32);
        observeError();
        if (result == 0 || character(buffers[15], 0) != 'N' || character(buffers[15], 1) != 'T' ||
            character(buffers[15], 2) != 'F' || character(buffers[15], 3) != 'S' || character(buffers[15], 4) != 0 ||
            (buffers[18].get(ValueLayout.JAVA_INT, 0) & 8) == 0 || buffers[17].get(ValueLayout.JAVA_INT, 0) < 255) {
            throw new IllegalStateException("Original runtime volume lacks required NTFS ACL semantics");
        }
        // The held file's actual volume GUID must agree, not merely a possibly colliding volume serial
        // and file ID after drive-letter remapping. No filesystem label or user data is requested.
        buffers[2].fill((byte) 0x7f);
        int fileCount = (int) finalPathCall.invokeExact(buffers[0], originalFileHandle, buffers[2], GUID_PATH_CHARS, 1);
        observeError();
        if (fileCount != pathLength + 46 || character(buffers[2], fileCount) != 0) {
            throw new IllegalStateException("Original held JVM file has an unsupported volume-relative path");
        }
        for (int index = 0; index < rootGuid.length; index++) {
            if (fold(character(buffers[2], index)) != fold(rootGuid[index])) {
                throw new IllegalStateException("Original held JVM file differs from the observed volume root");
            }
        }
        for (int index = 3; index < pathLength; index++) {
            if (fold(character(buffers[2], index + 46)) != fold(originalPath[index])) {
                throw new IllegalStateException("Original held JVM file differs from the observed ancestor path");
            }
        }
    }

    private void inspectPolicy(int index, WindowsInstallationSecurity.Kind kind) throws Throwable {
        buffers[7].fill((byte) 0);
        buffers[8].fill((byte) 0xff);
        queryStatuses[index] = (int) queryCall.invokeExact(handles[index], 5, buffers[7], DESCRIPTOR_BYTES, buffers[8]);
        descriptorLengths[index] = buffers[8].get(ValueLayout.JAVA_INT, 0);
        long count = Integer.toUnsignedLong(descriptorLengths[index]);
        if (queryStatuses[index] != 0 || count < 20 || count > DESCRIPTOR_BYTES) {
            throw new IllegalStateException("Original ancestor security descriptor observation is incomplete");
        }
        descriptors[index] = new byte[descriptorLengths[index]];
        MemorySegment.copy(buffers[7], ValueLayout.JAVA_BYTE, 0, descriptors[index], 0, descriptorLengths[index]);
        try {
            WindowsInstallationSecurity.require(descriptors[index], kind);
            policies[index] = true;
        } catch (IllegalArgumentException refused) {
            policies[index] = false;
            allPoliciesAccepted = false;
        }
    }

    private void requireOriginalSecurity() {
        if (Thread.currentThread() != thread || security == null) {
            throw new IllegalStateException("Original ancestor observation requires its original platform thread");
        }
        security.requireOriginalAncestors(this);
        if (bootstrapArena == null || !bootstrapArena.scope().isAlive() || moduleArena == null ||
            !moduleArena.scope().isAlive() || module == null || queryEntry == null ||
            !module.scope().equals(moduleArena.scope()) || !queryEntry.scope().equals(moduleArena.scope()) ||
            !module.isAccessibleBy(thread) || !queryEntry.isAccessibleBy(thread) || originalFileArena == null ||
            !originalFileArena.scope().isAlive() || originalFileHandle == null || !originalFileHandle.isNative() ||
            originalFileHandle.byteSize() != 0 || originalFileHandle.address() <= 0 ||
            !originalFileHandle.scope().equals(originalFileArena.scope()) || !originalFileHandle.isAccessibleBy(thread)) {
            throw new IllegalStateException("Original ancestors lost their exact native owners");
        }
        for (MemorySegment entry : systemEntries) {
            if (entry == null || !entry.isNative() || entry.byteSize() != 0 || entry.address() <= 65_535 ||
                entry.address() > Long.MAX_VALUE - 1 || !entry.scope().equals(bootstrapArena.scope()) ||
                !entry.isAccessibleBy(thread)) {
                throw new IllegalStateException("Original ancestors lost a scoped system entry");
            }
        }
    }

    private void observeError() {
        if (errorCount >= lastErrors.length) throw new IllegalStateException("Original ancestor call inventory exceeded its bound");
        lastErrors[errorCount++] = buffers[0].get(ValueLayout.JAVA_INT, errorOffset);
    }

    private void retireFrame() {
        if (frameRetired || ntCompletionUnconfirmed) return;
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
        // No original module/file/directory handle, original arena, or uncertain completion frame closes.
    }

    private static char character(MemorySegment buffer, int index) {
        return (char) Short.toUnsignedInt(buffer.getAtIndex(ValueLayout.JAVA_SHORT, index));
    }
    private static boolean letter(char value) { return value >= 'a' && value <= 'z' || value >= 'A' && value <= 'Z'; }
    private static char fold(char value) { return value >= 'A' && value <= 'Z' ? (char) (value + 32) : value; }
    private static boolean overlap(long first, long size, long second, long count) {
        return first < second + count && second < first + size;
    }
    private static void rejectAlias(long address, long size, MemorySegment buffer) {
        if (overlap(address, size, buffer.address(), buffer.byteSize())) {
            throw new IllegalStateException("Original ancestor owner aliases its private native frame");
        }
    }

    private void requireCompleted() {
        requireOriginalSecurity();
        if (!succeeded || !frameRetired || ntCompletionUnconfirmed || openedCount != componentCount + 1 ||
            directoryCount != componentCount || leaseArena == null || !leaseArena.scope().isAlive()) {
            throw new IllegalStateException("Original JVM ancestors have no completed observation");
        }
    }
    boolean completed() { requireCompleted(); return true; }
    int ancestorCount() { requireCompleted(); return directoryCount; } // Root + directories, excluding the leaf probe.
    boolean descriptorPoliciesAccepted() { requireCompleted(); return allPoliciesAccepted; } // Ancestors only.
}
