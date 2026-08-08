# Workspace Sync Dashboard

**Last updated:** 2026-07-28
**Current state:** `VERSION_NAME=0.7.0` release candidate — authenticated Noise
v2 and fail-closed authorization are the default; secure discovery uses
`_p2pkit2._tcp`. Published `0.6.x` artifacts are immutable. Automated
JVM/Android-host/Apple-simulator, ABI, publication-shape, consumer, and SBOM
gates are available; physical-device and remote Central release gates remain
open in `docs/STABILIZATION_AND_RELEASE.md`.
**Host context:** macOS. iOS Simulator loopback tests green; physical-radio
results must be recorded separately.

This file is the running scratchpad for state that isn't otherwise captured in
README / INTERNAL_TESTING / git. Update freely as work moves; don't treat it
as locked spec.

---

## 1. Current Backlog & Pending Verification

These items are **code-complete and tested in CI** but have no real-device
manual sign-off yet. They gate tagging the corresponding `-internal`
milestones but do not block forward development.

| Item | Branch / commit | Recipe | Blocks |
|---|---|---|---|
| **§H Android `LocalOnlyHotspot` host (Task 11)** | `v0.2.1-dev` @ `1465a7a` | `INTERNAL_TESTING.md` §H | `v0.2.1-internal` tag, and transitively `v0.2.2-internal` |
| **§I Android Wi-Fi join via `WifiNetworkSpecifier` (Task 12)** | `v0.2.1-dev` @ `1465a7a` | `INTERNAL_TESTING.md` §I | Same as above |
| **§J Cross-device file transfer end-to-end** *(non-blocking)* | `v0.2.2-dev` @ `d9edb7f` | `INTERNAL_TESTING.md` §J | Nothing — 5 MiB SHA-256 LAN loopback already covers the protocol; §J is sample-UX + SAF-on-real-device validation only |

### What's missing physically — exactly what needs human hands

To unblock `v0.2.1-internal` *and* `v0.2.2-internal`, the following must
happen on real hardware with no shortcut available from automated tests:

- [ ] **Two Android phones on the same Wi-Fi (or one with hotspot host).** Any Android API 26+ devices; mixed OEMs (e.g., Pixel + Samsung) preferred since the v0.2.1 Huawei quirk taught us OEM-specific behavior matters.
- [ ] **§H steps 1–8 on phone A:** install the sample APK, grant `NEARBY_WIFI_DEVICES` (API 33+) or `ACCESS_FINE_LOCATION` (API ≤ 32), system-wide **Location toggle ON**, tap **Host hotspot**, confirm SSID + passphrase render, and verify a peer phone joining its hotspot.
- [ ] **§I steps 1–8 on phone B:** with phone A hosting (`LocalNetworkResult.Started`), type the SSID + passphrase into the **Join hotspot** card, tap **Join**, approve the OS prompt, confirm the card flips to `Joined.` with an AP-subnet IP, and verify auto-mesh forms across the hotspot.
- [ ] **Clean teardown verification:** tap **Stop** on the guest; confirm via `adb shell dumpsys wifi | grep p2pkit` (or similar) that no `bindProcessToNetwork` reservation is leaked.
- [ ] *(Optional, non-blocking)* **§J file transfer** on the same pair: pick a ≥ 10 MiB file via the OpenDocument picker, send to the peer, confirm the saved file's hash matches the source.

### What's already covered automatically — DO NOT re-run by hand

- `:p2p-core:allTests` (KMP common + JVM — 134 unique test methods as of v0.6; `allTests` multiplies commonTest across targets).
- `:p2p-transport-lan:jvmTest` (HostSelector + the loopback tests, including the 5 MiB SHA-256 file-transfer round-trip).
- All host-side `:p2p-network-provisioning-desktop:test` and `:p2p-network-provisioning-android:testAndroidHostTest`.
- `assembleDebug` / `assemble` on every sample app.

If the device verification later surfaces a regression, fix it on the current
dev branch and re-verify there — `v0.2.1-dev` is long merged; the original
"fix on the frozen branch" rule no longer applies.

---

## 2. macOS CLI Connection & Run Guide

The JVM desktop CLI (`p2p-sample-desktop`) is the fastest way to drive the SDK
on a Mac, independent of any iOS work. It uses the same `lan()` transport
JmDNS implementation as on Windows/Linux; nothing is platform-specific.

### One-time setup on macOS

```bash
# Repo + JDK + Gradle wrapper.
# Java 17+ required (matches `jvmToolchain(17)` in the build files).
cd /path/to/P2pKit
./gradlew --version          # confirms the wrapper works and JDK is visible
```

The wrapper executable lives at `./gradlew` (shell script) on macOS — same as
Linux. The Windows `gradlew.bat` is irrelevant here. If you see
"permission denied", `chmod +x gradlew` once.

### Build + install the CLI

```bash
./gradlew :p2p-sample-desktop:installDist
```

This produces a self-contained launcher tree at:

```
p2p-sample-desktop/build/install/p2p-sample-desktop/
├── bin/
│   ├── p2p-sample-desktop       (macOS / Linux launcher script — use this)
│   └── p2p-sample-desktop.bat   (Windows — ignore)
└── lib/
    └── *.jar
```

### Run it

```bash
# Minimal — pick any device name. appId defaults to "p2pkit-desktop-sample"
# so it interops with the Android sample by default.
./p2p-sample-desktop/build/install/p2p-sample-desktop/bin/p2p-sample-desktop Alice

# With a custom appId (must match on every peer to discover each other).
./p2p-sample-desktop/build/install/p2p-sample-desktop/bin/p2p-sample-desktop Alice my.custom.app

# With ReconnectPolicy.Enabled (maxAttempts, retryDelayMillis).
./p2p-sample-desktop/build/install/p2p-sample-desktop/bin/p2p-sample-desktop Alice p2pkit-desktop-sample reconnect=5,1000
```

A second instance in a different terminal becomes `Bob`. Within a few seconds
both terminals should print `[peers] 1: Bob(<id-prefix>)…` and auto-mesh
should open a session (auto-mesh is ON by default, lexicographic tie-break).

### Targeting peers from the prompt

Once the `>` prompt is up, every command takes either an **id prefix** OR a
**name** (case-insensitive). You don't need the full peer id — the first
8 characters are usually enough.

| You want to… | Command |
|---|---|
| List discovered peers | `peers` |
| Open a session to a peer manually | `connect <id-or-name>` |
| Broadcast a text message to every active session | `send hello room` |
| Send to one specific peer | `to <id-or-name> hello bob` |
| Stream a file from disk to one peer | `sendfile <id-or-name> /Users/me/Downloads/file.zip` |
| List active sessions + state | `sessions` |
| Close one session | `close <id-or-name>` |
| Pause / resume mDNS advertise | `adv off` / `adv on` |
| Pause / resume mDNS browse | `disc off` / `disc on` |
| Pause / resume auto-mesh | `mesh off` / `mesh on` |
| Show local identity + provisioning info | `info` |
| Stop the kit cleanly and exit | `quit` |

### Bypassing auto-discovery: manual-IP fallback

When the network blocks mDNS multicast (corporate Wi-Fi, hotel guest network,
some VPNs), use the `manual` command. It calls the JVM provisioning module's
`createManualPeer(host, port)` to register a synthetic peer and immediately
dial it.

```
> info                                       # prints "manual host(s)" + "manual port"
manual host(s)   192.168.1.42, fe80::xxxx
manual port      54321

# On the OTHER side, take those host:port and:
> manual 192.168.1.42:54321
connected manual peer 192.168.1.42
```

The receiving side does **not** need to run `manual` — only the side dialing
out does. The receiver just needs `advertising` ON (default) and its
`manual port` reachable from the dialer's host.

### Verifying you're listening / broadcasting on the macOS network interfaces

Run these in a separate terminal while the CLI is up:

```bash
# 1. See which IP your Mac is using. Usually en0 (Wi-Fi) or en6 (Ethernet).
ifconfig | grep -E "^(en[0-9]+):|inet " | grep -v 127.0.0.1

# 2. Confirm the JVM has bound an ephemeral TCP port (the LAN data transport).
#    The PID column will match the `jps` line for "p2p-sample-desktop".
lsof -nP -iTCP -sTCP:LISTEN | grep java

# 3. Confirm Bonjour is advertising _p2pkit._tcp. macOS ships dns-sd; this
#    browses the local domain and lists every peer (your own + others).
dns-sd -B _p2pkit._tcp local.
#    Press Ctrl-C when done. Expect at least one row per running CLI/Android peer.

# 4. Resolve a specific Bonjour service to IP:port (paste the "Instance Name"
#    column from `dns-sd -B`).
dns-sd -L "<instance-name>" _p2pkit._tcp local.
```

### macOS-specific gotchas

