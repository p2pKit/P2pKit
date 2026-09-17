# Bounded hosted dependency-cache preparation

This is **dormant preparation**, not an activated cache, a successful hosted run,
or measured download savings. Both ordinary workflow activation HOLDs remain.
[`hosted_dependency_cache.py`](../../scripts/hosted_dependency_cache.py) has no
CLI, action runner, downloader, extraction, deletion or subprocess entry point.
Do not bypass the HOLD or restore an entire Gradle home to use this helper.

## Reuse bytes, not old test results

The explicit modes are:

- **Consume:** exact-key standalone restore into the original staging directory
  S, then existing strict file admission into a fresh canonical Gradle home H.
  No writeback. A missing/unqualified result does not silently select bootstrap.
- **Bootstrap:** original empty S, no restore, the existing known-empty seed and
  separately qualified product execution; then a bounded verified H-to-S
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
`make_plan` or `validate_plan` call checks supplied data; the future real caller
must independently admit the exact source, stage and actual original outcomes.

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
that preceding product workers have retired; the helper cannot infer that from
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

The prepared standalone pair is
`actions/cache/{restore,save}@caa296126883cff596d87d8935842f9db880ef25`, with no
fallback keys or cross-OS archive. It uses Node24 and needs a compatible hosted
runner (upstream minimum 2.327.1). There is no automatic post action in this
contract. This pin is ordinary supplier selection, not an independent
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

## Verification and remaining integration

Focused offline commands (not a claim they ran on a particular host):

```bash
python3 -I -B -S scripts/tests/hosted-dependency-cache-test.py
python3 -I -B -S scripts/tests/hosted-dependency-seed-files-test.py
python3 -I -B -S scripts/tests/check-hosted-test-composition-test.py
```

These use declared provider outputs and tiny synthetic owned files, no dependency
download or Gradle. Native Windows provider behavior and actual resolver/cache
reuse require separate genuine execution. Changes to shared executable suppliers
also require independent review of the explicit composition tripwire update.

Still required before activation: real source/outcome binding and explicit mode
routing, bounded provider operations, frozen-snapshot checks, separate original
receipt retention/seal integration, and complete allocation inside the unchanged
30/60-minute job limits. Appending save/probe timeouts after an already-full job
budget is not scheduling proof. FULL's snapshot belongs after known prior
producer/Swift retirement and **before Central's final credential screen**; do
not expand `post_screen_addition` to admit a late arbitrary receipt. The actual
successful profile and seal must gate save; an encrypted failed profile is not
a successful producer.

Routine custodian/recipient policy and trusted-original-base approval, genuine
current required CI checks, formal nonauthor PR review and normal main delivery
remain separate requirements. No sample Release, issue closure or release-ready
claim follows from these helpers. Physical-phone work stays deferred.
