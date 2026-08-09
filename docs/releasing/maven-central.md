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

After publication, retain the deployment ID, bundle SHA-256, file counts,
workflow URL, source/tag SHA, and remote byte/consumer verification in a release
record. See [`../releases/0.7.0-rc3.md`](../releases/0.7.0-rc3.md).
