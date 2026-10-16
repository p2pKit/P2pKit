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
    private static final String LOADER = "dev.p2pkit.rpc.windows.loader.";

    private enum Stage { PREFLIGHT, MANIFEST, PLAN, BOOTSTRAP, LOAD, EXPORT, IMPORT, READ,
        COMPARE, REGISTER, ABI, RETIRE, LOADER_REFUSAL }
    private enum Category { ASSERTION, ARGUMENT, STATE, LINKAGE, REFLECTION, IO, SECURITY,
        ERROR, EXCEPTION, UNKNOWN }
    private enum Site { FIXTURE, SYSTEM_IMPORT_RESOLUTION, CLASS_BINDING, PACKAGED_ADAPTER, PACKAGED_HELPER,
        PE_IMAGE, BYTE_MANIFEST, MAPPED_CODE, IMPORT_ADDRESSES, EXPORT_ADDRESSES, JNI_PLAN,
        JNI_DECLARATION, LOADER_RUNTIME, SYSTEM_BOOTSTRAP, ORIGINAL_JVM, JVM_ACQUISITION,
        LIBRARY_LOAD, EXPORT_LOOKUP, IMAGE_READ, REGISTRATION_INVOCATION, REGISTRATION_OWNER,
        SITE_UNKNOWN }

    private LoadedRegistrationTests() {}

    public static void main(String[] args) throws Throwable {
        if (args.length == 1 && args[0].equals("diagnostics")) {
            diagnostics(); // Inert formatting only, before every platform/linker/native-access guard.
            System.out.println("WINDOWS_LOADED_REGISTRATION_DIAGNOSTICS_PASS" +
                " scope=INERT_FORMATTING_NOT_DLL_OR_AUTHORITY");
            return;
        }
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
            fixture.stage = Stage.LOADER_REFUSAL;
            try {
                WindowsLoader.openInstalledProvider();
                throw new AssertionError("Test DLL enabled productive loading");
            } catch (UnsupportedOperationException expected) {
                check(WindowsLoader.REFUSAL.equals(expected.getMessage()));
            }
        } catch (Throwable failure) {
            fixture.failure = failure;
            try {
                System.out.println(diagnostic(fixture.stage, failure));
                if (fixture.mappedObservation != null) System.out.println(fixture.mappedObservation);
            }
            catch (Throwable reporting) { fixture.diagnosticFailure = reporting; }
            throw failure;
        }
        System.out.println("WINDOWS_LOADED_REGISTRATION_PASS case=" + mode +
            " scope=DEV_TEST_DLL_DENY_STORAGE_NOT_INSTALLED_AUTHORITY_OR_PROVIDER");
    }

    private static final class Fixture {
        private Throwable failure;
        private Throwable diagnosticFailure;
        private Throwable mappedObservationFailure;
        private String mappedObservation;
        private Stage stage = Stage.PREFLIGHT;
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
        private WindowsSystemImportResolution imports;
        private Arena modulePathArena;
        private MemorySegment modulePathBuffer;
        private MethodHandle modulePathCall;
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
            stage = Stage.MANIFEST;
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
            stage = Stage.PLAN;
            plan = WindowsPackagedVerifier.prepare((byte[]) manifest[0], originalBytes,
                (String) manifest[1], args[4], args[5]);
            check(plan.declaringClass() == declaration && plan.imageLayout()[0] <= 16L * 1024 * 1024);
            String[] imported = plan.importNames();
            for (int index = 0; index < imported.length; index += 2) check(imported[index].equals("kernel32.dll"));

            // This is expressly conditional development bootstrap. Its observations cannot authorize
            // the earlier OS calls or a production DLL; no fixture object is presented as that authority.
            stage = Stage.BOOTSTRAP;
            bootstrap = WindowsSystemBootstrapCandidate.inspect();
            originalJvm = bootstrap.inspectOriginalJvm();
            originalArena = (Arena) field(bootstrap, "originalArena");
            entries = (MemorySegment[]) field(bootstrap, "entries");
            // Resolve the original plan independently BEFORE candidate loading, not from its IAT.
            // This kernel32 subset remains conditional development mechanics, not startup authority.
            stage = Stage.IMPORT;
            imports = bootstrap.resolveSystemImports(plan);
            long[] importTargets = imports.addresses();
            check(importTargets.length == imported.length / 2);
            long[] alteredCopy = imports.addresses();
            alteredCopy[0] ^= 1;
            check(Arrays.equals(imports.addresses(), importTargets));
            expect(IllegalStateException.class, () -> bootstrap.resolveSystemImports(plan));
            stage = Stage.LOAD;
            load = WindowsLibraryLoadInvocation.prepare(this, originalJvm, file, entries[5], originalArena,
                path.toString());
            loaded = load.invoke();
            MemorySegment module = loaded.module();
            requireModulePath(module, path.toString());

            stage = Stage.EXPORT;
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
            stage = Stage.READ;
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
            stage = Stage.COMPARE;
            long[] verified;
            try {
                verified = plan.verify(module.address(), exportTargets, importTargets, pages);
            } catch (Throwable comparisonFailure) {
                // Observe ONLY after refusal, with the original copied test DLL bytes and existing readbacks.
                // No retry, additional native read, byte masking or changed acceptance requirement.
                try {
                    String observation = (String) helper.getMethod("mappedObservation", byte[].class, long.class,
                        long[].class, byte[][].class).invoke(null, originalBytes, module.address(), requested, pages);
                    check(observation.matches("WINDOWS_LOADED_MAPPED_OBSERVATION first=" +
                        "(NONE|HEADER_RAW|HEADER_PADDING|EXECUTABLE_RAW|EXECUTABLE_PADDING|RELOCATION)" +
                        " offset=([0-9]|[1-9][0-9]{1,2}|[1-3][0-9]{3}|40[0-8][0-9]|409[0-5])" +
                        " headerFilePage=(MATCH|DIFFERENT) executable=(MATCH|DIFFERENT)"));
                    mappedObservation = observation;
                } catch (Throwable diagnosticFailure) {
                    mappedObservationFailure = diagnosticFailure;
                }
                throw comparisonFailure;
            }
            stage = Stage.REGISTER;
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
                stage = Stage.ABI;
                expect(UnsatisfiedLinkError.class, () -> abi.invoke(null));
            } else {
                owner = WindowsJniRegistrationOwner.registerOnce(roots, registration);
                check(owner.state() == WindowsJniRegistrationOwner.State.Registered);
                check(field(owner, "report").equals(new WindowsJniRegistrationOwner.Report(32, 1, 2, 0, 1, 0, 0, 0)));
                stage = Stage.ABI;
                check(abi.invoke(null).equals(13) && capabilities.invoke(null).equals(0x43L));
                System.gc(); // A request, not a claim that collection occurred.
                check(abi.invoke(null).equals(13) && capabilities.invoke(null).equals(0x43L));
            }
            stage = Stage.RETIRE;
            check(owner == WindowsJniRegistrationOwner.retainedProcessOwner() && owner.retention == roots &&
                owner.ownsInvocation(registration));
            check(!entriesFrame.scope().isAlive() && !reportFrame.scope().isAlive());
            expect(IllegalStateException.class, () -> WindowsJniRegistrationOwner.registerOnce(roots, registration));
            check(file.isOpen() && originalArena.scope().isAlive() && loaded.module().address() == module.address());
            check(vm.virtualMachine().scope().isAlive() && registrar.scope().isAlive());
            check(Arrays.equals(imports.addresses(), importTargets));
            check(field(bootstrap, "imports") == imports && field(imports, "plan") == plan);
            check(Boolean.TRUE.equals(field(imports, "frameRetired")) &&
                !((Arena) field(imports, "frameArena")).scope().isAlive());
            if (args[0].equals("success")) check(abi.invoke(null).equals(13));
        }

        // Preserve the original candidate pathname assertion separately from production import mechanics.
        // This test-only frame remains rooted with the fixture on both success and any uncertain return.
        private void requireModulePath(MemorySegment module, String expected) throws Throwable {
            modulePathArena = Arena.ofConfined();
            MemoryLayout layout = MemoryLayout.sequenceLayout(1024, ValueLayout.JAVA_SHORT);
            modulePathBuffer = modulePathArena.allocate(layout);
            modulePathCall = Linker.nativeLinker().downcallHandle(entries[2],
                FunctionDescriptor.of(ValueLayout.JAVA_INT, ValueLayout.ADDRESS,
                    ValueLayout.ADDRESS.withTargetLayout(layout), ValueLayout.JAVA_INT));
            modulePathBuffer.fill((byte) 0x7f);
            int length = (int) modulePathCall.invokeExact(module, modulePathBuffer, 1024);
            check(length > 0 && length < 1024 && modulePathBuffer.getAtIndex(ValueLayout.JAVA_SHORT, length) == 0);
            char[] characters = new char[length];
            for (int index = 0; index < length; index++) {
                int value = Short.toUnsignedInt(modulePathBuffer.getAtIndex(ValueLayout.JAVA_SHORT, index));
                check(value >= 32 && value < 127);
                characters[index] = (char) value;
            }
            check(new String(characters).equalsIgnoreCase(expected));
        }
    }

    /** Closed diagnostic projection. Never emit a throwable message, filename, method, path, address or cause text. */
    private static String diagnostic(Stage stage, Throwable failure) {
        Throwable actual = failure;
        for (int depth = 0; depth < 8; depth++) {
            Throwable next;
            if (actual.getClass() == InvocationTargetException.class) {
                next = ((InvocationTargetException) actual).getTargetException();
            } else if (actual.getClass() == WindowsSystemImportResolution.Failure.class) {
                next = ((WindowsSystemImportResolution.Failure) actual).operationFailure;
            } else break;
            if (next == null || next == actual) break;
            actual = next;
        }
        Category category = actual instanceof AssertionError ? Category.ASSERTION :
            actual instanceof IllegalArgumentException ? Category.ARGUMENT :
            actual instanceof IllegalStateException ? Category.STATE :
            actual instanceof LinkageError ? Category.LINKAGE :
            actual instanceof ReflectiveOperationException ? Category.REFLECTION :
            actual instanceof java.io.IOException ? Category.IO :
            actual instanceof SecurityException ? Category.SECURITY :
            actual instanceof Error ? Category.ERROR :
            actual instanceof Exception ? Category.EXCEPTION : Category.UNKNOWN;
        Site found = Site.SITE_UNKNOWN;
        int line = 0;
        StackTraceElement[] frames = actual.getStackTrace();
        for (int index = 0; index < Math.min(64, frames.length); index++) {
            StackTraceElement frame = frames[index];
            // These assertion helpers obscure the actual fixture call site; no native frame is guessed.
            if (frame.getClassName().equals(LOADER + "LoadedRegistrationTests") &&
                (frame.getMethodName().equals("check") || frame.getMethodName().equals("expect"))) continue;
            Site candidate = site(frame.getClassName());
            if (candidate != Site.SITE_UNKNOWN && frame.getLineNumber() > 0 && frame.getLineNumber() <= 4096) {
                found = candidate;
                line = frame.getLineNumber();
                break;
            }
        }
        return "WINDOWS_LOADED_REGISTRATION_REFUSED stage=" + stage.name() + " category=" + category.name() +
            " site=" + found.name() + " line=" + line;
    }

    private static Site site(String name) {
        return switch (name) {
            case LOADER + "LoadedRegistrationTests", LOADER + "LoadedRegistrationTests$Fixture" -> Site.FIXTURE;
            case LOADER + "WindowsSystemImportResolution" -> Site.SYSTEM_IMPORT_RESOLUTION;
            case LOADER + "PackagedVerifierTests" -> Site.CLASS_BINDING;
            case LOADER + "WindowsPackagedVerifier" -> Site.PACKAGED_ADAPTER;
            case PROFILE + "WindowsProfilePackagedVerifier", PROFILE + "WindowsProfilePackagedVerifier$Companion",
                PROFILE + "WindowsProfileLoadedNativeFixture" -> Site.PACKAGED_HELPER;
            case PROFILE + "WindowsProfilePeImage", PROFILE + "WindowsProfilePeImage$Reader" -> Site.PE_IMAGE;
            case PROFILE + "WindowsProfileByteManifest" -> Site.BYTE_MANIFEST;
            case PROFILE + "WindowsProfileMappedCode", PROFILE + "WindowsProfileMappedCode$Companion" ->
                Site.MAPPED_CODE;
            case PROFILE + "WindowsProfileImportAddresses", PROFILE + "WindowsProfileImportAddresses$Plan",
                PROFILE + "WindowsProfileImportAddresses$Plan$Companion" -> Site.IMPORT_ADDRESSES;
            case PROFILE + "WindowsProfileExportAddresses" -> Site.EXPORT_ADDRESSES;
            case PROFILE + "WindowsProfileJniPlan", PROFILE + "WindowsProfileJniPlan$Companion" -> Site.JNI_PLAN;
            case PROFILE + "WindowsProfileCustodyJni" -> Site.JNI_DECLARATION;
            case LOADER + "WindowsLoaderRuntime", LOADER + "WindowsLoader" -> Site.LOADER_RUNTIME;
            case LOADER + "WindowsSystemBootstrapCandidate" -> Site.SYSTEM_BOOTSTRAP;
            case LOADER + "WindowsOriginalJvmCandidate" -> Site.ORIGINAL_JVM;
            case LOADER + "WindowsJvmAcquisitionInvocation" -> Site.JVM_ACQUISITION;
            case LOADER + "WindowsLibraryLoadInvocation" -> Site.LIBRARY_LOAD;
            case LOADER + "WindowsExportLookupInvocation" -> Site.EXPORT_LOOKUP;
            case LOADER + "WindowsImageReadInvocation" -> Site.IMAGE_READ;
            case LOADER + "WindowsJniRegistrationInvocation" -> Site.REGISTRATION_INVOCATION;
            case LOADER + "WindowsJniRegistrationOwner" -> Site.REGISTRATION_OWNER;
            default -> Site.SITE_UNKNOWN;
        };
    }

    private static void diagnostics() {
        String secret = "C:\\private\\DO_NOT_PRINT\naddress=0x12345678";
        Throwable assertion = new AssertionError(secret);
        assertion.setStackTrace(new StackTraceElement[] {
            new StackTraceElement(LOADER + "LoadedRegistrationTests", "check", secret, 409),
            new StackTraceElement(LOADER + "LoadedRegistrationTests$Fixture", secret, secret, 123),
        });
        String expected = "WINDOWS_LOADED_REGISTRATION_REFUSED stage=READ category=ASSERTION site=FIXTURE line=123";
        check(diagnostic(Stage.READ, assertion).equals(expected));
        try {
            var constructor = WindowsSystemImportResolution.Failure.class
                .getDeclaredConstructor(WindowsSystemImportResolution.class);
            constructor.setAccessible(true);
            WindowsSystemImportResolution.Failure retainedFailure = constructor.newInstance((Object) null);
            retainedFailure.operationFailure = new IllegalStateException(secret);
            retainedFailure.operationFailure.setStackTrace(new StackTraceElement[] {
                new StackTraceElement(LOADER + "WindowsSystemImportResolution", secret, secret, 200),
            });
            check(diagnostic(Stage.IMPORT, retainedFailure).equals("WINDOWS_LOADED_REGISTRATION_REFUSED" +
                " stage=IMPORT category=STATE site=SYSTEM_IMPORT_RESOLUTION line=200"));
        } catch (ReflectiveOperationException unexpected) {
            throw new AssertionError("Inert retained-failure diagnostic fixture failed", unexpected);
        }
        Throwable nested = assertion;
        for (int depth = 0; depth < 8; depth++) nested = new InvocationTargetException(nested, secret);
        check(diagnostic(Stage.READ, nested).equals(expected));
        Throwable tooDeep = new InvocationTargetException(nested, secret);
        tooDeep.setStackTrace(new StackTraceElement[0]);
        // The ninth wrapper is not unwrapped; no unbounded cause traversal or borrowed assertion category.
        String bounded = diagnostic(Stage.READ, tooDeep);
        check(bounded.contains(" category=REFLECTION "));
        check(!bounded.contains("ASSERTION") && !bounded.contains(secret));
        Throwable ordinary = new Exception(secret, assertion);
        ordinary.addSuppressed(assertion);
        ordinary.setStackTrace(new StackTraceElement[] {
            new StackTraceElement(secret, secret, secret, 123),
            new StackTraceElement(LOADER + "WindowsImageReadInvocation", secret, secret, -2),
            new StackTraceElement(LOADER + "WindowsImageReadInvocation", secret, secret, 4097),
        });
        check(diagnostic(Stage.IMPORT, ordinary).equals(
            "WINDOWS_LOADED_REGISTRATION_REFUSED stage=IMPORT category=EXCEPTION site=SITE_UNKNOWN line=0"));
        check(ordinary.getCause() == assertion && ordinary.getSuppressed().length == 1 &&
            ordinary.getSuppressed()[0] == assertion && ordinary.getStackTrace().length == 3);
        StackTraceElement[] many = new StackTraceElement[65];
        Arrays.fill(many, new StackTraceElement(secret, secret, secret, 1));
        many[64] = new StackTraceElement(LOADER + "WindowsImageReadInvocation", secret, secret, 7);
        ordinary.setStackTrace(many);
        check(diagnostic(Stage.READ, ordinary).endsWith(" site=SITE_UNKNOWN line=0"));
        Throwable[] categories = {new IllegalArgumentException(secret), new IllegalStateException(secret),
            new UnsatisfiedLinkError(secret), new NoSuchMethodException(secret), new java.io.IOException(secret),
            new SecurityException(secret), new Error(secret), new Throwable(secret)};
        Category[] names = {Category.ARGUMENT, Category.STATE, Category.LINKAGE, Category.REFLECTION,
            Category.IO, Category.SECURITY, Category.ERROR, Category.UNKNOWN};
        for (int index = 0; index < categories.length; index++) {
            categories[index].setStackTrace(new StackTraceElement[0]);
            check(diagnostic(Stage.PREFLIGHT, categories[index]).equals(
                "WINDOWS_LOADED_REGISTRATION_REFUSED stage=PREFLIGHT category=" + names[index].name() +
                    " site=SITE_UNKNOWN line=0"));
        }
        for (Stage stage : Stage.values()) {
            String projected = diagnostic(stage, assertion);
            check(projected.matches("WINDOWS_LOADED_REGISTRATION_REFUSED stage=[A-Z_]+" +
                " category=ASSERTION site=FIXTURE line=123"));
            check(!projected.contains(secret) && projected.indexOf('\n') < 0 && projected.length() <= 192);
        }
        check(retained == null); // Formatter validation never acquired the native fixture's process owner.
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
