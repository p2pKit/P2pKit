# Maven Central publication

P2pKit publishes under the owner-verified namespace
`io.github.apdelrahman1911`. The protected workflow is
`.github/workflows/publish-maven-central.yml`; it is tag-triggered and uses the
`maven-central` GitHub Environment for irreversible publication.

Required secrets and variables remain in the GitHub Environment and must never
be printed or committed. The workflow validates namespace/publisher access,
the exact tag/commit/version relationship, signing-key fingerprint, credential
rotation policy, artifact signatures/checksums, bundle shape, SBOM, provenance,
and coordinate absence before upload.

Local secret-free verification:

```bash
scripts/run-release-gate.sh
scripts/check-maven-central-version.sh absent
```

The signed bundle builder may be run only with in-memory signing material and
the expected full fingerprint. It does not upload by itself. Publication must
remain in the protected workflow; do not invoke Portal mutation scripts merely
to test credentials.

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
checksums and the bundle. It writes the versioned ZIP, SHA-256 manifest and JSON
summary under `build/central/`. It never uploads and does not replace the
complete release gates or authorize publication. Keep secret material out of
logs and remove it from the invocation environment afterward.

After publication, retain the deployment ID, bundle SHA-256, file counts,
workflow URL, source/tag SHA, and remote byte/consumer verification in a release
record. See [`../releases/0.7.0-rc3.md`](../releases/0.7.0-rc3.md).
