import dev.p2pkit.build.P2pPomMetadata

plugins {
    alias(libs.plugins.kotlin.jvm)
    alias(libs.plugins.dokka)
    `maven-publish`
}

kotlin {
    @OptIn(org.jetbrains.kotlin.gradle.dsl.abi.ExperimentalAbiValidation::class)
    abiValidation()

    jvmToolchain(17)
    // Retain rc2's published META-INF module identity under Kotlin 2.4.
    compilerOptions.moduleName.set(project.name)
}

// Sources are supplied by the Java component; real Dokka Javadoc is attached
// centrally to each publication by the root build.
java {
    withSourcesJar()
}

dokka {
    dokkaPublications.html {
        moduleName.set(project.name)
        moduleVersion.set(project.version.toString())
        outputDirectory.set(layout.buildDirectory.dir("dokka/html"))
        failOnWarning.set(true)
        // Release artifacts must not depend on remote package-list availability.
        offlineMode.set(true)
    }
}

dependencies {
    api(project(":p2p-core"))
    api(libs.kotlinx.coroutines.core)

    testImplementation(kotlin("test"))
    testImplementation(project(":p2p-transport-lan"))
    testImplementation(libs.kotlinx.coroutines.test)
    testImplementation(libs.kotlinx.coroutines.core)
}

// AUDIT-2026-06: this provisioning sidecar was previously unpublishable
// (no `maven-publish`). Plain Kotlin/JVM modules don't auto-create a
// publication, so register one from the `java` component; group/version come
// from the root `allprojects` block and signing is wired centrally in the root
// build. POM enriched here for Central-readiness.
publishing {
    publications {
        create<MavenPublication>("maven") {
            from(components["java"])
            pom {
                name.set("P2pKit ${project.name}")
                description.set(
                    "P2pKit desktop network-provisioning sidecar — manual-IP fallback " +
                        "(NetworkProvisioningManager) for mDNS-blocked LANs on JVM."
                )
                P2pPomMetadata.configure(this)
            }
        }
    }
}
