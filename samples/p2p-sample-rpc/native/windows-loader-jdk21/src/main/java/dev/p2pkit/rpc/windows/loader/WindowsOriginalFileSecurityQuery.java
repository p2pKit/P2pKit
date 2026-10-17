package dev.p2pkit.rpc.windows.loader;

import java.lang.foreign.Arena;
import java.lang.foreign.FunctionDescriptor;
import java.lang.foreign.Linker;
import java.lang.foreign.MemoryLayout;
import java.lang.foreign.MemorySegment;
import java.lang.foreign.ValueLayout;
import java.lang.invoke.MethodHandle;
import java.util.Arrays;

/**
 * Shared bounded OWNER|DACL query for three concrete original file/security chains, not installation authority.
 * Uses only fixed already-loaded ntdll.dll and NtQuerySecurityObject. No explicit DLL-loading API is
 * called; GetProcAddress forwarding may have implicit loader effects before the same-provider check.
 * Original startup/system-runtime/export authority must therefore precede productive use. A successful
 * query and even accepted FILE policy do not establish ancestor custody, SACL/MIC, mapped-file identity,
 * pre-existing mapping/handle safety, runtime provenance or complete installed-application admission.
 */
final class WindowsOriginalFileSecurityQuery {
    private static final int PATH_CHARS = 1024;
    private static final int MAXIMUM_DESCRIPTOR_BYTES = 65_536;
    private static final String MODULE_NAME = "ntdll.dll";
    private static final String EXPORT_NAME = "NtQuerySecurityObject";
    private static final MemoryLayout PATH = MemoryLayout.sequenceLayout(PATH_CHARS, ValueLayout.JAVA_SHORT);
    private static final MemoryLayout NAME = MemoryLayout.sequenceLayout(MODULE_NAME.length() + 1, ValueLayout.JAVA_SHORT);
    private static final MemoryLayout EXPORT = MemoryLayout.sequenceLayout(EXPORT_NAME.length() + 1, ValueLayout.JAVA_BYTE);
    private static final MemoryLayout DESCRIPTOR =
        MemoryLayout.sequenceLayout(MAXIMUM_DESCRIPTOR_BYTES, ValueLayout.JAVA_BYTE).withByteAlignment(4);

    static final class Failure extends RuntimeException {
        private static final long serialVersionUID = 1L;
        final transient WindowsOriginalFileSecurityQuery retainedCandidate;
        Throwable operationFailure;
        final Throwable[] clearFailures = new Throwable[8];
        Throwable arenaCloseFailure;

        private Failure(WindowsOriginalFileSecurityQuery candidate) {
            super("Original JVM file security query failed with original ownership retained", null, false, false);
            retainedCandidate = candidate;
        }

        private boolean retirementFailed() {
            if (arenaCloseFailure != null) return true;
            for (Throwable clearFailure : clearFailures) if (clearFailure != null) return true;
            return false;
        }
    }

    private final Thread thread = Thread.currentThread();
    private final WindowsOriginalJvmSecurityCandidate originalJvmOwner;
    private final WindowsOriginalProfileDllSecurityCandidate originalProfileDllOwner;
    private final WindowsOriginalSystemModuleCandidate originalSystemOwner;
    private final Linker linker;
    private final Arena bootstrapArena;
    private final Arena fileArena;
    private final MemorySegment fileHandle;
    private final MemorySegment pinEntry;
    private final MemorySegment pathEntry;
    private final MemorySegment systemPathEntry;
    private final MemorySegment resolveEntry;
    private final Failure failure = new Failure(this);
    // HMODULE, module/system paths, fixed module/export names, Windows error, descriptor, ULONG length.
    private final MemorySegment[] buffers = new MemorySegment[8];
    private final int[] lastErrors = new int[5];
    private final boolean[] errorObserved = new boolean[5];
    private final byte[] preservedDescriptor = new byte[MAXIMUM_DESCRIPTOR_BYTES];
    private byte[] exactDescriptor;
    private Arena moduleArena;
    private Arena frameArena;
    private MethodHandle pinCall;
    private MethodHandle pathCall;
    private MethodHandle systemPathCall;
    private MethodHandle resolveCall;
    private MethodHandle queryCall;
    private long rawModule;
    private long rawProvider;
    private long rawEntry;
    private MemorySegment returnedModule;
    private MemorySegment returnedProvider;
    private MemorySegment returnedEntry;
    private MemorySegment module;
    private MemorySegment entry;
    private long errorOffset;
    private long stateBytes;
    private int modulePinReturn;
    private int modulePathReturn;
    private int systemPathReturn;
    private int providerPinReturn;
    private int ntStatus;
    private int requiredLength;
    private int phase;
    private boolean ntReturned;
    private boolean policyEvaluated;
    private boolean policyAccepted;
    private boolean attempted;
    private boolean frameRetired;
    private boolean nativeReturnUnconfirmed;
    private boolean succeeded;

