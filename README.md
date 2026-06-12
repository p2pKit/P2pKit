# P2pKit

A Kotlin Multiplatform SDK for discovering nearby devices and exchanging text or binary messages over the local network. The public API exposes peers, sessions, send, and receive — transport selection, mDNS, TCP framing, chunking, keep-alive, and platform differences are hidden behind it.

**Version:** v0.6-dev (LAN/TCP on Android + JVM desktop + iOS).

```kotlin
val p2p = P2pKit.create {
    appId = AppId("com.example.transfer")
    deviceName = "My Phone"
    transports { lan() }      // JVM
    // transports { lan(applicationContext) }   // Android
}

p2p.startAdvertising()
p2p.startDiscovery()

p2p.peers
    .onEach { peers -> println("known peers: $peers") }
    .launchIn(scope)

val peer = p2p.peers.first { it.isNotEmpty() }.first()
val session = p2p.connect(peer)
session.send(P2pMessage.Text("hello"))
```

---

## What P2pKit is

- A **small, transport-agnostic API** for nearby-device communication on Android, JVM desktop, and iOS.
- Built around `Peer`, `P2pSession`, `send(...)`, and a `SharedFlow<P2pMessage>` for receiving.
- Uses Kotlin **coroutines and `Flow` / `StateFlow`** everywhere; no callbacks.
- **Modular**: each transport is a separate Gradle module. Apps depend only on what they use.
- Honest about platform limits — surfaces `Unsupported` / `RequiresUserAction` / typed `P2pError`s rather than swallowing failures.

## What P2pKit is not

- Not Bluetooth, Wi-Fi Direct, Apple Multipeer, or a relay client — those are **future** transports designed to plug in behind the same API.
- Not iOS / native macOS in v0.1.
- Not encrypted in v0.1 (`SecurityMode.NoneForMvp`); the security abstraction exists so encryption can be added without breaking the public API.
- Not a multimedia streaming SDK — file transfer (added in v0.2.2) streams discrete files via `sendFile` / `incomingFiles` with a 2 GiB default cap, but the SDK does not provide a media pipeline. Text and binary messages stay capped at **4 MiB per `send()`** (use `sendFile` for anything larger).
- Does not request runtime permissions on your behalf — that's the app's responsibility.
- Does not promise to put two devices on the same LAN automatically. **Network provisioning** is a planned v0.2 sidecar.

## Platform support

| Platform | Core types compile | Discovery | Data | Provisioning |
|---|---|---|---|---|
| Android (minSdk 24) | yes | JmDNS mDNS (in-process, v0.5+) | TCP via `java.net.Socket` | Android `LocalOnlyHotspot` host + Wi-Fi join (v0.2.1) |
| JVM desktop (Windows / Linux / macOS) | yes | JmDNS | TCP via `java.net.Socket` | manual-IP fallback only (v0.2.1) |
| iOS (iosX64 / iosArm64 / iosSimulatorArm64) | yes | `NWBrowser` (Bonjour) | TCP via `nw_connection_t` | **never supported on iOS** — Apple does not allow apps to create hotspots or silently join Wi-Fi |
| macOS native | not in v0.3 | not in v0.3 | not in v0.3 | not in v0.3 |

**v0.3 iOS scope, explicitly:** `:p2p-core` declares iOS targets and ships `iosMain` actuals for `currentPlatform()`, `systemTimeMillis()`, and `PeerId` persistence (via `NSUserDefaults`); `:p2p-transport-lan` now also declares `iosX64` / `iosArm64` / `iosSimulatorArm64` and ships an `appleMain` source set with `IosLanDataTransport` (`nw_listener_t` + `nw_connection_t`), `IosLanDiscoveryTransport` (`nw_browser_t` + `nw_advertise_descriptor_set_txt_record_object`), and `IosBonjour` TXT-record helpers. Service type is `_p2pkit._tcp` — wire-identical to the JmDNS-based JVM and Android transports. Verified by the `iosSimulatorArm64Test` loopback suite mirroring the JVM one (text round-trip, 200 KB binary, 5 MiB streamed file). The iOS sample app shipped in **v0.4**: the `iosApp/` Xcode project embeds the `P2pKitShared` XCFramework and provides the required `Info.plist` entries (`NSLocalNetworkUsageDescription`, `NSBonjourServices`) and Network entitlement.

Cross-platform LAN today:
- **Android ↔ JVM**: works (verified by `INTERNAL_TESTING.md` §A).
- **iOS ↔ Android**: works — same Bonjour service type, same TXT record keys; real-device validated during the v0.5 reconnect work (Huawei Android ↔ iPhone).
- **iOS ↔ JVM**: works in principle — same wire format; the `INTERNAL_TESTING.md` §K simulator recipe covers the JVM CLI ↔ iOS Simulator pair.
- **iOS ↔ iOS in one process**: verified by `:p2p-transport-lan:iosSimulatorArm64Test`.

iOS Network Provisioning is **not** planned and will remain `Unsupported` indefinitely. App Store rules forbid third-party apps from creating Wi-Fi hotspots, and silent Wi-Fi join is not exposed to third-party apps. The `networkProvisioning` accessor on `P2pKit` will continue to throw `Unsupported` on iOS.

## Quick start

