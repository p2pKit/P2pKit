# Final repository consolidation record — 2026-08-08

This is the permanent disposition record for the post-`0.7.0-rc2`
consolidation. GitHub remains authoritative for live issue, pull-request, and
workflow state. This document records what was inspected, what was preserved,
and why material was removed or archived.

## Integrity boundary

- Published `0.7.0-rc2` remains tag `v0.7.0-rc2` at commit
  `90acb29583ea11d18685cf1315476756e7618245`.
- Development remains `0.7.0-rc3-SNAPSHOT`; no RC3 release or tag was created.
- Maven coordinates remain `io.github.apdelrahman1911` and published RC2
  artifacts were not changed.
- The canonical Apache-2.0 text replaced the incomplete license, and GitHub
  subsequently detected the repository as `Apache License 2.0` instead of
  `NOASSERTION`.
- No public API, wire-format, cryptographic default, or release-history rewrite
  was part of this cleanup.

## Repository inventory and disposition

The audited candidate contains 768 tracked paths and ten included Gradle
subprojects. `scripts/tests/check-repository-layout.sh` is the executable layout
contract.

| Area | Canonical location | Disposition and evidence |
| --- | --- | --- |
| Production library | `library/p2p-core`, `library/p2p-transport-lan`, `library/p2p-network-provisioning-*` | **Keep.** These are all published modules and are consumed by publication-shape and isolated-consumer gates. Source-set boundaries preserve common, JVM, Android, and Apple behavior. |
| Public API baselines | `library/*/api` | **Keep.** Kotlin binary-compatibility validation reads these files. |
| Tests and fixtures | Module `src/*Test`, `src/*HostTest`, and diagnostics module tests | **Keep.** They are executed by `check`, focused platform tasks, and the complete gate. No second test tree remains. |
| Samples | `samples/iosApp`, `samples/p2p-sample-android`, `samples/p2p-sample-desktop`, `samples/p2p-sample-desktop-ui`, `samples/p2p-sample-diagnostics`, `samples/sample-kmp-shared` | **Keep.** They are the actual compile/test/evidence harnesses. The former `docs/ios-sample-app` copy was deleted in PR #59 because it was a stale six-file implementation while the canonical iOS app had the current diagnostics, UI tests, Gradle/XcodeGen project, and XCFramework checks. |
| Build logic | Root Gradle files, `buildSrc`, `gradle/`, module build files and lockfiles | **Keep.** Publication metadata, BuildInfo, dependency verification, provenance, ABI, Dokka, and locked resolution depend on it. `gradle-wrapper.jar` is the sole tracked binary build tool and its checksum is verified. |
| Release/security tooling | `scripts/`, `.github/workflows`, `.github/dependabot.yml` | **Keep.** Maven Central, disposable signing, provenance, SBOM, OSV, dependency submission, publication consumers, XCFramework, and Swift gates call these files. Four applicable pinned action updates were folded into the consolidation candidate and passed together. |
| Current documentation | Root community files plus `docs/architecture`, `docs/guides`, `docs/security`, `docs/testing`, `docs/validation`, `docs/releasing`, `docs/releases` | **Keep.** `README.md` and `docs/README.md` are the navigation roots. Each responsibility has one current source; compatibility redirects exist only where external links may still use an old path. |
| Historical remediation and evidence | `docs/archive/` | **Keep as archive, not current guidance.** July owner material, review reports, raw test evidence, and older runbooks retain provenance. Archive banners and indexes state that historical status is not a current claim. |
| Maintainer decisions | `docs/maintenance/` and `docs/archive/branch-cleanup-2026-08.md` | **Keep.** These records explain branch, issue, PR, and consolidation decisions without replacing GitHub's live state. |
| IDE run profiles | `.run/` | **Keep.** Current sample documentation references the checked-in Android Studio/IntelliJ launch profiles, and the sample-profile test validates them. |
| Generated outputs | Ignored module `build/`, `.gradle/`, Xcode DerivedData, APK/AAB, XCFramework output, evidence ZIP/JSONL | **Do not track.** `git ls-files` found no generated package output. Historical `.bin`/XML files under the July archive are intentionally retained evidence, not live build products. |
| Credentials and local state | GitHub environments/secrets, local Gradle/Android/Xcode state | **Do not track.** Filename and diff review found no key, credential, token, signing material, or private payload. Workflows consume secret names only and their fail-closed tests passed. |

## Consolidations and deletions

