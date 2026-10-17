package dev.p2pkit.rpc.windows.loader;

import java.lang.foreign.Arena;
import java.lang.foreign.FunctionDescriptor;
import java.lang.foreign.Linker;
import java.lang.foreign.MemoryLayout;
import java.lang.foreign.MemorySegment;
import java.lang.foreign.SymbolLookup;
import java.lang.foreign.ValueLayout;
import java.lang.invoke.MethodHandle;
import java.nio.ByteOrder;

/**
 * Dormant fixed-system bootstrap CANDIDATE, not independently established installation/loading authority.
 * The String lookup uses the selected JDK's ordinary Windows LoadLibrary/GetProcAddress implementation.
 * Foundation must first admit that exact runtime and original process startup, including protected launcher
 * and manifests, OS imports, activation/redirection and absence of pre-bootstrap code injection. KnownDLL
 * naming alone is not that guarantee. The later path/PID observations cannot retroactively authorize the
 * first lookup/call. No candidate profile DLL, provider, native registration or storage is entered here.
 */
final class WindowsSystemBootstrapCandidate {
    private static final int PATH_CHARS = 1024;
    private static final MemoryLayout PATH = MemoryLayout.sequenceLayout(PATH_CHARS, ValueLayout.JAVA_SHORT);
    private static final String[] EXPORTS = {
        "GetCurrentProcessId", "GetModuleHandleExW", "GetModuleFileNameW", "GetSystemDirectoryW",
        "GetProcAddress", "LoadLibraryExW", "VirtualQuery", "ReadProcessMemory",
        "CreateFileW", "GetFileInformationByHandleEx", "GetFinalPathNameByHandleW",
        "GetVolumeInformationByHandleW", "GetDriveTypeW", "ReadFile"
    };
    private static final FunctionDescriptor PID = FunctionDescriptor.of(ValueLayout.JAVA_INT);
    // withTargetLayout is restricted in JDK21. Construct these only after inspect's runtime/access guard,
    // never during class initialization of a refused caller.
    private final FunctionDescriptor pinDescriptor = FunctionDescriptor.of(ValueLayout.JAVA_INT,
        ValueLayout.JAVA_INT, ValueLayout.ADDRESS, ValueLayout.ADDRESS.withTargetLayout(ValueLayout.JAVA_LONG));
    private final FunctionDescriptor modulePathDescriptor = FunctionDescriptor.of(ValueLayout.JAVA_INT,
        ValueLayout.ADDRESS, ValueLayout.ADDRESS.withTargetLayout(PATH), ValueLayout.JAVA_INT);
    private final FunctionDescriptor systemPathDescriptor = FunctionDescriptor.of(ValueLayout.JAVA_INT,
        ValueLayout.ADDRESS.withTargetLayout(PATH), ValueLayout.JAVA_INT);

    static final class Failure extends RuntimeException {
        private static final long serialVersionUID = 1L;
        final transient WindowsSystemBootstrapCandidate retainedCandidate;
        Throwable operationFailure;
        final Throwable[] clearFailures = new Throwable[4];
        Throwable arenaCloseFailure;

        private Failure(WindowsSystemBootstrapCandidate candidate) {
            super("Windows system bootstrap candidate failed with ownership retained", null, false, false);
            retainedCandidate = candidate;
        }

        private boolean retirementFailed() {
            if (arenaCloseFailure != null) return true;
            for (int index = 0; index < clearFailures.length; index++) {
                if (clearFailures[index] != null) return true;
            }
            return false;
        }
    }

    private static WindowsSystemBootstrapCandidate processOwner;
    private final Thread thread = Thread.currentThread();
    private final Linker linker;
    private final Failure failure = new Failure(this);
    private final MemorySegment[] entries = new MemorySegment[EXPORTS.length];
    private final long[] rawModules = new long[EXPORTS.length];
    private final MemorySegment[] modules = new MemorySegment[EXPORTS.length];
    private final int[] pinReturns = new int[EXPORTS.length];
    private final int[] pathReturns = new int[EXPORTS.length];
    private final int[] lastErrors = new int[2 + 2 * EXPORTS.length];
    private final boolean[] errorObserved = new boolean[lastErrors.length];
    private final MemorySegment[] buffers = new MemorySegment[4]; // HMODULE, module path, system path, error state
    private Arena originalArena;
    private SymbolLookup lookup;
    private Arena frameArena;
    private MethodHandle pidCall;
    private MethodHandle pinCall;
    private MethodHandle modulePathCall;
    private MethodHandle systemPathCall;
    private long errorOffset;
    private long stateBytes;
    private int pidReturn;
    private int systemPathReturn;
    private long pid;
    private int providers;
    private long kernel32Base;
    private long kernelbaseBase;
    private int phase;
    private boolean nativeReturnUnconfirmed;
    private boolean frameRetired;
    private boolean succeeded;
    private boolean originalJvmAttempted;
    private WindowsOriginalJvmCandidate originalJvm;
    private boolean profileDllAttempted;
    private WindowsOriginalProfileDllFileCandidate profileDll;
    private final Failure systemModulesAttachmentFailure = new Failure(this);
    private boolean systemModulesAttempted;
    private WindowsOriginalSystemModulesCandidate systemModules;
    private boolean importsAttempted;
    private WindowsSystemImportResolution imports;

