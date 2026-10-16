package dev.p2pkit.rpc.windows.loader;

import java.lang.foreign.Arena;
import java.lang.foreign.FunctionDescriptor;
import java.lang.foreign.Linker;
import java.lang.foreign.MemoryLayout;
import java.lang.foreign.MemorySegment;
import java.lang.foreign.ValueLayout;
import java.lang.invoke.MethodHandle;
import java.security.MessageDigest;
import java.security.Provider;

/**
 * Bounded byte observation through the original, exclusively retained synchronous JVM file handle.
 * No reopen, pathname input, seek, expected digest, DLL load or production authority is introduced.
 * A digest and unchanged metadata do not prove a mapped image, independent runtime provenance or
 * absence of pre-existing writable mappings/security handles. Startup/export authority is still required.
 */
final class WindowsOriginalJvmBytesCandidate {
    private static final int CHUNK = 65_536;
    private static final long MAXIMUM_BYTES = 512L * 1024 * 1024;
    private static final long[] SIZES = {0, CHUNK, 4, 24, 8, 24};
    private static final int[] ALIGNMENTS = {4, 8, 4, 8, 4, 8};

    static final class Failure extends RuntimeException {
        private static final long serialVersionUID = 1L;
        final transient WindowsOriginalJvmBytesCandidate retainedCandidate;
        Throwable operationFailure;
        final Throwable[] clearFailures = new Throwable[SIZES.length];
        Throwable arenaCloseFailure;

        private Failure(WindowsOriginalJvmBytesCandidate candidate) {
            super("Original JVM byte observation failed with original ownership retained", null, false, false);
            retainedCandidate = candidate;
        }

        private boolean retirementFailed() {
            if (arenaCloseFailure != null) return true;
            for (Throwable caught : clearFailures) if (caught != null) return true;
            return false;
        }
    }

    private final Thread thread = Thread.currentThread();
    private final WindowsOriginalJvmFileCandidate file;
    private final Linker linker;
    private final Arena bootstrapArena;
    private final Arena fileArena;
    private final MemorySegment fileHandle;
    private final MemorySegment readEntry;
    private final MemorySegment informationEntry;
    private final long[] originalMetadata;
    private final Failure failure = new Failure(this);
    private final MemorySegment[] buffers = new MemorySegment[SIZES.length];
    private final long[] repeatedMetadata = new long[8];
    private Arena frameArena;
    private MethodHandle readCall;
    private MethodHandle informationCall;
    private MessageDigest digest;
    private byte[] observedDigest;
    private long errorOffset;
    private long total;
    private long returnedBytes;
    private int returnedStatus;
    private int lastError;
    private int readCalls;
    private boolean readCompletionUnconfirmed;
    private boolean attempted;
    private boolean frameRetired;
    private boolean succeeded;

    WindowsOriginalJvmBytesCandidate(WindowsOriginalJvmFileCandidate file, Linker linker,
        Arena bootstrapArena, Arena fileArena, MemorySegment fileHandle, MemorySegment readEntry,
        MemorySegment informationEntry, long[] originalMetadata) {
        this.file = file;
        this.linker = linker;
        this.bootstrapArena = bootstrapArena;
        this.fileArena = fileArena;
        this.fileHandle = fileHandle;
        this.readEntry = readEntry;
        this.informationEntry = informationEntry;
        this.originalMetadata = originalMetadata.clone();
    }

    void observe() {
        requireOriginalFile();
        if (attempted) throw new IllegalStateException("Original JVM byte observation is already consumed");
        attempted = true;
        boolean accepted = false;
        try {
            if (originalMetadata.length != 8 || originalMetadata[4] <= 0 || originalMetadata[4] > MAXIMUM_BYTES) {
                throw new IllegalStateException("Original JVM byte observation lacks a bounded file size");
            }
            prepare();
            inspectMetadata();
            // The original CreateFileW handle was opened without OVERLAPPED and has never been read
            // or sought. Only this once-attached component moves its private initial-zero file pointer.
            while (total < originalMetadata[4]) {
                requireOriginalFile();
                int wanted = (int) Math.min(CHUNK, originalMetadata[4] - total);
                readOnce(wanted);
                if (returnedBytes != wanted) {
                    throw new IllegalStateException("Original JVM file ended before its retained length");
                }
                digest.update(buffers[1].asSlice(0, wanted).asByteBuffer());
                total += wanted;
            }
            requireOriginalFile();
            readOnce(1);
            if (returnedBytes != 0) throw new IllegalStateException("Original JVM file exceeds its retained length");
            inspectMetadata();
            requireOriginalFile();
            observedDigest = digest.digest();
            if (observedDigest.length != 32) throw new IllegalStateException("Invalid original file digest result");
            accepted = true;
        } catch (Throwable caught) {
            failure.operationFailure = caught;
        } finally {
            retireFrame();
            succeeded = accepted && frameRetired && !failure.retirementFailed();
        }
        if (!succeeded) throw failure;
    }