```kotlin
import dev.p2pkit.core.*
import dev.p2pkit.transport.lan.lan
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.*

val p2p = P2pKit.create {
    appId = AppId("com.example.transfer")
    deviceName = "Abdo's Phone"

    transports { lan() }            // JVM
    // transports { lan(applicationContext) }   // Android — pass any Context

    keepAlive {
        pingIntervalMillis = 10_000
        timeoutMillis = 30_000
    }

    lifecycle {
        reconnectPolicy = ReconnectPolicy.Disabled
        onBackground = BackgroundPolicy.CloseActiveSessions
        onAppKilled = AppKilledPolicy.NoPersistenceForMvp
    }

    security {
        mode = SecurityMode.NoneForMvp
    }
}

val scope = CoroutineScope(Dispatchers.Default + SupervisorJob())

scope.launch {
    p2p.startAdvertising()
    p2p.startDiscovery()
}

// Observe peers (StateFlow — always-current snapshot)
p2p.peers
    .onEach { peers -> println("known peers: ${peers.map { it.name }}") }
    .launchIn(scope)

// Accept incoming sessions
p2p.incomingSessions
    .onEach { session ->
        session.incoming
            .onEach { msg -> println("[${session.peer.name}] $msg") }
            .launchIn(scope)
    }
    .launchIn(scope)

// Connect outgoing
scope.launch {
    val peer = p2p.peers.first { it.isNotEmpty() }.first()
    val session = p2p.connect(peer)
    session.send(P2pMessage.Text("hello"))
}
```

**Never use nested `collect { collect { … } }`** — always use `launchIn(scope)` on inner flows.

### File transfer (v0.2.2)

```kotlin
// Outgoing (JVM): the convenience extension reads file.name / file.length() for you.
import dev.p2pkit.core.transfer.sendFile

val transfer = session.sendFile(java.io.File("/path/to/report.pdf"))
transfer.state
    .onEach { state -> println("$state ${transfer.bytesTransferred.value}/${transfer.sizeBytes}") }
    .launchIn(scope)
// transfer.cancel("user aborted") at any time

// Outgoing (Android): pass an Activity Result Uri from the system picker; the
// extension resolves name/size/mime via ContentResolver.
import dev.p2pkit.core.transfer.sendFile

session.sendFile(context, pickedUri)

// Incoming: the peer's send arrives as a P2pFileOffer.
session.incomingFiles
    .onEach { offer ->
        // sink can be Buffer(), File.outputStream().asSink(), getExternalFilesDir(...)... etc.
        offer.accept(saveFile.outputStream().asSink())
        // or: offer.reject("not now")
    }
    .launchIn(scope)
```

Files stream in 64 KiB chunks (configurable via `fileTransfer { chunkSizeBytes = … }`); the SDK never buffers the whole file in memory. The default 2 GiB cap and 30 s offer-timeout are also configurable.

## Required permissions

### Android (manifest, install-time)

```xml
<uses-permission android:name="android.permission.INTERNET" />
<uses-permission android:name="android.permission.ACCESS_NETWORK_STATE" />
<uses-permission android:name="android.permission.ACCESS_WIFI_STATE" />
<uses-permission android:name="android.permission.CHANGE_WIFI_MULTICAST_STATE" />
```

The in-process JmDNS-based mDNS (v0.5+) does **not** require runtime permissions on any supported API level (24-36). v0.2's Wi-Fi-Direct / hotspot work will need `NEARBY_WIFI_DEVICES` (API 33+) and possibly `ACCESS_FINE_LOCATION` for older devices; the library will not request them on your behalf, but `P2pKit.permissions.missingPermissions()` will list them.

### JVM desktop

No runtime permissions required. On first run, Windows Defender Firewall may prompt to allow inbound TCP on the chosen ephemeral port — **allow it**.

### Android `Application.onCreate` (recommended)

To enable persistent `PeerId` on Android, register an `Application` subclass and call `P2pKitAndroid.initialize(this)` once:

```kotlin
class MyApp : Application() {
    override fun onCreate() {
        super.onCreate()
        P2pKitAndroid.initialize(this)
    }
}
```

```xml
<application android:name=".MyApp" …>
```

If you skip this on Android, P2pKit still works — it falls back to in-memory `PeerId` storage and logs a warning. The device will appear to other peers with a new id after every process restart.

## Why LAN/TCP first

LAN + TCP is the **only transport that works the same way on every desktop and mobile platform** without proprietary stacks. Bluetooth, Wi-Fi Direct, and Multipeer each work great on one side but not the others. Starting with LAN keeps the public API honest about portability; pluggable transports are added behind it as separate Gradle modules.

## Future transport roadmap

