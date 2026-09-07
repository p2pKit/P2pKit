import java.time.Duration

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
    }

    buildFeatures {
        compose = true
        buildConfig = true
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
