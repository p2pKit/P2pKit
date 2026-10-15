package dev.p2pkit.build;

import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.nio.ByteBuffer;
import java.nio.charset.CodingErrorAction;
import java.nio.charset.StandardCharsets;
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

/** Keeps the one reviewed producer intact when AGP splits local JAR classes and resources. */
public final class EmbeddedJmdnsAar {
    private static final String PRIVATE = "dev/p2pkit/transport/lan/internal/jmdns/";
    private static final String NOTICES = "META-INF/p2pkit/third-party/jmdns/";
    private static final String EMBEDDED = "libs/p2pkit-internal-jmdns.jar";
    private static final int ARCHIVE_LIMIT = 64 * 1024 * 1024;
    private static final int MEMBER_LIMIT = 16 * 1024 * 1024;
    private static final int EXPANDED_LIMIT = 128 * 1024 * 1024;

    private EmbeddedJmdnsAar() { }

    /**
     * Runs inside BundleAar after its ordinary assembly, before publication/GMM checksums.
     * Class bytes must already match the producer: this does not repair stale compilation.
     * Only byte-identical private resources are moved out of classes.jar into that producer.
     * Unexpected input fails before replacing the task's output; inspectors stay unchanged.
     */
    public static void preserve(File aarFile, File producerFile) throws IOException {
        Path aar = aarFile.toPath();
        byte[] producerBytes = read(producerFile.toPath());
        Map<String, byte[]> producer = unzip(producerBytes);
        Map<String, byte[]> outer = unzip(read(aar));
        require(outer.containsKey(EMBEDDED) && outer.containsKey("classes.jar"), "Missing AAR JAR inputs");
        require(producer.containsKey("META-INF/LICENSE") && producer.containsKey(PRIVATE + "version.properties")
                && producer.containsKey(NOTICES + "PROVENANCE.json"), "Incomplete private producer resources");
        Map<String, byte[]> filtered = unzip(outer.get(EMBEDDED));
        Map<String, byte[]> module = unzip(outer.get("classes.jar"));
        Set<String> classes = new HashSet<>();
        Set<String> packagedClasses = new HashSet<>();
        for (Map.Entry<String, byte[]> entry : producer.entrySet()) {
            if (entry.getKey().endsWith(".class")) {
                require(entry.getKey().startsWith(PRIVATE), "Foreign class in private producer");
                classes.add(entry.getKey());
            }
        }
        require(!classes.isEmpty(), "Empty private producer class set");
        for (Map.Entry<String, byte[]> entry : filtered.entrySet()) {
            require(Arrays.equals(entry.getValue(), producer.get(entry.getKey())),
                    "AGP local JAR contains changed or unknown producer bytes");
            if (entry.getKey().endsWith(".class")) packagedClasses.add(entry.getKey());
        }
        require(classes.equals(packagedClasses), "AGP local JAR class inventory differs from producer");
        for (String name : new HashSet<>(module.keySet())) {
            if (name.startsWith(PRIVATE) || name.startsWith(NOTICES)) {
                require(!name.endsWith(".class"), "AAR classes.jar duplicates private classes");
                require(Arrays.equals(module.get(name), producer.get(name)),
                        "AAR classes.jar contains changed or unknown private resources");
                module.remove(name);
            }
        }
        outer.put(EMBEDDED, producerBytes);
        outer.put("classes.jar", zip(module));
        byte[] replacement = zip(outer);
        Path temporary = Files.createTempFile(aar.getParent(), "p2pkit-aar-producer-", ".tmp");
        // No in-place ZIP mutation. Preserve a failed temporary rather than hiding a write failure.
        try (FileOutputStream stream = new FileOutputStream(temporary.toFile())) {
            stream.write(replacement);
            stream.getFD().sync();
        }
        Files.move(temporary, aar, StandardCopyOption.ATOMIC_MOVE, StandardCopyOption.REPLACE_EXISTING);
    }

    private static byte[] read(Path path) throws IOException {
        require(!Files.isSymbolicLink(path) && Files.isRegularFile(path)
                && Files.size(path) > 0 && Files.size(path) <= ARCHIVE_LIMIT, "Invalid bounded archive input");
        try (var stream = Files.newInputStream(path)) {
            byte[] result = stream.readNBytes(ARCHIVE_LIMIT + 1);
            require(result.length <= ARCHIVE_LIMIT, "Archive grew beyond its bound");
            return result;
        }
    }

    private static Map<String, byte[]> unzip(byte[] bytes) throws IOException {
        require(bytes.length <= ARCHIVE_LIMIT, "Archive exceeds its byte bound");
        Map<String, ZipEntry> central = centralDirectory(bytes);
        Map<String, byte[]> result = new TreeMap<>();
        Set<String> seen = new HashSet<>();
        int total = 0;
        try (ZipInputStream stream = new ZipInputStream(new ByteArrayInputStream(bytes))) {
            ZipEntry entry;
            while ((entry = stream.getNextEntry()) != null) {
                String name = entry.getName();
                String path = entry.isDirectory() ? name.substring(0, name.length() - 1) : name;
                require(!path.isEmpty() && !path.startsWith("/") && !path.matches("^[A-Za-z]:.*")
                        && path.indexOf('\\') < 0 && path.indexOf('\0') < 0 && seen.add(name)
                        && seen.size() <= 4096, "Unsafe, duplicate or excessive archive entry");
                for (String part : path.split("/", -1)) {
                    require(!part.isEmpty() && !part.equals(".") && !part.equals(".."), "Unsafe archive path");
                }
                byte[] content = stream.readNBytes(MEMBER_LIMIT + 1);
                require(content.length <= MEMBER_LIMIT, "Archive member exceeds its byte bound");
                total += content.length;
                require(total <= EXPANDED_LIMIT, "Expanded archive exceeds its byte bound");
                stream.closeEntry();
                ZipEntry recorded = central.get(name);
                require(recorded != null && recorded.getCrc() == entry.getCrc()
                        && recorded.getSize() == entry.getSize()
                        && recorded.getCompressedSize() == entry.getCompressedSize(),
                        "Local ZIP entry differs from its central directory");
                if (entry.isDirectory()) require(content.length == 0, "Directory entry has content");
                else result.put(name, content);
            }
        }
        require(!result.isEmpty() && seen.equals(central.keySet()), "Empty or inconsistent archive");
        return result;
    }

