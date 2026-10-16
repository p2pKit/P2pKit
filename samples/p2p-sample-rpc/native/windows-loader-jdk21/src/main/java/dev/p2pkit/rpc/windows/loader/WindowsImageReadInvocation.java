package dev.p2pkit.rpc.windows.loader;

import java.lang.foreign.Arena;
import java.lang.foreign.FunctionDescriptor;
import java.lang.foreign.Linker;
import java.lang.foreign.MemoryLayout;
import java.lang.foreign.MemorySegment;
import java.lang.foreign.ValueLayout;
import java.lang.invoke.MethodHandle;
import java.nio.ByteOrder;
import java.util.Arrays;

/**
 * Dormant, bounded original-image observation, NOT bootstrap, mapping custody or provider admission.
 * A future reviewed caller must supply exclusively retained original OS/module owners and derive the range
 * and policy from its independently pinned PE plan. References, scopes and matching queries prove none of that.
 * Queries cannot exclude intervening mapping changes/COW. No arbitrary Java native-memory dereference occurs:
 * only the fixed current-process ReadProcessMemory call copies into our privately owned bounded buffer.
 */
final class WindowsImageReadInvocation {
    enum Kind { EXECUTABLE, DATA }

    static final int MAXIMUM_BYTES = 65_536;
    static final MemoryLayout INFORMATION = MemoryLayout.sequenceLayout(6, ValueLayout.JAVA_LONG);
    static final MemoryLayout OUTPUT = MemoryLayout.sequenceLayout(MAXIMUM_BYTES, ValueLayout.JAVA_BYTE);
    static final FunctionDescriptor QUERY = FunctionDescriptor.of(ValueLayout.JAVA_LONG,
        ValueLayout.ADDRESS, ValueLayout.ADDRESS.withTargetLayout(INFORMATION), ValueLayout.JAVA_LONG);
    static final FunctionDescriptor READ = FunctionDescriptor.of(ValueLayout.JAVA_INT,
        ValueLayout.ADDRESS, ValueLayout.ADDRESS, ValueLayout.ADDRESS.withTargetLayout(OUTPUT),
        ValueLayout.JAVA_LONG, ValueLayout.ADDRESS.withTargetLayout(ValueLayout.JAVA_LONG));
    private static final MemorySegment CURRENT_PROCESS = MemorySegment.ofAddress(-1L);

    static final class Result {
        final WindowsImageReadInvocation retainedInvocation;

        private Result(WindowsImageReadInvocation invocation) { retainedInvocation = invocation; }

        /** A bounded defensive copy; neither private buffers nor a mapped pointer escape. */
        byte[] bytes() {
            retainedInvocation.requireThread();
            if (!retainedInvocation.succeeded) throw new IllegalStateException("Original image read is not successful");
            retainedInvocation.requireOriginalScopes();
            return retainedInvocation.snapshot.clone();
        }
    }

    static final class Failure extends RuntimeException {
        private static final long serialVersionUID = 1L;
        final transient WindowsImageReadInvocation retainedInvocation;
        Throwable preparationFailure;
        Throwable operationFailure;
        final Throwable[] clearFailures = new Throwable[5];
        Throwable arenaCloseFailure;

        Failure(WindowsImageReadInvocation invocation) {
            super("Original image observation failed with original ownership retained", null, false, false);
            retainedInvocation = invocation;
        }

        boolean retirementFailed() {
            if (arenaCloseFailure != null) return true;
            for (int index = 0; index < clearFailures.length; index++) if (clearFailures[index] != null) return true;
            return false;
        }
    }

    private final Thread thread = Thread.currentThread();
    final Object bootstrapOwner;
    final Object moduleOwner;
    final Object originalImagePlan;
    private final MemorySegment queryEntry;
    private final MemorySegment readEntry;
    private final Arena bootstrapArena;
    private final MemorySegment module;
    private final Arena moduleArena;
    private final long imageBytes;
    private final long rva;
    private final int length;
    private final Kind kind;
    private final Failure failure = new Failure(this);
    private final Result result = new Result(this);
    private final MemorySegment[] buffers = new MemorySegment[5]; // before, after, count, bytes, captured state
    private final long[] before = new long[8];
    private final long[] after = new long[8];
    private final int[] lastErrors = new int[3];
    private final boolean[] errorsObserved = new boolean[3];
    private final byte[] snapshot;
    private Arena frameArena;
    private MemorySegment source;
    private MethodHandle query;
    private MethodHandle read;
    private long errorOffset;
    private long stateBytes;
    private long firstQuerySize;
    private long lastQuerySize;
    private int readStatus;
    private long bytesRead;
    private int phase;
    private boolean attempted;
    private boolean active;
    private boolean retired;
    private boolean succeeded;

