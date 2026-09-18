# Bounded hosted dependency-cache preparation

Ordinary FULL/Desktop now have **consume-only source wiring behind unchanged
activation HOLDs**. That wiring is not an activated cache, a successful hosted
run, provider qualification or measured download savings. Dependency bootstrap,
H-to-S snapshot export and save/probe orchestration remain dormant; source or
offline-model success cannot lift either HOLD.
[`hosted_dependency_cache.py`](../../scripts/hosted_dependency_cache.py) has no
CLI, action runner, downloader, extraction, deletion or subprocess entry point.
The connected caller is
[`run-hosted-test-custody.py`](../../scripts/run-hosted-test-custody.py). Do not
bypass the HOLD or restore an entire Gradle home to use it.

## Reuse bytes, not old test results

The explicit modes are:

- **Consume (connected source, held):** exact-key standalone restore into the original staging directory
  S, then existing strict file admission into a fresh canonical Gradle home H.
  No writeback. A missing/unqualified result does not silently select bootstrap.
- **Bootstrap (dormant):** original empty S, no restore, the existing known-empty seed and
  separately admitted dependency-producer execution; then a bounded verified H-to-S
  snapshot. The helper writes new dependency files in S; it never replaces S,
  adopts restored contents, clears files, or modifies H.

The reusable key binds a versioned namespace, admitted profile/native role,
semantic exact-artifact allowlist hash and wrapper-properties hash. Source
commit/tree, original run/attempt, admission and staging hashes remain separately
bound in each plan/receipt. Unchanged dependency inputs may share bytes across
source revisions; **tests must still qualify the changed source**. Wrapper
distributions, resolver metadata and toolchains are not seeded, so zero network
traffic is not promised. Provider cache versions also depend on path/compression
and branch scope; equal keys alone do not guarantee a hit across those cohorts.

Plans are private, path-bearing records, not public evidence companions. A pure
`make_plan` or `validate_plan` call only checks supplied data. The connected
consume path separately requires the exact admitted source, stage and original
action outcomes; those requirements still need genuine hosted qualification.

## Separate bootstrap identity (dormant)

[`hosted_cache_bootstrap_identity.py`](../../scripts/hosted_cache_bootstrap_identity.py)
defines a manual-only `cache-bootstrap` identity, not an ordinary FULL/Desktop
test identity. Its closed `selection` names are `desktop-linux-x64`,
`desktop-windows-x64`, `desktop-macos-arm64`, `desktop-macos-x64`,
`full-macos-arm64` and `full-macos-x64`. The separate `cacheCohort` selects only
the byte-reuse profile/role. A future controller must derive that cohort from
the admission; it cannot accept an independent caller-selected profile or give
FULL's simulator/ABI/transcript authority to a configuration-only producer.

The three dispatch inputs are exactly `selection`, `expected_sha` and
`expected_tree`. The fixed proposed producer request is
`help --console=plain --no-configure-on-demand`; it is explicitly
`CONFIGURATION_ONLY_NOT_COMPLETE_DEPENDENCIES_OR_TESTS` with `NOT_PERFORMED`
test acceptance. Configuration may resolve only part of the dependencies.
Neither a declared identity nor a successful configuration proves population,
resolver reuse, zero downloads or any ordinary product test.

The identity requires exact hosted workflow/run/source/tree/role labels, clean
full history and ancestry from the original fetched main. Recipient policy is
read only from that main, with source and main rechecked afterward. Candidate
policy and key/budget/command inputs cannot supply authority. The real entry
uses the existing required native-owned Git query boundary. Its closed grammar
admits the exact shallow-repository query and `merge-base` with two full lowercase
commit SHAs, not arbitrary refs/options, fetches or writes. Existing query
count, capture, 15-second query and 45-second finalization bounds are unchanged;
they are not a complete bootstrap schedule. Supplied event/Git models do not
attest a real hosted caller or native retirement.

