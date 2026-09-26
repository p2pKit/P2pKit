package dev.p2pkit.build;

import org.gradle.api.DefaultTask;
import org.gradle.api.file.DirectoryProperty;
import org.gradle.api.provider.Property;
import org.gradle.api.tasks.CacheableTask;
import org.gradle.api.tasks.Input;
import org.gradle.api.tasks.OutputDirectory;
import org.gradle.api.tasks.TaskAction;

/** Embedded in the APK assets and the Desktop application JAR, never only in a release title. */
@CacheableTask
public abstract class GenerateSampleReleaseIdentityTask extends DefaultTask {
    @Input
    public abstract Property<String> getSourceCommit();

    @Input
    public abstract Property<String> getCanonicalVersion();

    @OutputDirectory
    public abstract DirectoryProperty getOutputDirectory();

    @TaskAction
    public void generate() {
        ApplicationReleaseVersion version = ApplicationReleaseVersion.parse(getCanonicalVersion().get());
        ProvenanceFiles.writeIfChanged(
            getOutputDirectory().file("p2pkit-release.json").get().getAsFile(),
            version.identityJson(getSourceCommit().get())
        );
    }
}
