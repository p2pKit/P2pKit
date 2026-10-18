package dev.p2pkit.rpc.windows.loader;

import java.lang.foreign.Arena;
import java.lang.foreign.MemorySegment;
import java.lang.foreign.ValueLayout;
import java.lang.invoke.MethodHandles;
import java.lang.invoke.MethodType;
import java.lang.reflect.Constructor;
import java.lang.reflect.InvocationTargetException;
import java.lang.reflect.Method;
import java.lang.reflect.Modifier;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Arrays;
import java.util.Locale;
import java.util.concurrent.atomic.AtomicReference;
import java.util.jar.JarEntry;
import java.util.jar.JarOutputStream;

import static dev.p2pkit.rpc.windows.loader.OriginalFileBytesLeaseTests.check;
import static dev.p2pkit.rpc.windows.loader.OriginalFileBytesLeaseTests.expect;
import static dev.p2pkit.rpc.windows.loader.OriginalFileBytesLeaseTests.field;
import static dev.p2pkit.rpc.windows.loader.OriginalFileBytesLeaseTests.invoke;
import static dev.p2pkit.rpc.windows.loader.OriginalFileBytesLeaseTests.value;

/** Inert guards/private call frames and ordinary parser fixtures, never installed/native qualification. */
public final class InstalledProfilePreparationTests {
    private static final String ROOT = "C:\\Program Files\\P2pKit Sample";
    private static final String PIN = "META-INF/p2pkit/windows-profile-parent.properties";
    private static final String DATA = "schema=1\nscope=PACKAGED_COMPONENT_PIN_NOT_LOAD_AUTHORITY\nsource=" + "a".repeat(40) +
        "\ntree=" + "b".repeat(40) + "\nmanifestSha256=" + "c".repeat(64) + "\ndllSha256=" + "d".repeat(64) + "\n";
    private static int calls;
    private static boolean unknown;
    private static final LinkageError UNKNOWN = new LinkageError("inert missing primitive return");
    private InstalledProfilePreparationTests() {}

    public static void main(String[] arguments) throws Throwable {
        check(arguments.length == 1);
        WindowsLoaderRuntime.requireDiagnosticRuntime();
        String mode = arguments[0];
        switch (mode) {
            case "contract" -> contract();
            case "owners" -> owners();
            case "policy" -> policy();
            case "failure-latch" -> failureLatch();
            case "thread" -> wrongThread();
            case "root-match", "root-mutations" -> roots(mode.equals("root-mutations"));
            case "known-folder-path" -> knownPath();
            case "folder-call", "folder-unknown" -> folderCall(mode.equals("folder-unknown"));
            case "folder-retirement" -> retirement();
            case "parent-fields" -> parentFields();
            case "parent-origin" -> parentOrigin();
            case "parent-archive" -> parentArchive();
            case "manifest-bounds" -> manifestBounds();
            case "load-gates" -> loadGates();
            case "registration-contract" -> registrationContract();
            case "registration-unprepared" -> registrationUnprepared();
            case "registration-owner" -> registrationOwner();
            case "registration-policy" -> registrationPolicy();
            case "registration-thread" -> registrationThread();
            case "registration-failed" -> registrationFailed();
            case "registration-consumed" -> registrationConsumed();
            default -> throw new AssertionError("Unknown installed pre-load control");
        }
        expect(WindowsLoader.Unavailable.class, WindowsLoader::openInstalledProvider);
        if (mode.startsWith("registration-")) {
            System.out.println("WINDOWS_INSTALLED_REGISTRATION_GUARDS_PASS case=" + mode +
                " scope=GUARDS_ONLY_NOT_LOAD_VERIFY_OR_JNI_EXECUTION");
        } else {
            System.out.println("WINDOWS_INSTALLED_PRELOAD_PASS case=" + mode +
                " scope=INERT_BINDINGS_AND_FIXED_FRAMES_NOT_INSTALLED_NATIVE_OR_PROVIDER_QUALIFICATION");
        }
    }

