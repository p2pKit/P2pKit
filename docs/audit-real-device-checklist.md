# v0.3.0-dev real-device validation checklist

Three tracks, all **NOT RUN** as of the 2026-05-17 audit pass (no hardware on the macOS workstation).

| Track | Hardware needed | Owner ref |
|---|---|---|
| Android Task 11 (`LocalOnlyHotspot` host) | 2× Android API 26+ phones | `INTERNAL_TESTING.md §H` |
| Android Task 12 (`WifiNetworkSpecifier` join) | Same pair | `INTERNAL_TESTING.md §I` |
| iOS sample on physical iPhone | 1× iPhone running iOS 14+ | `docs/ios-sample-app/README.md` |

Each test below carries an explicit pass/fail criterion plus the **single line of evidence** to capture (logcat snippet, screenshot, or dns-sd output) so that a future audit can verify the row was actually run, not just claimed.

---

## A. Android — Task 11: `LocalOnlyHotspot` host

Source recipe: `INTERNAL_TESTING.md §H`. The recipe below is the same in test order but with stricter pass/fail criteria.

### A.1 — Hotspot starts and credentials are visible

| | |
|---|---|
| Steps | (1) Install sample APK on phone A. (2) Grant `NEARBY_WIFI_DEVICES` (API 33+) or `ACCESS_FINE_LOCATION` (≤ API 32). (3) Verify device-wide Location toggle is ON in Settings → Location. (4) Tap **Host hotspot** in the Hotspot card. |
| Expected | The card transitions from idle → `Starting` → `Started` within ~2 s. Card body shows `SSID: AndroidShare_xxxx`, `Pass: <8-char-passphrase>`, and `host(s): 192.168.43.x` plus a port number. |
| Pass | All three fields populated AND `adb shell dumpsys wifi \| grep -i localonlyhotspot` confirms the reservation is held. |
| Fail | Card stays on `Starting` past 5 s, OR shows `Failed: HotspotStopped — startLocalOnlyHotspot failed (reason code X)`. Reason codes: NO_CHANNEL=0, GENERIC=1, INCOMPATIBLE_MODE=2, TETHERING_DISALLOWED=3. |
| Evidence | Screenshot of the card in `Started` state PLUS the dumpsys output line. |
| OEM notes | Huawei / MIUI / older Samsung throw `SecurityException("Location mode is not enabled")` even with the runtime perm granted. The card surfaces an **Open Location settings** button — verify it opens the right system page. |

### A.2 — Second device can join the hotspot

| | |
|---|---|
| Steps | (1) On phone B, open Wi-Fi settings. (2) Find the `AndroidShare_xxxx` SSID. (3) Enter the passphrase from A.1. (4) Connect. |
| Expected | B joins within ~5 s; its Wi-Fi indicator shows the new SSID. `adb -s <B> shell ip addr show wlan0` lists an IP in the same subnet as phone A's (`192.168.43.x`). |
| Pass | Both phones on the AP subnet, ping in either direction succeeds. |
| Fail | B's Wi-Fi sticks on "Obtaining IP address" past 30 s, OR shows "Saved" but never connects. |
| Evidence | `ip addr` output from B showing the matching subnet. |

### A.3 — LAN discovery + session over the hotspot