| Removed or superseded item | Preserved destination/evidence | Why removal was safe |
| --- | --- | --- |
| Root-level June/July audit, tracker, plan, and specification documents | `docs/archive/remediation/2026-06` and `docs/archive/remediation/2026-07` | PR #59 moved tracked documents at 100% similarity; the remaining previously protected documents and review campaign were subsequently moved without deleting content. Current guidance lives outside the archive. |
| Root `P2PKIT_EXTERNAL_VALIDATION_TEST_PLAN.md` | `docs/validation/test-catalog.md`; compatibility link at `docs/testing/external-validation.md` | The executable catalog was preserved and the new six-area handbook supplies current navigation and operational procedures. |
| `docs/ios-sample-app/` | `samples/iosApp/` and `docs/guides/samples.md` | The deleted copy lacked the current diagnostics/export UI, UI tests, Gradle integration, XCFramework validation, and thousands of lines of current sample behavior. Git history and PR #59 retain the obsolete copy. |
| Legacy validation/release runbooks presented as current | `docs/archive/validation/legacy/` | Files were 100%-similarity moves. Current release and validation documents supersede them; archive indexing prevents stale status claims. |
| Old diagnostic/fix/performance development branches | Exact tips and replacement evidence in `docs/archive/branch-cleanup-2026-08.md`; contributor history also remains in PRs #22, #24, and #46 | File-by-file comparison showed temporary logging, old lifecycle/sample approaches, or work implemented more completely on `main`. The only unique issue-21 trace experiment remains in an explicitly retained local stash. |

No unique source, unresolved finding, legal notice, release evidence, or
published tag was deleted. Broken-link validation covers active Markdown while
archive-relative links were manually dispositioned where historic paths are
intentionally frozen.

## Previously protected owner material

| Original path | Useful content and verified disposition | Authoritative location |
| --- | --- | --- |
| `.review-2026-07/` | Review method, 18 reports, provisional findings, implementation notes, and raw test snapshots. The provisional draft is explicitly non-authoritative; raw evidence remains historical and is not reused as current test proof. | `docs/archive/remediation/2026-07/review-campaign/` |
| `DEFERRED_ITEMS_REGISTER_2026-07.md` | Owner decisions, external-test dependencies, and deferred work. Implemented decisions were compared with current APIs/tests; still-external work is represented by the current validation handbooks and live issues. | `docs/archive/remediation/2026-07/DEFERRED_ITEMS_REGISTER_2026-07.md`, with current execution status in `docs/validation/` |
| `P2PKIT_FULL_CODE_REVIEW_2026-07-17.md` | Original 150-finding review and recommendations. Findings are preserved for traceability; its date-specific statuses do not override current code or GitHub issues. | `docs/archive/remediation/2026-07/P2PKIT_FULL_CODE_REVIEW_2026-07-17.md` |
| `P2PKIT_REMEDIATION_HANDOFF_2026-07-22.md` | Batch/commit history, secure-v2 design context, verification evidence, blockers, and continuation instructions. It is historically useful but no longer an operating handoff. | `docs/archive/remediation/2026-07/P2PKIT_REMEDIATION_HANDOFF_2026-07-22.md` |

The detailed item-by-item disposition rules and cross-links are in
[`../archive/remediation/2026-07/LEGACY_MATERIAL_DISPOSITION.md`](../archive/remediation/2026-07/LEGACY_MATERIAL_DISPOSITION.md).

## GitHub reconciliation

- The branch-by-branch proof is in the
  [branch cleanup record](../archive/branch-cleanup-2026-08.md).
- The issue and pull-request acceptance review is in the
  [GitHub audit](github-audit-2026-08.md).
- The protected integration was
  [PR #60](https://github.com/p2pKit/P2pKit/pull/60), merged normally as
  `0a6c6bac28f9f99bab96d3753992994b867d6dad` without an administrator bypass.
- Issue #45 was closed only after its stronger atomic implementation and focused
  regression passed. All partially completed network/device issues remain open.
- PR #49 was merged through the protected path. Applicable workflow-action PRs
  #50, #51, #57, and #58 were preserved as authored commits in PR #60, passed
  together, and then closed as redundant; their remote branches were removed.
  Library/toolchain PRs #52–#56 remain open until their dependency-verification
  and compatibility gates pass.

## Validation status

The complete local release gate passed on exact merged `main` commit
`0a6c6bac28f9f99bab96d3753992994b867d6dad` on 2026-08-08. It covered
repository entry tests, complete Gradle checks, ABI, Android lint, Dokka, a
38-component SBOM, signed publication shape, isolated JVM/Android/KMP/iOS
consumers, release XCFramework and provenance, Swift warnings-as-errors, and
iOS sample/UI checks. The independent hosted
[exact-main CI run](https://github.com/p2pKit/P2pKit/actions/runs/31239454112)
also passed all of those stages in 28 minutes 7 seconds. The exact-main
[OSV advisory scan](https://github.com/p2pKit/P2pKit/actions/runs/31239454300)
and [dependency submission](https://github.com/p2pKit/P2pKit/actions/runs/31239454093)
passed as well. The pre-merge required dependency review, OSV scanner, OSV
advisory scan, and complete gate all passed on PR #60's exact head before the
protected merge.

The six non-local areas remain deliberately unverified:

1. Android physical-device validation — **NOT STARTED**.
2. Apple physical-device/AWDL validation — **NOT STARTED**.
3. Two-machine hostile-network validation — **NOT STARTED**.
4. CLI fault injection and headful Desktop observation — **PARTIALLY VALIDATED**
   by local automation only.
5. Independent secure-v2 interoperability — **NOT STARTED**.
6. Professional cryptographic audit — **EXTERNAL AUDIT REQUIRED**.

Execution procedures and evidence requirements are indexed at
[`../validation/README.md`](../validation/README.md). No status may be promoted
without the evidence required there.
