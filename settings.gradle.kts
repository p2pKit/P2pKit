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
        google()
        mavenCentral()
    }
}

rootProject.name = "p2pkit"

include(":p2p-core")
include(":p2p-transport-lan")
include(":p2p-sample-desktop")
include(":p2p-sample-desktop-ui")
include(":p2p-sample-android")
include(":sample-kmp-shared")