    private static Object staticCall(Class<?> type, String name, Class<?>[] types, Object... arguments) throws Throwable {
        Method method = type.getDeclaredMethod(name, types);
        method.setAccessible(true);
        try { return method.invoke(null, arguments); }
        catch (InvocationTargetException failure) { throw failure.getCause(); }
    }

    private static void contract() throws Throwable {
        Method entry = WindowsOriginalInstallationCandidate.class.getDeclaredMethod("prepareProfileLoad");
        check(entry.getParameterCount() == 0 && entry.getReturnType() == WindowsInstalledProfileCandidate.class && !Modifier.isPublic(entry.getModifiers()));
        Method prepare = WindowsLibraryLoadInvocation.class.getDeclaredMethod("prepareInstalled", WindowsInstalledProfileCandidate.class);
        check(!Modifier.isPublic(prepare.getModifiers()));
        check(!Modifier.isPublic(WindowsInstalledProfileCandidate.class.getModifiers()));
        check(Arrays.stream(WindowsInstalledProfileCandidate.class.getDeclaredMethods()).noneMatch(m -> m.getName().equals("invoke")));
        expect(IllegalArgumentException.class, () -> WindowsLibraryLoadInvocation.prepareInstalled(null));
        expect(IllegalArgumentException.class, () -> WindowsInstalledParentPin.read(null));
        WindowsInstalledProfileCandidate empty = new WindowsInstalledProfileCandidate(null);
        expect(IllegalStateException.class, empty::prepare);
        check(!(boolean) value(empty, "attempted") && value(empty, "load") == null);
    }

    private static void owners() throws Throwable {
        try (Fixture fixture = new Fixture(); Fixture other = new Fixture()) {
            check(fixture.child.originalRoot().equals(ROOT));
            check(fixture.child.fixedJvmPath().equals(ROOT + "\\runtime\\bin\\server\\jvm.dll"));
            expect(IllegalStateException.class, fixture.child::fixedProfilePath);
            expect(IllegalStateException.class, () -> fixture.installation.requireOriginalProfile(other.child));
            expect(IllegalStateException.class, () -> fixture.child.requireOriginalJvmFile(null));
            expect(IllegalStateException.class, () -> fixture.child.requireOriginalProfileFile(null));
            expect(IllegalStateException.class, () -> fixture.child.requireOriginalKnownFolder(new WindowsOriginalProgramFilesCandidate(fixture.child)));
            check(value(fixture.child, "jvm") == null && value(fixture.child, "profile") == null);
            expect(IllegalStateException.class, fixture.installation::prepareProfileLoad); // Existing attempt cannot reset.
        }
    }

    private static void policy() throws Throwable {
        for (String flag : new String[] {"leafPolicyRefused", "ancestorPolicyRefused"}) {
            try (Fixture fixture = new Fixture()) {
                field(fixture.installation, flag).setBoolean(fixture.installation, true);
                expect(IllegalStateException.class, fixture.child::prepare);
                expect(IllegalStateException.class, () -> WindowsLibraryLoadInvocation.prepareInstalled(fixture.child));
                check(!(boolean) value(fixture.child, "attempted") && value(fixture.child, "systems") == null);
            }
        }
    }

    private static void failureLatch() throws Throwable {
        try (Fixture fixture = new Fixture()) {
            field(fixture.bootstrap, "systemModulesAttempted").setBoolean(fixture.bootstrap, true);
            Throwable failed = expect(WindowsInstalledProfileCandidate.Failure.class, fixture.child::prepare);
            check(((WindowsInstalledProfileCandidate.Failure) failed).retainedCandidate == fixture.child);
            check(((WindowsInstalledProfileCandidate.Failure) failed).operationFailure instanceof IllegalStateException);
            check(expect(WindowsInstalledProfileCandidate.Failure.class, fixture.child::prepare) == failed);
            check(value(fixture.child, "programFiles") == null && value(fixture.child, "jvm") == null && value(fixture.child, "load") == null);
        }
    }

