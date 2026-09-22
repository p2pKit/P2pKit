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
Node startup, tools or original runtime-service credentials. The17-tested return
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
This is not a broader cancellation/security review. At exact source
`b5c9889dcb8793295e5f0e08751e40681da69bec` / tree
`28bf571b0692ffc2e74e6892ea07e2be48217486`, separate bounded offline reader
**45/45**, entry **52/52** and corrected independent **6/6** aggregates passed.
The first independent invocation failed during fixture import, before its tests;
the two-line fixture-order correction preserved all six method bodies/assertions.
Neither author suite was repeated. All successful invocations had exit0,
guard8/unexpected0/ResourceWarnings0 and matching pre/post input integrity.
No actual Windows pipe, provider, native clock or Actions runner was executed.
Independent review returned
**APPROVE_EXACT_FOUR_R1_SOURCE_REPAIRS_ONLY_NOT_EXECUTION_OR_WINDOWS_QUALIFICATION**,
report SHA-256
`ea2caf3de467db8444767a11e48aab57e01716346ae81b654e370d63a2fc9e16`.
Independent original-result inspection returned
**ACCEPT_EXACT_ORIGINAL_R2_GUARDED_MODEL_RESULTS_ONLY**, report SHA-256
`c733eb67e820ebad2c73cf0e118ff1edd286f10b160c7042ec79af2bc6a799ec`.
Capture manifests (including the retained setup failure, then corrected6):
`b4cb511227e0375520d788a6b1955664cbf5c9c1abd1653627443ef39ea94ba2` /
`de6c5ec5e7541ce441369951ee1fb77898952acb555a95cb749b77a6fa596033`.
The Node17 pass remains separately scoped to its earlier exact source.

Read-only GitHub refresh on22September still found unchanged main, all four
preview artifacts unexpired, no campaign PR and zero queued/in-progress/waiting
runs. Complete #437/#424 conversations now contain124/113 comments, including
the earlier preservation mappings; no previously captured comment changed.
Effective required checks and the main-only/no-admin-bypass owner-review
environment remain unchanged. Bootstrap registration and its separate initial
execution environment remain absent. Public development delivery is still0/4.

## Next narrow source: observe RAW after the provider child closes