The native-query supplier also accepts an optional **same-process monotonic
work/final owner-fence pair**. It only shortens the existing bounds, including
constructor allocation, every query, admission/failure retention, readers,
writers and final session close. Defaults preserve ordinary behavior. The
separate dormant original-acquisition caller now supplies this pair; no ordinary
caller or activated workflow does. Cancellation callbacks alone cannot
cap the supplier's finalization I/O. Expiry forbids new retained-file acquisition
but does not excuse known-owner cleanup; UNKNOWN still quarantines its pins.
A provisional session receipt can precede a failed late close, so it never
substitutes for actual supplier return. This seam supplies no shared-clock
identity, complete bootstrap allocation or service-job/productive budget.

Pre-budget plan, stage and seed-intent helpers now bind that closed cohort to
the original bootstrap admission. Selection, native host labels, manual workflow,
configuration-only request and `NOT_PERFORMED` disposition must agree. A caller
cannot choose a different profile/role or use bootstrap admission in consume mode.
Removing/relabeling the bootstrap scope/profile while leaving its reserved fields
or recognizable bootstrap workflow/job/event-binding markers does not select the
legacy ordinary path. Stage/plan declarations still cannot
attest empty directories, original live identities or successful acquisition.

This is **cohort planning, not the bootstrap execution-context integration**.
Seed, export and save-set entry/retained-receipt checks explicitly refuse bootstrap
admission before owned acquisition. Fabricated ordinary Desktop context or FULL
`primaryAbiAccounting` cannot fill the missing producer/budget path. A future
separate path must retain and rederive original source/run/clock-bound budget
evidence and carry a nonrenewable fence; a supplied budget digest alone is not
authority. No new context schema, allowance or clock is admitted by these guards.

The evidence-only caller below now connects this identity, not a productive
bootstrap job. The named future `.github/workflows/dependency-cache-bootstrap.yml`
still does not exist. Original producer success, same-home stop, known worker retirement,
empty-seed/export/freeze/save/probe custody, separate seal and a complete admitted
budget remain unfinished. The proposed 5,400 seconds is **not admitted or
measured**. Windows file ownership still has its 900-second lifetime; its
576MiB aggregate Snapshot cannot hold the 2GiB dependency cohort. Both ordinary
activation HOLDs remain. The original checkpoint's untested WIP status is dated;
later scoped checks/review are recorded against their exact source, not claimed
as executions at that checkpoint.

### Original acquisition, not bootstrap execution

[`run-hosted-cache-bootstrap.py`](../../scripts/run-hosted-cache-bootstrap.py)
and [`hosted_cache_bootstrap_origin.py`](../../scripts/hosted_cache_bootstrap_origin.py)
add a **dormant, not-workflow-wired original-acquisition slice**. Its sole public
acquisition operation is `prepare-originals`; the later `adopt-originals` operation
only revalidates retained originals. `_service` is the closed native-child entry,
not a local identity override. No environment impersonation or execution is
authorized by this documentation.

The source-proposed prelude caps are **120 seconds final /75 seconds new work**,
explicitly **UNMEASURED / NOT_ADMITTED**, not part of an admitted 5,400-second
bootstrap budget. One native service phase uses the earlier of its original
45-second work fence or the prelude work cutoff, followed by at most45 seconds
of finalization inside the original prelude. Each GET remains15 seconds/socket5;
the pair, retention and child success share the original phase work fence.
Initial child metadata reads have a local45 ceiling that loading the original
parent frame can only shorten. Known-owner cleanup is still attempted on expiry;
expiry cannot turn new acquisition or a late return into success.

The caller retains the original prelude, actual native-query admission/session
return, closed context/prelaunch records, prelaunch native baseline, native birth,
process exit/drain/close dispositions, capture outcomes and two closed Actions
GET observations. The original first child reading must follow the **last parent
pre-spawn high-water**, carried in the exact native launch argv. Early metadata
observations are preserved through frame binding. The parent's later birth
observation can occur concurrently with child work; it is not substituted for
that pre-spawn floor. Original source/main/policy admission runs again before
the final provisional receipt.

The Actions-read token is confined to service-child acquisition and is absent
from retained command/context records and the native Git environment. This is
non-inheritance, not memory erasure or a sandbox against hostile same-user code.
Closed selectors map the four native roles to `ubuntu-latest`, `windows-latest`,
`macos-26` and `macos-15-intel`; these are dormant source selections, not deployed
or qualified runner environments. Configuration and product execution never run
in this slice.