    private WindowsSystemBootstrapCandidate(Linker linker) { this.linker = linker; }

    static WindowsSystemBootstrapCandidate inspect() {
        WindowsLoaderRuntime.requireDiagnosticRuntime();
        if (Thread.currentThread().isVirtual() ||
            WindowsSystemBootstrapCandidate.class.getModule() != WindowsLoaderRuntime.class.getModule()) {
            throw new IllegalStateException("System bootstrap candidate requires its original platform thread/module");
        }
        // The accepted JDK's nativeLinker path does not invoke defaultLookup/SystemLookup. Verify the actual
        // boot implementation; os.name/os.arch and a caller-selected pathname are not bootstrap authority.
        Linker linker = Linker.nativeLinker();
        if (linker.getClass().getModule() != Object.class.getModule() || linker.getClass().getClassLoader() != null ||
            !linker.getClass().getName().equals("jdk.internal.foreign.abi.x64.windows.Windowsx64Linker") ||
            ValueLayout.ADDRESS.byteSize() != 8 || ValueLayout.JAVA_INT.byteSize() != 4 ||
            ByteOrder.nativeOrder() != ByteOrder.LITTLE_ENDIAN || PATH.byteSize() != 2048) {
            throw new IllegalStateException("System bootstrap candidate requires the actual Windows x64 linker");
        }
        WindowsSystemBootstrapCandidate candidate = new WindowsSystemBootstrapCandidate(linker);
        synchronized (WindowsSystemBootstrapCandidate.class) {
            if (processOwner != null) throw new IllegalStateException("System bootstrap candidate was already attempted");
            processOwner = candidate; // Permanent original owner/failure storage exists BEFORE library effects.
        }
        candidate.observe();
        return candidate;
    }

    private void observe() {
        boolean accepted = false;
        try {
            prepareFrames();
            phase = 1;
            // Only this fixed non-path String is looked up. It is CONDITIONAL on prior startup authority:
            // no java.library.path, SystemRoot, defaultLookup, supplied path or candidate helper is used.
            lookup = SymbolLookup.libraryLookup("kernel32.dll", originalArena);
            for (int index = 0; index < EXPORTS.length; index++) {
                entries[index] = lookup.find(EXPORTS[index]).orElseThrow(
                    () -> new IllegalStateException("Required fixed system export is unavailable"));
                validateEntry(entries[index]);
            }
            pidCall = linker.downcallHandle(entries[0], PID, Linker.Option.captureCallState("GetLastError"));
            pinCall = linker.downcallHandle(entries[1], pinDescriptor, Linker.Option.captureCallState("GetLastError"));
            modulePathCall = linker.downcallHandle(entries[2], modulePathDescriptor,
                Linker.Option.captureCallState("GetLastError"));
            systemPathCall = linker.downcallHandle(entries[3], systemPathDescriptor,
                Linker.Option.captureCallState("GetLastError"));
            phase = 2;
            callProcessId();
            observeError(0);
            pid = Integer.toUnsignedLong(pidReturn);
            if (pid == 0 || pid != ProcessHandle.current().pid()) {
                throw new IllegalStateException("System bootstrap process observation differs");
            }
            buffers[2].fill((byte) 0x7f);
            phase = 3;
            callSystemPath();
            observeError(1);
            int systemLength = validatePath(buffers[2], systemPathReturn);
            // Supported path subset is deliberately absolute ASCII, not locale-sensitive Unicode folding.
            if (systemLength < 3 || !letter(character(buffers[2], 0)) || character(buffers[2], 1) != ':' ||
                character(buffers[2], 2) != '\\' || character(buffers[2], systemLength - 1) == '\\') {
                throw new IllegalStateException("Unsupported original Windows system-directory observation");
            }
            for (int index = 0; index < entries.length; index++) observeProvider(index, systemLength);
            accepted = true;
        } catch (Throwable caught) {
            failure.operationFailure = caught;
        } finally {
            retireFrame();
            succeeded = accepted && frameRetired && !nativeReturnUnconfirmed && !failure.retirementFailed();
        }
        if (!succeeded) throw failure;
    }

