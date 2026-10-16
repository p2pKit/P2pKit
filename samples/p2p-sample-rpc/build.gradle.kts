import dev.p2pkit.build.GitCommitValueSource
import dev.p2pkit.build.GitDirtyValueSource
import dev.p2pkit.build.VerifyXcframeworkProvenanceTask
import dev.p2pkit.build.WriteXcframeworkProvenanceTask
import groovy.json.JsonOutput
import org.jetbrains.kotlin.gradle.plugin.mpp.apple.XCFramework
import org.jetbrains.kotlin.gradle.targets.jvm.KotlinJvmTarget
import java.security.MessageDigest
import java.nio.file.Files
import java.nio.file.StandardOpenOption
import org.gradle.jvm.toolchain.JavaLanguageVersion
import org.gradle.jvm.toolchain.JavaToolchainService

plugins {
    alias(libs.plugins.kotlin.multiplatform)
    alias(libs.plugins.kotlin.serialization)
    alias(libs.plugins.android.kmp.library)
}

// Filesystem integration is host-specific; portable RPC/ownership tests remain in every jvmTest.
// No assumptions, ignored tests or runtime fallback: the opposite host has its own mandatory tests.
val rpcJvmTestHost = providers.systemProperty("os.name").map { name ->
    when {
        name.startsWith("Windows", ignoreCase = true) -> "windows"
        name == "Mac OS X" || name == "Linux" -> "posix"
        else -> error("RPC filesystem test host is unsupported: $name")
    }
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
        named("jvmTest") {
            kotlin.srcDir(rpcJvmTestHost.map { "src/${it}JvmTest/kotlin" })
        }
    }
}