Failed HTTP observations use only the remaining **original** failure-finalization
interval. A failed or implicit EOF reader close keeps UNKNOWN even after the
standard HTTP parser detaches its reader, without retrying an ambiguous close.
Cancellation and the first failure remain failures. Observations retain bounded
bytes actually returned through the supplier, not a complete wire capture or a
reconstruction of bytes lost before return. Long-lived capture files use the
original phase final fence, not a newly started or prematurely ending IO45
allowance; their allocation still checks the original work cutoff.

The chain is acyclic: child provisional terminal → post-close ACK → separately
observed native return/retirement → parent provisional receipt → private
post-original-owner-close handoff. Internal
revalidation is **repeatable read-only within that owning call**. It requires
that owner's original returned phase/admission objects and exact retained
prelude/session/baseline/response bytes; copied data or a caller success flag
does not create provenance. The separate reader below never populates those
original-call registries from disk. No cross-process **execution** adoption exists.
A future trusted workflow must bind the **exact original prepare-step outcome**,
not its normalized conclusion or the provisional receipt/digest, before any
downstream adoption. No receipt can observe its own later successful return.

### Private handoff and read-only adoption

Preparation binds the original native session/child-directory identities and
native preparer lifetime, not merely paths or a PID. The existing service scope
observes that preparer before launch and before its close; Windows uses a
nonowning current-process pseudo-handle, not another acquired process handle.
The parent receipt retains those bindings. After its original owner actually
closes successfully, a fresh small owner reopens only those original directories
and exclusively writes private `prepare-handoff.json`. It records the original
post-close clock observation and original receipt/context hashes.

That handoff writer has at most45 seconds, shortened by the **remaining original
120-second final fence**. It grants no new work/job allowance. Its own subsequent
close and command/step return are still unobserved by its file; a later failure
cannot be rehabilitated from provisional bytes. Public preparation output
contains only a closed scope, handoff hash and explicit non-authority fields,
**not private native, clock, path or runner records**.

The dormant `adopt-originals` input boundary requires
`P2PKIT_BOOTSTRAP_PREPARE_OUTCOME == success` and the original handoff hash in
`P2PKIT_BOOTSTRAP_PREPARE_SHA256`. These must eventually be supplied by a fixed,
reviewed workflow from the actual prepare step's **outcome**, never its normalized
conclusion. **No workflow currently establishes that trusted wiring.** Environment
values, matching digests and consistent supplied records cannot authorize
themselves; offline models do not attest a GitHub caller.

The reader carries its **first** shared-clock observation and every pre-frame
metadata high-water into the original prelude. A first observation preceding
the handoff fails even if a later clock recovers. Initial metadata I/O has a
local45-second ceiling which frame binding can only shorten. Readmission is
**work inside the original75-second cutoff**, not an extension using the final
120-second cleanup interval. Actual source/main/policy/native re-admission uses
the existing owned query supplier. It records new originals in a separate
exclusive sibling episode; it never modifies preparation originals, reacquires
the two HTTP responses, or inherits the acquisition token. The entire original
chain and directory identities are reread before and after that admission.

Same-PID adoption is conservatively refused; this is **not** native proof of
preparer liveness, absence or complete retirement. The proposed workflow's actual
successful original step outcome remains essential. The adoption receipt/public
hash are themselves provisional until their own close/handler/output/command
returns succeed. Adoption remains `NOT_ADMITTED`, tests `NOT_PERFORMED`, and
export/save authority false. No canonical initializer, producer, cache/provider
execution, admitted job budget or encrypted custody/seal is added by this reader.

There is still no canonical initializer/producer launcher, seed/export/save/probe
caller, encrypted export/seal/upload, or productive/job-budget acceptance here.
No production caller invokes `cache.export_snapshot` or `cache.save_set`.
The [source continuation](../maintenance/nonphysical-source-resume-2026-09-17.md)
records executed offline controls, retained failures and exact independent-review
scope. Neither those controls nor this caller lifts either ordinary activation
HOLD or supplies the missing routine recipient policy.

### Read-only execution-entry context

