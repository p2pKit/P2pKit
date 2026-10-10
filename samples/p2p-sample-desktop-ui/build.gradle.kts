import dev.p2pkit.build.GitCommitValueSource
import org.jetbrains.compose.desktop.application.dsl.TargetFormat
import org.jetbrains.compose.desktop.application.tasks.AbstractJPackageTask

plugins {
    alias(libs.plugins.kotlin.jvm)
    alias(libs.plugins.kotlin.compose)
    alias(libs.plugins.jetbrains.compose)
}

kotlin {
    jvmToolchain(17)
}

// Gradle -D properties are not automatically inherited by the sample JVM.
// Forward explicit operator opt-ins without changing packaged-app defaults.
tasks.withType<JavaExec>().matching { it.name == "run" }.configureEach {
    for (property in listOf("dev.p2pkit.lan.trace", "dev.p2pkit.lan.traceFrames")) {
        providers.systemProperty(property).orNull?.let { systemProperty(property, it) }
    }
}

tasks.withType<Test>().configureEach {
    doFirst {
        // Forked property probes need the declared runtime classpath, not
        // Gradle worker ClassLoader implementation details.
        systemProperty("dev.p2pkit.sample.test.runtimeClasspath", classpath.asPath)
    }
}

val supportedDesktopLockTargets = setOf(
    "linux-arm64",
    "linux-x64",
    "macos-arm64",
    "macos-x64",
    "windows-arm64",
    "windows-x64"
)
val detectedDesktopLockTarget = run {
    val os = System.getProperty("os.name").lowercase()
    val architecture = when (System.getProperty("os.arch").lowercase()) {
        "aarch64", "arm64" -> "arm64"
        "amd64", "x64", "x86_64" -> "x64"
        else -> error("Unsupported Desktop architecture: ${System.getProperty("os.arch")}")
    }
    val platform = when {
        os.contains("mac") || os.contains("darwin") -> "macos"
        os.contains("linux") -> "linux"
        os.contains("windows") -> "windows"
        else -> error("Unsupported Desktop operating system: ${System.getProperty("os.name")}")
    }
    "$platform-$architecture"
}
val desktopLockTarget =
    providers.gradleProperty("p2pkit.desktop.lockTarget").orNull ?: detectedDesktopLockTarget
require(desktopLockTarget in supportedDesktopLockTargets) {
    "p2pkit.desktop.lockTarget must be one of ${supportedDesktopLockTargets.sorted()}"
}
val composeDesktopRuntime = when (desktopLockTarget) {
    "linux-arm64" -> libs.jetbrains.compose.desktop.linux.arm64
    "linux-x64" -> libs.jetbrains.compose.desktop.linux.x64
    "macos-arm64" -> libs.jetbrains.compose.desktop.macos.arm64
    "macos-x64" -> libs.jetbrains.compose.desktop.macos.x64
    "windows-arm64" -> libs.jetbrains.compose.desktop.windows.arm64
    "windows-x64" -> libs.jetbrains.compose.desktop.windows.x64
    else -> error("Unsupported Desktop target: $desktopLockTarget")
}

// The override is a dependency-resolution seam for regenerating and checking
// all platform verification metadata from one host. Never run or package a
// foreign runtime as though it belonged to the current machine.
val currentHostOnlyDesktopTasks = setOf(
    "run",
    "runHot",
    "hotRun",
    "hotRunAsync",
    "hotDev",
    "hotDevAsync",
    "test"
)
tasks.matching { task ->
    task.name in currentHostOnlyDesktopTasks ||
        task.name.contains("Distributable") ||
        task.name.startsWith("package")
}.configureEach {
    doFirst {
        check(desktopLockTarget == detectedDesktopLockTarget) {
            "p2pkit.desktop.lockTarget is for dependency resolution only; " +
                "cannot execute $name for $desktopLockTarget on $detectedDesktopLockTarget"
        }
    }
}

dependencies {
    implementation(project(":p2p-core"))
    implementation(project(":p2p-transport-lan"))
    implementation(project(":p2p-network-provisioning-desktop"))
    implementation(project(":p2p-sample-diagnostics"))
    implementation(project(":p2p-sample-rpc"))
    implementation(libs.kotlinx.coroutines.core)

    implementation(composeDesktopRuntime)
    // The Compose plugin dependency shorthands for these artifacts are
    // deprecated. Pin their currently resolved coordinates in the catalog so
    // configuration stays warning-free without changing the runtime graph.
    implementation(libs.jetbrains.compose.material3)
    implementation(libs.jetbrains.compose.material.icons.extended)

    // Silence JmDNS's SLF4J "no provider" warning on startup.
    // AUDIT-2026-06 (BUILD-G10-11): coordinates moved to the version catalog.
    runtimeOnly(libs.slf4j.nop)

    // 2026-07 (P1-32 / SMP-1): minimal test wiring for the sample's shared
    // incoming-file destination-uniquification helper (UniqueSaveFileTest).
    // This module previously had no test source set; samples are unpublished
    // test harnesses, so this stays out of the published dependency graph.
    testImplementation(kotlin("test"))
}

