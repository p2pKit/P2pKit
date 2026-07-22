import dev.p2pkit.build.GenerateBuildInfoTask
import dev.p2pkit.build.GitCommitTimeValueSource
import dev.p2pkit.build.GitCommitValueSource
import dev.p2pkit.build.GitDirtyValueSource
import dev.p2pkit.build.VerifyBuildInfoTask

plugins {
    alias(libs.plugins.kotlin.multiplatform)
    alias(libs.plugins.kotlin.serialization)
    alias(libs.plugins.android.kmp.library)
    alias(libs.plugins.cryptography)
    alias(libs.plugins.dokka)
    `maven-publish`
}

cryptography {
    // cryptography-kotlin's CryptoKit provider is implemented through Swift
    // interop. Resolve the active Xcode toolchain rather than baking in an
    // /Applications/Xcode.app linker path.
    configureSwiftLinkerOpts = true
}

// V0.4-PROVENANCE (L1): generate a BuildInfo Kotlin object containing the
// current git commit / relevant dirty flag / commit time. The constants are
// compiled into the framework binary, so they identify the artifact
// unambiguously regardless of how it was packaged. Wired into commonMain
// below via `kotlin.srcDir(generateBuildInfo)`.
//
// Git values are declared task inputs. Gradle therefore checks them when it
// evaluates task freshness, but does not rewrite the generated source or
// invalidate Kotlin compilation when the commit and relevant source state are
// unchanged. Checkout-local branch names and wall-clock build times are not
// embedded: two clean builds of the same commit produce the same BuildInfo.
val buildInfoGitCommit = providers.of(GitCommitValueSource::class) {
    parameters.rootDirectory.set(rootProject.layout.projectDirectory)
}

val buildInfoCommitTime = providers.of(GitCommitTimeValueSource::class) {
    parameters.rootDirectory.set(rootProject.layout.projectDirectory)
}

val buildInfoRelevantPaths = listOf(
    "buildSrc/src/main/java/dev/p2pkit/build",
    "p2p-core/src",
    "p2p-core/build.gradle.kts",
    "build.gradle.kts",
    "settings.gradle.kts",
    "gradle.properties",
    "gradle/libs.versions.toml",
    "gradle/wrapper/gradle-wrapper.properties",
)
val buildInfoDirty = providers.of(GitDirtyValueSource::class) {
    parameters.rootDirectory.set(rootProject.layout.projectDirectory)
    parameters.relevantPaths.set(buildInfoRelevantPaths)
}

val generateBuildInfo by tasks.registering(GenerateBuildInfoTask::class) {
    sourceCommit.set(buildInfoGitCommit)
    sourceCommitTime.set(buildInfoCommitTime)
    relevantSourceDirty.set(buildInfoDirty)
    outputDirectory.set(layout.buildDirectory.dir("generated/buildinfo/commonMain/kotlin"))
}

val verifyBuildInfoReproducibility by tasks.registering(VerifyBuildInfoTask::class) {
    group = "verification"
    description = "Verifies that generated BuildInfo contains only stable source provenance."
    dependsOn(generateBuildInfo)
    generatedFile.set(
        generateBuildInfo.flatMap { task ->
            task.outputDirectory.file("dev/p2pkit/core/BuildInfo.kt")
        },
    )
    sourceCommit.set(buildInfoGitCommit)
    sourceCommitTime.set(buildInfoCommitTime)
    relevantSourceDirty.set(buildInfoDirty)
}

kotlin {
    @OptIn(org.jetbrains.kotlin.gradle.dsl.abi.ExperimentalAbiValidation::class)
    abiValidation {
        enabled.set(true)
    }

    jvmToolchain(17)
    jvm()

    android {
        namespace = "dev.p2pkit.core"
        compileSdk = libs.versions.android.compileSdk.get().toInt()
        minSdk = libs.versions.android.minSdk.get().toInt()
    }

    // Core types compile for iOS; the iOS LAN/TCP transport (Bonjour +
    // Network.framework) ships in :p2p-transport-lan's appleMain source set.
    iosX64()
    iosArm64()
    iosSimulatorArm64()

    sourceSets {
        commonMain {
            kotlin.srcDir(generateBuildInfo)
            dependencies {
                api(libs.kotlinx.coroutines.core)
                implementation(libs.kotlinx.serialization.json)
                implementation(libs.cryptography.core)
                api(libs.kotlinx.io.core)
            }
        }
        jvmMain.dependencies {
            implementation(libs.cryptography.provider.jdk)
            implementation(libs.bouncycastle.provider)
        }
        androidMain.dependencies {
            implementation(libs.cryptography.provider.jdk)
            implementation(libs.bouncycastle.provider)
        }
        iosMain.dependencies {
            implementation(libs.cryptography.provider.cryptokit)
        }
        commonTest.dependencies {
            implementation(kotlin("test"))
            implementation(libs.kotlinx.coroutines.test)
        }
    }
}

dokka {
    dokkaPublications.html {
        moduleName.set(project.name)
        moduleVersion.set(project.version.toString())
        outputDirectory.set(layout.buildDirectory.dir("dokka/html"))
        failOnWarning.set(true)
    }
}

// Maven publishing (fixes no-publishing-plugin / no-pom-metadata). The KMP +
// Android-KMP-library plugins auto-create the per-target publications once
// `maven-publish` is applied; group/version come from the root `allprojects`
// block (dev.p2pkit / VERSION_NAME). We enrich the POM here so artifacts carry
// the metadata Maven Central requires. Signing is wired centrally in the root
// build (conditional on a PGP key being supplied), so local `publishToMavenLocal`
// stays keyless while a Central release just sets the signing properties.
publishing {
    publications.withType<MavenPublication>().configureEach {
        pom {
            name.set("P2pKit ${project.name}")
            description.set("P2pKit — cross-platform peer-to-peer local-network library (Android, iOS, JVM/desktop).")
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
