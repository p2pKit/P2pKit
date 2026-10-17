package dev.p2pkit.rpc.windows.loader;

import java.lang.foreign.Arena;
import java.lang.foreign.MemorySegment;
import java.nio.charset.StandardCharsets;
import java.nio.file.Path;
import java.security.MessageDigest;
import java.util.Arrays;
import java.util.HashSet;
import java.util.HexFormat;
import java.util.Set;

import static dev.p2pkit.rpc.windows.loader.OriginalFileBytesLeaseTests.expect;
import static dev.p2pkit.rpc.windows.loader.OriginalFileBytesLeaseTests.value;

/**
 * Positive development fixture: real original file/security/ancestors/bytes to the packaged PE verifier.
 * The separately supervised fixture creates its own protected directory and pins its compiler output.
 * This test changes no ACL and never opens another byte channel, loads the DLL, registers JNI or calls
 * the profile backend. The fixed comparison manifest describes ABI13/0x43 bytes, not observed execution
 * of those exports or production installation/bootstrap authority. Existing policies must all accept;
 * an ordinary refusal is a failed positive test, never a skipped or qualified execution.
 */
public final class ProtectedProfileDllSnapshotTests {
    private static final String EXPORT_PREFIX = "Java_dev_p2pkit_sample_rpc_profile_WindowsProfileCustodyJni_";
    private static final String[] METHODS = {
        "abi", "capabilities", "openRoot", "child", "createChildDirectory", "identity", "fileIdentity",
        "exists", "names", "read", "lockExisting", "createProfileLock", "createVaultLock", "stageRecord",
        "prepareRecord", "writeRecord", "renameCandidate", "replaceCandidate", "syncDirectory", "discardStage",
        "requestExpectedFileDeletion", "deleteRecord", "close"
    };
    private static WindowsSystemBootstrapCandidate bootstrap;
    private static WindowsOriginalProfileDllFileCandidate file;
    private static WindowsOriginalProfileDllSecurityCandidate security;
    private static WindowsOriginalProfileDllAncestorsCandidate ancestors;
    private static WindowsOriginalProfileDllBytesCandidate bytes;
    private static WindowsPackagedVerifier packaged;

    private ProtectedProfileDllSnapshotTests() {}

    public static void main(String[] arguments) throws Throwable {
        // All argument syntax, numeric bounds and actual application-class bindings precede bootstrap.
        check(arguments.length == 8 && bootstrap == null);
        String dll = arguments[0];
        WindowsProfileDllPath.require(dll);
        check(hexadecimal(arguments[1], 40) && hexadecimal(arguments[2], 40));
        check(arguments[3].length() <= 8 && arguments[3].matches("[1-9][0-9]*"));
        long compiledBytes = Long.parseLong(arguments[3]);
        check(compiledBytes >= 512 && compiledBytes <= 32L * 1024 * 1024);
        check(hexadecimal(arguments[4], 64) && hexadecimal(arguments[6], 64) && hexadecimal(arguments[7], 64));
        check(arguments[5] != null && !arguments[5].isEmpty() && arguments[5].length() <= 4096);
        Path main = Path.of(arguments[5]);
        check(main.isAbsolute() && main.equals(main.normalize()));
        main = main.toRealPath();
        Path locator = Path.of(dll);
        check(locator.isAbsolute() && locator.equals(locator.normalize())); // Syntax only, no candidate I/O.
        WindowsLoaderRuntime.requireDiagnosticRuntime();
        Class<?> helper = PackagedVerifierTests.actualClass("WindowsProfilePackagedVerifier", main, arguments[6]);
        Class<?> declaration = PackagedVerifierTests.actualClass("WindowsProfileCustodyJni", main, arguments[7]);
        byte[] manifest = manifest(arguments[1], arguments[2], compiledBytes, arguments[4]);
        String manifestHash = HexFormat.of().formatHex(digest(manifest));
        byte[] compilerHash = HexFormat.of().parseHex(arguments[4]);
        loaderRefuses();

        bootstrap = WindowsSystemBootstrapCandidate.inspect();
        check(bootstrap.completed());
        file = bootstrap.inspectOriginalProfileDll(dll);
        check(file.completed() && file.leaseHeld());
        Object lease = value(file, "lease");
        MemorySegment handle = (MemorySegment) value(lease, "handle");
        Arena handleArena = (Arena) value(lease, "handleArena");
        security = file.inspectSecurity();
        check(security.completed() && security.descriptorPolicyAccepted());
        ancestors = security.inspectAncestors();
        check(ancestors.completed() && ancestors.descriptorPoliciesAccepted());
        check(ancestors.ancestorCount() >= 1 && ancestors.ancestorCount() <= 63);
        bytes = file.inspectBytes();
        check(bytes.completed() && bytes.byteCount() == compiledBytes);
        check(MessageDigest.isEqual(bytes.sha256(), compilerHash));
        byte[] snapshot = bytes.snapshot(); // Only the already completed original HANDLE supplies DLL bytes.
        check(snapshot.length == compiledBytes && MessageDigest.isEqual(digest(snapshot), compilerHash));
        // Dispose this defensive test copy before the owned bridge makes its independently checked copy.
        Arrays.fill(snapshot, (byte) 0);
        snapshot = null;
        check(MessageDigest.isEqual(bytes.sha256(), compilerHash));
        packaged = bytes.inspectPackagedBytes(manifest, manifestHash, arguments[1], arguments[2]);
        check(value(bytes, "packaged") == packaged && value(packaged, "originalBytes") == bytes);
        check(value(packaged, "originalVerifier").getClass() == helper && packaged.declaringClass() == declaration);
        check(MessageDigest.isEqual((byte[]) value(packaged, "originalSnapshotSha256"), compilerHash));
        checkImagePlan(packaged);
        continuity(lease, handle, handleArena);
        expect(IllegalStateException.class, file::inspectBytes);
        expect(IllegalStateException.class,
            () -> bytes.inspectPackagedBytes(manifest, manifestHash, arguments[1], arguments[2]));
        loaderRefuses();
        continuity(lease, handle, handleArena);
        System.out.println("WINDOWS_PROTECTED_DLL_SNAPSHOT_PASS " +
            "scope=DEVELOPMENT_PROTECTED_FILE_AND_PE_NOT_STANDARD_USER_INSTALLATION_OR_DLL_LOAD");
    }

