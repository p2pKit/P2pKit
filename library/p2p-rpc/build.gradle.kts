import dev.p2pkit.build.P2pPomMetadata
import kotlinx.validation.KotlinApiBuildTask
import org.jetbrains.kotlin.gradle.tasks.KotlinCompile

plugins {
    alias(libs.plugins.kotlin.multiplatform)
    alias(libs.plugins.kotlin.serialization)
    alias(libs.plugins.android.kmp.library)
    alias(libs.plugins.dokka)
    `maven-publish`
}

kotlin {
    @OptIn(org.jetbrains.kotlin.gradle.dsl.abi.ExperimentalAbiValidation::class)
    abiValidation()
    jvmToolchain(17)
    jvm { compilerOptions.moduleName.set(project.name) }
    android {
        compilerOptions.moduleName.set(project.name)
        namespace = "dev.p2pkit.rpc"
        compileSdk = libs.versions.android.compileSdk.get().toInt()
        minSdk = libs.versions.android.minSdk.get().toInt()
        withHostTest { }
    }
    val minimum = providers.gradleProperty("IOS_MIN_VERSION").get()
    require(minimum.matches(Regex("[0-9]+\\.[0-9]+")))
    listOf(iosX64(), iosArm64(), iosSimulatorArm64()).forEach { target ->
        target.binaries.configureEach {
            freeCompilerArgs += "-Xoverride-konan-properties=minVersion.ios=$minimum"
        }
    }
    sourceSets {
        commonMain.dependencies {
            api(project(":p2p-core"))
            api(project(":p2p-transport-lan"))
            api(libs.kotlinx.serialization.core)
            implementation(libs.kotlinx.serialization.json)
            // Same codec family/version, streaming into a bounded sink instead of an unbounded String.
            implementation(libs.kotlinx.serialization.json.io)
        }
        jvmMain.dependencies { implementation(project(":p2p-network-provisioning-desktop")) }
        androidMain.dependencies { implementation(project(":p2p-network-provisioning-android")) }
        commonTest.dependencies {
            implementation(kotlin("test"))
            implementation(libs.kotlinx.coroutines.test)
        }
        getByName("androidHostTest").dependencies {
            implementation(kotlin("test"))
            implementation(libs.kotlinx.coroutines.test)
        }
    }
}

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
        offlineMode.set(true)
    }
}

publishing {
    publications.withType<MavenPublication>().configureEach {
        pom {
            name.set("P2pKit ${project.name}")
            description.set("Optional authenticated, bounded organization-LAN RPC over P2pKit.")
            P2pPomMetadata.configure(this)
        }
    }
}
