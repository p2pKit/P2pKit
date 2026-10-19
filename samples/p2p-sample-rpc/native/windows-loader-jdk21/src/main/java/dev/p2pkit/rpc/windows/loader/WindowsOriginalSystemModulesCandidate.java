package dev.p2pkit.rpc.windows.loader;

import java.lang.foreign.Arena;
import java.lang.foreign.FunctionDescriptor;
import java.lang.foreign.Linker;
import java.lang.foreign.MemoryLayout;
import java.lang.foreign.MemorySegment;
import java.lang.foreign.ValueLayout;
import java.lang.invoke.MethodHandle;

/**
 * Fixed already-loaded nine-module observation cohort, never an OS-provider admission allowlist.
 * PIN/path observations do NOT associate the later disk HANDLE with the original mapped image section.
 * The original conditional bootstrap calls, ntdll GPA/query and startup still need independent authority.
 * The general graph API yields copied export DATA, not callable authority. The fixed original Program
 * Files child additionally uses the retained shell32 PIN with actual GPA/provider checks under trusted
 * startup. Installed preparation can attach the separate original process API-set reader and route
 * PINs. No LoadLibrary fallback, profile loading or JNI registration occurs in this collection.
 * Full OS transitive load closure is not modeled.
 */
final class WindowsOriginalSystemModulesCandidate {
    private static final int COUNT = 9;
    private static final int PATH_CHARS = 1024;
    private static final MemoryLayout PATH = MemoryLayout.sequenceLayout(PATH_CHARS, ValueLayout.JAVA_SHORT);
    private static final MemoryLayout NAME = MemoryLayout.sequenceLayout(32, ValueLayout.JAVA_SHORT);

    static final class Failure extends RuntimeException {
        private static final long serialVersionUID = 1L;
        final transient WindowsOriginalSystemModulesCandidate retainedCandidate;
        Throwable operationFailure;
        final Throwable[] clearFailures = new Throwable[5];
        Throwable arenaCloseFailure;

        private Failure(WindowsOriginalSystemModulesCandidate candidate) {
            super("Original system module collection failed with ownership retained", null, false, false);
            retainedCandidate = candidate;
        }
        private boolean retirementFailed() {
            if (arenaCloseFailure != null) return true;
            for (Throwable caught : clearFailures) if (caught != null) return true;
            return false;
        }
    }

    private final Thread thread = Thread.currentThread();
    private final WindowsSystemBootstrapCandidate bootstrap;
    private final Failure failure = new Failure(this);
    private final WindowsOriginalSystemModuleCandidate[] modules = new WindowsOriginalSystemModuleCandidate[COUNT];
    private final long[] rawModules = new long[COUNT];
    private final int[] pinReturns = new int[COUNT];
    private final boolean[] moduleAttempted = new boolean[COUNT];
    private final int[] pathReturns = new int[COUNT];
    private final int[] lastErrors = new int[1 + COUNT * 2];
    private final MemorySegment[] buffers = new MemorySegment[5];
    private Linker linker;
    private Arena bootstrapArena;
    private Arena moduleArena;
    private Arena frameArena;
    private MemorySegment pinEntry;
    private MemorySegment pathEntry;
    private MemorySegment systemPathEntry;
    private MethodHandle pinCall;
    private MethodHandle pathCall;
    private MethodHandle systemPathCall;
    private long errorOffset;
    private int systemPathReturn;
    private int systemLength;
    private int activeSlot = -1;
    private boolean attempted;
    private boolean nativeReturnUnconfirmed;
    private boolean frameRetired;
    private boolean systemPathAttempted;
    private boolean pinsComplete;
    private boolean filesAttempted;
    private boolean completed;
    private boolean failed;
    private String outcome;
    private int stoppedSlot = -1;
    private WindowsSystemExportPlan.Input[] inputs;
    private WindowsSystemExportPlan graph;
    private int diagnosticPhase; // Stored readback only; never participates in admission or ownership.
    private boolean apiSetAttempted;
    private WindowsOriginalApiSetCandidate apiSets;

