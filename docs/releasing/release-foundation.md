# Exact-source library and development application releases

## Activation status

This foundation is **not yet operationally qualified**. Its source controls do
not replace ordinary FULL/Desktop, native packages, provider/cache/custody,
Intel Apple coverage, required GitHub checks, or personal owner approvals.
The initial-recipient trust bootstrap and ordinary activation HOLDs still apply.
No historical preview or earlier campaign authorization qualifies this branch.
Do not create a release tag merely to exercise the new preflight.

The existing Maven signer, bundle inspector, publication-build SBOM, Central
uploader and remote/consumer verification are retained. The new handoff adds a
required frozen application set **before** any protected Maven publication.
It does not make the retained gates optional or change the development-app
classification. See the [checklist](checklist.md) and
[application version encoding](application-versions.md).

## Identity and normal future procedure

Use these identities throughout, without overrides or floating branch selection:

- **S/T**: the exact approved main merge commit and its tree.
- **V**: the single canonical `VERSION_NAME` stored in S.
- **vV**: immutable library tag resolving to S, including annotated-tag identity.
- **samples-vV**: development-app prerelease tag resolving to the same S.
- **A**: the one frozen set of original producer artifacts, native package
  metadata, embedded source/version, installer hashes and original evidence.

After this foundation's activation prerequisites are genuinely satisfied:

1. Create normal feature/release-preparation branches from `main`. Review the
   feature, select the canonical version through a PR, and pass all required
   checks. The existing compatibility policy requires the next publication to
   be a non-snapshot **0.8.0+** version; published RC3 history stays immutable.
2. The owner posts `/p2pkit approve-pr <exact-final-head-SHA>` after successful
   required checks. This is the approved replacement for GitHub's unavailable
   author self-review, not an agent-generated approval. Use a normal,
   history-preserving manual merge. Include case-sensitive `[release ci]` in
   the **actual main merge commit message**, not only in the PR or a branch commit.
3. The qualified ordinary main workflows run for S. FULL and all three native
   Desktop hosts must succeed. They retain the Android APK, Windows **x64** MSI,
   macOS **ARM64** DMG and Linux **x64** DEB, plus required encrypted evidence.
   The apps use the in-repository library at S; no floating Maven dependency is
   substituted. Package inspection reads the actual installer/APK metadata and
   embedded source identity, not just a release title.
4. Obtain the owner's explicit authorization for vV at S. Verify the existing
   tag/source/version/coordinate-absence conditions, then push that immutable
   tag. Do not move or recreate any library tag.
5. `Publish Maven Central` first runs `freeze-applications`. This secret-free
   job validates main/PR/marker/gates, inspects all four original bundles and
   notices, and retains one immutable `release-application-set.json` artifact
   named `release-application-set-<Maven-run>-<attempt>`.
6. The existing `verify-release` complete gate must pass. At `maven-central`,
   the owner reviews A and enters the **exact challenge from the freeze job's
   summary** as the environment approval comment:

   ```text
   APPROVE_APPLICATION_SET <Maven-run>/<attempt> <frozen-JSON-SHA256>
   ```

   The workflow revalidates original artifact IDs/digests, source, version,
   successful gates, retention and that real approval after the delay and
   immediately before Central upload. A generic “approved”, another attempt's
   challenge or an agent-written approval is not authority.
7. The existing protected Maven job signs/inspects/publishes from S/V and
   verifies remote bytes and isolated consumers. Signing material stays within
   its existing secret-bearing steps; it never enters the frozen app record.
8. **Only verified Maven completion**, or the separately approved verification
   recovery described below, automatically starts `Development sample Releases`.
   Ordinary CI/Desktop/OSV completions cannot publish applications. The delivery
   job loads A from the original Maven attempt; it never selects a new producer
   or builds replacement applications.
