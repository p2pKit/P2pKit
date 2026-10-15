package dev.p2pkit.build;

import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardCopyOption;
import java.time.LocalDateTime;
import java.util.Arrays;
import java.util.HashSet;
import java.util.Map;
import java.util.Set;
import java.util.TreeMap;
import java.util.zip.ZipEntry;
import java.util.zip.ZipInputStream;
import java.util.zip.ZipOutputStream;

/** Restores the owned producer after AGP splits local JAR classes/resources. */
public final class EmbeddedJmdnsAar {
    private static final String PREFIX = "dev/p2pkit/transport/lan/internal/jmdns/";
    private static final String NOTICES = "META-INF/p2pkit/third-party/jmdns/";
    private static final String EMBEDDED = "libs/p2pkit-internal-jmdns.jar";
    private static final LocalDateTime ZIP_TIME = LocalDateTime.of(1980, 1, 1, 0, 0);

    private EmbeddedJmdnsAar() { }

    public static void restore(Path inputAar, Path producerJar, Path outputAar) throws IOException {
        require(!inputAar.toAbsolutePath().normalize().equals(outputAar.toAbsolutePath().normalize()) &&
                !producerJar.toAbsolutePath().normalize().equals(outputAar.toAbsolutePath().normalize()),
                "output must not overwrite an input");
        byte[] producerBytes = Files.readAllBytes(producerJar);
        Map<String, byte[]> producer = readZip(producerBytes);
        Map<String, byte[]> aar = readZip(Files.readAllBytes(inputAar));
        require(aar.containsKey(EMBEDDED) && aar.containsKey("classes.jar"), "missing AAR runtime JAR");

        Map<String, byte[]> local = readZip(aar.get(EMBEDDED));
        Set<String> expectedClasses = new HashSet<>();
        for (Map.Entry<String, byte[]> entry : producer.entrySet()) {
            if (entry.getKey().endsWith(".class")) {
                require(entry.getKey().startsWith(PREFIX), "producer has an unrelated class");
                expectedClasses.add(entry.getKey());
                require(Arrays.equals(entry.getValue(), local.get(entry.getKey())), "changed or missing private class");
            }
        }
        require(!expectedClasses.isEmpty(), "producer has no classes");
        for (Map.Entry<String, byte[]> entry : local.entrySet()) {
            // AGP normally retains only classes. Also admit a previously restored
            // exact resource, but never hide an unexpected input by replacing it.
            require(Arrays.equals(entry.getValue(), producer.get(entry.getKey())), "unexpected private JAR entry");
        }

        Map<String, byte[]> module = readZip(aar.get("classes.jar"));
        for (Map.Entry<String, byte[]> entry : producer.entrySet()) {
            String name = entry.getKey();
            if ((name.startsWith(PREFIX) || name.startsWith(NOTICES)) && !name.endsWith(".class")) {
                require(Arrays.equals(entry.getValue(), local.get(name)) ||
                        Arrays.equals(entry.getValue(), module.get(name)), "missing private resource");
            }
        }
        for (String name : Set.copyOf(module.keySet())) {
            if (name.startsWith(PREFIX) || name.startsWith(NOTICES)) {
                require(!name.endsWith(".class"), "private class duplicated in classes.jar");
                require(Arrays.equals(module.get(name), producer.get(name)), "changed or unknown private resource");
                module.remove(name);
            }
        }
        aar.put(EMBEDDED, producerBytes);
        aar.put("classes.jar", writeZip(module));
        byte[] result = writeZip(aar);

        Path parent = outputAar.toAbsolutePath().getParent();
        Files.createDirectories(parent);
        Path temporary = Files.createTempFile(parent, "embedded-jmdns-", ".aar.tmp");
        try {
            Files.write(temporary, result);
            Files.move(temporary, outputAar, StandardCopyOption.REPLACE_EXISTING);
        } finally {
            Files.deleteIfExists(temporary);
        }
    }

    private static Map<String, byte[]> readZip(byte[] bytes) throws IOException {
        require(bytes.length >= 4 && bytes[0] == 'P' && bytes[1] == 'K', "invalid ZIP");
        Map<String, byte[]> files = new TreeMap<>();
        Set<String> names = new HashSet<>();
        try (ZipInputStream archive = new ZipInputStream(new ByteArrayInputStream(bytes))) {
            ZipEntry entry;
            while ((entry = archive.getNextEntry()) != null) {
                String name = entry.getName();
                require(!name.isEmpty() && !name.startsWith("/") && name.indexOf('\\') < 0 &&
                        name.indexOf('\0') < 0 && name.indexOf(':') < 0, "unsafe ZIP entry");
                String path = entry.isDirectory() ? name.substring(0, name.length() - 1) : name;
                for (String part : path.split("/", -1)) {
                    require(!part.isEmpty() && !part.equals(".") && !part.equals(".."), "unsafe ZIP entry");
                }
                require(names.add(name), "duplicate ZIP entry");
                if (!entry.isDirectory()) {
                    files.put(name, archive.readAllBytes());
                }
                archive.closeEntry();
            }
        }
        require(!files.isEmpty(), "empty ZIP");
        return files;
    }

    private static byte[] writeZip(Map<String, byte[]> files) throws IOException {
        ByteArrayOutputStream bytes = new ByteArrayOutputStream();
        try (ZipOutputStream archive = new ZipOutputStream(bytes)) {
            for (Map.Entry<String, byte[]> file : new TreeMap<>(files).entrySet()) {
                ZipEntry entry = new ZipEntry(file.getKey());
                entry.setTimeLocal(ZIP_TIME);
                archive.putNextEntry(entry);
                archive.write(file.getValue());
                archive.closeEntry();
            }
        }
        return bytes.toByteArray();
    }

    private static void require(boolean condition, String message) throws IOException {
        if (!condition) {
            throw new IOException("Embedded JmDNS AAR: " + message);
        }
    }
}