    WindowsOriginalSystemModulesCandidate(WindowsSystemBootstrapCandidate bootstrap) { this.bootstrap = bootstrap; }

    static String fixedName(int slot) {
        return switch (slot) {
            case 0 -> "kernel32.dll";
            case 1 -> "advapi32.dll";
            case 2 -> "ntdll.dll";
            case 3 -> "shell32.dll";
            case 4 -> "ole32.dll";
            case 5 -> "kernelbase.dll";
            case 6 -> "sechost.dll";
            case 7 -> "combase.dll";
            case 8 -> "iphlpapi.dll";
            default -> throw new IllegalArgumentException("Unknown fixed system module slot");
        };
    }

    void observe() {
        requireOriginalBootstrap();
        if (attempted) throw new IllegalStateException("Original system collection was already attempted");
        attempted = true;
        boolean observed = false;
        try {
            diagnosticPhase = 1;
            // All concrete owners/failure carriers are attached before any PIN or native effect.
            for (int slot = 0; slot < COUNT; slot++) modules[slot] = new WindowsOriginalSystemModuleCandidate(this, slot);
            prepareFrame();
            observeLoadedModules();
            observed = true;
        } catch (Throwable caught) {
            if (caught != failure) failure.operationFailure = caught;
        } finally { retireFrame(); }
        if (!observed || !frameRetired || nativeReturnUnconfirmed || failure.retirementFailed()) throw fail(failure.operationFailure);
        if (outcome != null) {
            completed = true; // Only an honest missing already-loaded module diagnostic; never a partial graph.
            return;
        }
        try {
            observeOriginalFiles();
            completed = true;
        } catch (Throwable caught) { throw fail(caught); }
    }

    private void observeOriginalFiles() {
        requireOriginalNativeInputs();
        if (!pinsComplete || !frameRetired || filesAttempted) {
            throw new IllegalStateException("System files lack the original unconsumed retained PIN cohort");
        }
        filesAttempted = true;
        long aggregate = 0;
        for (int slot = 0; slot < COUNT; slot++) {
            activeSlot = slot;
            WindowsOriginalSystemModuleCandidate module = modules[slot];
            diagnosticPhase = 5;
            module.observeFile();
            diagnosticPhase = 6;
            module.observeSecurity();
            if (!module.descriptorPolicyAccepted()) {
                stoppedSlot = slot;
                outcome = "LEAF_POLICY_REFUSED";
                return;
            }
            diagnosticPhase = 7;
            module.observeAncestors();
            if (!module.descriptorPoliciesAccepted()) {
                stoppedSlot = slot;
                outcome = "ANCESTOR_POLICY_REFUSED";
                return;
            }
            diagnosticPhase = 8;
            aggregate = WindowsSystemExportPlan.checkedAggregateSize(aggregate, Math.toIntExact(module.byteCount()));
        }
        // The unchanged parser cap is an input arithmetic bound, NOT a -Xmx128m memory guarantee.
        // Original snapshots and Input's defensive copies coexist; any allocation failure retains roots.
        inputs = new WindowsSystemExportPlan.Input[COUNT];
        for (int slot = 0; slot < COUNT; slot++) {
            activeSlot = slot;
            diagnosticPhase = 9;
            modules[slot].observeBytes();
            diagnosticPhase = 10;
            inputs[slot] = modules[slot].originalExportInput();
        }
        diagnosticPhase = 11;
        WindowsSystemExportPlan observed = WindowsSystemExportPlan.parse(inputs);
        requireOriginalNativeInputs();
        graph = observed;
        activeSlot = -1;
        outcome = "COMPLETE";
    }

