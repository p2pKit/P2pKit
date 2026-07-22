package dev.p2pkit.build;

import java.time.OffsetDateTime;
import java.time.format.DateTimeParseException;
import java.util.List;
import org.gradle.api.file.DirectoryProperty;
import org.gradle.api.provider.ValueSource;
import org.gradle.api.provider.ValueSourceParameters;

public abstract class GitCommitTimeValueSource implements ValueSource<String, GitCommitTimeValueSource.Parameters> {
    public interface Parameters extends ValueSourceParameters {
        DirectoryProperty getRootDirectory();
    }

    @Override
    public String obtain() {
        GitProcess.Result result = GitProcess.run(
            getParameters().getRootDirectory().get().getAsFile(),
            List.of("show", "-s", "--format=%cI", "HEAD")
        );
        if (result.exitCode() != 0) {
            return "unknown";
        }
        try {
            return OffsetDateTime.parse(result.output()).toInstant().toString();
        } catch (DateTimeParseException exception) {
            return "unknown";
        }
    }
}