Inside that same adoption call, an internal entry bridge now binds the actual
returned re-admission and its original session/return bytes to the preparation
originals. Its private `entry-context.json` keeps execution profile
`cache-bootstrap` separate from the byte-routing `cacheCohort`, and binds the
original source/run, shared-clock identity, directory identities and observation
high-waters. The schema2 adoption receipt consumes this context and binds its
exact hash; the public scope is `BOOTSTRAP_READ_ONLY_ADOPTION_PENDING_RETURN_V2`.
This is not another operation, an admitted job budget or a productive owner.

The entry retains the actual preparation and adoption directory objects. Each
must still be an unretired resource registered with this owner; matching paths
or native identities cannot put a different handle inside its close obligation.
An equal/copied entry, admission, owner or fence is not the original same-call
return. Disk records never recreate those private references or registries, and
the entry cannot be used after its owning call closes. These checks do not
claim protection against arbitrary hostile mutation of the Python process.

Consuming checks reread the original preparation chain, including around entry
and adoption-result retention. They require the exact original handoff/context
bytes, preparation binding, directory identities and current re-admission
originals. Only the new read-only `originalChain.revalidatedNs` observation may
advance during comparison; original child/service/native times and hashes cannot
change. These are point-in-time rechecks, not an atomic filesystem freeze or
proof of any provider's archived bytes. No second HTTP acquisition occurs.

Entry work remains inside **original75**, and its owned reads/writes/close retain
the original adopter's **local45** ceiling. Remaining **original120** time is
not a renewed entry allowance. The pre-existing public handler/output/flush
completion checks use original120 after the owner closes; local45 is not a
new whole-command deadline. Late work, cancellation or UNKNOWN remains failure
even when provisional files exist. No source-owned deadline was widened.

Both the context and receipt retain `NOT_ADMITTED`, `NOT_PERFORMED` and export/
save authority false. No canonical initializer, producer, seed/export/save/probe
or encrypted-custody caller consumes this entry for execution. A future
productive owner still needs separate reviewed allocation, original service-
budget rederivation, trusted workflow outcomes and live native/source admission;
the proposed5,400 seconds remains unadmitted/unmeasured. The entry cannot make
configuration-only execution satisfy ordinary FULL ABI/simulator/transcript
acceptance or lift either ordinary activation HOLD.

### Original service-time basis, not a job budget

[`hosted_cache_bootstrap_service_time.py`](../../scripts/hosted_cache_bootstrap_service_time.py)
derives a closed, private `BOOTSTRAP_SERVICE_TIME_BASIS_V1` record from the two
original service responses. It reuses their complete bootstrap identity/freshness
validation, not an ordinary FULL/Desktop budget or a caller-supplied service
summary. It reads no clock/file and selects no job duration, reserve, deadline,
productive allocation or execution owner.

Its integer-only translation is:

```text
jobStartBasisNs = original_jobs_request_started_ns
    - (original_jobs_Date_epoch - original_job_started_at_epoch + 1 + 60 + 5) * 1000000000
```

The unchanged charges are Date quantization1 second, maximum service-cache60
seconds and clock margin5 seconds. Absent/zero Age and max-age0 do not discount
them. The anchor is the original **jobs request start**, not the attempt request,
response finish, retention or a later observation. Unsigned overflow/underflow
refuses without clamping or selecting a new epoch; exact zero is representable.
This is a conservative service-Date translation under the existing clock policy,
**not an observed native job start**, HTTP Date correctness, cross-boot/suspend
qualification or measured scheduling fit.

The basis binds the original admission/source/run/cohort, complete role/domain/
frequency identity, invocation, exact response hashes, selected service job and
fixed policy. `validate_basis` rederives and compares exact canonical bytes;
matching copied records still cannot attest their provenance. Reserialized or
changed responses cannot validate an earlier basis even when parsed fields agree.

The existing original-chain reader now retains and rederives mandatory
`originalChain.serviceTimeBasis`; preparation, read-only adoption and entry
consumption carry it unchanged. Only the existing `revalidatedNs` observation
may advance. Older source-generated chains missing this nested versioned record
remain historical evidence, but this changed reader **rejects** them: it does
not backfill, migrate or rewrite originals. All original owner/step/source
admission requirements and original75/local45/original120 bounds remain.

Budget remains `NOT_ADMITTED`, tests `NOT_PERFORMED`, export/save authority false.
The proposed5,400 seconds is still unadmitted/unmeasured. A separate productive
owner and complete bounded allocation, live native qualification and trusted
workflow outcomes remain necessary before any producer/export/provider action.

