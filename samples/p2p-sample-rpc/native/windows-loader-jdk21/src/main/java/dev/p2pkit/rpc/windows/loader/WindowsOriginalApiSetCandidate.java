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
 * Original AMD64 process API-set observation, conditional on independently admitted OS/JVM startup.
 * A version-6, read-only mapped namespace is copied through the original ReadProcessMemory entry.
 * Only unambiguous default routes into the retained system cohort can be used, and every contract
 * must PIN that same already-loaded module through the actual OS name resolver before candidate load.
 * No namespace file, caller map, raw-address factory, LoadLibrary fallback or GPA of an API set exists.
 */
final class WindowsOriginalApiSetCandidate {
    private static final String QUERY = "NtQueryInformationProcess";
    private static final int MAXIMUM_ROUTES = 128;
    private static final MemorySegment CURRENT_PROCESS = MemorySegment.ofAddress(-1L);

    static final class Failure extends RuntimeException {
        private static final long serialVersionUID = 1L;
        final transient WindowsOriginalApiSetCandidate retainedCandidate;
        Throwable operationFailure;
        final Throwable[] clearFailures = new Throwable[11];
        Throwable closeFailure;
        private Failure(WindowsOriginalApiSetCandidate candidate) {
            super("Original API-set observation failed with ownership retained", null, false, false);
            retainedCandidate = candidate;
        }
        boolean retirementFailed() {
            if (closeFailure != null) return true;
            for (Throwable value : clearFailures) if (value != null) return true;
            return false;
        }
    }

    private final Thread thread = Thread.currentThread();
    private final WindowsOriginalSystemModulesCandidate owner;
    private final Failure failure = new Failure(this);
    // Error, export, HMODULE, basic information, ULONG length, MBI, pointer, header, bytes, SIZE_T, contract.
    private final MemorySegment[] buffers = new MemorySegment[11];
    private final String[] contracts = new String[MAXIMUM_ROUTES];
    private final long[] rawRouteModules = new long[MAXIMUM_ROUTES];
    private final WindowsOriginalSystemModuleCandidate[] routeProviders = new WindowsOriginalSystemModuleCandidate[MAXIMUM_ROUTES];
    private final int[] routeReturns = new int[MAXIMUM_ROUTES];
    private Arena frame;
    private Arena originalArena;
    private Linker linker;
    private MemorySegment ntdll;
    private MemorySegment queryEntry;
    private MethodHandle resolveCall;
    private MethodHandle pinCall;
    private MethodHandle queryCall;
    private MethodHandle memoryCall;
    private MethodHandle readCall;
    private long rawQuery;
    private long rawQueryProvider;
    private long peb;
    private long namespaceAddress;
    private long expectedQuery;
    private long errorOffset;
    private int lastError;
    private int processStatus;
    private int queryPinStatus;
    private int readStatus;
    private long queryBytes;
    private long readBytes;
    private byte[] originalRegion;
    private byte[] snapshot;
    private WindowsApiSetPlan plan;
    private int routeCount;
    private int phase;
    private boolean attempted;
    private boolean observed;
    private boolean sealed;
    private boolean nativeReturnUnconfirmed;
    private boolean frameRetired;
    private boolean failed;

    WindowsOriginalApiSetCandidate(WindowsOriginalSystemModulesCandidate owner) { this.owner = owner; }

    void observe() {
        requireOriginal();
        if (attempted) throw new IllegalStateException("Original API-set observation is already consumed");
        attempted = true;
        try {
            phase = 1;
            prepareFrame();
            phase = 2;
            resolveQuery();
            phase = 3;
            queryProcess();
            phase = 4;
            namespaceAddress = readNamespacePointer();
            phase = 5;
            originalRegion = observeRegion(namespaceAddress);
            phase = 6;
            read(namespaceAddress, buffers[7], 28);
            int size = checkedHeader(buffers[7].toArray(ValueLayout.JAVA_BYTE));
            requireRegion(originalRegion, namespaceAddress, size);
            phase = 7;
            read(namespaceAddress, buffers[8], size);
            snapshot = buffers[8].asSlice(0, size).toArray(ValueLayout.JAVA_BYTE);
            if (!Arrays.equals(Arrays.copyOf(snapshot, 28), buffers[7].toArray(ValueLayout.JAVA_BYTE))) throw refused();
            plan = WindowsApiSetPlan.parse(snapshot);
            phase = 8;
            recheckNamespace();
            observed = true;
        } catch (Throwable caught) { throw fail(caught); }
    }

