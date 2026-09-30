# Intel and 128-client investigation — 2026-09-30

## Scope and current conclusions

Feature branch: `work/rpc-lan-20260927-054728-8b1b11da`, in the separate
`/root/projects/p2pkit-feature-prep-20260927-yiDjCB` clone. No other session's
directory, source, keys, private evidence or CI was used. All release HOLDs
remain; Release Foundation is **NOT_READY**. Instructions and the approved plan
are unchanged. The known `org.jmdns` lock baseline is unrelated to these failures.

- **Capacity remains unqualified.** The missed sends are generator slots
  rejected before RPC invocation, not remotely lost RPCs. The new complete run
  attributes each slot and strongly associates the timer/worker stalls with
  independent guest memory-balloon/reclaim activity. No product change is justified
  by the available evidence.
- **Intel is not yet qualified.** The diagnostic run establishes nine LAN Native
  failures and a system Data Migration readiness timeout, not a renewed native
  process-ownership admission defect. A reporting defect and an ordinary
  Native-to-Swift lifecycle omission have been corrected; actual Intel follow-up
  is still required before claiming that the corrections resolve product gates.
- The owner deleted the supplemental Mac before additional remote files could
  be copied. Source and earlier Linux exports survive; original Mac-only XCTest
  bundles and the unsigned iPhone app were **not recovered**.

This is source-bound local/hosted evidence, not physical LAN, cross-device,
Android/iPhone hosting capacity, or release readiness.

## Where the historical 69,538 sends went

The original `a15aa78f` run dispatched and completed **2,234,462** RPCs, with
**69,538** missed slots against 2,304,000. Source inspection of
[`RpcCapacityMain.kt`](../../samples/p2p-sample-rpc/src/jvmMain/kotlin/dev/p2pkit/sample/rpc/RpcCapacityMain.kt)
establishes the only three places that increment the missed counter:

1. The 10-Hz timer resumes at least 100 ms after the intended time: no call job
   is enqueued and `RpcClient.call` is never reached.
2. A timely timer cannot acquire that client's eight-outstanding-call permit:
   no job is enqueued and RPC is never invoked.
3. A permitted worker begins at least 100 ms late: its permit is released at
   completion, but `measureCall` / `RpcClient.call` is deliberately not invoked.

There is no path that turns a dispatched transport request, remote rejection,
lost response or call timeout into this missed-slot counter. Calls made it to
the host exactly as reflected by the dispatched/accepted/completed counters.
Zero RPC errors/timeouts/retries is therefore consistent with the failure:
those **unsent** slots never enter RPC error accounting. The overall capacity
gate correctly fails despite successful invoked calls.

The old run recorded these three branches in one combined counter. Its exact
historical timer/permit/worker split cannot be reconstructed. No retrospective
per-slot attribution is claimed from coarse old CPU/GC samples.

## Unchanged full workload, with stage instrumentation

Exact executed source: `88f81e6bc32ca5e49c20625d0b7f6343629920af`.
The maintained [same-host fixture](same-host-lab.md) used two independent
processes and 128 distinct authenticated identities, production `RpcPlatform.jvm`,
encrypted real TCP, strict `OrganizationLan`, and an explicitly isolated virtual
Ethernet link. There was no public listener, SSH forwarding or peer-authentication
bypass. Both processes ran on the same Linux VPS, not on the deleted Mac.

Only bounded diagnostic collection was added: per-scheduled-second stage totals,
an independent observer thread, clock/worker/process CPU and fault observations,
and bounded JVM GC/safepoint logs. The 128 phase-spaced clocks, 10 calls/s/client,
eight permits/client, 100-ms missed criterion, 1-KiB payloads, 1,800-second window,
call/drain bounds, heap/collector and production RPC code were unchanged.