    WindowsOriginalFileSecurityQuery(WindowsOriginalJvmSecurityCandidate owner, Linker linker,
        Arena bootstrapArena, Arena fileArena, MemorySegment fileHandle, MemorySegment pinEntry,
        MemorySegment pathEntry, MemorySegment systemPathEntry, MemorySegment resolveEntry) {
        this(owner, null, null, linker, bootstrapArena, fileArena, fileHandle, pinEntry, pathEntry, systemPathEntry, resolveEntry);
    }

    static WindowsOriginalFileSecurityQuery forProfileDll(WindowsOriginalProfileDllSecurityCandidate owner,
        Linker linker, Arena bootstrapArena, Arena fileArena, MemorySegment fileHandle, MemorySegment pinEntry,
        MemorySegment pathEntry, MemorySegment systemPathEntry, MemorySegment resolveEntry) {
        if (owner == null) throw new IllegalArgumentException("Missing original profile DLL security owner");
        return new WindowsOriginalFileSecurityQuery(null, owner, null, linker, bootstrapArena, fileArena, fileHandle,
            pinEntry, pathEntry, systemPathEntry, resolveEntry);
    }

    static WindowsOriginalFileSecurityQuery forSystemModule(WindowsOriginalSystemModuleCandidate owner,
        Linker linker, Arena bootstrapArena, Arena fileArena, MemorySegment fileHandle, MemorySegment pinEntry,
        MemorySegment pathEntry, MemorySegment systemPathEntry, MemorySegment resolveEntry) {
        if (owner == null) throw new IllegalArgumentException("Missing original system module security owner");
        return new WindowsOriginalFileSecurityQuery(null, null, owner, linker, bootstrapArena, fileArena, fileHandle,
            pinEntry, pathEntry, systemPathEntry, resolveEntry);
    }

    private WindowsOriginalFileSecurityQuery(WindowsOriginalJvmSecurityCandidate jvm,
        WindowsOriginalProfileDllSecurityCandidate dll, WindowsOriginalSystemModuleCandidate system,
        Linker linker, Arena bootstrapArena, Arena fileArena,
        MemorySegment fileHandle, MemorySegment pinEntry, MemorySegment pathEntry, MemorySegment systemPathEntry,
        MemorySegment resolveEntry) {
        originalJvmOwner = jvm;
        originalProfileDllOwner = dll;
        originalSystemOwner = system;
        // Inputs come only from the original lease's three concrete, guarded child factories.
        // No caller-facing raw HANDLE, export, permission or descriptor-kind selection exists.
        this.linker = linker;
        this.bootstrapArena = bootstrapArena;
        this.fileArena = fileArena;
        this.fileHandle = fileHandle;
        this.pinEntry = pinEntry;
        this.pathEntry = pathEntry;
        this.systemPathEntry = systemPathEntry;
        this.resolveEntry = resolveEntry;
    }

