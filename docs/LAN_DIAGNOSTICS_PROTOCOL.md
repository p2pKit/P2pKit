# LAN Diagnostics — Physical Test Protocols (Issue #2 & Issue #3)

**Purpose.** Drive the two hardware-dependent transport issues on real devices
and capture a full diagnostic trail to send back for forensic verification.

- **Issue #2 — Interface Selection:** the SDK can bind mDNS / dial over the
  *wrong* local interface (VPN tunnel, cellular, virtual, loopback) instead of
  the real Wi-Fi/Ethernet LAN.
- **Issue #3 — iOS AWDL asymmetry:** the iOS *browser* opts into peer-to-peer
  (AWDL), but the *listener/connection* params do not — so an AWDL-discovered
  peer may be undialable.

This build adds trace logging across every relevant path. **Capture everything;
do not pre-filter.** Send the raw logs back.

> **Already proven on the dev Mac:** running the desktop CLI immediately showed
> JmDNS binding to `utun5` (a VPN tunnel, `fe80::…` link-local) instead of `en0`
> (`192.168.1.4`, the real Wi-Fi LAN). That is Issue #2 in one line — your
> device logs will show the same shape.

---

## 0. One-time setup: turn the trace ON and learn where it prints

| Platform | How logging is enabled | Where it appears | How to capture |
|---|---|---|---|
| **JVM desktop** (`p2p-sample-desktop` CLI or `-ui`) | **On by default** in the samples (transport trace + decoded frame-type trace). CLI extra modes: `trace=frames` (also byte-level), `trace=off`. | **stdout**, prefixes `P2pKitLAN` (transport) + `P2pKitFRAME` (frame types). | `… | tee jvm-trace.log` |
| **Android** (`p2p-sample-android`) | **Always on** (logcat). The sample also enables frame-type trace (routed to a `P2pKitFrame` logcat tag). For byte-level frames too, set `AndroidLanDiag.traceFrames = true`. | **logcat**, all tags start with `P2pKit`. | `adb logcat -v time | tee android-trace.log` (filter: `grep P2pKit`) |
| **iOS** (`iosApp`) | **On by default** — sample sets `IosLanDebug.shared.mirrorToConsole = true` (+ shows an in-app log) and `FrameTrace.shared.enabled = true`. | **Xcode console** / **Console.app**: transport lines filter `p2pkit`, frame-type lines filter `P2pKitFRAME`. | Xcode: copy the console. Console.app: filter `p2pkit OR P2pKitFRAME`, File ▸ Save. |

**Decoded frame-type trace (all platforms).** Alongside the transport byte
lines, each protocol frame is logged once per direction with its command name
and size, e.g. `P2pKitFRAME TX type=PING len=0B`, `… RX type=DATA len=1024B
chunk=2/3 id=ab12cd34`, `… TX type=FILE_DATA len=65536B chunk=10/80 id=… `,
`… RX type=PONG len=0B`. This makes a keep-alive PING, a message DATA chunk, and
a FILE_DATA chunk distinguishable at a glance.

**Tag legend** (what each line means):

| Tag (JVM `P2pKitLAN [tag]` / Android tag / iOS `[tag]`) | Meaning |
|---|---|
| `bind` / `P2pKitJmDNS ensureJmdns` | which local address/interface JmDNS bound to |
| `nic` / `P2pKitJmDNS NICs` | full local interface dump (name, flags, MTU, addresses) |
| `P2pKitJmDNS active …transports=[…]` | **Android only:** is the bound network WIFI / CELLULAR / ETHERNET / VPN |
| `advertise` | the addresses we published for peers to dial |
| `browse` | discovery events: serviceResolved candidates + selected host:port, Lost |
| `dial` / `P2pKitLanData connect` | outbound TCP: target, **local egress address**, success/fail reason |
| `accept` / `P2pKitLanData inbound` | inbound TCP accepted |
| `conn` / `P2pKitLanConn` | per-connection lifecycle: open, EOF, socket drop, write timeout, close; iOS adds connection **path interfaces** + nw_error codes |
| `P2pKitFRAME` (all platforms) | decoded protocol frame per direction: `TX/RX type=<CMD> len=<bytes>` (+ chunk/id for DATA/FILE_DATA) — the command-name layer above the byte trace |

