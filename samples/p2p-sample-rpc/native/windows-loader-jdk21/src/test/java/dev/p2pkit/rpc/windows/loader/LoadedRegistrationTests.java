package dev.p2pkit.rpc.windows.loader;

import java.lang.foreign.Arena;
import java.lang.foreign.FunctionDescriptor;
import java.lang.foreign.Linker;
import java.lang.foreign.MemoryLayout;
import java.lang.foreign.MemorySegment;
import java.lang.foreign.ValueLayout;
import java.lang.invoke.MethodHandle;
import java.lang.reflect.Field;
import java.lang.reflect.InvocationTargetException;
import java.lang.reflect.Method;
import java.nio.ByteBuffer;
import java.nio.channels.FileChannel;
import java.nio.file.Files;
import java.nio.file.LinkOption;
import java.nio.file.OpenOption;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;
import java.security.MessageDigest;
import java.util.Arrays;
import java.util.HashSet;
import java.util.HexFormat;
import java.util.Set;

/**
 * Actual development test DLL -> original FFM mechanics -> original compiled JNI declaration.
 * The separately compiled DLL contains only policy/JNI/registrar and the aborting deny-storage backend.
 * Compiler byte pins and this test's conditional bootstrap are NOT installed-runtime authority.
 * All private access below is test-only: no production acceptance seam or availability change is added.
 */
public final class LoadedRegistrationTests {
    private static Fixture retained;
    private static final String PROFILE = "dev.p2pkit.sample.rpc.profile.";

    private LoadedRegistrationTests() {}

    public static void main(String[] args) throws Throwable {
        check(args.length == 9);
        String mode = args[0];
        check(mode.equals("success") || mode.equals("address") || mode.equals("pin"));
        WindowsLoaderRuntime.requireDiagnosticRuntime();
        check(Linker.nativeLinker().getClass().getName()
            .equals("jdk.internal.foreign.abi.x64.windows.Windowsx64Linker"));
        Fixture fixture = new Fixture();
        check(retained == null);
        retained = fixture; // Root all original owners BEFORE file acquisition or any native effect.
        try {
            fixture.run(args);
        } catch (Throwable failure) {
            fixture.failure = failure;
            throw failure;
        }
        try {
            WindowsLoader.openInstalledProvider();
            throw new AssertionError("Test DLL enabled productive loading");
        } catch (UnsupportedOperationException expected) {
            check(WindowsLoader.REFUSAL.equals(expected.getMessage()));
        }
        System.out.println("WINDOWS_LOADED_REGISTRATION_PASS case=" + mode +
            " scope=DEV_TEST_DLL_DENY_STORAGE_NOT_INSTALLED_AUTHORITY_OR_PROVIDER");
    }

    private static final class Fixture {
        private Throwable failure;
        private FileChannel file;
        private byte[] originalBytes;
        private WindowsPackagedVerifier plan;
        private WindowsSystemBootstrapCandidate bootstrap;
        private WindowsOriginalJvmCandidate originalJvm;
        private Arena originalArena;
        private MemorySegment[] entries;
        private WindowsLibraryLoadInvocation load;
        private WindowsLibraryLoadInvocation.Result loaded;
        private WindowsExportLookupInvocation[] exports;
        private MemorySegment[] exportEntries;
        private WindowsImageReadInvocation[] reads;
        private SystemImports imports;
        private WindowsJniRegistrationInvocation registration;
        private WindowsJniRegistrationOwner owner;