| Transport / capability | Status | Notes |
|---|---|---|
| LAN (mDNS + TCP) | **v0.1** | Shipped. |
| Network provisioning sidecar | **v0.2.1** | Android `LocalOnlyHotspot` host + Wi-Fi join via `WifiNetworkSpecifier`; JVM manual-IP fallback. Code complete, real-device verification pending (see backlog). |
| File transfer (`sendFile` / `incomingFiles`) | **v0.2.2** | Streaming via `kotlinx.io.RawSource` / `RawSink`; default 2 GiB cap, 64 KiB chunks, 30 s offer timeout; JVM `sendFile(File)` and Android `sendFile(Context, Uri)` convenience extensions; integration-tested via 5 MiB SHA-256 LAN loopback. |
| iOS LAN (Bonjour + `Network.framework`) | **v0.3** | Same public API as JVM/Android. `NWBrowser` + `NWListener` + `NWConnection` via the auto-generated `platform.Network` bindings, with a small cinterop helper (`p2pkit_nw.h`) that wraps the void-returning block macros (`NW_PARAMETERS_DISABLE_PROTOCOL` etc.) which Kotlin/Native cannot box. Wire-compatible with JmDNS peers (JVM and Android). iOS sample app followed in v0.4 (`iosApp/`). |
| macOS native LAN | v0.3.x candidate | Not declared on any module yet; same `Network.framework` story would apply, but needs Bonjour testing on Wi-Fi vs the simulator's network stack to be sure. |
| BLE | v0.4+ | Discovery + small messages. **Not** for large file transfer. |
| Android Wi-Fi Direct | v0.4+ | Android-to-Android offline. |
| Apple Multipeer | v0.4+ | Apple-to-Apple offline. |
| Relay (internet fallback) | v0.4+ | Server-mediated when both peers have only internet. |
| Encryption (`SecurityMode.PairingCode` / `QrCode`) | v0.4+ | X25519 + HKDF + AES-GCM / ChaCha20-Poly1305. Wires into the existing `SecurityManager` extension point. |

## Network provisioning vs transport

Two distinct concerns:

- **Transport** moves bytes once two devices can reach each other. LAN/TCP in v0.1.
- **Network provisioning** helps two devices *get* on the same LAN in the first place — e.g., one device starts an Android `LocalOnlyHotspot`, the other joins it.

In v0.1, `P2pKit.networkProvisioning` is implemented by an `UnsupportedNetworkProvisioningManager` stub: every method returns `Unsupported(…)` or throws. The API shape is locked (see `P2pKit-Spec.md` §20), so app code written against it today compiles unchanged when v0.2 replaces the stub with real `LocalOnlyHotspot` + Wi-Fi join helpers.

## Recommended connection flow (v0.1)

1. Both devices call `startAdvertising()` and `startDiscovery()`.
2. App observes `p2p.peers` and shows the user the discovered devices.
3. User picks one → `p2p.connect(peer)` returns a `P2pSession`.
4. Send and receive on the session.
5. On the other side, the session arrives on `p2p.incomingSessions`.

If step 2 produces no peers within a reasonable time:

- Check that both devices are on the same Wi-Fi (LAN).
- Check that the firewall isn't blocking mDNS (UDP 5353) or peer-to-peer TCP.
- v0.2 will add a manual-IP fallback through `networkProvisioning.createManualPeer(host, port)`.

## Firewall and network notes

- **Windows**: Defender Firewall prompts on first run. Allow inbound TCP on the chosen ephemeral port. mDNS (UDP 5353) is normally allowed on private networks.
- **Linux**: `ufw allow 5353/udp` for mDNS reception; the TCP port is ephemeral so blanket "allow from LAN" rules are easier than per-port. Distro-specific.
- **macOS**: System Settings → Network → Firewall → Options → Allow incoming connections for the JVM binary the sample runs under.
- **Corporate / guest / hotel Wi-Fi** frequently blocks mDNS multicast and peer-to-peer TCP. This is the most common cause of "no peers found"; try a home network or hotspot.
- **Android on mobile data only** cannot use LAN discovery — both devices must be on Wi-Fi (or sharing a hotspot).

## Architecture

```
App
 ↓
P2pKit public API
 ├── NetworkProvisioningManager   (v0.2 sidecar — Unsupported stub in v0.1)
 ├── P2pPermissionManager         (sidecar)
 └── core pipeline:
     PeerRegistry / Discovery     ← aggregates DiscoveryTransport events
       ↓
     SessionManager               ← creates outgoing, accepts incoming
       ↓
     Protocol Layer               ← framing, chunking, ACK, keepalive
       ↓
     SecurityManager              ← NoOp in v0.1; encrypted in future
       ↓
     TransportManager             ← picks best DataTransport per peer
       ↓
     LAN Transport                ← mDNS + TCP (only transport in v0.1)
```

Detailed design lives in [`P2pKit-Spec.md`](./P2pKit-Spec.md).

## Modules