9. A secret-free preparation job verifies those bytes again and creates a
   fresh post-build evidence-review request. The owner retrieves/decrypts the
   original encrypted evidence privately and approves the protected
   `sample-development-release` environment with its exact summary challenge:

   ```text
   APPROVE_EVIDENCE <sample-publisher-run>/<attempt> <review-request-SHA256>
   ```

   This second approval is required even when the same owner approved Maven.
   Reruns/manual delivery cannot reuse an earlier request or approval.
10. Publish the **already-qualified bytes** as a development prerelease, not
    production-signed/notarized applications. Read back the complete asset
    roster/digests, then anonymously download and SHA-256-check every complete
    public asset. This is not merely an HTTP HEAD or one-byte access probe.

No automatic PR approval or merge is introduced. Required checks remain
`complete-gate`, `review`, `scan / osv-scan`, and `osv-scanner`; the publisher
fails closed if that live policy changes rather than silently ignoring a gate.

## Retention and access

Application bundles, the frozen public JSON and encrypted CI evidence use
14-day Actions retention. Each original object's actual GitHub `created_at`
and `expires_at` are retained. A frozen JSON upload **does not restart** the
originals' lifetime. Eligibility ends at the earliest original application or
evidence expiry. The pre-Maven checks preserve 90 minutes for the existing
Maven job plus 20 minutes for sample delivery; delivery requires its remaining
20-minute window. These are freshness headroom checks, not a runtime pass.

The public record contains hashes and identities, never private test originals,
custodian private keys or passphrases. The owner decrypts evidence privately;
the publisher does not. Actions permissions are not claimed to make artifact
metadata or ciphertext owner-only. The separately published APK/MSI/DMG/DEB
are unencrypted public Release assets and require no evidence decryption access.

## Partial failure and app-only resume

- **Before Maven upload:** fail closed on missing/mismatched gates or objects.
  No absence/readiness failure is permission to change versions or fabricate
  producer results. A new approved qualification must have its own identities.
- **Maven completed successfully, sample delivery failed:** use the maintained
  sample workflow's `workflow_dispatch` from `main`. Supply S, the **original**
  Maven run/attempt, frozen artifact ID and frozen JSON SHA-256. `verify` has no
  publication permission; `publish` always creates a fresh evidence request and
  waits for the owner's protected approval. It performs no Maven upload/build.
- **Draft already exists:** only missing, approved assets may be added. Existing
  tags, assets, hashes, release body and source must match. Never clobber an asset
  or adopt an unrelated/orphan tag. An already-public complete release is only
  reverified; its bytes are not replaced.
- **Central upload succeeded but the Maven job later failed:** do **not** rerun
  the tag publisher or reinterpret that failed attempt as success. Use the
  separate original-bound recovery below only when the failure is confined to
  the post-publication verification/evidence tail and every required original
  survives. Missing/expired signed-bundle or deployment originals remain HOLD;
  rebuilding cannot recreate them.
- **Original retention expired:** no automatic substitution, new producer,
  reconstructed evidence or refreshed ciphertext lifetime is allowed. Stop at
  the retained policy boundary even if Central publication already occurred.

## Read-only recovery after an original PUBLISHED deployment

`Recover Maven Central verification` (`recover-maven-central.yml`) is a separate
main-only manual workflow. Its controller is the workflow's exact main commit;
the original release S is checked out into a different directory. Advancing
main does not select another library version, consumer fixture or application
set. The original Maven attempt must remain **failed**, with no later rerun.

Eligibility requires successful original freeze and complete-gate jobs, the
original owner's application-set approval, successful signing/SBOM/upload, and
both immutable, attempt-named original evidence artifacts:

- `maven-central-signed-bundle-<tag>-<run>-<attempt>`: the original ZIP, SHA-256
  manifest, source-bound summary and **public-only** signing certificate.
- `maven-central-deployment-<tag>-<run>-<attempt>`: original Portal events,
  PUBLISHED status, deployment ID, bundle/source hashes and their bound receipt.