        private void run(String[] args) throws Throwable {
            Path path = Path.of(args[1]).toRealPath(LinkOption.NOFOLLOW_LINKS);
            check(path.isAbsolute() && path.getFileName().toString().equals("p2pkit-windows-profile.dll"));
            check(Files.isRegularFile(path, LinkOption.NOFOLLOW_LINKS));
            check(args[2].matches("[0-9a-f]{64}") && args[4].matches("[0-9a-f]{40}") &&
                args[5].matches("[0-9a-f]{40}"));
            long bytes = Long.parseLong(args[3]);
            check(bytes >= 512 && bytes <= 4 * 1024 * 1024);
            Set<OpenOption> options = new HashSet<>();
            options.add(StandardOpenOption.READ);
            options.add(LinkOption.NOFOLLOW_LINKS);
            Class<?> sharing = Class.forName("com.sun.nio.file.ExtendedOpenOption");
            for (String name : new String[] {"NOSHARE_WRITE", "NOSHARE_DELETE"}) {
                options.add((OpenOption) sharing.getField(name).get(null));
            }
            file = FileChannel.open(path, options); // Never closed: no unload/close behind cached JNI addresses.
            check(file.size() == bytes);
            originalBytes = new byte[(int) bytes];
            ByteBuffer destination = ByteBuffer.wrap(originalBytes);
            while (destination.hasRemaining()) check(file.read(destination) > 0);
            check(file.read(ByteBuffer.allocate(1)) == -1 && file.size() == bytes);
            String actualHash = HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(originalBytes));
            requirePin(actualHash, args[2]);
            if (args[0].equals("pin")) {
                String wrong = (args[2].charAt(0) == '0' ? "1" : "0") + args[2].substring(1);
                expect(IllegalArgumentException.class, () -> requirePin(actualHash, wrong));
                check(bootstrap == null && load == null && owner == null && file.isOpen());
                return;
            }
            // Reuse the independently hash-bound real Java17 class/resource check, not a fixture helper substitute.
            Path main = Path.of(args[6]).toRealPath();
            PackagedVerifierTests.actualClass("WindowsProfilePackagedVerifier", main, args[7]);
            Class<?> declaration = PackagedVerifierTests.actualClass("WindowsProfileCustodyJni", main, args[8]);
            Class<?> helper = Class.forName(PROFILE + "WindowsProfileLoadedNativeFixture", true,
                ClassLoader.getSystemClassLoader());
            check(helper.getClassLoader() == ClassLoader.getSystemClassLoader());
            Method abi = helper.getMethod("abi");
            Method capabilities = helper.getMethod("capabilities");
            expect(UnsatisfiedLinkError.class, () -> abi.invoke(null));
            Object[] manifest = (Object[]) helper.getMethod("manifest", byte[].class, String.class, String.class)
                .invoke(null, originalBytes, args[4], args[5]);
            check(manifest.length == 2);
            plan = WindowsPackagedVerifier.prepare((byte[]) manifest[0], originalBytes,
                (String) manifest[1], args[4], args[5]);
            check(plan.declaringClass() == declaration && plan.imageLayout()[0] <= 16L * 1024 * 1024);
            String[] imported = plan.importNames();
            for (int index = 0; index < imported.length; index += 2) check(imported[index].equals("kernel32.dll"));

            // This is expressly conditional development bootstrap. Its observations cannot authorize
            // the earlier OS calls or a production DLL; no fixture object is presented as that authority.
            bootstrap = WindowsSystemBootstrapCandidate.inspect();
            originalJvm = bootstrap.inspectOriginalJvm();
            originalArena = (Arena) field(bootstrap, "originalArena");
            entries = (MemorySegment[]) field(bootstrap, "entries");
            load = WindowsLibraryLoadInvocation.prepare(this, originalJvm, file, entries[5], originalArena,
                path.toString());
            loaded = load.invoke();
            MemorySegment module = loaded.module();
            imports = new SystemImports(bootstrap, originalArena, entries, imported.length / 2);
            imports.requireModulePath(module, path.toString());