    private void requireOriginal() {
        if (Thread.currentThread() != thread || owner == null) throw new IllegalStateException("API-set observation requires its original owner/thread");
        owner.requireOriginalApiSet(this);
        if (failed) throw failure;
    }

    private void requireFrame() {
        requireOriginal();
        if (!attempted || frameRetired || nativeReturnUnconfirmed || frame == null || !frame.scope().isAlive()) throw refused();
    }

    void requireOriginalNtdll(WindowsOriginalSystemModuleCandidate candidate) {
        requireOriginal();
        if (candidate == null || candidate != owner.module(2)) throw refused();
    }

    private void prepareFrame() {
        linker = owner.apiSetLinker(this);
        originalArena = owner.apiSetArena(this);
        ntdll = owner.module(2).originalApiSetModule(this);
        WindowsSystemExportPlan.Target target = owner.apiSetGraph(this).resolve("ntdll.dll", QUERY);
        if (!target.module().equals("ntdll.dll") || target.rva() <= 0 ||
            ntdll.address() > Long.MAX_VALUE - target.rva()) throw refused();
        expectedQuery = ntdll.address() + target.rva(); // Comparison only, never a callable address.
        MemorySegment pin = owner.apiSetEntry(this, 1);
        MemorySegment resolve = owner.apiSetEntry(this, 4);
        MemorySegment memory = owner.apiSetEntry(this, 6);
        MemorySegment read = owner.apiSetEntry(this, 7);
        for (MemorySegment entry : new MemorySegment[] {pin, resolve, memory, read}) {
            if (entry == null || !entry.isNative() || entry.byteSize() != 0 || entry.address() <= 65_535 ||
                !entry.scope().equals(originalArena.scope()) || !entry.isAccessibleBy(thread)) throw refused();
        }
        MemoryLayout state = Linker.Option.captureStateLayout();
        MemoryLayout error = state.select(MemoryLayout.PathElement.groupElement("GetLastError"));
        errorOffset = state.byteOffset(MemoryLayout.PathElement.groupElement("GetLastError"));
        if (!(error instanceof ValueLayout.OfInt) || error.byteSize() != 4 || error.byteAlignment() != 4 ||
            state.byteSize() < 4 || state.byteSize() > 64 || errorOffset < 0 || errorOffset % 4 != 0 || errorOffset > state.byteSize() - 4) throw refused();
        resolveCall = linker.downcallHandle(resolve, FunctionDescriptor.of(ValueLayout.JAVA_LONG,
            ValueLayout.ADDRESS, ValueLayout.ADDRESS), Linker.Option.captureCallState("GetLastError"));
        pinCall = linker.downcallHandle(pin, FunctionDescriptor.of(ValueLayout.JAVA_INT,
            ValueLayout.JAVA_INT, ValueLayout.ADDRESS, ValueLayout.ADDRESS), Linker.Option.captureCallState("GetLastError"));
        memoryCall = linker.downcallHandle(memory, FunctionDescriptor.of(ValueLayout.JAVA_LONG,
            ValueLayout.ADDRESS, ValueLayout.ADDRESS, ValueLayout.JAVA_LONG));
        readCall = linker.downcallHandle(read, FunctionDescriptor.of(ValueLayout.JAVA_INT,
            ValueLayout.ADDRESS, ValueLayout.ADDRESS, ValueLayout.ADDRESS, ValueLayout.JAVA_LONG,
            ValueLayout.ADDRESS), Linker.Option.captureCallState("GetLastError"));
        frame = Arena.ofConfined();
        long[] sizes = {state.byteSize(), QUERY.length() + 1L, 8, 48, 4, 48, 8, 28,
            WindowsApiSetPlan.MAXIMUM_BYTES, 8, 258};
        for (int index = 0; index < buffers.length; index++) {
            MemorySegment buffer = frame.allocate(sizes[index], 8);
            buffers[index] = buffer;
            if (!buffer.isNative() || buffer.address() <= 65_535 || buffer.address() % 8 != 0 ||
                buffer.address() > Long.MAX_VALUE - sizes[index] || !buffer.scope().equals(frame.scope()) ||
                !buffer.isAccessibleBy(thread)) throw refused();
            for (int prior = 0; prior < index; prior++) rejectAlias(buffer.address(), sizes[index], buffers[prior]);
            for (MemorySegment entry : new MemorySegment[] {pin, resolve, memory, read, ntdll}) rejectAlias(entry.address(), 1, buffer);
            buffer.fill((byte) 0);
        }
        for (int index = 0; index < QUERY.length(); index++) buffers[1].set(ValueLayout.JAVA_BYTE, index, (byte) QUERY.charAt(index));
    }

