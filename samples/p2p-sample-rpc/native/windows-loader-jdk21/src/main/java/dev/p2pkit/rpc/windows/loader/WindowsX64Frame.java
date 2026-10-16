package dev.p2pkit.rpc.windows.loader;

import java.lang.foreign.Arena;
import java.lang.foreign.MemoryLayout;
import java.lang.foreign.MemorySegment;
import java.lang.foreign.ValueLayout;
import java.nio.ByteOrder;
import java.util.Locale;

/**
 * Owned bounded data for future handle-relative Windows calls; no addresses/handles supplied by a caller.
 * Only Java FFM arena allocation occurs. This does not perform OS discovery, lookup, downcalls or loading.
 * Package-private until an independently admitted native verifier can own these borrowed segments.
 */
final class WindowsX64Frame implements AutoCloseable {
    static final int MAXIMUM_COMPONENT_CHARS = 255;
    static final ValueLayout.OfShort USHORT = ValueLayout.JAVA_SHORT.withOrder(ByteOrder.LITTLE_ENDIAN);
    static final MemoryLayout UNICODE_STRING = MemoryLayout.structLayout(
        USHORT.withName("Length"), USHORT.withName("MaximumLength"), MemoryLayout.paddingLayout(4),
        ValueLayout.ADDRESS.withOrder(ByteOrder.LITTLE_ENDIAN).withName("Buffer"));
    static final MemoryLayout IO_STATUS_BLOCK = MemoryLayout.structLayout(
        ValueLayout.JAVA_LONG.withOrder(ByteOrder.LITTLE_ENDIAN).withName("StatusOrPointer"),
        ValueLayout.JAVA_LONG.withOrder(ByteOrder.LITTLE_ENDIAN).withName("Information"));

    /** After-operation reporting seam for portable tests only; it cannot admit native calls or loading. */
    interface CleanupObservation {
        void afterClear();
        void afterArenaClose();
    }

    private static final CleanupObservation NOOP = new CleanupObservation() {
        @Override public void afterClear() {}
        @Override public void afterArenaClose() {}
    };
    private final Thread owner = Thread.currentThread();
    private final CleanupObservation cleanupObservation;
    private final CloseFailure closeFailure = new CloseFailure(this);
    private Arena arena;
    private MemorySegment component;
    private MemorySegment unicode;
    private MemorySegment status;
    private MemorySegment componentView;
    private MemorySegment unicodeView;
    private boolean closed;

    private WindowsX64Frame(CleanupObservation observation) { cleanupObservation = observation; }

    /** Exact distinct failure slots; no suppression allocation may erase an uncertain retirement. */
    static final class CloseFailure extends RuntimeException {
        private static final long serialVersionUID = 1L;
        final transient WindowsX64Frame retainedFrame;
        Throwable clearFailure;
        Throwable arenaCloseFailure;

        CloseFailure(WindowsX64Frame frame) {
            super("Windows data-frame retirement is uncertain");
            retainedFrame = frame;
        }

        boolean failed() { return clearFailure != null || arenaCloseFailure != null; }
    }

    /** Preallocated before any arena; a failed partial acquisition must not discard uncertain ownership. */
    static final class AcquisitionFailure extends RuntimeException {
        private static final long serialVersionUID = 1L;
        final transient WindowsX64Frame retainedFrame;
        Throwable cleanupFailure;

        AcquisitionFailure(WindowsX64Frame frame) {
            super("Windows data-frame initialization failed with retained cleanup ownership");
            retainedFrame = frame;
        }
    }

    static WindowsX64Frame openComponent(String name) {
        return acquire(name, NOOP);
    }

    static WindowsX64Frame openForValidation(String name, CleanupObservation observation) {
        if (observation == null) throw new IllegalArgumentException("Missing model cleanup observation");
        return acquire(name, observation);
    }

