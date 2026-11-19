# Physical testing: practical checklist

Reviewed **2 November 2026**, against main `0efabaaa00186efbaa00eb644b7eb0e97f5edf14`, the open issues and their latest acceptance comments. This is a test plan, not a claim that tests passed.

**Start with section 3 using your Android, iPhone and Mac.** Save the results; report failures immediately. You do not have to finish everything before asking for analysis. Sections marked **Engineer** need prepared test tools; sections marked **Extra equipment** cannot be completed with only your current three devices.

## 1. Choose the correct apps

| Purpose | Use |
| --- | --- |
| RPC, Multi-device and Smart buttons | Your installed lab apps from PR #533. Prepared source: `5683c28cdc0edfed8246b391904a2c0557ec319c`; tree: `5e8335aca5fdb8dcd67ce6665ec25a3cb0d4886c`. [Exact APK, signed iPhone app, framework and Mac hashes](https://github.com/p2pKit/P2pKit/blob/b6d7658f7c9bab4e029804db88e07b4932e5f111/docs/validation/rpc-multi-smart-2026-11-01.md#source-and-products). |
| Core discovery, hotspot, files, lifecycle and network faults | Ordinary P2pKit sample screens, using one agreed source and matching builds on every peer. RPC echo buttons do not test the file-transfer/provisioning APIs. |
| Published rc10 qualification | Separate source: `c22762af6c9a62728528d49ccca1fa4b28089712`. Use the artifacts in the [rc10 release record](../releases/0.8.0-rc10.md). The installed Smart/Multi lab apps do not certify these different bytes. |

Do not install public downloads over the lab apps or clear profiles to prepare this checklist. Preserve saved tests and identities. An engineer should record each actual installed version/hash before testing; if it differs from the table, give it its own results set.

## 2. Platform settings and equipment

### Settings for your current devices

| Platform | Configuration |
| --- | --- |
| All three | Same approved private Wi-Fi, with peer-to-peer traffic and multicast allowed. Use automatic Wi-Fi selection for RPC; no IP typing. Start with VPN and alternate routes off. Use synthetic test files and unique device names. |
| Android | Unlock; keep app visible. Enable USB debugging and approve the selected Mac test connection for installation/evidence. Grant requested Nearby Wi-Fi/Location permissions for the normal baseline. Battery saver off; at least 2 GiB free storage. Record model, Android/API version, app target SDK and charging state. |
| iPhone/iPad | Enable Developer Mode and developer-app trust when required. Enable P2pKit under **Settings → Privacy & Security → Local Network**. Keep app visible/unlocked during workload measurements. Paired wireless development is allowed; USB may be needed for installation/trust. Record model, iOS build and charging state. |
| Mac RPC | Use the prepared Mac launcher. Unlock its existing RPC profile with the profile passphrase, not the Mac password. There is no default passphrase. If unavailable, the prepared `run-desktop.py --new-test-profile` creates a separate profile; choose 12–128 characters in the app and retain that profile for later runs. |
| Mac/Linux/Windows core sample | Unique **Device name**; **App ID** = `p2pkit-desktop-sample` to match Android/iOS. Reconnect enabled: **5 attempts, 1000 ms delay**. Start with Auto-mesh off; test it on separately. Use the real Desktop window. |
| Windows RPC | Use the exact installed MSI and its bundled runtime, in a disposable ordinary-user account; see section 8. Successful development-mode or administrator runs do not qualify this path. |

USB is for control, installation and evidence. **RPC traffic stays on the private Wi-Fi/LAN**, with no USB tunnel or public service exposure. Wall/USB charging is permitted for normal tests; record it separately from discharge tests.

