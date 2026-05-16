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

## Platform support

| Platform | Core types compile | Discovery | Data | Provisioning |
|---|---|---|---|---|
| Android (minSdk 24) | yes | `NsdManager` mDNS | TCP via `java.net.Socket` | not in v0.2 (v0.3+) |
| JVM desktop (Windows / Linux / macOS) | yes | JmDNS | TCP via `java.net.Socket` | not in v0.2 (v0.3+) |
| iOS (iosX64 / iosArm64 / iosSimulatorArm64) | **v0.2 scaffolding** | **not implemented** (v0.3) | **not implemented** (v0.3) | **never supported on iOS** — Apple does not allow apps to create hotspots or silently join Wi-Fi |
| macOS native | not in v0.2 | not in v0.2 | not in v0.2 | not in v0.2 |

**v0.2 iOS scope, explicitly:** `:p2p-core` declares iOS targets and ships `iosMain` actuals for `currentPlatform()`, `systemTimeMillis()`, and `PeerId` persistence (via `NSUserDefaults`). Common code — protocol framing, chunking, keep-alive, `SessionManager`, `ReconnectPolicy`, errors — compiles for iOS. **No LAN transport ships for iOS in v0.2.** `:p2p-transport-lan` remains JVM + Android only. Calling `transports { lan() }` from an iOS-targeting consumer will not link because the `lan()` extension is not declared in `iosMain` of `:p2p-transport-lan`. iOS LAN/TCP (Bonjour discovery via `NWBrowser` + TCP via `NWConnection` / `NWListener`) ships in v0.3.

Cross-platform LAN today:
- **Android ↔ JVM**: works.
- **iOS ↔ Android**: not in v0.2 — planned for v0.3.
- **iOS ↔ JVM**: not in v0.2 — planned for v0.3.

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

- **`:p2p-core`** — public API, models, errors, protocol framing, session manager, peer registry. KMP module with `commonMain` / `jvmMain` / `androidMain` / `iosMain` (core scaffolding only — no LAN).
- **`:p2p-transport-lan`** — mDNS discovery + TCP data. JmDNS on JVM, `NsdManager` on Android. **iOS targets are not declared on this module yet** (v0.3).
- **`:p2p-sample-android`** — Compose UI room/broadcast test harness. **Primary visual harness** for v0.2. `./gradlew :p2p-sample-android:assembleDebug`.
- **`:p2p-sample-desktop`** — JVM CLI test harness. **Canonical desktop harness** for v0.2. `./gradlew :p2p-sample-desktop:installDist` then run the launcher. Type `help` for commands.
- **`:p2p-sample-desktop-ui`** — Compose Desktop room/broadcast test harness. Same v0.2 feature parity as the Android sample (status header, peer chips with state + close, broadcast/targeted send, room timeline, log strip, reconnect picker, manual-IP fallback). Run with `./gradlew :p2p-sample-desktop-ui:run`.
- **`:p2p-network-provisioning-desktop`** *(v0.2.1)* — JVM Network Provisioning sidecar. Implements `getManualConnectionInfo()` + `createManualPeer(host, port)` for the manual-IP fallback when mDNS is blocked. Hotspot hosting and Wi-Fi join return `Unsupported` (Android-only capabilities). Wire into a JVM kit via `networkProvisioning { jvm() }`.
- **`:p2p-network-provisioning-android`** *(v0.2.1)* — Android Network Provisioning sidecar. Implements `startLocalNetwork()` via `WifiManager.startLocalOnlyHotspot()` (OS-chosen random SSID + passphrase), `getManualConnectionInfo()`, `createManualPeer()`, plus the matching `AndroidP2pPermissionManager`. `joinLocalNetwork()` returns `Unsupported` until v0.2.1 task 12 (Wi-Fi join). Wire into an Android kit via `networkProvisioning { android(applicationContext) }`. App must declare `NEARBY_WIFI_DEVICES` (API 33+) / `ACCESS_FINE_LOCATION` (API ≤ 32) in its manifest; library reports missing runtime perms via `P2pKit.permissions`.

Planned modules (not in v0.2.1): `:p2p-network-provisioning-android` (v0.2.1 task 11–12), `:p2p-transport-ble`, `:p2p-transport-android-wifidirect`, `:p2p-transport-apple-multipeer`, `:p2p-transport-relay`, `:p2p-sample-ios`.

