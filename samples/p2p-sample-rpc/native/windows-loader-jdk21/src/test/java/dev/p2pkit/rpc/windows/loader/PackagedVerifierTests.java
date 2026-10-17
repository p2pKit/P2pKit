package dev.p2pkit.rpc.windows.loader;

import java.io.InputStream;
import java.lang.reflect.InvocationTargetException;
import java.lang.reflect.Modifier;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.nio.file.Files;
import java.nio.file.Path;
import java.security.MessageDigest;
import java.util.Arrays;
import java.util.HexFormat;

/** Real named-module/application-classloader connection, using inert PE bytes only. No OS/native calls. */
public final class PackagedVerifierTests {
    private static final String PROFILE = "dev.p2pkit.sample.rpc.profile.";
    private static final String PREFIX = "Java_dev_p2pkit_sample_rpc_profile_WindowsProfileCustodyJni_";
    private static final String[] METHODS = {
        "abi", "capabilities", "openRoot", "child", "createChildDirectory", "identity", "fileIdentity",
        "exists", "names", "read", "lockExisting", "createProfileLock", "createVaultLock", "stageRecord",
        "prepareRecord", "writeRecord", "renameCandidate", "replaceCandidate", "syncDirectory", "discardStage",
        "requestExpectedFileDeletion", "deleteRecord", "close"
    };
    private static final long BASE = 0x0000000180000000L;
    private static final long IMPORT = 0x0000000070000000L;

    private PackagedVerifierTests() {}

    public static void main(String[] arguments) throws Exception {
        check(arguments.length == 4);
        String mode = arguments[0];
        check(Arrays.asList("success", "missing-helper", "invalid-pin", "manifest-pin", "header-byte",
            "code-byte", "iat-byte", "export-address", "page-count").contains(mode));
        WindowsLoaderRuntime.requireDiagnosticRuntime();
        check(PackagedVerifierTests.class.getModule().isNamed());
        if (mode.equals("missing-helper")) {
            expect(ClassNotFoundException.class, () -> WindowsPackagedVerifier.prepare(new byte[1], new byte[512],
                "0".repeat(64), "a".repeat(40), "b".repeat(40)));
        } else {
            ClassLoader system = ClassLoader.getSystemClassLoader();
            Path main = Path.of(arguments[1]).toRealPath();
            Class<?> helper = actualClass("WindowsProfilePackagedVerifier", main, arguments[2]);
            Class<?> declaration = actualClass("WindowsProfileCustodyJni", main, arguments[3]);
            check(helper.getClassLoader() == system && declaration.getClassLoader() == system);
            Class<?> fixture = Class.forName(PROFILE + "WindowsProfilePackagedConnectionFixture", true, system);
            check(fixture.getClassLoader() == system && !fixture.getModule().isNamed());
            Object raw = fixture.getDeclaredMethod("data").invoke(null);
            check(raw instanceof Object[] && ((Object[]) raw).length == 5);
            Object[] data = (Object[]) raw;
            byte[] manifest = (byte[]) data[0];
            byte[] library = (byte[]) data[1];
            String digest = (String) data[2];
            String source = (String) data[3];
            String tree = (String) data[4];
            check(library.length == 0x1200 && source.equals("a".repeat(40)) && tree.equals("b".repeat(40)));
            if (mode.equals("invalid-pin")) {
                expect(IllegalArgumentException.class, () -> WindowsPackagedVerifier.prepare(
                    manifest, library, "invalid", source, tree));
            } else if (mode.equals("manifest-pin")) {
                expect(IllegalArgumentException.class, () -> WindowsPackagedVerifier.prepare(
                    manifest, library, "0".repeat(64), source, tree));
            } else {
                byte[][] pages = pages(library);
                WindowsPackagedVerifier plan = WindowsPackagedVerifier.prepare(manifest, library, digest, source, tree);
                check(plan.declaringClass() == declaration);
                check(declaration.getDeclaredMethods().length == 23);
                for (var method : declaration.getDeclaredMethods()) {
                    check(method.getModifiers() == (Modifier.PUBLIC | Modifier.FINAL | Modifier.NATIVE));
                }
                check(Arrays.equals(plan.imageLayout(), new long[] {0x4000, 0x2000, 0x800}));
                String[] names = new String[24];
                for (int index = 0; index < METHODS.length; index++) names[index] = PREFIX + METHODS[index];
                names[23] = "pwp_jni_register_once";
                Arrays.sort(names);
                check(Arrays.equals(plan.exportNames(), names));
                long[] rvas = new long[24];
                long[] targets = new long[24];
                for (int index = 0; index < rvas.length; index++) {
                    rvas[index] = 0x1000L + index;
                    targets[index] = BASE + rvas[index];
                }
                check(Arrays.equals(plan.exportRvas(), rvas));
                check(Arrays.equals(plan.importNames(), new String[] {"kernel32.dll", "CloseHandle"}));
                check(Arrays.equals(plan.regions(BASE), new long[] {
                    BASE, 4096, 0, BASE + 0x1000, 4096, 1, BASE + 0x2880, 16, 2
                }));
                long[] imports = {IMPORT};
                switch (mode) {
                    case "success" -> {
                        // Inputs and returned metadata cannot change the retained private byte plan.
                        Arrays.fill(manifest, (byte) 0);
                        Arrays.fill(library, (byte) 0);
                        plan.imageLayout()[0] = 1;
                        plan.exportNames()[0] = "wrong";
                        plan.exportRvas()[0] = 1;
                        plan.importNames()[0] = "wrong";
                        plan.regions(BASE)[0] = 1;
                        long[] expected = new long[24];
                        for (int index = 0; index < expected.length; index++) {
                            String name = index == 23 ? "pwp_jni_register_once" : PREFIX + METHODS[index];
                            expected[index] = BASE + 0x1000 + Arrays.binarySearch(names, name);
                        }
                        long[] result = plan.verify(BASE, targets, imports, pages);
                        check(Arrays.equals(result, expected));
                        result[0] = 0;
                        check(Arrays.equals(plan.verify(BASE, targets, imports, pages), expected));
                    }
                    case "header-byte", "code-byte", "iat-byte" -> {
                        int index = mode.equals("header-byte") ? 0 : mode.equals("code-byte") ? 1 : 2;
                        pages[index][0] ^= 1;
                        expect(IllegalArgumentException.class, () -> plan.verify(BASE, targets, imports, pages));
                    }
                    case "export-address" -> {
                        targets[0]++;
                        expect(IllegalArgumentException.class, () -> plan.verify(BASE, targets, imports, pages));
                    }
                    case "page-count" -> expect(IllegalArgumentException.class,
                        () -> plan.verify(BASE, targets, imports, new byte[][] {pages[0], pages[1]}));
                    default -> throw new AssertionError("Unhandled packaged verifier control");
                }
            }
        }
        try {
            WindowsLoader.openInstalledProvider();
            throw new AssertionError("Byte verification enabled native loading");
        } catch (UnsupportedOperationException expected) {
            check(WindowsLoader.REFUSAL.equals(expected.getMessage()));
        }
        System.out.println("WINDOWS_PACKAGED_VERIFIER_PASS case=" + mode +
            " scope=REAL_JDK21_TO_JDK17_BYTE_COMPARISON_NOT_LOAD_OR_AUTHORITY");
    }

