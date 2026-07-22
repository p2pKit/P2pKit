package dev.p2pkit.build;

import java.io.File;
import java.io.IOException;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.Comparator;
import java.util.HexFormat;

final class ProvenanceFiles {
    private ProvenanceFiles() {}

    static String fingerprint(Iterable<File> files, File rootDirectory) {
        try {
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            var sortedFiles = new java.util.ArrayList<File>();
            files.forEach(file -> {
                if (file.isFile()) {
                    sortedFiles.add(file);
                }
            });
            sortedFiles.sort(Comparator.comparing(file -> relativePath(file, rootDirectory)));
            byte[] buffer = new byte[8192];
            for (File file : sortedFiles) {
                digest.update(relativePath(file, rootDirectory).getBytes(StandardCharsets.UTF_8));
                digest.update((byte) 0);
                try (InputStream input = Files.newInputStream(file.toPath())) {
                    int count;
                    while ((count = input.read(buffer)) >= 0) {
                        digest.update(buffer, 0, count);
                    }
                }
                digest.update((byte) 0);
            }
            return HexFormat.of().formatHex(digest.digest());
        } catch (IOException | NoSuchAlgorithmException exception) {
            throw new IllegalStateException("Cannot fingerprint provenance inputs", exception);
        }
    }

    static void writeIfChanged(File file, String content) {
        try {
            Files.createDirectories(file.toPath().getParent());
            if (!file.isFile() || !Files.readString(file.toPath()).equals(content)) {
                Files.writeString(file.toPath(), content, StandardCharsets.UTF_8);
            }
        } catch (IOException exception) {
            throw new IllegalStateException("Cannot write provenance file " + file, exception);
        }
    }

    private static String relativePath(File file, File rootDirectory) {
        return rootDirectory.toPath().toAbsolutePath().normalize()
            .relativize(file.toPath().toAbsolutePath().normalize())
            .toString()
            .replace(File.separatorChar, '/');
    }
}