    private void prepareFrame() {
        requireOriginalNativeInputs();
        linker = bootstrap.originalSystemModulesLinker(this);
        bootstrapArena = bootstrap.originalSystemModulesArena(this);
        pinEntry = bootstrap.originalSystemModulesObservationEntry(this, 0);
        pathEntry = bootstrap.originalSystemModulesObservationEntry(this, 1);
        systemPathEntry = bootstrap.originalSystemModulesObservationEntry(this, 2);
        validateEntry(pinEntry);
        validateEntry(pathEntry);
        validateEntry(systemPathEntry);
        MemoryLayout state = Linker.Option.captureStateLayout();
        MemoryLayout error = state.select(MemoryLayout.PathElement.groupElement("GetLastError"));
        errorOffset = state.byteOffset(MemoryLayout.PathElement.groupElement("GetLastError"));
        if (!(error instanceof ValueLayout.OfInt) || error.byteSize() != 4 || error.byteAlignment() != 4 ||
            state.byteSize() < 4 || state.byteSize() > 64 || errorOffset < 0 || errorOffset % 4 != 0 ||
            errorOffset > state.byteSize() - 4) throw new IllegalStateException("Unsupported system collection error layout");
        pinCall = linker.downcallHandle(pinEntry, FunctionDescriptor.of(ValueLayout.JAVA_INT,
            ValueLayout.JAVA_INT, ValueLayout.ADDRESS.withTargetLayout(NAME),
            ValueLayout.ADDRESS.withTargetLayout(ValueLayout.JAVA_LONG)), Linker.Option.captureCallState("GetLastError"));
        pathCall = linker.downcallHandle(pathEntry, FunctionDescriptor.of(ValueLayout.JAVA_INT,
            ValueLayout.ADDRESS, ValueLayout.ADDRESS.withTargetLayout(PATH), ValueLayout.JAVA_INT),
            Linker.Option.captureCallState("GetLastError"));
        systemPathCall = linker.downcallHandle(systemPathEntry, FunctionDescriptor.of(ValueLayout.JAVA_INT,
            ValueLayout.ADDRESS.withTargetLayout(PATH), ValueLayout.JAVA_INT), Linker.Option.captureCallState("GetLastError"));
        moduleArena = Arena.ofConfined(); // Permanently owns all successful PIN views, never closed here.
        frameArena = Arena.ofConfined();
        buffers[0] = frameArena.allocate(ValueLayout.JAVA_LONG);
        buffers[1] = frameArena.allocate(PATH);
        buffers[2] = frameArena.allocate(PATH);
        buffers[3] = frameArena.allocate(NAME);
        buffers[4] = frameArena.allocate(state);
        for (int index = 0; index < buffers.length; index++) {
            MemorySegment buffer = buffers[index];
            long size = index == 0 ? 8 : index < 3 ? PATH.byteSize() : index == 3 ? NAME.byteSize() : state.byteSize();
            int alignment = index == 0 ? 8 : index < 4 ? 2 : 4;
            if (!buffer.isNative() || buffer.byteSize() != size || buffer.address() <= 65_535 ||
                buffer.address() > Long.MAX_VALUE - size || buffer.address() % alignment != 0 ||
                !buffer.scope().equals(frameArena.scope()) || !buffer.isAccessibleBy(thread)) {
                throw new IllegalStateException("Invalid private system collection frame");
            }
            for (int prior = 0; prior < index; prior++) rejectAlias(buffers[prior].address(), buffers[prior].byteSize(), buffer);
            rejectAlias(pinEntry.address(), 1, buffer);
            rejectAlias(pathEntry.address(), 1, buffer);
            rejectAlias(systemPathEntry.address(), 1, buffer);
            buffer.fill((byte) 0);
        }
    }

    /** Fixed-call inert MethodHandle controls exercise these same methods, not an alternate native engine. */
    private void observeLoadedModules() throws Throwable {
        observeSystemPath();
        for (int slot = 0; slot < COUNT; slot++) {
            activeSlot = slot;
            if (!observeModule(slot)) return;
        }
        pinsComplete = true;
        activeSlot = -1;
    }

