# Reviewed dependency update candidates

The custom dependency-maintenance custody/qualification workflow was retired on
2026-10-15 with the owner-approved [modular CI architecture](release-foundation.md).
Its source and historical results remain in Git history; they are not claims of
successful dependency generation or qualification. Routine maintenance no longer
requires C1/H1/C2/H2, an owner-only actor name, a special branch prefix, recursive
native custody, or the repository-global heavy-job queue.

## Exact-source generation, not automatic application

`dependency-update-candidate.yml` runs the unchanged maintained
`scripts/prepare-dependency-update.sh` on GitHub-hosted macOS. That command still
resolves the actual Gradle project graph, writes dependency locks/SHA-256
verification candidates, checks strict verification and approved plugin floors,
and runs the independent remote checksum/signature/provenance review. No
hand-written ten/fourteen-project graph substitutes for the real build.

A manually dispatched request identifies three immutable commits:

- **Controller:** `controller_sha` and `controller_tree`, matching the workflow
  ref and the clean controller checkout. It contains the reviewed adapter,
  generator/checkers and public evidence-recipient pins.
- **Candidate:** `candidate_sha` and `candidate_tree`, a separate reviewed, clean
  checkout with the desired build-source changes. Its maintained generator and
  checker files must equal the controller's. It may not have prewritten lock/XML
  changes relative to the dependency base.
- **Base:** `dependency_base_sha`, an actual ancestor of the candidate with its
  original tracked lockfiles and `gradle/verification-metadata.xml`. Any new
  tracked lockfile path must already exist in this reviewed base; generation
  cannot create arbitrary new tracked or untracked source paths.

For example, after independently identifying those exact public Git values:

```bash
gh workflow run dependency-update-candidate.yml --ref CONTROLLER_BRANCH \
  -f controller_sha=CONTROLLER_COMMIT -f controller_tree=CONTROLLER_TREE \
  -f candidate_sha=CANDIDATE_COMMIT -f candidate_tree=CANDIDATE_TREE \
  -f dependency_base_sha=DEPENDENCY_BASE_COMMIT
```

Repository dispatch permissions authorize this routine operation; it does not
need a separate personal-owner comment. A dispatch against different workflow
source is rejected. No generator is run merely because the dependency set is
unchanged. Foundation and an eventual RPC integration are different sources;
earlier Foundation evidence cannot qualify RPC's expanded graph.

## Evidence and allowed output

The small `scripts/dependency_update.py` adapter runs inside `ci_evidence.py` with
an **immutable controller** as the evidence source. Only the separate candidate
may change, and only its existing tracked lockfiles and verification XML. The
adapter rejects source/ref/tree drift, generator changes, staged/untracked files,
mode/link changes, removed checksums, or altered verification trust settings.
It attempts `gradlew --stop` even after generator failure; successful outer
owned-process cleanup is also required before public candidate upload.

The job has a three-hour command envelope inside a 210-minute workflow budget.
Real command failure, timeout, uncertain cleanup, or evidence encryption failure
fails the operation. Retrying is a new explicit run/attempt, not an overwrite.
There is no automatic commit, push, patch application, signing or publication.

Two immutable, 14-day artifacts use the original run ID and attempt:

- `dependency-evidence-RUN-ATTEMPT`: `manifest.json` plus
  `evidence.tar.gz.gpg`. Original stdout/stderr and selected reports are encrypted
  to the same independently pinned public recipient as modular CI. Failed
  generation retains this evidence when capture/encryption succeed. No private
  key or passphrase is available to CI.
- `dependency-candidate-RUN-ATTEMPT`: only `generated-dependencies.patch` and
  `generated-dependencies.json`, uploaded after successful generation and outer
  cleanup. The manifest records the exact controller/candidate/base, old/new
  file digests, patch digest, successful generator/Gradle-stop returns, and the
  count of newly verified artifacts. Its explicit scope is
  `DEPENDENCY_UPDATE_CANDIDATE_NOT_QUALIFICATION` and `releaseQualified` is false.

Review the complete patch, source identities, manifest/digests and encrypted
provenance results before applying anything. Apply reviewed bytes only to the
matching candidate source. After committing an accepted patch, run the normal
modular components on that **new exact source**. A generated candidate is not a
release qualification, a successful application build, or approval to publish.
The normal final merge, tag and protected publication approvals remain intact.

## Ordinary dependency graph submission

`dependency-submission.yml` uses the pinned standard
`gradle/actions/dependency-submission` action on canonical `main`, with the
reviewed Java/Android/Xcode setup and **strict** dependency verification explicitly
enabled (the action's permissive default is not used). Its graph is generated
from the real Gradle projects. It does not generate/apply update candidates or
replace the required modular dependency/security/platform checks. No custom
custody export, bootstrap artifact or context-qualification run is required.
