# v0.3.0-dev cross-platform interop evidence

Captured 2026-05-17 during the validation audit pass.

## Setup

- JVM CLI: `./p2p-sample-desktop/build/install/p2p-sample-desktop/bin/p2p-sample-desktop JvmAlice` (default `appId = "p2pkit-desktop-sample"`)
- iOS Simulator: `IosLanDiagnosticTest.advertiseForSixtySecondsForInteropCapture` with matching `appId`
- Network observation: `dns-sd -B _p2pkit._tcp local.` (host-side `mDNSResponder`)

The `@Ignore`-marked diagnostic test is the iOS-side fixture: it holds a kit alive for 60 s advertising over `nw_listener_set_advertise_descriptor`. Un-`@Ignore` to re-run.

## Files

- `dns-sd-browse.log` — `dns-sd -B` output capturing both services appearing and disappearing over the run.
- `jvm-cli.log` — JVM CLI's peer-discovery + auto-mesh + state transitions log.

## What the evidence proves

### JVM (JmDNS) → iOS (NWListener.advertise + NWBrowser) wire compatibility ✅

From `jvm-cli.log`:

```
[P2pKit CLI] deviceName=JvmAlice  appId=p2pkit-desktop-sample  reconnect=Disabled
[peers] 0:
Ready. Type 'help' for commands.
> [p2pkit] auto-mesh: initiating connect to iOSDiagnostic
[peers] 1: iOSDiagnostic(61ca2c26)
[state] iOSDiagnostic → Connected
[peers] 0:
[peers] 1: iOSDiagnostic(61ca2c26)
[peers] 0:
[state] iOSDiagnostic → Closed
```

- JVM's JmDNS browser discovered the iOS-advertised peer (`iOSDiagnostic`) from a clean state.
- TXT record decoded successfully (else the peer would have been filtered out by the JVM-side appId match).
- Auto-mesh chose JVM as initiator (lexicographically smaller `localPeerId`).
- TCP connection to the iOS `nw_listener_t` succeeded and `Connected` was reached — i.e., the wire-level protocol handshake (Hello frames) completed.
- Clean shutdown observed when the iOS test ended: `[state] iOSDiagnostic → Closed`.

### Bonjour multicast cross-visibility ✅

From `dns-sd-browse.log`:

```
Browsing for _p2pkit._tcp.local.
Timestamp     A/R    Flags  if Domain   Service Type    Instance Name
15:16:56.417  Add        2  14 local.   _p2pkit._tcp.   0f0ddd0b-e720-437f-8498-904523e4c41f
15:17:34.449  Add        3   1 local.   _p2pkit._tcp.   61ca2c26-9442-4e41-8e13-c3e2a4c83ab0
15:17:34.449  Add        2  14 local.   _p2pkit._tcp.   61ca2c26-9442-4e41-8e13-c3e2a4c83ab0
15:18:34.753  Rmv        1   1 local.   _p2pkit._tcp.   61ca2c26-9442-4e41-8e13-c3e2a4c83ab0
15:18:34.753  Rmv        0  14 local.   _p2pkit._tcp.   61ca2c26-9442-4e41-8e13-c3e2a4c83ab0
```

- JVM service `0f0ddd0b-...` (advertised via JmDNS) and iOS service `61ca2c26-...` (advertised via `nw_listener_set_advertise_descriptor`) BOTH appear under the same `_p2pkit._tcp` service type — proving wire-level service-type compatibility on the Bonjour multicast layer.
- iOS service was added at 15:17:34 and cleanly removed at 15:18:34 — 60 s lifetime matching the diagnostic test's advertise window.
- Both services were visible on multiple interfaces (`if 1` = loopback, `if 14` = en0 Wi-Fi).

### TXT record from JVM side decoded correctly ✅

```
$ dns-sd -L "0f0ddd0b-..." _p2pkit._tcp local.
0f0ddd0b-...._p2pkit._tcp.local. can be reached at fd42-...-en0.local.:58680
 pid=0f0ddd0b-e720-437f-8498-904523e4c41f
 app=p2pkit-desktop-sample
 name=JvmAlice
 plat=JVM_DESKTOP
 caps=LAN
 pv=1
```

All `LanConstants.TXT_*` keys present and well-formed. The iOS `IosBonjour.txtRecordToMap` parses this same key set (proven by `IosBonjourTest`).

## Gaps in this evidence

- **iOS-side discovery of the JVM peer is implied but not directly captured.** The 60 s diagnostic test prints `DIAG: t=...s peers=...` lines, but Gradle's `iosSimulatorArm64Test` swallows test-process stdout (only test results are bridged back to the host). The JVM auto-mesh initiate behavior (JVM took the initiator role) means the iOS side also saw the JVM peer — but a more rigorous capture would require either an explicit Kotlin/Native test logger or asserting `kit.peers.value.size > 0` inside the test before returning.
- **iOS TXT record dump via `dns-sd -L`** was attempted but missed the 60 s advertise window. The TXT-key contract is proven via `IosBonjourTest` (round-trip) and `LanConstants` (commonMain shared definition), so wire compatibility is established by construction.
- **Real-iPhone / real-Android validation not run.** Tracked separately in the audit report.
