package dev.p2pkit.build;

import java.util.List;
import org.gradle.api.file.DirectoryProperty;
import org.gradle.api.provider.ValueSource;
import org.gradle.api.provider.ValueSourceParameters;

public abstract class GitCommitValueSource implements ValueSource<String, GitCommitValueSource.Parameters> {
    public interface Parameters extends ValueSourceParameters {
        DirectoryProperty getRootDirectory();
    }

    @Override
    public String obtain() {
        GitProcess.Result result = GitProcess.run(
            getParameters().getRootDirectory().get().getAsFile(),
            List.of("rev-parse", "--verify", "HEAD")
        );
        String commit = result.output().toLowerCase();
        return result.exitCode() == 0 && commit.matches("[0-9a-f]{40,64}") ? commit : "unknown";
    }
}