    private static void wrongThread() throws Throwable {
        try (Fixture fixture = new Fixture()) {
            AtomicReference<Throwable> caught = new AtomicReference<>();
            Thread thread = Thread.startVirtualThread(() -> {
                try {
                    expect(IllegalStateException.class, fixture.child::prepare);
                    expect(IllegalStateException.class, fixture.child::originalRoot);
                    expect(IllegalStateException.class, () -> WindowsLibraryLoadInvocation.prepareInstalled(fixture.child));
                } catch (Throwable failure) { caught.set(failure); }
            });
            thread.join();
            check(caught.get() == null && !(boolean) value(fixture.child, "attempted"));
        }
    }

    private static void roots(boolean mutations) throws Throwable {
        char[] path = (ROOT + "\\runtime\\bin\\server\\jvm.dll\0").toCharArray();
        char[] guid = "\\\\?\\Volume{12345678-1234-1234-1234-123456789abc}\\".toCharArray();
        check(guid.length == 49);
        long[][] left = new long[3][8], right = new long[6][8];
        for (int index = 0; index < 3; index++) {
            left[index] = new long[] {123, index + 1, index + 10, 5, 6, 1, 16, 0};
            right[index] = left[index].clone();
            right[index][3] += 100; right[index][4] += 200; // Allocation/size are not stable directory identity.
        }
        rootCompare(ROOT, path, guid, guid.clone(), left, right, 3, 6);
        if (!mutations) return;
        for (int directory = 0; directory < 3; directory++) {
            for (int item : new int[] {0, 1, 2, 5, 6, 7}) {
                right[directory][item]++;
                expect(IllegalStateException.class, () -> rootCompare(ROOT, path, guid, guid, left, right, 3, 6));
                right[directory][item]--;
            }
        }
        char[] changed = guid.clone(); changed[12] = 'f';
        expect(IllegalStateException.class, () -> rootCompare(ROOT, path, guid, changed, left, right, 3, 6));
        expect(IllegalStateException.class, () -> rootCompare("D" + ROOT.substring(1), path, guid, guid, left, right, 3, 6));
        expect(IllegalStateException.class, () -> rootCompare(ROOT + "x", path, guid, guid, left, right, 3, 6));
        expect(IllegalStateException.class, () -> rootCompare(ROOT, path, guid, guid, left, right, 3, 3));
    }

    private static void rootCompare(String root, char[] path, char[] a, char[] b, long[][] left, long[][] right, int lc, int rc) throws Throwable {
        staticCall(WindowsOriginalFileAncestorsLease.class, "compareRootObservations",
            new Class<?>[] {String.class, char[].class, int.class, char[].class, char[].class, long[][].class, long[][].class, int.class, int.class},
            root, path, path.length - 1, a, b, left, right, lc, rc);
    }

