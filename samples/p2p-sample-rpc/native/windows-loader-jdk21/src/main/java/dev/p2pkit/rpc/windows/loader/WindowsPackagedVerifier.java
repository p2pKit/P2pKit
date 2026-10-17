package dev.p2pkit.rpc.windows.loader;

import java.lang.reflect.Method;
import java.lang.reflect.Modifier;
import java.security.GeneralSecurityException;
import java.security.MessageDigest;
import java.util.Arrays;
import java.util.HashSet;
import java.util.Set;

/**
 * Fixed Java-21 named-module connection to the existing packaged Java-17 byte-verification algorithms.
 * This is data verification only: supplied pins/arrays, class names and successful comparisons grant no
 * startup, package, filesystem, loaded-module or native-call authority. No native function is invoked.
 * The future productive owner must supply independently admitted inputs and retain its original scoped
 * observations separately. The optional original-byte child binds the same comparison to its retained
 * original file/security/ancestors/byte chain; supplied manifest pins still grant no admission. There is
 * no caller-selected class, method, classloader, reflection fallback,
 * forced JNI initialization, module read/export change, or provider activation.
 */
final class WindowsPackagedVerifier {
    private static final String HELPER = "dev.p2pkit.sample.rpc.profile.WindowsProfilePackagedVerifier";
    private static final String DECLARING = "dev.p2pkit.sample.rpc.profile.WindowsProfileCustodyJni";
    private static final String EXPORT_PREFIX = "Java_dev_p2pkit_sample_rpc_profile_WindowsProfileCustodyJni_";
    private static final String REGISTRAR = "pwp_jni_register_once";
    private static final int MAXIMUM_LIBRARY = 32 * 1024 * 1024;
    private static final long MAXIMUM_IMAGE = 128L * 1024 * 1024;
    private static final int MAXIMUM_REGIONS = 40_961; // <=128MiB code/header + <=32MiB page-split IAT.
    private final WindowsOriginalProfileDllBytesCandidate originalBytes;
    private Object originalVerifier;
    private Class<?> helperClass;
    private Class<?> declaringClass;
    private Method regionsMethod;
    private Method verifyMethod;
    private long[] image;
    private String[] exports;
    private long[] rvas;
    private String[] imports;
    private byte[] originalSnapshotSha256;
    private boolean attempted;
    // Publish the once-written data together, including for the legacy unowned comparison API.
    private volatile boolean prepared;

    private WindowsPackagedVerifier(WindowsOriginalProfileDllBytesCandidate originalBytes) {
        this.originalBytes = originalBytes;
    }

    static WindowsPackagedVerifier forOriginalBytes(WindowsOriginalProfileDllBytesCandidate originalBytes) {
        if (originalBytes == null) throw new IllegalArgumentException("Original DLL byte owner is required");
        return new WindowsPackagedVerifier(originalBytes);
    }

    void prepareOriginalBytes(byte[] comparisonManifest, String comparisonManifestSha256,
        String comparisonSource, String comparisonTree) throws ReflectiveOperationException {
        if (originalBytes == null) throw new IllegalStateException("Unowned byte comparison cannot acquire an owner");
        originalBytes.requireOriginalPackagedVerifier(this);
        if (attempted) throw new IllegalStateException("Original DLL packaged comparison was already prepared");
        attempted = true;
        // Only the original completed byte core supplies the DLL and digest. The clone hashed here is
        // the exact private input to the existing bridge, never a caller DLL array or a reopened path.
        byte[] snapshot = originalBytes.snapshot();
        originalSnapshotSha256 = originalBytes.sha256();
        MessageDigest digest;
        try { digest = MessageDigest.getInstance("SHA-256", "SUN"); }
        catch (GeneralSecurityException caught) {
            throw new IllegalStateException("Original DLL snapshot digest provider is unavailable", caught);
        }
        require(digest.getProvider().getClass().getModule() == Object.class.getModule() &&
            digest.getProvider().getClass().getClassLoader() == null &&
            digest.getProvider().getClass().getName().equals("sun.security.provider.Sun") && digest.getDigestLength() == 32,
            "Original DLL snapshot digest provider differs");
        require(originalSnapshotSha256.length == 32 &&
            MessageDigest.isEqual(digest.digest(snapshot), originalSnapshotSha256),
            "Original DLL snapshot differs from its completed original digest");
        prepareData(comparisonManifest, snapshot, comparisonManifestSha256, comparisonSource, comparisonTree);
        originalBytes.requireOriginalPackagedVerifier(this);
        prepared = true;
    }