    private static byte[] manifest(String source, String tree, long count, String sha256) {
        // Exact current producer order: twelve fields, no inferred DLL digest or candidate sidecar.
        String contents = "schema=1\ncomponent=windows-profile-custody\nabi=13\nplatform=windows\narch=x86_64\n" +
            "source=" + source + "\ntree=" + tree + "\nclean=true\nfile=p2pkit-windows-profile.dll\n" +
            "bytes=" + count + "\nsha256=" + sha256 + "\ncapabilities=0x43\n";
        check(contents.length() <= 4096 && contents.lines().count() == 12);
        return contents.getBytes(StandardCharsets.US_ASCII);
    }

    private static void checkImagePlan(WindowsPackagedVerifier plan) {
        long[] image = plan.imageLayout();
        check(image.length == 3 && image[0] >= 4096 && image[0] <= 128L * 1024 * 1024 && image[0] % 4096 == 0);
        check(image[1] > 0 && image[1] < image[0] && image[2] >= 40 && image[2] <= image[0] - image[1]);
        String[] names = plan.exportNames();
        long[] rvas = plan.exportRvas();
        check(names.length == 24 && rvas.length == 24);
        Set<String> expected = new HashSet<>();
        for (String name : METHODS) check(expected.add(EXPORT_PREFIX + name));
        check(expected.size() == 23 && expected.add("pwp_jni_register_once"));
        for (int index = 0; index < names.length; index++) {
            check(expected.remove(names[index]) && rvas[index] > 0 && rvas[index] < image[0]);
            check(rvas[index] < image[1] || rvas[index] >= image[1] + image[2]);
        }
        check(expected.isEmpty());
        String[] imports = plan.importNames();
        check(imports.length >= 2 && imports.length <= 8192 && imports.length % 2 == 0);
        // No synthetic loaded base/targets/readback and no verify(mapping) call: this is file/PE inspection.
    }

    private static void continuity(Object lease, MemorySegment handle, Arena handleArena) throws Exception {
        check(file.completed() && file.leaseHeld() && security.completed() && security.descriptorPolicyAccepted());
        check(ancestors.completed() && ancestors.descriptorPoliciesAccepted() && bytes.completed());
        check(value(bootstrap, "profileDll") == file && value(bootstrap, "originalJvm") == null);
        check(!(boolean) value(bootstrap, "originalJvmAttempted"));
        check(value(lease, "handle") == handle && handleArena.scope().isAlive());
        Object core = value(bytes, "core");
        check(value(core, "originalProfileDllOwner") == bytes && value(core, "originalJvmOwner") == null);
        check(value(core, "fileHandle") == handle && value(core, "fileArena") == handleArena);
        check(value(core, "bootstrapArena") == value(bootstrap, "originalArena"));
        check((boolean) value(core, "frameRetired") && !(boolean) value(core, "nativeReturnUnconfirmed") &&
            !(boolean) value(core, "readCompletionUnconfirmed"));
        check(!((Arena) value(core, "frameArena")).scope().isAlive());
        Object ancestorCore = value(ancestors, "core");
        check(value(ancestorCore, "originalFileHandle") == handle && value(ancestorCore, "originalFileArena") == handleArena);
        check(((Arena) value(ancestorCore, "leaseArena")).scope().isAlive());
        check((boolean) value(ancestorCore, "frameRetired") && !(boolean) value(ancestorCore, "nativeReturnUnconfirmed") &&
            !(boolean) value(ancestorCore, "ntCompletionUnconfirmed"));
        check(!((Arena) value(ancestorCore, "frameArena")).scope().isAlive());
        check(value(file, "security") == security && value(security, "ancestors") == ancestors);
        check(value(file, "bytes") == bytes && value(bytes, "file") == file);
    }

    private static void loaderRefuses() throws Throwable {
        Throwable refusal = expect(WindowsLoader.Unavailable.class, WindowsLoader::openInstalledProvider);
        check(WindowsLoader.REFUSAL.equals(refusal.getMessage()));
    }

    private static byte[] digest(byte[] data) throws Exception {
        return MessageDigest.getInstance("SHA-256", "SUN").digest(data);
    }

    private static boolean hexadecimal(String text, int count) {
        return text != null && text.length() == count && text.matches("[0-9a-f]+");
    }

    private static void check(boolean condition) {
        if (!condition) throw new AssertionError("Protected DLL snapshot control failed");
    }
}
