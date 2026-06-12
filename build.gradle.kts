import org.gradle.api.publish.PublishingExtension
import org.gradle.api.publish.maven.tasks.AbstractPublishToMaven
import org.gradle.plugins.signing.Sign
import org.gradle.plugins.signing.SigningExtension

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
// AUDIT-2026-06: `maven-publish` now ships on all four library modules
// (:p2p-core, :p2p-transport-lan, :p2p-network-provisioning-android,
// :p2p-network-provisioning-desktop). Per-module POM metadata lives in each
// module's own build script; signing is wired centrally below.
allprojects {
    group = (findProperty("GROUP") as String?) ?: "dev.p2pkit"
    version = (findProperty("VERSION_NAME") as String?) ?: "0.0.0-SNAPSHOT"
}

// AUDIT-2026-06 / RC-readiness: wire artifact signing + a robust publish→sign
// task dependency for every module that publishes (those applying
// `maven-publish`). Centralized here so the four library modules stay identical
// and only their POM differs.
//
// Signing is REQUIRED only when a PGP key is supplied via Gradle properties or
// env vars (`ORG_GRADLE_PROJECT_signingInMemoryKey[+Password]` → the
// `signingInMemoryKey[+Password]` project properties). So `publishToMavenLocal`
// and ordinary dev/CI builds need no keys and are unaffected (Sign tasks are
// skipped); a Maven Central release just sets those two properties. See
// docs/STABILIZATION_AND_RELEASE.md for the release recipe.
subprojects {
    val sub = this
    plugins.withId("maven-publish") {
        sub.apply(plugin = "signing")
        val publishing = sub.extensions.getByType(PublishingExtension::class.java)
        sub.extensions.configure(SigningExtension::class.java) {
            val signingKey = sub.findProperty("signingInMemoryKey") as String?
            val signingPassword = sub.findProperty("signingInMemoryKeyPassword") as String?
            isRequired = signingKey != null
            if (signingKey != null) {
                useInMemoryPgpKeys(signingKey, signingPassword)
            }
            // Live collection — also covers KMP's per-target publications,
            // which the multiplatform plugin creates lazily in afterEvaluate.
            sign(publishing.publications)
        }
        // Gradle flags sign→publish ordering unless declared. Make every publish
        // task depend on all Sign tasks so `publish` works without the "uses
        // output of task … without declaring dependency" execution error.
        sub.tasks.withType(AbstractPublishToMaven::class.java).configureEach {
            dependsOn(sub.tasks.withType(Sign::class.java))
        }
    }
}