| Measurement | Historical combined-counter run | Instrumented run |
|---|---:|---:|
| Required calls | 2,304,000 | 2,304,000 |
| Actual calls / successful responses | 2,234,462 | **2,217,973** |
| Missed slots | 69,538 | **86,027** |
| Timer-late slots | Not separately recorded | **83,805** |
| Permit-unavailable slots | Not separately recorded | **0** |
| Worker-late slots | Not separately recorded | **2,222** |
| Responses/second | 1,241.367588 | **1,232.206726** |
| Invocation-to-completion p50 / p95 / p99, ms bucket upper bounds | 2 / 2 / 5 | **2 / 2 / 5** |
| Invocation-to-completion maximum, ms bucket upper bound | See original record | **2,821** |
| Scheduling-delay p99 / maximum, ms bucket upper bounds | 1,340 / 2,744 | **1,595 / 2,799** |
| RPC errors / timeouts / retries | 0 / 0 / 0 | **0 / 0 / 0** |
| Sampled host queue maximum | 0 | **0** |

The scheduling window actually lasted **1,800.000724445 seconds**, followed by
a **0.002658098-second** drain. All 1,800 scheduled-second bins reconcile:

```text
2,304,000 considered = 83,805 timer-late + 0 permit-unavailable + 2,220,195 enqueued
2,220,195 enqueued = 2,220,195 workers started = 2,222 worker-late + 2,217,973 dispatched
2,217,973 dispatched = 2,217,973 completed + 0 failed
86,027 missed = 83,805 timer-late + 0 permit-unavailable + 2,222 worker-late
host accepted = host completed = client completed = 2,217,973
```

No requests remained outstanding after drain, no connection changes were
observed, and no host telemetry sample was rejected. The separate **65.006-second**
post-client idle-retention observation returned connections, running/queued work,
records and payload accounting to zero. Native cleanup reaped both owned workers;
the host exited zero and the client exited one because scheduling acceptance
failed. The coordinator retained that failure; successful cleanup did not erase it.

### Resource and runtime observations

- Host workload-window CPU: **3,070.47 CPU-seconds** over 1,800.634 seconds of
  host uptime (about **1.71 logical cores**). Client process CPU over the scheduling
  measurement: **4,085.17 CPU-seconds** (about **2.27 logical cores**).
- Entire host time series, including setup/retention: **1,812 samples**; maximum
  RSS **805,588,992 bytes**, maximum native threads **209**, JVM threads **175**,
  authenticated connections **128**, running handlers **4**, queue **0**,
  retained records **74,635**, and retained payload bytes **29,717,934**.
  These are observed maxima, not continuous proofs of a peak or reservations.
- Driver observer: **1,743 samples**, maximum observation gap **3.202331628 s**,
  maximum timer delay **2.798834663 s**, maximum worker queue delay
  **2.480445184 s**. The timer thread consumed approximately **38 CPU-seconds**
  over the run, not a continuously saturated core. JVM RUNNABLE counts also
  include native socket waits and are not CPU utilization measurements.
- Client major-fault delta: **1,102,772**. Guest direct-reclaim scans increased by
  **293,442,667 pages**, allocation stalls by **1,004,173**. Visible available
  memory ranged from **1,545,696 to 21,418,868 KiB** despite no reserved-memory
  guarantee. No swap was configured.
- The guest's actual `virtio_balloon` device periodically inflated/deflated
  about five million 4-KiB pages (roughly 20 GiB), approximately once per minute.
  The run accumulated **144,466,508** inflated and the same number of deflated
  pages. Independent idle observations already showed this behavior without RPC.
- Retained JVM timing has **12 safepoints of at least 100 ms**, with a maximum
  **2.708943221 s**. GC labels alone do not prove expensive evacuation: the long
  episodes also have large system/wall time and guest faults/reclaim. Cumulative
  GC collection time is not a maximum-pause measurement.

All **86,027 misses** fall in the **131 scheduled-second bins** overlapping
observed direct-reclaim sample windows. Long JVM-safepoint windows overlap
**29,848** misses in 33 bins; they do not alone account for all misses. There are
**zero misses outside** the union of observed reclaim/long-safepoint windows.
This is one-second-bin/sample-window correlation, not nanosecond causal tracing
of each instruction or proof of the provider's internal scheduling policy.

### Independent no-RPC/no-Java control

An owned Linux `timerfd` control used a 10-ms kernel timer for
**125.000063152 seconds**, without Java, RPC or network traffic. The kernel
recorded **12,500 expirations**; userspace made **12,154 reads**, coalescing
**346 expirations**, with a maximum read gap of **1.456726377 seconds**. Delayed
reads and its own major faults coincided with the same balloon/reclaim episodes.
Its native finalization passed. Coalesced kernel expirations and the immediately
measured read gap have different boundaries; neither is called an RPC loss.

