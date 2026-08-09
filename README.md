# P2pKit

[![Maven Central](https://img.shields.io/maven-central/v/io.github.apdelrahman1911/p2p-core?label=Maven%20Central)](https://central.sonatype.com/artifact/io.github.apdelrahman1911/p2p-core/0.7.0-rc2)
[![CI](https://github.com/p2pKit/P2pKit/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/p2pKit/P2pKit/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)

P2pKit is a Kotlin Multiplatform library for authenticated peer discovery,
messaging, and durable file transfer over a reachable local network. It
supports Android, JVM/Desktop, and iOS through one transport-independent API.

**Current source version:** `0.7.0-rc3` release candidate.
**Latest published version:** `0.7.0-rc2`.

`0.7.0-rc2` is available from Maven Central under
`io.github.apdelrahman1911`. It is a release candidate: the automated release
gates are extensive, but the external validation areas listed below remain
pending.

The RC3 source is the candidate for the pending physical-device,
hostile-network, independent-interoperability, and professional-review
campaigns. Until RC3 is published, the installation coordinates below remain
on the latest remotely available version, RC2.

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

## Install

Use `mavenCentral()` and keep all P2pKit modules on the same version.

| Published module | Purpose |
| --- | --- |
| `io.github.apdelrahman1911:p2p-core:0.7.0-rc2` | Public API, protocol, security, sessions, and file transfer |
| `io.github.apdelrahman1911:p2p-transport-lan:0.7.0-rc2` | Multiplatform LAN discovery and TCP transport |
| `io.github.apdelrahman1911:p2p-network-provisioning-android:0.7.0-rc2` | Optional Android provisioning sidecar |
| `io.github.apdelrahman1911:p2p-network-provisioning-desktop:0.7.0-rc2` | Optional JVM/Desktop manual-endpoint sidecar |

### Kotlin Multiplatform

```kotlin
kotlin {
    sourceSets {
        commonMain.dependencies {
            implementation("io.github.apdelrahman1911:p2p-core:0.7.0-rc2")
            implementation("io.github.apdelrahman1911:p2p-transport-lan:0.7.0-rc2")
        }
    }
}
```

### Android

```kotlin
dependencies {
    implementation("io.github.apdelrahman1911:p2p-transport-lan-android:0.7.0-rc2")
    // Optional hotspot/Wi-Fi provisioning:
    implementation("io.github.apdelrahman1911:p2p-network-provisioning-android-android:0.7.0-rc2")
}
```

### JVM/Desktop

```kotlin
dependencies {
    implementation("io.github.apdelrahman1911:p2p-transport-lan-jvm:0.7.0-rc2")
    // Optional manual-endpoint provisioning:
    implementation("io.github.apdelrahman1911:p2p-network-provisioning-desktop:0.7.0-rc2")
}
```

Kotlin Multiplatform root coordinates select their platform variants. The
complete 15-coordinate publication set is recorded in the
[`0.7.0-rc2` release record](docs/releases/0.7.0-rc2.md).

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
| `samples/` | Android, JVM CLI, Desktop UI, KMP, iOS, and shared diagnostics samples |
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
receiver verifies the sender's prepared SHA-256 snapshot and durably commits
the destination.

Read the [security model](docs/security/model.md),
[compatibility policy](docs/compatibility.md), and
[0.6-to-0.7 migration guide](docs/guides/migrating-to-0.7.md).

## Validation status

The automated module/platform, ABI, strict Dokka, publication-shape, isolated
consumer, SBOM, signing, provenance, Swift warnings-as-errors, and XCFramework
gates passed for the published `0.7.0-rc2` commit. This does not replace
external evidence.

These areas remain explicitly pending:

1. Android physical-device validation.
2. Apple device, AWDL, path-rotation, background, and restart validation.
3. Two-machine hostile-network validation.
4. CLI fault injection and headful Desktop observation.
5. Independent secure-v2 interoperability validation.
6. Professional cryptographic audit.

See [validation status](docs/testing/validation-status.md) and the operational
[real-world validation handbook](docs/validation/README.md). Do not treat this
release candidate as fully production validated or independently audited.

## Contributing and support

- [Documentation index](docs/README.md)
- [Contributing](CONTRIBUTING.md)
- [Security reporting](SECURITY.md)
- [Support policy](SUPPORT.md)
- [Changelog](CHANGELOG.md)

P2pKit is licensed under the [Apache License 2.0](LICENSE).
