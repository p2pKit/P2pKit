import org.gradle.api.publish.PublishingExtension
import org.gradle.api.publish.maven.MavenPublication
import org.gradle.api.publish.maven.tasks.AbstractPublishToMaven
import org.gradle.api.tasks.compile.JavaCompile
import org.gradle.jvm.tasks.Jar
import org.gradle.plugins.signing.Sign
import org.gradle.plugins.signing.SigningExtension
import org.cyclonedx.gradle.CyclonedxDirectTask
import org.jetbrains.kotlin.gradle.tasks.KotlinCompilationTask

plugins {
    alias(libs.plugins.kotlin.multiplatform) apply false
    alias(libs.plugins.kotlin.jvm) apply false
    alias(libs.plugins.kotlin.serialization) apply false
    alias(libs.plugins.kotlin.compose) apply false
    alias(libs.plugins.android.application) apply false
    alias(libs.plugins.android.kmp.library) apply false
    alias(libs.plugins.jetbrains.compose) apply false
    alias(libs.plugins.dokka) apply false
    alias(libs.plugins.cyclonedx)
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

    // REL-SUPPLY-01 (BUILD-06): every resolvable project configuration uses
    // committed lock state. The maintenance task below refreshes all locks in
    // one explicit --write-locks operation; ordinary builds never rewrite it.
    dependencyLocking {
        lockAllConfigurations()
    }

    // The aggregate release SBOM describes the four published libraries, not
    // sample applications, compiler toolchains, test engines, or build-system
    // internals. Narrow inputs to one runtime graph per published module and
    // disable the direct BOM task everywhere else.
    tasks.withType(CyclonedxDirectTask::class.java).configureEach {
        val releaseConfigurations = when (project.path) {
            ":p2p-core", ":p2p-transport-lan" -> listOf("jvmRuntimeClasspath")
            ":p2p-network-provisioning-android" -> listOf("androidRuntimeClasspath")
            ":p2p-network-provisioning-desktop" -> listOf("runtimeClasspath")
            else -> null
        }
        if (releaseConfigurations == null) {
            enabled = false
        } else {
            includeConfigs.set(releaseConfigurations)
            includeMetadataResolution.set(false)
            includeBuildEnvironment.set(false)
        }
    }
}

val resolveAndLockRequested = gradle.startParameter.taskNames.any {
    it == "resolveAndLockAll" || it.endsWith(":resolveAndLockAll")
}
if (resolveAndLockRequested && !gradle.startParameter.isWriteDependencyLocks) {
    error("resolveAndLockAll must be invoked with --write-locks")
}

tasks.register("resolveAndLockAll") {
    group = "build setup"
    description = "Runs every dependency-consuming gate; invoke only with --write-locks."
    doFirst {
        check(gradle.startParameter.isWriteDependencyLocks) {
            "resolveAndLockAll must be invoked with --write-locks"
        }
    }
    dependsOn(
        "cyclonedxBom",
        ":p2p-core:check",
        ":p2p-transport-lan:check",
        ":p2p-network-provisioning-android:check",
        ":p2p-network-provisioning-desktop:check",
        ":p2p-sample-android:check",
        ":p2p-sample-desktop:check",
        ":p2p-sample-desktop-ui:check",
        ":sample-kmp-shared:check",
        ":p2p-core:dokkaGeneratePublicationHtml",
        ":p2p-transport-lan:dokkaGeneratePublicationHtml",
        ":p2p-network-provisioning-android:dokkaGeneratePublicationHtml",
        ":p2p-network-provisioning-desktop:dokkaGeneratePublicationHtml",
    )
}

tasks.cyclonedxBom {
    projectType.set(org.cyclonedx.model.Component.Type.LIBRARY)
    componentGroup = project.group.toString()
    componentName = rootProject.name
    componentVersion = project.version.toString()
    includeBomSerialNumber = false
    includeBuildSystem = false
    includeLicenseText = false
    jsonOutput.set(layout.buildDirectory.file("reports/cyclonedx/bom.json"))
    xmlOutput.set(layout.buildDirectory.file("reports/cyclonedx/bom.xml"))
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

    // REL-GATE-01 (BUILD-14): warnings are regressions, not informational
    // output. Apply this to every Kotlin target (including common tests and
    // native compilations) and to Java sources such as Android/buildSrc-facing
    // helpers. Gradle's own deprecation warnings are promoted separately in
    // gradle.properties.
    tasks.withType(KotlinCompilationTask::class.java).configureEach {
        compilerOptions.allWarningsAsErrors.set(true)
    }
    tasks.withType(JavaCompile::class.java).configureEach {
        options.compilerArgs.add("-Werror")
    }

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

        // REL-SUPPLY-01 (BUILD-13): every published variant gets real Dokka
        // Javadoc rather than a formally present but empty archive. One Jar
        // per publication keeps signing outputs disjoint even though all jars
        // consume the same module-level Dokka output.
        plugins.withId("org.jetbrains.dokka") {
            publishing.publications.withType(MavenPublication::class.java).configureEach {
                val publicationName = name
                val javadocJar = sub.tasks.register(
                    "${publicationName}DokkaJavadocJar",
                    Jar::class.java,
                ) {
                    dependsOn("dokkaGeneratePublicationHtml")
                    from(sub.layout.buildDirectory.dir("dokka/html"))
                    archiveClassifier.set("javadoc")
                    archiveAppendix.set(publicationName.lowercase())
                }
                artifact(javadocJar)
            }
        }
    }
}