    private void observeSystemPath() throws Throwable {
        requireOriginalNativeInputs();
        if (systemPathAttempted || frameRetired) throw new IllegalStateException("Original system pathname call was already consumed");
        systemPathAttempted = true;
        diagnosticPhase = 2;
        buffers[2].fill((byte) 0x7f);
        nativeReturnUnconfirmed = true;
        systemPathReturn = (int) systemPathCall.invokeExact(buffers[4], buffers[2], PATH_CHARS);
        nativeReturnUnconfirmed = false;
        lastErrors[0] = buffers[4].get(ValueLayout.JAVA_INT, errorOffset);
        systemLength = validatePath(buffers[2], systemPathReturn);
        if (systemLength < 4 || character(buffers[2], systemLength - 1) == '\\') {
            throw new IllegalStateException("System directory observation is incomplete");
        }
    }

    private boolean observeModule(int slot) throws Throwable {
        requireOriginalNativeInputs();
        if (slot != activeSlot || slot < 0 || slot >= COUNT || !systemPathAttempted || systemLength < 4 ||
            frameRetired || modules[slot] == null || moduleAttempted[slot] || pinReturns[slot] != 0 || rawModules[slot] != 0) {
            throw new IllegalStateException("Fixed original module observation is out of order or already consumed");
        }
        moduleAttempted[slot] = true;
        diagnosticPhase = 3;
        String name = fixedName(slot);
        buffers[3].fill((byte) 0);
        for (int index = 0; index < name.length(); index++) buffers[3].setAtIndex(ValueLayout.JAVA_SHORT, index, (short) name.charAt(index));
        buffers[0].fill((byte) 0);
        nativeReturnUnconfirmed = true;
        pinReturns[slot] = (int) pinCall.invokeExact(buffers[4], 1, buffers[3], buffers[0]); // PIN, already-loaded name only.
        rawModules[slot] = buffers[0].get(ValueLayout.JAVA_LONG, 0); // Before a wrapper or any allocating/error interpretation.
        nativeReturnUnconfirmed = false;
        modules[slot].retainRawModule(rawModules[slot]);
        lastErrors[1 + slot * 2] = buffers[4].get(ValueLayout.JAVA_INT, errorOffset);
        if (pinReturns[slot] == 0) {
            if (rawModules[slot] != 0 || lastErrors[1 + slot * 2] != 126) {
                throw new IllegalStateException("Original named module PIN failed without a confirmed absence");
            }
            stoppedSlot = slot;
            outcome = "MODULE_ABSENT";
            return false;
        }
        if (rawModules[slot] <= 0 || (rawModules[slot] & 65_535) != 0 || rawModules[slot] > Long.MAX_VALUE - 65_536) {
            throw new IllegalStateException("Original named module has an invalid HMODULE");
        }
        for (MemorySegment buffer : buffers) rejectAlias(rawModules[slot], 65_536, buffer);
        for (int prior = 0; prior < slot; prior++) {
            if (rawModules[slot] == rawModules[prior]) throw new IllegalStateException("Different fixed modules share one observation");
        }
        MemorySegment module = MemorySegment.ofAddress(rawModules[slot]).reinterpret(moduleArena, null);
        diagnosticPhase = 4;
        buffers[1].fill((byte) 0x7f);
        nativeReturnUnconfirmed = true;
        pathReturns[slot] = (int) pathCall.invokeExact(buffers[4], module, buffers[1], PATH_CHARS);
        nativeReturnUnconfirmed = false;
        lastErrors[2 + slot * 2] = buffers[4].get(ValueLayout.JAVA_INT, errorOffset);
        int length = validatePath(buffers[1], pathReturns[slot]);
        if (length != systemLength + 1 + name.length()) throw new IllegalStateException("Fixed module is not directly in the system directory");
        for (int index = 0; index < systemLength; index++) {
            if (fold(character(buffers[1], index)) != fold(character(buffers[2], index))) {
                throw new IllegalStateException("Fixed module differs from original system directory observation");
            }
        }
        if (character(buffers[1], systemLength) != '\\') throw new IllegalStateException("System module path boundary differs");
        for (int index = 0; index < name.length(); index++) {
            if (fold(character(buffers[1], systemLength + 1 + index)) != name.charAt(index)) {
                throw new IllegalStateException("System module basename differs from its fixed slot");
            }
        }
        char[] original = new char[length + 1];
        for (int index = 0; index < length; index++) original[index] = character(buffers[1], index);
        modules[slot].finishPin(moduleArena, original);
        return true;
    }