    private void prepareFrames() {
        MemoryLayout state = Linker.Option.captureStateLayout();
        MemoryLayout error = state.select(MemoryLayout.PathElement.groupElement("GetLastError"));
        errorOffset = state.byteOffset(MemoryLayout.PathElement.groupElement("GetLastError"));
        stateBytes = state.byteSize();
        if (!(error instanceof ValueLayout.OfInt) || error.byteSize() != 4 || error.byteAlignment() != 4 ||
            stateBytes < 4 || stateBytes > 64 || errorOffset < 0 || errorOffset % 4 != 0 || errorOffset > stateBytes - 4) {
            throw new IllegalStateException("Unsupported captured Windows error layout");
        }
        originalArena = Arena.ofConfined(); // Never closed, even after refusal or ordinary Profile Stop.
        frameArena = Arena.ofConfined();
        buffers[0] = frameArena.allocate(ValueLayout.JAVA_LONG);
        buffers[1] = frameArena.allocate(PATH);
        buffers[2] = frameArena.allocate(PATH);
        buffers[3] = frameArena.allocate(state);
        for (int index = 0; index < buffers.length; index++) {
            MemorySegment buffer = buffers[index];
            long size = index == 0 ? 8 : index == 3 ? stateBytes : PATH.byteSize();
            int alignment = index == 0 ? 8 : index == 3 ? 4 : 2;
            if (!buffer.isNative() || buffer.byteSize() != size || buffer.address() <= 0 ||
                buffer.address() > Long.MAX_VALUE - size || buffer.address() % alignment != 0 ||
                !buffer.scope().equals(frameArena.scope()) || !buffer.isAccessibleBy(thread)) {
                throw new IllegalStateException("Invalid private system observation frame");
            }
            for (int prior = 0; prior < index; prior++) {
                if (overlap(buffer.address(), size, buffers[prior].address(), buffers[prior].byteSize())) {
                    throw new IllegalStateException("System observation frame ranges overlap");
                }
            }
        }
    }

    private void observeProvider(int index, int systemLength) throws Throwable {
        validateEntry(entries[index]);
        buffers[0].fill((byte) 0);
        phase = 4 + index * 2;
        // FROM_ADDRESS | PIN: no arbitrary library-name lookup, and no corresponding FreeLibrary/CloseHandle.
        callProviderPin(index);
        observeError(2 + index * 2);
        long raw = rawModules[index];
        if (pinReturns[index] == 0 || raw <= 0 || (raw & 65_535) != 0 || raw > Long.MAX_VALUE - 65_536) {
            throw new IllegalStateException("Original system provider could not be pinned");
        }
        for (MemorySegment buffer : buffers) {
            if (overlap(raw, 65_536, buffer.address(), buffer.byteSize())) {
                throw new IllegalStateException("System provider aliases a private call frame");
            }
        }
        modules[index] = MemorySegment.ofAddress(raw).reinterpret(originalArena, null);
        buffers[1].fill((byte) 0x7f);
        phase++;
        callModulePath(index);
        observeError(3 + index * 2);
        int length = validatePath(buffers[1], pathReturns[index]);
        if (matchesSystemPath(length, systemLength, "kernel32.dll")) {
            if ((kernel32Base != 0 && kernel32Base != raw) || kernelbaseBase == raw) {
                throw new IllegalStateException("System provider basename has ambiguous original mappings");
            }
            kernel32Base = raw;
        } else if (matchesSystemPath(length, systemLength, "kernelbase.dll")) {
            if ((kernelbaseBase != 0 && kernelbaseBase != raw) || kernel32Base == raw) {
                throw new IllegalStateException("System provider basename has ambiguous original mappings");
            }
            kernelbaseBase = raw;
        } else {
            throw new IllegalStateException("Observed system export has an unsupported physical provider");
        }
        boolean first = true;
        for (int prior = 0; prior < index; prior++) if (rawModules[prior] == raw) first = false;
        if (first && ++providers > 2) throw new IllegalStateException("Ambiguous original system provider inventory");
    }

