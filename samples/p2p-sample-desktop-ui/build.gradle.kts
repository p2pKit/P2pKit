import dev.p2pkit.build.ApplicationReleaseVersion
import dev.p2pkit.build.GenerateSampleReleaseIdentityTask
import dev.p2pkit.build.GitCommitValueSource
import dev.p2pkit.build.BuildWindowsProfileTask
import dev.p2pkit.build.VerifyWindowsProfileSourceTask
import java.nio.file.Files
import java.nio.file.LinkOption
import java.nio.file.StandardOpenOption
import java.nio.file.attribute.BasicFileAttributes
import org.jetbrains.compose.desktop.application.dsl.TargetFormat
import org.jetbrains.compose.desktop.application.tasks.AbstractCheckNativeDistributionRuntime
import org.jetbrains.compose.desktop.application.tasks.AbstractJLinkTask
import org.jetbrains.compose.desktop.application.tasks.AbstractJPackageTask

plugins {
    alias(libs.plugins.kotlin.jvm)
    alias(libs.plugins.kotlin.compose)
    alias(libs.plugins.jetbrains.compose)
}

val applicationReleaseVersion = ApplicationReleaseVersion.parse(project.version.toString())
val sampleReleaseIdentity = tasks.register<GenerateSampleReleaseIdentityTask>("generateSampleReleaseIdentity") {
    canonicalVersion.set(applicationReleaseVersion.name)
    sourceCommit.set(providers.of(GitCommitValueSource::class) {
        parameters.rootDirectory.set(rootProject.layout.projectDirectory)
    })
    outputDirectory.set(layout.buildDirectory.dir("generated/sample-release-resources"))
}
tasks.named<ProcessResources>("processResources") { from(sampleReleaseIdentity) }

kotlin {
    jvmToolchain(17)
}

// Gradle -D properties are not automatically inherited by the sample JVM.
// Forward explicit operator opt-ins without changing packaged-app defaults.
tasks.withType<JavaExec>().matching { it.name == "run" }.configureEach {
    for (property in listOf("dev.p2pkit.lan.trace", "dev.p2pkit.lan.traceFrames")) {
        providers.systemProperty(property).orNull?.let { systemProperty(property, it) }
    }
}

tasks.withType<Test>().configureEach {
    doFirst {
        // Forked property probes need the declared runtime classpath, not
        // Gradle worker ClassLoader implementation details.
        systemProperty("dev.p2pkit.sample.test.runtimeClasspath", classpath.asPath)
    }
}

val supportedDesktopLockTargets = setOf(
    "linux-arm64",
    "linux-x64",
    "macos-arm64",
    "macos-x64",
    "windows-arm64",
    "windows-x64"
)
val detectedDesktopLockTarget = run {
    val os = System.getProperty("os.name").lowercase()
    val architecture = when (System.getProperty("os.arch").lowercase()) {
        "aarch64", "arm64" -> "arm64"
        "amd64", "x64", "x86_64" -> "x64"
        else -> error("Unsupported Desktop architecture: ${System.getProperty("os.arch")}")
    }
    val platform = when {
        os.contains("mac") || os.contains("darwin") -> "macos"
        os.contains("linux") -> "linux"
        os.contains("windows") -> "windows"
        else -> error("Unsupported Desktop operating system: ${System.getProperty("os.name")}")
    }
    "$platform-$architecture"
}
val desktopLockTarget =
    providers.gradleProperty("p2pkit.desktop.lockTarget").orNull ?: detectedDesktopLockTarget
require(desktopLockTarget in supportedDesktopLockTargets) {
    "p2pkit.desktop.lockTarget must be one of ${supportedDesktopLockTargets.sorted()}"
}
val composeDesktopRuntime = when (desktopLockTarget) {
    "linux-arm64" -> libs.jetbrains.compose.desktop.linux.arm64
    "linux-x64" -> libs.jetbrains.compose.desktop.linux.x64
    "macos-arm64" -> libs.jetbrains.compose.desktop.macos.arm64
    "macos-x64" -> libs.jetbrains.compose.desktop.macos.x64
    "windows-arm64" -> libs.jetbrains.compose.desktop.windows.arm64
    "windows-x64" -> libs.jetbrains.compose.desktop.windows.x64
    else -> error("Unsupported Desktop target: $desktopLockTarget")
}

