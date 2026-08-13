import dev.p2pkit.build.P2pPomMetadata
import kotlinx.validation.KotlinApiBuildTask
import org.jetbrains.kotlin.gradle.tasks.KotlinCompile

plugins {
    alias(libs.plugins.kotlin.multiplatform)
    alias(libs.plugins.android.kmp.library)
    alias(libs.plugins.dokka)
    `maven-publish`
}

kotlin {
    @OptIn(org.jetbrains.kotlin.gradle.dsl.abi.ExperimentalAbiValidation::class)
    abiValidation()

    jvmToolchain(17)

    android {
        // Preserve the published rc2 META-INF Kotlin module identity.
        compilerOptions.moduleName.set(project.name)
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

// Kotlin's built-in ABI validator excludes Android targets. Feed the
// supplemental metadata-aware guard from the compiler's declared output;
// flatMap retains producer ownership if Kotlin relocates that output.
val compileAndroidMain = tasks.named<KotlinCompile>("compileAndroidMain")
tasks.named<KotlinApiBuildTask>("buildAndroidAbi") {
    inputClassesDirs.from(compileAndroidMain.flatMap { it.destinationDirectory })
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

// AUDIT-2026-06: this provisioning sidecar was previously unpublishable
// (no `maven-publish`). The KMP + Android-KMP-library plugins auto-create the
// per-target publications once the plugin is applied; group/version come from
// the root `allprojects` block (io.github.apdelrahman1911 / VERSION_NAME) and signing is wired
// centrally in the root build. POM enriched here for Central-readiness.
publishing {
    publications.withType<MavenPublication>().configureEach {
        pom {
            name.set("P2pKit ${project.name}")
            description.set(
                "P2pKit Android network-provisioning sidecar — LocalOnlyHotspot host " +
                    "+ Wi-Fi join (NetworkProvisioningManager)."
            )
            P2pPomMetadata.configure(this)
        }
    }
}
