package dev.p2pkit.rpc.windows.loader;

import java.lang.foreign.Arena;
import java.lang.foreign.FunctionDescriptor;
import java.lang.foreign.Linker;
import java.lang.foreign.MemoryLayout;
import java.lang.foreign.MemorySegment;
import java.lang.foreign.ValueLayout;
import java.lang.invoke.MethodHandle;
import java.nio.ByteOrder;

/**
 * Dormant, fixed JNI_GetCreatedJavaVMs invocation mechanics, NOT discovery or bootstrap authority.
 * The future reviewed loader must admit the original already-loaded JVM and exact export first,
 * then retain its exclusive original owner and arena. A reference/scope alone proves none of that.
 * No lookup, library load, VM creation, attach/detach, or numeric-address construction occurs here.
 */
final class WindowsJvmAcquisitionInvocation {
    static final MemoryLayout VM_BUFFER = MemoryLayout.sequenceLayout(1, ValueLayout.ADDRESS);
    static final FunctionDescriptor DESCRIPTOR = FunctionDescriptor.of(ValueLayout.JAVA_INT,
        ValueLayout.ADDRESS.withTargetLayout(VM_BUFFER), ValueLayout.JAVA_INT,
        ValueLayout.ADDRESS.withTargetLayout(ValueLayout.JAVA_INT));

    /** Keeps the original runtime/entry owner alive after private invocation buffers are retired. */
    static final class Result {
        final WindowsJvmAcquisitionInvocation retainedInvocation;

        private Result(WindowsJvmAcquisitionInvocation invocation) { retainedInvocation = invocation; }

        MemorySegment virtualMachine() {
            retainedInvocation.requireThread();
            if (!retainedInvocation.succeeded) {
                throw new IllegalStateException("Original JVM acquisition has not completed successfully");
            }
            retainedInvocation.requireOriginalRuntime();
            return retainedInvocation.vm;
        }
    }

    /** Reserved before native effects. No raw messages, suppression allocation, retry or lost owner. */
    static final class Failure extends RuntimeException {
        private static final long serialVersionUID = 1L;
        final transient WindowsJvmAcquisitionInvocation retainedInvocation;
        Throwable preparationFailure;
        Throwable invocationFailure;
        Throwable readbackFailure;
        Throwable vmClearFailure;
        Throwable countClearFailure;
        Throwable arenaCloseFailure;

        Failure(WindowsJvmAcquisitionInvocation invocation) {
            super("Original JVM acquisition failed with runtime ownership retained", null, false, false);
            retainedInvocation = invocation;
        }

        boolean retirementFailed() {
            return vmClearFailure != null || countClearFailure != null || arenaCloseFailure != null;
        }
    }

    private final Thread thread = Thread.currentThread();
    final Object runtimeOwner;
    private final MemorySegment entry;
    private final Arena runtimeArena;
    private final Failure failure = new Failure(this);
    private final Result result = new Result(this);
    private Arena frameArena;
    private MemorySegment vmBuffer;
    private MemorySegment countBuffer;
    private MethodHandle call;
    private MemorySegment vm;
    private boolean attempted;
    private boolean active;
    private boolean retired;
    private boolean succeeded;

    private WindowsJvmAcquisitionInvocation(Object runtimeOwner, MemorySegment entry, Arena runtimeArena) {
        this.runtimeOwner = runtimeOwner;
        this.entry = entry;
        this.runtimeArena = runtimeArena;
    }

