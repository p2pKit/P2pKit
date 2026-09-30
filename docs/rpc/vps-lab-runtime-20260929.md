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