- **`:p2p-core`** — public API, models, errors, protocol framing, session manager, peer registry, **file transfer** (`P2pSession.sendFile` / `incomingFiles`, JVM `sendFile(File)` and Android `sendFile(Context, Uri)` convenience extensions, configurable cap + chunk size + offer timeout via `fileTransfer { … }`). KMP module with `commonMain` / `jvmMain` / `androidMain` / `iosMain` (core scaffolding only — no LAN).
- **`:p2p-transport-lan`** — mDNS discovery + TCP data. JmDNS on JVM **and Android** (Android migrated from `NsdManager` to in-process JmDNS in v0.5 so the SDK owns the mDNS cache), `NWBrowser` + `NWListener` + `NWConnection` on iOS (v0.3). Apple targets share an `appleMain` source set plus a small static-inline-only cinterop wrapper at `src/nativeInterop/cinterop/p2pkit_nw.h` so void-returning block sentinels (`NW_PARAMETERS_DISABLE_PROTOCOL`, `NW_CONNECTION_DEFAULT_MESSAGE_CONTEXT`) never round-trip through `Kotlin_Interop_refFromObjC`.
- **`:p2p-sample-android`** — Compose UI room/broadcast test harness. **Primary visual harness** for v0.2. `./gradlew :p2p-sample-android:assembleDebug`.
- **`:p2p-sample-desktop`** — JVM CLI test harness. **Canonical desktop harness** for v0.2. `./gradlew :p2p-sample-desktop:installDist` then run the launcher. Type `help` for commands.
- **`:p2p-sample-desktop-ui`** — Compose Desktop room/broadcast test harness. Same v0.2 feature parity as the Android sample (status header, peer chips with state + close, broadcast/targeted send, room timeline, log strip, reconnect picker, manual-IP fallback). Run with `./gradlew :p2p-sample-desktop-ui:run`.
- **`:p2p-network-provisioning-desktop`** *(v0.2.1)* — JVM Network Provisioning sidecar. Implements `getManualConnectionInfo()` + `createManualPeer(host, port)` for the manual-IP fallback when mDNS is blocked. Hotspot hosting and Wi-Fi join return `Unsupported` (Android-only capabilities). Wire into a JVM kit via `networkProvisioning { jvm() }`.
- **`:p2p-network-provisioning-android`** *(v0.2.1)* — Android Network Provisioning sidecar. Implements `startLocalNetwork()` via `WifiManager.startLocalOnlyHotspot()` (OS-chosen random SSID + passphrase), `joinLocalNetwork(credentials)` via `WifiNetworkSpecifier` + `ConnectivityManager.requestNetwork` with process-wide network binding so the LAN transport's outgoing sockets route through the joined AP, `getManualConnectionInfo()`, `createManualPeer()`, plus the matching `AndroidP2pPermissionManager`. Wire into an Android kit via `networkProvisioning { android(applicationContext) }`. App must declare `NEARBY_WIFI_DEVICES` (API 33+) / `ACCESS_FINE_LOCATION` (API ≤ 32) in its manifest; library reports missing runtime perms via `P2pKit.permissions`.

Planned modules (not yet implemented): `:p2p-transport-ble`, `:p2p-transport-android-wifidirect`, `:p2p-transport-apple-multipeer`, `:p2p-transport-relay`. (The iOS sample ships as the `iosApp/` Xcode project rather than a Gradle sample module.)

## Sample feature coverage (v0.2.2-dev)

| Feature | Android sample | JVM CLI | Compose Desktop UI |
|---|---|---|---|
| `appId` shown | ✅ status header | ✅ banner + `info` | ✅ status header + setup |
| `localPeerId` shown | ✅ status header | ✅ `info` | ✅ status header |
| `localDeviceName` shown | ✅ header / setup | ✅ banner + `info` | ✅ status header + setup |
| `state` (kit) | ✅ status header | ✅ `info` | ✅ status header |
| `startAdvertising` / `stopAdvertising` | ✅ Advertise switch | ✅ `adv on / off` | ✅ Advertise switch |
| `startDiscovery` / `stopDiscovery` | ✅ Discover switch | ✅ `disc on / off` | ✅ Discover switch |
| Peer discovery / lost | ✅ list | ✅ `peers` cmd | ✅ list |
| `connect(peer)` | ✅ Connect button | ✅ `connect <id>` | ✅ Connect button |
| Multiple active sessions | ✅ chip row | ✅ `sessions` | ✅ chip row |
| Broadcast send | ✅ default (no chip selected) | ✅ `send <text>` | ✅ default (no chip selected) |
| Targeted send | ✅ chip multi-select | ✅ `to <id> <text>` | ✅ chip multi-select |
| Incoming from every session | ✅ unified timeline | ✅ per-session print | ✅ unified timeline |
| Per-session `ConnectionState` | ✅ chip label | ✅ `[state] N → S` | ✅ chip label |
| `session.close()` | ✅ chip overflow menu | ✅ `close <id>` | ✅ chip overflow menu |
| `kit.stop()` | ✅ overflow menu | ✅ `quit` / `exit` | ✅ overflow menu |
| `ReconnectPolicy.Enabled` configurable | ✅ setup picker | ✅ `reconnect=N,delayMs` arg | ✅ setup picker |
| PeerId persistence verifiable | ✅ visible in header | ✅ via `info` | ✅ visible in header |
| Auto-mesh (lexicographic tie-break) | ✅ Auto-mesh switch (default on) | ✅ `mesh on/off` (default on) | ✅ Auto-mesh switch (default on) |
| MulticastLock | ✅ implicit (active while running) | N/A | N/A |
| In-app log strip | ✅ tail of TailLogger | ✅ stderr | ✅ tail of TailLogger |
| File transfer — pick & send (v0.2.2) | ✅ chip overflow → SAF picker | ✅ `sendfile <id> <path>` | ✅ chip overflow → AWT FileDialog |
| File transfer — auto-accept inbound | ✅ `getExternalFilesDir/p2pkit-incoming/<sender>/` | ✅ `~/.p2pkit/incoming/<sender>/` | ✅ `~/.p2pkit/incoming/<sender>/` |
| File transfer — live progress & cancel | ✅ transfer rows with % + Cancel | ✅ `[file …] state` lines | ✅ transfer rows with % + Cancel |

## Platform testing matrix (v0.2-dev)