    // These fixed call sites expose no callback or caller-selected native entry. A thrown downcall
    // leaves its private output frame quarantined; it is not proof that an asynchronous API was used.
    private void requireCallFrame() {
        if (Thread.currentThread() != thread || frameRetired || nativeReturnUnconfirmed) {
            throw new IllegalStateException("System bootstrap call has no available original frame");
        }
    }

    private void callProcessId() throws Throwable {
        requireCallFrame();
        nativeReturnUnconfirmed = true;
        pidReturn = (int) pidCall.invokeExact(buffers[3]);
        nativeReturnUnconfirmed = false;
    }

    private void callSystemPath() throws Throwable {
        requireCallFrame();
        nativeReturnUnconfirmed = true;
        systemPathReturn = (int) systemPathCall.invokeExact(buffers[3], buffers[2], PATH_CHARS);
        nativeReturnUnconfirmed = false;
    }

    private void callProviderPin(int index) throws Throwable {
        requireCallFrame();
        nativeReturnUnconfirmed = true;
        pinReturns[index] = (int) pinCall.invokeExact(buffers[3], 0x00000005, entries[index], buffers[0]);
        // Preserve the permanent PIN result before error decoding or allocating any pointer view.
        rawModules[index] = buffers[0].get(ValueLayout.JAVA_LONG, 0);
        nativeReturnUnconfirmed = false;
    }

    private void callModulePath(int index) throws Throwable {
        requireCallFrame();
        nativeReturnUnconfirmed = true;
        pathReturns[index] = (int) modulePathCall.invokeExact(buffers[3], modules[index], buffers[1], PATH_CHARS);
        nativeReturnUnconfirmed = false;
    }

    private void validateEntry(MemorySegment entry) {
        if (entry == null || !entry.isNative() || entry.byteSize() != 0 || entry.address() <= 65_535 ||
            entry.address() > Long.MAX_VALUE - 1 || !entry.scope().equals(originalArena.scope()) || !entry.scope().isAlive() ||
            !entry.isAccessibleBy(thread)) {
            throw new IllegalStateException("Invalid original system export observation");
        }
        for (MemorySegment buffer : buffers) {
            if (overlap(entry.address(), 1, buffer.address(), buffer.byteSize())) {
                throw new IllegalStateException("System export aliases a private call frame");
            }
        }
    }

    private void observeError(int index) {
        lastErrors[index] = buffers[3].get(ValueLayout.JAVA_INT, errorOffset);
        errorObserved[index] = true; // Success permits stale error state; zero is not an acceptance criterion.
    }

    private static int validatePath(MemorySegment buffer, int returned) {
        long count = Integer.toUnsignedLong(returned);
        if (count == 0 || count >= PATH_CHARS || character(buffer, (int) count) != 0) {
            throw new IllegalStateException("System pathname observation is incomplete");
        }
        for (int index = 0; index < count; index++) {
            char value = character(buffer, index);
            if (value < 32 || value > 126 || value == '/') {
                throw new IllegalStateException("Unsupported system pathname representation");
            }
        }
        return (int) count;
    }

    private boolean matchesSystemPath(int moduleLength, int systemLength, String name) {
        if (moduleLength != systemLength + 1 + name.length()) return false;
        for (int index = 0; index < systemLength; index++) {
            if (fold(character(buffers[1], index)) != fold(character(buffers[2], index))) return false;
        }
        if (character(buffers[1], systemLength) != '\\') return false;
        for (int index = 0; index < name.length(); index++) {
            if (fold(character(buffers[1], systemLength + 1 + index)) != name.charAt(index)) return false;
        }
        return true;
    }

    private static char character(MemorySegment buffer, int index) {
        return (char) Short.toUnsignedInt(buffer.getAtIndex(ValueLayout.JAVA_SHORT, index));
    }
    private static boolean letter(char value) { return value >= 'A' && value <= 'Z' || value >= 'a' && value <= 'z'; }
    private static char fold(char value) { return value >= 'A' && value <= 'Z' ? (char) (value + ('a' - 'A')) : value; }
    private static boolean overlap(long first, long count, long second, long size) {
        return first < second + size && second < first + count;
    }

    private void retireFrame() {
        if (Thread.currentThread() != thread) throw new IllegalStateException("System bootstrap frame belongs to another thread");
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
    }

