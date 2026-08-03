# P2pKit

P2pKit is a Kotlin Multiplatform SDK for discovering nearby devices and
exchanging messages or files over a reachable local network. It provides one
transport-independent API for Android, iOS, and JVM desktop while the shipped
LAN module owns mDNS/Bonjour discovery, TCP connections, framing, keepalive,
reconnect, and authenticated encryption.

**Current source version:** `0.7.0-rc1` release candidate. The repository can
produce complete signed Maven Central Portal bundles, but no remote publication
is claimed here. Published `0.6.x` coordinates are immutable; `0.7.0-rc1` is a new
version and wire/security migration.

## Scope and guarantees

P2pKit provides:

- Android API 24+, JVM desktop, and iOS (`iosArm64`, `iosSimulatorArm64`,
  `iosX64`) targets.
- LAN discovery through in-process JmDNS on Android/JVM and Bonjour through
  `Network.framework` on iOS.
- TCP message transport, 4 MiB text/binary message limit, streaming file
  transfer, keepalive, and outgoing-session reconnect.
- Authenticated protocol v2 by default:
  `Noise_XX_25519_ChaChaPoly_SHA256`, persistent X25519 identities, encrypted
  records, and explicit peer authorization.
- Typed failures, coroutine/Flow APIs, explicit lifecycle ownership, and no
  SDK-initiated runtime permission prompts.

P2pKit does **not** provide internet connectivity, NAT traversal, signaling,
relay, user accounts, room membership, application-level authorization,
delivery acknowledgements, host migration, or game-state synchronization.
Both peers must already be able to reach each other over the same LAN (or use a
supported provisioning/manual-IP path). Guest and enterprise Wi-Fi commonly
block multicast discovery or peer-to-peer TCP.

## Modules

| Module | Purpose |
|---|---|
| `dev.p2pkit:p2p-core:0.7.0-rc1` | Public API, protocol, security, sessions, file transfer |
| `dev.p2pkit:p2p-transport-lan:0.7.0-rc1` | Android/JVM JmDNS, iOS Bonjour, TCP transport |
| `dev.p2pkit:p2p-network-provisioning-android:0.7.0-rc1` | Optional Android LocalOnlyHotspot/Wi-Fi join sidecar |
| `dev.p2pkit:p2p-network-provisioning-desktop:0.7.0-rc1` | Optional JVM manual-IP sidecar |

The LAN module exposes core transitively. Use only the modules your app needs.
For local source validation before a remote release, publish to an isolated
repository and point the consumer at that repository explicitly:

```bash
./gradlew publishToMavenLocal \
  -Dmaven.repo.local=/absolute/path/to/isolated-p2pkit-repository
```

Do not make consumer builds silently prefer a developer's global `~/.m2`.

## Secure quick start

Authenticated v2 is the default and fails closed. Its default authorization
policy, `RejectUnknown`, does not trust an mDNS fingerprint claim. Exchange the
full pairing QR or fingerprint through a trusted out-of-band channel, parse it
against the exact `AppId`, then pin it on connect:

```kotlin
import dev.p2pkit.core.AppId
import dev.p2pkit.core.BackgroundPolicy
import dev.p2pkit.core.P2pKit
import dev.p2pkit.core.P2pMessage
import dev.p2pkit.core.ReconnectPolicy
import dev.p2pkit.transport.lan.lan
import kotlinx.coroutines.flow.first

val p2p = P2pKit.create {
    appId = AppId("com.example.transfer")
    deviceName = "My Phone"
    transports { lan() } // JVM/iOS; Android: lan(applicationContext)
    lifecycle {
        reconnectPolicy = ReconnectPolicy.Enabled(
            maxAttempts = 8,
            retryDelayMillis = 500,
        )
        onBackground = BackgroundPolicy.CloseActiveSessions
    }
    // SecurityMode.AuthenticatedV2(RejectUnknown) is already the default.
}

p2p.start()
p2p.startAdvertising()
p2p.startDiscovery()

val expectedFingerprint =
    requireNotNull(p2p.parsePeerPairingQr(qrTextFromTrustedChannel))
val peer = p2p.peers.first { it.isNotEmpty() }.first()
val session = p2p.connect(peer, expectedFingerprint)
session.send(P2pMessage.Text("hello"))
```

`localPairingQr` contains this device's AppId-bound canonical QR text. A
discovered name, peer id, TXT record, room code, or short human-entered value is
not a cryptographic identity pin.

For inbound sessions under `RejectUnknown`, construct the kit with the set of
identities that may connect:

```kotlin
security {
    mode = SecurityMode.AuthenticatedV2(
        PeerAuthorizationPolicy.PinnedOnly(approvedFingerprints),
    )
}
```

Applications that intentionally admit any authenticated key using the same
public `AppId` may opt into
`PeerAuthorizationPolicy.AcceptAnyAuthenticatedSameApp`. That policy still
encrypts traffic and proves key possession, but `AppId` is not a secret and the
policy does not identify or authorize a human/device. It is marked
`@ExplicitSecurityRisk`; pair it with an application-level admission protocol
and document the residual active-MITM/relay and peer-impersonation model.

There is no automatic fallback from authenticated v2 to plaintext.
`SecurityMode.NoneForMvp` remains deprecated only so existing consumers can
perform an explicit migration. See
[`docs/MIGRATING_TO_0.7.md`](docs/MIGRATING_TO_0.7.md).

## Platform setup

### Android

Initialize P2pKit once from `Application.onCreate()` before constructing a
secure kit. Authenticated v2 uses Android Keystore-wrapped, no-backup storage;
missing initialization fails with a typed local-identity configuration error.