    private static int validatePath(MemorySegment buffer, int returned) {
        long count = Integer.toUnsignedLong(returned);
        if (count < 4 || count >= PATH_CHARS || character(buffer, (int) count) != 0 ||
            !letter(character(buffer, 0)) || character(buffer, 1) != ':' || character(buffer, 2) != '\\') {
            throw new IllegalStateException("System module pathname is unbounded or not absolute");
        }
        int start = 3;
        for (int index = 3; index <= count; index++) {
            char value = character(buffer, index);
            if (value == 0 && index != count) throw new IllegalStateException("System pathname contains an embedded terminator");
            if (value == '\\' || value == 0) {
                if (index == start || index - start > 255 ||
                    !(letter(character(buffer, start)) || character(buffer, start) >= '0' && character(buffer, start) <= '9') ||
                    reserved(buffer, start, index) || character(buffer, index - 1) == '.' ||
                    character(buffer, index - 1) == ' ') throw new IllegalStateException("Unsupported system path component");
                start = index + 1;
            } else if (!(letter(value) || value >= '0' && value <= '9' || value == ' ' || value == '.' || value == '_' || value == '-')) {
                throw new IllegalStateException("Unsupported system path representation");
            }
        }
        return (int) count;
    }

    private static boolean reserved(MemorySegment buffer, int start, int end) {
        int stemEnd = start;
        while (stemEnd < end && character(buffer, stemEnd) != '.') stemEnd++;
        while (stemEnd > start && character(buffer, stemEnd - 1) == ' ') stemEnd--;
        int length = stemEnd - start;
        if (length != 3 && length != 4) return false;
        char first = fold(character(buffer, start));
        char second = fold(character(buffer, start + 1));
        char third = fold(character(buffer, start + 2));
        if (length == 3) return first == 'c' && second == 'o' && third == 'n' ||
            first == 'p' && second == 'r' && third == 'n' || first == 'a' && second == 'u' && third == 'x' ||
            first == 'n' && second == 'u' && third == 'l';
        char last = character(buffer, start + 3);
        return last >= '1' && last <= '9' && (first == 'c' && second == 'o' && third == 'm' ||
            first == 'l' && second == 'p' && third == 't');
    }

    private void validateEntry(MemorySegment entry) {
        if (entry == null || !entry.isNative() || entry.byteSize() != 0 || entry.address() <= 65_535 ||
            entry.address() > Long.MAX_VALUE - 1 || bootstrapArena == null || !bootstrapArena.scope().isAlive() ||
            !entry.scope().equals(bootstrapArena.scope()) || !entry.isAccessibleBy(thread)) {
            throw new IllegalStateException("Original collection lost a scoped bootstrap entry");
        }
    }

    private void retireFrame() {
        if (Thread.currentThread() != thread) throw new IllegalStateException("Original system frame belongs to another thread");
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
        // No FreeLibrary, CloseHandle or original-scope close; every successful PIN remains permanent.
    }

    private Failure fail(Throwable caught) {
        if (!failed) {
            if (caught != failure && failure.operationFailure == null) failure.operationFailure = caught;
            failed = true;
        }
        return failure;
    }