    private void requireCompleted() {
        if (Thread.currentThread() != thread || !succeeded || !frameRetired || nativeReturnUnconfirmed || originalArena == null ||
            !originalArena.scope().isAlive()) {
            throw new IllegalStateException("System bootstrap candidate has no completed observation on this thread");
        }
    }

    long processId() { requireCompleted(); return pid; }
    int observedProviderCount() { requireCompleted(); return providers; }
    boolean completed() { requireCompleted(); return true; }

    WindowsOriginalJvmCandidate inspectOriginalJvm() {
        requireCompleted();
        if (originalJvmAttempted) throw new IllegalStateException("Original JVM candidate was already attempted");
        originalJvmAttempted = true;
        originalJvm = new WindowsOriginalJvmCandidate(this, linker, originalArena, entries[1], entries[2], entries[4]);
        originalJvm.observe();
        return originalJvm;
    }

    WindowsOriginalProfileDllFileCandidate inspectOriginalProfileDll(String candidatePath) {
        requireCompleted();
        if (profileDllAttempted) throw new IllegalStateException("Original profile DLL file was already attempted");
        profileDllAttempted = true;
        profileDll = new WindowsOriginalProfileDllFileCandidate(this, candidatePath);
        // The original facade and its failure carrier are rooted BEFORE validation or file acquisition.
        // The locator is comparison/input data only, never approved package/startup authority.
        profileDll.observe();
        return profileDll;
    }

    void requireOriginalProfileDll(WindowsOriginalProfileDllFileCandidate candidate) {
        requireCompleted();
        if (candidate == null || profileDll != candidate) {
            throw new IllegalStateException("Profile DLL file is not this bootstrap's original retained attachment");
        }
    }

    Linker originalProfileDllLinker(WindowsOriginalProfileDllFileCandidate candidate) {
        requireOriginalProfileDll(candidate);
        candidate.requireOriginalNativeInputs();
        return linker;
    }

    Arena originalProfileDllArena(WindowsOriginalProfileDllFileCandidate candidate) {
        requireOriginalProfileDll(candidate);
        candidate.requireOriginalNativeInputs();
        return originalArena;
    }

    MemorySegment originalProfileDllFileEntry(WindowsOriginalProfileDllFileCandidate candidate, int index) {
        requireOriginalProfileDll(candidate);
        candidate.requireOriginalNativeInputs();
        if (index < 0 || index > 2) throw new IllegalArgumentException("Unknown fixed profile DLL file entry");
        return entries[8 + index]; // CreateFileW, GetFileInformationByHandleEx, GetFinalPathNameByHandleW only.
    }

    MemorySegment originalProfileDllSecurityEntry(WindowsOriginalProfileDllFileCandidate candidate, int index) {
        requireOriginalProfileDll(candidate);
        candidate.requireOriginalNativeInputs();
        if (index < 0 || index > 3) throw new IllegalArgumentException("Unknown fixed profile DLL security entry");
        return entries[1 + index]; // PIN, module pathname, system directory, exact named export resolution only.
    }

    MemorySegment originalProfileDllAncestorsEntry(WindowsOriginalProfileDllFileCandidate candidate, int index) {
        requireOriginalProfileDll(candidate);
        candidate.requireOriginalNativeInputs();
        if (index < 0 || index > 1) throw new IllegalArgumentException("Unknown fixed profile DLL ancestors entry");
        return entries[11 + index]; // GetVolumeInformationByHandleW and GetDriveTypeW only.
    }

    MemorySegment originalProfileDllReadEntry(WindowsOriginalProfileDllFileCandidate candidate) {
        requireOriginalProfileDll(candidate);
        candidate.requireOriginalByteInputs();
        return entries[13]; // Exact original ReadFile; no supplied export selector or alternate channel.
    }

    WindowsOriginalSystemModulesCandidate inspectOriginalSystemModules() {
        requireCompleted();
        if (systemModulesAttempted) throw new IllegalStateException("Original system modules were already attempted");
        systemModulesAttempted = true;
        try {
            systemModules = new WindowsOriginalSystemModulesCandidate(this);
        } catch (Throwable caught) {
            systemModulesAttachmentFailure.operationFailure = caught;
            throw systemModulesAttachmentFailure;
        }
        systemModules.observe();
        return systemModules;
    }

    void requireOriginalSystemModules(WindowsOriginalSystemModulesCandidate candidate) {
        requireCompleted();
        if (candidate == null || candidate != systemModules) {
            throw new IllegalStateException("System modules are not this bootstrap's original retained attachment");
        }
    }

