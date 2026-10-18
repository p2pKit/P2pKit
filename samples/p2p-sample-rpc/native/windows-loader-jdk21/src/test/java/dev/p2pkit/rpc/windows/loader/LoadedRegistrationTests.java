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
        LIBRARY_LOAD, LOADED_IMAGE, EXPORT_LOOKUP, IMAGE_READ, REGISTRATION_INVOCATION, REGISTRATION_OWNER,
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
        check(mode.equals("success") || mode.equals("address") || mode.equals("pin") || mode.equals("preloaded"));
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
        private Arena preloadArena;
        private MemorySegment preloadPath;
        private MethodHandle preloadCall;
        private long rawPreloadedModule;
        private boolean preloadReturnUnconfirmed;
        private MemorySegment preloadedModule;
        private WindowsLibraryLoadInvocation load;
        private WindowsLibraryLoadInvocation.Result loaded;
        private WindowsLoadedProfileImageVerification image;
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
            if (args[0].equals("preloaded")) {
                preloadedRefusal(path.toString(), abi);
                return;
            }
            load = WindowsLibraryLoadInvocation.prepareDevelopment(bootstrap, this, originalJvm, file, path.toString());
            loaded = load.invoke();
            MemorySegment module = loaded.module();
            requireModulePath(module, path.toString());

            stage = Stage.EXPORT;
            try {
                image = loaded.verifyImage(bootstrap, plan, imports);
            } catch (WindowsLoadedProfileImageVerification.Failure comparisonFailure) {
                image = comparisonFailure.retainedVerification;
                int phase = (int) field(image, "phase");
                stage = switch (phase) {
                    case WindowsLoadedProfileImageVerification.READ -> Stage.READ;
                    case WindowsLoadedProfileImageVerification.COMPARE -> Stage.COMPARE;
                    default -> Stage.EXPORT;
                };
                if (phase == WindowsLoadedProfileImageVerification.COMPARE) {
                    // Failure-only diagnostics consume this same owner's retained readbacks. No second
                    // lookup/read, relaxed byte comparison, alternate import target or retry is performed.
                    try {
                        long[] requested = (long[]) field(image, "requested");
                        byte[][] pages = (byte[][]) field(image, "pages");
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
                }
                throw comparisonFailure;
            }
            check(image.declaringClass() == declaration && image.originalJvm() == originalJvm);
            MemorySegment[] nativeMethods = image.jniEntries();
            check(nativeMethods.length == 23);
            long[] methods = new long[23];
            for (int index = 0; index < methods.length; index++) methods[index] = nativeMethods[index].address();
            MemorySegment registrar = image.registrar();
            MemorySegment[] alteredMethods = image.jniEntries();
            alteredMethods[0] = MemorySegment.NULL;
            check(image.jniEntries()[0] == nativeMethods[0]);
            expect(IllegalStateException.class, () -> loaded.verifyImage(bootstrap, plan, imports));
            expect(IllegalStateException.class, () -> loaded.verifyImage(bootstrap, plan));
            check(field(load, "imageVerification") == image);
            WindowsExportLookupInvocation[] exports = (WindowsExportLookupInvocation[]) field(image, "exports");
            WindowsImageReadInvocation[] reads = (WindowsImageReadInvocation[]) field(image, "reads");
            check(exports.length == 24 && reads.length == ((long[]) field(image, "requested")).length / 3);
            for (WindowsExportLookupInvocation export : exports) {
                check(Boolean.TRUE.equals(field(export, "retired")) &&
                    !((Arena) field(export, "frameArena")).scope().isAlive());
            }
            for (WindowsImageReadInvocation read : reads) {
                check(Boolean.TRUE.equals(field(read, "retired")) &&
                    !((Arena) field(read, "frameArena")).scope().isAlive());
            }
            stage = Stage.REGISTER;
            WindowsJvmAcquisitionInvocation.Result vm =
                (WindowsJvmAcquisitionInvocation.Result) field(originalJvm, "acquired");
            WindowsJniRegistrationOwner.Retention roots;
            if (args[0].equals("address")) {
                roots = new WindowsJniRegistrationOwner.Retention(image, originalJvm, load, declaration, plan);
                methods[0]++; // Existing low-level negative: registrar compares but never calls this bad address.
                registration = WindowsJniRegistrationInvocation.prepare(roots, registrar, vm.virtualMachine(), methods);
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
                owner = image.registerOriginalJni(); // Same typed production mechanics, no caller-chosen JNI inputs.
                registration = (WindowsJniRegistrationInvocation) field(image, "registrationInvocation");
                roots = (WindowsJniRegistrationOwner.Retention) field(image, "registrationRoots");
                check(field(image, "registrationVm") == vm && field(image, "registrationOwner") == owner &&
                    field(image, "registrationFailure") == null && roots.installationOwner() == image &&
                    roots.runtimeOwner() == originalJvm && roots.moduleOwner() == loaded &&
                    roots.declaringClass() == declaration && roots.registrationPlan() == plan);
                check(owner.state() == WindowsJniRegistrationOwner.State.Registered);
                check(field(owner, "report").equals(new WindowsJniRegistrationOwner.Report(32, 1, 2, 0, 1, 0, 0, 0)));
                stage = Stage.ABI;
                check(abi.invoke(null).equals(13) && capabilities.invoke(null).equals(0x43L));
                System.gc(); // A request, not a claim that collection occurred.
                check(abi.invoke(null).equals(13) && capabilities.invoke(null).equals(0x43L));
            }
            stage = Stage.RETIRE;
            MemorySegment entriesFrame = (MemorySegment) field(registration, "entries");
            MemorySegment reportFrame = (MemorySegment) field(registration, "output");
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
            if (args[0].equals("success")) {
                expect(IllegalStateException.class, image::registerOriginalJni);
                check(field(image, "registrationOwner") == owner && field(image, "registrationInvocation") == registration);
                check(image.jniEntries()[0] == nativeMethods[0] && image.registrar() == registrar);
                check(abi.invoke(null).equals(13));
            } else {
                // The already retained negative owner makes this separate typed attempt a controller refusal.
                // Its private prepared frame is retained, not claimed retired or registered; there is no retry.
                WindowsLoadedProfileImageVerification.Failure refused = (WindowsLoadedProfileImageVerification.Failure)
                    expect(WindowsLoadedProfileImageVerification.Failure.class, image::registerOriginalJni);
                check(refused.retainedVerification == image && refused.operationFailure instanceof IllegalStateException &&
                    field(image, "registrationFailure") == refused.operationFailure &&
                    field(image, "registrationVm") == vm && field(image, "registrationOwner") == null);
                WindowsJniRegistrationInvocation unentered =
                    (WindowsJniRegistrationInvocation) field(image, "registrationInvocation");
                check(unentered != registration && !(boolean) field(unentered, "attempted") &&
                    ((MemorySegment) field(unentered, "output")).scope().isAlive());
                expect(IllegalStateException.class, image::jniEntries);
                expect(IllegalStateException.class, image::registrar);
                expect(IllegalStateException.class, image::originalJvm);
                expect(IllegalStateException.class, image::registerOriginalJni);
                check(owner == WindowsJniRegistrationOwner.retainedProcessOwner() &&
                    field(image, "registrationInvocation") == unentered && file.isOpen());
                expect(UnsatisfiedLinkError.class, () -> abi.invoke(null));
            }
        }

        /** Preload only the already byte-checked maintained DENY-STORAGE fixture, outside the load process slot. */
        private void preloadedRefusal(String path, Method abi) throws Throwable {
            WindowsProfileDllPath.require(path);
            Field process = WindowsLibraryLoadInvocation.class.getDeclaredField("processOwner");
            process.setAccessible(true);
            check(process.get(null) == null && loaded == null && owner == null && file.isOpen());
            preloadArena = Arena.ofConfined();
            preloadPath = preloadArena.allocate(WindowsLibraryLoadInvocation.PATH);
            for (int index = 0; index < path.length(); index++) {
                preloadPath.setAtIndex(ValueLayout.JAVA_SHORT, index, (short) path.charAt(index));
            }
            preloadCall = Linker.nativeLinker().downcallHandle(
                bootstrap.originalLibraryLoadEntry(originalJvm, 1), WindowsLibraryLoadInvocation.DESCRIPTOR);
            // The retained fixture owns the native input and primitive return BEFORE any wrapper or check.
            // No WindowsLibraryLoadInvocation exists yet, no JNI binding, and this module is never unloaded.
            preloadReturnUnconfirmed = true;
            rawPreloadedModule = (long) preloadCall.invokeExact(preloadPath, MemorySegment.NULL,
                WindowsLibraryLoadInvocation.SEARCH_SYSTEM32);
            preloadReturnUnconfirmed = false;
            check(rawPreloadedModule > 0 && (rawPreloadedModule & 65_535) == 0);
            preloadedModule = MemorySegment.ofAddress(rawPreloadedModule).reinterpret(originalArena, null);
            requireModulePath(preloadedModule, path);
            check(process.get(null) == null);
            expect(UnsatisfiedLinkError.class, () -> abi.invoke(null));
            load = WindowsLibraryLoadInvocation.prepareDevelopment(bootstrap, this, originalJvm, file, path);
            WindowsLibraryLoadInvocation.Failure refused = (WindowsLibraryLoadInvocation.Failure)
                expect(WindowsLibraryLoadInvocation.Failure.class, load::invoke);
            check(refused.retainedInvocation == load && refused.probeFailure instanceof IllegalStateException &&
                refused.invocationFailure == null && refused.readbackFailure == null && !refused.retirementFailed());
            check(process.get(null) == load && (boolean) field(load, "attempted") &&
                (boolean) field(load, "probeAttempted") && (boolean) field(load, "probeReturned") &&
                (int) field(load, "probeStatus") != 0 && (long) field(load, "rawPreexistingModule") == rawPreloadedModule);
            check(!(boolean) field(load, "nativeReturned") && !(boolean) field(load, "nativeReturnUnconfirmed") &&
                !(boolean) field(load, "probeObservationUnconfirmed") && (long) field(load, "rawModule") == 0 &&
                field(load, "module") == null && !(boolean) field(load, "succeeded") &&
                !((Arena) field(load, "frameArena")).scope().isAlive());
            expect(IllegalStateException.class, load::invoke);
            expect(UnsatisfiedLinkError.class, () -> abi.invoke(null));
            check(loaded == null && image == null && registration == null && owner == null && file.isOpen() &&
                !preloadReturnUnconfirmed && preloadArena.scope().isAlive() && originalJvm.completed() &&
                preloadedModule.scope().isAlive());
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
            } else if (actual.getClass() == WindowsLoadedProfileImageVerification.Failure.class) {
                next = ((WindowsLoadedProfileImageVerification.Failure) actual).operationFailure;
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
            case LOADER + "WindowsLoadedProfileImageVerification" -> Site.LOADED_IMAGE;
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
        try {
            var constructor = WindowsLoadedProfileImageVerification.Failure.class
                .getDeclaredConstructor(WindowsLoadedProfileImageVerification.class);
            constructor.setAccessible(true);
            WindowsLoadedProfileImageVerification.Failure imageFailure = constructor.newInstance((Object) null);
            imageFailure.operationFailure = new IllegalStateException(secret);
            imageFailure.operationFailure.setStackTrace(new StackTraceElement[] {
                new StackTraceElement(LOADER + "WindowsLoadedProfileImageVerification", secret, secret, 120),
            });
            check(diagnostic(Stage.COMPARE, imageFailure).equals("WINDOWS_LOADED_REGISTRATION_REFUSED" +
                " stage=COMPARE category=STATE site=LOADED_IMAGE line=120"));
        } catch (ReflectiveOperationException unexpected) {
            throw new AssertionError("Inert loaded-image diagnostic fixture failed", unexpected);
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
