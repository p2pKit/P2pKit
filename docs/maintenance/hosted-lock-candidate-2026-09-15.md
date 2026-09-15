# Encrypted hosted lock candidate — 15 September 2026

This implements the [previously researched route](hosted-lock-route-2026-09-15.md).
The owner subsequently authorized encrypted evidence delivery, with the private
key kept only on the Mac. That permission does not authorize raw-log publication,
production releases, bypassed reviews/checks or physical-phone work.

**Subsequent execution:** the one authorized dispatch has now completed:
[run 35007680254 failed before Gradle; encrypted failure evidence was retained](hosted-lock-result-2026-09-15.md).
The source/offline checkpoint below predates that run. Its dispatch recipe is not
permission for another attempt; no automatic retry is authorized.

**Source/offline implementation is not a successful hosted writer.** At this
checkpoint all twelve locks and verification metadata are unchanged; six locks
still contain removed upstream JmDNS membership. The failed/cancelled sample run
[34978847218](https://github.com/p2pKit/P2pKit/actions/runs/34978847218) has zero
artifacts. The reviewed Windows allocation correction remains at
[`614e534`](https://github.com/p2pKit/P2pKit/commit/614e5344b6161ff4adeb5ec27a2bba267326e815),
without a genuine post-fix Windows result. Do not reimplement it or rerun the
unchanged failing sample matrix.

## One isolated operation, not a release bypass

The existing [Desktop workflow](../../.github/workflows/desktop-cross-host.yml)
adds the manual `dependency-lock-candidate` operation. It cannot fall through to
the ordinary sample matrix or publisher. It uses the existing non-cancelling
heavy-job queue, a read-only token, full-history exact-SHA checkout without
persisted credentials, `macos-26` and explicit Xcode 26.5 (`17F42`). Normal sample
tasks and publisher authority are unchanged.

The [controller](../../scripts/run-hosted-lock-candidate.py) requires the actual
workflow/job/event/run/attempt/ref, exact source SHA/tree and an independently
reviewed base **equal to that new source SHA**. An older reviewed controller commit
is not the base for changed controller inputs. The maintained operation remains:

```sh
scripts/prepare-dependency-update.sh <exact-reviewed-controller-source-SHA>
```

It is the complete mutable writer, including its check/Dokka/SBOM graph, strict
postchecks and provenance classifier/curator. No hand-edited locks, reduced task
graph, obsolete dependency restoration, immutable-leaf impersonation or automatic
retry is introduced. Successful generation still requires independent review of
the complete candidate and actual original evidence.

Before any dependency acquisition, the controller validates the recipient and
admits installed native JDK 17/21, literal SDK 36/37.0, Xcode first-launch status,
the actual iOS 26.5 runtime and one originally Shutdown iPhone 17 simulator. It
runs the maintained native ownership controls, then compiles current vendored
JmDNS sources for the existing narrow `control` fixture. That control is **not**
the eight-mode #410 acceptance campaign. No phone is used.

The child-only credential boundary starts from a finite environment allowlist,
with isolated Git/GH/curl/GPG configuration and no inherited token/agent hooks.
It leaves the parent's SSH agent untouched. HOME is retained for CoreSimulator;
this is **not a hostile same-user sandbox**. The old no-child collector's
`SSH_AUTH_SOCK` rejection remains historical and unresolved, not relabeled a pass.

## Resources, failure and custody

- No local writer, SDK installation or local dependency-cache upload is involved.
  GitHub's installed tools are admitted, not replaced. The first SLF4J fetch is
  hash-pinned and capped at 1 MiB; the complete writer may acquire its remaining
  dependencies once. Automatic JDK download is disabled.
- Two workers, no parallel Gradle, bounded heap and in-process Kotlin remain.
  Admission requires NORMAL pressure and 16 GiB free disk. Ongoing checks retain
  a 7 GiB disk floor and abort at 1 GiB cumulative swap growth or 8 GiB sampled
  inbound growth. Independent fast/network lanes are checked for freshness.
  These are **sampled guards, not hard filesystem/network quotas**, and do not
  promise zero downloads or sustained capacity before actual execution.
- Original command, stop and stream outcomes stay separate. Private streams have
  finite limits; an exceeded limit records incomplete prefix custody and fails,
  never silently truncates a passing result. Cleanup has a separate stream budget.
- The #424 allocator reserves the actual writer/stop native IDs for both classes.
  Collection is unconditional after stop/drains; missing reports/exports or
  uncertain retirement stay HOLD. Current expected counts are 9 CLI and
  23 diagnostics methods, with two/four original exports—not execution results.
- Recovery uses each command's persisted **original pre-launch process baseline**,
  bound into its launch record. A new process census would incorrectly hide
  already-running orphans. Fresh lifetime/domain/audit-token checks still govern
  signaling; missing or changed baseline after launch blocks sealing. Recovery
  never invents original writer/stop success or upgrades original UNKNOWN records.
- Independent retention stages preserve all twelve before/after locks, metadata,
  original reports/custody, task/output maps, generated ABI/Dokka bytes and the
  actual embedded JmDNS producer. Producer hashes are compared with generated
  JSON/XML SBOMs. An interrupted owner uses a separate recovery directory rather
  than overwriting partial originals. Any such recovery remains HOLD.
- Stop only the same owned Gradle home and invocation-owned descendants; retire
  only the selected simulator. No source reset, shared-cache deletion or blanket
  simulator/process shutdown is permitted.

Job/step limits and the always-run seal step reserve a failure-retention path,
but **runner destruction, hard cancellation or failed sealing/upload can still
lose hosted private originals**. No successful durable custody is claimed until
the encrypted artifact is downloaded, authenticated/decrypted and inspected.

## Encrypted artifact and safe resumption

Only `encrypted/evidence.tar.gz.gpg` and a minimal `manifest.json` are eligible
for upload. The public manifest binds source SHA/tree, run/attempt and ciphertext
size/hash; it is not test acceptance. Archive limits are 512 MiB/10,000 members,
with ciphertext capped at 576 MiB. Keys must be public-only, valid and bound to
the exact recipient fingerprint; GPG cannot start an agent or use a keyserver.
Private cleanup may fail after ciphertext is produced: public validation also
requires the controller's **post-return private seal receipt**, never manifest
presence alone. The private key/passphrase must not enter dispatch, Git or logs.

After independent exact-diff review, reconcile active work, verify remote source
and recipient availability, and dispatch once. This is a recipe, not a run record:

```sh
SOURCE="$(git rev-parse HEAD)"
TREE="$(git rev-parse 'HEAD^{tree}')"
gh workflow run desktop-cross-host.yml --repo p2pKit/P2pKit \
  --ref work/nonphysical-integration-20260915-022112 \
  -f operation=dependency-lock-candidate \
  -f expected_sha="$SOURCE" -f expected_tree="$TREE" -f reviewed_base="$SOURCE" \
  -F evidence_public_key=@/absolute/path/to/recipient-public.asc \
  -f evidence_fingerprint="$PUBLIC_FINGERPRINT"
```

Read back the genuine run identity. Download its encrypted artifact before the
14-day expiry; validate the manifest/hash and decrypt privately with the retained
Mac key. Safely inventory the archive before extracting into a new private
directory. Inspect original exits, custody, all lock/metadata deltas, producer,
SBOM, generated ABI and provenance before accepting anything. A green upload is
not a green writer, and a green writer is not sample/release qualification.

Refs [#424](https://github.com/p2pKit/P2pKit/issues/424),
[#425](https://github.com/p2pKit/P2pKit/issues/425),
[#437](https://github.com/p2pKit/P2pKit/issues/437),
[#439](https://github.com/p2pKit/P2pKit/issues/439). Their current conversations own
subsequent execution/review/closure decisions. Remaining sample builds, current
OSV/submission, required CI, formal independent PR review, normal main merge and
development-prerelease readback are not waived. Kotlin advisory
GHSA-r937-wjx7-w2jp remains **EXCEPTED_NOT_FIXED**, expiry **2026-10-31**.
Historical approval credit remains **206/234**; the refreshed issue census was
**61 open issues**, separately. Whole audit/release remains **NOT_READY**.

## Source/offline review checkpoint (before hosted dispatch)

At **2026-09-15T18:23Z**, an independent reviewer who implemented none of this
change approved the scoped source/offline integration. Review found and resolved
the orphan-recovery baseline defect and missing generated-producer retention.
The separate encryption/workflow review was also independent. Neither verdict
is a formal GitHub PR approval, native execution, accepted locks or issue closure.

The frozen controller SHA-256 is
`626dda80b4e9124a72d589bea84bf99ea2c8861c205a03e2b0979c74a4b70415`;
its test is
`a43c1e13c245a7ec981f38ca25ed92c2a71dfaaf988b8170ba6fa077fb5e815d`.
The containing commit records the candidate above parent `e5d0485`; the later
dispatch must use that new full commit/tree, not the parent. Private independent
review-report SHA-256:
`597c1efaa231038838847943899d1b5190aa65d374f1dfcc343293e4995faa5e`.

Actually executed on local ARM macOS, using installed Xcode Python 3.9.6
(`-I -B -S`) and Ruby 2.6.10:

| Command/check | Result and limit |
| --- | --- |
| `python3 -I -B -S scripts/tests/run-hosted-lock-candidate-test.py` | Independent **82/82 PASS**; native/GPG/network calls mocked. |
| `python3 -I -B -S scripts/tests/hosted-lock-resources-test.py` | Independent **19/19 PASS**; synthetic resource samples, not real host capacity. |
| `ruby scripts/tests/check-hosted-lock-candidate-policy-test.rb` | Independent **285 PASS**; workflow/entrypoint policy, not scheduler execution. |
| `scripts/tests/check-repository-layout.sh`, `scripts/tests/check-markdown-links.sh`, `scripts/check-release-metadata.sh` | PASS, including 468 relative links across 97 active Markdown files. |
| `scripts/tests/check-osv-lockfile-coverage.sh` | PASS for ten populated locks and upstream inventory; **not an advisory scan**. |
| Checkout policy, heavy-job queue policy, CI-scope policy | PASS; CI-scope suite has 21 controls. |
| Python AST, Ruby/shell syntax, changed-workflow YAML parsing, staged/unstaged `git diff --check` | PASS; not compilation or a full release gate. |

The earlier independent 28-test encryption packet includes real throwaway-key
decryption and integrity checks. It is reused after checking unchanged executable
crypto bytes; only its overly broad failure-cleanup docstring changed. Current
controller regressions cover the required post-return seal. The unchanged
queue/Mac/Windows/sample policy and parser packets are reused with source hashes;
the earlier 124-check hosted-policy result is superseded by 285, not counted as
current proof. Actionlint 1.7.12 still exited 1 for four unsupported `queue` keys:
**not a lint pass**.

No local Gradle, dependency download or device was started for these controls.
Synthetic fixtures retired; private original logs/source bindings remain retained.
The real Gradle initializer, native controls, JmDNS probe, complete writer and
encrypted hosted retrieval are **unexecuted at this checkpoint**. The full
release/workflow shell gates were not run. All earlier runtime/merge/closure holds
remain; subsequent execution belongs in a separate source/run-bound record.