    static WindowsJvmAcquisitionInvocation prepare(Object runtimeOwner, MemorySegment entry, Arena runtimeArena) {
        WindowsLoaderRuntime.requireDiagnosticRuntime();
        if (WindowsJvmAcquisitionInvocation.class.getModule() != WindowsLoaderRuntime.class.getModule() ||
            Thread.currentThread().isVirtual()) {
            throw new IllegalStateException("Original JVM acquisition requires its boot module/platform thread");
        }
        if (ValueLayout.ADDRESS.byteSize() != 8 || ByteOrder.nativeOrder() != ByteOrder.LITTLE_ENDIAN ||
            VM_BUFFER.byteSize() != 8 || VM_BUFFER.byteAlignment() != 8) {
            throw new IllegalStateException("Unsupported original JVM invocation data layout");
        }
        if (runtimeOwner == null || entry == null || runtimeArena == null || !entry.isNative() ||
            entry.address() <= 0 || !entry.scope().equals(runtimeArena.scope()) ||
            runtimeArena.scope().equals(Arena.global().scope()) || !runtimeArena.scope().isAlive() ||
            !entry.isAccessibleBy(Thread.currentThread())) {
            throw new IllegalArgumentException("Missing original scoped runtime entry/owner");
        }
        WindowsJvmAcquisitionInvocation invocation =
            new WindowsJvmAcquisitionInvocation(runtimeOwner, entry, runtimeArena);
        try {
            // Stub preparation executes no supplied entry. This still does not authenticate its address.
            invocation.call = Linker.nativeLinker().downcallHandle(entry, DESCRIPTOR);
            invocation.frameArena = Arena.ofConfined();
            invocation.vmBuffer = invocation.frameArena.allocate(VM_BUFFER);
            invocation.countBuffer = invocation.frameArena.allocate(ValueLayout.JAVA_INT);
            long first = invocation.vmBuffer.address();
            long second = invocation.countBuffer.address();
            if (first <= 0 || first > Long.MAX_VALUE - 8 || second <= 0 || second > Long.MAX_VALUE - 4 ||
                (first & 7) != 0 || (second & 3) != 0 || (first < second + 4 && second < first + 8)) {
                throw new IllegalStateException("Invalid or overlapping original JVM invocation buffers");
            }
            return invocation;
        } catch (Throwable caught) {
            invocation.failure.preparationFailure = caught;
            try { invocation.retireFrame(); }
            catch (Failure ignored) { /* Original independent retirement failures remain in the reserved carrier. */ }
            throw invocation.failure;
        }
    }

    private void requireThread() {
        if (Thread.currentThread() != thread) {
            throw new IllegalStateException("Original JVM acquisition accessed outside its owning platform thread");
        }
    }

    private void requireOriginalRuntime() {
        if (!runtimeArena.scope().isAlive() || !entry.scope().isAlive() ||
            !entry.scope().equals(runtimeArena.scope()) || !entry.isAccessibleBy(Thread.currentThread())) {
            throw new IllegalStateException("Original JVM runtime scope is no longer available");
        }
    }

    Result invoke() {
        requireThread();
        if (attempted || retired) throw new IllegalStateException("Original JVM acquisition is already consumed");
        attempted = true;
        boolean accepted = false;
        try {
            int status;
            try {
                requireOriginalRuntime();
                active = true;
                try { status = (int) call.invokeExact(vmBuffer, 1, countBuffer); }
                finally { active = false; }
            } catch (Throwable caught) {
                failure.invocationFailure = caught;
                throw failure;
            }
            try {
                requireOriginalRuntime();
                MemorySegment observed = vmBuffer.get(ValueLayout.ADDRESS, 0);
                long address = observed.address();
                // A JavaVM begins with an 8-byte interface pointer. Reject any overlap of that word,
                // not merely a start address inside an output: countBuffer has only 4-byte alignment.
                if (status != 0 || countBuffer.get(ValueLayout.JAVA_INT, 0) != 1 ||
                    address <= 0 || address > Long.MAX_VALUE - 8 || (address & 7) != 0 ||
                    (address < vmBuffer.address() + 8 && vmBuffer.address() < address + 8) ||
                    (address < countBuffer.address() + 4 && countBuffer.address() < address + 8)) {
                    throw new IllegalStateException("Original JVM acquisition returned an invalid fixed result");
                }
                // Only the original native return is re-scoped, never dereferenced or made from a number.
                // Retiring our data frame must not invalidate the VM or close its original runtime arena.
                vm = observed.reinterpret(runtimeArena, null);
                accepted = true;
            } catch (Throwable caught) {
                failure.readbackFailure = caught;
                throw failure;
            }
        } finally {
            try { retireFrame(); }
            finally { succeeded = accepted && !failure.retirementFailed(); }
        }
        return result;
    }

    /** Retires only private output buffers, never the original entry, JVM, runtime arena or runtime owner. */
    void retireFrame() {
        requireThread();
        if (active) throw new IllegalStateException("Original JVM invocation is still active");
        if (retired) {
            if (failure.retirementFailed()) throw failure;
            return;
        }
        retired = true;
        try { if (vmBuffer != null) vmBuffer.fill((byte) 0); }
        catch (Throwable caught) { failure.vmClearFailure = caught; }
        try { if (countBuffer != null) countBuffer.fill((byte) 0); }
        catch (Throwable caught) { failure.countClearFailure = caught; }
        try { if (frameArena != null) frameArena.close(); }
        catch (Throwable caught) { failure.arenaCloseFailure = caught; }
        if (failure.retirementFailed()) throw failure;
    }
}
