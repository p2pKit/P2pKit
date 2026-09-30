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

## Current September 30 disposition

| Requirement | Verified disposition |
|---|---|
| Original Apple ownership admission | **Resolved**: all 122 controls passed on both required native architectures after process-local audit-session isolation. |
| Dedicated ARM cleanup/cancellation | **Passed at `c22aeebb`**: four exact Native methods plus ABI, 28 Swift lifecycle methods and one actual adapter cancellation case; all 63 commands finalized. |
| Complete Apple matrix | **Not passed**: multicast blocks full profiles; Intel repeats nine Native discovery-wait failures and an independent clean-boot System App readiness timeout. |
| Direct VPS↔Mac LAN capacity | **Blocked topology**, not silently reclassified as LAN: Mac's active multihoming and provider NAT remain; production admission is unchanged. |
| Same-host 128-client steady workload | Three complete 30-minute attempts, **all failed scheduling acceptance**; instrumented latest: 2,217,973 replies, 83,805 timer-late slots, 2,222 worker-late slots, zero permit rejections/RPC errors. See the [attribution investigation](qualification-investigation-20260930.md). |
| Same-host large-payload workload | **20/20 passed again at `51445086`**, one MiB each way at concurrency two; 65.795-second idle retention and native cleanup verified. |
| Separate real-socket correctness | **All six cases passed again at `51445086`**, including uncertain close outcome, cancellation, timeout and independent-client isolation; 65.153-second retention and native cleanup verified. |

These source-bound results are detailed below. Same-host virtual Ethernet is
not physical-LAN, cross-device or mobile-host qualification. Release Foundation
remains **NOT_READY**, with all existing HOLDs intact.

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
