# Exact-source library and development application releases

## Status and trust boundary

The owner approved replacement of the custom bootstrap architecture on
2026-10-15. The modular replacement completed genuine hosted qualification and
protected publication for [`0.8.0-rc2`](../releases/0.8.0-rc2.md) on 2026-10-17.
A passing source/model test alone is still not a platform build.

Dependency Cache Bootstrap, C1/H1/C2/H2, recipient activation windows, recursive
custody proofs and global runner reservations are **retired release prerequisites**.
Their old implementation and historical failures remain in Git history. They are
not reported as passing. Routine CI uses GitHub's source/run/job/artifact identity;
there are no owner VPS commands or special approval windows for routine tests.
Final protected main merge, tag, signing and publication approvals remain required.

The latest published release remains **`0.8.0-rc6`**. The current source candidate
is **`0.8.0-rc7`**, pending its own qualification and publication.
Its [release record](../releases/0.8.0-rc6.md) binds the actual main qualification,
separate protected approvals and immutable public library/application bytes.
The original Maven final-upload failure remains recorded; a successful separate
read-only recovery authorized delivery without republishing Maven or rebuilding apps.
Later source requires its own exact-source gates; neither earlier release
evidence nor subsequent bookkeeping results replace the published originals.

Historically, combined [PR #466](https://github.com/p2pKit/P2pKit/pull/466),
release-admission [PR #467](https://github.com/p2pKit/P2pKit/pull/467), and the
rc2 preflight/version repair [PR #468](https://github.com/p2pKit/P2pKit/pull/468)
merged through their separately authorized protected process, preserving
both Foundation history (`6014595493b59e57a1a17fc3c67d378ca5accbbe`) and agreed
RPC history (`68d470189773d56d939c0add0a39ef929739e7bb`) with integration fixes.
This replaced the earlier separate Foundation-first landing plan; it does not
change [RPC PR #463](https://github.com/p2pKit/P2pKit/pull/463)'s status or authorize
any further merge.

Immutable `v0.8.0-rc1` remains at main commit
`8700583a5ae5aeaf5c77edee2a3ed4f5bd9a2d2c`. Its Maven
[run38941438027/1](https://github.com/p2pKit/P2pKit/actions/runs/38941438027) failed
before signing/upload because the internal namespace preflight returned HTTP401.
The rc2 release used the reviewed supported-API preflight repair described in
[the Maven release guide](maven-central.md); it did not alter the old tag or
reclassify its failure. Exact main `bd98deeb6ab44b5f5126d88742aa69b57f290c32`
passed its own fourteen-component/four-application qualification and dry run.
Maven [38986454729/1](https://github.com/p2pKit/P2pKit/actions/runs/38986454729)
and sample [38993901743/1](https://github.com/p2pKit/P2pKit/actions/runs/38993901743)
then succeeded after separate exact-source/tag, frozen-set and evidence approvals.
The release record binds the original artifacts and public download hashes.

Every future release still requires its own exact source/version and 14-lockfile
graph checks, exact-head merge authorization, actual-main qualification, four
application artifacts and separate tag/Maven/sample approvals. Historical
rc1/rc2/rc3 artifacts do not qualify rc4; rc4 artifacts likewise cannot qualify
a different source or later release.

## Independent components

`ci.yml` calls `ci-component.yml` with these independently selectable components:

| Component | Responsibility / runner |
| --- | --- |
| source | Repository, workflow, version and release-contract controls / Ubuntu |
| dependencies | Locks, SHA-256 integrity, approved dependency floors / Ubuntu |
| jvm-linux, jvm-windows | Real library JVM tests / Ubuntu, Windows x64 |
| android | Android unit tests, build and native APK inspection / Ubuntu |
| apple-arm64 | Four native Apple ARM64 test tasks / macOS 26 ARM64 |
| macos-shared | Original aggregate `check`, delegating only eight native test tasks to the two mandatory Apple lanes / macOS 15 Intel, Xcode 26.3 |
| apple-x64 | Actual `iosX64` execution, not cross-compilation / macOS Intel |
| desktop-linux, desktop-windows, desktop-macos | Desktop tests and DEB/MSI/ARM64-DMG packaging |
| security | Pinned unfiltered OSV scan / Ubuntu |
| compatibility | API/ABI, strict Dokka, SBOM, publication, XCFramework and Swift / macOS 26 ARM64 |
| consumers | Complete isolated published-coordinate JVM/Android/KMP/iOS consumers / macOS 15 Intel, Xcode 26.3 |

All fourteen components are mandatory for the same source. The `macos-shared`
profile runs the original `check` with `-x` for exactly four ARM64 and four Intel
native test tasks, each required in its matching Apple component. It retains all
16 JVM/Android-host test tasks and the non-test dependencies of `check`, including
BuildInfo reproducibility, Android SDK-matrix verification and plugin checks.
The three profiles cover all 24 portable policy tasks; the two already separate
opt-in bundle/JNI tasks remain honestly unqualified here. No task is disabled and
the standalone `full` profile is unchanged.

The prior macOS 26 FULL [run](https://github.com/p2pKit/P2pKit/actions/runs/38823809770)
failed actual JmDNS close tests with `NoRouteToHostException`; that failure is not
reclassified as passed. The published rc2 shared CLI tests used the reviewed macOS 14 baseline.
The released rc5 source uses macOS 15 Intel/Xcode 26.3; no result
on either host proves macOS 26 JVM multicast functionality. New
current-source results from all fourteen components are required, with all four
application artifacts (18 frozen inputs total). Splitting consumers likewise
does not omit or weaken their tests. The full dependency-update candidate writer
also selects the macOS 15 Intel / Xcode 26.3 CLI baseline. The existing protected Maven
`publish-release` and read-only `verify-recovery` jobs use this same explicit
CLI setup, including Java 21 then Java 17, so complete remote consumers do not
silently return to the failing plain macOS 26 context after irreversible upload.
The three Maven jobs and original failed-publication recovery contract remain
unchanged; no extra publication authority or signing credential is introduced.
Configuring these hosts alone is not publication or recovery execution evidence.
The original [RPC baseline run](https://github.com/p2pKit/P2pKit/actions/runs/38759538710)
was followed by rc2's own completed qualification and protected publication;
those results do not establish execution of the separate recovery procedure.
macOS 26 remains the native ARM64, DMG,
XCFramework and Swift lane, with Intel native execution on macOS 15 Intel.

**Replacement qualification:** macOS 14 retires on 2026-11-02. The current
source selects explicit macOS 15 Intel/Xcode 26.3 instead, including the focused
JmDNS diagnostic, complete shared/consumer components and dependency writer.
The rc5 release record binds successful exact-source shared/consumer components
and protected publication on this configuration. Those results are specific to
that source; later sources still require their own real gates. Configuration
alone is not signing/publication evidence, and the separate recovery procedure
is not claimed executed. No Terminal/TCC permission workaround or Bonjour
mutation is added to these CLI routes. Native
ARM64/Intel and Desktop/Swift lanes are unchanged. Exact host/tool mismatches
fail; no floating runner, architecture emulation or Xcode fallback is allowed.

List exact commands without executing them:

```bash
python3 scripts/ci_component.py android --list-commands
```

Run one component locally with the required tools installed:

```bash
python3 scripts/ci_component.py jvm-linux
```

Dispatch independently against a branch whose HEAD is the reviewed source:

```bash
gh workflow run ci.yml --ref YOUR_BRANCH -f component=desktop-windows
```

Run `gh workflow run ci.yml --ref YOUR_BRANCH -f component=bundle-diagnostic` for the existing disposable-key signed-bundle test alone.

The 0.8+ Central bundle contains exactly 121 signed originals across 21 coordinates: 117 dependency artifacts plus the pinned Kotlin plugin's four root `-kotlin-tooling-metadata.json` sidecars (core, LAN, RPC, Android provisioning). Each original retains its signature and four checksums: 726 files. Exact filenames, bounded JSON objects, signatures and hashes are checked; equal-count substitutions are refused. Historical 0.7 bundles remain 15 coordinates / 84 originals, and the isolated-consumer dependency verification allowlist remains 117—not the four tooling sidecars.
Run `gh workflow run ci.yml --ref YOUR_BRANCH -f component=jmdns-diagnostic` for only the existing real-resource JmDNS close tests on the explicit macOS 15 Intel CLI candidate.
Run `gh workflow run ci.yml --ref YOUR_BRANCH -f component=published-consumers-diagnostic` for the complete maintained `--latest-published` consumer checks against fixed public Maven Central in the Terminal context; this downloads dependencies but does not publish.
The required `consumers` component still checks locally produced current-source coordinates; the remote diagnostic cannot replace it.
These optional diagnostics retain encrypted evidence but cannot aggregate/complete qualification or publish; the full required components remain unchanged.

Use `component=all` for a full qualification. Main pushes and PRs run the full
matrix. Each component has its own job, reports and artifacts. A failure does
not cancel other jobs. GitHub's **Re-run failed jobs** is supported; no repository-
wide exclusive queue is required. The standalone source, Desktop and Intel
wrappers are focused developer checks; final aggregation selects `ci.yml` results.
On a same-run retry, collection automatically preserves each untouched successful
component's original attempt and pairs its application with that same attempt.
It selects the latest execution, not the latest success: a newer failed, skipped
or incomplete component cannot fall back to an older pass. A qualifier-only retry
can reuse all unchanged originals. GitHub may copy successful job records into
that attempt with new job IDs but the original execution times, steps and runner.
Collection follows such copies only when the authenticated attempt records and
immediately preceding execution match exactly and the execution finished before
the new attempt began. It never falls back merely because an artifact is absent.
Collection uses the current run attempt; already frozen selections are revalidated
without being silently reselected.

For PR execution, GitHub's embedded run/PR association can retain an older base
SHA after `main` advances. Qualification checks the actual tested merge's two
ordered parents and exact PR head. If its first parent differs from that cached
base, exact-commit API comparisons must prove recorded-base → actual-base →
current-main ancestry. This does not replace the original job, artifact-digest,
manifest source/workflow SHA, version and tree checks. PR evidence still cannot
qualify a main release. A stale association is not rewritten or treated as proof
that a different commit was tested.

The plan reports reasonable external wall limits (30–180 minutes per component,
plus 10 minutes for evidence/upload). No special CPU20, initializer120 or
before-upload handshakes apply. Real timeouts, test failures, unknown owned-process
cleanup and corrupt dependencies still fail. Do not raise a timeout to mask a
functional deadlock.

## Dependencies, evidence and retries

Standard `gradle/actions/setup-gradle` caching is optional and read-only outside
main. Build-cache and affected executable Kotlin/Gradle script-cache entries are
excluded. A cache miss downloads through the approved repositories under strict
Gradle locks and checksum verification. It is not a qualification failure.

`ci_evidence.py` captures the actual command and reports privately, retains owned
process cleanup, checks the source before/after, and writes a small public
manifest. It encrypts logs/reports to the **existing public key** in
`.github/ci-evidence-recipient.asc`. Independently configured repository variables
`CI_EVIDENCE_RECIPIENT_SHA256` and `CI_EVIDENCE_RECIPIENT_FINGERPRINT` pin that key.
CI has no private key or passphrase. The retired policy's authorization dates do
not govern routine tests; the real cryptographic key expiry still applies.

Routine macOS CI uses the explicit `GITHUB_HOSTED_DARWIN_MARKER_DOMAIN_V1`
cleanup boundary. It retains positive inherited markers, pipe capabilities,
observed original-parent ownership, identity-scoped signaling, original child
waits and closed capture pipes. A new same-user process with no ownership proof
and only an unobserved original parent is not part of that observed domain. The
receipt records a cumulative `outsideDomainObservations` count (capped at one
million), not a claim that those lifetimes are unrelated or retired. Every later
census can still establish ownership. Traced ancestry, unreadable environments,
malformed markers, leaked native rights and uncertain known-child cleanup still
fail. The strict audit/RPC supervisor itself is unchanged.

This ordinary hosted policy trusts reviewed commands to preserve their ownership
markers; it is not containment of malicious detached/marker-erasing work. Known
Gradle/simulator cleanup remains required, while other delegated system services
belong to their explicit platform lifecycle and the disposable GitHub VM. The
qualifier requires this exact boundary on fresh macOS receipts; historical
whole-host failures are not relabeled as successes. Public-only GPG separately
uses bounded original-child/pipe ownership on Darwin with agent/network helper
startup disabled; it never upgrades a failed command into qualification.

Standard immutable Actions artifacts retain the manifest/ciphertext for 14 days
from upload. Public app artifacts are separate and unencrypted. Reports include
source/tree/version, command/tools, OS/architecture, run/attempt, completion,
cleanup and file hashes. Genuine failed-task evidence is retained too. Missing
or unreadable evidence is not success. Public diagnostics contain safe task names
and result codes, never private log text.

`ci_qualification.py` validates all fourteen successful component jobs and four
application producers. It compares exact source/tree/version, host, workflow,
run/attempt, job completion, original artifact metadata and downloaded digests.
There is **no fixed job-step count**. Failed overall matrix runs may still supply
individually successful jobs, with their original attempt IDs. PR merge-source
results remain premerge evidence, not main release evidence.

To aggregate successes from separate same-source runs without rerunning them, supply the
`qualification_selection` dispatch input. It is the machine-readable selection
from a previous qualification (or `ci_qualification.py collect`), with only the failed
component's run/attempt/artifact/digest and its app artifact, if any, replaced.
Each selector is revalidated; it is not an approval or an arbitrary success flag.
Missing, failed, expired, stale-source and wrong-platform selections fail closed.
Source changes require fresh compatible results; never combine different commits.
If more than one complete qualification exists for the exact release source,
select one explicitly with the public repository variable
`RELEASE_QUALIFICATION_BINDING`: JSON containing `runId`, `runAttempt`,
`artifactId`, and its `digest` (`sha256:…`). The verifier checks that original
against the release source; it never chooses floating latest-main. Clear/update
this optional selector for a different release. Once frozen, the record's binding
wins and cannot be changed through the variable.
If artifacts expired, rebuild/requalify before publication rather than silently
reselecting after Maven.

## One release identity and protected publication

1. Develop normally from main. Preserve APIs, samples, MainKt, Windows components
   and all product functionality. Select canonical `VERSION_NAME` in the final
   release PR; existing behavior changes require **0.8.0+**. Leave
   `LATEST_PUBLISHED_VERSION` unchanged until remote publication is verified.
2. Pass PR checks and obtain the owner's exact-head PR authorization. Use the
   protected history-preserving merge process. The actual main merge message
   must contain case-sensitive **`[release ci]`** for publication.
3. Qualify that exact main commit. Build and inspect APK, Windows x64 MSI,
   macOS ARM64 DMG and Linux x64 DEB from the same source/version. Use the existing
   [canonical package encoding](application-versions.md), not release titles or
   historical preview files. Ordinary CI may build packages without authorizing
   their publication.
4. Run the secret-free **Release dry run** for that exact main SHA/version. It
   revalidates the completed qualification, ancestry and coordinate absence;
   it does not rebuild all already-qualified components.
5. Obtain separate owner authorization for immutable `v<VERSION_NAME>` at that
   exact commit. Never move or replace the tag. A tag push begins Maven preflight.
6. `freeze-applications` verifies all four original bundles and the source-bound
   qualification and records one immutable `release-application-set.json` **before
   signing or Maven upload**. `verify-release` rechecks qualification and identity
   without rebuilding the application set.
7. At protected `maven-central`, the owner reviews the frozen set and submits its
   exact challenge: `APPROVE_APPLICATION_SET <run>/<attempt> <frozen-JSON-SHA256>`.
   The publisher revalidates readiness after approval and before irreversible
   upload. It rebuilds/signs/inspects the Maven bundle at the same source/version,
   generates its actual publication-build SBOM and verifies remote bytes/consumers.
   Signed Maven bytes are not claimed identical to an unsigned verification build.
8. After Maven succeeds, **Development sample Releases** reuses the frozen app
   bytes. The owner reviews the main-run evidence and separately approves the
   protected `sample-development-release` stage. Publish only then, preserving
   the development/prerelease classification and `samples-v<VERSION_NAME>` tag at
   the same source. Verify all four complete public downloads anonymously against
   recorded SHA-256 hashes.

## Partial failure and recovery

A failed component can be rerun independently. A successful Maven upload cannot
be rolled back or blindly retried. If upload status is ambiguous, use the existing
**Recover Maven Central verification** read-only recovery procedure to reconcile
original deployment/bundle evidence. Do not upload again or retag.

If Maven succeeded but application publication failed, resume **Development sample
Releases** with the original Maven run/attempt and frozen artifact/hash. It must
reuse the same qualified app bytes, revalidate surviving evidence and require the
existing final approval. No application rebuild/substitution is allowed after
Maven. Existing draft/asset idempotency checks remain enforced. See the
[release checklist](checklist.md) for publication contents and limitations.

No local model, source-only CI, accepted Windows risk or historical preview is a
substitute for an actually required gate. Published rc2/rc3 Windows RPC retains
its unavailable productive-provider behavior. The rc4 provider is implemented,
but the source/artifact-bound incoming manual report, Back deadline failure,
zero fully accepted automated UI cycles and partial W01–W11 remain distinct
from publication. See the [Windows scope](../rpc/windows-release-scope.md);
no unsafe load or inferred installed-runtime pass is permitted.

For focused published-POM discovery diagnosis, dispatch CI with `component=consumers-pom-diagnostic`.
This runs the original source-local POM smoke and cleanup, not the required complete consumer gate or release qualification.
