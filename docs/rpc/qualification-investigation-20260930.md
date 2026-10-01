# Intel and 128-client investigation — 2026-09-30

## Scope and current conclusions

Feature branch: `work/rpc-lan-20260927-054728-8b1b11da`, in the separate
`/root/projects/p2pkit-feature-prep-20260927-yiDjCB` clone. No other session's
directory, source, keys, private evidence or CI was used. All release HOLDs
remain; Release Foundation is **NOT_READY**. Instructions and the approved plan
are unchanged. The known `org.jmdns` lock baseline is unrelated to these failures.

- **Current full-rate qualification remains open.** The latest instrumented
  [complete run at `1b3c4169`](#october-1-instrumented-full-run-cpu-pressure-and-fresh-snapshot-candidate)
  returned **2,233,926 responses / 70,074 pre-invocation missed slots**, zero RPC
  errors, and verified cleanup. Both JVMs share four CPUs; the JFR observation
  reports approximately **97.7% total machine CPU load**, predominantly JVM
  system time. This establishes saturation, not a proved kernel hot path. A
  fresh-per-check LAN snapshot reuse candidate removes a redundant enumeration
  without caching, fewer checks, or interface exemptions; it still needs runtime
  regression and the entire unchanged workload. The **earlier** full-rate
  same-host JVM steady workload passed at `911e5edf`.
  All **2,304,000** responses completed over the full 30 minutes, with **zero**
  missed slots/RPC failures, p95/p99 **14/32 ms**, bounded observed resources and
  verified teardown. See the [independently reviewed result](#october-1-full-rate-30-minute-same-host-jvm-workload-passed).
  This is not physical-LAN or mobile capacity qualification; subsequent-source
  regressions passed but full-rate workload reruns failed as retained below.
  The preceding hosted full 30-minute run at
  `7b23caae` completed 2,301,188 calls with **2,812 pre-invocation permit refusals**,
  zero timer/worker misses and zero RPC failures. Unlike the earlier VPS runs,
  its generator showed no balloon/reclaim or long-safepoint stalls. See the
  [separate full-run investigation](#october-1-complete-hosted-capacity-run-permit-saturation-not-timer-loss).
  Fixed, separately accounted initialization precedes the unchanged full
  steady-state gate; cold-start peak load is not qualified. Its first attempt
  stopped at JVM regression before any workload;
  the [diagnostic follow-up](#october-1-jvm-regression-stopped-the-next-capacity-attempt-before-load)
  preserves that failure without guessing its cause. The historical missed sends are generator slots
  rejected before RPC invocation, not remotely lost RPCs. The earlier complete VPS run
  attributes each slot and strongly associates the timer/worker stalls with
  independent guest memory-balloon/reclaim activity. No product capacity change is
  justified by that evidence. The first separate hosted attempt passed fresh JVM
  regression, real-socket correctness, large payloads and the independent healthy
  clock preflight, but its steady phase exited before producing an admissible
  measurement. Its exact underlying failure is not established by the original
  export. The [failed-attempt diagnostic correction](#october-1-healthy-hosted-preflight-steady-phase-unadmitted)
  retains that failure and repairs reporting, not a product capacity claim.
- **The original nine Intel LAN failures are resolved; full Intel qualification
  is still pending.** The historical diagnostic run established nine LAN Native
  failures and a system Data Migration readiness timeout, not a renewed native
  process-ownership admission defect. A reporting defect and an ordinary
  Native-to-Swift lifecycle omission have been corrected. The completed follow-up
  maps all nine failures but **disproves stale Booted state as their explanation**:
  the simulator was already Shutdown and the same failures remain. Independent
  diagnostics now reproduce a clean-boot **System App readiness timeout** without
  preceding product work and nine discovery-wait failures. Native's intermediate
  report conversion discarded the new context messages. A subsequent real run
  also exposed an incorrect exported-symbol assumption in the test-only frame
  reader. The correction is now verified by all **eight actual Intel Native
  helper tests**. Before environment correction, the original nine cases timed
  out at initial Bonjour discovery, with advertising/browser/listener-ready flags
  but no observed browse-result callback. The corrected disposable test environment
  now passes the identical **203-case LAN inventory: 202 passed, zero failures,
  one pre-existing ignored diagnostic**, including all nine original failures.
  The complete `2bd107b3` Intel run repeated that discovery pass, but exposed
  a separate Android host-test failure and another original-bound simulator
  Data Migration timeout. Those two failures remain under investigation, not
  relabeled as discovery failures or ownership defects.
  The [separate runtime diagnostic](#october-1-intel-host-failure-identified-and-fresh-gui-timeout-reproduced)
  now identifies the host method and its accept-path source location, and
  reproduces readiness failure without any preceding Native/Swift execution.
  Product/test sources, coverage policy and individual bounds are unchanged.
  This is not a production-networking workaround or a full-matrix claim.
- The owner deleted the supplemental Mac before additional remote files could
  be copied. Source and earlier Linux exports survive; original Mac-only XCTest
  bundles and the unsigned iPhone app were **not recovered**.
- **Full native ARM follow-through:** the verified Intel disposable-runner
  preparation is now explicitly bound to either actual Apple architecture. Its
  [ARM application](#october-1-native-arm-environment-follow-through) preserves
  every original full-platform and owned-cleanup phase. The first actual run
  passed 125 native controls and Terminal retirement, but stopped at the strict
  Bonjour preference snapshot **before any setting change or product test**.
  Full ARM qualification remains blocked; no Intel result is reused as ARM
  execution evidence.
- The launchd-context endpoint probe reported **Local Network Denied** for the
  host. A subsequent verified Terminal-context run allowed both host/simulator
  raw multicast sends, but **all inline-TXT browsers still lacked callbacks**.
  Successful sends are not multicast-receipt or physical-LAN proof. The next
  narrow SSH comparison verified its native authenticated audit session but
  reproduced denial and missing TXT results. The completed interface-directed
  comparison now observes the host's global **`NoMulticastAdvertisements=TRUE`**:
  explicit selected-interface browsing/resolution has no callbacks even though
  registration succeeds. Actually loaded executable declarations do not repair
  inline-TXT browsing. The actual reversible setting write/restoration has now
  executed, but reload failed with **service not found (113)** for the old hard-coded
  launchd name. With the installed service label verified, the completed same-runner
  A/B now proves **all 38 native OS observations pass** after disabling only that
  advertising suppression, followed by exact setting/service restoration. The
  subsequent original Kotlin LAN profile also passed independently. GUI readiness
  and the complete matrix still require execution; OS-probe success is not
  substituted for those tests.
- The first original-product follow-through at `d6d8a2a1` passed the unchanged
  **JVM multicast readiness/disposal control**, native admission and exact
  advertising-setting restoration. It stopped before Kotlin because the first
  `simctl list --json runtimes` returned no output within its original **120-second**
  bound. No simulator was created. This is a runtime-enumeration prerequisite
  failure with zero ownership-discovery errors, not evidence of another native
  ownership-permission defect. Its internal cause is not yet established. An
  identical-source fresh-runner comparison passed enumeration and the complete
  original LAN profile; the first failed allocation is retained, not erased.

This is source-bound local/hosted evidence, not physical LAN, cross-device,
Android/iPhone hosting capacity, or release readiness.

## Bonjour OS-API differential and SSH-context experiment

[Run 36717690273, attempt 2](https://github.com/p2pKit/P2pKit/actions/runs/36717690273/attempts/2),
source `c1c09d1de1bb03073a285498b6680671ce4594af`, completed **FAIL** on the
required Intel/macOS 15/Xcode 26.3 cell. All **122 native ownership controls**,
**51 command finalizations**, source rechecks and exact simulator retirement
passed independently of the failed network observations. There were **28 actual
C observations**, compiled separately for the macOS host and the standalone
iOS 26.2 x86_64 simulator. Attempt 1 failed the unchanged runtime-enumeration
prerequisite before compiling/running a network probe; it is retained separately.

Both native contexts show the same differential:

- Selected-interface BSD multicast has zero setup/close errors but fails
  `sendto` with **65 / EHOSTUNREACH**. No successful multicast send is claimed.
- DNS-SD Any and explicitly LocalOnly register/browse controls succeed.
- Basic Network.framework browse, late attachment, default domain, legacy
  spelling, and publication of TXT without requesting inline browser TXT work.
- Every inline-TXT browser variant, including empty TXT and TCP parameters,
  produces **zero browse callbacks** under its original bound.
- The separate-TXT diagnostic gets the exact synthetic TXT using DNS-SD and
  connects/accepts through the **actual Bonjour endpoint**, with queue-confined
  DNS query deallocation and complete native cleanup. This does not authorize
  substituting a DNS-SD fallback into production.
- Direct resolution returns the correct synthetic TXT and port, but its SRV
  target is **`LOCALHOST`**, not a case/terminator spelling of a `.local.` name.
  The original `localTarget` assertion remains false and that probe remains
  failed. A same-host connection is not proof of multicast or physical LAN.

Pinned public Apple mDNSResponder source (`d4658af3f5f291311c6aee4210aa6d39bda82bbe`,
`mDNSCore/mDNS.c`) uses `localhost` for LocalOnly registrations. This supports
investigating local-only/system-policy behavior, but is **not proof of the
running OS's private implementation or its denial cause**. Apple's TN3179
documents that simulator local-network privacy is unsupported, and that macOS
command-line descendants of Terminal/SSH are automatically allowed. Therefore
missing simulator Info.plist declarations alone do not explain these results.

The next narrowly scoped experiment uses
[`with-darwin-ssh-context.py`](../../scripts/with-darwin-ssh-context.py). It creates
one disposable loopback SSH **control** session on the authorized hosted runner,
with independent fresh Ed25519 client/host keys, exact host-key verification,
public-key-only authentication, one allowed invoking account, PAM account checks,
fixed command, no terminal, no user SSH RC, and no forwarding/tunnel capability.
System `sshd -i` handles only one accepted loopback socket. Its authentication
bootstrap is privileged; the actual child verifies original nonroot credentials
and inability to regain root, then runs the **unchanged audit-session and native
ownership executors**. No production networking/security code, TCC/SIP state,
system SSH configuration, user keys, firewall, route or host permission is changed.
This is an explicit diagnostic opt-in, not a new production default.

The collector requires the exact authenticated child exit, both SSH endpoints
reaped, closed listener, removal of all fresh credentials, source identity and
native receipts. Missing/failed SSH finalization prevents a passing result;
successful control cleanup cannot erase a failed product exit. Only closed
counts/status/error categories are exported, never keys or raw SSH logs. The
C probe additionally records closed LocalOnly/loopback-interface observations;
these fields do not change its pass assertions. The service-name offset is
expressed using the prefix size defensively; the **original offset 13 was already
correct**, so no naming/collision root cause is claimed.

Alternatives rejected for now: root product tests, TCC edits, relaxed multicast
checks, numeric-endpoint substitution, a new production TXT resolver that might
merely conceal host policy, or inferring LAN from a LocalOnly success. Local offline controls passed: 11 SSH-context, 11 audit-session, 68 qualification,
21 network-diagnostic and 18 product-diagnostic tests, plus repository layout,
lock coverage, Markdown links, release metadata and `git diff --check`. These
are not Apple execution. The SSH experiment still needs actual native execution. The original nine Kotlin cases,
independent full-simulator readiness, multicast gates and healthy full-rate
30-minute capacity run remain pending; no new passing workload is claimed.

Evidence remains under `.git/rpc-bonjour-qualification-20260930.oOYgSoqr/` in the
isolated clone. Attempt 2's artifact ZIP SHA-256 is
`38c6cff8192d3b28b12995e7505fc0ee82748a801d6c91ee6adfaf4aaaa39959`,
complete available workflow logs ZIP
`a79cc674481fcc20f82e75e1a5beee77df1a9a9327d5cbe79a3f0bb87d9350f1`,
and independent review
`730c6e9800055a107c7b3cc9e5620e397a4360e3793bdc701e5a9093b9b26e06`.
All previous failures and release HOLDs remain authoritative.

## SSH follow-up and nonroot launchd comparison

[Run 36728648795](https://github.com/p2pKit/P2pKit/actions/runs/36728648795),
source `85a8e3ca983594c6b3bd0880dd475168ba97a77c`, completed **FAIL**. The actual
authenticated nonroot SSH child completed 122 native controls, 51 finalized
commands and all 28 host/simulator observations. Exact source and simulator
retirement were verified. The new locality fields establish that **every
successful Any-interface DNS browse addition was LocalOnly**, both separate TXT
resolutions were LocalOnly, and all observed Network.framework results and
connections used loopback. Raw multicast still failed `sendto` with errno 65;
every inline-TXT variant still produced zero callbacks. The supported-control
hypothesis did not fix this execution context. No nine-case Kotlin pass is inferred.

All SSH cleanup flags were true, but the inetd server exited **255**, not the
required zero. The finalization validator correctly rejected that separate
control exit. It has not been relaxed. The child failure, cleanup checks, raw
publisher-verified artifact and complete workflow logs are retained. Artifact
SHA-256: `96ab8e85f4f73d385314adb3231e466fb56921a9f473afeca9e928db4b5f7d82`;
logs ZIP: `e51d5414d2f6464ae54b992919a23a604455af2d441922d23918227b686f83e5`.
The independently reviewed result is in `actions-36728648795/` under the same
private continuation-evidence directory. This is not a claim that Terminal/SSH
is universally broken or proof of the runner's exact responsible-code attribution.

The next diagnostic compares the original APIs from a **nonroot system launchd
job**, the other explicit automatic CLI permission context documented by Apple
TN3179. The feature-only [`with-darwin-launchd-context.py`](../../scripts/with-darwin-launchd-context.py)
creates one random, nonpersistent system job with the invoking `UserName` and
`GroupName`, no socket, no KeepAlive, no schedule, and a fixed command. Its plist
is fresh task state, not an installed `/Library/LaunchDaemons` entry. Root is
used only to bootstrap/remove that exact job. The direct child must have
launchd as its parent, the original nonroot account/group policy and no
recoverable root privilege. It then executes the **unchanged** audit-session,
native ownership, product and finalization paths. No policy, permissions, TCC,
SIP, routes, interface, production adapter or security assertion changes.

Removal is allowed only after the exact child result and stopped job/exit are
verified, never by signaling an arbitrary PID. A collector requires removal of
the job and plist as well as the source-bound native receipts; failed or missing
finalization cannot pass. The experiment is initially restricted to the Intel
network-diagnostic lane. It is not application-permission, GUI readiness,
physical-network, ARM or capacity qualification. SSH remains opt-out because
its tested hypothesis failed. Production discovery code is unchanged; root
product execution, permission automation, weaker TXT validation, and relaxing
multicast gates remain rejected alternatives.

Local pre-dispatch checks passed: **13** launchd-context controls, 11 SSH-context,
11 audit-session, 68 qualification, 18 product-diagnostic and 21 network-diagnostic
controls; repository layout, lock coverage, Markdown links, release metadata and
whitespace checks also passed. These are offline checks, not a native result.

The first launchd dispatch,
[36731776430](https://github.com/p2pKit/P2pKit/actions/runs/36731776430),
failed **before native execution** in the new offline fixture. Its accepted
configuration used literal `/tmp/fixture`, while Darwin resolves `/tmp` to
`/private/tmp`; the unchanged physical-path admission correctly rejected that
mismatch. The fixture now uses the actual canonical temporary parent and adds
a portable alias regression. No production or ownership path boundary was
relaxed. All **14** launchd-context offline controls now pass locally; this is
not evidence that launchd or the nine discovery cases ran. The original failed
artifact/logs are retained in `actions-36731776430/`. Artifact SHA-256:
`e1746d5741cf9731b28409db35df9b8577b1589c359cd4992b602b893efe4cd3`.

### Verified launchd result and endpoint-specific policy investigation

[Run 36732417495](https://github.com/p2pKit/P2pKit/actions/runs/36732417495),
source `f28f0a0afa56539761e899028f1a4d3b3311aac5`, completed **FAIL**. All 122
native controls, all 51 command finalizations, exact source checks, simulator
retirement, and the nonroot launchd context's job/plist cleanup passed. The
context child returned **1** because the original network observations failed;
successful context cleanup did not erase that result. Twelve of the 28 native
host/simulator observations failed with the same differential: selected-interface
BSD multicast `sendto` returned errno **65**, and every inline-TXT browser had
zero result callbacks. Observed basic-browse results were LocalOnly/loopback.
The documented nonroot system-job comparison therefore did **not** fix this
runner. No original Kotlin test, GUI-readiness gate or capacity workload ran.

Publisher-verified artifact SHA-256:
`04d667d38f9aa433fc014a7f902c87a656f3a0c8850f7e70940887ca483925d0`;
complete available workflow logs:
`31f14d3b2ea00bc70161831213dc39dd5a2e148555d66444f36993f85ea983af`.
The separate `actions-36732417495/independent-review.json` rechecked all command
diagnostics, exact commit/tree, all 28 observations and context finalization.

Public [runner-image issue 13230](https://github.com/actions/runner-images/issues/13230)
reports the same basic/TXT-browser differential. Its July 21 linked successful
reproduction changed the runner label to `macos-15` and launched an iOS **app**;
it is not our required Intel/Xcode/native-executable result or proof of a
particular policy denial. [Issue 10924](https://github.com/actions/runner-images/issues/10924)
also documents multicast `No route to host` and unresolved local-network
attribution. Those reports inform alternatives, not acceptance verdicts.

The next bounded probe adds **only** a UDP Network.framework path observation
to the fixed mDNS destination, with its source bound to the selected private
interface address. The prior satisfied monitor/TCP paths were unicast and cannot
establish the multicast endpoint's effective policy. The new observation records
an actual `local_network_denied` reason if reported, before cancellation can
replace the path. It sends no application data, retains all previous probes and
their assertions, and requires its own cancelled callback and queue teardown.
UDP readiness would not prove multicast delivery. No production fallback,
permission grant, route change, root product execution or ownership exception is
introduced. Its subsequent native execution is recorded in the next subsection.

Separately, the hosted capacity reader now shares the analyzer's existing
bounded **9-MiB** per-rotation allowance: JVM's nominal 8-MiB rotation occurs
after a record is written. Eight offline analyzer controls and nine hosted-driver
controls passed, including oversized/symlink/duplicate input rejection. This
prevents a parser-only evidence failure; it is not a new capacity run. Discovery
verification still precedes the full hosted capacity dispatch.

### Actual endpoint-specific denial and a bounded Terminal comparison

[Run 36734896195](https://github.com/p2pKit/P2pKit/actions/runs/36734896195),
source `a0a1708798417fa749e7fd3e1b8641b2a6300cfa`, compiled and executed the new
probe on both actual Intel contexts. All **122 native controls**, **53 command
finalizations**, source checks, and exact simulator/launchd retirement passed.
Thirteen of **30** primitive observations failed; the diagnostic remains **FAIL**.

- The host's source-bound mDNS UDP path was **unsatisfied**, with
  `nw_path_unsatisfied_reason_local_network_denied` (**3**), waiting rather than
  ready. Cancellation and queue teardown completed. This is an OS-reported
  policy denial, unlike the earlier inference from errno 65 alone.
- The simulator's corresponding path was satisfied/ready, with reason zero,
  but its independent BSD multicast send still returned **EHOSTUNREACH (65)**.
  UDP readiness sent no data and is **not multicast delivery**. This difference
  prevents attributing all the failures solely to the host path observation.
- Both BSD probes still failed, inline-TXT browsers still had no callbacks, and
  separate TXT/basic-browse results remained **LocalOnly/loopback**. None of the
  original Kotlin cases or GUI-readiness tests was rerun or newly passed.

Publisher-verified artifact **11108035294** SHA-256:
`a1ee776c3a243ca2a321c20fd2d320e2996662f2a9730d73f52466631fb6da93`.
Complete available workflow logs:
`c4693e113d70d420825cf15b7ad5ec8c9f980b75aaf8c6c93b144773af7fcfdb`.
The retained `actions-36734896195/independent-review.json` independently checks
the exact source, every command's pending/error/survivor/finalization fields,
all 30 observation/exit pairs, all available log bytes and context retirement.

Apple TN3179 also documents **Terminal descendants** as an automatically allowed
CLI context. The test-only [Terminal controller](../../scripts/diagnostics/apple-terminal-context.m)
and [wrapper](../../scripts/with-darwin-terminal-context.py) investigate that
remaining documented alternative, not an undocumented entitlement or permission
override. The workflow opts into it **only for the Intel network diagnostic**;
all product/ARM roles keep their original execution and complete inventories.

The controller requires the invoking nonroot account to own the console and
refuses a preexisting Terminal. LaunchServices opens one private, fixed command
in a fresh system Terminal instance, with prompts disabled and no AppleScript,
clicks, TCC/SIP edits, route/firewall changes or defaults writes. The child proves
its kernel parent-unique-ID chain to the retained application's original UID and
start identity, then runs the **unchanged** audit-session/native executor. No
ownership capability is fabricated. The shell waits for that exact child before
recording its exit; only afterward may the controller request ordinary Quit on
the retained application object. Forced/PID-based termination is forbidden.
Application termination, child reaping and exact private-command removal must
all be verified; refusal, prompts, errors or uncertain cleanup remain failures.
Only closed flags/error categories and log hashes are exported, never identities
or raw context logs. A failed primitive child remains failed even if cleanup passes.

Local **offline** checks passed: 10 Terminal-context, 14 launchd-context,
11 audit-session, 11 SSH-context, 23 network-diagnostic, 18 product-diagnostic
and 68 qualification controls, plus layout, OSV coverage, Markdown links,
release metadata and `git diff --check`. These do **not** compile AppKit or
execute Terminal, Native tests or a capacity workload. Native execution of this
context, original discovery/cold-boot recovery and the subsequent full 30-minute
capacity qualification remain required. All HOLDs and **NOT_READY** are intact.

The first Terminal execution, [run 36737469811](https://github.com/p2pKit/P2pKit/actions/runs/36737469811)
at `1113e4e975f6d9880b070b322e78b601a313b43a`, compiled the AppKit controller
without diagnostics and created the fresh application as the actual console
user. Its fixed child stopped at **native ancestry admission**, before any
native control, simulator creation or network probe. The shell reaped that
child, the retained original application quit and terminated, and the exact
private command was removed. Source remained unchanged. The outcome is **FAIL**,
not a discovery attempt or pass. Publisher-verified artifact SHA-256:
`56f02827864f1f7e35a93c20cd287687f5696452f7e59e65eee1f6f6f4b3c41c`;
complete available logs:
`bca761153cc5776bad61955625cbfc34e24a91adbdfd8b41e9b92afd2b199107`.
Its independent review verifies application cleanup separately from the refused
native work. The next diagnostic distinguishes the exact ancestry assertion
(native API, PID/lifetime, UID, parent-unique-ID or start identity), including
whether an observed privileged intermediary is the **actual `/usr/bin/login`
image**. This is read-only classification, not a new exception: every original
ancestry and nonroot assertion still rejects the same inputs. Eleven offline
Terminal controls pass, including proof that a privileged login still fails.

The follow-up [run 36738083575](https://github.com/p2pKit/P2pKit/actions/runs/36738083575)
at `73c35ec5174667c3d8d12524daba71af3eadf5dd` again retired the exact application,
but now identifies the failed check as **the native combined-identity API read**,
before credential/parent assertions. No native product/control ran. Its original
publisher-verified artifact and complete available log hashes are respectively
`f4f663730ea63004a23b9216b2d0c3e804ca7f598ea55c000da8f0e4a08799b1`
and `8c7ed6f5b8648dd1e1a6be94156bbf5db74407de67ade1aef689836557611f3e`.

Inspection of Apple's [kernel implementation](https://github.com/apple-oss-distributions/xnu/blob/main/bsd/kern/proc_info.c)
establishes an API-contract difference: combined full BSD/unique information
(flavor 18) requires matching effective UIDs; limited BSD (13), unique identity
(17) and image-path queries do not impose that extra UID requirement. All still
undergo kernel MAC policy checks. Apple's [login implementation](https://github.com/apple-oss-distributions/system_cmds/blob/main/login/login.c)
explicitly forks **before** dropping privilege because its parent must close
the PAM session. Requiring every Terminal ancestor to be an ordinary same-UID
product and querying it with the full-info API is therefore not a sound context
model. This source analysis alone does not prove which intermediary that run
encountered; the corrected reader records an actual restricted-API denial and
verified system-login count to check the explanation natively.

The test-only origin reader now uses limited BSD/path observations **bracketed
by matching kernel unique identity and exec-version records**. Credential,
parent, lifetime or exec changes fail. Same-UID ancestors, especially the exact
retained Terminal, still require the original full start identity. At most one
privileged intermediary is accepted, only for the actual `/usr/bin/login` image
directly parented by that exact Terminal and with a matching kernel
parent-unique-ID link. The diagnostic child itself can never use this exception:
its original UID/groups, inability to regain root and unchanged native executor
remain mandatory. The OS login process is **not adopted or signaled**. A failed
kernel observation, arbitrary/root image, replaced parent or uncertain origin
still fails. This corrects test-context observation, not production ownership.

Running the observer as root, removing native admission, trusting a process name
or using a PID to signal the OS helper were rejected. Only closed ancestry counts
are exported; native identifiers remain private. Fifteen local offline Terminal
controls cover the permitted read sequence, original EPERM negative control,
PID/exec/parent/credential races, wrong images, root-child rejection and public
evidence bounds. The unchanged production ownership module is not edited.
The next native run must prove this context correction **and still execute the
original 122 controls and all 30 networking observations**; no discovery or
capacity result is inferred from offline fixtures or successful GUI cleanup.

### Verified Terminal origin, working send returns, still missing TXT results

Both attempts of [run 36739975307](https://github.com/p2pKit/P2pKit/actions/runs/36739975307)
used exact source `25abaaf39ef058cfa5869a95ac020ba12cb5be4e`. The actual kernel
observations verify the ancestry correction: depth **5**, one genuine privileged
system-login ancestor and one original combined-identity permission denial.
The exact Terminal, fixed child and command file were retired in both attempts.

- **Attempt 1: FAIL.** All **122 native controls** passed. Eight commands
  finalized; the ninth, `simulator-runtimes`, exceeded its unchanged **120-second**
  bound (product -15, final exit 125). Finalization correctly failed. No simulator
  was created, and no networking observation or Kotlin test ran. This is retained
  as a prerequisite/ownership failure, not a network result.
- **Attempt 2: FAIL.** One unchanged fresh allocation completed in **13m16s**:
  **122 controls**, **53 verified command finalizations**, and all **30** actual
  C observations. Source, exact simulator retirement, Terminal shutdown and all
  pending/discovery-error/owned-survivor counts were independently checked.
  Both BSD probes returned successful sends (errno zero), and both source-bound
  UDP paths were satisfied/ready without an OS local-network denial. Nevertheless,
  **10 observations failed**: every inline-TXT browser still had zero callbacks,
  and the exact-TXT/port resolver's first target was `LOCALHOST`, not `.local.`.
  First Any-interface DNS additions remained LocalOnly; separate-TXT/basic
  connections used loopback. No original Kotlin test, full JmDNS admission,
  untouched GUI-readiness test or capacity workload ran.

The successful raw sends are a genuine differential from earlier allocations,
but changing both the execution context and runner allocation prevents assigning
the difference exclusively to Terminal. They neither prove multicast receipt
nor fix the absent inline-TXT callbacks. The DNS diagnostic currently stops at
its first own-service addition/resolution: a LocalOnly first result does **not**
prove that a later interface-specific result is impossible. All original failed
assertions remain failed; none was waived on that basis.

Evidence is retained in `actions-36739975307/` and
`actions-36739975307-attempt2/` under the private continuation-evidence directory.
Each includes original publisher-verified artifact, complete available workflow
logs and independent review. SHA-256 values (artifact / logs / review):

```text
attempt 1:
decbba9c0b39640ce65e1fd54549c2c9fa6645153c6bb446c29ca381b063f351
39b1c6a9a84d7e1ae7980304824cd02c2da999d6247014d8c66541ed58acf5d5
4d740dcf951a678b6adadca29d86b0930c76335c525c1d1d7c76498842f36bb4
attempt 2 (artifact 11111316300):
b9117907be39a58890db64b79a999575b8413719ea1625489ee6a44fd59a55d8
7aec486e9fa2b652567f7265a66ad9e0a84f1c4903e785876d40e4cbcb5f55e0
c76059457e83042187176567c8b27298c666a879a81536822b439163bda9aaaf
```

### Native SSH-session comparison and exact protocol-close evidence

All previous context comparisons allocated another audit session **after**
entering Terminal/SSH/launchd. Apple's public OpenSSH source at
`f386b2e948280f6ecac875329c0b56020821d558` establishes that authentication itself
creates an assigned audit session (`openssh/audit-bsm.c`, called from
`sshd-session.c`). The new `--native-session` experiment therefore keeps the
authenticated SSH child's observed native session. It is restricted to the
**Intel network diagnostic**, not full/native/ARM qualification. It requires a
nonroot authenticated audit user, an assigned session distinct from the
controller's, and an unchanged before/after observation. An incoming session-ID
environment variable is still rejected. The actual native ownership executor
and all 122 controls remain unchanged; a session ID is not ownership authority.

The earlier SSH exit 255 is separately investigated rather than ignored. Pinned
Apple OpenSSH `clientloop.c` sends normal disconnect reason **11** after command
completion; `packet.c` handles it as `SSH_ERR_DISCONNECTED` and calls `logdie`;
`log.c:440–449` logs at INFO and exits **255**. ERROR logging had suppressed that
reason in the old failed run, so its cause cannot be retrospectively certified.
The new wrapper retains INFO in fresh **0600** private logs and requires the
exact ordered acceptance/normal-disconnect/authenticated-user-close events for
the fresh client key, account and loopback peer port. Bare 255, another reason,
wrong peer/key/user, missing/reordered/duplicate events or unexpected output
still fail. It exports only bounded counts and hashes, never identities or raw
authentication lines. All child, socket, source, credential-removal and native
finalization checks remain; a failed child remains failed. This is a source-
supported infrastructure correction **awaiting actual native verification**,
not a suppression of cleanup errors.

Changed files are the SSH wrapper and controls, explicit diagnostic workflow,
public-summary scope check, Terminal opt-in fixture and these reports. Root
product execution, weakening ownership, TCC/SIP/route/firewall edits, accepting
LocalOnly as LAN, removing TXT validation and increasing bounds remain rejected.
The original nine tests, GUI readiness, complete Apple matrix and the later
healthy-generator 30-minute capacity run remain required. All release HOLDs and
Foundation **NOT_READY** are unchanged.

Pre-dispatch local offline checks passed: **17 SSH**, **15 Terminal**, **14
launchd**, **11 audit-session**, **68 qualification**, **18 product-diagnostic**,
**23 network-diagnostic**, **8 capacity-analyzer** and **9 hosted-capacity-driver**
controls. Repository layout, OSV lock coverage, release metadata, **598 relative
Markdown links** and `git diff --check` also passed. No local Java/Gradle build,
new capacity workload or Apple execution is represented by these checks.

### Native SSH session: actual hypothesis failure, not a discovery repair

[Run 36744969088](https://github.com/p2pKit/P2pKit/actions/runs/36744969088), source
`edd7d61c0b7640a88de1bbc12c26f2e4350fd414`, completed **FAIL** in **13m7s**.
SSH's actual audit session was assigned, distinct from the controller's, owned
by the authenticated nonroot audit user, and unchanged afterward. All **122
native controls**, **53 command finalizations**, source checks and exact
simulator retirement were verified. The experiment nevertheless reproduced the
host's explicit **Local Network Denied** observation, both BSD `sendto` errors
**65**, and every missing inline-TXT result. **13/30** OS observations failed.
Reallocating a second audit session is therefore **not necessary** for this
failure to occur; omitting it is not a supported fix.

The SSH server returned 255 with all three expected exact accepted-key,
reason-11 and authenticated-user-close lines, **plus one unrecognized line**.
All child/socket/credential/reaping flags were true, but the ordered-close proof
was correctly rejected (`UNPROVEN`; wrapper exit 125). Its 319-byte private log
was represented only by counts and SHA-256; its unknown line is not explained
or ignored. The earlier server-close assumption has not yet been fully proven
against native output. This SSH context is now opt-out again; no unproven
cleanup is used to admit a product run. Original Kotlin, GUI-readiness and
capacity workloads were not executed.

The independent review checked every exported receipt diagnostic, all 30
observation/exit pairs, the session flags and strict closing rejection, source,
complete available workflow logs and exact simulator retirement. Artifact
**11112323707** SHA-256:
`c89ffbffe5c483b00026ab1e68c328ab3c17ce814d4d4fe3f6395e88f41d8516`;
logs: `108f2c7c5ebf3999f123ac458bf37e6bf10da61b69b2a802f803dd48f92e8735`;
review: `bc2d576e9adec6b49da6e18940eb7c98b248ed844ff266d09067df266605e541`.
These remain under `actions-36744969088/` in the continuation-evidence directory.

### Additional scope and metadata controls, without a production workaround

The next Terminal-context experiment retains all original **30** observations
and their bounds/assertions, adding **eight** observations (four per context):

1. `dns-selected` uses an actual observed UP, multicast-capable, non-loopback,
   non-point-to-point RFC1918 interface index for both registration and browse.
   Only an own-service addition on that **exact index** can pass; LocalOnly and
   other-interface responses cannot substitute. Candidate counts and error codes,
   not interface names/addresses, are exported. This is diagnostic selection,
   not a production whitelist or proof of physical LAN.
2. `dns-resolve-selected` binds registration, resolution and independent TXT
   query to that observed index. Exact synthetic TXT, port, `.local.` target,
   both returned interfaces, bounded completion and deallocation remain required.
   The existing Any/LocalOnly controls are untouched. This tests the previous
   first-result scope ambiguity without waiving the original failed assertion.
3. `network-declared` compiles the same C source with checked-in Mach-O
   `__TEXT,__info_plist` metadata. It observes the **actually loaded** identifier,
   nonempty local-network usage description and both exact service declarations,
   then runs the same production-shaped inline-TXT networking and cleanup checks.
   The baseline executable is still compiled **without** this section. Declaring
   intended network use is not granting permission; no TCC/SIP changes, entitlement
   override, consent automation, or privileged network operation is introduced.
4. `mdns-policy` reads only the documented global `NoMulticastAdvertisements`
   preference through `CFPreferencesCopyValue`, without writes or synchronization.
   Only a closed value-kind is exported. `NOT_RETURNED` does not distinguish an
   absent/unavailable value; even `FALSE` cannot prove the daemon's loaded policy
   or local-network permission. Successful observation is not network admission.

The public Apple man page at mDNSResponder source
`d4658af3f5f291311c6aee4210aa6d39bda82bbe`, `mDNSShared/mDNSResponder.8`, documents
that optional preference. Its existence motivates an observation, not an
assumption that the hosted runner sets it. No preferences, daemon, route,
interface, production networking code or original test timeout is changed.
Compiler and observation records distinguish the declared binary from both
original binaries. Offline controls reject missing declarations, wrong returned
interfaces, LocalOnly substitution, wrong TXT/port/target, failed cleanup and
unbounded/private fields. Actual native execution and the original nine tests
still remain necessary before claiming recovery or dispatching capacity.

Pre-dispatch offline controls passed: **28 network-diagnostic**, **68
qualification**, **18 product-diagnostic**, **17 SSH**, **15 Terminal**, **14
launchd** and **11 audit-session** tests. Layout, OSV coverage, release metadata,
**599 relative Markdown links** and `git diff --check` passed. These are not C
compilation, native networking execution or capacity measurements.

### Verified configured advertising suppression and bounded same-runner A/B

[Run 36747721136](https://github.com/p2pKit/P2pKit/actions/runs/36747721136), source
`1fe7ebbef86a78e3130be1b3d9c6295028e623c9`, completed **FAIL** in **14m37s** on
native Intel/macOS **15.7.9**, image **20260824.0482.1**, with Xcode 26.3. Independent
review checked all **122 native controls**, **63 command finalizations**, **38
observation/exit pairs**, four successful diagnostic compilations, exact source,
Terminal retirement and simulator deletion. Every receipt had zero errors,
discovery errors, pending observations and known owned survivors. Terminal
returned the actual product failure **1**, not an ownership/cleanup failure 125.

**Sixteen observations failed.** On both host and standalone simulator, the one
eligible private, UP, non-loopback/non-point-to-point multicast interface accepts
the raw multicast send and has a ready endpoint-specific UDP path. Nevertheless,
selected-interface DNS-SD registration succeeds while selected browse, resolve
and TXT query receive **zero callbacks**. All inline-TXT NWBrowser variants still
receive zero callbacks. The declared executable actually sees the matching
bundle ID, usage string and both Bonjour declarations; that does not repair it.
Any-interface resolution still returns exact TXT/port with LocalOnly/`LOCALHOST`.

The new read-only host CFPreferences probe observes the documented global
**`NoMulticastAdvertisements` Boolean as `TRUE`**. Apple's pinned man page states
that this suppresses Bonjour service advertising via multicast DNS. The simulator
returns `NOT_RETURNED`, which is not evidence of a false or absent effective host
policy. This is a concrete configuration finding; it is not yet causal recovery
evidence. No system preference or service was changed by this failed run. The
public runner-image revision is `f10516542b8f2fef89b652a8d5f5de63aa543b77`; the
inspected public configuration files do not establish who set this preference.

Evidence is retained in `actions-36747721136/` under the private continuation
directory. Publisher-verified artifact **11113792221** SHA-256:
`010bb8d61eb4e0074eb05f819eb84fc99c30262f8670f3b4f922db05d2411c6e`.
Complete logs ZIP: `87844032222b8c5f75d9db58c4cb14a4e185da377cb38c2c810b59390a5f0d07`.
Independent review: `e82fe9e6c638fbe91c56d12d16a6bfd14a0deb61e8d533a4337405a619e224a0`.
All 17 available log entries were read and hashed. Original Kotlin/GUI tests
were not run; no discovery, full-matrix or capacity pass is inferred.

The next feature-only Intel network run explicitly enables
[`rpc_apple_bonjour_environment.py`](../../scripts/rpc_apple_bonjour_environment.py).
It first runs **12 before-change observations** on the **same allocation**, using
the original nonroot executor and both actual compiled contexts: raw multicast,
UDP path, preference, selected browse, selected resolve/TXT and production-shaped
inline-TXT browse. Their failures remain in a separate baseline collection; they
cannot supply product admission. It then changes only the already-observed
Boolean from true to false with the fixed system `defaults` command, followed by
the normal `launchctl kickstart -k system/com.apple.mDNSResponder` operation.
The full original **38 observations**, bounds and assertions run afterward.

This is disposable test-environment configuration, not a new production default,
TCC permission grant or process-ownership exemption. There is no root product or
observer, route/interface/firewall change, TCC/SIP edit, global private-address
whitelist or authentication change. Full typed preference content, ownership and
file modes are checked, with arbitrary values retained privately. The exact
Boolean is restored in a finalizer even after a product/ownership failure, then
the service is normally reloaded and the original complete preference state is
verified. Missing/failed restoration cannot pass the collector. A protected-service
refusal is retained as a prerequisite failure: **no PID signaling, security
disablement or bypass fallback is allowed**. Raw configuration/logs are not uploaded.

Alternatives not selected: weakening TXT assertions or production discovery,
claiming LocalOnly as LAN, another unsupported audit-session permutation, or
merely rerunning the same nine cases on an unchanged suppressed host. A genuinely
suitable runner remains necessary if ordinary service preparation is refused.
The Any-resolution diagnostic's existing `.local.` assertion is still unchanged.

Local checks passed: **70 qualification**, **16 advertising-preparation**, **28
network-diagnostic**, **18 product-diagnostic**, **15 Terminal**, **17 SSH**, **14
launchd** and **11 audit-session** controls. This includes partial-write/reload
failures, no privileged fallback, restoration after product failure, typed-key
and metadata drift, private logs, and both-context execution ordering. Layout,
OSV lock coverage, release metadata, Markdown links and whitespace checks passed.
These are offline tests, **not an executed advertising correction**. The original
nine cases, GUI readiness, full matrix and healthy-generator full 30-minute
capacity workload remain required. All HOLDs and **NOT_READY** remain intact.

The first A/B dispatch, [36751707283](https://github.com/p2pKit/P2pKit/actions/runs/36751707283)
at `fec14653a70af48702881b5e7c46ca4830f26a2b`, failed **before native execution
or any setting change**. One new offline fixture passed Darwin's symlinked
temporary spelling to the unchanged private-file reader, which correctly
rejected it (`test_actual_subprocess_path_is_bounded_private_fixed_and_not_retried`).
The fixture now uses its actual physical temporary parent, matching admitted
runtime state, with a regression proving that the reader still rejects alias
access. No production/helper path admission changed. All **17 preparation** and
**70 qualification** controls pass locally, including the enabled A/B environment.
The skipped execution is not a network result. Retained artifact SHA-256:
`966e44e48c7a64ec74c46aed99f6b015bf6c7ce1e47e9a11d53a02e465944803`;
logs: `199e0902d117743f2e8bcc59f4414df22f37fc8c28884e0a16de216478b7b969`;
independent review: `02156636d47f663f83c72da39bae6dc797f8ed759eb4988f3e036b6c14f96ea5`.

### October 1: correct the dropped advertising request before repeating native work

[Run 36752026196](https://github.com/p2pKit/P2pKit/actions/runs/36752026196), source
`7c7434bb00f7e2f91685731774c87898cce85479`, completed **FAIL**. Independent review
read both complete available workflow-log entries and checked all **122 native
controls, 63 finalized commands and 38 observation/exit bindings**, unchanged
source, exact simulator retirement and Terminal finalization. The same **16**
observations failed, and the native host again reported advertising suppression
**TRUE**. There were **no baseline observations and no advertising-preparation
proof**. This run did **not** attempt to change the setting; it is not evidence
that the proposed correction failed.

The exact harness defect is the nested environment boundary:
`workflow → Terminal context → audit-session wrapper → qualification driver`.
The first two retained `RPC_APPLE_BONJOUR_ADVERTISING=true`, but
[`with-darwin-audit-session.py`](../../scripts/with-darwin-audit-session.py)'s
closed allowlist omitted that key. Its private configuration therefore omitted
the option and the driver ran the original diagnostic. The outer collector still
required preparation evidence and correctly refused success.

The smallest correction adds **only that one key** to the audit-session allowlist.
A regression using both actual allowlists reproduced `None != 'true'` before the
fix. The Terminal context now also binds the requested experiment into its exact
child argv with `--require-bonjour-advertising`. The qualification entry point
checks that argv, environment and Intel/network/Terminal scope agree **before any
native work**. A dropped flag can no longer spend another run silently executing
the wrong experiment. Arbitrary argv, secrets, loader hooks, root credentials and
ownership overrides remain rejected; default product execution is unchanged.
No TCC/SIP, route, authentication, LAN admission, native ownership, cleanup,
simulator-readiness or test deadline was changed.

Local checks passed: **72 qualification** (with the advertising option enabled),
**17 Terminal, 11 audit-session, 17 advertising-preparation, 28 network-diagnostic,
18 product-diagnostic, 17 SSH, 14 launchd, 8 capacity-analysis and 9 hosted-capacity
driver** controls. Layout, OSV lock coverage, release metadata, **604** relative
Markdown links, changed Python ASTs and `git diff --check` also passed. Both
repository instruction files retain their original Git hashes. These checks
execute no Apple product, Java build or capacity workload.

Evidence is in `actions-36752026196/` under the private continuation directory.
Publisher-verified artifact **11115716915** SHA-256:
`67a7cb59bdb03720c6f75a37a6e3f0a13d238013cc718a6645f48bce367b01f9`;
complete logs: `572748482fe3ac850c3f07420b8cfa89a06553cd1fc083de63a180b1ec80b6bb`;
independent review: `782101a05bfe7de9c9fe1a1feaf2a943552e6ad8ca6ae77a2deb366bd511e092`.
The original **nine Kotlin discovery failures**, untouched GUI readiness and full
matrix remain unresolved. The actual same-runner advertising A/B must execute
before claiming recovery or starting the subsequent full-rate capacity gate.

### October 1: actual baseline reached; correct the source-contract handoff

[Run 36798060006](https://github.com/p2pKit/P2pKit/actions/runs/36798060006), source
`4450f5f029a409ee29605c178c600eff5df2d89a`, completed **FAIL** in **6m40s**.
All **122 native controls, 37 command finalizations and 12 baseline observations**
were independently checked. Six baseline observations failed: selected-interface
browse, selected-interface resolve/TXT and production-shaped inline-TXT browsing,
on each actual compiled context. The host suppression Boolean was **TRUE**;
raw multicast sends and endpoint-specific UDP readiness still succeeded.
Terminal and the exact simulator finalized, with unchanged source and zero
receipt errors, discovery errors, pending observations or known owned survivors.

The request-propagation fix worked: the before-change collection actually ran.
The next failure was **before preparation construction**, not a protected-service
refusal or an unsuccessful preference change. The native executor's actual
`source_snapshot()` returns `{commit, tree, status, diffSha256}`; the separate
preparation helper deliberately admits only `{commit, tree}` and independently
checks clean source. Passing the entire executor dictionary unconditionally
fails `Exact unchanged feature source required` before creating preparation state
or invoking `defaults`/`launchctl`. There were **zero after observations and no
preparation proof**. This trace was reproduced locally through the actual helper
constructor/admission, not just a mocked preparation object.

The caller now projects the already-admitted commit/tree into that exact contract.
The executor still retains and checks all four fields; the helper still rejects
unknown source fields and rechecks the actual clean revision. No gate was relaxed.
The new integration test executes real preparation admission, apply/finalization
logic and private proof serialization with the actual four-field caller schema;
only external native observations and administrative commands are fixtures.
It fails before the fix and passes afterward, including all 12/38 before/after
invocations and mandatory restoration. It supplies **no native/product counts**.

Local **73 qualification, 17 preparation, 17 Terminal, 11 audit-session, 28
network-diagnostic and 18 product-diagnostic** controls passed. The actual system
configuration correction, original nine discovery tests, independent GUI readiness,
full matrix and subsequent 30-minute capacity qualification remain pending.

Evidence: `actions-36798060006/`, artifact **11134522572** SHA-256
`754ed5c2fe6255f5d1a10ccf5257e172e484ecc109f0f075202d461fd28d5428`;
complete logs `bb25b5f614ebb4155b7f0821813a44aa329313fc1d3dc990478030a68fd58f7e`;
independent review `b27ea63738d2602fb5033df5b4d6fa05a8fc0dec0c132d5caad803ba27c66f29`.
All 17 available workflow-log entries were read and hashed. The deleted Mac was
not contacted. All release HOLDs and Foundation **NOT_READY** remain unchanged.

### October 1: actual preference round trip; wrong launchd service name

[Run 36798931459](https://github.com/p2pKit/P2pKit/actions/runs/36798931459), source
`7c2b3dfbbb33230ec814c618aa45796bd07a85f3`, completed **FAIL** in **10m14s**.
Independent review verified **122 native controls, 37 finalized commands, all
12 baseline observations** (six failed), source/Terminal/simulator finalization,
and the actual administrative result. For the first time the fixed `defaults`
write really executed: the Boolean became **FALSE**, with all other typed
preferences and file ownership/mode unchanged. Restoration returned the complete
domain to its exact original **TRUE** state. Both writes returned zero.

The intervening `launchctl kickstart -k system/com.apple.mDNSResponder` returned
**113**, classified from its actual private stderr as **SERVICE_UNAVAILABLE**
(`Could not find service`). It was **not** a SIP/permission denial, native ownership
failure or a demonstrated discovery failure after an effective reload. No reload
succeeded, no retry/fallback ran, and all **38 after observations remained unrun**.
The failed result and missing runtime-configuration proof remain failures.

The mistaken assumption was equating the preference/LaunchDaemon filename with
the service's launchd `Label`. The corrected fixed target is
`system/com.apple.mDNSResponder.reloaded`. Before any preference mutation, the
helper now reads **only** the root-owned, non-writable-to-others, non-symlinked
`/System/Library/LaunchDaemons/com.apple.mDNSResponder.plist`, requires that exact
label and `/usr/sbin/mDNSResponder` program, rejects command-line advertising
suppression, and checks actual registration with a **nonroot**, read-only
`launchctl print` of the exact target. It retains only the configuration digest
and closed verdicts publicly. The installed configuration must retain the same
digest before each service operation. An absent, different, replaced or denied
service fails; the code cannot choose an arbitrary label/program or use raw PID
signals. The new target still requires actual runner verification, not trust in
the filename or a successful offline fixture.

There is still just one ordinary `kickstart` attempt and mandatory exact Boolean
restoration; an actual protected-service refusal cannot trigger a workaround.
No launch plist, TCC/SIP policy, interface, route, authentication, ownership rule,
test assertion or deadline is edited. Local **21 preparation** and **73
qualification** controls passed, including wrong label/program, command-line
suppression, refusal before mutation, source-schema integration and changed
service configuration. This is not yet original Kotlin/GUI recovery or capacity
qualification.

Evidence: `actions-36798931459/`, artifact **11134658601** SHA-256
`ac2734f77576f93af37ad736371be0ca07b6ebabc61bfb75d1f4344c6cd44c55`;
complete logs `6f56d35c061f2ca4d8b93c48a9c7afd492d89db85b84eb1971b1ee7d884ac0a4`;
independent review `b84fce9cc6b4a7da2953d4421a36866b61355b66847368d4e4183e7fb2a80f9a`.
All 17 log entries were read and hashed. The public service-label cross-reference
is [STONIX's existing modern macOS service mapping](https://github.com/CSD-Public/stonix/blob/9fdcd7437e97fb3efd72a453de4ff4fca033c4c6/src/stonix_resources/rules/SecureMDNS.py#L135-L150);
it is **not** substituted for the required installed-configuration/registration
checks. All release HOLDs and **NOT_READY** remain intact.

### October 1: preserve a separate native prerequisite/Terminal failure

[Run 36800355634, attempt 1](https://github.com/p2pKit/P2pKit/actions/runs/36800355634/attempts/1),
source `ce819163c8ba5caba0f99f165c005e3c4471f3a6`, failed **before** toolchain,
simulator, network probes or advertising preparation. Native output reported
122 tests but the admitted count is **zero**, because
`test_actual_consumer_caller_with_real_executor_retains_external_report_and_receipts`
failed its line-3269 exit assertion. The nested `consumer-publish` receipt passed;
the enclosing `executor-fixture` hit its original **20-second** product deadline,
returned product **-15/final 125**, and retained `Product command timed out`.
Native retirement was known, with zero owned survivors/discovery errors/pending
observations. The outer native-control command finalized with product failure 1.
No new Bonjour helper code had executed at that point.

Separately, Terminal's exact original instance accepted its ordinary Quit request
after the native child result and waited-shell-child evidence, but **did not
prove termination in the original 30 seconds** (`QUIT_COMPLETION`). Its command
was therefore not removed and context finalization returned 125. This is a real
cleanup failure, not a warning or an admitted successful fixture. The job completed;
there was no attempt to kill an arbitrary process or revisit the retired hosted VM.

The native executor, consumer fixture and Terminal controller source are byte-for-byte
unchanged from the preceding successful 122-control runs. The retained public
evidence does **not** establish why this allocation exceeded either time bound;
no CPU-starvation or application-defect attribution is invented. A single bounded
fresh-runner repeat uses the **identical source, complete inventory and unchanged
deadlines** to separate recurrence from an allocation-specific failure. The first
attempt remains failed regardless of the repeat; no assertion or cleanup gate is
relaxed and it is not evidence for or against the corrected service target.

Evidence: `actions-36800355634/`, artifact **11135466713** SHA-256
`f7de301f35c15312f3a10dd819cf70fed27fb9b69be3478da781d82f126e052d`;
complete logs `3c085c44c0c1e1e8a6cefab5a86daaf53815e1ab61276671e024f897761203c9`;
independent review `7af2e3fa43eb7900bbf0bf028cdc53d5c2ba19c1d02dee21b5dca3f8c62e4d7a`.
All 17 available log entries and the retained fixed failure/receipt diagnostics
were reviewed. No discovery, GUI, capacity or release claim follows.

### October 1: verified causal Bonjour recovery below Kotlin

[Run 36800355634, attempt 2](https://github.com/p2pKit/P2pKit/actions/runs/36800355634/attempts/2)
completed **PASS** on the identical source
`ce819163c8ba5caba0f99f165c005e3c4471f3a6`, tree
`a55b26f072967c27025c10ac675bc2376adb8d14`. The actual runner was native Intel,
macOS **15.7.9**, image **20260824.0482.1**, selected **Xcode 26.3**, and the
standalone simulator runtime was **iOS 26.2/x86_64**. All **122 native ownership
controls** and **75 exact command finalizations** were verified. Attempt 1 above
remains a failed allocation with unresolved prerequisite/Quit timing, not an
inferred repaired defect.

The decisive comparison used the **same binaries, original observation bounds,
Terminal origin, nonroot executor and runner** before and after the setting change:

| Observation | Before, suppression TRUE | After, suppression FALSE |
|---|---|---|
| Selected-interface DNS-SD browse, host and simulator | Registration callback, **zero** browse callbacks/selected adds | Selected adds and browse callbacks present |
| Selected-interface resolution/TXT, both contexts | **Zero** resolve/query callbacks | Actual selected resolution/query, matching port/TXT, `.local.` absolute target |
| Original Network.framework inline-TXT parameter shape, both contexts | Listener/browser ready, **zero** browse callbacks | Browse callback, real connect/accept, complete native cleanup |
| Entire after inventory | Not a claimed passing baseline | **38/38 pass**, including every inline-TXT variant and loaded-declarations control |

All **12 before observations** are retained separately, including the **six
failed before probes**; none is rewritten as a pass. All after probes reported
unprivileged execution. The five fixed preparation commands (`inspect`, `apply`,
`reload`, `restore`, `restore-reload`) each returned **0**, without timeout.
The observed preference round trip was **TRUE → FALSE → TRUE**; typed preference
contents, unrelated settings and file policy restored exactly. The installed
service-configuration digest remained
`cf4640edf49c255bce24c4fed29a12a144ba005a3f7e5141d232cb6c2235f0da`.

Every command retained known retirement with **zero discovery errors, cleanup
errors, pending native observations and owned survivors**. The exact Terminal
application terminated through ordinary Quit after reaping its child, the command
was removed, the exact created simulator was deleted, and source was unchanged.
Some successful same-host connections selected loopback; this is **not physical
multicast receipt or cross-device LAN evidence**.

Independent local review checked all **17 complete log entries**, publisher
artifact digest, source/tree, baseline/after measurements, each command receipt
summary, preparation proof and Terminal/simulator finalization. Evidence is in
`actions-36800355634-attempt2/` under the existing private qualification directory:

- Artifact **11135842512**, SHA-256
  `0cad2f4575dce3708b29c4a44759adb4558adf5112ef5d5f5cfe524bc980b99b`.
- Complete workflow logs:
  `5222a5eca51dd9f1747147c645ab38e79261de6f20a5d502b52d2fd331c1d776`.
- Independent review:
  `4b0b9670edbc4b331faa3b136a6b13de0b7eb6da454290d14fd82424b7295b67`.

**Engineering conclusion:** this verifies configured host advertising suppression
as the cause of the missing native Bonjour results, not a Kotlin discovery or
peer-authentication defect. No production transport workaround is justified.
The nine original Kotlin failures must now be rerun in this functioning environment.

### Extend only the verified Intel test environment to original product gates

The harness now admits three explicitly bound Terminal inventories: the existing
OS `network` diagnostic, original `native` LAN profile, and full Intel
`qualification`. Native/full execution additionally **requires** the reversible
advertising preparation. Exact argv, source, environment mode and schema-2
Terminal receipt must agree. Mode changes, dropped flags, admission-only runs,
ARM/Android substitutions and arbitrary commands remain rejected.

For native/full execution, an additional `bonjour-advertising` prerequisite runs
before multicast/product work, and the preparation object is retained **before**
applying the setting. Finalization restores it even after application, ownership,
simulator-retirement or partially failed preparation. A failed restoration fails
the run. The full original phase inventory remains mandatory; native diagnostics
remain labeled diagnostics. No OS-probe result can replace a product test.

The original **1,800-second network-diagnostic application lease**, **120-second
GUI readiness**, **45-second multicast control**, **7,200-second platform/Swift
command bounds**, and **30-second ordinary Quit** bound are unchanged. New
native/full orchestration uses a closed **320-minute aggregate application lease**
inside the already-existing **325-minute workflow step**, since it now encloses
multiple independently bounded build/test phases rather than only OS probes.
This does not lengthen or retry any individual failed test/readiness gate.
ARM, Android and the untouched cold-boot diagnostic keep their existing context.
No TCC/SIP, production ownership, authentication, LAN policy or release gate changes.

Local regression checks for this extension passed: **76 qualification, 22 Terminal,
21 reversible-preparation, 11 audit-session, 17 SSH-context, 14 launchd-context,
28 native-network parser, 18 product-diagnostic and nine hosted-capacity controls**.
The added controls cover exact mode/argv forwarding across both environment
allowlists, proof-inventory mismatch, mandatory preparation, original phase/bound
preservation, blocked starts after setup failure and restoration after partially
failed writes/product/ownership/simulator failures. These are offline harness
controls, not native Apple execution. Repository layout, OSV lock coverage,
**609 relative Markdown links**, release metadata, changed Python ASTs and
`git diff --check` also passed. Log `intel-product-complete-controls.0CTOMvcK.log`,
SHA-256 `52b9e783c63f581961236cc4ba2ede3bbdfe4411889aa2a8b82efb74c598cc57`.
No local Java/Gradle/application build or capacity workload was started. Next is
the narrowly scoped original Intel LAN test profile on the actual native runner.

### October 1: original multicast control recovered; runtime enumeration timed out

[Run 36805158026, attempt 1](https://github.com/p2pKit/P2pKit/actions/runs/36805158026/attempts/1)
at `d6d8a2a1ef403f65f4a0226684872920ad88b633`, tree
`d6506183f5678af185b338ce45b5e5658d3ad844`, failed before Kotlin execution.
The actual Intel runner used macOS **15.7.9**, image **20260824.0482.1** and
**Xcode 26.3**. All **122 native controls** passed. Toolchain, tool installation
and reversible Bonjour preparation passed, followed by the original Java control:

```text
phase=ready mode=control
phase=original_resources_disposed_without_rescue mode=control
PASS mode=control
```

This is actual recovery of the original multicast prerequisite, not an inferred
pass from the separate C probes. Its **10-second readiness/45-second command**
bounds and no-rescue requirement are unchanged.

The next exact command was `/usr/bin/xcrun simctl list --json runtimes`.
It produced **zero stdout and stderr bytes**, exceeded its original **120-second**
product deadline and was retired with product exit **-15**, final exit **125**,
and the sole fixed error **`Product command timed out`**. The first 14 command
finalizations were verified; this fifteenth command remains unadmitted. The
strict caller reports `OWNERSHIP_UNPROVEN` because a timed-out receipt cannot
validate, but its actual diagnostic reports **zero ownership-discovery errors,
zero pending Darwin observations, zero owned survivors, known retirement and
successful stop**. Do not substitute that generic phase code for the real cause.

No `simulator-create` or Kotlin command ran. `simulatorRetired=false` therefore
does not describe an abandoned newly owned simulator. Native tests remain
`BLOCKED_PREREQUISITE`. The schema-2 Terminal `native` inventory finalized with
the expected failed child exit **1**, ordinary Quit, reaped child and removed
command. All five Bonjour preparation/restoration commands exited **0** with
the exact **TRUE → FALSE → TRUE** preference round trip and preserved file,
unrelated preference and installed-service policy. Source remained unchanged.

Independent review read all **17 complete log entries**, verified the publisher
digest/source/tree, every command summary, numeric diagnostics and both strict
preparation/context proofs. Evidence is retained in `actions-36805158026/`:

- Artifact **11137940398**, SHA-256
  `76107f8048704a450bdeb537d1791624511a14bc65258ef07813fbb5ce90b1e0`.
- Complete workflow logs:
  `bf402430c860478654b9e5a9261aa4c521a3fdbdc9cd42708457af8c38c3e31c`.
- Independent review:
  `7c627202d5cda13f98dd093c74e59bebcdc4b88321db0937ee01811bfbae8b18`.

The silent enumeration's internal cause is **not established** by these records;
there is no stack or resource observation proving CPU starvation or a service
deadlock. Earlier unchanged enumeration commands passed, and earlier failed
allocations are retained. One identical-source fresh-runner comparison is now
requested to distinguish a repeatable integration problem from an allocation
prerequisite failure. It preserves every timeout, assertion, ownership check and
failed attempt; no service kill, hidden warm-up, runtime substitution or automatic
in-job retry is introduced. No original Kotlin, GUI-readiness or capacity pass is
claimed before that actual execution and independent review.

### October 1: original nine Kotlin discovery failures recovered without source changes

[Run 36805158026, attempt 2](https://github.com/p2pKit/P2pKit/actions/runs/36805158026/attempts/2)
passed in **12m51s** on identical source `d6d8a2a1ef403f65f4a0226684872920ad88b633`
and tree `d6506183f5678af185b338ce45b5e5658d3ad844`. The native Intel environment
remained macOS **15.7.9**, image **20260824.0482.1**, **Xcode 26.3** and the
**iOS 26.2 x86_64** standalone simulator. Runtime enumeration succeeded within
the unchanged bound. This does not establish the internal cause of attempt 1's
silent enumeration timeout or retrospectively repair that failed allocation.

Actual source-bound results:

- **122 native ownership controls passed** with no failed control diagnostics.
- Original Java multicast readiness and natural disposal passed again, without rescue.
- The original `ios-lan-x64` profile actually executed
  **`:p2p-transport-lan:iosX64Test`**: **202 passed, zero failures/errors, one
  pre-existing ignored diagnostic**, across **33 XML suites**. The unchanged
  assessor and workflow XML/execution reconciliation both passed.
- All **eight Native failure-context/frame regression methods** passed.
- All **26 command finalizations** verified zero errors, discovery errors,
  pending observations and owned survivors; source remained unchanged.
- The exact created simulator was retired and deleted. Terminal ordinary Quit,
  child reap and command removal completed. All five Bonjour commands exited zero
  and the complete original **TRUE → FALSE → TRUE** preference/file/service
  configuration was restored.

Independent comparison against the original failed `63530bb8` source/run
**36703393356** verified **no differences in `library/`, `samples/`, `gradle/`
or `scripts/run-platform-tests.py`**. The same 203-case inventory previously
reported **193 passed / nine failed / one ignored**. Its recovered cases are:

| Unchanged class | Recovered original methods |
|---|---|
| `IosLanLifecycleTest` | `advertiseStopRestartProducesObservablePeerChurn`, `midTransferCancelTerminatesBothSidesCleanly`, `peerLostEventFiresWhenPeerStops`, `rapidConnectCloseCycle`, `stopDiscoveryWithdrawsOwnedPeersAndRestartReplaysCurrentState`, `threePeersMutuallyDiscover` |
| `IosLanLoopbackTest` | `fileTransferRoundTripsOverTcp`, `largeBinaryPayloadRoundTripsOverTcp`, `twoKitsDiscoverEachOtherAndExchangeText` |

The supported correction is **test-environment preparation**, not a production
transport change: a genuine nonroot Terminal context plus reversible removal of
the runner's documented multicast-advertising suppression. The causal native
A/B and actual Kotlin follow-through agree. No test was removed, renamed,
quarantined, mocked, retried inside its run or given a longer deadline. Native
architecture, authentication, LAN admission, TXT validation and resource
ownership remain unchanged. The existing ignored capture-only diagnostic was
neither added nor used as passing evidence.

All **17 complete log entries** and the closed source-bound artifact were read
and independently validated in `actions-36805158026-attempt2/`:

- Artifact **11137224028**, SHA-256
  `1db85f5e2cec4187da648a9657189e74dfb97594a37f57f7779e6c2d70a35136`.
- Complete workflow logs:
  `8c0d6e909ee604efcb3307dbdd1bb3f66a038c64bd0be44b53a9157e9560c802`.
- Independent review:
  `ac9bc65085e71a43a319a05badd9bcdb313d70355b413235b480a8fbe6cb8f77`.

The run remains explicitly **an original Native LAN profile**, not full Intel,
Apple-matrix, GUI-readiness, physical-LAN or mobile capacity qualification.
Following this verified discovery recovery, the complete original Intel inventory
and separately isolated hosted Linux capacity experiment are next. The latter
must pass its generator preflight, exact full **1,800-second / 2,304,000-call**
workload, separate **20 one-MiB request/reply calls**, resource and cleanup review.
No numerical latency threshold is invented; the approved plan requires reporting
the distribution, not a latency pass/fail cutoff.

Local continuation checks also passed **76 qualification, 21 advertising,
22 Terminal, 11 audit-session, 28 network, 18 product-diagnostic, 20 same-host,
12 capacity-lab, 11 numeric-evidence, nine hosted-driver and eight scheduling
analysis controls**. Repository layout, OSV lock coverage, **610 Markdown links**,
release metadata and `git diff --check` passed. Log
`current-offline.iP7AZak6.log`, SHA-256
`29ac86da35c45bb15af4d5626cba63a0f34051ed87b748f8b4a2fdba659dbc30`.
These checks did not run a local Java/Gradle/application build or load workload.
All release HOLDs and Foundation **NOT_READY** remain intact.

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

### October 1: healthy hosted preflight; steady phase unadmitted

[Run 36807541215](https://github.com/p2pKit/P2pKit/actions/runs/36807541215),
source `2bd107b3bd926d66d7b701c77fdb9f1b51d3eca0`, completed **FAIL in 21m47s**.
The fresh hosted Linux allocation provided four CPU-affinity slots and
16,373,452 KiB RAM, using native Temurin 17.0.20+1 and daemon 21.0.12+1.
This was the maintained separate-process, private-veth same-host fixture with
no RPC egress, unchanged production authentication/LAN checks and exact original
nonroot credentials. It was not physical LAN or mobile-host qualification.

Independently checked source-bound evidence establishes these earlier phases:

- All **121 initial native controls**, seven command finalizations and
  **1,172 JVM tests** passed: core 858, LAN 233, RPC 46, RPC sample 35, with no
  failures/skips. The capacity producer was rebuilt from that exact source.
- Each earlier real-socket workload passed its own fresh 121-control admission
  and three native finalizations. All **six correctness cases** passed, followed
  by **65.190 seconds** of actual idle-retention observation.
- The separate **20/20 one-MiB request/reply calls at concurrency two** completed
  in **2.200376241 seconds**, **9.08935464 responses/s**, with zero failed calls
  or typed RPC errors. Client invocation-to-reply upper-millisecond buckets were
  **p50/p95/p99/max 165/466/504/504**. Host RSS peaked at **321,064,960 bytes**,
  sampled queues remained zero, and the **65.181-second** retention check returned
  connections/running/queued/records/payload bytes to zero. Whole-host telemetry,
  including provisioning/idle, spans 71.213 seconds and 4.610 CPU-seconds; it is
  not a server-processing latency measurement.
- The independent 10-ms kernel-timer preflight passed over **125.000208492
  seconds**: **12,500 expirations/12,500 reads/zero coalesced**, maximum observed
  gap **10.264570 ms**, minimum available memory **15,256,436 KiB**, and no observed
  balloon, direct-reclaim or swap-counter growth. This admits an attempt; it
  does not prove a healthy full 30-minute workload.

At **03:02:06 UTC** the driver entered `same-host-steady`; at **03:09:53** it
reported `OWNERSHIP_UNPROVEN`, namespace exit **125**, `measurement=null` and
empty `sourceSites`. No completed 30-minute measurement exists. The label is the
driver's fail-closed response to failed evidence review, **not proof of a native
ownership defect**, failed RPC throughput or missed scheduling. The published
record cannot establish whether either steady JVM began execution.

Inspection found a separate **reporting defect**: the namespace entry point
catches exceptions and emits a fixed prerequisite message without a traceback,
whereas `failed_attempt()` searched only Python traceback frames. It also omitted
coordinator, native-receipt and worker/JVM diagnostics after admission failed.
The exact underlying steady failure therefore remains unknown for this allocation;
its raw private runner files were deliberately not public artifact inputs.

The smallest correction changes only `scripts/run-rpc-capacity-qualification.py`
and its offline tests. Exact source-authored prerequisite messages map to a
script/line, without exporting message contents. Failed records now retain
bounded coordinator flags/exits/cleanup counts, closed native diagnostics and
typed JVM abort/cleanup observations. Missing/invalid evidence stays explicit;
every such observation remains **unadmitted**, with no raw identity, key, payload,
PID, private path or arbitrary exception exported. Workload, production code,
native admission, cleanup and all deadlines are unchanged.

The old checkpoint fails the new no-traceback regression; corrected reporting
passes it and **all 15 offline driver controls**, including an end-to-end failed
attempt that must remain FAIL, privacy tests and invalid-evidence rejection.
This proves the reporting fix only, not the unknown steady failure. A new
source-bound hosted attempt is required to expose any recurring cause and then
complete the unchanged 2,304,000-call workload. No failed allocation is discarded.
The subsequent bounded offline run passed **220 controls** across the capacity,
same-host, numeric evidence, scheduling analysis, qualification and Apple
diagnostic/environment suites, plus repository layout, OSV-lock coverage,
Markdown links, release metadata and `git diff --check`. Its log SHA-256 is
`31227ed8458177b7ad848f2ff017c1a8c44ba00d78178f5dc34d295d2bde45ce`.
No local Java/Gradle/application build or capacity workload was started during
this continuation; the changed exporter still needs hosted execution.

All **17 workflow-log entries**, artifact/source binding and independent numeric
reconciliation were reviewed. Task-owned preserved evidence:
`.git/rpc-bonjour-qualification-20260930.oOYgSoqr/actions-36807541215/`.
Artifact **11139545211** SHA-256:
`6b23d0208234a7fce262253dc04d31b7dd7c8ffa5318d97ebecbf583bc796f5c`;
complete logs SHA-256:
`6ece597f2614af4579d47731949d2205c8c83a8c7763ba4810e1324778bb888e`;
independent review SHA-256:
`76365f0efd47d648f5f1f24725ebe39622f32fa684e72fd872c3c2474033f65b`.
The separate full Intel run **36807541133** remains in progress at this checkpoint;
it is not cancelled or declared passed. All release HOLDs and **NOT_READY** remain.

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

### Frame follow-up: preserve both attempts and correct private-symbol handling

[Run 36698432884](https://github.com/p2pKit/P2pKit/actions/runs/36698432884),
source `8506b0013c6d1cbc14db11386604a7eea785b6d0`, has **two failed attempts**.
They used the same source, required Intel/macOS-15/Xcode-26.3 cell, controls and
deadlines. The first did not reach Native execution; it is not overwritten by
the second's results.

**Attempt 1:** the unchanged ownership fixture
`test_actual_consumer_caller_with_real_executor_retains_external_report_and_receipts`
failed its expected-zero assertion at `scripts/tests/run-audit-command-test.py:3269`.
Its enclosing `executor-fixture` exceeded `start()`'s original **20-second** bound.
The nested `consumer-publish` product/final exits were 0/0, whereas
`consumer-build` had product zero, final 125, cancellation and failed source-binding
verification. The enclosing product was terminated (-15/final 125). The failed
Git check during cancellation is **not proof that source files changed**.
The suite reported 122 cases but admitted zero; its own finalization passed with
unchanged feature source and no owned survivors. No simulator or Native build
was created. Sanitized evidence does not attribute why that nested invocation
exceeded its bound. One fresh allocation was requested, not a retry-until-green
loop or an increased timeout.

**Attempt 2:** all **122 ownership controls passed**. Real LAN `iosX64Test`
executed **191 passes, 11 failures and one existing ignored case**, 33 XML suites.
The original nine discovery failures remained. The two additional failures were
the new `allStageContextsRetainOwnNativeConstructorFrames` and
`allObservationContextsRetainOwnNativeConstructorFrames` tests: both reached
their actual frame assertion, not a lifecycle or ownership failure. All six other
helper methods have individually exported passing outcomes. **All 26 command
receipts finalized**, retaining the Native and multicast product failures, with
unchanged source and zero pending identities, discovery errors or owned survivors.
The owned iOS 26.2 device was Shutdown before/after Native and retired/deleted.
No Swift, cold-boot, core/RPC/sample Native or full-platform execution is claimed.

The original failures' exported locations independently resolve against the
**executed** source: eight contain the initial-peer constructor at line 40 and
`threePeersMutuallyDiscover` the initial-peer-set constructor at line 41.
Each also contains the browser-ready, listener-ready and missing usage/Bonjour
declaration constructor locations. Thus these methods stop at their initial
discovery prerequisites, before their intended transfer, cancellation or peer-loss
checks. This is a **source-location review**, not reconstruction of missing raw
XML or a claim that the failed format assertions passed. Missing `Info.plist`
declarations and the independent interface-matched multicast `NoRouteToHostException`
are relevant observations, not proof of TCC denial or a production cleanup leak.

The remaining reporting defect has a specific compiler explanation:
Kotlin **2.4.10**
[`LlvmDeclarations.kt`](https://github.com/JetBrains/kotlin/blob/v2.4.10/kotlin-native/backend.native/compiler/ir/backend.native/src/org/jetbrains/kotlin/backend/konan/llvm/LlvmDeclarations.kt)
names non-exported functions using their dotted declaration name followed by
`#internal`, without the exported mangled signature. These **private** constructors
therefore use `Class.<init>#internal`, not the assumed `Class#<init>()` form.
The pinned KGP parser keeps that suffix in its JVM method name. Both the Native
regression's substring and the Python exporter's constructor pattern were wrong.
The actual declaration frames were present; the readers did not recognize them.

The correction retains private classes and requires the exact private Native
constructor frame, including `kfun:` and its frame-offset delimiter. The exporter
recognizes only the closed classes and exact constructor suffix; unrelated types,
methods, prefixes and suffix extensions remain rejected. It does not remove an
assertion, replace the original timeout, promote a failed case or export raw text.
Changing class visibility to force different compiler symbols was unnecessary.
Offline reproduction proves the old exporter misses the signatureless private
frame and the corrected one retains exactly its closed label.

Four additional **passively observed, test-only flags** distinguish advertising
intent, a real browse-result callback, peer-record rejection and peer acceptance
using existing transport diagnostics. They retain no TXT fields, endpoint, name or
identity, never alter production logging, and cannot assert delivery of every
event. This lets the same follow-up distinguish missing OS results from a record
admission failure, rather than assuming browser-ready proves discovery. The
two real constructor tests now cover all three stages and 14 observation types;
their successful Native execution still needs verification. All eight helper
outcomes remain source-bound and cannot admit a failed product profile.

**18 diagnostic/privacy, 63 qualification, 23 platform-assessor, 11 Darwin-session
and seven capacity-analyzer offline tests, plus 31 platform-policy checks**, passed
before requesting the revised Native-only diagnostic. This request changes the
verified test/reporting defect, not the architecture/security/readiness contract.
No unchanged cold-boot/full-matrix or VPS capacity rerun is justified by these data.

### Verified private-symbol fix; original discovery prerequisites still fail

[Run 36703393356](https://github.com/p2pKit/P2pKit/actions/runs/36703393356),
source `63530bb89724fe8f87de66b481151cabf157bc34`, completed **FAIL**, not a
qualification pass. Its single Native diagnostic job ran from **10:36:02 to
11:00:39 UTC**, on actual **Intel/macOS 15.7.9/Xcode 26.3**, image
`20260824.0482.1`. No cold-boot, ARM, ART or full-matrix rerun was requested.
The existing admitted entry point above used
`--lane apple-x64 --intel-investigation native`, retaining its original
architecture, source, ownership, test-deadline and cleanup requirements.

| Actual LAN `iosX64Test` observation | `8506b001`, attempt 2 | Corrected `63530bb8` |
|---|---:|---:|
| Passed / failed / existing ignored | 191 / 11 / 1 | **193 / 9 / 1** |
| Diagnostic helper methods passed | 6 of 8 | **8 of 8** |
| Original discovery failures | 9 | **Same 9** |
| XML suites / unmapped failures | 33 / 0 | **33 / 0** |
| Native ownership controls passed | 122 | **122** |
| Command finalizations verified | 26 of 26 | **26 of 26** |

Both previously failing constructor assertions now pass on real Native,
covering **all three stage and 14 observation constructors**. The six cancellation,
collector-ownership and closed-data tests also pass individually. All nine real
failure records now retain their correct closed markers through KGP's actual
conversion. This validates the private-symbol reporting correction, not merely
the offline regex examples. No original product assertion was weakened or removed.

The exact remaining trace is now visible:

1. Eight cases time out in `INITIAL_PEER`; `threePeersMutuallyDiscover` times
   out in `INITIAL_PEER_SET`, under the original 30-second discovery bound.
   None reaches the intended transfer, mid-transfer cancellation, peer-loss,
   restart or connect/close checks following that discovery prerequisite.
2. Every failure observes `ADVERTISING_STARTED`, `BROWSER_READY`,
   `LISTENER_READY`, `MISSING_LOCAL_NETWORK_USAGE` and `MISSING_BONJOUR_SERVICE`.
3. **No browse-result callback, record rejection or accepted-peer flag was
   observed** in these waits. Neither a browser waiting/failed state nor a browser
   error code was observed. These bounded, aggregate debug-flow observations
   cannot prove that every event was delivered, but do not support blaming TXT
   admission, peer authentication or cleanup for the missing initial peer.
   Advertising intent and browser-ready are not service-registration/delivery
   acknowledgements.
4. The independent JVM multicast control again made **two IPv4 mDNS send
   attempts with zero successful returns**, raising `NoRouteToHostException`.
   Selected/host/socket interfaces still matched; the observed route was
   UP/IFSCOPE, not REJECT/BLACKHOLE/GATEWAY. The failure is retained independently
   of Native and the historical dependency-lock baseline.

All command receipts have unchanged source, stop exit zero, known zero owned
survivors, zero unresolved observations and zero discovery errors. The scoped
Native and multicast commands retain product/final exit **one**, so successful
finalization does not hide either failure. The exact iOS **26.2** simulator
(x86_64 and arm64 supported) was Shutdown before/after Native, then retired and
deleted. The full profile remains unexecuted; the existing clean-boot System App
readiness failure is **not** retested or fixed by this run.

#### Permission hypothesis: verified observations, not a permission verdict

Apple's current [TN3179: Understanding local network privacy](https://developer.apple.com/documentation/technotes/tn3179-understanding-local-network-privacy),
retrieved on 2026-09-30, explicitly says the **simulator does not support local
network privacy** and requires real-device testing for that behavior. It separately
describes macOS permission attribution, including responsible app/agent code and
automatic allowances for some command-line contexts. Consequently, the missing
simulator `Info.plist` flags are **not proof of iOS permission denial**, and the
host's Java multicast error is not enough to identify a particular macOS TCC
decision. No `kDNSServiceErr_PolicyDenied` browser observation was obtained here.

Blindly adding plist metadata, changing security attribution, running products
as root, editing TCC/SIP, substituting a runtime or allowing a failed readiness
probe would not establish the cause. None was done. The verified remaining
mechanism is a bounded initial-discovery wait without an observed OS browse
result, plus an independent host multicast send failure and separately reproduced
GUI-readiness failure. **The provider/OS-internal cause remains unresolved**;
these artifacts do not justify an additional production admission/networking
change. A legitimate next qualification environment must support actual Bonjour
results and the original GUI-readiness bound on the required native Intel
toolchain, followed by the unchanged full profile. No ARM result can replace it.

The current source also passed **18 diagnostic/privacy, 63 qualification-driver,
23 platform-assessor, 11 Darwin-session and seven capacity-analyzer tests, plus
31 platform-policy checks**, locally. Repository layout, strict dependency
metadata, OSV lock coverage, release metadata, **585 relative links across 108
Markdown files** and `git diff --check` passed. The instruction and approved-plan
hashes remain unchanged. The complete available workflow logs,
publisher-verified artifact and independent source/receipt review are retained
under `actions-36703393356/`. The review's command timing is restricted to the
actual execution step: an initial local reviewer assertion correctly stopped
when the combined job log also contained synthetic unit-test START/END lines.
That local review failure is retained; no CI result was altered.

No new JVM workload was run for this diagnostic-only correction. The preserved
30-minute slot reconciliation and independent kernel-timer evidence still support
the documented environment-induced generator failure; they do **not** qualify
the required 2,304,000-response, zero-miss workload. Stable-resource, real-host
and physical-device requirements, all release HOLDs and **NOT_READY** remain.

### Native OS networking probe: preserve failures before diagnosis

The next, separately labelled Intel experiment compares real BSD multicast,
DNS-SD `Any`, DNS-SD **LocalOnly** (a control, never LAN qualification), and
Network.framework advertisement/browse/local TCP on the macOS host and the
selected iOS simulator. It uses the same unprivileged, source-bound executor,
the required Intel/macOS 15/Xcode 26.3 host, and a newly owned simulator with
verified retirement. Numeric API outcomes and source-bound compiler locations
are exported; addresses, names, payloads and raw private logs are not. Original
product discovery/readiness bounds, matrix entries and admission stay unchanged.

Three attempts failed **before any OS networking probe executed**:

| Run / source | Verified diagnostic build failure |
|---|---|
| [36709128433](https://github.com/p2pKit/P2pKit/actions/runs/36709128433), `733de1b7` | Host C compilation failed; no source-location observation was yet retained. |
| [36710319179](https://github.com/p2pKit/P2pKit/actions/runs/36710319179), `f0bf2451` | Identical 548-byte stderr hash; the source-bound observation locates a null argument to the **nonnull** path-monitor update-handler setter. |
| [36711378914](https://github.com/p2pKit/P2pKit/actions/runs/36711378914), `5e6fbbb9` | Compilation proceeds to linking, which fails because `-ldns_sd` requests an unavailable standalone Apple SDK library. |

`5e6fbbb9` replaces the cancelled monitor's callback with a noncapturing empty
block rather than `NULL`, breaking its stack reference while respecting the SDK
contract. `-Wall -Wextra -Werror` remain. The next correction removes only
`-ldns_sd`: Apple's own `mDNSResponder/Clients/Makefile` documents that Darwin
provides these APIs through implicitly linked `libSystem`. This is not a stub,
optional symbol, replacement DNS implementation or suppressed linker error.
Both host and simulator command controls assert the corrected linkage.

The third run's **exact 111-byte linker stderr** was reconstructed and matched
to its publisher-verified SHA-256
`905a97f9d0f15bdebd0466c4bbab5caa19a5308d1b5fd9d357166a400c3a2a24`:
`ld: library 'dns_sd' not found`, followed by Clang's exit-one linker failure.
All **122 native controls and 21 source-bound command finalizations passed**;
the compile command correctly remained exit one. The owned simulator was
deleted. **No original Native discovery test, readiness gate or capacity run
passed as a result of these diagnostic build corrections.**

Evidence is preserved separately in
`.git/rpc-bonjour-qualification-20260930.oOYgSoqr/`, including complete available
workflow logs, publisher-digest-verified original artifacts, decoded summaries,
the link-error byte/hash verification and the source-bound independent review.
Offline checks after the Darwin linkage correction passed **15 network schema,
68 qualification-driver and 18 product-diagnostic controls**. These are not
native execution or permission/discovery evidence.

#### Actual primitive execution separates Bonjour from raw multicast

[Run 36712131992](https://github.com/p2pKit/P2pKit/actions/runs/36712131992),
source `4c8faef98b9ea04ef0ac05219a1f63250d767804`, compiled **both** native
diagnostic executables without warnings/errors and ran all eight controls:

| Unprivileged OS control | macOS host | iOS 26.2 x86_64 standalone simulator |
|---|---|---|
| Interface-selected IPv4 mDNS send | **FAIL**, errno 65, setup/close errors zero | **FAIL**, errno 65, setup/close errors zero |
| DNS-SD Any register/browse | One successful registration and own-service addition | One successful registration and own-service addition |
| DNS-SD LocalOnly register/browse | One successful registration and own-service addition | One successful registration and own-service addition |
| Network.framework advertise/browse/local TCP | One advertisement, own-service browse and accepted connection; connection ready; cleanup complete | Same observations; cleanup complete |

Neither Network.framework control reported an error or unsatisfied-path reason;
both observed a satisfied path. No DNS-SD policy-denied outcome occurred. Each
BSD control selected the one UP multicast-capable, non-loopback IPv4 interface;
it had a private address and was not point-to-point. Neither send returned
success. These observations establish that **working local Bonjour delivery
and failed raw multicast sends coexist**. Same-process Bonjour callbacks do
not prove packets traversed the provider network or that the JVM multicast gate
passed. Nor do the raw-send failures establish a blanket Bonjour/permission
denial explaining the original nine Kotlin failures.

All **122 ownership controls and 31 command finalizations** passed with known
zero owned survivors, no discovery errors, unchanged source and exact simulator
deletion. The two failed BSD commands and overall diagnostic remain **FAIL**.
The original nine Native methods, cold GUI readiness and capacity were **not
executed** in this diagnostic. Publisher-verified artifact SHA-256:
`cee1151441928f3f7884d35eb488c5e66d58e03b5d75d24182dd351436c1fdb9`.

The working C control differs from production in when it attaches advertising,
whether it includes TXT records, default versus explicit local domain, and
secure versus legacy service type. The next closed diagnostic variants vary
those choices separately, then combine the production-shaped choices. They
retain both actual architectures/contexts and all original diagnostic failure
requirements. They do not change production code, privilege, routes, permission
attribution or original discovery deadlines, and cannot admit product tests.

#### TXT-enabled browsing reproduces the missing callback below Kotlin

[Run 36713474346](https://github.com/p2pKit/P2pKit/actions/runs/36713474346),
source `840a4326d0ac92f557e77efd34446981c9221b8a`, actually executed all **18**
primitive observations on Intel/macOS 15/Xcode 26.3 and the iOS 26.2 x86_64
standalone simulator. Both contexts independently produced the same differential:

| Network.framework variation | Actual observation in both contexts |
|---|---|
| Basic advertisement/browser/local TCP | Own-service browse and accepted connection |
| Attach advertisement after listener-ready | Own-service browse and accepted connection |
| Null/default Bonjour domain | Own-service browse and accepted connection |
| Legacy `_p2pkit._tcp` type | Own-service browse and accepted connection |
| Publish TXT and request browser TXT | **Zero browse callbacks**, despite registered advertisement and ready browser |
| Combined production-shaped choices, including TXT | **Zero browse callbacks**, despite registered advertisement and ready browser |

The failing TXT variants still accepted the direct local TCP control connection;
all reported Network.framework error codes and unsatisfied-path reasons were
zero. Cancellation and owned cleanup completed. This reproduces the symptom in
plain C, below Kotlin, and rules out late attachment, domain defaulting or legacy
service spelling **alone**. It does **not yet distinguish TXT publication from
TXT resolution**, because that first TXT variant changed both. TXT admission
metadata must not be removed or silently made optional to obtain discovery.

DNS-SD Any/LocalOnly controls passed again; both selected-interface BSD mDNS
sends still failed with errno 65. All **122 ownership controls and 41 command
finalizations** passed. The six failed primitive commands and overall diagnostic
remain **FAIL**. No original Kotlin test or GUI-readiness gate ran here.
Publisher-verified artifact SHA-256:
`54c548dce82847758230c3108e601974796d9183d97e7485e92f9010031be489`.

The next bounded diagnostic separates publication-only, empty-TXT resolution,
and TCP versus empty browser parameters. A direct DNS-SD control additionally
resolves and independently queries a fixed synthetic TXT record, requiring exact
bytes, the registered port and a local target, then deallocating every reference.
It exports only codes, counts and booleans, never names, addresses or TXT data.
These controls retain production security settings and do not change product
discovery, deadlines, authentication or admission. The updated offline controls
passed **17 network-schema, 68 qualification-driver and 18 product-diagnostic**
tests; they are not a new native result.

#### TXT resolution, not publication or empty browser parameters

[Run 36715925411](https://github.com/p2pKit/P2pKit/actions/runs/36715925411),
source `46f001e0e503d1c07fae19808c7f4fe6dc3f6f08`, executed all **26** primitive
observations with **122 native controls and 49 verified command finalizations**.
Both actual Intel contexts independently confirmed:

- Publishing TXT while browsing without TXT **does deliver** the own-service
  result. TXT publication is not the cause of the missing callback.
- Requesting browser TXT still delivers **no callback**, even for an otherwise
  empty advertised TXT and when using full TCP browser parameters. Replacing
  `nw_parameters_create()` alone is therefore not an evidence-supported fix.
- Direct `DNSServiceResolve` and independent `DNSServiceQueryRecord(TXT)` both
  returned the **exact synthetic TXT bytes**, with zero API/process errors and
  the expected SRV port. However, the diagnostic's exact `.local.` SRV-target
  suffix observation was **false**. That complete diagnostic remains **FAIL**;
  its unexpected target must be explained, not waived. No target name/address
  was exported. All three DNS references were deallocated.
- Raw interface-selected multicast still failed with errno 65. Numeric local
  TCP controls still succeeded. These do not prove that dialing the discovered
  opaque Bonjour endpoint works.

The additional closed `network-separate-txt` experiment therefore uses a real
Bonjour endpoint, not the numeric connection shortcut, and queries the actual
Network.framework-published TXT on the same serial queue. Its success requires
both exact TXT and connection readiness/acceptance plus deallocation. A closed
SRV-target shape observation will distinguish case/terminator assumptions from
an unexpected target without exporting hostnames. No production API or policy
has yet changed and the original nine cases remain unresolved.

Public [runner-images issue #13230](https://github.com/actions/runner-images/issues/13230)
reports the same TXT-enabled/browser differential and manual DNS-SD resolution
in another CI environment. Its July 2026 closure links an ARM/macOS-15 app run;
that is **not** proof of a fix on this Intel runner or of this execution context's
internal cause. It does not justify permission changes, removing TXT checks or
substituting architectures. Original artifacts, complete workflow logs and the
independent review are retained in `actions-36715925411/` in the continuation
evidence directory.

#### Stable resources are still not available on the current Linux VPS

A fresh independent, natively owned kernel-timer control observed
**125.000079078 seconds** at a 10-ms period: **12,500 kernel expirations**,
**12,125 userspace reads**, **375 coalesced expirations** and a maximum read gap
of **1.880114653 seconds**. Three observed gaps were at least 100 ms. Guest
available memory again ranged from approximately 1.6 to 22.1 million KiB and the
balloon-inflate counter grew by **10,353,178 pages**. This ran without Java, RPC
or load traffic, in owned PID/mount namespaces, after dropping capabilities;
native finalization and private mount retirement were verified. The original
receipt SHA-256 is
`26371598b05538ac81e583df79bf1e2121902008e2ecbae28fab7e601be2fb36`.

Briefly high available memory between balloon cycles is not stable-resource
evidence. No new full capacity run was launched on this unchanged environment.
`clock-readiness-reviewed.json` in the continuation evidence directory retains
the independently reviewed observations. A healthy-generator full workload is
still required after resolving discovery; no numerical latency threshold has
been invented beyond the approved contract.

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
| Private-frame follow-up attempt 1 artifact ZIP, publisher digest verified | `a205f4e08ee40f44851c2c571f1d8bf0672c72462a2e2a755e667ddb8922dd76` |
| Private-frame follow-up attempt 1 independent review | `c9ab9ee5e3f67478ca830a2e4365a80f1af133d0492dd1869e1077e4b5513826` |
| Private-frame follow-up attempt 2 artifact ZIP, publisher digest verified | `6e83ec974a929e174885d5f6d8ed8ac525c3a8688d67953e7d54e67d964ab051` |
| Private-frame follow-up attempt 2 complete workflow-log ZIP | `109d60a22f34ad118c457c707b6f17fa66c0d95b4c1eb9d666ab1bcdb572f089` |
| Private-frame follow-up attempt 2 independent review | `07b788793bda757bd39c66d73d711d3ddba751cdc034bb8bad732f25c55b5b30` |
| Verified private-symbol 36703393356 artifact ZIP, publisher digest verified | `84fb1dcb556f81ae5c3e54f685d735dbba23641b6b1278a31af7da67c4342052` |
| Verified private-symbol complete workflow-log ZIP | `2cfef2740bfcccdfde3186d6d1a98e89fbd454bd14178c4b8e5a009e360319b3` |
| Verified private-symbol independent review | `1822f4bc204e9472e0022fefbe933af4b273be0ca83f483a75bb69e9417b77d8` |
| Public Apple TN3179 JSON response, research only | `478396395b18ce5024feb6635b08ac0719e45656a1adf30fa22ff39002b97c07` |

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
`actions-36698432884/` and `actions-36698432884-attempt2/` retain each attempt
separately, including complete available logs, original artifact, publisher
metadata, decoded summary and independent review. The pinned compiler symbol
and parser implementation/research are in `kotlin-simulator-source/`, with Git
blob identities verified. `private-native-symbol-offline.log` records the narrow
follow-up checks; they are not another Apple execution.
`actions-36703393356/` retains the completed private-symbol follow-up's original
artifact (ID **11091737693**), complete available workflow logs, source/attempt
metadata, `independent-review.json` and both local reviewer logs. The independent
reviewer is `review-36703393356.py` beside that directory. The current-source
offline checks are in `current-source-offline-63530bb8.log`; final repository
checks and repeated immutable-artifact verification are in
`verified-intel-final-offline.log`.
`public-intel-issues/apple-local-network-privacy-20260930.json` retains the
additional public Apple guidance; it is not runtime or permission-grant evidence.

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

## October 1 full Intel inventory: discovery recovered again, two separate failures

[36807541133](https://github.com/p2pKit/P2pKit/actions/runs/36807541133), source
`2bd107b3bd926d66d7b701c77fdb9f1b51d3eca0`, completed **FAIL** on native Intel /
macOS 15.7.9 / Xcode 26.3 / iOS 26.2. The original multicast control and original
LAN Native inventory passed again: **202 passed, zero failures/errors, one
pre-existing ignored diagnostic**. Observed Native totals were **1,049 passed,
zero failures/errors, one ignored**, including all eight diagnostic/frame-helper
methods. There is no remaining observed failure among the original nine cases.

The actual remaining failures are different:

1. `full-platform` returned product/final exit **1**, with **verified native
   finalization**. `:p2p-transport-lan:testAndroidHostTest` had **120 passes and
   one failure**; `:sample-kmp-shared:testAndroidHostTest` did not complete. The
   existing exporter reads Native XML only, so it did not preserve the failed
   Android method/assertion. The retained aggregate cannot identify its root
   cause. Extending closed source-bound Android failure diagnostics is required
   before attributing it to any known fixture or production defect.
2. `swift-simulator-readiness` hit the **original 120-second `simctl bootstatus`
   bound**, product **-15**, final **125**, with no admitted readiness. The
   simulator was initially Shutdown. Its 88 boot observations ended at elapsed
   111–118 seconds in status 2, with `WAIT_BACKBOARD` / `WAIT_MIGRATION` markers.
   The internal migration stall is unestablished; neither stale Booted state
   nor a native ownership defect is supported. No Swift unit/UI test ran.

All 122 native controls, ABI, Dokka, RPC frameworks, Swift API, SBOM, producer /
project and archive controls passed. There were **43 commands, 42 verified
finalizations (including the failed full-platform product), and 41 zero-exit
commands**. The readiness timeout remains unadmitted. Discovery-error/pending /
owned-survivor counts were zero; one transient environment observation recovered.
Exact simulator retirement, Terminal ordinary Quit, original advertising-policy
restoration and unchanged source were verified. No bound or security gate is
waived by these partial results.

Evidence is retained in `actions-36807541133/` under the continuation directory.
Artifact **11140828873** SHA-256:
`56d214ddbe909d8a8bef0bae2c9117bc7a7b1b453b4ec3aaab633c040ce18542`;
complete logs SHA-256:
`c6a7604ca088337e896bd79247397c3365957dbed871075ea6d3b300b7d4e9a3`.
The original review incorrectly labeled 41 successful commands as finalizations;
it is retained. Independently recounted `independent-review-v2.json` SHA-256:
`9158a69a084d781afb57fcb60660f2a9c743fe1489eb61b94b18e1b3c9ecfe9b`.
This correction does not promote either failed phase.

### Narrow source-bound follow-up, before repeating the full Intel inventory

The diagnostic exporter now observes `testAndroidHostTest` XML **separately**
from Native XML. Both the full profile and a new explicit
`[rpc-intel-runtime-investigate]` experiment retain failed source method names,
unambiguous source line locations, fixed error markers and counts; no raw
assertion text, paths, identities or payloads leave the runner. The original
Native reader remains Native-only, so Android observations cannot inflate its
counts. Regression controls reproduce the original lost-host-failure shape and
reject unknown identities, cross-family labels, entities and symlinks.

The narrow experiment uses the same real Intel/macOS 15/Xcode 26.3 host,
nonroot Terminal ancestry, all native controls, reversible advertising setup and
original multicast admission. It requests the two affected tasks only:

```text
:p2p-transport-lan:testAndroidHostTest :sample-kmp-shared:testAndroidHostTest
```

Original fresh/no-cache/strict-dependency/two-worker flags and the 7,200-second
outer platform bound remain. `--continue` allows the second independent task to
produce evidence after a test assertion, but **both must execute and pass**:
skips, cached tasks, stale coverage, unrequested tasks or unverified finalization
cannot pass. Exact task XML must match the actual model/coverage counts.

It then creates its own untouched simulator and executes the **same single
120-second `simctl bootstatus -b` check**, with read-only hardware/memory/load
observations before/after. This compares fresh GUI readiness in the same
Terminal context as the failed full run without preceding Native or Swift
work. It does not reattempt an already timed-out boot or extend its deadline.
Any unsafe ownership still blocks product continuation; exact device retirement
and configuration restoration remain mandatory on every outcome. The earlier
non-Terminal cold-boot experiment is unchanged. The new scope cannot stand in
for full Intel, ARM, Swift, physical LAN or release qualification.

Files changed: `rpc_product_diagnostics.py`, `run-rpc-qualification.py`, the
explicit Terminal mode allowlists in `with-darwin-terminal-context.py` and
`diagnostics/apple-terminal-context.m`, the feature workflow and their offline
controls. No product/adapter, architecture, native tracker, timeout, original
full-profile policy or Apple fixture is changed. Actual follow-up results are
pending; the Android failed method and internal migration-stall cause remain
unestablished until evidence is produced.

The narrowed follow-up passed **254 offline controls**, including 79
qualification/architecture/ownership controls, 20 diagnostic privacy/failure
controls and 22 Terminal ownership/context controls. Repository layout, OSV
coverage, 618 active Markdown links, release metadata and whitespace passed.
Retained log `intel-runtime-offline.nRRBMjtR.log`, SHA-256:
`da3b8f49435f8f79efdf719cfdaa68e3e329588680ba291ef8e75406ec866987`.
No Apple or Android execution is inferred from these offline fixtures.

## October 1 complete hosted capacity run: permit saturation, not timer loss

[36810471106](https://github.com/p2pKit/P2pKit/actions/runs/36810471106), source
`7b23caae372170b110ff463aab62822d2a0dc3db`, completed the actual full workload on
a four-affinity-CPU hosted Linux runner, using separate authenticated JVM
processes over the isolated same-host veth/TCP fixture. It **failed acceptance**:

| Measurement | Actual result |
|---|---:|
| Measured scheduling duration | 1,800.000942576 s |
| Required calls | 2,304,000 |
| Dispatched / replied / host accepted / host completed | 2,301,188 each |
| Missed slots: permit / timer / worker | 2,812 / 0 / 0 |
| RPC errors / failed invoked calls / timeouts | 0 / 0 / 0 |
| Completed-response throughput | 1,278.4371083 / s |
| Client-call p50 / p95 / p99 / max, upper-ms buckets | 4 / 13 / 134 / 4,621 |
| Scheduling-delay p50 / p95 / p99 / max, upper-ms buckets | 1 / 2 / 4 / 85 |
| Host / client CPU, measured interval | 3,125.05 / 3,468.56 CPU-s |
| Whole host-series maximum RSS / native threads | 889,516,032 bytes / 179 |
| Sampled maximum outstanding / host queue | 465 / 0 |
| Whole-series maximum records / retained payload | 77,190 / 31,272,730 bytes |
| Idle-retention observation | 65.217 s, PASS |

Every one of the 2,304,000 slots was considered. In the unchanged scheduler,
`permits[index].tryAcquire()` refused **2,812** because that client's existing
eight call jobs had not completed. These slots never reached `RpcClient.call`;
therefore zero RPC errors/timeouts is consistent with, not contradictory to,
this failure. No automatic retry or transport loss is involved. After drain,
outstanding calls, invalid host samples and connection changes were all zero.
The independent collector verified the complete accounting and native
finalization, including the client exit **1** required by the failed gate.
Retained connections/work/records/payload all returned to zero without forced GC.

The generator was not experiencing the earlier VPS resource problem: the
independent 125-second control read all **12,500** expirations without coalescing;
measured timer/worker maxima were **66.788286 / 40.954527 ms**; no observed
balloon, direct reclaim, major-fault or steal growth occurred. There were **zero
100-ms safepoints** (maximum **50.434003 ms**). Combined product CPU averaged
about **3.66 cores of four**, so this is not evidence of unlimited headroom.

Host observations show initially lower throughput, reaching approximately
1,280/s near host uptime 39 seconds, then sustained two-minute windows near the
target. This supports investigating uninitialized RPC/codec/JVM paths, but the
old exported diagnostic retains only aggregate schedule counts: it does **not**
prove the exact seconds of all permit refusals or identify JIT as their cause.
The successful-call percentiles exclude unsent slots and are not proof of
full-arrival latency or cold-start qualification.

The same run also passed **1,172 JVM cases**, all six actual socket correctness
cases, and **20/20** separate 1-MiB request/reply calls at concurrency two:
**3.164384640 s**, **6.32034417 responses/s**, p50/p95/p99 **239/639/760 ms**,
zero errors, **65.251-second** retention and exact native cleanup. These passes
do not compensate for the failed steady experiment.

### Bounded initialization experiment, without changing measured acceptance

The approved plan explicitly requires **steady state**, not immediate peak load
from cold RPC/codec paths. The driver previously started measurement immediately
after connection setup, before any application RPC. The maintained sample now
adds a fixed, separately accounted **600 real echo calls/client** before the
clock: **76,800 additional** requests/responses, one in flight/client, minimum
100-ms spacing, fixed 120-second call-phase bound. It awaits slow replies rather
than dropping slots; any failure cancels children and prevents measurement.
Initialization counts, latency, CPU, compilation counters and exact host deltas
are exported separately as **INITIALIZED_NOT_CAPACITY**, never capacity credit.

The subsequent 1,800-second / 2,304,000-call target, original eight permits,
100-ms late condition, deadlines, host/queue/resource limits, retention and
ownership remain unchanged. No adaptive repeated warmup, missed-slot tolerance,
product transport change or larger limit is introduced. The collector requires
initialization → full measurement → cleanup order and separate host accounting.
Complete bounded per-second schedule/runtime series are now exported, so the
next result can localize any new missed slots instead of relying on aggregate
correlation. An initialization-only result or partial measurement cannot pass.

Four new deterministic Kotlin controls cover exact call counts/spacing, slow
calls without dropping/overlap, failure without retry and deadline/child cleanup.
They require the next hosted JVM execution; **not yet run at this checkpoint**.
The current local offline controls pass: **15** numeric evidence, **9** scheduler
analysis, **17** hosted admission/accounting and **12** lab controls. The next
source-bound workflow must compile/test first, then run the entire full workload.
No capacity pass is claimed before actual results and independent resource review.

The broader offline continuation passed **227 Python controls**, repository
layout, OSV lock coverage, **618** active Markdown links, release metadata,
changed Kotlin line-length and `git diff --check`. Retained log:
`capacity-initialization-offline.9itr4vfM.log`, SHA-256
`8ae8db2195e8b73eeadc4d5b155797a392222072bb967cb6f25dc6273062ba60`.
No local Java/Gradle/application execution or dependency download was performed.

Alternative changes rejected: raising permits would alter the original limit;
allowing misses/shortening the window would relax acceptance; product tuning
without a demonstrated product defect would conflate causes. The cold-path
failure remains visible, and a future steady pass would not qualify startup,
cross-device, physical LAN, Android or iPhone hosting capacity.

Retained evidence: `actions-36810471106/`, artifact **11139934798** SHA-256
`a996608f4094da043ce6103bf8cf1f308ecedf34b498f6e9ac50c7fb02078475`;
complete workflow logs SHA-256
`b69548925e26ff4d28848c1dcd3a6bfa20a086221fe6710cb21abe4a92ec11e8`;
independent review SHA-256
`ba1190af47c6333cee2357ff3c3653f56b5cb50231c065e6dd3f20e0798cf2e1`.
The earlier unadmitted hosted attempt and all earlier failed VPS runs are
retained separately. Foundation remains **NOT_READY**, with every HOLD intact.

## October 1 JVM regression stopped the next capacity attempt before load

[Run 36815606270](https://github.com/p2pKit/P2pKit/actions/runs/36815606270),
source `4f295c81f7954b4e330fb3e5cf6f2899c3da370c`, completed **FAIL**.
All **121 native controls**, both JDK checks and compile-SDK setup passed.
The original `jvm-regression` invocation returned **product exit 1** after
**328.488 seconds**, with independently verified native finalization. All five
command receipts and unchanged source were verified. The producer, correctness,
large-payload, clock, initialization and steady workloads **did not execute**.

The complete workflow logs expose the phase boundary but not the underlying
Gradle output. The existing capacity exporter omitted compiler and failed JVM
test observations; the exact underlying failure is therefore **not established**.
It is not evidence of a 30-minute capacity failure, and is not labeled a Kotlin
compile failure or assigned to a particular test without the missing evidence.

The reporting fix adds source-bound JVM XML and closed compiler diagnostics to
`scripts/rpc_product_diagnostics.py` and integrates them into
`scripts/run-rpc-capacity-qualification.py` **before** nonzero product exit stops
the phase. It records only known method/task names, unambiguous checked-in source
locations, fixed error categories, counts and digests. All observations retain
`executionAdmitted=false`; raw messages, private paths, identities and payloads
remain unexported. The collector independently rereads the original receipt-bound
streams and token-bound report and requires exact equality before export.

Regression controls exercise the actual failed-invocation reporting path with
synthetic inputs, plus wrong tokens, altered logs, duplicate observations,
ambiguous/unknown filenames, out-of-range source locations and private-field
rejection. These are offline reporting tests, **not JVM or capacity execution**.
No product, admission, workload, concurrency, deadline or cleanup gate changed.
The next authorized hosted attempt must first pass the unchanged complete JVM
regression before any load is allowed.

Local verification: **259 offline controls passed** across capacity isolation,
accounting, generator analysis, native/Terminal orchestration, Bonjour preparation
and diagnostic privacy. Android setup policy, RPC source inventory, repository
layout, OSV lock coverage, **619 Markdown links**, release metadata and whitespace
checks passed. Log `capacity-diagnostic-offline.UqxMJUss.log` SHA-256:
`71a26c57db95cd493d13126ca12c016c718f1cc8a96abb7f6c4260b0cc7dea1a`.
These checks did not start local Java/Gradle/application workloads or download
dependencies; the new Kotlin initialization tests still require actual execution.

Evidence directory: `actions-36815606270/` under the task-private evidence root.
All **17 complete workflow log entries** were read and hashed. Artifact
**11140879823** SHA-256:
`c945c799b106ff8b27bbe3ec3bbd8c579e3d69cbea4a10a5afe551779d04584a`;
complete logs SHA-256:
`b0ed3d2273e009c2050f7bdb0ac26120126194325963cddaeafa4a2c31ca5b2c`;
independent review SHA-256:
`93882c98b40884718d7d84ea9ec1f317547e6ad57800aea9521e5a0f70d76e23`.
The Intel runtime diagnostic at source `016d79ea` is independent and still
pending at this checkpoint. Capacity, complete Intel/ARM qualification and all
release HOLDs remain unchanged; Foundation is **NOT_READY**.

## October 1 Intel host failure identified and fresh GUI timeout reproduced

[36816282836](https://github.com/p2pKit/P2pKit/actions/runs/36816282836), source
`016d79ea4d42a479720cfed9a46ebffc00aa01ed`, completed **FAIL**, not a full matrix
execution. All **122 native controls**, original JVM multicast and reversible
Bonjour preparation passed. The two Android host tasks actually reported:

- `:p2p-transport-lan:testAndroidHostTest`: **120 passed / one failed**.
- `:sample-kmp-shared:testAndroidHostTest`: **one passed / zero failed**.

The failed method is
`AndroidLanDataTransportOwnershipTest.inboundPerSourceQuotaRejectsBeforeQueueAndRecoversAfterRelease`.
The recovered failure locations are **`AndroidLanDataTransport.kt:362`**, the
actual `sock.accept()` call, and **`AndroidLanDataTransportOwnershipTest.kt:385`**,
the independent incoming-flow collector. This is not an original Bonjour test,
a Native test, or a process-ownership assertion. The first diagnostic exporter
did not retain the JDK exception kind/fixed socket-error category, so **the exact
socket failure mechanism is not established yet**. No production exception is
being ignored or retried on that incomplete evidence. The next diagnostic adds
only closed JDK error categories; it retains the complete original host tasks,
all assertions, timeout limits and failed-attempt evidence.

The diagnostic-only change passes **24 closed-diagnostic, 79 qualification and
19 capacity orchestration controls**, repository layout, OSV coverage, 620
Markdown links, release metadata and whitespace checks. Offline log
`intel-accept-diagnostic-offline.anEUE7Eo.log` SHA-256:
`ae94335c551eabe07c6eaf1e002ab5721834753a3b54351a4779ba3cf3b3509c`.
These are not Native/JVM product or simulator pass counts.

The newly created **iOS 26.2 x86_64-capable iPhone-17 simulator** started Shutdown,
had never run Native/Swift products, and again failed its single **120-second**
`bootstatus -b` readiness bound. It recorded 99 states: Data Migration progressed
to System App at approximately 115 seconds, but remained nonterminal at 119.
It never passed the readiness gate. Thus prior Native execution or a stale
Booted simulator cannot account for this reproduction.

Read-only native-host snapshots show **four logical CPUs / 14 GiB RAM**. The
1/5/15-minute load averages changed from **4.428 / 5.441 / 5.469** to
**393.650 / 145.046 / 61.077** during boot. Free pages changed from 1,469,102 to
4,840 (4-KiB pages); pageouts increased by 266, with no reported swap-in/out or
compressed-page growth. These are real resource observations, **not CPU
utilization or proof of a particular service's internal cause**. Inactive and
speculative pages must not be mislabeled as unreclaimable memory. The protected
set-id system `ps` was not executed. No deadline extension, hidden warm-up,
extra boot attempt, security change or substitute architecture was used.

There were **30 verified finalizations among 31 commands**, with zero discovery
errors, pending observations or owned survivors. The remaining unadmitted
receipt records exactly **`Product command timed out`** for readiness; the generic
`OWNERSHIP_UNPROVEN` phase label does not establish an ownership-discovery defect.
Exact simulator shutdown/deletion, nonroot Terminal Quit/child reap and
**TRUE → FALSE → TRUE** advertising restoration all passed independently.

All 17 complete workflow-log entries were read/hashed. Evidence:
`actions-36816282836/`; artifact **11141766994** SHA-256
`0d43f4977f8f17de1bc4c12f5fec5d00e1d4d62ebf8e6270bad9340e369f201a`;
complete logs SHA-256
`54004040fb9ffe5830af6ce2e8a526b55054e2a39767c51bb8f74c3f0714e34b`;
independent review SHA-256
`d76ff8fda81622a3545d4b0f497c88411d1b461ce8ad489f6d84244be6b60d8a`.
The original nine discovery cases remain recovered in two prior original-profile
runs. Full Intel/ARM, GUI readiness and the full-rate capacity gate are still
unqualified. The independent capacity run at source `911e5edf` is in progress;
all release HOLDs and Foundation **NOT_READY** remain.

## October 1 socket-closed failure isolated; cancellation regression pending

[36818385640](https://github.com/p2pKit/P2pKit/actions/runs/36818385640), source
`84281a7a4f5c11c425bdeb527469cb53a1aa692a`, completed **FAIL**. The closed
diagnostic now identifies `JAVA_SOCKET_EXCEPTION` / `JAVA_SOCKET_CLOSED` in
`AndroidLanDataTransportOwnershipTest.acceptedOptionFailureClosesWithoutConsumingASourceSlot`.
Source locations at that commit are test line **151** (the fixture delegates to
real `ServerSocket.accept()`), production line **362** (that call), and test
line **636** (the incoming-flow collector). The previous run failed a different
method at the same accept boundary. Original host-task counts remain **120/1**
for LAN and **1/0** for the shared sample; no host suite pass is claimed.

Source tracing identifies a cancellation race to test: `awaitClose` cancels the
accepter and closes its listener to unblock real `accept()`. The exception
handler checks transport-wide `closed`, but not accepter cancellation. When the
collector cancels before transport-wide close, the expected unblock exception
can re-enter live-listener recovery, close the already retired listener again,
and try to terminate the producer with that socket error. This is not permission,
authentication, quota rejection or another initial Bonjour-discovery failure.

Two new mirrored JVM/Android-host regressions use a real accepting socket and
the original five-second bound: one requires cancellation with exactly one
production listener retirement; the other requires an active accept failure to
retain its cause and retire its listener. Join is outside the cancellation
assertion, so a hung cleanup cannot pass as cancellation. These tests are
**not yet executed**, and no production change is included in this checkpoint.
The next authorized JVM regression runs before any capacity workload; the
existing full capacity attempt is not cancelled or replaced.

The fresh iOS 26.2 x86_64-capable simulator again failed its original readiness
bound, still in Data Migration at 120–121 seconds (95 observed statuses).
Readiness remains unqualified. Unlike the earlier allocation, this run also
has **unproven observer and Terminal cleanup**: the after-hardware command
actually exited **zero**, but an unresolved native `ENVIRONMENT_EIO` made its
finalization fail with `PRE_STOP_DRAIN_FAILED`. It was **not** a hardware-command
timeout. Terminal's native child finished and its script child was reaped, but
the original Quit completion check failed; application termination and command
removal are not proven. Neither error has been suppressed. There were **27/29**
verified command finalizations, 122 native controls, zero recorded discovery
errors/pending observations/owned survivors, and verified exact simulator and
Bonjour-setting restoration. Those successes do not imply whole-context cleanup.

All 17 workflow-log entries are retained and hashed under
`actions-36818385640/`. Artifact **11142034383** SHA-256:
`7641ce89e3f402eceba51b17ad35e64d70a601a0a6cf40203e148c866b68853e`;
complete logs SHA-256:
`e58c727a075843940ca5f7e3dd38439d3db1d0b8568f72695e9f4253924c4665`;
independent review SHA-256:
`745871bd16bed40cf71a217feb563af5d930d78b87e5fdc9f8e1a58a1ae9b273`.
The original nine discovery passes remain valid for their recorded sources;
full Intel/ARM and capacity are not qualified. All release HOLDs remain.

## October 1 full-rate 30-minute same-host JVM workload passed

[36817165645](https://github.com/p2pKit/P2pKit/actions/runs/36817165645), source
`911e5edf6b84af62da0f37b5456aec9dcaf2f29f`, completed the **entire** workload.
The independent review verified publisher/source hashes, all 1,800 schedule
bins, complete counters, resource series, retention and native finalization.
The eight workflow phases and all seven outer command receipts passed, as did
the three native receipts for **each** separate socket workload. The fresh JVM
regression passed **1,176 tests** (core 858, RPC 46, LAN 233, sample 39), including
all four new initialization controls; none failed or skipped.

Topology is unchanged: two independently owned JVM processes in isolated Linux
network namespaces communicate through private virtual Ethernet/TCP, using
128 independently authenticated synthetic clients and the real production
transport/RPC/serialization paths. This is **same-host JVM validation**, not
two physical machines, Bonjour-over-physical-LAN proof, or Android/iPhone capacity.
The feature-only `rpc-capacity.yml` workflow runs the source-bound executor and
`python3 scripts/run-rpc-capacity-qualification.py run`, followed by the
independent `collect`; no local JVM execution was performed for this result.

| Measurement | Verified result |
|---|---:|
| Measured scheduling duration | **1,800.000735685 s** |
| Independently authenticated clients / calls per second each | **128 / 10** |
| Encoded request / response | **1,024 / 1,024 bytes** |
| Required / dispatched / completed / host accepted / host completed | **2,304,000 each** |
| Timer / permit / worker misses | **0 / 0 / 0** |
| RPC failures / timeouts / connection changes | **0 / 0 / 0** |
| Completed responses per scheduling second | **1,279.999476846** |
| Client-call p50 / p95 / p99 / max, upper-ms buckets | **4 / 14 / 32 / 294** |
| Scheduling p50 / p95 / p99 / max, upper-ms buckets | **1 / 2 / 3 / 21** |
| Final call-drain duration | **10.830613 ms** |
| Host / generator observed CPU | **3,148.54 / 3,493.02 CPU-s** |
| Whole host-series sampled peak RSS / native threads | **931,823,616 bytes / 177** |
| Sampled maximum host queue / outstanding calls | **0 / 48** |
| Whole-series maximum retained records / payload bytes | **76,875 / 30,045,664** |
| Idle-retention observation | **65.171 s, PASS** |

All 1,800 schedule bins independently contain **1,280 considered, dispatched and
completed slots** with zero refusals or late drops. The host reports zero
duplicate requests, protocol/connection failures and refusals during the steady
experiment. There is no separate exported retry counter; the complete first-call
latencies and unchanged connection/duplicate counters show no recovery activity.
The agreed plan has **no numerical latency cutoff**: these are measurements, not
comparisons against a new or relaxed threshold. Client-call latency includes
serialization/transport/dispatch/response; it is not isolated server-handler time.

The independent preflight read all **12,500/12,500** clock expirations over
125.000271948 seconds, with zero coalescing. During load, timer/worker maxima
were **16.063330 / 14.875816 ms**; no balloon, reclaim, allocation-stall,
major-fault or CPU-steal growth was observed. Available system memory remained
13,698,268–14,328,420 KiB. Maximum JVM safepoint was **16.595622 ms**, with zero
100-ms pauses. These data rule out the earlier measured generator stalls in
**this** run; they do not guarantee that an arbitrary VPS will behave similarly.

Resource review does not treat a green mechanical result as automatic capacity
evidence. RPC queue samples remain zero; retained records settle near the
60-second window of 76,800 and stay below the original bounds. Native threads
plateau at 176 during the final 20 minutes. RSS rises while the JVM commits
memory, then approaches a plateau: final successive five-minute ranges are
**875.62–875.92 MiB** and **875.93–876.27 MiB**; the final window rises 360,448
bytes. After retention, connections, running/queued work, records and retained
payload all equal zero; JVM/native threads fall to **11/28**. RSS is not claimed
to reset, and this bounded 30-minute observation is not proof against every
possible smaller or longer-horizon leak. Host and generator together consume
approximately **3.69 of four cores**; there is no spare-capacity extrapolation.

The fixed initialization independently completed **76,800 additional calls** in
65.982128391 seconds (zero errors); its p95/p99 were 114/231 ms and the generator's
cumulative compilation counter rose from 7,365 to 53,373 ms. None of these calls
or seconds count toward the measured requirement. Compared with the previous
2,812-permit-refusal attempt, the unchanged eight-per-client permits now suffice
for every scheduled steady call. This supports correcting the benchmark's cold
data-path start, **not changing product admission or reliability**. It does not
retroactively identify JIT as the sole cause of every old refusal or qualify
cold-start peak load. The earlier 69,538-slot VPS failure and all failed attempts
remain recorded separately.

The independent large-payload workload also passed: **20/20** 1-MiB request and
response calls, concurrency **two**, duration **2.989906670 s**, throughput
6.689172007/s, p50/p95/p99 **216/677/748 ms**, zero errors and **65.240-second**
retention with complete native/identity cleanup. All six real-socket correctness
cases passed: concurrent correlation, application errors, procedure authorization,
sent deadlines, sent cancellation and closure during a call.

Evidence: `actions-36817165645/` under the task-private evidence root. Artifact
**11143925710** SHA-256:
`91d38f888e0b1e79fc62b4d82c92f26ee91325f829a21ea3b5d8c0c20a32aa5c`;
all 17 complete workflow-log entries retained, archive SHA-256:
`cf17faad0e0ff31e6df2961ab416061f7ff2baa216ca7153917b2078d2f47919`;
independent review (including five-minute resource windows) SHA-256:
`fce4dd82c97d3ea73c8ae86b2c827d442481597e803d302ba4e453446162f592`.
This qualifies the **recorded same-host steady workload and observed resources
at this source**. It does not promote the full RPC/mobile/physical-LAN or release
gates, nor automatically validate the pending cancellation correction. Original
Intel discovery has passed twice; independent Intel GUI/cleanup and full ARM
gates remain open. Foundation remains **NOT_READY**.

## October 1 cancellation race reproduced before the production correction

[36820318142](https://github.com/p2pKit/P2pKit/actions/runs/36820318142), source
`5383c5c936c0fdab38236c69e3c1a9fe3e80c42c`, produced the intended **red
regression**. The real-socket test
`collectorCancellationDoesNotReclassifyItsClosedListenerAsAnAcceptFailure`
failed exactly at **line 83**, the assertion requiring one production listener
retirement. Its earlier real-accept entry, bounded join, cancellation, closed
listener and unpublished-port assertions had passed. The active-error cause
control and 233 original JVM LAN cases passed: **234 passed / one failed**.
The other three JVM tasks did not complete because the build failed; there was
**no producer or capacity workload execution** in this deliberate regression run.
All 121 native controls and five command finalizations passed independently.

The smallest mirrored production correction in `JvmLanDataTransport.kt` and
`AndroidLanDataTransport.kt` checks `currentCoroutineContext().ensureActive()`
when blocking `accept()` throws, before live-listener failure recovery. A
cancelled accepter now follows its existing cancellation exit; `awaitClose`
continues to own the listener retirement. An active accepter still executes
the unchanged error/cleanup path. No socket exception is globally ignored, no
listener retry added, and no admission, quota, authentication, cleanup-ledger,
deadline or lifecycle assertion changed. Two pre-existing overlong logging
lines in the touched files were wrapped without changing their messages.
The correction is **awaiting green JVM and Android-host execution** at this
checkpoint; the passing capacity run above was at the preceding product source.

For the independent Intel GUI failure, the prior snapshots could not identify
which OS processes consumed resources because system `ps` is set-id. The new
diagnostic-only [`rpc_intel_process_diagnostics.py`](../../scripts/rpc_intel_process_diagnostics.py)
reads documented libproc task/BSD/path metadata and host CPU ticks as the
unprivileged, admitted native Intel account. It never executes/copies `ps`,
reads arguments/environments, acquires process task ports, signals a process,
or changes services/settings. Its host-port reference is always released, and
release failure fails the observation. Only numeric aggregates for fixed OS
roles leave the probe; unknown names/PIDs/paths do not. Unreadable or racing
processes are explicitly counted, never treated as safe exits. These snapshots
run before/after the **unchanged 120-second boot command**, only in the existing
Intel diagnostic scope, and cannot replace ownership or readiness admission.

Seven new offline controls cover ABI layouts, native/nonroot admission,
host-port cleanup, closed aggregation, denied/racing observations, privacy and
collector validation. Together with the existing 24 diagnostic, 79
qualification and 19 capacity orchestration controls, **129 offline tests pass**;
log `native-process-observation-offline.R5VTgCIg.log` SHA-256:
`d33dac9e5f12d8fbdfcd312fc2f9cb3e3b90e4a3daf09d2492d9158878c1bd2f`.
This is not yet native execution of the new probe. Public runner reports of
CPU/indexing/crash-service contention are hypotheses, not this run's established
cause; disabling those services, privileged product execution, longer readiness
limits and architecture substitution remain rejected alternatives.

Red-run evidence: `actions-36820318142/`; artifact **11143087225** SHA-256:
`82131387e503f1aaba0bf87b83f6b8406acb19fc8862e7b95d0c595ba8a56977`;
complete logs SHA-256:
`3bbe27aa1572cc567a4eb0475683b928b4f715d021255930bb77f7168bfdcfdd`;
independent review SHA-256:
`5dafcfd1aeba6e6361f490e8649d31187855ecc286c55b87711c79f6ac419d9a`.
The next runs retain complete JVM/Android-host regression and the full measured
workload. Intel GUI/cleanup and full ARM remain open, with all release HOLDs.

Before dispatch, the broader **14-suite / 298-test offline check** passed, along
with repository layout, OSV lock coverage, **624** Markdown links, release
metadata, complete touched-Kotlin line limits and whitespace checks. Instructions
remain byte-identical. Log `cancel-aware-accept-offline.7ggE98Mv.log` SHA-256:
`34b9270faf59fc72d78110d4ab9a4b755c1f97c7b3e3430303fbe3ee649d25eb`.
No local Java/Gradle/application execution or dependency download was started.

## October 1 follow-up: admission fixture timeout and drain observation defect

[36821968958](https://github.com/p2pKit/P2pKit/actions/runs/36821968958), source
`1b50f655eec687e757ecbfdfe45024413b4c438b`, failed **before** Android host tests,
the new process snapshots, or simulator creation. Its 122-control attempt has
one failure:
`test_actual_consumer_caller_with_real_executor_retains_external_report_and_receipts`,
at source line **3269**. The outer `executor-fixture` command hit its original
**20-second** deadline. `consumer-publish` completed and finalized; the nested
`consumer-build` product and stop exited zero, but its source recheck was
interrupted during enclosing cancellation. This is not evidence of a changed
feature source, an Android accept assertion, or another Bonjour regression.

The native command's actual finalization passed with zero remaining discovery
errors/pending lifetimes. Its `ENVIRONMENT_EIO` observation recovered. No native
control pass is admitted from an incomplete attempt. Separately, Terminal
reported the exact script child reaped and Quit requested, but failed
`QUIT_COMPLETION`: application termination and command removal remain unproven.
Successful earlier Terminal finalizations also include nonzero product exits,
so a failing product exit alone does **not** explain this behavior. No forced
Quit, process-name sweep, prompt acceptance, or deadline increase was attempted.

The existing export omitted command durations, preventing attribution of the
20 seconds among fixture preparation, product execution, and finalization.
The diagnostic collector now exports bounded **relative** receipt timing:
monotonic total elapsed milliseconds and explicitly labeled UTC-wall intervals
before/during the product, before/during stop, and after stop. Missing intervals
remain null; wall-clock reversal remains negative, not a successful deadline.
No timestamp, identity, path, environment, or raw output is published. These
observations cannot admit execution or change the original deadline.

Independent inspection of the earlier `36818385640` pre-stop failure found a
real finalizer defect in `scripts/audit_processes.py`: the common POSIX drain
counted an empty **known-owned** list as quiet even when `pending_discoveries`
contained an unresolved lifetime. Three polls could return after **0.2 seconds**;
the Darwin wrapper then correctly rejected the still-unclassified lifetime.
That return was premature, not permission to suppress the rejection. The
earlier receipt later had no pending record, but its export cannot establish
when reconciliation occurred or that it was within the original drain bounds.

Three deterministic, explicitly **offline** regressions reproduced the defect
before correction: both eventual-exit/positive-ownership cases raised too
early, and the persistent-unknown case used only 0.2 seconds rather than its
configured observation window. The minimal correction counts a quiet sample
only when both known-owned workers **and pending discoveries** are empty.
It keeps the original grace/kill-wait bounds, native identity acquisition,
signaling authority, sticky structural errors, and terminal rejection intact.
It neither signals nor declares an unknown process retired. Newly proven owned
workers are still drained; persistent unknowns still fail. All three regressions
and the other **81** offline policy/observation controls pass after correction.
This is not yet native Apple verification of the change and does not establish
the consumer timeout or simulator-readiness root cause.

The required native inventory grows to **125 Apple / 124 Linux controls**;
the capacity collector now uses that same source-derived complete inventory
instead of a stale historical literal. Old counts cannot satisfy the new gate.
No product source, qualification target, architecture cell, or original test
bound changes in this follow-up. The independently running full capacity rerun
at `1b50f655` must still complete and be reviewed on its own source binding.

Failed-run evidence is retained in `actions-36821968958/`: artifact
**11142958578**, SHA-256
`405984d0544ff9cdf7d839755e7dcf792648b56e0c6b413e39a606e43509765a`;
all **17** complete workflow-log entries, archive SHA-256
`52268a4419777d97301e7fae6a77b9e071e4cdecc087a3a59955e528b863cc3e`;
independent review SHA-256
`049f1219bfffd8efa33aaf8c59da0f6c5cd1f8fd35ac5c29fea080d605a36ad0`.
The deliberate red offline run is `pending-drain-regression-before.log` in
the task-private evidence root. All wider gates and Foundation **NOT_READY**
remain unchanged.

Before native follow-through, **386 offline tests across 15 suites** passed,
plus repository layout, OSV lock coverage, **625** Markdown links, release
metadata and whitespace checks. Protected instructions are byte-identical.
Log `pending-drain-offline.XSNvMy1c.log`, SHA-256
`0afa3ad94f06253eac710200622f805917b991ea57f2cb28f193ed15f387c8d9`.
No local Java/Gradle/application execution or dependency download was used.

The correction is committed as `9d3bf1608ead8e41093ee48305ca8ebbfb643ce8`.
The targeted [Intel runtime follow-through](https://github.com/p2pKit/P2pKit/actions/runs/36823649364)
retains Android host regression, actual process observations, and the original
fresh-simulator deadline. It is **in progress, not passed**, at this checkpoint.
Because the drain is a shared native executor, the next separately requested
Apple admission matrix must also execute all **125** controls on **both**
required native architectures. Intel or offline observations cannot substitute
for ARM. Admission-only evidence will not be promoted to product, discovery,
Swift, or capacity qualification.

## October 1 native admission verified on both architectures; Intel GUI remains failed

[36823874982](https://github.com/p2pKit/P2pKit/actions/runs/36823874982), source
`3d3058af1e3260d390622a4262b3ac36225ba5cb`, passed **125/125 required native
controls on each architecture**: actual ARM/macOS 26/Xcode 26.5 and actual
Intel/macOS 15/Xcode 26.3. Both source-bound command finalizations passed with
zero pending observations, discovery errors or owned survivors. ARM reconciled
eight absent/one recovered observations; Intel seven absent/two recovered.
The products took 120.221/160.456 seconds; their complete receipts took
127.918/173.334 seconds. This is native follow-through for the pending-drain
correction, **not** product, GUI, Bonjour, or capacity qualification.

The separate Intel runtime diagnostic
[36823649364](https://github.com/p2pKit/P2pKit/actions/runs/36823649364), source
`9d3bf1608ead8e41093ee48305ca8ebbfb643ce8`, also passed all 125 controls and the
original JVM multicast prerequisite. Android **host** regression passed all
**124 cases** (LAN 123, shared sample one; 19 XML files, zero failed/skipped),
including the mirrored cancellation/active-accept failure controls. These are
not ART or device results. Its consumer fixture no longer timed out, but this
does not retrospectively establish the exact cause of its earlier 20-second
failure.

Two independent failures remain in that diagnostic:

- A freshly created, initially Shutdown, x86_64-capable **iOS 26.2** simulator
  still exceeded the original **120-second** readiness deadline without any
  preceding Native/Swift use. The 101 recorded statuses end at status two,
  119 seconds, with `WAIT_BACKBOARD` and `WAIT_MIGRATION`. The product lasted
  120.169 seconds, exited -15 and finalized 125 with the exact
  `Product command timed out`. All four environment-observation errors
  reconciled; zero pending identities remained. This is a readiness timeout,
  not a newly demonstrated ownership-admission defect.
- Terminal again failed **`QUIT_COMPLETION`**. Its native child finished and
  the script reaped that child; the original application identity was verified
  and ordinary Quit requested, but application termination and command removal
  remain unproven. No forced quit, prompt suppression or relaxed deadline was
  substituted for cleanup.

**32/33** native command finalizations passed. Exact simulator shutdown/deletion
and Bonjour `TRUE → FALSE → TRUE` preference/service restoration passed;
source was unchanged. Nonprivileged native snapshots now provide actual host
CPU ticks: user/system/idle deltas **30,210/23,943/218** (nice zero), or
**99.599% aggregate busy** over the enclosing observation interval on four
logical CPUs and 15,032,385,536 bytes RAM. One-minute load rose **8.210 →
283.241** and the process census 548 → 686. There was no compression/swap/pageout
growth. The final snapshot includes six running `mdworker_shared` threads,
SpringBoard, backboardd and launchd_sim. These role aggregates **do not measure
per-process CPU deltas or prove the cause of the saturation**; blaming Spotlight,
the provider, or the observer conclusively would exceed the evidence.

Evidence under the task-private root:

- `actions-36823874982/`: ARM artifact **11144805400** SHA-256
  `4f97a45ef392b1ab8c6b3efefff6ffc01d58c15cb8140e51be515f18eb2b4399`;
  Intel artifact **11144885520** SHA-256
  `9fbe08616d87592931c33d31fb7a1fabb0c3c163df8ac4c67655136e4e06ef5c`.
  Complete 34-entry log archive SHA-256
  `a7b739fa66f35c3c268562cdaf3c6d963d6ce0d7cb648bb76deb54d629484dc7`;
  independent review SHA-256
  `63a6d2af89207aed68a1afd285fa8b4494c5c06db2af4a9ba09a1346833085fb`.
- `actions-36823649364/`: artifact **11144254014** SHA-256
  `6cb7227a8547f37df0c3df9d0fc86cbd312ff65bb0568d2085296f3f8d78a27d`;
  complete 17-entry logs SHA-256
  `27f105f8b1ebc3408e60bc6202981670b854d44bdabb5bab57069f3148bf6e3c`;
  independent review SHA-256
  `303871cef6beba798a6a789b7117bd82666ee67b75a8f3ba2ee6df6e7eab34ae`.

## October 1 capacity follow-through: rotating telemetry lifetime race

[36821968961](https://github.com/p2pKit/P2pKit/actions/runs/36821968961), source
`1b50f655eec687e757ecbfdfe45024413b4c438b`, passed **1,178 JVM tests** (core
858, RPC 46, LAN 235, sample 39), including both new real-socket accept
regressions. All six real-socket correctness cases and their 65.242-second
retention passed. Separately **20/20 one-MiB requests/replies**, concurrency two,
passed in **4.162566239 seconds**, 4.804728345849633 responses/s, client-call
p50/p95/p99 **309/888/954 ms**, zero RPC errors and 65.244-second retention.
Both short workloads have all three native receipts and identity cleanup.
The independent clock preflight and all seven outer command finalizations
passed. This older source required 121 native controls, not the newer 124.

The full steady rerun **failed before completion**. Its exact first source-bound
failure is `scripts/run-rpc-capacity-lab.py:58`, **`Control file lifetime changed`**.
The steady `measurement` is **null**: there is no admitted duration, response
count, latency distribution or zero-RPC-error claim for this attempt. The
coordinator's `finally` then cancelled its two retained pidfd-bound workers;
both products exited -15/final 125 with `Invocation cancellation requested`.
The workers were reaped with zero coordinator cleanup errors, but their native
execution finalizations remain unadmitted. Do not mistake the outer
`OWNERSHIP_UNPROVEN` category for the initial cause or a completed load result.

### Verified mechanism and narrow correction

The real host publishes `host-telemetry.txt` every second in
`samples/p2p-sample-rpc/src/jvmLab/kotlin/dev/p2pkit/sample/rpc/lab/LabHost.kt`.
`LabFiles.write(..., replace = true)` atomically publishes a fully written,
private inode with `ATOMIC_MOVE`/`REPLACE_EXISTING`. The Python coordinator
copies the rotating publication every 250 ms using the same strict reader as
immutable pins/configuration. A legitimate rename **between lstat and open**
makes the two observations refer to different lifetimes, correctly failing that
single observation. Applying an immutable-publication assumption to rotating
telemetry incorrectly made that race fatal to the experiment.

A deterministic offline reproduction uses real 0600 files and `os.replace`
at precisely that boundary; the old reader fails with the observed literal.
The fix is confined to test coordination:

- `read_private` remains strict and non-retrying. Its opened descriptor now
  independently rechecks owner/mode/type; `O_NOFOLLOW | O_NONBLOCK` rejects
  symlink/FIFO substitution without hanging, and metadata must remain unchanged
  across the bounded read.
- New `read_telemetry` permits **at most three complete observations**, only
  for the exact `host-telemetry.txt` name and only after the typed
  `ControlFileLifetimeChanged`. Rejected descriptors are closed without
  consuming their bytes. Permission, owner, symlink, FIFO, in-place mutation,
  byte-limit and unsafe-directory failures are never retried.
- Only telemetry copying/retention use that reader. Immutable pins, readiness,
  configuration and receipts retain their original immediate failure. The
  existing freshness/sequence checks, five-second observation bound, RPC
  policies and all workload/deadline/resource gates are unchanged.
- The public failure locator recognizes the new literal typed raise while
  still rejecting private suffixes; exhausted observations remain an exact,
  source-bound failure rather than a warning.

Removing inode checks globally would weaken security; in-place writes would
introduce torn reads; slower sampling merely hides the race. Cross-language
locking or a replacement telemetry transport is unnecessary. Bounded full
reobservation accepts only a new, completely verified private snapshot and
does not change production security, ownership or RPC behavior.

The **397-test / 15-suite offline run passed**, including deterministic race,
descriptor-retirement, immutable-control rejection, three-attempt exhaustion,
malicious-replacement and coordinator-selection controls. Repository layout,
OSV coverage, **625** Markdown links, release metadata and whitespace passed;
protected instructions remain byte-identical. These are offline controls, not
the required native workload. No local Java/Gradle/application execution or
dependency download was started. The next feature-only dispatch must rerun the
current original Intel LAN profile and the **entire** full-rate capacity suite,
including 124 current Linux native controls and healthy-generator/resource review.

Evidence in `actions-36821968961/`: artifact **11144178469** SHA-256
`5ff250e13a32ad166853237a41ca56425686a654c0ddd36119f5926c9f146e9c`;
all 17 complete workflow logs SHA-256
`155f1acbfe577bf7c3f50ee5e6c7150b143d6e483e50ab94e0a1697b3af8e894`;
independent review SHA-256
`89fac11719a7b85719d47611976a2c553169e71769bf6c0b124c40e89962b9d1`.
Offline reproduction `telemetry-publication-race-before.log` SHA-256
`df123383f496e694f31ad4dff00fb729e0239dc5d35bd2fb55f250c08f0ebfab`;
complete offline log `telemetry-race-offline.dyWzTArr.log` SHA-256
`db7e1905cd063022fd5491954310ed85243c4b638992b77ecd390fb4c45a13cb`.
The earlier full same-host pass at `911e5edf` remains valid for that source;
this aborted rerun cannot qualify newer source. All release HOLDs and
Foundation **NOT_READY** remain unchanged.

## October 1 current-harness Intel original profile passed

[36825774694](https://github.com/p2pKit/P2pKit/actions/runs/36825774694), source
`ae9ab3d11bcd1f57c4c49f6130ba96a0d8fba463` / tree
`1b86cecd63324212b8859a88b5c8b9b510faaef5`, completed successfully in
**18m21s** on native Intel, macOS **15.7.9**, runner image **20260824.0482.1**,
required Xcode **26.3**, and iOS **26.2 x86_64** standalone simulator.

- All **125 required native controls** passed. All **26 command finalizations**
  have zero errors, discovery errors, pending lifetimes and owned survivors.
- Original JVM multicast readiness and natural disposal passed.
- The **entire original `ios-lan-x64` profile** executed
  `:p2p-transport-lan:iosX64Test`: **202 passed, zero failed/errors**, and the
  **same one pre-existing ignored capture-only diagnostic**, across 33 XML
  suites. No new skip/quarantine was introduced. All eight Native diagnostic
  regression methods also passed within that inventory.
- Exact simulator retirement/deletion, original Terminal ordinary Quit,
  child reap, command removal, and complete Bonjour preference/file/service
  restoration all passed. Source remained unchanged.

Independent Git comparison against the original failed `63530bb8` checkpoint
again finds **no change** in Apple LAN production code, Apple LAN tests or
`scripts/run-platform-tests.py`. The original nine failing methods named
[above](#october-1-original-nine-kotlin-discovery-failures-recovered-without-source-changes)
are therefore recovered on the current harness without altering those methods,
timeouts or production policy. This is the third complete zero-failure original
profile execution, not a partial run, count substitution, or mocked discovery.

The fix remains the explicitly authorized, reversible **hosted test-environment
preparation**: nonroot Terminal CLI context and restoration-safe removal of
`NoMulticastAdvertisements=TRUE` using the actual registered mDNS service.
This pass does not resolve the separate full-GUI 120-second readiness failure,
prove every Terminal lifecycle under that failed GUI workload, qualify physical
LAN/mobile capacity, or complete the full Apple matrix. The current full-rate
capacity rerun is independently in progress; no result is inferred from it.

Evidence in `actions-36825774694/`: artifact **11145911691** SHA-256
`313f82caf1d7be2bb51dac4da4923b1372bc4c1fb56f79d852d35436292ad5ee`;
all **17** complete workflow-log entries SHA-256
`c9f21c84b65f330f9601266aa1918d82a40064b32ed5e3a0b5eaf79d4ce16df3`;
independent source/inventory/cleanup review SHA-256
`9cc53c5eed7e00335115d646a8d18a593823b2b0bbf7aba6c2ad0788f942836c`.
The complete current-source offline rerun also passed **397 tests / 15 suites**,
layout, OSV coverage, **626** Markdown links and release metadata. Its log is
`current-source-offline.1qAuPB3b.log`, SHA-256
`381bc5c065ae20eb6ab16f43a40e1926631581c2700b457ecda072f5073abfa3`.
All wider release HOLDs and Foundation **NOT_READY** remain unchanged.

## October 1 complete rerun: generator JVM safepoint suspension, not lost RPCs

[36825774682](https://github.com/p2pKit/P2pKit/actions/runs/36825774682), source
`ae9ab3d11bcd1f57c4c49f6130ba96a0d8fba463`, finished the entire measured
**1,800.000240424 seconds**, but **failed** the unchanged zero-miss requirement.
The telemetry publication race did not recur. All **124 current Linux native
controls**, **1,178 JVM tests**, seven outer finalizations and all three native
finalizations for each socket workload passed. The steady client correctly
returned product exit one for failed capacity acceptance; cleanup remains
independently verified, not suppressed.

| Measurement | Actual result, not a capacity pass |
|---|---:|
| Required calls | 2,304,000 |
| Dispatched / completed / host accepted / host completed | 2,291,827 each |
| Missed dispatch slots | **12,173** |
| Timer-late / worker-late / permit-refused slots | **11,605 / 568 / 0** |
| RPC errors / timeouts / connection changes | **0 / 0 / 0** |
| Responses per scheduling second | 1,273.237052157364 |
| Client-call p50 / p95 / p99 / max | 2 / 12 / 70 / 803 ms |
| Scheduling p50 / p95 / p99 / max | 1 / 2 / 43 / 754 ms |
| Host / generator observed CPU | 2,564.14 / 3,134.06 CPU-seconds |
| Whole-series host peak RSS / native threads | 958,599,168 bytes / 176 |
| Sampled queue / outstanding maximum | 0 / 146 |
| Idle retention, all connections/work/records/payload cleared | 65.138 s, PASS |

All 1,800 bins reconcile: every missing slot was refused **before RPC
invocation**, either at the 100-ms timer-lateness boundary or the unchanged
worker-entry boundary. There were 111 affected scheduled seconds, from second
86 through 1,795. Zero RPC errors are consistent with this mechanism: no
operation existed for those slots, and every operation actually dispatched
completed. No retry or host-admission change can recover a never-issued call
without changing the benchmark's schedule semantics.

Unlike the historical VPS balloon-pressure failure, this runner had **zero
observed balloon/reclaim/allocation-stall/major-fault/steal growth** and
13,776,196–14,406,296 KiB available memory. Its separate preflight read all
12,500 clock expirations with zero coalescing. During actual load, however,
the JVM recorded **97 safepoints of at least 100 ms**. Maximum time **already
stopped at the safepoint** was **753.409935 ms**, versus maximum time reaching
a safepoint of only 2.134973 ms. The independent in-JVM clock observer recorded
753.006069-ms lag and the send timer 753.734118-ms lateness. In the worst
scheduled bin, 555 slots were never invoked. This establishes an actual
JVM-wide application-thread suspension, not merely a slow RPC callback.

**12,172 of the 12,173** misses occur in one-second bins overlapping the long
safepoints. One remains outside those bins; the correlation is not a
per-request trace and must not be reported as 100% attribution. The previous
sanitized export retained totals but not the operation name or GC CPU rows.
It therefore cannot establish whether the long stopped phase came from GC,
another diagnostic VM operation, logging, or underlying scheduling costs. Raw
private runtime logs were intentionally not published and cannot be
reconstructed from their hashes. Calling this definitively a particular GC
defect or provider defect would exceed the preserved evidence.

The follow-up changes **only offline evidence analysis**: closed safepoint
operation categories, complete per-category count/time totals, a bounded
longest-16 event subset, and JVM's explicitly rounded GC CPU counters.
Unknown operation names become `OTHER`, never arbitrary public strings;
unavailable counters remain explicitly unrecorded. Duplicate/inconsistent
timings are rejected. No product code, JVM heap/collector/priority flag,
100-ms boundary, permit count, 30-minute duration or qualification predicate
changes. Deterministic privacy/accounting tests cover these additions before
the next complete run. The objective is to identify the suspension rather
than make the acceptance number pass by suppressing misses.

The separate **20/20 one-MiB requests/replies**, concurrency two, passed in
**2.594871186 seconds**, p50/p95/p99 **193/596/649 ms**, zero errors and
65.737-second retention. All six real-socket correctness cases and their
65.855-second retention passed. Neither these nor the earlier full pass at
`911e5edf` turns this failed current-source attempt into qualification.

Evidence in `actions-36825774682/`: artifact **11147306415** SHA-256
`a32c6ca471b8e058dfc33e7debbebf7c3ded4a8ca8b4394021d19ff5aaebae6c`;
all 17 complete workflow logs SHA-256
`9cf9cff8a77399d411a2abafd46e2385b460118abc7f4d740bb459d21a19882f`;
independent review SHA-256
`558969f37832aa7f3683feef0d5a321b85b55848a29e139790f77ed6978f4446`.
Current full-rate qualification remains open. The recovered Intel discovery
inventory is unaffected; full Apple/physical/mobile HOLDs and Foundation
**NOT_READY** remain unchanged.

Before the diagnostic follow-through, **403 tests across 15 offline suites**
passed, plus layout, OSV coverage, **627** Markdown links, release metadata and
whitespace checks. The six additional parser controls distinguish GC versus
other VM operations, preserve unknown-operation counts without disclosing their
names, bound the ranked event subset, retain explicit missing GC observations,
and reject duplicate/inconsistent counters. Log
`safepoint-details-offline.6DXPptdf.log`, SHA-256
`c258f324b4a520495506df0f259f4b9f9f8d2e9ae1c85bf701b3b5caab39d723`.
No local Java/Gradle/application execution or SDK/dependency download was used.

## October 1 full follow-up: sustained permit saturation, not generator safepoints

[36831891298](https://github.com/p2pKit/P2pKit/actions/runs/36831891298), source
`a25951eeaa2fb4142db3b9d14db903bef16a39e1`, completed the full scheduling
interval but **failed** the unchanged capacity contract. This failure must not
be assigned the previous run's safepoint diagnosis: there were **zero generator
safepoints of at least 100 ms** in this execution.

| Measurement | Actual result, not a capacity pass |
|---|---:|
| Actual scheduling duration | 1,800.000744050 s |
| Required calls | 2,304,000 |
| Dispatched / completed / host accepted / host completed | 1,740,951 each |
| Missed slots | **563,049** |
| Timer-late / permit-unavailable / worker-late | **0 / 562,825 / 224** |
| RPC errors / timeouts / connection changes | **0 / 0 / 0** |
| Responses per scheduling second | 967.1946001993654 |
| Client-call p50 / p95 / p99 / max | 802 / 1,314 / 1,568 / 3,139 ms |
| Scheduling p50 / p95 / p99 / max | 2 / 36 / 60 / 150 ms |
| Host / generator process CPU | 3,088.73 / 3,720.63 CPU-seconds |
| Whole-series host peak RSS / native threads | 1,185,931,264 bytes / 180 |
| Driver-sampled host queue / outstanding maximum | 0 / 1,009 |
| Drain, then actual idle retention | 426.006142 ms, then 65.158 s |

### What the evidence establishes

All 1,800 scheduled-second bins reconcile. **562,825** slots were refused by
`permits[index].tryAcquire()` in `RpcCapacityMain.kt`, before creating a call;
**224** more reached their worker at or after the original 100-ms boundary
and were not invoked. There are no unaccounted dispatched operations: client
completion and host admission/completion all agree. Zero RPC errors are
consistent with these never-invoked slots; they do not turn the missing load
into a pass. The eight-per-client permit limit must not be raised to conceal it.

Permit pressure persists throughout the run, not just at cold startup. The
six successive five-minute windows completed **291,162 / 287,389 / 288,597 /
292,787 / 289,847 / 291,169** calls, versus 384,000 required in each window.
Initialization separately completed all 76,800 calls in **89.588997882 s**,
with p50/p95/p99 **114/259/401 ms**. In the earlier passing run it took
65.982 s with **6/114/231 ms**. The current driver and host share four CPUs;
their measured process CPU totals consume about **3.783 CPU-seconds per
scheduling second**. That is evidence of little shared CPU headroom, but not
proof of the precise hot path or provider scheduling cause. A Java thread in
`RUNNABLE` may be blocked in native socket I/O and is not proof of CPU activity.

The new diagnostic export records 851 generator safepoints, maximum
**51.119216 ms**, with **750** `G1CollectForAllocation` events. Rounded GC CPU
observations total **18.25 user / 0.63 system / 13.58 real seconds**. All missed
slots are outside the long-safepoint/reclaim bins; balloon/reclaim/allocation
stall/major-fault/steal growth remained zero. The apparent **985.983336-ms**
maximum clock lag occurs at elapsed **1,800.986124521 s**, **after scheduling
has ended**; it is not an in-window clock stall. Actual timer-late slots are zero.

The slower call residence is therefore real, but existing evidence cannot yet
attribute it among client processing, host processing, transport scheduling,
or shared-runner CPU cost. Host queue zero measures the RPC handler queue, not
every transport/coroutine queue. No unnecessary production/GC/permit change is
justified by these totals alone. Completed-call latency describes the reduced
admitted load, not proven latency at 1,280 offered calls/s.

### Independent tests and cleanup

All **124 native controls**, **1,178 JVM tests**, seven outer finalizations,
and three inner finalizations for each real-socket workload passed. The client
properly returned exit one for steady acceptance failure. Retention cleared
all connections, running/queued work, records and payload; native thread count
fell to 28. The six correctness cases passed with **65.271 s** retention.
The separate large test completed **20/20** one-MiB requests/replies at
concurrency two in **3.923012102 s**, p50/p95/p99 **298/817/922 ms**, zero errors,
and **65.219 s** retention. These do not substitute for full-rate acceptance.

Evidence in `actions-36831891298/`: artifact **11149352491** SHA-256
`98391d0e595749f93fd241d7f020bd5f682127a180abbe47fadeb2639e67d6fb`;
all 17 complete workflow-log entries SHA-256
`083f1a8e90a0a3d230bacb2a9d1a3fdd67a1e2f4307d65661c772b12761f7605`;
independent review SHA-256
`df1b08f6ddc0b260d9ca5d81074a64048d63de9e32009924e734d53d19e7ad40`.

### Bounded attribution follow-through, not a speculative product fix

The next candidate adds **test-only JDK Flight Recorder CPU/wait sampling**
in both already-owned JVMs: a 120-second startup delay followed by a fixed
180-second observation inside the **unchanged full 1,800-second workload**.
It is not a shortened capacity mode. Only execution/native-method samples,
one-second normalized CPU-load observations and 20-ms-or-longer parks/monitor
waits are enabled; no payload, exception,
allocation, network-address or environment events are requested. Raw JFR stays
private, with a 32-MiB recording cap and a 64-MiB bounded post-exit reader.
Only closed subsystem categories and numeric counts/durations are exported.
Native samples and wait durations are explicitly **not CPU percentages**.
JFR's CPU-load observations are separately reported in integer parts per million,
not inferred from sampled stacks. Both the live recording repository and final
recording are placed inside the existing private lab directory.

`LabJfrProfile.kt` parses after each measured JVM exits; its child remains in
the same native-owned invocation, without attach, raw-PID signalling or relaxed
cleanup. `runtime_profile` independently validates source, role, input hash,
closed fields, bounds and count conservation. Both host and generator's
existing GC/safepoint logs are now summarized, using each JVM's own epoch.
Unknown VM operation names remain `OTHER`. No raw profile/log is uploaded.

The first actual execution must validate this new diagnostic path; offline
controls are not a claimed JFR or capacity pass. There is **no production code,
heap/collector/priority, retry policy, permit, deadline, assertion or acceptance
threshold change**. All prior failures remain preserved. The current Intel
original discovery profile remains verified separately; full Apple/physical/
mobile gates and Release Foundation **NOT_READY** remain unchanged.

Before this diagnostic dispatch, **410 tests across 15 offline suites** passed;
the final CPU-load/private-repository additions were rechecked with all **79
tests in the four affected suites**. Layout, OSV inventory, **628** Markdown
links, release metadata and whitespace checks passed. The full offline log is
`runtime-profile-final-offline.JhQ5j653.log`, SHA-256
`3293d32f074edac2cd9404174d7f94a70cd03052bdd6303c463f1a58a200c628`;
the final targeted/repository log is `runtime-profile-cpu-offline.JGjEUj0u.log`,
SHA-256 `6a3851914bf3c231d2ec654b480d0c9c03eb4ac9cee55b926728d6b6df7abdf4`.
The three new Kotlin classifier controls and actual JFR parsing still require
hosted JVM execution. No local Java/Gradle/application execution or dependency
download was used for this diagnostic change.

## October 1 instrumented full run: CPU pressure and fresh-snapshot candidate

[Run 36839868389](https://github.com/p2pKit/P2pKit/actions/runs/36839868389),
source `1b3c41694abd09c3fd43935692805e82dc177a5b`, completed **FAIL** after
the entire **1,800.000900606-second** scheduling window. Its new bounded JFR
diagnostic compiled and ran on both real JVMs; this is no longer an unexecuted
profiler proposal. The source-bound, publisher-hash-verified artifact and complete
17-entry workflow log ZIP are preserved, including the failed client exit.

| Measurement | Actual result |
|---|---:|
| Expected steady calls | 2,304,000 |
| Dispatched / client completed / host accepted / host completed | 2,233,926 each |
| Missed starts | 70,074 |
| Per-client permit unavailable / timer late / worker late | 68,747 / 855 / 472 |
| Successful responses/s | 1,241.069379 |
| Client-call p50 / p95 / p99 / maximum | 471 / 829 / 1,001 / 1,857 ms |
| Scheduling-delay p50 / p95 / p99 / maximum | 2 / 30 / 44 / 214 ms |
| RPC failures / deadline errors / connection changes | 0 / 0 / 0 |
| Host / generator process CPU | 3,073.22 / 3,719.96 CPU-seconds |
| Sampled maximum outstanding / handler queue | 906 / 0 |
| Whole-series peak host RSS / native threads | 1,148,866,560 bytes / 185 |
| Idle retention actually observed | 65.150 seconds |

Every missed slot is accounted **before RPC invocation**. All invoked calls
completed; zero RPC failures is therefore consistent with the missed-start
failure, not evidence that unsent calls were delivered. The per-client eight-call
permit remains unchanged. Queue zero describes the **handler queue**, not every
coroutine, transport or executor queue. The driver has no independent retry
counter; its policy remains `RecoverOnly`. No numerical latency cutoff was
approved; the reported percentiles cannot replace the full-rate acceptance.
The separate fixed initialization completed **76,800 calls in 70.044728785 s**;
none counts toward steady-state success.

Both profiles observed 179 CPU-load samples during the fixed three-minute
window, starting 120 seconds after launch. Percentages below are normalized to
**all four shared CPUs**, not to one core:

| JVM | Mean user CPU | Mean system CPU | Mean whole-machine CPU |
|---|---:|---:|---:|
| Generator | 19.0974% | 31.7189% | 97.6878% |
| Host | 15.9294% | 27.3430% | 97.6841% |

Full-workload combined process CPU averaged **3.774 cores**. Java execution
samples include crypto, coroutine scheduling, LAN path validation and RPC;
native samples include LAN interface enumeration and mostly parked socket reads.
**Native samples and parked durations are not CPU utilization or proof that
socket reads dominate CPU.** The summaries do not establish the exact kernel
cost distribution. Generator/host had 13/9 safepoints of at least 100 ms, all
`G1CollectForAllocation`; maximum durations were 208.842/170.140 ms. Only
2,097 missed slots fall in bins overlapping those long generator safepoints;
67,977 lie outside. This is bin correlation, not per-slot causality. Unlike the
original VPS run, no balloon, direct reclaim, allocstall, major-fault or CPU-steal
growth was observed. Reusing the old balloon/safepoint explanation is unjustified.

All **124 native ownership controls**, **1,181 JVM tests** (858 core, 235 LAN,
46 RPC, 42 sample, including the three new JFR classifier cases), all seven
outer finalizations, and all nine inner workload proofs passed. The failed
steady client still had a verified exit-1 finalization, not a suppressed failure.
All six real-socket correctness cases passed. The separate one-MiB-each-way
workload passed **20/20 calls at concurrency two**, **3.074694 s**, p50/p95/p99
**217/578/656 ms**, zero RPC failures, and **65.743 s** verified idle retention.
After each workload, connections/running/queued/records/payload returned to zero;
steady native/JVM threads fell to 32/14, including the extra profiler threads.
RSS rose during early heap commitment and then plateaued near 1.14 GB; retained
record and payload counts remained bounded. That does not rescue failed rate
acceptance or prove a long-term memory ceiling.

### Small, security-preserving candidate

Source inspection found that **each** strict JVM socket path check performs
`NetworkInterface.getNetworkInterfaces()` and then `getByInetAddress(remote)`.
The latter performs another complete native enumeration in inspected OpenJDK
17u source. Both also run on every existing pre/post-I/O check and the 250-ms
connection watcher. Removing duplicated work within one check is justified for
investigation under CPU pressure, but is **not yet proved to fix the workload**.

[`JvmOrganizationLan.kt`](../../library/p2p-transport-lan/src/jvmMain/kotlin/dev/p2pkit/transport/lan/JvmOrganizationLan.kt)
now derives interface eligibility and self/hairpin-address rejection from **one
fresh full OS enumeration per validation**. It does not retain snapshots across
calls or connections, reduce checking frequency, omit any existing interface
flag read, or exempt tunnels/multihoming. The complete local-address inventory
includes down/loopback interfaces and subinterfaces, not just selected bind
candidates or prefix bindings. The public Java address-enumeration contract
permits filtering under a `SecurityManager`, so the optimization is **not used
when one is observed before or after collection**: the original native
`getByInetAddress` locality check remains the fallback. Unreadable snapshots,
flags and failed fallback lookups still deny the path. These observations remain
subject to the same non-atomic OS-topology boundary as the original Java checks;
this is not kernel route attestation or proof of upstream network transit.

The new internal-only
[`JvmLanSocketAdmissionTest`](../../library/p2p-transport-lan/src/jvmTest/kotlin/dev/p2pkit/transport/lan/JvmLanSocketAdmissionTest.kt)
covers fresh observations, disappearance/multihoming, all four active `utun`s,
selected/secondary/down/loopback/alias self-addresses, IPv6 numeric identity,
filtered-address fallback, unreadable flags/lookup failures, prohibited endpoints
and predicate equivalence over 320 fixed topology/address/visibility cases.
The original four organization-selection regressions remain unchanged. These
Kotlin tests have **not yet executed** at this candidate checkpoint.

Alternatives not selected: caching/TTL or fewer path checks (stale admission),
ignoring interfaces (unverifiable routes), raising outstanding-call/CPU-priority
limits (changes the workload or runtime contract), weakening locality/authentication,
or rerunning unchanged code until a lucky pass. Ordinary P2P defaults, Apple and
Android adapters, scheduling/initialization, retry policies, JFR settings and
acceptance remain unchanged. The next full run must establish whether this
candidate actually reduces CPU cost and missed starts; retained failures and
the earlier `911e5edf` pass remain independently source-bound.

Evidence under `.git/rpc-bonjour-qualification-20260930.oOYgSoqr/actions-36839868389/`:

- Artifact `11151994839`, SHA-256
  `2f96db78a3cc49ccdfc1c05c67fc93ac6ee9ea73f62edba773d19b3ce163ce1e`.
- Complete workflow logs, SHA-256
  `b16781c110fe349c4ade63dbdcf5a2b098bd906be35303b1a684229b73cc0a5d`.
- Independent count/timing/resource/profile/cleanup review, SHA-256
  `a5d7e744907000962bbee8f077ca554c2996f3e81e697164323b3cfd1fe8acdc`.

The inspected public OpenJDK 17u revision is
`3b0480102f8595deb241a666498f77644d5ec376`; its Unix `NetworkInterface.c`
`getAll` and `getByInetAddress0` both call `enumInterfaces`, and alias addresses
are copied to the parent inventory. This is implementation support, not a claim
that those source bytes were independently matched to the running Temurin build.
The compatibility fallback follows the public Java API contract. No raw JFR,
keys, private addresses, payloads or device identifiers are committed/uploaded.
All release HOLDs and Foundation **NOT_READY** remain unchanged.

Before dispatching the snapshot candidate, **410 tests across 15 offline
suites** passed (326 qualification/context/evidence controls plus 84 native
policy/observation fixtures). Repository layout, RPC inventory/negative controls,
OSV lock coverage, **631** Markdown links, release metadata, Kotlin line-width
inspection and `git diff --check` passed. These are not Kotlin compilation or
native runtime admission. Logs `lan-snapshot-offline.50VkMdwf.log` and
`lan-snapshot-owned-offline.mc3ePrFO.log` are retained in the same evidence root,
SHA-256 `33a8b46c487230dd5c96670cd83c0c35bc23793be6fb54add4cc222cd10b2aac`
and `ebf5e7d9e2387e3bb7d9e26d3ef060b2f2688fef25ab3697a116349c6df35d3b`.
No local Java/Gradle/application execution or dependency download was used for
this candidate; the owned hosted JVM regression precedes its full workload.

## October 1 native ARM environment follow-through

The earlier actual ARM/macOS 26/Xcode 26.5
[run at `c22aeebb`](https://github.com/p2pKit/P2pKit/actions/runs/36663774955)
passed scoped Native, ABI/Swift, owned lifecycle/cancellation and finalization,
but its JVM multicast prerequisite failed with `NoRouteToHostException`, so the
required **full** platform profile did not run. This is not an ARM ownership
registration defect. The subsequent Intel experiments established two separate
disposable-runner prerequisites: an ordinary nonroot Terminal context allowed by
the OS and removal of the image's explicit Bonjour advertising suppression,
followed by exact restoration. They did not establish an ARM multicast pass.

The smallest next experiment applies those same bounded prerequisites to the
**original full native ARM inventory**. It neither replaces that inventory with
the Intel diagnostic nor counts OS probes as product tests:

- [`rpc_apple_runner_context.py`](../../scripts/rpc_apple_runner_context.py)
  binds explicit `RPC_APPLE_LANE` to both the actual process architecture and the
  existing native `host_role()` check. Translation, absent/mismatched lanes and
  cross-architecture proof reuse are rejected.
- [`with-darwin-terminal-context.py`](../../scripts/with-darwin-terminal-context.py)
  forwards only the exact selected native command through the unchanged audit
  bootstrap. Its native helper compiles for the selected architecture. ARM may
  request only complete qualification, never an Intel diagnostic mode. Proof
  schema 3 carries `nativeLane`; collector and public-summary checks require the
  exact lane as well as source, successful child exit and complete app retirement.
- [`rpc_apple_bonjour_environment.py`](../../scripts/rpc_apple_bonjour_environment.py)
  retains the original Boolean-only, exact-installed-service preparation and
  restoration, now with native-lane-bound schema 2. The runner must actually
  expose `NoMulticastAdvertisements=TRUE` and the expected installed service
  before any change. No missing/alternate setting is guessed or overwritten.
  A service refusal or failed restoration still fails the run.
- [`run-rpc-qualification.py`](../../scripts/run-rpc-qualification.py) adds only
  the preparation prerequisite. All four `ARM_PHASES`, full-platform tests,
  architecture/ownership admission, actual adapter cancellation, simulator and
  command cleanup remain required. The
  [feature workflow](../../.github/workflows/rpc-qualification.yml) retains all
  native matrix entries and Xcode pins; admission-only, Android and the untouched
  Intel cold-boot comparison do not opt into preparation.

Alternatives considered: repeat the unprepared ARM failure (no new hypothesis),
use scoped Native or Intel success as the full ARM result (invalid coverage),
disable multicast/ownership admission (unsafe), or use the deleted Mac (not
available and not the required native ARM host). This explicit runner setup is
preferred because it addresses an established environment mechanism while
leaving the security rules, original tests, time bounds and cleanup intact.
No production Apple source, TCC/SIP, routes, authentication or resource limits
changed. If the ARM image does not meet the exact prerequisites, that failure
must be investigated, not waived.

Before native dispatch, **416 tests across 16 offline suites passed**: 332
qualification/context/evidence controls and 84 native policy/observation
fixtures. New coverage rejects lane/proof substitution and confirms actual
orchestration still invokes every original ARM phase; a failed preparation
blocks products but not finalization. These are offline fixtures, **not native
ARM execution**. Repository layout, RPC inventory/negative controls, OSV lock
coverage, 631 Markdown links, metadata and `git diff --check` also passed.

Commands were `python3 -B scripts/tests/{rpc-apple-runner-context,
with-darwin-terminal-context,rpc-apple-bonjour-environment,
run-rpc-qualification}-test.py` individually, followed by the existing
context/network/capacity controls and repository checks. The exact suite list
and results are retained in
`.git/rpc-bonjour-qualification-20260930.oOYgSoqr/apple-native-context-offline.2RS4ngdA.log`,
SHA-256 `7a35ead38c956dbf98199a77a84f23640e1b0c7526e60aadb1151ac888ab093f`.
The complete source-bound native run remains **pending** at this checkpoint.
Full Intel GUI readiness, maintained ART, physical/mobile validation and every
release HOLD remain open; Foundation remains **NOT_READY**.

### Actual first ARM result: preference snapshot prerequisite, not ownership

[Run 36848749768](https://github.com/p2pKit/P2pKit/actions/runs/36848749768),
`fc7e12c1fb7bf8dc4aa5a764aec98b038abf93a9`, ran on actual ARM/macOS **26.6.2**,
Xcode **26.5**, image `macos-26-arm64/20260907.0351.1`. All **125 native controls**
and seven command finalizations passed. The native ARM Terminal helper compiled,
ran the nonroot audit child, verified its ancestry, reaped that child and proved
ordinary Terminal termination and command removal. This is valid native
admission/context evidence, not a product or ARM cleanup-gate pass.

The installed `.reloaded` mDNS service was verified and its nonroot inspection
succeeded. Preparation then failed at **SNAPSHOT / PREREQUISITE**:
`originalRecorded=false`, empty preference observations and
`changeAttempted=false`. There was no preference write/reload and no simulator
creation. Every dependent product phase remained blocked, not skipped or passed.
The existing closed proof cannot distinguish a missing preference file/key,
unexpected plist type, file-policy refusal, or already-disabled suppression.
Those are hypotheses, not an established ARM configuration. A more specific
closed snapshot diagnosis is needed before changing preparation behavior; the
original strict checks remain enforced.

Evidence root:
`.git/rpc-bonjour-qualification-20260930.oOYgSoqr/actions-36848749768/`.
Artifact `11154732480` SHA-256:
`1675bde52f99a47354a3e66cef260052adbdc938c56951c77913643937a41181`;
complete 17-entry workflow-log ZIP SHA-256:
`e1cd53fabed3ae3f14a2b30b29c09b8b709cfbf022157e2bb22d8141e0f223ac`.
Source, artifact publisher digest, seven finalizations and complete context proof
were checked independently. No blocked product result is promoted.

The next diagnostic correction retains the same strict preference reader and
all original admission behavior, but records closed categories for a missing or
unreadable file, file-policy/read race, malformed plist, missing/non-Boolean key,
or already-enabled advertising. Even an already-enabled setting **still refuses
preparation** in this diagnostic version; no no-op path, guessed default or
system change was added to make the run pass. Two new negative controls and all
**133 targeted controls across four suites passed**. Log
`arm-preference-diagnosis-offline.IdRp2VVs.log` has SHA-256
`58ca1062852d193d0a9b7a43c04308f5eb2e7aeec08216136ff0655e383700c5`.
This addresses the lost failure detail before another native attempt; it does
not claim to have resolved the ARM environment prerequisite.

## October 1 Intel post-boot CPU attribution diagnostic

The retained Intel runtime failure established a fresh simulator's original
120-second readiness timeout plus approximately 99.6% whole-host CPU activity.
It did **not** identify which processes consumed that CPU. Before/after process
counts, memory and runnable-thread snapshots cannot establish CPU attribution.
The next narrow runtime experiment adds a **fixed ten-second, read-only
post-attempt interval**, not a retry, warm-up or readiness extension.

[`rpc_intel_process_diagnostics.py`](../../scripts/rpc_intel_process_diagnostics.py)
uses the same nonprivileged libproc/Mach APIs. It differences task user/system
counters only for consistently observed matching process lifetimes, converting
Mach absolute units using the actual reported timebase. Public evidence contains
fixed-role aggregates, matched/unmatched/reset/unreadable counts, census costs
and interval spans; no PIDs, arbitrary executable names, arguments, environments
or task ports. Python/Java/tool roles and one closed `other-readable` category
help distinguish harness activity from OS services without exposing unrelated
names. Changed or unobserved processes are not represented as zero-CPU or
verified exits. Native ownership policy is unchanged.

The additional command runs **after** the unchanged one-shot boot attempt and
inside the existing native executor with a 30-second observation bound. It
cannot turn boot failure into success or resume product tests after unverified
ownership. Exact simulator and Terminal retirement remain required. The CPU
interval measures post-attempt conditions, **not every instant of the failed
boot**; rapidly exited or unreadable processes remain an explicit coverage gap.
There is no permission to kill/disable Spotlight or other unrelated services,
change priority, relax timeouts or blame a provider without evidence.

All **171 targeted offline controls across six suites passed**, including nine
new CPU interval/privacy/timebase/lifetime cases and the exact post-attempt
orchestration assertion. The first local control run caught the expected
inventory change (eight snapshot commands versus nine); the assertion now checks
all nine exact commands and unchanged bounds rather than ignoring the addition.
No actual Intel CPU interval has executed at this checkpoint.

Commands: individual `python3 -B scripts/tests/rpc-intel-process-diagnostics-test.py`,
`rpc-product-diagnostics-test.py`, `run-rpc-qualification-test.py`,
`rpc-apple-runner-context-test.py`, `with-darwin-terminal-context-test.py`, and
`rpc-apple-bonjour-environment-test.py`, followed by `git diff --check`.
Log `intel-cpu-interval-controls.cYU5yPRB.log` in the same evidence root has SHA-256
`69f876b15a12652b1ba0a772420d520e8fc612d673f82f163f6788329c962a5e`.
The earlier local failed-control log is retained as
`intel-cpu-interval-targeted.JpGJUXx0.log`. All release HOLDs remain intact.

## October 1 ARM preference absence: correct the preparation assumption

[Run 36850116367](https://github.com/p2pKit/P2pKit/actions/runs/36850116367),
source `256b0432c5edf74afc8f1934b13fe9bcb83480ea`, identifies the previously
ambiguous prerequisite precisely: **SNAPSHOT / PREFERENCE_MISSING**. On the
native ARM image, `/Library/Preferences/com.apple.mDNSResponder.plist` is absent.
This is not an unregistered application resource, cross-thread cleanup error,
permission denial, or evidence of broken multicast. The Intel repair incorrectly
assumed that every Apple image already had its explicit advertising-suppression
preference. All **125 native controls**, seven command finalizations and complete
Terminal retirement passed. No setting was changed and no product/simulator ran.

The correction in
[`rpc_apple_bonjour_environment.py`](../../scripts/rpc_apple_bonjour_environment.py)
keeps the original `EXPLICIT_TRUE_REPAIR` path and its five commands unchanged.
Only actual native ARM plus the exact missing-file category may select
`ARM_ABSENT_DOMAIN_NO_CHANGE`. It then independently requires ENOENT, rejects
symlinks/read denial, checks a root-owned non-group/world-writable parent and
brackets that parent's identity. It neither writes/deletes a preference nor
reloads a service. Finalization verifies continued absence, the same protected
parent and installed service configuration, a second nonroot service-registration
inspection, and unchanged feature source. Newly appearing files, policy/source
drift or inspection failure remain failures; no cleanup deletes another file.

Schema 3 records the distinct operation and before/after absence digests.
Mutation/restoration flags remain **false** for a no-change observation; it
cannot fabricate a successful repair, run a mutation command, substitute an Intel
restoration proof or replace native Terminal admission. Existing missing-key,
non-Boolean, unreadable and unexpected settings still fail closed. The original
real multicast control, complete ARM platform inventory, lifecycle/cancellation,
architecture and ownership/cleanup requirements are all unchanged. Passing
preparation alone is **not multicast or ARM qualification**.

Alternatives rejected: manufacture the Intel plist on ARM (unnecessary system
mutation and restoration risk), treat every preference error as absence (unsafe),
disable preparation/multicast globally (lost evidence), or use the earlier scoped
ARM/Intel results as full ARM qualification (incorrect coverage). The narrowly
observed no-change path fixes the verified harness assumption without a product
security change. Actual ARM follow-through remains pending at this checkpoint.

**435 offline tests across 16 suites passed**, including absence/denial/symlink,
parent replacement, source/service drift, wrong architecture, forbidden mutation
and public-proof separation regressions. An old local assertion and subsequent
indentation error were corrected; their failed logs remain retained. The broad
suite then passed, but its shell driver named a nonexistent repository-check
script. The actual maintained RPC-policy/layout/OSV/link/metadata/diff checks
were separately run and passed, including **639** Markdown links. None of these
offline fixtures is native runtime evidence; no local build/download was used.

Evidence in `.git/rpc-bonjour-qualification-20260930.oOYgSoqr/`:

- `actions-36850116367/`: artifact `11155311660`, verified SHA-256
  `c3b5489ff6187e3ba3237d0becb06db8b23f732c8327f164100473da8de363f0`;
  complete workflow-log ZIP
  `96d2171c2966b858e89bf3922f953c299714a8db6e72cfda5b8bb46532ae30da`.
- `arm-absent-domain-controls.AcYgBgTr.log`: all 435 controls passed before
  the shell path error, SHA-256
  `7ef0ce43966c51a093e90614e637d6bd7b0a4aa58c86482ce0478be47ffadf90`.
- `arm-absent-domain-repository.ngy4Lro2.log`: corrected repository checks,
  SHA-256 `3446790287ae6f3972ce5f0309b8b8a093a90741548ba78be0e3d566d96f1bac`.

Foundation remains **NOT_READY**. No release, physical-network, mobile-capacity
or other pending gate is promoted by this preparation correction.

## October 1 Intel CPU interval: readiness timeout, not an unresolved exec race

[36849889422](https://github.com/p2pKit/P2pKit/actions/runs/36849889422),
source `a2a30ade341484d6555fb43b2aed73cd2615638b`, passed **125 native controls**,
the real multicast prerequisite and **124 Android-host tests** on native Intel,
macOS 15/Xcode 26.3, image `macos-15/20260824.0482.1`. The only unverified command
was the original `simctl bootstatus <owned-device> -b`: its **120-second** bound
expired in Data Migration. Eight final status observations (110–117 seconds)
were nonterminal status 2. The simulator reporting `Booted` later is not GUI
readiness. It was shut down/deleted, and exact Bonjour restoration and complete
Terminal retirement passed. There were **33/34** admitted command finalizations.

The failed leaf has one actual error, **Product command timed out**, product
exit `-15` and infrastructure exit `125`. Its two transient environment/exec
observations both say **RECOVERED**; pending discoveries, retained discovery
errors and exported owned survivors are all zero. A recovered exec-version
observation is therefore **not** the remaining ownership defect in this run.
The unchanged receipt checker correctly refuses status 125; the coordinator's
generic `OWNERSHIP_UNPROVEN` label must not be mistaken for proof of a leaked
native resource. A new closed `PRODUCT_DEADLINE_EXCEEDED` diagnostic distinguishes
the actual timeout without admitting that leaf or resuming dependent products.

The read-only ten-second post-attempt CPU observation really ran:

- 433 matched readable process lifetimes; 17 newly observed afterward, zero
  counter resets. 256/255 unreadable processes remain a coverage gap.
- Over 10.060 elapsed seconds, whole-host counters advanced **2,473 user + 1,542
  system + zero idle ticks**. The four-CPU host was fully busy in that interval.
- Matched `diagnosticd` used **4.756 CPU-seconds**, `backboardd` 0.892 and
  `launchd_sim` 0.443. `other-readable` accounts for **17.958 CPU-seconds**.
  These measurements are post-attempt, not CPU attribution across the whole boot.
- Source review found a real diagnostic coverage gap: the fixed role classifier
  recognizes `python3` names but not macOS framework executables named `Python`.
  Thus this result cannot exclude the harness from `other-readable`, and does not
  justify blaming or disabling unrelated OS services.

One red-to-green offline regression corrects those fixed Python aliases. Nine
additional fixed Apple boot-service names refine the same read-only categories;
arbitrary process names, arguments, environments and identifiers remain private.
No ownership observer, sampling deadline, simulator choice, resource budget or
product code changed. A narrow native follow-up is required to attribute the
unclassified CPU; this is **not a simulator fix or a qualification pass**.

**125 targeted offline controls passed**: 17 process-diagnostic, 84 qualification
and 24 public-evidence controls. The timeout regression proves that an otherwise
clean recovered-observation record still cannot pass the receipt checker.
Evidence in the existing root:

- `actions-36849889422/`: artifact `11155932768`, verified SHA-256
  `9fd38398805bd9cb8d9dabf8b39bf92abed0a4b0e81f21a75216e77163810688`;
  complete 17-entry workflow-log ZIP
  `46dacf2351a39840271ec7c60314b0d13db569220c03d091bd049fdc09d8742f`.
- `actions-36849889422/independent-review.json`, SHA-256
  `0a91bfe63de4f9f5787caeb0292ec7829693bd2b48e49a55cd8dcc0ab4bdd126`.
- Red fixture `intel-framework-python-red.xkfoCnRu.log`, SHA-256
  `fd6b3b17fa996df922538ff88a692758a405cc859b15fb922afb21147deecd68`.
- Passing `intel-cpu-classification.TYSILv9M.log`, SHA-256
  `c61271183bc2609a9b33f789bccb1cbd9ce54e434abdc91cb94c30e8e35880cf`.

Full Intel GUI/platform qualification remains failed. Foundation stays
**NOT_READY**; no skipped, blocked or timed-out test is promoted.

## October 1 snapshot candidate full run failed; next isolate owned CPU sets

[36846798110](https://github.com/p2pKit/P2pKit/actions/runs/36846798110), source
`56bfa200d351643051555a01211b334e092fb6e5`, actually executed the full unchanged
**1,800.000103939-second** workload. It returned **2,009,648 / 2,304,000** replies,
with **294,352 missed slots** and **1,116.471046642 responses/s**. Client-call
p50/p95/p99/max were **637/1,071/1,291/2,731 ms**; scheduling-delay
p50/p95/p99/max were **2/29/51/122 ms**. This is **FAIL**, not a near-enough pass.

All misses reconcile **before RPC invocation**: **294,238** encountered the
unchanged eight-in-flight-per-client semaphore and **114** workers reached their
slot too late; timer-late was **zero**. Every invoked call completed, matching
host accepted/completed deltas. RPC failures, timeouts and connection changes
were zero, consistent with unsent slots never entering RPC. The immutable
`RecoverOnly` policy remains; the export has no separate observed retry counter.
Misses occurred in all six five-minute windows. Zero sampled *handler queue*
does not establish that coroutine, write or socket work had no backlog.

The host/client consumed **3,085.56 / 3,738.13 CPU-seconds** over the measured
interval, sharing four allowed logical CPUs. JFR's 179-sample CPU window was
approximately **98.8% whole-machine busy**. No observed balloon/reclaim/steal or
major-fault growth explains this run. There were no generator safepoints at least
100 ms; the host had **16**, maximum approximately **152.646 ms**. Those bounded
pauses alone do not explain sustained misses. Native parked samples are not CPU
percentages. This does **not** establish one kernel/crypto/dispatcher hot path as
the sole cause, nor prove that a fresh runner is equivalent hardware to an older
pass. The snapshot optimization passed eleven new equivalence/security cases but
has **not demonstrated a throughput improvement**.

Independent passes: **124 native controls**, **1,192 JVM cases**, all seven outer
finalizations, the six real-socket correctness cases, and **20/20** one-MiB
requests/responses at concurrency two. The latter took **3.901303809 seconds**,
p50/p95/p99 **286/867/920 ms**, zero RPC errors. Full-series peak host RSS was
**1,179,025,408 bytes**, native/JVM threads **183/164**, retained records **68,610**
and payload **33,037,528 bytes**. RSS approached a late plateau; retained work,
connections, records and payload cleared through the original **65.183-second**
idle observation. No forced GC/RSS reset or altered retention was used. These
independent passes cannot compensate for the failed offered-rate requirement.

### Next controlled environment change, not a production capacity fix

The next experiment explicitly restricts each of the two owned JVM launchers
and its future children to **two disjoint logical CPUs**, from complete
OS-reported guest-core/sibling groups within the **same original four-CPU
allocation**. The hypothesis is that shared-pool competition/migration is a
material co-location cost. This hypothesis is not yet a verified cause or fix.
No additional CPU, adaptive tuning, workload downscaling, dispatcher override,
priority change, warm-up extension or relaxed retry/timeout/permit is introduced.

[`rpc_capacity_cpu.py`](../../scripts/rpc_capacity_cpu.py) fails closed on missing,
incomplete, inconsistent or changing guest topology. It calls `sched_setaffinity`
only for PID 0 in the admitted single-threaded, nonroot **launcher**, never for
the native owner, controller, unrelated processes or machine settings. The JVM
inherits that mask normally. The launcher also samples its directly created,
unreaped child's main-thread affinity at most once/second, checks its own final
mask and rechecks topology. These observations do not claim every thread was
sampled, dedicated hypervisor physical cores, or exclusive use by system services.
The per-machine default remains `inherited`; the hosted coordinator explicitly
requests `--cpu-placement split-guest-cores` in all three unchanged workloads.

Collection requires both actual role proofs to name the **same** complete plan,
correct complementary CPU sets and successful observation/finalization. Source,
native ownership, identities, LAN path admission, 128 clients, 10 Hz/client,
1,800 measured seconds, both payload definitions, 8-call permits, initialization,
JFR window and retention are unchanged. No physical LAN or mobile claim follows
from this same-host private-veth/TCP fixture. The approved plan requires latency
distributions but explicitly sets **no numerical latency pass/fail threshold**;
none is invented here.

**117 targeted offline controls across six suites passed**: CPU topology/negative
controls, launcher, same-host fixture, hosted coordinator, evidence and scheduling
analyzer. A separate harmless Python-child control confirmed Linux can read the
owned unreaped child's affinity after EOF; it is not a JVM or capacity test.
Actual full-workload follow-through remains pending. If allocation fails or rate
still misses, retain that failure and its counters rather than retuning the gate.

Evidence in `.git/rpc-bonjour-qualification-20260930.oOYgSoqr/`:

- `actions-36846798110/`: artifact `11155289262`, verified SHA-256
  `038a8a59aae4b7bdb33b3167f57e503007d2611b28aea659842730f56e4337a3`;
  complete logs `59f5c083e6bde1b903ad481b9b75d0170a50e26b07f3a8badab447dc6bf2d7b1`.
- `actions-36846798110/summary.json`, SHA-256
  `1fc58e58173535ec3d5c80585550ba0ddbf10a830f846b6bcd65d249b065cd27`;
  independent review `fd786e8b825c352278ad3cf12fff05a2664730d6840b4891a181ff54939dd17a`.
- `capacity-cpu-controls.iBNbPpkG.log`, SHA-256
  `fd36ae6cebe622b4b86511467bebc0ddf3984a249b614dc15bf2874a73e1284a`.

All historical failed attempts remain failures. Foundation remains **NOT_READY**.