    private void prepare() throws Exception {
        digest = MessageDigest.getInstance("SHA-256", "SUN");
        Provider provider = digest.getProvider();
        if (provider.getClass().getModule() != Object.class.getModule() ||
            provider.getClass().getClassLoader() != null ||
            !provider.getClass().getName().equals("sun.security.provider.Sun") || digest.getDigestLength() != 32) {
            throw new IllegalStateException("Original runtime lacks the expected boot digest provider");
        }
        MemoryLayout state = Linker.Option.captureStateLayout();
        MemoryLayout error = state.select(MemoryLayout.PathElement.groupElement("GetLastError"));
        errorOffset = state.byteOffset(MemoryLayout.PathElement.groupElement("GetLastError"));
        if (!(error instanceof ValueLayout.OfInt) || error.byteAlignment() != 4 || state.byteSize() < 4 ||
            state.byteSize() > 64 || errorOffset < 0 || errorOffset % 4 != 0 || errorOffset > state.byteSize() - 4) {
            throw new IllegalStateException("Unsupported original file captured-error layout");
        }
        readCall = linker.downcallHandle(readEntry, FunctionDescriptor.of(ValueLayout.JAVA_INT,
            ValueLayout.ADDRESS, ValueLayout.ADDRESS, ValueLayout.JAVA_INT, ValueLayout.ADDRESS, ValueLayout.ADDRESS),
            Linker.Option.captureCallState("GetLastError"));
        informationCall = linker.downcallHandle(informationEntry, FunctionDescriptor.of(ValueLayout.JAVA_INT,
            ValueLayout.ADDRESS, ValueLayout.JAVA_INT, ValueLayout.ADDRESS, ValueLayout.JAVA_INT),
            Linker.Option.captureCallState("GetLastError"));
        prepareFrame(state);
    }

    private void prepareFrame(MemoryLayout state) {
        frameArena = Arena.ofConfined();
        for (int index = 0; index < buffers.length; index++) {
            buffers[index] = index == 0 ? frameArena.allocate(state) : frameArena.allocate(SIZES[index], ALIGNMENTS[index]);
            MemorySegment buffer = buffers[index];
            long size = index == 0 ? state.byteSize() : SIZES[index];
            if (!buffer.isNative() || buffer.byteSize() != size || buffer.address() <= 65_535 ||
                buffer.address() > Long.MAX_VALUE - size || buffer.address() % ALIGNMENTS[index] != 0 ||
                !buffer.scope().equals(frameArena.scope()) || !buffer.isAccessibleBy(thread)) {
                throw new IllegalStateException("Invalid original file byte frame");
            }
            for (int prior = 0; prior < index; prior++) rejectAlias(buffers[prior].address(), buffers[prior].byteSize(), buffer);
            rejectAlias(fileHandle.address(), 1, buffer);
            rejectAlias(readEntry.address(), 1, buffer);
            rejectAlias(informationEntry.address(), 1, buffer);
            buffer.fill((byte) 0);
        }
    }

    /** One synchronous native read only. Its primitive outcomes are retained before any interpretation. */
    private void readOnce(int wanted) throws Throwable {
        if (Thread.currentThread() != thread || frameRetired || readCompletionUnconfirmed ||
            wanted < 1 || wanted > CHUNK || readCalls >= MAXIMUM_BYTES / CHUNK + 1) {
            throw new IllegalStateException("Original JVM read is unbounded, consumed or outside its thread");
        }
        buffers[1].fill((byte) 0);
        buffers[2].fill((byte) 0xff);
        readCalls++;
        readCompletionUnconfirmed = true;
        returnedStatus = (int) readCall.invokeExact(buffers[0], fileHandle, buffers[1], wanted, buffers[2], MemorySegment.NULL);
        returnedBytes = Integer.toUnsignedLong(buffers[2].get(ValueLayout.JAVA_INT, 0));
        lastError = buffers[0].get(ValueLayout.JAVA_INT, errorOffset);
        if (returnedStatus == 0 || returnedBytes > wanted) {
            throw new IllegalStateException("Original JVM read has no confirmed bounded completion");
        }
        // TRUE plus a bounded count confirms this synchronous call completed, including a short/EOF
        // result. FALSE (including ERROR_IO_PENDING), thrown or contradictory outcomes retain the frame.
        // Successful Win32 calls may leave nonzero stale last-error state.
        readCompletionUnconfirmed = false;
    }

