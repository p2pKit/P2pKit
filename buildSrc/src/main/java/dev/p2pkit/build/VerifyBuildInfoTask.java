package dev.p2pkit.build;

import java.io.IOException;
import java.nio.file.Files;
import java.time.Instant;
import java.time.format.DateTimeParseException;
import org.gradle.api.DefaultTask;
import org.gradle.api.GradleException;
import org.gradle.api.file.RegularFileProperty;
import org.gradle.api.provider.Property;
import org.gradle.api.tasks.Input;
import org.gradle.api.tasks.InputFile;
import org.gradle.api.tasks.PathSensitive;
import org.gradle.api.tasks.PathSensitivity;
import org.gradle.api.tasks.TaskAction;
import org.gradle.work.DisableCachingByDefault;

@DisableCachingByDefault(because = "Verification has no outputs")
public abstract class VerifyBuildInfoTask extends DefaultTask {
    @InputFile
    @PathSensitive(PathSensitivity.NONE)
    public abstract RegularFileProperty getGeneratedFile();

    @Input
    public abstract Property<String> getSourceCommit();

    @Input
    public abstract Property<String> getSourceCommitTime();

    @Input
    public abstract Property<Boolean> getRelevantSourceDirty();

    @TaskAction
    public void verify() throws IOException {
        String content = Files.readString(getGeneratedFile().get().getAsFile().toPath());
        String commit = getSourceCommit().get();
        String commitTime = getSourceCommitTime().get();
        require(commit.matches("[0-9a-f]{40,64}"));
        require(validInstant(commitTime));
        require(content.equals(GenerateBuildInfoTask.render(
            commit,
            commitTime,
            getRelevantSourceDirty().get()
        )));
    }

    private static void require(boolean condition) {
        if (!condition) {
            throw new GradleException("Generated BuildInfo violates the reproducible provenance contract");
        }
    }

    private static boolean validInstant(String value) {
        try {
            Instant.parse(value);
            return true;
        } catch (DateTimeParseException ignored) {
            return false;
        }
    }
}