```kotlin
class MyApplication : Application() {
    override fun onCreate() {
        super.onCreate()
        P2pKitAndroid.initialize(this)
    }
}
```

Declare the base LAN transport's install-time permissions:

```xml
<uses-permission android:name="android.permission.INTERNET" />
<uses-permission android:name="android.permission.ACCESS_NETWORK_STATE" />
<uses-permission android:name="android.permission.ACCESS_WIFI_STATE" />
<uses-permission android:name="android.permission.CHANGE_WIFI_MULTICAST_STATE" />
```

Base LAN discovery does not require a runtime nearby/location permission on the
supported API range. The optional hotspot/Wi-Fi-join sidecar has separate
permission requirements; query its permission manager immediately before those
provisioning operations instead of gating the base transport.

### iOS

Authenticated v2 uses a device-only Keychain identity. The host app must include
a nonblank local-network usage description and the exact service type selected
by its security mode:

```xml
<key>NSLocalNetworkUsageDescription</key>
<string>Find and connect to nearby devices on your local network.</string>
<key>NSBonjourServices</key>
<array>
    <string>_p2pkit2._tcp</string>
</array>
```

Use `_p2pkit2._tcp` for authenticated v2. Add `_p2pkit._tcp` only if the app
deliberately constructs a deprecated plaintext-v1 kit. The profiles use
separate discovery namespaces and cannot interoperate. Keep these keys in the
source that generates the final Info.plist; the maintained sample stores them
in `iosApp/project.yml`.

### JVM desktop

Core deliberately has no passwordless/plain-file secure identity default.
Provide a durable, confidential, integrity-protected implementation backed by
the operating system's credential/secret store:

```kotlin
val p2p = P2pKit.create {
    appId = AppId("com.example.transfer")
    deviceName = "Desktop"
    jvmSecureIdentityStore(protectedIdentityStore)
    transports { lan() }
}
```

`JvmSecureIdentityStore` must make `putIfAbsent` atomic across processes,
persist before returning, return defensive copies, and protect values at rest.
The samples' in-memory store is development-only and deliberately loses
identity on process exit.

## Session and lifecycle contract

- Subscribe eagerly to `incomingSessions` before advertising and attach each
  `session.incoming` collector immediately. Both are hot streams and
  `session.incoming` has `replay = 0`; an application protocol should exchange
  a ready/admission message before sending real payloads.
- `send()` means the message was written to the local transport. It is not a
  remote application acknowledgement. Add command ids, sequence/revision
  checks, deduplication, acknowledgements, and snapshots in the application
  protocol when the domain requires them.
- Only outgoing sessions auto-reconnect. An incoming session fails and the
  remote outgoing owner redials. A clean close never reconnects.
- Call `notifyAppBackgrounded()` and `notifyAppForegrounded()` from the host
  lifecycle. The default background policy closes sessions and stops
  advertising/discovery.
- `stop()` is terminal and performs bounded cleanup. Cancel and join
  application collectors, close sessions, then call `stop()` exactly once per
  kit ownership lifecycle.
- Payloads and discovered peers are untrusted input even inside encrypted
  transport. Bound and validate the application's serialized envelope before
  decoding game/business state.

## File transfer

Files stream in configurable chunks and are never buffered wholly in memory.
Authenticated v2 completes an outgoing transfer only after the receiver
validates SHA-256 and durably commits the destination. Observe retained
`pendingFileOffers`; the older replay-zero `incomingFiles` stream and raw
flush-only source/sink overloads are deprecated migration APIs.

Text and binary `send()` payloads are capped at 4 MiB. Use file transfer for
larger content and apply a lower application-specific cap whenever possible.

## Architecture

```text
Host application
  ├─ application identity, admission, room/game protocol
  ├─ lifecycle and coroutine ownership
  └─ P2pKit public API
       ├─ PeerRegistry / discovery state
       ├─ SessionManager / reconnect / simultaneous-open arbitration
       ├─ Noise v2 security + frame/message/file protocol
       ├─ LAN transport (JmDNS or Bonjour + TCP)
       └─ optional network-provisioning sidecar
```

The API and wire contract live in [`P2pKit-Spec.md`](P2pKit-Spec.md).

## Verification

Java 17 and macOS are required for the complete local matrix:

```bash
./gradlew check
./gradlew :p2p-core:allTests
./gradlew :p2p-transport-lan:jvmTest
./gradlew :p2p-transport-lan:iosSimulatorArm64Test
scripts/check-sbom.sh
scripts/check-publish-artifacts.sh
scripts/check-published-consumers.sh
./gradlew :p2p-transport-lan:verifyP2pKitSharedReleaseXCFrameworkProvenance
```

Simulator and loopback tests cannot prove physical-radio behavior. Real-device
Bonjour/JmDNS removal, Wi-Fi/cellular path changes, LocalOnlyHotspot, hostile
network departure, and cross-platform interoperability remain explicit manual
release gates in [`docs/STABILIZATION_AND_RELEASE.md`](docs/STABILIZATION_AND_RELEASE.md).

## Publication status

All four library modules produce Central-shaped POMs, sources, strict Dokka
documentation, Gradle module metadata, ABI baselines, dependency locks, and an
SBOM. Signing activates only when an in-memory PGP key is supplied.
`scripts/build-central-portal-bundle.sh` creates a signed, checksummed upload
bundle without uploading it. The protected tag workflow can upload an approved
bundle and then verifies the immutable bytes and isolated consumers from Maven
Central.

Maven Central namespace ownership, release credentials, final Portal
validation, and publication are external maintainer actions. A local build or
successful bundle does not prove that `0.7.0-rc1` is available from Maven Central.

P2pKit is licensed under Apache-2.0. See [`LICENSE`](LICENSE).
