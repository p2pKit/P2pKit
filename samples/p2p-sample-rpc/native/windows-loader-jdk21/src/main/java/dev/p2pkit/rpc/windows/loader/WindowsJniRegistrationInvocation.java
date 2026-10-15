package dev.p2pkit.rpc.windows.loader;

import java.lang.foreign.Arena;
import java.lang.foreign.FunctionDescriptor;
import java.lang.foreign.Linker;
import java.lang.foreign.MemoryLayout;
import java.lang.foreign.MemorySegment;
import java.lang.foreign.ValueLayout;
import java.lang.invoke.MethodHandle;
import java.nio.ByteOrder;
import java.util.Objects;

/**
 * Dormant fixed post-admission call mechanics, NOT a loader or authority grant. No productive caller exists.
 * A future reviewed loader must independently admit the original registration entry/VM/module and transfer
 * exclusive original owners to Retention before use. Nonzero/scoped addresses and Java references do not
 * establish that authority. This class performs no OS/symbol discovery, loads no library, and never creates
 * a native pointer from a numeric address. Only its private invocation data is allocated/retired here.
 */
final class WindowsJniRegistrationInvocation implements WindowsJniRegistrationOwner.Invocation {
    static final int ENTRY_COUNT = 23;
    static final int REPORT_BYTES = 32;
    static final MemoryLayout ENTRIES = MemoryLayout.sequenceLayout(ENTRY_COUNT, ValueLayout.JAVA_LONG);
    static final MemoryLayout REPORT = MemoryLayout.sequenceLayout(8, ValueLayout.JAVA_INT);
    static final FunctionDescriptor DESCRIPTOR = FunctionDescriptor.of(ValueLayout.JAVA_INT,
        ValueLayout.ADDRESS, ValueLayout.ADDRESS.withTargetLayout(ENTRIES), ValueLayout.JAVA_INT,
        ValueLayout.ADDRESS.withTargetLayout(REPORT), ValueLayout.JAVA_INT);

    static final class RetirementFailure extends RuntimeException {
        private static final long serialVersionUID = 1L;
        final transient WindowsJniRegistrationInvocation retainedInvocation;
        Throwable entriesClearFailure;
        Throwable reportClearFailure;
        Throwable arenaCloseFailure;

        RetirementFailure(WindowsJniRegistrationInvocation invocation) {
            super("Windows JNI invocation frame retirement is uncertain", null, false, false);
            retainedInvocation = invocation;
        }

        boolean failed() {
            return entriesClearFailure != null || reportClearFailure != null || arenaCloseFailure != null;
        }
    }

    static final class AcquisitionFailure extends RuntimeException {
        private static final long serialVersionUID = 1L;
        final transient WindowsJniRegistrationInvocation retainedInvocation;
        Throwable acquisitionFailure;
        Throwable retirementFailure;

        AcquisitionFailure(WindowsJniRegistrationInvocation invocation) {
            super("Windows JNI invocation acquisition failed with retained frame ownership", null, false, false);
            retainedInvocation = invocation;
        }
    }

    private final Thread thread = Thread.currentThread();
    private final WindowsJniRegistrationOwner.Retention retention;
    private final MemorySegment entry;
    private final MemorySegment vm;
    private final RetirementFailure retirementFailure = new RetirementFailure(this);
    private Arena arena;
    private MemorySegment entries;
    private MemorySegment input;
    private MemorySegment output;
    private MethodHandle call;
    private boolean attempted;
    private boolean active;
    private boolean returned;
    private boolean read;
    private boolean retired;

    private WindowsJniRegistrationInvocation(WindowsJniRegistrationOwner.Retention retention,
                                           MemorySegment entry, MemorySegment vm) {
        this.retention = Objects.requireNonNull(retention);
        this.entry = entry;
        this.vm = vm;
    }