    void observe() {
        requireOriginalFile();
        if (attempted) throw new IllegalStateException("Original JVM security query is already consumed");
        attempted = true;
        boolean accepted = false;
        try {
            prepareFrame();
            phase = 1;
            buffers[0].fill((byte) 0);
            nativeReturnUnconfirmed = true;
            modulePinReturn = (int) pinCall.invokeExact(buffers[5], 0x00000001, buffers[3], buffers[0]);
            nativeReturnUnconfirmed = false;
            rawModule = buffers[0].get(ValueLayout.JAVA_LONG, 0); // Retain PIN effect before wrapper allocation.
            returnedModule = buffers[0].get(ValueLayout.ADDRESS, 0);
            observeError(0);
            validateModule(returnedModule, modulePinReturn);
            module = returnedModule.reinterpret(moduleArena, null);
            if (originalSystemOwner != null) originalSystemOwner.requireOriginalQueryProvider(this, rawModule);
            phase = 2;
            buffers[1].fill((byte) 0x7f);
            nativeReturnUnconfirmed = true;
            modulePathReturn = (int) pathCall.invokeExact(buffers[5], module, buffers[1], PATH_CHARS);
            nativeReturnUnconfirmed = false;
            observeError(1);
            buffers[2].fill((byte) 0x7f);
            nativeReturnUnconfirmed = true;
            systemPathReturn = (int) systemPathCall.invokeExact(buffers[5], buffers[2], PATH_CHARS);
            nativeReturnUnconfirmed = false;
            observeError(2);
            validateSystemModulePath();
            phase = 3;
            nativeReturnUnconfirmed = true;
            rawEntry = (long) resolveCall.invokeExact(buffers[5], module, buffers[4]);
            nativeReturnUnconfirmed = false; // Retain exact Windows x64 return bits before wrapper allocation.
            returnedEntry = MemorySegment.ofAddress(rawEntry);
            observeError(3);
            validateReturnedEntry();
            entry = returnedEntry.reinterpret(moduleArena, null);
            phase = 4;
            buffers[0].fill((byte) 0);
            nativeReturnUnconfirmed = true;
            providerPinReturn = (int) pinCall.invokeExact(buffers[5], 0x00000005, entry, buffers[0]);
            nativeReturnUnconfirmed = false;
            rawProvider = buffers[0].get(ValueLayout.JAVA_LONG, 0);
            returnedProvider = buffers[0].get(ValueLayout.ADDRESS, 0);
            observeError(4);
            validateModule(returnedProvider, providerPinReturn);
            if (rawProvider != rawModule) {
                throw new IllegalStateException("Original security export resolved to another physical provider");
            }
            requireOriginalFile();
            if (originalSystemOwner != null) originalSystemOwner.requireOriginalQueryProvider(this, rawModule);
            FunctionDescriptor query = FunctionDescriptor.of(ValueLayout.JAVA_INT, ValueLayout.ADDRESS,
                ValueLayout.JAVA_INT, ValueLayout.ADDRESS.withTargetLayout(DESCRIPTOR), ValueLayout.JAVA_INT,
                ValueLayout.ADDRESS.withTargetLayout(ValueLayout.JAVA_INT));
            queryCall = linker.downcallHandle(entry, query);
            buffers[6].fill((byte) 0);
            buffers[7].fill((byte) 0xff);
            phase = 5;
            // READ_CONTROL already belongs to the original file lease. OWNER|DACL == 5 requests no SACL
            // or privilege. NTSTATUS, not GetLastError, is authoritative for this one bounded NT call.
            nativeReturnUnconfirmed = true;
            ntStatus = (int) queryCall.invokeExact(fileHandle, 5, buffers[6], MAXIMUM_DESCRIPTOR_BYTES, buffers[7]);
            nativeReturnUnconfirmed = false;
            ntReturned = true;
            requiredLength = buffers[7].get(ValueLayout.JAVA_INT, 0);
            preserveDescriptor();
            requireOriginalFile();
            accepted = true;
        } catch (Throwable caught) {
            failure.operationFailure = caught;
        } finally {
            retireFrame();
            succeeded = accepted && frameRetired && !nativeReturnUnconfirmed && !failure.retirementFailed();
        }
        if (!succeeded) throw failure;
    }

    private void preserveDescriptor() {
        long length = Integer.toUnsignedLong(requiredLength);
        if (ntStatus != 0 || length < 20 || length > MAXIMUM_DESCRIPTOR_BYTES) {
            throw new IllegalStateException("Original JVM security descriptor query is incomplete");
        }
        MemorySegment.copy(buffers[6], ValueLayout.JAVA_BYTE, 0, preservedDescriptor, 0, requiredLength);
        exactDescriptor = Arrays.copyOf(preservedDescriptor, requiredLength);
        phase = 6;
        try {
            WindowsInstallationSecurity.require(exactDescriptor, WindowsInstallationSecurity.Kind.FILE);
            policyAccepted = true;
        } catch (IllegalArgumentException refused) {
            // Ordinary binary-policy refusal is distinct from native-query or owner-retirement failure.
            policyAccepted = false;
        }
        policyEvaluated = true;
    }

