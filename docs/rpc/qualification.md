# RPC verification and capacity qualification

## Status and boundaries

**Latest scoped results:** the [RPC lab execution](vps-lab-runtime-20260929.md)
passed all eight actual API-24 ART/Keystore/Activity controls at `715680f0`, with
fresh native admission, both same-source APKs, independently verified signatures
and owned shutdown. The separate iPhone candidate `b6c5e197` passed nine
app-hosted XCTest methods and produced an unsigned arm64 app, **not a physically
installable signed package**. Both Linux and Intel Mac also passed an actual
minimal ART probe on a booted API-24 software emulator. These are scoped runtime
results, not the maintained ART suite, deployed LAN or capacity qualification.
The former Mac topology failed the unchanged strict JVM LAN admission; that
workspace has since been owner-deleted. Its Mac-only app/original XCTest bundles
were not recovered, while earlier bounded exports and source remain on Linux.
The authorized [same-host real-transport fallback](same-host-lab.md) has now
completed **three full 30-minute, 128-client runs, all failed acceptance**.
The instrumented `88f81e6b` run returned **2,217,973 successful replies, zero RPC
errors, but 86,027 pre-invocation missed slots**: 83,805 timer-late and 2,222
worker-late, with zero permit rejections. The earlier 69,538 misses were combined
and cannot be retrospectively divided. The [attribution investigation](qualification-investigation-20260930.md)
records independent guest balloon/reclaim/timer evidence and why no production
RPC change is justified; the unchanged 2,304,000-call gate remains unqualified.
The separate **20/20 one-MiB request/reply calls at concurrency two passed**
on this local virtual-Ethernet topology. The revised `a15aa78f` and instrumented
`88f81e6b` runs each passed the actual 65-second idle-retention and native cleanup
checks. The runtime record retains
all failed steady attempts and latency/resource measurements; none is physical
LAN, mobile or capacity qualification. Completed-call percentiles at reduced
admitted load do not prove latency at the full offered load.
The separate `481bf772` candidate also passed **all six real-socket correctness
cases**, 65.5-second retention/native cleanup, and **1,169 JVM tests**. The close
fixture now distinguishes retained connection state from the existing local
call-admission error; production behavior and deadlines are unchanged.

