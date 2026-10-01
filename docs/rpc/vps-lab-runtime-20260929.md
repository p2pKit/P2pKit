# Supplemental RPC lab execution — 2026-09-29

## Scope

This is feature-only, source-bound evidence, **not release readiness or capacity
qualification**. The owner authorized the isolated Linux/Intel Mac builds,
tooling downloads, emulator experiments and synthetic test integration. The
existing LAN, authentication, native process-ownership and execution gates were
not weakened. Release Foundation remains **NOT_READY**, with every HOLD intact.

The working branch is `work/rpc-lan-20260927-054728-8b1b11da` in the separate
`/root/projects/p2pkit-feature-prep-20260927-yiDjCB` clone. Fresh main remained
`3bc76f956f8f47447b51a62474fc878b9c43173c`. Instructions and the approved plan
are unchanged. No Foundation/campaign source or other session's work, caches,
keys or evidence was imported. The older [P2P sample runtime record](mac-vps-runtime-20260929.md)
remains bound to its original source; it is not RPC phone-app execution.

## Current October 1 follow-through

- **Latest full Intel result:** [36857338675](https://github.com/p2pKit/P2pKit/actions/runs/36857338675)
  at `4b6d8cbc` passed all 20 required platform tasks, **3,036 JUnit cases**,
  zero failures/errors and the one existing ignored diagnostic. Native LAN
  again passed **202 cases with zero failures**. The remaining Swift readiness
  command exceeded its original 120-second Data Migration bound; it has no
  pending process observation or recorded survivor. The failed command is not
  admitted, and no ordinary Swift runtime case ran. All other 42 commands,
  exact simulator/Terminal cleanup and Bonjour restoration verified. See the
  [source-bound review](qualification-investigation-20260930.md#october-1-full-intel-platform-passes-swift-readiness-still-times-out).

- **Native ARM follow-through:** the [complete original matrix and dedicated
  cleanup passed at `ac4e7335`](qualification-investigation-20260930.md#october-1-complete-native-arm-matrix-and-cleanup-passed),
  but [the later `274f59cc` run failed](qualification-investigation-20260930.md#october-1-arm-follow-through-keeps-new-failures-open)
  one JVM test and finalization of the actual adapter cancellation command.
  Its unclassified Darwin lifetime is not waived. The [fresh full follow-through
  at `991682e1`](#october-1-fresh-complete-native-arm-follow-through-passed)
  passed all **3,036 platform cases**, **128 native controls**, **88 Swift unit /
  six UI cases** and the dedicated **four Native / 28 lifecycle / one actual
  adapter cancellation** gate. All **68 commands** finalized. This independent
  pass does not uniquely explain the earlier intermittent failure.
- **Intel GUI investigation:** [actual CPU observations](qualification-investigation-20260930.md#october-1-intel-native-cpu-follow-through-and-original-full-matrix-selection)
  found whole-host saturation after the attempt but did not establish a unique
  cause across the entire boot. Neither disabling OS services nor extending
  the original readiness bound is authorized by those observations.
- **Native ownership admission:** [125/125 controls on both actual Apple
  architectures](qualification-investigation-20260930.md#october-1-native-admission-verified-on-both-architectures-intel-gui-remains-failed)
  passed at `3d3058af`, including the corrected pending-observation drain.
  This is admission-only evidence, not full Apple product qualification.
- **Original nine Intel Bonjour failures:** the unchanged 203-case LAN inventory
  [passed again on current source `ae9ab3d1`](qualification-investigation-20260930.md#october-1-current-harness-intel-original-profile-passed)
  (202 passed, zero failures, the same one pre-existing ignored diagnostic), with
  all 125 native controls, 26 finalizations and exact simulator/Terminal/Bonjour
  restoration. This is the third recovered original-profile execution. The
  separate Intel runtime diagnostic passed all 124 Android-host cases and
  multicast, but fresh iOS 26.2 GUI readiness and its Terminal Quit completion
  failed; those failures are not erased by this original-profile pass.
- **Same-host JVM capacity:** the earlier full-rate pass at `911e5edf` remains
  preserved. The [latest two-image attempt at `0d42c8ca`](#october-1-capacity-image-attempt-completed-with-two-distinct-failures)
  did not qualify capacity. Ubuntu 24.04 completed all 30 minutes but returned
  **1,891,141 replies / 412,859 pre-invocation permit refusals**, zero timer/worker
  misses or RPC errors; p50/p95/p99 were **503/1,585/2,403 ms**. All **1,193 JVM
  tests**, six correctness cases, **20/20 one-MiB calls**, retention and cleanup
  passed separately. Ubuntu 22.04 stopped at the file-offer error-contract
  assertion before any workload. A [directed fixture regression and correction](#october-1-file-writer-fixture-clock-reproduced-and-corrected)
  now pass locally, including all 861 core JVM cases; the hosted follow-through
  remains pending. There is no completed cross-image capacity comparison. The container remains
  unstable under guest balloon/reclaim, not demonstrated load-generator headroom.
- **Phone handoff:** Android's eight supplemental API-24 controls and both
  debug APKs remain verified. [Fresh native-ARM phone execution](#october-1-fresh-unsigned-iphone-package-independently-verified)
  passed nine XCTest methods and produced an independently checked unsigned
  device app. The [handoff](device-testing-handoff.md) gives exact download IDs,
  source hashes and signing boundaries. Neither package qualifies mobile-host
  capacity. Maintained ART still needs separately approved temporary KVM access.
- **Unchanged scope/HOLDs:** same-host private virtual Ethernet/TCP is not
  physical LAN, cross-device or Android/iPhone hosting capacity. The supplemental
  Mac was deleted. Full Apple/physical/mobile gates and Foundation **NOT_READY**
  remain unchanged. No production/security/architecture gate was relaxed.

The following chronological checkpoints retain failed attempts and their
source-specific status; later verified entries supersede earlier pending text.

## Historical September 30 and early October 1 checkpoint

| Requirement | Verified disposition |
|---|---|
| Original Apple ownership admission | **Resolved**: all 122 controls passed on both required native architectures after process-local audit-session isolation. |
| Dedicated ARM cleanup/cancellation | **Passed at `c22aeebb`**: four exact Native methods plus ABI, 28 Swift lifecycle methods and one actual adapter cancellation case; all 63 commands finalized. |
| Original nine Intel discovery failures | **Resolved at `d6d8a2a1`, run 36805158026 attempt 2**: identical LAN profile now 202 passed / zero failed / one pre-existing ignored diagnostic, with 122 native controls, 26 finalized commands and exact environment restoration. |
| Complete Apple matrix | **Not passed**: the original Intel LAN profile and JVM multicast prerequisite now pass; full Intel/GUI follow-through and the remaining full ARM profile still require independent verification. |
| Direct VPS↔Mac LAN capacity | **Blocked topology**, not silently reclassified as LAN: Mac's active multihoming and provider NAT remain; production admission is unchanged. |
| Same-host 128-client steady workload | Three complete 30-minute attempts, **all failed scheduling acceptance**; instrumented latest: 2,217,973 replies, 83,805 timer-late slots, 2,222 worker-late slots, zero permit rejections/RPC errors. See the [attribution investigation](qualification-investigation-20260930.md). |
| Same-host large-payload workload | **20/20 passed again at `51445086`**, one MiB each way at concurrency two; 65.795-second idle retention and native cleanup verified. |
| Separate real-socket correctness | **All six cases passed again at `51445086`**, including uncertain close outcome, cancellation, timeout and independent-client isolation; 65.153-second retention and native cleanup verified. |

These source-bound results are detailed below. Same-host virtual Ethernet is
not physical-LAN, cross-device or mobile-host qualification. Release Foundation
remains **NOT_READY**, with all existing HOLDs intact.

The subsequent [Bonjour OS-API investigation](qualification-investigation-20260930.md#bonjour-os-api-differential-and-ssh-context-experiment)
verified 28 native host/simulator observations: inline-TXT browsing fails while
basic browsing/separate DNS-SD TXT works, raw multicast fails with EHOSTUNREACH,
and a resolved service target is LocalOnly-shaped `localhost`. These are not
production or LAN passes. Both the authenticated SSH comparison and subsequent
nonroot system-launchd comparison completed without restoring multicast/TXT
discovery. The latter passed 122 native controls, 51 command finalizations and
exact job/plist/simulator cleanup; its original primitive failures remain FAIL.
See the [verified result and next narrow observation](qualification-investigation-20260930.md#verified-launchd-result-and-endpoint-specific-policy-investigation).
The original nine Kotlin cases still need a verified correction; no new capacity
workload or qualification is claimed from the historical failed scheduling runs.
The subsequent [endpoint-specific probe](qualification-investigation-20260930.md#actual-endpoint-specific-denial-and-a-bounded-terminal-comparison)
actually reports macOS **Local Network Denied** for the host's mDNS path. The
simulator's ready UDP path does not explain away its failed multicast send.
All 122 native controls and 53 command finalizations passed; 13 of 30 primitive
observations failed. A strictly owned, nonroot Terminal-context diagnostic is
implemented for the next run, without changing any production/security gate.

The latest [same-context interface/declaration comparison](qualification-investigation-20260930.md#verified-configured-advertising-suppression-and-bounded-same-runner-ab)
now establishes that the hosted Intel system explicitly sets
**`NoMulticastAdvertisements=TRUE`**. Run **36747721136** remains **FAIL**:
122 ownership controls and 63 finalizations passed, but 16 of 38 real OS
observations failed. Selected-interface browse/resolve and inline-TXT callbacks
are missing despite successful registration/raw sends and actually loaded
declarations. The subsequent actual reversible setting write/restoration passed,
but reload failed because the hard-coded launchd service was not found (113).
The corrected service-label/configuration preflight subsequently passed the
same-runner A/B: **38/38 native OS observations passed**, with **122 ownership
controls, 75 finalizations and exact preference/service restoration**. This proves
native Bonjour recovery, not recovery of the original nine Kotlin tests or GUI
readiness. Those product runs and full-rate capacity remain pending; see the
[verified comparison](qualification-investigation-20260930.md#october-1-verified-causal-bonjour-recovery-below-kotlin).

## Actual Android emulator experiments

Both machines **booted an actual Android virtual device and passed a minimal
Activity/instrumentation probe on ART**, not merely an SDK installation check.

| Host | Actual configuration | Minimal probe result |
|---|---|---|
| Linux VPS | Ubuntu 24.04.4, Linux 6.1.72, x86_64; 16 visible CPUs and approximately 31.4 GiB visible RAM | API 24 booted in 119.252 seconds; one Activity/ART probe passed; owned shutdown passed |
| Intel Mac VPS | macOS 26.6.2 / 25G83, Xcode 26.6 / 17F113; 16 logical CPUs, 22,951,231,488 bytes RAM | API 24 booted in 151.317 seconds; one Activity/ART probe passed; owned shutdown passed |

Both used emulator **37.1.11 / build 15917651**, the **API 24 `default/x86_64`
revision 8** image, software acceleration (`-accel off`), one core, 1,536 MiB RAM,
SwiftShader, no snapshots/window/audio/boot animation/metrics, and a 480×800 skin.
The installed app reported ART's `Dalvik` VM name, version 2.1.0, API 24 and
x86_64 through the actual nonce-bound instrumentation result. Fresh AVDs and
private loopback ADB servers were used; no unrelated device/server was adopted.

Linux exposes neither `/dev/kvm` nor VMX/SVM. No readable cgroup quota hierarchy
was exposed to this environment inspection; visible host memory is not proof
of a reserved load-generator allocation. The Mac reports `kern.hv_support=0`.
SIP and Gatekeeper remained enabled. Hardware acceleration is unavailable in
these observed configurations, but the successful software boots disprove the
claim that *every* emulator configuration is impossible.

The API 35 software experiment failed its original **600-second boot bound**,
with guest ANR/watchdog evidence. Failed boot/probe attempts remain retained;
no bound, host security setting or required test assertion was relaxed. No
further unlimited unsupported boot experiments were substituted for testing.
These results do **not** pass the maintained API 37/24/25 ART suite, API 37
LAN-permission gate, physical interoperability or Android hosting capacity.

## RPC phone applications

### iPhone simulator and unsigned device app: passed

Exact source: `b6c5e197a6ff0d4dcb45857245b12a78029ce8f6`.
A September 30 owner-confirmed deletion made the Mac-only unsigned app and
original XCTest bundles unavailable before they could be copied. Earlier
bounded text exports and source remain verified on Linux. The historical
execution below is not a claim that the original app is still available;
rebuilding and owner signing are required for installation.
A fresh candidate passed all **122 native ownership controls**, then
[`run-rpc-phone-ios-controls.py`](../../scripts/run-rpc-phone-ios-controls.py)
completed:

- Actual XcodeGen generation and strict framework/plist path inspection.
- Fresh, source-bound Debug XCFramework production/provenance.
- A new owned iOS **26.5 / 23F77** simulator, within the original 120-second
  readiness bound.
- **All nine exact XCTest methods**: six ownership/cancellation controls, one
  application-hosted real Keychain control, and two UI controls. The actual
  xcresult contained no missing, duplicate, failed or skipped required cases.
- An **unsigned arm64 iPhone `.app`**, with actual binary-architecture and
  minimum-OS inspection. Both Xcode builds ran their mandatory nested native
  provenance verifier through the explicitly pinned Python interpreter.
- Verified exact simulator Shutdown, unchanged source, zero owned survivors
  and no unresolved discovery/finalization errors. Independent reinspection
  matched the original xcresult and unsigned-app manifests.

This is simulator application/lifecycle/Keychain evidence, not hardware-backed
physical-device assurance, network RPC interoperability, the dedicated ARM
cancellation gate, or capacity. The unsigned app is **not an installable iPhone
package** without the owner's development signing and device access. No signing
material, account, provisioning profile or custodian key was accessed.

### Android RPC controls

Exact source: `715680f0a7703185bc8c77b6d218420e6a076327`.
A fresh full-history/no-tags candidate passed all **121 native controls** in
76.304 seconds. With strict unchanged dependency inputs, one producer completed
both `:p2p-sample-android:assembleDebug` and
`:p2p-sample-android:assembleDebugAndroidTest` in **7m45s**, with all 140 actionable
tasks executed. No earlier APK or build cache was substituted.

The actual test APK contained **both required instrumentation runners**. The
supplemental runner then booted a new API-24 software emulator in **115.484
seconds**, installed both APKs, and passed **all eight actual ART controls**:

1. Real non-exportable Android Keystore round trip, atomic close-on-exec
   descriptor observation and directory barrier/regular-file rejection.
2. Separate trust namespaces and the 128-approved-pin limit.
3. Tamper rejection without erasing existing approvals.
4. Authenticated trust-purpose isolation.
5. Real RPC client identity persistence, not-connected/not-sent results,
   unauthorized selection rejection and retained close behavior.
6. Invalid phone-policy/input rejection.
7. Actual foreground debug Activity creation, secure-window flag and destruction.
8. Missing-key failure without silently recreating a key or clearing approvals.

The eight-control result was exact, nonce-bound and complete, with fixture
cleanup passed. Both APKs were uninstalled, the exact owned emulator/ADB server
stopped, the source remained unchanged, and native plus private-namespace
finalization passed with no owned survivors or discovery errors. A separate
native-owned review revalidated all original receipts, actual instrumentation
and binary manifests, and both APK signatures through build-tools 37.0.0.
The main P2P launcher remains present alongside the explicit debug RPC launcher.

The image/emulator/RAM/core/graphics configuration is the same API-24 software
configuration above, with explicitly bounded **2-GiB userdata**. The current app
is minSdk 24 / targetSdk 37 and debug-signed. These eight controls send **no RPC
network traffic** and are not the maintained API-37 permission or API-24/25
repeated-export/JmDNS suite, physical hardware-backed key assurance, phone
interoperability or hosting capacity.

| Produced artifact | Bytes | SHA-256 |
|---|---:|---|
| Debug application APK | 17,750,119 | `17d9362e56142bede85928f7cba4a306cdacec51371a85b12d8b551adf901d31` |
| Android test APK | 107,576 | `4d1475935db3c8333d81aa689af81adb9ac16f3a87d1cd92339ac78f2eec70d3` |


The [foreground phone lab](../../samples/p2p-sample-rpc/phone-ios/README.md)
explains explicit role selection, local enrollment/approval, OS-backed trust,
foreground cleanup and the separate physical-device procedure. Neither phone
application runs the 128-client steady-state experiment merely by launching it.

## Preserved failures and corrections

- Android directory durability initially used unavailable API surface. The
  sample now uses public `Os.open`/`fstat`/`fsync`, validates the actual directory
  identity, and retains atomic Linux `O_CLOEXEC` on API 24 without referencing
  the API-27-only public constant or a racy open-then-fcntl fallback. The real
  API-24 control inspects its own descriptor's kernel flags and rejects a
  regular-file substitution. No trust or durability check was removed.
- The unbundled Native Keychain test received `errSecMissingEntitlement`
  (`-34018`). The required real test now runs in the app-hosted XCTest process,
  in a new synthetic namespace. It was not mocked, skipped or relabeled green.
- Earlier phone builds failed generated framework and plist path resolution.
  Source-relative XcodeGen paths and both generated-project roots are now
  explicit; generated Debug/Release references are checked before expensive
  builds. The mandatory verifier uses the selected absolute Python rather than
  Xcode's modified `PATH`. All 12 offline phone-runner controls passed.
- A fresh Linux ownership admission failed its modeled read-only fixture on
  the supplied filesystem: the new temporary directory and its regular child
  reported different device IDs (23 and 24). A private tmpfs corrected that
  observation, but the first capability-dropped attempt still shared the outer
  PID namespace and could not classify new same-UID processes. Its ten failed
  controls/infrastructure exit 125 remain **FAIL**, not a usable admission.
  The successful configuration used private mount **and PID** namespaces with
  private `/proc`, a 2-GiB temporary tmpfs, and dropped all setup capabilities
  before native execution. It retained the unchanged full 121-control inventory;
  no privileged observer, process-name exception or weakened assertion was used.
- The first Android control attempt stopped before creating an emulator because
  the task SDK lacked `aapt`. Official SDK build-tools **37.0.0** were then
  installed after checking the exact stable Linux publisher package metadata.
  Two earlier installer prechecks also failed before installation: a generic
  report-size limit and then a mistaken 2-GiB limit did not fit the inspected
  2,684,354,560-byte system image. Only the private binary-input hashing was
  corrected, using the exact image sizes. Existing emulator/ADB/image and APK
  hashes were preserved; no test bound or dependency verification was relaxed.
- The next Android attempt rejected the **actual binary test manifest** before
  emulator startup: only the maintained runner was present. The source manifest
  had been merged, not ignored. Inspection of the pinned AGP 9.3.1 merger showed
  that `testInstrumentationRunner` overwrites the **first** instrumentation
  element. Commit `6d05ef5f` explicitly reserves that first entry for the
  unchanged API-37 runner, followed by the supplemental RPC runner; a source
  regression now protects the ordering/default. Both runtime drivers still
  require the exact two-entry inventory from the produced APK. This does not
  select, replace or mark the maintained API-37 test as executed.
- Commit `715680f0` sizes only the newly owned supplemental AVD's userdata to
  **2 GiB** rather than Pixel 2's 10-GiB default. Missing/duplicate configuration
  entries are rejected and two offline controls cover the change. The image,
  runtime assertions, 600-second software boot bound, 90-second instrumentation
  body bound and separate maintained ART configuration are unchanged. This
  bounded fixture is not storage, network or capacity qualification.
- The first complete API-24-corrected dependency writer at `8fc0991f` completed
  `resolveAndLockAll` in **37m49s** (359 actionable tasks), strict metadata checks
  and security-floor checks, but its final independent review failed:
  `no new verified artifacts relative to 8fc0991f...`. The private launcher had
  incorrectly used its source commit as the review base for lock-only changes.
  That entire attempt remains **FAIL** and supplied no imported inputs.

The corrected private launcher reran the **entire unchanged maintained writer**
from the same immutable `8fc0991f` source, comparing publisher metadata against
verified main `3bc76f95` rather than the source commit. It used a new mutable
inner clone, the original 7,200-second complete-writer bound, no copied build
caches, and the verified existing simulator-binding init script. The complete
writer and all **69 exact artifact checksum/publisher provenance reviews** passed;
its exact simulator was Shutdown and native ownership finalized successfully.
An additional source-bound review/export independently checked all **14 locks
and verification metadata**, the original failed receipt and the complete diff.

Only two generated locks changed: the Android debug/lint configurations gained
the already-reviewed `kotlinx-serialization-json-io{,-jvm}:1.11.0` coordinates,
and the RPC sample gained its opt-in `jvmLab` configuration membership. No
versions, checksum entries, trust policy, other locks or Foundation inputs were
changed. All 15 pre-import hashes matched the clean feature source; every final
hash and diff line was checked (allowing only Git's different object-ID
abbreviation lengths). The accepted generated inputs are committed as
`3ada3ea031e48a4b20441d6c0318fa03b04dd4cc`. This review is not a fresh immutable
runtime, supported-host or capacity pass.

## JVM regression and capacity integration

A separate immutable Linux candidate at
`0947f7e0cf1783fffd332e08a7657d4370243153` passed **1,161 JVM tests**:
core 858, LAN 231, RPC 45 and RPC sample 27, with zero failures/errors/skips.
This includes the synthetic fixture/telemetry and shared phone-facade controls;
it is not a throughput measurement or an execution of a later commit.

The opt-in `jvmLab` compilation and
[`run-rpc-capacity-lab.py`](../../scripts/run-rpc-capacity-lab.py) provide the
missing synthetic-only integration: 128 distinct protected identities,
explicit public-pin provisioning, the existing strict organization-LAN
factories, source/artifact binding, host-process telemetry, open-loop scheduling,
latency/error/scheduling counters, post-retention observations and owned cleanup.
It is not a permissive provider in the public library or main sample artifact.
Ten offline capacity-lab controls passed; JVM tests are recorded above.

### Two-machine attempt: blocked before workload

The inspected Linux private `/32` interface routes to the provider gateway.
The Mac's provider-private SSH address reaches a guest behind a different
RFC1918 `/24` NAT/default gateway. The existing connection is a dedicated-key,
pinned-host SSH control channel, **not proof of a directly reachable approved
RPC LAN endpoint**. Bounded direct test-port probes timed out.

The Mac also has four additional up non-loopback `utun` interfaces. An actual
JVM interface observation confirmed them. The existing strict
`organizationJvmTarget` rejects that unverifiable multihomed configuration;
changing which machine is host does not remove the Mac client's same policy.
The September 29 follow-up rechecked the same four up `utun` interfaces, guest
route and private SSH control connection; the prerequisites have not changed.
No interface was disabled, route/firewall widened, authentication bypassed, or
SSH/VPN path silently substituted for LAN acceptance.

The preferred Linux-client/Mac-host startup at `213e51ae` generated **128
distinct synthetic identities**, then failed closed before the workload. Owned
client fixtures and the host vault were removed; source and native cleanup
were verified. This is **not 128 authenticated connections** or a host-load
failure measurement. A compatible, SDK-verifiable approved path is still needed.

**Security decision boundary:** retain the strict profile. The immediate
recommendation is a directly reachable approved LAN host/client environment
whose selected interface the SDK can verify. Supporting this Mac's current
multihoming instead needs a separately reviewed OS-enforced binding/path design;
removing the `utun` rejection or tunneling around it is not an ordinary test fix.

Status **at the initial two-machine attempt**, before the September 30 local
fallback below:

| Requirement | Actual execution/result |
|---|---|
| 128 clients × 10 calls/s × 1,800 seconds; 1 KiB each way | **NOT STARTED** |
| 2,304,000 successful responses; sustained 1,280 calls/s | Not measured |
| Latency, errors, scheduling misses, queues and host CPU/RSS/threads | No workload time series; no pass/fail performance inference |
| Separate 20 × 1 MiB request/reply calls, concurrency two | **NOT STARTED** |

No latency pass/fail threshold was approved; distributions must still be
reported. A future mechanical driver success additionally needs full resource
review and each real JVM/Android/iPhone host's qualification. A simulator or JVM
result cannot establish real Android/iPhone hosting capacity.

### September 30: exact Mac rejection and real same-host fallback

The four active interfaces were investigated rather than assumed to be user
VPNs. Kernel control observations associated `utun0` with `nehelper` and
`utun1`–`utun3` with `identityservicesd`; no configured VPN service appeared in
`scutil --nc list`. Each had only IPv6 link-local addresses and scoped IPv6
default routes. The actual **IPv4** route to the Linux peer selected **en0 and
the provider guest gateway**, not any of those `utun` interfaces. These
observations identify the interface controllers and routing, not the hidden
application purpose or trustworthiness of every tunnel.

A final read-only SSH/interface/route recheck at **04:19:31 UTC on September 30**
still found all four up IPv6-link-local `utun` interfaces, Mac en0 behind the
same guest gateway, and Linux's provider-private gateway route. SIP and
Gatekeeper remained enabled; `kern.hv_support` remained zero. No device, route,
service or security setting was changed. The retained task-private
`mac-final-network-observation.txt` SHA-256 is
`33b865fe0299c7bf9fa794352cf146281ea70b596aeec6e919c2f43ec7fafdfa`.

The precise rejection is the **first multihoming predicate** in
[`organizationJvmTarget`](../../library/p2p-transport-lan/src/jvmMain/kotlin/dev/p2pkit/transport/lan/JvmOrganizationLan.kt):
any additional up non-loopback interface makes admission fail, even when it
currently has only IPv6 link-local addresses. Explicit en0 selection does not
override this predicate. It is not a failure to find en0's private address, a
discovery-name problem, or evidence that IPv4 RPC used a `utun`. Java 17 cannot
portably enforce interface-bound routing; source-address binding alone does
not prove the path. Ignoring current IPv6-only interfaces would change that
production guarantee and its behavior under interface/address changes.

The provider-private SSH address also translates to a different guest subnet:
Linux has a provider `/32` route, while Mac en0 is behind the provider's guest
NAT/default gateway. Direct approved RPC-port probes did not establish
reachability. SSH control connectivity is real, but neither a direct LAN nor
proof that a reverse RPC connection can bind an approved path. Reversing host
and client roles retains the same Mac admission problem. A loopback SSH tunnel
would also fail the existing loopback/self-peer checks and would not establish
direct-LAN acceptance. No tunnel, interface shutdown, firewall change, arbitrary
private-address whitelist or production exception was used.

Two new `JvmOrganizationLanTest` regressions retain rejection of four active
IPv6-link-local-only `utun` interfaces and ensure explicit selection cannot
override virtual, point-to-point, loopback or missing-address rejection. The
initial immutable `e3df87087ce7e069485d230dd84856e6a72f629e` candidate passed
the narrow LAN check and **1,163 JVM tests** (core 858, LAN 233, RPC 45, sample
27; zero failures/errors/skips), after all 121 native admission controls.
This is separate from the actual workload and from later source revisions.

The chosen authorized fallback is **two independent real JVM processes on the
same Linux host**, in separate private network namespaces joined only by a
new virtual Ethernet pair:

```text
128 independent authenticated clients                  one RPC host
192.168.252.2/30 -- private veth rpc-local -- 192.168.252.1/30:28473
```

There is no default route, host bridge, public endpoint or SSH data forwarding.
Native observers and JVMs drop all capabilities before execution. The actual
strict factories, authenticated-v2 encryption, framing, serialization, request
IDs and RPC handlers are used, with distinct protected synthetic identities.
This is **SAME_HOST_VIRTUAL_ETHERNET_NOT_PHYSICAL_LAN_OR_DEVICE_QUALIFICATION**,
not a mock, physical-LAN or cross-device pass. The detailed setup, immutable
product/harness binding, exact commands and cleanup contract are in
[the reproducible same-host guide](same-host-lab.md).

### First full steady workload: completed, failed acceptance

Product source: `e3df87087ce7e069485d230dd84856e6a72f629e`.
Immutable coordinator: `15c498b1b3642ec315f34069c24c4c8d623c9228`.
The workload repeated all 121 native controls in the final namespaces before
releasing either JVM. Its configuration was the original 128 clients, 10 calls
per second per client, **1,800 seconds**, 1-KiB request/reply, bounded eight
outstanding calls per client, and unchanged RPC/drain deadlines. No retry or
unsafe replay was enabled.

| Measurement | Actual result |
|---|---:|
| Scheduling interval | 1,800.000373476 seconds |
| Expected successful replies | 2,304,000 |
| Dispatched / successful | 2,217,986 / 2,217,986 |
| RPC failures / timeouts / retries | 0 / 0 / 0 |
| Missed scheduled sends | **86,014 — FAIL** |
| Response throughput | 1,232.214 responses/second |
| Client end-to-end p50 / p95 / p99 | 13 / 23 / 28 ms bucket upper bounds |
| Maximum client latency | 2,664 ms bucket upper bound |
| Scheduling-delay p50 / p95 / p99 / max | 4 / 14 / 1,262 / 2,653 ms bucket upper bounds |
| Connection changes / outstanding after drain | 0 / 0 |
| Host accepted / completed at final retained sample | 2,217,986 / 2,217,986 |
| Host refused / protocol / connection failures | 0 / 0 / 0 |
| Maximum host sampled queue / running calls | 0 / 97 |
| Maximum host retained records / accounted payload bytes | 75,208 / 31,175,054 |
| Host RSS maximum / final retained sample | 1,433,444,352 / 742,313,984 bytes |
| Host native threads maximum | 214, including setup/closure |
| Host CPU, entire 1,805.983-second sample span | 2,995.9 CPU-seconds; 1.659 core-equivalents average |
| Finalization | Both workers reaped; no native ownership errors/survivors; source/harness unchanged |

The host time series contains **1,745 actual samples**. Client-side ten-second
sampling saw only 209 maximum host threads and a final counter lag of 256
already successful calls; the denser host records above preserve those facts
rather than substituting one sampling series for another. Latency includes the
whole client call path; wire-only and handler-only times were not instrumented.
There is no approved numeric latency pass/fail threshold. The workload fails
the completion/scheduling target regardless of its zero RPC errors.

The initial driver imposed synchronized 128-call bursts on its shared worker
pool, rather than independent phase-spaced clocks. The correction at
`a15aa78fbab6687cc447535daf2782c76f67b38d` isolates only test scheduling, adds
client CPU/GC counters, and requires the final host counters to catch up within
the **original five-second** telemetry deadline. Every client still has 18,000
scheduled calls and the same miss criterion; production transport/RPC is
unchanged. This identifies a load-generator limitation, **not proof that it
explains every measured pause** or that the revised workload will pass.

The first coordinator closed the host before a full idle-retention observation.
Its final pre-close sample still had 70,400 retained records and zero connected,
running, queued or payload-accounted work. Native close passed, but this does
not establish idle retention expiry or a no-leak capacity result. The newer
coordinator explicitly observes **65 seconds of idle host uptime** before normal
close, requires resource accounting to return to zero, and preserves failures.
No forced GC, weakened limit or expanded original execution deadline was used.

The failed attempt, original receipts and time series are retained under
`local-capacity.dLB3px4C/state/work/same-host-steady/` and
`local-capacity.dLB3px4C/state/work/local-steady-{host,client}/` in the September
30 continuation evidence directory. The independently checked aggregate
`initial-steady-reviewed.json` SHA-256 is
`4eeaefaa2cd2cd71a394ce1716957f717c06fe314f21792e19f1e27b3dbcb2d5`.
This first attempt remains failed; subsequent attempts must use fresh paths
and report their own source, full duration, measurements and finalization.

### Revised source admission and separate large-payload workload

A fresh immutable candidate at
`a15aa78fbab6687cc447535daf2782c76f67b38d` passed all **121 native controls**,
the narrow `RpcCapacityDriverTest`, and **1,166 JVM tests**: core 858, LAN 233,
RPC 45 and sample 30, with zero failures/errors/skips. It then produced its own
`prepareRpcCapacityLab` distribution. All commands finalized with unchanged
source, no owned survivors or discovery errors, and successful private-namespace
retirement. These are source-bound regression/build results, not capacity.

One earlier fresh candidate at that same source failed
`test_xcode_provenance_reuse_requires_bound_producer`. Its retained inner receipt
reports `OSError: [Errno 22] Invalid argument`, product exit -15 and final exit
125, but zero discovery errors/survivors; outer cleanup succeeded. The exact
originating syscall is not established. That attempt supplied **no product
admission**, remains failed, and was not overwritten or reclassified by the
later complete 121-control pass. Its admission receipt SHA-256 is
`713cb58247aed43d983b0c3a80bedac6de663446a199ed677bf0b99028d04488`.

The separate **large** workload actually completed on the same-host private
veth topology, using two independent JVM processes, one authenticated client,
and concurrency two. It repeated native admission inside the final namespaces;
the prepared source and JAR hashes were checked again before execution.

| Measurement | Actual result |
|---|---:|
| Requests / successful responses | **20 / 20** |
| Encoded request / response size | **1,048,576 / 1,048,576 bytes** |
| Concurrent calls | 2 |
| Actual workload duration | 1.997503848 seconds |
| Response throughput | 10.012496 responses/second |
| RPC failures / timeouts / retries | 0 / 0 / 0 |
| Client end-to-end p50 / p95 / p99 / max | 152 / 458 / 498 / 498 ms bucket upper bounds |
| Host samples / maximum RSS / maximum native threads | 71 / 328,081,408 bytes / 52 |
| Host CPU over the entire sampled span | 6.26 CPU-seconds over 70.353 seconds, including idle observation |
| Post-retention idle observation | **65,320 ms — PASS** |
| Final connected / running / queued / records / accounted payload bytes | 0 / 0 / 0 / 0 / 0 |
| Finalization | Both workers reaped; native cleanup verified; synthetic vaults removed; source unchanged |

The 20-call percentiles have limited statistical significance. Host sampling
spans startup/workload/idle retention and cannot establish peak-workload CPU
from the span average. These results pass this **local large-payload experiment
only**, not deliberate overload, physical LAN, cross-device or mobile capacity.
There is no independent transport-only or handler-only latency measurement.

Evidence is retained in `scheduled-recheck.RR1263SZ/` beneath the September 30
continuation directory. The original `state/work/same-host-large/` coordinator
and native receipts, both `state/work/local-large-{host,client}/` control areas,
complete time series and exact immutable distribution remain source-bound.
The independently reviewed aggregate `revised-large-reviewed.json` SHA-256 is
`9ab6eac0a0e50aabb5cffcf4ac54b8faef349b602afb429f09a5cec428595189`.

| Same-source successful receipt | SHA-256 |
|---|---|
| Build native admission | `c6ea9736f4bfa6c264e73de73a9f34e819606c257c5799313f7f312ee6ae2691` |
| Narrow driver regression | `81fa9d9bbdada5216ecc03474d499d20922e76649b263a84b3761b2c634254e0` |
| Four-module JVM regression | `1608592a8c5e83cf27809ed45ebb005fe361dd740f8f755853400a5e86f84a6d` |
| Prepared lab distribution | `0d8b9e6a66f1add481f2764e50335d6f6f026443f76b9c3757d0ed37b6d7dcf7` |
| Large workload's repeated native admission | `64f1b767479ff497468a40928a1eddbd347ab2f55421041f1d145dd9b7dc621e` |

### Revised full steady workload: completed, still failed acceptance

The independently scheduled `a15aa78f` workload actually ran for the full
**1,800.000275335 seconds**, with the original payloads, client count, per-client
frequency, outstanding limit, call deadlines and missed-clock criterion.
It did not run alongside another build initiated by this continuation. The
same-host topology, strict LAN/authentication factories and default JVM GC/heap
configuration were unchanged. A separate correctness build waited until both
workers and native ownership finalized.

| Measurement | Actual result |
|---|---:|
| Expected responses | 2,304,000 |
| Dispatched / successful responses | **2,234,462 / 2,234,462** |
| Missed scheduled sends | **69,538 — FAIL** |
| RPC failures / timeouts / retries | 0 / 0 / 0 |
| Response throughput | 1,241.367588 responses/second |
| Client end-to-end p50 / p95 / p99 / max | 2 / 2 / 5 / 2,758 ms bucket upper bounds |
| Scheduling-delay p50 / p95 / p99 / max | 1 / 2 / 1,340 / 2,744 ms bucket upper bounds |
| Connection changes / invalid host samples / outstanding after drain | 0 / 0 / 0 |
| Host accepted / completed, independently retained final counters | 2,234,462 / 2,234,462 |
| Host refused / protocol / connection failures | 0 / 0 / 0 |
| Host samples / maximum queue / maximum running calls | 1,822 / 0 / 10 |
| Maximum retained records / accounted payload bytes | 76,901 / 29,987,680 |
| Host RSS maximum / final idle sample | 872,218,624 / 860,225,536 bytes |
| Maximum host native threads, including setup/closure | 215 |
| Host CPU during driver-observed steady span | 3,279.98 CPU-seconds over 1,800.524 seconds |
| Host CPU over complete sampled span, including setup/idle | 3,293.73 CPU-seconds; 1.757924 core-equivalents average |
| Driver CPU / GC collections / JVM-reported GC time | 4,151.83 CPU-seconds / 1,998 / 18,071 ms |
| Post-retention observation | **65,068 ms — PASS** |
| Final connected / running / queued / records / accounted payload bytes | 0 / 0 / 0 / 0 / 0 |
| Finalization | Both workers reaped; zero native discovery errors/survivors; source/harness unchanged |

The client-side ten-second series has 181 admitted host samples; its largest
observed host RSS/threads were 845,045,760 bytes / 206. The denser host-side
series above includes setup, shutdown and idle samples rather than silently
substituting the sparser values. Five-minute host RSS maxima were approximately
818, 826, 834, 837, 845 and 839 million bytes; queue samples stayed zero and
record retention remained bounded. After the unchanged retention window, SDK
accounting returned to zero and native close passed. RSS was not forced back
to startup levels; these observations are not a universal no-leak guarantee.

The scheduling correction did **not** close the throughput gate. Significant
multi-second scheduling/host-sampling gaps remain, including recurring gaps
near minute boundaries. Some ten-second driver intervals correlate reduced
completion counts with 1.25–1.99 seconds of JVM-reported GC time, while other
reduced-completion intervals do not. Cumulative GC time is neither a maximum
pause measurement nor proof that GC explains every miss. No production RPC
failure, overload, retry or increasing SDK queue was observed, but it would
still be incorrect to claim the host met the unoffered workload.

A separately recorded **mid-run guest-aggregate** observation covers 223 samples
over 1,110.270 seconds, not the full experiment. Visible available memory varied
from about 1,603 to 21,405 MiB and one-minute load reached 18.44. This is not
process attribution or proof of reserved CPU/memory; no unrelated process was
inspected, stopped or reorganized. Its five-second observer itself had no
interval exceeding 5.024 seconds, so a whole-VM pause was **not established**.
The exact cause of the remaining JVM/scheduling stalls is unresolved. Neither
a new GC policy, relaxed miss threshold, larger budget nor a shortened workload
was substituted to manufacture a pass. Further performance attribution and a
successful complete rerun remain necessary; all independent correctness and
Apple work continued.

The overall coordinator returned **125/FAIL** because the client measurement
failed; the client worker returned 1 and the host returned 0. This is not an
unresolved native cleanup failure: every original worker receipt was separately
validated, with successful stop, no discovery errors/survivors, and successful
65-second retention review. Original evidence remains in
`scheduled-recheck.RR1263SZ/state/work/same-host-steady/` and
`state/work/local-steady-{host,client}/` under the continuation evidence root.

| Reviewed evidence | SHA-256 |
|---|---|
| Aggregate `revised-steady-reviewed.json` | `ce8327292ad2a17432f0caf3397afcbf104840ce5b215e584cbf06385f6f506e` |
| Repeated runtime native admission | `1032ba1bca48b0fb777f13253fb4509d9192e438b8bb29675d0c7ed56a3d22b0` |
| Client worker receipt, failed measurement / verified cleanup | `02fe9a44730f0775560e03a004eb3b5b7093825247865e513ebb9a88ea9a2c1d` |
| Host worker receipt | `8504fa5e42457310564d21860b4ddbb2352945503a9d57626753d01ad658f0ac` |
| Mid-run guest-only telemetry | `497759988f23a90d665a7bacc9fc41ac522d868134736313dc3ddba07e1d3e20` |

### Separate real-socket correctness and call-admission contract

The opt-in `correctness` mode adds two independent authenticated clients and
a separate real `RpcHost` on the same private veth topology. It uses production
identity, encryption, framing, typed JSON, request correlation and lifecycle
paths, not an in-memory replacement transport. Its fixed synthetic procedures
exist only in `jvmLab`, never on the ordinary capacity host or in public library
artifacts. The [same-host guide](same-host-lab.md#separate-real-socket-correctness-mode)
describes the exact six-case inventory and its deliberately limited scope.

The initial `ab55ff1cfcb75ffe93d9c9f65550b8a6da9b4979` candidate passed all
121 native controls, the narrow lab inventory tests and **1,168 JVM tests**,
then produced its own distribution. Its actual real-socket invocation passed
the first five cases but **failed `close-during-call`**. The client returned
one; the coordinator returned 125. Native finalization and a **65,285-ms** idle
retention observation still passed, with zero remaining SDK accounting.
The original log identifies the case but contains no raw assertion location.
That failed run remains failed, with reviewed aggregate
`initial-correctness-reviewed.json`, SHA-256
`5f56ba2a759433263c89e402e41ef45e59686a3827220e32ec576f406df17dc2`.

Source inspection found an incorrect **new test assumption**, not a reason to
change production lifecycle behavior: the fixture demanded `Closed` as the
new call's failure kind. `RpcClient.close()` permanently closes the engine and
removes its selected attachment. The existing `RpcClientEngine.call()` then
rejects the call as `NotConnected` / `Admission` / `NotSent`, before allocating
an ID or encoding. The retained **connection state** is `Closed`; attempting to
reattach the permanently closed engine is separately rejected as `Closed`.
Changing production error semantics or accepting any error would be unnecessary.

Commit `481bf7721e7525247d49555c42967435c7cc0015` corrects that exact fixture
expectation and additionally requires `Closed` state, admission phase and no
allocated request ID. A new `RpcClosedClientTest` deterministically exercises
unchanged production call admission, retained close and denied reattachment;
fixed step/enum/boolean diagnostics reveal no exception text, pins, IDs or
payloads. The sent call must still report `UnknownOutcome` / `MayHaveExecuted`,
the remote handler must really retire, and the independent observer must remain
usable. No assertion became a warning, deadline was extended, or production
RPC/LAN/ownership code changed.

A new immutable candidate passed fresh **121-control** native admission, the
one-case close-admission regression, both lab-inventory cases, then all
**1,169 JVM tests**: core 858, LAN 233, RPC 46 and sample 32, with zero
failures/errors/skips across 151 suites. It rebuilt its own source-bound lab
distribution. Every receipt, original retained XML, JAR binding, unchanged
source and final private-tmp unmount was independently verified.

The actual Gradle task sequence, through the unchanged bounded native executor,
was:

```text
:p2p-rpc:jvmTest --tests dev.p2pkit.rpc.internal.RpcClosedClientTest
:p2p-sample-rpc:jvmTest --tests dev.p2pkit.sample.rpc.LabRpcChecksTest
:p2p-core:jvmTest :p2p-transport-lan:jvmTest :p2p-rpc:jvmTest :p2p-sample-rpc:jvmTest
:p2p-sample-rpc:prepareRpcCapacityLab
```

The producer used the original strict dependency/resource/rerun policy and
same-home stop. Its exact launcher is retained in
`closed-call-recheck.g2uZTe0Q/run-build.sh` under the continuation evidence root;
the independent `closed-call-build-review.json` retains all source/count/receipt
bindings. This JVM-only regression does not add a case to the earlier ARM run.

| Successful build receipt at `481bf772` | SHA-256 |
|---|---|
| Native admission | `ecbb0984fc3c23a096a6577cd8142703dfe8c652e6ded7cf01faca3666458716` |
| Closed-call contract regression | `a25df603476d6b4f414a0eef3dd9fbbcfb4464cc2550a7ff3f799766ae678dcb` |
| Narrow lab inventory regression | `8c8857fb63ec958194be27f37623e03c4c63bb56b9d03f86d902a314d00d69b9` |
| Complete four-module JVM regression | `e7439f74780444a00cc726c15e0fc804ad666d4cbee1fa38ba786bc3f2eccc97` |
| Fresh prepared lab distribution | `f7520906da8c83a8e835c857cfdb82b2986be1ff9bd99c86419fe7ba254a951a` |

The corrected **actual socket execution** then repeated all 121 native controls
inside the final namespaces and passed all six exact cases. Its own output
observed `state=Closed; kind=NotConnected; evidence=NotSent;
requestIdAllocated=false`. Both the original failed case and this corrected
result remain source-bound; no production behavior was changed to get green.

| Corrected local experiment | Actual result |
|---|---|
| Required cases | **6/6 passed**, exact inventory, none skipped |
| Independent connected identities | 2; separate real client instances and host process |
| Client launcher interval | 19.258 seconds, including local client setup/cleanup; not per-call latency |
| Coordinator interval | 90.205 seconds including provisioning/idle review; excludes native admission |
| Host samples / maximum RSS / maximum native threads | 81 / 184,938,496 bytes / 53 |
| Host CPU over the complete sampled span | 6.36 CPU-seconds over 82.596 seconds, including idle observation |
| Host accepted / completed | 430 / 430, including RPC state probes, not 430 success payloads or a capacity rate |
| Host refusal / protocol failures / connection failures | 1 deliberately unauthorized procedure / 0 / 0 |
| Idle-retention observation | **65,503 ms — PASS** |
| Final connected / running / queued / records / accounted payload bytes | 0 / 0 / 0 / 0 / 0 |
| Worker / coordinator exits | Client 0, host 0, coordinator 0; both workers reaped |
| Finalization | Source/JAR/harness unchanged; fixtures removed; zero ownership errors/survivors |

Application errors, sent deadlines, caller cancellation and uncertain sent
outcomes are **expected assertions** here, not silently counted as successful
business operations. The cooperative waiting handler has no side effects;
these controls do not promise rollback or termination of non-cooperative work.
The test does not measure transport-only/handler-only timing or replace the
separate steady/large latency histograms. It supplies real local transport
correctness evidence, not physical LAN, mobile or throughput qualification.

The exact execution, with `SOURCE`/`STATE` set to the above immutable candidate
and its admitted state, was:

```bash
cd "$SOURCE"
unshare --mount --pid --fork --mount-proc --propagation private --net -- \
  python3 scripts/run-rpc-same-host-lab.py \
  --owner-authorized-same-host --state "$STATE" --mode correctness
```

Both runtime processes selected the installed Ubuntu JDK 17; the final
read-only release-file inspection reports **17.0.20+8-1-24.04-Ubuntu**. Build
daemon tooling is **21.0.12+8-1-24.04-Ubuntu**, with the repository's pinned
Gradle 9.7.0 / Kotlin 2.4.10 inputs. Linux remains x86_64 Ubuntu 24.04.4 / kernel
6.1.72. This is the same private no-egress veth fixture described above, not an
SSH tunnel or access through Mac en0.

The independent review revalidated every original receipt, the exact six-case
record, prepared JARs, all host samples and retention/finalization results.
The coordinator's pending-review label alone was **not** treated as a pass.
Actual paths are `closed-call-recheck.g2uZTe0Q/state/work/same-host-correctness/`
and `state/work/local-correctness-{host,client}/` under the continuation root.

| Reviewed correctness evidence | SHA-256 |
|---|---|
| `closed-call-build-review.json` | `6b8387ba3db3e93f8fce923bbbd081691eea0f3fd0d6bec8a9c39a92c60103e3` |
| `closed-call-correctness-reviewed.json` | `685715b21035e092ef6b89da98ef97693333645f3ca8415ed15e3bc65f887dca` |
| Repeated runtime native admission | `238f4137de99aa27d796c82d349b7979f7244b7bf9b4a40da698320604707c85` |
| Client worker receipt | `385597fd08c936d8d7dc4ca17a77fcd887b500ad507572faddffd6e436c9dbc8` |
| Host worker receipt | `9c2dbf27b4ddbd240805e2584b9009080efd1f765089c8fca867b818db7a4ee9` |

## Evidence and remaining gates

Private evidence is retained under `.git/rpc-lab-validation-20260929.pYFvtw/`
in the isolated clone; actual xcresult/app bundles remain in the corresponding
owned Mac phone context. Failed attempts, logs, immutable source bindings,
configuration, manifests and native receipts were preserved. Only finalized,
independently inspected outcomes above are reported as passes. Disk recovery
retired only exact completed task-private Gradle/Native caches after exclusive
lease and receipt checks; source, artifacts and evidence were retained and
rechecked. Retired contexts were not reused for product execution; unrelated
sessions were not cleaned.

| Evidence | SHA-256 |
|---|---|
| JVM regression receipt, `0947f7e0` | `59139053c9b88ba324bf670cf2d1d67756e3996cec84326c075ffb5aa12bfeac` |
| Failed writer's successful finalization, `8fc0991f` | `97d32c08ef11d125176606255e2afb899afae98aa0599b960689a35158268bda` |
| iPhone phone-controls receipt, `b6c5e197` | `b9c4ea34b65f99fd16b69514836d88a92af86d427d8fdde22ca6e547e3b3e366` |
| Independently reviewed phone text archive | `af094720c7ad10b08a4b16a4b6aff3832ed6a1b959298bc96cae03e31dc49643` |
| Independent phone-review/export receipt | `612b6606cff2560d8bdca6bff4cdcaf1d0d5eced1d9c6d29d26d5c9f4d255177` |
| Complete successful writer receipt, `8fc0991f` | `51820f5a39e1682b3cf8ec86069d2dce391e9d90b3a8a844524d512c8d28a2b1` |
| Independent writer-review/export receipt | `4d91c6594fadc2ccc3dcb84cf8da3e94f8c8950ac4ec98ff4ec0729f53e95545` |
| Independently reviewed complete-writer archive | `19b59bc00c42d6ebeff755f7a5f7d366166c4ee92ec65b57bef7c7657a51a977` |
| Fresh Android native-admission receipt, `715680f0` | `1b14ab60ae5be106bb7fdea00dfb78fd2cbfe0f4f3aa1c892e797be896f235bc` |
| Same-source two-APK producer receipt | `6c7024ed5e8c448345e2a60d481f96df5ea6e555d27558b60f3edcc851ca0a72` |
| Eight actual Android-controls receipt | `5e9335d196fd8e37847697ef3e64d7ee16246067c283c39cb094ff82aec07b6e` |
| Independent Android artifact/runtime review receipt | `a29fa5362c8fe16ce07335f8f9b184904ed86363e3d7dc9ffa82b02b2ae820c2` |
| Android scenario result | `af5eb2486e5576a44a7cceffcc58a7a522d712bbee56ff3aa8158b1bdd8562dd` |

The corresponding failed Android admissions/attempts remain separate:

| Failed attempt (no control pass inferred) | Receipt SHA-256 |
|---|---|
| Ordinary-filesystem native admission | `25d80328a0ea950474ef08f5f2ac13d4387205b0c464da8261ed9b61e5ad6f6b` |
| Tmpfs-only/shared-PID native admission | `e1919bb3951d162b982b527aa012e576feb4c898bfa4d2c2d300b25e63960a3d` |
| Missing SDK build-tools, before emulator startup | `1ba694e7473e4b50a013b39ef3a603135edab9eff365fe92c4fbc2370d9870d0` |
| Actual test-manifest rejection, before emulator startup | `0e1c9e8e0ec01dd0b52559d5a9986796bcc4994874cd8fb329a1dda04a3518f6` |

Reproducible source and private artifacts:

- Android immutable candidate: `.git/rpc-lab-validation-20260929.pYFvtw/phone-android-manifest.c4wzYZ/`.
  Its `source/` contains the committed runner and both APKs under the normal
  `samples/p2p-sample-android/build/outputs/apk/{debug,androidTest/debug}/` paths.
  `results/`, `state/work/rpc-phone-api24-controls/`,
  `state/work/rpc-phone-android-review/` and the namespace-finalization records
  retain source/tool/configuration bindings, command logs and exact results.
- The task-private `run-phone-android-manifest.sh` and `lab-execute.py` retain the
  actual namespace setup and commands. The source-controlled
  [`run-rpc-android-controls.py`](../../scripts/run-rpc-android-controls.py)
  requires the finalized two-task producer, selected installed SDK and a new
  direct child of the native context's `work/` directory. Authorization and the
  complete native admission precede product execution; mounting temporary
  storage alone is not an ownership admission.
- Reviewed iPhone text/manifest export:
  `.git/rpc-lab-validation-20260929.pYFvtw/phone-controls-success-reviewed.RdOAyt/`.
  The unsigned device bundle remains on the Mac in the owned
  `rpc-phone-controls-plist-20260929.MCArMu/state/work/rpc-phone-ios-controls/device-derived/Build/Products/Debug-iphoneos/p2pkit-rpc-phone.app`
  context beneath `/Users/oblien/p2pkit-rpc-supplemental-20260927.nApnIS/`.
- Complete reviewed writer export:
  `.git/rpc-lab-validation-20260929.pYFvtw/complete-phone-writer-reviewed.ltp22f/`.
  Both prior export archives and all **64 phone / 70 writer** manifest-listed
  files were rehashed after the final Android source changes; they matched.
- At `715680f0`, all 21 ART-driver, seven supplemental Android-result/config,
  12 phone-runner, ten capacity-lab, 27 qualification and 22 hosted-driver
  offline controls passed, plus seven source-policy negatives. Repository
  layout, OSV coverage, Markdown links, release/dependency policy and protected
  instruction/plan hashes also passed. These offline checks are not additional
  runtime tests or performance evidence.

At the original September 29 checkpoint, the following remained unqualified
(the source-bound September 30 follow-through below supersedes prerequisite
status only where an actual result is recorded):

1. Maintained Android ART/API-37 permission and API-24/25 compatibility gates.
   The latest [hosted Android run](https://github.com/p2pKit/P2pKit/actions/runs/36399194444)
   passed native admission but lacked authorized existing KVM access. No device
   ACL, mode or security policy was changed or restoration sentinel fabricated.
2. Apple Silicon/macOS 26/Xcode 26.5 and true Intel/macOS 15/Xcode 26.3, plus
   the dedicated ARM cancellation/cleanup follow-through. The available VPS is
   a different matrix cell. The latest [Apple admission run](https://github.com/p2pKit/P2pKit/actions/runs/36402025957)
   failed with 16/17 unresolved Darwin lifetimes; no unchanged blind rerun,
   process-name whitelist, privileged observer or weakened ownership rule was used.
3. Real Android/iPhone installation and host interoperability, LAN permissions,
   network changes/Internet-disconnected operation, hostile-network/security and
   all three actual host platforms' capacity/large-payload requirements.

No new hosted execution was initiated in that September 29 continuation. Historical CI links
above remain failed prerequisite evidence, not runs of the latest phone source.
No merge, release tag, external publication or repository/environment setting
change occurred. The [qualification contract](qualification.md) and all six
existing [external validation areas](../validation/README.md) remain unchanged.

## September 30 continuation: Apple process-admission isolation

The complete available log ZIP and both digest-verified artifacts of
[failed run 36402025957](https://github.com/p2pKit/P2pKit/actions/runs/36402025957)
were inspected again. The first failed **prerequisite** in each job is
`native-controls`: the product returns 1 and the enclosing executor returns 125
because pre-stop/final drain cannot classify 16 ARM / 17 Intel live lifetimes.
No Kotlin/Native, Swift, RPC or ARM cancellation product test ran. The first
listed failing fixture is a cleanup-failure retention control on each lane;
additional unrelated fixture methods also fail. This is not evidence of a
Kotlin resource-registration or cross-thread-close defect.

The trace is `Qualification.native_controls` → `run-audit-command` →
`DarwinScope.discover` → `_ownership_proof` → `_parent_proof`. Missing inherited
domain/pipe proof plus an unobserved non-reaper original parent cannot establish
ownership. A matching or unassigned audit session cannot establish nonownership
either. `DarwinScope.drain` correctly refuses successful cleanup while those
lifetimes remain unresolved. Transient environment/Mach observations were
reconciled in the original aggregate records; they do not erase this ambiguity.
The historical workflow intentionally exported no raw fixture tracebacks,
process names or session IDs. Those unavailable details cannot now establish
which exact OS service or fixture originated each lifetime; no such attribution
is claimed from the sanitized artifacts.

The selected environment-level remedy is a **fresh kernel audit session for the
test invocation**, before any observer exists. It provides a distinguishable
session boundary without changing `audit_processes.py`, signaling authority,
fixture assertions, deadlines or production RPC/LAN rules. See
[the bootstrap contract](../testing/darwin-process-ownership.md#explicit-lab-audit-session-isolation).
Only session allocation uses existing setup privilege; audit masks/identity/
terminal/flags are checked unchanged, then original account credentials are
permanently restored before any observer, evidence writer or test executes.
All original same-session missing-proof and stale-token negative controls remain.

Alternatives considered: accepting launchd parentage or missing markers is
unsafe; longer timeouts cannot prove ancestry; privileged observation broadens
authority; removing matrix cells or using Intel instead of ARM supplies no ARM
evidence. A public `SessionCreate(0, ...)` probe in an ordinary disposable Mac
process returned **100001**, without changing its session. The narrowly scoped
kernel allocation succeeded. An initial diagnostic comparison after dropping
privilege saw different audit masks because Darwin deliberately redacts those
fields for non-root callers; SDK/XNU inspection confirmed this. The maintained
bootstrap compares the actual masks **before** dropping privilege and verifies
the assigned session again afterwards. It does not change mask policy.

At source `d822ee9744664d972bcceeec00b9f9ec19501c34`, all **11 bootstrap policy
controls** and **28 qualification-driver controls** passed on Linux. A fresh
full-history/no-tags Mac candidate then ran the unchanged **122 native controls
in 171.125 seconds**, with product/stop exit zero, unchanged source, no discovery
errors or owned survivors, and independently checked finalization. Its receipt
SHA-256 is `5972c9c4498f7a3d5ed3dd8e27b88da652054a37d68704c9b938978ef33dcf87`.
The bootstrap record confirms a fresh assigned session, preserved audit policy,
restored credentials and inability to regain root. This is the supplemental
Intel/macOS-26.6.2 VPS, **not** either required hosted matrix result. The next
request is Apple-only native admission with the fix, not an unchanged rerun or
a claim that product/capacity gates passed.

Fresh continuation evidence is retained in
`.git/rpc-apple-local-20260930.52SVVqPK/` in the isolated clone; the immutable Mac
candidate is the task-owned `rpc-session-20260930.uOhk3n3r/` directory beneath
the existing supplemental task area. Failed public-API/bootstrap diagnostic
probes and the original hosted failure remain recorded. Foundation is still
**NOT_READY**, with every release and external-validation HOLD preserved.

### Required hosted admission: verified recovery

[Run 36657649113](https://github.com/p2pKit/P2pKit/actions/runs/36657649113),
source `43cdfc6a65eff05f56d980436db0fa5afeb31f25`, completed both **native
admission-only** jobs successfully. Each actual ARM64/macOS-26 and
Intel/macOS-15 runner executed all **122 unchanged native controls**, with zero
failed controls, unresolved lifetimes, discovery errors or owned survivors.
Product and same-home stop exits were zero, source was unchanged, and the
collector independently verified finalization. Transient Darwin observations
resolved as absent/recovered; no failed assertion was ignored. Both complete
job logs and digest-verified sanitized artifacts were retained under
`actions-36657649113/` in the continuation evidence directory.

| Original GitHub artifact ZIP | SHA-256 |
|---|---|
| ARM64 admission | `0c0fe67b4c70a47ffa36c0591faeadec62ffec15e7c732e9a64be63752877d8b` |
| Intel admission | `955eafd7bc09163f5124b64089cf4174b6d0f50d65697bcf9dfccf5f071288ec` |

This resolves the **ownership-admission prerequisite**, not the Apple product
matrix, native cancellation, physical LAN or capacity requirements. Neither job
started product tests. The old failed run remains failed evidence.

The feature-only qualification driver now additionally schedules the maintained
dedicated ARM follow-through: four project controls, four exact native
`IosOwnedFlowCollectionTest` methods **plus aggregate LAN ABI**, the 28 exact
Swift ownership/lifecycle methods, and the one actual production-adapter
`SwiftOwnedFlowCancellationTests` case. It reuses the maintained assessors and
scoped XCTest actions without invoking or changing the campaign workflow.
Every scoped phase retires only the job's newly created simulator; cancellation
success still requires the actual passing case, not simulator shutdown. Failed
retirement blocks subsequent execution, whereas a finalized ordinary assertion
failure remains failed without erasing independent evidence. Ordinary full
Apple tests and both required matrix cells remain mandatory. All **35
qualification-driver and 11 session-bootstrap offline controls** passed before
requesting the full Apple-only run. Native ARM execution of the new follow-through
is still pending at this checkpoint.

### Subsequent Intel prerequisite failure: not reclassified as a pass

The full Apple-only request at `0260eed45c245ef7e630d53c93432e96b4b93ae9`
started [run 36658403670](https://github.com/p2pKit/P2pKit/actions/runs/36658403670).
Its Intel lane subsequently failed **one** native control:
`test_actual_consumer_caller_with_real_executor_retains_external_report_and_receipts`.
Unlike the original admission failure, the enclosing receipt has **zero pending
lifetimes, discovery errors and owned survivors**, unchanged source and stop
exit zero. The fixture product exit is one; zero native/product counts are
admitted. This failed attempt remains failed. The independently running ARM
lane was not cancelled or treated as an Intel substitute.

A single targeted execution of the unchanged consumer fixture on the admitted
Intel/macOS-26 VPS passed in **16.210 seconds**, with verified cleanup and receipt
`8e466f225b2ee42d238479eabca862198011f03d63e0525adecc95cbd0cac328` at source
`d822ee9744664d972bcceeec00b9f9ec19501c34`. This is a supplemental diagnostic,
not proof that the macOS-15 failure was fixed or passed. The prior artifact
contains no inner fixture receipt or assertion location, so the precise inner
cause cannot honestly be inferred yet.

The next **Intel-only native diagnostic** adds source-line locations and
closed, digest-bound inner-receipt aggregates to the sanitized summary; it
does not export raw traces, command lines, paths, identities or payloads. All
38 driver privacy/admission controls passed. The explicit `[rpc-intel-admit]`
marker cannot admit product or ARM work. Separate non-cancelling admission and
product queue keys let this bounded diagnosis run without stopping/repeating
the active full ARM lane; full matrix entries and cleanup assertions remain
unchanged. No timeout or ownership rule was relaxed.

The instrumented Intel-only admission at `adc555f4d9a4588e33357b49feb78367f60547c7`
then passed all **122 native controls** in
[run 36659734707](https://github.com/p2pKit/P2pKit/actions/runs/36659734707).
Finalization was independently verified with zero unresolved lifetimes,
discovery errors or survivors. The complete log ZIP and sanitized artifact
were retained; the latter's publisher digest matched
`e88e3cc955a06a784681dc6b859ed49446246dc9907afb341cf45f4f7ed6be1f`.
This passing diagnostic does **not** explain or erase the preceding intermittent
consumer-fixture failure. Its precise inner cause remains unproven; the new
diagnostics will retain failure sites and bounded inner receipts if it recurs.

An explicit `[rpc-intel-qualify]` follow-through request now selects the original
Intel/macOS-15/Xcode-26.3 product lane without repeating the already running ARM
lane. It still requires the full fresh native admission and every original
Intel product/cleanup gate. It cannot supply ARM or Android evidence, cannot
turn admission-only execution into a product pass, and never cancels another
run. Both full-matrix cells remain mandatory; results from distinct source
commits must be reported with their actual bindings, not combined into an
invented single-source matrix pass. All **39 qualification-driver controls**
passed before this request.

### Intel native-role check: separate test-harness defect

[Run 36660391250](https://github.com/p2pKit/P2pKit/actions/runs/36660391250) at
`80883248c0e3f5c9b7e97c0e8f7e0e1fb1ea3066` passed all **122 native controls**
and their finalization, then failed **toolchain admission**, not ownership or a
Kotlin test. JDK 17/21 native architecture, macOS 15, Xcode 26.3 and first-launch
checks passed. The next `rosetta-admission` command exited zero, but its parser
rejected the observation before the Intel hardware query. Complete logs and the
digest-verified summary ZIP are retained under `actions-36660391250/`; its ZIP
SHA-256 is `1c1c91e9116f7059369ef8ed120cfbe315ee4dd740e556ba193e504ffef823fe`.
No product tests were admitted, and this attempt remains failed.

The parser allowed only `(0, "0")` or `(1, "")` from
`sysctl -in sysctl.proc_translated`. The command's documented `-i` option
**ignores unknown OIDs**, returning `(0, "")` on genuine Intel hardware.
That exact behavior was reproduced on the available Intel VPS; the strict
`-n` query instead returned unknown-OID/exit one. The same interpreter's
maintained `audit_processes.host_role()` returned `macos-x64` successfully.
The historical hosted artifact does not export that raw CLI stdout; the
reproduced parser defect and exact failing prerequisite are distinguished from
unavailable historical bytes.

The chosen fix reuses that unchanged **native API observer** inside the bounded
source-owned command. It checks `sysctlbyname`'s value, size and errno, permits
the legitimate Intel `ENOENT`, and rejects translation or other query errors.
The exact required lane, native JDKs and independent Intel CPU-brand check are
still mandatory. Merely accepting every empty CLI result would hide errors;
parsing localized `sysctl` error text is brittle. Reusing the existing strict
observer avoids both. No production ownership rule, timeout or matrix entry
changed. The two added regressions cover absent-OID/native success, Rosetta,
bad sizes, access/I/O errors, wrong roles and empty/ambiguous output. All **41
qualification-driver controls** passed before the corrected Intel follow-through.

### Required ARM product follow-through and focused Native binding defect

The ARM lane of [run 36658403670](https://github.com/p2pKit/P2pKit/actions/runs/36658403670),
at `0260eed45c245ef7e630d53c93432e96b4b93ae9`, finished with these independently
retained results on **native ARM64/macOS 26/Xcode 26.5**:

- All **122 native controls** passed; all **63 commands** finalized, source
  remained unchanged, and there were no unresolved lifetimes or owned survivors.
- The scoped Native profile passed **1,041 cases**, with zero failures/errors
  and one pre-existing ignored diagnostic. This is not the full platform profile.
- All four project controls, all **28 exact Swift ownership/lifecycle methods**,
  and the **one actual production-adapter cancellation test** passed. The exact
  owned simulator's retirement was independently verified.
- Ordinary **88 Swift unit and six UI cases**, aggregate library ABI, strict
  Dokka, RPC frameworks, Swift API probes, SBOM, and fresh XCFramework
  producer/provenance passed.

The job nevertheless remains **FAIL**. Selected-interface IPv4 mDNS sends
failed with `NoRouteToHostException`; the full platform profile is
**BLOCKED_PREREQUISITE**, not passed. The separately required focused four-case
Native-helper/aggregate-LAN-ABI command also failed before admitting any focused
case counts. The broader Native and separate ABI passes do not replace it.
The original sanitized ARM artifact ZIP SHA-256 is
`b87d9e9ad39fa354e69a1d67e53a50fe505d677b89a8d4f13dd05b93eccbdbba`.
Complete available logs and the publisher-digest-verified artifact are retained
under `actions-36658403670/` in the continuation evidence directory.

Inspection found two writers of the same KGP task `device` property:
`SIMULATOR_INIT` assigns the newly owned device and calls `finalizeValue()` in
`projectsEvaluated`, then `owned_native_helper()` passes `--device` on the
task command line. Gradle applies the CLI option later and rejects even an
identical UUID: **"property 'device' is final and cannot be changed any further."**
This exact failure was reproduced using the actual Gradle **9.7.0**/Kotlin
plugin and repository task on the admitted Linux candidate `e3df8708`, with
`--dry-run`. Removing only `--device UUID` made the otherwise identical
configuration command succeed. Both source-bound invocations finalized cleanly.
These are configuration diagnostics, **not native Apple tests on Linux**.
Historical hosted raw Gradle output was not exported; the deterministic
reproduction, failing phase, and subsequent native rerun must be distinguished.

Reproduction uses the exact `SIMULATOR_INIT` text in a new private init script,
`P2PKIT_STRICT_SOURCE_ROOT` equal to the admitted checkout, and a synthetic
`P2PKIT_SELECTED_SIMULATOR` UUID. Through the existing owned executor, run:

```bash
# Expected configuration failure; executes no simulator or test body.
./gradlew :p2p-transport-lan:iosSimulatorArm64Test \
  --device "$P2PKIT_SELECTED_SIMULATOR" --dry-run \
  --init-script "$STRICT_SIMULATOR_INIT" --no-configure-on-demand
# Expected configuration success only; still executes no native tests.
./gradlew :p2p-transport-lan:iosSimulatorArm64Test --dry-run \
  --init-script "$STRICT_SIMULATOR_INIT" --no-configure-on-demand
```

The maintained executor adds its original strict dependency, resource,
no-cache/rerun and same-home-stop policy to both commands. The negative receipt
SHA-256 is `2ba388d6426682a132e434a3d5db5f5c568e9058c72d2a80889fceb1ff872c12`;
the corrected configuration receipt is
`7371e131eabe06a1dae180b6cfe0682033568f8f049bf65ecd714ca42b24194d`.
They remain under `local-capacity.dLB3px4C/results/` in the continuation evidence.

The selected minimal fix removes the redundant CLI writer in
`scripts/run-rpc-qualification.py`. The immutable device assignment, pre-body
equality check, exact four-method inventory, aggregate ABI, original deadline,
native ARM requirement and unconditional owned-device retirement remain.
Unfinalizing the property would weaken the fixture's binding; abandoning the
init script could let other Native tasks select an unrelated simulator. Neither
alternative was used. No production lifecycle/ownership rule was modified.

The regression in `scripts/tests/run-rpc-qualification-test.py` checks the exact
focused command, single binding, preserved ABI/deadline and retirement even on
execution failure. All **43 qualification-driver** and **11 audit-session
bootstrap** offline controls passed. An explicit `[rpc-arm-qualify]` request
selects only the original required ARM product lane, without cancelling or
repeating the independently running Intel lane. Full Apple/all-platform markers
still preserve every required matrix cell; ARM cannot supply Intel evidence or
admission-only success. Actual corrected ARM execution remains pending until
its separately recorded result; no configuration pass closes that gate.

### Corrected Intel follow-through: admission recovered, product gates still fail

[Run 36660995815](https://github.com/p2pKit/P2pKit/actions/runs/36660995815),
source `e28f50a88860b56a5ccb5c74e9b146073065d211`, completed on actual
**Intel/macOS 15.7.9/Xcode 26.3**, image `20260824.0482.1`. All **122 native
controls** and their finalization passed, followed by native JDK 17/21,
translation/hardware checks and the pinned toolchain. This validates recovery
of the original ownership prerequisite and the separate native-role parser
fix on the required host, not merely on the supplemental VPS.

The full job remains **FAIL**, with three distinct later failures:

1. Selected-interface mDNS again failed with `NoRouteToHostException`.
   The retained markers show matching selected/host/socket interfaces, a
   matching selected-interface route, no REJECT/BLACKHOLE/GATEWAY flags, and
   zero successful sends. This is not the historical stale dependency-lock
   issue. Full-platform testing remained **BLOCKED_PREREQUISITE**.
2. `scoped-native` returned product exit 1 with verified native finalization;
   its coverage assessor failed before admitting JUnit counts. No exact
   failing test or successful case count is established by the sanitized
   export. The raw Gradle/coverage details were not exported by that historical
   workflow; a failure location must not be invented from zero admitted counts.
3. `swift-simulator-readiness` exceeded its original **120-second product
   bound**. Its receipt records product -15, final 125 and the fixed error
   `Product command timed out`, with zero discovery errors or owned survivors.
   The qualification wrapper correctly refused successful finalization and
   labeled the phase `OWNERSHIP_UNPROVEN`; this is **not a recurrence of the
   original 16/17 unresolved-lifetime admission failure**. No ordinary Swift
   test was admitted. Subsequent exact owned-simulator shutdown, deletion and
   source verification succeeded; that does not convert the timed-out command
   or its product phase into a pass.

Independent ABI, strict Dokka, RPC frameworks, all three Swift API probes,
SBOM, fresh XCFramework production/minimum-OS and project generation passed.
The dedicated ARM cases were not run on Intel and are not replaced by it.
The precise Native-test and simulator-readiness root causes remain unresolved;
there was no blind expensive rerun, timeout extension, TCC/security change or
substitution of the supplemental Mac's different OS/Xcode result.

The complete available job logs and original sanitized artifact were retained
under `actions-36660995815/` in the continuation evidence directory. The artifact
ZIP's publisher SHA-256 matched
`a72bc634eea2e812a3445652ef6f6f3840c4a5962eb4ba4af272ac0576405792`;
the complete log ZIP SHA-256 is
`21d83d49628e5912e0fd5a555de8973f172322cc50143b4f539b4d3db2055a0f`.
The exact public runner-image manifest was also retained and checked against
its Git blob. It lists Xcode 26.3's iOS simulator SDK as 26.2 and installed
runtimes through iOS 26.2, plus 18.5; that does not establish the failed guest's
actual boot state or prove that selecting an older runtime would fix it.

### Corrected native ARM execution: focused ownership gates passed

[Run 36663774955](https://github.com/p2pKit/P2pKit/actions/runs/36663774955),
source `c22aeebbf88afb9d43eac63ca3a7a5685ddeb24d`, completed on the required
**native ARM64/macOS 26/Xcode 26.5** host. The duplicated finalized-device
assignment was removed **before** this run; it is not an unchanged rerun.
The publisher-digest-verified artifact admits these actual results:

| Gate | Result |
|---|---|
| Unchanged native ownership admission | **122 controls passed** |
| Scoped four-module Native profile | **1,041 passed**, zero failures/errors, one existing ignored diagnostic, 127 suites |
| Dedicated ownership project controls | All four maintained controls passed |
| Focused `IosOwnedFlowCollectionTest` plus aggregate LAN ABI | **All four exact methods passed**, required fresh ABI tasks verified |
| Focused Swift ownership/lifecycle | **All 28 exact methods passed** |
| Production-adapter Swift cancellation | **The one required actual case passed** |
| Ordinary Swift application tests | **88 unit + six UI passed** |
| Independent compilation/package-shape gates | ABI, strict Dokka, RPC frameworks, all three Swift API probes, SBOM, fresh XCFramework/provenance and project generation passed |
| Owned cleanup | **All 63 commands finalized**, zero pending lifetimes/discovery errors/survivors; exact simulator retired/deleted; source unchanged |

Focused repetitions are separate gate executions, not extra unique tests to add
to the broader suites. The Native-helper command and ordinary/full test
inventories retained the original assertions, bounds, owned device binding and
native ARM requirement. This closes the **ownership-admission and focused ARM
cleanup/cancellation blockage at this exact source**. It does not authorize
another source, merge, release or physical-device claim.

The overall workflow is still **FAIL**, solely because the selected-interface
mDNS prerequisite failed with `NoRouteToHostException`. The dependent full
platform profile is **BLOCKED_PREREQUISITE**, not passed. The failed multicast
command itself finalized correctly; no failure was converted into a warning
or removed from the overall verdict. The Intel source-specific failures above
are separate and cannot be filled in with ARM results.

Complete available logs, the original artifact and decoded sanitized summary
are retained under `actions-36663774955/` in the continuation evidence root.
The original artifact ZIP matched publisher SHA-256
`039377f2c5c217eb7cac79f945ff87e0cbd450cf8e8ccead93f5eb5b94bf1b42`;
the complete job-log ZIP SHA-256 is
`deeeca77efdb75f636a0238dcb009415d3fe28264b633c83f254f5485fcded1d`.
No Foundation/campaign workflow, source or private evidence was used, and all
Release Foundation and external-validation HOLDs remain intact.

### Final September 30 checkpoint checks and remaining gates

During the final checkpoint review, the revised full-steady and separate
large-payload evidence sets were independently re-read from their original
receipts, JARs and time series. Their recomputed aggregates matched the earlier
reviewed files **byte for byte**. Both latest Apple artifact ZIPs again matched
their publisher digests and actual source bindings; the live GitHub API still
reported the same completed **failed** overall runs. The independently reviewed
Apple aggregate `final-apple-evidence-review.json` SHA-256 is
`6edb34ec8eb0e527cb1a4d636c48586d5ee6de00b8fc4308792db636e9e6211e`.

All **43 qualification-driver, 11 audit-session bootstrap, 16 same-host fixture
and 12 capacity-lab offline controls** passed, as did seven module-policy
negatives, repository layout, OSV input coverage, relative Markdown links,
release metadata and strict dependency metadata/lock checks. The five added or
changed Kotlin files since `c22aeebb` passed the bounded line-length/wildcard
import scan; that is not a claim to have run ktlint. The protected instruction
and approved-plan hashes remain unchanged. These offline results are not more
Apple, Android or performance executions. Their complete log is
`final-offline-checks-20260930.log` in the continuation evidence root.

Fresh main remains `3bc76f956f8f47447b51a62474fc878b9c43173c`; its six stale
`org.jmdns` lock entries remain separate historical baseline debt. The feature's
previous independently reviewed correction is present; this continuation did
not regenerate/copy dependency inputs or import unfinished Foundation work.
Only test/harness/documentation files changed after the corrected ARM source;
no production RPC, LAN, native ownership, deadlines, limits or matrix entries
were relaxed. All required gates remain explicit:

| Remaining gate | Exact disposition / prerequisite |
|---|---|
| Full hosted Apple platform profiles | **Blocked** by selected-interface mDNS `NoRouteToHostException`; matching interface/route observations do not establish the underlying OS/provider cause. |
| Intel/macOS-15/Xcode-26.3 Native and Swift runtime | **Failed** Native assessment and 120-second readiness; precise Native assertion and simulator boot cause were not exported. Requires bounded failure diagnostics on the exact cell, not ARM substitution or a larger timeout. |
| Original intermittent Intel consumer fixture | A later 122-control pass does not explain the earlier failed inner invocation; failure evidence and diagnostics are preserved. |
| Direct Mac↔VPS LAN | **Blocked** by unverifiable JVM multihoming and provider NAT/reachability. Needs an SDK-verifiable approved path or a separately reviewed OS-enforced binding design; SSH/local-veth is not that proof. |
| 128-client capacity contract | **Failed twice locally**, most recently 69,538 missed sends; the remaining scheduling stalls are not attributed. Needs actual performance attribution and a complete successful unchanged 30-minute rerun, followed by real-host/platform qualification. |
| Maintained Android API-37/24/25 ART and permission gates | Still unqualified; scoped API-24 software probes/eight RPC controls passed, but do not replace the maintained suite or its currently unavailable authorized KVM prerequisite. |
| Signed iPhone installation / real Android↔iPhone hosting and capacity | **Not executed**; signed iPhone testing still needs owner signing/device access, and both actual mobile hosts require physical network/workload evidence. |
| Hostile-network, raw path/permission changes and six external validation areas | Remain independently pending under their original evidence and authorization rules. |

No unchanged expensive hosted rerun, merge, publication, release tag, repository
setting change or cancellation of another session's run was used to close this
checkpoint. **Release Foundation remains NOT_READY.** The completed local
fallback and genuine focused ARM passes are useful evidence, not a declaration
that the entire feature or release is ready.

## Further Intel and missed-send investigation — September 30

The [detailed investigation](qualification-investigation-20260930.md) supersedes
the unresolved scheduling attribution and two-attempt status above without
erasing any failed run. The third complete unchanged workload at `88f81e6b`
reconciled all 2,304,000 slots: **83,805 timer-late, zero permit-unavailable,
2,222 worker-late, and 2,217,973 actual calls/replies**. No dispatched call failed.
Every missed scheduled-second bin overlapped observed guest direct reclaim;
independent no-Java/no-RPC kernel-timer control also stalled during the VPS's
periodic balloon/reclaim episodes. This supports a generator/environment cause,
not remotely lost requests. The historical 69,538 combined counter cannot be
retrospectively divided into its three pre-invocation branches. No production
RPC change, extra retry or catch-up burst was made. **Capacity remains failed**.
The original 65-second retention and native cleanup passed independently.

Required Intel [run 36676816096](https://github.com/p2pKit/P2pKit/actions/runs/36676816096)
again passed all 122 ownership controls on Intel/macOS 15.7.9/Xcode 26.3. Its
actual iOS 26.2 runtime supported x86_64 and arm64. Core Native passed 793 cases;
LAN Native attempted 185 passes, nine failures and one existing ignored case;
RPC/sample Native tasks did not complete. These are failure diagnostics, not
admitted complete-profile counts. The exporter mistakenly failed to recognize
Gradle's task-prefixed Native class names. That reporting defect is corrected
with both-architecture positive/negative controls and an independent check of
1,036 preserved real Native XML case names. Raw messages remain private.

Swift readiness stopped at nonterminal **Data Migration, status 2**, within
the unchanged 120-second product bound. Product -15/final 125 reflected that
timeout, not unresolved process identities; native discovery errors and owned
survivors were zero, and exact simulator retirement/deletion later succeeded.
The ordinary platform phase lacked the explicit standalone-simulator retirement
already used by the maintained host and focused ARM helper. Both ordinary Apple
roles now isolate and retire only their created device, including on failure,
and ordinary Swift requires verified Shutdown before its original readiness
check. The subsequent Intel execution below proves that this lifecycle correction
does **not** resolve the boot stall. It does not relax ARM-only
follow-through, architecture, ownership, assertions or readiness deadlines.

Intel [run 36684095464](https://github.com/p2pKit/P2pKit/actions/runs/36684095464),
source `d7f093490966486552d24355105cda7caeefe84c`, completed **FAIL** with all 122
ownership controls passed. The reporting fix now maps all nine timeout failures
to the six lifecycle and three loopback methods listed in the detailed record.
The exact device was already Shutdown before/after Native and before Swift, so
stale Booted state is not their explanation. Swift again stalled at nonterminal
Data Migration/status 2 under the original 120-second bound; zero unresolved
identities/survivors and successful exact-device retirement remain independent
of that product failure. mDNS again failed IPv4 sends despite matching interfaces.

Two explicitly diagnostic Intel jobs now separate the existing LAN Native profile
with closed per-wait/browser observations from an untouched fresh-device boot
under the same deadline. Original ownership/security/full-matrix requirements
remain unchanged. Their scope is **not product qualification**; actual hosted
results must still be reviewed. The detailed record includes exact commands,
privacy/lifecycle regression coverage and the alternatives rejected rather than
weakening platform gates. Public provider permission/readiness reports corroborate
hypotheses but cannot replace per-run evidence.

The first two diagnostic cells, [run 36692979970](https://github.com/p2pKit/P2pKit/actions/runs/36692979970)
at `e9e357614d421e59cee16eeac396cc0b79472e7d`, **both stopped before their intended
experiments** despite 122 native controls passing in each. The Native cell timed
out during runtime enumeration, before simulator creation/build. The cold-boot
cell's added `/bin/ps` probe had an unadmitted `IDENTITY_EPERM` receipt; the driver
correctly did not boot, and exact simulator retirement/deletion passed afterward.
Those failures are retained. The narrowly revised probe observes only file-mode
metadata/load without executing a possibly set-id tool or relaxing ownership.
The existing 120-second bounds/full gate inventories remain unchanged; 62
qualification and 15 diagnostic offline controls cover the revised probe and
partial evidence. The bounded follow-up below subsequently executed both
experiments; the first attempt is not retroactively counted as their execution.

Revised [run 36694674756](https://github.com/p2pKit/P2pKit/actions/runs/36694674756)
at `9a086f88a1e790326a8cc12e519f859ded5eca16` completed **FAIL** in both diagnostic
cells, with **122 ownership controls passed per cell**. The Native cell actually
executed LAN `iosX64Test`: **191 passed, the same nine failed, one existing
ignored**, 33 XML suites. All 26 command receipts finalized, with no pending
identities/discovery errors/survivors. The unchanged strict assessor refused the
failed profile; core/RPC/sample Native and Swift were not requested by this
diagnostic. Interface-matched IPv4 multicast still failed before a successful
send return. Exact simulator retirement/deletion and source checks passed.

The other job verified a fresh Shutdown iOS 26.2 device and actually ran
`bootstatus -b` **without preceding Native/Swift/Gradle product or multicast
work**. All six revised read-only probes finalized. File metadata confirms
`/bin/ps` is setuid-root; the replacement never executed it or elevated its
observer. Boot passed Data Migration but stayed at **System App/status 4**,
nonterminal through 133 reported seconds, under the original **120-second
configured** deadline (not a proven exact wall-time termination bound).
Product -15/final 125 retained the timeout plus an exec-version observation
error. Three observation records were unresolved even though final pending
identities/discovery errors/known survivors were zero; this failed receipt is
not admitted. The device was subsequently verified Shutdown/deleted.
On four logical CPUs/14 GiB RAM, 1/5/15-minute load averages rose from
**3.312/10.203/9.877** to **426.955/194.265/87.273**. Load is not CPU percent,
and no per-daemon cause is asserted. A prerequisite independent of prior Native
work therefore remains; resetting shared services or extending bounds is not a fix.

Native's added diagnostic exception frames reached XML but their messages did
not. Inspection of the pinned Kotlin 2.4.10 parser and `KotlinTestFailure` proves
why: suppressed-message lines after the first frame are discarded, while their
frames are flattened. The test-only annotation now uses distinct closed
constructor types, preserving the original cancellation and all test/cleanup
requirements. Two new Native tests require all 13 constructor frames, and the
exporter will retain source-bound outcomes for the helper tests rather than
infer them from aggregate counts. One Native-only diagnostic request is justified
by this verified reporting defect; no unchanged cold-boot/full-matrix rerun or
production security change is made. Actual follow-up results remain required.
The [detailed investigation](qualification-investigation-20260930.md) records
the alternatives, all original failures, source bindings and verified artifact
hashes, including both complete revised jobs.

Fresh immutable `51445086` also passed 121 native ownership controls, seven
targeted path-recovery cases, 11 capacity-driver/diagnostic cases and **1,172
four-module JVM tests** (858 core, 233 LAN, 46 RPC, 35 sample), with no failures
or skips and verified native finalization. This validates the independent
path-fixture race correction on JVM; it is not an Intel Native result.

The same rebuilt candidate then passed the separate **20/20 one-MiB** real-socket
workload in **2.500899093 s** (7.997124 replies/s; p50/p95/p99 **181/574/606 ms**
bucket upper bounds) and all **six correctness cases**. Each new namespace
repeated 121 native controls. Idle retention passed after 65.795/65.153 seconds,
respectively; both independently owned workers retired with zero cleanup errors.
The [detailed record](qualification-investigation-20260930.md) binds all source,
JAR, measurement, host-resource and cleanup evidence and its limitations. This
does not retest or pass the failed 128-client capacity gate.

The detailed record contains source bindings, alternatives, measured resource
and timing limits, local fixture regression status, evidence hashes and the Mac
deletion gap. No Mac-only original was claimed recovered after deletion.
**All HOLDs remain; Release Foundation is NOT_READY.**

### Private Native frame follow-up — both failed attempts retained

[Run 36698432884](https://github.com/p2pKit/P2pKit/actions/runs/36698432884),
source `8506b0013c6d1cbc14db11386604a7eea785b6d0`, first failed **before** Native
compilation: the unchanged real consumer/executor fixture exceeded its original
20-second enclosing bound. Nested build verification was cancelled; that is not
proof of a source edit. The fixture and suite failures remain authoritative despite
successful top-level finalization. No simulator was created on that attempt.

One fresh allocation, with no source/control/deadline change, passed all **122
ownership controls** and executed actual LAN `iosX64Test`. It recorded **191 passed,
11 failed, one existing ignored**, 33 XML suites: the original nine discovery
failures and two new diagnostic-format assertions. The six other helper methods
passed individually. All **26 receipts finalized**, preserving product failure,
with unchanged source and no pending identities, discovery errors or owned
survivors. The exact iOS 26.2 simulator remained Shutdown around Native and was
retired/deleted. No new Swift, cold-boot, ARM or full-platform result is claimed.

Source-bound constructor locations now place every original failure at **initial
peer discovery**, before its advertised lifecycle/transfer check. Browser/listener
ready and missing host usage/Bonjour declarations were observed; they do not
establish a permission-denial cause. Multicast still returned `NoRouteToHostException`.
The new assertions failed because the private constructor frame is
`Class.<init>#internal`, as established by the pinned Kotlin 2.4.10 compiler, not
the assumed exported `Class#<init>()` form. The Native expectation and closed
exporter now recognize that exact private form without weakening either check.
Additional passive flags distinguish advertising intent and result/admission
callbacks without retaining identity or TXT data. All three stage and 14
observation constructors remain subject to actual Native regression assertions.

The [detailed investigation](qualification-investigation-20260930.md) retains
both failed attempts, exact assertion/source traces, publisher-verified artifact
hashes, alternatives and narrow offline results. A revised Native-only diagnostic
is required to verify this reporting fix; none of the failed cases is reclassified.
The independent simulator-readiness and full-platform multicast blockers,
failed 128-client scheduling gate, physical-device gates and **NOT_READY** HOLD
remain unchanged.

### Verified Intel diagnostic correction; original qualification failures retained

[Run 36703393356](https://github.com/p2pKit/P2pKit/actions/runs/36703393356),
exact source `63530bb89724fe8f87de66b481151cabf157bc34`, completed at **11:00:39
UTC on 2026-09-30** on the required native **Intel/macOS 15.7.9/Xcode 26.3**
cell. This was the existing Native-only diagnostic, not another full Apple/ARM
matrix or capacity attempt.

- **Verified fix:** all eight `AppleLanDiscoveryFailureTest` methods passed,
  including the two formerly failing real-constructor checks for three stage
  and 14 observation types. The private `Class.<init>#internal` recognition now
  works through actual Native execution and KGP export, not just offline examples.
- **Before/after:** LAN `iosX64Test` changed from **191 passed / 11 failed / one
  existing ignored** to **193 passed / nine failed / one existing ignored**,
  across 33 XML suites. Only the two diagnostic assertions were fixed; the same
  nine original methods still fail and the strict profile remains **CHECK_FAILED**.
- **Exact remaining stage:** eight initial-peer waits and one initial-peer-set
  wait. Every failure observes advertising intent, browser-ready, listener-ready
  and missing usage/Bonjour declarations. No browse-result callback, record
  rejection, peer acceptance or browser error was observed. This does not prove
  delivery of every debug event or identify an OS-internal cause, but it places
  the failures before their intended transfer/cancellation/lifecycle assertions.
- **Ownership/cleanup:** all **122 controls** and **26 command finalizations**
  passed, with unchanged source, zero pending observations/discovery errors and
  known zero owned survivors. Both failed product exits remain one. The exact
  iOS 26.2 simulator was Shutdown around Native and retired/deleted.
- **Still failed:** JVM multicast again had two IPv4 mDNS send attempts, zero
  successful returns and `NoRouteToHostException` despite interface/route matches.
  The separate original System App readiness failure was not rerun or fixed.
  No Swift, full-platform, ARM, ART or physical-device pass is claimed here.

Apple's current TN3179 says local-network privacy is not supported in the
simulator; macOS host permission attribution is a separate issue. Missing
simulator plist flags therefore do not prove permission denial. No evidence
supports changing production admission, increasing timeouts, changing the required
runtime or altering host security. The provider/OS root cause remains unresolved;
the original native Intel networking/readiness prerequisites remain required.

The [detailed investigation](qualification-investigation-20260930.md) records the
source trace, alternatives, exact command, public Apple reference, before/after
results and publisher-verified artifact **11091737693**. Its SHA-256 is
`84fb1dcb556f81ae5c3e54f685d735dbba23641b6b1278a31af7da67c4342052`.
Complete available logs, artifact, metadata and the independent review remain
under `.git/rpc-intel-capacity-20260930.QnOgzKzS/actions-36703393356/` in the
isolated clone. Current-source local diagnostic/lifecycle/policy checks passed.
No new product source, dependency, workflow or production-security change was
needed for this evidence checkpoint.

**Capacity remains unqualified:** the historical 69,538 misses were unsent
generator slots; the instrumented unchanged run reconciled 83,805 timer-late plus
2,222 worker-late slots, zero permit misses and zero dispatched RPC failures.
The stable-resource, full-rate 30-minute run and real JVM/Android/iPhone-host and
physical-network evidence remain required. The deleted Mac is not being accessed;
its previously documented preservation gap remains. All HOLDs and Release
Foundation **NOT_READY** are unchanged.

## 2026-09-30 continuation: SSH did not restore Intel Bonjour

Run [36728648795](https://github.com/p2pKit/P2pKit/actions/runs/36728648795)
completed the diagnostic APIs but failed: multicast errno 65, only LocalOnly
DNS-SD/loopback results, and zero inline-TXT browse callbacks remain. Its 122
native controls, 51 command finalizations and exact simulator retirement were
verified; a separate SSH server exit 255 also failed its strict finalization.
No Kotlin discovery or capacity gate was newly passed. A narrowly scoped
nonroot system-launchd comparison is implemented for actual execution next;
see [the investigation](qualification-investigation-20260930.md#ssh-follow-up-and-nonroot-launchd-comparison)
for scope, source/evidence hashes and cleanup safeguards. No production
networking or security gate changed. All release HOLDs and **NOT_READY** remain.

## 2026-09-30 continuation: hosted capacity integration, not a measured pass

The same-host fixture now supports a nonroot hosted state owner without chowning
source or relaxing namespace/capability/identity admission. An explicit
Ubuntu-24.04 workflow and source-bound driver perform native controls, actual
four-module JVM tests, distribution provenance, real-socket correctness, the
separate large-payload test, timer readiness and the original full-rate
30-minute workload. The timer/memory preflight screens the previously observed
VPS generator problem rather than making another partial capacity claim. No
capacity dispatch is authorized by an ordinary push; discovery verification
precedes the capacity marker. See [the hosted experiment contract](same-host-lab.md#owner-authorized-hosted-linux-experiment).

Local **offline** checks: 20 same-host fixture, 12 capacity-lab, 11 numeric-evidence,
9 hosted-driver and 7 scheduling-diagnostic controls passed. The new parser also
read the genuine prior 2,217,973-response/86,027-miss record and all 1,812 host
samples; it retained **FAIL** and reproduced the old independently reviewed
resource maxima. This checks parser compatibility, not a new workload. No new
Java, capacity run or measured performance is claimed here. The full hosted
execution, subsequent resource review, and physical/mobile gates remain pending.
All Foundation/release HOLDs remain **NOT_READY**.

## 2026-09-30 continuation: verified Terminal control, unresolved discovery

Both attempts of [36739975307](https://github.com/p2pKit/P2pKit/actions/runs/36739975307)
at `25abaaf39ef058cfa5869a95ac020ba12cb5be4e` verify the actual five-link Terminal
ancestry, including the expected restricted full-info query on one privileged
system-login ancestor, and exact application/child/command retirement. Attempt 1
failed the unchanged 120-second runtime-listing bound before any simulator or
network probe. Attempt 2 completed **122 native controls, 53 verified command
finalizations and 30 actual C observations**. Raw host/simulator multicast sends
returned successfully, but **10 observations still failed**: inline-TXT browsers
had zero callbacks and first DNS resolution was LocalOnly/`LOCALHOST`. Successful
sends do not prove multicast receipt, physical LAN or product discovery. Both
attempts remain **FAIL**; the original nine Kotlin cases and GUI readiness were
not rerun and capacity was not dispatched.

The [detailed investigation](qualification-investigation-20260930.md#verified-terminal-origin-working-send-returns-still-missing-txt-results)
records original artifact/log/review hashes and alternative explanations. A
narrow SSH comparison now retains SSH's own assigned authenticated audit session
instead of allocating another, while retaining the unchanged native ownership
executor. Its exact normal protocol-close observation distinguishes OpenSSH's
documented reason-11/exit-255 from unexplained failure; all cleanup, source,
credential, child-exit and bounded-evidence checks still apply. This is **pending
native verification**, not a claimed fix or relaxed gate. No production LAN,
authentication or ownership policy changed. Release HOLDs and **NOT_READY** stay.

## 2026-09-30 continuation: native SSH session did not repair discovery

[36744969088](https://github.com/p2pKit/P2pKit/actions/runs/36744969088), source
`edd7d61c0b7640a88de1bbc12c26f2e4350fd414`, verified the actual assigned,
authenticated, distinct and unchanged native SSH audit session, **122 native
controls, 53 command finalizations** and exact simulator retirement. It still
failed **13/30** OS observations: host local-network denial, BSD errno 65, and no
inline-TXT callbacks. One extra unknown SSH close-log line also kept strict
control finalization **unproven**; it was not ignored. SSH is opt-out again.

The next additive Terminal experiment tests exact selected-interface DNS-SD,
actually loaded executable declarations and a read-only global multicast
preference observation, while retaining all original probes and assertions.
See the [verified failed hypothesis and next controls](qualification-investigation-20260930.md#native-ssh-session-actual-hypothesis-failure-not-a-discovery-repair)
for evidence hashes, scope and security implications. No original discovery,
readiness or capacity gate is newly passed. Production policy, all HOLDs and
Foundation **NOT_READY** remain unchanged.

## 2026-09-30 continuation: actual multicast-advertising suppression found

[Run 36747721136](https://github.com/p2pKit/P2pKit/actions/runs/36747721136) at
`1fe7ebbef86a78e3130be1b3d9c6295028e623c9` verified **122 native controls, 63
command finalizations and 38 C observations** in the nonroot Terminal context.
**Sixteen observations failed**. The host's global documented advertising
suppression Boolean is actually **TRUE**; selected-interface DNS-SD browse and
resolve/TXT produce no callbacks on either compiled context, while registration
succeeds. The embedded usage/Bonjour metadata is loaded but does not repair
inline-TXT browsing. Source, Terminal shutdown and exact simulator deletion were
independently verified. Product failure remains one; no cleanup failure was hidden.

The [detailed investigation](qualification-investigation-20260930.md#verified-configured-advertising-suppression-and-bounded-same-runner-ab)
records artifact **11113792221**, all hashes, exact environment and alternatives.
The proposed correction now has offline regression coverage and an explicit
same-runner baseline/after experiment. It changes only the documented advertising
Boolean on a disposable admitted Intel job, uses the ordinary service manager,
and restores the original typed settings and file policy. Products and ownership
observers stay nonroot. TCC/SIP, routes, firewall, LAN admission, authentication,
test assertions and original deadlines remain unchanged. Service protection or
restoration failure is a real failure, never permission to bypass it.

The **70 qualification / 16 preparation / 28 network / 18 product-diagnostic /
15 Terminal / 17 SSH / 14 launchd / 11 audit-session** local controls passed.
No local Java build, new capacity workload or actual corrected Apple execution
is represented by them. The original nine discovery tests and untouched GUI
readiness still require execution; the full-rate capacity run follows verified
discovery recovery. All release HOLDs and Foundation **NOT_READY** are unchanged.

The first A/B run **36751707283** stopped in one offline fixture **before** native
execution, simulator creation or preference changes. Its Darwin temporary path
used a symlink alias rejected by the original private-file rule. The fixture now
uses the canonical physical parent and includes an alias-rejection regression;
all **17 preparation and 70 qualification** controls pass locally. The failure
and independent hashes remain in the detailed investigation; the actual A/B and
original discovery/capacity qualification are still pending, not passed.

## 2026-10-01 continuation: requested A/B was lost at the nested session boundary

[Run 36752026196](https://github.com/p2pKit/P2pKit/actions/runs/36752026196) at
`7c7434bb00f7e2f91685731774c87898cce85479` completed **FAIL**, with **122 native
controls, 63 finalized commands, 38 observations and the same 16 failures**.
Independent review verified unchanged source, simulator deletion, clean ownership
finalizations and Terminal retirement. The host setting remained **TRUE**. No
baseline or preparation proof exists: **the setting change was not attempted**.

The nested audit-session environment allowlist dropped the requested advertising
flag. The fix forwards that single explicit key and binds the request into the
Terminal child's exact argv. The driver now rejects argv/environment/scope
mismatch before native work. A two-allowlist regression reproduces the original
loss; negative controls retain rejection of secrets, loader hooks, arbitrary
commands and wrong architecture/context. No production or security policy changed.

The [detailed investigation](qualification-investigation-20260930.md#october-1-correct-the-dropped-advertising-request-before-repeating-native-work)
retains complete log/artifact/review hashes. These are harness corrections, not
verified recovery of the nine discovery failures. GUI readiness, full native
qualification and the required healthy-generator 30-minute capacity run remain
pending; all release HOLDs and Foundation **NOT_READY** remain unchanged.

### Baseline now executes; second integration defect corrected

[Run 36798060006](https://github.com/p2pKit/P2pKit/actions/runs/36798060006) at
`4450f5f029a409ee29605c178c600eff5df2d89a` completed **FAIL** after **122 native
controls, 37 finalized commands and all 12 before-change observations**. Six
baseline observations failed and the host advertising Boolean remained **TRUE**.
The dropped-option fix is verified, but a second handoff failed: the executor's
four-field source snapshot was passed to a helper requiring exactly commit/tree.
Source tracing and a failing-then-passing integration regression locate rejection
before preparation state or administrative commands. There was no setting change.

The caller now supplies the exact two-field identity; neither component's source,
ownership or cleanliness validation changed. A regression now runs the actual
preparation/admission/finalization code rather than replacing its constructor.
All **73 qualification, 17 preparation, 17 Terminal, 11 audit-session, 28 network
and 18 product-diagnostic** local controls passed. Full logs, source-bound artifact
and independent-review hashes are in the [detailed investigation](qualification-investigation-20260930.md#october-1-actual-baseline-reached-correct-the-source-contract-handoff).
Native discovery recovery, GUI readiness and capacity remain unqualified; no
release HOLD was lifted.

### Actual setting restoration passed; service lookup was wrong

[Run 36798931459](https://github.com/p2pKit/P2pKit/actions/runs/36798931459) at
`7c2b3dfbbb33230ec814c618aa45796bd07a85f3` executed the actual Boolean write and
exact restoration with unchanged typed preferences and file policy. However,
the old target `system/com.apple.mDNSResponder` returned **113/service not found**.
This is not a SIP denial or a failed discovery test after reload: **no reload and
no after probes ran**. The 122 native controls, 37 finalizations, 12 baseline
observations and complete Terminal/simulator retirement were independently checked.

The correction distinguishes the LaunchDaemon filename from its `Label`, uses
the fixed modern `.reloaded` service, validates the root-owned installed label
and program, and requires nonroot registration lookup **before** preference writes.
No arbitrary service, plist edit, PID signaling or protected-service fallback is
allowed. The actual runner must still verify this corrected setup. Local **21
preparation and 73 qualification** controls pass; the [detailed investigation](qualification-investigation-20260930.md#october-1-actual-preference-round-trip-wrong-launchd-service-name)
contains commands, complete hashes, actual failure and remaining gates. Discovery,
GUI readiness, full matrix and 30-minute capacity remain unqualified. Foundation
is still **NOT_READY**.

### Separate native/Terminal prerequisite failure retained

[36800355634 attempt 1](https://github.com/p2pKit/P2pKit/actions/runs/36800355634/attempts/1)
at `ce819163c8ba5caba0f99f165c005e3c4471f3a6` never reached Bonjour preparation.
The real consumer/executor integration fixture exceeded its existing **20-second**
outer product deadline, after a passed nested publication-fixture receipt. All
122 tests were reported but **none admitted** because the suite failed. Product
retirement was known; Terminal independently failed its **30-second ordinary
Quit** completion gate. Neither failure is suppressed or attributed to a CPU
cause without evidence. Source for both failed paths is unchanged from prior
passing runs. One fresh-runner repeat retains the same complete controls and
limits; it cannot erase the first failure. The [investigation](qualification-investigation-20260930.md#october-1-preserve-a-separate-native-prerequisiteterminal-failure)
records exact assertions, receipt errors, full hashes and remaining uncertainty.

### Verified same-runner advertising correction — original Kotlin follow-through next

[36800355634 attempt 2](https://github.com/p2pKit/P2pKit/actions/runs/36800355634/attempts/2)
at the **same `ce819163` source** passed all **38 native host/simulator OS probes**
after changing only the documented advertising-suppression Boolean. Before that
change, the same binaries retained **six failures among 12 baseline observations**:
selected-interface browsing/resolution and production-shaped inline-TXT browsing
had zero callbacks in both contexts. Afterward they produced actual callbacks,
matching TXT/port, selected-interface resolution and real connect/accept results.

All **122 ownership controls**, **75 command finalizations**, exact Terminal Quit,
simulator deletion and clean-source recheck passed. The preference round trip was
**TRUE → FALSE → TRUE**, all five service/configuration commands succeeded, and
full typed settings/ownership/mode were restored. No production transport,
authentication, ownership or LAN gate was changed. Some connections were loopback;
this remains native **same-host OS evidence**, not physical LAN qualification.

All 17 workflow log entries and the source-bound artifact were independently
reviewed. Artifact **11135842512** SHA-256:
`0cad2f4575dce3708b29c4a44759adb4558adf5112ef5d5f5cfe524bc980b99b`;
review SHA-256:
`4b0b9670edbc4b331faa3b136a6b13de0b7eb6da454290d14fd82424b7295b67`.
The [detailed investigation](qualification-investigation-20260930.md#october-1-verified-causal-bonjour-recovery-below-kotlin)
contains full logs hash, exact before/after observations, preserved attempt-1
failure and the narrow extension to original Intel native/full test inventories.
The nine Kotlin cases, GUI readiness, complete matrix and full-rate 30-minute
capacity are **not yet passed**. All release HOLDs and **NOT_READY** remain.

### Original JVM multicast recovered; new runtime-enumeration prerequisite failure

[36805158026 attempt 1](https://github.com/p2pKit/P2pKit/actions/runs/36805158026/attempts/1)
at `d6d8a2a1` passed **122 native controls**, toolchain/setup and the unchanged
**JVM multicast readiness/disposal control without rescue**. The exact native
Terminal inventory and reversible Bonjour setup/restoration worked; all five
setting/service commands exited zero and the original Boolean/file policy was
restored despite the failed prerequisite.

The next command, `xcrun simctl list --json runtimes`, emitted **zero bytes** and
hit its original **120-second** bound (product **-15**, final **125**). It had
zero ownership-discovery errors, pending observations or owned survivors and
successful stop, but its failed receipt remains unadmitted. No simulator was
created and **no Kotlin case ran**. This is not a renewed native permission
failure, nor is the missing output sufficient to diagnose the internal stall.
Terminal ordinary Quit/child retirement and clean source were verified.

All 17 logs and the source-bound artifact were independently reviewed. Artifact
**11137940398** SHA-256:
`76107f8048704a450bdeb537d1791624511a14bc65258ef07813fbb5ce90b1e0`;
review SHA-256:
`7c627202d5cda13f98dd093c74e59bebcdc4b88321db0937ee01811bfbae8b18`.
The [detailed investigation](qualification-investigation-20260930.md#october-1-original-multicast-control-recovered-runtime-enumeration-timed-out)
retains exact checks, full hashes and the rationale for one unchanged fresh-runner
comparison. The first attempt stays failed; no deadline, production policy or
release HOLD changed. Discovery's original Kotlin cases, GUI readiness and the
full 30-minute capacity run still require successful execution.

### Original nine Intel discovery failures: actual unchanged Kotlin profile passed

[36805158026 attempt 2](https://github.com/p2pKit/P2pKit/actions/runs/36805158026/attempts/2)
at the identical `d6d8a2a1` source completed **PASS in 12m51s**. The native
Intel/macOS-15.7.9/Xcode-26.3/iOS-26.2 environment passed **122 ownership controls**,
the original JVM multicast control and the entire original LAN Native profile:
**202 passed, zero failures/errors, one pre-existing ignored diagnostic, 33 XML
suites**. All eight Native diagnostic/frame methods passed as well.

Independent source comparison against the original **193-pass/nine-failure**
run verified unchanged product/tests, Gradle policy and platform assessor.
All six original lifecycle and three original loopback discovery cases are
recovered; none was skipped, renamed, relaxed or replaced. The verified fix is
the disposable runner's nonroot Terminal context and reversible advertising
preparation, not a production transport/security workaround.

All **26 command finalizations** passed with zero ownership/discovery/cleanup
errors or survivors. The exact simulator was deleted; Terminal ordinary Quit,
child reap, command removal and original Bonjour preference/service restoration
passed. Attempt 1's silent runtime-listing timeout is retained with its cause
unestablished; a passing fresh allocation does not erase it.

Artifact **11137224028** SHA-256:
`1db85f5e2cec4187da648a9657189e74dfb97594a37f57f7779e6c2d70a35136`;
independent review SHA-256:
`ac9bc65085e71a43a319a05badd9bcdb313d70355b413235b480a8fbe6cb8f77`.
The [detailed recovery record](qualification-investigation-20260930.md#october-1-original-nine-kotlin-discovery-failures-recovered-without-source-changes)
lists all nine methods, complete log hash, exact scope and preserved failures.
Next are the complete Intel inventory and separately isolated, healthy-generator
full 30-minute capacity run. **Neither is claimed passed yet.** Same-host
simulator/transport evidence is not physical LAN, cross-device or mobile-host
qualification. All release HOLDs and Foundation **NOT_READY** stay unchanged.

### Hosted stable-resource attempt: earlier gates passed, steady result unadmitted

[36807541215](https://github.com/p2pKit/P2pKit/actions/runs/36807541215) at
`2bd107b3` completed **FAIL**, not capacity qualification. Its fresh four-CPU,
16,373,452-KiB Linux allocation passed **121 native controls, 1,172 JVM tests,
all six real-socket correctness cases, and 20/20 one-MiB request/reply calls at
concurrency two**. Large calls took **2.200376241 s**, **9.08935464 responses/s**,
with zero RPC errors and client-call p50/p95/p99 **165/466/504 ms** (upper buckets).
Peak host RSS was **321,064,960 bytes**; sampled queue maximum was zero; exact
native finalization and **65.181-second** idle-retention resource cleanup passed.

The **125.000208492-second** independent clock preflight was healthy: 12,500
kernel expirations/reads, zero coalescing, maximum gap **10.264570 ms**, no observed
balloon/reclaim/swap growth. Nevertheless, the later steady phase exited **125**
with `OWNERSHIP_UNPROVEN` and **no measurement**. It did not complete the required
30-minute workload. The exported evidence is insufficient to identify the
underlying steady failure or establish that the JVM workload began.

The identified reporting defect searched only tracebacks even though the
namespace catches exceptions without printing one. The diagnostic-only correction
retains exact source locations and closed coordinator/native/worker observations,
always unadmitted and without exporting secrets or raw logs. Its original-source
regression fails before the correction; **15 offline controls** pass afterward.
It changes no production, workload, admission, retention or deadline contract.
The [detailed failed-attempt record](qualification-investigation-20260930.md#october-1-healthy-hosted-preflight-steady-phase-unadmitted)
contains exact scope, commands, hashes and remaining uncertainty. Artifact
**11139545211**, SHA-256
`6b23d0208234a7fce262253dc04d31b7dd7c8ffa5318d97ebecbf583bc796f5c`;
independent review SHA-256
`76365f0efd47d648f5f1f24725ebe39622f32fa684e72fd872c3c2474033f65b`.

At this earlier checkpoint the complete Intel inventory at **36807541133** was
still executing. Its completed result and the subsequent full capacity attempt
are recorded below; no passing full-inventory/capacity verdict was inferred.

### Completed Intel inventory: original discovery passed again, separate failures retained

[36807541133](https://github.com/p2pKit/P2pKit/actions/runs/36807541133), source
`2bd107b3`, completed **FAIL**. The original LAN profile again had **202 passed,
zero failures/errors, one pre-existing ignored diagnostic**; Native observed
totals were 1,049 passes / zero failures / one ignored. All 122 native controls,
eight helper methods, ABI/Dokka/framework/Swift API/SBOM/producer/archive controls
and exact simulator/Terminal/Bonjour restoration passed.

Remaining failures were **one Android host-test case** in
`:p2p-transport-lan:testAndroidHostTest` (120 passed; its name/assertion was not
exported by the Native-only diagnostic reader), and the **original 120-second
Swift `bootstatus` timeout**, ending in Data Migration with an initially Shutdown
simulator. No Swift runtime tests ran. These are not renewed failures of the
nine discovery cases or evidence of an ownership defect. There were **42
verified finalizations among 43 commands**, including the failed full-platform
product, and 41 zero-exit commands. The [complete investigation](qualification-investigation-20260930.md#october-1-full-intel-inventory-discovery-recovered-again-two-separate-failures)
records the exact evidence and corrects the earlier review's mislabeled count.
The next explicit Intel runtime diagnostic exports Android host-test failures
separately and runs the two affected tasks before one fresh-device readiness
attempt in the same protected Terminal context. It preserves original limits,
actual XML/coverage checks and every full-matrix requirement; it is not a
passing result or substitute for the full inventory.

### Completed full hosted capacity: 2,812 permit refusals, not a passing workload

[36810471106](https://github.com/p2pKit/P2pKit/actions/runs/36810471106), source
`7b23caae`, actually ran **1,800.000942576 seconds** with 128 authenticated
clients. It produced **2,301,188** responses of the required **2,304,000**,
**1,278.4371083 responses/s**, client-call p50/p95/p99 **4/13/134 ms**, zero RPC
errors/timeouts, zero timer/worker misses and **2,812 permit refusals before RPC
invocation**. Every missed slot encountered the unchanged eight-outstanding
per-client limit. The generator had no observed balloon/reclaim/steal growth
or 100-ms safepoints. Cold-path/initial throughput is the next investigated
factor, but the original aggregate export cannot locate every missed second.

Host/client measured CPU was **3,125.05 / 3,468.56 CPU-seconds**. Whole-series
host maxima were **889,516,032-byte RSS / 179 native threads / zero queued calls**.
Actual **65.217-second** retention returned clients/work/records/payload to zero;
native finalization and identity retirement passed. Separately **20/20 one-MiB
request/reply calls**, concurrency two, passed in **3.164384640 seconds**, with
p50/p95/p99 **239/639/760 ms**, zero errors and 65.251-second retention. All six
real-socket correctness cases and 1,172 JVM tests passed beforehand.

The [full record](qualification-investigation-20260930.md#october-1-complete-hosted-capacity-run-permit-saturation-not-timer-loss)
retains hashes, attribution limits and the fixed initialization experiment.
Initialization adds **76,800 separately counted real calls**, never subtracts
from the full steady target, and fails closed on error. The next hosted run
must verify the new deterministic Kotlin controls and all **2,304,000 measured
responses**; the offline accounting/privacy controls already pass. The current
capacity gate remains **unqualified**. This is isolated same-host virtual
Ethernet/TCP evidence, not physical LAN or mobile hosting capacity. All release
HOLDs and Foundation **NOT_READY** remain unchanged.

### Initialization follow-up stopped at JVM regression, before any workload

[36815606270](https://github.com/p2pKit/P2pKit/actions/runs/36815606270), source
`4f295c81`, completed **FAIL**. All 121 native controls and five command
finalizations passed; `jvm-regression` returned **product exit 1**. No producer,
correctness, large-payload, initialization or steady workload ran. Complete logs
and the original summary omit the failing compiler/test details, so the exact
underlying cause is **not established**, not guessed to be a product capacity
failure.

The [detailed record](qualification-investigation-20260930.md#october-1-jvm-regression-stopped-the-next-capacity-attempt-before-load)
retains the failed attempt and complete log/artifact/review hashes. The exporter
now retains closed source-bound JVM/compiler observations before failing the
phase, independently rereads them during collection, and never treats diagnostic
output as execution admission. Offline regression controls verify privacy,
source/token binding and failure retention. No product or qualification gate was
changed. A new actual hosted JVM pass must precede any capacity experiment;
the full 30-minute capacity gate remains **unqualified**, and Foundation remains
**NOT_READY**.

### Intel diagnostic identified the host method; fresh GUI boot still failed

[36816282836](https://github.com/p2pKit/P2pKit/actions/runs/36816282836), source
`016d79ea`, identified the failing host method as
`AndroidLanDataTransportOwnershipTest.inboundPerSourceQuotaRejectsBeforeQueueAndRecoversAfterRelease`,
originating from `AndroidLanDataTransport.kt:362` (`ServerSocket.accept()`). LAN
host tests reported 120 passed / one failed; the shared sample host test passed.
The exact JDK socket-error category was not exported yet and is not guessed.

A fresh iOS 26.2 simulator, with no preceding Native/Swift work, again exceeded
the unchanged 120-second readiness bound. It progressed from Data Migration to
System App but never reached terminal readiness. Four-CPU / 14-GiB host snapshots
showed 1-minute load rising from 4.428 to 393.650; this alone cannot identify an
internal CPU/I/O cause. All 122 native controls, original multicast, 30 of 31
command finalizations, exact simulator/Terminal retirement and advertising
restoration passed. The failed finalization records the readiness timeout, with
zero discovery errors/pending observations/survivors, not a demonstrated ownership
defect. The [detailed runtime record](qualification-investigation-20260930.md#october-1-intel-host-failure-identified-and-fresh-gui-timeout-reproduced)
retains hashes and attribution limits. The next narrow diagnostic preserves the
complete host tasks and all gates while extracting fixed JDK error categories;
no production exception handling or timeout has been weakened.

### Real-socket cancellation regression reproduced; correction dispatched next

[36820318142](https://github.com/p2pKit/P2pKit/actions/runs/36820318142) at
`5383c5c9` failed exactly at the new real-socket single-retirement assertion:
**234 JVM LAN cases passed / one failed**. All earlier assertions in that case,
including cancellation and actual closed listener, passed. All five native
finalizations passed; no capacity phase ran after the regression failure.

JVM and Android now check accepter cancellation before interpreting a blocking
`accept()` exception as a live listener failure. Active errors retain their
original cause/recovery path; security, quotas, ownership and deadlines are
unchanged. Green JVM/Android execution and a full workload rerun are pending.
The independent Intel readiness diagnostic also gains nonprivileged native
process/host snapshots instead of executing set-id `ps`; it cannot signal,
grant ownership, skip errors or extend boot time. The [red-run/correction record](qualification-investigation-20260930.md#october-1-cancellation-race-reproduced-before-the-production-correction)
contains evidence hashes and **129 passing offline controls**. Native execution
of that probe remains pending. All release HOLDs stay intact.

### Socket-closed reproduction and additional cleanup failures retained

[36818385640](https://github.com/p2pKit/P2pKit/actions/runs/36818385640) at
`84281a7a` identifies an actual socket-closed exception from real `accept()` in
`acceptedOptionFailureClosesWithoutConsumingASourceSlot`. The likely cancellation
reclassification path now has two mirrored real-socket JVM/Android-host regression
tests, **not yet executed**; production behavior remains unchanged at this
checkpoint. The full capacity attempt at `911e5edf` is still running independently.

The fresh simulator remained in Data Migration at its original readiness limit.
The after-hardware product returned zero, but an unresolved native
`ENVIRONMENT_EIO` prevented ownership finalization. Terminal Quit completion also
failed, leaving termination/command removal unproven. These are retained failures,
not successful cleanup or a hardware-command timeout. There were **27/29**
verified finalizations, 122 native controls, and exact simulator/Bonjour
restoration. See the [complete failure and regression record](qualification-investigation-20260930.md#october-1-socket-closed-failure-isolated-cancellation-regression-pending)
for source locations, hashes and attribution limits. No gate has been relaxed;
Foundation remains **NOT_READY**.

### Complete steady-state capacity result, independently reviewed

[36817165645](https://github.com/p2pKit/P2pKit/actions/runs/36817165645), source
`911e5edf6b84af62da0f37b5456aec9dcaf2f29f`, completed **1,800.000735685 seconds**
with **2,304,000/2,304,000 successful responses**, **zero missed sends**, zero RPC
errors/timeouts/connection changes, and **1,279.999476846 responses/s**. The
128 independently authenticated clients sent 1-KiB requests/replies at ten calls
per second each. Client-call p50/p95/p99 were **4/14/32 ms**, maximum 294 ms.
Every one of the 1,800 schedule bins contains the full 1,280 completed slots.

The separately counted fixed initialization added 76,800 calls and did not
shorten or contribute to the measured gate. Native thread/retained-state limits
and all cleanup checks passed; queue maximum was zero. The host's sampled
whole-series peak was **888.65625 MiB / 177 native threads**; steady RSS approached
a plateau and all connections/work/records/payload cleared during 65.171-second
retention. Host/generator CPU observations were **3,148.54/3,493.02 CPU-seconds**
on four shared cores. No balloon/reclaim/steal or 100-ms safepoint stalls occurred.

The separate large test passed **20/20** 1-MiB requests and replies, concurrency
two, in **2.989906670 seconds**, p50/p95/p99 **216/677/748 ms**, with zero errors.
Fresh JVM regression passed **1,176 cases**, plus all six real-socket correctness
cases. The [full source-bound review](qualification-investigation-20260930.md#october-1-full-rate-30-minute-same-host-jvm-workload-passed)
records artifacts, hashes, exact commands, sampling limits and failed-attempt
comparisons. No numeric latency cutoff was invented.

This is a **same-host private-veth/TCP JVM qualification result**, not physical
LAN, mobile capacity or full release qualification. The pending cancellation
fix still needs its own regression/full rerun; Intel readiness/cleanup and full
ARM gates remain open. All release HOLDs and Foundation **NOT_READY** remain.

## October 1 pending-discovery drain correction and Intel admission follow-up

Intel [36821968958](https://github.com/p2pKit/P2pKit/actions/runs/36821968958)
at `1b50f655` stopped at the consumer executor fixture's original 20-second
deadline. Android tests, process snapshots and simulator readiness did **not**
execute. The command itself finalized, but Terminal's `QUIT_COMPLETION` did
not; whole-context cleanup remains unproven. Relative receipt timing has been
added to distinguish the next attempt's execution and finalization costs
without publishing raw output or identities.

Separately, three offline red-to-green regressions establish that the POSIX
drain previously counted unresolved discoveries as quiet and could return
after only 0.2 seconds. It now observes them within the unchanged original
grace/kill-wait bounds; unknown processes are never signaled, and unresolved
records still fail finalization. Native follow-through is required; this does
not prove the consumer timeout or GUI-readiness cause. Complete required
inventories increase to 125 Apple / 124 Linux controls. See the
[detailed evidence and security analysis](qualification-investigation-20260930.md#october-1-follow-up-admission-fixture-timeout-and-drain-observation-defect).

The prior original nine-case Bonjour recovery and full 2,304,000-response
capacity pass at `911e5edf` remain source-bound results, not blanket current
readiness. The full capacity rerun at `1b50f655` remains pending independent
review. All release HOLDs and Release Foundation **NOT_READY** are preserved.

## October 1 current full-rate follow-up failed through permit saturation

[36831891298](https://github.com/p2pKit/P2pKit/actions/runs/36831891298), source
`a25951ee`, actually completed **1,800.000744050 s** but produced only
**1,740,951 / 2,304,000** required replies: **967.1946/s**, client-call
p50/p95/p99 **802/1,314/1,568 ms**. All **563,049** misses are reconciled
before invocation: **562,825** at the unchanged eight-per-client permits and
**224** at worker entry. No timer-late slots, RPC errors, timeouts or connection
changes occurred; every dispatched call completed on client and host.

Unlike the prior attempt, the generator had **zero 100-ms safepoints** and no
observed reclaim/balloon/major-fault/steal growth. Permit pressure persisted in
all six five-minute windows. The apparent 986-ms clock-observer lag is after
the scheduling window, not a lost-timer cause. The two JVMs used **6,809.36
process CPU-seconds** on four shared CPUs; this does not identify the exact
slow path. No production change or higher permit allowance is justified yet.

All **124 native controls**, **1,178 JVM tests**, six socket correctness cases
and native finalizations passed. Steady idle retention actually ran **65.158 s**
and cleared connections/work/records/payload. Whole-series host maxima were
**1,185,931,264 RSS bytes / 180 native threads**, not a process-memory ceiling.
The large phase passed **20/20** one-MiB requests/replies at concurrency two,
**3.923012102 s**, p50/p95/p99 **298/817/922 ms**, zero errors.

The [complete diagnosis and evidence](qualification-investigation-20260930.md#october-1-full-follow-up-sustained-permit-saturation-not-generator-safepoints)
preserve hashes and attribution limits. The next diagnostic adds bounded
CPU/wait sampling in both already-owned JVMs and exports the existing host GC
timings, without changing any workload or gate. Raw recordings remain private;
only source-bound closed categories are exported. That diagnostic is pending
actual execution, not a claim of a fix. Full-rate capacity remains unqualified;
Intel discovery is separately recovered. All release HOLDs and Foundation
**NOT_READY** remain unchanged.

## October 1 ARM preparation prerequisite isolated

Native ARM [36850116367](https://github.com/p2pKit/P2pKit/actions/runs/36850116367)
at `256b0432` passed all **125 native controls**, seven finalized commands and
complete Terminal cleanup. It stopped before products at
**SNAPSHOT / PREFERENCE_MISSING**: the image has no system mDNS preference domain,
unlike the Intel image with its explicit advertising suppression. This is a
preparation assumption, not a product ownership or multicast failure.

An ARM-only observed-absence/no-change path now verifies the protected parent,
actual ENOENT and unchanged installed service before/after execution. It cannot
write/delete settings, reload services, admit permission errors as absence or
fabricate restoration flags. Intel repair and every real multicast, native ARM,
cancellation and cleanup gate remain unchanged. **435 offline controls** plus
the corrected repository checks passed; actual ARM follow-through is pending.
The [detailed root cause, alternatives and evidence](qualification-investigation-20260930.md#october-1-arm-preference-absence-correct-the-preparation-assumption)
retain failed attempts and artifact hashes. Foundation remains **NOT_READY**.

## October 1 reproducible Android handoff integration

The [feature-only handoff workflow](../../.github/workflows/rpc-android-handoff.yml)
now produces both debug APKs through a fresh admitted native producer and runs
the existing eight supplemental API-24 software-AVD controls before delivery.
It retains all maintained ART, KVM, production-signing and physical/capacity gates.
The collector rechecks source, six exact finalized commands, actual controls and
both APK hashes; only complete private staging may become an upload path. A
failed/partial collector never uploads binaries. Native APK/AVD execution remains
**pending** here; no new installable artifact is claimed from offline fixtures.

**25 offline controls passed** (18 handoff and seven unchanged Android-controller
controls), including source/receipt/type/privacy failures, unsafe subsequent work,
second-file copy failure, source drift and byte-for-byte atomic export. The first
local fixture omitted the actual policy file needed by the diagnostic validator;
it was corrected without changing production validation. Failed logs remain.
Passing log `android-handoff-controls.8vDzZd7u.log` in the existing evidence root
has SHA-256 `4fd69ad2863411c61f6597122857f71548ae8d0694f40c52c37600e76ac6ecdc`.
The [handoff instructions](device-testing-handoff.md) explicitly separate physical
installation, missing mobile telemetry integration and unsigned iPhone preparation
from completed hosted checks. All release HOLDs remain unchanged.

## October 1 Intel follow-up: separate timeout from recovered observation

[36849889422](https://github.com/p2pKit/P2pKit/actions/runs/36849889422) at
`a2a30ade` passed 125 native controls, real multicast and all 124 Android-host
tests. Fresh iOS 26.2 GUI readiness still exceeded the unchanged 120-second
Data Migration limit. All later exact simulator/Bonjour/Terminal cleanup passed.
The failed receipt's only actual error is the product deadline; its two
environment/exec observations recovered, with no pending discovery or retained
survivor. Infrastructure status 125 still fails admission—no gate was bypassed.

The actual ten-second post-attempt interval recorded zero idle ticks, but
17.958 CPU-seconds fell in `other-readable`. The diagnostic classifier omitted
framework `Python` names, so harness CPU cannot yet be excluded. That coverage
gap and timeout-category reporting are corrected with **125 passing offline
controls**; original deadlines and ownership remain intact. The
[full review](qualification-investigation-20260930.md#october-1-intel-cpu-interval-readiness-timeout-not-an-unresolved-exec-race)
retains exact counts, failed prerequisites, hashes and attribution limits.
Native follow-through is pending; this is not a GUI-readiness pass.

## October 1 Android handoff: producer succeeded, diagnostic registration failed

[36853495799](https://github.com/p2pKit/P2pKit/actions/runs/36853495799), source
`d8da13abd9cc8f73e7f6d6a0c91c66495373b52b`, passed **124 native controls**,
both native JDK inspections, SDK installation and the actual two-APK producer.
All five executed command receipts were independently finalized; source was
unchanged. The workflow nevertheless failed before starting the software AVD.
There is no emulator, instrumentation or delivered-binary pass in this attempt.

The exact mechanism is a coordinator integration defect: after the verified
zero-exit producer, `Job.invoke` called the closed build-diagnostic validator
with `android-apk-producer`. Its fixed list still recognized only the older
`jvm-regression` and `capacity-producer` names. It raised `ValueError` before the
producer's `END` message or the subsequent emulator command. The exported empty
diagnostics/five successful commands and complete workflow logs agree with the
red offline reproduction of that exact call path. This was not a compiler,
emulator, native-ownership or production-security failure.

The smallest correction registers **only that exact additional diagnostic
purpose**, still requiring membership in the calling coordinator's purpose list.
It changes no execution admission, timeout, ownership, API-level, cleanup or APK
delivery requirement. Unknown names and missing caller authorization still fail;
diagnostic rows still carry `executionAdmitted: false`. The new orchestration
regression uses the real parser/validator, not a mocked diagnostic result.
**50 offline controls passed** (19 handoff, 24 diagnostic, seven unchanged Android
controls), followed by whitespace checking. Fresh hosted follow-through remains
required; neither fake offline receipts nor an APK build proves ART execution.

Evidence in `.git/rpc-bonjour-qualification-20260930.oOYgSoqr/`:

- `android-handoff-36853495799-attempt1/`: artifact `11157310971`, verified SHA-256
  `14750807ffed7df33113bb7132c96b178a8c122deaf66c47d888288ad724ea6a`;
  complete workflow logs `495a294d49687bab6de9cfade517396d3dea9e453e847770706bad68a6fbc6ff`.
- `android-producer-red.t6oYLdKv.log`: reproduced original failure, SHA-256
  `1e80429b31363b855c6c14b2e68c03e010a02d75c1c79fa7c1a3b3e67064025c`.
- `android-producer-controls.JiZuQmwA.log`: all 50 passing controls, SHA-256
  `0c2a842917d7520fbbebcd0bba965d18eaf504bddb687ec09dfd224e24ab066d`.

No binary was exported from the failed attempt. Foundation remains **NOT_READY**.

## October 1 Android follow-up: binary/report bound mismatch

[36854821191](https://github.com/p2pKit/P2pKit/actions/runs/36854821191),
source `8c5719c8afaeb8fcffea5020358c9a118ff91325`, independently finalized all
six exact commands at exit zero, including the actual supplemental API-24
controller. All 124 native controls passed and source remained unchanged.
Post-execution assessment/export nevertheless failed; no APK, exact boot time
or runtime/package-detail handoff is admitted from its failed manifest.

The next source defect is in `run-rpc-android-handoff.py::apk_metadata`: it
explicitly permitted APKs up to 128 MiB, then used the JSON/report hasher whose
independent maximum is eight MiB. A real-file, SDK-free 8-MiB-plus-one-byte
reproducer fails at that exact `bounded()` call. This explains a normal-sized
APK's rejection after successful native execution; the failed job did not
export its APK sizes or private exception, so that size for this particular
job is not retrospectively asserted. Hosted follow-through remains necessary.

Only APK hashing now streams through an already-open, non-symlink, owned
regular file with the original 128-MiB cap. It checks inode/owner/mode/link
count/size/timestamp/content length before and after reading, and closes its
descriptor even when rejecting a nonregular input. Copying remains bounded,
content-checked, create-only and privately staged. The eight-MiB report limit,
actual control assertions, source binding, native ownership, cleanup and all
maintained ART/KVM gates are unchanged. No partial binaries can be exported.

**53 offline controls passed**: 22 handoff, 24 diagnostic and seven existing
Android-controller controls, including oversized/symlink/hardlink/changed-file
rejection and atomic export failure. No local Java, SDK or application ran.
Evidence in `.git/rpc-bonjour-qualification-20260930.oOYgSoqr/`:

- `android-handoff-36854821191-attempt1/`: artifact `11158531788`, SHA-256
  `1f7e1aecc4653ffc143b14b1e80166be1591cc1e9f0ca37cb5620330029be08f`;
  complete logs `6953fa323b949b3f59584ed844513e3e2d28d3049bc27272e425937e30b03cef`.
- `android-apk-bound-red.jGz0rYoO.log`: original bound failure, SHA-256
  `4d509d3110ed94897b428dfa0358a54f030e71f152c838690cb370dec61ee0a0`.
- `android-apk-bound-controls.CxWKVHPb.log`: first local correction exposed
  an exception-type/descriptor-lifecycle defect on a directory input; retained
  failed result, `e72ac2aebbb86d357862506f1ed89eec4d094f8b78e83b36f51d4b66a58c32fe`.
- `android-apk-bound-controls.Ko6zqrRb.log`: all 53 controls passed, SHA-256
  `cf3e12c121be61f4d685b5bddb8bf309887879ebe1e344a51d679b0ebbc7ca9f`.

Fresh hosted export is pending. Foundation remains **NOT_READY**, all HOLDs intact.

## October 1 current regression prerequisite and Intel follow-through

Capacity [36855481289](https://github.com/p2pKit/P2pKit/actions/runs/36855481289)
at `0827bfb0` never reached load generation. All 124 native controls/five
finalizations passed, but one of 1,104 executed JVM cases failed: the successful
reconnect fixture stopped Bob after outgoing Connected but before Bob's own
incoming-session commit. The production lifecycle rejected that late commit;
the strict logger correctly failed teardown. The fixture now waits for both
publications, with an additional deliberately held-responder regression.
All diagnostics, retry/state/identity assertions and existing bounds remain.
Offline repository checks passed; actual JVM and full capacity reruns are pending.

Intel [36853772857](https://github.com/p2pKit/P2pKit/actions/runs/36853772857)
passed 125 native controls, real multicast and 124 Android-host cases. Its only
failed command remained never-used-device Data Migration readiness at 120 s.
33/34 commands and exact simulator/Terminal/Bonjour cleanup finalized. The
post-attempt CPU observation measured only 0.865 Python CPU-seconds in 10.663 s,
so it does not substantiate the suggested dominant harness-CPU explanation.
Unreadable processes and measurement timing remain coverage limits.

The next Intel run follows the unchanged **original full matrix**, whose Native
test/retire/Swift-readiness sequence differs from the first-boot diagnostic.
No hidden warm-up, timeout extension, architecture substitution or cleanup
exception is introduced. The [detailed evidence, alternatives and exact hashes](qualification-investigation-20260930.md#october-1-regression-prerequisite-responder-publication-versus-test-teardown)
retain the failed attempts. No new capacity or full Apple pass is claimed.
Foundation remains **NOT_READY**.

## October 1 fresh iPhone handoff preparation

The feature-only `rpc-ios-handoff.yml` workflow and `run-rpc-ios-handoff.py`
coordinator now provide a reproducible **unsigned** app handoff path after the
old Mac's deletion. All eleven exact commands use the unchanged native owner
and fresh source-bound state on ARM/macOS 26/Xcode 26.5. The existing controller
retains its original boot/test/producer deadlines, nine exact XCTest methods,
current-source framework producer and both mandatory nested provenance checks.
It additionally deletes and verifies absence of **only** its newly created
simulator after confirmed Shutdown; malformed/duplicate inventories, case-varied
retained identities or unavailable cleanup fail, never become warnings.

Collection independently verifies native host/toolchains, receipts and nested
ownership/source/Gradle-home binding, actual XCTest method JSON, tool/app hashes,
arm64 device binary and Mach-O iOS-15 deployment target, and unsigned app inputs.
All bytes are privately staged and rechecked before atomic public rename.
Failures cannot upload a partial app; signing/provisioning material is refused.
The [handoff document](device-testing-handoff.md) distinguishes this app scope
from the unchanged full Apple, Bonjour and dedicated ARM adapter-cleanup gates.

**41 offline controls passed** (17 handoff, 13 phone-controller, 11 audit-session).
These use explicit fake files/receipts for orchestration, not simulated Apple
execution evidence. Native execution/build/export remains pending. The first
local fixture used the wrong argv slice for the host flag and failed; that
fixture index was corrected without altering the actual command or admission.

Evidence in `.git/rpc-bonjour-qualification-20260930.oOYgSoqr/`:

- `ios-handoff-offline.KKyhQLd0.log`: retained fixture-index failure, SHA-256
  `80ab7c5fce1010364f9c5a7f04e814139a1303577292940aac85efbb4b73beb8`.
- `ios-handoff-offline.3YHFWp09.log`: 41 passing controls, SHA-256
  `a52513844685de58a79842d1b730d79ba8b0fe7537eda637c789a40ab7c071e0`.

Repository layout/RPC policy/OSV/links/release metadata/checkout-credential
checks also passed (`ios-handoff-repository.1mTShmPY.log`, SHA-256
`25703ae8e4ce83a39e65d063a596fa3d9f0d0270e3473b751ded0cc14476b04d`).

No signing credential was accessed, no local Java/SDK/Xcode ran, and no
physical-installability claim is made. Foundation remains **NOT_READY**.

## October 1 verified Android handoff and native ARM full qualification

Android [36857064456](https://github.com/p2pKit/P2pKit/actions/runs/36857064456),
source `489b1f92caecce3b60df2647795de2c2be24c763`, passed **124 native controls**,
all six exact finalized commands, fresh production of both APKs and **all eight
actual supplemental RPC/Keystore/Activity controls**. The API-24 x86_64 software
emulator booted in **100.449 s**, using emulator **37.1.11**, image revision **8**,
acceleration off and VM property `Dalvik`. Natural cleanup and unchanged source
were verified. The independent collector passed, and both downloaded APKs were
independently rehashed and matched their recorded byte counts.

The [device handoff](device-testing-handoff.md) now gives the exact successful
artifact, source, download/install commands and binary hashes. This closes the
APK/report-size integration defect with real execution; both earlier failed
attempts remain failures. It does **not** close maintained API-37/24/25 ART,
physical-network or mobile-capacity qualification. Public package/evidence
artifacts `11159486321` / `11159371360` have publisher ZIP SHA-256 values
`454e126fb11eb5745e76c2003b5d68e47110bad635a0019bbcb20ea0dd29441b` /
`8478751d41b0abc42755ba523b5dc02b3b6c2917007a10d616d27e6d73ddd583`.
Complete workflow logs have SHA-256
`9072a435956626be5235420908ac8f05536c1dc3e87f468abec95684dee66aa9`.
All are preserved under `android-handoff-36857064456-attempt1/` in the existing
evidence root, with the verified APKs and `independent-review.json`.

Separately, native ARM [36852424465](https://github.com/p2pKit/P2pKit/actions/runs/36852424465)
at `ac4e733587a8405054a91c4ac226ce5a58b703d0` passed the **complete original
matrix** on macOS **26.6.2**, Xcode **26.5** and the iOS-**26.5** ARM simulator:
**3,034 JUnit passes / zero failures/errors / one existing ignored diagnostic**,
all 20 required tasks, **125 native controls**, real multicast, ABI/Dokka/SBOM,
framework/provenance, **88 Swift unit/six UI methods**, and the dedicated
**four Native / 28 Swift lifecycle / one production-adapter cancellation** gate.
All **68 commands** finalized and the exact simulator/Terminal cleanup passed.
The [full source-bound review](qualification-investigation-20260930.md#october-1-complete-native-arm-matrix-and-cleanup-passed)
records root-cause confirmation, environment, artifact hashes and unchanged
security guarantees. The later reconnect fixture still requires ARM follow-through;
Intel and capacity results must be reviewed separately, not inferred from ARM.

The complete permitted offline fixture pass at `d76138c3` additionally executed
**22 scripts: 451 unittest cases plus seven source-policy negative controls**.
Every command/log hash is retained in
`current-offline-suite.q15tti7q/summary.json` in the evidence root. No product,
native, build or SDK operation was executed locally for this offline pass.
All release HOLDs and Foundation **NOT_READY** are unchanged.

## October 1 first fresh iPhone handoff failed; inner-phase evidence added

[36858137736](https://github.com/p2pKit/P2pKit/actions/runs/36858137736), source
`d76138c329537ff2744d21060b280c05f33117de`, passed all **125 native controls**
and finalized all eleven outer commands. The first ten products returned zero;
`phone-controls` returned **1** after approximately 638 seconds. Collection
correctly produced a **FAIL-only manifest with no app or control pass**.

The original manifest and complete logs do not expose the controller's inner
phase. They cannot establish whether the failure was framework production,
simulator boot, XCTest, device compilation or final verification, nor certify
the inner simulator's cleanup. Outer native finalization alone does not answer
those questions. A cold-boot or compiler diagnosis at this point would be an
assumption. This failed attempt is retained, not relabeled or rerun unchanged.

`rpc_phone_diagnostics.py` now projects only fixed controller labels, original
bounds, exit codes, relative wall intervals, reported flags, closed error/boot
categories and log hashes. The collector reads only its finalized controller's
source-bound result and fixed owned paths, and independently binds any nested
producer diagnostic to its canonical receipt, source, ancestor and exact task.
Missing output stays missing; unknown errors never export their text. Schema 2
keeps diagnostics separate from actual admission/controls. No test, deadline,
cleanup condition, architecture, production path or signing policy changed.

**73 offline controls passed**: 25 handoff, 13 phone-controller, 24 existing
diagnostic and 11 audit-session cases. Coverage includes lost inner-phase
evidence, private-text rejection, null/missing output, clock reversal, forbidden
command/bound/type, source/owner/ancestry/argv drift, symlinks and a failed
controller's inability to export an app. This verifies reporting infrastructure,
not the unresolved native phone failure. A fresh native diagnostic run is needed.

Evidence in `.git/rpc-bonjour-qualification-20260930.oOYgSoqr/`:

- `ios-handoff-36858137736-attempt1/`: artifact `11161780561`, verified publisher
  SHA-256 `53eb1cfe11ceb4db5fc5e312df39a427e3fc939a9b839e346a36eb3bd8dbdc6d`;
  complete workflow-log ZIP
  `fcb7f1a8cf67e38f5cf202b1a4168bea02cb3a6908ad9564ec961468abcbb7b5`.
- `iphone-phase-diagnostics-red.yot2Kag4.log`: expected missing-projection
  regression, SHA-256
  `f7fb7a28ee26692db5a435f782b8074416aa4839b71cfc0f1f7d5c3e4e865afb`.
- `iphone-phase-diagnostics-controls.f4D1WASN.log`: 73 passing controls,
  SHA-256 `3f1c8ad7a8233e9ad124486f6bd0fbc3f909cfbc768ff6ad7422e19b1fa2127f`.

Android's verified package and full ARM qualification remain separate results.
Foundation remains **NOT_READY**; all physical/signing/capacity HOLDs remain.

## October 1 read-only ART prerequisite follow-through

The container was re-inspected using the bounded read-only KVM diagnostic. It
still has **no `/dev/kvm`**, no exposed VMX/SVM CPU flag and no readable Intel/AMD
nested-module parameter file. This is not a claim that software emulation is
impossible: the separately recorded API-24 software-emulator execution stands.
It does explain why this container cannot satisfy the unchanged **accelerated
maintained ART** prerequisite in its current configuration.

The feature-only Actions workflow now performs the same closed observation for
the Linux ART lane before the original native executor/gates. No user/group,
device ACL, module, security setting or qualification condition is changed.
**112 offline controls passed**: six metadata/privacy/negative controls, 84
existing qualification controls and 22 hosted-policy controls. The source-bound
fresh ART run must still establish its own access and actual test results.

Evidence in the existing root:
`container-kvm-observation.WYwTaTEZ.json`, SHA-256
`cf1f1e7b9e30a2d1f76694601156d1a17ebfbc414ac7aae64d1cee87c20512cb`;
`kvm-read-only-controls.Ob5lvxWh.log`, SHA-256
`74372811aa9c13639079fae0db552a88abda777ef7ac44e03b2be5fbf6b57cfb`.
The complete offline RPC/context suite at `e6566221` also passed all **459
unittest cases plus seven source-policy controls across 22 scripts**;
`current-offline-suite.31oiqn_h/summary.json` has SHA-256
`c1b5a94f9a3aba6d733a25afd34c4e387af3a975eeca23fa685769244b6885a9`.
These are not native emulator/ART or capacity passes. Foundation remains
**NOT_READY** with every release and external gate intact.

## October 1 exact ART prerequisite and phone cold-readiness result

[ART 36861400094](https://github.com/p2pKit/P2pKit/actions/runs/36861400094),
source `a591ff3b2040c8f56c3525686b5a839aa54c32f3`, passed all **124 native
controls**, both actual JDK inspections and all three finalizations. The original
KVM gate failed `PREREQUISITE_MISSING`; maintained ART never ran. Read-only
metadata proves a non-symlink character `/dev/kvm`, mode **0660**, exposed SVM and
enabled `kvm_amd` nesting, but the nonroot job process neither owns the device
nor matches its group and has neither read nor write access. This identifies
an access blocker, not missing CPU virtualization. Process-local temporary
KVM-group access was requested separately and is **not yet approved or applied**.
The earlier actual API-24 software-emulator/APK handoff is unaffected.

Artifact `11160934651` has publisher SHA-256
`5a3b65bbe8c85dce56d3e32a89a516c537c6cbae096a2a61bb49705372b97dfc`;
complete logs `f3cdc7deb746918ef35fdc41cbf4fff2569d064acfecf6ee095a18bbcbe86d61`,
retained under `actions-36861400094/` in the existing evidence root.

[iPhone 36860697654](https://github.com/p2pKit/P2pKit/actions/runs/36860697654),
source `e656622193aca786c251df08dde778ec02633f44`, passed **125 native controls**
and finalized all eleven outer commands. The newly retained inner evidence
identifies the first failure precisely: **`boot-readiness` exceeded its original
120-second bound**. The framework producer succeeded in **390.443 seconds**,
with no retained ownership error/survivor; no XCTest or device build ran.
The boot monitor's later output still showed nonterminal migration/system-app
states through 132 seconds. That post-deadline output is not a readiness pass.
Exact simulator shutdown/deletion and outer native cleanup were verified.

The next bounded experiment moves this same **one cold boot before compilation**.
It removes producer-before-boot ordering as a variable and avoids another
expensive build if readiness is unavailable. It does not reuse an initialized
device, retry, warm up, change runtime/architecture or extend a deadline.
Concurrent CPU/memory attribution was not captured in the failed attempt, so
compiler-related pressure or GUI context is **not yet a verified root cause**.
The unrelated production RPC implementation is not implicated by these logs.

Inspection also found that the tool loop checked the deadline only while the
child was still running: a zero exit first observed after the deadline could
otherwise be accepted. The extracted `execute_tool` now checks the unchanged
bound for every observation, including a zero exit, and records observation end
on failure without fabricating process exit/retirement. It neither signals
children itself nor replaces native finalization. This strengthens the check;
it is not claimed as the cause of the observed boot timeout.

**79 offline controls passed**: 19 phone-controller, 25 handoff, 24 diagnostic
and 11 audit-session cases. New controls cover late-zero exit, unfinished child,
start failure, optional-result versus deadline semantics, and exactly one cold
boot before producer/XCTest. All existing native/phone inventories, bounds,
provenance, cleanup and binary-export conditions remain. Actual hosted
follow-through is required before claiming a phone handoff.

Evidence in `.git/rpc-bonjour-qualification-20260930.oOYgSoqr/`:

- `ios-handoff-36860697654-attempt1/`: artifact `11161559724`, SHA-256
  `b823463958be564030b40661de0c13beec4ac1f2149d4d5373ea8d7964b19817`;
  complete logs `b4e0b4b1e5eb730208a9702cac4632761b8335348f74cedfc7b6d9077376f30a`;
  independent review `177c2d85d0a38e1459dad97cc326d96c8134111d35327156f703b01f1d129bef`.
- `phone-cold-prerequisite-controls.pV3Gca2X.log`: 79 passing offline controls,
  SHA-256 `7acfd19b77a4f60fbdb24c484af4ec3f6670af3669c3265181ed6082b0d91975`.

Foundation remains **NOT_READY**. Failed phone/ART attempts are not promoted,
and every physical, mobile-capacity and release HOLD remains intact.

## October 1 complete offline follow-through and stale synthetic ABI fixture

The broader offline run exposed two stale **test-fixture inventories**, not a
production admission failure. `run-rpc-capacity-qualification-test.py` still
expected 124 Linux controls after three scripted Darwin-observation controls
were added to the maintained complete suite. It now requires the actual 127.
`audit-leaf-hooks-test.py` built a synthetic three-module checkout even though
the real ABI guard correctly requires all four Android libraries, including
RPC. Its copied inputs, exact fake graph request and twelve-edge graph now
include RPC. All missing-edge and nonzero-product negatives remain, including
each of RPC's producer/extractor/comparison edges. The production guard,
executor, ownership, architecture, native-test inventory and deadlines did not
change. No fake Gradle boundary is represented as an actual Gradle execution.

The corrected 27-case leaf-hook suite and 21 capacity-coordinator controls pass.
The complete nonduplicated follow-through comprises **721 passing offline
unittest cases across 26 suites**, including 45 scripted Darwin observations
(not native Apple execution). Layout, OSV coverage, 665 Markdown links, release
metadata, static Android ABI wiring and `git diff --check` pass. The first
`audit-host-test.py` invocation incorrectly put `TMPDIR` inside the checkout;
its fail-closed rejection was retained and the suite passed with fresh external
private temporary state. A mistyped nonexistent Darwin-test filename also
remains in the invocation log; the actual observation class was subsequently
executed, not counted as passing from that failed command.

Evidence under `.git/rpc-bonjour-qualification-20260930.oOYgSoqr/`:
`offline-followthrough-review-20261001.json`, SHA-256
`d6fcd49ae48f11c6064a5923c7fcf40ab1dabf2e822eaaf79868925c8705dd51`,
contains the exact suite paths, counts and individual hashes.
`leaf-fixture-followthrough.L5T6hhve/audit-leaf-hooks.log` has SHA-256
`7b6d8fb6f45b89a1ed5a1ad27a82103221679e8dff8eeb3e5cdfd919e03ca7fc`;
`final-offline-repository.9Kb1FbCS/repository.log` has SHA-256
`594ef9ffe914217500bc3e73a02fda1054e71bcaee2d2143a86e7c6dc82cb554`.
Capacity, native Apple readiness/cleanup, maintained ART and device-only gates
remain separate, open qualification work. Foundation remains **NOT_READY**.

## October 1 verified guest-core experiment and cold-phone follow-through

The complete hosted [capacity run 36857338712](https://github.com/p2pKit/P2pKit/actions/runs/36857338712)
at `4b6d8cbc` **failed** after **1,800.010260304 s**: **1,852,791** successful
responses, **451,209** original per-client permit refusals before invocation,
**1,029.322466 responses/s**, call p50/p95/p99 **723/1,452/2,146 ms**. There
were zero timer/worker misses, RPC errors, deadline errors or connection changes.
All 1,800 bins and client/host counters reconcile. Both JVMs consumed about
3.70 of four allowed CPUs; the two-plus-two guest-core split did **not** fix the
shortfall. No limits, deadlines, LAN checks or authentication are changed.

All **1,193 JVM tests**, 124 native controls, six real-socket correctness cases,
**20/20 one-MiB calls at concurrency two**, original retention and native cleanup
passed independently. The large workload took **4.123837424 s**, with
p50/p95/p99 **311/927/993 ms**, zero failures. The [full review and hashes](qualification-investigation-20260930.md#october-1-guest-core-split-failed-all-misses-before-rpc-invocation)
distinguish completed-call latency, CPU evidence and remaining causal limits.
The existing container's fresh `7c5ce336` capsule passed 124 native controls but
**failed** its original 125-second clock prerequisite: 368 coalesced expirations,
a 1.509449163-second maximum gap, available memory down to 1,544,020 KiB, and
severe balloon/reclaim pressure. Its 16 CPUs and roughly 20 GiB available at the
end do not negate the measured instability. **No build, dependency download or
load workload started.** Own evidence preservation and private-tmpfs unmount
both exited zero at 13:00:43 UTC; the retired native context will not be reused.
The linked review records the receipts, observation and preserved archive hashes.
No unrelated processes/files or provider security settings were changed.

Separately, [phone 36863266184](https://github.com/p2pKit/P2pKit/actions/runs/36863266184)
at `7c5ce336` failed its original 120-second cold-readiness bound **before any
framework compilation**. All 125 native controls, eleven outer finalizations and
exact simulator shutdown/deletion passed; no XCTest/device build/app export ran.
The [independent review](qualification-investigation-20260930.md#october-1-cold-phone-boot-before-compilation-also-failed)
preserves the failure and does not claim CPU or GUI-session causality without
measurements. The original full Apple workflows remain separate executions.
Foundation remains **NOT_READY**, with all release, physical and capacity HOLDs.

## October 1 ARM repeat failed, without a multicast regression

The [reviewed ARM follow-through](qualification-investigation-20260930.md#october-1-arm-follow-through-keeps-new-failures-open)
at `274f59cc`, run **36859931148**, passed 125 native controls and real multicast,
but failed the full profile at one core JVM test and failed native finalization
of the actual adapter cancellation case. The cancellation product's zero exit
does **not** pass cleanup: one RUNNING process remained unclassified following
environment-read failures, and survivor inventory is unknown. Sixty-five of
66 commands finalized; exact simulator/Terminal retirement was verified.
The previous source-specific ARM pass is retained, not used to erase this result.

The four focused Native methods/ABI, 28 Swift lifecycle cases and 88 ordinary
Swift unit/six UI cases passed independently. Missing full-profile JVM failure
details and unresolved-process context are now addressed with closed diagnostic
exports and regression coverage, not relaxed admission. The linked report records
the exact evidence hashes, remaining causal uncertainty and rejected bypasses.
No production networking, authentication, ownership or release gate is changed.

## October 1 fresh unsigned iPhone package independently verified

[36869803924](https://github.com/p2pKit/P2pKit/actions/runs/36869803924), source
`834c02c9a7819754dcf8a9a2db62306e3cfc9fe8`, completed successfully on actual
ARM/macOS 26/Xcode 26.5/iOS-26.5 simulator. All **128 native controls**, all
**seven unit/two UI methods**, one nested framework producer, both mandatory
nested provenance verifiers and **eleven outer finalizations** were checked.
Exact simulator shutdown/deletion, known empty survivors/pending observations
and unchanged source were independently verified. The original failed phone
attempts remain recorded; this is not a full Apple matrix or device-capacity pass.

The boot controller reports exit zero, enforcing its unchanged 120-second
monotonic checks before/after sampling. Its UTC command interval is **118.254 s**;
the diagnostic observer's `finish()` reports **125.825906 s**, with an unobserved
tail of **11.288186833 s**. These observations have different endpoints/clocks.
No decision-time monotonic value was exported, so the exact difference cannot
be independently attributed to scheduling or clock adjustment. It is not
evidence of an extended readiness allowance or a demonstrated boot fix, and
does not settle the independent Intel timeout. Nine contemporaneous intervals
had 21,290 user / 12,047 system / one idle tick; matched role CPU included
83.559 s in `other-readable`, 18.791 s in `lsd`, 18.189 s in `diagnosticd`,
13.392 s in `SpringBoard` and 4.150 s in Python. Unmatched/unreadable lifetimes
remain a coverage gap; these aggregates do not identify a unique boot cause.

Framework production, phone unit/UI execution and the unsigned device build
took **861.785 / 412.308 / 369.253 s** respectively. The exported archive is
**4,661,051 bytes**, SHA-256
`f1da24d09a771be16f1c4137df056ae551a0c5efa53c23ca6e923d32383c8e7a`.
Independent inspection checked every archive entry and all **three** Mach-O
images: the launcher, preview dylib and 19,655,216-byte implementation/debug
dylib are arm64 iOS platform 2, minimum 15.0, SDK 26.5, with no code-signature
command. The implementation is not missing merely because the launcher is
small. No profile, signature directory or symlink is exported. The unsigned
`.app` is **not an installable IPA**; owner signing and device trust remain
external prerequisites. Exact download/hash instructions are in the
[device handoff](device-testing-handoff.md#iphone-installation-boundary).

Evidence in `ios-handoff-36869803924-attempt1/` under the existing private root:

- Package artifact **11167623797**, publisher ZIP SHA-256
  `9c58d5cf6e36a3f4864a28befca5263c69ac30fe87f02895172e3e58e4892ff1`.
- Evidence artifact **11167299051**, publisher ZIP SHA-256
  `d2ddbd6b0f2209d04b4e682a3b6fbf920e8a473548208bd360c228b6457b0d52`.
- Complete logs `1a55a2cd45ca5acb8ea29fa8b845c34004e5b9103b220d58d64c4c4205a95b35`;
  initial source/count/receipt review
  `8d9172ce23af67d16fb729da91cc0db8655d17c825cce2878ea36fc4447baddd`.
- Supplemental all-image review `archive-content-review.json`, SHA-256
  `b3f5ff96613e70b47038cb1e44cc7b26f5229dc07a581c7731bd99930c062a64`,
  explicitly qualifies the earlier review's speculative scheduling attribution:
  the exact timing difference is unproven, not a causal finding.

No signing material or private evidence was uploaded. Release Foundation remains
**NOT_READY**, with every physical, mobile-capacity and release HOLD intact.


## October 1 fresh complete native ARM follow-through passed

[Run 36867809415, attempt 1](https://github.com/p2pKit/P2pKit/actions/runs/36867809415),
source `991682e174f7ba1e5a94064e42d3ca761bce422d`, completed the original native
ARM/macOS-26/Xcode-26.5 profile on iOS-26.5 simulator without substituting Intel,
a mock or a skipped requirement. Independent review reconciled **all 20 enabled
platform tasks**, **3,036 JUnit passes / zero failures or errors / the same one
pre-existing ignored LAN diagnostic**, and **393 suites**. Actual Native counts
were core **794**, RPC **45**, RPC sample **9**, and LAN **202**.

All **128 native ownership controls**, real multicast, ABI, strict Dokka, SBOM,
framework production/provenance, Swift API checks and **88 Swift unit/six UI
methods** passed. The dedicated ARM gate independently executed **four Native
helper methods plus ABI**, **28 Swift lifecycle methods** and **one actual
production-adapter cancellation method**. All **68/68 commands** finalized with
zero pending observations and known-empty survivor inventories; exact simulator
and Terminal retirement and unchanged source were verified. Swift readiness's
recorded product interval was **102.813 seconds** under the original 120-second
bound. No deadline or production/ownership policy changed.

The ARM Bonjour preference domain was absent. Its explicit
`ARM_ABSENT_DOMAIN_NO_CHANGE` path performed **no configuration write** and
verified identical absence before/after; this is not a claimed restore of a
setting that never existed. The earlier `274f59cc` run's core JVM failure and
unclassified Darwin lifetime remain failed evidence. The diagnostic-only
follow-through did **not** reproduce or uniquely explain that earlier lifetime;
this new execution supplies its own passing evidence, not a retrospective fix.

Evidence in `actions-36867809415/` under the existing private evidence root:
artifact **11169197247**, independently verified publisher SHA-256
`328bb209837db4b0bec0febb29a2d9609106780bdb797c4e8c4d97b0b173a5b4`;
complete workflow logs
`a49f1949b60998c67e73f3b4b5f8fd9e63c551f4789aad8bf4f867d424aa0054`;
`independent-review.json`
`f0ba3175fb291376eb14d904471b721e5b27185beafb38a0dc1b4ce1d0ed8097`.
All 17 workflow log entries were read. This is native ARM simulator evidence,
not Intel readiness, physical LAN, mobile capacity or a release qualification.
Foundation remains **NOT_READY** with all external HOLDs intact.


## October 1 capacity image attempt completed with two distinct failures

[36872767997, attempt 1](https://github.com/p2pKit/P2pKit/actions/runs/36872767997),
source `0d42c8ca89d2c40ac961c6562db36afaf2a4c311`, finished both requested cells.
Neither passed capacity; a green prerequisite is not a successful workload.

**Ubuntu 22.04:** all **127 native controls** and all five command finalizations
passed. `:p2p-core:jvmTest` produced **858 passes / one failure**, specifically
`SendErrorContractTest.sendFileOfferWriteFailureSurfacesAsTypedTransportFailureWithCausePreserved`
at the original exact-cause assertion (line 349). LAN's **246 JVM cases** passed;
the aggregate attempt was **1,104 passes / one failure**. RPC/sample tasks did
not finish, and **no correctness, large or steady workload ran**. The actual
unexpected cause was not included in the original closed export; the local
fixture investigation must not be presented as a uniquely proven historical
exception. This guest reported Intel family **6**, model **207**, stepping **2**,
two cores/four logical CPUs and kernel **6.8.0-1064-AZURE**.

**Ubuntu 24.04:** all **1,193 JVM cases** (859 core / 246 LAN / 46 RPC / 42 sample),
127 native controls, six real-socket correctness cases and the independent clock
prerequisite passed. The unchanged steady workload completed:

| Measurement | Actual result — FAIL, not capacity qualification |
| --- | ---: |
| Required / actual scheduling duration | 1,800 / 1,800.000687215 s |
| Expected calls | 2,304,000 |
| Dispatched / client replies / host accepted / host completed | 1,891,141 each |
| Misses, all `PermitUnavailable` before invoking RPC | **412,859** |
| Timer-late / worker-late / RPC errors / deadline errors | **0 / 0 / 0 / 0** |
| Throughput | 1,050.6334877716154 replies/s |
| Client-call p50 / p95 / p99 / maximum | 503 / 1,585 / 2,403 / 7,320 ms |
| Scheduling p50 / p95 / p99 / maximum | 2 / 4 / 8 / 31 ms |
| Host / generator process CPU | 3,132.59 / 3,478.62 CPU-s |
| Sampled outstanding / handler queue maximum | 976 / 0 |
| Whole-series host maximum RSS / native threads / JVM threads | 890,916,864 bytes / 174 / 158 |
| Host maximum retained records / accounted payload | 65,151 / 32,723,212 bytes |

All 1,800 bins reconciled with the logical-slot, dispatch, client-completion and
host counters. The original eight outstanding permits per client refused every
miss **before an RPC existed**; zero RPC errors is consistent with all admitted
calls completing. No independent retry counter exists; policy remains
`RecoverOnly`. Handler queue zero is not proof that socket/coroutine work never
queued. These latencies describe reduced admitted load, not the requested full
arrival rate; there is no approved numeric p95/p99 cutoff to invent.

No observed generator balloon/reclaim, major-fault, allocation-stall or CPU-steal
counter grew. Maximum generator/host safepoints were **19.120921 / 66.028622 ms**,
with none at least 100 ms. Both JVMs consumed approximately **3.673 CPU-seconds
per second** in the explicit two-plus-two guest-core split. This guest reported
AMD family **25**, model **1**, stepping **1**, two cores/four logical CPUs and
kernel **6.17.0-1022-AZURE**. Different hardware as well as kernel/image prevents
attribution to the image alone; the 22.04 workload never ran. There is no
justification here for another unchanged 24.04 rerun or a security-policy change.

The separate one-MiB request/reply workload completed **20/20 at concurrency two**
in **4.186153851 s**, p50/p95/p99 **299/988/1,027 ms**, with zero RPC failures.
All three real-socket workloads independently verified original retention,
zero final connections/running/queued/records/payload counters, identity retirement,
worker reaping and all native finalizations. The seven coordinator commands
also finalized. Neither that cleanup nor the large-payload pass repairs the
failed full-rate gate. Same-host virtual Ethernet is not physical LAN or mobile
hosting capacity.

Evidence in `actions-36872767997/` under the existing private evidence root:

- Ubuntu 22 artifact **11167823090**, publisher SHA-256
  `e026b72394dcb7a79eb7acb6fde685e3321c917f8943d774a320a705e3f67215`.
- Ubuntu 24 artifact **11171210690**, publisher SHA-256
  `09f68ef0e3a968ac25cfb58cbc22227926990c3c9a5b5686b0ba5a20de1ec339`.
- Complete workflow logs: `0e8ae0fb21c6a532c2a6d1f7ee0c7914f4075a42aee2d7236fdf09be23b4eca6`.
- `independent-image-review.json`:
  `ea6f82e6af1e96e6f7203f96083d5ca5d85e8be6ca136e58714e3a5c2fa08ea7`.

All failures remain preserved. Foundation stays **NOT_READY**, with every HOLD.


## October 1 Intel cache-preparation experiment prepared, not a readiness pass

The [scoped investigation](qualification-investigation-20260930.md#october-1-scoped-intel-runtime-cache-preparation-experiment)
uses Apple's documented update-if-missing operation for **only the selected
runtime**, before creating a device, then attempts the unchanged **single
120-second cold boot**. It neither forces/deletes caches nor changes production,
security, ownership, full matrix selection or readiness bounds. The complete
runtime definition must remain unchanged; failed/unowned preparation blocks boot.

All **205 focused offline controls** and the repository checks passed. Native
Intel execution is still pending, and updater success alone cannot establish
missing-cache causality or any product pass. This experiment does not replace
the complete Intel gate. Foundation remains **NOT_READY**, all HOLDs preserved.

## October 1 file-writer fixture clock reproduced and corrected

The Ubuntu-22 prerequisite failure was the original exact-cause assertion in
`SendErrorContractTest.sendFileOfferWriteFailureSurfacesAsTypedTransportFailureWithCausePreserved`.
The exported hosted artifact did not contain the unexpected cause; no particular
historical exception is claimed as proven. The unmodified 15-method class passed
locally, so an unchanged rerun alone did not establish a fix.

A directed regression suspends the actual independent file-offer writer for
100 real milliseconds while retaining the fixture's original virtual keep-alive.
Under `runTest`, that wait advanced the session clock from **0 to 1,200,000 virtual
milliseconds**, terminating the session before the writer finished. The directed
17-method attempt had **16 passes / one failure**. Preserving `backgroundScope`
in a second candidate still produced the same clock jump and failure; it was
not accepted as a correction. Both failed attempts and their successful cleanup
remain preserved.

The correction is **test-only**. The three real-file-worker boundary cases use
the existing `StuckReconnectWatchdogTest` idiom: an independent
`TestCoroutineScheduler`, real `runBlocking` settlement, and `runCurrent()` only.
No future virtual deadline is advanced while waiting on an independent worker.
Settlement and fixture cancellation/join have a five-second real bound. All
original cause/kind/phase/retryability/value-copy assertions remain, with new
zero-clock/connected-state assertions. A separate regression explicitly advances
virtual time and still requires keep-alive expiry. Production timers, transport,
exception handling and cleanup policy are unchanged.

The immutable local diagnostic source was
`6c53eed3d9c668c7f6f69fab2eb78297ebd2746a`, tree
`2b6666b10802437894f2e410242f0c2699d31d19`; the tested file blob
`36e98139f9e1415f3e1b92c904012899d4802f04` matches the committed correction.
In a fresh private mount/PID namespace with dropped capabilities, **127 native
ownership controls**, the **17-method regression**, then **all 861 core JVM
tests in 98 suites** passed. All five command receipts independently finalized
with unchanged source and no discovery errors/survivors. Evidence preservation
and unmount both succeeded. This is Linux JVM evidence, not Apple/ART/capacity.

Commands were the narrow `:p2p-core:jvmTest --tests
dev.p2pkit.core.internal.SendErrorContractTest`, followed by the unfiltered
`:p2p-core:jvmTest`; both used `--no-daemon --no-build-cache
--no-configuration-cache --rerun-tasks --dependency-verification strict
--max-workers=2 --no-parallel --console=plain --no-configure-on-demand
--warning-mode=fail --stacktrace`, through the unchanged native executor with
an 1,800-second outer command bound. No workload gate was run or relaxed.

Private evidence under `.git/rpc-bonjour-qualification-20260930.oOYgSoqr/`:

| Attempt | Archive SHA-256 | Independent review SHA-256 |
| --- | --- | --- |
| Directed red, `send-error-red.se_iksu4` | `a78c941c2d655662926dd1b26199a9e8511993b5f9c0b915016fdcd00167fb7f` | `4dc16329e128e09df9b046ed434eb0a912635dfe0f61addda17558e0d3983f70` |
| Failed background-scope candidate, `send-error-green.x_9oc0g5` | `fd3dd928fcdf1f940d1066b76f4f1d1097d2b08cfba362731f870e83db87e083` | `6704b03e80e4704070e3eb59e6511214d7e27ea4a622062706e8ff7eb24d043f` |
| Corrected/current-work scheduler, `send-error-manual.mq33ud9b` | `52fc15d5a348dee3b448b4d387f32176e6275ac780cbbea54beea11ac5b0f923` | `4b0d14f6611a13ea8aa429e8a8ae448cdbda5e7c8fa584319bebda982b6b70e6` |

Each XML is checked against its own invocation receipt; the narrow and full
suite's copies are not double-counted or assumed byte-identical. The Ubuntu-22
workload still needs an actual complete execution. Foundation stays **NOT_READY**.

## October 1 Intel offline prerequisite overhead corrected without a longer bound

[36880138639](https://github.com/p2pKit/P2pKit/actions/runs/36880138639), source
`ce68b71465b13910e9d6ff9196ae84193d02143b`, failed **before native admission or
any simulator operation**. All eleven offline suites reported success, but their
combined workflow step exceeded its original **three-minute** bound. The step ran
from 14:55:25 to 14:58:32 UTC and Actions rejected it. There were **zero** native
commands, cache updates or boot attempts; this does not test the cache hypothesis.
All 16 log entries, including the aggregate log, were read. Complete logs hash:
`696119296c9da23d95091e18b93b76ecc10ed926c29db98d90b4f5136b48a092`;
artifact **11170403239** publisher ZIP hash:
`b9b96b8c6d60b3a3adfebcf5c96153fcaa800e1242aedaac3b7b44d60786cd14`.

Local profiling identified repeated **unused** source indexing in the diagnostic
exporter. One unchanged Terminal privacy-control method called `public_summary`
33 times; even an empty failure list reparsed/walked the 127-control Python AST,
and empty product diagnostics rescanned Kotlin methods/locations. The profiled
method made **32,022,255 calls in 14.178 s**. This was source/indexing work, not
simulator readiness, a native resource lifetime or a production RPC failure.

The correction indexes source only when diagnostic fields reference it, once
per validation, with **no persistent cache**. Every nonempty source-bound export
still rereads source and enforces the original identifier/location/schema checks.
Empty observations grant no source, native or product admission. Four regression
controls cover absence of unnecessary reads, wrong types, refreshed method
membership after source changes, and one location scan per validation. The new
checks failed on the original exporter and pass after correction. No assertion,
offline suite, inventory, architecture, ownership rule or timeout was removed.

The same profiled method now makes **139,720 calls in 1.049 s**. All **286 offline
controls across the exact eleven workflow suites** passed sequentially in
**13.502 s locally**. Those times are local diagnostic observations, not a claim
about native Intel readiness. The original three-minute step and 120-second
fresh-simulator deadline remain unchanged. Local profile paths are
`offline-overhead.mQ53H1v2/` and `offline-overhead-after.REYnwbbn/` under the
existing evidence root. The complete-suite review hash is
`568bbf3d3c2a4f8f79c0bce454c53358be7daf565d3e1ef9dfb503631c8c2adf`.
The earlier mistargeted `cProfile -m` invocation failed unittest discovery; it
is retained separately and not counted as a test pass.

## October 1 Ubuntu-22 workload follow-through requested separately

The explicit `[rpc-capacity-ubuntu22]` marker selects only the Ubuntu-22 cell
that previously stopped before workload execution. Original Ubuntu-24 defaults
and the two-image comparison marker remain available and unchanged. Source,
native architecture, exact image, exclusive marker/mode binding, fresh artifacts,
CPU-placement evidence and every original workload/cleanup gate remain required.
The **65 focused runner/coordinator/CPU/evidence controls** passed. This avoids
another unchanged Ubuntu-24 load run; it is not a passing comparison or capacity
result. The full 30-minute Ubuntu-22 run still has to execute and be reviewed.
No unavailable Android/iPhone or physical-LAN gate is replaced. Foundation
remains **NOT_READY** with every HOLD.

## October 1 Ubuntu-22 system Python prerequisite identified

[36882114812](https://github.com/p2pKit/P2pKit/actions/runs/36882114812), source
`828ece59a795bb7db0bb916856282ccf8909b037`, passed all **127 native controls**,
**1,195 JVM tests** (861 core, 246 LAN, 46 RPC, 42 RPC-sample), the distribution
producer and all six outer command finalizations. Thus the corrected file-writer
fixture also passed in the previously failing hosted image. There were no test
failures or skipped JVM cases.

The next phase failed **before any RPC traffic**. Its namespace log was exactly
82 bytes with SHA-256
`9afd75d1fb960e5a220bde462a94078c907d2b058a18eb8eee19cd0f1a5a30fc`.
Reconstructing the source's fixed error prefix and standard exception text
matched both the recorded length and digest:

```text
Same-host virtual-network experiment failed: module 'os' has no attribute 'setns'
```

Both workers' independently recorded 69-byte logs likewise match the exact
`Worker was not released` message and digest
`3182617f13980b6ccea1f18e9562edac196366a08e35baf7029c2541b3ab034d`.
No local-native admission, client or host receipt exists. The bootstrap's missing
Python API closed the gates before namespace coordination; namespace exit 125
is not native cleanup or product evidence. The conservative
`OWNERSHIP_UNPROVEN` phase stays failed, with large/clock/steady blocked.
This is an interpreter prerequisite defect, not a failed RPC request, JVM
capacity result or production LAN rejection.

Python documents `os.setns` as added in **3.12**. The Ubuntu-22 job had relied on
its older system interpreter. The smallest correction explicitly selects native
x64 Python 3.12 using the official, commit-pinned `actions/setup-python` action.
A preflight runs it without `LD_LIBRARY_PATH`; the existing privileged bootstrap
environment still refuses loader overrides. Both the hosted coordinator and
the standalone namespace setup check the actual setns/pidfd APIs **before state
or worker creation**, respectively. No ctypes/syscall compatibility shim,
namespace substitute, UID change, ownership waiver, production setting,
workload limit or timeout was introduced. Selecting a supported interpreter is
preferable to maintaining another privileged native-call implementation.

Three new offline controls failed against the absent prerequisite check, then
passed after correction; all **158 focused offline controls** passed. These are
not real-network execution. The earlier complete offline follow-through was
also independently reconciled: **744 controls / 27 suites** passed. Its incorrect
unittest positional-selector invocation remains preserved and is not counted;
the 45 scripted Darwin observations used an explicit importlib/unittest selector,
not a native-Apple claim. Review digest:
`91a09a8eb18c6cfaed898ee12fe4d45c49ac7305c0c942cf2e3ba694a4d539c0`.

Private evidence under the existing root:

- `actions-36882114812/`: all **17** workflow log entries read; complete log ZIP
  `4bec38707919bf7cf37f5f20126d043b93d7e1e9e01b0a841b50bafb47c6f67b`.
- Artifact **11172426364**, publisher ZIP SHA-256
  `3c13fc6e20983d8075ba37ec7bffa8615ab5d4e89a1b5fde8df82822d86e15ff`.
- `independent-prerequisite-review.json`:
  `583ad5427f2ec47d50e6206caa12634752e1ba28ea4055e1f872037a89f93da5`.
- `capacity-python-red.h20ccw_e/` and `capacity-python-green.razyal6_/` retain
  the actual regression outputs. The next Ubuntu-22 attempt must still complete
  every original workload; no past failed run is promoted.

The correction's complete follow-through then passed **747 offline controls /
27 suites**, including every original negative admission/privacy control.
`offline-python-followthrough.1_c7jl5v/review.json` has SHA-256
`3f82e165a753e61f91bc3dc05c9c43d38215145699d205908da803796ee3fa0a`.
All repository layout, lock/provenance coverage, **671** Markdown links, release
metadata, RPC workflow YAML parsing and whitespace checks passed. No project
source, security model or native ownership implementation changed in this
interpreter correction; native-ARM follow-through of the earlier common-test
fixture correction is requested independently of the Ubuntu-22 workload.

## October 1 Intel runtime inventory timed out before the cache experiment

[36882114824](https://github.com/p2pKit/P2pKit/actions/runs/36882114824), at the
same `828ece59` source, passed the original offline prerequisite, all **128 native
controls**, real multicast and **124 Intel Android-host tests**. The earlier
three-minute offline-overhead issue did not recur. All scoped Bonjour changes
were restored and the job-owned Terminal/script were retired with unchanged
source.

The **first** `xcrun simctl list --json runtimes` command then exceeded its
unchanged 120-second limit: product interval **120.147 s**, product exit **-15**,
outer exit **125**. It emitted **zero bytes** to both stdout and stderr. The
receipt records exactly one error (`Product command timed out`), zero discovery
errors, zero pending Darwin observations, a known-empty survivor inventory and
stop exit zero. The gate's aggregate `OWNERSHIP_UNPROVEN` label must not be
misreported as proof of an unresolved native resource lifetime: its full
finalization predicate also requires an empty error list, which the timeout
correctly fails.

No cache-update command ran, no simulator was created or booted, and no cold-boot
or full Intel qualification result exists in this attempt. Consequently it does
**not** establish whether the selected-runtime cache operation repairs Intel
readiness. It establishes a still-earlier, bounded CoreSimulator inventory
prerequisite failure; the internal reason for the silent inventory stall is
not exported and is not asserted as known. Neither reraising a bound nor
reclassifying a timeout/skip as success is permitted.

All complete workflow logs and the source-bound public summary are preserved in
`actions-36882114824/`. Artifact **11173800737**, publisher ZIP SHA-256:
`93d8eac87b6458be9679efd71066500c22a11a51e5570bcaf45e9701f811bbcd`;
complete logs:
`b9352746464a6ff74409f0c3fb84aeba2fea7258e1974b384d413738bd0e596f`.
The diagnostic pass counts cannot replace the original complete Intel lane or
the dedicated native-ARM gate. Foundation remains **NOT_READY**, all HOLDs intact.

## October 1 silent Intel inventory observation prepared

The [bounded inventory observer](qualification-investigation-20260930.md#october-1-observe-the-silent-intel-inventory-within-its-original-deadline)
adds contemporaneous, closed CPU observations to only the explicit Intel runtime
diagnostic. It executes the same single inventory command within the same
120-second native-owned bound, with no retries, service changes, privileged
inspection or alternative architecture. All **346 focused offline controls**
passed. No production implementation or ownership/readiness policy changed.
Actual native observations and any proven fix remain pending.

## October 1 Ubuntu-22 follow-through stopped at the LAN fixture prerequisite

[36884703517](https://github.com/p2pKit/P2pKit/actions/runs/36884703517), source
`0bee78b93a8e129848fe1af86dd82e1df051a778`, passed selection and clean-loader
verification of Python 3.12, the offline controls and **127 native controls**.
All five invoked commands independently finalized with unchanged source.

The first product failure was
`BoundedBlockingHandleCreatorTest.interruptedWaiterReturnsBeforeCompletedOrphanCleanupFinishes`
in `:p2p-transport-lan:jvmTest`: **245 passes / one failure**. No other required
JVM task completed, and the producer, correctness, large and steady phases
remained blocked. This is **not** another completed capacity measurement or a
reappearance of the nine Intel Bonjour discovery failures. The closed historical
diagnostic identifies the method but not its failing line/exception; an exact
historical exception must not be invented. A directed fixture/lifecycle
investigation is required before rerunning the workload.

All **19** complete workflow log entries were read and preserved privately in
`actions-36884703517/`. Artifact **11174461599**, publisher ZIP SHA-256:
`18db430ab17ca11fd1f44d047ce099be2cd74094472096545b0b38a110faa78b`;
complete logs SHA-256:
`38812de7c3629f6365b5a3a3affacffa1186898e90d4e429a55f236b12b8e170`.
No failed attempt is promoted, no test/limit is removed, and Foundation stays
**NOT_READY**.

## October 1 cleanup notification is not construction-admission retirement

The `BoundedBlockingHandleCreatorTest` investigation found a **fixture race**:
`closeOrphan` signalled `cleanupFinished` (or `orphanClosed`) inside its callback,
but production `cleanOrphan` clears its active `Cleaning` admission **after that
callback returns**. Receiving the notification does not establish retirement.
The final recovery `create()` could therefore correctly receive `IOException:
blocking handle creation unavailable: previous attempt is Cleaning`.

The unchanged fixture, even with 256 repeats, passed locally; that was not
accepted as proof of a correction. A directed attempt added a 100-ms suspension
after the notification but before callback return, leaving production unchanged.
Its single case failed at the final recovery call with that exact `Cleaning`
exception. The historical hosted export identifies the method but lacks its
exception/line: this independently reproduced race is **not** represented as a
uniquely proven historical exception.

Both JVM and Android-host fixtures now retain and join the **exact owned
construction/cleanup Thread**, with a 1,000-ms bound and an assertion that it
retired, before checking recovery. `finally` releases fixture latches and joins
the owned workers on failure. Original one-second latches, interrupted-caller
return, typed failure and refusal of parallel construction remain unchanged.
There is no name/PID sweep, retry of `create()`, production change or longer
deadline. Regression cases retain all assertions through 256 repetitions, the
directed after-notification suspension, and a deterministic negative check that
admission **must remain closed** until callback return. A closed diagnostic
marker recognizes only this exact source-owned exception, never arbitrary text.

Immutable candidate `21dd620dcff3d38cd7addd60bcd2c018467c028d`, tree
`43870f7da70e42de08e97918d3f685af2757e06f`, passed **127 native controls**, then
**eight JVM/seven Android-host targeted methods**, then the unfiltered **1,324
regression cases**: core JVM 861, LAN JVM 249, RPC JVM 46, sample JVM 42, LAN
Android-host 126. There were zero failures, errors or skipped cases. All five
command finalizations, unchanged source, empty survivor inventories, evidence
preservation and private tmpfs unmount were independently verified. The four
tested file blobs match the submitted correction. This is Linux JVM/host-test
evidence, not Android ART, native Apple or capacity qualification.

The narrow command selected `BoundedBlockingHandleCreatorTest` in
`:p2p-transport-lan:jvmTest` and `:p2p-transport-lan:testAndroidHostTest`; the full
command ran those tasks unfiltered plus `:p2p-core:jvmTest`, `:p2p-rpc:jvmTest`
and `:p2p-sample-rpc:jvmTest`. Both retained `--no-daemon --no-build-cache
--no-configuration-cache --rerun-tasks --dependency-verification strict
--max-workers=2 --no-parallel --console=plain --no-configure-on-demand
--warning-mode=fail --stacktrace`, through the unchanged native executor and
original 1,800-second command bound. **756 offline controls / 28 suites** also
passed (including 45 explicitly scripted Darwin observations, not native Apple).

Private evidence under the existing evidence root:

| Attempt | Archive SHA-256 | Independent review SHA-256 |
| --- | --- | --- |
| Unchanged + 256 repeats, `creator-race-original.s9zpt5ki` | `ce4c342e35b085bc96a07bb44474255596bd58baddfb36dee31634fba1393e00` | `97386f5157d7ab69bf89ed254283828d10d813b65f190214294c2f967ae7037b` |
| Directed red, `creator-race-directed.pxfvxx6a` | `20b6717aa3a71222f13e6506ae1dffcfc38b2cb3630171cfb4ee342105cb55f8` | `c5256dd519b3bf90fd196c6f8176456008e511f1f6bf5d68778f75b79e50ef9a` |
| Corrected full regression, `creator-retirement-final.v2p_1d3z` | `c6f00d69ec59dcf6192627708c5ec3838fe065d1de368b299a5b5d37e39337e7` | `3de5974dde6ac7723a49246dca5ab558da9020b9802fbd60146f9e7c8e9e8108` |

The first reviewer invocation incorrectly assumed static HTML CSS/JS entries
were retained again. Its failure is preserved; the corrected reviewer reconciles
all six unchanged assets against their earlier retained bytes and still requires
each invocation's actual XML/hash. No test result is omitted or double-counted.
The full Ubuntu-22 workload is requested only after this correction; an actual
complete 30-minute result and resource review remain required.

## October 1 Intel inventory observations and separate Terminal finalization failure

[36886491406](https://github.com/p2pKit/P2pKit/actions/runs/36886491406), source
`5361977c2b2c7e9e0d612c7dd858f2360acfa7a9`, passed **128 native controls**, real
multicast, **124 Intel Android-host tests** and `xcodebuild
-checkFirstLaunchStatus`. The first inventory command still timed out at
**120.106 s**, product exit **-15**, outer exit **125**, with zero stdout bytes.
Its only receipt error is `Product command timed out`; discovery errors,
pending observations and survivors are zero, the survivor inventory is known,
and stop exited zero. **15 of 16** commands finalized. This cannot be promoted
to native admission success for the timed-out invocation.

Eleven contemporaneous CPU intervals cover **110.975421523 s**. Across the ten
matched intervals after startup, `simctl` accumulated **203,377 CPU ns** and
CoreSimulatorService **142,988 CPU ns**. Aggregate host busy ticks were **60.493%**;
229–253 processes were unreadable at each observation. The final approximately
nine seconds before timeout were not observed. These numbers establish an
almost-idle matched service/client wait, **not** a uniquely identified IPC,
disk, cache, permission or CPU-saturation cause. A missing child exit remains
`null`, never zero. No runtime-cache update, device creation or boot occurred.

The Bonjour preference and daemon configuration were independently restored
with matching original hashes. **Terminal cleanup did not pass**: its exact
native child finished and script child was reaped, but the retained application's
ordinary Quit did not complete in 30 seconds (`QUIT_COMPLETION`); the command
file was correctly retained. Do not confuse this separate application lease
failure with the inventory receipt's known-empty product survivors, or claim
all environment cleanup succeeded. No forced quit or security-policy change
was attempted.

All **17 complete log entries** and the publisher artifact were independently
read and verified in `actions-36886491406/`. Artifact **11175691054** ZIP SHA-256:
`44c4e5336d08538ee62563a9763bc7a23421da84635014aff3658757198c907e`;
complete logs `de6707198cb06e3d6ef8189bdcd465971262ca6736b7e67f0a059d6a6be41277`;
independent review `8cc82db31cd45cf1f767a8ecdbac446cc05414f3620b7593336d04630e9f09a8`.
Both unresolved failures remain open; neither repeats the original nine Bonjour
failures. Foundation remains **NOT_READY**, with all HOLDs intact.
