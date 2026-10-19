package dev.p2pkit.build;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Properties;
import javax.inject.Inject;
import org.gradle.api.DefaultTask;
import org.gradle.api.file.DirectoryProperty;
import org.gradle.api.tasks.InputDirectory;
import org.gradle.api.tasks.Internal;
import org.gradle.api.tasks.OutputDirectory;
import org.gradle.api.tasks.PathSensitive;
import org.gradle.api.tasks.PathSensitivity;
import org.gradle.api.tasks.TaskAction;
import org.gradle.process.ExecOperations;
import org.gradle.work.DisableCachingByDefault;

/** The Android KMP plugin has no externalNativeBuild DSL. Register its JNI source output through AGP. */
@DisableCachingByDefault(because = "Uses the locally installed, pinned Android NDK")
public abstract class BuildAndroidLanSocketsTask extends DefaultTask {
    public static final String NDK_VERSION = "29.0.14206865";
    @Inject protected abstract ExecOperations getExecOperations();
    @Internal public abstract DirectoryProperty getSdkDirectory();
    @InputDirectory @PathSensitive(PathSensitivity.RELATIVE)
    public abstract DirectoryProperty getSourceDirectory();
    @OutputDirectory public abstract DirectoryProperty getJniDirectory();

    public BuildAndroidLanSocketsTask() {
        // Toolchain files can change outside Gradle. Never reuse an output solely from its source timestamp.
        getOutputs().upToDateWhen(task -> false);
        getTimeout().set(java.time.Duration.ofMinutes(2));
    }

    @TaskAction public void compile() throws IOException {
        Path ndk = getSdkDirectory().get().getAsFile().toPath().resolve("ndk").resolve(NDK_VERSION);
        Properties properties = new Properties();
        try (var input = Files.newInputStream(ndk.resolve("source.properties"))) { properties.load(input); }
        if (!NDK_VERSION.equals(properties.getProperty("Pkg.Revision"))) {
            throw new IllegalStateException("Install Android NDK " + NDK_VERSION + " with sdkmanager");
        }
        String os = System.getProperty("os.name");
        String host = os.startsWith("Windows") ? "windows-x86_64" :
            os.equals("Mac OS X") ? "darwin-x86_64" : os.equals("Linux") ? "linux-x86_64" : null;
        if (host == null) throw new IllegalStateException("Unsupported Android NDK build host");
        Path clang = ndk.resolve("toolchains/llvm/prebuilt").resolve(host)
            .resolve("bin").resolve(os.startsWith("Windows") ? "clang.exe" : "clang");
        var targets = new LinkedHashMap<String, String>();
        targets.put("arm64-v8a", "aarch64-linux-android24");
        targets.put("armeabi-v7a", "armv7a-linux-androideabi24");
        targets.put("x86", "i686-linux-android24");
        targets.put("x86_64", "x86_64-linux-android24");
        for (var target : targets.entrySet()) {
            Path output = getJniDirectory().get().getAsFile().toPath().resolve(target.getKey());
            Files.createDirectories(output);
            List<String> command = List.of(clang.toString(), "--target=" + target.getValue(),
                "-std=c11", "-D_GNU_SOURCE", "-O2", "-fPIC", "-shared", "-Wall", "-Wextra", "-Werror",
                "-fvisibility=hidden", "-fstack-protector-strong", "-Wl,--no-undefined",
                "-Wl,-z,relro,-z,now,-z,noexecstack,-z,max-page-size=16384",
                "-Wl,-soname,libp2pkit_lan_sockets.so",
                getSourceDirectory().get().getAsFile().toPath().resolve("sockets.c").toString(),
                "-o", output.resolve("libp2pkit_lan_sockets.so").toString());
            getExecOperations().exec(spec -> spec.commandLine(command)).assertNormalExitValue();
        }
    }
}
