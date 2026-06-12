import org.jetbrains.compose.desktop.application.dsl.TargetFormat

plugins {
    alias(libs.plugins.kotlin.jvm)
    alias(libs.plugins.kotlin.compose)
    alias(libs.plugins.jetbrains.compose)
}

kotlin {
    jvmToolchain(17)
}

dependencies {
    implementation(project(":p2p-core"))
    implementation(project(":p2p-transport-lan"))
    implementation(project(":p2p-network-provisioning-desktop"))
    implementation(libs.kotlinx.coroutines.core)

    implementation(compose.desktop.currentOs)
    implementation(compose.material3)
    implementation(compose.materialIconsExtended)

    // Silence JmDNS's SLF4J "no provider" warning on startup.
    // AUDIT-2026-06 (BUILD-G10-11): coordinates moved to the version catalog.
    runtimeOnly(libs.slf4j.nop)
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
