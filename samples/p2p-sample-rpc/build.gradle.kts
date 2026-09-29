import groovy.json.JsonOutput
import org.jetbrains.kotlin.gradle.targets.jvm.KotlinJvmTarget
import java.security.MessageDigest

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
            export(project.dependencies.project(":p2p-rpc"))
            export(project.dependencies.project(":p2p-core"))
            export(project.dependencies.project(":p2p-transport-lan"))
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
// Application-owned, opt-in lab integration. It is not part of the sample's main
// artifact or any library publication, and is never an automatic transport fallback.
val labCompilation = (kotlin.targets.getByName("jvm") as KotlinJvmTarget).compilations.create("lab") {
    associateWith(mainCompilation)
}
(kotlin.targets.getByName("jvm") as KotlinJvmTarget).compilations.getByName("test").associateWith(labCompilation)

tasks.register<JavaExec>("runRpcCapacity") {
    group = "application"
    description = "Explicitly authorized LAN capacity experiment; never selected by check."
    classpath(mainCompilation.output.allOutputs, mainCompilation.runtimeDependencyFiles)
    mainClass.set("dev.p2pkit.sample.rpc.RpcCapacityMainKt")
    // No default environment/keys/host, and no automatic permission to run. See this sample's README.
}

tasks.register<JavaExec>("runRpcCapacityLab") {
    group = "verification"
    description = "Explicitly authorized synthetic lab clients; never selected by check."
    classpath(labCompilation.output.allOutputs, labCompilation.runtimeDependencyFiles)
    mainClass.set("dev.p2pkit.sample.rpc.RpcCapacityMainKt")
}

tasks.register<JavaExec>("runRpcCapacityLabHost") {
    group = "verification"
    description = "Explicitly authorized synthetic lab host; never selected by check."
    classpath(labCompilation.output.allOutputs, labCompilation.runtimeDependencyFiles)
    mainClass.set("dev.p2pkit.sample.rpc.lab.LabHostKt")
}

// Explicitly prepared standalone test tooling, not a published artifact. A coordinator
// starts each JVM through the admitted native executor and supplies its private config.
val capacityLabJar = tasks.register<Jar>("jvmCapacityLabJar") {
    archiveClassifier.set("capacity-lab")
    from(mainCompilation.output.allOutputs, labCompilation.output.allOutputs)
    duplicatesStrategy = DuplicatesStrategy.FAIL
}
tasks.register<Sync>("prepareRpcCapacityLab") {
    group = "verification"
    description = "Prepare opt-in capacity tooling without starting a host or any clients."
    into(layout.buildDirectory.dir("capacity-lab"))
    from(capacityLabJar)
    from(labCompilation.runtimeDependencyFiles.filter { it.extension == "jar" })
    duplicatesStrategy = DuplicatesStrategy.FAIL
    val sourceCommit = providers.exec {
        workingDir(rootDir)
        commandLine("git", "rev-parse", "HEAD")
    }.standardOutput.asText.map(String::trim)
    inputs.property("sourceCommit", sourceCommit)
    doLast {
        val status = providers.exec {
            workingDir(rootDir)
            commandLine("git", "status", "--porcelain=v1")
        }.standardOutput.asText.get()
        check(status.isBlank()) { "The lab distribution requires a clean source-bound candidate" }
        val directory = destinationDir
        val entries = directory.listFiles()!!.filter { it.extension == "jar" }.sortedBy { it.name }.map { file ->
            val digest = MessageDigest.getInstance("SHA-256")
            file.inputStream().use { input ->
                val buffer = ByteArray(64 * 1024)
                while (true) {
                    val count = input.read(buffer)
                    if (count < 0) break
                    digest.update(buffer, 0, count)
                }
            }
            mapOf("name" to file.name, "sha256" to digest.digest().joinToString("") { "%02x".format(it) })
        }
        check(entries.isNotEmpty())
        directory.resolve("manifest.json").writeText(JsonOutput.toJson(mapOf(
            "schema" to 1, "sourceSha" to sourceCommit.get(), "entries" to entries,
            "scope" to "SYNTHETIC_LAB_NOT_PUBLICATION_OR_QUALIFICATION",
        )) + "\n")
    }
}