// The override is a dependency-resolution seam for regenerating and checking
// all platform verification metadata from one host. Never run or package a
// foreign runtime as though it belonged to the current machine.
val currentHostOnlyDesktopTasks = setOf(
    "run",
    "runHot",
    "hotRun",
    "hotRunAsync",
    "hotDev",
    "hotDevAsync",
    "test"
)
tasks.matching { task ->
    task.name in currentHostOnlyDesktopTasks ||
        task.name.contains("Distributable") ||
        task.name.startsWith("package")
}.configureEach {
    doFirst {
        check(desktopLockTarget == detectedDesktopLockTarget) {
            "p2pkit.desktop.lockTarget is for dependency resolution only; " +
                "cannot execute $name for $desktopLockTarget on $detectedDesktopLockTarget"
        }
    }
}

dependencies {
    implementation(project(":p2p-core"))
    implementation(project(":p2p-transport-lan"))
    implementation(project(":p2p-network-provisioning-desktop"))
    implementation(project(":p2p-sample-diagnostics"))
    implementation(project(":p2p-sample-rpc"))
    implementation(libs.kotlinx.coroutines.core)

    implementation(composeDesktopRuntime)
    // The Compose plugin dependency shorthands for these artifacts are
    // deprecated. Pin their currently resolved coordinates in the catalog so
    // configuration stays warning-free without changing the runtime graph.
    implementation(libs.jetbrains.compose.material3)
    implementation(libs.jetbrains.compose.material.icons.extended)

    // Silence JmDNS's SLF4J "no provider" warning on startup.
    // AUDIT-2026-06 (BUILD-G10-11): coordinates moved to the version catalog.
    runtimeOnly(libs.slf4j.nop)

    // 2026-07 (P1-32 / SMP-1): minimal test wiring for the sample's shared
    // incoming-file destination-uniquification helper (UniqueSaveFileTest).
    // This module previously had no test source set; samples are unpublished
    // test harnesses, so this stays out of the published dependency graph.
    testImplementation(kotlin("test"))
}

// Private Gradle execution and packaged development apps use distinct admission policies.
// Neither path claims Developer ID/notarization or substitutes a new release pipeline.
if (detectedDesktopLockTarget == "macos-arm64") {
    val sourceCommit = providers.of(GitCommitValueSource::class) {
        parameters.rootDirectory.set(rootProject.layout.projectDirectory)
    }
    val nativeDirectory = project(":p2p-transport-lan").layout.buildDirectory.dir(
        sourceCommit.map { "macos-tcp/$it" },
    )
    tasks.withType<JavaExec>().matching { it.name == "run" }.configureEach {
        dependsOn(":p2p-transport-lan:stageMacTcp")
        classpath(files(nativeDirectory.map { it.file("p2pkit-macos-tcp-manifest.jar") }))
        systemProperty("dev.p2pkit.lan.macos.nativeDir", nativeDirectory.get().asFile.absolutePath)
    }

    val finalizedDirectory = layout.buildDirectory.dir(sourceCommit.map { "rpc-macos-app-image/$it" })
    val dmgPackagerJdk = extensions.getByType<JavaToolchainService>().launcherFor {
        languageVersion.set(JavaLanguageVersion.of(17))
    }
    val finalizedApp = finalizedDirectory.map { it.dir("P2pKit Sample.app") }
    val finalizationReceipt = finalizedDirectory.map { it.file("native-finalization.json") }
    val finalizer = rootProject.layout.projectDirectory.file("scripts/stage-rpc-macos-app.py")
    val originalApp = providers.provider {
        tasks.named<AbstractJPackageTask>("createDistributable").get().destinationDir.get().dir("P2pKit Sample.app")
    }
    val finalizeRpcMacosDevelopmentApp = tasks.register<Exec>("finalizeRpcMacosDevelopmentApp") {
        group = "distribution"
        description = "Finalizes an owned development-ad-hoc copy for the existing DMG producer; never publishes."
        // Declare these before lazy package-task configuration: requesting this task alone must realize its producer.
        dependsOn("createDistributable", ":p2p-transport-lan:stageMacTcp")
        inputs.file(finalizer)
        inputs.dir(nativeDirectory)
        inputs.dir(originalApp)
        inputs.property("sourceCommit", sourceCommit)
        // Gradle may pre-create declared output directories; the helper must create the .app itself.
        outputs.dir(finalizedDirectory)
        outputs.file(finalizationReceipt)
        executable = "python3"
        argumentProviders.add(CommandLineArgumentProvider {
            listOf("-I", "-S", "-B", finalizer.asFile.absolutePath,
                "--root", rootProject.projectDir.absolutePath,
                "--input-app", originalApp.get().asFile.absolutePath,
                "--output-app", finalizedApp.get().asFile.absolutePath,
                "--native-stage", nativeDirectory.get().asFile.absolutePath,
                "--receipt", finalizationReceipt.get().asFile.absolutePath,
                "--policy", "development-adhoc-v1")
        })
        // Gradle creates the declared output parent; the helper validates it before use.
    }
    tasks.withType<AbstractJPackageTask>().configureEach {
        if (name == "createDistributable") {
            dependsOn(":p2p-transport-lan:stageMacTcp")
            files.from(nativeDirectory.map { it.file("p2pkit-macos-tcp-manifest.jar") })
        }
    }
    // Compose sets launcherJvmArgs during its deferred task registration. Append afterward;
    // an early configureEach addition is overwritten. Do not apply installed policy to Gradle run.
    afterEvaluate {
        tasks.named<AbstractJPackageTask>("createDistributable") {
            launcherJvmArgs.add("-Ddev.p2pkit.lan.macos.installedPolicy=development-adhoc-v1")
        }
        tasks.named<AbstractJPackageTask>("packageDmg") {
            dependsOn(finalizeRpcMacosDevelopmentApp)
            // JDK 21 installer packaging re-signs an ad-hoc predefined image, invalidating its native pin.
            // Use the JDK 17 image-preserving installer tool; do not change the application's runtime.
            javaHome.set(dmgPackagerJdk.map { it.metadata.installationPath.asFile.absolutePath })
            // Compose also sets this input during registration; bind the finalized parent afterward.
            // The plugin appends .app for the active JDK, so do not pass finalizedApp here.
            appImage.set(finalizedDirectory)
        }
    }
}