## Sample feature coverage (v0.2-dev)

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

## Platform testing matrix (v0.2-dev)

| Combination | Supported now | Notes |
|---|---|---|
| Android ↔ JVM Desktop | ✅ | mDNS + TCP across same Wi-Fi; verified by §A in `INTERNAL_TESTING.md`. |
| JVM ↔ JVM | ✅ | Same machine or two machines on the same LAN. |
| Android ↔ Android | ✅ | NsdManager ↔ NsdManager on the same Wi-Fi. |
| Multi-peer room (3+ peers, mixed platforms) | ✅ | No SDK peer cap; verified by §B. |
| Android ↔ iOS | ❌ | No iOS LAN transport in v0.2. v0.3. |
| JVM ↔ iOS | ❌ | Same — v0.3. |
| iOS ↔ iOS | ❌ | Same — v0.3. |
| Three-way involving iOS | ❌ | Same — v0.3. |

## OS / device testing matrix

| Endpoint | Supported now | What can be tested | What cannot | Limitations |
|---|---|---|---|---|
| Android real device (API 24+) | yes | discovery, connect, send, broadcast, targeted, reconnect, MulticastLock | iOS interop | sample doesn't auto-call `notifyAppBackgrounded` |
| Android emulator | yes-ish | same as real device | host-firewall scenarios | NAT-through-host can break cross-machine mDNS |
| Windows JVM desktop | yes | full LAN feature set via CLI | iOS interop | Defender Firewall prompt on first run |
| macOS JVM desktop | yes | full LAN feature set | iOS interop | macOS Firewall must allow incoming |
| Linux JVM desktop | yes | full LAN feature set | iOS interop | `ufw allow 5353/udp` may be needed |
| iPhone real device | **scaffolding only** | core types compile (with macOS host) | discovery / connect / send / anything LAN | requires macOS + Xcode just to build; no `:p2p-transport-lan` for iOS |
| iOS simulator | scaffolding only | same as iPhone real | same | builds only on macOS host |
| macOS native target | not declared | nothing | everything | target not in any module |

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

Type `help` for the full command list (`info`, `sessions`, `adv on|off`, `disc on|off`, `connect`, `send`, `to`, `close`, `quit`).

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

The current `v0.2-dev` branch ships **94 unit + integration tests** in `:p2p-core` plus 2 in `:p2p-transport-lan` and 2 in `:sample-kmp-shared`. The loopback integration test in `:p2p-transport-lan` runs two `P2pKit` instances inside one JVM and exchanges a 200 KB binary payload over real TCP + mDNS — exercise the full pipeline end-to-end without external machines.

## Known limitations (v0.1-internal, partial v0.2)