    private static byte[][] pages(byte[] library) {
        byte[][] result = {new byte[4096], new byte[4096], new byte[16]};
        System.arraycopy(library, 0, result[0], 0, 0x400);
        System.arraycopy(library, 0x400, result[1], 0, 0x200);
        System.arraycopy(library, 0xe80, result[2], 0, 16);
        ByteBuffer.wrap(result[2]).order(ByteOrder.LITTLE_ENDIAN).putLong(IMPORT);
        return result; // Independent fixture geometry; no production parser generates its own expected readbacks.
    }

    static Class<?> actualClass(String simple, Path main, String expectedHash) throws Exception {
        return actualApplicationClass(PROFILE + simple, main, expectedHash);
    }

    static Class<?> actualApplicationClass(String name, Path main, String expectedHash) throws Exception {
        String resource = name.replace('.', '/') + ".class";
        Class<?> actual = Class.forName(name, false, ClassLoader.getSystemClassLoader());
        check(actual.getClassLoader() == ClassLoader.getSystemClassLoader() && !actual.getModule().isNamed());
        check(Path.of(actual.getProtectionDomain().getCodeSource().getLocation().toURI()).toRealPath().equals(main));
        byte[] produced;
        try (InputStream input = Files.newInputStream(main.resolve(resource))) {
            produced = input.readNBytes(1024 * 1024 + 1);
        }
        check(produced.length >= 8 && produced.length <= 1024 * 1024);
        check(ByteBuffer.wrap(produced).order(ByteOrder.BIG_ENDIAN).getInt() == 0xcafebabe);
        check(produced[4] == 0 && produced[5] == 0 && produced[6] == 0 && produced[7] == 61);
        try (InputStream input = actual.getResourceAsStream("/" + resource)) {
            check(input != null);
            byte[] resolved = input.readNBytes(1024 * 1024 + 1);
            check(Arrays.equals(resolved, produced));
        }
        check(HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(produced)).equals(expectedHash));
        return actual;
    }

    private interface Action { void run() throws Exception; }
    private static void expect(Class<? extends Throwable> wanted, Action action) throws Exception {
        try { action.run(); }
        catch (Exception caught) {
            Throwable failure = caught;
            while (failure instanceof InvocationTargetException invocation) failure = invocation.getCause();
            if (wanted.isInstance(failure)) return;
            throw new AssertionError("Unexpected packaged verifier failure", failure);
        }
        throw new AssertionError("Expected packaged verifier refusal");
    }
    private static void check(boolean condition) {
        if (!condition) throw new AssertionError("Packaged verifier control failed");
    }
}