| Combination | Supported now | Notes |
|---|---|---|
| Android ↔ JVM Desktop | ✅ | mDNS + TCP across same Wi-Fi; verified by §A in `INTERNAL_TESTING.md`. |
| JVM ↔ JVM | ✅ | Same machine or two machines on the same LAN. |
| Android ↔ Android | ✅ | In-process JmDNS ↔ JmDNS (v0.5+) on the same Wi-Fi. |
| Multi-peer room (3+ peers, mixed platforms) | ✅ | No SDK peer cap; verified by §B. |
| Android ↔ iOS | ✅ | Same Bonjour service type + TXT keys; wire format verified in-process by `INTERNAL_TESTING.md` §K.1; real-device validated during the v0.5 reconnect work (Huawei Android ↔ iPhone Wi-Fi-flap cycles). |
| JVM ↔ iOS | ✅ (v0.3) | Same wire format; verified in-process by the iOS loopback suite (§K.1). The cross-process JVM CLI ↔ iOS Simulator recipe is outlined in `INTERNAL_TESTING.md` §K.2 but has not been executed yet. |
| iOS ↔ iOS | ✅ (v0.3) | Verified in-process by `:p2p-transport-lan:iosSimulatorArm64Test` (text + 200 KB binary + 5 MiB file). Two simulators would also work. |
| Three-way involving iOS | ✅ (v0.3) | Same wire protocol — no additional handling needed when an iOS peer joins an existing JVM/Android room. |

## OS / device testing matrix

| Endpoint | Supported now | What can be tested | What cannot | Limitations |
|---|---|---|---|---|
| Android real device (API 24+) | yes | discovery, connect, send, broadcast, targeted, reconnect, MulticastLock | iOS interop | sample doesn't auto-call `notifyAppBackgrounded` |
| Android emulator | yes-ish | same as real device | host-firewall scenarios | NAT-through-host can break cross-machine mDNS |
| Windows JVM desktop | yes | full LAN feature set via CLI | iOS interop | Defender Firewall prompt on first run |
| macOS JVM desktop | yes | full LAN feature set | iOS interop | macOS Firewall must allow incoming |
| Linux JVM desktop | yes | full LAN feature set | iOS interop | `ufw allow 5353/udp` may be needed |
| iPhone real device | yes (`iosApp/` sample, shipped v0.4) | discovery, connect, send via the `iosApp/` sample or the SDK linked into any Xcode project providing `Info.plist` entries `NSLocalNetworkUsageDescription` + `NSBonjourServices = ["_p2pkit._tcp"]` | network provisioning (never supported on iOS) | requires macOS + Xcode + an Apple Developer account for device deploys; SDK is wire-compatible with JmDNS peers (JVM and Android) |
| iOS simulator | yes | full LAN feature set via `:p2p-transport-lan:iosSimulatorArm64Test` or the `iosApp/` sample; cross-process recipe in `INTERNAL_TESTING.md` §K | network provisioning (never supported on iOS) | builds only on macOS host; requires Xcode + the iOS simulator runtime |
| macOS native target | not declared | nothing | everything | target not in any module; v0.3.x candidate |

## Running the samples

### Desktop CLI

```
./gradlew :p2p-sample-desktop:installDist
./p2p-sample-desktop/build/install/p2p-sample-desktop/bin/p2p-sample-desktop Alice
```

On Windows:

```
.\p2p-sample-desktop\build\install\p2p-sample-desktop\bin\p2p-sample-desktop.bat Alice
```

In a second terminal, start a second instance with a different device name (e.g. `Bob`). After a few seconds each should print `[peers] 1: …` for the other. Then:

```
> peers
> connect <id-prefix-of-other>
> send hello
```

Optional third arg configures reconnect:
```
.\p2p-sample-desktop.bat Alice p2pkit-desktop-sample reconnect=5,1000
```

Type `help` for the full command list (`peers`, `sessions`, `info`, `adv on|off`, `disc on|off`, `mesh on|off`, `connect`, `send`, `to`, `manual`, `sendfile`, `close`, `quit`).

### Android

```
./gradlew :p2p-sample-android:assembleDebug
adb -s <device-A> install -r p2p-sample-android/build/outputs/apk/debug/p2p-sample-android-debug.apk
adb -s <device-B> install -r p2p-sample-android/build/outputs/apk/debug/p2p-sample-android-debug.apk
```

Launch on both devices (same Wi-Fi), enter different names, tap **Start**, then tap **Connect** on the discovered peer.

## Testing

```
./gradlew :p2p-core:allTests
./gradlew :p2p-transport-lan:jvmTest
./gradlew :p2p-core:assemble :p2p-transport-lan:assemble :p2p-sample-desktop:installDist :p2p-sample-android:assembleDebug
```

The tree currently ships **134 unit + integration tests** in `:p2p-core` (122 common + 12 JVM-only), 17 in `:p2p-transport-lan:jvmTest`, 20 in `:p2p-transport-lan:iosSimulatorArm64Test`, and the host-side tests under `:p2p-network-provisioning-android` and `:p2p-network-provisioning-desktop`. The JVM LAN loopback suite runs two `P2pKit` instances inside one JVM over real TCP + mDNS — `largeBinaryPayloadRoundTripsOverTcp` exchanges a 200 KB binary, `fileTransferRoundTripsOverTcpWithMatchingHash` streams a deterministic 5 MiB temp file and SHA-256-verifies it on the receiver. The iOS loopback suite (`./gradlew :p2p-transport-lan:iosSimulatorArm64Test`) does the same on the simulator over real Bonjour + `nw_connection_t`.