// The same Desktop app/MSI gains a staged native component, not a separate installer or load policy.
// Merely including these bytes must not enable the unqualified Windows RPC provider.
if (detectedDesktopLockTarget == "windows-x64") {
    // Experimental packaging/readback only. Even when included, the adapter refuses every productive load.
    // Foundation must still qualify and pin the installed runtime/bootstrap before enabling that path.
    val previewAdapter = providers.gradleProperty("p2pkit.rpc.windows.previewAdapter").map {
        it.toBooleanStrict()
    }.getOrElse(false)
    val adapterProject = project(":p2p-sample-rpc")
    val adapterJar = adapterProject.layout.buildDirectory.file(
        "windows-loader-jdk21/p2pkit-windows-loader-jdk21.jar",
    )
    // Bind packaging to setup-java's explicitly selected installation, not Gradle's
    // major-only toolchain search (which can prefer a different cached JDK).
    // The environment selects a candidate; full archive verification remains authority.
    val previewRuntimeHome = providers.environmentVariable("JAVA_HOME_21_X64").map {
        file(it).absolutePath
    }
    val runtimeSupplierArchive = providers.environmentVariable("P2PKIT_RPC_WINDOWS_JDK21_ARCHIVE")
    val runtimeSupplierReceipt = rootProject.layout.buildDirectory.file("reports/rpc-windows-runtime/supplier.json")
    val verifyRpcWindowsJdk21 = tasks.register<Exec>("verifyRpcWindowsJdk21") {
        group = "verification"
        description = "Compare the actual Windows packaging JDK with its reviewed supplier archive."
        val verifier = rootProject.layout.projectDirectory.file("scripts/verify-rpc-windows-jdk21.py")
        val supplier = adapterProject.layout.projectDirectory.file(
            "native/windows-loader-jdk21/runtime-supplier.properties",
        )
        inputs.files(verifier, supplier)
        inputs.file(runtimeSupplierArchive)
        inputs.dir(previewRuntimeHome)
        outputs.file(runtimeSupplierReceipt)
        // A previous observation is not a lease on today's mutable build tool directory.
        outputs.upToDateWhen { false }
        doFirst {
            val result = runtimeSupplierReceipt.get().asFile.toPath()
            Files.createDirectories(result.parent)
            Files.deleteIfExists(result)
            commandLine("python3", "-I", "-B", verifier.asFile.absolutePath,
                "--archive", runtimeSupplierArchive.get(),
                "--jdk-home", previewRuntimeHome.get(),
                "--output", result.toString())
        }
    }
    val sourceCommit = providers.of(GitCommitValueSource::class) {
        parameters.rootDirectory.set(rootProject.layout.projectDirectory)
    }
    val nativeBuild = layout.buildDirectory.dir(sourceCommit.map { "rpc-windows-profile/$it/compiler" })
    val appResources = layout.buildDirectory.dir(sourceCommit.map { "rpc-windows-profile/$it/resources" })
    val parentPinResources = layout.buildDirectory.dir(sourceCommit.map { "rpc-windows-profile/$it/parent-pin" })
    val nativeJdk = extensions.getByType<JavaToolchainService>().launcherFor {
        languageVersion.set(JavaLanguageVersion.of(17))
    }
    val verifyRpcWindowsPackagingSource = tasks.register<VerifyWindowsProfileSourceTask>(
        "verifyRpcWindowsPackagingSource",
    ) {
        group = "verification"
        description = "Always recheck clean native package source, even when generated bytes are up to date."
        rootDirectory.set(rootProject.layout.projectDirectory)
        this.sourceCommit.set(sourceCommit)
    }
    val buildRpcWindowsProfileNative = tasks.register<BuildWindowsProfileTask>("buildRpcWindowsProfileNative") {
        group = "distribution"
        description = "Compile the Windows x64 custody component for the existing app; never load or publish."
        dependsOn(verifyRpcWindowsPackagingSource)
        rootDirectory.set(rootProject.layout.projectDirectory)
        nativeDirectory.set(project(":p2p-sample-rpc").layout.projectDirectory.dir("native/windows-profile"))
        javaHome.set(nativeJdk.map { it.metadata.installationPath })
        this.sourceCommit.set(sourceCommit)
        libraryFile.set(nativeBuild.map { it.file("p2pkit-windows-profile.dll") })
        compilerReceipt.set(nativeBuild.map { it.file("compiler.properties") })
    }
    val stageRpcWindowsProfileNative = tasks.register<JavaExec>("stageRpcWindowsProfileNative") {
        group = "distribution"
        description = "Inspect and stage byte-pinned DLL/resources in the existing Desktop distribution."
        dependsOn(buildRpcWindowsProfileNative)
        // Production code only: packaging never depends on the sample's test or lab compilation.
        classpath(configurations.runtimeClasspath)
        mainClass.set("dev.p2pkit.sample.rpc.profile.WindowsProfilePackageStage")
        javaLauncher.set(nativeJdk)
        inputs.files(buildRpcWindowsProfileNative.flatMap { it.libraryFile },
            buildRpcWindowsProfileNative.flatMap { it.compilerReceipt })
        outputs.dir(appResources)
        outputs.dir(parentPinResources)
        argumentProviders.add(CommandLineArgumentProvider {
            listOf(buildRpcWindowsProfileNative.get().libraryFile.get().asFile.absolutePath,
                buildRpcWindowsProfileNative.get().compilerReceipt.get().asFile.absolutePath,
                appResources.get().dir("windows/rpc-profile/windows-x64").asFile.absolutePath,
                parentPinResources.get().asFile.absolutePath)
        })
    }
    val rpcWindowsParentPinJar = tasks.register<Jar>("rpcWindowsParentPinJar") {
        dependsOn(stageRpcWindowsProfileNative)
        from(parentPinResources) {
            include("META-INF/p2pkit/windows-profile-parent.properties")
        }
        archiveFileName.set("p2pkit-windows-profile-parent-pin.jar")
        destinationDirectory.set(layout.buildDirectory.dir(sourceCommit.map { "rpc-windows-profile/$it/parent-jar" }))
    }
    val rpcWindowsApplicationResources = tasks.register<Sync>("rpcWindowsApplicationResources") {
        dependsOn(stageRpcWindowsProfileNative)
        // Do not attach native compilation to Compose's shared prepareAppResources task: run also uses it.
        // Preserve ordinary application resources and add native bytes only for packaged images.
        from(tasks.named<Sync>("prepareAppResources").map { it.destinationDir })
        from(appResources.map { it.dir("windows") })
        // JDK21 recursively adds every input .jar to app.classpath, including resource subdirectories.
        // The named preview adapter is staged after image generation, never in this scanned input.
        into(layout.buildDirectory.dir(sourceCommit.map { "rpc-windows-profile/$it/package-resources" }))
        duplicatesStrategy = DuplicatesStrategy.FAIL
    }
    compose.desktop.application.nativeDistributions {
        modules("jdk.unsupported") // com.sun.nio.file.ExtendedOpenOption; no ambient/full JDK dependency.
    }
    // Compose marks appResourcesDir @Internal: its provider does NOT infer producer dependencies or inputs.
    // Explicitly bind both for each maintained package task; keep ordinary run/test independent.
    afterEvaluate {
        val packageTasks = setOf(
            "createDistributable", "packageMsi", "packageExe",
            "createReleaseDistributable", "packageReleaseMsi", "packageReleaseExe",
        )
        check(setOf("createDistributable", "packageMsi", "packageExe").all { it in tasks.names }) {
            "Expected maintained Windows distribution tasks are missing"
        }
        if (previewAdapter) {
            // Selecting jpackage alone does not select the linked application runtime.
            tasks.withType<AbstractJLinkTask>().configureEach {
                dependsOn(verifyRpcWindowsJdk21)
                inputs.file(runtimeSupplierReceipt).withPropertyName("rpcWindowsRuntimeSupplier")
                javaHome.set(previewRuntimeHome)
                doFirst {
                    check(javaHome.get() == previewRuntimeHome.get()) {
                        "Linked runtime tool does not match the verified Windows supplier"
                    }
                }
            }
            tasks.withType<AbstractCheckNativeDistributionRuntime>().configureEach {
                dependsOn(verifyRpcWindowsJdk21)
                inputs.file(runtimeSupplierReceipt).withPropertyName("rpcWindowsRuntimeSupplier")
                jdkHome.set(previewRuntimeHome)
                doFirst {
                    check(jdkHome.get() == previewRuntimeHome.get()) {
                        "Runtime check does not match the verified Windows supplier"
                    }
                }
            }
        }
        val imageTasks = setOf("createDistributable", "createReleaseDistributable")
        packageTasks.filter { it in tasks.names }.forEach { packageTask ->
            tasks.named<AbstractJPackageTask>(packageTask) {
                dependsOn(rpcWindowsApplicationResources)
                inputs.dir(rpcWindowsApplicationResources.map { it.destinationDir })
                    .withPropertyName("rpcWindowsApplicationResources")
                    .withPathSensitivity(PathSensitivity.RELATIVE)
                files.from(rpcWindowsParentPinJar.flatMap { it.archiveFile })
                appResourcesDir.set(layout.dir(rpcWindowsApplicationResources.map { it.destinationDir }))
                if (previewAdapter) {
                    // Do not change public/Kotlin bytecode targets or silently run a21-preview class on17.
                    // Use the explicit installation and verify every byte against the fixed supplier.
                    dependsOn(verifyRpcWindowsJdk21)
                    javaHome.set(previewRuntimeHome)
                    inputs.file(runtimeSupplierReceipt).withPropertyName("rpcWindowsRuntimeSupplier")
                    doFirst {
                        check(javaHome.get() == previewRuntimeHome.get()) {
                            "Packager does not match the verified Windows supplier"
                        }
                    }
                    launcherJvmArgs.addAll(listOf(
                        "--enable-preview",
                        "--module-path=\$APPDIR/resources/rpc-loader-jdk21",
                        "--add-modules=dev.p2pkit.rpc.windows.loader",
                        "--enable-native-access=dev.p2pkit.rpc.windows.loader",
                    ))
                    if (packageTask in imageTasks) {
                        dependsOn(":p2p-sample-rpc:rpcWindowsLoaderJdk21Jar")
                        inputs.file(adapterJar).withPropertyName("rpcWindowsPreviewAdapterJar")
                            .withPathSensitivity(PathSensitivity.NONE)
                        // Complete this same image before Gradle snapshots it or an installer consumes it.
                        // This is build-directory staging only, not installed-root or DLL-load authority.
                        doLast {
                            check(targetFormat == TargetFormat.AppImage && packageName.get() == "P2pKit Sample")
                            val image = destinationDir.get().dir(packageName.get()).asFile.toPath()
                            val app = image.resolve("app")
                            val resources = app.resolve("resources")
                            for (directory in listOf(image, app, resources)) {
                                check(Files.isDirectory(directory, LinkOption.NOFOLLOW_LINKS)) {
                                    "Expected existing ordinary Windows image directories"
                                }
                            }
                            val source = adapterJar.get().asFile.toPath()
                            val before = Files.readAttributes(
                                source, BasicFileAttributes::class.java, LinkOption.NOFOLLOW_LINKS,
                            )
                            check(before.isRegularFile && before.size() in 1..16L * 1024 * 1024)
                            val bytes = Files.newInputStream(source).use { it.readNBytes(16 * 1024 * 1024 + 1) }
                            val after = Files.readAttributes(
                                source, BasicFileAttributes::class.java, LinkOption.NOFOLLOW_LINKS,
                            )
                            check(bytes.size.toLong() == before.size() && after.isRegularFile &&
                                after.size() == before.size() && after.fileKey() == before.fileKey() &&
                                after.lastModifiedTime() == before.lastModifiedTime()) {
                                "Preview adapter input changed during bounded staging"
                            }
                            val cfg = app.resolve(packageName.get() + ".cfg")
                            check(Files.isRegularFile(cfg, LinkOption.NOFOLLOW_LINKS) &&
                                Files.size(cfg) in 1..65536L)
                            val cfgBytes = Files.newInputStream(cfg).use { it.readNBytes(65537) }
                            check(cfgBytes.size <= 65536 &&
                                !cfgBytes.toString(Charsets.UTF_8).contains(source.fileName.toString())) {
                                "Preview adapter must not enter the generated application classpath"
                            }
                            val adapterDirectory = resources.resolve("rpc-loader-jdk21")
                            Files.createDirectory(adapterDirectory)
                            val target = adapterDirectory.resolve(source.fileName)
                            Files.write(target, bytes, StandardOpenOption.CREATE_NEW, StandardOpenOption.WRITE)
                            check(Files.mismatch(source, target) == -1L) {
                                "Preview adapter image bytes differ from their declared build input"
                            }
                        }
                    } else {
                        val imageTask = if (packageTask.startsWith("packageRelease")) {
                            "createReleaseDistributable"
                        } else {
                            "createDistributable"
                        }
                        val maintainedImage = tasks.named<AbstractJPackageTask>(imageTask)
                        val completedImage = maintainedImage.flatMap { image ->
                            image.destinationDir.map { it.dir(image.packageName.get()) }
                        }
                        // Compose 1.11.1 only supplies appImage automatically on macOS. Without this
                        // Windows would build a second image from --input, omitting our staged module.
                        // Windows jpackage consumes the actual named image, not its output parent.
                        if (!appImage.isPresent) appImage.set(completedImage)
                        dependsOn(maintainedImage)
                        inputs.dir(completedImage)
                            .withPropertyName("rpcWindowsPreviewCompletedImage")
                            .withPathSensitivity(PathSensitivity.RELATIVE)
                        doFirst {
                            check(appImage.get().asFile == completedImage.get().asFile) {
                                "Windows installer must consume its completed maintained application image"
                            }
                        }
                    }
                }
                doFirst {
                    check(appResourcesDir.get().asFile == rpcWindowsApplicationResources.get().destinationDir) {
                        "Windows native application resources were replaced after package configuration"
                    }
                }
            }
        }
    }
}

compose.desktop {
    application {
        mainClass = "dev.p2pkit.sample.desktop.ui.MainKt"

        nativeDistributions {
            targetFormats(TargetFormat.Exe, TargetFormat.Msi, TargetFormat.Dmg, TargetFormat.Deb)
            packageName = "P2pKit Sample"
            packageVersion = applicationReleaseVersion.nativeVersion
            linux {
                packageName = "p2pkit-sample"
                appRelease = "1"
            }
            macOS { packageBuildVersion = applicationReleaseVersion.nativeVersion }
            windows {
                // Productive installed-root admission requires a protected machine installation.
                // This fixes the default/UI; runtime checks must still reject unsafe overrides.
                perUserInstall = false
                dirChooser = false
            }
            // AUDIT-2026-06 (BUILD-G10-12): derive from the project version
            // (gradle.properties VERSION_NAME) instead of a stale literal.
            description = "P2pKit ${project.version} desktop sample (room broadcast + file transfer)"
        }
    }
}
