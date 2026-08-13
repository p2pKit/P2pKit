package dev.p2pkit.build;

import java.io.File;
import java.io.IOException;
import java.nio.file.Files;
import org.gradle.api.DefaultTask;
import org.gradle.api.GradleException;
import org.gradle.api.file.ConfigurableFileCollection;
import org.gradle.api.file.DirectoryProperty;
import org.gradle.api.file.RegularFileProperty;
import org.gradle.api.provider.Property;
import org.gradle.api.tasks.Input;
import org.gradle.api.tasks.InputFile;
import org.gradle.api.tasks.InputFiles;
import org.gradle.api.tasks.Internal;
import org.gradle.api.tasks.PathSensitive;
import org.gradle.api.tasks.PathSensitivity;
import org.gradle.api.tasks.TaskAction;
import org.gradle.work.DisableCachingByDefault;

@DisableCachingByDefault(because = "Verification has no outputs")
public abstract class VerifyXcframeworkProvenanceTask extends DefaultTask {
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

    @InputFile
    @PathSensitive(PathSensitivity.NONE)
    public abstract RegularFileProperty getCommitFile();

    @InputFile
    @PathSensitive(PathSensitivity.NONE)
    public abstract RegularFileProperty getStateFile();

    @InputFile
    @PathSensitive(PathSensitivity.NONE)
    public abstract RegularFileProperty getFingerprintFile();

    @InputFile
    @PathSensitive(PathSensitivity.NONE)
    public abstract RegularFileProperty getArtifactFingerprintFile();

    @TaskAction
    public void verify() throws IOException {
        String expectedCommit = getSourceCommit().get();
        String actualCommit = Files.readString(getCommitFile().get().getAsFile().toPath()).trim();
        require(!expectedCommit.equals("unknown") && actualCommit.equals(expectedCommit), "commit");
        var binaries = getFrameworkBinaries().getFiles();
        require(binaries.size() == 2 && binaries.stream().allMatch(File::isFile), "Apple binaries");
        String expectedState = getRelevantSourceDirty().get() ? "dirty" : "clean";
        String actualState = Files.readString(getStateFile().get().getAsFile().toPath()).trim();
        require(actualState.equals(expectedState), "source state");
        String expectedFingerprint = ProvenanceFiles.fingerprint(
            getProvenanceInputs().getFiles(),
            getRootDirectory().get().getAsFile()
        );
        String actualFingerprint = Files.readString(getFingerprintFile().get().getAsFile().toPath()).trim();
        require(actualFingerprint.equals(expectedFingerprint), "input fingerprint");
        var artifacts = getFrameworkArtifacts().getFiles();
        require(artifacts.size() >= 4 && artifacts.stream().allMatch(File::isFile), "framework artifacts");
        String expectedArtifactFingerprint = ProvenanceFiles.fingerprint(
            artifacts,
            getRootDirectory().get().getAsFile()
        );
        String actualArtifactFingerprint = Files.readString(
            getArtifactFingerprintFile().get().getAsFile().toPath()
        ).trim();
        require(actualArtifactFingerprint.equals(expectedArtifactFingerprint), "artifact fingerprint");
    }

    private static void require(boolean condition, String field) {
        if (!condition) {
            throw new GradleException("XCFramework provenance mismatch: " + field);
        }
    }
}