// Private Gradle execution and packaged development apps use distinct admission policies.
// Neither path claims Developer ID/notarization or substitutes a new release pipeline.
if (detectedDesktopLockTarget == "macos-arm64") {
    val sourceCommit = providers.of(GitCommitValueSource::class) {
        parameters.rootDirectory.set(rootProject.layout.projectDirectory)
    }
    val nativeDirectory = project(":p2p-transport-lan").layout.buildDirectory.dir(
        sourceCommit.map { "macos-tcp/$it" },
    )
    tasks.withType<JavaExec>().matching { it.name == "run" }.configureEach {
        dependsOn(":p2p-transport-lan:stageMacTcp")
        classpath(files(nativeDirectory.map { it.file("p2pkit-macos-tcp-manifest.jar") }))
        systemProperty("dev.p2pkit.lan.macos.nativeDir", nativeDirectory.get().asFile.absolutePath)
    }

    val finalizedDirectory = layout.buildDirectory.dir(sourceCommit.map { "rpc-macos-app-image/$it" })
    val finalizedApp = finalizedDirectory.map { it.dir("P2pKit Sample.app") }
    val finalizationReceipt = finalizedDirectory.map { it.file("native-finalization.json") }
    val finalizer = rootProject.layout.projectDirectory.file("scripts/stage-rpc-macos-app.py")
    val originalApp = providers.provider {
        tasks.named<AbstractJPackageTask>("createDistributable").get().destinationDir.get().dir("P2pKit Sample.app")
    }
    val finalizeRpcMacosDevelopmentApp = tasks.register<Exec>("finalizeRpcMacosDevelopmentApp") {
        group = "distribution"
        description = "Finalizes an owned development-ad-hoc copy for the existing DMG producer; never publishes."
        // Declare these before lazy package-task configuration: requesting this task alone must realize its producer.
        dependsOn("createDistributable", ":p2p-transport-lan:stageMacTcp")
        inputs.file(finalizer)
        inputs.dir(nativeDirectory)
        inputs.dir(originalApp)
        inputs.property("sourceCommit", sourceCommit)
        // Gradle may pre-create declared output directories; the helper must create the .app itself.
        outputs.dir(finalizedDirectory)
        outputs.file(finalizationReceipt)
        executable = "python3"
        argumentProviders.add(CommandLineArgumentProvider {
            listOf("-I", "-S", "-B", finalizer.asFile.absolutePath,
                "--root", rootProject.projectDir.absolutePath,
                "--input-app", originalApp.get().asFile.absolutePath,
                "--output-app", finalizedApp.get().asFile.absolutePath,
                "--native-stage", nativeDirectory.get().asFile.absolutePath,
                "--receipt", finalizationReceipt.get().asFile.absolutePath,
                "--policy", "development-adhoc-v1")
        })
        // Gradle creates the declared output parent; the helper validates it before use.
    }
    tasks.withType<AbstractJPackageTask>().configureEach {
        if (name == "createDistributable") {
            dependsOn(":p2p-transport-lan:stageMacTcp")
            files.from(nativeDirectory.map { it.file("p2pkit-macos-tcp-manifest.jar") })
            launcherJvmArgs.add("-Ddev.p2pkit.lan.macos.installedPolicy=development-adhoc-v1")
        }
        if (name == "packageDmg") {
            dependsOn(finalizeRpcMacosDevelopmentApp)
            // Compose expects the producer's parent directory and appends .app for the active JDK.
            appImage.set(finalizedDirectory)
        }
    }
}

compose.desktop {
    application {
        mainClass = "dev.p2pkit.sample.desktop.ui.MainKt"

        nativeDistributions {
            targetFormats(TargetFormat.Exe, TargetFormat.Msi, TargetFormat.Dmg, TargetFormat.Deb)
            packageName = "P2pKit Sample"
            packageVersion = "1.0.0" // installer version; jpackage requires MAJOR > 0
            // AUDIT-2026-06 (BUILD-G10-12): derive from the project version
            // (gradle.properties VERSION_NAME) instead of a stale literal.
            description = "P2pKit ${project.version} desktop sample (room broadcast + file transfer)"
        }
    }
}