    private static void knownPath() throws Throwable {
        try (Arena arena = Arena.ofConfined()) {
            MemorySegment path = arena.allocate(520, 2);
            put(path, "C:\\Program Files");
            validateKnown(path, 0, ROOT);
            validateKnown(path, 0, ROOT.toLowerCase(Locale.ROOT));
            for (int status : new int[] {1, -1, Integer.MIN_VALUE}) expect(IllegalStateException.class, () -> validateKnown(path, status, ROOT));
            for (String text : new String[] {"", "C:\\Program Files (x86)", "D:\\Program Files", "C:\\Program Files\\", "C:/Program Files"}) {
                put(path, text);
                expect(IllegalStateException.class, () -> validateKnown(path, 0, ROOT));
            }
            path.fill((byte) 0x7f);
            expect(IllegalStateException.class, () -> validateKnown(path, 0, ROOT));
            for (int index = 0; index < 260; index++) path.setAtIndex(ValueLayout.JAVA_SHORT, index, (short) 'a');
            expect(IllegalStateException.class, () -> validateKnown(path, 0, ROOT));
        }
    }
    private static void validateKnown(MemorySegment path, int status, String root) throws Throwable {
        staticCall(WindowsOriginalProgramFilesCandidate.class, "validatePath", new Class<?>[] {MemorySegment.class, int.class, String.class}, path, status, root);
    }
    private static void put(MemorySegment path, String text) {
        path.fill((byte) 0);
        for (int index = 0; index < text.length(); index++) path.setAtIndex(ValueLayout.JAVA_SHORT, index, (short) text.charAt(index));
    }
    private static int fakeFolder(MemorySegment window, int csidl, MemorySegment token, int flags, MemorySegment path) {
        calls++;
        check(window.address() == 0 && token.address() == 0 && csidl == 0x26 && flags == 0 && path.byteSize() == 520);
        if (unknown) throw UNKNOWN;
        put(path, "C:\\Program Files");
        return 0;
    }
    private static void folderCall(boolean missingReturn) throws Throwable {
        calls = 0; unknown = missingReturn;
        WindowsOriginalProgramFilesCandidate query = new WindowsOriginalProgramFilesCandidate(null);
        Arena frame = Arena.ofConfined();
        try {
            MemorySegment[] buffers = (MemorySegment[]) value(query, "buffers");
            buffers[3] = frame.allocate(520, 2);
            field(query, "frameArena").set(query, frame);
            field(query, "attempted").setBoolean(query, true);
            field(query, "folderCall").set(query, MethodHandles.lookup().findStatic(InstalledProfilePreparationTests.class,
                "fakeFolder", MethodType.methodType(int.class, MemorySegment.class, int.class, MemorySegment.class, int.class, MemorySegment.class)));
            if (missingReturn) check(expect(LinkageError.class, () -> invoke(query, "invokeFolder")) == UNKNOWN);
            else { invoke(query, "invokeFolder"); validateKnown(buffers[3], (int) value(query, "folderStatus"), ROOT); }
            check(calls == 1 && (boolean) value(query, "nativeReturnUnconfirmed") == missingReturn);
            expect(IllegalStateException.class, () -> invoke(query, "invokeFolder"));
            invoke(query, "retireFrame");
            check(frame.scope().isAlive() == missingReturn && (boolean) value(query, "frameRetired") == !missingReturn);
        } finally {
            // Inert test owns this frame; no actual pending native operation exists.
            if (frame.scope().isAlive()) frame.close();
        }
    }

    private static void retirement() throws Throwable {
        WindowsOriginalProgramFilesCandidate query = new WindowsOriginalProgramFilesCandidate(null);
        try (Arena backing = Arena.ofConfined()) {
            Arena frame = Arena.ofConfined();
            MemorySegment[] buffers = (MemorySegment[]) value(query, "buffers");
            buffers[0] = backing.allocate(4).asReadOnly();
            buffers[1] = frame.allocate(8);
            field(query, "frameArena").set(query, frame);
            frame.close();
            invoke(query, "retireFrame");
            WindowsOriginalProgramFilesCandidate.Failure failure = (WindowsOriginalProgramFilesCandidate.Failure) value(query, "failure");
            check(failure.retainedCandidate == query && failure.clearFailures[0] != null && failure.clearFailures[1] != null && failure.arenaCloseFailure != null);
            invoke(query, "retireFrame");
            expect(IllegalStateException.class, query::completed);
        }
    }

