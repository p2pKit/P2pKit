# Review-only core API candidates

Use **Prepare core API candidate** (`prepare-api-candidate.yml`) for an intentional
`p2p-core` public API change, not to make an unexplained compatibility failure green.
Select the reviewed dispatch ref and enter its **full lowercase 40-character commit
SHA** as `source_sha`. That value must equal both the workflow SHA and checked-out
source SHA; a moving ref or mismatched revision fails before checkout.

For initial workflow discovery before merging, a temporary push trigger is limited
to branch `work/readiness-source-20261024-khnosw` and changes to this workflow file.
It runs only a two-minute-budget registration message on Ubuntu: no checkout,
generation, or artifact upload. Generation remains **explicit dispatch only** with
the full reviewed SHA. Once this workflow is present on the default branch, that
narrow onboarding trigger and registration job may be removed in a reviewed change.

The workflow uses credential-free checkout, the standard macOS 15 Intel / Xcode 26.3
setup, Java 21 and 17, and optional read-only Gradle caches. The helper creates a fresh
detached, job-owned worktree at that exact commit. It runs the existing wrapper and
dependency-policy checks, then only these generation tasks with strict dependency
verification and the existing locks:

```text
:p2p-core:updateKotlinAbi
:p2p-core:updateAndroidAbi
```

No lock/checksum writer, arbitrary task, shell input, publication, automatic commit,
or API application is offered. The source controller stays unchanged; the owned
generation worktree is removed after the attempt. An interrupted job may leave only
job-local temporary state, never an uploadable successful candidate.

## Outputs and review

After successful generation **and** encrypted evidence export, the review artifact
contains only `core-api-candidate.patch` (at most 4 MiB) and
`core-api-candidate.json`. The manifest records the exact input commit/tree, workflow
commit, fixed tasks, changed paths, each file's before/after SHA-256 and size, and the
patch SHA-256. Its scope is `CORE_API_CANDIDATE_REVIEW_ONLY`, never release qualification.
Successful unchanged generation is explicitly `UNCHANGED` with an empty patch.

Only these four existing baselines may differ:

```text
library/p2p-core/api/p2p-core.klib.api
library/p2p-core/api/jvm/p2p-core.api
library/p2p-core/api/android/p2p-core.api
library/p2p-core/api/android-bcv/p2p-core.api
```

Every file must be bounded, nonempty UTF-8 with the expected dump shape; Native must
include all three iOS targets. Other tracked changes (including locks/checksums),
index/mode changes, new untracked source, invalid API output, or failed generation
or Gradle shutdown prevent export. Ignored build outputs are not review artifacts.

The existing `ci_evidence.py` encrypts original stdout/stderr for the independently
pinned recipient and emits its source/workflow-bound manifest. The encrypted log
records the review manifest's SHA-256, binding the separate review files to that
execution. Diagnostic uploads contain only the existing evidence manifest,
ciphertext, or failure receipt, not plaintext logs. A failed generation or evidence
export must not be repackaged as a successful candidate.

**Generation is not compatibility approval.** Review the actual Native, JVM and both
Android views for the intended additive SPI/status change before applying anything
in a separate reviewed source change. Textual removals/replacements may expose
breaking changes and require deliberate review; the helper does not infer semantic
additivity from diff signs. Recheck the source SHA and file/patch hashes, then run
the normal ABI and compatibility gates on the reviewed resulting source. Never edit
historical release tags or claim release/device qualification from this artifact.
See [local ABI guidance](local.md) and the [compatibility contract](../compatibility.md).

If strict verification fails on a missing host dependency, use the separate reviewed
dependency-curation process; do not disable verification, rewrite locks/checksums,
drop a target, or substitute a failed generation's files.

Local fixture controls (no Gradle or network):

```bash
python3 -B scripts/tests/prepare-api-candidate-test.py -v
```
