# Compatibility policy

P2pKit is currently a release candidate. The project protects published
artifacts and reviews API/protocol compatibility, but reserves the right to
make documented breaking changes before `1.0.0` in a new version.

- Published Maven coordinates and Git tags are immutable.
- All P2pKit modules used by one application should have the same version.
- Kotlin and Java compatibility is guarded by committed ABI baselines.
- Swift consumes a source-built XCFramework; generated names and exported ABI
  are checked by Apple builds and Swift warnings-as-errors gates.
- Protocol v2 changes require explicit negotiation and must fail closed with
  older peers. Protocol v1 and v2 never silently downgrade or share discovery.
- A repository directory move does not change Gradle project names, artifact
  IDs, packages, public API, or wire behavior.

Supported build targets for the `0.7` line are Android API 24+, JVM 17, and
iOS/iPadOS 14+ through `iosArm64`, `iosSimulatorArm64`, and `iosX64`. The iOS
sample currently targets iOS 15 for its application UI; that does not raise
the library compatibility floor. Current development uses Kotlin 2.4.10,
whose default linked-binary floor is iOS 15. Repository-built XCFrameworks
override that default with the canonical `IOS_MIN_VERSION=14.0` property, and
the release gate inspects every Mach-O device/simulator slice.

Kotlin Multiplatform applications that link their own iOS binary with Kotlin
2.4 must apply the same documented Kotlin/Native override to each binary:

```kotlin
kotlin {
    targets.withType<org.jetbrains.kotlin.gradle.plugin.mpp.KotlinNativeTarget>()
        .configureEach {
            binaries.configureEach {
                freeCompilerArgs +=
                    "-Xoverride-konan-properties=minVersion.ios=14.0"
            }
        }
}
```

This changes only the deployment floor; it does not make simulator builds
physical-device evidence. Exact toolchain versions are locked in the Gradle
wrapper, version catalog, and CI workflows. Physical validation at the Android
and Apple minimums remains pending until the evidence handbook is completed.
