package dev.p2pkit.build;

import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Arrays;
import java.util.Map;
import java.util.TreeMap;
import java.util.zip.ZipEntry;
import java.util.zip.ZipInputStream;
import java.util.zip.ZipOutputStream;

/** Synthetic archive controls, not Android execution or actual publication evidence. */
public final class EmbeddedJmdnsAarTest {
    private static final String PRIVATE = "dev/p2pkit/transport/lan/internal/jmdns/";
    private static final String NOTICES = "META-INF/p2pkit/third-party/jmdns/";
    private static final String CLASS = PRIVATE + "Fixture.class";
    private static final String EMBEDDED = "libs/p2pkit-internal-jmdns.jar";
    private static int count;

    private EmbeddedJmdnsAarTest() { }

    private static byte[] bytes(String value) { return value.getBytes(StandardCharsets.UTF_8); }

    private static Map<String, byte[]> producer() {
        return new TreeMap<>(Map.of("META-INF/LICENSE", bytes("canonical synthetic license\n"),
                "META-INF/MANIFEST.MF", bytes("Manifest-Version: 1.0\r\n\r\n"),
                PRIVATE + "version.properties", bytes("jmdns.version=synthetic\n"),
                NOTICES + "PROVENANCE.json", bytes("{\"synthetic\":true}\n"),
                NOTICES + "NOTICE.txt", bytes("original synthetic attribution\n"),
                CLASS, bytes("synthetic class bytes, never loaded")));
    }

    private static Map<String, byte[]> module() {
        return new TreeMap<>(Map.of("dev/p2pkit/transport/lan/Fixture.class", bytes("public synthetic bytecode"),
                "META-INF/p2p-transport-lan.kotlin_module", bytes("module identity"),
                PRIVATE + "version.properties", producer().get(PRIVATE + "version.properties"),
                NOTICES + "PROVENANCE.json", producer().get(NOTICES + "PROVENANCE.json"),
                NOTICES + "NOTICE.txt", producer().get(NOTICES + "NOTICE.txt")));
    }

    private static byte[] zip(Map<String, byte[]> entries) throws IOException {
        ByteArrayOutputStream result = new ByteArrayOutputStream();
        try (ZipOutputStream zip = new ZipOutputStream(result)) {
            for (Map.Entry<String, byte[]> item : new TreeMap<>(entries).entrySet()) {
                ZipEntry entry = new ZipEntry(item.getKey());
                entry.setTime(0);
                zip.putNextEntry(entry);
                zip.write(item.getValue());
                zip.closeEntry();
            }
        }
        return result.toByteArray();
    }

    private static Map<String, byte[]> unzip(byte[] bytes) throws IOException {
        Map<String, byte[]> result = new TreeMap<>();
        try (ZipInputStream zip = new ZipInputStream(new ByteArrayInputStream(bytes))) {
            ZipEntry entry;
            while ((entry = zip.getNextEntry()) != null) result.put(entry.getName(), zip.readAllBytes());
        }
        return result;
    }

