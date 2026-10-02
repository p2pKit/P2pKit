# Resume the RPC work on an owner laptop

This is a **workstream transfer, not new qualification or release approval**.
The next session must continue the existing implementation, not redesign it or
repeat completed experiments merely because its working directory changed.
Foundation remains **NOT_READY**. All security, architecture, ownership,
cleanup, readiness, and physical-device HOLDs remain in force.

## October 2 official ARM environment supersession

The owner now accepts **native macOS27 / Xcode27** for the remaining ARM
qualification, starting at `e1ae3f37b27780cc4d9efaa16228fcb75c8e159b`.
**Do not wait for macOS26/Xcode26.5.** Earlier host requirements and supplemental
scopes below are historical; neither old failures nor old receipts are relabeled.
Use the explicit [local ARM27 continuation](local-arm27-qualification.md), not
fabricated GitHub environment variables or an old consumed bootstrap config.
The preserved `$HOME/Projects/P2pKit` checkout remains read-only.

## Exact starting point

- Repository: `https://github.com/p2pKit/P2pKit`.
- Existing working branch: `work/rpc-lan-20260927-054728-8b1b11da`.
- Implementation/report checkpoint before this documentation-only handoff:
  `e18786a057aeb677e2cad353eb43a1499ee62e48`, verified equal to the remote branch.
- Original base and freshly inspected main:
  `3bc76f956f8f47447b51a62474fc878b9c43173c`; main had not advanced.
- Original isolated clone: `/root/projects/p2pkit-feature-prep-20260927-yiDjCB`.
  The laptop must use its **own new directory**, not this Linux path.
- The transfer package records the subsequent documentation commit separately.
  Its source checkpoint is not a claim that older APKs or measurements were
  produced by that documentation commit.
- The old Mac VPS was deleted. Do not reconnect to its addresses, reuse its
  credentials, or assume its tools, files, processes, or authorizations survive.

`AGENTS.md`, `CLAUDE.md`, and the approved [RPC plan](../../RPC_MODULE_PLAN.md)
remain unchanged. Never access `/root/projects/p2pkit/`, the Foundation session,
campaign/Maven branches, custodian keys, or unrelated private evidence.
The other session's branch is `work/release-foundation-20260926-1WzHcOIr`, last
reported at `012dc723f59f40cfc2bcc19459db764ecf4676eb`. These are context, not
instructions to check out or import that work. The historic `org.jmdns` lock
issue and Foundation repair `123074eeacda8c3129fb28a483d488d262877c50` are not a
new RPC regression; inspect current source, never copy unfinished Foundation work.

## October 2 laptop source checkpoint

