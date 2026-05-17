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
    val iosTargets = listOf(iosX64(), iosArm64(), iosSimulatorArm64())
    iosTargets.forEach { target ->
        // Wraps NW_PARAMETERS_DISABLE_PROTOCOL / NW_PARAMETERS_DEFAULT_CONFIGURATION
        // in a static-inline C helper so Kotlin never has to box those
        // void-returning block globals as kotlin.Any. See
        // src/nativeInterop/cinterop/p2pkit_nw.h for the rationale.
        target.compilations.getByName("main") {
            cinterops.create("p2pkit_nw") {
                defFile = project.file("src/nativeInterop/cinterop/p2pkit_nw.def")
            }
        }
        // Sample-app consumers want a single Swift-importable framework that
        // bundles :p2p-core's types alongside the LAN transport extension.
        // `export(project(":p2p-core"))` lifts the dependency's public API
        // into the framework's Swift surface so consumers can reference
        // P2pKit / AppId / Peer / P2pMessage / ... directly.
        // Run `./gradlew :p2p-transport-lan:linkDebugFrameworkIosSimulatorArm64`
        // (or `linkReleaseFrameworkIosArm64` for device builds) and drop the
        // resulting `.framework` into Xcode — see docs/ios-sample-app/.
        target.binaries.framework {
            baseName = "P2pKitShared"
            isStatic = false
            export(project(":p2p-core"))
        }
    }

    sourceSets {
        commonMain.dependencies {
            // `api` rather than `implementation`: the iOS framework's
            // `export(project(":p2p-core"))` above requires the dependency to
            // be in the public API surface. Has no effect on the JVM/Android
            // consumers (their build doesn't surface it differently).
            api(project(":p2p-core"))
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