## Known limitations (v0.1-internal, partial v0.2)

- **`PeerId` persistence (v0.2 task 1 — implemented).** JVM persists automatically under `<user.home>/.p2pkit/<appId>/peer-id`. Android persists under `<filesDir>/p2pkit/<appId>/peer-id` **after** the host app calls `P2pKitAndroid.initialize(applicationContext)` (typically from `Application.onCreate`). Without the init call, Android falls back to in-memory storage and the kit logs a `P2pLogger.warn` at construction. Apps wanting persistent identity must add the init.
- **`ReconnectPolicy.Enabled` applies to outgoing sessions only (v0.2 task 3 — implemented).** When an outgoing session loses its connection, the kit transitions it to `Reconnecting` and retries the dial up to `maxAttempts` times with `retryDelayMillis` between attempts. On success the session returns to `Connected` with its public identity preserved (same `P2pSession` instance, same `incoming` flow). On exhaustion it transitions to `Failed`. **Incoming sessions do not auto-reconnect** — they still transition directly to `Failed` on connection loss; the remote peer is expected to redial. Retries reuse the originally-discovered peer transport info; if the peer's address has rotated since (e.g., Wi-Fi reconnect changed its IP), attempts may exhaust until the app re-discovers the peer and calls `connect(...)` again. Clean closes — both `session.close()` and a peer-sent `CLOSE` frame — never trigger retry.
- **Sample `appId`** is now `p2pkit-desktop-sample` on **both** the JVM desktop and Android samples — they discover each other out of the box. The desktop sample also accepts a second positional arg (`gradlew :p2p-sample-desktop:run --args="Alice some-other-app-id"`) if you want to align with a different consumer.
- **No instrumented Android tests.** Android LAN paths (the JmDNS-backed `AndroidLanDiscoveryTransport`, `AndroidLanDataTransport`, `AndroidRawConnection`) are validated by code review + manual two-device testing only. The protocol layer that flows over them is JVM-tested.
- **Android sample survives rotation but not process death.** The kit and its session/peer/chat state live in a `P2pKitViewModel` that survives configuration changes (rotation, dark mode, locale, multi-window). If Android kills the app process while it's backgrounded, the kit is lost and the next launch starts at the setup screen. `SavedStateHandle`-based recovery is a planned v0.3 task.
- **Sample app doesn't track background/foreground.** v0.2 dropped the `LifecycleEventObserver` from the Android sample — it was firing `notifyAppBackgrounded()` on rotation start, which the kit interpreted via `BackgroundPolicy.CloseActiveSessions`. The sample now keeps the kit running until the user taps **Stop** or the `Activity` is destroyed for real. Apps that want proper background detection should wire `ProcessLifecycleOwner` (from `androidx.lifecycle:lifecycle-process`) themselves.
- **iOS LAN ships in v0.3 (tasks 18–22).** `:p2p-transport-lan` now declares `iosX64()`, `iosArm64()`, and `iosSimulatorArm64()` with an `appleMain` source set that wires `nw_listener_t` + `nw_connection_t` + `nw_browser_t` behind the same `transports { lan() }` API as JVM and Android. Service type is `_p2pkit._tcp`, TXT keys are identical to the JmDNS transports, so an iOS peer is indistinguishable on the wire. **iOS Network Provisioning remains unsupported** — Apple does not allow third-party apps to create hotspots or join Wi-Fi silently. No iOS sample app shipped in v0.3 — embedding the SDK in an Xcode project (Info.plist `NSLocalNetworkUsageDescription` + `NSBonjourServices` entries, Network entitlement, framework export, provisioning profile) followed in v0.4 as `iosApp/`. Build / test verification requires a macOS host with Xcode; the iosSimulatorArm64 test target needs an installed iOS simulator runtime to run end-to-end.
- **Room/broadcast is sample-only; auto-mesh is sample-only.** The SDK exposes one `P2pSession` per peer — there is no `P2pRoom` type, no relay, no central node. Each sample iterates `kit.sessions` and fans out sends. To make 3+ device rooms form a full mesh automatically, each sample has an **auto-mesh** switch (default ON) that calls `kit.connect()` on every newly-discovered peer when the local `localPeerId` is lexicographically less than the discovered peer's id — exactly one side per pair initiates, the other accepts the incoming. **Simultaneous-open arbitration is in the SDK itself** (v0.2 task — `SessionManager.registerSession`): even when both sides race a `connect()` call to each other at the same instant, the kit deterministically picks one physical TCP connection to keep (smaller-id peer's outgoing wins) and closes the other on both sides. `P2pKit.sessions` therefore never contains more than one entry per peer, including under user-mashes-Connect-on-both-sides scenarios.
- **Resolved in v0.5 — iPhone-side Wi-Fi flap / Airplane Mode on Android no longer requires manual recovery.** Up through v0.4 the Android peer's `NsdManager` cache served pre-flap SRV records when the iPhone toggled Wi-Fi (off → on) or Airplane Mode (on/off); the daemon could not be flushed via any public API (`stopServiceDiscovery + discoverServices` left the cache intact, mDNS TTL opaque), and Android typically exhausted its reconnect budget dialling the stale port. v0.4 shipped two defensive nudges (`V0.4-D-IOS-NUDGE` in `IosLanDiscoveryTransport`, `V0.4-D-ANDROID-NUDGE` in `AndroidLanDiscoveryTransport`) that fired correctly but could not move the system daemon's cache. The same-direction (Android-side Wi-Fi flap) was already unaffected because Android's own `NetworkCallback` fires → `rebindNow` runs a full NSD subsystem cycle on the new interface. **v0.5 closes the asymmetry** by replacing `NsdManager` on Android with in-process JmDNS so the SDK owns the cache (`34134a5`), force-re-querying every known peer via `requestServiceInfo(..., persistent=true)` on each `DiscoveryTransport.refresh()` (`d40cb1d`), and refiring that primitive every ~3 s (with ±400 ms jitter) on a bounded coroutine in `SessionManager` for the entire `Reconnecting` window so a remote re-announce that lands mid-budget is caught regardless of when it arrives (`1f7c2db`). The v0.4 nudges are kept as defensive code because they are harmless and may still help on device combinations not yet covered. **Real-device validation** (Huawei Android + iPhone, iPhone Cellular Data OFF, iPhone Wi-Fi OFF→ON): two consecutive flap cycles auto-recover without manual `kit.connect(peer)` and without iPhone-app foreground/background workarounds.
- **Resolved in v0.6 — iPhone Wi-Fi flap with cellular enabled (the v0.5 residual edge case).** Through v0.5, when iPhone cellular data was enabled and Wi-Fi was toggled, iOS's `Network.framework` could briefly select the cellular interface during the Wi-Fi gap and rotate the listener through an intermediate cellular-only port that Android cannot reach over LAN; the eventual post-Wi-Fi-back announce could arrive after Android's reconnect budget had exhausted. **v0.6 closes it**: `IosLanDataTransport` prohibits the cellular interface on its shared TCP `nw_parameters_t` (`nw_parameters_prohibit_interface_type`), so the LAN listener never binds or advertises a cellular-only port and outbound dials never route over cellular. Wired Ethernet remains permitted. The previous workarounds (disable iPhone cellular data, or redial from the iPhone side) are no longer needed.