            long[] layout = plan.imageLayout();
            String[] names = plan.exportNames();
            long[] rvas = plan.exportRvas();
            long[] exportTargets = new long[names.length];
            exports = new WindowsExportLookupInvocation[names.length];
            exportEntries = new MemorySegment[names.length];
            for (int index = 0; index < names.length; index++) {
                exports[index] = WindowsExportLookupInvocation.prepare(bootstrap, load, plan, entries[4], originalArena,
                    module, originalArena, names[index], layout[0], layout[1], layout[2], rvas[index]);
                exportEntries[index] = exports[index].invoke().entry();
                exportTargets[index] = exportEntries[index].address();
            }
            // Derive expected import targets by separate logical-library resolution and physical system
            // provider pins BEFORE reading any IAT. Never select an expected target from candidate memory.
            long[] importTargets = imports.resolve(imported);
            long[] requested = plan.regions(module.address());
            reads = new WindowsImageReadInvocation[requested.length / 3];
            byte[][] pages = new byte[reads.length][];
            for (int index = 0; index < reads.length; index++) {
                int kind = (int) requested[index * 3 + 2];
                reads[index] = WindowsImageReadInvocation.prepare(bootstrap, load, plan, entries[6], entries[7],
                    originalArena, module, originalArena, layout[0], requested[index * 3] - module.address(),
                    Math.toIntExact(requested[index * 3 + 1]), kind == 0 ? WindowsImageReadInvocation.Kind.READ_ONLY :
                    kind == 1 ? WindowsImageReadInvocation.Kind.EXECUTABLE : WindowsImageReadInvocation.Kind.DATA);
                pages[index] = reads[index].invoke().bytes();
            }
            long[] verified = plan.verify(module.address(), exportTargets, importTargets, pages);
            long[] methods = Arrays.copyOf(verified, 23);
            MemorySegment registrar = null;
            for (int index = 0; index < names.length; index++) {
                if (names[index].equals("pwp_jni_register_once")) registrar = exportEntries[index];
            }
            check(registrar != null && registrar.address() == verified[23]);
            WindowsJvmAcquisitionInvocation.Result vm =
                (WindowsJvmAcquisitionInvocation.Result) field(originalJvm, "acquired");
            WindowsJniRegistrationOwner.Retention roots = new WindowsJniRegistrationOwner.Retention(
                this, originalJvm, load, declaration, plan);
            if (args[0].equals("address")) methods[0]++; // Registrar compares but must never call this bad address.
            registration = WindowsJniRegistrationInvocation.prepare(roots, registrar, vm.virtualMachine(), methods);
            MemorySegment entriesFrame = (MemorySegment) field(registration, "entries");
            MemorySegment reportFrame = (MemorySegment) field(registration, "output");
            if (args[0].equals("address")) {
                WindowsJniRegistrationOwner.Failure refused = (WindowsJniRegistrationOwner.Failure)
                    expect(WindowsJniRegistrationOwner.Failure.class,
                        () -> WindowsJniRegistrationOwner.registerOnce(roots, registration));
                owner = refused.retainedOwner;
                check(owner.state() == WindowsJniRegistrationOwner.State.Failed &&
                    refused.kind == WindowsJniRegistrationOwner.FailureKind.NativeRefusal);
                check(field(owner, "report").equals(new WindowsJniRegistrationOwner.Report(32, 1, 0, 3, 0, 0, 0, 0)));
                expect(UnsatisfiedLinkError.class, () -> abi.invoke(null));
            } else {
                owner = WindowsJniRegistrationOwner.registerOnce(roots, registration);
                check(owner.state() == WindowsJniRegistrationOwner.State.Registered);
                check(field(owner, "report").equals(new WindowsJniRegistrationOwner.Report(32, 1, 2, 0, 1, 0, 0, 0)));
                check(abi.invoke(null).equals(13) && capabilities.invoke(null).equals(0x43L));
                System.gc(); // A request, not a claim that collection occurred.
                check(abi.invoke(null).equals(13) && capabilities.invoke(null).equals(0x43L));
            }
            check(owner == WindowsJniRegistrationOwner.retainedProcessOwner() && owner.retention == roots &&
                owner.ownsInvocation(registration));
            check(!entriesFrame.scope().isAlive() && !reportFrame.scope().isAlive());
            expect(IllegalStateException.class, () -> WindowsJniRegistrationOwner.registerOnce(roots, registration));
            check(file.isOpen() && originalArena.scope().isAlive() && loaded.module().address() == module.address());
            check(vm.virtualMachine().scope().isAlive() && registrar.scope().isAlive());
            if (args[0].equals("success")) check(abi.invoke(null).equals(13));
        }
    }

    /** Test-only fixed kernel32 import resolver. Original bootstrap/handles/frames remain retained forever. */
    private static final class SystemImports {
        private static final int CHARS = 1024;
        private final WindowsSystemBootstrapCandidate bootstrap;
        private final Arena originalArena;
        private final Arena frame = Arena.ofConfined();
        private final MemorySegment wide = frame.allocate((long) CHARS * 2, 2);
        private final MemorySegment ascii = frame.allocate(256);
        private final MemorySegment handle = frame.allocate(ValueLayout.JAVA_LONG);
        private final MethodHandle pin;
        private final MethodHandle path;
        private final MethodHandle system;
        private final MethodHandle resolve;
        private final long[] rawProviders;
        private final long[] rawEntries;
        private long rawKernel;
        private String systemDirectory;

        private SystemImports(WindowsSystemBootstrapCandidate bootstrap, Arena originalArena,
                              MemorySegment[] entries, int count) {
            this.bootstrap = bootstrap;
            this.originalArena = originalArena;
            rawProviders = new long[count];
            rawEntries = new long[count];
            Linker linker = Linker.nativeLinker();
            MemoryLayout wideLayout = MemoryLayout.sequenceLayout(CHARS, ValueLayout.JAVA_SHORT);
            pin = linker.downcallHandle(entries[1], FunctionDescriptor.of(ValueLayout.JAVA_INT,
                ValueLayout.JAVA_INT, ValueLayout.ADDRESS, ValueLayout.ADDRESS.withTargetLayout(ValueLayout.JAVA_LONG)));
            path = linker.downcallHandle(entries[2], FunctionDescriptor.of(ValueLayout.JAVA_INT,
                ValueLayout.ADDRESS, ValueLayout.ADDRESS.withTargetLayout(wideLayout), ValueLayout.JAVA_INT));
            system = linker.downcallHandle(entries[3], FunctionDescriptor.of(ValueLayout.JAVA_INT,
                ValueLayout.ADDRESS.withTargetLayout(wideLayout), ValueLayout.JAVA_INT));
            // Exact Windows-x64 pointer return is retained as RAX bits before segment allocation.
            resolve = linker.downcallHandle(entries[4], FunctionDescriptor.of(ValueLayout.JAVA_LONG,
                ValueLayout.ADDRESS, ValueLayout.ADDRESS.withTargetLayout(MemoryLayout.sequenceLayout(256,
                    ValueLayout.JAVA_BYTE))));
            check(ascii.address() > 65_535 && wide.address() > 65_535);
        }

        private void requireModulePath(MemorySegment module, String expected) throws Throwable {
            wide.fill((byte) 0x7f);
            int length = (int) path.invokeExact(module, wide, CHARS);
            check(readWide(length).equalsIgnoreCase(expected));
        }

        private long[] resolve(String[] names) throws Throwable {
            check(bootstrap.completed() && originalArena.scope().isAlive());
            wide.fill((byte) 0x7f);
            int systemLength = (int) system.invokeExact(wide, CHARS);
            systemDirectory = readWide(systemLength);
            check(systemDirectory.matches("[A-Za-z]:\\\\[A-Za-z0-9 ._\\\\-]+"));
            putWide("kernel32.dll");
            handle.fill((byte) 0);
            int result = (int) pin.invokeExact(1, wide, handle); // PIN already-loaded fixed logical provider.
            rawKernel = handle.get(ValueLayout.JAVA_LONG, 0);
            check(result != 0 && validModule(rawKernel));
            MemorySegment kernel = MemorySegment.ofAddress(rawKernel).reinterpret(originalArena, null);
            requireModulePath(kernel, systemDirectory + "\\kernel32.dll");
            for (int index = 0; index < rawEntries.length; index++) {
                check(names[index * 2].equals("kernel32.dll"));
                String name = names[index * 2 + 1];
                check(name.matches("[A-Za-z_][A-Za-z0-9_]{0,127}"));
                ascii.fill((byte) 0);
                for (int offset = 0; offset < name.length(); offset++) {
                    ascii.set(ValueLayout.JAVA_BYTE, offset, (byte) name.charAt(offset));
                }
                // A forwarder may have implicit load effects before this later physical-provider check.
                // This is conditional development testing, not production startup/export authority.
                rawEntries[index] = (long) resolve.invokeExact(kernel, ascii);
                check(rawEntries[index] > 65_535);
                MemorySegment entry = MemorySegment.ofAddress(rawEntries[index]).reinterpret(originalArena, null);
                handle.fill((byte) 0);
                result = (int) pin.invokeExact(5, entry, handle); // Actual physical FROM_ADDRESS|PIN provider.
                rawProviders[index] = handle.get(ValueLayout.JAVA_LONG, 0);
                check(result != 0 && validModule(rawProviders[index]));
                MemorySegment provider = MemorySegment.ofAddress(rawProviders[index]).reinterpret(originalArena, null);
                wide.fill((byte) 0x7f);
                int length = (int) path.invokeExact(provider, wide, CHARS);
                String actual = readWide(length);
                check(actual.equalsIgnoreCase(systemDirectory + "\\kernel32.dll") ||
                    actual.equalsIgnoreCase(systemDirectory + "\\kernelbase.dll") ||
                    actual.equalsIgnoreCase(systemDirectory + "\\ntdll.dll"));
            }
            return rawEntries.clone();
        }

        private String readWide(int length) {
            check(length > 0 && length < CHARS && wide.getAtIndex(ValueLayout.JAVA_SHORT, length) == 0);
            char[] characters = new char[length];
            for (int index = 0; index < length; index++) {
                int value = Short.toUnsignedInt(wide.getAtIndex(ValueLayout.JAVA_SHORT, index));
                check(value >= 32 && value < 127);
                characters[index] = (char) value;
            }
            return new String(characters);
        }

        private void putWide(String value) {
            check(value.length() < CHARS);
            wide.fill((byte) 0);
            for (int index = 0; index < value.length(); index++) {
                wide.setAtIndex(ValueLayout.JAVA_SHORT, index, (short) value.charAt(index));
            }
        }

        private static boolean validModule(long value) { return value > 0 && (value & 65_535) == 0; }
    }

    private static Object field(Object owner, String name) throws ReflectiveOperationException {
        Field field = owner.getClass().getDeclaredField(name);
        field.setAccessible(true);
        return field.get(owner);
    }

    private static void requirePin(String actual, String expected) {
        if (!actual.equals(expected)) throw new IllegalArgumentException("Test DLL differs from compiler byte pin");
    }

    private interface Action { void run() throws Throwable; }

    private static Throwable expect(Class<? extends Throwable> expected, Action action) {
        try { action.run(); }
        catch (Throwable caught) {
            Throwable actual = caught;
            while (actual instanceof InvocationTargetException invocation) actual = invocation.getCause();
            if (expected.isInstance(actual)) return actual;
            throw new AssertionError("Unexpected loaded registration control outcome", actual);
        }
        throw new AssertionError("Expected loaded registration refusal");
    }

    private static void check(boolean condition) {
        if (!condition) throw new AssertionError("Loaded registration control failed");
    }
}
