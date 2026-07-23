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

    // The maintained Alice/Bob IDE configurations must share the same appId
    // (otherwise they cannot discover each other) while persisting different
    // PeerIds. A named profile gives each child JVM a stable, separate home
    // beneath the operator's real home without changing CLI defaults.
    providers.gradleProperty("p2pkit.sample.identityProfile").orNull?.let { profile ->
        require(profile.matches(Regex("[A-Za-z0-9_-]{1,32}"))) {
            "p2pkit.sample.identityProfile must match [A-Za-z0-9_-]{1,32}"
        }
        val realHome = providers.systemProperty("user.home").orNull
            ?.takeIf { it.isNotBlank() }
            ?: error("A nonblank user.home is required for a named sample identity profile")
        val profileHome = file("$realHome/.p2pkit/sample-profiles/$profile")
        doFirst {
            check(profileHome.isDirectory || profileHome.mkdirs()) {
                "Could not create sample identity profile directory $profileHome"
            }
        }
        systemProperty("user.home", profileHome.absolutePath)
    }
}

kotlin {
    jvmToolchain(17)
}

dependencies {
    implementation(project(":p2p-core"))
    implementation(project(":p2p-transport-lan"))
    implementation(project(":p2p-network-provisioning-desktop"))
    implementation(project(":p2p-sample-diagnostics"))
    implementation(libs.kotlinx.coroutines.core)
    // Silence JmDNS's SLF4J "no provider" warning on startup. No-op logger;
    // JmDNS's own log messages are simply discarded.
    // AUDIT-2026-06: coordinate via the version catalog instead of a hardcoded literal.
    runtimeOnly(libs.slf4j.nop)
    testImplementation(kotlin("test"))
}