    private WindowsImageReadInvocation(Object bootstrapOwner, Object moduleOwner, Object originalImagePlan,
                                       MemorySegment queryEntry, MemorySegment readEntry, Arena bootstrapArena,
                                       MemorySegment module, Arena moduleArena, long imageBytes,
                                       long rva, int length, Kind kind) {
        this.bootstrapOwner = bootstrapOwner;
        this.moduleOwner = moduleOwner;
        this.originalImagePlan = originalImagePlan;
        this.queryEntry = queryEntry;
        this.readEntry = readEntry;
        this.bootstrapArena = bootstrapArena;
        this.module = module;
        this.moduleArena = moduleArena;
        this.imageBytes = imageBytes;
        this.rva = rva;
        this.length = length;
        this.kind = kind;
        snapshot = new byte[length]; // Reserve the result and failure owners before native effects.
    }

    static WindowsImageReadInvocation prepare(Object bootstrapOwner, Object moduleOwner, Object originalImagePlan,
                                              MemorySegment queryEntry, MemorySegment readEntry, Arena bootstrapArena,
                                              MemorySegment module, Arena moduleArena, long imageBytes,
                                              long rva, int length, Kind kind) {
        WindowsLoaderRuntime.requireDiagnosticRuntime();
        if (WindowsImageReadInvocation.class.getModule() != WindowsLoaderRuntime.class.getModule() ||
            Thread.currentThread().isVirtual()) {
            throw new IllegalStateException("Original image observation requires its boot module/platform thread");
        }
        if (bootstrapOwner == null || moduleOwner == null || originalImagePlan == null || kind == null ||
            !originalSegment(queryEntry, bootstrapArena) || !originalSegment(readEntry, bootstrapArena) ||
            !originalSegment(module, moduleArena) || queryEntry.address() == readEntry.address() ||
            imageBytes < 4096 || imageBytes > 128L * 1024 * 1024 || (imageBytes & 4095) != 0 ||
            (module.address() & 65_535) != 0 || module.address() > Long.MAX_VALUE - imageBytes ||
            length < 1 || length > MAXIMUM_BYTES || rva < 0 || rva > imageBytes - length ||
            within(queryEntry.address(), module.address(), imageBytes) ||
            within(readEntry.address(), module.address(), imageBytes)) {
            throw new IllegalArgumentException("Invalid original image observation binding");
        }
        Linker linker = Linker.nativeLinker();
        if (linker.getClass().getModule() != Object.class.getModule() || linker.getClass().getClassLoader() != null ||
            !linker.getClass().getName().equals("jdk.internal.foreign.abi.x64.windows.Windowsx64Linker") ||
            ValueLayout.ADDRESS.byteSize() != 8 || ByteOrder.nativeOrder() != ByteOrder.LITTLE_ENDIAN ||
            INFORMATION.byteSize() != 48 || INFORMATION.byteAlignment() != 8) {
            throw new IllegalStateException("Original image observation requires the actual Windows x64 linker");
        }
        WindowsImageReadInvocation invocation = new WindowsImageReadInvocation(bootstrapOwner, moduleOwner,
            originalImagePlan, queryEntry, readEntry, bootstrapArena, module, moduleArena, imageBytes, rva, length, kind);
        try {
            MemoryLayout state = Linker.Option.captureStateLayout();
            MemoryLayout error = state.select(MemoryLayout.PathElement.groupElement("GetLastError"));
            long offset = state.byteOffset(MemoryLayout.PathElement.groupElement("GetLastError"));
            if (!(error instanceof ValueLayout.OfInt) || error.byteSize() != 4 || error.byteAlignment() != 4 ||
                state.byteSize() < 4 || state.byteSize() > 64 || offset < 0 || offset % 4 != 0 ||
                offset > state.byteSize() - 4) {
                throw new IllegalStateException("Unsupported Windows captured error layout");
            }
            invocation.prepareFrame(linker.downcallHandle(queryEntry, QUERY, Linker.Option.captureCallState("GetLastError")),
                linker.downcallHandle(readEntry, READ, Linker.Option.captureCallState("GetLastError")), state, offset);
            return invocation;
        } catch (Throwable caught) {
            invocation.failure.preparationFailure = caught;
            try { invocation.retireFrame(); } catch (Failure ignored) { /* Preserve independent failures. */ }
            throw invocation.failure;
        }
    }

