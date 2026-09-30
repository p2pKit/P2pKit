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
  Native-to-Swift lifecycle omission have been corrected. The completed follow-up
  maps all nine failures but **disproves stale Booted state as their explanation**:
  the simulator was already Shutdown and the same failures remain. Independent
  diagnostics now reproduce a clean-boot **System App readiness timeout** without
  preceding product work and nine discovery-wait failures. Native's intermediate
  report conversion discarded the new context messages; a narrowly tested
  reporting correction is being verified, not a claimed production fix.
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

### Separate post-fix real-socket regression

The rebuilt, independently admitted `51445086` candidate subsequently ran
`--mode large` and `--mode correctness` as **separate** same-host veth experiments,
after all build work had finished. Each re-ran all **121 native controls** inside
its new mount/PID/network namespaces, used fresh protected synthetic identities,
verified every prepared JAR and finished with unchanged source and no owned
survivors. The JVM runtime was Ubuntu OpenJDK **17.0.20**, x86_64; the build daemon
toolchain was OpenJDK **21.0.12**. Production admission and encrypted TCP remained
unchanged.

| Measurement | One-MiB large-call workload | Real-socket correctness |
|---|---:|---:|
| Actual result | **20/20 replies**, concurrency two | **6/6 cases** |
| Encoded request/reply size | **1,048,576 bytes each** | Case-specific |
| Call-workload duration | **2.500899093 s** | Not a timed load workload |
| Responses/s over call window | **7.997124** | Not a throughput claim |
| Call p50 / p95 / p99 / max, ms bucket upper bounds | **181 / 574 / 606 / 606** | No latency histogram in this mode |
| Unexpected RPC failures | **0** | **0**; intentional negative outcomes asserted |
| Maximum sampled RSS | **334,483,456 bytes** | **194,347,008 bytes** |
| Maximum native / JVM threads | **52 / 22** | **53 / 25** |
| Maximum connections / running / queued | **1 / 2 / 0** | **2 / 1 / 0** |
| Maximum retained records / payload bytes | **20 / 18,205,872** | **414 / 496,906** |
| Post-client idle retention actually observed | **65.795 s** | **65.153 s** |
| Total coordinator time including provisioning/retention | **77.453 s** | **87.717 s** |

Large-call process CPU grew by **9.13 host CPU-seconds** across its **71.845-s**
sampled host interval; correctness grew by **9.88 CPU-seconds** across **82.258 s**.
Those intervals include setup and idle retention, **not only the call window**.
The large-call suite uses one authenticated client with two outstanding calls;
it is not another 128-client experiment. Twenty observations do not establish
stable tail-latency percentiles or a numerical latency qualification.

The six correctness cases are concurrent typed correlation, application error,
procedure authorization, sent deadline, sent cancellation and close during call
with an independent client. The recorded **414 accepted/completed** host calls
include real status-observation RPCs; they are not 414 independent test cases.
The one refusal is the deliberately unauthorized procedure call, whose handler
never runs. Deadline/cancellation/uncertain-close outcomes are asserted, not
hidden as successful business responses. Both runs returned connections,
running/queued work, retained records and payload accounting to zero before
normal host shutdown and verified native finalization.