    private static WindowsInstalledParentPin parse(byte[] data) throws Throwable {
        return (WindowsInstalledParentPin) staticCall(WindowsInstalledParentPin.class, "parse", new Class<?>[] {byte[].class}, (Object) data);
    }
    private static void parentFields() throws Throwable {
        byte[] data = DATA.getBytes(StandardCharsets.US_ASCII);
        WindowsInstalledParentPin pin = parse(data);
        check(pin.source().equals("a".repeat(40)) && pin.tree().equals("b".repeat(40)) && pin.manifestSha256().equals("c".repeat(64)) && pin.dllSha256().equals("d".repeat(64)));
        Arrays.fill(data, (byte) 0);
        check(pin.dllSha256().equals("d".repeat(64)));
        for (String bad : new String[] {"", DATA + "extra=1\n", DATA.replace("schema=1", "schema=2"),
            DATA.replace("source=", "tree="), DATA.replace("a".repeat(40), "a".repeat(39)),
            DATA.replace("c".repeat(64), "C".repeat(64)), DATA.replace("\n", "\r\n"), DATA.substring(0, DATA.length() - 1)}) {
            expect(IllegalStateException.class, () -> parse(bad.getBytes(StandardCharsets.US_ASCII)));
        }
        expect(IllegalStateException.class, () -> parse(new byte[4097]));
    }
    private static void origin(String root, String jar) throws Throwable {
        staticCall(WindowsInstalledParentPin.class, "requireOrigin", new Class<?>[] {String.class, String.class}, root, jar);
    }
    private static void parentOrigin() throws Throwable {
        String jar = "p2pkit-windows-profile-parent-pin.jar";
        origin(ROOT, ROOT + "\\app\\" + jar);
        origin(ROOT, ROOT + "\\app\\p2pkit-windows-profile-parent-pin-" + "a".repeat(32) + ".jar");
        for (String bad : new String[] {"D:\\Other\\app\\" + jar, ROOT + "\\elsewhere\\" + jar,
            ROOT + "\\app\\..\\" + jar, ROOT + "\\app\\nested\\" + jar, ROOT + "\\app\\other.jar", ROOT + "\\app\\" + jar + "\\extra"}) {
            expect(IllegalStateException.class, () -> origin(ROOT, bad));
        }
    }
    private static void parentArchive() throws Throwable {
        Path jar = Files.createTempFile("p2pkit-inert-parent-", ".jar");
        try {
            for (String name : new String[] {PIN, "other"}) {
                try (JarOutputStream out = new JarOutputStream(Files.newOutputStream(jar))) {
                    out.putNextEntry(new JarEntry(name)); out.write(DATA.getBytes(StandardCharsets.US_ASCII)); out.closeEntry();
                }
                if (name.equals(PIN)) check(((WindowsInstalledParentPin) staticCall(WindowsInstalledParentPin.class, "readArchive", new Class<?>[] {Path.class}, jar)).source().equals("a".repeat(40)));
                else expect(IllegalStateException.class, () -> staticCall(WindowsInstalledParentPin.class, "readArchive", new Class<?>[] {Path.class}, jar));
            }
            String alias = PIN.substring(0, PIN.length() - 1) + "X";
            try (JarOutputStream out = new JarOutputStream(Files.newOutputStream(jar))) {
                for (String name : new String[] {PIN, alias}) {
                    out.putNextEntry(new JarEntry(name)); out.write(DATA.getBytes(StandardCharsets.US_ASCII)); out.closeEntry();
                }
            }
            byte[] archive = Files.readAllBytes(jar), from = alias.getBytes(StandardCharsets.US_ASCII), to = PIN.getBytes(StandardCharsets.US_ASCII);
            int replacements = 0;
            for (int offset = 0; offset <= archive.length - from.length; offset++) {
                if (Arrays.equals(archive, offset, offset + from.length, from, 0, from.length)) {
                    System.arraycopy(to, 0, archive, offset, to.length); replacements++;
                }
            }
            check(replacements == 2); // Actual local+central duplicate JAR entry names; content CRC remains valid.
            Files.write(jar, archive);
            expect(IllegalStateException.class, () -> staticCall(WindowsInstalledParentPin.class, "readArchive", new Class<?>[] {Path.class}, jar));
            try (JarOutputStream out = new JarOutputStream(Files.newOutputStream(jar))) {
                out.putNextEntry(new JarEntry(PIN)); out.write(new byte[4097]); out.closeEntry();
            }
            expect(IllegalStateException.class, () -> staticCall(WindowsInstalledParentPin.class, "readArchive", new Class<?>[] {Path.class}, jar));
        } finally { Files.delete(jar); }
    }
    private static void manifestBounds() throws Throwable {
        Path path = Files.createTempFile("p2pkit-inert-manifest-", ".txt");
        try {
            for (int size : new int[] {0, 1, 4096, 4097}) {
                Files.write(path, new byte[size]);
                if (size == 1 || size == 4096) check(((byte[]) staticCall(WindowsInstalledProfileCandidate.class, "readManifest", new Class<?>[] {Path.class}, path)).length == size);
                else expect(IllegalStateException.class, () -> staticCall(WindowsInstalledProfileCandidate.class, "readManifest", new Class<?>[] {Path.class}, path));
            }
        } finally { Files.delete(path); }
    }
    private static void loadGates() throws Throwable {
        try (Fixture fixture = new Fixture()) {
            expect(IllegalStateException.class, () -> WindowsLibraryLoadInvocation.prepareInstalled(fixture.child));
            expect(IllegalArgumentException.class, () -> WindowsLibraryLoadInvocation.prepareDevelopment(fixture.bootstrap, fixture.installation, null, new Object(), "ignored"));
            expect(IllegalArgumentException.class, () -> WindowsLibraryLoadInvocation.prepareDevelopment(fixture.bootstrap, fixture.child, null, new Object(), "ignored"));
            check(value(fixture.child, "load") == null && value(fixture.child, "profile") == null);
            expect(IllegalStateException.class, () -> fixture.child.attachOriginalLoad(null));
            expect(IllegalStateException.class, () -> fixture.child.requireOriginalLoad(null));
        }
    }

