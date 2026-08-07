# Release checklist

This checklist applies to a future non-snapshot release. It does not authorize
a tag or Maven Central publication.

1. Update `VERSION_NAME` to the exact non-snapshot version and update current
   docs/changelog. Keep `LATEST_PUBLISHED_VERSION` at the previous release until
   remote publication is verified.
2. Confirm a clean worktree and exact ancestry from `origin/main`.
3. Run all script tests, `git diff --check`, and `scripts/run-release-gate.sh`.
4. Run OSV, dependency submission, ABI, strict Dokka, SBOM, publication shape,
   isolated consumers, Swift warnings-as-errors, and XCFramework provenance.
5. Confirm `scripts/check-release-tag.sh v<VERSION_NAME>` and
   `scripts/check-maven-central-version.sh absent` pass.
6. Obtain explicit owner authorization for the exact tag and commit.
7. Push the immutable tag and allow the protected `maven-central` environment
   to perform signing, bundle validation, provenance, and publication.
8. Verify remote bytes, signatures, checksums, metadata, and isolated consumers.
9. Create a release record, set `LATEST_PUBLISHED_VERSION`, open the next
   snapshot line, and create a GitHub prerelease/release entry.

Never move or recreate an existing release tag, weaken a gate, put secrets in
the repository, or publish a snapshot.
