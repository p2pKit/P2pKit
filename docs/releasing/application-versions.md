# Library and application version identity

The single source is the literal `VERSION_NAME` in root `gradle.properties`.
Gradle rejects missing/duplicate declarations and conflicting `-P`, environment,
or subproject overrides. A release changes that tracked value through review;
the release publisher must not supply a different version at build time.

## Supported encoding (version 1)

Admitted values are `M.m.p`, `M.m.p-SNAPSHOT`, `M.m.p-alphaN`, `M.m.p-betaN`,
and `M.m.p-rcN`. Each numeric component is 0–99, and N is 1–99. Leading zeroes,
build metadata, and other aliases are rejected. Prerelease numbers are **numeric
ordinals** (`rc2 < rc10`), not lexical SemVer identifier ordering.

Define `rank` as snapshot=0, alphaN=N, betaN=100+N, rcN=200+N, stable=399.

| Field | Exact value |
| --- | --- |
| Library version / Android `versionName` | Unmodified `VERSION_NAME` |
| Android `versionCode` | `1 + (M*10000 + m*100 + p)*400 + rank` |
| MSI ProductVersion | `(M+1).m.(p*400+rank)` |
| macOS CFBundleShortVersionString and CFBundleVersion | Same numeric tuple |
| DEB Version | Same numeric tuple, followed by the explicitly pinned revision `-1` |

Android codes range from 1 through 400,000,000. The largest native version is
`100.99.39999`, within MSI limits. The major offset satisfies jpackage's
positive-major restriction even while the library is on a 0.x line. For example,
`0.8.0-rc1` maps to Android code 320202, native `1.8.201`, DEB `1.8.201-1`.

The encoding is injective and order-preserving across admitted **version
strings**, not commits: two builds with the same SNAPSHOT value have the same
numeric version. Source SHA remains an independent, mandatory identity.
This encoding is not permission to publish snapshots or reuse a version/tag.
The [release checklist](checklist.md) still reserves the integrated behavior
changes for 0.8.0+ and protects all previously published RC history.

## Build and verification boundaries

`ApplicationReleaseVersion.java` drives Gradle metadata. A generated
`p2pkit-release.json` is embedded in APK assets and the Desktop application JAR,
carrying exact commit, canonical version and numeric mappings. The commit is a
task input, so another source cannot reuse its generated identity through a
cached task. Local builds without Git may carry `unknown`; release inspection
must reject that value and dirty source.

`scripts/application_release_version.py` independently derives verification
expectations. Java and Python share public test vectors, not implementation.
Package qualification must inspect the actual binary Android manifest,
MSI database, mounted DMG Info.plist, DEB control fields and embedded identity;
an AGP sidecar or GitHub Release title is insufficient. No installation,
application launch, signing, or physical-device acceptance follows from these
metadata checks. Development APK/installers retain their existing classification.

Changing the encoding later requires a reviewed migration that preserves
installer upgrade ordering. Do not silently wrap counters or truncate versions.