Restoration is now complete in `$HOME/Projects/P2pKit-RPC-current` on the existing
RPC branch, starting from verified transfer commit
`c0f1c313012a02aad5af34063fc0c5b0cb979970`. Use that checkout; do not clone again
or modify the preserved old project. Source fix
`5abdd7980ee9d0742ace30716fd86129d4903701` rejects phone-tool launches after
setup exhausts the original deadline. Its
[61 passing offline controls](vps-lab-runtime-20260929.md#october-2-laptop-launch-deadline-guard)
do not resolve the earlier native failures.

The inspected laptop is native ARM with macOS27/Xcode27, not the required
macOS26/Xcode26.5 lane. The owner subsequently authorized one bounded local
readiness attempt at `1246c0e3247f7c1fa95c9256b0b10b3ffd5eae55`:
[129 current-host controls passed and cold boot completed in 36.891 seconds](vps-lab-runtime-20260929.md#october-2-authorized-local-readiness-attempt).
The exact fresh simulator was shut down/deleted, but an unsupported local
architecture utility and four unclassified native lifetimes kept the overall
result **FAIL**. Do not replay the probe unchanged or treat simulator deletion
as native finalization. The owner then requested a fix: the
[runtime-bound probe correction and prepared audit-context guard](vps-lab-runtime-20260929.md#october-2-local-probe-repair-and-audit-context-prerequisite)
at `bfc8f5ca48b831580dcc438ff89bf166e86593a6` passed 95 offline controls.

The owner subsequently authorized the process-local administrator bootstrap and
authenticated directly in Terminal. The
[corrected isolated attempt](vps-lab-runtime-20260929.md#october-2-isolated-local-readiness-recovery)
at `57df23248be2c1872e5bbe18a8f44fcf1f32b177` is now independently verified:
**129 native controls passed**, fresh-device cold readiness took **29.291 s**,
the ARM64 runtime probe passed, and exact simulator deletion plus both native
finalizers succeeded with zero unknown lifetimes or owned survivors. This closes
the supplemental local probe failures, not any required Apple/product matrix
cell. Keep the failed earlier attempt unchanged and do not reuse either run's
native state or repeat completed readiness solely because a session changed.

No application build was run. That bootstrap/rerun authorization does not cover
new installations, signing, devices or subsequent product builds; the remaining
gates below still apply. Continue with their specific source/host prerequisites
and obtain the necessary execution authorization, never by accepting unknown
lifetimes or launching the old shared-session probe again.

## Owner: transfer source and evidence separately

### 1. Clone the existing branch into an unused laptop directory

**If the assistant starts in your old pre-VPS P2pKit project:** that directory
is not the current checkpoint. First inspect its path, branch, HEAD and Git
status read-only, then leave it unchanged. Do not run `git pull`, `reset`,
`clean`, `stash`, or `switch` there merely to make it resemble the VPS. Its
uncommitted work, local branches and app data may be important. Create the
separate checkout below and make that the assistant's working folder. Fetching
the already implemented RPC branch is **resuming**, not reimplementing the work.
Do not merge old local changes into the qualified baseline automatically; report
them separately for a later integration decision.

With Git already available, run in your laptop terminal:

```bash
mkdir -p "$HOME/Projects"
git clone --no-tags \
  --branch work/rpc-lan-20260927-054728-8b1b11da \
  https://github.com/p2pKit/P2pKit \
  "$HOME/Projects/P2pKit-RPC"
cd "$HOME/Projects/P2pKit-RPC"
git branch --show-current
git rev-parse HEAD
git status --short --branch
git rev-parse --is-shallow-repository
git for-each-ref --format='%(refname)' refs/tags
```

If that directory already exists, choose a different unused directory; do not
clean, reset, overwrite, or delete it. Expected: the named RPC branch, clean
worktree, `false` for shallow history, and no tags. Compare HEAD with the
transfer manifest/final handoff message. If the remote has advanced, inspect
the extra commits instead of resetting it or mislabeling the checkpoint.
Do not create a replacement feature branch or merge main as part of transfer.
GitHub authentication for subsequent pushes belongs to the owner locally;
do not copy tokens, SSH private keys, signing material, or another agent's state.

### 2. Preserve the evidence package before deleting the Linux workspace

**Git transfers source and committed reports, not the local evidence or APKs.**
Download the separately announced laptop-transfer ZIP from the current Linux
workspace, using its file browser or your existing authenticated file-transfer
connection. Use the path and SHA-256 in the final handoff message, not an old
Mac address. Do not copy the whole `.git`, home directory, SDK caches, or private
audit state. The curated archive contains no credentials or reusable identities.

The prepared transfer location in the current Linux clone is:

```text
/root/projects/p2pkit-feature-prep-20260927-yiDjCB/.git/rpc-bonjour-qualification-20260930.oOYgSoqr/laptop-transfer-20261002.zip
```

Verify its announced SHA-256 with `shasum -a 256`, then unpack into a **new**
directory outside the source checkout. Keep the original ZIP unchanged.
Its `README.txt` and `transfer.json` identify the exact source, approved files,
their hashes, remaining work, and the separate source-specific device bundle.
Run its offline `verify-transfer.py` before using the copied evidence; this
does not build, install, boot, connect to a device, or qualify a platform.

The nested owner bundle is unchanged:

```text
owner-device-handoff-ea566ef4-elw86vae.zip
39,392,185 bytes
SHA256 010b501fd2b7f51df77a3bccc41157a1127e3e99d6da30691c3fa7066b242f69
```

It contains both Android APKs, their matching 24-JAR driver, the older unsigned
iPhone app, original manifests/reviews, and the full JVM capacity summary.
Extract it separately into a new directory and run its own
`python3 -B verify-handoff.py`. `qualificationComplete: false` is intentional.
Actions artifacts have short retention; the preserved archive avoids relying
on those downloads still existing later.

Historical report paths beginning `.git/rpc-bonjour-qualification-20260930.oOYgSoqr/`
refer to the Linux evidence store. The transfer index maps each copied item to
its original path. Do not invent missing raw evidence or recreate private audit
receipts. The curated summaries are portable; native execution state is not.

### 3. Open the cloned folder in the laptop coding assistant

Start its session with this folder as the project and paste the prompt at the
end of this document, supplying the extracted transfer-directory path. A new
session must read these saved instructions; do not assume it automatically
inherits the old conversation or its uncommitted evidence.

## Read order and source map for the next agent

1. Read root `AGENTS.md` and `CLAUDE.md` completely; preserve them unchanged.
2. Read this document, the transfer index, and the approved `RPC_MODULE_PLAN.md`.
3. Read [qualification](qualification.md), [device handoff](device-testing-handoff.md),
   [mobile capacity](mobile-capacity.md), and the **Current October 2 handoff** at
   the start of the [runtime report](vps-lab-runtime-20260929.md).
4. For implementation contracts, read [RPC usage/architecture](README.md),
   [protocol](protocol.md), [reliability](reliability.md), and
   [security/deployment](security-and-deployment.md). The
   [implementation checkpoint](implementation-status.md) maps delivered work.
5. For an open failure, follow its source-specific section in the runtime report
   and [qualification investigation](qualification-investigation-20260930.md).
   Both deliberately retain failed attempts and historical pending text; later
   verified entries supersede status, never erase failed evidence.

Relevant implementation and harness locations:

- `library/p2p-rpc`: optional typed RPC above existing core/authenticated LAN.
- `library/p2p-core` and `library/p2p-transport-lan`: reused secure sessions,
  framing, peer admission, discovery and transports; preserve ordinary P2P defaults.
- `samples/p2p-sample-rpc`: JVM driver, common phone façade and iPhone test app.
- `samples/p2p-sample-android/src/debug/java/dev/p2pkit/sample/android/rpclab`:
  Android RPC lab, debug-only file-metadata helper and mobile control integration.
- `scripts/run-rpc-qualification.py` and `.github/workflows/rpc-qualification.yml`:
  exact Apple/ART inventories and hosted prerequisites.
- `scripts/run-audit-command.py`, `scripts/check-audit-receipt.py`,
  `scripts/with-darwin-audit-session.py`, and `scripts/rpc_apple_runner_context.py`:
  real process ownership, privilege drop, native observation and finalization.
- `scripts/run-rpc-ios-handoff.py`, `scripts/run-rpc-phone-ios-controls.py`,
  `.github/workflows/rpc-ios-handoff.yml`, and
  [iPhone project instructions](../../samples/p2p-sample-rpc/phone-ios/README.md):
  latest app producer, exact XCTest inventory and provenance.
- `scripts/run-rpc-mobile-capacity.py`: Linux x86-64 Android USB/LAN candidate;
  `IosUsb` intentionally refuses unverified execution.
- `scripts/tests/`: offline regressions; native receipts and mocked controls
  must never be confused with runtime or physical-device evidence.

## Completed work: do not repeat unchanged

| Work | Source-bound verified result | Scope limitation |
| --- | --- | --- |
| Full 128-client steady workload | [36890348000](https://github.com/p2pKit/P2pKit/actions/runs/36890348000), source `a658740db81c446d2e217b0b76cd4dc45f7b613f`: 1,800.000772188 s, **2,304,000** considered/enqueued/invoked/completed; all 1,800 bins reconcile to 1,280 replies; zero misses/errors/timeouts; 1,279.999450889 replies/s; client p50/p95/p99 bucket upper bounds **2/4/21 ms**. | Ubuntu-22 same-host, separate JVMs, virtual Ethernet; not radio, physical LAN, mobile hosting, or every provider allocation. No numeric latency SLO was approved. |
| Capacity resources/correctness | Same run: healthy generator, bounded/stabilizing host resources, queue max zero, original idle retention and exact cleanup; **1,198 JVM tests and six real-socket cases**. | Not a blanket latest-source/all-platform pass. |
| Large payload | Same run: **20/20** calls, 1 MiB each way, concurrency two; 2.967773654 s; p50/p95/p99 **214/759/772 ms**. | Separate small workload, not a 30-minute large-payload claim. |
| Original nine Bonjour failures | Repeated original LAN inventory: **202 passed, zero failed, one pre-existing ignored diagnostic**. Provider advertising suppression was causally reproduced and restored under the owned harness. | Do not skip tests, remove the diagnostic, disable privacy, or change a laptop's network settings to manufacture a pass. Latest simulator readiness is a separate failure. |
| Android APK/driver handoff | [36941905738](https://github.com/p2pKit/P2pKit/actions/runs/36941905738), source `ea566ef4c9fa02ee752dc63c1daed3f052bf29d9`: **127 native controls, six finalizations, ten instrumentation controls and nine real shell-file controls**, verified APKs/driver and owned cleanup. | API24 x86_64 default revision 8, emulator 37.2.12 with acceleration off, boot 109.050 s. Supplemental only, not maintained ART or physical USB/LAN. |
| Offline regression checkpoint | **894 controls in 34 suites**, standard layout/inventory/lock/metadata checks, whitespace, unchanged instructions; 713 relative links before this documentation addition. | Historical source-bound checks, not a new laptop runtime pass. |

At the pre-transfer checkpoint, `library/` is byte-identical to the qualified
capacity source. Documentation transfer alone does not require another full
load test. Re-run relevant controls if their inputs change; requalify workload
behavior if relevant production/driver/harness code changes or a new host
configuration is being claimed. Never combine old measurements into a fictional
single-source complete matrix pass.

The earlier 69,538-miss run and later failed generator attempts remain failures
in the reports. They were not RPC response losses: instrumentation distinguishes
pre-invocation timer/worker lateness and permit refusals from actual RPC calls.
The stable Ubuntu-22 run subsequently met the full workload. CPU allocation and
OS/kernel both changed, so neither a unique OS-only cause nor a product fix is
claimed. Do not reopen that completed investigation solely because of transfer.

## Remaining work and what an Apple Silicon laptop can actually close

| Priority | Open gate and exact latest evidence | Next action, without relaxing a gate |
| --- | --- | --- |
| 1 | Native ARM/macOS26/Xcode26.5: [36908958520](https://github.com/p2pKit/P2pKit/actions/runs/36908958520) passed **3,046 product cases**, including 202 LAN, and native ownership controls. Separate cold readiness failed at **120.039 s**, preventing latest actual-adapter cleanup. | Inventory the laptop, establish supported native ARM execution and fresh owned simulator readiness within the original bound, then the complete required actual-adapter lifecycle/cancellation/cleanup gate. Old ARM passes and x86/Rosetta results do not substitute. |
| 2 | New iPhone resource/control app: [36922719322](https://github.com/p2pKit/P2pKit/actions/runs/36922719322) failed cold readiness at **120.291 s** before production. | Run the unchanged ten unit/two UI controls, current-source framework provenance and unsigned device-app producer on suitable native ARM. Export only after complete receipts, source binding and exact cleanup. |
| 3 | Intel/macOS15/Xcode26.3: [36911837915](https://github.com/p2pKit/P2pKit/actions/runs/36911837915), inventory **120.163 s**, before simulator creation. Multicast, 127 host cases and exact Terminal cleanup passed. | Still requires supported **native Intel**, not Apple Silicon/Rosetta. Do not blindly rerun the same overloaded runner or invent provider-internal causality. |
| 4 | Maintained API37/24/25 ART: [36923543329](https://github.com/p2pKit/P2pKit/actions/runs/36923543329) found exposed virtualization but nonroot lacked access to `0660 /dev/kvm`; no emulator ran. | A supported already-authorized environment or separately authorized narrow provisioning. A Mac ARM guest is not automatically the unchanged Linux/x86 gate. No KVM ACL/group change was authorized or made. |
| 5 | iPhone USB coordinator is unimplemented by design. | Real device-backed create-only app-container publication/reading/retirement, source binding and cleanup must be engineered and tested. Signing the older app does not implement this adapter. |
| 6 | Physical Android/iPhone LAN, both host roles, mobile capacity and hostile-network acceptance. | Actual devices, approved organization LAN, local permissions/trust, owner signing where needed, and each phone's own full workload/resource evidence. Follow the device handoff and validation handbook. |

The preserved older iPhone app is from `834c02c9a7819754dcf8a9a2db62306e3cfc9fe8`,
[36869803924](https://github.com/p2pKit/P2pKit/actions/runs/36869803924). It passed
seven unit/two UI controls and is an unsigned arm64/iOS15 `.app`, **not an IPA**;
it lacks newer mobile-resource controls. Preserve its source/hash; do not relabel
it as the current candidate or silently install it as a signed app.

The current Android mobile coordinator needs a stable **Linux x86-64** generator,
physical USB and direct approved LAN. A laptop macOS port is not already
implemented. Its original four-second phone observation budget is unverified:
the supplemental emulator's 10-second reads passed a separate 40-second shell
test, not that physical budget. Start with actual control admission, never a
30-minute workload against an unproven control path.

## First actions on the laptop

1. Inspect branch, HEAD, worktree and remote advancement without discarding local
   work. Verify the transfer files. Do not start broad CI or repeat load tests.
2. Inventory native architecture/Rosetta status, OS, memory, free disk, selected
   Xcode and installed runtimes, JDK17 plus the JDK21 daemon toolchain, Python,
   XcodeGen, Android tools and existing user-owned workloads. Report exact versions.
   Do not launch an unbounded simulator inventory/boot as a harmless shell probe:
   that is itself one of the bounded readiness prerequisites.
3. Determine whether the exact native ARM host contract is satisfied. A different
   OS/Xcode combination can yield supplemental evidence but not silently replace
   required matrix cells. Do not fake architecture or GitHub-runner variables.
4. Inspect the existing native executor and workflow before adapting orchestration
   to the laptop. Allocate **fresh private test state**; never reuse Linux/Mac
   process receipts or invent an ownership chain. Preserve all original native
   controls, deadlines, actual production adapters, source/tool binding and cleanup.
5. Run narrow relevant offline controls before any authorized runtime execution.
   Then run the targeted native prerequisite, followed by required ARM/iPhone
   suites if it succeeds. Retain failed attempts and independently verify exports.
6. Commit/push coherent validated changes only to the existing RPC branch. Record
   exact commands, source, environment, measurements and remaining blockers in
   the runtime/qualification/handoff documents. Leave a clean worktree.

Transferring the work does **not** authorize new laptop installations, local
Java/Gradle/Xcode/application execution, privileged/system/security changes,
signing access or device erasure. The owner must separately authorize the
specific local operations when needed. Prior scoped hosted approvals are not a
blanket license to alter a personal laptop. Continue safe source inspection and
offline checks in the meantime; ask only for genuine missing prerequisites.

Never disable SIP/Gatekeeper/TCC, alter authentication, globally whitelist
interfaces, prewarm to bypass cold readiness, extend deadlines, kill unrelated
services/terminals, or expose RPC publicly. Do not treat VPN/SSH/NAT reachability
as physical LAN. Do not merge main, publish, tag, change repository settings,
cancel another session's CI, or mark Foundation READY.

If PocketTerminal notifications exist in the new session, use its actual local
context. Do not copy an old session ID or credentials; if unavailable, report
normally rather than trying another session.

## Paste this into the new coding session

Replace the transfer-directory placeholder with the actual extracted path:

```text
Continue the existing P2pKit RPC/LAN work; do not start over.
You may initially be opened in my OLD pre-VPS P2pKit project. Inspect its
path/branch/HEAD/status read-only and preserve it. Do not reset, clean, stash,
pull, overwrite, switch its branch or merge its local changes automatically.
Use an unused sibling directory for a full-history, no-tags clone of:
https://github.com/p2pKit/P2pKit
Branch: work/rpc-lan-20260927-054728-8b1b11da
If I already opened the verified new checkout, use it rather than cloning again.
Make the current RPC clone your working folder; the old project is not baseline.
Transfer evidence: <absolute extracted laptop-transfer directory>

Read AGENTS.md and CLAUDE.md completely, then
docs/rpc/laptop-continuation.md and its listed context documents.
Verify the source checkpoint, clean worktree, remote advancement and transferred
evidence before editing. Retain source-specific results and failed attempts.

Do not repeat the already verified 30-minute JVM capacity, large-payload,
Bonjour recovery or Android package runs unless relevant inputs have changed.
First investigate this laptop's actual suitability for the remaining native
ARM/macOS26/Xcode26.5 readiness/actual-adapter cleanup and updated iPhone app.
Keep Intel, maintained ART, physical LAN and each phone's capacity gates separate.
Do not treat an old unsigned iPhone app or simulator test as physical acceptance.

Preserve all ownership/security/readiness/cleanup/architecture gates and
Foundation NOT_READY. Work only in this isolated clone and fresh owned test
state. No Foundation directories, old deleted Mac, unrelated processes,
credentials, signing keys or private evidence. No merge/publish/tags/settings.
Ordinary source work and own-branch commits/pushes remain authorized; this
transfer alone does not authorize previously restricted local builds, software
installs, administrative changes or signing/device access. Inventory first and
identify any specific missing authorization or physical prerequisite.

Continue with meaningful safe work rather than another generic plan. Keep
progress concise and distinguish verified results, attempts and open gates.
Update the reports and preserve a clean, pushed checkpoint when finished.
```
