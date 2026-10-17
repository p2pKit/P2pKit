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

The current development source is `0.8.0-SNAPSHOT`, continuing the existing
0.8.0 development line after the published `0.8.0-rc2` prerelease. The latest
published release is [`0.8.0-rc2`](releases/0.8.0-rc2.md); development is not
a new release candidate or a publication authorization. Release-specific
validation must use that immutable tag and its published artifacts, not this
later snapshot. The snapshot does not replace or change the versions of published apps.

The pre-`1.0.0` breaking-change reservation includes public sealed-hierarchy
evolution. See the [compatibility policy](compatibility.md#public-sealed-hierarchies)
for variant additions and exhaustive consumer `when` expressions; an ABI check
is not a guarantee of consumer source compatibility.
