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
  report conversion discarded the new context messages. A subsequent real run
  also exposed an incorrect exported-symbol assumption in the test-only frame
  reader. The correction is now verified by all **eight actual Intel Native
  helper tests**. The original nine cases still time out at initial Bonjour
  discovery, with advertising/browser/listener-ready flags but no observed
  browse-result callback. This is not a claimed production-networking fix.
- The owner deleted the supplemental Mac before additional remote files could
  be copied. Source and earlier Linux exports survive; original Mac-only XCTest
  bundles and the unsigned iPhone app were **not recovered**.
- The launchd-context endpoint probe reported **Local Network Denied** for the
  host. A subsequent verified Terminal-context run allowed both host/simulator
  raw multicast sends, but **all inline-TXT browsers still lacked callbacks**.
  Successful sends are not multicast-receipt or physical-LAN proof. The next
  narrow SSH comparison verified its native authenticated audit session but
  reproduced denial and missing TXT results. The completed interface-directed
  comparison now observes the host's global **`NoMulticastAdvertisements=TRUE`**:
  explicit selected-interface browsing/resolution has no callbacks even though
  registration succeeds. Actually loaded executable declarations do not repair
  inline-TXT browsing. A reversible, narrowly scoped advertising A/B is prepared
  next; recovery has **not** yet been demonstrated.

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