    private void requireOriginalBootstrap() {
        if (Thread.currentThread() != thread || bootstrap == null) throw new IllegalStateException("Collection requires its original bootstrap/thread");
        bootstrap.requireOriginalSystemModules(this);
        if (failed) throw failure;
    }

    void requireOriginalBootstrap(WindowsSystemBootstrapCandidate candidate) {
        if (candidate == null || candidate != bootstrap) {
            throw new IllegalStateException("System collection belongs to a different original bootstrap");
        }
        // Identity only. The consumer attaches this root before checking a possibly failed graph.
    }

    void requireOriginalNativeInputs() {
        requireOriginalBootstrap();
        if (!attempted || outcome != null || completed || nativeReturnUnconfirmed) {
            throw new IllegalStateException("Original system collection is not open for native observations");
        }
    }

    void requireOriginalModule(WindowsOriginalSystemModuleCandidate candidate, int slot) {
        requireOriginalBootstrap();
        if (!attempted || slot < 0 || slot >= COUNT || candidate == null || candidate != modules[slot]) {
            throw new IllegalStateException("System module is not this collection's original fixed attachment");
        }
    }

    Failure failOriginalModule(WindowsOriginalSystemModuleCandidate candidate, int slot, Throwable caught) {
        // Identity only: a failing module's own completion/latch must never be consulted recursively.
        if (Thread.currentThread() != thread || slot < 0 || slot >= COUNT || candidate == null || modules[slot] != candidate) {
            throw new IllegalStateException("Failure is not from the original fixed module");
        }
        return fail(caught);
    }

    boolean isOriginalModuleArena(Arena arena) { requireOriginalBootstrap(); return arena != null && arena == moduleArena && arena.scope().isAlive(); }
    boolean isOriginalModuleScope(MemorySegment module) {
        requireOriginalBootstrap();
        return moduleArena != null && moduleArena.scope().isAlive() && module.scope().equals(moduleArena.scope());
    }
    void requireOriginalQueryProvider(WindowsOriginalSystemModuleCandidate requester, int slot, long provider) {
        requireOriginalModule(requester, slot);
        requireOriginalNativeInputs();
        if (!pinsComplete || provider != modules[2].originalModuleBits()) {
            throw new IllegalStateException("Original ntdll query provider differs from the fixed retained cohort");
        }
    }
    Linker originalLinker(WindowsOriginalSystemModuleCandidate requester, int slot) {
        requireOriginalModule(requester, slot); requireOriginalNativeInputs(); return linker;
    }
    Arena originalBootstrapArena(WindowsOriginalSystemModuleCandidate requester, int slot) {
        requireOriginalModule(requester, slot); requireOriginalNativeInputs(); return bootstrapArena;
    }
    MemorySegment originalFileEntry(WindowsOriginalSystemModuleCandidate requester, int slot, int index) {
        requireOriginalModule(requester, slot); requireOriginalNativeInputs(); return bootstrap.originalSystemModuleFileEntry(this, index);
    }
    MemorySegment originalSecurityEntry(WindowsOriginalSystemModuleCandidate requester, int slot, int index) {
        requireOriginalModule(requester, slot); requireOriginalNativeInputs(); return bootstrap.originalSystemModuleSecurityEntry(this, index);
    }
    MemorySegment originalAncestorsEntry(WindowsOriginalSystemModuleCandidate requester, int slot, int index) {
        requireOriginalModule(requester, slot); requireOriginalNativeInputs(); return bootstrap.originalSystemModuleAncestorsEntry(this, index);
    }
    MemorySegment originalReadEntry(WindowsOriginalSystemModuleCandidate requester, int slot) {
        requireOriginalModule(requester, slot); requester.requireOriginalByteInputs(); return bootstrap.originalSystemModuleReadEntry(this);
    }

