# Versioning policy

The repository uses SemVer-style versions with release-candidate prereleases.

- `VERSION_NAME` is the source/build version.
- `LATEST_PUBLISHED_VERSION` is the immutable version consumers should install.
- Unreleased development may use a `-SNAPSHOT` suffix. After a release, `main`
  can retain that version until the next reviewed version change. Snapshot
  versions cannot pass the release-tag or Maven Central collision gates.
- A release tag must be exactly `v<VERSION_NAME>` and must point to the exact
  verified commit.
- Published tags and artifacts are never moved, deleted, overwritten, or
  rebuilt under the same coordinate.

Read the two canonical values in [`gradle.properties`](../gradle.properties)
and the corresponding [release record](README.md#test-and-release), rather than inferring
publication from the source version. A later commit can retain the released
version without belonging to its immutable tag. Release-specific validation must
use the recorded tag, exact source and artifacts, not a later `main` checkout.
Changing `VERSION_NAME` alone is neither publication nor publication approval.

The pre-`1.0.0` breaking-change reservation includes public sealed-hierarchy
evolution. See the [compatibility policy](compatibility.md#public-sealed-hierarchies)
for variant additions and exhaustive consumer `when` expressions; an ABI check
is not a guarantee of consumer source compatibility.
