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
python3 -I -B -S scripts/tests/hosted-dependency-cache-test.py
python3 -I -B -S scripts/tests/hosted-dependency-seed-files-test.py
python3 -I -B -S scripts/tests/check-hosted-test-composition-test.py
python3 -I -B -S scripts/tests/hosted-consume-delivery-test.py
python3 -I -B -S scripts/tests/hosted-desktop-job-budget-test.py
```

These use modeled provider/native boundaries and tiny synthetic owned files, no
dependency download or Gradle. The connected/budget controls are registered in the
unconditional ordinary CI policy step and both release script entry points.
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