tasks.named<Test>("jvmTest") {
    inputs.property("rpcJvmTestHost", rpcJvmTestHost)
    doFirst {
        val host = rpcJvmTestHost.get()
        val sourceRoots = kotlin.sourceSets.getByName("jvmTest").kotlin.srcDirs
        check(file("src/jvmTest/kotlin") in sourceRoots) { "Portable RPC tests must remain registered" }
        check(file("src/${host}JvmTest/kotlin") in sourceRoots) { "Host filesystem tests must remain registered" }
        check(file("src/${host}JvmTest/kotlin").isDirectory) { "Host filesystem test sources are missing" }
        val other = if (host == "windows") "posix" else "windows"
        check(file("src/${other}JvmTest/kotlin") !in sourceRoots) { "Wrong-host filesystem test registration" }
        logger.lifecycle("RPC JVM tests: portable + $host filesystem contracts; not installed/native qualification")
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
// Isolated, unpublished investigation module. No preview classes enter the Kotlin/JVM17 main artifact.
// Compiling it does not authorize any native call or enable the Windows profile provider.
val windowsLoaderJdk21 = extensions.getByType<JavaToolchainService>().compilerFor {
    languageVersion.set(JavaLanguageVersion.of(21))
}
val compileRpcWindowsLoaderJdk21 = tasks.register<JavaCompile>("compileRpcWindowsLoaderJdk21") {
    group = "verification"
    description = "Compile the production-disabled, named JDK21-preview adapter only."
    javaCompiler.set(windowsLoaderJdk21)
    source(layout.projectDirectory.dir("native/windows-loader-jdk21/src/main/java"))
    classpath = files()
    destinationDirectory.set(layout.buildDirectory.dir("windows-loader-jdk21/classes"))
    options.release.set(21)
    options.encoding = "UTF-8"
    options.compilerArgs.addAll(listOf("--enable-preview", "-proc:none", "-Xlint:all,-preview", "-Werror"))
}
val rpcWindowsLoaderJdk21Jar = tasks.register<Jar>("rpcWindowsLoaderJdk21Jar") {
    group = "verification"
    description = "Package only the disabled adapter; never publish it as a Maven coordinate."
    from(compileRpcWindowsLoaderJdk21.flatMap { it.destinationDirectory })
    archiveFileName.set("p2pkit-windows-loader-jdk21.jar")
    destinationDirectory.set(layout.buildDirectory.dir("windows-loader-jdk21"))
    duplicatesStrategy = DuplicatesStrategy.FAIL
    isPreserveFileTimestamps = false
    isReproducibleFileOrder = true
}
// Keep the existing adapter controls in the ordinary Windows component, not an obsolete hosted dispatch lane.
// Development-JDK controls include a separate deny-storage test DLL, never the productive profile DLL.
val windowsControlsJdk17 = extensions.getByType<JavaToolchainService>().launcherFor {
    languageVersion.set(JavaLanguageVersion.of(17))
}
// Only explicit adapter verification/Windows JVM tests compile the connection fixtures.
// Depend on compilation outputs, never jvmTest itself (which already depends on verification on Windows).
val windowsVerifierCompilation = (kotlin.targets.getByName("jvm") as KotlinJvmTarget).compilations.getByName("test")
val windowsVerifierClasspath = files(mainCompilation.output.allOutputs, mainCompilation.runtimeDependencyFiles,
    windowsVerifierCompilation.output.allOutputs, windowsVerifierCompilation.runtimeDependencyFiles)
val verifyRpcWindowsLoaderJdk21 = tasks.register<Exec>("verifyRpcWindowsLoaderJdk21") {
    group = "verification"
    description = "Exercise disabled-adapter invocation/refusal controls; not installed Windows qualification."
    dependsOn(rpcWindowsLoaderJdk21Jar)
    dependsOn(windowsVerifierClasspath)
    workingDir(rootProject.layout.projectDirectory)
    inputs.file(rootProject.file("scripts/tests/check-rpc-windows-loader-jdk21.py"))
    inputs.dir(layout.projectDirectory.dir("native/windows-loader-jdk21/src/test/java"))
    // This test-only Windows DLL never enters production resources, packaging or the artifact freeze.
    inputs.files(listOf("profile_policy.c", "profile_jni.c", "profile_jni_registration.c", "profile_policy.h",
        "profile_win32.h", "profile_jni_registration.h", "tests/jvm/deny_storage.c", "tests/jvm/build-test-dll.py",
        "tests/jvm/test-build-test-dll.py")
        .map { layout.projectDirectory.file("native/windows-profile/$it") })
    inputs.files(windowsVerifierClasspath)
    outputs.upToDateWhen { false }
    doFirst {
        val reports = rootProject.layout.buildDirectory.dir("reports/rpc-windows-loader-jdk21").get().asFile.toPath()
        Files.createDirectories(reports)
        // Never erase or overwrite a prior result. The maintained runner creates its fresh controls directory.
        val attempt = Files.createTempDirectory(reports, "attempt-").resolve("controls")
        val applicationClasspath = attempt.parent.resolve("application-classpath.json")
        Files.writeString(applicationClasspath, JsonOutput.toJson(mapOf(
            "schema" to 1,
            "mainClassDirectories" to mainCompilation.output.classesDirs.files.filter { it.isDirectory }
                .map { it.absolutePath },
            "classpath" to windowsVerifierClasspath.files.filter { it.exists() }.map { it.absolutePath },
        )) + "\n", StandardOpenOption.CREATE_NEW)
        commandLine("python3", "-I", "-B", "scripts/tests/check-rpc-windows-loader-jdk21.py",
            "--java21", windowsLoaderJdk21.get().metadata.installationPath.asFile.absolutePath,
            "--java17", windowsControlsJdk17.get().metadata.installationPath.asFile.absolutePath,
            "--jar", rpcWindowsLoaderJdk21Jar.get().archiveFile.get().asFile.absolutePath,
            "--application-classpath", applicationClasspath.toString(),
            "--output", attempt.toString())
    }
}
tasks.named<Test>("jvmTest") {
    // Other host library tests still require only JDK17. Explicit adapter verification remains available there.
    // Gradle treats a system-property provider as a known non-task producer: mapping its value to task
    // providers does not add those tasks to the graph. Resolve only the host selector here, not a toolchain.
    if (rpcJvmTestHost.get() == "windows") dependsOn(verifyRpcWindowsLoaderJdk21)
    doFirst {
        if (rpcJvmTestHost.get() == "windows") {
            val controls = verifyRpcWindowsLoaderJdk21.get().state
            check(controls.executed && !controls.skipped && controls.failure == null) {
                "Windows RPC JVM tests require completed, unskipped adapter controls"
            }
        }
    }
}
// Application-owned, opt-in lab integration. It is not part of the sample's main
// artifact or any library publication, and is never an automatic transport fallback.
val labCompilation = (kotlin.targets.getByName("jvm") as KotlinJvmTarget).compilations.create("lab") {
    associateWith(mainCompilation)
}
(kotlin.targets.getByName("jvm") as KotlinJvmTarget).compilations.getByName("test").associateWith(labCompilation)

// Explicit byte inspection only. Neither normal tests nor packaging invoke this task or load its input DLL.
val windowsByteCompilation = (kotlin.targets.getByName("jvm") as KotlinJvmTarget).compilations.getByName("test")
// Target-only execution, not a skipped/pretend-passing Windows test in the portable JVM suite.
// Synthetic ordinary files only: no profile, native code loading, installer, or network role.
tasks.register<JavaExec>("verifyRpcWindowsPinnedImage") {
    group = "verification"
    description = "Test final-file Windows sharing pins; not native profile or installed-loader qualification."
    classpath(windowsByteCompilation.output.allOutputs, windowsByteCompilation.runtimeDependencyFiles)
    mainClass.set("dev.p2pkit.sample.rpc.profile.WindowsProfilePinnedImageWindowsProbe")
    javaLauncher.set(project.extensions.getByType<JavaToolchainService>().launcherFor {
        languageVersion.set(JavaLanguageVersion.of(17))
    })
    val output = providers.gradleProperty("rpcWindowsPinOutput")
    outputs.upToDateWhen { false }
    doFirst {
        check(System.getProperty("os.name").startsWith("Windows")) { "Windows execution is required" }
        setArgs(listOf(output.orNull?.takeIf(String::isNotBlank)
            ?: error("Explicit -PrpcWindowsPinOutput is required")))
    }
}

tasks.register<JavaExec>("verifyRpcWindowsProfileBytes") {
    group = "verification"
    description = "Inspect an independently hash-pinned Windows DLL; never load, execute, sign or publish it."
    classpath(windowsByteCompilation.output.allOutputs, windowsByteCompilation.runtimeDependencyFiles)
    mainClass.set("dev.p2pkit.sample.rpc.profile.WindowsProfileActualDllVerification")
    javaLauncher.set(project.extensions.getByType<JavaToolchainService>().launcherFor {
        languageVersion.set(JavaLanguageVersion.of(17))
    })
    val root = rootProject.layout.projectDirectory.asFile.absolutePath
    val arguments = listOf(
        "rpcWindowsDll", "rpcWindowsSource", "rpcWindowsTree", "rpcWindowsSha256", "rpcWindowsByteOutput",
    ).map { name -> name to providers.gradleProperty(name) }
    outputs.upToDateWhen { false }
    doFirst {
        // Pins come from the separate compiler receipt, not a manifest found alongside the candidate DLL.
        setArgs(listOf(root) + arguments.map { (name, value) ->
            value.orNull?.takeIf(String::isNotBlank) ?: error("Explicit -P$name is required")
        })
    }
}

// Small interactive manual-pairing sample, not the capacity driver or a check dependency.
tasks.register<JavaExec>("runRpcDesktopSample") {
    group = "application"
    description = "Open the opt-in Desktop RPC preview; choose a role and physical LAN in its local UI."
    classpath(labCompilation.output.allOutputs, labCompilation.runtimeDependencyFiles)
    mainClass.set("dev.p2pkit.sample.rpc.desktop.RpcDesktopMainKt")
    if (System.getProperty("os.name") == "Mac OS X" &&
        System.getProperty("os.arch") in setOf("aarch64", "arm64")) {
        dependsOn(":p2p-transport-lan:stageMacTcp")
        val directory = project(":p2p-transport-lan").layout.buildDirectory.dir(
            phoneFrameworkCommit.map { "macos-tcp/$it" }
        )
        classpath(files(directory.map { it.file("p2pkit-macos-tcp-manifest.jar") }))
        systemProperty("dev.p2pkit.lan.macos.nativeDir", directory.get().asFile.absolutePath)
    }
}

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

// Separate from capacity/discovery artifacts: a source-bound manual Desktop package, never auto-launched.
val desktopMacProducerRoot = rootProject.projectDir
val desktopMacProducerScript = rootProject.file("scripts/prepare-macos-rpc-desktop.py")
val desktopMacProducerJars = layout.buildDirectory.dir("capacity-lab")
val desktopMacJdk = extensions.getByType<JavaToolchainService>().launcherFor {
    languageVersion.set(JavaLanguageVersion.of(17))
}
tasks.register<Exec>("prepareRpcDesktopMac") {
    group = "application"
    description = "Create the explicit local ARM64 Desktop TCP package without starting any network role."
    dependsOn("prepareRpcCapacityLab", ":p2p-transport-lan:stageMacTcp")
    val output = layout.buildDirectory.dir(phoneFrameworkCommit.map { "desktop-macos/$it" })
    inputs.property("sourceCommit", phoneFrameworkCommit)
    inputs.file(rootProject.file("scripts/prepare-macos-rpc-desktop.py"))
    inputs.dir(layout.buildDirectory.dir("capacity-lab"))
    val native = project(":p2p-transport-lan").layout.buildDirectory.dir(
        phoneFrameworkCommit.map { "macos-tcp/$it" }
    )
    inputs.dir(native)
    outputs.dir(output)
    doFirst {
        commandLine("python3", "-I", "-B", desktopMacProducerScript,
            "--root", desktopMacProducerRoot, "--jars", desktopMacProducerJars.get().asFile,
            "--native", native.get().asFile, "--output", output.get().asFile,
            "--java", desktopMacJdk.get().executablePath.asFile)
    }
}