    private void resolveQuery() throws Throwable {
        requireFrame();
        nativeReturnUnconfirmed = true;
        rawQuery = (long) resolveCall.invokeExact(buffers[0], ntdll, buffers[1]);
        nativeReturnUnconfirmed = false;
        lastError = buffers[0].get(ValueLayout.JAVA_INT, errorOffset);
        if (rawQuery != expectedQuery) throw refused();
        rejectFrameAlias(rawQuery, 1);
        queryEntry = MemorySegment.ofAddress(rawQuery).reinterpret(originalArena, null);
        nativeReturnUnconfirmed = true;
        queryPinStatus = (int) pinCall.invokeExact(buffers[0], 5, queryEntry, buffers[2]);
        rawQueryProvider = buffers[2].get(ValueLayout.JAVA_LONG, 0);
        nativeReturnUnconfirmed = false;
        lastError = buffers[0].get(ValueLayout.JAVA_INT, errorOffset);
        if (queryPinStatus == 0 || rawQueryProvider != ntdll.address()) throw refused();
        queryCall = linker.downcallHandle(queryEntry, FunctionDescriptor.of(ValueLayout.JAVA_INT,
            ValueLayout.ADDRESS, ValueLayout.JAVA_INT, ValueLayout.ADDRESS, ValueLayout.JAVA_INT, ValueLayout.ADDRESS));
    }

    private void queryProcess() throws Throwable {
        requireFrame();
        nativeReturnUnconfirmed = true;
        processStatus = (int) queryCall.invokeExact(CURRENT_PROCESS, 0, buffers[3], 48, buffers[4]);
        nativeReturnUnconfirmed = false;
        if (processStatus != 0 || buffers[4].get(ValueLayout.JAVA_INT, 0) != 48 ||
            buffers[3].get(ValueLayout.JAVA_LONG, 32) != ProcessHandle.current().pid()) throw refused();
        peb = buffers[3].get(ValueLayout.JAVA_LONG, 8);
        if (!pointer(peb) || peb % 8 != 0 || peb > Long.MAX_VALUE - 0x70) throw refused();
    }

    private long readNamespacePointer() throws Throwable {
        read(peb + 0x68, buffers[6], 8); // Native AMD64 PEB ApiSetMap; unsupported layouts must refuse.
        long value = buffers[6].get(ValueLayout.JAVA_LONG, 0);
        if (!pointer(value) || value % 4096 != 0) throw refused();
        return value;
    }

    private byte[] observeRegion(long address) throws Throwable {
        requireFrame();
        rejectFrameAlias(address, 1);
        buffers[5].fill((byte) 0);
        nativeReturnUnconfirmed = true;
        queryBytes = (long) memoryCall.invokeExact(MemorySegment.ofAddress(address), buffers[5], 48L);
        nativeReturnUnconfirmed = false;
        if (queryBytes != 48) throw refused();
        byte[] region = buffers[5].toArray(ValueLayout.JAVA_BYTE);
        requireRegion(region, address, 28);
        return region;
    }

