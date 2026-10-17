# P2pKit

[![Maven Central](https://img.shields.io/maven-central/v/io.github.apdelrahman1911/p2p-core?label=Maven%20Central)](https://central.sonatype.com/artifact/io.github.apdelrahman1911/p2p-core/0.8.0-rc2)
[![CI](https://github.com/p2pKit/P2pKit/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/p2pKit/P2pKit/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)

P2pKit is a Kotlin Multiplatform library for authenticated peer discovery,
messaging, and durable file transfer over a reachable local network. It
supports Android, JVM/Desktop, and iOS through one transport-independent API.

**Development version:** `0.8.0-SNAPSHOT` (unpublished work toward the next 0.8 release).
**Latest published version:** `0.8.0-rc2`.

`0.8.0-rc2` is available from Maven Central under `io.github.apdelrahman1911`.
The [matching development samples](https://github.com/p2pKit/P2pKit/releases/tag/samples-v0.8.0-rc2)
provide an Android APK, Windows x64 MSI, macOS ARM64 DMG and Linux x64 DEB.
The library and four applications come from the same approved source commit;
see the [release record](docs/releases/0.8.0-rc2.md) for hashes and verification.

This is a release candidate, not a production-audit or physical-device pass.
Campaign status remains governed by the
[validation authority](docs/validation/README.md#current-status).
Published tags and artifacts are immutable; later snapshot changes and tests
must not be described as evidence for the released binaries.

## What it provides

- Android API 24+, JVM 17, and iOS/iPadOS 14+ through `iosArm64`,
  `iosSimulatorArm64`, and `iosX64`.
- Android/JVM JmDNS and Apple Bonjour discovery with TCP transport.
- Authenticated protocol v2 by default using
  `Noise_XX_25519_ChaChaPoly_SHA256` and persistent X25519 identities.
- Independent advertising/discovery states, typed failures, bounded framing,
  keepalive, and outgoing-session reconnect.
- Authenticated metadata envelopes and streaming file transfer with negotiated
  SHA-256 verification and receiver durable-commit acknowledgement.
- Coroutine/Flow APIs and explicit host ownership of lifecycle and permission
  presentation.

P2pKit does not provide internet signaling, NAT traversal, relays, accounts,
rooms, or application-level authorization. Both peers must already be mutually
reachable on the LAN. Guest/enterprise Wi-Fi may block multicast or peer TCP.

## Optional organization-LAN RPC

The new optional [`p2p-rpc`](docs/rpc/README.md) module adds one explicitly
selected authenticated host, dial-only clients, registered typed procedures,
bounded recovery, administrator pairing and best-effort notifications. It
reuses core/LAN rather than changing ordinary P2P defaults.

RPC is included in the `0.8.0-rc2` Maven publication and integrated as a section
in the existing samples. **Windows sample RPC Host/Client remains unavailable**
because productive trusted DLL loading and protected-profile integration are
unfinished; the other sample features and MSI are preserved. See the
[Windows prerelease limitations](docs/rpc/windows-release-scope.md) and
[RPC qualification requirements](docs/rpc/qualification.md). Publication and
hosted checks do not imply completed physical-network or installed-app testing.

## Install

Use `mavenCentral()` and keep all P2pKit modules on the same version.
Supported consumer languages are Kotlin (Android, JVM/Desktop, and KMP) and
Swift through the source-built XCFramework. Java is not supported as an
end-to-end SDK integration; see the [Java interop limitations](docs/compatibility.md#consumer-languages-and-java-interop).

| Published module | Purpose |
| --- | --- |
| `io.github.apdelrahman1911:p2p-core:0.8.0-rc2` | Public API, protocol, security, sessions, and file transfer |
| `io.github.apdelrahman1911:p2p-transport-lan:0.8.0-rc2` | Multiplatform LAN discovery and TCP transport |
| `io.github.apdelrahman1911:p2p-rpc:0.8.0-rc2` | Optional typed organization-LAN RPC |
| `io.github.apdelrahman1911:p2p-network-provisioning-android:0.8.0-rc2` | Optional Android provisioning sidecar |
| `io.github.apdelrahman1911:p2p-network-provisioning-desktop:0.8.0-rc2` | Optional JVM/Desktop manual-endpoint sidecar |

### Kotlin Multiplatform

```kotlin
kotlin {
    sourceSets {
        commonMain.dependencies {
            implementation("io.github.apdelrahman1911:p2p-core:0.8.0-rc2")
            implementation("io.github.apdelrahman1911:p2p-transport-lan:0.8.0-rc2")
        }
    }
}
```

### Android

```kotlin
dependencies {
    implementation("io.github.apdelrahman1911:p2p-transport-lan-android:0.8.0-rc2")
    // Optional hotspot/Wi-Fi provisioning:
    implementation("io.github.apdelrahman1911:p2p-network-provisioning-android-android:0.8.0-rc2")
}
```

### JVM/Desktop

```kotlin
dependencies {
    implementation("io.github.apdelrahman1911:p2p-transport-lan-jvm:0.8.0-rc2")
    // Optional manual-endpoint provisioning:
    implementation("io.github.apdelrahman1911:p2p-network-provisioning-desktop:0.8.0-rc2")
}
```

Kotlin Multiplatform root coordinates select their platform variants. The
complete 21-coordinate publication set is recorded in the
[`0.8.0-rc2` release record](docs/releases/0.8.0-rc2.md).

### Direct Swift application

The Maven publications serve Kotlin Multiplatform consumers. A direct Swift
application builds `P2pKitShared.xcframework` from this repository:

```bash
./gradlew :p2p-transport-lan:assembleP2pKitSharedReleaseXCFramework
```

The maintained Swift sample and provenance-checked integration live under
[`samples/iosApp`](samples/iosApp).

Current development builds with Kotlin 2.4.10 while retaining the iOS 14
library floor explicitly. Kotlin Multiplatform applications that link their
own Apple binary must apply the iOS 14 Kotlin/Native override documented in
the [compatibility policy](docs/compatibility.md); repository-built
XCFrameworks apply it and verify every Mach-O slice automatically.

## Secure quick start

Authenticated v2 is the default and fails closed. Exchange the full pairing QR
or fingerprint through a trusted channel, then pin the expected identity:

```kotlin
import dev.p2pkit.core.AppId
import dev.p2pkit.core.P2pKit
import dev.p2pkit.core.P2pMessage
import dev.p2pkit.transport.lan.lan
import kotlinx.coroutines.flow.first

val kit = P2pKit.create {
    appId = AppId("com.example.transfer")
    deviceName = "My device"
    transports { lan() } // Android: lan(applicationContext)
}

kit.start()
kit.startAdvertising()
kit.startDiscovery()

val expectedFingerprint =
    requireNotNull(kit.parsePeerPairingQr(qrFromTrustedChannel))
val peer = kit.peers.first { it.isNotEmpty() }.first()
val session = kit.connect(peer, expectedFingerprint)
session.send(P2pMessage.Text("hello"))
```

For an executable discovered-peer example, the CLI's `pairing` and
`connect-pinned <peer-alias> <full-pairing-QR>` commands implement this exchange;
see the [sample pairing walkthrough](docs/guides/samples.md#pairing-with-a-verified-fingerprint).
The interactive samples' incoming admission remains development-only, not an
allowlist. The KMP sample separately demonstrates `PinnedOnly` admission.

Subscribe to `incomingSessions` before advertising and attach each
`session.incoming` collector promptly; these are hot event streams. `send()`
confirms a local transport write, not remote application processing. Add
domain-level IDs, ordering, deduplication, acknowledgements, and repair where
your application requires them.

## Platform setup

### Android

Initialize secure identity storage once from `Application.onCreate()` before
constructing a kit:

```kotlin
class MyApplication : Application() {
    override fun onCreate() {
        super.onCreate()
        P2pKitAndroid.initialize(this)
    }
}
```

Declare the base LAN permissions:

```xml
<uses-permission android:name="android.permission.INTERNET" />
<uses-permission android:name="android.permission.ACCESS_NETWORK_STATE" />
<uses-permission android:name="android.permission.ACCESS_WIFI_STATE" />
<uses-permission android:name="android.permission.CHANGE_WIFI_MULTICAST_STATE" />
```

For an app **targeting SDK 37+**, raw LAN additionally needs the dangerous
`android.permission.ACCESS_LOCAL_NETWORK` grant **on Android 17/API 37+**.
Declare it in that final app (not in apps targeting SDK 36 or lower):

```xml
<uses-permission android:name="android.permission.ACCESS_LOCAL_NETWORK" />
```

The current development source reports this live grant as
`P2pPermission.LocalNetwork` through `kit.permissions`; this is not a claim
about older published binaries. The app requests access using Android's
permission APIs and rechecks the live result before retrying its intended
operation. Denial/revocation must not trigger automatic start or prompt loops.
Preflight direct `start()`/`connect()` calls too; only the advertising/discovery
feature entry points perform the SDK permission gate. A preflight cannot prevent
a later OS revocation, so handle operation failures and keep cleanup available.
Android 16's explicit local-network compatibility opt-in is a separate test
mode, not ordinary API 36 behavior. See the
[Android policy](https://developer.android.com/privacy-and-security/local-network-permission#android-17-enforcement).

The optional network-provisioning sidecar has separate runtime permission and
system-state requirements. Query its permission manager immediately before a
provisioning operation; do not gate the base LAN transport on those permissions.

### iOS

The final application Info.plist must contain a nonblank local-network reason
and the secure-v2 Bonjour service:

```xml
<key>NSLocalNetworkUsageDescription</key>
<string>Find and connect to nearby devices on your local network.</string>
<key>NSBonjourServices</key>
<array>
    <string>_p2pkit2._tcp</string>
</array>
```

Keep these values in the source that generates the final plist. The sample uses
[`samples/iosApp/project.yml`](samples/iosApp/project.yml). Add the legacy
`_p2pkit._tcp` service only for an explicitly configured deprecated plaintext-v1
build; v1 and v2 do not interoperate or downgrade.

### JVM/Desktop

Core intentionally has no plaintext secure-identity default. Install a durable,
confidential, integrity-protected operating-system-backed store:

```kotlin
val kit = P2pKit.create {
    appId = AppId("com.example.transfer")
    deviceName = "Desktop"
    jvmSecureIdentityStore(protectedIdentityStore)
    transports { lan() }
}
```

`putIfAbsent` must be atomic across processes and durable before returning.
The samples' in-memory stores are development-only.

## Modules and repository structure

| Directory / project | Purpose |
| --- | --- |
| `library/p2p-core` / `:p2p-core` | API, protocol, security, sessions, file transfer |
| `library/p2p-transport-lan` / `:p2p-transport-lan` | JmDNS/Bonjour and TCP transport |
| `library/p2p-network-provisioning-android` | Optional Android network provisioning |
| `library/p2p-network-provisioning-desktop` | Optional JVM manual-endpoint provisioning |
| `library/p2p-rpc` / `:p2p-rpc` | Optional organization-LAN RPC (unqualified feature source) |
| `samples/` | Android, JVM CLI, Desktop UI, KMP, iOS, diagnostics, and optional RPC examples |
| `buildSrc/` | Build provenance and canonical publication metadata logic |
| `scripts/` | Release, security, publication, consumer, and repository gates |

See the [architecture overview](docs/architecture/overview.md) and
[current specification](docs/architecture/specification.md).

## Security and stability

Discovery TXT records, names, peer IDs, and `AppId` are untrusted. The default
`RejectUnknown` policy requires an exact trusted identity. The explicit-risk
`AcceptAnyAuthenticatedSameApp` policy encrypts and authenticates key possession
but does not identify a person/device; it requires application-level admission.
There is no automatic fallback to plaintext.

Public collection models are snapshot values. Text/binary messages are capped
at 4 MiB. File transfer is streaming and completes only after the authenticated
receiver verifies the sender's prepared SHA-256 snapshot and completes the
destination's platform durability contract. The JVM destination fsyncs file
content and atomically publishes it; POSIX hosts also fsync the parent
directory. The public JDK exposes no equivalent parent-directory barrier on
Windows, so sudden power loss may lose the renamed directory entry there.

Use the [operational limits reference](docs/reference/limits.md) for current
admission, receive-backlog, framing, discovery and timeout policies, their
observable failures, and the settings applications can configure.

Read the [security model](docs/security/model.md),
[compatibility policy](docs/compatibility.md), and
[0.6-to-0.7 migration guide](docs/guides/migrating-to-0.7.md).
That guide retains its historical security-transition scope. Upgrading from
0.7 to 0.8 also requires reviewing the [0.8 behavior changes](CHANGELOG.md)
and [RPC/Windows limitations](docs/rpc/windows-release-scope.md).

## Validation status

The [`0.8.0-rc2` release record](docs/releases/0.8.0-rc2.md) records the exact
main-source modular qualification, API/ABI, strict Dokka, dependency/SBOM,
publication shape and consumers, Swift/XCFramework checks, and native ARM64
and Intel simulator execution. Maven publication separately verified signed
remote bytes and consumers; the sample publisher verified complete anonymous
download hashes for all four applications and their public metadata.

These results belong to the released commit, not future `0.8.0-SNAPSHOT` changes.
A resolved-graph SBOM is not a scan of every distributed binary; a successful
build or simulator test is not a real-device or installed-application result.
The `iosArm64` device target still needs external hardware for runtime testing.
One focused API37 permission/recreation/TCP instrumentation case is authored;
its execution must be recorded separately, and it is not a general device suite.
Android host JVM tests (including Robolectric shadows) are not ART or physical-device evidence.

The [canonical six-area status table](docs/validation/README.md#current-status)
records external campaign progress and links each execution handbook. In
particular, the CLI/Desktop row's partial automated coverage is not a completed
fault-injection or real-display campaign. See
[automated scope and history](docs/testing/validation-status.md) for the distinct
host/target evidence. Do not treat this release candidate as fully production
validated or independently audited.

## Contributing and support

- [Mac continuation handoff](docs/testing/mac-handoff.md) (start from `main`)
- [In-progress audit checkpoint](AUDIT_CHECKPOINT.md) (not a release approval)
- [Documentation index](docs/README.md)
- [Contributing](CONTRIBUTING.md)
- [Security reporting](SECURITY.md)
- [Support policy](SUPPORT.md)
- [Changelog](CHANGELOG.md)

P2pKit is licensed under the [Apache License 2.0](LICENSE).
