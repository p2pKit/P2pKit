pluginManagement {
    repositories {
        google {
            content {
                includeGroupByRegex("com\\.android.*")
                includeGroupByRegex("com\\.google.*")
                includeGroupByRegex("androidx.*")
            }
        }
        mavenCentral()
        gradlePluginPortal()
    }
}

dependencyResolutionManagement {
    repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS)
    repositories {
        google {
            content {
                // These exact locked Kotlin compiler/ABI inputs are published on Central.
                // A failed unrelated Google lookup must not disable their resolution.
                excludeVersion("org.jetbrains.kotlin", "kotlin-metadata-jvm", "2.4.20")
                excludeVersion("org.jetbrains.kotlin", "kotlin-script-runtime", "2.4.20")
                excludeVersion("org.jetbrains.kotlin", "kotlin-scripting-common", "2.4.20")
                excludeVersion("org.jetbrains.kotlin", "kotlin-scripting-compiler-embeddable", "2.4.20")
                excludeVersion("org.jetbrains.kotlin", "kotlin-scripting-compiler-impl-embeddable", "2.4.20")
                excludeVersion("org.jetbrains.kotlin", "kotlin-scripting-jvm", "2.4.20")
                excludeVersion("org.jetbrains.kotlin", "kotlin-serialization-compiler-plugin-embeddable", "2.4.20")
                excludeVersion("org.jetbrains.kotlin", "kotlin-stdlib", "2.4.20")
                excludeVersion("org.jetbrains", "annotations", "13.0")
            }
        }
        mavenCentral()
    }
}

rootProject.name = "p2pkit"

include(":p2p-core")
include(":p2p-transport-lan")
include(":p2p-rpc")
include(":p2p-network-provisioning-desktop")
include(":p2p-network-provisioning-android")
include(":p2p-sample-desktop")
include(":p2p-sample-desktop-ui")
include(":p2p-sample-android")
include(":sample-kmp-shared")
include(":p2p-sample-diagnostics")
include(":p2p-sample-rpc")
include(":iosApp")

project(":p2p-core").projectDir = file("library/p2p-core")
project(":p2p-transport-lan").projectDir = file("library/p2p-transport-lan")
project(":p2p-rpc").projectDir = file("library/p2p-rpc")
project(":p2p-network-provisioning-desktop").projectDir = file("library/p2p-network-provisioning-desktop")
project(":p2p-network-provisioning-android").projectDir = file("library/p2p-network-provisioning-android")
project(":p2p-sample-desktop").projectDir = file("samples/p2p-sample-desktop")
project(":p2p-sample-desktop-ui").projectDir = file("samples/p2p-sample-desktop-ui")
project(":p2p-sample-android").projectDir = file("samples/p2p-sample-android")
project(":sample-kmp-shared").projectDir = file("samples/sample-kmp-shared")
project(":p2p-sample-diagnostics").projectDir = file("samples/p2p-sample-diagnostics")
project(":p2p-sample-rpc").projectDir = file("samples/p2p-sample-rpc")
project(":iosApp").projectDir = file("samples/iosApp")
