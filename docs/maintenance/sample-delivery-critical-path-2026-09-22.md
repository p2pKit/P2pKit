# Development sample delivery: critical path — 22 September 2026

The owner paused cancellation-review expansion and prioritized the actual
runner/provider connection and four public development app assets. This is a
source checkpoint, **not workflow activation, a passed build or publication**.
The six pre-existing cancellation WIP files remain unchanged in the integration
worktree. New work is isolated from them and from the older review worktrees.

## Fresh service observations

Read-only GitHub metadata was refreshed at approximately **01:03 UTC**. Main is
still `3bc76f956f8f47447b51a62474fc878b9c43173c`; the source base for this increment
is `af5b64c8823d6a16e4bc44d6f2d0646e48fd89f9`. Complete paginated #437/#424
conversations contain 122/112 comments before this increment's mapping. The
earlier successful builds, recipient key validation/recovery and accepted
fixture repairs were not repeated.

The successful [preview run 35070982169/1](https://github.com/p2pKit/P2pKit/actions/runs/35070982169)
still has all four non-expired artifacts. These are service metadata observations,
not fresh ZIP inspection or anonymous Release downloads:

| Artifact | ID | Service expiry (UTC) |
| --- | --- | --- |
| Android APK bundle | `10435977781` | `2026-09-30T08:00:53Z` |
| Windows MSI bundle | `10435803838` | `2026-09-30T08:06:41Z` |
| macOS ARM64 DMG bundle | `10436538265` | `2026-09-30T08:11:22Z` |
| Linux DEB bundle | `10436202245` | `2026-09-30T08:00:51Z` |

The preview's actual event is `workflow_dispatch`, branch is the integration
branch, and source is `8e4ca8383f5f54a03f7b64f3c8f92225c00deb5b`. The
[publisher](../../scripts/publish-sample-release.py) requires a successful
**main push** producer and exact-source main evidence. Relabelling this preview
as that producer would bypass admission. Android sample build/runtime inputs
also changed after the preview; no four-platform current-source equivalence is
claimed. No preview ZIP, app binary or dependency was downloaded, and no rebuild
was started to recreate evidence.

The public repository's returned Releases are RC2/RC3, with no app assets.
**Public development sample delivery: 0/4 (0%); remaining: 4/4 (100%).** This
counts delivered files, not engineering effort or historical repair progress.

The `sample-development-release` environment now has exactly the owner reviewer,
self-review permitted, administrator bypass disabled and only the `main` branch.
That prerequisite is satisfied; it is not an approval of a particular run.
Effective rules still require `complete-gate`, `review`, `scan / osv-scan`, and
`osv-scanner`. The legacy branch-protection endpoint's 404 does not remove those
ruleset protections. No campaign PR or active/waiting Actions run was returned.
Neither the bootstrap nor sample-release workflow is registered, and
`initial-recipient-execution` is still absent.

## Narrow new source: connect the original child events

The [Node child adapter](../../scripts/hosted-cache-provider-node-bridge.cjs)
adds an actual asynchronous `spawn` call for the existing isolated Python
`--supervisor` entry, fixed argv/cwd, a fresh closed environment and original
pipe/exit/close handlers. It reuses the accepted supplied-event reducer rather
than implementing another ACK parser. No provider output is forwarded to the
runner's command parser; bounded opaque bytes and original errors are available
only through explicit private-access methods.

It takes an existing original Node-local deadline, not a new180-second allowance.
A timeout preserves an incomplete/live-child reference; it does **not** prove
retirement or permit native-file reads, cleanup or sealing. The original Python
supervisor still owns its native domain and unchanged provider180/shared-final45.
Node `hrtime` is not relabelled as the required native RAW observation.

On POSIX, cooperative cancellation targets the original child with SIGTERM.
On Windows the committed no-stdin roster refuses **before spawn**. A future
admitted roster with the fixed stdin reader uses one `C` byte, never Windows
`kill(SIGTERM)`. Presence of that source name is not implementation approval or
runtime qualification. The paused reader/entry WIP has not been changed,
executed or promoted by this adapter.

**The adapter remains NOT_WORKFLOW_WIRED.** Its implementation-review verdict is
**APPROVE_EXACT_NODE_BRIDGE_SOURCE_ONLY_NOT_EXECUTION_OR_HOSTED_ACCEPTANCE**,
report SHA-256
`8fde20b5f1a362e21d5f44bc252f985f7f1ac30e7b2a657c487ca4317d4c41a3`.
The exact adapter/test hashes are respectively
`1302bca39d88e8cbc65d61d2e500d200112a69550005c5bf50219852c956fe91` and
`3e8a153ab356536ade9f80f021232990b65d82388bacea2cc3cd73fae4cdc0a5`.
R1 found a concrete returned-child/partial-stdio error-listener ordering defect;
R2 installs the original error/close observers before pipe validation and adds a
regression. This was source inspection, **not an executed preimage failure**.
The asynchronous suite also defaults to exit1 until its final aggregate completes,
so an unresolved model Promise cannot quietly exit0. The containing commit's
issue record binds the final preservation and any separate offline request.
The [17 authored controls](../../scripts/tests/hosted-cache-provider-node-bridge-test.cjs)
replace process/timer/clock boundaries with explicit models; they are not
seventeen actual child/Windows/provider tests. They were unexecuted at the source
checkpoint. After a separate exact one-invocation owner authorization, all
**17/17 passed at 01:39:44 UTC**, original command/wrapper exit0, empty stderr,
guard4/unexpected0 and matching pre/post input hashes. Source was exactly
`4207bad2d932541eef2465c036502266d22f53dd`, tree
`ec4c219312d5d344e485a0bc10568cc25cd61951`; request-manifest SHA-256
`c0694e853a2ca77cd118f7b8b57878d4a36e1216cbe7e3f38b2de50d20ba1207`.
Original capture-manifest SHA-256:
`65d58b276301540db8459d0b14094cd61c5995a4fe20baeb856cfe96e05f540e`.
Independent read-only result verdict:
**ACCEPT_EXACT_ORIGINAL_OFFLINE_BRIDGE_MODEL_RESULT_ONLY**. No rerun occurred.
This one authorization is now consumed, as are the two earlier reducer
invocations. No further Node startup, provider or hosted execution is authorized.

This module is not yet a GitHub JavaScript Action or an admitted CLI. A closed
environment or matching supplied source hashes cannot authenticate the caller,
Node startup, tools or original runtime-service credentials. Its return always
leaves RAW/outer-Node/runner/provider acceptance unestablished. No ordinary
consumer or publisher is changed to accept this partial result.

## Narrow follow-up: the Windows launch refusal

The committed no-stdin roster makes the bridge refuse Windows before spawning.
Only the four already-recorded reader/entry launch/retirement defects were
therefore resumed as actual execution blockers. The six original paused files
remain unchanged in the integration worktree and are preserved in WIP ancestry
at `27330dc4f30e3bf64b624e7dcf4f5313a1b5ffb7`; R2 source is isolated.
The [cache guide](../testing/hosted-dependency-cache.md) records the post-poll
work-fence, lifecycle-phase, terminal-binding and wrong-return retirement repairs.
This is not a broader cancellation/security review. New reader45/entry52 methods
and the existing six focused independent controls remain **UNEXECUTED** for R2;
the Node17 pass does not qualify this changed composition.
Independent review returned
**APPROVE_EXACT_FOUR_R1_SOURCE_REPAIRS_ONLY_NOT_EXECUTION_OR_WINDOWS_QUALIFICATION**,
report SHA-256
`ea2caf3de467db8444767a11e48aab57e01716346ae81b654e370d63a2fc9e16`.

## Remaining execution blockers, in order

1. **Finish this real runner connection:** focused implementation validation,
   trusted prestart source/tool/service handoff, original post-close RAW
   readback and the required Windows cooperative stop integration. Do not
   reactivate unrelated cancellation review merely to polish it.
2. **Finish the existing Stage 1 path:** original receiving authority and
   initialization, bounded productive bootstrap, provider save/probe and
   encrypted export/custody. The complete1066 receiver still lacks its complete
   positive/owner-close acceptance; its held profile was not imported or retried.
   Bootstrap5400 remains **UNADMITTED / UNMEASURED**, not a usable job budget.
3. **Legitimate execution admission:** safely register the workflow, configure
   the separate initial-recipient environment and obtain the owner's exact
   stage/run/attempt/commit/tree/policy authorization. These operations require
   their separate authorization; this source checkpoint creates none of them.
   The public recipient policy remains branch-only, hash
   `2e90a1ed038d5bb6759d8d22e1bb5468331b49274a6956df470c1e785691f521`,
   valid September21-inclusive through October5-exclusive, not silently renewed.
4. **Hosted qualification and required checks:** genuine native/cache/resolver/
   custody/scheduling evidence must resolve both ordinary activation HOLDs and
   the whole-JVM interlock. No configuration-only result counts as ordinary
   test/ABI/simulator acceptance. Required checks remain mandatory.
5. **Owner-controlled delivery:** exact-head PR authorization, manual preserving
   main merge containing case-sensitive `[release ci]`, qualified main
   producer/evidence, then the owner's fresh post-build evidence approval.
   Only then may the existing publisher copy admitted app bytes to a public
   development prerelease and verify unauthenticated asset access.

There is no executable dispatch or publication authorization to infer from these
source changes. No settings, HOLDs, key material, protected instructions, RC3
history, compatibility rules or unrelated dependency proposals were changed.
Production/Maven/Store publication and physical-phone work remain outside this
immediate sample-delivery task. **Release NOT_READY.**