    /** Off-host tests reflect this private inert frame only; there is no production host bypass. */
    private void prepareFrame(MethodHandle query, MethodHandle read, MemoryLayout state, long offset) {
        this.query = query;
        this.read = read;
        errorOffset = offset;
        stateBytes = state.byteSize();
        frameArena = Arena.ofConfined();
        buffers[0] = frameArena.allocate(INFORMATION);
        buffers[1] = frameArena.allocate(INFORMATION);
        buffers[2] = frameArena.allocate(ValueLayout.JAVA_LONG);
        buffers[3] = frameArena.allocate(OUTPUT);
        buffers[4] = frameArena.allocate(state);
        // Derive only a zero-length query argument from the retained original image. Never read this view in Java.
        source = module.reinterpret(imageBytes, moduleArena, null).asSlice(rva, 0);
        validateBuffers();
    }

    private static boolean originalSegment(MemorySegment segment, Arena arena) {
        return segment != null && arena != null && segment.isNative() && segment.address() > 0 &&
            arena.scope().isAlive() && !arena.scope().equals(Arena.global().scope()) &&
            segment.scope().equals(arena.scope()) && segment.isAccessibleBy(Thread.currentThread());
    }

    private static boolean within(long address, long base, long size) { return address >= base && address < base + size; }

    private void requireThread() {
        if (Thread.currentThread() != thread) throw new IllegalStateException("Image observation accessed outside its thread");
    }

    private void requireOriginalScopes() {
        if (!originalSegment(queryEntry, bootstrapArena) || !originalSegment(readEntry, bootstrapArena) ||
            !originalSegment(module, moduleArena)) {
            throw new IllegalStateException("Original image observation scopes are unavailable");
        }
    }

    private void validateBuffers() {
        for (int index = 0; index < buffers.length; index++) {
            MemorySegment buffer = buffers[index];
            long size = index < 2 ? 48 : index == 2 ? 8 : index == 3 ? MAXIMUM_BYTES : stateBytes;
            int alignment = index < 3 ? 8 : index == 3 ? 1 : 4;
            if (buffer == null || !buffer.isNative() || buffer.byteSize() != size || buffer.address() <= 0 ||
                buffer.address() > Long.MAX_VALUE - size || buffer.address() % alignment != 0 ||
                !buffer.scope().equals(frameArena.scope()) || !buffer.scope().isAlive() || !buffer.isAccessibleBy(thread) ||
                (buffer.address() < module.address() + imageBytes && module.address() < buffer.address() + size) ||
                within(queryEntry.address(), buffer.address(), size) || within(readEntry.address(), buffer.address(), size)) {
                throw new IllegalStateException("Invalid original image observation buffer");
            }
            for (int prior = 0; prior < index; prior++) {
                if (buffer.address() < buffers[prior].address() + buffers[prior].byteSize() &&
                    buffers[prior].address() < buffer.address() + size) {
                    throw new IllegalStateException("Original image observation buffers overlap");
                }
            }
        }
    }

