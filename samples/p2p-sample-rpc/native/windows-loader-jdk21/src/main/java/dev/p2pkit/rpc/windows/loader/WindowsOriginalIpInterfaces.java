package dev.p2pkit.rpc.windows.loader;

import java.lang.foreign.Arena;
import java.lang.foreign.FunctionDescriptor;
import java.lang.foreign.MemorySegment;
import java.lang.foreign.ValueLayout;
import java.lang.invoke.MethodHandle;
import java.util.List;

/** Original installed system-image/export custody continued into read-only IP Helper observations. */
final class WindowsOriginalIpInterfaces {
    private static final String[] NAMES = {"GetIpInterfaceTable", "FreeMibTable"};
    private final WindowsInstalledProfileCandidate parent;
    private final Thread originalThread = Thread.currentThread();
    private WindowsOriginalSystemModulesCandidate systems;
    private WindowsOriginalSystemModuleCandidate ip;
    private Arena permanentEntries;
    private Arena preparation;
    private MemorySegment name, output;
    private MethodHandle query, free;
    private boolean attempted, completed, unknownReturn;
    private Throwable failure;
    private Query retainedQuery;
    private int preparationPhase;

    WindowsOriginalIpInterfaces(WindowsInstalledProfileCandidate parent) { this.parent = parent; }

    void prepare() {
        preparationPhase = 1;
        parent.requireOriginalIpInterfaces(this);
        if (attempted || Thread.currentThread() != originalThread) throw refused();
        attempted = true;
        try {
            preparationPhase = 2;
            systems = parent.originalIpSystems(this);
            ip = systems.module(8);
            preparationPhase = 3;
            MemorySegment originalModule = ip.originalIpModule(this);
            preparationPhase = 4;
            var linker = parent.originalLinker();
            var resolve = linker.downcallHandle(parent.resolverEntry(1),
                FunctionDescriptor.of(ValueLayout.ADDRESS, ValueLayout.ADDRESS, ValueLayout.ADDRESS));
            var pin = linker.downcallHandle(parent.resolverEntry(0),
                FunctionDescriptor.of(ValueLayout.JAVA_INT, ValueLayout.JAVA_INT,
                    ValueLayout.ADDRESS, ValueLayout.ADDRESS));
            // The actual GPA returns are attached to one permanent shared arena, after checking their
            // physical provider. No copied RVA becomes a callable address, and no module is unloaded.
            permanentEntries = Arena.ofShared();
            preparation = Arena.ofConfined();
            name = preparation.allocate(64, 1);
            output = preparation.allocate(ValueLayout.JAVA_LONG);
            MethodHandle[] calls = new MethodHandle[2];
            for (int n = 0; n < NAMES.length; n++) {
                preparationPhase = 5 + n * 5;
                var target = systems.resolveIpExport(this, NAMES[n]);
                if (!target.module().equals("iphlpapi.dll") || target.rva() <= 0 ||
                    target.rva() >= 256L * 1024 * 1024) throw refused();
                long base = ip.originalModuleBits();
                if (base > Long.MAX_VALUE - target.rva()) throw refused();
                name.fill((byte) 0); output.fill((byte) 0);
                for (int j = 0; j < NAMES[n].length(); j++) name.set(ValueLayout.JAVA_BYTE, j, (byte) NAMES[n].charAt(j));
                preparationPhase = 6 + n * 5;
                unknownReturn = true;
                MemorySegment entry = (MemorySegment) resolve.invokeExact(originalModule, name);
                unknownReturn = false;
                if (entry.address() != base + target.rva()) throw refused();
                preparationPhase = 7 + n * 5;
                unknownReturn = true;
                int status = (int) pin.invokeExact(5, entry, output); // PIN | FROM_ADDRESS.
                unknownReturn = false;
                if (status == 0 || output.get(ValueLayout.JAVA_LONG, 0) != base) throw refused();
                preparationPhase = 8 + n * 5;
                MemorySegment retained = entry.reinterpret(permanentEntries, null);
                preparationPhase = 9 + n * 5;
                calls[n] = linker.downcallHandle(retained, n == 0
                    ? FunctionDescriptor.of(ValueLayout.JAVA_INT, ValueLayout.JAVA_SHORT, ValueLayout.ADDRESS)
                    : FunctionDescriptor.ofVoid(ValueLayout.ADDRESS));
            }
            query = calls[0]; free = calls[1];
            preparationPhase = 15;
            name.fill((byte) 0); output.fill((byte) 0);
            preparation.close();
            preparation = null;
            completed = true;
        } catch (Throwable caught) {
            failure = caught;
            // Parent was attached before entry; partial frames/PINs remain rooted, never retried/unloaded.
            throw refused();
        }
    }