    private void prepareFrame() {
        MemoryLayout state = Linker.Option.captureStateLayout();
        MemoryLayout error = state.select(MemoryLayout.PathElement.groupElement("GetLastError"));
        errorOffset = state.byteOffset(MemoryLayout.PathElement.groupElement("GetLastError"));
        stateBytes = state.byteSize();
        if (!(error instanceof ValueLayout.OfInt) || error.byteSize() != 4 || error.byteAlignment() != 4 ||
            stateBytes < 4 || stateBytes > 64 || errorOffset < 0 || errorOffset % 4 != 0 || errorOffset > stateBytes - 4) {
            throw new IllegalStateException("Unsupported original security captured-error layout");
        }
        // All restricted layouts/downcalls follow the exact completed original file/bootstrap guard.
        FunctionDescriptor pin = FunctionDescriptor.of(ValueLayout.JAVA_INT, ValueLayout.JAVA_INT,
            ValueLayout.ADDRESS, ValueLayout.ADDRESS.withTargetLayout(ValueLayout.JAVA_LONG));
        FunctionDescriptor path = FunctionDescriptor.of(ValueLayout.JAVA_INT, ValueLayout.ADDRESS,
            ValueLayout.ADDRESS.withTargetLayout(PATH), ValueLayout.JAVA_INT);
        FunctionDescriptor systemPath = FunctionDescriptor.of(ValueLayout.JAVA_INT,
            ValueLayout.ADDRESS.withTargetLayout(PATH), ValueLayout.JAVA_INT);
        FunctionDescriptor resolve = FunctionDescriptor.of(ValueLayout.JAVA_LONG, ValueLayout.ADDRESS,
            ValueLayout.ADDRESS.withTargetLayout(EXPORT));
        pinCall = linker.downcallHandle(pinEntry, pin, Linker.Option.captureCallState("GetLastError"));
        pathCall = linker.downcallHandle(pathEntry, path, Linker.Option.captureCallState("GetLastError"));
        systemPathCall = linker.downcallHandle(systemPathEntry, systemPath, Linker.Option.captureCallState("GetLastError"));
        resolveCall = linker.downcallHandle(resolveEntry, resolve, Linker.Option.captureCallState("GetLastError"));
        moduleArena = Arena.ofConfined(); // Permanent actual ntdll/module-entry ownership; no unload/closure.
        frameArena = Arena.ofConfined();
        buffers[0] = frameArena.allocate(ValueLayout.JAVA_LONG);
        buffers[1] = frameArena.allocate(PATH);
        buffers[2] = frameArena.allocate(PATH);
        buffers[3] = frameArena.allocate(NAME);
        buffers[4] = frameArena.allocate(EXPORT);
        buffers[5] = frameArena.allocate(state);
        buffers[6] = frameArena.allocate(DESCRIPTOR);
        buffers[7] = frameArena.allocate(ValueLayout.JAVA_INT);
        for (int index = 0; index < buffers.length; index++) {
            MemorySegment buffer = buffers[index];
            long size = index == 0 ? 8 : index == 1 || index == 2 ? PATH.byteSize() : index == 3 ? NAME.byteSize() :
                index == 4 ? EXPORT.byteSize() : index == 5 ? stateBytes : index == 6 ? MAXIMUM_DESCRIPTOR_BYTES : 4;
            int alignment = index == 0 ? 8 : index < 4 ? 2 : index == 4 ? 1 : 4;
            if (!buffer.isNative() || buffer.byteSize() != size || buffer.address() <= 65_535 ||
                buffer.address() > Long.MAX_VALUE - size || buffer.address() % alignment != 0 ||
                !buffer.scope().equals(frameArena.scope()) || !buffer.isAccessibleBy(thread)) {
                throw new IllegalStateException("Invalid original security private frame");
            }
            for (int prior = 0; prior < index; prior++) {
                if (overlap(buffer.address(), size, buffers[prior].address(), buffers[prior].byteSize())) {
                    throw new IllegalStateException("Original security private frame ranges overlap");
                }
            }
            if (overlap(fileHandle.address(), 1, buffer.address(), size) ||
                overlap(pinEntry.address(), 1, buffer.address(), size) ||
                overlap(pathEntry.address(), 1, buffer.address(), size) ||
                overlap(systemPathEntry.address(), 1, buffer.address(), size) ||
                overlap(resolveEntry.address(), 1, buffer.address(), size)) {
                throw new IllegalStateException("Original security owner aliases a private frame");
            }
        }
        buffers[3].fill((byte) 0);
        for (int index = 0; index < MODULE_NAME.length(); index++) {
            buffers[3].setAtIndex(ValueLayout.JAVA_SHORT, index, (short) MODULE_NAME.charAt(index));
        }
        buffers[4].fill((byte) 0);
        for (int index = 0; index < EXPORT_NAME.length(); index++) {
            buffers[4].setAtIndex(ValueLayout.JAVA_BYTE, index, (byte) EXPORT_NAME.charAt(index));
        }
    }