### Canonical producer records, not producer execution

[`hosted_cache_bootstrap_producer.py`](../../scripts/hosted_cache_bootstrap_producer.py)
adds a dormant **pure request/observation contract**, not a producer launcher.
The request binds the original bootstrap admission and canonical context, one
invocation and its existing ancestor chain, exact configuration-only request,
canonical enforced arguments and same-home stop. It has no timeout or budget.
It does not instantiate the ordinary controller or relax the seed/export/save
execution refusal above.

The observation requires the original prelaunch `start.json`, terminal canonical
`receipt.json` and separately supplied original process exit. It checks source,
home/job/invocation, unchanged start fields, typed successful product/stop/final
exits, and the corresponding native launch declarations. Windows batch framing,
suspended job assignment and temporary-resource records are separate from POSIX
argv and Darwin's original drain dispositions. These are consistency checks of
supplied records, not native execution or authentication of a supplied System32
path. Complete original records are hash-bound; reserialized or replaced records
cannot validate an earlier observation even when their parsed fields agree.
Darwin terminal discovery and per-drain signal histories must have the native
supplier's resolved dispositions; an empty error list or a later quiet drain
cannot conceal unresolved terminal records. Earlier observation failures remain
in the original history even when their access uncertainty was later reconciled.

`CANONICAL_CONFIGURATION_REPORTED_SUCCESS` explicitly leaves test acceptance
`NOT_PERFORMED`, enclosing native retirement `NOT_OBSERVED_HERE`, budget
`NOT_ADMITTED_HERE` and export/save authority false. The canonical report cannot
observe the enclosing controller's subsequent close/return. UTC labels and
duration metadata do not establish shared-clock deadlines; empty reports prove
no tests or dependency population. Errors still require failed-original custody,
not disposal. Live re-admission, source/native/toolchain and original-budget
binding, known complete enclosing retirement, positive empty-seed export,
freeze/provider/custody integration and separate sealing remain necessary.
No caller invokes this helper in production.

## Connected consume and delivery path

After the unchanged HOLD and native/source admission, `prepare-consume` binds
the original service-job timing, run/attempt, source commit/tree, native role,
owned staging identities and exact consume plan. The Actions-read token is
scoped only to that preparation, not to the product, restore guard or seal.

The pinned standalone restore uses only that plan's path/key, no fallback/save,
and a 1–3-minute timeout floored from its original bounded window. A separate
`restore-guard` requires the original successful outcome, exact primary/matched
keys and literal positive hit. `run --consume-dependencies` then re-admits those
originals and copies only allowlisted, exact-SHA-256 files into the fresh H. It
requires **positive admitted bytes**: an exact provider label, empty directory
or zero-byte inventory cannot become a qualified dependency cohort. Missing,
failed, changed or unqualified restoration fails; it never silently cold-builds
or switches to bootstrap. This is byte admission, not proof Gradle reused them.

Preparation, restoration and seed originals join the single encrypted evidence
packet. Separate post-return sealing and before/after upload guards bind their
original outcomes/hashes and the [original job-clock chain](hosted-job-clock.md),
not refreshed allowances. FULL has no cache save or change to Central's final
credential screen or `post_screen_addition` inventory.

For ordinary Desktop, successful product retirement and custody collection/
uninstallation precede the owned sample-packaging phase. Packaging runs **before
the one evidence freeze/export**, so its command/retirement records and package
hashes are retained in that packet. The later `package-samples` entry point only
revalidates those original application/package bytes and writes guard metadata;
it does not rebuild or repackage after the seal. Desktop then Android (Linux
only) uploads require completed predecessor guards and share **one 180-second
sample window**, bounded by the original delivery deadline. Preview/sample-apps
and publication paths are separate and unchanged by this consume wiring.

## Shared bounded file custody

The exporter reuses the maintained allowlist parser, source lookup, exact
same-reader prehash/copy/readback and native POSIX/Windows ownership primitives.
It does not reverse-call `seed_home` with fictional contexts. The existing seed
keeps its properties-only fresh-H default. Only the explicit export destination
mode permits an empty root.