    private static void run(Path parent, String damage) throws IOException {
        Path work = Files.createDirectory(parent.resolve(damage));
        Map<String, byte[]> producer = producer();
        Map<String, byte[]> filtered = new TreeMap<>(Map.of(CLASS, producer.get(CLASS)));
        Map<String, byte[]> module = module();
        switch (damage) {
            case "already-complete": filtered = producer(); break;
            case "changed-class": filtered.put(CLASS, bytes("changed")); break;
            case "missing-class":
                producer.put(PRIVATE + "Second.class", bytes("required second class")); break;
            case "extra-class": filtered.put(PRIVATE + "Extra.class", bytes("unexpected")); break;
            case "foreign-producer-class": producer.put("foreign/Other.class", bytes("foreign")); break;
            case "changed-resource": module.put(PRIVATE + "version.properties", bytes("wrong version")); break;
            case "unknown-resource": module.put(NOTICES + "unexpected.txt", bytes("undeclared")); break;
            case "duplicated-class": module.put(CLASS, producer.get(CLASS)); break;
            case "missing-license": producer.remove("META-INF/LICENSE"); break;
            case "missing-version": producer.remove(PRIVATE + "version.properties"); break;
            case "missing-provenance": producer.remove(NOTICES + "PROVENANCE.json"); break;
            case "unsafe-parent": producer.put("../outside", bytes("unsafe")); break;
            case "unsafe-absolute": producer.put("/outside", bytes("unsafe")); break;
            case "unsafe-backslash": producer.put("part\\outside", bytes("unsafe")); break;
            case "unsafe-drive": producer.put("C:/outside", bytes("unsafe")); break;
            case "large-member": producer.put("large", new byte[16 * 1024 * 1024 + 1]); break;
            case "too-many-entries":
                for (int i = 0; i < 4097; i++) producer.put("entry" + i, new byte[0]); break;
            default: break;
        }
        byte[] producerBytes = zip(producer);
        if (damage.equals("truncated-directory")) producerBytes = Arrays.copyOf(producerBytes, producerBytes.length - 23);
        if (damage.equals("trailing-bytes")) producerBytes = Arrays.copyOf(producerBytes, producerBytes.length + 1);
        if (damage.equals("bad-central-crc") || damage.equals("bad-central-name")) {
            for (int i = 0; i < producerBytes.length - 46; i++) {
                if (producerBytes[i] == 'P' && producerBytes[i + 1] == 'K'
                        && producerBytes[i + 2] == 1 && producerBytes[i + 3] == 2) {
                    producerBytes[i + (damage.equals("bad-central-crc") ? 16 : 46)] ^= 1;
                    break;
                }
            }
        }
        Map<String, byte[]> outer = new TreeMap<>(Map.of("classes.jar", zip(module), EMBEDDED, zip(filtered),
                "AndroidManifest.xml", bytes("synthetic manifest"), "META-INF/LICENSE", bytes("canonical synthetic license\n")));
        if (damage.equals("missing-embedded")) outer.remove(EMBEDDED);
        if (damage.equals("missing-module")) outer.remove("classes.jar");
        if (damage.equals("malformed-embedded")) outer.put(EMBEDDED, bytes("not a zip"));
        Path aar = work.resolve("fixture.aar"), jar = work.resolve("producer.jar");
        Files.write(aar, zip(outer));
        Files.write(jar, producerBytes);
        byte[] original = Files.readAllBytes(aar);
        boolean positive = damage.equals("agp-split") || damage.equals("already-complete");
        try {
            EmbeddedJmdnsAar.preserve(aar.toFile(), jar.toFile());
            if (!positive) throw new AssertionError("Accepted negative archive: " + damage);
        } catch (IOException rejected) {
            if (positive) throw new AssertionError("Rejected positive archive", rejected);
            if (!Arrays.equals(Files.readAllBytes(aar), original)) throw new AssertionError("Replaced failed input");
            count++;
            return;
        }
        byte[] first = Files.readAllBytes(aar);
        Map<String, byte[]> result = unzip(first);
        if (!Arrays.equals(result.get(EMBEDDED), producerBytes)) throw new AssertionError("Producer not byte-exact");
        if (!Arrays.equals(result.get("AndroidManifest.xml"), outer.get("AndroidManifest.xml"))) {
            throw new AssertionError("Changed unrelated AAR entry");
        }
        Map<String, byte[]> actualModule = unzip(result.get("classes.jar"));
        if (actualModule.size() != 2 || actualModule.keySet().stream().anyMatch(name -> name.startsWith(PRIVATE)
                || name.startsWith(NOTICES))) throw new AssertionError("Duplicated private resources");
        EmbeddedJmdnsAar.preserve(aar.toFile(), jar.toFile());
        if (!Arrays.equals(first, Files.readAllBytes(aar))) throw new AssertionError("Non-deterministic repeated assembly");
        count++;
    }

    public static void main(String[] args) throws IOException {
        Path root = Path.of(args[0]);
        for (String damage : new String[]{"agp-split", "already-complete", "changed-class", "missing-class", "extra-class",
                "foreign-producer-class", "changed-resource", "unknown-resource", "duplicated-class", "missing-license",
                "missing-version", "missing-provenance", "unsafe-parent", "unsafe-absolute", "unsafe-backslash",
                "unsafe-drive", "large-member", "too-many-entries", "missing-embedded", "missing-module", "malformed-embedded",
                "truncated-directory", "trailing-bytes", "bad-central-crc", "bad-central-name"}) {
            run(root, damage);
        }
        if (count != 25) throw new AssertionError("Incomplete archive controls");
        System.out.println("PASS: 25 synthetic AAR producer-preservation controls; no Android/runtime claim");
    }
}
