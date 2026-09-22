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

## Nonproductive Stage1 workflow source

The [manual-only bootstrap workflow](../../.github/workflows/dependency-cache-bootstrap.yml)
now connects the existing `prepare-originals` CLI in the actual
`initial-recipient-gate` job on `ubuntu-24.04`. It retains exactly `selection`,
`expected_sha` and `expected_tree`, the separate `initial-recipient-execution`
environment and the original owner approval-history/comment checks. Job/API
names are not display/matrix aliases. The dedicated `P2PKIT_ACTIONS_READ_TOKEN`
mapping is confined to the acquisition step. Checkout separately uses its
platform credential temporarily, with no persisted authentication for the
explicit public fetch. No credential is sent to a provider or job output;
native acquisition never serializes its read token into Git records or logs.
The native gate still owns work75/final120; the six-minute job ceiling is only
an unqualified outer checkout/fetch/acquisition limit, not bootstrap5400 admission.

Pinned checkout starts shallow with tags disabled and no persisted credentials;
one explicit no-tags fetch then obtains the two required complete source histories.
Read-only inspection of checkout `3d3c42e`'s `git-source-provider.ts` established
that its depth-zero route fetches all branches/tags, so setting only
`fetch-tags:false` alongside depth0 would not meet the no-tags requirement.
The inspected12701-byte public source has SHA-256
`aaad769029fde263ba2c9fd26287ada2eed4d7d0c89676a04b78c0bfd52dc7a2`;
no Action was executed or installed by that source inspection.

The dependent `populate` job maps the six exact cohorts to their maintained
native selectors, but its **only command exits125**. It has no checkout, setup,
credentials, environment, provider call, artifact upload or unconditional Gradle
cleanup. Gate success cannot bypass this productive HOLD. There is no push,
schedule, PR or guessed registration event, and no change to CI's Stage2/whole-JVM
interlock or either ordinary HOLD. No completed bootstrap, provider call or
Release asset follows from this preparation. A wrong-context skipped gate also
supplies no eligibility or qualification.

The [focused workflow controls](../../scripts/tests/check-initial-recipient-workflow-policy-test.rb)
received independent implementation verdict
**APPROVE_EXACT_NONPRODUCTIVE_STAGE1_WORKFLOW_SOURCE_AND_43_AUTHORED_CONTROLS_ONLY**,
report SHA-256
`069809e652299d0addf153e43fde0f69c90c90811c347e4a260d78fe43120ffa`.
The final seven-input source manifest is
`563001b1ce36e044a6b2df7a5408f2476294024524cf4c484058a48189bdebd4`,
over baseline `e22e9dd6a6467f0db2a5c2dc24e5f630eb88577f` / tree
`954f713d6810cbe4c76b0d1abb4f5bd58406677b`. That verdict is distinct from the
earlier preimplementation recommendation and did not execute the controls.

At **11:45:44UTC**, the43 controls passed once, together with one positive
existing heavy-queue composition check over all current workflows. Ruby reported
CPU0.071693s/wall0.081107s; command/wrapper/enclosing exits were0/0/0, stderr was
empty and pre/post source/tool integrity matched. The first Ruby startup had
refused before loading any controls because bubblewrap added `PWD` to the four
allowed environment names. A no-project environment diagnostic confirmed that
cause. The corrected launcher clears the environment again immediately before
Ruby; the original harness, assertions, YAML and test remained unchanged.
The failed startup is retained, not counted as a passing test or erased.

Both launches retained UID/GID65534, no-network namespaces, read-only case/runtime,
CPU20/AS512MiB/file32MiB/FD128/core0/wall30+kill2. Successful capture and enclosing
manifest SHA-256 values are
`da3f52743588fcc8b01913116f465ab79f764ca14f6736793d037c9250b95d5d` /
`658ba2c2ad8fabb2d5c1a3c4ede8cba8a55f03e7fd5a6f154df6ef9e91b5b7a7`;
the failed capture is
`96b83b3d42dbee54e96c262f0c41e0e1ff539460ddee7b68bea209a06f74d013`.
Independent original-result/final-document review is mapped separately in #437.
This standalone control is not yet a CI/release gate. No existing suite, Python
controller, complete1066 receiver, provider, hosted Action or app build ran.

This workflow is **not dispatch-ready**. The environment and workflow
registration remain absent, and no exact Stage1 owner statement/challenge has
been supplied for this source. Merely referencing an environment in YAML does
not configure its required protection; GitHub can create an unprotected missing
environment at execution. Do not dispatch to discover that condition. Safe
registration/configuration/allocation need their existing separate authorization.
The worker is deliberately held until the complete receiver/current authority,
initializer, producer, provider, evidence integration and qualification exist.

