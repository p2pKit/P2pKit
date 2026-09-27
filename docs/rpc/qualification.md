# RPC verification and capacity qualification

## Status and boundaries

**JVM/Android compilation and deterministic tests passed; Apple, real-network,
security and capacity qualification remain pending.** Unit tests and workflow
configuration are not platform or capacity evidence. Release Foundation remains
**NOT_READY**, with all existing HOLDs, validation and release gates intact.
RPC is not part of the immutable `0.7.0-rc3` publication.

The [implementation checkpoint](implementation-status.md) records source scope,
checks actually run, resolved local fixture failures and missing generated inputs.

The approved [plan](../../RPC_MODULE_PLAN.md) fixes the contract and capacity
requirements. No performance or readiness claim follows from these defaults.
If mobile/path security or capacity cannot meet the approved contract, stop
for owner review; do not loosen admission, shrink the workload, raise budgets
blindly, introduce another transport, or broaden firewall policy to get a pass.

## Checks authorized in the implementation workspace

Bounded source review, Git/GitHub inspection, whitespace, Markdown links,
repository-layout checks and inspected offline Python/Ruby/shell policy fixtures
can run. The owner additionally authorized isolated JVM/Android compilation,
tests, dependency downloads and genuine ABI/lock/checksum generation. This is
not authorization for Apple toolchains, real-device/capacity experiments,
publishing or shared hosted execution. Record exact commands and results;
local unit tests do not qualify deployed LAN enforcement.

JVM/Android ABI files were genuinely generated and reviewed. The 13 new
streaming-JSON checksums passed independent Maven-byte/checksum/signature review.
Native ABI and RPC/sample dependency locks remain pending: the mandatory
complete lock writer includes Apple work. Do not accept partial lock candidates,
fabricate baselines, exclude missing locks or disable any gate. Strict Dokka
also selects Native/Apple producers, so its full execution remains gated.

Fresh main still contained the historical stale `org.jmdns` coordinate. The
six obsolete lines were independently removed on this feature branch after
reproducing the resolver failure and verifying the existing embedded producer.
This is a separate baseline correction, not an RPC regression or a copied
unfinished Foundation repair. See the checkpoint for exact scope and results.

## Automated validation and remaining authorization

Authorize the relevant host/toolchain and dependency resolution first. Merely
running `--dry-run` can configure Gradle and resolve/download inputs. The local
JVM/Android authorization does not extend to the remaining Apple/shared jobs.

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
5. Run the repository's platform-evidence wrapper on authorized macOS/Intel
   hosts; the RPC and shared sample tasks are included in the broad profiles.
   Do not turn off required tasks or treat missing/empty XML as a test pass.

Relevant added deterministic suites (common/JVM/Android cases executed;
Apple cases still unexecuted):

| Area | Tests / assertions |
| --- | --- |
| Codec and protocol | `RpcCodecTest`: strict/duplicate/nested JSON, streaming limits, malformed wire lengths/features, separate 1 MiB round-trip, owned-byte release. |
| Host execution | `RpcHostEngineTest`: concurrent/altered duplicates, retained outcomes, receipts/cache eviction, tombstones/expiry, per-peer/global tables, queued/running cancellation/deadlines, bounded admission/result authorization, stale/replaced links and revocation. |
| Client recovery | `RpcClientEngineTest`: typed out-of-order responses/business errors, response loss, STATUS without unsafe replay, dual idempotency opt-in, one deadline, missing/stale READY, disconnect, replacement host and incarnation change. |
| Pairing/trust | `RpcPairingTrustTest`: identity-bound single use, expiry, concurrent candidates, durable approval failure, immediate revocation and cleanup/storage failure. |
| Queue ownership | `SessionRpcLinkTest`, `RpcNotificationsTest`: writer priority, generation isolation, entry/byte limits including active work, nullable schemas, slow consumers, worker cancellation and teardown leases. |
| Generic prerequisites | `SessionProfileTest`, `RestrictedProtocolBudgetTest`, `RestrictedSessionTest` and authenticated-v2 extensions: live admission/quarantine, both-direction capacity, message restrictions, accounting and preserved pin checks. |
| LAN policy | `OrganizationLanTest`, `JvmOrganizationLanTest`, `AndroidLanNetworkStateTest`, `AppleOrganizationLanInteropTest`: CIDR/numeric rejection, strict selected-interface and multihoming failure, fresh Android route lookup without stale fallback, native numeric equivalence and null-path rejection. Native tests are pending and are not real path-binding evidence. |
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
