package dev.p2pkit.build;

import java.io.File;
import org.gradle.api.DefaultTask;
import org.gradle.api.GradleException;
import org.gradle.api.file.ConfigurableFileCollection;
import org.gradle.api.file.DirectoryProperty;
import org.gradle.api.file.RegularFileProperty;
import org.gradle.api.provider.Property;
import org.gradle.api.tasks.CacheableTask;
import org.gradle.api.tasks.Input;
import org.gradle.api.tasks.InputFiles;
import org.gradle.api.tasks.Internal;
import org.gradle.api.tasks.OutputFile;
import org.gradle.api.tasks.PathSensitive;
import org.gradle.api.tasks.PathSensitivity;
import org.gradle.api.tasks.TaskAction;

@CacheableTask
public abstract class WriteXcframeworkProvenanceTask extends DefaultTask {
    @InputFiles
    @PathSensitive(PathSensitivity.RELATIVE)
    public abstract ConfigurableFileCollection getProvenanceInputs();

    @InputFiles
    @PathSensitive(PathSensitivity.NONE)
    public abstract ConfigurableFileCollection getFrameworkBinaries();

    @InputFiles
    @PathSensitive(PathSensitivity.RELATIVE)
    public abstract ConfigurableFileCollection getFrameworkArtifacts();

    @Internal
    public abstract DirectoryProperty getRootDirectory();

    @Input
    public abstract Property<String> getSourceCommit();

    @Input
    public abstract Property<Boolean> getRelevantSourceDirty();

    @OutputFile
    public abstract RegularFileProperty getCommitFile();

    @OutputFile
    public abstract RegularFileProperty getStateFile();

    @OutputFile
    public abstract RegularFileProperty getFingerprintFile();

    @OutputFile
    public abstract RegularFileProperty getArtifactFingerprintFile();

    @TaskAction
    public void write() {
        String commit = getSourceCommit().get();
        if (commit.equals("unknown")) {
            throw new GradleException("Cannot attest XCFramework provenance: git HEAD is unavailable or invalid");
        }
        var binaries = getFrameworkBinaries().getFiles();
        if (binaries.size() != 2 || binaries.stream().anyMatch(file -> !file.isFile())) {
            throw new GradleException("XCFramework assembly did not produce both required Apple binaries");
        }
        String fingerprint = ProvenanceFiles.fingerprint(
            getProvenanceInputs().getFiles(),
            getRootDirectory().get().getAsFile()
        );
        var artifacts = getFrameworkArtifacts().getFiles();
        if (artifacts.size() < 4 || artifacts.stream().anyMatch(file -> !file.isFile())) {
            throw new GradleException("XCFramework provenance did not capture binaries and headers");
        }
        String artifactFingerprint = ProvenanceFiles.fingerprint(
            artifacts,
            getRootDirectory().get().getAsFile()
        );
        ProvenanceFiles.writeIfChanged(getCommitFile().get().getAsFile(), commit + "\n");
        ProvenanceFiles.writeIfChanged(
            getStateFile().get().getAsFile(),
            getRelevantSourceDirty().get() ? "dirty\n" : "clean\n"
        );
        ProvenanceFiles.writeIfChanged(getFingerprintFile().get().getAsFile(), fingerprint + "\n");
        ProvenanceFiles.writeIfChanged(
            getArtifactFingerprintFile().get().getAsFile(),
            artifactFingerprint + "\n"
        );
    }
}