    static void requireRegion(byte[] region, long address, int bytes) {
        if (region == null || region.length != 48 || !pointer(address) || address % 4096 != 0 ||
            bytes < 28 || bytes > WindowsApiSetPlan.MAXIMUM_BYTES) throw refused();
        long base = longAt(region, 0), allocation = longAt(region, 8), size = longAt(region, 24);
        if (base != address || allocation != address || size < bytes || size > WindowsApiSetPlan.MAXIMUM_BYTES ||
            size % 4096 != 0 || address > Long.MAX_VALUE - size || intAt(region, 16) != 2 ||
            intAt(region, 20) != 0 || intAt(region, 32) != 0x1000 || intAt(region, 36) != 2 ||
            intAt(region, 40) != 0x40000) throw refused(); // MEM_COMMIT, PAGE_READONLY, MEM_MAPPED only.
    }

    static int checkedHeader(byte[] header) {
        if (header == null || header.length != 28 || intAt(header, 0) != 6 || intAt(header, 8) != 0) throw refused();
        int size = intAt(header, 4);
        if (size < 28 || size > WindowsApiSetPlan.MAXIMUM_BYTES) throw refused();
        return size;
    }

    private void read(long address, MemorySegment output, int bytes) throws Throwable {
        requireFrame();
        if (!pointer(address) || bytes < 1 || bytes > WindowsApiSetPlan.MAXIMUM_BYTES ||
            address > Long.MAX_VALUE - bytes || output == null || bytes > output.byteSize()) throw refused();
        rejectFrameAlias(address, bytes);
        output.fill((byte) 0);
        buffers[9].fill((byte) 0);
        nativeReturnUnconfirmed = true;
        readStatus = (int) readCall.invokeExact(buffers[0], CURRENT_PROCESS, MemorySegment.ofAddress(address),
            output, (long) bytes, buffers[9]);
        readBytes = buffers[9].get(ValueLayout.JAVA_LONG, 0);
        nativeReturnUnconfirmed = false;
        lastError = buffers[0].get(ValueLayout.JAVA_INT, errorOffset);
        if (readStatus == 0 || readBytes != bytes) throw refused();
    }

    private void recheckNamespace() throws Throwable {
        if (snapshot == null || originalRegion == null || readNamespacePointer() != namespaceAddress ||
            !Arrays.equals(originalRegion, observeRegion(namespaceAddress))) throw refused();
        read(namespaceAddress, buffers[8], snapshot.length);
        for (int index = 0; index < snapshot.length; index++) {
            if (snapshot[index] != buffers[8].get(ValueLayout.JAVA_BYTE, index)) throw refused();
        }
        if (readNamespacePointer() != namespaceAddress || !Arrays.equals(originalRegion, observeRegion(namespaceAddress))) throw refused();
    }

    WindowsSystemExportPlan.Target resolve(String module, String name) {
        requireFrame();
        if (!observed || sealed || plan == null) throw refused();
        try {
            WindowsSystemExportPlan.Resolution result = owner.apiSetGraph(this).resolvePlan(module, name, plan);
            for (WindowsSystemExportPlan.ApiRoute route : result.routes()) observeRoute(route);
            return result.target();
        } catch (Throwable caught) { throw fail(caught); }
    }

    private void observeRoute(WindowsSystemExportPlan.ApiRoute route) throws Throwable {
        requireFrame();
        phase = 9;
        String contract = route.contract();
        if (contract == null || contract.length() > 128 || !plan.defaultHost(contract).equals(route.host())) throw refused();
        WindowsOriginalSystemModuleCandidate provider = null;
        for (int slot = 0; slot < 8; slot++) {
            if (WindowsOriginalSystemModulesCandidate.fixedName(slot).equals(route.host())) provider = owner.module(slot);
        }
        if (provider == null) throw refused(); // Refuse before any lookup outside the independently retained cohort.
        long expected = provider.originalModuleBits();
        for (int index = 0; index < routeCount; index++) {
            if (contracts[index].equals(contract)) {
                if (routeProviders[index] != provider || routeReturns[index] == 0 || rawRouteModules[index] != expected) throw refused();
                return;
            }
        }
        if (routeCount == MAXIMUM_ROUTES) throw refused();
        int index = routeCount++;
        contracts[index] = contract;
        routeProviders[index] = provider;
        buffers[10].fill((byte) 0);
        buffers[2].fill((byte) 0);
        for (int character = 0; character < contract.length(); character++) {
            buffers[10].setAtIndex(ValueLayout.JAVA_SHORT, character, (short) contract.charAt(character));
        }
        nativeReturnUnconfirmed = true;
        routeReturns[index] = (int) pinCall.invokeExact(buffers[0], 1, buffers[10], buffers[2]);
        rawRouteModules[index] = buffers[2].get(ValueLayout.JAVA_LONG, 0); // Retain permanent PIN before interpretation.
        nativeReturnUnconfirmed = false;
        lastError = buffers[0].get(ValueLayout.JAVA_INT, errorOffset);
        if (routeReturns[index] == 0 || rawRouteModules[index] != expected) throw refused();
    }