| | |
|---|---|
| Steps | (1) Launch the sample on B (not the hotspot host). (2) Tap **Start**. (3) Watch the discovered-peers list. (4) Tap **Connect** on A. (5) Send text both directions. |
| Expected | B's discovered list shows A within ~10 s. Tap Connect → session reaches Connected. Bidirectional `send` round-trips in both directions. |
| Pass | Session forms, both sides print sent messages on the other. No `Failed` state observed. |
| Fail | 0 peers discovered after 30 s (means mDNS isn't propagating over the hotspot subnet — usually fine on AOSP, fails on some OEM kernels). |
| Evidence | logcat: `kit started`, `session A → Connected`, `[broadcast → 1]` lines. |

### A.4 — 200 KB binary + 5 MB file over hotspot

| | |
|---|---|
| Steps | From the §J file-transfer recipe: pick a ≥ 10 MiB file via the SAF picker on B; tap Send to A. Then reverse. |
| Expected | Transfer card on both sides walks `Offered → Accepted → Sending(N%) → Completed`. Bytes match (`adb pull` from each side and `shasum -a 256` if you want hard evidence). |
| Pass | SHA-256 matches in both directions. Cancel button works mid-transfer (both sides flip to `Cancelled` within 1 s). |
| Fail | Transfer stalls past 60 s without progress, OR completes but saved file is shorter than expected. |
| Evidence | `shasum -a 256` outputs OR a screenshot of the Completed row showing the full byte count. |

### A.5 — Hotspot stop releases reservation cleanly

| | |
|---|---|
| Steps | On A, tap **Stop hotspot**. Wait 3 s. |
| Expected | Card returns to idle "Host a LocalOnlyHotspot…" state. Phone B drops the Wi-Fi connection (the AP is gone). `dumpsys wifi \| grep -i localonlyhotspot` no longer shows the reservation. |
| Pass | No leaked reservation. Subsequent **Host hotspot** taps work — proves the OS released the slot. |
| Fail | dumpsys still shows the reservation, OR a subsequent host attempt errors with "already started". |
| Evidence | Before/after dumpsys output. |

---

## B. Android — Task 12: `WifiNetworkSpecifier` client join

Source recipe: `INTERNAL_TESTING.md §I`. Phone B is the guest, joining A's hotspot from inside the sample (not via system Wi-Fi settings).

### B.1 — Join card accepts credentials and OS prompt appears

| | |
|---|---|
| Steps | (1) Complete A.1 so phone A hosts the hotspot. (2) On phone B, scroll to **Join hotspot** card. (3) Type the SSID + passphrase from A.1. (4) Tap **Join hotspot**. (5) Grant `NEARBY_WIFI_DEVICES` if prompted. |
| Expected | Android shows its own "Use device's Wi-Fi to connect to 'AndroidShare_xxxx'?" sheet. |
| Pass | OS sheet appears. Tap **Connect** → card flips to `Joining` then `Joined` within ~5 s. |
| Fail | OS sheet never appears (usually a missing `NEARBY_WIFI_DEVICES` grant), OR `Failed: JoinFailed — network unavailable — user declined, SSID not found, or wrong passphrase` (recipe lists the diagnosis steps). |
| Evidence | Screenshot of the OS prompt AND the `Joined.` card state with AP-subnet IP visible. |

### B.2 — Process-wide network binding routes traffic through the AP

| | |
|---|---|
| Steps | With the join active, launch the LAN sample on B. Tap **Start**. |
| Expected | Discovered-peers list populates with phone A within ~10 s. Auto-mesh opens a session. |
| Pass | Session forms over the AP subnet (not the original Wi-Fi, since `bindProcessToNetwork` is in effect). Round-trip a text message. |
| Fail | Discovery shows 0 peers despite `Joined.` — indicates the kit didn't pick up the bound network. |
| Evidence | logcat: `[NetworkProvisioning] bindProcessToNetwork: ...` + auto-mesh + `Connected`. |

### B.3 — `kit.stop()` releases the network binding

| | |
|---|---|
| Steps | On B, tap **Stop**. |
| Expected | `ConnectivityManager.bindProcessToNetwork(null)` is called via the manager's `close()`. `unregisterNetworkCallback` releases the reservation. Phone B's Wi-Fi returns to whatever network it was on before joining. |
| Pass | `adb shell dumpsys connectivity \| grep -i wifinetworkspecifier` shows no held requests. |
| Fail | Reservation still held; subsequent join attempts fail with "a join is already in progress". |
| Evidence | Before/after dumpsys output. |

### B.4 — Failure paths surface as documented errors

| | |
|---|---|
| Steps | (1) Type a wrong passphrase, tap Join, decline the OS prompt. (2) Try again with correct creds. (3) Toggle Wi-Fi off mid-join. |
| Expected | Each surfaces a specific `Failed: JoinFailed — <reason>` message: `network unavailable`, `join released: ...`, or `a join is already in progress`. |
| Pass | All three error modes match the recipe's failure-reasons table. |
| Fail | Generic "failed" with no useful reason, OR a crash. |
| Evidence | Screenshot of each failure card. |

---

## C. iPhone — sample-app device validation

See `docs/ios-sample-app/README.md` §4 for the full T1.1 → T1.10 checklist. The matrix below is the **abbreviated pass/fail criteria** for quick reporting.

| ID | Test | Pass criteria | Evidence |
|---|---|---|---|
| T1.1 | Local-network permission prompt | Prompt appears exactly once on first launch; subsequent launches use saved decision | Screenshot of prompt + kit-started log |
| T1.2 | Discover JVM peer | Both sides see each other within 5 s | iPhone screenshot + JVM CLI `[peers] 1: …` line |
| T1.3 | iPhone → JVM session | Reaches `Connected` within 10 s | JVM `[state] iPhone → Connected` |
| T1.4 | JVM → iPhone session | Same | iPhone "incoming sessions" screenshot |
| T1.5 | Bidirectional text | Both messages arrive verbatim | Screenshots of both sides |
| T1.6 | 200 KB binary | SHA-256 matches both directions | `shasum -a 256` outputs |
| T1.7 | 5 MB file | SHA-256 matches; state walks Offered → Completed | `shasum -a 256` outputs + screenshot of Completed row |
| T1.8 | Stop / restart cycle | Same `localPeerId` post-restart (NSUserDefaults persistence); no leaked Bonjour entry | `dns-sd -B _p2pkit._tcp local.` before / during / after |
| T1.9 | Background → foreground | No crash; session either survives or is observably re-established | Console log of foreground transition |
| T1.10 | Wi-Fi off → on | No crash; no hung `Connecting`; kit recovers without restart | Same |

---

## How to report results back

Each row above expects a single piece of evidence (screenshot, log line, hash). The audit report's "What was actually tested" table should be updated with rows like:

```
| T1.2 | iPhone 17, iOS 26.2 | <see steps> | PASS | screenshot + dns-sd output in audit-evidence/iphone-2026-05-XX/ | None | Does not block v0.3-internal |
```

When all 5 Android (A.1–A.5) + 4 Android (B.1–B.4) + 10 iPhone (T1.1–T1.10) rows are PASS, the v0.3-internal tag is ready to cut.
