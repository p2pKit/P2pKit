# RPC verification and capacity qualification

## Status and boundaries

**JVM/Android and scoped ARM simulator tests, strict core/LAN/RPC Dokka, and
Apple framework/Swift API compilation passed. Supplemental Mac prerequisites
have recovered after an owner-authorized restart and separate runtime setup.
A new complete dependency writer, full generated-input review and fresh
122-test admission of committed candidate `ec44b7d0` passed, including cleanup.
The separate strict immutable full-profile run passed all 20 required tasks:
2,957 passes, zero failures/errors and one pre-existing ignored diagnostic,
with source integrity and cleanup verified. ABI/compiler checks passed, but
SBOM privacy validation failed because the clone inherited private transfer-bundle
VCS URLs. A fresh same-commit canonical-origin clone passed new admission and
repeated the complete profile with the same 2,957 passes and one ignored
diagnostic, including source/cleanup verification. All ten fresh ABI/compiler/
SBOM commands passed, including unchanged privacy validation on the actual
88-component pair; all 11 generated ABI dumps match their baselines. The original
failed evidence remains unchanged.
Fresh XCFramework provenance/minimum-OS checks and the existing unsigned iOS
sample application build also passed. The subsequent Swift unit/UI attempt
failed at its unchanged 120-second simulator-readiness bound (`Waiting on
System App`), before launching XCTest. Source, cleanup and final Shutdown were
independently verified; that does not turn the runtime gate green.
Independent existing Android/Desktop package builds subsequently passed with
verified receipts, source integrity, output inventories and cleanup. Read-only
graphics/session observations did not establish the system-app failure cause.
Matching supported-host, Swift runtime, Maven artifact/consumer,
real-network, security and capacity qualification remain pending.** Unit tests
and workflow configuration alone are not supported-host or capacity evidence.
Release Foundation remains **NOT_READY**, with all existing HOLDs, validation
and release gates intact.
RPC is not part of the immutable `0.7.0-rc3` publication.

The [implementation checkpoint](implementation-status.md) records source scope,
checks actually run, resolved local fixture failures and reviewed generated inputs.
The [Mac VPS continuation](mac-vps-validation.md) preserves the scan diagnosis,
earlier failures, subsequent verified recovery and remaining
supported-host gates. A successful contained test suite is not a successful
admission when cleanup is unproven.

The approved [plan](../../RPC_MODULE_PLAN.md) fixes the contract and capacity
requirements. No performance or readiness claim follows from these defaults.
If mobile/path security or capacity cannot meet the approved contract, stop
for owner review; do not loosen admission, shrink the workload, raise budgets
blindly, introduce another transport, or broaden firewall policy to get a pass.

## Checks authorized in the implementation workspace

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

The latest owner approval covers remaining feature-only GitHub Actions and
isolated Intel Mac validation, required tooling downloads on those hosts, and
disposable Mac-local Maven staging/consumer checks. It does not authorize new
local Java/Gradle/Xcode/application builds or local SDK/dependency downloads,
normal `~/.m2` use, external publication, security-policy changes or other
sessions' workflows. Failed executor admission blocks further product testing.

JVM/Android ABI files were genuinely generated and reviewed. The 13 new
streaming-JSON checksums passed independent Maven-byte/checksum/signature review.
The maintained Native ABI generation and independent source comparison later
completed on the supplemental VPS; the reviewed baselines are committed, not
inferred from a failed writer. The new complete writer included Apple work and
passed; all 14 locks and 55 additional POM checksums were independently reviewed
before the four changed dependency inputs were committed as `ec44b7d0`.
The fresh candidate's strict full-profile check passed on this supplemental
VPS, followed by strict ABI/compiler/SBOM and existing Android/Desktop/iOS sample
builds. Those P2P packages are not turnkey RPC installers. Swift runtime,
Maven artifact/consumer and supported-host qualification remain separate.
Do not accept partial lock candidates, fabricate baselines, exclude missing
locks or disable gates.
Earlier scoped compiler passes and the new mutable writer do not replace
immutable supported-host qualification. The newly authorized private Maven
staging passed, but the unchanged artifact checker rejected AGP's split local
JAR representation. The feature now preserves the exact reviewed producer in
the AAR; that repair still requires genuine packaging verification. Complete
published-consumer fixtures now explicitly cover six RPC coordinates and typed
JVM/Android/common/iOS API use. Their 52 offline controls passed; actual consumer
Gradle compilation and the no-network JVM API smoke are still pending. Neither
consumer compilation nor the smoke establishes transport or capacity behavior.
See the [remaining validation record](mac-vps-validation.md#authorized-packaging-and-consumer-continuation).

The current VM needs a working system-app/GUI simulator prerequisite before
the unexecuted 88 Swift unit and six UI methods can run. Its reported display
has 3 MB memory with no Metal capability reported, and the SSH test user does
not own the console; neither observation proves the failure's root cause.
Separately, `kern.hv_support: 0` rules out hardware-accelerated Android emulator
qualification in this configuration. Obtain suitable owner/provider prerequisites
rather than relaxing tests or conflating Android host-side JVM tests with ART.

Fresh main still contained the historical stale `org.jmdns` coordinate. The
six obsolete lines were independently removed on this feature branch after
reproducing the resolver failure and verifying the existing embedded producer.
This is a separate baseline correction, not an RPC regression or a copied
unfinished Foundation repair. See the checkpoint for exact scope and results.

## Automated validation and remaining authorization

Authorize the relevant host/toolchain and dependency resolution first. Merely
running `--dry-run` can configure Gradle and resolve/download inputs. The local
JVM/Android authorization did not extend to Apple/shared jobs; the later explicit
hosted approval is scoped as described above, not to arbitrary repository jobs.

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
| Pairing/trust | `RpcPairingTrustTest`: identity-bound single use, expiry, concurrent candidates, durable approval failure, immediate revocation and cleanup/storage failure. |
| Queue ownership | `SessionRpcLinkTest`, `RpcNotificationsTest`: writer priority, generation isolation, entry/byte limits including active work, nullable schemas, slow consumers, worker cancellation and teardown leases. |
| Generic prerequisites | `SessionProfileTest`, `RestrictedProtocolBudgetTest`, `RestrictedSessionTest` and authenticated-v2 extensions: live admission/quarantine, both-direction capacity, message restrictions, accounting and preserved pin checks. |
| LAN policy | `OrganizationLanTest`, `JvmOrganizationLanTest`, `AndroidLanNetworkStateTest`, `AppleOrganizationLanInteropTest`: CIDR/numeric rejection, strict selected-interface and multihoming failure, fresh Android route lookup without stale fallback, strict Native numeric spelling, host/sockaddr endpoint normalization and null-path rejection. The Native helper regressions passed on ARM simulator; this is not real path-binding evidence. |
| Examples/driver | `RpcSampleContractTest`, `RpcCapacityDriverTest`: exact payload/workload constants and bounded reporting; **not** a throughput measurement. |

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
