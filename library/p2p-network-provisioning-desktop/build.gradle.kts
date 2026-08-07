plugins {
    alias(libs.plugins.kotlin.jvm)
    alias(libs.plugins.dokka)
    `maven-publish`
}

kotlin {
    @OptIn(org.jetbrains.kotlin.gradle.dsl.abi.ExperimentalAbiValidation::class)
    abiValidation {
        enabled.set(true)
    }

    jvmToolchain(17)
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
                url.set("https://github.com/p2pKit/P2pKit")
                licenses {
                    license {
                        name.set("The Apache License, Version 2.0")
                        url.set("https://www.apache.org/licenses/LICENSE-2.0.txt")
                    }
                }
                developers {
                    developer {
                        id.set("Apdelrahman1911")
                        name.set("Abdelrahman")
                    }
                }
                scm {
                    url.set("https://github.com/p2pKit/P2pKit")
                    connection.set("scm:git:https://github.com/p2pKit/P2pKit.git")
                    developerConnection.set("scm:git:ssh://git@github.com/p2pKit/P2pKit.git")
                }
            }
        }
    }
}