    Linker originalSystemModulesLinker(WindowsOriginalSystemModulesCandidate candidate) {
        requireOriginalSystemModules(candidate); candidate.requireOriginalNativeInputs(); return linker;
    }
    Arena originalSystemModulesArena(WindowsOriginalSystemModulesCandidate candidate) {
        requireOriginalSystemModules(candidate); candidate.requireOriginalNativeInputs(); return originalArena;
    }
    MemorySegment originalSystemModulesObservationEntry(WindowsOriginalSystemModulesCandidate candidate, int index) {
        requireOriginalSystemModules(candidate); candidate.requireOriginalNativeInputs();
        if (index < 0 || index > 2) throw new IllegalArgumentException("Unknown fixed system module observation entry");
        return entries[1 + index]; // GetModuleHandleExW/PIN, GetModuleFileNameW, GetSystemDirectoryW only.
    }
    MemorySegment originalSystemModuleFileEntry(WindowsOriginalSystemModulesCandidate candidate, int index) {
        requireOriginalSystemModules(candidate); candidate.requireOriginalNativeInputs();
        if (index < 0 || index > 2) throw new IllegalArgumentException("Unknown fixed system module file entry");
        return entries[8 + index];
    }
    MemorySegment originalSystemModuleSecurityEntry(WindowsOriginalSystemModulesCandidate candidate, int index) {
        requireOriginalSystemModules(candidate); candidate.requireOriginalNativeInputs();
        if (index < 0 || index > 3) throw new IllegalArgumentException("Unknown fixed system module security entry");
        return entries[1 + index];
    }
    MemorySegment originalSystemModuleAncestorsEntry(WindowsOriginalSystemModulesCandidate candidate, int index) {
        requireOriginalSystemModules(candidate); candidate.requireOriginalNativeInputs();
        if (index < 0 || index > 1) throw new IllegalArgumentException("Unknown fixed system module ancestor entry");
        return entries[11 + index];
    }
    MemorySegment originalSystemModuleReadEntry(WindowsOriginalSystemModulesCandidate candidate) {
        requireOriginalSystemModules(candidate); candidate.requireOriginalNativeInputs(); return entries[13];
    }

    WindowsSystemImportResolution resolveSystemImports(WindowsPackagedVerifier plan) {
        requireCompleted();
        if (importsAttempted) throw new IllegalStateException("System imports were already attempted");
        importsAttempted = true;
        imports = new WindowsSystemImportResolution(this, plan, linker, originalArena,
            entries[1], entries[2], entries[3], entries[4]);
        // The exact typed attachment permanently roots the original plan, scopes and failure carrier
        // BEFORE the first resolver native effect. The plan is comparison data, not startup authority.
        imports.observe();
        return imports;
    }

    void requireOriginalImports(WindowsSystemImportResolution candidate) {
        requireCompleted();
        if (candidate == null || imports != candidate) {
            throw new IllegalStateException("System imports are not this bootstrap's retained attachment");
        }
    }

    void requireOriginalJvm(WindowsOriginalJvmCandidate candidate) {
        requireCompleted();
        if (candidate == null || originalJvm != candidate) {
            throw new IllegalStateException("Original JVM candidate is not this bootstrap's retained attachment");
        }
    }

    MemorySegment originalJvmFileEntry(WindowsOriginalJvmCandidate candidate, int index) {
        requireOriginalJvm(candidate);
        if (index < 0 || index > 2) throw new IllegalArgumentException("Unknown fixed JVM file entry");
        return entries[8 + index];
    }

    MemorySegment originalJvmSecurityEntry(WindowsOriginalJvmCandidate candidate, int index) {
        requireOriginalJvm(candidate);
        if (index < 0 || index > 3) throw new IllegalArgumentException("Unknown fixed JVM security entry");
        return entries[1 + index]; // PIN, module pathname, system directory, exact named export resolution.
    }

    MemorySegment originalJvmAncestorsEntry(WindowsOriginalJvmCandidate candidate, int index) {
        requireOriginalJvm(candidate);
        if (index < 0 || index > 1) throw new IllegalArgumentException("Unknown fixed JVM ancestors entry");
        return entries[11 + index];
    }

    MemorySegment originalJvmReadEntry(WindowsOriginalJvmCandidate candidate) {
        requireOriginalJvm(candidate);
        return entries[13];
    }
}
