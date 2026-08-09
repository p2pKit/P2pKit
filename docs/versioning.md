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

The current source is `0.7.0-SNAPSHOT`, the post-RC3 stabilization line for the
eventual stable `0.7.0` release. The latest published release is `0.7.0-rc3`.
External validation for RC3 must use its immutable tag and published artifacts,
not a later source snapshot.
