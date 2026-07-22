package dev.p2pkit.build;

import java.io.File;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.List;

final class GitProcess {
    record Result(int exitCode, String output) {}

    private GitProcess() {}

    static Result run(File rootDirectory, List<String> arguments) {
        var command = new ArrayList<String>();
        command.add("git");
        command.addAll(arguments);
        try {
            Process process = new ProcessBuilder(command)
                .directory(rootDirectory)
                .redirectErrorStream(true)
                .start();
            String output = new String(process.getInputStream().readAllBytes(), StandardCharsets.UTF_8).trim();
            return new Result(process.waitFor(), output);
        } catch (IOException exception) {
            return new Result(-1, "");
        } catch (InterruptedException exception) {
            Thread.currentThread().interrupt();
            return new Result(-1, "");
        }
    }
}
