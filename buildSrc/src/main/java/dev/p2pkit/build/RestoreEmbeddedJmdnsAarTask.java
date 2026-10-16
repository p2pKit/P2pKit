package dev.p2pkit.build;

import java.io.IOException;
import org.gradle.api.DefaultTask;
import org.gradle.api.file.RegularFileProperty;
import org.gradle.api.tasks.CacheableTask;
import org.gradle.api.tasks.InputFile;
import org.gradle.api.tasks.OutputFile;
import org.gradle.api.tasks.PathSensitive;
import org.gradle.api.tasks.PathSensitivity;
import org.gradle.api.tasks.TaskAction;

/** Publication-only transform; the Android implementation dependency stays intact. */
@CacheableTask
public abstract class RestoreEmbeddedJmdnsAarTask extends DefaultTask {
    @InputFile
    @PathSensitive(PathSensitivity.NONE)
    public abstract RegularFileProperty getInputAar();

    @InputFile
    @PathSensitive(PathSensitivity.NONE)
    public abstract RegularFileProperty getProducerJar();

    @OutputFile
    public abstract RegularFileProperty getOutputAar();

    @TaskAction
    public void restore() throws IOException {
        EmbeddedJmdnsAar.restore(getInputAar().get().getAsFile().toPath(),
                getProducerJar().get().getAsFile().toPath(), getOutputAar().get().getAsFile().toPath());
    }
}