Use the [maintained same-host commands](same-host-lab.md) with the admitted
candidate's `SOURCE`/`STATE`, selecting `large` and then `correctness`; do not
invoke an unowned JVM directly. Evidence is under
`final-jvm-regression.2OjFJU2U/state/work/same-host-{large,correctness}/` and
`local-{large,correctness}-{host,client}/` in the continuation evidence directory.
`fresh-local-workloads-reviewed.json` independently reconciles native receipts,
topology, JARs, raw result records, all 71/81 host samples and cleanup. These are
scoped **local transport passes**, not physical LAN, mobile, Apple or 128-client
capacity qualification.

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
controls at that checkpoint. The focused follow-up,
[run 36684095464](https://github.com/p2pKit/P2pKit/actions/runs/36684095464), source
`d7f093490966486552d24355105cda7caeefe84c`, requested only after the narrow local
regressions and repository checks passed, **completed FAIL** at 08:26:26 UTC.
No unrelated Apple/ART lane was requested. It proves the prefix-reporting fix:
all nine failed methods now map to checked-in source; none is unmapped.

| Failing Native fixture | Exact failing methods |
|---|---|
| `IosLanLifecycleTest` | `advertiseStopRestartProducesObservablePeerChurn`, `midTransferCancelTerminatesBothSidesCleanly`, `peerLostEventFiresWhenPeerStops`, `rapidConnectCloseCycle`, `stopDiscoveryWithdrawsOwnedPeersAndRestartReplaysCurrentState`, `threePeersMutuallyDiscover` |
| `IosLanLoopbackTest` | `fileTransferRoundTripsOverTcp`, `largeBinaryPayloadRoundTripsOverTcp`, `twoKitsDiscoverEachOtherAndExchangeText` |

All nine retained `TIMEOUT`, without Native source-line information. Core again
passed 793 cases; LAN recorded 185 passes, nine failures and one existing ignored
diagnostic; RPC/sample Native did not complete. All 122 ownership controls and
independent ABI/Dokka/framework/Swift-API/SBOM/provenance/project gates passed.

The created iOS 26.2 device was **Shutdown before and after Native execution and
before Swift boot**. Therefore the added retirement contract is useful cleanup
coverage, but it did **not** resolve these failures and stale Booted state is not
their demonstrated root cause. Swift boot again reached nonterminal Data
Migration/status 2 (last reported elapsed 114 seconds), then exceeded the original
120-second bound: product -15/final 125. Its receipt retained zero discovery
errors, pending identities and owned survivors. Exact shutdown/deletion passed.
The ownership-wrapper timeout verdict must not be described as a proven resource
registration or architecture-specific cleanup defect.

The independent mDNS probe again returned `NoRouteToHostException` on IPv4
multicast sends (zero successful send returns). Selected, host and socket
interfaces matched; the observed route was UP/IFSCOPE, not REJECT/BLACKHOLE/GATEWAY.
This is not explained by the old dependency-lock issue or a mismatched selected
interface. It does not, by itself, prove the Native browser's failure cause.

### Narrow Intel experiments, not replacement qualification

The explicit `[rpc-intel-investigate]` marker selects two separate native
Intel/macOS-15/Xcode-26.3 jobs, with distinctly named public artifacts:

```text
scripts/with-darwin-audit-session.py --parent "$RPC_QUALIFICATION_PARENT" -- \
  python3 scripts/run-rpc-qualification.py run --lane apple-x64 --intel-investigation native
scripts/with-darwin-audit-session.py --parent "$RPC_QUALIFICATION_PARENT" -- \
  python3 scripts/run-rpc-qualification.py run --lane apple-x64 --intel-investigation cold-boot
```

These commands run only in the admitted disposable hosted context. Each starts
with unchanged native ownership controls and exact architecture/toolchain checks.

- **Native experiment:** run the existing `ios-lan-x64` profile and strict
  coverage assessor, not the expensive full compilation/Swift pipeline. Test-only
  failure annotations distinguish initial-peer, initial-peer-set and rediscovery
  waits. They preserve the **same original timeout exception**, deadlines and
  all cleanup assertions. An independently owned, cancelled/joined collector
  subscribes to the existing diagnostic flow before kit creation, retaining only
  a small closed set of browser/listener/packaging flags. It does not retain raw
  debug text, alter global history/console settings, mock a transport or change
  discovery/admission. Flags aggregate the case's kits and are observations, not
  proof that every diagnostic was delivered. The codes -65570/-65563 are recorded
  by number, not assumed to prove a permission cause without other evidence.
- **Cold-boot experiment:** create a fresh Shutdown device on an independent job
  with no preceding Native, Swift, Gradle or multicast workload; run the same
  `simctl bootstatus <owned-device> -b` under the original **120-second** bound.
  Read-only owned `sysctl`, `vm_stat` and an unprivileged Python metadata/load
  probe before/after retain bounded hardware/VM/load data and executable mode
  booleans. The original auxiliary `ps` probe was refused as detailed below; the
  follow-up does not execute it or claim per-process CPU telemetry. No PIDs,
  command arguments, raw paths or process names are exported. The snapshots are
  not peak-resource measurements or ownership proof.
- On failure, only exact-device finalization and scoped read-only evidence are
  permitted. Unsafe state is never cleared, a snapshot failure cannot replace the
  original boot failure, and later product execution remains blocked. No hidden
  warm-up, longer deadline, extra boot attempt or global service reset is added.

Both modes explicitly export
`FEATURE_ONLY_INTEL_DIAGNOSTIC_NOT_PRODUCT_QUALIFICATION`. They cannot admit full
Apple, ARM or ART qualification; mixing ordinary/diagnostic markers is rejected.
All original full matrix inventories and dedicated ARM phases remain required.
**60 qualification, 14 product-diagnostic, 23 platform-policy and 11 Darwin-session
offline controls passed** before hosted execution; the six new Apple helper tests
still require actual Native execution. The pinned Kotlin 2.4.10 TeamCity logger
uses `Throwable.dumpStackTrace()`, whose implementation includes suppressed
exceptions, so the closed annotations follow the existing Native report path.

Public provider reports corroborate, but do not prove this run's internal cause:
[runner-images #10924](https://github.com/actions/runner-images/issues/10924) and
[#11901](https://github.com/actions/runner-images/issues/11901) describe macOS
local-network permission failures including multicast/private-IP “no route to
host”; [#12777](https://github.com/actions/runner-images/issues/12777) includes
simulator-readiness failures with several distinct mechanisms. Their workarounds
are **not authorization** to alter TCC/SIP, run products as root, automatically
approve permission prompts, kill shared services or substitute a required image.
The older PerfPowerServices issue reportedly fixed in 2025 is not assumed to
explain a current run. The new experiments must provide their own evidence.

### First diagnostic attempt: neither intended experiment executed

[Run 36692979970](https://github.com/p2pKit/P2pKit/actions/runs/36692979970),
source `e9e357614d421e59cee16eeac396cc0b79472e7d`, completed **FAIL** in both cells.
Both independently passed all 122 ownership controls and exact native Intel
toolchain checks. These are new infrastructure observations, **not a new Native
test result or fresh-device boot attempt**:

- **Native cell:** multicast admission failed as before. The following
  `simctl list --json runtimes` itself exceeded its original 120-second bound
  (product -15, final 125, `Product command timed out`), before device creation or
  any Native build. Pending identities, discovery errors and survivors were zero.
  A reconciled absent `ENVIRONMENT_EINVAL` observation is not an unresolved
  ownership leak. Runtime enumeration had succeeded on other Intel runs; this
  attempt does not identify the provider/service's internal reason for the stall.
- **Cold-boot cell:** the fresh iOS 26.2 device was created and verified Shutdown.
  Hardware/memory probes finalized, but the newly added auxiliary `/bin/ps`
  exited zero while its native receipt failed identity verification with
  `IDENTITY_EPERM` (one unresolved identity observation, final 125). Zero pending
  lifetimes/discovery errors/survivors does **not** turn that receipt into a pass.
  The driver correctly stopped before calling `bootstatus`; it subsequently
  verified exact-device Shutdown/deletion. No ownership error was ignored.

The auxiliary process-list probe is not one of the original product/architecture
gates. A system tool may execute with set-id privileges that are incompatible
with the unprivileged ownership observer. That is a hypothesis to verify from
actual file-mode metadata, **not** grounds to exempt it or elevate the observer.
The smallest follow-up replaces only this added diagnostic with an owned Python
probe using `os.stat('/bin/ps')` and `os.getloadavg()`, never executing/copying
`ps`, changing its permissions or reading process arguments/environments.
It records the set-id/root-owner bits and verifies unprivileged execution. There
is no per-process CPU claim. Earlier completed snapshots are now retained even
if a later probe fails, without clearing the failure. Runtime-list/create logs
also receive the existing bounded, closed marker export to avoid an opaque
prerequisite failure. All original readiness/admission gates are unchanged.

The change is covered by **62 qualification and 15 product-diagnostic offline
controls**, including no subprocess/privilege operation in the metadata probe,
strict output shape and partial-observation handling. One fresh bounded
follow-up is justified by this actual auxiliary-probe defect; no failed command
is retried in an unsafe job and no expensive full Apple matrix is requested.
The six new Apple helper tests remain **unexecuted** at this checkpoint.

### Revised diagnostics: actual Native execution and untouched-device boot

[Run 36694674756](https://github.com/p2pKit/P2pKit/actions/runs/36694674756),
source `9a086f88a1e790326a8cc12e519f859ded5eca16`, completed **FAIL** in both
independent Intel/macOS-15/Xcode-26.3 cells. Both passed all **122 native ownership
controls**, required toolchain/architecture checks and fresh simulator creation.
Both selected iOS **26.2**, with x86_64 and arm64 support; neither silently
substituted an ARM runtime, adopted a shared device or changed ownership policy.

**Untouched-device experiment:** the created simulator was verified Shutdown;
no preceding Native/Swift/Gradle product or multicast workload ran. All six
revised before/after hardware, VM and Python metadata/load probes finalized.
The actual runner confirms `/bin/ps` is **root-owned and setuid, not setgid**.
The replacement did not execute it and verified that the observer stayed
unprivileged. This resolves the auxiliary diagnostic's privilege mismatch without
exempting a set-id process or elevating the ownership observer.

Actual `bootstatus -b` passed Data Migration but remained at **Waiting on System
App / status 4**, nonterminal through its last reported **133 seconds**. The
configured product deadline remains **120 seconds**. Controller entry to the
next observation took approximately 178 seconds, including observation and
finalization; this is **not proof of an exact 120-second hard wall-time bound**.
The receipt retained product -15/final 125 and `Product command timed out`, plus
an exec-version observation error: `ENVIRONMENT_EINVAL`, `ENVIRONMENT_EIO` and
`EXEC_CHANGED` appeared in three unresolved observations and one recovered
observation. Final pending identities, discovery errors and known owned survivors
were zero, with stop exit zero. Those final zeros do **not** make the failed
receipt admitted. Of 24 command receipts, 23 finalized; readiness did not.
Only read-only observations and exact-device finalization followed the failure.
The device was Booted at finalization, then verified Shutdown/deleted; Booted is
not completed System App readiness.

| Read-only snapshot | Before boot | After failed readiness |
|---|---:|---:|
| Logical CPUs / physical RAM bytes | 4 / 15,032,385,536 | Same |
| Load averages, 1 / 5 / 15 minutes | 3.312 / 10.203 / 9.877 | 426.955 / 194.265 / 87.273 |
| Free 4-KiB VM pages | 1,356,695 | 109,083 |
| Swap-ins / swap-outs | 0 / 0 | 0 / 0 |

Load average is **not CPU percent**. No per-process CPU measurement was obtained,
so no particular daemon or provider-internal mechanism is blamed. This clean
failure disproves the hypothesis that preceding standalone Native state is
necessary for the readiness stall. It establishes an independent readiness
prerequisite failure under extreme system load, not a product lifecycle leak or
permission to extend the readiness bound.

**Native-only experiment:** real LAN `iosX64Test` recorded **191 passes, nine
failures and one existing ignored case**, across 33 XML suites. The same nine
methods listed above failed. All **26 command receipts finalized**, including
the failed product (exit one, stop zero, no pending identities/discovery errors
or survivors). Device state was Shutdown before and after Native and at final
retirement. The strict assessor retained **CHECK_FAILED**. This scoped run did
not execute core/RPC/sample Native or Swift tests and is not full qualification.
The independent IPv4 multicast check still had two send attempts, **zero send
returns**, `NoRouteToHostException` and matching interface/UP-IFSCOPE route data.

The new Native stack locations now reach `AppleLanDiscoveryFailure.kt` at both
the timeout annotation and observed-marker annotation. However, none of the
marker **messages** survived into XML: the public record still contains only
`ASSERTION` / `TIMEOUT`. Thus the exception was caught in the discovery wait,
but its exact stage and browser flags cannot be reconstructed from this artifact.
The six extra nonfailed cases match the six added helper tests; their individual
identities were not exported, so individual helper execution is not inferred
from that aggregate alone.

### Correct the verified Native diagnostic conversion defect

The complete pinned Kotlin **2.4.10** path explains the missing context:

1. `TeamCityLogger` calls `Throwable.dumpStackTrace()`, which does include
   suppressed exceptions. The initial investigation verified only this step.
2. `KotlinNativeTest` chooses `parseKotlinNativeStackTraceAsJvm`.
   `KotlinNativeStackTraceParser` retains message lines **only before the first
   frame**; subsequent suppressed-message lines are discarded, while their
   frames are flattened into one list.
3. `TCServiceMessagesClient` constructs `KotlinTestFailure` from that first
   message and flattened frames. Its `printStackTrace` prints those frames, not
   the retained original raw stack string. This exactly matches the observed
   annotation source locations with missing annotation messages.

The test helper now uses **distinct, closed test-only exception types** for
the three stages and ten observation flags. Their constructor frames survive
the existing conversion. The original `TimeoutCancellationException` is still
re-thrown unchanged; bounds, collectors and cleanup assertions are untouched.
The exporter recognizes only those exact constructor identities and existing
message markers. No raw logs, arbitrary types, endpoints or payloads are added
to hosted artifacts. New Native regression cases require a real constructor
frame for **every** stage/flag, rather than assuming messages survive. A closed
source-bound helper-case inventory will distinguish their actual pass/failure/
skip outcomes without admitting a failed profile.

Reflecting into KGP's private raw-stack field or publishing raw test output was
rejected as brittle or outside the privacy contract. Replacing/wrapping the
original cancellation was also rejected. The selected correction affects only
test diagnostics, not production transport, permissions or the native executor.
One explicit `[rpc-intel-native-investigate]` push repeats only the existing LAN
Native diagnostic and its unchanged admission/cleanup requirements. It cannot
select cold boot, full Apple/ARM/ART qualification or admission-only work;
ordinary full-matrix entries remain required. The independent clean-boot
experiment is not repeated without a new evidence-supported hypothesis.

Before that push, **17 diagnostic/privacy, 63 qualification-driver, 23 platform
policy, 11 Darwin-bootstrap and seven capacity-analyzer offline tests passed**.
Repository layout, dependency verification, OSV lock coverage, release metadata,
583 relative links across 108 Markdown files and `git diff --check` passed.
These checks do not compile or execute the two new Native regression cases;
their actual Intel results are still required. No production library source,
native ownership executor, platform policy, dependency input or approved plan
was changed by this correction.

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
  Actual follow-up establishes that this alone does not fix the current failure.
- Separate untouched full boot from a Native-only discovery probe: selected as
  a diagnostic, retaining required host, controls, lifecycle and bounds. A passing
  clean boot would justify investigating supported non-standalone Native launch;
  a failure would establish a readiness prerequisite independent of prior Native
  work. Neither is a substitute for full qualification.

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
| Fresh separate large/correctness independent review | `d23a421e3ee522aa76d4be9ea8d6fb01a2ee73cca67dc8fa5c3f354765415643` |
| Intel original artifact ZIP, publisher digest verified | `f7fb9c87700c09325048e28920b220e29a541a995e885be9eb012bbdd7ae3e1f` |
| Intel complete available workflow-log ZIP | `47510811b3fc3807c4da2396d9a5599d922df811663d887919be042114edd517` |
| Intel follow-up 36684095464 artifact ZIP, publisher digest verified | `f5ed0c62ac267138eb8a16fd2237b4af15009bec3696bc062b8f5a2205b98e19` |
| Intel follow-up complete available workflow-log ZIP | `68ab49005e4f223d7bf8e67814ad003e9f762db738f80182532bcf73ff96963d` |
| First Intel cold-boot diagnostic artifact ZIP, publisher digest verified | `1c94b13732d7e2a2fc758f8b7c6cdedba81bb995a760ae34ff743db04f181b7c` |
| First Intel Native diagnostic artifact ZIP, publisher digest verified | `90379895400023258db32b18ae34fc74a35a4d3feff1de27a644b83a9f5cd6a2` |
| Revised Intel cold-boot diagnostic artifact ZIP, publisher digest verified | `2f8bb9f0be4f58aae1a4435eedaf77cd3b8c504e87120e2c94f60af323ef1492` |
| Revised Intel Native diagnostic artifact ZIP, publisher digest verified | `178c79e48a94309971d36663629747977a7f5b3a4f48deb144b106b9e67816b1` |
| Revised complete workflow-log ZIP | `6e7e4c0ed16ca26603502129f46e541487f92404ebb49df429562acce9b13071` |
| Independent review of both revised diagnostics | `48f473fa4a6bbc0b5219a78fead0c99d5a8bee59b219cfe67bf77986ceb0a784` |

The original Intel artifact, decoded summary, complete workflow logs and
independent review remain under `actions-36676816096/`. No failed attempt is
deleted, relabeled as passed or overwritten by a later source.
The corresponding complete available logs and decoded artifact for the completed
follow-up are in `actions-36684095464/`. Offline diagnostic controls and pinned
public Kotlin/provider research are retained beside them, not as release evidence.
`actions-36692979970/` retains both first diagnostic artifacts, complete available
workflow logs and per-job prerequisites. The failure before each intended
experiment is preserved rather than described as an attempted/passing test.
`actions-36694674756/` retains the actual revised Native/cold-boot artifacts,
complete available workflow logs, publisher metadata and
`independent-diagnostic-review.json`. `kotlin-simulator-source/` additionally
retains the public pinned parser/client/failure source, with Git blob hashes
verified against its API metadata. No missing original raw Native XML is claimed
recovered from a sanitized artifact.

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
