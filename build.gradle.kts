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
// in gradle.properties (GROUP / VERSION_NAME), producing artifacts at
// dev.p2pkit:<module>:<version>.
// AUDIT-2026-06: the `maven-publish` plugin is currently applied to :p2p-core
// and :p2p-transport-lan only; the :p2p-network-provisioning-* sidecars still
// need it wired before they can be published (see AUDIT_REPORT_2026-06.md).
allprojects {
    group = (findProperty("GROUP") as String?) ?: "dev.p2pkit"
    version = (findProperty("VERSION_NAME") as String?) ?: "0.0.0-SNAPSHOT"
}
