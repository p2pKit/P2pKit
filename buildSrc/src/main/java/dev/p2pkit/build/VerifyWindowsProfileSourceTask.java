package dev.p2pkit.build;

import org.gradle.api.DefaultTask;
import org.gradle.api.file.DirectoryProperty;
import org.gradle.api.provider.Property;
import org.gradle.api.tasks.Input;
import org.gradle.api.tasks.Internal;
import org.gradle.api.tasks.TaskAction;
import org.gradle.work.DisableCachingByDefault;

/** Run even when compiled bytes/resources are up to date: unrelated source dirt must fail packaging. */
@DisableCachingByDefault(because = "Git source admission is an observation, never a reusable artifact")
public abstract class VerifyWindowsProfileSourceTask extends DefaultTask {
    public VerifyWindowsProfileSourceTask() {
        doNotTrackState("Always observe current source before Windows packaging");
    }
    @Internal public abstract DirectoryProperty getRootDirectory();
    @Input public abstract Property<String> getSourceCommit();

    @TaskAction
    public void verify() {
        WindowsProfilePackagingSource.inspect(getRootDirectory().get().getAsFile(), getSourceCommit().get());
    }
}