    static WindowsPackagedVerifier prepare(byte[] manifest, byte[] library, String manifestSha256,
                                           String source, String tree) throws ReflectiveOperationException {
        WindowsPackagedVerifier verifier = new WindowsPackagedVerifier(null);
        verifier.attempted = true;
        verifier.prepareData(manifest, library, manifestSha256, source, tree);
        verifier.prepared = true;
        return verifier;
    }

    private void prepareData(byte[] manifest, byte[] library, String manifestSha256,
        String source, String tree) throws ReflectiveOperationException {
        WindowsLoaderRuntime.requireDiagnosticRuntime();
        require(WindowsPackagedVerifier.class.getModule() == WindowsLoaderRuntime.class.getModule(),
            "Packaged verifier must remain in the original named module");
        require(manifest != null && manifest.length >= 1 && manifest.length <= 4096 && library != null &&
            library.length >= 512 && library.length <= MAXIMUM_LIBRARY && hexadecimal(manifestSha256, 64) &&
            hexadecimal(source, 40) && hexadecimal(tree, 40), "Invalid bounded packaged verifier data");
        byte[] manifestSnapshot = manifest.clone();
        // The owned path has already made and hashed this private clone; preserve that exact input.
        byte[] librarySnapshot = originalBytes == null ? library.clone() : library;
        ClassLoader system = ClassLoader.getSystemClassLoader();
        require(system != null, "Packaged verifier requires the maintained system classloader");
        Class<?> helper = Class.forName(HELPER, false, system);
        Class<?> declaration = Class.forName(DECLARING, false, system);
        require(helper.getClassLoader() == system && declaration.getClassLoader() == system &&
            !helper.getModule().isNamed() && !declaration.getModule().isNamed() &&
            helper.getName().equals(HELPER) && declaration.getName().equals(DECLARING) &&
            Modifier.isPublic(helper.getModifiers()) && Modifier.isFinal(helper.getModifiers()) &&
            Modifier.isPublic(declaration.getModifiers()) && Modifier.isFinal(declaration.getModifiers()),
            "Packaged verifier classes differ from the maintained application relationship");
        Method factory = fixed(helper, "create", helper, true,
            byte[].class, byte[].class, String.class, String.class, String.class);
        Method declarationMethod = fixed(helper, "declaringClass", Class.class, false);
        Method imageMethod = fixed(helper, "imageLayout", long[].class, false);
        Method exportMethod = fixed(helper, "exportNames", String[].class, false);
        Method rvasMethod = fixed(helper, "exportRvas", long[].class, false);
        Method importMethod = fixed(helper, "importNames", String[].class, false);
        Method regionsMethod = fixed(helper, "regions", long[].class, false, long.class);
        Method verifyMethod = fixed(helper, "verify", long[].class, false,
            long.class, long[].class, long[].class, byte[][].class);
        Object delegate = factory.invoke(null, manifestSnapshot, librarySnapshot, manifestSha256, source, tree);
        require(delegate != null && delegate.getClass() == helper, "Packaged verifier returned another plan class");
        require(declarationMethod.invoke(delegate) == declaration, "Packaged verifier changed the original JNI class");
        long[] image = longs(imageMethod.invoke(delegate), 3, 3);
        require(image[0] >= 4096 && image[0] <= MAXIMUM_IMAGE && image[0] % 4096 == 0 &&
            image[1] > 0 && image[1] < image[0] && image[2] >= 40 && image[2] <= image[0] - image[1],
            "Packaged verifier returned invalid original export/image bounds");
        String[] exports = strings(exportMethod.invoke(delegate), 24, 24);
        long[] rvas = longs(rvasMethod.invoke(delegate), 24, 24);
        Set<String> expectedNames = new HashSet<>();
        for (Method method : declaration.getDeclaredMethods()) {
            require(method.getModifiers() == (Modifier.PUBLIC | Modifier.FINAL | Modifier.NATIVE) &&
                !method.isBridge() && !method.isSynthetic(), "Packaged JNI declaration has an unexpected method");
            require(expectedNames.add(EXPORT_PREFIX + method.getName()), "Packaged JNI method name is duplicated");
        }
        require(expectedNames.size() == 23 && expectedNames.add(REGISTRAR), "Packaged JNI method inventory differs");
        for (int index = 0; index < exports.length; index++) {
            require(asciiName(exports[index], 255) && expectedNames.remove(exports[index]) && rvas[index] > 0 &&
                rvas[index] < image[0] && !(rvas[index] >= image[1] && rvas[index] < image[1] + image[2]),
                "Packaged verifier returned a malformed or forwarded export plan");
        }
        require(expectedNames.isEmpty(), "Packaged verifier export inventory is incomplete");
        String[] imports = strings(importMethod.invoke(delegate), 2, 8192);
        require(imports.length % 2 == 0, "Packaged verifier import tuple inventory differs");
        Set<String> tuples = new HashSet<>();
        Set<String> libraries = Set.of("kernel32.dll", "advapi32.dll", "ntdll.dll", "shell32.dll", "ole32.dll");
        for (int index = 0; index < imports.length; index += 2) {
            require(imports[index] != null && libraries.contains(imports[index]) && asciiName(imports[index + 1], 128) &&
                tuples.add(imports[index] + "/" + imports[index + 1]), "Packaged verifier returned an invalid import tuple");
        }
        originalVerifier = delegate;
        helperClass = helper;
        declaringClass = declaration;
        this.regionsMethod = regionsMethod;
        this.verifyMethod = verifyMethod;
        this.image = image;
        this.exports = exports;
        this.rvas = rvas;
        this.imports = imports;
    }