These are retained before the fallible remote-verification step. Cancellation,
pre-upload failure, absent originals, changed tags, expired custody, a skipped
remote-verification step or another failed stage cannot use this recovery path.
An uploaded receipt is evidence, not owner approval or a successful Maven job.

1. Dispatch `Recover Maven Central verification` from `main` with the five
   required inputs: `source_sha` (S), `maven_run`, `maven_attempt`,
   `frozen_artifact` (original frozen application-set artifact ID) and
   `frozen_sha256` (the original JSON hash). No `latest` or version override is
   accepted. This does not upload to Central or mutate tags/releases.
2. The 20-minute secret-free preparation job checks original identity,
   deployment, custody, gates and structural public-bundle data. It retains
   a new exact-attempt recovery request. Structural preparation does **not**
   count as signature, remote-byte or consumer verification.
3. The separately configured `maven-central-recovery` environment must allow
   only the `main` branch, name `Apdelrahman1911` as its sole reviewer, allow
   self-review and disable administrator bypass. It has no Central or signing
   secrets. The owner reviews the request and uses its exact summary challenge:

   ```text
   APPROVE_MAVEN_RECOVERY <recovery-run>/<attempt> <request-SHA256>
   ```

   The controller checks the actual environment and personal approval again;
   adding the environment name to YAML cannot create that authority.
4. The protected 90-minute macOS job revalidates the originals after the delay,
   verifies all 84 original public signatures and the local 504-member
   bundle/checksum roster, then runs S's existing remote-byte verifier against
   that original bundle and S's **complete** isolated remote consumers. The
   remote checker compares 168 base/signature files; do not describe that as
   remote comparison of all 504 ZIP members. No library build, signing,
   coordinate-absence probe, Central upload or application rebuild is allowed.
5. Successful command/source/step/ownership records join the approved request
   and original PUBLISHED deployment into `recovery-result.json`. Only a
   successful recovery job and its exact retained artifact give distinct
   `mavenRecovery` delivery authority. The original remains visibly failed;
   there is no manufactured green status for it.
6. Successful recovery automatically starts normal sample delivery using A.
   The separate fresh `APPROVE_EVIDENCE` approval is still mandatory. If delivery
   later fails, the normal sample manual path must supply its six original
   inputs **and** all four recovery inputs: `recovery_run`, `recovery_attempt`,
   `recovery_artifact` and `recovery_sha256`. These are the exact successful
   recovery attempt, result artifact ID and JSON hash, not another recovery.

Recovery records also have 14-day retention, but their creation never renews
the original objects' lifetime. Preparation/authorization require the existing
110-minute recovery-plus-delivery headroom; final delivery still needs 20 minutes
before the earliest original expiry. A new recovery after failure needs its own
request and personal approval. It may not replace A or reupload Maven.

On command failure or unknown process retirement, owned command logs, consumer
work and acquired public-bundle inputs are left on the ephemeral runner rather
than being deleted while a child may still use them. Raw logs are not uploaded
or printed. Bounded status/exit diagnostics do not claim retained encrypted
failure evidence; successful public receipts contain hashes, not log contents.

The recovery source controls are not hosted remote-consumer qualification.
Its environment provisioning, genuine hosted qualification and this foundation's
other activation prerequisites must be completed before operational use.

## Maintained implementation boundary

`release_application_set.py` is the preflight/frozen-record validator;
`publish-sample-release.py` is the app-only admission/delivery controller;
`package-sample-apps.py` and `sample_artifact_identity.py` produce and inspect
source/version-bound application bundles on their native hosts. The existing
Maven workflow remains the only Central upload path.
`central_bundle_evidence.py` and `central_deployment_evidence.py` preserve and
verify original public publication evidence; `maven_recovery.py` provides only
the separate protected verification-recovery path, never a second publisher.

The source-control workflow runs synthetic policy/package tests and the
dependency-free version helper. Passing it is **not** a native app build,
ordinary FULL/Desktop qualification, evidence decryption or Release approval.
