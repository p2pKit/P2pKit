package dev.p2pkit.build;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.LinkOption;
import java.nio.file.Path;
import java.nio.file.StandardCopyOption;
import java.nio.file.attribute.BasicFileAttributes;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.HexFormat;
import java.util.List;
import java.util.UUID;
import javax.inject.Inject;
import org.gradle.api.DefaultTask;
import org.gradle.api.file.DirectoryProperty;
import org.gradle.api.file.RegularFileProperty;
import org.gradle.api.provider.Property;
import org.gradle.api.tasks.Input;
import org.gradle.api.tasks.InputDirectory;
import org.gradle.api.tasks.Internal;
import org.gradle.api.tasks.OutputFile;
import org.gradle.api.tasks.PathSensitive;
import org.gradle.api.tasks.PathSensitivity;
import org.gradle.api.tasks.TaskAction;
import org.gradle.process.ExecOperations;
import org.gradle.work.DisableCachingByDefault;

/** Existing-app compiler input only. No signing, installation, library loading or runtime qualification. */
@DisableCachingByDefault(because = "Native MSVC toolchain identity is not an interchangeable remote-cache input")
public abstract class BuildWindowsProfileTask extends DefaultTask {
    @Inject protected abstract ExecOperations getExecOperations();
    @Internal public abstract DirectoryProperty getRootDirectory();
    @InputDirectory @PathSensitive(PathSensitivity.RELATIVE)
    public abstract DirectoryProperty getNativeDirectory();
    @InputDirectory @PathSensitive(PathSensitivity.ABSOLUTE)
    public abstract DirectoryProperty getJavaHome();
    @Input public abstract Property<String> getSourceCommit();
    @OutputFile public abstract RegularFileProperty getLibraryFile();
    @OutputFile public abstract RegularFileProperty getCompilerReceipt();