Taken together, source-level slot reconciliation, low permit pressure, exactly
matched remote completions, the observer/GC evidence and the independent kernel
control support an **environment-induced load-generator timing failure**, not
a demonstrated P2pKit reliability defect. The diagnostics can affect pause timing;
the larger missed count in this run is not treated as a new product regression.
During the last minutes, the owner's urgent Mac-preservation request caused
bounded SSH/metadata checks; no remote transfer succeeded. Source bundling and
bulk local export verification started only after the workload/finalizer ended.
The independent earlier control prevents attributing the periodic problem solely
to those late checks, but their overlap is disclosed rather than hidden.

### Engineering decision and qualification requirement

**Do not change production RPC for this evidence.** Adding retries cannot recover
calls never submitted. Catch-up bursts, dropping the 100-ms criterion, lowering
the target or lengthening the window would change the workload instead of
demonstrating capacity. No such change was made.

The measured 2/2/5-ms percentiles describe actual completed calls at the
**reduced admitted load**. They do not describe intended-arrival latency or prove
p99 at 1,280 calls/s. Timing is client invocation through reply handling; it is
not a wire-only or server-processing measurement. The approved plan explicitly
selected **no numerical latency pass/fail threshold**, so percentiles are
measurements, not an invented latency pass.

For an application, periodic work not submitted while its process is suspended
is an application scheduling concern. Real Android/iPhone background restrictions
can make that concern relevant; the RPC module does not promise a durable offline
queue or catch-up of unsent business events. This does not excuse a capacity gate
failure or prove that a real host can sustain the full arrival rate.

Qualification still needs an adequately isolated, stable/reserved-resource
generator and host, actual full-rate scheduling for 30 minutes, **2,304,000
successful responses with zero missed sends/errors**, resource/latency reporting
under the approved contract and original cleanup. Deployment claims additionally need each intended
JVM/Android/iPhone host and approved real-network evidence. Repeating the unchanged
VPS experiment indefinitely without addressing the measured environment is not
a product fix or a useful qualification strategy.

## Intel: failure trace and fixes under verification

