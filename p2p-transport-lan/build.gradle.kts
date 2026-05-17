plugins {
    alias(libs.plugins.kotlin.multiplatform)
    alias(libs.plugins.android.kmp.library)
}

kotlin {
    jvmToolchain(17)
    jvm()

    android {
        namespace = "dev.p2pkit.transport.lan"
        compileSdk = libs.versions.android.compileSdk.get().toInt()
        minSdk = libs.versions.android.minSdk.get().toInt()
    }

    // v0.3.0-dev: iOS LAN/TCP via Bonjour + Network.framework. Same public API
    // as JVM/Android (`transports { lan() }`), backed by NWBrowser / NWListener
    // / NWConnection. Requires iOS 13+; minimum is enforced by the Network
    // framework symbols themselves.
    iosX64()
    iosArm64()
    iosSimulatorArm64()

    sourceSets {
        commonMain.dependencies {
            implementation(project(":p2p-core"))
            implementation(libs.kotlinx.coroutines.core)
        }
        commonTest.dependencies {
            implementation(kotlin("test"))
            implementation(libs.kotlinx.coroutines.test)
        }
        jvmMain.dependencies {
            implementation(libs.jmdns)
        }
    }
}