    static WindowsJniRegistrationInvocation prepare(WindowsJniRegistrationOwner.Retention retention,
                                                   MemorySegment entry, MemorySegment vm, long[] expected) {
        WindowsLoaderRuntime.requireDiagnosticRuntime();
        if (WindowsJniRegistrationInvocation.class.getModule() != WindowsLoaderRuntime.class.getModule() ||
            Thread.currentThread().isVirtual()) {
            throw new IllegalStateException("Windows JNI invocation requires its original boot module/platform thread");
        }
        if (ValueLayout.ADDRESS.byteSize() != 8 || ByteOrder.nativeOrder() != ByteOrder.LITTLE_ENDIAN ||
            ENTRIES.byteSize() != 184 || ENTRIES.byteAlignment() != 8 ||
            REPORT.byteSize() != REPORT_BYTES || REPORT.byteAlignment() != 4) {
            throw new IllegalStateException("Unsupported Windows JNI invocation data layout");
        }
        requireOriginalSegment(entry);
        requireOriginalSegment(vm);
        if ((vm.address() & 7) != 0 || expected == null || expected.length != ENTRY_COUNT) {
            throw new IllegalArgumentException("Invalid fixed Windows JNI arguments");
        }
        long[] snapshot = expected.clone();
        for (long address : snapshot) {
            if (address <= 0) throw new IllegalArgumentException("Invalid original user-mode entry address");
        }
        WindowsJniRegistrationInvocation invocation = new WindowsJniRegistrationInvocation(retention, entry, vm);
        AcquisitionFailure failure = new AcquisitionFailure(invocation);
        try {
            // Creating the fixed stub invokes no candidate address. The original segment stays scoped/live.
            invocation.call = Linker.nativeLinker().downcallHandle(entry, DESCRIPTOR);
            invocation.arena = Arena.ofConfined();
            invocation.entries = invocation.arena.allocate(ENTRIES);
            invocation.output = invocation.arena.allocate(REPORT);
            long first = invocation.entries.address();
            long second = invocation.output.address();
            if (first <= 0 || first > Long.MAX_VALUE - 184 || second <= 0 ||
                second > Long.MAX_VALUE - REPORT_BYTES || (first & 7) != 0 || (second & 3) != 0 ||
                (first < second + REPORT_BYTES && second < first + 184)) {
                throw new IllegalStateException("Invalid or overlapping Windows JNI invocation buffers");
            }
            for (int index = 0; index < ENTRY_COUNT; index++) {
                invocation.entries.setAtIndex(ValueLayout.JAVA_LONG, index, snapshot[index]);
            }
            invocation.input = invocation.entries.asReadOnly();
            return invocation;
        } catch (Throwable caught) {
            try { invocation.retireFrame(); }
            catch (Throwable retirement) {
                failure.acquisitionFailure = caught;
                failure.retirementFailure = retirement;
                throw failure;
            }
            throw caught;
        }
    }

    private static void requireOriginalSegment(MemorySegment segment) {
        if (segment == null || !segment.isNative() || segment.address() <= 0 ||
            !segment.scope().isAlive() || segment.scope().equals(Arena.global().scope()) ||
            !segment.isAccessibleBy(Thread.currentThread())) {
            throw new IllegalArgumentException("Missing live scoped original Windows JNI address");
        }
    }

    private void requireThread() {
        if (Thread.currentThread() != thread) {
            throw new IllegalStateException("Windows JNI invocation accessed outside its owning platform thread");
        }
    }

    private void requireReservedOwner() {
        WindowsJniRegistrationOwner owner = WindowsJniRegistrationOwner.retainedProcessOwner();
        if (owner == null || owner.retention != retention || !owner.ownsInvocation(this) ||
            owner.state() != WindowsJniRegistrationOwner.State.Invoking) {
            throw new IllegalStateException("Windows JNI invocation requires its exact reserved lifetime owner");
        }
    }

    @Override public int invoke() throws Throwable {
        requireThread();
        requireReservedOwner();
        if (attempted || retired) throw new IllegalStateException("Windows JNI invocation is already consumed");
        attempted = true;
        requireOriginalSegment(entry);
        requireOriginalSegment(vm);
        active = true;
        try {
            int result = (int) call.invokeExact(vm, input, ENTRY_COUNT, output, REPORT_BYTES);
            returned = true;
            return result;
        } finally { active = false; }
    }

    @Override public WindowsJniRegistrationOwner.Report readReport() {
        requireThread();
        requireReservedOwner();
        if (!returned || active || retired || read) {
            throw new IllegalStateException("Windows JNI report is not a fresh completed invocation");
        }
        read = true;
        return new WindowsJniRegistrationOwner.Report(
            output.getAtIndex(ValueLayout.JAVA_INT, 0), output.getAtIndex(ValueLayout.JAVA_INT, 1),
            output.getAtIndex(ValueLayout.JAVA_INT, 2), output.getAtIndex(ValueLayout.JAVA_INT, 3),
            output.getAtIndex(ValueLayout.JAVA_INT, 4), output.getAtIndex(ValueLayout.JAVA_INT, 5),
            output.getAtIndex(ValueLayout.JAVA_INT, 6), output.getAtIndex(ValueLayout.JAVA_INT, 7));
    }

    @Override public void retireFrame() {
        requireThread();
        if (active) throw new IllegalStateException("Windows JNI invocation frame is in active native use");
        if (retired) {
            if (retirementFailure.failed()) throw retirementFailure;
            return;
        }
        retired = true;
        try { if (entries != null) entries.fill((byte) 0); }
        catch (Throwable caught) { retirementFailure.entriesClearFailure = caught; }
        try { if (output != null) output.fill((byte) 0); }
        catch (Throwable caught) { retirementFailure.reportClearFailure = caught; }
        try { if (arena != null) arena.close(); }
        catch (Throwable caught) { retirementFailure.arenaCloseFailure = caught; }
        // Never retire entry/VM/module/runtime owners. A failed close keeps exact state and is not retried.
        if (retirementFailure.failed()) throw retirementFailure;
    }
}