    void finishRoutes() {
        requireFrame();
        if (!observed || sealed) throw refused();
        try {
            phase = 10;
            recheckNamespace();
            retireFrame();
            if (!frameRetired || failure.retirementFailed()) throw refused();
            sealed = true;
        } catch (Throwable caught) { throw fail(caught); }
    }

    void requireSealed() {
        requireOriginal();
        if (!sealed || !frameRetired || nativeReturnUnconfirmed || failure.retirementFailed()) throw refused();
    }

    private Failure fail(Throwable caught) {
        if (!failed) { failure.operationFailure = caught; failed = true; }
        retireFrame();
        return failure;
    }

    private void retireFrame() {
        if (Thread.currentThread() != thread) throw refused();
        if (frameRetired || nativeReturnUnconfirmed) return;
        frameRetired = true;
        for (int index = 0; index < buffers.length; index++) {
            if (buffers[index] != null) {
                try { buffers[index].fill((byte) 0); }
                catch (Throwable caught) { failure.clearFailures[index] = caught; }
            }
        }
        if (frame != null) {
            try { frame.close(); }
            catch (Throwable caught) { failure.closeFailure = caught; }
        }
        // No FreeLibrary or close of the original module/arena: every successful PIN lives to process exit.
    }

    String failureOperation() {
        if (nativeReturnUnconfirmed) return "API_SET_RETURN_UNKNOWN";
        if (failure.retirementFailed()) return "API_SET_RETIREMENT";
        return switch (phase) {
            case 1 -> "API_SET_FRAME";
            case 2 -> "API_SET_QUERY_EXPORT";
            case 3 -> "API_SET_PROCESS_QUERY";
            case 4 -> "API_SET_NAMESPACE_POINTER";
            case 5 -> "API_SET_NAMESPACE_REGION";
            case 6 -> "API_SET_NAMESPACE_HEADER";
            case 7 -> "API_SET_NAMESPACE_DATA";
            case 8, 10 -> "API_SET_NAMESPACE_RECHECK";
            case 9 -> "API_SET_ROUTE_PIN";
            default -> "API_SET_PRECONDITION";
        };
    }
    boolean hasFailed() { return failed; }

    private void rejectFrameAlias(long address, long size) {
        for (MemorySegment buffer : buffers) if (buffer != null) rejectAlias(address, size, buffer);
    }
    private static void rejectAlias(long address, long size, MemorySegment buffer) {
        if (address < buffer.address() + buffer.byteSize() && buffer.address() < address + size) throw refused();
    }
    private static boolean pointer(long value) { return value > 65_535 && value <= 0x00007fffffffffffL; }
    private static int intAt(byte[] bytes, int at) {
        return (bytes[at] & 255) | (bytes[at + 1] & 255) << 8 | (bytes[at + 2] & 255) << 16 | (bytes[at + 3] & 255) << 24;
    }
    private static long longAt(byte[] bytes, int at) {
        return Integer.toUnsignedLong(intAt(bytes, at)) | Integer.toUnsignedLong(intAt(bytes, at + 4)) << 32;
    }
    private static IllegalStateException refused() {
        return new IllegalStateException("Original API-set routing is incomplete or unsupported");
    }
}