## Status

- **v0.1**: shipped as `v0.1-internal` tag.
- **v0.2-dev** → tagged **`v0.2-internal`** at `a9d683d`. v0.2 contents: Tasks 1–8 (`PeerId` persistence, rotation survival, `ReconnectPolicy.Enabled` retry, iOS scaffolding, Android `MulticastLock`, room/broadcast samples, local identity accessors, simultaneous-open arbitration).
- **v0.2.1-dev** (branch `v0.2.1-dev`, `1465a7a`): Task 10 — JVM Network Provisioning sidecar with manual-IP fallback (`:p2p-network-provisioning-desktop`) — **done**. Task 11 — Android `LocalOnlyHotspot` host — **done (code+tests; pending real-device verification — see backlog)**. Task 12 — Android Wi-Fi join via `WifiNetworkSpecifier` (process-wide socket binding so the LAN transport routes through the joined AP) — **done (code+tests; pending real-device verification — see backlog)**. Plus the small SDK addition `ProvisioningContext.parentJob` so manager scopes are tied to `kit.stop()` cleanly. **Tagging `v0.2.1-internal` is blocked** on the real-device verification milestone below.
- **v0.2.2-dev**: file transfer track. Task 13 — `kotlinx-io` dep + protocol additions (FILE_OFFER / ACCEPT / REJECT / DATA / DONE / CANCEL) + commonMain `P2pFileTransfer` / `P2pFileOffer` / `FileTransferState` / `FileTransferConfig` + internal streaming sender / receiver — **done**. Task 14 — `FileTransferDispatcher` wired into `P2pSessionImpl`, `fileTransfer { … }` DSL block, offer-timeout + cancel propagation, `closeAll` on session close, 5 MiB SHA-256 LAN loopback test — **done**. Task 15 — JVM `sendFile(File)` and Android `sendFile(Context, Uri)` convenience extensions, source-close-on-terminal in dispatcher so the extensions never leak file handles — **done**. Task 16 — all three sample apps gain a "Send file…" menu, live progress rows, auto-accept of inbound offers to platform-appropriate folders — **done**. Code complete and tagged `v0.2.2-internal` blocked **only** on the same Task 11/12 real-device verification (file transfer itself is verified by the 5 MiB loopback test; pending verification covers the provisioning underlying it on Android-only scenarios).
- **v0.3.0-dev**: iOS LAN/TCP via Bonjour + `Network.framework`. Task 18 — build setup + `appleMain` source set + empty `IosLan*.kt` stubs + `lan()` extension on `TransportsBuilder` for iOS that registers an as-yet-unimplemented factory — **done**. Task 19 — `IosRawConnection` (NWConnection wrapper with `state` StateFlow, `write(bytes)`, `read(): Flow<ByteArray>`, `close()`) + `IosLanDataTransport` (`nw_listener_t` for inbound, `nw_connection_create` from endpoint registry for outbound) — **done**. Task 20 — `IosLanDiscoveryTransport` (`nw_browser_t` for browse, `nw_listener_set_advertise_descriptor` for advertise) + `IosBonjour.kt` TXT helpers (`mapToTxtRecord` / `txtRecordToMap` against `LanConstants.TXT_*` keys) — **done**. Task 21 — three `iosSimulatorArm64Test` cases mirror `JvmLanLoopbackTest` (text round-trip, 200 KB binary, 5 MiB streamed file); cinterop helper `src/nativeInterop/cinterop/p2pkit_nw.h` works around three Kotlin/Native ObjC-block bridging hazards (the void-returning block macros in `nw_parameters_create_secure_tcp` and `NW_CONNECTION_DEFAULT_MESSAGE_CONTEXT`, plus `dispatch_data_t` / `nw_content_context_t` on the send/receive hot path) — **done**. Task 22 — README platform tables flip iOS rows to ✅, `INTERNAL_TESTING.md` §K adds CLI ↔ iOS Simulator recipe — **done**. Tagging `v0.3-internal` still blocks on the same Task 11/12 real-device verification (v0.3 transitively includes v0.2.1's provisioning work).
- **v0.4.0-dev** → tagged **`v0.4-internal`** at `21216e4`. SDK stabilization + real-device LAN hardening: `SessionStore` extracted as single source of truth, symmetric Failed-path cleanup, single `transitionToTerminal` codepath, per-attempt endpoint re-resolution on every reconnect retry (`V0.4-RECONNECT`), stuck-Reconnecting watchdog, `NetworkPathObserver` plumbing. iOS LAN: `V0.4-IOS-FOREGROUND-REBIND`, `V0.4-IOS-PATH-INTERFACE-CHANGE`, `V0.4-IOS-LISTENER-REBIND`, `V0.4-D-IOS-NUDGE`. Android LAN: `NetworkCallback`-driven rebind, `V0.4-D-ANDROID-NUDGE`, `V0.4-DISCOVERY-REFRESH`. Samples: keepAlive tuned to 2s / 6s, reconnect preset 10 / 1500, iOS sample app shipped (Xcode project, `NSLocalNetworkUsageDescription`, `NSBonjourServices`, Network entitlement). Build-time identity stamping (commit + branch surfaced in logs).
- **v0.5.0-dev**: closes the v0.4 known limitation around Android `NsdManager` stale-cache. Phase 1 — `:p2p-transport-lan` androidMain discovery side rewritten to use in-process JmDNS (`org.jmdns:jmdns:3.6.3`) so the SDK owns the mDNS cache (`34134a5`). Phase 2 — `DiscoveryTransport.refresh()` on Android rotates the JmDNS service listener and force-re-queries every known peer via `requestServiceInfo(..., persistent=true)` (`d40cb1d`). Phase 2.5 — `SessionManager.SessionReconnectHandler` repeats that refresh every ~3 s (with ±400 ms jitter) on a bounded coroutine for the entire `Reconnecting` window, cancelled deterministically on every exit path — rearm success, attempt exhaustion, state change, scope cancellation (`1f7c2db`). Plus an iOS Xcode pre-build script fix to invoke gradle via `sh ./gradlew` because `gradlew` is checked in 0644 (`fd91c81`). Real-device validated on Huawei Android + iPhone with iPhone Cellular Data OFF: two consecutive Wi-Fi OFF→ON flap cycles auto-recover without manual `kit.connect(peer)`. Tagged **`v0.5-internal`** (follow-up fixes tagged `v0.5.1-internal`).
- **v0.6-dev** (current, `VERSION_NAME=0.6.0`): iOS LAN hardening — `IosLanDataTransport` prohibits the cellular interface on its TCP parameters (listener + outbound dials), closing the v0.5 residual edge case around iPhone Wi-Fi flaps with cellular enabled (issue #11, `d6bf1e4`). JVM LAN loopback tests stabilized on macOS by binding JmDNS to a routable test IPv4 (issue #12).
- **v0.7+**: macOS native LAN target. BLE. Wi-Fi Direct. Multipeer. Relay. Encryption.

### Pending verification backlog

| Milestone | What | Blocks |
|---|---|---|
| **Task 11 & 12 real-device manual verification** | Two real Android phones: host runs `LocalOnlyHotspot` via `HotspotCard`, guest joins via `JoinHotspotCard`, verify OS join prompt, `Joined` state, AP-subnet socket routing via `bindProcessToNetwork`, auto-mesh session formation across the AP, and clean teardown on `kit.stop()`. Full recipe in `INTERNAL_TESTING.md` §H + §I. | Tagging `v0.2.1-internal` from `v0.2.1-dev@1465a7a`, and `v0.2.2-internal` from `v0.2.2-dev` (the v0.2.2 file-transfer pipeline is automated-test-verified — 5 MiB SHA-256 LAN loopback — but the v0.2.2 branch transitively includes v0.2.1's provisioning work, so the same device verification gates both tags). |
| **Cross-device file-transfer device verification** (optional) | Two real Android phones or one Android + one JVM desktop on the same Wi-Fi: send a file ≥ 10 MiB end-to-end via the sample UIs, verify the saved file is byte-identical, exercise the Cancel button mid-transfer. Full recipe in `INTERNAL_TESTING.md` §J. | Not blocking — the automated 5 MiB SHA-256 loopback test already covers the protocol layer. This recipe validates the sample UX, the Android SAF integration path, and the bind-through-hotspot routing if combined with §H/§I. |

Other carried-forward deferrals (not blocking any tag): instrumented Android tests, process-death recovery via `SavedStateHandle`, per-socket network binding (Option C from Task 12 audit; current impl uses process-wide `bindProcessToNetwork`), encryption, iOS LAN/TCP.

See `P2pKit-Spec.md` for the complete v0.1 and planned v0.2 contracts.