    private void requirePrepared() {
        if (originalBytes != null) originalBytes.requireOriginalPackagedVerifier(this);
        if (!prepared) throw new IllegalStateException("Packaged verifier comparison is incomplete");
    }

    Class<?> declaringClass() { requirePrepared(); return declaringClass; }
    long[] imageLayout() {
        requirePrepared();
        try { return image.clone(); }
        catch (Throwable caught) {
            if (originalBytes != null) throw originalBytes.failOriginalPackagedVerifier(this, caught);
            throw caught;
        }
    }
    String[] exportNames() {
        requirePrepared();
        try { return exports.clone(); }
        catch (Throwable caught) {
            if (originalBytes != null) throw originalBytes.failOriginalPackagedVerifier(this, caught);
            throw caught;
        }
    }
    long[] exportRvas() {
        requirePrepared();
        try { return rvas.clone(); }
        catch (Throwable caught) {
            if (originalBytes != null) throw originalBytes.failOriginalPackagedVerifier(this, caught);
            throw caught;
        }
    }
    String[] importNames() {
        requirePrepared();
        try { return imports.clone(); }
        catch (Throwable caught) {
            if (originalBytes != null) throw originalBytes.failOriginalPackagedVerifier(this, caught);
            throw caught;
        }
    }

    long[] regions(long moduleBase) throws ReflectiveOperationException {
        requirePrepared();
        try { return compareRegions(moduleBase); }
        catch (Throwable caught) {
            if (originalBytes != null) throw originalBytes.failOriginalPackagedVerifier(this, caught);
            throw caught;
        }
    }

    private long[] compareRegions(long moduleBase) throws ReflectiveOperationException {
        requireMapping(moduleBase);
        require(originalVerifier.getClass() == helperClass, "Original packaged verifier plan was replaced");
        long[] ranges = longs(regionsMethod.invoke(originalVerifier, moduleBase), 9, MAXIMUM_REGIONS * 3);
        require(ranges.length % 3 == 0, "Packaged verifier returned a partial readback tuple");
        long[][] intervals = new long[ranges.length / 3][2];
        boolean header = false;
        boolean executable = false;
        boolean data = false;
        for (int index = 0; index < intervals.length; index++) {
            long address = ranges[index * 3];
            long bytes = ranges[index * 3 + 1];
            long kind = ranges[index * 3 + 2];
            require(address >= moduleBase && address < moduleBase + image[0] && bytes >= 1 && bytes <= 4096 &&
                bytes <= moduleBase + image[0] - address && address % 4096 + bytes <= 4096 && kind >= 0 && kind <= 2,
                "Packaged verifier readback range exceeds the original image or page bound");
            require(kind == 2 || (address % 4096 == 0 && bytes == 4096),
                "Packaged verifier code/header page is incomplete");
            if (kind == 0) header = true;
            if (kind == 1) executable = true;
            if (kind == 2) data = true;
            intervals[index][0] = address;
            intervals[index][1] = address + bytes;
        }
        require(header && executable && data && ranges[0] == moduleBase && ranges[2] == 0,
            "Packaged verifier omitted required header, executable or IAT readbacks");
        Arrays.sort(intervals, (left, right) -> Long.compare(left[0], right[0]));
        for (int index = 1; index < intervals.length; index++) {
            require(intervals[index - 1][1] <= intervals[index][0], "Packaged verifier readback ranges overlap");
        }
        return ranges;
    }

