# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

P2pKit is a Kotlin Multiplatform SDK for discovering nearby devices and exchanging messages/files over the local network (mDNS discovery + TCP data). Targets: JVM desktop, Android (minSdk 24), iOS. The public API (`P2pKit`, `Peer`, `P2pSession`, `send`, flows for receive) hides transport selection, framing, chunking, and keep-alive. The API contract is locked by `P2pKit-Spec.md` — don't change public API shape casually.

## Commands

```bash
# Build everything that matters
./gradlew :p2p-core:assemble :p2p-transport-lan:assemble

# Tests
./gradlew :p2p-core:allTests                        # all targets' tests for core
./gradlew :p2p-core:jvmTest                         # JVM-only (fastest loop)
./gradlew :p2p-transport-lan:jvmTest                # JVM LAN loopback (real TCP + mDNS in one JVM)
./gradlew :p2p-transport-lan:iosSimulatorArm64Test  # iOS loopback (macOS + Xcode + simulator runtime required)
./gradlew :p2p-network-provisioning-android:testAndroidHostTest
./gradlew :p2p-network-provisioning-desktop:test

# Single test class / method (per-target task + --tests filter)
./gradlew :p2p-core:jvmTest --tests "dev.p2pkit.core.internal.SessionFlowTest"
./gradlew :p2p-core:jvmTest --tests "*FileTransferFlowTest.someTestName*"

# Sample apps
./gradlew :p2p-sample-desktop:installDist           # then run p2p-sample-desktop/build/install/p2p-sample-desktop/bin/p2p-sample-desktop <Name>
./gradlew :p2p-sample-desktop-ui:run                # Compose Desktop UI
./gradlew :p2p-sample-android:assembleDebug         # APK at p2p-sample-android/build/outputs/apk/debug/

# iOS framework for the Xcode sample (macOS only)
./gradlew :p2p-transport-lan:assembleP2pKitSharedXCFramework
```

There is no lint/format task configured. Maven coordinates come from `gradle.properties` (`GROUP` / `VERSION_NAME`) applied to all modules in the root `build.gradle.kts`; a publishing plugin is not yet wired (see `PROBLEMS_P2PKIT.md`).

## Module structure

