package dev.p2pkit.sample.diagnostics

import java.nio.file.Files
import javax.tools.ToolProvider

/** Classloader-local SDK constant; no fake android.os.Build enters the ordinary test classpath. */
internal fun syntheticAndroidSdkClasses(sdk: Int): Map<String, ByteArray> {
    require(sdk == 24 || sdk == 25)
    val directory = Files.createTempDirectory("p2pkit-synthetic-sdk").toFile()
    try {
        val source = directory.resolve("Build.java").apply {
            writeText(
                "package android.os; public final class Build { " +
                    "public static final class VERSION { public static final int SDK_INT = $sdk; } }"
            )
        }
        // The JDK compiler runs in this test JVM: no subprocess, daemon or shared output directory.
        val compiler = requireNotNull(ToolProvider.getSystemJavaCompiler()) { "Diagnostic tests require JDK 17" }
        check(compiler.run(null, null, null, "--release", "8", "-d", directory.path, source.path) == 0)
        return listOf("android.os.Build", "android.os.Build\$VERSION").associateWith {
            directory.resolve(it.replace('.', '/') + ".class").readBytes()
        }
    } finally {
        check(directory.deleteRecursively()) { "Could not clean synthetic SDK compiler outputs" }
    }
}
