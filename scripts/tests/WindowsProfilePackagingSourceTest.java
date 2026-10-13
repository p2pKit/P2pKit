package dev.p2pkit.build;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;

/** Synthetic local repositories only. No Windows, credentials, native loading or publication. */
public final class WindowsProfilePackagingSourceTest {
    private static int controls;
    private WindowsProfilePackagingSourceTest() {}

    public static void main(String[] args) throws Exception {
        Path root = Files.createDirectory(Path.of(args[0]).resolve("source"));
        git(root, "init", "--template=");
        Files.createDirectory(root.resolve("empty-hooks"));
        Files.writeString(root.resolve("input.txt"), "original\n");
        git(root, "add", "input.txt");
        git(root, "commit", "-m", "Synthetic packaging admission fixture");
        String head = git(root, "rev-parse", "HEAD");
        String tree = git(root, "rev-parse", "HEAD^{tree}");
        if (!tree.equals(WindowsProfilePackagingSource.inspect(root.toFile(), head))) {
            throw new AssertionError("Exact clean source must be admitted");
        }
        controls++;
        rejects(root, "0".repeat(40));
        rejects(root, "HEAD");
        Files.writeString(root.resolve("input.txt"), "edited\n");
        rejects(root, head);
        git(root, "add", "input.txt");
        rejects(root, head);
        git(root, "restore", "--staged", "input.txt");
        Files.writeString(root.resolve("input.txt"), "original\n");
        Files.writeString(root.resolve("untracked.txt"), "new\n");
        rejects(root, head);
        Files.delete(root.resolve("untracked.txt"));
        Files.createDirectory(root.resolve("nested"));
        Files.writeString(root.resolve("nested/untracked.txt"), "new\n");
        rejects(root, head);
        Files.delete(root.resolve("nested/untracked.txt"));
        Files.delete(root.resolve("nested"));
        git(root, "commit", "--allow-empty", "-m", "Synthetic new checkpoint");
        rejects(root, head);
        System.out.println("PASS " + controls + " synthetic clean-source admission controls; not Windows runtime");
    }

    private static void rejects(Path root, String expected) {
        try {
            WindowsProfilePackagingSource.inspect(root.toFile(), expected);
        } catch (IllegalStateException expectedFailure) {
            controls++;
            return;
        }
        throw new AssertionError("Changed or invalid source must fail");
    }

    private static String git(Path root, String... arguments) {
        var command = new ArrayList<>(List.of("-c", "user.name=Local fixture", "-c",
            "user.email=fixture@example.invalid", "-c", "commit.gpgsign=false", "-c",
            "core.hooksPath=" + root.resolve("empty-hooks"), "-c", "core.fsmonitor=false"));
        command.addAll(List.of(arguments));
        GitProcess.Result result = GitProcess.run(root.toFile(), command);
        if (result.exitCode() != 0) throw new AssertionError("Synthetic Git fixture command failed");
        return result.output();
    }
}
