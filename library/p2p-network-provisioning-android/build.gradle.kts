import dev.p2pkit.build.P2pPomMetadata
import kotlinx.validation.KotlinApiBuildTask
import org.jetbrains.kotlin.gradle.tasks.KotlinCompile
import javax.xml.parsers.DocumentBuilderFactory

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
            implementation(libs.robolectric.runner)
        }
    }
}

// Resolve each SDK separately: one configuration would conflict-resolve the
// four versions of android-all-instrumented to a single (incorrect) SDK. These
// test-only inputs use the same committed locks/checksums as other artifacts.
val robolectricSdks = listOf(
    "26" to libs.robolectric.sdk26,
    "29" to libs.robolectric.sdk29,
    "30" to libs.robolectric.sdk30,
    "35" to libs.robolectric.sdk35,
).map { (api, artifact) ->
    configurations.create("robolectricSdk$api") {
        isCanBeConsumed = false
        isCanBeResolved = true
        isTransitive = false
        dependencies.add(project.dependencies.create(artifact.get()))
    }
}
val prepareRobolectricSdks = tasks.register<Sync>("prepareRobolectricSdks") {
    from(robolectricSdks)
    into(layout.buildDirectory.dir("robolectric-sdks"))
}
tasks.withType<Test>().configureEach {
    dependsOn(prepareRobolectricSdks)
    // Task dependencies alone do not invalidate a cached Test result when an
    // SDK changes: the framework JAR bytes must also be explicit test inputs.
    inputs.files(robolectricSdks)
        .withPropertyName("robolectricFrameworks")
        .withNormalizer(ClasspathNormalizer::class.java)
    // Robolectric must not download unchecked runtime JARs outside Gradle.
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
}

val verifyAndroidAdapterTests = tasks.register("verifyAndroidAdapterTests") {
    group = "verification"
    description = "Requires executed, non-skipped framework adapter coverage on every pinned host SDK."
    // AGP registers this host-test task after the module build script runs.
    dependsOn("testAndroidHostTest")
    val results = layout.buildDirectory.dir("test-results/testAndroidHostTest")
    inputs.dir(results)
    doLast {
        val factory = DocumentBuilderFactory.newInstance().apply {
            setFeature("http://apache.org/xml/features/disallow-doctype-decl", true)
            setFeature("http://xml.org/sax/features/external-general-entities", false)
            setFeature("http://xml.org/sax/features/external-parameter-entities", false)
        }
        val expected = mapOf(
            "WifiManagerWrapperLegacyHotspotTest" to setOf(26, 29),
            "WifiManagerWrapperModernHotspotTest" to setOf(30, 35),
            "WifiManagerWrapperJoinTest" to setOf(29, 30, 35)
        )
        expected.forEach { (suite, sdks) ->
            val report = results.get().file("TEST-dev.p2pkit.provisioning.android.$suite.xml").asFile
            check(report.isFile) { "Missing Android adapter test results: $suite" }
            val root = factory.newDocumentBuilder().parse(report).documentElement
            check(root.getAttribute("tests").toInt() >= sdks.size) { "Empty Android adapter suite: $suite" }
            for (failure in listOf("failures", "errors", "skipped")) {
                check(root.getAttribute(failure).toInt() == 0) { "$suite reports $failure" }
            }
            val output = root.getElementsByTagName("system-out").item(0)?.textContent.orEmpty()
            sdks.forEach { sdk ->
                check(output.lineSequence().any { it == "Android adapter framework SDK=$sdk" }) {
                    "$suite did not execute framework SDK $sdk"
                }
            }
            logger.lifecycle("Android adapter: $suite executed SDKs ${sdks.sorted()} (host shadows, not ART)")
        }
    }
}
tasks.named("check") { dependsOn(verifyAndroidAdapterTests) }

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
