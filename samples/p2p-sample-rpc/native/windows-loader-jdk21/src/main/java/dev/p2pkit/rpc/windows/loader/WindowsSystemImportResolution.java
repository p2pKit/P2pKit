package dev.p2pkit.rpc.windows.loader;

import java.lang.foreign.Arena;
import java.lang.foreign.FunctionDescriptor;
import java.lang.foreign.Linker;
import java.lang.foreign.MemoryLayout;
import java.lang.foreign.MemorySegment;
import java.lang.foreign.ValueLayout;
import java.lang.invoke.MethodHandle;
import java.util.HashSet;
import java.util.Set;

/**
 * Conditional kernel32-only import resolution mechanics, NOT startup or import-provider authority.
 * The original immutable byte plan supplies names, never expected addresses from the candidate IAT.
 * GetProcAddress can execute implicit forwarder loads before the later physical-provider observation.
 * A reviewed original runtime/startup/export policy must precede productive use; later System32 paths
 * and permanent module pins cannot establish that earlier authority. The other four logical libraries
 * accepted by the byte parser are deliberately unsupported here, not silently mapped to kernel32.
 * This component neither loads the profile DLL, registers JNI, nor enables the productive loader.
 */
final class WindowsSystemImportResolution {
    private static final int PATH_CHARS = 1024;
    private static final int MAXIMUM_IMPORTS = 4096;
    private static final MemoryLayout PATH = MemoryLayout.sequenceLayout(PATH_CHARS, ValueLayout.JAVA_SHORT);
    private static final MemoryLayout NAME = MemoryLayout.sequenceLayout(256, ValueLayout.JAVA_BYTE);
    private static final String[] PHYSICAL_NAMES = {"kernel32.dll", "kernelbase.dll", "ntdll.dll"};

    static final class Failure extends RuntimeException {
        private static final long serialVersionUID = 1L;
        final transient WindowsSystemImportResolution retainedResolution;
        Throwable operationFailure;
        final Throwable[] clearFailures = new Throwable[5];
        Throwable arenaCloseFailure;

        private Failure(WindowsSystemImportResolution resolution) {
            super("System import resolution failed with original ownership retained", null, false, false);
            retainedResolution = resolution;
        }

        private boolean retirementFailed() {
            if (arenaCloseFailure != null) return true;
            for (Throwable caught : clearFailures) if (caught != null) return true;
            return false;
        }
    }

    private final Thread thread = Thread.currentThread();
    private final WindowsSystemBootstrapCandidate bootstrap;
    private final WindowsPackagedVerifier plan;
    private final Linker linker;
    private final Arena originalArena;
    private final MemorySegment pinEntry;
    private final MemorySegment pathEntry;
    private final MemorySegment systemEntry;
    private final MemorySegment resolveEntry;
    private final String[] names;
    private final long[] rawEntries;
    private final long[] rawProviders;
    private final MemorySegment[] entryViews;
    private final MemorySegment[] providerViews;
    private final int[] callReturns;
    private final int[] lastErrors;
    private final boolean[] errorObserved;
    private final long[] physicalModules = new long[3];
    private final Failure failure = new Failure(this);
    // Actual HMODULE, module path, original system directory, bounded ASCII name, captured Windows error.
    private final MemorySegment[] buffers = new MemorySegment[5];
    private Arena frameArena;
    private MethodHandle pinCall;
    private MethodHandle pathCall;
    private MethodHandle systemCall;
    private MethodHandle resolveCall;
    private MemorySegment kernel;
    private long rawKernel;
    private long errorOffset;
    private long stateBytes;
    private int systemLength;
    private int phase;
    private boolean attempted;
    private boolean callInFlight;
    private boolean frameRetired;
    private boolean succeeded;

    WindowsSystemImportResolution(WindowsSystemBootstrapCandidate bootstrap, WindowsPackagedVerifier plan,
        Linker linker, Arena originalArena, MemorySegment pinEntry, MemorySegment pathEntry,
        MemorySegment systemEntry, MemorySegment resolveEntry) {
        if (plan == null) throw new IllegalArgumentException("System import resolution requires its original byte plan");
        // No native effects or native frame allocation before the complete unsupported-inventory refusal.
        names = snapshotInventory(plan.importNames());
        this.bootstrap = bootstrap;
        this.plan = plan;
        this.linker = linker;
        this.originalArena = originalArena;
        this.pinEntry = pinEntry;
        this.pathEntry = pathEntry;
        this.systemEntry = systemEntry;
        this.resolveEntry = resolveEntry;
        int count = names.length / 2;
        rawEntries = new long[count];
        rawProviders = new long[count];
        entryViews = new MemorySegment[count];
        providerViews = new MemorySegment[count];
        callReturns = new int[3 + 3 * count];
        lastErrors = new int[callReturns.length];
        errorObserved = new boolean[callReturns.length];
    }