- **`PeerId` persistence (v0.2 task 1 — implemented).** JVM persists automatically under `<user.home>/.p2pkit/<appId>/peer-id`. Android persists under `<filesDir>/p2pkit/<appId>/peer-id` **after** the host app calls `P2pKitAndroid.initialize(applicationContext)` (typically from `Application.onCreate`). Without the init call, Android falls back to in-memory storage and the kit logs a `P2pLogger.warn` at construction. Apps wanting persistent identity must add the init.
- **`ReconnectPolicy.Enabled` applies to outgoing sessions only (v0.2 task 3 — implemented).** When an outgoing session loses its connection, the kit transitions it to `Reconnecting` and retries the dial up to `maxAttempts` times with `retryDelayMillis` between attempts. On success the session returns to `Connected` with its public identity preserved (same `P2pSession` instance, same `incoming` flow). On exhaustion it transitions to `Failed`. **Incoming sessions do not auto-reconnect** — they still transition directly to `Failed` on connection loss; the remote peer is expected to redial. Retries reuse the originally-discovered peer transport info; if the peer's address has rotated since (e.g., Wi-Fi reconnect changed its IP), attempts may exhaust until the app re-discovers the peer and calls `connect(...)` again. Clean closes — both `session.close()` and a peer-sent `CLOSE` frame — never trigger retry.
- **Sample `appId`** is now `p2pkit-desktop-sample` on **both** the JVM desktop and Android samples — they discover each other out of the box. The desktop sample also accepts a second positional arg (`gradlew :p2p-sample-desktop:run --args="Alice some-other-app-id"`) if you want to align with a different consumer.
- **No instrumented Android tests.** Android LAN paths (`NsdManager`, `AndroidLanDataTransport`, `AndroidRawConnection`) are validated by code review + manual two-device testing only. The protocol layer that flows over them is JVM-tested.
- **Android sample survives rotation but not process death.** The kit and its session/peer/chat state live in a `P2pKitViewModel` that survives configuration changes (rotation, dark mode, locale, multi-window). If Android kills the app process while it's backgrounded, the kit is lost and the next launch starts at the setup screen. `SavedStateHandle`-based recovery is a planned v0.3 task.
- **Sample app doesn't track background/foreground.** v0.2 dropped the `LifecycleEventObserver` from the Android sample — it was firing `notifyAppBackgrounded()` on rotation start, which the kit interpreted via `BackgroundPolicy.CloseActiveSessions`. The sample now keeps the kit running until the user taps **Stop** or the `Activity` is destroyed for real. Apps that want proper background detection should wire `ProcessLifecycleOwner` (from `androidx.lifecycle:lifecycle-process`) themselves.
- **iOS support is core-only scaffolding in v0.2 (task 4).** `:p2p-core` adds `iosX64()`, `iosArm64()`, and `iosSimulatorArm64()` targets and ships iOS actuals for `Platform.IOS`, `systemTimeMillis()`, and `PeerId` persistence via `NSUserDefaults`. **No iOS LAN/TCP transport is implemented yet** — Bonjour discovery (`NWBrowser`), TCP listener (`NWListener`), and TCP client (`NWConnection`) all land in v0.3. iOS Network Provisioning is unsupported and will stay that way — Apple does not allow third-party apps to create hotspots or join Wi-Fi silently. Until v0.3 ships, iOS targets cannot exchange messages with Android/JVM peers over LAN. Build/test verification of iOS targets requires a macOS host with Xcode and is not exercised on the Windows release pipeline.
- **Room/broadcast is sample-only; auto-mesh is sample-only.** The SDK exposes one `P2pSession` per peer — there is no `P2pRoom` type, no relay, no central node. Each sample iterates `kit.sessions` and fans out sends. To make 3+ device rooms form a full mesh automatically, each sample has an **auto-mesh** switch (default ON) that calls `kit.connect()` on every newly-discovered peer when the local `localPeerId` is lexicographically less than the discovered peer's id — exactly one side per pair initiates, the other accepts the incoming. **Simultaneous-open arbitration is in the SDK itself** (v0.2 task — `SessionManager.registerSession`): even when both sides race a `connect()` call to each other at the same instant, the kit deterministically picks one physical TCP connection to keep (smaller-id peer's outgoing wins) and closes the other on both sides. `P2pKit.sessions` therefore never contains more than one entry per peer, including under user-mashes-Connect-on-both-sides scenarios.

## Status

- **v0.1**: shipped as `v0.1-internal` tag.
- **v0.2-dev** → tagged **`v0.2-internal`** at `a9d683d`. v0.2 contents: Tasks 1–8 (`PeerId` persistence, rotation survival, `ReconnectPolicy.Enabled` retry, iOS scaffolding, Android `MulticastLock`, room/broadcast samples, local identity accessors, simultaneous-open arbitration).
- **v0.2.1-dev** (current branch): Task 10 — JVM Network Provisioning sidecar with manual-IP fallback (`:p2p-network-provisioning-desktop`) — **done**. Task 11 — Android `LocalOnlyHotspot` host (`:p2p-network-provisioning-android`) — **done**. Still to do: Task 12 (Android Wi-Fi join via `WifiNetworkSpecifier`). Then tag v0.2.1-internal. Deferred to later milestones: Network Provisioning sidecar (Android `LocalOnlyHotspot` + Wi-Fi join helpers; JVM network state + manual IP fallback), file transfer API, instrumented Android tests, process-death recovery via `SavedStateHandle`.
- **v0.3+**: full iOS LAN/TCP transport (`NWBrowser` + `NWListener` + `NWConnection` + iOS sample app), macOS native LAN, BLE, Wi-Fi Direct, Multipeer, Relay, encryption.

See `P2pKit-Spec.md` for the complete v0.1 and planned v0.2 contracts.
