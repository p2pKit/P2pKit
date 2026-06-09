plugins {
    alias(libs.plugins.kotlin.multiplatform) apply false
    alias(libs.plugins.kotlin.jvm) apply false
    alias(libs.plugins.kotlin.serialization) apply false
    alias(libs.plugins.kotlin.compose) apply false
    alias(libs.plugins.android.application) apply false
    alias(libs.plugins.android.kmp.library) apply false
    alias(libs.plugins.jetbrains.compose) apply false
}

// Establish Maven coordinates for every module from the single source of truth
// in gradle.properties (GROUP / VERSION_NAME). Applying a publishing plugin to
// the library modules then produces artifacts at dev.p2pkit:<module>:<version>.
// See PROBLEMS_P2PKIT.md → no-publishing-plugin for the remaining publish wiring.
allprojects {
    group = (findProperty("GROUP") as String?) ?: "dev.p2pkit"
    version = (findProperty("VERSION_NAME") as String?) ?: "0.0.0-SNAPSHOT"
}