    private static String[] snapshotInventory(String[] source) {
        if (source == null || source.length < 2 || source.length > MAXIMUM_IMPORTS * 2 || source.length % 2 != 0) {
            throw new IllegalArgumentException("Invalid bounded system import inventory");
        }
        String[] snapshot = source.clone();
        Set<String> seen = new HashSet<>();
        for (int index = 0; index < snapshot.length; index += 2) {
            if (!"kernel32.dll".equals(snapshot[index]) || !identifier(snapshot[index + 1]) ||
                !seen.add(snapshot[index + 1])) {
                throw new IllegalArgumentException("Unsupported or ambiguous system import inventory");
            }
        }
        return snapshot;
    }

    private static boolean identifier(String name) {
        if (name == null || name.isEmpty() || name.length() > 128) return false;
        for (int index = 0; index < name.length(); index++) {
            char value = name.charAt(index);
            if (!(value >= 'a' && value <= 'z' || value >= 'A' && value <= 'Z' || value == '_' ||
                index != 0 && value >= '0' && value <= '9')) return false;
        }
        return true;
    }

    void observe() {
        requireOriginal();
        if (attempted) throw new IllegalStateException("System import resolution was already attempted");
        attempted = true;
        boolean accepted = false;
        try {
            prepareFrame();
            buffers[2].fill((byte) 0x7f);
            phase = 0;
            callInFlight = true;
            callReturns[0] = (int) systemCall.invokeExact(buffers[4], buffers[2], PATH_CHARS);
            callInFlight = false;
            observeError(0);
            systemLength = validatePath(buffers[2], callReturns[0]);
            if (systemLength < 3 || !letter(character(buffers[2], 0)) || character(buffers[2], 1) != ':' ||
                character(buffers[2], 2) != '\\' || character(buffers[2], systemLength - 1) == '\\') {
                throw new IllegalStateException("Unsupported original system directory observation");
            }
            buffers[1].fill((byte) 0);
            String logical = PHYSICAL_NAMES[0];
            for (int index = 0; index < logical.length(); index++) {
                buffers[1].setAtIndex(ValueLayout.JAVA_SHORT, index, (short) logical.charAt(index));
            }
            buffers[0].fill((byte) 0);
            phase = 1;
            callInFlight = true;
            callReturns[1] = (int) pinCall.invokeExact(buffers[4], 1, buffers[1], buffers[0]);
            rawKernel = buffers[0].get(ValueLayout.JAVA_LONG, 0); // PIN effect retained BEFORE wrapper/error access.
            callInFlight = false;
            observeError(1);
            validateModule(rawKernel, callReturns[1]);
            kernel = MemorySegment.ofAddress(rawKernel).reinterpret(originalArena, null);
            observePath(kernel, 2);
            if (!matchesSystemPath(callReturns[2], PHYSICAL_NAMES[0])) {
                throw new IllegalStateException("Original logical kernel32 mapping differs");
            }
            physicalModules[0] = rawKernel;
            for (int index = 0; index < rawEntries.length; index++) observeImport(index);
            requireOriginal();
            accepted = true;
        } catch (Throwable caught) {
            failure.operationFailure = caught;
        } finally {
            retireFrame();
            succeeded = accepted && frameRetired && !failure.retirementFailed();
        }
        if (!succeeded) throw failure;
    }

