# Hosted CI continuation — 16 September 2026

**Dated evidence, not a release approval or another mutable status ledger.**
This adds later results to the [accepted locks/sample record](hosted-lock-acceptance-2026-09-16.md).
Continue on `work/nonphysical-integration-20260915-022112`, not an older topic
branch. Refresh GitHub before continuing; do not repeat the accepted complete
writer, four-platform preview or branch dependency submission merely for ceremony.

At the 11:10 UTC continuation, the source was
`da03bee4b44524d9784707b4bcf3ccdc2437c84b`, tree
`a0f3914b418bb44b9cc87de86f269e2945b9ea32`. Main was still
`3bc76f956f8f47447b51a62474fc878b9c43173c`, tree
`2a1105fde1d1ac299448489501e29d7a0d4a407a`. The refreshed inventory had **69 open
issues, six dependency PRs and no campaign PR**. No merge, Release, issue closure
or branch deletion is claimed. Historical repair accounting remains
**206/234 (88.0%)**; new issues are a separate denominator. Audit/release: **NOT_READY**.

## Dependency submission: accepted branch snapshot, not main graph update

[Run 35084157788/1](https://github.com/p2pKit/P2pKit/actions/runs/35084157788)
completed **SUCCESS** at
[`084e5daf25d73fccf4bc0e2f1aea5a45445ed6d1`](https://github.com/p2pKit/P2pKit/commit/084e5daf25d73fccf4bc0e2f1aea5a45445ed6d1),
tree `b0036910f514fea354c5d9c853cf4b849daff394`. Its bounded JDK/SDK/owned-home
prerequisite correction preserves the pinned default resolver, strict
verification, checkout credential isolation and real API submission.

Actual host: native ARM64 macOS **26.6.2 / 25G83**, image `20260907.0351.1`;
Java **17.0.20.1**, daemon **21.0.12.1**. Literal compile platforms **36 and 37.0**
were already installed: the missing-only SDK step did **not** install an SDK.
All **13 recorded steps** succeeded. Step-number gaps are not extra steps.

The actual wrapper invocation was:

```text
./gradlew -Dorg.gradle.configureondemand=false -Dorg.gradle.dependency.verification=off -Dorg.gradle.unsafe.isolated-projects=false -Dorg.gradle.isolated-projects=false :ForceDependencyResolutionPlugin_resolveAllDependencies --dependency-verification strict
```

The maintained CLI `strict` option takes precedence over the upstream action's
system-property default `off`. All **11 root/project resolver tasks** ran;
Gradle reported **BUILD SUCCESSFUL in 2m40s**, 13 actionable tasks executed.
This resolves dependencies; it does not execute product tests or compile the apps.

The graph has **656 coordinates and 2,349 closed references**, with **335 unique
included configuration pairs**. It is **not exhaustive lock coverage**:
87/739 locked coordinates are absent (10 transformed plugin markers and 77
across internal ABI, JaCoCo and Compose hot-reload tool configurations).
The original log retains 22 informational variant-selection diagnostics. No
zero-unresolved, full-lock-coverage or SBOM claim follows.

The GitHub API explicitly reported:

> The snapshot was accepted, but it is not for the default branch. It will not
> update dependency results for the repository.

Checkout removed its auth before Gradle; the dependency action separately uses
its legitimate API token. This is not token-free Gradle/sandbox evidence.
Same-home `./gradlew --stop --console=plain` and action POST succeeded. Cache was
read-only, with zero restored/saved entries; hosted dependency downloads did
occur. Complete worker retirement and a post-POST source snapshot were not
established. Do not substitute daemon-stop success for those observations.

Both small original artifact ZIPs were downloaded and completely hash-verified:

| Artifact | Bytes | SHA-256 |
| --- | ---: | --- |
| Graph `10441174410` | 18,866 | `38303a824e89accf801c1b8f80aad3617e1ae0bc1117b402bbf4228e901d14c0` |
| Prerequisite receipts `10441079704` | 3,389 | `49a50c4d279958d6695cb1eaae43097bb066b18c4fd336d60700897d2dd97c53` |

Independent verdict: **APPROVE_SCOPED_BRANCH_DEPENDENCY_SUBMISSION_35084157788_1**;
report SHA-256 `c42ae3d9317987e8d4c35c39011a832b3a696e2c5016f31c1eff29f3604bd648`.
Keep [#143](https://github.com/p2pKit/P2pKit/issues/143),
[#425](https://github.com/p2pKit/P2pKit/issues/425) and
[#437](https://github.com/p2pKit/P2pKit/issues/437) open for their remaining
ordinary/full-path, final/formal-review, main and delivery requirements.

## Windows helper: safe first-failure observation; native acceptance still failed

[#446](https://github.com/p2pKit/P2pKit/issues/446) records a confirmed candidate
helper defect: an uppercase regex could select arbitrary private exception text
for public output. This was reproduced with a synthetic sentinel, **not an actual
hosted secret leak**. Earlier failures could also collapse into a later generic
recipient guard instead of retaining the first failing stage.

[`da03bee4`](https://github.com/p2pKit/P2pKit/commit/da03bee4b44524d9784707b4bcf3ccdc2437c84b)
changes only the helper and its offline tests. It projects finite source-owned
stage/reason/native/GPG categories, preserves the first failure and late UNKNOWN,
and changes no workflow, crypto argv, native supplier, deadline or seal policy.
Independent review **APPROVE_EXACT_TWO_FILE_SOURCE_AND_OFFLINE_REGRESSIONS**,
report SHA-256 `2864d54a84ced76a6500e9bc81d51a2d08492eb9d4b254a6ecf36030ddcd7d20`.
With installed Xcode Python 3.9.6 `-I -B -S`, the unchanged independent privacy
oracle actually failed once on the Git preimage, then passed on the postimage;
the exact proposed `scripts/tests/windows-helper-controls-test.py` suite passed
**96/96**. These are offline models, not Windows/GPG execution.

The subsequent genuine Windows Server 2025 helper
[35086976664/1](https://github.com/p2pKit/P2pKit/actions/runs/35086976664), job
`104763994157`, **FAILED** at that exact source. Both maintained commands ran:

```text
python -I -B -S scripts/run-hosted-windows-helper-controls.py run
python -I -B -S scripts/run-hosted-windows-helper-controls.py validate-public
```

Actual finite observation:

```text
WINDOWS_HELPER_NOT_ACCEPTED=EVIDENCE_REFUSED;
stage=RECIPIENT;
nativeOperation=UNOBSERVED;
nativeStatus=UNOBSERVED;
lastGpgCommand=SHOW_ONLY;
lastGpgExit=NONZERO;
retirementObservation=NO_UNKNOWN_REPORTED
```

The post-return seal refused with `HELPER_GUARD_REFUSED; stage=POST_RETURN_SEAL`.
Upload was skipped and GitHub returned **zero artifacts**. The native executor,
file and supplement suites were **NOT_RUN**. This identifies the last recorded
GPG operation/nonzero result, **not its underlying cause**, successful recipient
admission or known complete retirement. `NO_UNKNOWN_REPORTED` is not a KNOWN
custody result. Original 25,993-byte job log SHA-256:
`daea38f53d09fcc4ff9f542b4a76d8fc2511179e168336b4a66132b6d462b9da`.

Historical `35083374634/1` remains a separate failed generic-guard observation;
this new result cannot retrospectively identify its cause. No unchanged retry
was dispatched. Source research identified a GPG filename-parser portability
candidate, but the installed runner's exact selected GPG and underlying failure
remain unproved. Do not relax file pins, deadlines or private-evidence custody.

The proposed ordinary full/Desktop custody controller remains **NOT_APPLIED**.
Its independent review requested changes for isolated canonical-child imports,
missing crypto-return UNKNOWN handling, and late final-close deadline fences.
Those findings concern an inert proposal, not an executed ordinary controller.
Neither its original 57 passing models nor these findings are hosted acceptance.

## Reuse and remaining delivery boundary

Independent input reconciliation through `da03bee4` confirms **91 OSV inputs and
738 sample build inputs unchanged**. Reports:
`0917b47c2d1f1f9c1da3f7f3f190e4ea80b1093b40a52f05381648ed78f6421b`
and `d17a2180f74b2a4cd57cd2c449efe19cea4d93be6ab725c8403d5ae17c4b27c9`.

- Four-platform preview [35070982169/1](https://github.com/p2pKit/P2pKit/actions/runs/35070982169)
  remains the **8e4ca838-source build-only artifacts**, expiring **30 September**.
  It was not rerun, is not a main Release, and did not execute ordinary CLI/UI tests.
- OSV [35074618795/1](https://github.com/p2pKit/P2pKit/actions/runs/35074618795)
  remains the original accepted scan, not a new-head scan. **EXCEPTED_NOT_FIXED**:
  GHSA-r937-wjx7-w2jp / CVE-2026-53914, Kotlin 2.4.10, expiry **2026-10-31**.
- `bash scripts/tests/release-workflow-test.sh` and the two query-model suites
  passed at **084e5daf**. The hook includes actual synthetic GPG/POSIX-worker
  fixtures and fake-Gradle controls; it is not wholly mocked or a product build.
  **The whole hook was not rerun at da03bee4**; the focused changed-helper proof
  above is separate. No current-head required CI pass is manufactured from reuse.

Main delivery still requires qualified ordinary custody/native Windows handling,
the missing trusted finite recipient/key-responsibility decision, required PR
`complete-gate`, `review`, `scan / osv-scan`, `osv-scanner` checks, formal nonauthor
PR review and a normal merge with preservation. Candidate policy cannot authorize
its own trusted base. The explicit manual public recipient does not establish
ongoing ordinary-CI key responsibility. Do not activate that policy by inference.
The development Release publisher additionally requires the actual successful
push-only Desktop producer on reviewed merged main; branch preview artifacts
must not be republished under a campaign tag to bypass it.

No local Mac Java/Gradle/Xcode build, SDK/dependency acquisition, emulator or
simulator was run for this continuation. Original offline commands completed;
small evidence/review packets are retained, with no task-only workers left by
those checks. No shared cache, source, protected instruction or evidence was
deleted. Physical-phone criteria remain deferred; #151 production publication
and protected-file/product decisions remain separate owner holds.

Private packet handles under the campaign evidence root:
`dependency-submission-084e5da-hosted-tGyhGx`,
`review-dependency-submission-result-oyQ0w9`, `windows-helper-da03-hosted-Umhwzb`,
`review-helper-boundary-root-KaCpBN`, `review-current-gate-reuse-i4rh9kl_`,
`review-gate-reuse-da03-5p_mnftq`, and
`review-ordinary-controller-import-finalization-eHClI9`. Transfer only selected
needed originals through the owner's private channel and verify their hashes.
