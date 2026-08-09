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

The current source is the `0.7.0-rc3` release candidate; the latest published
release remains `0.7.0-rc2` until RC3 publication and remote-byte verification
complete.
