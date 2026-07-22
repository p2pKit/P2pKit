package dev.p2pkit.build;

import java.io.IOException;
import java.nio.file.Files;
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
        require(content.contains("public const val COMMIT: String = \"" + getSourceCommit().get() + "\""));
        require(content.contains("public const val COMMIT_TIME: String = \"" + getSourceCommitTime().get() + "\""));
        require(content.contains("public const val DIRTY: Boolean = " + getRelevantSourceDirty().get()));
        require(content.contains("public const val BRANCH: String = \"not-embedded\""));
        require(content.contains("public const val BUILD_TIME: String = COMMIT_TIME"));
        require(!content.contains("Instant.now"));
        require(!content.contains("built \" + BUILD_TIME"));
    }

    private static void require(boolean condition) {
        if (!condition) {
            throw new GradleException("Generated BuildInfo violates the reproducible provenance contract");
        }
    }
}