    private void observeImport(int index) throws Throwable {
        requireOriginal();
        String name = names[index * 2 + 1];
        buffers[3].fill((byte) 0);
        for (int offset = 0; offset < name.length(); offset++) {
            buffers[3].set(ValueLayout.JAVA_BYTE, offset, (byte) name.charAt(offset));
        }
        int slot = 3 + index * 3;
        phase = slot;
        callInFlight = true;
        // Exact Windows-x64 pointer return in RAX, retained before allocating a segment wrapper.
        // Forwarder loads can occur INSIDE this call; later path checks are not initial authority.
        rawEntries[index] = (long) resolveCall.invokeExact(buffers[4], kernel, buffers[3]);
        callInFlight = false;
        observeError(slot);
        validateAddress(rawEntries[index], 1);
        entryViews[index] = MemorySegment.ofAddress(rawEntries[index]).reinterpret(originalArena, null);
        buffers[0].fill((byte) 0);
        phase = slot + 1;
        callInFlight = true;
        callReturns[slot + 1] = (int) pinCall.invokeExact(buffers[4], 5, entryViews[index], buffers[0]);
        rawProviders[index] = buffers[0].get(ValueLayout.JAVA_LONG, 0);
        callInFlight = false;
        observeError(slot + 1);
        validateModule(rawProviders[index], callReturns[slot + 1]);
        providerViews[index] = MemorySegment.ofAddress(rawProviders[index]).reinterpret(originalArena, null);
        observePath(providerViews[index], slot + 2);
        int physical = -1;
        for (int candidate = 0; candidate < PHYSICAL_NAMES.length; candidate++) {
            if (matchesSystemPath(callReturns[slot + 2], PHYSICAL_NAMES[candidate])) physical = candidate;
        }
        if (physical < 0 || physicalModules[physical] != 0 && physicalModules[physical] != rawProviders[index]) {
            throw new IllegalStateException("System import resolved to an unsupported or ambiguous physical provider");
        }
        for (int candidate = 0; candidate < physicalModules.length; candidate++) {
            if (candidate != physical && physicalModules[candidate] == rawProviders[index]) {
                throw new IllegalStateException("System import provider identities alias");
            }
        }
        physicalModules[physical] = rawProviders[index];
    }

    private void observePath(MemorySegment module, int slot) throws Throwable {
        requireOriginal();
        buffers[1].fill((byte) 0x7f);
        phase = slot;
        callInFlight = true;
        callReturns[slot] = (int) pathCall.invokeExact(buffers[4], module, buffers[1], PATH_CHARS);
        callInFlight = false;
        observeError(slot);
        validatePath(buffers[1], callReturns[slot]);
    }

    private void prepareFrame() {
        MemoryLayout state = Linker.Option.captureStateLayout();
        MemoryLayout error = state.select(MemoryLayout.PathElement.groupElement("GetLastError"));
        errorOffset = state.byteOffset(MemoryLayout.PathElement.groupElement("GetLastError"));
        stateBytes = state.byteSize();
        if (!(error instanceof ValueLayout.OfInt) || error.byteSize() != 4 || error.byteAlignment() != 4 ||
            stateBytes < 4 || stateBytes > 64 || errorOffset < 0 || errorOffset % 4 != 0 || errorOffset > stateBytes - 4) {
            throw new IllegalStateException("Unsupported captured Windows error layout");
        }
        frameArena = Arena.ofConfined();
        buffers[0] = frameArena.allocate(ValueLayout.JAVA_LONG);
        buffers[1] = frameArena.allocate(PATH);
        buffers[2] = frameArena.allocate(PATH);
        buffers[3] = frameArena.allocate(NAME);
        buffers[4] = frameArena.allocate(state);
        for (int index = 0; index < buffers.length; index++) {
            MemorySegment buffer = buffers[index];
            long size = index == 0 ? 8 : index == 3 ? 256 : index == 4 ? stateBytes : PATH.byteSize();
            int alignment = index == 0 ? 8 : index == 3 ? 1 : index == 4 ? 4 : 2;
            if (!buffer.isNative() || buffer.byteSize() != size || buffer.address() <= 65_535 ||
                buffer.address() > Long.MAX_VALUE - size || buffer.address() % alignment != 0 ||
                !buffer.scope().equals(frameArena.scope()) || !buffer.isAccessibleBy(thread)) {
                throw new IllegalStateException("Invalid private import resolution frame");
            }
            for (int prior = 0; prior < index; prior++) {
                if (overlap(buffer.address(), size, buffers[prior].address(), buffers[prior].byteSize())) {
                    throw new IllegalStateException("Import resolution frame ranges overlap");
                }
            }
        }
        validateEntry(pinEntry);
        validateEntry(pathEntry);
        validateEntry(systemEntry);
        validateEntry(resolveEntry);
        pinCall = linker.downcallHandle(pinEntry, FunctionDescriptor.of(ValueLayout.JAVA_INT,
            ValueLayout.JAVA_INT, ValueLayout.ADDRESS, ValueLayout.ADDRESS.withTargetLayout(ValueLayout.JAVA_LONG)),
            Linker.Option.captureCallState("GetLastError"));
        pathCall = linker.downcallHandle(pathEntry, FunctionDescriptor.of(ValueLayout.JAVA_INT,
            ValueLayout.ADDRESS, ValueLayout.ADDRESS.withTargetLayout(PATH), ValueLayout.JAVA_INT),
            Linker.Option.captureCallState("GetLastError"));
        systemCall = linker.downcallHandle(systemEntry, FunctionDescriptor.of(ValueLayout.JAVA_INT,
            ValueLayout.ADDRESS.withTargetLayout(PATH), ValueLayout.JAVA_INT),
            Linker.Option.captureCallState("GetLastError"));
        resolveCall = linker.downcallHandle(resolveEntry, FunctionDescriptor.of(ValueLayout.JAVA_LONG,
            ValueLayout.ADDRESS, ValueLayout.ADDRESS.withTargetLayout(NAME)),
            Linker.Option.captureCallState("GetLastError"));
    }

