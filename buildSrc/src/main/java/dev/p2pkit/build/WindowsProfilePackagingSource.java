package dev.p2pkit.build;

import java.util.List;

/** Exact builder source admission; no release, runtime or signature authority. */
final class WindowsProfilePackagingSource {
    private WindowsProfilePackagingSource() {}

    static String inspect(java.io.File root, String expected) {
        GitProcess.Result head = GitProcess.run(root, List.of("rev-parse", "--verify", "HEAD"));
        GitProcess.Result tree = GitProcess.run(root, List.of("rev-parse", "--verify", "HEAD^{tree}"));
        GitProcess.Result status = GitProcess.run(root,
            List.of("--no-optional-locks", "-c", "core.fsmonitor=false", "status", "--porcelain=v1",
                "--untracked-files=all"));
        if (!expected.matches("[a-f0-9]{40}") || head.exitCode() != 0 || !expected.equals(head.output()) ||
            tree.exitCode() != 0 || !tree.output().matches("[a-f0-9]{40}") ||
            status.exitCode() != 0 || !status.output().isEmpty()) {
            throw new IllegalStateException("Native packaging requires an exact clean committed source");
        }
        return tree.output();
    }

}
