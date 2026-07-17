plugins {
    alias(libs.plugins.kotlin.multiplatform)
    alias(libs.plugins.android.kmp.library)
    `maven-publish`
}

kotlin {
    jvmToolchain(17)

    android {
        namespace = "dev.p2pkit.provisioning.android"
        compileSdk = libs.versions.android.compileSdk.get().toInt()
        minSdk = libs.versions.android.minSdk.get().toInt()
        withHostTest { }
    }

    sourceSets {
        androidMain.dependencies {
            api(project(":p2p-core"))
            api(libs.kotlinx.coroutines.core)
        }
        getByName("androidHostTest").dependencies {
            implementation(kotlin("test"))
            implementation(libs.kotlinx.coroutines.test)
        }
    }
}

// AUDIT-2026-06: this provisioning sidecar was previously unpublishable
// (no `maven-publish`). The KMP + Android-KMP-library plugins auto-create the
// per-target publications once the plugin is applied; group/version come from
// the root `allprojects` block (dev.p2pkit / VERSION_NAME) and signing is wired
// centrally in the root build. POM enriched here for Central-readiness.
publishing {
    publications.withType<MavenPublication>().configureEach {
        pom {
            name.set("P2pKit ${project.name}")
            description.set(
                "P2pKit Android network-provisioning sidecar — LocalOnlyHotspot host " +
                    "+ Wi-Fi join (NetworkProvisioningManager)."
            )
            url.set("https://github.com/Apdelrahman1911/P2pKit")
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
                url.set("https://github.com/Apdelrahman1911/P2pKit")
                connection.set("scm:git:https://github.com/Apdelrahman1911/P2pKit.git")
                developerConnection.set("scm:git:ssh://git@github.com/Apdelrahman1911/P2pKit.git")
            }
        }
    }
}
