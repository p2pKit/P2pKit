import org.jetbrains.kotlin.gradle.targets.jvm.KotlinJvmTarget

plugins {
    alias(libs.plugins.kotlin.multiplatform)
    alias(libs.plugins.kotlin.serialization)
    alias(libs.plugins.android.kmp.library)
}

kotlin {
    jvmToolchain(17)
    jvm()
    android {
        namespace = "dev.p2pkit.sample.rpc"
        compileSdk = libs.versions.android.compileSdk.get().toInt()
        minSdk = libs.versions.android.minSdk.get().toInt()
        withHostTest { }
    }
    val minimum = providers.gradleProperty("IOS_MIN_VERSION").get()
    require(minimum.matches(Regex("[0-9]+\\.[0-9]+")))
    listOf(iosX64(), iosArm64(), iosSimulatorArm64()).forEach { target ->
        target.binaries.framework {
            baseName = "P2pKitRpcExample"
            isStatic = true
            export(project(":p2p-rpc"))
            export(project(":p2p-core"))
            export(project(":p2p-transport-lan"))
        }
        target.binaries.configureEach {
            freeCompilerArgs += "-Xoverride-konan-properties=minVersion.ios=$minimum"
        }
    }
    sourceSets {
        commonMain.dependencies {
            api(project(":p2p-rpc"))
            api(project(":p2p-core"))
            api(project(":p2p-transport-lan"))
            implementation(libs.kotlinx.serialization.json)
        }
        commonTest.dependencies {
            implementation(kotlin("test"))
            implementation(libs.kotlinx.coroutines.test)
        }
    }
}

val mainCompilation = (kotlin.targets.getByName("jvm") as KotlinJvmTarget).compilations.getByName("main")
tasks.register<JavaExec>("runRpcCapacity") {
    group = "application"
    description = "Explicitly authorized LAN capacity experiment; never selected by check."
    classpath(mainCompilation.output.allOutputs, mainCompilation.runtimeDependencyFiles)
    mainClass.set("dev.p2pkit.sample.rpc.RpcCapacityMainKt")
    // No default environment/keys/host, and no automatic permission to run. See this sample's README.
}