- **`:p2p-core`** — public API, models, typed errors, protocol layer, session/peer management, file transfer. KMP: jvm, android, iosX64/iosArm64/iosSimulatorArm64. No LAN code here.
- **`:p2p-transport-lan`** — the only shipped transport. JmDNS + `java.net.Socket` on JVM **and Android** (Android discovery was migrated from `NsdManager` to in-process JmDNS in v0.5 so the SDK owns the mDNS cache — don't reintroduce NsdManager); `Network.framework` (`nw_browser_t`/`nw_listener_t`/`nw_connection_t`) on iOS via an `appleMain` source set. Depends on `:p2p-core` and exports it into the iOS XCFramework.
- **`:p2p-network-provisioning-android` / `-desktop`** — optional sidecars implementing `NetworkProvisioningManager` (Android `LocalOnlyHotspot` host + Wi-Fi join; JVM manual-IP fallback). iOS provisioning is permanently `Unsupported` (Apple policy).
- **`:p2p-sample-desktop`** (JVM CLI), **`:p2p-sample-desktop-ui`** (Compose Desktop), **`:p2p-sample-android`** (Compose), **`:sample-kmp-shared`**, **`:iosApp`** (Xcode project; pre-build script runs gradle via `sh ./gradlew`) — test harnesses, not published.

## Architecture (the core pipeline)

Everything is coroutines + `Flow`/`StateFlow`/`SharedFlow`; there are no callbacks. Layering inside `:p2p-core` (`dev/p2pkit/core/internal/` and `protocol/`):

```
P2pKit public API (P2pKitImpl wires everything, owns the kit scope)
  PeerRegistry        ← aggregates/dedupes PeerEvents from all DiscoveryTransports, tracks lastSeen → peers StateFlow
  SessionManager      ← connect(peer) outgoing + accepts incoming connections; HELLO handshake; one session per peer
                        (simultaneous-open arbitration: smaller-peer-id's outgoing connection wins);
                        SessionReconnectHandler retries outgoing dials when ReconnectPolicy.Enabled
  P2pSessionImpl      ← per-session state machine; Mutex-serialized writes; routes frames (DATA→incoming,
                        PING/PONG→keep-alive, CLOSE→clean shutdown); rearmWith(newConnection) swaps the
                        connection on reconnect while preserving the public session instance
  DefaultP2pProtocol  ← framing/chunking/reassembly + control frames; FileTransferDispatcher for FILE_* frames
  TransportManager    ← picks the DataTransport to dial a peer
  DataTransport / DiscoveryTransport / RawConnection  ← implemented by :p2p-transport-lan per platform
```

Transports plug in via `TransportFactory` and the `transports { lan() }` DSL — new transports (BLE, Wi-Fi Direct, etc.) are meant to be added as new Gradle modules behind the same API.

### Wire protocol — keep platforms identical

The three platform transport implementations must stay wire-compatible: Bonjour service type `_p2pkit._tcp`, identical TXT record keys, and the binary frame format in `protocol/` (magic "PP2K", version 1, 36-byte header; frame types DATA/HELLO/ACK/PING/PONG/CLOSE/ERROR/FILE_OFFER/FILE_ACCEPT/FILE_REJECT/FILE_DATA/FILE_DONE/FILE_CANCEL). Limits live in `ProtocolConstants`: 4 MiB max per `send()` message, 8 MiB max frame payload (DoS guard), 64 KiB default chunks, reassembly caps/timeouts. A change to any of these must be mirrored across jvmMain/androidMain/appleMain or cross-platform interop breaks.

### Reconnect semantics (subtle, frequently touched)

Only **outgoing** sessions auto-reconnect; incoming sessions go straight to `Failed` and the remote redials. Each retry re-resolves the peer endpoint from fresh discovery data, and during the whole `Reconnecting` window `SessionManager` refires `DiscoveryTransport.refresh()` every ~3 s. Clean closes (local `close()` or peer CLOSE frame) never trigger retry. `SessionStore` is the single source of truth for session state; terminal transitions go through one `transitionToTerminal` codepath.

### iOS specifics

Apple targets share `appleMain` in `:p2p-transport-lan` with a cinterop header at `src/nativeInterop/cinterop/p2pkit_nw.h` that wraps void-returning ObjC block macros (`NW_PARAMETERS_DISABLE_PROTOCOL`, `NW_CONNECTION_DEFAULT_MESSAGE_CONTEXT`, dispatch_data helpers) that Kotlin/Native cannot box — go through that helper rather than calling those macros directly. iOS targets compile only on a macOS host.

## Testing notes

- Core logic is tested in `commonTest` using fakes in `p2p-core/src/commonTest/.../testfixtures/` (`FakeDataTransport`, `FakeDiscoveryTransport`, `FakeRawConnection`, `FakeNetworkPathObserver`) — prefer these for session/protocol/reconnect tests; no real I/O needed.
- Integration: `:p2p-transport-lan:jvmTest` runs two full `P2pKit` instances in one JVM over real TCP + mDNS (text, 200 KB binary, SHA-256-verified 5 MiB file). `iosSimulatorArm64Test` mirrors it over real Bonjour + `nw_connection_t`.
- There are **no instrumented Android tests** — Android-specific LAN paths are verified manually (recipes in `INTERNAL_TESTING.md`).

## Key documents

- `P2pKit-Spec.md` — the API/design contract.
- `PROBLEMS_P2PKIT.md` — production-readiness audit (238 confirmed findings with severities); the active worklist for hardening. Check it before "fixing" something — the problem may already be catalogued with an agreed fix.
- `INTERNAL_TESTING.md` — manual multi-device test recipes (§A–§K), including the JVM CLI ↔ iOS Simulator pairing.
- `docs/production-readiness.md` — design notes for hardening work (backoff, NetworkPathObserver, lifecycle ownership).

## Conventions

- Never nest `collect { collect { … } }` — use `launchIn(scope)` on inner flows (stated rule in README, followed throughout samples).
- Surface failures as typed `P2pError` / `Unsupported` / `RequiresUserAction` rather than swallowing them; the SDK never requests runtime permissions itself (reports them via `P2pKit.permissions`).
- Version-numbered marker comments (e.g. `V0.4-RECONNECT`, `V0.4-D-ANDROID-NUDGE`) tag behaviorally significant fixes in code and are referenced from README/docs — keep them when refactoring.
