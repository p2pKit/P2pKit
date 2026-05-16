plugins {
    alias(libs.plugins.kotlin.jvm)
    application
}

application {
    mainClass.set("dev.p2pkit.sample.desktop.MainKt")
}

kotlin {
    jvmToolchain(17)
}

dependencies {
    implementation(project(":p2p-core"))
    implementation(project(":p2p-transport-lan"))
    implementation(libs.kotlinx.coroutines.core)
    // Silence JmDNS's SLF4J "no provider" warning on startup. No-op logger;
    // JmDNS's own log messages are simply discarded.
    runtimeOnly("org.slf4j:slf4j-nop:2.0.13")
}