    private void validateModule(long raw, int returned) {
        if (returned == 0 || (raw & 65_535) != 0) throw new IllegalStateException("Original import provider PIN failed");
        validateAddress(raw, 65_536);
    }

    private void validateAddress(long raw, long bytes) {
        if (raw <= 65_535 || raw > Long.MAX_VALUE - bytes) {
            throw new IllegalStateException("Invalid original import address");
        }
        for (MemorySegment buffer : buffers) {
            if (buffer != null && overlap(raw, bytes, buffer.address(), buffer.byteSize())) {
                throw new IllegalStateException("Import address aliases a private call frame");
            }
        }
    }

    private void validateEntry(MemorySegment entry) {
        if (entry == null || !entry.isNative() || entry.byteSize() != 0 ||
            !entry.scope().equals(originalArena.scope()) || !entry.isAccessibleBy(thread) || !entry.scope().isAlive()) {
            throw new IllegalStateException("Invalid original bootstrap entry scope");
        }
        validateAddress(entry.address(), 1);
    }

    private void requireOriginal() {
        if (Thread.currentThread() != thread || thread.isVirtual() || bootstrap == null || plan == null ||
            linker == null || originalArena == null || !originalArena.scope().isAlive()) {
            throw new IllegalStateException("System import resolution has no original thread and scope");
        }
        bootstrap.requireOriginalImports(this);
    }

    private void observeError(int index) {
        lastErrors[index] = buffers[4].get(ValueLayout.JAVA_INT, errorOffset);
        errorObserved[index] = true; // Successful Windows calls may preserve a stale error; never require zero.
    }

    private static int validatePath(MemorySegment buffer, int returned) {
        long count = Integer.toUnsignedLong(returned);
        if (count == 0 || count >= PATH_CHARS || character(buffer, (int) count) != 0) {
            throw new IllegalStateException("System import provider pathname is incomplete");
        }
        for (int index = 0; index < count; index++) {
            char value = character(buffer, index);
            if (value < 32 || value > 126 || value == '/') {
                throw new IllegalStateException("Unsupported system import pathname representation");
            }
        }
        return (int) count;
    }

    private boolean matchesSystemPath(int length, String name) {
        if (length != systemLength + 1 + name.length()) return false;
        for (int index = 0; index < systemLength; index++) {
            if (fold(character(buffers[1], index)) != fold(character(buffers[2], index))) return false;
        }
        if (character(buffers[1], systemLength) != '\\') return false;
        for (int index = 0; index < name.length(); index++) {
            if (fold(character(buffers[1], systemLength + 1 + index)) != name.charAt(index)) return false;
        }
        return true;
    }

    private void retireFrame() {
        // An uncertain native/FFM return might still hold the original buffer. Quarantine the entire
        // original frame; no clearing, close, retry, further native call or successful result publication.
        if (frameRetired || callInFlight) return;
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

    long[] addresses() {
        requireOriginal();
        if (!succeeded || !frameRetired) throw new IllegalStateException("System import resolution is incomplete");
        return rawEntries.clone();
    }

    private static char character(MemorySegment buffer, int index) {
        return (char) Short.toUnsignedInt(buffer.getAtIndex(ValueLayout.JAVA_SHORT, index));
    }
    private static boolean letter(char value) { return value >= 'A' && value <= 'Z' || value >= 'a' && value <= 'z'; }
    private static char fold(char value) { return value >= 'A' && value <= 'Z' ? (char) (value + ('a' - 'A')) : value; }
    private static boolean overlap(long first, long count, long second, long size) {
        return first < second + size && second < first + count;
    }
}
