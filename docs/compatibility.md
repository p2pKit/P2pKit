# Compatibility policy

P2pKit is currently a release candidate. The project protects published
artifacts and reviews API/protocol compatibility, but reserves the right to
make documented breaking changes before `1.0.0` in a new version.

- Published Maven coordinates and Git tags are immutable.
- All P2pKit modules used by one application should have the same version.
- Public Kotlin ABI is guarded by committed JVM/KLIB baselines plus
  Kotlin-metadata-aware Android bytecode baselines for Android-only APIs.
  These checks do not promise Java-source callability of the whole JVM API.
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

## Public sealed hierarchies

Public sealed hierarchies, including `PeerAuthorizationPolicy`, are not
promised to keep the same variants forever. The pre-`1.0.0` breaking-change
reservation above also applies to variant additions in a new version,
including a new minor version. Such an addition is a source-breaking change
for consumers with an exhaustive `when` and must be documented and reviewed
through the API-baseline gates; passing an ABI check alone does not establish
consumer source compatibility. This does not authorize changes to published
`0.7.0-rc3` artifacts or baselines.

Consumers can keep exhaustive branches to make recompilation require review
of each new variant. Where UI or error mapping must tolerate additions, use
a conservative `else` branch, such as an unknown/unsupported display state.
Never treat an unfamiliar authorization policy as permission to admit a peer.
The SDK's authorization checks remain exhaustive and fail closed.

## JVM-family constant ABI checks

Kotlin visibility and JVM field visibility differ: a `const val` in a private
companion can still become a public static field on its outer class. The Kotlin
JVM dumper omits some such fields; Android's metadata-aware dumper records the
existing provisioning constants, but can omit internal constants in public file
facades. `checkJvmPublicConstants` / `checkAndroidPublicConstants` therefore inspect
actual compiled fields using JDK `javap`, under the normal ABI and module `check`
tasks. Their scope is owners in the committed Kotlin-visible baselines, not every
raw JVM-internal class, and field signatures, not constant values.

New unrecorded constants fail. Only JVM `NOT_IN_V01` and Desktop
`DEFAULT_POLL_INTERVAL_MS` need explicit retained-field exceptions; Android's
`NOT_IN_V01`, `OS_CALLBACK_TIMEOUT_MS` and `CLOSE_TIMEOUT_MS` are already baselined.
Do not remove or rename these published RC2/RC3 fields in the stabilization line,
or add newly leaked fields to the exception list. New implementation constants
need an explicit `private` modifier on the property, not just its companion.

On Apple, full KLIB metadata can contain `NOT_IN_V01` inside its **private**
companion; it is not an exported Native ABI member. The Android/Desktop sidecars
have no Native targets. This guard adds no Java SDK support or wire guarantee.

Future breaking-version follow-up: decide whether to retire the legacy fields.
Any approved removal must coordinate declarations, Android baselines, retained
JVM exceptions and `check_rc2_legacy_jvm_symbols()` in the publication gate.
Until that migration is explicitly approved, preserve all of them.

## Consumer languages and Java interop

Supported consumers are **Kotlin** on Android, JVM/Desktop and KMP, and
**Swift** through the source-built XCFramework. The library does not provide
a Java-friendly facade for end-to-end kit creation and identity handling.

On JVM and Android, string-backed Kotlin value classes such as `AppId`,
`PeerId` and `PeerFingerprint` produce mangled members, for example
`setAppId-6QwJUv8`. Hyphens in those names prevent ordinary Java-source calls.
Java can invoke `P2pKit.Companion.create` with a Kotlin `Function1` returning
`Unit.INSTANCE`, but cannot set the required `P2pKitBuilder.appId` through a
Java-callable setter. The Kotlin `internal` builder constructor is actually
public in JVM bytecode; its absence from the Kotlin-aware baseline is not
proof of JVM privacy and does not solve the missing setter.

Selected current JVM/Android boundaries:

| Surface | Java-source behavior |
| --- | --- |
| `P2pKitBuilder.appId` | Mangled accessors; the required DSL field cannot be configured directly. |
| `P2pKit.appId`, `localPeerId`, `localFingerprint`, fingerprint-pinned `connect`, `lastSeen`, `parsePeerPairingQr` | Mangled members, not directly callable. |
| `PeerFingerprint.parse` / `parseOrNull`; `Peer` / `PeerIdentity` construction and typed identity getters | Mangled parsers/getters or synthetic-only public constructors, not directly callable. |
| `P2pSession.id`, `peer`, `send`, `sendFile` | Unmangled accessors/methods, but suspend calls still require Kotlin continuations and streams use Kotlin Flow. Returned identity types retain the limits above. |
| `P2pMessage.Text` / `Binary`; `P2pError.FileTransferFailed` | Constructors and normal getters are callable. This is a narrow data/error-mapping surface, not a complete Java SDK. |

In particular, the [file-transfer error mapping contract](architecture/specification.md#file-transfer)
remains supported: Java can read `FileTransferFailed.getKind()`, `getPhase()`,
`getRetryability()` and `getTransferId()` without reflection or mangled names.
The publication consumer gate includes this narrow Java compilation smoke;
it does not establish Java kit construction or coroutine integration.

For an otherwise Java application, keep kit creation, identity parsing and
coroutine/Flow adaptation in an application-owned Kotlin boundary using the
public Kotlin API. Do not depend on compiler-internal members or reflection
over mangled names as a supported workaround. Existing published signatures
are unchanged by this documentation; no Java facade is introduced.