    private static void registrationUnobserved(WindowsInstalledProfileCandidate child, boolean attempted) throws Throwable {
        check((boolean) value(child, "registrationAttempted") == attempted);
        check(value(child, "loadResult") == null && value(child, "imageVerification") == null &&
            value(child, "registrationOwner") == null && value(child, "load") == null);
    }

    private static void registrationContract() throws Throwable {
        Method entry = WindowsInstalledProfileCandidate.class.getDeclaredMethod("registerOriginalProfile");
        check(entry.getParameterCount() == 0 && entry.getReturnType() == WindowsJniRegistrationOwner.class);
        check(!Modifier.isPublic(entry.getModifiers()) && !Modifier.isProtected(entry.getModifiers()) &&
            !Modifier.isStatic(entry.getModifiers()));
        check(Arrays.stream(WindowsInstalledProfileCandidate.class.getDeclaredMethods())
            .filter(method -> method.getName().equals("registerOriginalProfile")).count() == 1);
        WindowsInstalledProfileCandidate empty = new WindowsInstalledProfileCandidate(null);
        expect(IllegalStateException.class, empty::registerOriginalProfile);
        registrationUnobserved(empty, false);
    }

    private static void registrationUnprepared() throws Throwable {
        try (Fixture fixture = new Fixture()) {
            for (int attempt = 0; attempt < 2; attempt++) {
                expect(IllegalStateException.class, fixture.child::registerOriginalProfile);
                registrationUnobserved(fixture.child, false);
                check(!(boolean) value(fixture.child, "failed"));
            }
        }
    }

    private static void registrationOwner() throws Throwable {
        try (Fixture fixture = new Fixture(); Fixture other = new Fixture()) {
            field(fixture.installation, "installedProfile").set(fixture.installation, other.child);
            expect(IllegalStateException.class, fixture.child::registerOriginalProfile);
            registrationUnobserved(fixture.child, false);
            registrationUnobserved(other.child, false);
        }
    }

