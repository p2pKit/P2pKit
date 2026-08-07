# Versioning policy

The repository uses SemVer-style versions with release-candidate prereleases.

- `VERSION_NAME` is the source/build version.
- `LATEST_PUBLISHED_VERSION` is the immutable version consumers should install.
- Development on `main` uses a `-SNAPSHOT` suffix. Snapshot versions cannot pass
  the release-tag or Maven Central collision gates.
- A release tag must be exactly `v<VERSION_NAME>` and must point to the exact
  verified commit.
- Published tags and artifacts are never moved, deleted, overwritten, or
  rebuilt under the same coordinate.

The current source line is `0.7.0-rc3-SNAPSHOT`; the latest published release is
`0.7.0-rc2`.