    private void requireOriginalFile() {
        if (Thread.currentThread() != thread || ((originalJvmOwner == null ? 0 : 1) + (originalProfileDllOwner == null ? 0 : 1) +
            (originalSystemOwner == null ? 0 : 1) != 1)) {
            throw new IllegalStateException("Original JVM security requires its original platform thread");
        }
        if (originalJvmOwner != null) originalJvmOwner.requireOriginalQuery(this);
        else if (originalProfileDllOwner != null) originalProfileDllOwner.requireOriginalQuery(this);
        else originalSystemOwner.requireOriginalQuery(this);
        if (bootstrapArena == null || !bootstrapArena.scope().isAlive() || fileArena == null ||
            !fileArena.scope().isAlive() || fileHandle == null || !fileHandle.isNative() ||
            fileHandle.byteSize() != 0 || fileHandle.address() <= 0 ||
            !fileHandle.scope().equals(fileArena.scope()) || !fileHandle.isAccessibleBy(thread)) {
            throw new IllegalStateException("Original JVM security lost its original file or bootstrap owner");
        }
        validateSystemEntry(pinEntry);
        validateSystemEntry(pathEntry);
        validateSystemEntry(systemPathEntry);
        validateSystemEntry(resolveEntry);
    }

    private void validateSystemEntry(MemorySegment observed) {
        if (observed == null || !observed.isNative() || observed.byteSize() != 0 || observed.address() <= 65_535 ||
            observed.address() > Long.MAX_VALUE - 1 || !observed.scope().equals(bootstrapArena.scope()) ||
            !observed.scope().isAlive() || !observed.isAccessibleBy(thread)) {
            throw new IllegalStateException("Original JVM security lost a scoped system entry");
        }
    }

    private void validateModule(MemorySegment observed, int returned) {
        if (returned == 0 || observed == null || !observed.isNative() || observed.byteSize() != 0 ||
            observed.address() <= 0 || (observed.address() & 65_535) != 0 ||
            observed.address() > Long.MAX_VALUE - 65_536) {
            throw new IllegalStateException("Original security module could not be pinned");
        }
        for (MemorySegment buffer : buffers) {
            if (overlap(observed.address(), 65_536, buffer.address(), buffer.byteSize())) {
                throw new IllegalStateException("Original security module aliases a private frame");
            }
        }
    }

    private void validateReturnedEntry() {
        if (returnedEntry == null || !returnedEntry.isNative() || returnedEntry.byteSize() != 0 ||
            returnedEntry.address() <= 65_535 || returnedEntry.address() > Long.MAX_VALUE - 1) {
            throw new IllegalStateException("Original security export is unavailable");
        }
        for (MemorySegment buffer : buffers) {
            if (overlap(returnedEntry.address(), 1, buffer.address(), buffer.byteSize())) {
                throw new IllegalStateException("Original security export aliases a private frame");
            }
        }
    }