[Run 36676816096](https://github.com/p2pKit/P2pKit/actions/runs/36676816096) ran
source `8e84466b9c94d4514f25764196192f20b9c60fc1` on actual **Intel/macOS 15.7.9,
Xcode 26.3**, runner image `20260824.0482.1`. Its created iOS **26.2** simulator
advertised both x86_64 and arm64 support. Wrong host architecture, Rosetta,
wrong Xcode and selecting an ARM-only runtime are not supported explanations.

1. **Ownership admission passed all 122 controls.** Toolchain/native-role checks
   and independent ABI/Dokka/framework/Swift-API/SBOM/provenance checks passed.
2. **Native product failure:** core `iosX64Test` passed **793** cases; LAN
   `iosX64Test` passed **185**, failed **nine**, and retained one existing ignored
   diagnostic. RPC/sample Native tasks were not completed. Product/final exit one,
   stop zero, no unresolved lifetime/discovery error or owned survivor. The strict
   assessor correctly refused a complete-profile pass.
3. **Reporting defect:** real KGP XML has classes such as
   `iosX64Test.dev.p2pkit.transport.lan.Class`, while source inventory contains
   `dev.p2pkit.transport.lan.Class`. The first exporter mapped no failed classes,
   recording nine unmapped failures. The raw XML was not a permitted hosted
   artifact, so those nine identities cannot be reconstructed from that artifact.
4. **Swift prerequisite failure:** `simctl bootstatus <owned-device> -b` remained
   at **Data Migration/status 2**, nonterminal through 116 seconds of reported
   elapsed time. The original 120-second product deadline then terminated it:
   product -15, final 125, fixed `Product command timed out`. Zero pending native
   identities/discovery errors/survivors were recorded. The wrapper's
   `OWNERSHIP_UNPROVEN` verdict is not proof of a native ownership-tracker leak.
   The exact created device was subsequently verified Shutdown and deleted.
5. **Independent multicast failure:** selected IPv4 mDNS sends raised
   `NoRouteToHostException` despite matching selected/host/socket interface and
   route observations. Full-platform testing remained blocked, not skipped into
   a successful overall verdict. This is separate from stale dependency locks.

### Corrected reporting

[`rpc_product_diagnostics.py`](../../scripts/rpc_product_diagnostics.py) now
removes only the exact Native task prefix matching the XML directory and still
requires class/method membership in checked-in source. Wrong-task, recursive,
arbitrary/private prefixes remain unmapped. Failure sites are limited to valid
lines in unambiguously named source files, with closed marker enums, never raw
payloads, exception messages, endpoints or device IDs. The generic word
"Finished" in a test stack no longer falsely labels simulator boot completion.

Eight offline diagnostic/privacy controls passed. Separately, all **1,036** case
names in a preserved actual `62716271` Mac Native XML export mapped to current
source with the corrected prefix reader. That is offline metadata verification,
not new Apple execution or a reconstruction of the missing nine failures.

### Ordinary Native-to-Swift lifecycle omission

The qualification driver did not explicitly retire its ordinary platform-test
simulator between standalone KGP execution and subsequent Swift GUI readiness.
The maintained `run-audit-host.py` helper and dedicated ARM follow-through
already require that retirement, including after a failed standalone spawn.
The pinned Kotlin 2.4.10 `KotlinNativeTest.kt` source confirms its Native task
uses `simctl spawn` with a distinct standalone mode; it is not a GUI-readiness
acknowledgement. No product request or code execution was inferred from Booted.

[`run-rpc-qualification.py`](../../scripts/run-rpc-qualification.py) now brackets
ordinary platform execution with exact created-device isolation/retirement on
both real Apple roles, including in `finally` after failure. Subsequent Swift
requires verified Shutdown and still runs its original **120-second** readiness
check. A retirement failure marks the context unsafe and blocks later products.
The ARM-specific methods retain their ARM-only guard; the shared ordinary helper
cannot admit ARM follow-through on Intel. No device reset, service kill, arbitrary
simulator adoption, cache deletion, global security change or retry is introduced.

**49 qualification-driver offline controls passed**, including six new lifecycle
controls. This fixes a verified harness ownership/lifecycle omission; it is **not
yet proof that the omission caused all nine Native failures or the Data Migration
stall**. The next actual Intel run must provide case locations and before/after
device states. Neither the diagnostic fix nor a subsequent successful boot alone
can retroactively identify an unexported failing assertion.

Alternatives considered:

- Export unrestricted raw XCTest/log bundles: rejected; it would violate the
  established hosted privacy boundary. Source-bound identifiers/lines suffice.
- Infer success from Booted, relax assertions, remove Intel/ARM entries or extend
  readiness: rejected; these would weaken qualification rather than fix it.
- Select an older runtime or substitute macOS 26/ARM: rejected as unsupported by
  the actual compatible x86_64 runtime evidence and required matrix contract.
- Reset shared CoreSimulator services or change audit/TCC/security policy:
  rejected; unrelated resources and production safeguards must remain intact.
- Retire only the simulator actually created by this job between different
  lifecycle modes: selected; matches the maintained ownership model, adds
  observable cleanup guarantees, and preserves original runtime requirements.

## Separate local test-fixture race

The first instrumented-source JVM rebuild exposed
`NetworkPathRecoveryTest.pathUnsatisfiedTransitionsConnectedSessionToReconnecting`:
Alice's local connect completed before Bob committed his independent incoming
session. Fixture teardown could stop Bob during that commit, triggering the strict
`Incoming session setup failed` diagnostic with
`P2pKit stopped before the session could be committed` in `SessionManager.kt`.

Commit `32edaa12` changes only the test fixture to await Bob's public committed
session before path changes. A deterministic existing pre-commit hook proves
Alice can be Connected while Bob is still uncommitted, then verifies the wait.
Original diagnostics/assertions and five-second bounds remain. No production
session logger, cancellation behavior or lifecycle contract changed. This Linux
failure is **not assumed to be the Intel LAN failure**. Fresh immutable source
`514450864cf1b63bf9d556b15c2044ebfde7099f` passed 121 native ownership controls,
then the seven targeted `NetworkPathRecoveryTest` cases, 11 targeted
capacity-driver/diagnostic cases, and **1,172 four-module JVM cases**:
858 core, 233 LAN, 46 RPC and 35 sample. No failures or skipped cases occurred.
Each invocation exited zero with unchanged source, no discovery errors or owned
survivors, and successful native finalization. The retained per-invocation XML
was independently rehashed and counted, not inferred from a Gradle exit code.
This validates the fixture correction on JVM, not on Intel Native.

Exact Gradle task arguments, run through the admitted native executor:

```text
:p2p-core:jvmTest --tests dev.p2pkit.core.internal.NetworkPathRecoveryTest --console=plain
:p2p-sample-rpc:jvmTest --tests dev.p2pkit.sample.rpc.CapacityScheduleDiagnosticsTest --tests dev.p2pkit.sample.rpc.RpcCapacityDriverTest --console=plain
:p2p-core:jvmTest :p2p-transport-lan:jvmTest :p2p-rpc:jvmTest :p2p-sample-rpc:jvmTest --console=plain
```

## Evidence and reproducibility

Private local continuation evidence is under:

```text
/root/projects/p2pkit-feature-prep-20260927-yiDjCB/.git/
  rpc-intel-capacity-20260930.QnOgzKzS/
```

The immutable `capacity-isolated.j7WzAbAA/source` and fresh admitted state retain
the instrumented distribution/JAR manifests, native controls, real network
configuration, raw counters, timing logs, telemetry and original failed receipts.
`instrumented-steady-reviewed.json` independently verifies source/artifacts and
retention/cleanup before aggregating. `instrumented-steady-diagnostics.json`
reconciles all bins; it is explicitly diagnostic, not admission. Reproduce with
the [maintained same-host commands and prerequisites](same-host-lab.md), not a
mock or a raw unowned Java launcher.

| Evidence | SHA-256 |
|---|---|
| Independently reviewed instrumented steady run | `88e79c227ed92c25f02bc58b887ca91b68c1def25e5a620e2198928aad168108` |
| Original client log | `f8ea7d9ce7f8dacf30cf0f3d8737a817033ee9f58db9c98fb1f63c70c1726ad1` |
| Independent kernel-timer control review v2 | `64c7d486059b906d9602116558e2f193e1285a8396b7f4511ec329ff8f634862` |
| Fresh targeted and four-module JVM independent review | `ce025f5f60a3caad3cf883cf5c89cfb8dee82ae74b5126a1d8204121445c2939` |
| Intel original artifact ZIP, publisher digest verified | `f7fb9c87700c09325048e28920b220e29a541a995e885be9eb012bbdd7ae3e1f` |
| Intel complete available workflow-log ZIP | `47510811b3fc3807c4da2396d9a5599d922df811663d887919be042114edd517` |

The original Intel artifact, decoded summary, complete workflow logs and
independent review remain under `actions-36676816096/`. No failed attempt is
deleted, relabeled as passed or overwritten by a later source.

## Supplemental Mac deletion and preservation gap

Three pinned, bounded SSH attempts timed out before authentication. The owner
then confirmed that the Mac workspace had already been deleted. No new remote
file was copied. Earlier Linux exports were independently rehashed: **3,863 files,
123,660,124 bytes** matched their original per-file manifests. The local
preservation archive's **3,881 entries** were read back and matched; a full-history
feature bundle through `2cfef981` was verified separately. The active Linux clone
retains subsequent commits as well.

Preservation location:

```text
/root/projects/p2pkit-feature-prep-20260927-yiDjCB/.git/
  rpc-mac-preservation-20260930.ee7tv7mg/
```

`backup-manifest.json` / `SHA256SUMS` bind the source bundle and existing-evidence
archive. This is a verified backup of **previously available Linux copies**, not
a complete Mac backup. The unsigned iPhone app and unexported original XCTest
bundles are unavailable. Any unexported Mac changes could not be inventoried;
none is claimed preserved. Credentials, task/private keys, signing material,
SDKs, dependency caches and unrelated work were not copied. New iPhone packaging
must be rebuilt on an authorized Apple runner and signed by the owner for a
device; historical summaries do not recreate the lost native result bundles.
