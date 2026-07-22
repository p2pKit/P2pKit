package dev.p2pkit.build;

import java.util.ArrayList;
import org.gradle.api.file.DirectoryProperty;
import org.gradle.api.provider.ListProperty;
import org.gradle.api.provider.ValueSource;
import org.gradle.api.provider.ValueSourceParameters;

public abstract class GitDirtyValueSource implements ValueSource<Boolean, GitDirtyValueSource.Parameters> {
    public interface Parameters extends ValueSourceParameters {
        DirectoryProperty getRootDirectory();
        ListProperty<String> getRelevantPaths();
    }

    @Override
    public Boolean obtain() {
        var arguments = new ArrayList<String>();
        arguments.add("status");
        arguments.add("--porcelain=v1");
        arguments.add("--untracked-files=normal");
        arguments.add("--");
        arguments.addAll(getParameters().getRelevantPaths().get());
        GitProcess.Result result = GitProcess.run(
            getParameters().getRootDirectory().get().getAsFile(),
            arguments
        );
        return result.exitCode() != 0 || !result.output().isBlank();
    }
}
