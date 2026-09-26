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
8. **Only verified Maven completion** automatically starts `Development sample
   Releases`. Ordinary CI/Desktop/OSV completions cannot publish applications.
   The delivery job loads A from that Maven attempt; it never selects a new
   producer or builds replacement applications.
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
  the tag publisher or reinterpret that failed attempt as success. A separate
  original-bound, read-only verification-recovery path is still an outstanding
  implementation prerequisite. Missing/expired signed-bundle or deployment
  originals remain HOLD; rebuilding cannot recreate them.
- **Original retention expired:** no automatic substitution, new producer,
  reconstructed evidence or refreshed ciphertext lifetime is allowed. Stop at
  the retained policy boundary even if Central publication already occurred.

## Maintained implementation boundary

`release_application_set.py` is the preflight/frozen-record validator;
`publish-sample-release.py` is the app-only admission/delivery controller;
`package-sample-apps.py` and `sample_artifact_identity.py` produce and inspect
source/version-bound application bundles on their native hosts. The existing
Maven workflow remains the only Central upload path.

The source-control workflow runs synthetic policy/package tests and the
dependency-free version helper. Passing it is **not** a native app build,
ordinary FULL/Desktop qualification, evidence decryption or Release approval.