## Protected Stage1 environment configured — 12:10–12:12 UTC

The owner separately authorized creation/configuration of
`initial-recipient-execution`. This prerequisite is now **complete**, superseding
the earlier dated absence observations above; it is not registration, dispatch,
Stage1 authority or permission to lift a HOLD.

| Read-back setting | Actual value |
| --- | --- |
| Environment ID | `22474224636` |
| Sole required reviewer | `Apdelrahman1911` / user `104788132` |
| Self-review prevention / administrator bypass | `false` / `false` |
| Deployment policy | Custom branch policies; not protected-branches mode |
| Integration branch policy | `60692240`: `work/nonphysical-integration-20260915-022112` |
| PR merge branch policy | `60692241`: `refs/pull/*/merge` |

There are exactly these two branch policies, no tags, and exactly the
required-reviewers and branch-policy protection-rule types. No environment
secret was configured. Creation was recorded at **2026-09-22T12:10:45Z**;
configuration completed at **12:11:11Z**. Separate final GETs matched the original
responses. The unchanged maintained `hosted_initial_recipient_gate.check_environment`
ran **once**, on those real final bodies and IDs, at **12:12:59Z**: **PASS**,
exit0, empty stderr and matching pre/post input/tool integrity. It created no
owner statement, approval selector, eligibility or native Admission.

This was an offline check of public configuration bodies, not hosted/native
execution or proof of a particular namespace/resource envelope. The retained
packet does not include its launch command. Independent read-only original-result review returned
**APPROVE_EXACT_INITIAL_RECIPIENT_ENVIRONMENT_CONFIGURATION_READBACK_ONLY**,
report SHA-256
`eb3e5df39cd7749eb220129203e6bb36508e0ee9df0d49aa38a23170272cff16`.
The reviewer did not rerun the check or query GitHub independently.

Final environment/branch-policy GET SHA-256 values are
`4b2d7096ef531b17a2ac0d127e4f0cdee9798c34cf98a1658407ab9620f34095` /
`f70052e752222760e6d1f44210c8644d18cd06a0abd8b27e2a1d05e6bf64260d`;
the validator-capture manifest is
`c7c43858f7efe59552c8e28371e175bb757ff2671df6addcfa48f2ea86effac6`.
These are configuration records, not a challenge or authorization to execute.
Future statements must bind these actual IDs, and actual use must reacquire the
configuration rather than trust this dated record.

Read-only refresh completed at **12:22:41UTC**: both environment configurations
and main rules were unchanged; all four required checks remain. There are
78 open issues, seven dependency PRs, no campaign PR and zero queued/in-progress/
waiting Actions. Bootstrap and publisher workflows remain unregistered. The four
preview artifacts remain unexpired through September30; anonymous Releases still
have no sample assets. No artifact was downloaded, no accepted suite/build/key
procedure was repeated, and no private material was accessed. Main and integration
remain `3bc76f956f8f47447b51a62474fc878b9c43173c` and
`24bbe8e9b78cef552559904fe901a12c443ec184` at that refresh.

## Registration-only hosted probe completed — 12:55 UTC

After separate exact-source owner authorization, one normal no-tags push at
**12:55:07–12:55:11UTC** created only
`work/register-cache-bootstrap-20260922-24bbe8e9`, at commit
`210f87ec8a64ffd371a0001a19371857ffc10b45`, tree
`079640d2a9e8579338ad4b425ddcc87de951b839`. **Never merge this probe branch.**
Its only source change replaces the bootstrap workflow on that isolated branch;
the integration gate and productive exit125 HOLD remain unchanged.