The [fixed clock helper](../../scripts/hosted_cache_provider_clock.py) and updated
Node adapter now have a source connection for an isolated, credential-free native
clock read **after the provider supervisor's actual child close**. The same
invocation, role/domain, exact INT64 frequency, original RAW high-water and hard
end remain bound; Node keeps its original local deadline through the helper's
own EOF/exit/close. There is no new allowance, provider caller or workflow wiring.
The [cache guide](../testing/hosted-dependency-cache.md#post-provider-close-raw-continuation--partial-offline-verification)
describes the precise scope and remaining outer-ownership gap.

The helper samples before its own process closes. Thus this source can establish
only `OBSERVED_AFTER_PROVIDER_CLOSE`, **not post-last-owner/Node/runner RAW or
provider acceptance**. Timed-out children and failed/incomplete clock-helper
returns remain private and incomplete, never permission to read, delete, reuse
or seal native files. A closed known-failed provider transport stays failed.
Supplied source hashes do not authenticate prestart tools or runtime credentials.

At exact source `2f442918d06c9ff0f824dd0e006da96a18587edb` / tree
`4c46b9a9ca998aba86f05d7fac106323faced92b`, independent implementation review
approved **source only, not execution/native qualification** (report SHA-256
`cffe9b3ca5819c1be5544a70751175a84b25afe0d072cf80ada9ed7d956141e0`).
One later bounded Python invocation passed **18/18** at02:28:38UTC, test0.018s/
wall0.279s, command/wrapper0, guard8/unexpected0/ResourceWarnings0 and matching
pre/post integrity. This uses modeled readings and tiny source/file fixtures,
not native clock/provider execution. The cache guide binds its original capture.

The updated **30 Node controls subsequently passed once** at the same exact
`2f442918` source after separate owner authorization. Recorded timestamps were
02:43:43–02:43:44UTC, with command/wrapper0, guard4/unexpected0, empty stderr and
matching pre/post integrity. Independent original-result inspection returned
**ACCEPT_EXACT_ORIGINAL_NODE30_GUARDED_MODEL_RESULTS_ONLY**, report SHA-256
`f0a0d28a9bd1594098d63f7bfc70c07155b661e4be456a98f36bbf07ae07826f`.
The cache guide binds the exact request, original captures and resource limits.
No real provider/native/runner execution is inferred. This one-invocation
authorization is consumed, not a standing2GiB allowance or permission to start
held CI. No test or build was repeated.

## Fixed provider-original readback, still not an Action caller

The [new reader](../../scripts/hosted_cache_provider_readback.py) now checks
actual retained file identities and bytes against the successful outer ACK and
joins the original worker-request/native launch/inner packet bindings. Its22
focused offline controls passed once at03:11:49–03:11:51UTC; the
[cache guide](../testing/hosted-dependency-cache.md#fixed-ack-bound-provider-original-readback)
records exact scope, limits, original capture hash and independent approval.
These use tiny real POSIX files with modeled provider/native/clock originals,
not a hosted run or Windows qualification. Enclosing Owner/Action/runner return
and provider acceptance remain pending. No accepted test suite or app build was
repeated. Native preparation and the thin Node24 Action remain the next join.

Read-only service refresh at03:09:55UTC again found the four required checks,
sole-owner/main-only/no-admin-bypass release environment, no campaign PR or
active/waiting runs, and no bootstrap/initial-recipient execution registration.
The four preview artifacts remain unexpired; anonymous Releases still contain
RC2/RC3 without app assets. **Public development delivery remains0/4.**

## Native provider-file preparation: reviewed offline increment

The previously unfinished
[materializer](../../scripts/hosted_cache_provider_prepare.py) now has independent
implementation/result review and **26/26** focused offline passes, executed once
at03:38:11–03:38:13UTC. Two static deadline findings were repaired before that
invocation; the [cache guide](../testing/hosted-dependency-cache.md#fixed-native-provider-file-materialization)
binds exact scope, limits, captures and verdict. Tiny POSIX file writes/readbacks
are real; plan/admission/outcome/clock/bundle inputs are models. No accepted test
suite or successful app build was repeated, and no provider bundle was downloaded.

This completes only fixed file/request materialization under a borrowed Owner,
not the native readmission/preparation command, actual Action or acquisition path.
The enclosing Owner/Action return and provider/custody qualification remain open.
The earlier reader commit `fba24a179a58cafd687f1b6a4cbd76794233df45` is now mapped
to #437/#424 with exact posted-body readback. Source/GitHub refresh at03:27:07UTC
still found unchanged main, all existing gates, no campaign PR/active runs and
four unexpired preview artifacts. **Public development delivery remains0/4.**

## Native helper commands: reviewed offline increment

The [fixed native helper](../../scripts/hosted_cache_provider_native.py) now joins
old issuance observation, native preparation and ACK-bound readback in three
credential-free private-pipe commands. Independent implementation/original-result
review accepted **30/30** focused offline passes, executed once at
04:06:10–04:06:12UTC. The
[cache guide](../testing/hosted-dependency-cache.md#fixed-credential-free-native-provider-commands)
binds the three static preimage repairs, exact original capture/review hashes and
modeled scope. No accepted test suite, key procedure or app build was repeated.

This source reuses **trusted-main admission only**, not the still-unfinished
Stage1 receiving authority. The full controller was only source data; tests
compiled Owner+LIMIT, not the complete controller. No guarded native CLI, real
provider, Windows native files, Node Action or runner was executed. The proposed
oldEnd-minus30 worker cutoff is not admitted/measured. Source availability and
offline controls do not close the native/custody/scheduling acceptance gap.

At this native-helper checkpoint, the three new Action files were
**UNREVIEWED / UNTESTED / NOT_WORKFLOW_WIRED** and outside that increment;
the Action test file did not yet exist. The following source-only increment
supersedes that source-review status, not its execution HOLDs.

## Thin provider Action: reviewed source and subsequent offline result

The [Action](../../.github/actions/dependency-cache-provider/action.yml) now has
independent implementation review and
[48 authored controls](../../scripts/tests/hosted-cache-provider-action-test.cjs).
The [cache guide](../testing/hosted-dependency-cache.md#fixed-node24-provider-action--source-reviewed-not-executed)
records its exact scope and review hash. The single blocking static finding,
lost originals on main output failure, was repaired before execution. The
reviewer's final verdict is
**APPROVE_EXACT_PROVIDER_ACTION_SOURCE_AND_48_AUTHORED_CONTROLS_ONLY**.
At that source-only checkpoint, only the bounded Ruby manifest structure check
had run; no Node startup, syntax check, import or Action control execution had
occurred. The frozen offline envelope and execution authorization were separate.

After the owner's later release-workflow testing/qualification authorization,
the reviewed envelope ran once at **10:54:44–10:54:45UTC**: **48/48 PASS**,
guard4/unexpected0, command/wrapper/enclosing-invocation0/0/0, empty stderr and
exact input/output integrity. Source was
`14a1e8d0dda4d1dd13c11bb7e995052e123c358c`, tree
`4a8e6a29b239fadc7d4f2980cbf5e4635e9a5e03`. Independent original readback returned
**APPROVE_EXACT_ACTION48_ORIGINAL_OFFLINE_MODEL_RESULT_ONLY**, report SHA-256
`eb68d12d4a353c5a6f752b05ad120c59823eea1dae7f1d26b3fe56b1e4dd279e`.
The [exact result record](../testing/hosted-dependency-cache.md#subsequent-action48-original-offline-result)
binds the frozen request, complete original/enclosing manifests and unchanged
CPU20/AS2GiB/wall30+kill2 envelope. This is model execution, not actual
Python/native/provider/HTTP/cache/hosted acceptance. No accepted suite or app
build was repeated; no private key was accessed.

No workflow invokes this Action. Its native helper still requires trusted-main
admission; it cannot bootstrap its own recipient or supply Stage1 authority.
Actual runner/native/provider execution, post-last-owner RAW, custody and the
existing qualification/activation gates remain outstanding. Cancellation-review
expansion, repeated app builds and key setup remain out of scope.

Read-only GitHub refresh at **04:36:13–04:36:24UTC** found
the same four required checks, the sole-owner/main-only release environment,
no campaign PR and zero queued/in-progress/waiting runs. Complete #437/#424
conversations contained130/119 comments. All four preview artifacts remain
unexpired; anonymous Releases still list RC2/RC3 with no app assets.
**Public development delivery remains0/4 (0%); remaining4/4 (100%).**

## Remaining execution blockers, in order

1. **Finish/qualify this real runner connection:** its Node30 and Python18 model
   results are accepted, but actual caller/prestart source/tool/service handoff,
   post-last-owner/Node/runner custody and native Windows qualification remain.
   The new post-provider-close helper is only verified in offline models. Do not
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