    long[] verify(long moduleBase, long[] exportTargets, long[] importTargets, byte[][] pages)
        throws ReflectiveOperationException {
        requirePrepared();
        try { return compareImage(moduleBase, exportTargets, importTargets, pages); }
        catch (Throwable caught) {
            if (originalBytes != null) throw originalBytes.failOriginalPackagedVerifier(this, caught);
            throw caught;
        }
    }

    private long[] compareImage(long moduleBase, long[] exportTargets, long[] importTargets, byte[][] pages)
        throws ReflectiveOperationException {
        long[] requested = compareRegions(moduleBase);
        require(exportTargets != null && exportTargets.length == 24 && importTargets != null &&
            importTargets.length == imports.length / 2 && pages != null && pages.length == requested.length / 3,
            "Packaged verifier observations have an invalid cardinality");
        long[] exportSnapshot = exportTargets.clone();
        long[] importSnapshot = importTargets.clone();
        byte[][] references = pages.clone();
        byte[][] snapshots = new byte[references.length][];
        for (int index = 0; index < snapshots.length; index++) {
            require(references[index] != null && references[index].length == requested[index * 3 + 1],
                "Packaged verifier observation has an invalid page length");
            snapshots[index] = references[index].clone();
        }
        for (int index = 0; index < exportSnapshot.length; index++) {
            require(exportSnapshot[index] == moduleBase + rvas[index], "Packaged verifier export address differs");
        }
        for (long target : importSnapshot) {
            require(target > 0 && !(target >= moduleBase && target < moduleBase + image[0]),
                "Packaged verifier import address is invalid or inside the candidate");
        }
        long[] result = longs(verifyMethod.invoke(originalVerifier, moduleBase, exportSnapshot, importSnapshot, snapshots), 24, 24);
        // Kotlin checks the exact JNI descriptors/order. Bind the returned addresses again to that same
        // fixed declaring class's required order, not merely membership in the original module range.
        String[] methods = {"abi", "capabilities", "openRoot", "child", "createChildDirectory", "identity",
            "fileIdentity", "exists", "names", "read", "lockExisting", "createProfileLock", "createVaultLock",
            "stageRecord", "prepareRecord", "writeRecord", "renameCandidate", "replaceCandidate", "syncDirectory",
            "discardStage", "requestExpectedFileDeletion", "deleteRecord", "close"};
        for (int index = 0; index < result.length; index++) {
            String name = index == 23 ? REGISTRAR : EXPORT_PREFIX + methods[index];
            int found = -1;
            for (int slot = 0; slot < exports.length; slot++) if (exports[slot].equals(name)) found = slot;
            require(found >= 0 && result[index] == exportSnapshot[found], "Packaged verifier JNI result order differs");
        }
        return result;
    }

    private void requireMapping(long moduleBase) {
        require(moduleBase > 0 && moduleBase % 65_536 == 0 && moduleBase <= Long.MAX_VALUE - image[0],
            "Packaged verifier requires a bounded original image mapping");
    }
    private static Method fixed(Class<?> owner, String name, Class<?> result, boolean isStatic, Class<?>... arguments)
        throws ReflectiveOperationException {
        Method method = owner.getDeclaredMethod(name, arguments);
        require(method.getDeclaringClass() == owner && method.getReturnType() == result &&
            Modifier.isPublic(method.getModifiers()) && Modifier.isStatic(method.getModifiers()) == isStatic &&
            !method.isBridge() && !method.isSynthetic(), "Packaged verifier fixed method signature differs");
        return method; // Public reflection only: no setAccessible, fallback lookup, read edges or JDK internals.
    }
    private static long[] longs(Object returned, int minimum, int maximum) {
        require(returned instanceof long[], "Packaged verifier returned another primitive array type");
        long[] value = (long[]) returned;
        require(value.length >= minimum && value.length <= maximum, "Packaged verifier primitive array exceeds its bound");
        return value.clone();
    }
    private static String[] strings(Object returned, int minimum, int maximum) {
        require(returned != null && returned.getClass() == String[].class, "Packaged verifier returned another string array type");
        String[] value = (String[]) returned;
        require(value.length >= minimum && value.length <= maximum, "Packaged verifier string array exceeds its bound");
        return value.clone();
    }
    private static boolean hexadecimal(String value, int count) {
        return value != null && value.length() == count && value.matches("[0-9a-f]+");
    }
    private static boolean asciiName(String value, int maximum) {
        return value != null && value.length() >= 1 && value.length() <= maximum && value.matches("[A-Za-z_][A-Za-z0-9_]*");
    }
    private static void require(boolean condition, String message) {
        if (!condition) throw new IllegalArgumentException(message);
    }
}