    /** Fixed retained metadata only; no owner guard, exception text, address or native retry. */
    String failureOperation() {
        return switch (preparationPhase) {
            case 1 -> "IP_OBSERVER_PARENT";
            case 2 -> "IP_OBSERVER_SYSTEMS";
            case 3 -> "IP_OBSERVER_MODULE";
            case 4 -> "IP_OBSERVER_RESOLVERS";
            case 5 -> "IP_QUERY_EXPORT";
            case 6 -> "IP_QUERY_ADDRESS";
            case 7 -> "IP_QUERY_PROVIDER";
            case 8 -> "IP_QUERY_SCOPE";
            case 9 -> "IP_QUERY_HANDLE";
            case 10 -> "IP_FREE_EXPORT";
            case 11 -> "IP_FREE_ADDRESS";
            case 12 -> "IP_FREE_PROVIDER";
            case 13 -> "IP_FREE_SCOPE";
            case 14 -> "IP_FREE_HANDLE";
            case 15 -> "IP_OBSERVER_RETIREMENT";
            default -> "IP_INTERFACE_OBSERVER";
        };
    }

    void requireOriginalModule(WindowsOriginalSystemModuleCandidate candidate) {
        parent.requireOriginalIpInterfaces(this);
        if (!attempted || systems == null || candidate != ip || candidate != systems.module(8) ||
            Thread.currentThread() != originalThread) throw refused();
    }

    /** A single owner serializes read/free; uncertainty permanently seals this observer. */
    synchronized List<WindowsIpInterfaceTable.Row> read() {
        if (!completed || failure != null || unknownReturn || retainedQuery != null) throw refused();
        Query current = new Query();
        retainedQuery = current; // Root the frame before allocation or a call that may return ownership.
        try {
            current.frame = Arena.ofConfined();
            current.output = current.frame.allocate(ValueLayout.ADDRESS);
            current.output.fill((byte) 0);
            current.unknown = true;
            int status = (int) query.invokeExact((short) 0, current.output); // AF_UNSPEC; both IP families.
            current.table = current.output.get(ValueLayout.ADDRESS, 0);
            current.unknown = false;
            if (status != 0) {
                if (current.table.address() != 0) current.unknown = true;
                throw refused();
            }
            if (current.table.address() <= 65535 || current.table.address() % 8 != 0 ||
                current.table.address() == current.output.address()) {
                current.unknown = true;
                throw refused();
            }
            current.owned = true; // Successful fixed OS allocator return, not a caller-supplied pointer.
            int count = current.table.reinterpret(4).get(ValueLayout.JAVA_INT, 0);
            if (count < 1 || count > WindowsIpInterfaceTable.MAX_ROWS) throw refused();
            long bytes = 8L + (long) count * WindowsIpInterfaceTable.ROW_BYTES;
            if (current.table.address() > Long.MAX_VALUE - bytes) throw refused();
            byte[] copy = current.table.reinterpret(bytes).asSlice(8).toArray(ValueLayout.JAVA_BYTE);
            return WindowsIpInterfaceTable.parse(copy, count);
        } catch (Throwable caught) {
            if (current.unknown) failure = caught;
            throw refused();
        } finally {
            try {
                if (current.unknown) throw refused();
                if (current.owned) {
                    current.unknown = true;
                    free.invokeExact(current.table);
                    current.unknown = false;
                    current.owned = false;
                }
                if (current.output != null) current.output.fill((byte) 0);
                if (current.frame != null) current.frame.close();
                retainedQuery = null;
            } catch (Throwable caught) {
                failure = caught;
                throw refused();
            }
        }
    }

    private static final class Query {
        Arena frame;
        MemorySegment output, table;
        boolean unknown, owned;
    }

    private static IllegalStateException refused() {
        return new IllegalStateException("Original Windows IP-interface observation unavailable");
    }
}