    private static WindowsX64Frame acquire(String name, CleanupObservation observation) {
        WindowsLoaderRuntime.requireDiagnosticRuntime();
        validateComponent(name);
        if (ValueLayout.ADDRESS.byteSize() != 8 || UNICODE_STRING.byteSize() != 16 ||
            UNICODE_STRING.byteOffset(MemoryLayout.PathElement.groupElement("Buffer")) != 8 ||
            IO_STATUS_BLOCK.byteSize() != 16) {
            throw new IllegalStateException("Unsupported Windows x64 data layout");
        }
        // Allocate the owning wrapper before its arena or any native memory; never publish partial state.
        WindowsX64Frame frame = new WindowsX64Frame(observation);
        AcquisitionFailure retained = new AcquisitionFailure(frame);
        try {
            frame.arena = Arena.ofConfined();
            frame.component = frame.arena.allocate((name.length() + 1L) * 2, 2);
            frame.unicode = frame.arena.allocate(UNICODE_STRING);
            frame.status = frame.arena.allocate(IO_STATUS_BLOCK);
            for (int i = 0; i < name.length(); i++) {
                frame.component.set(USHORT, i * 2L, (short) name.charAt(i));
            }
            // Arena allocation zero-initializes the terminator, padding and complete output block.
            frame.unicode.set(USHORT, 0, (short) (name.length() * 2));
            frame.unicode.set(USHORT, 2, (short) ((name.length() + 1) * 2));
            frame.unicode.set(ValueLayout.ADDRESS.withOrder(ByteOrder.LITTLE_ENDIAN), 8, frame.component);
            frame.componentView = frame.component.asReadOnly();
            frame.unicodeView = frame.unicode.asReadOnly();
            return frame;
        } catch (Throwable failure) {
            try { frame.close(); } catch (Throwable cleanup) {
                retained.initCause(failure);
                retained.cleanupFailure = cleanup;
                throw retained;
            }
            throw failure;
        }
    }

    private static void validateComponent(String name) {
        if (name == null || name.isEmpty() || name.length() > MAXIMUM_COMPONENT_CHARS ||
            !name.matches("[A-Za-z0-9][A-Za-z0-9 ._-]*") || name.endsWith(".") || name.endsWith(" ")) {
            throw new IllegalArgumentException("Unsupported bounded Windows package component");
        }
        String stem = name.split("\\.", 2)[0].toUpperCase(Locale.ROOT);
        if (stem.equals("CON") || stem.equals("PRN") || stem.equals("AUX") || stem.equals("NUL") ||
            stem.matches("(?:COM|LPT)[1-9]")) {
            throw new IllegalArgumentException("Reserved Windows package component");
        }
    }

    private void requireOwner() {
        if (Thread.currentThread() != owner) {
            throw new IllegalStateException("Windows call-frame accessed outside its owning thread");
        }
    }

    private void requireOpen() {
        requireOwner();
        if (closed) throw new IllegalStateException("Windows call-frame is retired");
    }

    MemorySegment unicodeString() { requireOpen(); return unicodeView; }
    MemorySegment ioStatusBlock() { requireOpen(); return status; }
    MemorySegment componentBytes() { requireOpen(); return componentView; }

    /** Clears all buffers while still owned; reusable only as zeroed data, never as a restored component. */
    void clear() {
        requireOpen();
        clearAllocated();
    }

    private void clearAllocated() {
        if (status != null) status.fill((byte) 0);
        if (unicode != null) unicode.fill((byte) 0);
        if (component != null) component.fill((byte) 0);
    }

    @Override public void close() {
        requireOwner();
        if (closed) {
            if (closeFailure.failed()) throw closeFailure;
            return;
        }
        closed = true;
        try {
            clearAllocated();
            cleanupObservation.afterClear();
        } catch (Throwable caught) { closeFailure.clearFailure = caught; }
        try {
            if (arena != null) arena.close();
            cleanupObservation.afterArenaClose();
        } catch (Throwable caught) { closeFailure.arenaCloseFailure = caught; }
        if (closeFailure.failed()) {
            closeFailure.initCause(closeFailure.clearFailure != null ?
                closeFailure.clearFailure : closeFailure.arenaCloseFailure);
            throw closeFailure;
        }
    }
}
