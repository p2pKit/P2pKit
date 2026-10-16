package dev.p2pkit.rpc.windows.loader;

import java.lang.foreign.Arena;
import java.lang.foreign.MemorySegment;
import java.lang.reflect.Constructor;
import java.lang.reflect.Field;
import java.lang.reflect.InvocationTargetException;
import java.lang.reflect.Method;
import java.util.Arrays;

/** Inert inventory/ownership controls. No system lookup, native function, candidate DLL or authority. */
public final class SystemImportResolutionTests {
    private SystemImportResolutionTests() {}

    public static void main(String[] arguments) throws Exception {
        check(arguments.length == 1);
        String mode = arguments[0];
        switch (mode) {
            case "valid" -> {
                check(Arrays.equals(snapshot(new String[] {"kernel32.dll", "CloseHandle"}),
                    new String[] {"kernel32.dll", "CloseHandle"}));
                String[] largest = new String[8192];
                for (int index = 0; index < 4096; index++) {
                    largest[index * 2] = "kernel32.dll";
                    largest[index * 2 + 1] = "Function_" + index;
                }
                check(Arrays.equals(snapshot(largest), largest));
                check(snapshot(new String[] {"kernel32.dll", "A".repeat(128)}).length == 2);
            }
            case "bounds" -> {
                refused(null);
                refused(new String[0]);
                refused(new String[] {"kernel32.dll"});
                refused(new String[] {"kernel32.dll", "CloseHandle", "kernel32.dll"});
                refused(new String[8194]);
            }
            case "unsupported" -> {
                for (String module : new String[] {"advapi32.dll", "ntdll.dll", "shell32.dll", "ole32.dll",
                    "KERNEL32.DLL", "kernelbase.dll", "C:\\Windows\\System32\\kernel32.dll", "", "kernel32.dll\0"}) {
                    refused(new String[] {"kernel32.dll", "CloseHandle", module, "OtherFunction"});
                }
                refused(new String[] {null, "CloseHandle"});
            }
            case "names" -> {
                for (String name : new String[] {"", "#1", "1", "123name", "Close Handle", "name\0",
                    "name.dll", "ümlaut", "A".repeat(129)}) refused(new String[] {"kernel32.dll", name});
                refused(new String[] {"kernel32.dll", null});
            }
            case "duplicate" -> refused(new String[] {"kernel32.dll", "CloseHandle", "kernel32.dll", "CloseHandle"});
            case "snapshot" -> {
                String[] original = {"kernel32.dll", "CloseHandle"};
                String[] copy = snapshot(original);
                check(original != copy);
                original[0] = "ntdll.dll";
                original[1] = "Changed";
                check(Arrays.equals(copy, new String[] {"kernel32.dll", "CloseHandle"}));
            }
            case "owner-refusal" -> {
                try {
                    new WindowsSystemImportResolution(null, null, null, null, null, null, null, null);
                    throw new AssertionError("Missing plan accepted");
                } catch (IllegalArgumentException expected) { /* Refuses before native frame/lookup. */ }
                WindowsSystemImportResolution candidate = inertCandidate();
                try {
                    candidate.observe();
                    throw new AssertionError("Unattached resolution performed an observation");
                } catch (IllegalStateException expected) { /* A copied plan cannot invent a bootstrap owner. */ }
                check(get(candidate, "frameArena") == null && !((boolean) get(candidate, "attempted")));
                try {
                    candidate.addresses();
                    throw new AssertionError("Unattached resolution published addresses");
                } catch (IllegalStateException expected) { /* No authority or result from inert data. */ }
            }
            case "retirement-known", "retirement-unknown" -> retirement(mode.equals("retirement-unknown"));
            default -> throw new AssertionError("Unknown system import control");
        }
        System.out.println("WINDOWS_SYSTEM_IMPORT_RESOLUTION_PASS case=" + mode +
            " scope=INERT_INVENTORY_AND_OWNERSHIP_NOT_NATIVE_OR_AUTHORITY");
    }

    private static String[] snapshot(String[] input) throws Exception {
        Method method = WindowsSystemImportResolution.class.getDeclaredMethod("snapshotInventory", String[].class);
        method.setAccessible(true);
        try { return (String[]) method.invoke(null, (Object) input); }
        catch (InvocationTargetException wrapped) {
            if (wrapped.getCause() instanceof IllegalArgumentException refused) throw refused;
            throw wrapped;
        }
    }

    private static void refused(String[] input) throws Exception {
        try {
            snapshot(input);
            throw new AssertionError("Unsupported import inventory accepted");
        } catch (IllegalArgumentException expected) { /* Exact bounded preparatory refusal. */ }
    }

    private static WindowsSystemImportResolution inertCandidate() throws Exception {
        // Reflection constructs only inert copied-plan data, never an original bootstrap or executable entry.
        Constructor<WindowsPackagedVerifier> constructor = WindowsPackagedVerifier.class.getDeclaredConstructor(
            Object.class, Class.class, Class.class, Method.class, Method.class,
            long[].class, String[].class, long[].class, String[].class);
        constructor.setAccessible(true);
        WindowsPackagedVerifier plan = constructor.newInstance(null, null, null, null, null,
            null, null, null, new String[] {"kernel32.dll", "CloseHandle"});
        return new WindowsSystemImportResolution(null, plan, null, null, null, null, null, null);
    }

    private static void retirement(boolean unknown) throws Exception {
        WindowsSystemImportResolution candidate = inertCandidate();
        Arena backing = Arena.ofConfined();
        Arena frame = Arena.ofConfined();
        try {
            MemorySegment[] buffers = (MemorySegment[]) get(candidate, "buffers");
            MemorySegment[] original = new MemorySegment[buffers.length];
            for (int index = 0; index < buffers.length; index++) {
                original[index] = backing.allocate(8, 8).fill((byte) 0x5a);
                buffers[index] = original[index].reinterpret(8, frame, null);
            }
            set(candidate, "frameArena", frame);
            set(candidate, "callInFlight", unknown);
            Method retire = WindowsSystemImportResolution.class.getDeclaredMethod("retireFrame");
            retire.setAccessible(true);
            retire.invoke(candidate);
            retire.invoke(candidate);
            check((boolean) get(candidate, "frameRetired") == !unknown);
            check(frame.scope().isAlive() == unknown && backing.scope().isAlive());
            for (MemorySegment segment : original) {
                byte[] expected = new byte[8];
                if (unknown) Arrays.fill(expected, (byte) 0x5a);
                check(Arrays.equals(segment.toArray(java.lang.foreign.ValueLayout.JAVA_BYTE), expected));
            }
            Object failure = get(candidate, "failure");
            check(get(failure, "retainedResolution") == candidate);
            check(get(failure, "arenaCloseFailure") == null);
        } finally {
            // Test-owned inert allocations only: no OS/upcall or pending native write ever occurred.
            if (frame.scope().isAlive()) frame.close();
            backing.close();
        }
    }

    private static Object get(Object target, String name) throws Exception {
        Field field = target.getClass().getDeclaredField(name);
        field.setAccessible(true);
        return field.get(target);
    }

    private static void set(Object target, String name, Object value) throws Exception {
        Field field = target.getClass().getDeclaredField(name);
        field.setAccessible(true);
        field.set(target, value);
    }

    private static void check(boolean condition) {
        if (!condition) throw new AssertionError("System import control failed");
    }
}