- **macOS Firewall**: System Settings → Network → Firewall → Options. If the firewall is on, allow incoming connections for the JVM binary (the dialog usually pops on first run; if it doesn't, manually add `java` from `$(./gradlew -q :p2p-sample-desktop:javaToolchains)` or simply turn the firewall off while testing).
- **App Sandbox**: not applicable — the installed CLI is a plain Gradle distribution, not a sandboxed `.app`.
- **mDNS multicast on Wi-Fi**: works out of the box on home/personal networks. Hotel / guest / university Wi-Fi commonly block it. Use the **manual** command in that case, or tether two Macs via a phone hotspot.
- **macOS native target**: not declared on any module yet. The `desktop CLI` runs on the **JVM** on macOS, not as a native macOS binary. That works fine and uses the same `jvmMain` source as on Linux/Windows.

### Common failure signals (and what to check)

| Symptom | First thing to check |
|---|---|
| Stuck on `[peers] 0: ` indefinitely | Both peers on same Wi-Fi? `dns-sd -B _p2pkit._tcp local.` shows the other? |
| `dns-sd` shows both peers but CLI doesn't | Different `appId`s — pass the second positional arg to align them. |
| Connect fails with `TCP connect <ip>:<port> failed` | macOS Firewall blocking inbound, or peer crashed mid-handshake. Try `lsof` on the peer. |
| `sendfile` immediately `Failed` | Path with spaces — wrap in quotes: `sendfile bob "/Users/me/My Stuff/file.bin"`. |

---

## 3. v0.3.0-dev Roadmap (shipped)

iOS LAN/TCP via Bonjour + `Network.framework`. Cut from `v0.2.2-dev @ 0d99695`.

Status legend: `[ ]` = unstarted, `[~]` = in progress, `[x]` = done.

| Task | Title | Status | Output / verification gate |
|---|---|---|---|
| **18** | Build setup + iOS source set skeleton | `[x]` | `appleMain` source set on `:p2p-transport-lan` with `IosLan*.kt` stubs and a `lan()` extension that registers an iOS factory. `./gradlew :p2p-transport-lan:compileKotlinIosSimulatorArm64` green. |
| **19** | `IosRawConnection` + `IosLanDataTransport` | `[x]` | `nw_connection_t` wrapper with `state` StateFlow, suspending `write(bytes)`, cold `read(): Flow<ByteArray>` via `suspendCancellableCoroutine` per receive. Data transport owns one `nw_listener_t`, blocks init on `dispatch_semaphore` until `.ready` so `tcpPort` is synchronous. |
| **20** | `IosLanDiscoveryTransport` + TXT helpers | `[x]` | `nw_browser_t` for browse, `nw_listener_set_advertise_descriptor` for advertise. `IosBonjour.kt` round-trips `nw_txt_record_t` ↔ `Map<String,String>` against `LanConstants.TXT_*`. Resolved `nw_endpoint_t` stashed in `IosEndpointRegistry` keyed by peer id. |
| **21** | iosSimulatorArm64Test loopback | `[x]` | Three tests mirror `JvmLanLoopbackTest` (text, 200 KB binary, 5 MiB file) — `./gradlew :p2p-transport-lan:iosSimulatorArm64Test` reported 3/0 at ship time (the `appleTest` suite has since grown to 20 tests). Cinterop helper `src/nativeInterop/cinterop/p2pkit_nw.h` wraps the void-returning block macros (`NW_PARAMETERS_DISABLE_PROTOCOL` etc.) plus `dispatch_data_create` + `nw_connection_send` / `_receive` so Kotlin never has to box `dispatch_data_t` / `nw_content_context_t`. |
| **22** | Docs + cross-platform recipe + commit/push | `[x]` | README platform tables flipped, status section adds v0.3.0-dev row, `INTERNAL_TESTING.md` §K covers in-process simulator loopback + the Simulator-↔-CLI recipe (a placeholder at the time; active since the iOS sample app shipped in v0.4). Final pipeline + push. |

### Out of scope for v0.3.0-dev (status as of v0.6)

- **iOS sample app** — *since shipped in v0.4*: `iosApp/` carries the Xcode project (`p2pkit-sample.xcodeproj`), SwiftUI UI, and Info.plist entries. See `INTERNAL_TESTING.md` §K.2.
- **iOS Network Provisioning**. Stays `Unsupported`; Apple does not allow third-party apps to host hotspots or silently join Wi-Fi. This will *never* be implemented.
- **macOS native LAN target**. Not declared anywhere; possibly a v0.3.x track once iOS is solid.

### Definition of done for v0.3.0-dev

✅ Done as of 2026-05-17: all five tasks committed on `v0.3.0-dev`,
`:p2p-transport-lan:iosSimulatorArm64Test` reported 3/0 on the macOS host
(the suite has since grown to 20 tests), JVM + Android + all three iOS
targets compile clean, branch pushed to `origin/v0.3.0-dev`. Development
has since moved on through `v0.4-internal` and `v0.5-internal` tags; the
Task 11/12 hotspot device-verification rows in §1 remain the open backlog
(also tracked in the README backlog table).

### Notable lessons captured in code/comments
- **Kotlin/Native cannot read void-returning ObjC block globals as
  `kotlin.Any`.** `NW_PARAMETERS_DISABLE_PROTOCOL`,
  `NW_PARAMETERS_DEFAULT_CONFIGURATION`,
  `NW_CONNECTION_DEFAULT_MESSAGE_CONTEXT` all expand to such globals; reading
  them from Kotlin crashes inside `Kotlin_Interop_refFromObjC`. Workaround
  is static-inline C helpers — see `src/nativeInterop/cinterop/p2pkit_nw.h`.
- **Kotlin lambda → ObjC block conversion is sensitive to inferred return
  type.** `if (cond) { trySend(x) }` inside a callback lambda makes the
  lambda return `Any` (LUB of `ChannelResult` and the implicit-else `Unit`),
  which Kotlin/Native bridges as an id-returning block. libdispatch then
  crashes calling it. Fix: explicit `Unit` after each Unit-returning
  callback body.
- **Kotlin's `if (cond) something()` without `else` has type `Any` when
  `something()` is non-Unit.** Surfaces same bridging trap.