    /**
     * Only the sealed installed failure's reader uses this stored-state projection. In particular, do
     * not call requireCompleted(), inspect a MemorySegment, or traverse arbitrary exception messages:
     * a refused cohort is incomplete, and a failed cohort can retain an unconfirmed native return.
     */
    String failureOperation() {
        if (nativeReturnUnconfirmed) return "SYSTEM_RETURN_UNKNOWN_" + diagnosticSlot(activeSlot);
        if (failure.retirementFailed()) return "SYSTEM_RETIREMENT_" + diagnosticSlot(activeSlot);
        if (outcome != null) {
            String refusal = switch (outcome) {
                case "MODULE_ABSENT" -> "SYSTEM_MODULE_ABSENT_";
                case "LEAF_POLICY_REFUSED" -> "SYSTEM_LEAF_POLICY_";
                case "ANCESTOR_POLICY_REFUSED" -> "SYSTEM_ANCESTOR_POLICY_";
                case "COMPLETE" -> "SYSTEM_GRAPH_RECHECK_";
                default -> "SYSTEM_UNKNOWN_OUTCOME_";
            };
            return refusal + diagnosticSlot(stoppedSlot);
        }
        String operation = switch (diagnosticPhase) {
            case 0 -> "SYSTEM_PRECONDITION_";
            case 1 -> "SYSTEM_FRAME_";
            case 2 -> "SYSTEM_DIRECTORY_";
            case 3 -> "SYSTEM_MODULE_PIN_";
            case 4 -> "SYSTEM_MODULE_PATH_";
            case 5 -> "SYSTEM_FILE_";
            case 6 -> "SYSTEM_SECURITY_";
            case 7 -> "SYSTEM_ANCESTORS_";
            case 8 -> "SYSTEM_BYTE_BOUND_";
            case 9 -> "SYSTEM_BYTES_";
            case 10 -> "SYSTEM_EXPORT_INPUT_";
            case 11 -> "SYSTEM_EXPORT_GRAPH_";
            default -> "SYSTEM_UNKNOWN_OPERATION_";
        };
        return operation + diagnosticSlot(diagnosticPhase == 11 ? -1 : activeSlot);
    }

    private static String diagnosticSlot(int slot) {
        return switch (slot) {
            case -1 -> "NO_SLOT";
            case 0 -> "SLOT_ZERO";
            case 1 -> "SLOT_ONE";
            case 2 -> "SLOT_TWO";
            case 3 -> "SLOT_THREE";
            case 4 -> "SLOT_FOUR";
            case 5 -> "SLOT_FIVE";
            case 6 -> "SLOT_SIX";
            case 7 -> "SLOT_SEVEN";
            case 8 -> "SLOT_EIGHT";
            default -> "UNKNOWN_SLOT";
        };
    }

    private void requireCompleted() {
        requireOriginalBootstrap();
        if (!completed || outcome == null || !frameRetired || nativeReturnUnconfirmed) {
            throw new IllegalStateException("Original system collection has no completed diagnostic");
        }
    }
    void requireOriginalExportGraph() {
        requireCompleted();
        if (!outcome.equals("COMPLETE") || !pinsComplete || graph == null) {
            throw new IllegalStateException("Original system collection has no completed copied export graph");
        }
        for (WindowsOriginalSystemModuleCandidate module : modules) {
            if (!module.bytesObserved() || !module.descriptorPolicyAccepted() || !module.descriptorPoliciesAccepted()) {
                throw new IllegalStateException("Original graph lost a completed owned snapshot chain");
            }
        }
    }
    boolean completed() { requireCompleted(); return true; }
    String outcome() { requireCompleted(); return outcome; }
    int stoppedSlot() { requireCompleted(); return stoppedSlot; }
    int moduleCount() { requireCompleted(); return COUNT; }
    WindowsOriginalSystemModuleCandidate module(int slot) {
        requireCompleted();
        if (slot < 0 || slot >= COUNT) throw new IllegalArgumentException("Unknown fixed system module slot");
        return modules[slot];
    }
    WindowsSystemExportPlan.Target resolve(String module, String symbol) {
        requireOriginalExportGraph();
        try { return apiSets == null ? graph.resolve(module, symbol) : apiSets.resolve(module, symbol); }
        catch (Throwable caught) { throw fail(caught); }
    }

