# Owner-controlled development sample delivery — 20 September 2026

This dated source/configuration continuation supplements the preserved
[17 September checkpoint](nonphysical-checkpoint-2026-09-17.md), not a new audit
or a Release acceptance. Base: **`8cefc111dafb811ea8453c7e8a50f54c10449f82`**,
tree **`9cd55c72cf48e6d16a77524f2bb848ba4608b0fd`**, on
`work/nonphysical-integration-20260915-022112`. Original checkpoint ancestry
remains preserved. The containing commit and final review mapping belong in
[#437](https://github.com/p2pKit/P2pKit/issues/437), with the shared ordinary
custody boundary also linked from [#424](https://github.com/p2pKit/P2pKit/issues/424).

## Owner decisions, not fabricated approvals

The owner authorized `Apdelrahman1911` (API-verified user ID **`104788132`**) as
routine evidence custodian, a new passphrase-protected OpenPGP key on this trusted
VPS, 14-day Actions-only encrypted evidence retention and public **unencrypted**
development app assets. The approved label is
`P2pKit CI evidence (Apdelrahman1911)`; expiry is
**`2027-09-21T00:00:00Z`**. No email or second account is invented.

GitHub cannot accept a native `APPROVED` review from a PR's author. The owner
explicitly accepted a personally posted exact-head authorization instead:
`/p2pkit approve-pr <full-final-PR-head-SHA>`, after required PR checks and before
the manual preserving merge. The actual main merge commit must contain the
case-sensitive marker **`[release ci]`**. Normal required CI is not disabled by
omitting it. A second personal approval follows review of the actual main-run
evidence, before publication. Neither approval may be supplied by the agent.

The [custodian procedure](../testing/evidence-custodian.md) gives the exact key,
retention, trust/bootstrap and approval requirements. It supersedes only this
ordinary-CI/sample lane's older different-account and long-term-storage policy,
not historical results or external/physical evidence requirements. It does not
authorize production/Maven/Store publication, auto-approval/merge, or HOLD removal.

## Publisher and post-build approval implementation

Affected source: [`publish-sample-release.py`](../../scripts/publish-sample-release.py),
its [focused tests](../../scripts/tests/publish-sample-release-test.py), the
[sample Release workflow](../../.github/workflows/sample-development-releases.yml)
and its [workflow controls](../../scripts/tests/sample-release-workflow-test.rb).

- PR author and manual merger bind the exact owner login/ID. The owner comment
  binds the preserved final head, belongs to that PR and is **recorded-unedited**
  (`created_at == updated_at`), following all required checks and preceding merge.
  Unresolved formal change requests and every existing required check still block.
  This enforces publisher admission, not a new native merge-button rule.
- The publisher fetches the actual main commit message and refuses absent or
  differently cased markers. PR prose and earlier branch commits are insufficient.
- It binds the exact three native Desktop encrypted artifacts plus the FULL
  artifact from main's exact `complete-gate` run/attempt, including original API
  digests, availability and retention no longer than 14 days. **This is metadata
  binding, not ciphertext/decryption/internal evidence inspection.**
- Read-only `prepare-review` inspects application bundles and uploads four public
  metadata files as `sample-release-review-<publisher-run>-<attempt>`. The publish
  job waits on `sample-development-release`. The owner's approval comment must
  be the generated `APPROVE_EVIDENCE <publisher-run>/<attempt> <request-sha256>`.
- Publication checks actual Actions approval history, owner/environment, request,
  run/attempt, original artifacts/checks and inspected app-manifest bindings again
  before mutation. Manual publication and reruns cannot reuse a prior challenge.
  The record is an owner attestation, not automated proof of human decryption.
- Only `publish` has `contents: write`; `verify` remains read-only. No private
  evidence enters the Release. Existing immutable-tag/asset and partial-draft
  protections remain. Credential-free one-byte asset probes check public access;
  they are **not a second full anonymous byte/hash comparison**.

Independent R1 found a pre-merge-edited comment could incorrectly inherit its
original author's identity. The source now requires a fresh, recorded-unedited
comment; corrections require a new owner post. The original R1 diagnostic and
R2 refusal were retained, not rewritten as a first-pass success. Final verdict:
**`APPROVE_EXACT_PUBLISHER_OWNER_APPROVAL_R2_SOURCE_ONLY_NOT_RUNTIME_QUALIFICATION`**.
Independent report SHA-256:
`0fa29938564cffca2117b8de894e1f02220cbe2198d3abc7efc7d93547767583`.
Author R2 **48 tests PASS**; the **27 unchanged R1 workflow controls** are reused
only within their exact unchanged source scope. The independent R2 harness
confirmed the original edited-comment counterexample is refused. No actual
GitHub deployment approval or publication was exercised.

## Desktop producer marker implementation

The separate 14-file source batch covers `hosted_test_identity.py`,
`hosted_test_query.py`, `run-hosted-test-admission.py`,
`run-hosted-test-custody.py`, `desktop-cross-host.yml`, the two ordinary/sample
workflow policy scripts and their focused identity/query/controller/budget/
consume-delivery/workflow tests.

- Only native-admitted Desktop **main push**, exactly two commit parents and
  the actual immutable commit message can request Release packaging. A bounded
  read-only Git query adds only `show -s --format=%B <full-SHA>` with a 64KiB cap;
  query count/deadlines and credential boundaries are unchanged.
- The typed `samplePackagingRequired` decision is retained with admission and
  emitted as fixed `sample_packaging_required=true|false` only after the native
  admission call returns. Workflow consumers additionally require step success.
- Both marked and unmarked ordinary Desktop keep **all six normal tasks**,
  including `installDist` and `createDistributable`. Only marked main adds
  Release APK/native installer packaging, APK SDK acquisition and sample uploads.
  Original admitted intent, selector, packaging/frozen result and separate seal
  are rechecked; a caller cannot request packages by changing an output alone.
- Ordinary encrypted evidence and terminal delivery checks remain mandatory
  without samples. Unmarked runs require sample-output/SDK steps to be skipped,
  not silently considered successes. The explicit historical `sample-apps`
  manual preview stays separate and cannot qualify main publication.
- FULL ABI/simulator/transcript behavior, ordinary 30/60-minute jobs, product/
  outer limits, the Windows 900-second file lifetime and both literal HOLDs stay.

Independent verdict:
**`APPROVE_EXACT_DESKTOP_MERGE_MARKER_R2_SOURCE_ONLY_NOT_RUNTIME_QUALIFICATION`**,
no actionable finding. Report SHA-256:
`f4a6ac93c41875db2622791aa6c424eb3ddb921c3a44360c35a31c15be0f1d68`.
The exact 14-file patch SHA-256 is
`b3728abe6cb883440def20d03bd295e19141cde0cfa74108dab9e4187396548d`.

The review explicitly approved only the controller AST expectation in
`scripts/check-hosted-test-composition.py`, from
`eed36ef0e3b814ccdf4e1755ea4162a7ebd5caeb20833ab9a5ed326f8f2c116b` to
`e0c4a4aa8c742643253a8e9e47928f8c249837b00f3ffcd2fd8329d0cf29aee2`,
binding controller file SHA-256
`835b051a2c80958b2d9b8f6bb9c1c5e81c02d572b5ef3b0b1554c81ae72eeff5`.
That update was applied **after review**, with the six other supplier pins
unchanged; the source policy and all 34 composition controls then passed.

Independent initial aggregate: **seven logic controls PASS, one harness failure**.
The reviewer environment-key extractor omitted numeric `ORDINARY_JDK21`; this was
not a candidate finding. The original failure remains retained. Correcting only
that extractor, the targeted terminal control passed **66 bounded actual shell
cases**; the seven passing logic controls were not rerun. These independent
UID0 memory/shell controls are not ordinary-UID/native privacy qualification.

## Actually executed offline controls

These are bounded Python/Ruby source, synthetic-shell and model controls, not
Java/Gradle/Xcode/app builds. Query/consume/controller private-file tests used an
isolated source snapshot under actual ordinary Linux UID1000 (`ubuntu`); native,
network, GitHub and process boundaries were modeled and file fixtures were tiny.

| Command under `scripts/` | Retained result |
| --- | --- |
| `python3 -I -B -S tests/publish-sample-release-test.py -v` | R2 **48 PASS**; API/ZIP models, not real publication |
| `ruby tests/sample-release-workflow-test.rb` | R1 **27 PASS**, reused unchanged in R2, not rerun |
| `python3 -I -B -S tests/hosted-test-identity-test.py -v` | **44 PASS** |
| `python3 -I -B -S tests/hosted-test-query-test.py -v` | Final R2 **44 PASS**; both boolean CLI output cases covered |
| `python3 -I -B -S tests/hosted-desktop-job-budget-test.py -v` | **24 PASS** |
| `python3 -I -B -S tests/hosted-full-job-budget-test.py -v` | **39 PASS** |
| Selected `tests/hosted-test-controller-test.py` below | **24 PASS**, not its entire suite |
| `python3 -I -B -S tests/hosted-consume-delivery-test.py -v` | **59 PASS** |
| `ruby tests/check-sample-app-workflow-policy-test.rb` | **155 PASS** |
| `ruby tests/check-hosted-test-workflow-policy-test.rb` | **547 PASS**, offline policy/synthetic-shell scope |
| `ruby check-sample-app-workflow-policy.rb`; `ruby check-hosted-test-workflow-policy.rb` | Both source policies **PASS** |
| `python3 -I -B -S check-hosted-test-composition.py`; `python3 -I -B -S tests/check-hosted-test-composition-test.py -v` | Source tripwire **PASS**, **34 AST controls PASS**, no supplier execution |
| `python3 -I -B -S tests/hosted-controller-import-test.py -v` | **4 PASS**, cold import/modeled missing-native APIs; no native execution |
| `bash tests/check-repository-layout.sh` | **PASS**, 10 project mappings / 15 SDK negative controls |
| `bash tests/check-markdown-links.sh` | **PASS**, 655 relative links / 130 active Markdown files; no remote-link or anchor check |
| `bash tests/check-osv-lockfile-coverage.sh` | **PASS**, 10 nonempty locks plus verified upstream inventory; not an OSV run |
| `bash check-release-metadata.sh`; `git diff --check` | Both **PASS**; unchanged snapshot/RC3 metadata and whitespace |

The exact 24-case selected controller command was:

```bash
python3 -I -B -S scripts/tests/hosted-test-controller-test.py \
  ContractModels FinalizationModels \
  WholeControllerModels.test_desktop_whole_composition_and_post_return_seal_pass_in_model \
  WholeControllerModels.test_seed_full_model_preserves_primary_supplement_abi_simulator_and_clock_contracts \
  WholeControllerModels.test_full_guard_before_and_after_share_exact_frozen_upload_cap \
  WholeControllerModels.test_full_upload_expired_absolute_cap_cannot_be_renewed_by_after_guard \
  WholeControllerModels.test_full_upload_tampered_cap_refuses_even_with_matching_new_hash -v
```

The final query/budget/controller invocations each had an external 120-second
wall limit and five-second kill grace; all completed normally. Final query
source differs from R1 only in focused CLI-output test coverage and an accurate
`fsync`-failure test name. Do not sum reused and repeated commands as new product
coverage. None establishes native/provider/cache/resolver, scheduling or hosted
encryption/retention/delivery acceptance. Private source-test originals and
review packets are retained outside Git; hashes/public summaries are not those
originals. The final documentation/tripwire delta receives a separate accuracy
review; neither implementation verdict above automatically approves it.

## Configuration readback and unapplied key policy

GitHub readback on 20 September still has main
**`3bc76f956f8f47447b51a62474fc878b9c43173c`**, tree
**`2a1105fde1d1ac299448489501e29d7a0d4a407a`**. Required checks remain
`complete-gate`, `review`, `scan / osv-scan`, `osv-scanner`, with strict checks
and thread-resolution rules. Native required approving-review count was already
zero; no branch rule/check was changed. The unattributed-change protection is
unchanged. Seven dependency PRs remain separate; no campaign PR or queued/running
Actions was observed. All 79 #437 comments were refreshed and unchanged from
the earlier implementation read; #424's complete 72-comment conversation was
also refreshed. Dated fixture acceptance is not described as unexecuted.

Authorized configuration writes created only the isolated sample environment:

- **`sample-development-release`**, ID **`22338522000`**;
- sole required reviewer `Apdelrahman1911` / `104788132`;
- `prevent_self_review: false` so this owner may approve the deployment;
- exactly one custom branch policy, **`main`**, type `branch`, ID **`60503975`**.

**`can_admins_bypass` still reads `true`**. The available documented environment
REST/GraphQL update inputs did not expose that setting; no successful update is
invented. The owner must disable **Allow administrators to bypass configured
protection rules** in the environment UI. The publisher requires readback `false`
and refuses the current environment. No secret, deployment, approval or workflow
run was created. The existing `maven-central` environment was untouched.

No key or private backup was generated, and no key directory was created. The
documented unused VPS destination is
`/root/.local/share/p2pkit/evidence-custodian/2026-09-20/`; generation needs the
owner's private SSH/pinentry session. The agent has no verified private passphrase
channel. The exact GPG recipe is documented, **not executed or recovery-tested**.

The announced recipient-admission window is inclusive
**`2026-09-21T00:00:00Z`** through exclusive **`2026-10-05T00:00:00Z`**, with
`retentionDays: 14`; it is **unapplied**. Artifact expiry is independently based
on each actual upload's service timestamps, not this window or the key expiry.
`.github/test-evidence-recipient.json` remains absent. Real public key/fingerprint/
hash, owner confirmation and legitimate trusted-original-base bootstrap/normal
delivery remain necessary. Candidate source cannot authorize its own recipient;
the JSON selects FULL, not a Markdown-only shortcut around the circular prerequisite.

## Remaining execution and delivery acceptance

1. Owner privately generates/verifies/retains the real key, and the exact public
   policy reaches a legitimate trusted base without bypassing checks or HOLDs.
2. Environment administrator bypass is genuinely disabled and read back.
3. The [provider execution gap](../testing/hosted-dependency-cache.md#provider-execution-gap--20-september-2026),
   bootstrap failure-custody/export/freeze/seal/delivery/wiring, actual populated
   cache/resolver/native qualification and measured scheduling remain unfinished.
   The 5,400-second proposal is unadmitted/unmeasured; Windows NativeFile900 and
   Snapshot576MiB are unchanged. No guessed provider evidence is added here.
4. The applicable current PR checks, owner exact-head authorization and normal
   marked merge must actually succeed; then genuine main producer/FULL/OSV
   qualification and independent original-evidence inspection must succeed.
5. The owner's fresh post-build evidence approval is required before any public
   development prerelease. Publication/readback/anonymous access and preservation
   must be verified before claiming delivered apps or closing accepted issues.

Accepted preview **35070982169** and #424 writer **35066719641/1** (CLI9 /
diagnostics23, six inspected original exports) were not rerun or redownloaded.
Preview artifacts expire 30 September; they are not main Releases. No #372
Android runtime or unexecuted Kotlin tests are promoted by this work. Physical
phone/tablet work remains deferred. AGENTS.md, CLAUDE.md, published RC3,
compatibility restrictions and unrelated branches/dependency proposals remain
unchanged. No production/Maven/Store publication is authorized.

`osv-scanner.toml` still excepts **GHSA-r937-wjx7-w2jp / CVE-2026-53914** through
**2026-10-31**; Kotlin 2.4.10 remains affected. No remediation, exception extension
or new scan is claimed. Historical accounting stays **206/234 repair-approved**,
**207/234 historically resolved**. **Audit/release: NOT_READY. Apps have not been
delivered to repository Releases by this source work.**