Required original inputs include the current stage and the completed canonical
seed receipt. They bind original H/S identities. Export refuses a seeded restore,
a changed container/home/stage identity, nonempty S, changed canonical properties,
unsafe selected files or unknown retirement. A real caller must first establish
that preceding producer workers have retired; the helper cannot infer that from
a supplied receipt or from an empty directory.

Only allowlisted regular files below `caches/modules-2/files-2.1` can be created.
No properties, init scripts, wrapper executable/distribution, resolver metadata,
build cache, logs, credentials or unrelated cache tree is copied. SHA-1 is only
a layout address; exact coordinate/name/SHA-256 grants byte admission.

Bounds remain **512MiB/file, 2GiB prehash and output, 120 seconds hard /90 seconds
to start new work**, plus bounded directory/inventory/receipt sizes. Rejected
candidates consume prehash budget. Each admitted file is copied exclusively,
synced, closed and independently read back before admission. Directory identity,
membership and final file stamps are rechecked. Any close uncertainty stays
UNKNOWN and stops further ownership operations under the existing policy.
Filesystem calls are not claimed real-time cancellable.

`KNOWN_EMPTY`, `KNOWN_PARTIAL` and `KNOWN_EXPORTED` describe only that bounded
snapshot. Partial export is honest; even a fully admitted zero-length artifact
does not establish nonempty population. Failure retains its partial inventory
on the exception; no partial result may become completed. Retained receipt
validation checks original semantics, **not later live H/S contents**. A future
provider caller must independently recheck the frozen save set before and after
its action; receipt validation alone cannot authorize saving modified bytes.

### Dormant live save-set observations

`save_set` supplies that read-only file check, but has **no workflow/provider
caller yet**. Given the original positive export and original stage/seed/context/
admission bytes, it checks the original container and S, the exact complete
file/ancestor-directory roster, and every exported destination identity, stamp,
size and SHA-256. It also checks the actual original `staging.json` beside S.
That receipt is not part of the saved prefix. Unexpected files, even empty
directories, aliases, replaced ancestors and unsafe file kinds fail closed.

The first observation records directory metadata after export; export receipts
do not contain an earlier directory-stamp baseline. The after-save observation
requires the **original retained before-save bytes**, unchanged input hashes and
unchanged live directory/file bindings. A coherent replacement of the export or
context is not the original receipt. A record supplied by an untrusted caller
cannot authenticate itself; original-byte custody still belongs to the eventual
controller and separate seal.

Traversal streams per-file reads, keeps live handles depth-bounded, freshly
enumerates directories and reopens members for final metadata checks. It does
not use the Windows aggregate `Snapshot` (whose 576MiB limit is smaller than
the dependency cohort). Existing 512MiB/file, 2GiB dependency-byte, 10,000-member,
4MiB receipt and 120-second hard/90-second new-work bounds remain. Each pre/post
observation needs its own admitted interval; neither may precede its original
export/frozen predecessor or extend the relevant job cutoff. Backward clocks,
late validation and unknown closes cannot publish success. The helper retains
its final observed clock high-water; the caller must also bind return/retention.

A positive **partial export** can be frozen only as its exact completely checked
subset. A partially checked set, empty export or zero-byte cohort cannot pass.
`KNOWN_FROZEN` / `KNOWN_UNCHANGED` describe these observations, not complete
dependency population, a cache entry or resolver reuse. Closed pre/post checks
are not an atomic filesystem snapshot or proof of the bytes an external action
archives between them. Original producer success, same-home stop, loader removal,
worker retirement, provider custody/outcomes and inter-step timing remain the
separate bootstrap caller's obligations. No deletion or cleanup authority is
added by this helper.

## Provider observations are not provider execution

The selected standalone pair is
`actions/cache/{restore,save}@caa296126883cff596d87d8935842f9db880ef25`, with no
fallback keys or cross-OS archive. It uses Node24 and needs a compatible hosted
runner (upstream minimum 2.327.1). There is no automatic post action in this
contract. Only restore is connected behind the HOLD; save/probe orchestration
is dormant. This pin is ordinary supplier selection, not an independent
source-to-bundle or toolkit/extraction audit.

`provider_observation` accepts explicit original step outcomes and a closed
output roster. It never reads workflow environment variables or calls Actions.