The [actual run35730126848/1](https://github.com/p2pKit/P2pKit/actions/runs/35730126848)
completed **successfully**. GitHub now registers the bootstrap path as workflow
**364235112**, active, named `Dependency cache bootstrap registration only`.
Its sole job **106753327302 / registration_only**, label `ubuntu-24.04`, ran at
**12:55:24–12:55:26UTC** with the reviewed one-minute job ceiling. Apart from
GitHub's setup/completion steps, it executed only the fixed informational printf.
The retained log contains
`CACHE_BOOTSTRAP_REGISTRATION_ONLY; NO_ADMISSION_OR_PROVIDER_EXECUTION`.
There was no checkout, setup Action, environment gate, mapped credential,
provider invocation, build or artifact upload. The artifact list is empty.

The remote commit/tree/parent and decoded public workflow bytes match the
reviewed source. YAML SHA-256:
`d27d380c9c9d158539a0931bd5ea25ad979a4ff3b37fd3a3517d973df6ea1acc`.
Original job-log SHA-256:
`bcac0c6298a9dc4a10ad5f84f958b09c79eb28287b06c1323fe1941c13d1790d`.
Retained source/preflight/push/service-result manifest SHA-256:
`d4e7fa040c73a5758a6eab33ba87d7f8234b0c38e8bc68276234b057e0c2c0e7`.
Independent original-result review will be mapped separately in #437; these records
are not a personal Stage1 statement, environment challenge or native Admission.

A pre-push metadata helper initially addressed the wrong environment name and
received404. No push had occurred. That client variable-collision error and its
response were retained; corrected literal-endpoint GETs matched both actual
environments, branch policies and main rules. It was not a missing protection
or failed hosted attempt. The one authorized push and run were not retried.
The accepted13+15 offline controls and earlier suites/builds were not repeated.

Read-only verification at **12:57:47UTC** found exactly that one successful
attempt for the probe head and zero queued/in-progress/waiting runs. Main and
integration remained `3bc76f956f8f47447b51a62474fc878b9c43173c` and
`9db9f71b188c675533ef7f737a2e31e96df23741`. Publisher registration remains absent.
The consumed authorization permits no subsequent dispatch, rerun, productive
activation or publication. Successful registration does **not** prove branch
dispatch behavior, receiver/provider/native/cache/custody or scheduling
qualification, or remove any HOLD. Public development delivery remains **0/4**.

## Authorized receiver-capacity probe: failed, originals retained

The owner's subsequent exact single-push authorization was used once for
**`7c6b671dd9286a9bbd108730c75c9f506f85565b`**, tree
**`f427dd88345be216c8096460517cfdd73e629615`**, parent
`362aa96cdeff29a534b000814317dea7fcef6799`. The isolated branch
`work/receiver-hosted-capacity-20260922-362aa96c` is **NEVER MERGE**.
Its source/static approval did not approve execution results or Stage1.

[Run35747118161/1](https://github.com/p2pKit/P2pKit/actions/runs/35747118161)
completed **failure**. Its only job, `106811483340 / receiver_capacity_only`,
ran on `ubuntu-24.04` at **15:24:33–15:25:07UTC**. Actual image:
`20260920.314.1`, Ubuntu24.04.5, Python3.12.3 and util-linux2.39.3-9ubuntu6.6.
The two original serial model invocations, with unchanged CPU20/wall30+kill2
and other reviewed limits, returned:

| Invocation | Original result |
| --- | --- |
| `FixturePrepareModels.test_prepare_and_close_synthetic_graph` | Exit0, one method PASS; wall5.138/user3.872/system0.156 seconds; guard4, unexpected denials0, ResourceWarnings0. This is synthetic fixture/model close only. |
| `FixtureReaderModels.test_complete_fixed_graph_from_closed_synthetic_fixture` | Entered its fixed test, then exit1; wall20.009/user19.824/system0.182 seconds; `unshare: sigprocmask unblock failed: Invalid argument`. No completed-method result, complete1066 marker, final guard/resource summary or receiver-close acceptance. |

Body, completed launcher, Actions step and run all failed. Upload succeeded;
that does not turn the failed receiver into a pass. Artifact **10704000608**,
`receiver-capacity-model-35747118161-1`, contains only public model captures:
**31,326 ZIP bytes /43 files /136,592 uncompressed bytes**. GitHub records
creation **2026-09-22T15:25:04Z** and expiry **2026-10-06T15:25:03Z**.
The downloaded ZIP matches the service size/digest; every extracted byte,
complete42-entry capture manifest, all222 reviewed source inputs, both harness
inputs and four complete455-line pre/post integrity transcripts match.

- Artifact SHA-256: `3ddd56f52798e2e15f52f251bbf9fe1100ca1ce8f7676ac15961a56725abf42a`.
- Capture-manifest SHA-256: `ee28d53678dd105a2113888665dd1b7ab850713ec273759863e98ec1ffa01c16`.
- Retained seven-file original-manifest SHA-256: `beeddf82519aebf919c6bc5d44595f15122ed2f22733a3c3ee7dc57e9cb5ecf7`.

The observed20.006 aggregate CPU seconds strongly suggest exhaustion of the
existing20-second CPU limit. Public upstream util-linux2.39.3 reports that same
error for several child-signal restoration failures, including a rejected
`signal(SIGKILL, SIG_DFL)`. This is a supporting source explanation, **not an
exact Ubuntu-binary mapping or retained child wait status**. Do not relabel the
observed exit1 as137, assert a specific child signal, claim a wall30 timeout or
invent a Python assertion failure. No further experiment is needed merely to
establish that this attempt failed its required complete return.

Read-only post-run metadata at **15:30:52–15:31:40UTC** found exactly this one
head run/attempt, no queued/in-progress/waiting/pending/requested runs, unchanged
main/integration refs and effective rules, and unchanged complete136/125-comment
#437/#424 histories. The classic protection endpoint's404 is not absent ruleset
protection. The scoped original-result review will be mapped separately in #437;
it cannot approve capacity, native/provider execution or an owner decision.

No retry, alternate runtime/machine, deadline change, provider invocation, app
rebuild, private-key access, merge or publication followed. The authorization
is consumed. A defensible reviewed receiver repair is still needed; neither an
unchanged retry nor the rejected earlier primitive alternatives is justified by
this result. Any later execution needs its own exact authorization. Both ordinary
HOLDs, productive bootstrap refusal and later qualifications remain. Public
development sample delivery is still **0/4 (0%); remaining4/4 (100%)**.

## Receiver scan repair awaiting execution

After the failed hosted probe, the owner authorized a receiver-performance
source repair and independent implementation review, **then a fresh exact-source
execution request**. The repair preserves all check boundaries and limits. It
changes only private saved-path routing and aggregate roster-loop bookkeeping;
the [cache guide](../testing/hosted-dependency-cache.md#receiver-scan-performance-candidate-execution-held)
describes the live observations and fallback obligations. The query roster keeps
its original generator phases rather than introducing phase-lifetime machinery.

Independent source review identified two concrete lifetime-equivalence defects:
a temporary query tail row surviving into the next slice, and compiled path
references retaining a node after fallback exposed its mutable original list.
The candidate restores the original query phases and discards duplicate plan
references before fallback. Dedicated oracle controls cover both, including
deletion inside an intercepted helper and after helper restoration. These are
**source findings and authored regressions, not executed failures/passes**.

Final candidate file bindings:

| File | SHA-256 |
| --- | --- |
| `scripts/run-hosted-initial-recipient.py` | `44b1208c3eafe2a730838fcda1439b511396ec4bc075d4f36e47e6f05c980d65` |
| `scripts/tests/hosted-initial-recipient-reader-scans-test.py` | `2be93ee6e259544d16b36b896b772c142bd0bf3d4d4d74283a38fb0af81ae8e9` |

Independent verdict:
**APPROVE_EXACT_RECEIVER_SCAN_IMPLEMENTATION_AND_AUTHORED_CONTROLS_SOURCE_ONLY**,
corrected R3 report SHA-256
`d78f90aa02439b0da4c1799d9f75b9fe10a69887f3c54a05390e5bec6b7514ff`.
This is file-pair source approval, not executed equivalence, measured performance,
complete-reader capacity or the owner's exact-head PR authorization.

The new file contains **18 unexecuted focused controls** (11 history /7 roster)
plus **one unexecuted diagnostic**, not a complete graph test. The proposed next
request is exactly two serial, bounded offline Python invocations: the18 controls,
then the one fixed442-node/223-row diagnostic only after a successful first
aggregate. It uses the existing UID65534, isolated Python3.12, cleared environment,
read-only source, process/network/native-loader guards and unchanged resource
envelope. No syntax/import check, timing run, full receiver retry, application
build, provider execution, CI dispatch, merge or publication is included in this
source authorization. Whitespace/hash inspection is not a test pass.

No measured performance gain or CPU20/complete1066/owner-close acceptance exists
for these changed bytes. The earlier failed aggregate remains failed. The final
independent verdict is bound above. The local commit/tree and request manifest
will be mapped in #437/#424 after this checkpoint and request are frozen; that
mapping is not yet completed here. Source review is not execution or personal
owner authorization. No source push or workflow activation follows automatically. Original cancellation
WIP, protected instructions, public recipient policy and all HOLDs are preserved.
Public app delivery remains **0/4 (0%); remaining4/4 (100%)**; **Release NOT_READY**.

## Remaining execution blockers, in order

1. **Finish/qualify this real runner connection:** its Node30 and Python18 model
   results are accepted, but actual caller/prestart source/tool/service handoff,
   post-last-owner/Node/runner custody and native Windows qualification remain.
   The new post-provider-close helper is only verified in offline models. Do not
   reactivate unrelated cancellation review merely to polish it.
2. **Finish the existing Stage 1 path:** original receiving authority and
   initialization, bounded productive bootstrap, provider save/probe and
   encrypted export/custody. The complete1066 receiver still lacks its complete
   positive/owner-close acceptance. The separately authorized hosted capacity
   probe above failed; no subsequent retry or productive activation occurred.
   Bootstrap5400 remains **UNADMITTED / UNMEASURED**, not a usable job budget.
3. **Legitimate execution admission:** registration-only service behavior is now
   established, but actual branch dispatch/allocation remains unexecuted and
   separately authorized. Recheck the configured initial-recipient environment
   and obtain the owner's exact
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