Before each run: **note the wall-clock time and the device's network state**
(Wi-Fi SSID, VPN on/off, cellular on/off). Label each log file by scenario.

---

## Issue #2 — Interface Selection

**Hypothesis:** on a device with more than one usable interface (Wi-Fi **plus**
a VPN tunnel, a cellular link, an Ethernet dock, or while hosting/joining a
hotspot), the SDK binds mDNS and/or egresses TCP on the wrong one, so peers
either never resolve a routable address or the dial leaves on a non-LAN route.

**Recommended rig:** Device A = Android phone; Device B = JVM desktop (laptop).
A second Android phone works too. All on the **same Wi-Fi** to start.

### Test 2A — Baseline (clean Wi-Fi, no competing interface)

1. Desktop: **disconnect any VPN**, disconnect Ethernet, leave only Wi-Fi.
   Phone: Wi-Fi on, **cellular OFF**, no VPN. Same SSID.
2. Start Device B (desktop CLI):
   `./gradlew :p2p-sample-desktop:installDist` then
   `… /bin/p2p-sample-desktop DeskA 2>&1 | tee 2A-desktop.log`
   At the `>` prompt type `disc on`, then `adv on`.
3. Start Device A (Android sample); begin `adb logcat -v time | tee 2A-android.log`.
4. In each app, turn on **advertise + discover**. Wait until each side lists the
   other as a peer (~5–15 s).