    private void validateSystemModulePath() {
        int moduleLength = validatePath(buffers[1], modulePathReturn);
        int systemLength = validatePath(buffers[2], systemPathReturn);
        if (systemLength < 3 || !letter(character(buffers[2], 0)) || character(buffers[2], 1) != ':' ||
            character(buffers[2], 2) != '\\' || character(buffers[2], systemLength - 1) == '\\' ||
            moduleLength != systemLength + 1 + MODULE_NAME.length()) {
            throw new IllegalStateException("Original security module has an unsupported system pathname");
        }
        for (int index = 0; index < systemLength; index++) {
            if (fold(character(buffers[1], index)) != fold(character(buffers[2], index))) {
                throw new IllegalStateException("Original security module differs from the system directory");
            }
        }
        if (character(buffers[1], systemLength) != '\\') {
            throw new IllegalStateException("Original security module pathname boundary differs");
        }
        for (int index = 0; index < MODULE_NAME.length(); index++) {
            if (fold(character(buffers[1], systemLength + 1 + index)) != MODULE_NAME.charAt(index)) {
                throw new IllegalStateException("Original security module basename differs");
            }
        }
    }

    private static int validatePath(MemorySegment buffer, int returned) {
        long count = Integer.toUnsignedLong(returned);
        if (count == 0 || count >= PATH_CHARS || character(buffer, (int) count) != 0) {
            throw new IllegalStateException("Original security pathname observation is incomplete");
        }
        for (int index = 0; index < count; index++) {
            char value = character(buffer, index);
            if (value < 32 || value > 126 || value == '/') {
                throw new IllegalStateException("Unsupported original security pathname representation");
            }
        }
        return (int) count;
    }

    private static char character(MemorySegment buffer, int index) {
        return (char) Short.toUnsignedInt(buffer.getAtIndex(ValueLayout.JAVA_SHORT, index));
    }
    private static boolean letter(char value) { return value >= 'A' && value <= 'Z' || value >= 'a' && value <= 'z'; }
    private static char fold(char value) { return value >= 'A' && value <= 'Z' ? (char) (value + ('a' - 'A')) : value; }
    private static boolean overlap(long first, long count, long second, long size) {
        return first < second + size && second < first + count;
    }
    private void observeError(int index) {
        lastErrors[index] = buffers[5].get(ValueLayout.JAVA_INT, errorOffset);
        errorObserved[index] = true; // Only the five Win32 calls use captured GetLastError, never the NT query.
    }

    private void retireFrame() {
        // Conservative missing-return evidence gate, not a claim of asynchronous NT/Win32 I/O.
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
        // Original file HANDLE, module pins, entry scopes and all their original owners remain retained.
    }

    private void requireCompleted() {
        requireOriginalFile();
        if (!succeeded || !frameRetired || nativeReturnUnconfirmed || !ntReturned || ntStatus != 0 || !policyEvaluated ||
            exactDescriptor == null || moduleArena == null || !moduleArena.scope().isAlive() || entry == null ||
            !entry.scope().equals(moduleArena.scope()) || !entry.isAccessibleBy(thread)) {
            throw new IllegalStateException("Original JVM security has no completed observation");
        }
    }

    boolean completed() { requireCompleted(); return true; }
    boolean descriptorPolicyAccepted() { requireCompleted(); return policyAccepted; }

    WindowsOriginalFileAncestorsLease newSystemModuleAncestors(WindowsOriginalSystemModuleCandidate requester) {
        if (requester == null || requester != originalSystemOwner) {
            throw new IllegalStateException("Original security query belongs to another system module");
        }
        requireCompleted();
        requester.requireOriginalQueryProvider(this, rawModule);
        return requester.newOriginalAncestors(this, moduleArena, module, entry, pinEntry, resolveEntry);
    }

    WindowsOriginalJvmAncestorsCandidate newJvmAncestors(WindowsOriginalJvmSecurityCandidate requester) {
        if (requester == null || requester != originalJvmOwner) {
            throw new IllegalStateException("Original security query belongs to another JVM facade");
        }
        requireCompleted();
        return requester.newOriginalAncestors(this, moduleArena, module, entry, pinEntry, resolveEntry);
    }

    WindowsOriginalProfileDllAncestorsCandidate newProfileDllAncestors(
        WindowsOriginalProfileDllSecurityCandidate requester) {
        if (requester == null || requester != originalProfileDllOwner) {
            throw new IllegalStateException("Original security query belongs to another profile DLL facade");
        }
        requireCompleted();
        return requester.newOriginalAncestors(this, moduleArena, module, entry, pinEntry, resolveEntry);
    }
}
