import dev.p2pkit.build.GitCommitValueSource
import dev.p2pkit.build.GitDirtyValueSource
import dev.p2pkit.build.VerifyXcframeworkProvenanceTask
import dev.p2pkit.build.WriteXcframeworkProvenanceTask
import groovy.json.JsonOutput
import org.jetbrains.kotlin.gradle.plugin.mpp.apple.XCFramework
import org.jetbrains.kotlin.gradle.targets.jvm.KotlinJvmTarget
import java.security.MessageDigest

plugins {
    alias(libs.plugins.kotlin.multiplatform)
    alias(libs.plugins.kotlin.serialization)
    alias(libs.plugins.android.kmp.library)
}

kotlin {
    val exampleFramework = XCFramework("P2pKitRpcExample")
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
            exampleFramework.add(this)
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

// The separate phone test app consumes the actual current-source framework, never an unchecked binary.
val phoneFrameworkPaths = listOf(
    "buildSrc/src", "library/p2p-core/src", "library/p2p-transport-lan/src", "library/p2p-rpc/src",
    "samples/p2p-sample-rpc/src", "library/p2p-core/build.gradle.kts", "library/p2p-transport-lan/build.gradle.kts",
    "library/p2p-rpc/build.gradle.kts", "samples/p2p-sample-rpc/build.gradle.kts",
    "library/p2p-core/gradle.lockfile", "library/p2p-transport-lan/gradle.lockfile",
    "library/p2p-rpc/gradle.lockfile", "samples/p2p-sample-rpc/gradle.lockfile",
    "build.gradle.kts", "settings.gradle.kts", "settings-gradle.lockfile", "gradle.lockfile", "gradle.properties",
    "gradle/libs.versions.toml", "gradle/verification-metadata.xml", "gradle/wrapper",
)
val phoneFrameworkInputs = files(phoneFrameworkPaths.map(rootProject::file)).asFileTree
val phoneFrameworkCommit = providers.of(GitCommitValueSource::class) {
    parameters.rootDirectory.set(rootProject.layout.projectDirectory)
}
val phoneFrameworkDirty = providers.of(GitDirtyValueSource::class) {
    parameters.rootDirectory.set(rootProject.layout.projectDirectory)
    parameters.relevantPaths.set(phoneFrameworkPaths)
}
// The test app can bind a USB capacity session to its compiled source, rather
// than echoing a caller-supplied source label. This is sample-only provenance.
val phoneBuildStamp = tasks.register("generateRpcPhoneBuildStamp") {
    val output = layout.buildDirectory.dir("generated/rpc-phone-build-stamp")
    inputs.property("sourceCommit", phoneFrameworkCommit)
    inputs.property("sourceDirty", phoneFrameworkDirty)
    outputs.dir(output)
    doLast {
        val commit = phoneFrameworkCommit.get()
        check(commit.matches(Regex("[a-f0-9]{40}")))
        val file = output.get().file("dev/p2pkit/sample/rpc/RpcPhoneBuildStamp.kt").asFile
        check(file.parentFile.isDirectory || file.parentFile.mkdirs())
        file.writeText("""
            package dev.p2pkit.sample.rpc
            internal object RpcPhoneBuildStamp {
                const val SOURCE_COMMIT: String = "$commit"
                const val SOURCE_CLEAN: Boolean = ${!phoneFrameworkDirty.get()}
            }
        """.trimIndent() + "\n")
    }
}
kotlin.sourceSets.named("commonMain") {
    kotlin.srcDir(phoneBuildStamp)
}
listOf("debug", "release").forEach { config ->
    val capitalized = config.replaceFirstChar(Char::uppercaseChar)
    val directory = layout.buildDirectory.dir("XCFrameworks/$config")
    val binaries = directory.map { output ->
        listOf("ios-arm64", "ios-arm64_x86_64-simulator").map { slice ->
            output.file("P2pKitRpcExample.xcframework/$slice/P2pKitRpcExample.framework/P2pKitRpcExample").asFile
        }
    }
    val artifacts = directory.map { output ->
        output.dir("P2pKitRpcExample.xcframework").asFileTree.matching {
            include("**/*.framework/P2pKitRpcExample", "**/*.framework/Headers/**")
        }
    }
    val producer = tasks.register<WriteXcframeworkProvenanceTask>(
        "writeP2pKitRpcExample${capitalized}XCFrameworkProvenance",
    ) {
        dependsOn("assembleP2pKitRpcExample${capitalized}XCFramework")
        provenanceInputs.from(phoneFrameworkInputs)
        frameworkBinaries.from(binaries)
        frameworkArtifacts.from(artifacts)
        rootDirectory.set(rootProject.layout.projectDirectory)
        sourceCommit.set(phoneFrameworkCommit)
        relevantSourceDirty.set(phoneFrameworkDirty)
        commitFile.set(directory.map { it.file("BUILD_COMMIT.txt") })
        stateFile.set(directory.map { it.file("BUILD_SOURCE_STATE.txt") })
        fingerprintFile.set(directory.map { it.file("BUILD_INPUTS_SHA256.txt") })
        artifactFingerprintFile.set(directory.map { it.file("BUILD_ARTIFACTS_SHA256.txt") })
    }
    tasks.register<VerifyXcframeworkProvenanceTask>("verifyP2pKitRpcExample${capitalized}XCFrameworkProvenance") {
        dependsOn(producer)
        provenanceInputs.from(phoneFrameworkInputs)
        frameworkBinaries.from(binaries)
        frameworkArtifacts.from(artifacts)
        rootDirectory.set(rootProject.layout.projectDirectory)
        sourceCommit.set(phoneFrameworkCommit)
        relevantSourceDirty.set(phoneFrameworkDirty)
        commitFile.set(producer.flatMap { it.commitFile })
        stateFile.set(producer.flatMap { it.stateFile })
        fingerprintFile.set(producer.flatMap { it.fingerprintFile })
        artifactFingerprintFile.set(producer.flatMap { it.artifactFingerprintFile })
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