**Build preparation — Engineer, once per source:** JDK 17 and the repository Gradle wrapper; native JDK 21 for the Mac campaign/package; Python 3.12+; full compatible Xcode with existing local signing; XcodeGen; Android platforms `36` and `37.0`, platform-tools and NDK `29.0.14206865`. The formal Mac capacity campaign requires native Apple Silicon. Use [local setup](../testing/local.md#android-sdk-setup) and the [campaign preparation](../rpc/mac-mobile-continuation.md); record exact versions. Reuse unchanged verified products after verified shutdown.

### Equipment needed to close the wider matrix

| Coverage | Additional requirement |
| --- | --- |
| Android/OEM behavior | At least two manufacturers; physical OS bands API 24–25, 29–32, 33–34 and 35+. Two Androids together are needed for the long soak. |
| Apple/AWDL | Two physical Apple devices, preferably iPhone + iPad, two hardware generations; iOS/iPadOS 14, an intermediate release and latest. The UI app may require iOS 15+; an iOS-14-compatible consumer is needed to prove the library floor. |
| Intel Apple runtime | Intel Mac/supported x86_64 iOS Simulator runtime. This is a separate runtime test; neither a physical iPhone nor Rosetta alone replaces it. |
| Network changes/faults | Two AP/router models, two subnets, managed private AP, controlled impairment bridge, packet capture and dedicated Ethernet/USB-Ethernet adapters. |
| Desktop/Windows | Headful macOS, Linux and native AMD64 Windows; supported disposable Windows VM is acceptable for applicable cases. |
| Backup/independent protocol | Device with iCloud Backup and supported backup inspection; authoritative independent-peer test inputs. Details below. |

## 3. RPC tests you can start yourself

### Connect, then run one button at a time

1. Open **Device tests** on both devices. Choose **Host here** on one, **Client here** on the other.
2. On the Client, select the discovered Host. Compare fingerprints; approve the first connection on the Host. Wait for Ready/connected.
3. Press a test on the Client. To press it from the Host instead, enable **Allow selected Host to start tests** on the Client, keep that screen open, then select that Client on the Host.
4. Wait for the saved result before the next Pair test. **Cancel this test** cancels one run; **Cancel all tests** cancels the group; **Stop** closes the role.

**The arrow always means Client → Host.** With Mac Host and Android Client, Android sends the workload requests and Mac replies, even if you press Start on Mac.

Run the four short buttons below in all six directions. Keep both phones connected to Mac Host and select each in turn. Then reverse roles as shown.

| Client → Host | Short suite | Smart | Saved run IDs |
| --- | --- | --- | --- |
| Android → Mac | ☐ | ☐ | |
| iPhone → Mac | ☐ | ☐ | |
| Mac → Android | ☐ | ☐ | |
| iPhone → Android | ☐ | ☐ | |
| Mac → iPhone | ☐ | ☐ | |
| Android → iPhone | ☐ | ☐ | |

| Button, in recommended order | What to check |
| --- | --- |
| **Correctness** | Exact echo/application replies and the expected invalid-input error; no unexpected failure. |
| **Large data** | Three exact replies: 64 KiB, 256 KiB and 1 MiB encoded bodies. Both sides identify the same run. |
| **Cancellation / deadline** | Expected deadline and caller cancellation, followed by a valid successful reply. Deliberate errors are separate from unexpected errors. |
| **Disconnect / reconnect** | Five disconnect/reconnect cycles; rediscover the saved Host identity, then obtain a correct reply. |
| **Smart · find stable load** | Automatic ramp, safety decisions and fresh stable-level confirmation are saved. Inspect throughput, p50/p95/p99, errors, timeouts, missed schedules, concurrency and stop reason. |
| **Steady · 30 minutes** | Optional additional two-device endurance result: one call every 100 ms for 30 measured minutes after initialization. It does **not** replace the four required capacity runs in section 4. |

If a run fails, save its run ID and direction, stop that sequence, and report it. A new attempt gets a new run ID. In Pair mode a busy Host can reject another test; use Multi mode for intentional overlap.

### Multi-device tests

1. Open **Multi-device tests** on the Host and every participating Client; connect and enable each Client's Host-start permission.
2. On the Host, select both other devices and press one phase button. Repeat the short suite and Smart with **Mac Host**, **Android Host**, then **iPhone Host**.
3. Verify simultaneous progress, separate Client results and a shared group ID. Cancel one Client's run: the other must continue. Then check **Cancel all tests** and **Stop** separately.
4. Confirm each Client's output is saved on that device and reported to the Host. A missing Host report remains unconfirmed.

Current limit: **16 distinct trusted Clients**, one active local run per Client. Three devices exercise two simultaneous Clients. These buttons create no extra independent clients and cannot establish 128/256-client capacity.

### Smart Test: how to read the result

It starts at **1 request/s, one worker, 1 KiB echoes**. Default stages are **10 seconds**. It raises rate/concurrency, detects latency/errors/scheduling pressure or throughput plateau, backs off, and freshly confirms a stable level.

Default safety ceilings: **600 seconds, 24 stages, 64 workers, 5000 target requests/s, 512 MiB memory, 512 threads**; p95/p99 limits **1/2 seconds**, errors **1%**, missed schedules **10%**. These are safety bounds, not promised device capacity. A ceiling reached with confirmation gives a **lower bound**; no fresh confirmation means no stable-capacity claim.

Stop reasons include corruption, lost/unresponsive Host, memory pressure, missing/stale required telemetry, serious/critical thermal state and Android battery temperature ≥45°C. Check the generator's resources too: the result measures the whole Client–Host path. Smart reuses the existing connection; its workers drain before saving, while **Stop** closes the role. Do not add independently measured Multi Smart maxima together as Host capacity.

### Monitor and keep results

| Control/measurement | Meaning |
| --- | --- |
| **Live test activity** | Actual procedures, requests, replies/errors and elapsed times seen here. Host handler completion alone does not prove Client receipt. |
| Resource monitor | Available CPU, memory, threads, charging, battery and thermal data. CPU is percentage of one core and may exceed 100%. Mac UI counters are **JVM heap/JVM threads**, not native resident memory/threads. |
| Concurrent Host readings | Runs share the Host process. Their resource summaries overlap; do not sum them. |
| **Clear displayed logs** / **Show saved results** | Hide display / restore recent results; saved archives remain. This applies to the RPC controls, not every core diagnostic clear command. |
| **Delete this output…** | Confirmed deletion of that run on this device only. Do not use it until evidence has been collected and reviewed. |

Each run has its own saved metadata: direction, source, start/end time, initiator, run/group ID, phase, Pair/Multi mode, counts, latency, resource observations and failure/stop reason. The UI keeps the latest **100**; older archives persist. Per-record data is bounded to **64 KiB**, so it is not a complete packet trace. Android/iPhone use private `rpc-test-archive` storage; Mac uses its encrypted profile. There is no archive-export button yet; ask the agent to collect the private archives after testing. Stop/role changes preserve them; uninstall/data/profile deletion can remove them.

**iPhone app switching:** test a brief switch only as a separate lifecycle case. The lab app can retain an ordinary automatic-Wi-Fi role for up to **25 seconds**, subject to earlier OS expiry. Lock, network change or expiry may stop it. A failed/interrupted test is saved; it must not silently restart or become a pass. Keep it foreground for performance measurements.

## 4. Formal phone capacity — #525 — Engineer

Use matching products and `scripts/run-rpc-mac-campaign.py` **prepare → settings → run → analyze**, with **recover** for uncertain cleanup. Discover actual device/interface values; never reuse example IPs or IDs. Keep authentication, encryption, protected identities, admission limits and `host128()` defaults. Do not claim 512 clients.

Run **large, correctness, churn and steady independently for every row**:

| Physical Host | Independent Mac Clients | Measured steady duration | Scheduled steady replies | Result/run ID |
| --- | ---: | ---: | ---: | --- |
| Android | 128 | 1800 s | 2,304,000 | ☐ |
| Android | 256 | 1800 s | 4,608,000 | ☐ |
| iPhone | 128 | 1800 s | 2,304,000 | ☐ |
| iPhone | 256 | 1800 s | 4,608,000 | ☐ |

**Minimum: two hours of measured steady workload**, plus initialization, connected-idle baselines, other phases and cleanup. Schedule the four runs separately to avoid contaminating comparisons.

| Phase | Exact workload/acceptance |
| --- | --- |
| `large` | 20 exact 1 MiB request/reply calls, concurrency 2, on one selected independent client. This phase is not a full-cohort throughput test. |
| `correctness` | Full authenticated cohort; response correlation, business/authorization errors, sent deadlines/cancellation, slow-handler fairness, disconnect/reconnect and surviving cohort. |
| `churn` | Five rounds using original identities; reconnect batches ≤2; correct replies and the full cohort restored afterward. |
| `steady` | Full cohort, 1 KiB at 10 calls/s/client for 1800 measured seconds. Report actual correct replies and missed schedules; no catch-up hiding misses. |

For each phase retain: connection success, response correctness, throughput, p95/p99, errors/timeouts, missed schedules, phone CPU/resident memory/native threads, connected-idle overhead and battery/thermal readings. Measure Mac generator CPU, memory, GC and scheduling separately. Keep initialization and deliberate faults outside steady success totals. Record the maintained **65-second post-client drain**, exact phone Stop/pin retirement, listeners/connections/threads and final resource state.

The owner previously selected a **1 GiB available-memory admission override**; the stock guide defaults to **6 GiB**. Record the actual setting and observed reserve. The override is not evidence that 1 GiB is sufficient or that a generator-limited result measures phone capacity.

### Additional mandatory #525 cases — prepare/review extensions first

| Case | Required evidence |
| --- | --- |
| Mixed 256 Clients | Android Host with **iPhone Client + 255 independent Mac Clients simultaneously**, then iPhone Host with **Android Client + 255 Mac Clients**. A separate phone smoke run does not count. |
| Socket backpressure | A genuine authenticated peer stops/slows reading socket bytes while other Clients run. Prove bounded queues/memory and unaffected peers' progress. A delayed handler does not count. |
| Long mixed faults / fairness | Reviewed coordinated workload combining disconnect/reconnect, cancellation, deadlines, slow readers, authorization/revocation and competing Clients. Predeclare duration, fault schedule and pass limits; record per-peer fairness and deterministic cleanup. The current buttons do not supply this complete test. |
| Authorization/revocation | Reject unknown identity; approve verified identity; revoke during use; verify access ends, stale approvals cannot restore it and explicit reapproval is required. Preserve successful unrelated Clients and admission limits. |
| Real battery discharge | Reviewed unplugged recorder or supported wireless control; record start/end battery, charging state, duration/workload, available current/thermal readings and stop reason. The owner must physically unplug/reconnect when required. Never fake unplugging with simulated battery state. |

Stop safely on serious/critical thermal conditions. Android battery temperature is not CPU temperature; iOS thermal categories are not precise temperatures or calibrated energy. USB or wall charging supplies no discharge evidence. Missing counters remain unavailable. No fixed discharge duration/energy threshold is invented here; freeze it in the reviewed recorder plan.

**Close [#525](https://github.com/p2pKit/P2pKit/issues/525) only after** all four capacity rows, required fault/mixed/battery cases, application role matrix and cleanup evidence pass review. App-button successes alone cannot close it.

## 5. Core LAN, files and lifecycle

### Common procedure and evidence

Use the ordinary sample, same `p2pkit-desktop-sample` App ID. Open Android/Desktop **Diagnostics** or iOS **Test Diagnostics**. Start a diagnostic session with the catalog test ID, the **same session ID on both peers**, and sender/receiver roles. Enable Advertise/Discover; test Auto-mesh off then on where supported.

Core interactive samples use a disclosed permissive authenticated-same-AppId development policy. For identity-pin assertions, use the [verified fingerprint procedure](../guides/samples.md#pairing-with-a-verified-fingerprint) or prepared pinned consumer. Matching names/App ID alone do not authorize a peer. JVM core sample identity changes on kit recreation; re-exchange pairing information.

After each case, end the diagnostic session and **Export Test Evidence** on every peer. Save ZIPs, OS logs, screenshots, file hashes and required packet captures together. Core exports and RPC archives are separate evidence sources.

Run the applicable Android/Apple/hostile cases **three consecutive times per required device/OS/topology**, each with a new session ID. Retain earlier failures. Full coverage includes Android↔Android, Apple↔Apple, Android↔Apple, Android↔JVM and Apple↔JVM, with both initiation/transfer directions, plus three-peer concurrent traffic. Special 6-hour soaks and capacity durations remain explicit below.

### Basic files, permissions and UI — catalog PS-T04/07/08/09, ENV-01/04

| Test | Steps and pass condition |
| --- | --- |
| File sizes/data | Send **0 bytes, 1 byte, 200 KiB, 5 MiB, 49 MiB** both ways; include text, binary, image and Unicode/hostile filenames. iOS offers built-in 200 KiB/5 MiB/49 MiB fixtures; prepare other synthetic fixtures on the sender. Exact length/hash, durable commit then acknowledgement, one final outcome. |
| Consent/cancel | Accept, reject, leave offer pending/expire; cancel while Offered, Accepted and mid-transfer. Rotate Android with picker/offer open; Stop/close during transfer. No auto-accept, lost target, false completion or surviving partial file. |
| Storage faults — Engineer | Concurrent same-name offers, repeated offers, >50 MiB offer, quota/unwritable sink, export failure, controlled source mutation/hash mismatch, interrupted receiver. Existing files must survive; collision names remain distinct; no path escape or partial commit. Use bounded fixtures, not filling the owner's phone. |
| Lost final acknowledgement | Keep both timelines. A receiver may have a valid committed file while sender reports failure; reconcile that state without deleting valid output or converting sender failure into success. |
| Permission recovery | iOS Local Network deny → clear Settings guidance → allow → Stop/Start. Android grant/deny/revoke plus Location off/on. Record prompts and recovery; clean-state tests need a separate prepared test context, preserving current results. |
| Android backup rules — Engineer | On Android 12+, run supported backup/device-transfer controls, inspect package extraction rules and exclusions for credentials/protected data. Retain backup outcome and package/rule evidence; restore original settings. |
| KMP consumer | Android **Run KMP consumer smoke**, with initialization before kit creation; physical Swift consumer linked to the exact XCFramework. Discover/connect/greet, 200 KiB transfer, close/Stop; no missing symbols or leftover listener. Record dependency coordinates and hashes. The unverified local Android smoke is not production pinning. |
| Intel runtime — Extra equipment | On real/supported x86_64 Apple runtime: framework load, committed Start/Stop UI test, JVM connection and 200 KiB transfer where networking supports it. Record actual host/destination architecture. |

### Issue-specific network tests

| Issues / setup | Exactly what to do | Required result/evidence |
| --- | --- | --- |
| [#21](https://github.com/p2pKit/P2pKit/issues/21), [#43](https://github.com/p2pKit/P2pKit/issues/43): Android discovery | Advertise/discover **30 min without connecting**. Repeat with observer backgrounded for the supported interval. Stop/restart advertiser gracefully, then force-stop it. | Active peer stays visible; departed peer is removed. Correlate `serviceRemoved`, `hasInfo`, `hasPeerId`, `leaseActive`, admitted withdrawal, `discovery.peer.lost`, UI and packet TTL. #43 requires an **actual metadata-free removal callback**; if none occurs, that case remains unproven. |
| [#39](https://github.com/p2pKit/P2pKit/issues/39), #21: long soak — Extra Android | **Two Androids + JVM, ≥6 continuous hours; 12 preferred.** First 2 h: no connections. Snapshot at 30 min and hourly. Restart JVM at h2/h4; force-stop/restart one Android at h3/h5, with 20 advertise/discover cycles. Final hour: messages + 5 MiB each direction for every pair; graceful removal; 10 min quiet. | No disappearing live peers, stale-port dial or churn-proportional growth. Final descriptors/sockets ≤ warm baseline +16; PSS ≤ baseline + max(20 MiB, 50% of baseline). Save endpoint, memory/thread/socket counts and captures. Missing required metrics prevent PASS. |
| [#25](https://github.com/p2pKit/P2pKit/issues/25), [#31](https://github.com/p2pKit/P2pKit/issues/31): JVM/macOS/Linux binding | Two real endpoints. While running: Wi-Fi A→B, Wi-Fi→Ethernet, remove/re-add interface. | Explicit multicast bind and TCP egress use the selected LAN; discovery follows new address/port without app restart. Save route/interface/JmDNS logs and packet capture. |
| [#26](https://github.com/p2pKit/P2pKit/issues/26), [#28](https://github.com/p2pKit/P2pKit/issues/28), [#33](https://github.com/p2pKit/P2pKit/issues/33): Android routes | Repeat on normal AP and Android hotspot, IPv4/dual-stack/scoped IPv6 where supported; then with VPN + cellular active, across representative OEMs. Include no-safe-LAN case. | Selected interface, mDNS, outbound SYN and return path agree; no VPN/cellular fallback. Hotspot may report `network=none` but must bind its actual AP address before SYN. No safe route must fail before SYN. Isolation/multicast blocks are recorded failures, not manual-connect discovery passes. |
| [#29](https://github.com/p2pKit/P2pKit/issues/29), [#30](https://github.com/p2pKit/P2pKit/issues/30), [#35](https://github.com/p2pKit/P2pKit/issues/35): Android rebind | **50 Wi-Fi/hotspot toggles**, including bursts around the unchanged **800 ms** debounce; slow AP readiness, bind failure/retry, superseding callback and Stop during close/recreate. Engineer supplies delayed-callback/failure controls. | One live settled generation; old owner closes, bounded retry or typed failure, no process restart needed, no listener leak. Capture callback generations, bind attempts and actual terminal cleanup. |
| [#36](https://github.com/p2pKit/P2pKit/issues/36): Android background | During discovery/handshake/transfer: rotate, background **30 s**, then **10–15 min** screen-off/default OEM policy; lock/unlock; change Wi-Fi/hotspot; force-stop/relaunch. **20 kit Stop/Start** cycles. | Enabled Advertise/Discover intent resumes only after settled background stop; disabled features stay disabled. No stale collectors or pre-crash transfer falsely marked successful. |
| [#23](https://github.com/p2pKit/P2pKit/issues/23), [#27](https://github.com/p2pKit/P2pKit/issues/27), [#37](https://github.com/p2pKit/P2pKit/issues/37), [#38](https://github.com/p2pKit/P2pKit/issues/38): Apple recovery | During discovery/handshake/idle/transfer: peer restart/new port (**20 cycles**), Personal Hotspot off/on + return from Settings, Wi-Fi A/B, infrastructure↔AWDL. Control Center ≥30 s, system dialog/call interruption, supported iPad split-view; background 30 s/5 min, lock 30 s, swipe-kill/relaunch. | Current browser/endpoint generations only; temporary failure until fresh discovery; late old dial cannot remove newer endpoint. One actual rebind per inactive episode; path rebind followed by foreground/active must not duplicate it. Retain ordered lifecycle/path/listener events and old-port closure. |
| [#32](https://github.com/p2pKit/P2pKit/issues/32), [#34](https://github.com/p2pKit/P2pKit/issues/34): AWDL — Extra Apple device | Two physical Apple mobile devices. **Leave Wi-Fi enabled but disconnect both from AP.** Discover, authenticate and transfer both directions. Repeat Personal Hotspot host/client and cellular-disabled variant where OS permits. | Prove actual peer-to-peer path; browser/listener/outbound peer-to-peer enabled and cellular prohibited. Logs/path flags plus captures where available; connection alone is insufficient. Mac JVM is not a substitute for a second native Apple AWDL peer. Unsupported hotspot configuration stays blocked. |
| [#40](https://github.com/p2pKit/P2pKit/issues/40), [#41](https://github.com/p2pKit/P2pKit/issues/41): timing — Engineer | Measure repeated actual TCP success/failure on LAN/hotspot/AWDL: reset vs silent drop, stale peer endpoint, path interruption and Apple write before ready. | Save distributions and native timestamps, not RPC RTT. Current Android/JVM total dial **5 s**, alternate slices **1.5 s**; Apple connect/write-ready **10 s** each. Write-ready timeout → Closed + exactly one native cancel; later write rejects immediately. Keep ceilings unchanged; report whether observations justify them. |
| [#44](https://github.com/p2pKit/P2pKit/issues/44): link-local — Extra equipment | Direct physical Ethernet, **no DHCP**, macOS/Linux first; Android USB-Ethernet where supported. Disable alternate routes. Observe actual `169.254/16` and scoped IPv6 addresses. **Three bidirectional cycles**, 200 KiB + 5 MiB each. | Discovery, authenticated transfer and matching hashes all on the direct interface, with PCAP. Preserve IPv6 zone; unscoped link-local must not dial. Restore DHCP/interfaces afterward. |

Detailed acceptance: [Android handbook](android-physical-device.md), [Apple handbook](apple-physical-awdl.md), [catalog](test-catalog.md).

## 6. OS ownership and hostile-network tests — Engineer

These catalog cases are required for complete physical/platform acceptance even where earlier source-fix issues are closed. Ordinary taps cannot reproduce controlled native callback races.

| Case | Required actions and expected result |
| --- | --- |
| Android provisioning A1 / PS-T01 | Across OS bands: deny/permanent-deny/grant/revoke/system-cancel/user-cancel/timeout/success; API 33+ current-target Nearby Wi-Fi and target-32 legacy Location. Validate WPA2/WPA3 null/empty/non-ASCII passwords and OPEN with empty wrapper **before consent/native registration**, then valid retry. One terminal result; late callbacks cannot resurrect canceled work; failed cleanup retains ownership for retry. |
| Android capability/credentials | API 24–25 unsupported hotspot; API 26+ Ethernet-only device with Wi-Fi service but no hardware feature must refuse native start. Radio off alone is not “unsupported.” Actual secured LocalOnlyHotspot enrollment needs reviewed secure credential handoff: stock UI masks the password. Missing hardware/fixture stays blocked. |
| Android two-manager A2 / PS-T02 | **Same process, same production arbiter**: A owns a joined network; B reaches `onAvailable` and is refused without unbinding A. Both close orders, terminal stale callbacks, successful fresh reacquisition. Two concurrent closes must await the same held native attempt and see its same failure. N1→N2 then delayed N1 loss must preserve N2; available/unavailable race has one winner. Save actual network/manager/attempt attribution. |
| Apple manual-info lifetime | Signed harness races Stop with `getManualConnectionInfo()`, cancels caller separately, then stops owner. No detached work; later calls return ManagerClosed; repeated close safe. Compare identity/port and same-moment `getifaddrs`: only active LAN/AWDL unicast, valid IPv6 zone; exclude loopback/wildcard/cellular/VPN/down interfaces. |
| Hostile network baseline | Two independent real machines, isolated lab, known fixtures, synchronized clocks, packet capture. Three baseline runs, then **three runs per fault profile**, keeping settings/seed fixed. |
| Delay/loss/bandwidth profiles | Separately: **250 ms delay**; **100 ±75 ms jitter + 10% reorder**; loss **1%, 5%, 20%**; **64 kbit/s**, **1 Mbit/s**; **2% duplication**. Combined: **150 ±50 ms, 5% loss, 2% reorder, 1% duplication**. Correct completion or bounded typed failure; no corrupt/partial success or unbounded growth. |
| Disconnect/firewall/router | Interrupt discovery/handshake/idle/49 MiB transfer. Restart same/new identity, move interface/subnet. Block mDNS separately from data, asymmetric return, reset vs silent drop, AP isolation, two router models. Require bounded recovery/refusal on the intended route. |
| Malformed/admission attacks | Reviewed independent generator: wrong App ID/version/security metadata, malformed/missing/oversized TXT, duplicate identity and bounded flood; pre-handshake admission limit +1. No unsafe peer admission; legitimate peer still progresses; resources bounded. Packet duplication is not authenticated-record replay coverage. |
| Desktop/CLI PS-T05/06 | All three desktop OSes, actual windows/terminal. CLI options/invalid inputs/ambiguous peers, EOF/terminal close/signals/crash/blocked network; UI start/stop/toggles, chooser, accept/reject/cancel/storage faults, close while live. Three repeats; **≥1000 terminal messages/transfers or explicitly agreed byte/time budget**. Baseline/mid/end resources; bounded history and complete owned-process cleanup. |

Use [hostile-network procedures](hostile-network.md) and [CLI/Desktop fault procedures](cli-desktop-faults.md). Freeze fault-tool source, commands, seeds, resource limits and expected outcomes first. Resource exhaustion is confined to owned test children/fixtures. PCAP is mandatory for hostile discovery and route/firewall claims. Restore only the test rules and original topology; do not disable the whole firewall.

## 7. Backup and independent interoperability — Extra setup

### [#291](https://github.com/p2pKit/P2pKit/issues/291): actual iOS backup exclusion

1. Use a real device with **iCloud Backup enabled**, exact recorded app build and a unique synthetic received file.
2. Receive/commit it into `Documents/P2pKitInbox`; create a diagnostic export in `Documents/P2pKitEvidence`. Record private filenames/hashes and successful exclusion preparation.
3. Complete an actual backup. Use a supported inspection method that demonstrates whether the received inbox file is in the backup set; check the evidence root too. Keep backup time/device/build and inspection evidence.
4. If restore is needed, use a spare authorized device/test context. Never reset the owner's daily phone for this test.

**Pass:** demonstrable absence from the actual backup set. Exclusion flags, simulator tests, container downloads and iCloud storage totals do not prove this. Finder/local-backup inspection must be labeled as such; do not silently call it iCloud verification. If supported inspection cannot prove the required backup scope, keep the issue open with that blocker.

### [#133](https://github.com/p2pKit/P2pKit/issues/133): independently implemented secure-v2 peer

**Prerequisite:** recover and hash-verify the authoritative frozen independent peer and six-source coordinator, restore qualified execution authority, then run the required compiled-schema checks and bounded positive attempts. The retained C2 natural exit **70** is an unexplained failure. Do not replace missing inputs with an invented peer or relax its envelope. [Exact retained next step](https://github.com/p2pKit/P2pKit/issues/133#issuecomment-5712514067).

Then run **three repeats** in both initiator/responder roles: supported JVM Linux/macOS/Windows, physical Android in two OS bands, native iOS/iPadOS on Wi-Fi/AWDL where the harness supports routing. Check approved/refused fingerprints, text/binary/metadata, 5 MiB file, cancellation, reconnect and close. Retain independent known-answer checks plus malformed/replay/crypto/file-digest/version/App-ID negatives, both transcripts and PCAP. No legacy downgrade.

Android/iPhone/Mac using this same library are useful platform tests but **not independent implementation evidence**. Existing accepted wire goldens/negative controls remain credited. The separate professional cryptographic audit is an external requirement; this checklist does not resume the cancelled audit.

## 8. Windows installed RPC — #462 — Engineer + Windows environment

Productive Windows Host/Client is implemented; **formal installed qualification remains incomplete**. Use a reachable native AMD64 Windows 11/supported VM, actual GUI, a newly initialized **ordinary local user**, local fixed NTFS, protected Program Files install and fresh LocalAppData test profile. No administrator/filtered-admin, service, SYSTEM or daily-user profile. Record exact MSI/source/bundled-runtime/native-module hashes. Packaged JDK 21 and published Java 17 APIs are distinct.

First run one admitted **`ui-host-cycle`**, retaining phase, original failure and complete retirement evidence. Diagnose any recurrence before the required ≥20 accepted cycles. After the account/installation/evidence directory are admitted, the [maintained driver](../../scripts/run-windows-installed-admission.py) accepts:

```powershell
& '<verified absolute python.exe>' -I -B -S .\scripts\run-windows-installed-admission.py `
    --expected-source '<installed app commit>' `
    --private-parent '<existing private evidence directory>' `
    --python '<same verified absolute python.exe>' `
    --operation ui-host-cycle
```

The engineer resolves these placeholders and binds supervisor sources separately. A standalone native smoke payload or hosted administrator check does not supply installed admission. Preserve the original **10/15/5/30-second harness budgets**; 10 seconds was an aggregate UI window, not a separate Back deadline. Whole-application terminal exit is **30 seconds**; ordinary Stop has no invented terminal deadline.

| Case | Execute and verify |
| --- | --- |
| W01 | Real ordinary-user positive token/profile admission; unsafe elevated/filtered-admin/service/impersonation/root cases refuse before payload/profile creation. |
| W02 | Installed launcher/runtime load; writable root, wrong owner/access rules, redirected ancestor, swapped DLL, wrong source/manifest/architecture/ABI/import provider refuse **before candidate DLL/JNI executes**. |
| W03 | Original file identity equals loaded module; actual JNI registration/ABI and every method remain valid through Start/Stop/reopen. No stale address, ambient path substitution or unload behind live calls. |
| W04 | Every numbered native smoke control plus unsafe owner/access rules, reparse, alternate data stream, hardlink, case alias, UNC, delete-pending and impersonation fixtures. Require original-handle containment and no pre-admission secret write. |
| W05 | Competing processes/profile locks; 0/1/262144-byte records and over-limit refusal; create-only, replace, expected-identity delete and flush. Exact exclusive ownership, bytes and atomic visibility. |
| W06 | Encrypted identity/trust survives full cold reopen. Wrong password/corrupt/truncated/missing state refuses without reset. Interrupt each prepare/write/flush/rename/delete/ack phase; preserve uncertain state. Process kill is not power-loss proof. |
| W07 | Cancel before/during/after JNI, interrupt close owner/waiters, inject native/reporting failures. Retain real owner until return; shared close result, no abandoned worker or false cleanup. |
| W08 | Installed main app → RPC → Back; distinct-peer Host/Client; Reject then verified Approve; `users.get(123)`, `items.list(0,20)`, `message.send`, typed invalid/unknown cases. Save both peers' actual responses. |
| W09 | Restart without clearing stores, selected-pin reconnect, Host loss, revoke/forget, stale approvals and observer cancellation. Trust persists appropriately; revoked access ends; no automatic request replay. |
| W10 | **≥20 accepted navigation/Stop/close cycles**, blocked-JNI/interruption and supervisor-failure cases. All owned descendants/jobs/handles/threads/sockets/profile leases retire; parent exit alone is insufficient. |
| W11 | Read back installed bytes/runtime, reconcile every case and retained failure, hash evidence and obtain independent review. |

Complete [#462](https://github.com/p2pKit/P2pKit/issues/462)'s current W01–W11 criteria and [installed-supervisor procedure](../rpc/windows-profile-packaging.md#fixed-windows-supervisor). Historical Back failures remain in the report; later success does not erase them.

## 9. Save one result set per test; close only proven issues

Use a private folder per run:

```text
p2pkit/<tested-source-sha>/<area>/<scenario-id>/<run-id>/
```

Keep **both peers' evidence**, original failures and new reruns separately. A compact record must contain:

| Field | Record |
| --- | --- |
| Identity | Test/issue, run/group/shared session ID, Client→Host or sender→receiver, initiator, UTC start/end. |
| Products | Exact source commit/tree, version, installed artifact SHA-256s, tool/harness versions and hashes. |
| Environment | Model, OS/build, architecture, topology, actual private interface/route, permissions, charging state, relevant settings/fault seed. |
| Measurements | Initialization vs measured duration, scheduled/correct/failed replies, throughput/latency, resources with metric kind, file size/hash where applicable. |
| Decision | Expected vs observed UI/events, PASS/FAIL/BLOCKED/PENDING, reason, cleanup state, evidence file hashes, private location and independent reviewer. |

**PASS** requires every assertion and its evidence. An expected refusal can pass a negative test. Missing equipment/tooling is **BLOCKED**; not run/review incomplete is **PENDING**. An executed case with failed behavior or missing mandatory evidence does not pass. Preserve an original handbook `INCONCLUSIVE` classification for unavailable measurements and explain it in the summary.

- [ ] Every required OS/device/topology/role cell and repetition is accounted for.
- [ ] Required packet captures, both-side results and exact source/artifact bindings are present.
- [ ] Cleanup is verified; failures/unknown ownership were investigated before recovery or reinstall.
- [ ] An independent reviewer accepted the evidence and the issue-specific criteria.
- [ ] Publish only a sanitized summary and hash manifest; retain originals privately. No device serials, keys, passwords, private IPs, personal paths or raw logs on GitHub.

The issue links in sections 4–8 cover **all 25 currently open physical/external-validation issues**. Update each only for its completed criteria; one passing transfer cannot close a broader issue. [#520](https://github.com/p2pKit/P2pKit/issues/520), the intermittent English iOS port-keyboard UI failure, remains **deferred**: later physical observation may help, but a phone pass does not explain or close the retained simulator failure.

When ready, tell the agent: **“Collect my saved RPC tests and core evidence, analyze by direction/test/source, and tell me which issue criteria are complete.”** Include any failures and run IDs you noticed. Full evidence rules: [schema](evidence-schema.md) and [test catalog](test-catalog.md).