    @TaskAction
    public void compile() throws IOException, NoSuchAlgorithmException {
        if (!System.getProperty("os.name").startsWith("Windows") ||
            !List.of("amd64", "x86_64").contains(System.getProperty("os.arch"))) {
            throw new IllegalStateException("Windows x64 compiler execution is required");
        }
        String source = getSourceCommit().get();
        String tree = WindowsProfilePackagingSource.inspect(getRootDirectory().get().getAsFile(), source);
        Path temporary = getTemporaryDir().toPath().resolve("compiler-" + UUID.randomUUID());
        Path script = getNativeDirectory().get().getAsFile().toPath().resolve("build-windows.cmd");
        // Resolve an installed x64 compiler through Microsoft's installer inventory. No tool download,
        // administrative action, ambient compiler flags or product/runtime privilege changes are involved.
        Path command = compilerCommand(script, temporary);
        getExecOperations().exec(spec -> {
            spec.setWorkingDir(getRootDirectory().get().getAsFile());
            spec.environment("JAVA_HOME", getJavaHome().get().getAsFile().getAbsolutePath());
            spec.commandLine("cmd.exe", "/d", "/c", command.toString());
        }).assertNormalExitValue();
        if (!tree.equals(WindowsProfilePackagingSource.inspect(getRootDirectory().get().getAsFile(), source))) {
            throw new IllegalStateException("Native source changed during compilation");
        }
        Path dll = temporary.resolve("p2pkit-windows-profile.dll");
        BasicFileAttributes attributes =
            Files.readAttributes(dll, BasicFileAttributes.class, LinkOption.NOFOLLOW_LINKS);
        if (!attributes.isRegularFile() || attributes.isSymbolicLink() ||
            attributes.size() < 512 || attributes.size() > 32 * 1024 * 1024) {
            throw new IllegalStateException("Unsupported native compiler output");
        }
        byte[] bytes;
        try (var input = Files.newInputStream(dll, LinkOption.NOFOLLOW_LINKS)) {
            bytes = input.readNBytes(32 * 1024 * 1024 + 1);
        }
        if (bytes.length != attributes.size()) throw new IllegalStateException("Native output size changed");
        String hash = HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(bytes));
        writeGenerated(getLibraryFile().get().getAsFile().toPath(), bytes);
        String receipt = "schema=1\nscope=COMPILER_BYTES_ONLY\nsource=" + source + "\ntree=" + tree +
            "\nsha256=" + hash + "\n";
        writeGenerated(getCompilerReceipt().get().getAsFile().toPath(),
            receipt.getBytes(java.nio.charset.StandardCharsets.US_ASCII));
    }

    private Path compilerCommand(Path recipe, Path destination) throws IOException {
        String programFiles = System.getenv("ProgramFiles(x86)");
        if (programFiles == null) {
            throw new IllegalStateException("Visual Studio installer inventory is unavailable");
        }
        Path vswhere = Path.of(programFiles, "Microsoft Visual Studio", "Installer", "vswhere.exe");
        if (!Files.isRegularFile(vswhere)) throw new IllegalStateException("Installed Visual Studio locator is missing");
        var output = new ByteArrayOutputStream() {
            @Override public synchronized void write(byte[] bytes, int offset, int length) {
                if (length > 8192 - size()) throw new IllegalStateException("Compiler inventory exceeds its bound");
                super.write(bytes, offset, length);
            }
            @Override public synchronized void write(int value) {
                if (size() == 8192) throw new IllegalStateException("Compiler inventory exceeds its bound");
                super.write(value);
            }
        };
        getExecOperations().exec(spec -> {
            spec.commandLine(vswhere.toString(), "-latest", "-products", "*", "-requires",
                "Microsoft.VisualStudio.Component.VC.Tools.x86.x64", "-property", "installationPath");
            spec.setStandardOutput(output);
        }).assertNormalExitValue();
        String installation = output.toString(java.nio.charset.StandardCharsets.UTF_8).strip();
        Path developer = Path.of(installation, "Common7", "Tools", "VsDevCmd.bat");
        if (installation.isEmpty() || !Files.isRegularFile(developer)) {
            throw new IllegalStateException("Installed x64 Native Tools environment is missing");
        }
        for (Path path : List.of(developer, recipe, destination, getJavaHome().get().getAsFile().toPath())) {
            String value = path.toString();
            if (!path.isAbsolute() || value.chars().anyMatch(c -> c < 32 || c > 126 ||
                c == '"' || c == '%' || c == '!' || c == '&' || c == '|' || c == '<' || c == '>' || c == '^')) {
                throw new IllegalStateException("Unsupported native compiler command path");
            }
        }
        String text = "@echo off\r\nsetlocal\r\n" +
            "set \"CL=\"\r\nset \"_CL_=\"\r\nset \"LINK=\"\r\nset \"_LINK_=\"\r\n" +
            "set \"INCLUDE=\"\r\nset \"LIB=\"\r\nset \"LIBPATH=\"\r\nset \"ERRORLEVEL=\"\r\n" +
            "call \"" + developer + "\" -arch=x64 -host_arch=x64\r\n" +
            "if errorlevel 1 exit /b 2\r\ncall \"" + recipe + "\" \"" + destination +
            "\"\r\nexit /b %ERRORLEVEL%\r\n";
        Path command = getTemporaryDir().toPath().resolve("compile-" + UUID.randomUUID() + ".cmd");
        Files.writeString(command, text, java.nio.charset.StandardCharsets.US_ASCII,
            java.nio.file.StandardOpenOption.CREATE_NEW);
        return command;
    }

    private static void writeGenerated(Path destination, byte[] bytes) throws IOException {
        // Only declared build outputs are replaced. Do not follow a pre-existing link or truncate another inode.
        Files.createDirectories(destination.getParent());
        if (Files.exists(destination, LinkOption.NOFOLLOW_LINKS) &&
            !Files.isRegularFile(destination, LinkOption.NOFOLLOW_LINKS)) {
            throw new IllegalStateException("Generated native output is not an ordinary file");
        }
        Path pending = Files.createTempFile(destination.getParent(), ".rpc-native-", ".pending");
        Files.write(pending, bytes);
        Files.move(pending, destination, StandardCopyOption.ATOMIC_MOVE, StandardCopyOption.REPLACE_EXISTING);
    }
}
