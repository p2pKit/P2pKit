package dev.p2pkit.build;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;
import java.util.stream.Collectors;
import org.gradle.api.DefaultTask;
import org.gradle.api.GradleException;
import org.gradle.api.file.DirectoryProperty;
import org.gradle.api.tasks.CacheableTask;
import org.gradle.api.tasks.InputDirectory;
import org.gradle.api.tasks.OutputDirectory;
import org.gradle.api.tasks.PathSensitive;
import org.gradle.api.tasks.PathSensitivity;
import org.gradle.api.tasks.TaskAction;

/** Transcribes committed hex into commonTest literals; never calls a production encoder. */
@CacheableTask
public abstract class GenerateWireGoldensTask extends DefaultTask {
    @InputDirectory
    @PathSensitive(PathSensitivity.RELATIVE)
    public abstract DirectoryProperty getFixtureDirectory();

    @OutputDirectory
    public abstract DirectoryProperty getOutputDirectory();

    @TaskAction
    public void generate() throws IOException {
        List<Path> fixtures;
        try (var paths = Files.list(getFixtureDirectory().get().getAsFile().toPath())) {
            fixtures = paths.filter(path -> path.getFileName().toString().endsWith(".hex"))
                .sorted().collect(Collectors.toList());
        }
        if (fixtures.isEmpty()) throw new GradleException("No committed wire goldens found");
        StringBuilder source = new StringBuilder(
            "// Generated from commonTest/resources/wire-goldens; DO NOT EDIT.\n"
                + "package dev.p2pkit.core.testfixtures\n\n"
                + "internal object WireGoldenBytes {\n"
                + "    fun read(name: String): ByteArray = hexByName.getValue(name).hexToByteArray()\n\n"
                + "    private val hexByName: Map<String, String> = mapOf(\n"
        );
        for (Path fixture : fixtures) {
            String filename = fixture.getFileName().toString();
            if (!Files.isRegularFile(fixture) || !filename.matches("[a-z][a-z0-9-]*\\.hex")) {
                throw new GradleException("Invalid wire golden filename: " + filename);
            }
            String hex = Files.readString(fixture, StandardCharsets.UTF_8).replaceAll("[ \\t\\r\\n]", "");
            if (hex.length() % 2 != 0 || !hex.matches("[0-9a-f]+")) {
                throw new GradleException("Wire golden must contain nonempty lowercase hex: " + filename);
            }
            source.append("        \"").append(filename.substring(0, filename.length() - 4)).append("\" to (\n");
            for (int offset = 0; offset < hex.length(); offset += 96) {
                int end = Math.min(offset + 96, hex.length());
                source.append("            \"").append(hex, offset, end).append('"');
                source.append(end == hex.length() ? "\n" : " +\n");
            }
            source.append("        ),\n");
        }
        source.append("    )\n}\n");
        ProvenanceFiles.writeIfChanged(
            getOutputDirectory().get().file("dev/p2pkit/core/testfixtures/WireGoldenBytes.kt").getAsFile(),
            source.toString()
        );
    }
}
