package dev.p2pkit.build;

import java.io.File;
import java.io.IOException;
import java.util.List;
import org.gradle.api.DefaultTask;
import org.gradle.api.file.ConfigurableFileCollection;
import org.gradle.api.file.RegularFileProperty;
import org.gradle.api.provider.ListProperty;
import org.gradle.api.tasks.Input;
import org.gradle.api.tasks.InputFile;
import org.gradle.api.tasks.InputFiles;
import org.gradle.api.tasks.PathSensitive;
import org.gradle.api.tasks.PathSensitivity;
import org.gradle.api.tasks.TaskAction;
import org.gradle.work.DisableCachingByDefault;

@DisableCachingByDefault(because = "Verification has no outputs")
public abstract class VerifyPublicConstantAbiTask extends DefaultTask {
    public VerifyPublicConstantAbiTask() {
        getRetainedConstants().convention(List.of());
    }

    @InputFile
    @PathSensitive(PathSensitivity.NONE)
    public abstract RegularFileProperty getApiBaseline();

    @InputFiles
    @PathSensitive(PathSensitivity.RELATIVE)
    public abstract ConfigurableFileCollection getInputClassesDirs();

    @Input
    public abstract ListProperty<String> getRetainedConstants();

    @TaskAction
    public void verify() throws IOException {
        PublicConstantAbi.Result result = PublicConstantAbi.verify(
            getApiBaseline().get().getAsFile().toPath(),
            getInputClassesDirs().getFiles().stream().map(File::toPath).toList(),
            getRetainedConstants().get()
        );
        getLogger().lifecycle("Public constant ABI: {} classes, {} constants, {} retained JVM exceptions",
            result.classes(), result.constants(), result.retained());
    }
}