- Restore/probe requires original **success**, `cache-hit == "true"`, and
  byte-equal expected/primary/matched keys to report an exact hit. The primary
  key alone is provisional. `fail-on-cache-miss` is not an exact-match gate;
  provider early returns and inexact matches still need the explicit checks.
- Blank/false outputs mean **no qualified exact hit**, not demonstrated backend
  absence or a diagnosed network error. Failed/cancelled/skipped/missing original
  outcomes cannot qualify otherwise convincing outputs.
- Standalone save declares **no outputs**. Even success may mean no write;
  no cache ID, saved flag, upload or population proof is invented.
- A genuine successful exact lookup-only probe would report presence, not the
  entry's creator, contents, extraction, durability, later resolver reuse or
  measured bandwidth saved. The pure fixtures do not even establish that probe.

Each observation binds the whole original plan hash, so a reusable key is not
permission to reuse another source/run/attempt's result.

## Verification and remaining qualification

Focused offline commands (not a claim they ran on a particular host):

```bash
python3 -I -B -S scripts/tests/hosted-cache-bootstrap-identity-test.py
python3 -I -B -S scripts/tests/hosted-cache-bootstrap-cohort-test.py
python3 -I -B -S scripts/tests/hosted-cache-bootstrap-producer-test.py
python3 -I -B -S scripts/tests/hosted-cache-bootstrap-query-fence-test.py
python3 -I -B -S scripts/tests/hosted-cache-bootstrap-origin-test.py
python3 -I -B -S scripts/tests/hosted-cache-bootstrap-handoff-test.py
python3 -I -B -S scripts/tests/hosted-cache-bootstrap-entry-test.py
python3 -I -B -S scripts/tests/hosted-cache-bootstrap-service-time-test.py
python3 -I -B -S scripts/tests/hosted-dependency-cache-test.py
python3 -I -B -S scripts/tests/hosted-dependency-seed-files-test.py
python3 -I -B -S scripts/tests/check-hosted-test-composition-test.py
python3 -I -B -S scripts/tests/hosted-consume-delivery-test.py
python3 -I -B -S scripts/tests/hosted-desktop-job-budget-test.py
```

These use modeled provider/native boundaries and tiny synthetic owned files, no
dependency download or Gradle. The connected/budget controls are registered in the
unconditional ordinary CI policy step and both release script entry points.
The separate bootstrap identity/cohort/producer-record/query-fence/original-acquisition/
handoff/entry/service-time controls are standalone, not an activated or registered
bootstrap workflow.
Tiny private-file controls require an actual ordinary UID; root is not an
acceptable substitute and their modeled native boundaries are not host admission.
Native Windows provider behavior and actual resolver/cache reuse require
separate genuine execution. Changes to shared executable suppliers also require
independent review of the explicit composition tripwire update.

Still required before activation: independent review of the connected revision,
native clock/ownership admission, a genuine exact populated restore and resolver
reuse, original receipt/export/seal and delivery acceptance, and measured fit
inside the unchanged 30/60-minute jobs. The bounded shared envelopes reject
exhaustion; they do not prove all operation maxima or a cold build will fit.

Bootstrap/save remains separate unfinished work. The planned path is a manual
**`CACHE_BOOTSTRAP_ONLY` sibling**, not a snapshot/save added to ordinary FULL
or Desktop. It needs a genuinely successful dependency producer, original
worker retirement, frozen-snapshot checks before/after the provider, retained
original observations and complete bounded allocation. Appending save/probe
timeouts is not scheduling proof. Its dependency-population result must not be
reported as FULL/product acceptance; an encrypted failed producer cannot grant
save authority. Ordinary FULL remains consume-only, with no change to its ABI,
Central credential screen or `post_screen_addition` contract.

Historical milestone: the initial cache-helper preparation had no connected
provider/source/outcome caller. The later consume-only wiring addresses that
source integration; it does not retroactively qualify the earlier models or
demonstrate cache execution/download savings.

Routine custodian/recipient policy and trusted-original-base approval, genuine
current required CI checks, formal nonauthor PR review and normal main delivery
remain separate requirements. No sample Release, issue closure or release-ready
claim follows from these helpers. Physical-phone work stays deferred.
