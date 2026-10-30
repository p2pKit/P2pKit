# Maven Central publication

P2pKit publishes under the owner-verified namespace
`io.github.apdelrahman1911`. The protected workflow is
`.github/workflows/publish-maven-central.yml`; it is tag-triggered and uses the
`maven-central` GitHub Environment for irreversible publication.

Before the protected publisher can run, the secret-free application preflight
must freeze the matching four-platform main application/evidence set. Both
protected approval and the final pre-upload check revalidate its original
identity and retention. See the [exact-source release procedure](release-foundation.md)
for owner challenge comments, post-Maven application delivery and partial-failure
boundaries. The latest completed publication is
[`0.8.0-rc7`](../releases/0.8.0-rc7.md). Current source selects
`0.8.0-rc8` as an unpublished development candidate; this is not publication.
Later source needs its own qualification and protected publication; source
controls alone do not establish readiness for a subsequent release.

Required secrets and variables remain in the GitHub Environment and must never
be printed or committed. The workflow checks authenticated namespace-query access,
the exact tag/commit/version relationship, credential presence, signing-key
fingerprint, artifact signatures/checksums, bundle shape, SBOM, provenance,
and coordinate absence before upload.

Keep using existing Maven Central tokens while they remain valid; there is no
repository-imposed periodic rotation date or fourteen-day renewal window.
Rotate when required by compromise, exposure, revocation, the provider, or a
genuine operational need—not merely because a calendar deadline passed.
The legacy `MAVEN_CENTRAL_TOKEN_ROTATE_BY` variable is no longer consumed.
This does not guarantee indefinite provider validity or bypass actual
authentication/authorization, signing, protected approval, or integrity checks.
The separate fourteen-day retention policy for release evidence is unchanged.

Local secret-free verification:

```bash
scripts/run-release-gate.sh
scripts/check-maven-central-version.sh absent
```

The signed bundle builder may be run only with in-memory signing material and
the expected full fingerprint. It does not upload by itself. Publication must
remain in the protected workflow; do not invoke Portal mutation scripts merely
to test credentials.

## Authentication and namespace preflight

`scripts/check-maven-namespace-access.sh` uses the documented, read-only
[Central Publisher API](https://central.sonatype.org/publish/publish-portal-api/):
`GET /api/v1/publisher/deployments` with the exact namespace filter, page zero
and a page size of one. A successful response establishes that the token can
make that namespace-scoped query. It does **not** establish namespace
`VERIFIED` state, permission to publish a particular bundle, or publication.
Central's actual upload authorization, bundle validation, PUBLISHED status and
remote byte verification remain mandatory in the protected publisher.

The schema-2 `namespace-access.json` records only the source, time, namespace
and these limited access claims. `namespaceVerificationState: NOT_ASSERTED`
is deliberate; neither `state: VERIFIED` nor `tokenPublisherAccess: true` is
inferred from a read-only response. Raw API data and credentials are not
retained. Authentication/authorization errors, redirects, transport failures,
malformed responses and unexpected namespace results fail the check.

The former `/api/internal/publisher/namespace` endpoint is not part of the
documented Publisher API. A token accepted by the public API can receive HTTP
401 there. Do not rotate a working token solely because that internal endpoint
refuses it, and do not use browser cookies or fabricated responses as a fix.

Run focused, secret-free mocked controls locally:

```bash
bash scripts/tests/check-maven-namespace-access-test.sh
```

The existing **Verify Maven Central namespace** workflow also accepts
`operation=controls` for those same tests on a hosted runner, without an
environment or secrets. `operation=verify` remains the protected real check.
Mocked controls are not evidence of real Central access. The repaired checker
subsequently passed authenticated preflight in rc2 publication
[38986454729/1](https://github.com/p2pKit/P2pKit/actions/runs/38986454729), followed
by separately verified upload, PUBLISHED state and remote consumers. Its access
report still honestly recorded `namespaceVerificationState: NOT_ASSERTED`.

### Repairs after a release tag already exists

A publisher rerun uses its original immutable tag's workflow and source, not
a later repair on `main`. Do not move/recreate a tag, replace tagged files at
runtime, or relabel an older application set as a new source/version. The
read-only recovery workflow applies only after a retained PUBLISHED deployment;
it cannot repair a failure before signing or upload. A pre-publication source
repair therefore needs a separately approved release identity and matching
qualification, unless an explicit tag-preserving tooling path is independently
designed, reviewed and authorized. No such additional path is introduced here.

## Local signed bundle preparation

Use the [release checklist](checklist.md) for version, source and gate
requirements. This recipe requires a reviewed, authorized non-snapshot release
source. The builder rejects SNAPSHOT versions; do not change `VERSION_NAME`
just to try this recipe.

Inject these variables through an approved secret provider, without shell
tracing, secret literals in shell history, or checked-in credentials:

| Variable | Value |
| --- | --- |
| `ORG_GRADLE_PROJECT_signingInMemoryKey` | ASCII-armored private PGP signing key; use this **or** the base64 variable, never both. |
| `ORG_GRADLE_PROJECT_signingInMemoryKeyBase64` | Single-line base64 encoding of that key, as an alternative to the plaintext variable. |
| `ORG_GRADLE_PROJECT_signingInMemoryKeyPassword` | Non-empty password for the signing key. |
| `MAVEN_SIGNING_KEY_FINGERPRINT` | Expected complete public fingerprint (40 or 64 hexadecimal digits), not a short key ID. |

The protected workflow maps `MAVEN_SIGNING_KEY_B64` and
`MAVEN_SIGNING_PASSWORD` secrets to the base64-key and password variables above;
the expected fingerprint is its `MAVEN_SIGNING_KEY_FINGERPRINT` variable.
Portal credentials are not needed to build the local bundle.

Once those prerequisites are satisfied, run from the repository root, with no
other build running in the worktree:

```bash
scripts/build-central-portal-bundle.sh
```

The builder creates a fresh isolated local publication, verifies the signing
fingerprint, artifact signatures and publication shape, then generates
checksums and the bundle. It writes the versioned ZIP, SHA-256 manifest,
source-bound JSON summary and public-only signing certificate under
`build/central/`. The protected publisher retains this verified quartet before
upload and the original PUBLISHED deployment receipt before remote verification.
It never exports private signing material into those public artifacts.
The builder never uploads and does not replace the complete release gates or
authorize publication. Keep secret material out of logs and remove it from the
invocation environment afterward.

For an explicit `--latest-published` consumer check after a later release,
review its version-to-fixture mapping in `scripts/check-published-consumers.sh`.
The retained 0.7 RC2/RC3 contracts use upstream JmDNS without RPC; `0.8.0-rc2`
uses the qualified embedded-LAN/RPC contract. Unknown versions fail rather than
silently selecting the historical graph. This mapping does not change the
ordinary exact-source complete consumer gate used during publication.

After publication, retain the deployment ID, bundle SHA-256, file counts,
workflow URL, source/tag SHA, and remote byte/consumer verification in a release
record. See [`0.8.0-rc7`](../releases/0.8.0-rc7.md) for the latest completed
publication and [`0.7.0-rc3`](../releases/0.7.0-rc3.md) for immutable history.
If an irreversible upload succeeds but verification fails, do not rerun the
publisher. Follow the separately protected [read-only recovery procedure](release-foundation.md#read-only-recovery-after-an-original-published-deployment)
using the original signed quartet, deployment receipt and frozen applications.
Missing or expired originals remain a HOLD; rebuilding is not recovery.