    private static void registrationPolicy() throws Throwable {
        for (String flag : new String[] {"leafPolicyRefused", "ancestorPolicyRefused"}) {
            try (Fixture fixture = new Fixture()) {
                field(fixture.installation, flag).setBoolean(fixture.installation, true);
                expect(IllegalStateException.class, fixture.child::registerOriginalProfile);
                registrationUnobserved(fixture.child, false);
            }
        }
    }

    private static void registrationThread() throws Throwable {
        try (Fixture fixture = new Fixture()) {
            for (boolean virtual : new boolean[] {false, true}) {
                AtomicReference<Throwable> caught = new AtomicReference<>();
                Runnable action = () -> {
                    try { expect(IllegalStateException.class, fixture.child::registerOriginalProfile); }
                    catch (Throwable failure) { caught.set(failure); }
                };
                Thread thread = virtual ? Thread.ofVirtual().start(action) : Thread.ofPlatform().start(action);
                thread.join();
                check(caught.get() == null);
                registrationUnobserved(fixture.child, false);
            }
        }
    }

    private static void registrationFailed() throws Throwable {
        try (Fixture fixture = new Fixture()) {
            field(fixture.bootstrap, "systemModulesAttempted").setBoolean(fixture.bootstrap, true);
            Throwable failed = expect(WindowsInstalledProfileCandidate.Failure.class, fixture.child::prepare);
            Throwable original = ((WindowsInstalledProfileCandidate.Failure) failed).operationFailure;
            check(expect(WindowsInstalledProfileCandidate.Failure.class, fixture.child::registerOriginalProfile) == failed);
            check(((WindowsInstalledProfileCandidate.Failure) failed).operationFailure == original);
            check(((WindowsInstalledProfileCandidate.Failure) failed).retainedCandidate == fixture.child);
            registrationUnobserved(fixture.child, false);
        }
    }

    private static void registrationConsumed() throws Throwable {
        try (Fixture fixture = new Fixture()) {
            // Inert consumed-state model, not a fabricated successful load/registration owner.
            field(fixture.child, "registrationAttempted").setBoolean(fixture.child, true);
            Throwable refusal = expect(IllegalStateException.class, fixture.child::registerOriginalProfile);
            check(refusal.getMessage().equals("Installed profile registration is already consumed"));
            registrationUnobserved(fixture.child, true);
        }
    }

    private static final class Fixture implements AutoCloseable {
        final Object original;
        final WindowsSystemBootstrapCandidate bootstrap;
        final WindowsOriginalInstallationCandidate installation;
        final WindowsInstalledProfileCandidate child;
        Fixture() throws Throwable {
            // Reuse the existing inert original-custody fixture, not a production test-authority hook.
            Class<?> type = Class.forName(OriginalInstallationCandidateTests.class.getName() + "$Fixture");
            Constructor<?> constructor = type.getDeclaredConstructor(); constructor.setAccessible(true);
            original = constructor.newInstance();
            invoke(original, "file"); invoke(original, "security"); invoke(original, "ancestors");
            bootstrap = (WindowsSystemBootstrapCandidate) value(original, "bootstrap");
            installation = (WindowsOriginalInstallationCandidate) value(original, "owner");
            field(installation, "observationCompleted").setBoolean(installation, true);
            Object ancestors = value(original, "ancestors");
            field(ancestors, "allPoliciesAccepted").setBoolean(ancestors, true);
            child = new WindowsInstalledProfileCandidate(installation);
            field(installation, "profilePreparationAttempted").setBoolean(installation, true);
            field(installation, "installedProfile").set(installation, child);
        }
        @Override public void close() {
            try { ((AutoCloseable) original).close(); }
            catch (Exception failure) { throw new AssertionError("Inert fixture cleanup failed", failure); }
        }
    }
}