    private void inspectMetadata() throws Throwable {
        information(18, 3, 24);
        information(9, 4, 8);
        information(1, 5, 24);
        repeatedMetadata[0] = buffers[3].get(ValueLayout.JAVA_LONG, 0);
        repeatedMetadata[1] = buffers[3].get(ValueLayout.JAVA_LONG, 8);
        repeatedMetadata[2] = buffers[3].get(ValueLayout.JAVA_LONG, 16);
        repeatedMetadata[3] = buffers[5].get(ValueLayout.JAVA_LONG, 0);
        repeatedMetadata[4] = buffers[5].get(ValueLayout.JAVA_LONG, 8);
        repeatedMetadata[5] = Integer.toUnsignedLong(buffers[5].get(ValueLayout.JAVA_INT, 16));
        repeatedMetadata[6] = Integer.toUnsignedLong(buffers[4].get(ValueLayout.JAVA_INT, 0));
        repeatedMetadata[7] = Integer.toUnsignedLong(buffers[4].get(ValueLayout.JAVA_INT, 4));
        for (int index = 0; index < originalMetadata.length; index++) {
            if (originalMetadata[index] != repeatedMetadata[index]) {
                throw new IllegalStateException("Original JVM file metadata changed around its byte observation");
            }
        }
        if (buffers[5].get(ValueLayout.JAVA_BYTE, 20) != 0 || buffers[5].get(ValueLayout.JAVA_BYTE, 21) != 0) {
            throw new IllegalStateException("Original JVM byte source is deleted or a directory");
        }
    }

    private void information(int kind, int index, int size) throws Throwable {
        buffers[index].fill((byte) 0xff);
        int status = (int) informationCall.invokeExact(buffers[0], fileHandle, kind, buffers[index], size);
        lastError = buffers[0].get(ValueLayout.JAVA_INT, errorOffset);
        if (status == 0) throw new IllegalStateException("Original JVM byte metadata query failed");
    }

    private void requireOriginalFile() {
        if (Thread.currentThread() != thread || file == null) {
            throw new IllegalStateException("Original JVM bytes require their original platform thread/file");
        }
        file.requireOriginalBytes(this);
        if (bootstrapArena == null || !bootstrapArena.scope().isAlive() || fileArena == null ||
            !fileArena.scope().isAlive() || fileHandle == null || !fileHandle.isNative() ||
            fileHandle.byteSize() != 0 || fileHandle.address() <= 0 ||
            !fileHandle.scope().equals(fileArena.scope()) || !fileHandle.isAccessibleBy(thread)) {
            throw new IllegalStateException("Original JVM byte source lost its retained handle");
        }
        for (MemorySegment entry : new MemorySegment[] {readEntry, informationEntry}) {
            if (entry == null || !entry.isNative() || entry.byteSize() != 0 || entry.address() <= 65_535 ||
                entry.address() > Long.MAX_VALUE - 1 || !entry.scope().equals(bootstrapArena.scope()) ||
                !entry.isAccessibleBy(thread)) {
                throw new IllegalStateException("Original JVM byte source lost a scoped system entry");
            }
        }
    }

    private void retireFrame() {
        if (Thread.currentThread() != thread) throw new IllegalStateException("Original byte frame belongs to another thread");
        if (frameRetired || readCompletionUnconfirmed) return;
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
        // Never close/reopen/seek the original file, its arena, or any unconfirmed read frame.
    }

    private static void rejectAlias(long address, long size, MemorySegment buffer) {
        if (address < buffer.address() + buffer.byteSize() && buffer.address() < address + size) {
            throw new IllegalStateException("Original file byte owner aliases its private frame");
        }
    }

    private void requireCompleted() {
        requireOriginalFile();
        if (!succeeded || !frameRetired || readCompletionUnconfirmed || total != originalMetadata[4] || observedDigest == null) {
            throw new IllegalStateException("Original JVM bytes have no completed observation");
        }
    }
    boolean completed() { requireCompleted(); return true; }
    long byteCount() { requireCompleted(); return total; }
    byte[] sha256() { requireCompleted(); return observedDigest.clone(); }
}