    WindowsSystemExportPlan.Target resolveIpExport(WindowsOriginalIpInterfaces requester, String name) {
        requireOriginalExportGraph();
        requester.requireOriginalModule(modules[8]);
        if (!name.equals("GetIpInterfaceTable") && !name.equals("FreeMibTable")) {
            throw new IllegalArgumentException("Unknown fixed IP Helper export");
        }
        // These two fixed physical exports require no new API-set routing after that owner was sealed.
        return graph.resolve("iphlpapi.dll", name);
    }

    void prepareApiSetNamespace() {
        requireOriginalExportGraph();
        if (apiSetAttempted) throw new IllegalStateException("Original API-set namespace was already attempted");
        apiSetAttempted = true;
        try {
            apiSets = new WindowsOriginalApiSetCandidate(this); // Permanent attachment before any query/PIN.
            apiSets.observe();
        } catch (Throwable caught) { throw fail(caught); }
    }
    void finishApiSetRoutes() {
        requireOriginalExportGraph();
        if (apiSets == null) throw new IllegalStateException("Missing original API-set namespace");
        try { apiSets.finishRoutes(); }
        catch (Throwable caught) { throw fail(caught); }
    }
    void requireSealedApiSetRoutes() {
        requireOriginalExportGraph();
        if (apiSets == null) throw new IllegalStateException("Missing original API-set route ownership");
        apiSets.requireSealed();
    }
    void requireOriginalApiSet(WindowsOriginalApiSetCandidate candidate) {
        requireOriginalExportGraph();
        if (!apiSetAttempted || candidate == null || candidate != apiSets) {
            throw new IllegalStateException("API-set namespace is not the original retained child");
        }
    }
    Linker apiSetLinker(WindowsOriginalApiSetCandidate candidate) { requireOriginalApiSet(candidate); return linker; }
    Arena apiSetArena(WindowsOriginalApiSetCandidate candidate) { requireOriginalApiSet(candidate); return bootstrapArena; }
    WindowsSystemExportPlan apiSetGraph(WindowsOriginalApiSetCandidate candidate) { requireOriginalApiSet(candidate); return graph; }
    MemorySegment apiSetEntry(WindowsOriginalApiSetCandidate candidate, int index) {
        requireOriginalApiSet(candidate); return bootstrap.originalApiSetEntry(this, index);
    }
    String apiSetFailureOperation() { return apiSets == null ? "API_SET_PRECONDITION" : apiSets.failureOperation(); }
    String importFailureOperation() {
        return apiSets != null && apiSets.hasFailed() ? apiSets.failureOperation() : "PROFILE_IMPORTS";
    }
    WindowsSystemExportPlan.Target resolveOrdinal(String module, long ordinal) {
        requireOriginalExportGraph();
        try { return graph.resolveOrdinal(module, ordinal); }
        catch (Throwable caught) { throw fail(caught); }
    }

    private static char character(MemorySegment buffer, int index) { return (char) Short.toUnsignedInt(buffer.getAtIndex(ValueLayout.JAVA_SHORT, index)); }
    private static boolean letter(char value) { return value >= 'a' && value <= 'z' || value >= 'A' && value <= 'Z'; }
    private static char fold(char value) { return value >= 'A' && value <= 'Z' ? (char) (value + 32) : value; }
    private static void rejectAlias(long address, long size, MemorySegment buffer) {
        if (address < buffer.address() + buffer.byteSize() && buffer.address() < address + size) {
            throw new IllegalStateException("Original system module aliases its private frame");
        }
    }
}
