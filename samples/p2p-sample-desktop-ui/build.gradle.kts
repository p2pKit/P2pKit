import org.jetbrains.compose.desktop.application.dsl.TargetFormat

plugins {
    alias(libs.plugins.kotlin.jvm)
    alias(libs.plugins.kotlin.compose)
    alias(libs.plugins.jetbrains.compose)
}

kotlin {
    jvmToolchain(17)
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