5. Connect A→B (or use the sample's connect button / `connect <name>`), send a
   text, send a small file.
6. Stop both. Save both logs.

**Read the trail (and what "good" looks like):**
- `bind`: `boundInterface=` should be the **Wi-Fi LAN IPv4** (e.g. `192.168.x.y`),
  **not** a `fe80::…%utunN` (VPN), `…%awdl0`, or `127.0.0.1`.
- Android `active …transports=[WIFI]` (good) vs `[CELLULAR]`/`[VPN]` (bug).
- `advertise … publishedAddrs=[…]` should contain the Wi-Fi IPv4.
- `browse serviceResolved … candidates=[…] selected=…`: selected host should be
  the peer's Wi-Fi IPv4.
- `dial connect OK … local=<addr>`: `local` is the interface the OS egressed on —
  expect the Wi-Fi subnet.

### Test 2B — VPN competing interface (desktop)

1. Repeat 2A but **turn ON a VPN** on the desktop **before** starting the CLI.
   `… DeskB 2>&1 | tee 2B-desktop.log`.
2. `disc on`, `adv on`, then try to connect with the phone.

**Look for:** `bind boundInterface=fe80:…%utunN` (bound to the VPN tunnel) and/or
`advertise publishedAddrs` containing only a `utunN` link-local. If the phone
then logs `browse … no routable host` or `dial … unreachable/timeout`, that is
Issue #2 confirmed end-to-end.

### Test 2C — Android cellular + Wi-Fi

1. Android: Wi-Fi on **and cellular ON** (the common real-world state).
   `adb logcat -v time | tee 2C-android.log`.
2. Start the app, advertise + discover, connect to the desktop, send a file.
3. Then **toggle Wi-Fi off→on** once mid-session and watch the rebind.

**Look for:** `P2pKitJmDNS ensureJmdns: active … transports=[…]` — must be `WIFI`,
never `CELLULAR`. On the Wi-Fi flip: `scheduleRebind` → `rebindNow: rebinding onto
…transports=[WIFI]` and a fresh `bindAddr`. A `transports=[CELLULAR]` bind, or a
`dial … local=<cellular-subnet>`, is the bug.

### Test 2D — Hotspot host/join (2× Android, optional)

1. Phone A: **start a Wi-Fi hotspot / LocalOnlyHotspot** via the sample's
   provisioning UI. Phone B: **join** it. Logcat both.
2. Advertise + discover + connect over the hotspot link.

**Look for:** on the host, `DefaultNetworkCallback` firing and `rebindNow` landing
on the AP interface; on both, the `bind`/`active` lines showing the hotspot
subnet (often `192.168.49.x` for LocalOnlyHotspot). Discovery/dial should use
that subnet.

### Issue #2 — what to send back
All `2A`–`2D` log files (both devices each), plus for each scenario a one-line
note: which interfaces were active, whether the peer appeared, whether
connect/send/file succeeded, and the wall-clock of each network flip.

---

## Issue #3 — iOS AWDL asymmetry

**Hypothesis:** the browser discovers a peer over **AWDL/peer-to-peer**, but
because the listener/connection params never call
`nw_parameters_set_include_peer_to_peer`, the subsequent dial cannot route over
AWDL and the connection **parks in `waiting`** (no-route) or never reaches
`ready`.

**Forcing AWDL.** AWDL is Apple's peer-to-peer Wi-Fi link, used when two devices
can discover each other but have no shared infrastructure route. The most
reliable way to exercise it:

- **Rig:** two iOS devices (iPhone/iPad), **or** an iPhone + a Mac running the
  desktop sample.
- **Scenario A (same Wi-Fi):** both on the same Wi-Fi — confirms the normal
  infrastructure path still works and shows which interface `ready` uses.
- **Scenario B (AWDL-only):** put the two iOS devices on Wi-Fi but **different
  networks** (e.g. Device 1 on a router, Device 2 on a *different* router or a
  phone hotspot it alone joined), **or** turn the router's client isolation on,
  **or** disconnect both from any Wi-Fi but leave Wi-Fi radios ON (Bonjour will
  fall back to AWDL). The goal: discovery succeeds while infrastructure routing
  does not.

### Steps

1. Build/run `iosApp` from Xcode on Device 1 (keep Xcode console open, or open
   **Console.app** on the Mac and filter `p2pkit`). Start the peer (Device 2 /
   Mac CLI) with its own log capture.
2. In the iOS app, start **advertise + discover**.
3. Confirm discovery: look for
   `[browse] browser params: include_peer_to_peer=true (AWDL discovery ENABLED)`
   then `[browse] emitPeer: ACCEPTED Found <name>`.
4. **Attempt to connect** to that peer (and try a text + a file).
5. Repeat for Scenario A and Scenario B; label the logs `3A-ios.log` /
   `3B-ios.log` (+ the peer-side logs).

### Read the trail
On the **dial** you will see, in order:
- `[data] TCP params built: … include_peer_to_peer=NOT_SET … (issue #3)` — the
  asymmetry, logged once.
- `[connect] peer=… endpointSource=browse(AWDL-capable) connParams.include_peer_to_peer=NOT_SET`
  — we discovered it via the (AWDL-enabled) browser but are dialing without AWDL.
- Then the connection states from `[conn]`:
  - **Success path:** `state-changed -> ready` then
    `ready path interfaces: wifi=… cellular=… wired=… loopback=… other=…`.
    If `other=true` (or it succeeds only on Scenario A and not B), note it.
  - **AWDL-undialable signature:** `state-changed -> waiting errCode=<n>` and the
    explicit `WAITING errCode=<n> — endpoint not yet routable (AWDL-only peer
    without include_peer_to_peer? issue #3)`. `errCode=65` = EHOSTUNREACH,
    `60` = ETIMEDOUT, `61` = ECONNREFUSED. A dial that sits in `waiting` and
    never reaches `ready` (eventually `connect TIMEOUT after 10000ms`) in
    Scenario B but works in Scenario A **confirms Issue #3**.

### Issue #3 — what to send back
`3A`/`3B` iOS logs (Console.app or Xcode) **and** the peer-side logs, plus for
each: did the peer appear in the list, did connect/text/file succeed, and the
exact `[conn] state-changed` sequence with any `errCode`.

---

## Appendix — capture cheat-sheet

```bash
# JVM desktop CLI (trace on by default; add trace=frames for byte-level)
./gradlew :p2p-sample-desktop:installDist
./p2p-sample-desktop/build/install/p2p-sample-desktop/bin/p2p-sample-desktop MyDesk 2>&1 | tee desktop-trace.log
#   at the > prompt:  disc on   adv on   connect <peer>   sendfile <peer> <path>   quit

# Android (all P2pKit tags; clear first so the log starts at the test)
adb logcat -c && adb logcat -v time | tee android-trace.log
#   isolate ours:  grep P2pKit android-trace.log

# iOS — Console.app: filter "p2pkit", reproduce, File ▸ Save.
#   or run from Xcode and copy the console after the repro.
```

When sending logs back, include: device models + OS versions, the Wi-Fi/VPN/
cellular state per device, and the wall-clock of each manual network change so
the timestamps in the trail can be lined up across devices.
