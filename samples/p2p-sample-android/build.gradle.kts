import com.android.build.api.artifact.SingleArtifact
import com.android.build.api.variant.BuiltArtifactsLoader
import com.android.build.api.variant.VariantOutputConfiguration
import groovy.json.JsonOutput
import java.io.ByteArrayOutputStream
import java.nio.ByteBuffer
import java.nio.file.Files
import java.nio.file.LinkOption
import java.nio.file.Path
import java.nio.file.StandardOpenOption
import java.nio.file.attribute.BasicFileAttributes
import java.nio.file.attribute.PosixFilePermissions
import java.security.MessageDigest
import java.time.Duration
import org.gradle.api.file.Directory
import org.gradle.api.file.FileCollection

plugins {
    alias(libs.plugins.android.application)
    alias(libs.plugins.kotlin.compose)
}

android {
    namespace = "dev.p2pkit.sample.android"
    // AndroidX Core 1.19 requires API 37 at compile time. Published library
    // modules remain on the independently versioned API 36 compile SDK.
    compileSdk = libs.versions.android.sample.compileSdk.get().toInt()

    defaultConfig {
        applicationId = "dev.p2pkit.sample.android"
        minSdk = libs.versions.android.minSdk.get().toInt()
        targetSdk = libs.versions.android.sample.targetSdk.get().toInt()
        versionCode = 1
        versionName = "0.1.0"
        // One API37 runtime case, driven explicitly by run-android-art-smoke.py; no third-party test runner.
        testInstrumentationRunner = "dev.p2pkit.sample.android.runtime.LanPermissionRuntimeInstrumentation"
    }

    buildFeatures {
        compose = true
        buildConfig = true
    }

    // One recorder is exercised by host tests and the explicit API37 collector.
    // It is test support, never part of the shipped application or library API.
    sourceSets {
        getByName("test").java.srcDir("src/acceptanceTestSupport/java")
        getByName("androidTest").java.srcDir("src/acceptanceTestSupport/java")
    }

    buildTypes {
        release {
            isMinifyEnabled = false
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    lint {
        // REL-GATE-01 (BUILD-08/15): the sample is the executable Android
        // manifest/permission integration gate. New warnings must therefore
        // fail the build just like lint errors.
        warningsAsErrors = true
        abortOnError = true
    }
}

dependencies {
    implementation(project(":p2p-core"))
    implementation(project(":p2p-transport-lan"))
    implementation(project(":p2p-network-provisioning-android"))
    implementation(project(":sample-kmp-shared"))
    implementation(project(":p2p-sample-diagnostics"))

    // Core 1.19 moved the Kotlin extensions into `core`; keeping the empty
    // compatibility artifact as a direct constraint also aligns transitive
    // `core-ktx` requests on compile and runtime classpaths.
    implementation(libs.androidx.core.ktx)
    implementation(libs.androidx.activity.compose)
    implementation(libs.androidx.lifecycle.runtime.compose)
    implementation(libs.androidx.lifecycle.viewmodel.compose)
    // Lifecycle's Compose integration still requests serialization-core 1.7.x
    // on some variants. Align it with P2pKit's compile/runtime version.
    implementation(libs.kotlinx.serialization.core)

    implementation(platform(libs.androidx.compose.bom))
    implementation(libs.androidx.compose.ui)
    implementation(libs.androidx.compose.ui.tooling.preview)
    implementation(libs.androidx.compose.material.icons.core)
    implementation(libs.androidx.compose.material3)
    testImplementation(kotlin("test-junit"))
    testImplementation(libs.kotlinx.coroutines.test)
    testImplementation(libs.robolectric.runner)
}

// Compose runtime host tests need Android tracing/snapshot classes, not a device.
// Resolve the framework through the same locks/checksums as the adapter tests;
// Robolectric must never download an unchecked SDK at test runtime.
val robolectricSdk35 = configurations.create("robolectricSdk35") {
    isCanBeConsumed = false
    isCanBeResolved = true
    isTransitive = false
    dependencies.add(project.dependencies.create(libs.robolectric.sdk35.get()))
}
val prepareRobolectricSdk = tasks.register<Sync>("prepareRobolectricSdk") {
    from(robolectricSdk35)
    into(layout.buildDirectory.dir("robolectric-sdks"))
}
tasks.withType<Test>().configureEach {
    dependsOn(prepareRobolectricSdk)
    inputs.files(robolectricSdk35)
        .withPropertyName("robolectricFramework")
        .withNormalizer(ClasspathNormalizer::class.java)
    systemProperty("robolectric.offline", "true")
    systemProperty("robolectric.usePreinstrumentedJars", "true")
    systemProperty("robolectric.dependency.dir", layout.buildDirectory.dir("robolectric-sdks").get().asFile)
    val temporaryFiles = layout.buildDirectory.dir("host-test-tmp")
    systemProperty("java.io.tmpdir", temporaryFiles.get().asFile)
    doFirst {
        val directory = temporaryFiles.get().asFile
        check(directory.isDirectory || directory.mkdirs()) { "Cannot create host-test temporary directory" }
    }
    maxParallelForks = 1
    maxHeapSize = "1g"
    timeout.set(Duration.ofMinutes(2))
}

// Explicit local acceptance producer, not a check dependency or publication task.
// The outer executor must bind these bytes to its successful immutable build receipt.
androidComponents.onVariants(androidComponents.selector().withName("debug")) { variant ->
    // Do not change ordinary builds that intentionally disable the test component.
    val androidTest = variant.androidTest ?: return@onVariants
    val appManifest = files(variant.artifacts.get(SingleArtifact.MERGED_MANIFEST))
    val testManifest = files(androidTest.artifacts.get(SingleArtifact.MERGED_MANIFEST))
    val appApkDirectory = variant.artifacts.get(SingleArtifact.APK)
    val testApkDirectory = androidTest.artifacts.get(SingleArtifact.APK)
    val appApks = files(appApkDirectory)
    val testApks = files(testApkDirectory)
    val appLoader = variant.artifacts.getBuiltArtifactsLoader()
    val testLoader = androidTest.artifacts.getBuiltArtifactsLoader()
    val checkoutDirectory = rootProject.layout.projectDirectory
    val moduleDirectory = layout.projectDirectory
    val moduleBuildDirectory = layout.buildDirectory
    val retainedDirectory = layout.buildDirectory.dir("reports/android-acceptance/debug")

    tasks.register("retainDebugAcceptanceArtifacts") {
        val owner = this
        group = "verification"
        description = "Retain actual debug app/test merged manifests and provider-backed APK identities."
        inputs.files(appManifest).withPropertyName("appMergedManifest").withPathSensitivity(PathSensitivity.RELATIVE)
        inputs.files(testManifest).withPropertyName("testMergedManifest").withPathSensitivity(PathSensitivity.RELATIVE)
        inputs.files(appApks).withPropertyName("appApks").withPathSensitivity(PathSensitivity.RELATIVE)
        inputs.files(testApks).withPropertyName("testApks").withPathSensitivity(PathSensitivity.RELATIVE)
        inputs.property("appApplicationId", variant.applicationId)
        inputs.property("testApplicationId", androidTest.applicationId)
        inputs.property("appVariantName", variant.name)
        inputs.property("testVariantName", androidTest.name)
        outputs.dir(retainedDirectory)
        outputs.upToDateWhen { false }
        outputs.cacheIf("Acceptance maps must be produced in this invocation") { false }
        notCompatibleWithConfigurationCache("Inspects current AGP providers and their direct task dependencies")
        timeout.set(Duration.ofMinutes(2))

        doLast {
            val checkout = checkoutDirectory.asFile.toPath().toAbsolutePath().normalize()
            check(checkout.toRealPath() == checkout) { "Acceptance checkout must not be a path alias" }
            val module = moduleDirectory.asFile.toPath().toAbsolutePath().normalize()
            val buildRoot = moduleBuildDirectory.get().asFile.toPath()
            check(module.startsWith(checkout) && buildRoot == module.resolve("build")) {
                "Acceptance artifacts require this module's unrelocated build directory"
            }

            fun ownedPath(path: Path, mustExist: Boolean = true): Path {
                check(path.isAbsolute && path.normalize() == path && path.startsWith(buildRoot)) {
                    "Acceptance path is outside the module build root or is not canonical"
                }
                var current = checkout
                for (segment in checkout.relativize(path)) {
                    current = current.resolve(segment)
                    if (Files.exists(current, LinkOption.NOFOLLOW_LINKS)) {
                        check(!Files.isSymbolicLink(current) && current.toRealPath() == current) {
                            "Acceptance paths must not contain symlinks or aliases"
                        }
                    } else {
                        check(!mustExist) { "Acceptance artifact is missing" }
                    }
                }
                return path
            }

            fun relative(path: Path): String = checkout.relativize(path).joinToString("/")

            fun attributes(path: Path): BasicFileAttributes =
                Files.readAttributes(ownedPath(path), BasicFileAttributes::class.java, LinkOption.NOFOLLOW_LINKS)

            data class Snapshot(val bytes: Long, val sha256: String, val content: ByteArray?)

            fun snapshot(path: Path, maximum: Long, retain: Boolean = false): Snapshot {
                val before = attributes(path)
                check(before.isRegularFile && before.size() in 1..maximum) { "Invalid acceptance artifact size/type" }
                val digest = MessageDigest.getInstance("SHA-256")
                val content = if (retain) ByteArrayOutputStream() else null
                var count = 0L
                Files.newInputStream(path, StandardOpenOption.READ, LinkOption.NOFOLLOW_LINKS).use { input ->
                    val buffer = ByteArray(64 * 1024)
                    while (true) {
                        val size = input.read(buffer)
                        if (size == -1) break
                        count += size
                        check(count <= maximum) { "Acceptance artifact exceeded its read bound" }
                        digest.update(buffer, 0, size)
                        content?.write(buffer, 0, size)
                    }
                }
                val after = attributes(path)
                check(
                    after.isRegularFile && count == before.size() && after.size() == before.size() &&
                        after.fileKey() == before.fileKey() && after.lastModifiedTime() == before.lastModifiedTime(),
                ) { "Acceptance artifact changed during capture" }
                val sha256 = digest.digest().joinToString("") { "%02x".format(it.toInt() and 0xff) }
                return Snapshot(count, sha256, content?.toByteArray())
            }

            val output = ownedPath(retainedDirectory.get().asFile.toPath(), mustExist = false)
            // Gradle may create an empty output directory. Never overwrite/reuse an old map or partial capture.
            if (Files.exists(output, LinkOption.NOFOLLOW_LINKS)) {
                check(Files.isDirectory(output, LinkOption.NOFOLLOW_LINKS)) { "Acceptance output is not a directory" }
                Files.newDirectoryStream(output).use {
                    check(!it.iterator().hasNext()) { "Acceptance output is not new" }
                }
            }
            check(Files.getFileStore(ownedPath(buildRoot)).supportsFileAttributeView("posix")) {
                "Private local acceptance output requires a POSIX-permission filesystem"
            }
            val privateDirectory = PosixFilePermissions.fromString("rwx------")
            val privateFile = PosixFilePermissions.asFileAttribute(PosixFilePermissions.fromString("rw-------"))
            Files.createDirectories(output, PosixFilePermissions.asFileAttribute(privateDirectory))
            ownedPath(output)
            Files.setPosixFilePermissions(output, privateDirectory)

            fun writeNew(path: Path, content: ByteArray) {
                check(ownedPath(path, mustExist = false).parent == output) { "Unexpected acceptance output path" }
                Files.newByteChannel(
                    path,
                    setOf(StandardOpenOption.WRITE, StandardOpenOption.CREATE_NEW),
                    privateFile,
                ).use { channel ->
                    val bytes = ByteBuffer.wrap(content)
                    while (bytes.hasRemaining()) check(channel.write(bytes) > 0) { "Acceptance output write stalled" }
                }
            }

            fun producerTasks(files: FileCollection): List<String> {
                // Actual direct provider dependencies, not guessed task names or fresh-execution claims.
                val paths = files.buildDependencies.getDependencies(owner).map { it.path }.sorted()
                check(paths.isNotEmpty() && owner.path !in paths) { "Missing/recursive artifact producer dependency" }
                return paths
            }

            val manifestCopies = mutableListOf<Pair<Path, ByteArray>>()
            val seenSources = mutableSetOf<Path>()

            fun component(
                kind: String,
                applicationId: String,
                variantName: String,
                manifestFiles: FileCollection,
                apkFiles: FileCollection,
                apkDirectory: Directory,
                loader: BuiltArtifactsLoader,
                retainedName: String,
            ): Map<String, Any?> {
                val manifestPath = ownedPath(manifestFiles.singleFile.toPath())
                val directory = ownedPath(apkFiles.singleFile.toPath())
                check(directory == apkDirectory.asFile.toPath() && Files.isDirectory(directory)) {
                    "APK provider/file-collection mismatch"
                }
                // Preflight loader inputs without guessing metadata filenames; the outer lease excludes other writers.
                var entries = 0
                var metadataBytes = 0L
                val apkPaths = mutableListOf<Path>()
                Files.newDirectoryStream(directory).use { children ->
                    for (child in children) {
                        check(++entries <= 16) { "APK provider directory has too many entries" }
                        val attrs = attributes(child)
                        check(attrs.isRegularFile) { "APK provider directory contains a non-file" }
                        if (child.fileName.toString().endsWith(".apk")) {
                            check(attrs.size() in 1..(512L * 1024 * 1024)) { "APK exceeds its size bound" }
                            apkPaths.add(child)
                        } else {
                            metadataBytes += attrs.size()
                            check(metadataBytes <= 1024 * 1024) { "APK metadata exceeds its size bound" }
                        }
                    }
                }
                check(apkPaths.size == 1) { "Acceptance requires exactly one APK, without splits or stale APKs" }
                val metadata = checkNotNull(loader.load(apkDirectory)) { "AGP built-artifact metadata is missing" }
                check(
                    metadata.artifactType.name() == SingleArtifact.APK.name() &&
                        metadata.applicationId == applicationId && metadata.variantName == variantName &&
                        metadata.elements.size == 1,
                ) { "AGP built-artifact metadata does not match this component" }
                val artifact = metadata.elements.single()
                check(
                    artifact.outputType == VariantOutputConfiguration.OutputType.SINGLE && artifact.filters.isEmpty(),
                ) {
                    "Acceptance does not admit split or universal APK outputs"
                }
                val apkPath = ownedPath(artifact.path)
                check(
                    apkPath == Path.of(artifact.outputFile) && apkPath == apkPaths.single() &&
                        apkPath.parent == directory,
                ) {
                    "AGP selected APK does not match the sole physical provider output"
                }
                check(seenSources.add(manifestPath) && seenSources.add(apkPath)) { "Acceptance source paths overlap" }
                check(applicationId.length in 1..255 && variantName.length in 1..128) { "Oversized component identity" }
                val versionName = artifact.versionName
                check(versionName == null || (versionName.length <= 4096 && versionName.all { it.code >= 32 })) {
                    "Oversized version name or control character"
                }
                val retainedPath = ownedPath(output.resolve(retainedName), mustExist = false)
                check(manifestPath != retainedPath) { "Generated and retained manifest paths must differ" }
                val manifest = snapshot(manifestPath, 1024L * 1024, retain = true)
                val apk = snapshot(apkPath, 512L * 1024 * 1024)
                manifestCopies.add(retainedPath to checkNotNull(manifest.content))
                return linkedMapOf(
                    "componentKind" to kind,
                    "applicationId" to applicationId,
                    "variantName" to variantName,
                    "manifest" to linkedMapOf(
                        "sourcePath" to relative(manifestPath),
                        "retainedPath" to relative(retainedPath),
                        "bytes" to manifest.bytes,
                        "sha256" to manifest.sha256,
                        "producerTasks" to producerTasks(manifestFiles),
                    ),
                    "apk" to linkedMapOf(
                        "providerPath" to relative(directory),
                        "path" to relative(apkPath),
                        "bytes" to apk.bytes,
                        "sha256" to apk.sha256,
                        "producerTasks" to producerTasks(apkFiles),
                        "outputType" to artifact.outputType.name,
                        "filters" to emptyList<String>(),
                    ),
                    "metadataProjection" to linkedMapOf(
                        "kind" to "AGP_BUILT_ARTIFACTS_API_PROJECTION",
                        "artifactType" to metadata.artifactType.name(),
                        "applicationId" to metadata.applicationId,
                        "variantName" to metadata.variantName,
                        "elementCount" to metadata.elements.size,
                        "versionCode" to artifact.versionCode,
                        "versionName" to versionName,
                    ),
                )
            }

            val components = linkedMapOf(
                "app" to component(
                    "APPLICATION", variant.applicationId.get(), variant.name,
                    appManifest, appApks, appApkDirectory.get(), appLoader, "app-merged-AndroidManifest.xml",
                ),
                "test" to component(
                    "ANDROID_TEST", androidTest.applicationId.get(), androidTest.name,
                    testManifest, testApks, testApkDirectory.get(), testLoader, "test-merged-AndroidManifest.xml",
                ),
            )
            val report = linkedMapOf(
                "schemaVersion" to 1,
                "taskPath" to owner.path,
                "variantName" to variant.name,
                "components" to components,
            )
            val reportBytes = (JsonOutput.prettyPrint(JsonOutput.toJson(report)) + "\n").toByteArray(Charsets.UTF_8)
            check(reportBytes.size <= 1024 * 1024) { "Acceptance map exceeds its size bound" }
            manifestCopies.forEach { (path, content) -> writeNew(path, content) }
            // Last output, never an original metadata dump or a source/host/receipt attestation.
            writeNew(output.resolve("artifacts.json"), reportBytes)
        }
    }
}