Both required hosted Apple architectures subsequently passed all **122 native
ownership controls**. On actual ARM/macOS 26/Xcode 26.5, the corrected `c22aeebb`
run passed the scoped 1,041-case Native profile, 88 Swift unit/six UI cases,
**all four focused Native-helper methods plus aggregate ABI, all 28 focused
Swift lifecycle methods and the one actual adapter cancellation test**.
All 63 commands finalized, with exact simulator retirement and unchanged source.
This resolves the original admission and focused ARM cleanup blockage; the job
still **failed multicast**, leaving the full platform profile blocked. The
separate Intel/macOS-15/Xcode-26.3 `e28f50a8` run passed admission/toolchain but
failed multicast, scoped Native assessment and the original 120-second Swift
readiness bound. Those unresolved product failures are not filled in with ARM
or supplemental VPS results. See the [source-bound results](vps-lab-runtime-20260929.md#corrected-native-arm-execution-focused-ownership-gates-passed).

**Earlier, the September 29 supplemental Intel VPS candidate `62716271` passed native
admission (122 controls) and all six planned phases: original-bound readiness,
all 20 strict platform tasks (2,959 passes, zero failures/errors and one
pre-existing ignored diagnostic), fresh Apple framework provenance, all 88 Swift
unit/six UI methods, fresh peer preparation and one real Swift/JVM sample
integration case with 204,800 bytes each way. Finalized receipts, actual XML/xcresult evidence and owned cleanup were
independently verified.** Earlier ABI/Dokka/SBOM/sample builds at `ec44b7d0` and
private artifact/complete-consumer checks at `5ed6dbed` remain separate,
source-bound passes; no older failed attempt is promoted by the new results.
**Complete supported-host qualification, the maintained ART suite,
physical-device execution,
real-network/security and actual-host capacity qualification remain pending.**
Unit tests and workflow configuration alone are not supported-host or capacity
evidence.
Release Foundation remains **NOT_READY**, with all existing HOLDs, validation
and release gates intact.
RPC is not part of the immutable `0.7.0-rc3` publication.

The [implementation checkpoint](implementation-status.md) records source scope,
checks actually run, resolved local fixture failures and reviewed generated inputs.
The [September 29 runtime record](mac-vps-runtime-20260929.md) and
[earlier Mac VPS history](mac-vps-validation.md) preserve the diagnoses, failed
attempts, verified recovery and remaining supported-host gates. A successful
contained test suite is not a successful admission when cleanup is unproven.

The approved [plan](../../RPC_MODULE_PLAN.md) fixes the contract and capacity
requirements. No performance or readiness claim follows from these defaults.
If mobile/path security or capacity cannot meet the approved contract, stop
for owner review; do not loosen admission, shrink the workload, raise budgets
blindly, introduce another transport, or broaden firewall policy to get a pass.

## Checks authorized in the implementation workspace

**Current continuation authorization:** the owner subsequently explicitly
authorized local Linux and isolated Intel Mac tooling/dependency installation,
builds, software-emulator attempts, phone-test preparation and the two-machine
synthetic capacity workload, plus feature-only hosted execution when needed.
Earlier narrower execution permissions below describe their historical runs,
not the current permission boundary. This does **not** authorize changing LAN,
identity, virtualization-security or native-ownership protections, accessing
custodian/signing material, modifying another session, or publishing/merging.
See the [foreground phone lab](../../samples/p2p-sample-rpc/phone-ios/README.md)
for the newly added apps and their separate runtime evidence requirements.

Bounded source review, Git/GitHub inspection, whitespace, Markdown links,
repository-layout checks and inspected offline Python/Ruby/shell policy fixtures
can run. Earlier owner-authorized isolated JVM/Android compilation, tests,
dependency downloads and ABI/checksum generation completed as recorded in the
checkpoint. A later owner approval separately authorizes
[feature-only GitHub-hosted macOS work](hosted-validation.md),
including required hosted SDK/dependency downloads and sanitized artifacts.
It does not authorize real-device/capacity experiments, publication or execution
of Foundation/release workflows. Record exact commands and results; local unit
tests and hosted simulators do not qualify deployed LAN enforcement.

An earlier hosted/Mac-only approval covered feature-only GitHub Actions,
isolated Intel Mac validation and disposable Mac-local Maven staging/consumer
checks, but did not then authorize Linux builds or downloads. The broader
current authorization above supersedes that earlier local-execution boundary,
not the bans on normal `~/.m2` use, external publication, security-policy changes
or other sessions' work. Failed executor admission still blocks further product
testing in that context.

JVM/Android ABI files were genuinely generated and reviewed. The 13 new
streaming-JSON checksums passed independent Maven-byte/checksum/signature review.
The maintained Native ABI generation and independent source comparison later
completed on the supplemental VPS; the reviewed baselines are committed, not
inferred from a failed writer. The new complete writer included Apple work and
passed; all 14 locks and 55 additional POM checksums were independently reviewed
before the four changed dependency inputs were committed as `ec44b7d0`.
The fresh candidate's strict full-profile check passed on this supplemental
VPS, followed by strict ABI/compiler/SBOM and existing Android/Desktop/iOS sample
builds. Those P2P packages are not turnkey RPC installers. Private current-source
Maven artifact/consumer checks passed on `5ed6dbed`. Ordinary Swift/runtime
integration subsequently passed on `62716271`; ART and supported-host
qualification remain separate.
Do not accept partial lock candidates, fabricate baselines, exclude missing
locks or disable gates.
Earlier scoped compiler passes and the mutable writer do not replace immutable
supported-host qualification. After preserving the initial split-JAR artifact
failure, the repaired AAR passed 25 Java controls and the unchanged artifact gate.
Clean `5ed6dbed` passed all six packaging phases, including strict admission of
21 publications, 117 physical inputs and 141 verification records. The six RPC
coordinates and typed JVM/Android/common/iOS consumers compiled; the no-network
JVM API smoke and Android D8/R8/POM-only packaging checks passed. All 53 offline
consumer controls passed. The intermediate unverified IO descriptor failure was
resolved by one independently signature-reviewed checksum, not a graph change;
actual Android/JVM IO artifacts remain 0.9.0. Neither consumer compilation nor
the smoke establishes transport, ART/device or capacity behavior.
See the [remaining validation record](mac-vps-validation.md#authorized-packaging-and-consumer-continuation).

The two maintained Swift schemes passed compile-only `build-for-testing` on
`ec44b7d0`; all three bundles preserve iOS 15 and contain Intel/ARM simulator
binaries. Their source inventories cover 88 unit, six UI and one real-peer
method. A private manifest-format inspection failure was preserved and resolved
by a separately tested strict reader; the successful UI compiler was not rerun.
No XCTest was executed by those September 28 compile-only commands and the
simulator stayed Shutdown. The separate runtime attempt failed system-app
readiness; the display/console observations then recorded did not prove its cause.

On September 29 the test user owned the console and a newly created simulator
passed the original 120-second readiness bound. Fresh same-source framework and
Swift builds then executed all 88 unit/six UI methods successfully, followed by
the one real-peer method. The earlier failures and two test-only corrections are
preserved in the [runtime record](mac-vps-runtime-20260929.md). These are ordinary
P2P sample runtime results, not RPC phone-application or dedicated owned-cancellation
qualification. The latter's subsequently verified ARM execution is separately
source-bound above, not inferred from these VPS results.

Separately, `kern.hv_support: 0` rules out hardware-accelerated Android emulator
qualification in this configuration. The Linux Actions lane instead needs KVM
access; no permission change or emulator execution occurred **in that hosted
attempt**. Later API-24 software boots and eight RPC controls are recorded
separately above; they do not replace its maintained API-37/24/25 suite.
The separately requested temporary runner-access exception remains pending.
The historical Apple admission failures are retained; later native admission
recovery and source-specific product results are recorded above.
Obtain suitable owner/provider prerequisites rather than relaxing tests or
conflating Android host-side JVM tests with ART.

Fresh main still contained the historical stale `org.jmdns` coordinate. The
six obsolete lines were independently removed on this feature branch after
reproducing the resolver failure and verifying the existing embedded producer.
This is a separate baseline correction, not an RPC regression or a copied
unfinished Foundation repair. See the checkpoint for exact scope and results.

## Automated validation and remaining authorization

Use the explicitly authorized host/toolchain and admitted execution context.
Merely running `--dry-run` can configure Gradle and resolve/download inputs.
Earlier local JVM/Android-only authorization did not then extend to Apple/shared
jobs; the subsequent broader approvals are scoped as described above, not to
arbitrary repository jobs, physical access, signing or publication.

1. Generate genuine lock/checksum/ABI inputs with the repository's reviewed
   [dependency process](../releasing/checklist.md), compare changes, and keep
   baseline `org.jmdns` work separate. Never copy another session's caches,
   generated files, credentials or unfinished sources.
2. Compile/run `:p2p-rpc:jvmTest`, `:p2p-sample-rpc:jvmTest`, affected core/LAN
   suites and Android host tests; verify typed public examples and strict Dokka.
3. Compile/test Apple targets with the configured Xcode/Kotlin toolchain.
   Specifically verify Network.framework Cinterop types, ARC/MRC ownership,
   callback teardown and numeric effective-path checks. Linux source inspection
   is not Apple compilation or platform proof.
4. Run genuine API/Android ABI comparisons, lint, strict dependency verification,
   SBOM/publication-shape checks and full compatibility regressions. Publication
   **shape** does not authorize publishing or changing historical releases.
5. Run the complete platform profile on authorized macOS/Intel hosts, retaining
   the repository's execution-token/model assessor and every required task.
   The supplemental Mac uses the admitted native leaf rather than the legacy
   PID-based wrapper. Do not turn off required tasks or treat missing/empty XML
   as a test pass; RPC and shared-sample tasks remain in the broad profiles.

Relevant added deterministic suites (common/JVM/Android cases executed;
scoped ARM simulator results are recorded in [hosted validation](hosted-validation.md),
not a complete all-platform qualification):

| Area | Tests / assertions |
| --- | --- |
| Codec and protocol | `RpcCodecTest`: strict/duplicate/nested JSON, streaming limits, malformed wire lengths/features, separate 1 MiB round-trip, owned-byte release. |
| Host execution | `RpcHostEngineTest`: concurrent/altered duplicates, retained outcomes, receipts/cache eviction, tombstones/expiry, per-peer/global tables, queued/running cancellation/deadlines, bounded admission/result authorization, stale/replaced links and revocation. |
| Client recovery | `RpcClientEngineTest`: typed out-of-order responses/business errors, response loss, STATUS without unsafe replay, dual idempotency opt-in, one deadline, missing/stale READY, disconnect, replacement host and incarnation change. |
| Closed-client contract (JVM) | `RpcClosedClientTest`: retained `Closed` state, subsequent `NotConnected` / `NotSent` call rejection before ID/encoding, and denied reattachment. This deterministic control is distinct from the separate real-socket lab. |
| Pairing/trust | `RpcPairingTrustTest`: identity-bound single use, expiry, concurrent candidates, durable approval failure, immediate revocation and cleanup/storage failure. |
| Queue ownership | `SessionRpcLinkTest`, `RpcNotificationsTest`: writer priority, generation isolation, entry/byte limits including active work, nullable schemas, slow consumers, worker cancellation and teardown leases. |
| Generic prerequisites | `SessionProfileTest`, `RestrictedProtocolBudgetTest`, `RestrictedSessionTest` and authenticated-v2 extensions: live admission/quarantine, both-direction capacity, message restrictions, accounting and preserved pin checks. |
| LAN policy | `OrganizationLanTest`, `JvmOrganizationLanTest`, `AndroidLanNetworkStateTest`, `AppleOrganizationLanInteropTest`: CIDR/numeric rejection, strict selected-interface and multihoming failure, fresh Android route lookup without stale fallback, strict Native numeric spelling, host/sockaddr endpoint normalization and null-path rejection. The Native helper regressions passed on ARM simulator; this is not real path-binding evidence. |
| Examples/driver | `RpcSampleContractTest`, `RpcCapacityDriverTest`: exact payload/workload constants and bounded reporting; **not** a throughput measurement. |
| Foreground phone lab | `RpcLabRuntimeInstrumentation`: eight executed API-24 ART/Keystore/Activity controls; the separate iPhone app-hosted suite executed six ownership/cancellation, one real Keychain and two UI controls. Exact source and receipts are in the [RPC lab record](vps-lab-runtime-20260929.md); neither suite sends the capacity workload or qualifies physical phones. |

Runtime coverage must additionally include raw path changes, failed/slow socket
writes, 128 idle readers without writer starvation, teardown failures,
non-cooperative handlers, incoming flood/backpressure, enrollment abuse,
unauthorized cached-result access, and no RPC file/unrelated message path.

## Required real-host steady-state experiment

Run separately against **each real JVM, Android and iOS host**, recording:

- 128 independent, durably provisioned authenticated synthetic client identities;
- 10 calls/second/client: **1,280 calls/second** aggregate;
- exactly 1 KiB encoded request and 1 KiB encoded response bodies;
- 30 minutes of steady scheduling: **2,304,000 successful completions**;
- no RPC failures, unbounded/growing backlog or resource leak;
- latency distributions, CPU, resident memory, threads and connection health.
  **No latency pass/fail threshold** was approved.

The [shared host façade and JVM driver](../../samples/p2p-sample-rpc/README.md)
implement the synthetic contract, not the measurement result. The driver is
open-loop: missed scheduling or exhausted outstanding permits invalidate the
run rather than silently reducing offered load. Setup is outside steady state
and connects in batches of two to preserve the existing per-source gate. This
does not certify 128 physical Wi-Fi associations or every minimum-OS device.

Every run needs an owner-approved local `RpcCapacityEnvironment` provider with
128 protected identity stores, per-client durable host trust, policy-selected
interface and explicit pinned host. It must supply **actual host-process**
CPU/RSS/thread counters and SDK snapshots; driver heap statistics are not host
measurements. No default provider, keys, permissive trust or secret arguments
are supplied. Periodic missing/invalid telemetry invalidates the run.

The driver exits nonzero on setup, call-count/error or cleanup failures. Even a
mechanical success emits
`PENDING_HOST_RESOURCE_REVIEW_AND_PHYSICAL_INTEROPERABILITY`: exit zero is **not
qualification**. Review the full sampled time series for bounded steady-state
memory/threads/backlog, then check teardown and post-retention resource return.
RPC's 64 MiB payload policy is not a process RSS ceiling. Capture enough samples
before load, during warm-up, throughout steady state, after drain and after the
60-second retention window to distinguish normal cache/GC behavior from leaks.

Record exact source commit and dirty-state status, host/driver artifact SHA-256,
JDK/Kotlin/Xcode/SDK versions, host model class/OS, foreground/background state,
network topology/interface/routing/firewall configuration, clock/scheduling
method, raw sanitized local time series and test counts. Avoid personal device
identifiers, endpoints/pins, invitation text, real business data and secrets in
shared reports. Keep evidence in newly owned locations with explicit sharing
approval; do not access custodian or another session's private evidence.

## Separate payload, interoperability and hostile-network qualification

The driver `--large` experiment is only 20 synthetic 1 MiB request/reply calls
at concurrency two. Separately exercise oversized bodies, aggregate exhaustion,
slow readers, response retention/eviction, deliberate overload and recovery.
Do not combine 1 MiB bodies with peak throughput as an implied capacity promise.

Physical JVM↔Android↔iOS interoperability is still required, including actual
Android/iOS hosting. Verify pairing/rotation/revocation; LAN permission denial
and revocation; host sleep/restart; reconnect; response loss; duplicate and late
responses; queued/running cancellation after side effects; unsafe retry denial;
mDNS-blocked numeric fallback; VLANs; and firewall/Internet-disconnected use.
Path tests must demonstrate rejection of public/DNS/VPN/cellular/AWDL and
unverifiable routes, including change during active and idle connections.

Packet capture, hostile-network testing, physical devices, local application
execution and shared hosted execution require **separate authorization and
owner coordination**. Apply the existing [validation evidence rules](../validation/README.md);
RPC qualification neither substitutes for nor promotes those external gates.