    private void queryRegion(int index) throws Throwable {
        phase = index == 0 ? 1 : 3;
        requireOriginalScopes();
        long returned;
        active = true;
        try { returned = (long) query.invokeExact(buffers[4], source, buffers[index], 48L); }
        finally { active = false; }
        if (index == 0) firstQuerySize = returned; else lastQuerySize = returned;
        observeError(index == 0 ? 0 : 2);
        requireOriginalScopes();
        if (returned != 48) throw new IllegalStateException("Original image query was incomplete");
        MemorySegment info = buffers[index];
        long[] fields = index == 0 ? before : after;
        fields[0] = info.get(ValueLayout.JAVA_LONG, 0);
        fields[1] = info.get(ValueLayout.JAVA_LONG, 8);
        fields[2] = Integer.toUnsignedLong(info.get(ValueLayout.JAVA_INT, 16));
        fields[3] = Short.toUnsignedLong(info.get(ValueLayout.JAVA_SHORT, 20));
        fields[4] = info.get(ValueLayout.JAVA_LONG, 24);
        fields[5] = Integer.toUnsignedLong(info.get(ValueLayout.JAVA_INT, 32));
        fields[6] = Integer.toUnsignedLong(info.get(ValueLayout.JAVA_INT, 36));
        fields[7] = Integer.toUnsignedLong(info.get(ValueLayout.JAVA_INT, 40));
        // AllocationProtect is initial allocation policy, not current page protection. In particular a
        // loaded image can start EXECUTE_WRITECOPY (0x80) while its current code pages are EXECUTE_READ (0x20).
        long base = fields[0];
        long size = fields[4];
        long protection = fields[6];
        boolean readable = kind == Kind.EXECUTABLE ? protection == 0x20 :
            protection == 0x02 || protection == 0x04 || protection == 0x08;
        if (base < module.address() || (base & 4095) != 0 || size <= 0 || (size & 4095) != 0 ||
            base > Long.MAX_VALUE - size || base + size > module.address() + imageBytes ||
            source.address() < base || source.address() > base + size - length ||
            fields[1] != module.address() || fields[5] != 0x1000 || fields[7] != 0x1000000 || !readable) {
            throw new IllegalStateException("Original image range is not within the required committed image region");
        }
    }

    private void observeError(int index) {
        lastErrors[index] = buffers[4].get(ValueLayout.JAVA_INT, errorOffset);
        errorsObserved[index] = true; // A successful Win32 call may leave any stale error value.
    }

    Result invoke() {
        requireThread();
        if (attempted || retired) throw new IllegalStateException("Original image observation is already consumed");
        attempted = true;
        boolean accepted = false;
        try {
            try {
                requireOriginalScopes();
                validateBuffers();
                queryRegion(0);
                phase = 2;
                requireOriginalScopes();
                active = true;
                try {
                    readStatus = (int) read.invokeExact(buffers[4], CURRENT_PROCESS, source, buffers[3],
                        (long) length, buffers[2]);
                } finally { active = false; }
                observeError(1);
                bytesRead = buffers[2].get(ValueLayout.JAVA_LONG, 0);
                requireOriginalScopes();
                if (readStatus == 0 || bytesRead != length) throw new IllegalStateException("Original image read was incomplete");
                queryRegion(1);
                for (int index = 0; index < before.length; index++) {
                    if (before[index] != after[index]) throw new IllegalStateException("Original image mapping changed during read");
                }
                phase = 4;
                MemorySegment.copy(buffers[3], ValueLayout.JAVA_BYTE, 0, snapshot, 0, length);
                accepted = true;
            } catch (Throwable caught) {
                failure.operationFailure = caught;
                throw failure;
            }
        } finally {
            try { retireFrame(); }
            finally {
                succeeded = accepted && !failure.retirementFailed();
                if (!succeeded) Arrays.fill(snapshot, (byte) 0);
            }
        }
        return result;
    }

    /** Retire only private data frames, never original OS/module scopes, loaded modules or the pseudo-handle. */
    void retireFrame() {
        requireThread();
        if (active) throw new IllegalStateException("Original image observation is still active");
        if (retired) {
            if (failure.retirementFailed()) throw failure;
            return;
        }
        retired = true;
        for (int index = 0; index < buffers.length; index++) {
            try { if (buffers[index] != null) buffers[index].fill((byte) 0); }
            catch (Throwable caught) { failure.clearFailures[index] = caught; }
        }
        try { if (frameArena != null) frameArena.close(); }
        catch (Throwable caught) { failure.arenaCloseFailure = caught; }
        if (failure.retirementFailed()) throw failure;
    }
}
