# P2pKit

A Kotlin Multiplatform SDK for discovering nearby devices and exchanging text or binary messages over the local network. The public API exposes peers, sessions, send, and receive — transport selection, mDNS, TCP framing, chunking, keep-alive, and platform differences are hidden behind it.

**Version:** v0.1 (LAN/TCP only; Android + JVM desktop).

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

- A **small, transport-agnostic API** for nearby-device communication on Android and JVM desktop.
- Built around `Peer`, `P2pSession`, `send(...)`, and a `SharedFlow<P2pMessage>` for receiving.
- Uses Kotlin **coroutines and `Flow` / `StateFlow`** everywhere; no callbacks.
- **Modular**: each transport is a separate Gradle module. Apps depend only on what they use.
- Honest about platform limits — surfaces `Unsupported` / `RequiresUserAction` / typed `P2pError`s rather than swallowing failures.

## What P2pKit is not

- Not Bluetooth, Wi-Fi Direct, Apple Multipeer, or a relay client — those are **future** transports designed to plug in behind the same API.
- Not iOS / native macOS in v0.1.
- Not encrypted in v0.1 (`SecurityMode.NoneForMvp`); the security abstraction exists so encryption can be added without breaking the public API.
- Not a file-transfer SDK in v0.1 — text and binary messages up to **4 MiB per `send()`**.
- Does not request runtime permissions on your behalf — that's the app's responsibility.
- Does not promise to put two devices on the same LAN automatically. **Network provisioning** is a planned v0.2 sidecar.

## v0.1 platform support

| Platform | Discovery | Data | Provisioning |
|---|---|---|---|
| Android (minSdk 24) | `NsdManager` mDNS | TCP via `java.net.Socket` | not in v0.1 (v0.2) |
| JVM desktop (Windows / Linux / macOS) | JmDNS | TCP via `java.net.Socket` | not in v0.1 (v0.2) |
| iOS / macOS native | not in v0.1 | not in v0.1 | not in v0.1 |

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

## Required permissions

### Android (manifest, install-time)

```xml
<uses-permission android:name="android.permission.INTERNET" />
<uses-permission android:name="android.permission.ACCESS_NETWORK_STATE" />
<uses-permission android:name="android.permission.ACCESS_WIFI_STATE" />
<uses-permission android:name="android.permission.CHANGE_WIFI_MULTICAST_STATE" />
```

`NsdManager`-based mDNS does **not** require runtime permissions on any supported API level (24-36). v0.2's Wi-Fi-Direct / hotspot work will need `NEARBY_WIFI_DEVICES` (API 33+) and possibly `ACCESS_FINE_LOCATION` for older devices; the library will not request them on your behalf, but `P2pKit.permissions.missingPermissions()` will list them.

### JVM desktop

No runtime permissions required. On first run, Windows Defender Firewall may prompt to allow inbound TCP on the chosen ephemeral port — **allow it**.

## Why LAN/TCP first

LAN + TCP is the **only transport that works the same way on every desktop and mobile platform** without proprietary stacks. Bluetooth, Wi-Fi Direct, and Multipeer each work great on one side but not the others. Starting with LAN keeps the public API honest about portability; pluggable transports are added behind it as separate Gradle modules.

## Future transport roadmap

| Transport | Status | Notes |
|---|---|---|
| LAN (mDNS + TCP) | **v0.1** | This release. |
| Network provisioning sidecar | v0.2 | Android `LocalOnlyHotspot` + Wi-Fi join helpers. API shape is locked; not implemented yet. |
| iOS / macOS LAN (Bonjour + `Network.framework`) | v0.3 | Same public API; iOS sample app to follow. |
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

- **`:p2p-core`** — public API, models, errors, protocol framing, session manager, peer registry. KMP module with `commonMain` / `jvmMain` / `androidMain`.
- **`:p2p-transport-lan`** — mDNS discovery + TCP data. JmDNS on JVM, `NsdManager` on Android.
- **`:p2p-sample-desktop`** — JVM CLI sample (`./gradlew :p2p-sample-desktop:run`).
- **`:p2p-sample-android`** — Compose UI sample. Build with `./gradlew :p2p-sample-android:assembleDebug`.

Planned modules (not in v0.1): `:p2p-network-provisioning(-android|-desktop|-ios)`, `:p2p-transport-ble`, `:p2p-transport-android-wifidirect`, `:p2p-transport-apple-multipeer`, `:p2p-transport-relay`, `:p2p-sample-ios`.

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

Type `help` for the full command list.

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

v0.1 ships **69 unit + integration tests** (67 in `:p2p-core`, 2 in `:p2p-transport-lan`). The loopback integration test in `:p2p-transport-lan` runs two `P2pKit` instances inside one JVM and exchanges a 200 KB binary payload over real TCP + mDNS — exercise the full pipeline end-to-end without external machines.

## Known limitations (v0.1)

- **`ReconnectPolicy.Enabled` is accepted but does not retry yet.** The configuration is validated, but v0.1 sessions still transition to `Failed` on disconnect — equivalent to `Disabled`. The kit emits a `P2pLogger.warn` at construction so this isn't silent, and the KDoc on `ReconnectPolicy.Enabled` says so. Real retry semantics with `maxAttempts` / `retryDelayMillis` land in v0.2.
- **`PeerId` is regenerated every process.** A device that restarts shows up to other peers with a new id. Persistent identity (a file on JVM, `DataStore` on Android) is v0.2 — it needs a `Context` accessor on Android, which we'll add together with v0.2's `initP2pKitAndroid` rework. For v0.1 internal testing, treat each app launch as a new "device" from the peer's perspective.
- **Android sample's `appId` is hardcoded** to `dev.p2pkit.sample.android` while the desktop sample uses `p2pkit-desktop-sample`. For cross-platform demos, edit one to match — or expose the field in each sample's UI.
- **No instrumented Android tests.** Android LAN paths (`NsdManager`, `AndroidLanDataTransport`, `AndroidRawConnection`) are validated by code review + manual two-device testing only. The protocol layer that flows over them is JVM-tested.
- **Android sample loses session on screen rotation.** The kit lives inside the composable, so rotation tears it down. Moving state to a `ViewModel` is v0.2 polish.

## Status

- **v0.1**: this release.
- **v0.2**: Network Provisioning sidecar (Android `LocalOnlyHotspot` + Wi-Fi join helpers; JVM network state + manual IP fallback). Will also implement `ReconnectPolicy.Enabled` retries and persistent `PeerId`. Note: concurrent-`connect` idempotency and unknown-packet warn+skip are already fixed in v0.1-internal.
- **v0.3+**: iOS / macOS LAN, BLE, Wi-Fi Direct, Multipeer, Relay, encryption.

See `P2pKit-Spec.md` for the complete v0.1 and planned v0.2 contracts.
