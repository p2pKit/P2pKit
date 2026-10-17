package dev.p2pkit.rpc.windows.loader;

import java.io.InputStream;
import java.net.JarURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.LinkOption;
import java.nio.file.Path;
import java.util.Enumeration;
import java.util.jar.JarEntry;
import java.util.jar.JarFile;

/** Fixed trusted-application comparison data, not a caller-created loading or qualification token. */
final class WindowsInstalledParentPin {
    private static final String RESOURCE = "META-INF/p2pkit/windows-profile-parent.properties";
    private final String source;
    private final String tree;
    private final String manifestSha256;
    private final String dllSha256;

    private WindowsInstalledParentPin(String source, String tree, String manifestSha256, String dllSha256) {
        this.source = source; this.tree = tree; this.manifestSha256 = manifestSha256; this.dllSha256 = dllSha256;
    }

    static WindowsInstalledParentPin read(WindowsInstalledProfileCandidate owner) throws Exception {
        if (owner == null) throw new IllegalArgumentException("Missing original installed application owner");
        String root = owner.originalRoot();
        ClassLoader loader = ClassLoader.getSystemClassLoader();
        if (loader == null) throw new IllegalStateException("Missing original application loader");
        Class<?> application = Class.forName("dev.p2pkit.sample.rpc.profile.WindowsProfilePackagedVerifier", false, loader);
        if (application.getClassLoader() != loader || application.getModule().isNamed()) {
            throw new IllegalStateException("Parent pin is outside the original application relationship");
        }
        Enumeration<URL> resources = loader.getResources(RESOURCE);
        if (!resources.hasMoreElements()) throw new IllegalStateException("Missing application parent pin");
        URL resource = resources.nextElement();
        if (resources.hasMoreElements() || !"jar".equals(resource.getProtocol()) || resource.getRef() != null) {
            throw new IllegalStateException("Ambiguous or non-JAR application parent pin");
        }
        JarURLConnection connection = (JarURLConnection) resource.openConnection();
        connection.setUseCaches(false);
        if (!RESOURCE.equals(connection.getEntryName())) throw new IllegalStateException("Another application parent entry");
        URL origin = connection.getJarFileURL();
        if (!"file".equals(origin.getProtocol()) || origin.getQuery() != null || origin.getRef() != null) {
            throw new IllegalStateException("Parent pin has a nonlocal JAR origin");
        }
        Path jar = Path.of(origin.toURI());
        requireOrigin(root, jar.toString());
        if (!jar.isAbsolute() || !jar.equals(jar.normalize()) || !Files.isRegularFile(jar, LinkOption.NOFOLLOW_LINKS)) {
            throw new IllegalStateException("Parent pin JAR is not an ordinary installed file");
        }
        // The exact system-loader resource, fixed original root and unique actual JAR entry are bound.
        // This is not a new whole-JAR custody/signature or previously loaded-byte attestation.
        return readArchive(jar);
    }

    private static WindowsInstalledParentPin readArchive(Path jar) throws Exception {
        try (JarFile archive = new JarFile(jar.toFile(), false)) {
            JarEntry selected = null;
            Enumeration<JarEntry> entries = archive.entries();
            int count = 0;
            while (entries.hasMoreElements()) {
                if (++count > 100_000) throw new IllegalStateException("Parent JAR inventory exceeds its bound");
                JarEntry entry = entries.nextElement();
                if (entry.getName().equals(RESOURCE)) {
                    if (selected != null) throw new IllegalStateException("Duplicate parent pin JAR entry");
                    selected = entry;
                }
            }
            if (selected == null || selected.isDirectory() || selected.getSize() <= 0 || selected.getSize() > 4096) {
                throw new IllegalStateException("Missing or unbounded parent pin JAR entry");
            }
            try (InputStream stream = archive.getInputStream(selected)) {
                byte[] data = stream.readNBytes(4097);
                if (data.length != selected.getSize()) throw new IllegalStateException("Parent pin entry length differs");
                return parse(data);
            }
        }
    }

    private static void requireOrigin(String root, String jar) {
        String prefix = root + "\\app\\";
        if (jar.length() <= prefix.length() || !jar.regionMatches(true, 0, prefix, 0, prefix.length()) ||
            !jar.substring(prefix.length()).matches("p2pkit-windows-profile-parent-pin(?:-[a-f0-9]{16,32})?\\.jar")) {
            throw new IllegalStateException("Application parent pin is outside the fixed original app directory/family");
        }
    }

    private static WindowsInstalledParentPin parse(byte[] data) {
        if (data == null || data.length == 0 || data.length > 4096) throw new IllegalStateException("Unbounded application parent pin");
        for (byte value : data) if (value != 10 && (value < 32 || value > 126)) throw new IllegalStateException("Parent pin is not canonical ASCII");
        String[] lines = new String(data, StandardCharsets.US_ASCII).split("\n", -1);
        String[] keys = {"schema=1", "scope=PACKAGED_COMPONENT_PIN_NOT_LOAD_AUTHORITY", "source=", "tree=", "manifestSha256=", "dllSha256="};
        if (lines.length != 7 || !lines[6].isEmpty() || !lines[0].equals(keys[0]) || !lines[1].equals(keys[1])) {
            throw new IllegalStateException("Application parent pin schema differs");
        }
        String[] values = new String[4];
        for (int index = 2; index < 6; index++) {
            if (!lines[index].startsWith(keys[index])) throw new IllegalStateException("Application parent pin fields differ");
            values[index - 2] = lines[index].substring(keys[index].length());
            if (!values[index - 2].matches(index < 4 ? "[a-f0-9]{40}" : "[a-f0-9]{64}")) throw new IllegalStateException("Application parent pin digest/source differs");
        }
        return new WindowsInstalledParentPin(values[0], values[1], values[2], values[3]);
    }

    String source() { return source; }
    String tree() { return tree; }
    String manifestSha256() { return manifestSha256; }
    String dllSha256() { return dllSha256; }
}
