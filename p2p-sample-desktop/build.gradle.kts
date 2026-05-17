plugins {
    alias(libs.plugins.kotlin.jvm)
    application
}

application {
    mainClass.set("dev.p2pkit.sample.desktop.MainKt")
}

// Forward Android Studio's Run console stdin into the CLI's `readLine()`
// loop. Without this, running `:p2p-sample-desktop:run` from the IDE hangs
// at the first prompt because the spawned JVM gets a closed System.in.
tasks.named<JavaExec>("run") {
    standardInput = System.`in`
}

kotlin {
    jvmToolchain(17)
}

dependencies {
    implementation(project(":p2p-core"))
    implementation(project(":p2p-transport-lan"))
    implementation(project(":p2p-network-provisioning-desktop"))
    implementation(libs.kotlinx.coroutines.core)
    // Silence JmDNS's SLF4J "no provider" warning on startup. No-op logger;
    // JmDNS's own log messages are simply discarded.
    runtimeOnly("org.slf4j:slf4j-nop:2.0.13")
}