    /** Fail closed on incomplete ZIPs; ZipInputStream alone does not inspect the central directory. */
    private static Map<String, ZipEntry> centralDirectory(byte[] bytes) throws IOException {
        require(bytes.length >= 22 && number(bytes, 0, 4) == 0x04034b50L, "Missing ZIP local header");
        int end = -1;
        for (int i = bytes.length - 22; i >= Math.max(0, bytes.length - 65557); i--) {
            if (number(bytes, i, 4) == 0x06054b50L && i + 22 + number(bytes, i + 20, 2) == bytes.length) {
                end = i;
                break;
            }
        }
        require(end >= 0, "Missing ZIP end record or trailing bytes");
        long count = number(bytes, end + 10, 2);
        long size = number(bytes, end + 12, 4), start = number(bytes, end + 16, 4);
        require(number(bytes, end + 4, 2) == 0 && number(bytes, end + 6, 2) == 0
                && number(bytes, end + 8, 2) == count && count > 0 && count <= 4096
                && start + size == end, "Unsupported split/ZIP64 or incomplete ZIP directory");
        int position = (int) start;
        Map<String, ZipEntry> entries = new TreeMap<>();
        Set<Long> offsets = new HashSet<>();
        for (int i = 0; i < count; i++) {
            require(position + 46 <= end && number(bytes, position, 4) == 0x02014b50L, "Invalid ZIP directory entry");
            int length = (int) number(bytes, position + 28, 2);
            long next = position + 46L + length + number(bytes, position + 30, 2) + number(bytes, position + 32, 2);
            long offset = number(bytes, position + 42, 4), flags = number(bytes, position + 8, 2);
            require(next <= end && number(bytes, position + 34, 2) == 0 && (flags & 1) == 0
                    && offset + 30 <= start && offsets.add(offset), "Invalid ZIP entry bounds/ownership");
            int local = (int) offset;
            require(number(bytes, local, 4) == 0x04034b50L && number(bytes, local + 6, 2) == flags
                    && number(bytes, local + 8, 2) == number(bytes, position + 10, 2)
                    && number(bytes, local + 26, 2) == length
                    && offset + 30 + length + number(bytes, local + 28, 2)
                        + number(bytes, position + 20, 4) <= start,
                    "ZIP local/central headers disagree");
            byte[] nameBytes = Arrays.copyOfRange(bytes, position + 46, position + 46 + length);
            require(Arrays.equals(nameBytes, Arrays.copyOfRange(bytes, local + 30, local + 30 + length)),
                    "ZIP local/central names disagree");
            String name = StandardCharsets.UTF_8.newDecoder().onMalformedInput(CodingErrorAction.REPORT)
                    .onUnmappableCharacter(CodingErrorAction.REPORT).decode(ByteBuffer.wrap(nameBytes)).toString();
            ZipEntry entry = new ZipEntry(name);
            entry.setSize(number(bytes, position + 24, 4));
            entry.setCompressedSize(number(bytes, position + 20, 4));
            entry.setCrc(number(bytes, position + 16, 4));
            require(entries.put(name, entry) == null, "Duplicate ZIP directory name");
            position = (int) next;
        }
        require(position == end, "ZIP directory length differs");
        return entries;
    }

    private static long number(byte[] bytes, int offset, int length) throws IOException {
        require(offset >= 0 && offset <= bytes.length - length, "Truncated ZIP header");
        long result = 0;
        for (int i = 0; i < length; i++) result |= (bytes[offset + i] & 0xffL) << (8 * i);
        return result;
    }

    private static byte[] zip(Map<String, byte[]> entries) throws IOException {
        ByteArrayOutputStream bytes = new ByteArrayOutputStream();
        try (ZipOutputStream stream = new ZipOutputStream(bytes)) {
            for (Map.Entry<String, byte[]> item : new TreeMap<>(entries).entrySet()) {
                ZipEntry entry = new ZipEntry(item.getKey());
                // DOS-representable local time: deterministic across build-host time zones.
                entry.setTimeLocal(LocalDateTime.of(1980, 2, 1, 0, 0));
                stream.putNextEntry(entry);
                stream.write(item.getValue());
                stream.closeEntry();
                require(bytes.size() <= ARCHIVE_LIMIT, "Repacked archive exceeds its byte bound");
            }
        }
        require(bytes.size() <= ARCHIVE_LIMIT, "Repacked archive exceeds its byte bound");
        return bytes.toByteArray();
    }

    private static void require(boolean condition, String message) throws IOException {
        if (!condition) throw new IOException(message);
    }
}
