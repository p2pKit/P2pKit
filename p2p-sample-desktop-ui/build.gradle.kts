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
    implementation(libs.kotlinx.coroutines.core)

    implementation(compose.desktop.currentOs)
    implementation(compose.material3)
    implementation(compose.materialIconsExtended)

    // Silence JmDNS's SLF4J "no provider" warning on startup.
    runtimeOnly("org.slf4j:slf4j-nop:2.0.13")
}

compose.desktop {
    application {
        mainClass = "dev.p2pkit.sample.desktop.ui.MainKt"

        nativeDistributions {
            targetFormats(TargetFormat.Exe, TargetFormat.Msi, TargetFormat.Dmg, TargetFormat.Deb)
            packageName = "P2pKit Sample"
            packageVersion = "1.0.0" // installer version; jpackage requires MAJOR > 0
            description = "P2pKit v0.2 desktop sample (room broadcast)"
        }
    }
}
