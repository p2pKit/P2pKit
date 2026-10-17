package dev.p2pkit.rpc.windows.loader;

import java.lang.foreign.Arena;
import java.lang.foreign.MemorySegment;
import java.lang.foreign.ValueLayout;
import java.lang.reflect.Field;
import java.lang.reflect.Method;

/** Test-only private-frame fixtures; no Windows call, actual pending I/O or installation authority. */
public final class AncestorRetirementTests {
    private AncestorRetirementTests() {}

    private static void check(boolean value) {
        if (!value) throw new AssertionError("Ancestor frame retirement control failed");
    }

    private static Field field(String name) throws ReflectiveOperationException {
        Field field = WindowsOriginalFileAncestorsLease.class.getDeclaredField(name);
        field.setAccessible(true); // Same patched test module, never a packaged adapter or JDK opening.
        return field;
    }

    private static void retirement(boolean unconfirmed) throws ReflectiveOperationException {
        WindowsOriginalJvmAncestorsCandidate candidate = new WindowsOriginalJvmAncestorsCandidate(
            null, null, null, null, null, null, null, null, null, null, null, null, null, null, null,
            new char[4], 3, new long[8]);
        try {
            candidate.observe();
            throw new AssertionError("Unattached fixture reached original ancestor operations");
        } catch (IllegalStateException expected) {
            // Original identity guard refuses before allocation, native lookup or file operations.
        }
        Field attachment = WindowsOriginalJvmAncestorsCandidate.class.getDeclaredField("core");
        attachment.setAccessible(true);
        WindowsOriginalFileAncestorsLease core = (WindowsOriginalFileAncestorsLease) attachment.get(candidate);
        // The backing owner allows inspection of the same bytes after the test frame's view retires.
        // This is allocated inert memory, not an address supplied to any OS function or pending request.
        try (Arena backing = Arena.ofConfined(); Arena original = Arena.ofConfined()) {
            Arena frame = Arena.ofConfined();
            try {
                MemorySegment storage = backing.allocate(32);
                storage.fill((byte) 0x5a);
                MemorySegment view = storage.reinterpret(frame, null);
                field("frameArena").set(core, frame);
                field("leaseArena").set(core, original);
                ((MemorySegment[]) field("buffers").get(core))[0] = view;
                field("ntCompletionUnconfirmed").setBoolean(core, unconfirmed);
                Method retire = WindowsOriginalFileAncestorsLease.class.getDeclaredMethod("retireFrame");
                retire.setAccessible(true);
                retire.invoke(core);
                retire.invoke(core); // No second retirement or presumed resolution of uncertainty.
                check(frame.scope().isAlive() == unconfirmed);
                check(field("frameRetired").getBoolean(core) != unconfirmed);
                check(field("ntCompletionUnconfirmed").getBoolean(core) == unconfirmed);
                check(original.scope().isAlive());
                for (long index = 0; index < storage.byteSize(); index++) {
                    check(storage.get(ValueLayout.JAVA_BYTE, index) == (unconfirmed ? (byte) 0x5a : 0));
                }
                if (unconfirmed) check(view.get(ValueLayout.JAVA_BYTE, 0) == (byte) 0x5a);
                else {
                    try {
                        view.get(ValueLayout.JAVA_BYTE, 0);
                        throw new AssertionError("Retired frame view remained accessible");
                    } catch (IllegalStateException expected) {
                        // Successful retirement invalidated the exact frame view, not the original owner.
                    }
                }
            } finally {
                // Only this inert fixture owns these buffers. No asynchronous OS operation was invoked.
                if (frame.scope().isAlive()) frame.close();
            }
        }
    }

    public static void main(String[] arguments) throws ReflectiveOperationException {
        check(arguments.length == 0);
        WindowsLoaderRuntime.requireDiagnosticRuntime();
        retirement(true);
        retirement(false);
        System.out.println("WINDOWS_ANCESTOR_RETIREMENT_PASS tests=2 " +
            "scope=INERT_FRAME_QUARANTINE_NOT_PENDING_OS_IO_OR_AUTHORITY");
    }
}
