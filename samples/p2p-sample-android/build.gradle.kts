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

    implementation(platform(libs.androidx.compose.bom))
    implementation(libs.androidx.compose.ui)
    implementation(libs.androidx.compose.ui.tooling.preview)
    implementation(libs.androidx.compose.material3)
    testImplementation(kotlin("test-junit"))
}
